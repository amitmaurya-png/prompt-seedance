---
name: camera-knowledge
description: "Camera knowledge for film and Seedance prompts: shot sizes (extreme wide to extreme close-up), camera angles (eye level, high, low/up shot, worm's-eye, overhead, Dutch), framing and special shots (over-the-shoulder, POV, insert, cutaway, reaction, profile, rear, silhouette), dialogue coverage, the 180° rule, camera movement, focus, choosing a shot by storytelling goal, and which choices suit which genre and mood. Detects a shot's genre and mood and suggests the right camera angle. Use when choosing, explaining, suggesting, reviewing, or fixing a shot's camera direction, matching camera to genre or mood, or checking camera lines in data/prompt.json."
argument-hint: "[clip id, scene, or camera question]"
---

# Camera Knowledge

Answer camera questions and choose or review camera direction for this project's Seedance prompts. Use standard film terms so Seedance understands them, and keep camera choices consistent with the story's genre and continuity.

## References

| File | Use it for |
|---|---|
| [camera_language.md](./references/camera_language.md) | Camera vocabulary: shot sizes (EWS to ECU), angles with their feeling and uses (incl. worm's-eye, Dutch), framing and special-purpose shots (OTS, POV, insert, cutaway, reaction, profile, rear, reflection, silhouette), dialogue coverage (180° rule), movements, focus; choosing a shot by storytelling goal; a suspense sequence example; AI-prompt wording examples; how to write a `Camera:` line; checklist |
| [camera_genres.md](./references/camera_genres.md) | Typical and avoided camera choices for 12 genres, and how to apply them in a Seedance prompt |
| [camera_moods.md](./references/camera_moods.md) | How to detect a shot's mood, the camera defaults per mood, and how to adjust for genre, speakers, children, and continuity |
| [camera_angles.json](../../../data/camera_angles.json) | Camera term → diagram image (images in `assets/camera/`) |
| [seedance_2_0_prompt_guide.md](../seedance-prompting/references/seedance_2_0_prompt_guide.md) | Official Seedance 2.0 camera rules (§2.4: one camera movement per shot) |

## Scripts

Run from the repository root.

| Script | When to run it |
|---|---|
| [scripts/check_camera.py](../../../scripts/check_camera.py) | Review every shot's camera line, who the camera is on, and the dialogue: writes `reports/camera_report.html` and prints warnings |
| `python3 scripts/check_camera.py --query "<camera description>"` | Find the closest camera terms for free-form wording (similarity search) |
| [scripts/camera_suggest.py](../../../scripts/camera_suggest.py) `--describe "<shot>" [--genre storybook\|epic] [--new-scene]` | Detect the genre and mood of any shot description and suggest a camera line, with reasons |
| `python3 scripts/camera_suggest.py --all` | Suggest a camera for every shot in `data/prompt.json` (the report shows the same, with fit) |
| [scripts/apply_camera.py](../../../scripts/apply_camera.py) `--fit differs --dry-run` | Preview suggested camera changes for chosen shots (`--fit`, `--clips`, `--scene`, `--shot clip-37:2`) |
| `python3 scripts/apply_camera.py --set "clip-39:3=<camera line>" --why "<reason>"` | Write reviewed camera lines into `data/prompt.json` (backup saved, old line kept in `camera_previous`), then rebuild prompts and the report |
| `python3 scripts/apply_camera.py --undo clip-39:3` | Restore a shot's previous camera line |
| [scripts/add_placement.py](../../../scripts/add_placement.py) `[--dry-run] [--clip …]` | Write each shot's `Placement:` line (main character and where they sit in the frame) under its `Camera:` line; run after `add_continuity.py` or any camera change |
| [scripts/make_camera_images.py](../../../scripts/make_camera_images.py) | Redraw the camera diagrams and reset `data/camera_angles.json` |

## Workflow

1. Identify the task: explain a term, choose camera for a shot, review existing camera lines, or match a scene to a genre or mood.
2. For terms and how to write them, read `camera_language.md`. For genre fit, read `camera_genres.md`. For mood, read `camera_moods.md`.
3. To choose the camera for a shot, detect its **genre** (from the scene) and **mood** (from title, action, and dialogue), then apply `camera_moods.md`: mood defaults → coverage → genre → talking characters → children → continuity. Run `scripts/camera_suggest.py --describe "<shot>"` for a quick suggestion, and explain or override it with reasons.
4. Write each `Camera:` line as `<shot size>[, <angle>][, <one movement>]`, e.g. `Medium close-up, low angle, slow push-in`. Use `static` when the camera holds. Under it, always add a `Placement:` line naming the shot's main character and where they sit in the frame (which third, which way they face, who else is where); see "Placing the main character" in `camera_language.md`, and run `scripts/add_placement.py`.
5. Check the shot against its neighbours: open a new scene with an establishing or wide shot, step shot sizes gradually (WS → MS → MCU → CU), and keep each character on the same side of the frame within a scene (180° rule; see the scene's `CONTINUITY` block in `data/prompt.json`).
6. To review many shots, run `scripts/check_camera.py`: each shot card shows the detected genre and mood, a suggested camera, and whether the current line fits, is close, or differs. Work through "differs" first, then warnings and notes. After editing prompts, run `scripts/add_continuity.py`, then `scripts/check_camera.py` again.
7. To change camera lines in `data/prompt.json`:
   1. Preview with `apply_camera.py --dry-run`, scoped by `--fit`, `--clips`, `--scene`, or `--shot`.
   2. Review each proposal: keep the shot's context (subject, "through the crowd", "from behind …"), keep one movement, and keep deliberate choices such as reveals. Say which shots you keep and why.
   3. Apply the reviewed lines with `--set "clip:shot=<line>" --why "<reason>"`. Use `--fit … ` without `--set` only when the user asks to apply the raw suggestions.
   4. The script rebuilds the prompts and `reports/camera_report.html`, whose "Camera changes" section and per-shot "changed" notes list every edit with its reason; confirm the new lines appear in each clip's `prompt` text and that their fit improved.
   5. Report a before/after table. Changes can be undone with `--undo clip:shot` or from `data/backups/`.
8. When explaining a choice, name the term, say what it shows, and why it fits the moment or genre.

## Rules

- Every shot's camera direction says where the main character is placed (`Placement:` line), on the same side as the scene's screen positions.
- One camera movement per shot (Seedance rule). Shot size, angle, and focus are framing choices and can be combined.
- Prefer standard terms from `camera_language.md` over invented wording, so Seedance and `check_camera.py` both recognise them.
- Treat genre and mood conventions as defaults; break them on purpose and say why. Suggestions from `camera_suggest.py` are rule-based starting points, not final answers.
- For this project: family storybook framing in the village and scroll room (eye level at child height, gentle moves, few extreme close-ups); epic framing on the Galilean hillside (wide crowds, aerial reveals). Jesus is only shown from behind, as hands and robe, or in silhouette, never his face.
- Only change the `camera` field of shots; never alter dialogue, action, or continuity blocks. Never apply changes to every shot without a preview and the user's go-ahead.
- For writing full prompts (format, subjects, dialogue, continuity), use the `seedance-prompting` skill; this skill covers the camera only.
