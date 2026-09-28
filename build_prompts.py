#!/usr/bin/env python3
"""Turn breakdown.json into Seedance clips. Gemini fills every formula field."""

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

COMPONENT_SYSTEM = """You fill a Seedance 2.0 advanced prompt. Extract each component into its own field.
Do not merge the fields into one paragraph.

The components are:
- precise_subject: who is on screen, with two or three stable traits, bound to Image 1, Image 2, and so on
- action_details: the body movement for the clip, small and specific
- scene_environment: where the clip happens
- lighting_color: time of day, light, and palette
- camera_movement: the clip's overall camera idea
- visual_style: the look, painted storybook for this episode
- image_quality: detail and finish
- constraints: what must stay out, including no subtitles, no logo, and no watermark. If Jesus appears, say his face is not shown.

Also return 2 or 3 shots. Each shot has one camera move, one action, the place, and at most two spoken lines.

Return JSON only:
{"precise_subject": "", "action_details": "", "scene_environment": "", "lighting_color": "", "camera_movement": "", "visual_style": "", "image_quality": "", "constraints": "", "shots": [{"order": 1, "camera_movement": "", "action_details": "", "scene_environment": "", "dialogue": [{"character": "NAME", "line": "words"}]}]}
"""

FIELDS = (
    "precise_subject",
    "action_details",
    "scene_environment",
    "lighting_color",
    "camera_movement",
    "visual_style",
    "image_quality",
    "constraints",
)


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
            except Exception as error:
                if not busy(error):
                    raise
                last_error = error
                wait = 2 ** attempt
                print(f"{candidate} is busy. Retrying in {wait}s.", file=sys.stderr)
                time.sleep(wait)
        print(f"{candidate} stayed unavailable. Trying another model.", file=sys.stderr)
    raise RuntimeError("Gemini is busy on every model. Wait a minute and run the command again.") from last_error


def dialogue_line(turn: dict) -> str:
    character = turn.get("character") or "CHARACTER"
    line = (turn.get("line") or "").strip()
    if not line:
        return ""
    return f"{character} says {{{line}}}"


def render_prompt(components: dict) -> str:
    missing = [field for field in FIELDS if not str(components.get(field) or "").strip()]
    if missing:
        raise RuntimeError(f"Gemini left these components empty: {', '.join(missing)}")

    lines = [
        components["precise_subject"].strip(),
        "",
        components["action_details"].strip(),
        components["scene_environment"].strip(),
        components["lighting_color"].strip(),
        "",
    ]
    for index, shot in enumerate(components.get("shots") or [], start=1):
        order = shot.get("order") or index
        spoken = " ".join(dialogue_line(turn) for turn in shot.get("dialogue") or [] if turn.get("line"))
        piece = " ".join(
            part.strip()
            for part in (
                shot.get("camera_movement") or "",
                shot.get("action_details") or "",
                shot.get("scene_environment") or "",
                spoken,
            )
            if part and part.strip()
        )
        lines.append(f"Shot {order}: {piece}")
    lines.extend(
        [
            "",
            f"{components['visual_style'].strip()} {components['image_quality'].strip()}",
            components["constraints"].strip(),
        ]
    )
    return "\n".join(lines).strip() + "\n"


def group_act(client, model: str, act: dict) -> list[dict]:
    _, data = ask(
        client,
        model,
        GROUP_SYSTEM,
        "SCREENPLAY ACT:\n\n" + json.dumps(act, ensure_ascii=False),
        16384,
    )
    clips = data.get("clips")
    if not isinstance(clips, list) or not clips:
        raise RuntimeError(f"Gemini returned no clips for {act.get('act')}")
    return clips


def fill_components(client, model: str, clip: dict) -> dict:
    _, data = ask(
        client,
        model,
        COMPONENT_SYSTEM,
        "CLIP:\n\n" + json.dumps(clip, ensure_ascii=False),
        8192,
    )
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
        print(f"Grouping {act.get('act')}", file=sys.stderr)
        for clip in group_act(client, args.model, act):
            if args.max_clips and len(prompts) >= args.max_clips:
                break
            print(f"Filling {clip.get('id') or clip.get('scene')}", file=sys.stderr)
            filled = fill_components(client, args.model, clip)
            prompts.append(filled)
        if args.max_clips and len(prompts) >= args.max_clips:
            break

    result = {"source": str(args.breakdown), "model": used_model, "clips": prompts}
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(prompts)} clips)")


if __name__ == "__main__":
    main()
