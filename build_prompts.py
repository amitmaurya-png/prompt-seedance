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
CLAUDE_DEFAULT_MODEL = "claude-opus-5-5"
CLAUDE_FALLBACK_MODELS = ("claude-sonnet-5",)


def ask(client, provider: str, model: str, system: str, user: str, max_tokens: int) -> tuple[str, dict]:
    models_for_provider = {
        "anthropic": CLAUDE_FALLBACK_MODELS,
        "gemini": FALLBACK_MODELS,
    }
    models = [model] + [item for item in models_for_provider[provider] if item != model]
    last_error = None
    for candidate in models:
        for attempt in range(3):
            try:
                print(f"Calling {candidate}", file=sys.stderr)
                if provider == "anthropic":
                    response = client.messages.create(
                        model=candidate,
                        max_tokens=max_tokens,
                        system=system,
                        messages=[{"role": "user", "content": user}],
                    )
                    text = "\n".join(
                        block.text for block in response.content if getattr(block, "type", None) == "text"
                    )
                else:
                    from google.genai import types

                    response = client.models.generate_content(
                        model=candidate,
                        contents=user,
                        config=types.GenerateContentConfig(
                            system_instruction=system,
                            response_mime_type="application/json",
                            max_output_tokens=max_tokens,
                        ),
                    )
                    text = response.text or ""
                if not text.strip():
                    raise RuntimeError(f"{provider} returned no text.")
                return candidate, parse_json(text)
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
    raise RuntimeError(f"All {provider} models are busy. Wait a minute and run the command again.") from last_error


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


def group_payload(
    client, provider: str, model: str, label: str, payload: dict, max_tokens: int = 16384
) -> tuple[str, list[dict]]:
    used_model, data = ask(
        client,
        provider,
        model,
        GROUP_SYSTEM,
        label + "\n\n" + json.dumps(payload, ensure_ascii=False),
        max_tokens,
    )
    clips = data.get("clips")
    if not isinstance(clips, list) or not clips:
        raise RuntimeError(f"The model returned no clips for {label}")
    return used_model, clips


def group_act(client, provider: str, model: str, act: dict) -> tuple[str, list[dict]]:
    return group_payload(client, provider, model, "SCREENPLAY ACT:", act)


def group_scene(client, provider: str, model: str, act_name: str, scene: dict) -> tuple[str, list[dict]]:
    payload = {"act": act_name, "scenes": [scene]}
    return group_payload(client, provider, model, f"SCREENPLAY SCENE ({act_name}):", payload, 8192)


def fill_components(client, provider: str, model: str, clip: dict) -> tuple[str, dict]:
    used_model, data = ask(
        client,
        provider,
        model,
        COMPONENT_SYSTEM,
        "CLIP:\n\n" + json.dumps(clip, ensure_ascii=False),
        8192,
    )
    data["model"] = used_model
    data["formula"] = "basic"
    data["prompt"] = render_prompt(data)
    data["id"] = clip.get("id")
    data["act"] = clip.get("act")
    data["scene"] = clip.get("scene")
    data["source_shots"] = clip.get("source_shots")
    return used_model, data


def main() -> None:
    load_dotenv(ENV_PATH)
    parser = argparse.ArgumentParser(description="Build Seedance prompts with Claude or Gemini.")
    parser.add_argument("breakdown", type=Path, nargs="?", default=Path("breakdown.json"))
    parser.add_argument("-o", "--output", type=Path, default=Path("prompts.json"))
    parser.add_argument("--provider", choices=("anthropic", "gemini"), default=os.environ.get("PROMPT_PROVIDER", "anthropic"))
    parser.add_argument("--model")
    parser.add_argument("--max-clips", type=int, default=0, help="Stop after this many clips. 0 means all.")
    args = parser.parse_args()
    model_env = "CLAUDE_MODEL" if args.provider == "anthropic" else "GEMINI_MODEL"
    default_model = CLAUDE_DEFAULT_MODEL if args.provider == "anthropic" else DEFAULT_MODEL
    model = args.model or os.environ.get(model_env, default_model)

    if not args.breakdown.is_file():
        raise SystemExit(f"Breakdown not found: {args.breakdown}")
    if args.provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise SystemExit(f"Put ANTHROPIC_API_KEY in {ENV_PATH}")
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
    else:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise SystemExit(f"Put GEMINI_API_KEY in {ENV_PATH}")
        from google import genai

        client = genai.Client(api_key=api_key)

    breakdown = json.loads(args.breakdown.read_text(encoding="utf-8"))
    prompts = []
    models_used = set()
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
                grouping_model, clips = group_act(client, args.provider, model, act)
            else:
                print(f"Grouping {act_name} — {scene.get('scene')}", file=sys.stderr)
                grouping_model, clips = group_scene(client, args.provider, model, act_name, scene)
            models_used.add(grouping_model)

            for clip in clips:
                if args.max_clips and len(prompts) >= args.max_clips:
                    break
                print(f"Filling {clip.get('id') or clip.get('scene')}", file=sys.stderr)
                _, filled = fill_components(client, args.provider, model, clip)
                models_used.add(filled["model"])
                prompts.append(filled)
            if args.max_clips and len(prompts) >= args.max_clips:
                break
        if args.max_clips and len(prompts) >= args.max_clips:
            break

    result = {
        "source": str(args.breakdown),
        "provider": args.provider,
        "requested_model": model,
        "model": next(iter(models_used)) if len(models_used) == 1 else "mixed" if models_used else model,
        "models_used": sorted(models_used),
        "clips": prompts,
    }
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(prompts)} clips)")


if __name__ == "__main__":
    main()
