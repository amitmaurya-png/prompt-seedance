#!/usr/bin/env python3
"""Make every continuing clip open on exactly the characters in the previous clip's last frame.

For each clip that continues from a last-frame image (@Image N), shot 1's Continuity line gets:
  "; open on exactly the characters visible in @Image N, each in the same screen position, and add no one
   who is not in @Image N to the opening frame"
and, when the clip has named characters who were not on screen at the end of the previous clip (they enter
during this clip, e.g. "Ima appears from the doorway"):
  "; Ima is not in @Image N: keep Ima out of the opening frame until the action brings them in"
plus the constraint "Opening frame: only the characters visible in @Image N, in the same screen positions".

Who was on screen at the end of the previous clip follows keep_present.py: its subjects and still-present
characters (not voice-over only), minus anyone its action takes off screen. Run keep_present.py first.
Safe to run more than once. A backup is saved to data/backups/ and the camera report is rebuilt.

Usage:
  python3 scripts/strict_opening.py --dry-run
  python3 scripts/strict_opening.py
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from keep_present import ORDER, exits, join, subjects, voice_only
from paths import DATA

PROMPTS = DATA / "prompt.json"
HERE = Path(__file__).resolve().parent
MARK = "open on exactly the characters visible in"
MATCH = "Match lighting, positions, props, and character appearance to"


def on_screen_at_end(clip):
    have = subjects(clip)
    present = [n for n in have if not voice_only(clip, n)]
    present += [n for n in clip.get("still_present_names", []) if n not in present]
    gone = exits(clip, present)
    return [n for n in present if n not in gone]


def plan(clips):
    """[(clip, last-frame tag, newcomers)] for every continuing clip without the rule yet."""
    out = []
    for prev, clip in zip(clips, clips[1:]):
        tag = clip["continuity"].get("last_frame_reference")
        if clip["continuity"]["mode"] == "new_scene" or not tag or MARK in clip["prompt"]:
            continue
        before = on_screen_at_end(prev)
        new = [n for n in subjects(clip) if n in ORDER and n not in before
               and n not in clip.get("still_present_names", [])]
        out.append((clip, tag, new))
    return out


def apply(clip, tag, new):
    note = f"; {MARK} {tag}, each in the same screen position, and add no one who is not in {tag} to the opening frame"
    if new:
        names = join(new)
        verb = "is" if len(new) == 1 else "are"
        who = new[0] if len(new) == 1 else "them"
        note += f"; {names} {verb} not in {tag}: keep {who} out of the opening frame until the action brings them in"
    m = re.search(r"(?m)^  Continuity: (.*)$", clip["prompt"])
    assert m, clip["id"]
    old = m.group(1)
    clip["prompt"] = clip["prompt"].replace(f"  Continuity: {old}", f"  Continuity: {old}{note}", 1)
    if old in clip["shots"][0]:
        clip["shots"][0] = clip["shots"][0].replace(old, old + note, 1)

    rule = f"Opening frame: only the characters visible in {tag}, in the same screen positions"
    if rule not in clip["constraints"]:
        anchor = next((c for c in clip["constraints"] if c.startswith(MATCH)), None)
        i = clip["constraints"].index(anchor) + 1 if anchor else len(clip["constraints"])
        clip["constraints"].insert(i, rule)
        if anchor and f"- {anchor}\n" in clip["prompt"]:
            clip["prompt"] = clip["prompt"].replace(f"- {anchor}\n", f"- {anchor}\n- {rule}\n", 1)
            if "global_direction" in clip:
                clip["global_direction"] = clip["global_direction"].replace(f"{anchor}.", f"{anchor}. {rule}.", 1)
    clip.setdefault("continuity_fixes", []).append(
        "Strict opening: only the characters in the last frame" + (f"; kept out until they enter: {join(new)}" if new else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(PROMPTS.read_text(encoding="utf-8"), strict=False)
    todo = plan(data["clips"])
    for clip, tag, new in todo:
        if new:
            print(f"{clip['id']}: kept out of the opening frame: {', '.join(new)}")
    print(f"{len(todo)} continuing clips get the strict opening ({sum(bool(n) for *_, n in todo)} with newcomers)")
    if args.dry_run or not todo:
        return

    backup = DATA / "backups" / f"prompt.{datetime.now():%Y%m%d-%H%M%S}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PROMPTS, backup)
    for clip, tag, new in todo:
        apply(clip, tag, new)
    PROMPTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {PROMPTS.relative_to(DATA.parent)} (backup: {backup.relative_to(DATA.parent)})")
    subprocess.run([sys.executable, str(HERE / "check_camera.py")], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
