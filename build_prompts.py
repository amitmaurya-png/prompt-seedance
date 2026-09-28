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

COMPONENT_SYSTEM = """You write a Seedance 2.0 prompt matching this project's successful reference-based storyboard example.

Return a complete prompt with these sections:
1. Asset preparation: list only the useful reference assets for this clip, using @Image 1, @Image 2, and so on. Describe each asset's role, such as a character reference, scene reference, camera-motion video, or ambient/voice audio. Keep asset roles consistent with how they are named later. Do not claim assets are already supplied; these are preparation instructions.
2. Prompt: one short instruction identifying which image references define the characters and scene, and which video/audio references guide motion or sound when applicable.
3. Shot sequence: write the supplied beats as **Shot 1**, **Shot 2**, and so on, in order. For each, describe the setting/time, concrete visible action and expression, framing or camera movement, and spatial changes. Keep movement natural and use no timestamps.
4. Global direction: close with a concise project-consistent visual style, character-continuity, motion-quality, and audio direction. Include practical constraints such as no subtitles, logos, or watermarks when appropriate.

Preserve every supplied dialogue line exactly once, with its original speaker, in curly braces. Do not invent, omit, reorder, or paraphrase dialogue or events. Do not add unsupported character appearance details. Nim is a small fox, not a dog. If Jesus appears, his face is not shown. Keep the overall look consistent with a warm, painterly storybook animation.

Return JSON only:
{"asset_preparation": ["@Image 1: ..."], "image_reference": "Use ...", "video_reference": "Refer to the camera movement in @Video 1...", "audio_reference": "Use @Audio 1 for ...", "shots": ["Shot content, including any dialogue"], "global_direction": "The entire video should ..."}

asset_preparation, image_reference, shots, and global_direction are required. Set video_reference or audio_reference to an empty string if not applicable.
"""

FIELDS = ("image_reference", "global_direction")
def ask(client, system: str, user: str, max_tokens: int) -> tuple[str, dict]:
    last_error = None
    for attempt in range(3):
        try:
            print(f"Calling {DEFAULT_MODEL}", file=sys.stderr)
            response = client.responses.create(
                model=DEFAULT_MODEL,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_output_tokens=max_tokens,
                text={"format": {"type": "json_object"}},
            )
            text = response.output_text or ""
            if not text.strip():
                raise RuntimeError("OpenAI returned no text.")
            return DEFAULT_MODEL, parse_json(text)
        except json.JSONDecodeError as error:
            last_error = error
            wait = 2 ** attempt
            print(f"Invalid JSON from {DEFAULT_MODEL}. Retrying in {wait}s.", file=sys.stderr)
            time.sleep(wait)
        except Exception as error:
            if not busy(error):
                raise
            last_error = error
            wait = 2 ** attempt
            print(f"{DEFAULT_MODEL} is busy. Retrying in {wait}s.", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"{DEFAULT_MODEL} is busy. Wait a minute and run the command again.") from last_error


def render_prompt(components: dict) -> str:
    missing = [field for field in FIELDS if not str(components.get(field) or "").strip()]
    if missing:
        raise RuntimeError(f"The model left these components empty: {', '.join(missing)}")

    assets = components.get("asset_preparation")
    shots = components.get("shots")
    if not isinstance(assets, list) or not assets:
        raise RuntimeError("The model must return at least one asset-preparation item.")
    if not isinstance(shots, list) or not shots:
        raise RuntimeError("The model must return at least one shot.")

    lines = ["Asset preparation:"]
    lines.extend(f"- {str(asset).strip()}" for asset in assets if str(asset).strip())
    lines.extend(["", "Prompt:", components["image_reference"].strip()])
    for field in ("video_reference", "audio_reference"):
        value = str(components.get(field) or "").strip()
        if value:
            lines.append(value)
    lines.append("")
    lines.extend(f"**Shot {index}:** {str(shot).strip()}" for index, shot in enumerate(shots, 1))
    lines.extend(["", components["global_direction"].strip()])
    return "\n".join(lines) + "\n"


def group_payload(client, label: str, payload: dict, max_tokens: int = 16384) -> tuple[str, list[dict]]:
    used_model, data = ask(
        client,
        GROUP_SYSTEM,
        label + "\n\n" + json.dumps(payload, ensure_ascii=False),
        max_tokens,
    )
    clips = data.get("clips")
    if not isinstance(clips, list) or not clips:
        raise RuntimeError(f"The model returned no clips for {label}")
    return used_model, clips


def group_act(client, act: dict) -> tuple[str, list[dict]]:
    return group_payload(client, "SCREENPLAY ACT:", act)


def group_scene(client, act_name: str, scene: dict) -> tuple[str, list[dict]]:
    payload = {"act": act_name, "scenes": [scene]}
    return group_payload(client, f"SCREENPLAY SCENE ({act_name}):", payload, 8192)


def fill_components(client, clip: dict) -> tuple[str, dict]:
    used_model, data = ask(
        client,
        COMPONENT_SYSTEM,
        "CLIP:\n\n" + json.dumps(clip, ensure_ascii=False),
        8192,
    )
    data["model"] = used_model
    data["formula"] = "advanced"
    data["prompt"] = render_prompt(data)
    data["id"] = clip.get("id")
    data["act"] = clip.get("act")
    data["scene"] = clip.get("scene")
    data["source_shots"] = clip.get("source_shots")
    return used_model, data


def main() -> None:
    load_dotenv(ENV_PATH)
    parser = argparse.ArgumentParser(description="Build Seedance prompts with OpenAI GPT.")
    parser.add_argument("breakdown", type=Path, nargs="?", default=Path("breakdown.json"))
    parser.add_argument("-o", "--output", type=Path, default=Path("prompts.json"))
    parser.add_argument("--max-clips", type=int, default=0, help="Stop after this many clips. 0 means all.")
    args = parser.parse_args()

    if not args.breakdown.is_file():
        raise SystemExit(f"Breakdown not found: {args.breakdown}")
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(f"Put OPENAI_API_KEY in {ENV_PATH}")
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

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
                grouping_model, clips = group_act(client, act)
            else:
                print(f"Grouping {act_name} — {scene.get('scene')}", file=sys.stderr)
                grouping_model, clips = group_scene(client, act_name, scene)
            models_used.add(grouping_model)

            for clip in clips:
                if args.max_clips and len(prompts) >= args.max_clips:
                    break
                print(f"Filling {clip.get('id') or clip.get('scene')}", file=sys.stderr)
                _, filled = fill_components(client, clip)
                models_used.add(filled["model"])
                prompts.append(filled)
            if args.max_clips and len(prompts) >= args.max_clips:
                break
        if args.max_clips and len(prompts) >= args.max_clips:
            break

    result = {
        "source": str(args.breakdown),
        "provider": "openai",
        "requested_model": DEFAULT_MODEL,
        "model": next(iter(models_used)) if len(models_used) == 1 else "mixed" if models_used else DEFAULT_MODEL,
        "models_used": sorted(models_used),
        "clips": prompts,
    }
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(prompts)} clips)")


if __name__ == "__main__":
    main()
