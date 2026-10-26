#!/usr/bin/env python3
"""Write data/prompt_slim.json: each clip of data/prompt.json reduced to id, act, scene, and prompt.

data/prompt.json keeps every field (the curl builder and the camera, continuity, emotion, and eyeline scripts
need them); the slim file is a read-only view for reading or sharing the prompts. Re-run this after
prompt.json changes.

Usage:
  python3 scripts/export_prompt_slim.py
"""

import json

from paths import DATA

SOURCE, OUT = DATA / "prompt.json", DATA / "prompt_slim.json"
FIELDS = ("id", "act", "scene", "prompt")


def main():
    clips = json.loads(SOURCE.read_text(encoding="utf-8"), strict=False)["clips"]
    slim = {"source": "data/prompt.json", "builder": "scripts/export_prompt_slim.py", "clip_count": len(clips),
            "clips": [{k: c[k] for k in FIELDS} for c in clips]}
    OUT.write_text(json.dumps(slim, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(DATA.parent)}: {len(clips)} clips with {', '.join(FIELDS)}")


if __name__ == "__main__":
    main()
