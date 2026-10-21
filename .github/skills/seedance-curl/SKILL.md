---
name: seedance-curl
description: "Create curl commands that send each clip in data/prompt.json to the Seedance 2.0 API (BytePlus ModelArk), and save them per clip in curl/curl_commands.json. Each command carries the clip's prompt, its @Image references as image URLs in the same order, the speakers' voice references, the previous clip's last frame, and the clip's duration. Use when creating, updating, or checking curl commands or API requests for clips, adding image, voice, or last-frame URLs, or chaining a clip from the previous clip's last frame."
argument-hint: "[clip id(s), or 'all clips']"
---

# Seedance curl commands

Turn every clip in `data/prompt.json` into a ready-to-run curl command that creates a Seedance video task, and store it under the clip's id in `curl/curl_commands.json`.

## Files

| File | What it holds |
|---|---|
| [references/image_urls](./references/image_urls) | `NAME : url` per line: character, group, and scene images (`MIRI`, `COURTYARD_CHILDREN`, `SABA's COURTYARD`) |
| [references/audio_urls](./references/audio_urls) | `NAME : url` per line: character voices (`SABA`, `MIRI`) |
| [references/last_frames](./references/last_frames) | `clip-NN : url` per line: the last frame of each generated clip, from the finished task's `last_frame_url` |
| [references/example_request.sh](./references/example_request.sh) | A hand-written request for clip-14, for reference (the generated commands replace it) |
| `curl/curl_commands.json` | Output: `clips.<clip id>` → `scene`, `duration_seconds`, `previous_clip`, `missing`, `request` (JSON body), `curl` (command) |
| [build_curl_commands.py](../../../scripts/build_curl_commands.py) | Builds the output from `data/prompt.json` and the URL files |

## Commands

Run from the repository root.

```bash
python3 scripts/build_curl_commands.py                    # every clip
python3 scripts/build_curl_commands.py --clip clip-14     # only these clips; other clips in the file are kept
python3 scripts/build_curl_commands.py --model dreamina-seedance-2-0-mini-260615 --resolution 720p
python3 scripts/build_curl_commands.py --first-frame      # previous last frame sent as role first_frame
python3 scripts/build_curl_commands.py --video-ref        # previous clip's video as @Video 1 -> curl/curl_commands_video_ref.json
```

To run a command: `export ARK_API_KEY=...`, then copy the clip's `curl` value into the terminal.

## How a clip becomes a request

1. **Text**: the clip's `prompt`, unchanged. When voices are attached, a line `- Voice references: @Audio 1 is Saba's voice` is added under `- Voices:`.
2. **Images**: one `image_url` per `@Image N` in the clip's `references`, in @Image order, so `@Image N` in the prompt is the Nth image sent. Never reorder, skip, or add images, or the numbering breaks.
3. **URL matching**: a reference label is matched to a `NAME` in `references/image_urls`. It tries the full label first ("Saba's courtyard scene reference"), then the subject ("Saba's courtyard" → `SABA's COURTYARD`), then a unique word match ("Children" → `COURTYARD_CHILDREN`). Case, `_`, and `'s` are ignored. If a match is wrong or ambiguous, add a line whose NAME is the exact label.
4. **Last frame**: "last frame of clip-13" takes its URL from `references/last_frames`. Generate clips in order, add each finished clip's `last_frame_url` there, and rebuild the next clip.
5. **Audio**: the voice of each character with dialogue in the clip, in order of their first line, at most 3.
6. **Video extension** (`--video-ref` only): a clip that continues from a previous clip becomes an extend task on that clip's video. The video is sent first, as `video_url` with role `reference_video`, taking its URL from `references/video_urls` (the finished task's `video_url`, or a trimmed tail you host). The prompt opens with `Extend @Video 1 forward: generate the content after @Video 1, continuing the same moment without a cut, as described below.` Following the official guide, `@Video 1` is not listed under `REFERENCES` (naming it as a reference makes the model treat it as a style/motion reference). The previous clip's last-frame image is not sent; its `Continuity:` lines are dropped (the model blends the join itself) except for who is still present, and its `Match …` constraint becomes `Keep … consistent with @Video 1`. Clips that open a scene get no video. The output goes to `curl/curl_commands_video_ref.json`, so `curl/curl_commands.json` stays unchanged.
7. **Params**: the clip's `api_params`, with `duration` set to the clip's `duration_seconds` so it matches `FORMAT`, plus `resolution` (default `720p`). `--model` overrides the model.

A reference with no URL is sent as `<missing: label>` and listed in the clip's `missing`. A clip is ready to send only when `missing` is empty.

## Workflow

1. Add any new URLs to `references/image_urls` or `references/audio_urls`.
2. Run the builder. It prints how many clips are complete and which URLs are missing, most-used first.
3. For the clip you're about to generate, check `missing` in `curl/curl_commands.json`. A missing last frame means the previous clip hasn't been generated or recorded yet.
4. Run the clip's `curl`, then poll `GET .../contents/generations/tasks/<task id>` until it succeeds, and put its `last_frame_url` in `references/last_frames`.
5. Rebuild the next clip with `--clip clip-NN`.

## Rules

- Never write an API key into any file. Commands read it from `$ARK_API_KEY`. Keep keys in `.env` (git-ignored).
- Create a task with `POST` and a body. `GET` with `filter.*` query parameters only lists existing tasks.
- Don't edit prompts here. Prompt wording belongs to `seedance-prompting` and the other prompt skills. Change `data/prompt.json` there, then rebuild.
- Leave `data/prompt.json` unchanged. This skill only reads it (literal line breaks inside prompts are accepted) and writes `curl/curl_commands.json`.
- `--first-frame` locks the opening frame exactly, but Seedance 2.0 may not accept `first_frame` together with `reference_image` items. If the API rejects it, rebuild without the flag.
