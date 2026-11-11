#!/usr/bin/env python3
"""Say where each shot's main character sits in the frame, next to its camera line.

For every shot in data/prompt.json this picks the main character and writes a "Placement:" line under the
shot's "Camera:" line, e.g.

  Camera: Medium close-up, static on Saba
  Placement: Saba is the main subject, framed on the left third of the frame, facing right, with open space on the right

Main character, in order: the camera's subject ("on Saba", "onto Miri", "tracking with Miri"), the first speaker,
the first character named in the action, then Miri. A shot whose placement has "source": "manual" is kept.

Where they sit comes from the scene's fixed screen positions (SCENE_POSITIONS, the same sides as the CONTINUITY
notes in add_continuity.py), so every shot of a scene keeps each character on the same side (180° rule).
How they sit depends on the shot type:
  single (close-up, medium close-up on one person)  main on their side's third, facing the others, lead room ahead
  over-the-shoulder onto X                           X in focus on their third, the other's shoulder soft in front
  two-/three-shot, medium, wide                      main on their third, the others on theirs; wide keeps main clear
  tracking in a scene with travel                    main moving in the scene's direction, space ahead of them

Writes shot["placement"] = {"main", "line", "source"}, the Placement line in the prompt, and the shot text in
"shots". Safe to run more than once.

Usage:
  python3 scripts/add_placement.py              # every shot
  python3 scripts/add_placement.py --dry-run    # print the lines without writing
  python3 scripts/add_placement.py --clip clip-14 clip-15
"""

import argparse
import json
import re

from paths import DATA

PROMPTS = DATA / "prompt.json"

# side: "left" / "right" / "center" / "background", or ("with", other) to sit beside another character.
# "between" sits low in the middle, between the two sides.
SCENE_POSITIONS = {
    "EXT. MIRI’S VILLAGE — MORNING": {"Miri": "left", "Ima": "right", "Nim": ("with", "Miri")},
    "EXT. VILLAGE LANE — MOMENTS LATER": {"Miri": "left", "Nim": ("with", "Miri"), "Tav": "right",
                                         "_travel": "left to right"},
    "EXT. SABA ELIOR’S COURTYARD — LATE MORNING": {"Saba": "left", "Miri": "right", "Nim": "between"},
    "INT. SABA’S HOUSE — CONTINUOUS": {"Saba": "right", "Miri": "left", "Nim": ("with", "Miri"),
                                       "_travel": "left to right"},
    "INT. SCROLL ROOM — CONTINUOUS": {"Saba": "right", "Miri": "left", "Nim": ("with", "Miri")},
    "EXT. GALILEAN HILLSIDE — DAY": {"Miri": "left", "Nim": ("with", "Miri"), "Jesus": "center-right", "Child": "right"},
    "EXT. HILLSIDE PATH — CONTINUOUS": {"Miri": "left", "Yonah": "right", "Nim": "between", "Andrew": "right",
                                        "Philip": "left", "_travel": "left to right"},
    "EXT. EDGE OF CROWD — LATER": {"Miri": "left", "Yonah": "right", "Nim": "between", "Andrew": "right"},
    "EXT. NEAR JESUS — CONTINUOUS": {"Jesus": "center-right", "Andrew": "left", "Yonah": "left", "Miri": "left",
                                     "Nim": ("with", "Miri"), "Philip": "right"},
    "EXT. HILLSIDE — MOMENTS LATER": {"Miri": "left", "Andrew": "right", "Yonah": ("with", "Miri"),
                                      "Nim": ("with", "Miri"), "Jesus": "center-right", "Small Girl": "right",
                                      "Mother In Crowd": ("with", "Small Girl")},
    "EXT. HILLSIDE — LATE AFTERNOON": {"Miri": "left", "Yonah": "right", "Andrew": "background"},
    "EXT. HILLSIDE — CONTINUOUS": {"Miri": "left", "Yonah": "right", "Nim": "between", "Andrew": "right"},
    "EXT. HILLSIDE RIDGE — SUNSET": {"Miri": "left", "Nim": ("with", "Miri"), "Yonah": "right", "Saba": "right"},
    "INT. SCROLL ROOM — LATE AFTERNOON": {"Saba": "right", "Miri": "left", "Nim": ("with", "Miri")},
    "EXT. VILLAGE LANE — SUNSET": {"Tav": "right", "Miri": "left", "Nim": ("with", "Miri"),
                                   "Ima": "background", "Saba": "background"},
    "EXT. SABA’S COURTYARD — EVENING": {"Saba": "left", "Miri": "right", "Nim": "between"},
}
OPPOSITE = {"left": "right", "right": "left"}
NAME = r"[A-Z][a-z]+"


def clip_characters(clip):
    """Named characters ('Miri', 'Small Girl'); groups such as 'the children (a group)' are left out."""
    names = []
    for s in clip["subjects"]:
        m = re.search(r" as ([A-Z][\w ]*)$", s)
        if m and "(a group)" not in s:
            names.append(m.group(1).strip())
    return names


def named_in(text, chars):
    """Characters named in text, in order of first mention."""
    hits = []
    for ch in chars:
        m = re.search(rf"\b{ch}\b", text, re.I)
        if m:
            hits.append((m.start(), ch))
    return [ch for _, ch in sorted(hits)]


def shoulder_owner(camera):
    m = re.search(r"over (?:the )?([\w ]+?)['’]s shoulder", camera, re.I)
    return m.group(1) if m else None


def camera_subject(camera, chars):
    """The character the camera is aimed at: 'onto Miri', 'on Saba', 'tracking with Miri', 'toward the small girl'."""
    owner = (shoulder_owner(camera) or "").lower()
    for m in re.finditer(r"\b(?:onto|on|with|toward|towards|follows?|following)\s+(?:the\s+)?([\w’' ]+)", camera, re.I):
        target = m.group(1)
        hits = [ch for ch in named_in(target, chars) if ch.lower() != owner]
        if hits and re.match(rf"{re.escape(hits[0])}\b", target, re.I):
            return hits[0]
    return None


def shot_kind(camera):
    c = camera.lower()
    if "shoulder" in c:
        return "ots"
    if re.search(r"two-shot|three-shot|group shot", c):
        return "group"
    if re.search(r"\b(wide|long|establishing|aerial|crane)\b", c) and "close" not in c:
        return "wide"
    if "close-up" in c:
        return "single"
    return "group"


def side_of(ch, pos, main=None, main_side=None):
    s = pos.get(ch)
    if isinstance(s, tuple):
        return side_of(s[1], pos)
    if s:
        return s
    # not placed in this scene: across from the main character, else centered
    return OPPOSITE.get(main_side, "center") if ch != main else "center"


def where(ch, pos, main=None, main_side=None):
    """Words for where a supporting character sits."""
    s = pos.get(ch)
    if isinstance(s, tuple):
        return f"{ch} beside {s[1]}"
    if s == "between":
        return f"{ch} low in the middle between them"
    if s == "background":
        return f"{ch} in the background"
    side = side_of(ch, pos, main_side=main_side)
    if main and side == main_side and side in OPPOSITE:
        return f"{ch} beside {main}"
    if side == "center-right":
        return f"{ch} center-right"
    return f"{ch} on the {side} third" if side in OPPOSITE else f"{ch} in the center"


def placement(clip, shot):
    chars = clip_characters(clip)
    pos = SCENE_POSITIONS.get(clip["scene"], {})
    if not chars or not pos:
        return None
    camera = shot["camera"]
    kind = shot_kind(camera)
    owner = (shoulder_owner(camera) or "").lower() if kind == "ots" else ""
    speakers = [d["character"].title() for d in shot["dialogue"]
                if d["character"].title() in chars and d["character"].lower() != owner]
    in_action = [ch for ch in named_in(shot["action"], chars) if ch.lower() != owner]
    behind = re.search(r"from behind ([A-Z]\w+)", camera)
    behind = behind.group(1) if behind and behind.group(1) in chars else None
    lead_role = "Miri" if kind == "wide" and "Miri" in in_action else None  # wide shots favour the heroine
    main = (behind or camera_subject(camera, chars) or lead_role or (speakers[0] if speakers else None)
            or (in_action[0] if in_action else None) or ("Miri" if "Miri" in chars and owner != "miri" else chars[0]))
    if pos.get(main) == "background" and "Miri" in in_action and main != "Miri":
        main = "Miri"  # keep the foreground character as the main subject
    if main not in pos and main != "Jesus":
        # not placed in this scene: across from the first placed character in the shot
        placed = [ch for ch in speakers + in_action if ch != main and side_of(ch, pos) in OPPOSITE]
        pos = dict(pos, **{main: OPPOSITE[side_of(placed[0], pos)] if placed else "center"})

    raw = pos.get(main)
    side = side_of(main, pos)
    travel = pos.get("_travel") if re.search(r"track|follow", camera, re.I) else None

    if main == "Jesus":
        line = "Jesus is the main subject, seen only from behind, as hands, robe or silhouette, center-right of the frame"
        if kind == "ots" and owner:
            line += f"; {owner.title() if owner in [c.lower() for c in chars] else 'the ' + owner}'s shoulder soft in the left foreground"
        return main, line

    if raw == "between" or (main == "Nim" and isinstance(raw, tuple)):
        anchor = f" on {raw[1]}'s side ({side_of(main, pos)} third)" if isinstance(raw, tuple) else " in the middle"
        lead = f"{main} is the main subject, low in the frame{anchor}, at the characters' feet"
    elif side in OPPOSITE:
        third = f"on the {side} third of the frame"
        lead = f"{main} is the main subject, {'in focus ' if kind == 'ots' else ''}{'seen from behind ' if behind == main else ''}{third}"
        if travel:
            lead += f", moving {travel} with open space ahead"
        elif kind in ("single", "ots"):
            lead += f", facing {OPPOSITE[side]}, with open space on the {OPPOSITE[side]}"
    elif side == "background":
        lead = f"{main} is the main subject, in the background in the center of the frame"
    else:
        lead = f"{main} is the main subject, framed in the center"

    others = []
    if kind == "ots" and owner:
        who = owner.title() if owner in [c.lower() for c in chars] else "the " + owner
        others.append(f"{who}'s shoulder soft in the {OPPOSITE.get(side, 'left')} foreground")
    elif kind in ("group", "wide"):
        named = [ch for ch in dict.fromkeys(speakers + in_action + named_in(camera, chars)) if ch != main]
        named += [d["addressee"] for d in shot["dialogue"]
                  if d.get("addressee") in chars and d["addressee"] not in named and d["addressee"] != main]
        for ch in list(named):  # someone placed beside another: name that one too
            anchor = pos.get(ch)
            if isinstance(anchor, tuple) and anchor[1] != main and anchor[1] not in named and anchor[1] in chars:
                named.insert(named.index(ch), anchor[1])
        others = [where(ch, pos, main, side) for ch in named]
        if kind == "wide":
            lead += ", small but clear against the setting"
    line = lead + ("; " + "; ".join(others) if others else "")
    return main, line


def render(clip):
    """Put each shot's Placement line under its Camera line in the prompt and the shot text."""
    shots = clip["shot_details"]
    out, n = [], 0
    for line in clip["prompt"].split("\n"):
        if line.startswith("  Placement: "):
            continue
        m = re.match(r"(?:\[[^\]]*\] )?Shot (\d+):", line)
        if m:
            n = int(m.group(1))
        out.append(line)
        if line.startswith("  Camera: ") and 0 < n <= len(shots) and shots[n - 1].get("placement"):
            out.append(f"  Placement: {shots[n - 1]['placement']['line']}")
    clip["prompt"] = "\n".join(out)

    if "shots" in clip:
        for i, s in enumerate(shots):
            if i >= len(clip["shots"]):
                break
            text = re.sub(r" Placement: [^.]*\.", "", clip["shots"][i])
            cam = s["camera"].rstrip(".") + "."
            if s.get("placement") and cam in text:
                text = text.replace(cam, f"{cam} Placement: {s['placement']['line']}.", 1)
            clip["shots"][i] = text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clip", nargs="*", help="clip ids (default: all)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(PROMPTS.read_text(encoding="utf-8"), strict=False)
    wanted = set(args.clip or [])
    count = 0
    for clip in data["clips"]:
        if wanted and clip["id"] not in wanted:
            continue
        for i, shot in enumerate(clip["shot_details"], 1):
            if (shot.get("placement") or {}).get("source") == "manual":
                continue
            got = placement(clip, shot)
            if not got:
                shot.pop("placement", None)
                continue
            main_ch, line = got
            shot["placement"] = {"main": main_ch, "line": line, "source": "auto"}
            count += 1
            if args.dry_run:
                print(f"{clip['id']}:{i}  [{shot['camera']}]\n    {line}")
        render(clip)

    if args.dry_run:
        print(f"{count} shots (dry run, nothing written)")
        return
    PROMPTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Placement written for {count} shots in {PROMPTS.relative_to(DATA.parent)}")


if __name__ == "__main__":
    main()
