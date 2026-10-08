---
name: clip-continuity
description: "Check and add continuity for every clip and every clip-to-clip boundary in this project's Seedance prompts: continuing clips start from the previous last frame, scene cuts get a transition line, time of day moves forward, every character who acts or speaks has an image, dialogue fits the clip length, and every clip ends on a held frame. Applies fixes to data/prompt.json and updates reports/camera_report.html. Use when checking or fixing continuity between clips, transitions between scenes, or per-clip completeness."
argument-hint: "[clip id, boundary like clip-07→clip-08, or 'all clips']"
---

# Clip Continuity

Make all 63 clips cut together as one film. Check each clip on its own and each boundary to the next clip, add the missing continuity, write the fixes into `data/prompt.json`, and show the result in `reports/camera_report.html`.

## References

| File | Use it for |
|---|---|
| [clip_rules.md](./references/clip_rules.md) | Boundary types (continue vs cut), per-clip rules (cast, timing, ending), fixes, and fix order |
| [continuity_rules.md](../scene-continuity/references/continuity_rules.md) | Scene-level continuity (state blocks, screen positions, characters inside a scene) |
| [add_continuity.py](../../../scripts/add_continuity.py) | Builds handoff and transition lines, last-frame references, and rules into every prompt |

## Scripts

Run from the repository root.

| Script | When to run it |
|---|---|
| [scripts/check_clips.py](../../../scripts/check_clips.py) | Check every clip and boundary; prints issues |
| `python3 scripts/check_clips.py --fix --dry-run` | Preview fixes: transition lines for scene cuts, missing cast images, longer clips for dense dialogue |
| `python3 scripts/check_clips.py --fix` | Apply fixes to `data/prompt.json` (backup saved, each fix recorded in `clip_fixes`), then rebuild prompts, `continuity_report.html`, and `camera_report.html` |
| [scripts/check_continuity.py](../../../scripts/check_continuity.py) / [scripts/fix_continuity.py](../../../scripts/fix_continuity.py) | Scene-level checks and fixes (`scene-continuity` skill); run them too for a full pass |

## Workflow

1. Run `python3 scripts/check_clips.py` to list clip and boundary issues.
2. Preview with `--fix --dry-run`. Review each proposed change: keep deliberate choices (a reveal that opens a scene close, a time jump when leaving the story world) and say why.
3. Apply with `python3 scripts/check_clips.py --fix`. For a full pass, also run `python3 scripts/fix_continuity.py` (scene level).
4. Confirm in `data/prompt.json` that scene openers have a "Continuity: New scene: cut from …" line and continuing clips have "Continue the same moment from …".
5. Open `reports/camera_report.html`: the **Clip-to-clip transitions** table shows every boundary (continue or cut) and its status; each clip's **Scene continuity** box shows its transition, fixes, and any remaining notes.
6. Report: boundaries checked, fixes applied, and anything left on purpose.

## Rules

- Never change dialogue wording or order; never change story events.
- Add characters only with their usual definition, at most 4 per clip; never add Jesus automatically.
- Keep clips within 4-15 seconds; if dialogue still doesn't fit at 15 s, hand the clip to `seedance-prompting` to split.
- Camera lines belong to `camera-knowledge`; scene state and screen positions belong to `scene-continuity`.
