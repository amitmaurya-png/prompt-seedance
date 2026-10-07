# prompt-seedance

Seedance 2.0 video prompts for the animated episode **Little Witnesses: "The Smallest Lunch"**, built from the screenplay, plus tools to check camera direction, characters, and dialogue.

## Folder layout

```
prompt-seedance/
├── README.md
├── requirements.txt
├── .env                      OPENAI_API_KEY (not committed)
├── .github/skills/
│   ├── seedance-prompting/   Agent skill: writing Seedance prompts
│   └── camera-knowledge/     Agent skill: camera terms, genre conventions, camera checks
├── docs/
│   └── approach.md           How the screenplay becomes Seedance prompts
├── data/
│   ├── breakdown.json        Acts, scenes, shots, and dialogue from the screenplay
│   ├── prompt.json           Seedance prompts per clip, with scene continuity
│   ├── camera_angles.json    Camera term → diagram image
│   └── characters.json       Character → reference images, design notes, image prompt
├── scripts/
│   ├── paths.py              Shared folder paths
│   ├── extract_breakdown.py  Screenplay PDF → data/breakdown.json (OpenAI API)
│   ├── build_prompts.py      data/breakdown.json → data/prompts.json (OpenAI API)
│   ├── add_continuity.py     Adds scene continuity to data/prompt.json
│   ├── make_camera_images.py Draws assets/camera/ and data/camera_angles.json
│   ├── make_character_images.py  Draws assets/characters/, data/characters.json, reports/characters.html
│   └── check_camera.py       Checks every shot → reports/camera_report.html
├── assets/
│   ├── camera/               Camera term diagrams (SVG)
│   └── characters/           Character references (PNG for Seedance, SVG source)
└── reports/
    ├── camera_report.html    Shots, camera terms, characters, and dialogue
    └── characters.html       Character reference gallery
```

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
echo "OPENAI_API_KEY=..." > .env      # only needed for extract_breakdown.py and build_prompts.py
```

## Common commands

Run from the repository root.

```bash
python3 scripts/add_continuity.py           # rebuild data/prompt.json with scene continuity
python3 scripts/check_camera.py             # rebuild reports/camera_report.html
python3 scripts/check_camera.py --query "slow dolly-in on the boy"   # camera-term similarity search
python3 scripts/make_camera_images.py       # redraw camera diagrams
python3 scripts/make_character_images.py    # redraw character references and gallery

.venv/bin/python scripts/extract_breakdown.py path/to/screenplay.pdf   # OpenAI API
.venv/bin/python scripts/build_prompts.py                               # OpenAI API
```

Open `reports/camera_report.html` and `reports/characters.html` in a web browser. Keep `assets/` next to `reports/` so images load.

## Data links

Image links stored in `data/*.json` (for example `assets/camera/pan.svg`) are relative to the repository root. Replace any of them with your own file path or a full URL.
