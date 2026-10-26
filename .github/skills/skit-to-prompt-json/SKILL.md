---
name: skit-to-prompt-json
description: "Create data/prompt.json for a given skit or screenplay: parse it verbatim into data/breakdown.json, group its shots into Seedance 2.0 clips of 4-15 s, and write each clip's references, subjects, scene, shots, audio, constraints, and rendered prompt, keeping every action and dialogue line word for word and in screenplay order. Coordinates the camera, continuity, emotion, and eyeline skills. Use when building, rebuilding, or reviewing prompt.json for a skit, or adding a new skit's prompts."
argument-hint: "[skit PDF path, or clip id to rebuild]"
---

# Skit to prompt.json

Turn a skit into Seedance 2.0 clip prompts in `data/prompt.json`. The skit is the only source of story: copy its actions and dialogue word for word, in its order, and add only direction (camera, continuity, eyelines, emotion, audio, constraints) around them. Don't add, drop, merge, reorder, or paraphrase anything.

## References

| File | Use it for |
|---|---|
| [prompt_json_rules.md](./references/prompt_json_rules.md) | The clip schema, how shots are grouped into clips, references and subjects (including groups and unnamed speakers), the rendered prompt template, and the validation checklist |
| [prompt_syntax.md](../seedance-prompting/references/prompt_syntax.md) | Block order and grammar of the rendered prompt |
| [seedance_2_0_prompt_guide.md](../seedance-prompting/references/seedance_2_0_prompt_guide.md) | Seedance 2.0 limits: 4-15 s, ≤9 images (aim for 4-5), ≤4 characters, one camera move per shot, `{}` `（）` `<>` symbols |

Other skills own parts of each clip. Follow them for those parts:

| Skill | Owns |
|---|---|
| `seedance-prompting` | Prompt syntax, labels, style |
| `camera-knowledge` | Each shot's `Camera:` line, genre and mood |
| `scene-continuity` | Continuity within a scene (positions, props, lighting) |
| `clip-continuity` | Hand-offs between clips (`@Image N: last frame of clip-…`) |
| `emotion-detector` | Each line's emotion, intensity, and delivery |
| `eyeline-direction` | Who each line is said to and where characters look |

## Scripts

Run from the repository root.

| Script | When to run it |
|---|---|
| `python3 scripts/parse_screenplay.py [path/to/skit.pdf]` | Skit PDF → `data/breakdown.json`, every action and line verbatim (default `pdf_document/TSL.pdf`; `--dry-run` for a summary) |
| `python3 scripts/build_prompt_json.py --dry-run` | Preview the clip grouping |
| `python3 scripts/build_prompt_json.py --all` | Write `data/prompt.json` (backup in `data/backups/`), then emotions, eyelines, continuity, fixes, and reports |
| `python3 scripts/add_continuity.py` | Re-render every clip's `prompt` text after editing fields |
| `python3 scripts/keep_present.py [--dry-run]` | Keep every character on screen until they explicitly leave the scene (image while there is room, otherwise named as still present) |
| `python3 scripts/check_clips.py` / `check_continuity.py` / `check_camera.py` | Review clips, continuity, and camera (HTML reports in `reports/`) |

## Workflow

1. **Parse.** Run `parse_screenplay.py` on the skit. Check the summary (acts, scenes, shots, action paragraphs, dialogue lines) against the PDF. Fix parser errors in the parser, never by hand-editing the text.
2. **Set up the skit.** For a new skit, update `build_prompt_json.py`'s `ROSTER`, `CHAR_DEF`, `LOCATIONS`, and `STYLE`. This skill doesn't generate assets: reference images are supplied separately, and the prompts only refer to them as `@Image N`.
3. **Build.** Run `build_prompt_json.py --dry-run`, check the grouping, then run `--all`.
4. **Add references and subjects.** Every character who speaks or is seen in a clip has a reference image and a `Define … in @Image N as <Name>` subject. That includes groups (the children, the crowd) and unnamed speakers (Girl, Child, Mother In Crowd). See the rules file.
   Then run `keep_present.py`: characters stay on screen until the screenplay has them leave, so nobody vanishes between clips.
5. **Review direction** with the owning skills: camera lines, continuity hand-offs, emotions, and eyelines.
6. **Validate** with the checklist in the rules file, and compare `prompt.json` with `breakdown.json`: same actions, same dialogue, same order, nothing invented.
7. **Report** the clip count, total seconds, and anything you set by hand.

## Rules

- `breakdown.json` is the source of truth. Copy actions and dialogue verbatim and in order. Tag character names with their image (`Miri (@Image 1)`), but don't otherwise change the text.
- One clip is 4-15 s, up to 3 shots, about 28 spoken words, and up to 4 main characters. Split long dialogue across clips rather than cutting it.
- Render in stylized 3D. Reference images are 2D drawings and are used for design only, so say so in every clip's constraints.
- When the user asks for a change "at the prompt level", edit only `data/prompt.json`. Don't change the scripts, and tell the user that a rebuild would overwrite the edit.
- Project rules: Nim is a fox; Jesus's face is never shown (hands, robe, silhouette, or from behind only); no subtitles, logos, or watermarks.
