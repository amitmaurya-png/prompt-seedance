---
name: seedance-prompting
description: "Create, refine, or review Seedance video prompts using this project's universal prompt syntax and label vocabulary. Use for shot planning, camera and motion direction, image/video/audio references, and prompt continuity checks."
---

# Seedance Prompting

Create original, actionable prompts for Seedance 2.x. Follow the user's requested model version, format, duration, aspect ratio, and style when provided. Do not assume every Seedance version has identical capabilities.

One Seedance 2.0 generation is a single clip of 4 to 15 seconds. Longer pieces are separate clips that are cut together afterwards, with the same subject tags and style line kept in every clip.

## References

| File | Use it for |
|---|---|
| [prompt_syntax.md](./references/prompt_syntax.md) | The default prompt structure: block order, block grammar, template, worked example, validation checklist |
| [prompt_labels.md](./references/prompt_labels.md) | Label vocabulary from community Seedance prompts, grouped by category, with aliases and frequency |
| [seedance_2_0_prompt_guide.md](./references/seedance_2_0_prompt_guide.md) | Official BytePlus Seedance 2.0 prompt guide notes: task patterns (reference, edit, extend), subject binding, shot and action rules, special symbols, asset limits, troubleshooting. Source: [Seedance 2.0 prompt guide](https://ai.byteplus.com/ark/region:ap-southeast-1/docs/ModelArk/seedance-2-0-prompt-guide) |
| [camera_language.md](../camera-knowledge/references/camera_language.md) | Camera vocabulary and how to write a shot's `Camera:` line (owned by the `camera-knowledge` skill) |
| [camera_genres.md](../camera-knowledge/references/camera_genres.md) | Which camera choices suit which genre (owned by the `camera-knowledge` skill) |

### Camera language

Camera details live in the `camera-knowledge` skill. Read its `camera_language.md` when writing or reviewing a shot's `Camera:` line. Key rules:

- Write the line as `<shot size>[, <angle>][, <one movement>]`, e.g. `Medium close-up, low angle, slow push-in`. Use `static` when the camera doesn't move.
- Use one movement per shot. Shot size, angle, and focus are framing choices and can be combined freely.
- Open each new scene with an establishing or wide shot, then step closer gradually (WS → MS → MCU → CU).
- Cover dialogue with a two-shot, over-the-shoulder shots, or shot/reverse shot, and keep the 180° rule: each character stays on the same side of the frame throughout the scene.
- Match camera choices to the genre (`camera_genres.md`). For this project's screenplay, use family storybook conventions (eye level at child height, gentle moves, few extreme close-ups) and epic/biblical conventions for the Galilean hillside (wide crowds, aerial reveals, Jesus only from behind or in silhouette).

### Official Seedance 2.0 guide

Read `seedance_2_0_prompt_guide.md` when targeting Seedance 2.0, 2.0 Fast, or 2.0 Mini, and when writing reference, edit, or extend prompts. Where it is more specific than `prompt_syntax.md`, follow the official guide. Key rules:

- Bind every subject to its asset (`Miri (@Image 1)`) and reuse the same label in every mention.
- Put the most important assets and content first.
- Write shots as `Shot 1 / Shot 2 / Shot 3`, with no per-shot durations.
- Use one camera move per shot and slow, specific, body-part-level actions.
- Use the official symbols: dialogue `{ }`, music `（ ）`, sound effects `< >`. The `【 】` brackets render on-screen text in Seedance 2.0, so never use them as section labels.
- Keep a clip to about 4-5 assets and 4 or fewer reference characters.
- In edit and extend tasks, name the video directly (`Video 1`), not "reference Video 1".

### Prompt syntax

Read `prompt_syntax.md` before writing or reviewing a prompt. Its canonical block order is:

```
FORMAT → STYLE → REFERENCES → SUBJECT → SCENE → CAMERA → SHOTS → AUDIO → CONSTRAINTS
```

- Required: `FORMAT`, `STYLE`, `SUBJECT`, `SCENE`, `SHOTS`. Add `REFERENCES` only when assets are supplied. `CAMERA`, `AUDIO`, and `CONSTRAINTS` are optional.
- Leave out any block that does not apply. Never output an empty label.
- Use the compact paragraph form (same order, no labels) for short or simple clips.

### Label vocabulary

Use the canonical labels from `prompt_syntax.md`. Consult `prompt_labels.md` when you need to:

- interpret or review a user's prompt that uses alias labels (for example `Visual`, `Tone`, `【Scene】`, `[Constraints (Important)]`), mapping each to its canonical block;
- add a specialised sub-label that is already listed (for example `Velocity Ramp choreography`, `Freeze Frame`, `Final hero frame`).

Do not invent new label styles when a listed one fits. Use one bracket style throughout a prompt, and do not use `【 】` labels in Seedance 2.0 prompts (see the official guide).

## Workflow

1. Determine whether the user wants a new prompt, a revision, a critique, or structured output for this project's scripts. Ask a focused question only if missing information would materially change the result.
2. Fill the required blocks first: `FORMAT` (duration, aspect ratio, shot count, cut style), `STYLE`, `SUBJECT`, `SCENE`, and the visible action for `SHOTS`. Note any supplied references. Keep each generation focused on one clip unless the user asks for a sequence.
3. Write the prompt in the canonical block order. Give each subject a short stable tag (`A`, `B`, or a name) and refer to it by that tag in every shot. Use concrete, visible actions instead of mood-only directions.
4. Write each shot as `Shot <n>: <title>` with `Camera:` (framing + one primary move), `Action:`, `Visual:` (environment response), and optional `Audio:`. Make motion intensity and transitions explicit. Add timecodes only when the user or target workflow asks for timing; when used, ranges must be continuous and add up to the `FORMAT` duration.
5. For image references, list each asset in `REFERENCES` with one role and use the same token everywhere. Treat the supplied image as the authority for appearance; describe action, camera, and changes without re-describing the image.
6. Use video references to guide motion only when supplied. Use audio references for sound or voice only when supplied. Do not claim an asset exists when it was not provided; leave optional reference fields empty when inapplicable.
7. Preserve user-provided dialogue exactly, with its original speaker tag, and include it exactly once. Do not invent, omit, reorder, or paraphrase story events or dialogue.
8. Run the validation checklist in `prompt_syntax.md`: block order, no empty labels, timing adds up, one camera move per shot, consistent tags and tokens, exact dialogue, no contradictions between `STYLE`, `CAMERA`, shots, and `CONSTRAINTS`. Prefer a few clear constraints over repeated generic quality tags.

## Project Continuity

Project rules override the generic syntax when working on this repository's screenplay.

- For this project's screenplay, Nim is a fox, not a dog.
- If Jesus appears, show only his hands, robe, and silhouette; never show his face.
- Keep the established warm, painterly storybook animation style when working on this screenplay unless the user requests a change.
- Write dialogue in `{curly braces}` and asset tokens as `@Image 1`, `@Video 1`, `@Audio 1`.
- Do not add timecodes; shots are numbered and the model sets the pace.
- Follow [docs/approach.md](../../../docs/approach.md) and the system prompts in [scripts/build_prompts.py](../../../scripts/build_prompts.py) when generating or reviewing prompts for this repository.

## Project Scripts

Run these from the repository root. Data lives in `data/`, generated images in `assets/`, and HTML reports in `reports/`.

| Script | When to run it |
|---|---|
| [scripts/parse_screenplay.py](../../../scripts/parse_screenplay.py) | Screenplay PDF (`pdf_document/TSL.pdf`) → `data/breakdown.json`, every action and line verbatim (no AI) |
| [scripts/build_prompt_json.py](../../../scripts/build_prompt_json.py) `--all` | `data/breakdown.json` → `data/prompt.json` with verbatim actions and dialogue, then continuity, emotions, fixes, and reports |
| [scripts/check_continuity.py](../../../scripts/check_continuity.py) | To check continuity in every scene (owned by the `scene-continuity` skill): writes `reports/continuity_report.html` |
| [scripts/add_continuity.py](../../../scripts/add_continuity.py) | After editing `data/prompt.json` or the continuity blocks: rebuilds prompts with scene continuity |
| [scripts/check_camera.py](../../../scripts/check_camera.py) | To review camera lines, characters, and dialogue per shot: writes `reports/camera_report.html`. Use `--query "text"` for a camera-term similarity search |
| [scripts/make_camera_images.py](../../../scripts/make_camera_images.py) | To redraw camera diagrams and reset `data/camera_angles.json` |
| [scripts/make_character_images.py](../../../scripts/make_character_images.py) | To redraw character references and rewrite `data/characters.json` and `reports/characters.html` |
| [scripts/extract_breakdown.py](../../../scripts/extract_breakdown.py) | Screenplay PDF → `data/breakdown.json` (calls the OpenAI API) |
| [scripts/build_prompts.py](../../../scripts/build_prompts.py) | `data/breakdown.json` → `data/prompts.json` (calls the OpenAI API) |

## Output Formats

For a standalone request, return a clean, copyable Seedance prompt in the `prompt_syntax.md` structure, including only the blocks useful for that prompt.

When the user requests output compatible with `scripts/build_prompts.py`, return JSON with this shape. The syntax blocks map onto it: `REFERENCES` → `asset_preparation` and the `*_reference` fields, `SHOTS` → `shots`, and `STYLE` / `CAMERA` / `AUDIO` / `CONSTRAINTS` → `global_direction`.

```json
{
  "asset_preparation": [],
  "image_reference": "",
  "video_reference": "",
  "audio_reference": "",
  "shots": [],
  "global_direction": ""
}
```

`asset_preparation`, `image_reference`, `shots`, and `global_direction` are required. Set `video_reference` and `audio_reference` to empty strings when they do not apply. Preserve the expected JSON types and do not wrap JSON in Markdown fences when machine-readable output is requested.
