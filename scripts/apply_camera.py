#!/usr/bin/env python3
"""Apply suggested camera lines to shots in data/prompt.json.

Picks shots by how well their current camera fits the genre/mood suggestion (camera_suggest.py),
by clip, or by single shot; writes the suggested line into the shot's "camera" field; keeps the old
line in "camera_previous"; then rebuilds the prompts (add_continuity.py) and the camera report.

Usage:
  python3 scripts/apply_camera.py --fit differs --dry-run       # preview the 'differs' shots
  python3 scripts/apply_camera.py --fit differs                  # apply them
  python3 scripts/apply_camera.py --fit close,differs --scene HILLSIDE
  python3 scripts/apply_camera.py --shot clip-37:2               # one shot
  python3 scripts/apply_camera.py --clips clip-12,clip-13 --fit close,differs
  python3 scripts/apply_camera.py --set "clip-39:3=Medium long shot on Andrew, slow pull back" --why "keep the crowd"
  python3 scripts/apply_camera.py --undo clip-37:2               # restore the previous line
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from check_camera import analyse
from paths import DATA

PROMPTS = DATA / "prompt.json"
BACKUPS = DATA / "backups"
HERE = Path(__file__).resolve().parent


def parse_shots(values):
    out = set()
    for v in values or []:
        for item in v.split(","):
            clip, _, n = item.strip().partition(":")
            out.add((clip, int(n)))
    return out


def rebuild():
    for script in ("add_continuity.py", "add_placement.py", "check_camera.py"):
        subprocess.run([sys.executable, str(HERE / script)], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fit", default="", help="comma list of fits to change: differs, close, matches")
    ap.add_argument("--clips", default="", help="comma list of clip ids, e.g. clip-12,clip-13")
    ap.add_argument("--scene", default="", help="only scenes whose heading contains this text")
    ap.add_argument("--shot", action="append", help="clip:shot, e.g. clip-37:2 (repeatable)")
    ap.add_argument("--set", action="append", help='write your own line: "clip:shot=Camera line" (repeatable)')
    ap.add_argument("--why", default="", help="reason recorded with --set changes")
    ap.add_argument("--undo", action="append", help="restore camera_previous for clip:shot")
    ap.add_argument("--dry-run", action="store_true", help="show the changes without writing")
    ap.add_argument("--no-rebuild", action="store_true", help="skip add_continuity.py and check_camera.py")
    args = ap.parse_args()

    data = json.loads(PROMPTS.read_text(), strict=False)
    clips = {c["id"]: c for c in data["clips"]}

    if args.undo:
        changes = []
        for clip_id, n in sorted(parse_shots(args.undo)):
            shot = clips[clip_id]["shot_details"][n - 1]
            if "camera_previous" in shot:
                changes.append((clip_id, n, shot["camera"], shot["camera_previous"]))
                if not args.dry_run:
                    shot["camera"] = shot.pop("camera_previous")
                    shot.pop("camera_reason", None)
        report(changes, "Restore", args.dry_run)
        if changes and not args.dry_run:
            save(data)
            if not args.no_rebuild:
                rebuild()
        return

    if args.set:
        changes = []
        for item in args.set:
            target, _, line = item.partition("=")
            clip_id, _, n = target.strip().partition(":")
            shot = clips[clip_id]["shot_details"][int(n) - 1]
            changes.append((clip_id, int(n), shot["camera"], line.strip(), args.why or "reviewed change"))
        report([(a, b, c, d) for a, b, c, d, _ in changes], "Change", args.dry_run, reasons=[w for *_, w in changes])
        if not args.dry_run:
            for clip_id, n, old, new, why in changes:
                shot = clips[clip_id]["shot_details"][n - 1]
                shot.setdefault("camera_previous", old)
                shot["camera"], shot["camera_reason"] = new, why
            save(data)
            if not args.no_rebuild:
                rebuild()
        return

    fits = {f.strip() for f in args.fit.split(",") if f.strip()}
    clip_ids = {c.strip() for c in args.clips.split(",") if c.strip()}
    shots = parse_shots(args.shot)
    if not (fits or clip_ids or shots or args.scene):
        ap.error("choose shots with --fit, --clips, --scene, or --shot")

    results, _ = analyse(PROMPTS, roster=json.loads((DATA / "characters.json").read_text()).keys())
    changes = []
    for c in results:
        if clip_ids and c["id"] not in clip_ids:
            continue
        if args.scene and args.scene.upper() not in c["scene"].upper():
            continue
        for s in c["shots"]:
            if shots and (c["id"], s["n"]) not in shots:
                continue
            if fits and s["fit"] not in fits:
                continue
            new = s["suggestion"]["line"]
            if new.strip().lower() == s["camera"].strip().lower():
                continue
            why = "; ".join([f"{s['suggestion']['genre']} / {s['suggestion']['mood']}"] + s["fit_notes"])
            changes.append((c["id"], s["n"], s["camera"], new, why))

    report([(a, b, c, d) for a, b, c, d, _ in changes], "Change", args.dry_run,
           reasons=[w for *_, w in changes])
    if not changes or args.dry_run:
        return

    for clip_id, n, old, new, why in changes:
        shot = clips[clip_id]["shot_details"][n - 1]
        shot.setdefault("camera_previous", old)
        shot["camera"] = new
        shot["camera_reason"] = why
    save(data)
    if not args.no_rebuild:
        rebuild()


def save(data):
    BACKUPS.mkdir(parents=True, exist_ok=True)
    backup = BACKUPS / f"prompt.{datetime.now():%Y%m%d-%H%M%S}.json"
    shutil.copy2(PROMPTS, backup)
    PROMPTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"Saved {PROMPTS.name} (backup: {backup.relative_to(DATA.parent)})")


def report(changes, verb, dry_run, reasons=None):
    if not changes:
        print("No shots to change.")
        return
    print(f"{'Preview' if dry_run else verb}: {len(changes)} shot(s)")
    for i, (clip_id, n, old, new) in enumerate(changes):
        print(f"  {clip_id} shot {n}\n      before: {old}\n      after:  {new}")
        if reasons:
            print(f"      why:    {reasons[i]}")


if __name__ == "__main__":
    main()
