# prompt.json rules

How `data/prompt.json` is built from a skit's `data/breakdown.json`.

## File shape

```json
{
  "source": "breakdown.json",
  "builder": "build_prompt_json.py (verbatim actions and dialogue, no AI)",
  "skill": "seedance-prompting",
  "syntax": ".github/skills/seedance-prompting/references/prompt_syntax.md",
  "clip_count": 91,
  "total_seconds": 991,
  "clips": [ ... ]
}
```

## Clip fields

| Field | Content |
|---|---|
| `id` | `clip-01`, `clip-02`, … in skit order |
| `act`, `scene` | Act label and the skit's scene heading, verbatim |
| `source` | The breakdown shots this clip comes from |
| `duration_seconds` | 4-15, estimated from spoken words (≈2.6 words/s), shot count, and action length |
| `api_params` | `model` (`dreamina-seedance-2-0-260128`), `ratio` 16:9, `duration`, `return_last_frame` |
| `format` | `14s / 16:9 / 2 shots / soft cuts` (or `one continuous shot`) |
| `style` | The project style line (stylized 3D storybook animation) |
| `references` | `@Image N: <role>` per asset: characters first, then the scene, then the last frame of the previous clip |
| `subjects` | `Define <short description> in @Image N as <Name>` |
| `scene_setting` | The scene heading plus its scene image |
| `shot_details` | Per shot: `title`, `camera`, `action` (verbatim), `dialogue` [`character`, `line` verbatim, `parenthetical`, `voice_over`, `emotion`, `intensity`, `delivery`, `addressee`], `eyeline` |
| `audio` | Music `（…）`, ambience, SFX `<…>`, and voice notes per speaker |
| `constraints` | One camera move per shot, 3D render rule, stable faces, no duplicates, held end frame, continuity match, no subtitles, logos, or watermarks |
| `continuity` | `mode` (`new_scene` / `continue_scene`) and the hand-off image |
| `prompt` | The rendered text sent to Seedance (template below) |
| `asset_preparation`, `image_reference`, `shots`, `global_direction` | Copies kept for `build_prompts.py` compatibility |

## Grouping shots into clips

- Keep a scene's shots in order, and never mix two scenes in one clip unless the headings continue the same moment.
- Close a clip at 3 shots, about 28 spoken words, 15 s, or when a 5th character would be needed.
- If one shot's dialogue is too long, split it across clips at a line boundary. Only the first part carries the action.
- The first clip of a scene opens on an establishing or wide shot (`camera-knowledge`).

## References and subjects

- Everyone who speaks or is seen in the clip gets an image and a subject, speakers first, up to 4 characters and about 4-5 assets in total (9 at most).
- **Named characters:** `Define the young village girl in @Image 1 as Miri`.
- **Groups** (children, crowd, disciples, families) that appear in the action are one image and one subject: `Define the group of village children around Saba in @Image 5 as the children (a group)`.
- **Unnamed speakers** (GIRL, CHILD, SMALL GIRL, MOTHER IN CROWD) are subjects too. If they belong to a group in the clip, draw them from that group's image and say so: `Define the curly-haired girl in plum from the children in @Image 5, shown alone in @Image 6, as Girl`.
- Voice-over lines (V.O.) don't need the speaker on screen, so they don't add a subject.
- Tag each mention in actions and dialogue with the image: `A GIRL (@Image 6) spots…`, `Girl (@Image 6), excitedly, to the children: {Come on!}`. Don't tag a different group that only shares a word (e.g. "older children" in the lane).
- Scene images go in `REFERENCES` and on the `SCENE:` line. The previous clip's last frame is added when the scene continues.

## Rendered prompt template

```
FORMAT: <n>s / 16:9 / <k> shots / soft cuts
STYLE: <style line>
REFERENCES:
- @Image 1: <role>
SUBJECT:
- Define <description> in @Image 1 as <Name>
SCENE: <scene heading> (@Image N)
SHOTS:
Shot 1: <title from the action>
  Continuity: <hand-off or within-scene note>
  Camera: <shot size>[, <angle>][, <one movement>]
  Action: <verbatim action, names tagged>
  Eyeline: <who looks at whom>
  Dialogue: <Name> (@Image N), <delivery>, to <listener>: {<verbatim line>}
AUDIO:
- Music: （…）
- Voices: <Name> (@Image N) <voice description>; clear English dialogue
CONSTRAINTS:
- One camera move per shot
- Render everything in stylized 3D animation; use the reference images for character design only, not for their 2D drawing style
- …
```

Leave out lines that don't apply (no `Eyeline:` without dialogue, no `Continuity:` on a fresh scene). Never output an empty label.

## Validation checklist

- [ ] Every breakdown action paragraph and dialogue line appears once, word for word, in order, and nothing else is added.
- [ ] Every clip is 4-15 s with up to 3 shots, and `total_seconds` equals the sum.
- [ ] Every speaker on screen and every group in the action has a reference image and a subject, and every `@Image N` used is listed in `REFERENCES`.
- [ ] Every character is tagged consistently throughout the clip.
- [ ] One camera move per shot; dialogue in `{}`, music in `（）`, SFX in `<>`; no `【】`.
- [ ] Constraints include the 3D render rule and no subtitles, logos, or watermarks.
- [ ] Jesus's face is never shown, and Nim is a fox.
- [ ] `data/prompt.json` is valid strict JSON (no raw newlines inside strings).
