---
name: camera-knowledge
description: "Camera knowledge for film and Seedance prompts: shot sizes, camera angles, framing, over-the-shoulder and dialogue coverage, the 180° rule, camera movement, focus, and which choices suit which genre and mood. Detects a shot's genre and mood and suggests the right camera angle. Use when choosing, explaining, suggesting, reviewing, or fixing a shot's camera direction, matching camera to genre or mood, or checking camera lines in data/prompt.json."
argument-hint: "[clip id, scene, or camera question]"
---

# Camera Knowledge

Answer camera questions and choose or review camera direction for this project's Seedance prompts. Use standard film terms so Seedance understands them, and keep camera choices consistent with the story's genre and continuity.

## References

| File | Use it for |
|---|---|
| [camera_language.md](./references/camera_language.md) | Camera vocabulary: shot sizes (WS to ECU), angles, framing and dialogue coverage (OTS, shot/reverse shot, 180° rule), movements, focus; how to write a `Camera:` line; checklist |
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
| [scripts/make_camera_images.py](../../../scripts/make_camera_images.py) | Redraw the camera diagrams and reset `data/camera_angles.json` |

## Workflow

1. Identify the task: explain a term, choose camera for a shot, review existing camera lines, or match a scene to a genre or mood.
2. For terms and how to write them, read `camera_language.md`. For genre fit, read `camera_genres.md`. For mood, read `camera_moods.md`.
3. To choose the camera for a shot, detect its **genre** (from the scene) and **mood** (from title, action, and dialogue), then apply `camera_moods.md`: mood defaults → coverage → genre → talking characters → children → continuity. Run `scripts/camera_suggest.py --describe "<shot>"` for a quick suggestion, and explain or override it with reasons.
4. Write each `Camera:` line as `<shot size>[, <angle>][, <one movement>]`, e.g. `Medium close-up, low angle, slow push-in`. Use `static` when the camera holds.
5. Check the shot against its neighbours: open a new scene with an establishing or wide shot, step shot sizes gradually (WS → MS → MCU → CU), and keep each character on the same side of the frame within a scene (180° rule; see the scene's `CONTINUITY` block in `data/prompt.json`).
6. To review many shots, run `scripts/check_camera.py`: each shot card shows the detected genre and mood, a suggested camera, and whether the current line fits, is close, or differs. Work through "differs" first, then warnings and notes. After editing prompts, run `scripts/add_continuity.py`, then `scripts/check_camera.py` again.
7. When explaining a choice, name the term, say what it shows, and why it fits the moment or genre.

## Rules

- One camera movement per shot (Seedance rule). Shot size, angle, and focus are framing choices and can be combined.
- Prefer standard terms from `camera_language.md` over invented wording, so Seedance and `check_camera.py` both recognise them.
- Treat genre and mood conventions as defaults; break them on purpose and say why. Suggestions from `camera_suggest.py` are rule-based starting points, not final answers.
- For this project: family storybook framing in the village and scroll room (eye level at child height, gentle moves, few extreme close-ups); epic framing on the Galilean hillside (wide crowds, aerial reveals). Jesus is only shown from behind, as hands and robe, or in silhouette, never his face.
- For writing full prompts (format, subjects, dialogue, continuity), use the `seedance-prompting` skill; this skill covers the camera only.
