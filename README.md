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
│   ├── camera-knowledge/     Agent skill: camera terms, genre conventions, camera checks
│   ├── scene-continuity/     Agent skill: checks and fixes continuity in every scene
│   ├── clip-continuity/      Agent skill: checks and fixes every clip and clip-to-clip boundary
│   ├── emotion-detector/     Agent skill: detects each line's emotion and the conversation mood
│   ├── eyeline-direction/    Agent skill: who each line is said to, and where characters look
│   ├── skit-to-prompt-json/  Agent skill: builds data/prompt.json from a skit, verbatim and in order
│   └── seedance-curl/        Agent skill: one Seedance API curl command per clip → curl/curl_commands.json
├── docs/
│   └── approach.md           How the screenplay becomes Seedance prompts
├── data/
│   ├── breakdown.json        Acts, scenes, shots, and dialogue from the screenplay
│   ├── prompt.json           Seedance prompts per clip, with scene continuity
│   ├── camera_angles.json    Camera term → diagram image
│   └── characters.json       Character → reference images, design notes, image prompt
├── scripts/
│   ├── paths.py              Shared folder paths
│   ├── parse_screenplay.py   Screenplay PDF → data/breakdown.json, every action and line verbatim (no AI)
│   ├── extract_breakdown.py  Screenplay PDF → data/breakdown.json (OpenAI API, summarised; older method)
│   ├── build_prompt_json.py  data/breakdown.json → data/prompt.json, verbatim actions and dialogue (no AI)
│   ├── build_prompts.py      data/breakdown.json → data/prompts.json (OpenAI API)
│   ├── add_continuity.py     Adds scene continuity to data/prompt.json
│   ├── make_camera_images.py Draws assets/camera/ and data/camera_angles.json
│   ├── make_character_images.py  Draws assets/characters/, data/characters.json, reports/characters.html
│   ├── camera_suggest.py     Detects a shot's genre/mood and suggests a camera
│   ├── apply_camera.py       Writes reviewed camera lines into data/prompt.json
│   ├── check_camera.py       Checks every shot → reports/camera_report.html
│   ├── check_continuity.py   Checks every scene → reports/continuity_report.html
│   ├── fix_continuity.py     Fixes continuity breaks between clips in data/prompt.json
│   ├── check_clips.py        Checks/fixes every clip and boundary (transitions, cast, timing)
│   ├── detect_emotions.py    Adds emotion/delivery to each dialogue line in data/prompt.json
│   ├── add_eyelines.py       Adds eyelines and each line's listener to data/prompt.json
│   └── build_curl_commands.py  data/prompt.json → curl/curl_commands.json (Seedance API request per clip)
├── curl/
│   └── curl_commands.json    Curl command and request body per clip (URL inputs: .github/skills/seedance-curl/references/)
├── assets/
│   ├── camera/               Camera term diagrams (SVG)
│   └── characters/           Character references (PNG for Seedance, SVG source)
└── reports/
    ├── camera_report.html    Shots, camera terms, characters, and dialogue
    ├── continuity_report.html  Scene-by-scene continuity checks
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
python3 scripts/build_prompt_json.py --all  # rebuild data/prompt.json from breakdown.json, then all skills' steps
python3 scripts/add_continuity.py           # rebuild data/prompt.json with scene continuity
python3 scripts/check_camera.py             # rebuild reports/camera_report.html
python3 scripts/check_camera.py --query "slow dolly-in on the boy"   # camera-term similarity search
python3 scripts/camera_suggest.py --describe "Yonah hesitates, then offers his lunch"   # mood → camera suggestion
python3 scripts/check_continuity.py         # check continuity in every scene
python3 scripts/fix_continuity.py --dry-run # preview continuity fixes (drop --dry-run to apply)
python3 scripts/check_clips.py --fix        # clip-level continuity and scene transitions
python3 scripts/detect_emotions.py          # dialogue emotions and conversation moods (--dry-run to preview)
python3 scripts/add_eyelines.py             # eyelines and who each line is said to (--dry-run to preview)
python3 scripts/build_curl_commands.py      # Seedance curl command per clip (--clip clip-14 for one clip)
python3 scripts/make_camera_images.py       # redraw camera diagrams
python3 scripts/make_character_images.py    # redraw character references and gallery

.venv/bin/python scripts/parse_screenplay.py [path/to/screenplay.pdf]  # verbatim breakdown, no AI
.venv/bin/python scripts/extract_breakdown.py path/to/screenplay.pdf   # OpenAI API
.venv/bin/python scripts/build_prompts.py                               # OpenAI API
```

Open `reports/camera_report.html` and `reports/characters.html` in a web browser. Keep `assets/` next to `reports/` so images load.

## Data links

Image links stored in `data/*.json` (for example `assets/camera/pan.svg`) are relative to the repository root. Replace any of them with your own file path or a full URL.
