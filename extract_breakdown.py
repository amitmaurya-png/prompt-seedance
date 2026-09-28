#!/usr/bin/env python3
"""Extract acts, scenes, and shots from a screenplay PDF with Google Gemini."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from pypdf import PdfReader

DEFAULT_MODEL = "gemini-3.1-pro-preview"
FALLBACK_MODELS = ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash")
ENV_PATH = Path(__file__).resolve().parent / ".env"

SYSTEM = """You extract a screenplay into acts, scenes, and shots.

An act is a heading written as ACT ONE, ACT TWO, ACT THREE, or ACT FOUR.
Text before ACT ONE is the cold open. Label that act "COLD OPEN".
A scene is a heading that starts with INT. or EXT. Copy the heading as written.
MAIN TITLES, FADE OUT, and VISUAL SET PIECE lines are not scenes.
A shot is one visible action plus the dialogue spoken during that action.
Start a new shot when the person acting changes or a new physical action begins.
Ignore page numbers and lines like "-- 4 of 30 --".

Return JSON only, with no markdown:
{"acts": [{"act": "COLD OPEN", "scenes": [{"scene": "EXT. PLACE - TIME", "shots": [{"order": 1, "action": "what we see", "dialogue": [{"character": "NAME", "line": "what they say"}]}]}]}]}
"""


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ[key.strip()] = value.strip().strip("'").strip('"')


def extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def parse_json(text: str) -> dict:
    body = text.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[1]
        fence = body.rfind("```")
        if fence != -1:
            body = body[:fence]
    start = body.find("{")
    end = body.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("model reply did not contain a JSON object")
    return json.loads(body[start : end + 1])


def generate(client, model: str, script: str, max_tokens: int):
    from google.genai import types

    return client.models.generate_content(
        model=model,
        contents=f"SCREENPLAY:\n\n{script}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            response_mime_type="application/json",
            max_output_tokens=max_tokens,
        ),
    )


def busy(error: Exception) -> bool:
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    return status in (429, 503) or "503" in str(error) or "429" in str(error)


def ask_model(client, model: str, script: str, max_tokens: int) -> tuple[str, dict]:
    models = [model] + [item for item in FALLBACK_MODELS if item != model]
    last_error = None
    for candidate in models:
        for attempt in range(3):
            try:
                print(f"Calling {candidate}", file=sys.stderr)
                response = generate(client, candidate, script, max_tokens)
                if not response.text:
                    raise RuntimeError("Gemini returned no text. Check the API key and model name.")
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


def main() -> None:
    load_dotenv(ENV_PATH)
    parser = argparse.ArgumentParser(description="Extract acts, scenes, and shots with Google Gemini.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("breakdown.json"))
    parser.add_argument("--model", default=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--max-tokens", type=int, default=65536)
    args = parser.parse_args()

    if not args.pdf.is_file():
        raise SystemExit(f"PDF not found: {args.pdf}")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(f"Put GEMINI_API_KEY in {ENV_PATH}")

    from google import genai

    script = extract_text(args.pdf)
    used_model, breakdown = ask_model(genai.Client(api_key=api_key), args.model, script, args.max_tokens)
    breakdown = {"source": str(args.pdf), "model": used_model, "acts": breakdown.get("acts", [])}
    args.output.write_text(json.dumps(breakdown, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    scenes = sum(len(act.get("scenes", [])) for act in breakdown["acts"])
    shots = sum(len(scene.get("shots", [])) for act in breakdown["acts"] for scene in act.get("scenes", []))
    print(f"Wrote {args.output} ({len(breakdown['acts'])} acts, {scenes} scenes, {shots} shots)")


if __name__ == "__main__":
    main()
