#!/usr/bin/env python3
"""Turn breakdown.json into Seedance clips using the basic prompt formula."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from extract_breakdown import (
    DEFAULT_MODEL,
    ENV_PATH,
    FALLBACK_MODELS,
    busy,
    load_dotenv,
    parse_json,
)

GROUP_SYSTEM = """You group screenplay shots into Seedance clips.

Seedance has no acts or scenes. One clip lasts 4 to 15 seconds and contains 2 or 3 shots.
Keep breakdown shots together when the place, the people, and the feeling stay the same.
Start a new clip when the place changes, a new person enters, or the action turns.
If one breakdown shot holds more dialogue than a short clip can say, split that shot across clips and keep only the lines that belong to each beat.
Jesus is never given a face. Those beats describe his hands, robe, and silhouette.

Return JSON only:
{"clips": [{"id": "short-id", "act": "ACT ONE", "scene": "the slugline", "source_shots": [1, 2], "beats": [{"action": "one visible action", "dialogue": [{"character": "NAME", "line": "one spoken line"}]}]}]}
"""

COMPONENT_SYSTEM = """You write a Seedance 2.0 basic prompt for a new clip.

Use only the basic formula. Do not write the advanced formula fields
(lighting, color, visual style, image quality, or a separate constraints paragraph).

Nim is a small fox, not a dog. If Jesus appears, his face is not shown.
Spoken lines stay in curly braces, as in {Is it bread?}

Return JSON only, with these three sentences:
{"image_reference": "Reference <who> in Image 1 to generate <the action, the place, one camera move, and the spoken lines>.", "video_reference": "", "audio_reference": "Reference the timbre in Audio 1 to generate <whose voice>."}

image_reference is required.
Leave video_reference empty when this clip is not copying a move from an existing video.
Leave audio_reference empty when no voice timbre is needed.
"""

FIELDS = ("image_reference",)


def ask(client, model: str, system: str, user: str, max_tokens: int) -> tuple[str, dict]:
    from google.genai import types

    models = [model] + [item for item in FALLBACK_MODELS if item != model]
    last_error = None
    for candidate in models:
        for attempt in range(3):
            try:
                print(f"Calling {candidate}", file=sys.stderr)
                response = client.models.generate_content(
                    model=candidate,
                    contents=user,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        response_mime_type="application/json",
                        max_output_tokens=max_tokens,
                    ),
                )
                if not response.text:
                    raise RuntimeError("Gemini returned no text.")
                return candidate, parse_json(response.text)
            except json.JSONDecodeError as error:
                last_error = error
                wait = 2 ** attempt
                print(f"Invalid JSON from {candidate}. Retrying in {wait}s.", file=sys.stderr)
                time.sleep(wait)
            except Exception as error:
                if not busy(error):
                    raise
                last_error = error
                wait = 2 ** attempt
                print(f"{candidate} is busy. Retrying in {wait}s.", file=sys.stderr)
                time.sleep(wait)
        print(f"{candidate} stayed unavailable. Trying another model.", file=sys.stderr)
    raise RuntimeError("Gemini is busy on every model. Wait a minute and run the command again.") from last_error


def render_prompt(components: dict) -> str:
    missing = [field for field in FIELDS if not str(components.get(field) or "").strip()]
    if missing:
        raise RuntimeError(f"Gemini left these components empty: {', '.join(missing)}")

    lines = [components["image_reference"].strip()]
    for field in ("video_reference", "audio_reference"):
        value = str(components.get(field) or "").strip()
        if value:
            lines.append(value)
    return "\n".join(lines) + "\n"


def group_payload(client, model: str, label: str, payload: dict, max_tokens: int = 16384) -> list[dict]:
    _, data = ask(
        client,
        model,
        GROUP_SYSTEM,
        label + "\n\n" + json.dumps(payload, ensure_ascii=False),
        max_tokens,
    )
    clips = data.get("clips")
    if not isinstance(clips, list) or not clips:
        raise RuntimeError(f"Gemini returned no clips for {label}")
    return clips


def group_act(client, model: str, act: dict) -> list[dict]:
    return group_payload(client, model, "SCREENPLAY ACT:", act)


def group_scene(client, model: str, act_name: str, scene: dict) -> list[dict]:
    payload = {"act": act_name, "scenes": [scene]}
    return group_payload(client, model, f"SCREENPLAY SCENE ({act_name}):", payload, 8192)


def fill_components(client, model: str, clip: dict) -> dict:
    _, data = ask(
        client,
        model,
        COMPONENT_SYSTEM,
        "CLIP:\n\n" + json.dumps(clip, ensure_ascii=False),
        8192,
    )
    data["formula"] = "basic"
    data["prompt"] = render_prompt(data)
    data["id"] = clip.get("id")
    data["act"] = clip.get("act")
    data["scene"] = clip.get("scene")
    data["source_shots"] = clip.get("source_shots")
    return data


def main() -> None:
    load_dotenv(ENV_PATH)
    parser = argparse.ArgumentParser(description="Build Seedance prompts from breakdown.json with Gemini.")
    parser.add_argument("breakdown", type=Path, nargs="?", default=Path("breakdown.json"))
    parser.add_argument("-o", "--output", type=Path, default=Path("prompts.json"))
    parser.add_argument("--model", default=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--max-clips", type=int, default=0, help="Stop after this many clips. 0 means all.")
    args = parser.parse_args()

    if not args.breakdown.is_file():
        raise SystemExit(f"Breakdown not found: {args.breakdown}")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(f"Put GEMINI_API_KEY in {ENV_PATH}")

    from google import genai

    breakdown = json.loads(args.breakdown.read_text(encoding="utf-8"))
    client = genai.Client(api_key=api_key)
    prompts = []
    used_model = args.model
    for act in breakdown.get("acts") or []:
        act_name = act.get("act") or "ACT"
        scenes = act.get("scenes") or []
        if args.max_clips:
            scene_iter = scenes
        else:
            scene_iter = [None]

        for scene in scene_iter:
            if scene is None:
                print(f"Grouping {act_name}", file=sys.stderr)
                clips = group_act(client, args.model, act)
            else:
                print(f"Grouping {act_name} — {scene.get('scene')}", file=sys.stderr)
                clips = group_scene(client, args.model, act_name, scene)

            for clip in clips:
                if args.max_clips and len(prompts) >= args.max_clips:
                    break
                print(f"Filling {clip.get('id') or clip.get('scene')}", file=sys.stderr)
                filled = fill_components(client, args.model, clip)
                prompts.append(filled)
            if args.max_clips and len(prompts) >= args.max_clips:
                break
        if args.max_clips and len(prompts) >= args.max_clips:
            break

    result = {"source": str(args.breakdown), "model": used_model, "clips": prompts}
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(prompts)} clips)")


if __name__ == "__main__":
    main()
