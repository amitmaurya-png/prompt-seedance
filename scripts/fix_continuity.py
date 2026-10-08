#!/usr/bin/env python3
"""Fix continuity breaks between clips in data/prompt.json, then rebuild prompts and reports.

Runs the same checks as check_continuity.py and applies these fixes:
  vanishing   a character in the last shot of a clip has no image in the next clip of the same scene:
              add them to that clip (same description as elsewhere) and name them in the handoff line,
              unless the clip already has 4 characters or the character is Jesus (shown only from behind,
              never carried into another clip automatically)
  chain/state missing last-frame references, handoff lines, match rules, CONTINUITY blocks, or music cues
              are rebuilt by add_continuity.py

Every change is recorded on the clip ("continuity_added", "continuity_fixes"), a backup is saved to
data/backups/, and afterwards add_continuity.py, check_continuity.py, and check_camera.py are run.

Usage:
  python3 scripts/fix_continuity.py --dry-run        # preview
  python3 scripts/fix_continuity.py                  # apply
  python3 scripts/fix_continuity.py --scene PATH     # one scene
  python3 scripts/fix_continuity.py --skip clip-60:Miri,clip-60:Tav   # leave deliberate cuts alone
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from check_continuity import ORDER, TAG, group_scenes, names_in
from paths import DATA

PROMPTS = DATA / "prompt.json"
HERE = Path(__file__).resolve().parent
MAX_CHARACTERS = 4
NEVER_CARRY = {"Jesus"}


def canonical_definitions(clips):
    """Most common 'Define <description> in @Image N as <Name>' description for each character."""
    seen = defaultdict(lambda: defaultdict(int))
    for c in clips:
        for s in c["subjects"]:
            m = re.search(r"^Define (.+) in @Image \d+ as (\w+)$", s)
            if m:
                seen[m.group(2)][m.group(1)] += 1
    return {name: max(descs, key=descs.get) for name, descs in seen.items()}


def plan(clips, scene_filter="", skip=()):
    defs = canonical_definitions(clips)
    fixes = []  # (clip, name, reason)
    for scene in group_scenes(clips):
        if scene_filter and scene_filter.upper() not in scene["heading"].upper():
            continue
        for prev, clip in zip(scene["clips"], scene["clips"][1:]):
            end = TAG.sub("", prev["shot_details"][-1]["action"])
            have = {m.group(1) for x in clip["subjects"] for m in [re.search(r" as (\w+)$", x)] if m}
            for name in sorted(names_in(end) - have, key=ORDER.index):
                if (clip["id"], name) in skip:
                    continue
                if name in NEVER_CARRY:
                    fixes.append((clip, name, "skip", "Jesus is never carried into another clip automatically"))
                elif len(have) >= MAX_CHARACTERS:
                    fixes.append((clip, name, "skip", f"clip already has {MAX_CHARACTERS} characters"))
                elif name not in defs:
                    fixes.append((clip, name, "skip", "no reference description for this character"))
                else:
                    fixes.append((clip, name, "add", f"in the last shot of {prev['id']}; keep them in the scene"))
                    have.add(name)
    return fixes, defs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--scene", default="")
    ap.add_argument("--skip", default="", help="comma list of clip:Name pairs to leave alone")
    ap.add_argument("--no-rebuild", action="store_true")
    args = ap.parse_args()

    data = json.loads(PROMPTS.read_text(), strict=False)
    clips = data["clips"]
    skip = {tuple(x.strip().split(":")) for x in args.skip.split(",") if ":" in x}
    fixes, defs = plan(clips, args.scene, skip)

    adds = [f for f in fixes if f[2] == "add"]
    print(f"{'Preview' if args.dry_run else 'Fixes'}: {len(adds)} character(s) kept in scene, "
          f"{len(fixes) - len(adds)} left as is")
    for clip, name, action, why in fixes:
        mark = "+" if action == "add" else "-"
        print(f"  {mark} {clip['id']}: {name}  ({why})")

    if args.dry_run:
        return
    for clip, name, action, why in adds:
        clip["subjects"].append(f"Define {defs[name]} in @Image 1 as {name}")
        clip.setdefault("continuity_added", []).append(name)
        clip.setdefault("continuity_fixes", []).append(f"Added {name}: {why}")

    if adds:
        backup = DATA / "backups" / f"prompt.{datetime.now():%Y%m%d-%H%M%S}.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROMPTS, backup)
        PROMPTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        print(f"Saved {PROMPTS.name} (backup: {backup.relative_to(DATA.parent)})")

    if not args.no_rebuild:
        for script in ("add_continuity.py", "check_continuity.py", "check_camera.py"):
            subprocess.run([sys.executable, str(HERE / script)], check=True)


if __name__ == "__main__":
    main()
