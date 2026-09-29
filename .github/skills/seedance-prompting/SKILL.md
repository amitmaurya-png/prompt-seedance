---
name: seedance-prompting
description: "Create, refine, or review Seedance video prompts using this project's rules and reference examples. Use for shot planning, camera and motion direction, image/video/audio references, and prompt continuity checks."
---

# Seedance Prompting

Create original, actionable prompts for Seedance 2.x. Follow the user's requested model version, format, duration, aspect ratio, and style when provided. Do not assume every Seedance version has identical capabilities.

## Reference Corpus

The skill includes [prompt_examples.txt](./references/prompt_examples.txt), a large collection of attributed community examples.

- Search the reference file for the requested category or technique, such as POV, product advertising, character references, continuous camera movement, dialogue, or transformations.
- Read only a few relevant excerpts (usually 2-4 examples); do not load the entire file for a routine prompt request.
- Treat examples as inspiration for structure and directing techniques, not text to copy. Write original prompt language and do not reproduce long passages.
- When discussing a particular example, identify its title and creator/source when that information is available.
- The source repository contains mixed license statements and notes that authors retain rights to original prompt text. Do not assume blanket permission to republish the collection or its prompts.
- The collection mixes Seedance 2.0 and 2.5 labels. Follow the user's requested version and verify version-specific details instead of inferring them from a sample.

## Workflow

1. Determine whether the user wants a new prompt, a revision, a critique, or structured output for this project's scripts. Ask a focused question only if missing information would materially change the result.
2. Identify the subject, visible action, setting, emotional beat, visual style, clip duration, and any supplied references. Keep each generation focused on one clip unless the user asks for a sequence.
3. Search the reference corpus for a small number of relevant examples. Extract useful patterns such as shot progression, camera logic, motion intensity, continuity rules, and sound cues; do not copy their wording or unrelated details.
4. Organize the prompt so the model can distinguish subject, action, camera, setting, style, sound, and constraints. Use concrete, visible actions instead of mood-only directions.
5. For each shot, specify the framing, one primary camera move, the action, and any important environmental response. Make motion intensity and transitions explicit. Use timing only when the user or target workflow requests it.
6. For image references, use the supplied image as the authority for referenced appearance; describe the action, camera, and changes without unnecessarily re-describing the image. Preserve reference tokens and assign each asset a consistent role.
7. Use video references to guide motion only when supplied. Use audio references for sound or voice only when supplied. Do not claim an asset exists when it was not provided; leave optional reference fields empty when inapplicable.
8. Preserve user-provided dialogue exactly, with its original speaker, and include it exactly once. Do not invent, omit, reorder, or paraphrase story events or dialogue.
9. Review for contradictions, unsupported appearance details, continuity errors, overloaded shots, and conflicting camera or transition instructions. Prefer a few clear constraints over repeated generic quality tags.

## Project Continuity

- For this project's screenplay, Nim is a fox, not a dog.
- If Jesus appears, show only his hands, robe, and silhouette; never show his face.
- Keep the established warm, painterly storybook animation style when working on this screenplay unless the user requests a change.
- Follow `approach.md` and the system prompts in `build_prompts.py` when generating or reviewing prompts for this repository.

## Output Formats

For a standalone request, return a clean, copyable Seedance prompt. Include only sections useful for that prompt; a common layout is asset preparation, reference instructions, shot sequence, and global direction.

When the user requests output compatible with `build_prompts.py`, return JSON with this shape:

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