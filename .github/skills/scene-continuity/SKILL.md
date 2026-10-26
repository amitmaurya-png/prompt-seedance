---
name: scene-continuity
description: "Check, add, and fix continuity between clips in every scene of this project's Seedance prompts: clip-to-clip chaining with last frames, handoffs between clips, scene state (time of day, light, props, screen positions), characters that vanish or change, voices and music, and dialogue order. Applies fixes to data/prompt.json and updates reports/camera_report.html and reports/continuity_report.html. Use when checking whether scenes are continuous, adding continuity between clips, or fixing continuity breaks."
argument-hint: "[scene heading, clip id, or 'all scenes']"
---

# Scene Continuity

Check that every scene in `data/prompt.json` plays as one continuous piece, report breaks scene by scene, and fix them through the project's continuity settings. Each Seedance clip is generated independently, so continuity only holds if each clip repeats the scene's facts and starts where the previous clip ended.

## References

| File | Use it for |
|---|---|
| [continuity_rules.md](./references/continuity_rules.md) | Kinds of continuity, where each lives in `data/prompt.json`, how each issue is fixed, per-scene checklist |
| [add_continuity.py](../../../scripts/add_continuity.py) | The settings that create continuity: `CONTINUITY` (scene state), `HANDOFF_FIXES`, `CONTINUES_ACROSS_HEADING`, `VOICE`, `ORDER` |
| [breakdown.json](../../../data/breakdown.json) | The screenplay's scenes, shots, and dialogue: the source of truth for order and lines |

## Scripts

Run from the repository root.

| Script | When to run it |
|---|---|
| [scripts/check_continuity.py](../../../scripts/check_continuity.py) | Check every scene; prints issues and writes `reports/continuity_report.html`. Use `--scene "<heading text>"` for one scene |
| [scripts/fix_continuity.py](../../../scripts/fix_continuity.py) `--dry-run` | Preview fixes: characters kept in the scene so they don't vanish between clips, plus rebuilt chain/state |
| `python3 scripts/fix_continuity.py [--scene "<heading>"] [--skip clip-60:Miri]` | Apply the fixes to `data/prompt.json` (backup saved, each fix recorded on the clip), then rebuild prompts, `continuity_report.html`, and `camera_report.html` |
| [scripts/keep_present.py](../../../scripts/keep_present.py) `--dry-run` | Preview who is carried into which clip because they are still in the scene (not yet exited), and whether by image or by text |
| `python3 scripts/keep_present.py` | Carry them into `data/prompt.json` (backup saved, recorded in each clip's `still_present`); then rebuild the curl commands for the changed clips |
| [scripts/add_continuity.py](../../../scripts/add_continuity.py) | Rebuild prompts after changing continuity settings or a clip's `subjects` |
| [scripts/check_camera.py](../../../scripts/check_camera.py) | Camera continuity (shot-size jumps, scene openings); hand camera fixes to the `camera-knowledge` skill |

## Workflow

1. Run `python3 scripts/check_continuity.py` (all scenes, or `--scene` for one). Open `reports/continuity_report.html` for the scene-by-scene view.
2. For each issue, read the clips involved in `data/prompt.json` and decide whether it is a real break or a deliberate cut (e.g. the camera moving to other characters, a character leaving on screen). Say which issues you leave and why.
3. Preview automatic fixes with `python3 scripts/fix_continuity.py --dry-run`. Review each one; pass deliberate cuts with `--skip clip:Name`. Then apply with `python3 scripts/fix_continuity.py`.
4. Fix anything the script leaves using `continuity_rules.md` §3, preferring the settings in `add_continuity.py` (`CONTINUITY`, `HANDOFF_FIXES`, `CONTINUES_ACROSS_HEADING`, `VOICE`) over hand-editing prompt text, because `add_continuity.py` rebuilds every prompt from them. Then run `add_continuity.py`.
5. Run `python3 scripts/check_continuity.py` and `python3 scripts/check_camera.py` (the fix script runs both). Confirm the issues are gone in `reports/continuity_report.html`, and in `reports/camera_report.html`, where each clip shows "✓ continuous" or its continuity notes and fixes.
6. Read the CONTINUITY blocks of consecutive scenes in story order to check props over time (cakes, basket, Tav's wheel, the lunch, twelve baskets, the scroll); the script cannot judge story logic.
7. Report per scene: continuous or not, what changed, and what was left on purpose.

## Rules

- Never change dialogue wording or order; `data/breakdown.json` is the source of truth.
- Change actions only to bridge a handoff (via `HANDOFF_FIXES`), and keep the story's events unchanged.
- **Characters stay on screen until they leave.** Within a scene, everyone who has appeared stays present in every later clip until an action line explicitly takes them out ("hurries away", "scatter", "exits", "out of frame", or "follows" right after someone leaves). A character who is only heard (voice-over) isn't on screen. Carry each one into clips that don't otherwise include them: named characters (never Jesus) get an image and subject while the clip has fewer than 4 character images; everyone else is named in shot 1's Continuity line as `… with Nim (the small fox) and the hillside crowd of families with children still present`. `scripts/keep_present.py` does this.
- Keep at most 4 characters and about 5-6 images per clip (Seedance guidance).
- Keep each character's definition, voice, and image slot identical across clips.
- Camera lines belong to the `camera-knowledge` skill; whole-prompt format belongs to `seedance-prompting`.
- Clips in a chained scene must be generated in order, because each needs the previous clip's last frame.
