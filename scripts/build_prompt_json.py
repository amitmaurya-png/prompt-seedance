#!/usr/bin/env python3
"""Build data/prompt.json from data/breakdown.json, keeping every action and dialogue line verbatim.

No AI model is used.
  1. Each scene's shots are grouped into Seedance clips of 4-15 s (about 28 spoken words and up to 3 shots
     per clip). A shot whose dialogue is too long for one clip is split across clips.
  2. For every shot: the action paragraphs are copied word for word, in the screenplay's order, nothing added.
     When long dialogue is split across clips, only the first part carries the action. Dialogue is copied word
     for word with its parenthetical (e.g. SOFTLY) and voice-over flag. The scene is the screenplay heading.
  3. A camera line is suggested from the shot's genre and mood (camera_suggest.py, camera-knowledge rules).
  4. Characters for the image references: speakers first, then characters in the action (max 4).
Then run add_continuity.py (references, continuity, prompt text) and the other skills' scripts; see --all.

Usage:
  python3 scripts/build_prompt_json.py --dry-run     # summary only
  python3 scripts/build_prompt_json.py               # write data/prompt.json (backup saved)
  python3 scripts/build_prompt_json.py --all         # write, then emotions, eyelines, continuity, fixes, reports
"""

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from camera_suggest import genre_for, suggest
from paths import DATA

HERE = Path(__file__).resolve().parent
BREAKDOWN, PROMPTS = DATA / "breakdown.json", DATA / "prompt.json"

MAX_WORDS, MAX_SHOTS, MAX_CHARS, WPS = 28, 3, 4, 2.6
STYLE = ("Warm, stylized 3D storybook animation (feature-film CG), soft global illumination, gentle natural light, "
         "rich hand-crafted textures, HD, rich details, heartfelt tone with light comedy")
RENDER_3D = "Render everything in stylized 3D animation; use the reference images for character design only, not for their 2D drawing style"
ROSTER = ["Miri", "Nim", "Saba", "Ima", "Tav", "Yonah", "Andrew", "Philip", "Jesus"]
CHAR_DEF = {
    "Miri": "the young village girl", "Nim": "the small fox", "Saba": "the elderly storyteller",
    "Ima": "the mother", "Tav": "the small village boy", "Yonah": "the boy with the lunch bundle",
    "Andrew": "the kind, steady disciple", "Philip": "the worried, practical disciple",
    "Jesus": "the robed figure (hands, robe, and silhouette only)",
}
# scene heading -> (location label, scene description, ambience)
LOCATIONS = {
    "EXT. MIRI’S VILLAGE — MORNING": ("Miri's village", "Miri's village lane and doorway, morning light, low stone walls",
                                      "morning birdsong, distant village chatter, footsteps on dirt"),
    "EXT. VILLAGE LANE — MOMENTS LATER": ("village lane", "Narrow village lane beside a low wall, bright late-morning light",
                                          "light breeze, distant village sounds"),
    "MAIN TITLES": ("title card", "Painted parchment title card on a warm, textured background", "gentle storybook music swell"),
    "EXT. SABA ELIOR’S COURTYARD — LATE MORNING": ("Saba's courtyard", "Saba Elior's courtyard beneath a large fig tree, dappled late-morning light",
                                                   "rustling fig leaves, children's voices"),
    "INT. SABA’S HOUSE — CONTINUOUS": ("Saba's house", "Warm, crowded room of Saba's house with a faded hanging cloth leading to the scroll room",
                                       "creak of old wood, soft rustle of cloth"),
    "INT. SCROLL ROOM — CONTINUOUS": ("scroll room", "Scroll room lined with endless shelves of old scrolls, dusty warm light",
                                      "quiet room tone, parchment rustle"),
    "EXT. GALILEAN HILLSIDE — DAY": ("Galilean hillside", "Sunlit Galilean hillside above a lake, filled with families and disciples",
                                     "large crowd murmur, wind over grass, distant lake"),
    "EXT. HILLSIDE PATH — CONTINUOUS": ("hillside path", "Hillside path winding through the crowd, bright daylight",
                                        "crowd murmur, footsteps on grass"),
    "EXT. EDGE OF CROWD — LATER": ("edge of the crowd", "Small grassy rise at the edge of the crowd, afternoon light",
                                   "soft crowd murmur, wind"),
    "EXT. NEAR JESUS — CONTINUOUS": ("near Jesus", "Open grass near Jesus at the heart of the crowd, daylight",
                                     "crowd hush, rustle of people sitting"),
    "EXT. HILLSIDE — MOMENTS LATER": ("Galilean hillside", "Sunlit hillside where thousands sit in clusters on green grass",
                                      "large crowd murmur, wind over grass"),
    "EXT. HILLSIDE — LATE AFTERNOON": ("Galilean hillside", "Hillside in late-afternoon light, the crowd resting after eating",
                                       "contented crowd murmur, wicker baskets"),
    "EXT. HILLSIDE — CONTINUOUS": ("Galilean hillside", "Hillside in late-afternoon light, baskets filling with leftover bread",
                                   "contented crowd murmur, wicker baskets"),
    "EXT. HILLSIDE RIDGE — SUNSET": ("hillside ridge", "Hillside ridge at sunset overlooking the crowd and the lake",
                                     "gentle wind, fading crowd, evening birds"),
    "INT. SCROLL ROOM — LATE AFTERNOON": ("scroll room", "Scroll room lined with old scrolls, late-afternoon light from a small window",
                                          "quiet room tone, parchment rustle"),
    "EXT. VILLAGE LANE — SUNSET": ("village lane", "Village lane beside the low wall at sunset, long golden shadows",
                                   "evening birds, soft breeze"),
    "EXT. SABA’S COURTYARD — EVENING": ("Saba's courtyard", "Saba's courtyard beneath the fig tree in evening light, first lamps glowing",
                                        "crickets, rustling leaves"),
}
NAME_RE = re.compile(r"\b(" + "|".join(ROSTER) + r")\b", re.I)
PERSON_RE = re.compile(r"\b(" + "|".join(ROSTER) + r"|he|she|they|his|her|children|child|girl|boy|mother|"
                       r"disciples?|crowd|people|families|everyone|someone)\b", re.I)


def words(dialogue):
    return sum(len(d["line"].split()) for d in dialogue)


def title_for(text, dialogue):
    src = text or (dialogue[0]["line"] if dialogue else "")
    first = re.split(r"(?<=[.!?])\s+", src.strip())[0] if src else "Moment"
    title = " ".join(first.split()[:6]).rstrip(".,;:!?")
    # screenplay first mentions are in capitals ("MIRI stops"): keep names, soften other all-caps words
    title = " ".join(w.title() if w.isupper() and len(w) > 1 else w for w in title.split())
    return title[0].upper() + title[1:] if title else "Moment"


MEMORY_RE = re.compile(r"\b(remembers?|imagines?|imagining|thinks? of|thinking of|pictures?)\b[^.]*", re.I)


def names_in(text):
    """Characters present in an action; names inside a memory ("She remembers Tav's face") don't count."""
    return {m.group(1).title() for m in NAME_RE.finditer(MEMORY_RE.sub("", text or ""))}


def needed(units):
    """Every named character a group of shots needs on screen (speakers, except voice-over, and actors)."""
    out = set()
    for u in units:
        out |= {d["character"].split()[0].title() for d in u["dialogue"] if not d.get("voice_over")} & set(ROSTER)
        out |= names_in(u["action_text"])
    return out


def shot_units(scene):
    """Breakdown shots, with long dialogue split so every unit fits one clip."""
    units = []
    for sh in scene["shots"]:
        parts, cur = [], []
        for d in sh["dialogue"]:
            if cur and words(cur) + len(d["line"].split()) > MAX_WORDS:
                parts.append(cur)
                cur = []
            cur.append(d)
        parts.append(cur)
        for i, part in enumerate(parts):
            speakers = list(dict.fromkeys(d["character"].split()[0].title() for d in part))
            # the screenplay's action belongs to the first part only; later parts are dialogue only (nothing invented)
            action_text = sh["action"] if i == 0 else ""
            units.append({"order": sh["order"], "part": i + 1, "of": len(parts), "action_text": action_text, "dialogue": part,
                          "line_from": sum(len(p) for p in parts[:i]) + 1})
    return units


def group(units):
    clips, cur = [], []
    for u in units:
        w = words(u["dialogue"])
        if cur and (len(cur) >= MAX_SHOTS or words([d for x in cur for d in x["dialogue"]]) + w > MAX_WORDS
                    or estimate(cur + [u]) > 15 or len(needed(cur + [u])) > MAX_CHARS):
            clips.append(cur)
            cur = []
        cur.append(u)
    if cur:
        clips.append(cur)
    return clips


def estimate(units):
    w = words([d for u in units for d in u["dialogue"]])
    action_w = sum(len(u["action_text"].split()) for u in units)
    return max(5, min(15, math.ceil(w / WPS + 1.5 * len(units) + action_w / 25)))


def characters(units):
    speak, seen = [], []
    for u in units:
        for d in u["dialogue"]:
            n = d["character"].split()[0].title()
            if n in ROSTER and not d.get("voice_over") and n not in speak:
                speak.append(n)
        for n in sorted(names_in(u["action_text"]), key=ROSTER.index):
            if n not in seen:
                seen.append(n)
    chosen = list(dict.fromkeys(speak + seen))[:MAX_CHARS]
    return sorted(chosen, key=ROSTER.index)


def build(breakdown):
    clips, n = [], 0
    prev_scene = None
    for act in breakdown["acts"]:
        for scene in act["scenes"]:
            heading = scene["scene"]
            loc_name, loc_desc, ambience = LOCATIONS.get(heading, ("location", heading.title(), "ambient sound"))
            genre = genre_for(heading)
            for ci, units in enumerate(group(shot_units(scene))):
                n += 1
                chars = characters(units)
                title_card = heading == "MAIN TITLES"
                cast = [{"name": c, "role": "in shot"} for c in chars]
                shots = []
                for k, u in enumerate(units):
                    action, visual = u["action_text"], ""  # verbatim, in the screenplay's order
                    if title_card:  # mark the title words as on-screen text; the action stays verbatim
                        visual = "Title text reads: LITTLE WITNESSES “THE SMALLEST LUNCH”"
                    dlg = [{k2: v for k2, v in d.items()} for d in u["dialogue"]]
                    sug = suggest(title_for(u["action_text"], dlg), action, visual,
                                  [{"speaker": d["character"].title(), "line": d["line"]} for d in dlg],
                                  cast, "title" if title_card else genre,
                                  opens_scene=(ci == 0 and k == 0 and heading != prev_scene))
                    title = "Main titles" if title_card else title_for(u["action_text"], dlg)
                    if not u["action_text"] and u["part"] > 1:
                        title = f"{title_for('', dlg)} (dialogue continues, part {u['part']} of {u['of']})"
                    shots.append({"title": title,
                                  "camera": sug["line"], "action": action, "visual": visual, "dialogue": dlg})
                dur = estimate(units)
                loc_img = len(chars) + 1
                refs = [f"@Image {i}: {c} character reference" if c != "Jesus"
                        else f"@Image {i}: Jesus reference (robe, hands, silhouette only)" for i, c in enumerate(chars, 1)]
                refs.append(f"@Image {loc_img}: {loc_name} {'style' if title_card else 'scene'} reference")
                constraints = ["One camera move per shot"]
                if title_card:
                    constraints += ["Render only the title text in 【 】, exactly as written, clearly legible",
                                    "Do not generate a logo; do not generate a watermark"]
                else:
                    constraints += [RENDER_3D,
                                    "Faces and body proportions stay stable without deformation; movements are slow, "
                                    "natural, and smooth, with no stutter or flicker"]
                    if "Nim" in chars:
                        constraints.append("Nim is a small fox, never a dog")
                    if len(chars) > 1:
                        constraints.append("Each character appears only once; no duplicate or twin characters")
                    if "Jesus" in chars:
                        constraints.append("Jesus: show only his hands, robe, and silhouette; never show his face")
                clips.append({
                    "id": f"clip-{n:02d}", "act": act["act"], "scene": heading,
                    "source": [{"scene": heading, "shot": u["order"], "part": u["part"],
                                "lines": list(range(u["line_from"], u["line_from"] + len(u["dialogue"])))} for u in units],
                    "duration_seconds": dur,
                    "api_params": {"model": "dreamina-seedance-2-0-260128", "ratio": "16:9", "duration": dur,
                                   "generate_audio": True, "watermark": False, "return_last_frame": True},
                    "format": f"{dur}s / 16:9 / " + ("one continuous shot" if len(shots) == 1 else f"{len(shots)} shots / soft cuts"),
                    "style": STYLE,
                    "references": refs,
                    "subjects": [f"Define {CHAR_DEF[c]} in @Image {i} as {c}" for i, c in enumerate(chars, 1)]
                                or [f"A painted parchment title card in the style of @Image {loc_img}"],
                    "scene_setting": f"{heading} (@Image {loc_img})",
                    "shot_details": shots,
                    "audio": ["Music: （a gentle storybook theme）", "No dialogue"] if title_card
                             else ["Music: （a soft, warm storybook score）"],
                    "constraints": constraints,
                    "continuity": {"mode": "new_scene"},
                })
            prev_scene = heading
    return clips


def carry_manual_emotions(old_path, data):
    """Reapply hand-reviewed emotions and addressees from the previous prompt.json, matched by speaker and line."""
    try:
        old = json.loads(Path(old_path).read_text(), strict=False)
    except (OSError, ValueError):
        return 0
    manual = {(d["character"], d["line"]): d for c in old.get("clips", []) for s in c["shot_details"]
              for d in s["dialogue"] if d.get("emotion_source") == "manual" or d.get("addressee_source") == "manual"}
    n = 0
    for c in data["clips"]:
        for s in c["shot_details"]:
            for d in s["dialogue"]:
                m = manual.get((d["character"], d["line"]))
                if m:
                    keys = []
                    if m.get("emotion_source") == "manual":
                        keys += ["emotion", "intensity", "delivery", "emotion_evidence", "emotion_source"]
                    if m.get("addressee_source") == "manual":
                        keys += ["addressee", "addressee_source", "addressee_reason"]
                    for key in keys:
                        if key in m:
                            d[key] = m[key]
                    n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--all", action="store_true", help="also run continuity, emotions, fixes, and reports")
    args = ap.parse_args()

    breakdown = json.loads(BREAKDOWN.read_text())
    clips = build(breakdown)
    data = {"source": "breakdown.json", "builder": "build_prompt_json.py (verbatim actions and dialogue, no AI)",
            "skill": "seedance-prompting", "syntax": ".github/skills/seedance-prompting/references/prompt_syntax.md",
            "clip_count": len(clips), "total_seconds": sum(c["duration_seconds"] for c in clips), "clips": clips}

    shots = [s for c in clips for s in c["shot_details"]]
    lines = [d for s in shots for d in s["dialogue"]]
    want = [d["line"] for a in breakdown["acts"] for sc in a["scenes"] for sh in sc["shots"] for d in sh["dialogue"]]
    assert [d["line"] for d in lines] == want, "dialogue must match breakdown.json exactly, in order"
    print(f"{len(clips)} clips ({data['total_seconds']}s), {len(shots)} shots, {len(lines)} dialogue lines "
          f"(identical to breakdown.json), max {max(len(c['subjects']) for c in clips)} characters per clip")
    if args.dry_run:
        return

    backup = DATA / "backups" / f"prompt.{datetime.now():%Y%m%d-%H%M%S}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if PROMPTS.exists():
        shutil.copy2(PROMPTS, backup)
    carried = carry_manual_emotions(backup, data)
    PROMPTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"Saved {PROMPTS.relative_to(DATA.parent)} (backup: {backup.relative_to(DATA.parent)}); "
          f"carried over {carried} hand-reviewed emotions")

    steps = ["add_continuity.py"]
    if args.all:
        steps = [["detect_emotions.py", "--no-rebuild"], "add_continuity.py", ["add_eyelines.py", "--no-rebuild"], ["fix_continuity.py", "--no-rebuild"],
                 ["check_clips.py", "--fix", "--no-rebuild"], "add_continuity.py", "check_continuity.py", "check_camera.py"]
    for step in steps:
        cmd = step if isinstance(step, list) else [step]
        subprocess.run([sys.executable, str(HERE / cmd[0]), *cmd[1:]], check=True)


if __name__ == "__main__":
    main()
