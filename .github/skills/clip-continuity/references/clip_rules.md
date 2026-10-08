# Clip Continuity Rules

What every clip, and every boundary between two clips, needs so the 63 clips cut together into one film.
Scene-level checks (state blocks, screen positions, vanishing characters inside a scene) live in the `scene-continuity` skill; this file covers each clip and each clip-to-clip boundary, including cuts between scenes.

## 1. Boundaries (clip N-1 → clip N)

| Type | When | What clip N needs | Check |
|---|---|---|---|
| **Continue** | Same scene (or listed in `CONTINUES_ACROSS_HEADING`) | Previous clip's last frame in `REFERENCES`; Shot 1 "Continuity: Continue the same moment from @Image N…"; "Match lighting, positions, props…" rule; music "continues" | `check_clips.py` (boundary), `check_continuity.py` (chain) |
| **Cut** | New scene | Shot 1 "Continuity: New scene: cut from <place> (clip-XX) to <place>, <time> light; do not carry over the previous clip's framing"; no previous last frame; music "begins"; usually opens wide (camera-knowledge) | `check_clips.py` (boundary) |

Time of day should move forward within an act (morning → late morning → day → late afternoon → sunset → evening). A backwards jump is flagged as a note: it is fine when deliberate, such as returning from the story world to the scroll room.

## 2. Every clip

| Check | Rule | Fix |
|---|---|---|
| **Cast** | Everyone who acts or speaks on screen has an image reference (voice-over excepted) | Add `Define <usual description> in @Image 1 as <Name>` to `subjects` (max 4 characters; Jesus only by hand, from behind) |
| **Timing** | Dialogue fits the clip: about 2.6 words per second, clip length 4-15 s | Lengthen `api_params.duration` and `format` up to 15 s; if still too long, split the clip (seedance-prompting) |
| **Ending** | Ends on a calm, held frame; `api_params.return_last_frame` is true | Run `add_continuity.py` |

## 3. Fix order

1. `python3 scripts/check_clips.py --fix --dry-run`: preview.
2. Review: skip deliberate cases by fixing them by hand instead.
3. `python3 scripts/check_clips.py --fix`: applies, records each fix in the clip's `clip_fixes`, saves a backup, and rebuilds `data/prompt.json`, `reports/continuity_report.html`, and `reports/camera_report.html`.
4. In `reports/camera_report.html`, check **Clip-to-clip transitions** (every boundary with its type and status) and each clip's **Scene continuity** box (transition line, fixes, remaining notes).
