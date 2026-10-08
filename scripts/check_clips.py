#!/usr/bin/env python3
"""Check continuity for every clip and every clip-to-clip boundary in data/prompt.json; optionally fix it.

Every boundary (clip N-1 -> clip N):
  continue   same moment: previous last frame referenced, handoff line present (see check_continuity.py)
  cut        new scene: a transition line names the cut, and time of day does not run backwards
             within an act (flagged as a note: it may be deliberate, e.g. leaving the story world)
Every clip:
  cast       every character who acts or speaks on screen has an image reference
  timing     dialogue fits the clip length (about 2.6 words per second, 4-15 s)
  ending     ends on a held frame and returns its last frame for the next clip

Fixes (--fix):
  missing cast   add the character's usual definition (up to 4 characters, never Jesus automatically)
  timing         lengthen the clip (format + api_params.duration) up to 15 s
  transitions    recorded in "continuity_transition" and rendered by add_continuity.py as the first shot's
                 Continuity line for scene openers
Then add_continuity.py, check_continuity.py, and check_camera.py are run.

Usage:
  python3 scripts/check_clips.py                 # check and print
  python3 scripts/check_clips.py --fix --dry-run # preview fixes
  python3 scripts/check_clips.py --fix           # apply fixes and rebuild
"""

import argparse
import json
import math
import re
import shutil
import string
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from check_continuity import ORDER, TAG, names_in
from fix_continuity import canonical_definitions
from paths import DATA

PROMPTS = DATA / "prompt.json"
HERE = Path(__file__).resolve().parent
WPS = 2.6
MAX_CHARACTERS = 4
TIME_ORDER = ["MORNING", "LATE MORNING", "DAY", "LATE AFTERNOON", "SUNSET", "EVENING"]


def time_of(scene):
    tail = scene.split("—")[-1].upper()
    for t in sorted(TIME_ORDER, key=len, reverse=True):
        if t in tail:
            return t
    return None


def place_of(scene):
    return string.capwords(re.sub(r"^(INT\.|EXT\.)\s*", "", scene.split("—")[0].split(" / ")[-1]).strip().lower())


def clip_chars(c):
    return [m.group(1) for s in c["subjects"] for m in [re.search(r" as (\w+)$", s)] if m]


def voices(c):
    a = next((x for x in c["audio"] if x.startswith("Voices:")), "")
    return set(re.findall(r"(\w+) \(voice-over\)", a))


def transition_text(prev, c):
    t = time_of(c["scene"])
    when = {"DAY": "daylight"}.get(t, f"{t.lower()} light") if t else ""
    return (f"New scene: cut from {place_of(prev['scene'])} ({prev['id']}) to {place_of(c['scene'])}"
            + (f", {when}" if when else "") + "; do not carry over the previous clip's framing")


def check(clips):
    """Return {clip id: [(level, kind, message)]} and the boundary table."""
    issues, boundaries = {c["id"]: [] for c in clips}, []
    last_time = {}
    for i, c in enumerate(clips):
        add = lambda lv, kind, msg, cid=c["id"]: issues[cid].append((lv, kind, msg))
        title = c["scene"] == "MAIN TITLES"
        chars = clip_chars(c)

        # cast: everyone who acts or speaks on screen has an image
        if not title:
            acting = set()
            for s in c["shot_details"]:
                acting |= names_in(TAG.sub("", s["action"]))
                acting |= {d["character"].split()[0].title() for d in s["dialogue"]} & set(ORDER)
            for n in sorted(acting - set(chars) - voices(c), key=ORDER.index):
                add("warn", "cast", f"{n} acts or speaks but has no image reference.")

        # timing
        words = sum(len(d["line"].split()) for s in c["shot_details"] for d in s["dialogue"])
        dur = c["api_params"]["duration"]
        if words and words / dur > WPS:
            add("warn", "timing", f"{words} words of dialogue in {dur}s (~{words / dur:.1f} words/s); needs about "
                                  f"{math.ceil(words / WPS)}s.")
        if not 4 <= dur <= 15:
            add("warn", "timing", f"Duration {dur}s is outside Seedance 2.0's 4-15 s.")

        # ending
        if not title and not any(x.startswith("End on a calm") for x in c["constraints"]):
            add("warn", "ending", "Missing the 'End on a calm, held frame' rule.")
        if not c["api_params"].get("return_last_frame"):
            add("warn", "ending", "api_params.return_last_frame is off; the next clip can't continue from it.")

        # boundary with the previous clip
        if i:
            prev = clips[i - 1]
            mode = c["continuity"]["mode"]
            row = {"from": prev["id"], "to": c["id"], "type": "continue" if mode == "continue_scene" else "cut",
                   "from_scene": prev["scene"], "to_scene": c["scene"], "status": "ok", "detail": ""}
            if mode == "continue_scene":
                row["detail"] = "same moment, starts from the previous last frame"
                if "Continue the same moment from" not in c["prompt"]:
                    add("warn", "boundary", "Continues a scene but has no handoff line.")
            elif not title:
                row["detail"] = f"cut: {place_of(prev['scene'])} → {place_of(c['scene'])}"
                if not c.get("continuity_transition"):
                    add("note", "boundary", f"Scene cut from {prev['id']} has no transition line.")
                t, act = time_of(c["scene"]), c["act"]
                if t and act in last_time and TIME_ORDER.index(t) < TIME_ORDER.index(last_time[act]):
                    add("note", "boundary", f"Time of day goes back from {last_time[act].lower()} to {t.lower()} "
                                            f"within {act}; fine if deliberate (e.g. leaving the story world).")
            row["status"] = "ok" if not [x for x in issues[c["id"]] if x[1] == "boundary"] else "issue"
            boundaries.append(row)
        t = time_of(c["scene"])
        if t:
            last_time[c["act"]] = t
    return issues, boundaries


def fix(data, dry_run):
    clips = data["clips"]
    defs = canonical_definitions(clips)
    issues, _ = check(clips)
    changes = []
    for i, c in enumerate(clips):
        for lv, kind, msg in issues[c["id"]]:
            if kind == "cast":
                name = msg.split()[0]
                if name == "Jesus" or name not in defs:
                    changes.append((c, f"skip {name}: add by hand (sacred figure or no definition)", None))
                elif len(clip_chars(c)) >= MAX_CHARACTERS:
                    changes.append((c, f"skip {name}: clip already has {MAX_CHARACTERS} characters", None))
                else:
                    changes.append((c, f"add {name} (acts or speaks in this clip)", ("cast", name)))
            elif kind == "timing" and "needs about" in msg:
                need = min(15, int(re.search(r"needs about (\d+)s", msg).group(1)))
                if need > c["api_params"]["duration"]:
                    changes.append((c, f"lengthen {c['api_params']['duration']}s → {need}s for the dialogue", ("dur", need)))
            elif kind == "boundary" and "no transition line" in msg:
                text = transition_text(clips[i - 1], c)
                changes.append((c, f"transition: {text}", ("trans", text)))
    print(f"{'Preview' if dry_run else 'Fixes'}: {sum(1 for _, _, a in changes if a)} change(s), "
          f"{sum(1 for _, _, a in changes if not a)} left for review")
    for c, desc, _ in changes:
        print(f"  {c['id']}: {desc}")
    if dry_run:
        return 0
    n = 0
    for c, desc, action in changes:
        if not action:
            continue
        kind, val = action
        if kind == "cast":
            c["subjects"].append(f"Define {defs[val]} in @Image 1 as {val}")
        elif kind == "dur":
            c["api_params"]["duration"] = c["duration_seconds"] = val
            c["format"] = re.sub(r"^\d+s", f"{val}s", c["format"])
        elif kind == "trans":
            c["continuity_transition"] = val
        c.setdefault("clip_fixes", []).append(desc)
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-rebuild", action="store_true")
    args = ap.parse_args()

    data = json.loads(PROMPTS.read_text(), strict=False)
    if args.fix:
        n = fix(data, args.dry_run)
        if n:
            backup = DATA / "backups" / f"prompt.{datetime.now():%Y%m%d-%H%M%S}.json"
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PROMPTS, backup)
            PROMPTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            print(f"Saved {PROMPTS.name} (backup: {backup.relative_to(DATA.parent)})")
        if n and not args.no_rebuild:
            for script in ("add_continuity.py", "check_continuity.py", "check_camera.py"):
                subprocess.run([sys.executable, str(HERE / script)], check=True)
            data = json.loads(PROMPTS.read_text(), strict=False)
        if args.dry_run:
            return

    issues, boundaries = check(data["clips"])
    bad = {k: v for k, v in issues.items() if v}
    print(f"Checked {len(data['clips'])} clips and {len(boundaries)} boundaries "
          f"({sum(b['type'] == 'continue' for b in boundaries)} continue, {sum(b['type'] == 'cut' for b in boundaries)} cuts): "
          f"{len(data['clips']) - len(bad)} clips clean")
    for cid, items in bad.items():
        for lv, kind, msg in items:
            print(f"  {'⚠' if lv == 'warn' else 'ℹ'} {cid} [{kind}] {msg}")


if __name__ == "__main__":
    main()
