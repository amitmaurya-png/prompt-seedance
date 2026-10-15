#!/usr/bin/env python3
"""Build one Seedance (BytePlus ModelArk) curl command per clip in data/prompt.json -> curl/curl_commands.json.

Each clip's command creates a video task (POST .../contents/generations/tasks) with:
  text        the clip's rendered prompt (plus a voice-reference line when voices are attached)
  images      one image_url per "@Image N" in the clip's references, in @Image order, so the numbering matches
  audio       the voice of each character who speaks in the clip (at most 3), from the skill's references/audio_urls
  params      the clip's api_params (duration matches the clip), plus resolution

URL files (one "NAME : url" per line, in .github/skills/seedance-curl/references/):
  image_urls    character, group, and scene images; NAME is matched to the reference label
                ("Miri character reference" -> MIRI, "Saba's courtyard scene reference" -> SABA's COURTYARD,
                "Children group reference" -> COURTYARD_CHILDREN). A full label also works as NAME.
  audio_urls    character voices (NAME is the character, e.g. SABA)
  last_frames   last frame of each generated clip (NAME is the clip id, e.g. clip-13); fill it in from each
                task's last_frame_url so the next clip continues from it

A reference with no URL gets a "<missing: ...>" placeholder and is listed in the clip's "missing".
The API key is never written: commands read it from $ARK_API_KEY.

Usage:
  python3 scripts/build_curl_commands.py                     # every clip
  python3 scripts/build_curl_commands.py --clip clip-14      # only these clips (others in the file are kept)
  python3 scripts/build_curl_commands.py --model dreamina-seedance-2-0-mini-260615 --resolution 720p
  python3 scripts/build_curl_commands.py --first-frame       # send the previous clip's last frame as first_frame
"""

import argparse
import json
import re

from paths import DATA, ROOT

CURL = ROOT / "curl"
REFS = ROOT / ".github" / "skills" / "seedance-curl" / "references"
PROMPT_JSON = DATA / "prompt.json"
OUT = CURL / "curl_commands.json"
ENDPOINT = "https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks"
MAX_AUDIO = 3

REF_RE = re.compile(r"^@Image (\d+):\s*(.+)$")
LAST_FRAME_RE = re.compile(r"last frame of (clip-\d+)")
KIND_RE = re.compile(r"\s+(character|group|scene|style)?\s*reference\b.*$", re.I)


def norm(name):
    """'SABA's COURTYARD' -> 'saba courtyard'; 'COURTYARD_CHILDREN' -> 'courtyard children'."""
    name = re.sub(r"\(.*?\)", "", name.lower()).replace("_", " ")
    name = re.sub(r"['’]s\b", "", name)
    return " ".join(re.findall(r"[a-z0-9]+", name))


def read_urls(path):
    """'NAME : url' lines -> {NAME: url}; blank lines and # comments are skipped."""
    urls = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            # split on the first ':' that is not part of the URL scheme
            m = re.match(r"\s*(.+?)\s*:\s*(\S+://\S+)\s*$", line)
            if m and not line.lstrip().startswith("#"):
                urls[m.group(1)] = m.group(2)
    return urls


def match_url(label, urls):
    """Find the URL for a reference label: full label, then subject name, then a unique word-subset match."""
    by_norm = {norm(k): v for k, v in urls.items()}
    if norm(label) in by_norm:
        return by_norm[norm(label)]
    subject = norm(KIND_RE.sub("", label))
    if subject in by_norm:
        return by_norm[subject]
    words = set(subject.split())
    hits = [v for k, v in by_norm.items() if words and words <= set(k.split())]
    return hits[0] if len(hits) == 1 else None


def speakers(clip):
    """Characters who speak in the clip, in order of their first line."""
    seen = []
    for shot in clip.get("shot_details", []):
        for line in shot.get("dialogue", []):
            name = line["character"]
            if name not in seen:
                seen.append(name)
    return seen


def build(clip, images, voices, last_frames, args):
    content = []
    missing = []
    for ref in clip["references"]:
        m = REF_RE.match(ref)
        if not m:
            continue
        label = m.group(2)
        role = "reference_image"
        lf = LAST_FRAME_RE.search(label)
        if lf:
            url = last_frames.get(lf.group(1))
            if args.first_frame:
                role = "first_frame"
        else:
            url = match_url(label, images)
        if not url:
            missing.append(f"@Image {m.group(1)}: {label}")
            url = f"<missing: {label}>"
        content.append({"type": "image_url", "image_url": {"url": url}, "role": role})

    voice_names = []
    for name in speakers(clip):
        url = match_url(name, voices)
        if url and len(voice_names) < MAX_AUDIO:
            voice_names.append(name.title())
            content.append({"type": "audio_url", "audio_url": {"url": url}, "role": "reference_audio"})

    text = clip["prompt"].rstrip("\n")
    if voice_names:
        line = "- Voice references: " + "; ".join(
            f"@Audio {i} is {n}'s voice" for i, n in enumerate(voice_names, 1))
        text = re.sub(r"(^- Voices:.*$)", lambda m: m.group(1) + "\n" + line, text, count=1, flags=re.M)

    params = dict(clip["api_params"])
    params["duration"] = clip.get("duration_seconds", params.get("duration"))
    if args.model:
        params["model"] = args.model
    body = {"model": params.pop("model"), "content": [{"type": "text", "text": text}] + content}
    body.update(params)
    body["resolution"] = args.resolution
    return body, missing


def to_curl(body):
    data = json.dumps(body, indent=2, ensure_ascii=False).replace("'", "'\\''")
    return (f"curl --location --request POST '{ENDPOINT}' \\\n"
            "--header \"Authorization: Bearer $ARK_API_KEY\" \\\n"
            "--header 'Content-Type: application/json' \\\n"
            f"--data-raw '{data}'")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clip", nargs="*", help="clip ids to build (default: all)")
    ap.add_argument("--model", help="override each clip's api_params.model")
    ap.add_argument("--resolution", default="720p")
    ap.add_argument("--first-frame", action="store_true",
                    help="send the previous clip's last frame with role first_frame instead of reference_image")
    args = ap.parse_args()

    # strict=False: prompt.json may hold prompts with literal line breaks (edited by hand)
    clips = json.loads(PROMPT_JSON.read_text(encoding="utf-8"), strict=False)["clips"]
    images = read_urls(REFS / "image_urls")
    voices = read_urls(REFS / "audio_urls")
    last_frames = read_urls(REFS / "last_frames")

    out = {"endpoint": ENDPOINT, "source": "data/prompt.json", "builder": "scripts/build_curl_commands.py",
           "api_key": "read from $ARK_API_KEY", "clips": {}}
    if args.clip and OUT.exists():
        out["clips"] = json.loads(OUT.read_text(encoding="utf-8"))["clips"]

    wanted = set(args.clip or [])
    unknown = wanted - {c["id"] for c in clips}
    if unknown:
        ap.error("unknown clip ids: " + ", ".join(sorted(unknown)))

    for clip in clips:
        if wanted and clip["id"] not in wanted:
            continue
        body, missing = build(clip, images, voices, last_frames, args)
        out["clips"][clip["id"]] = {
            "scene": clip["scene"],
            "duration_seconds": body["duration"],
            "previous_clip": clip.get("continuity", {}).get("previous_clip"),
            "missing": missing,
            "request": body,
            "curl": to_curl(body),
        }

    out["clips"] = dict(sorted(out["clips"].items(), key=lambda kv: int(kv[0].split("-")[1])))
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    built = [c for c in out["clips"] if not wanted or c in wanted]
    ready = [c for c in built if not out["clips"][c]["missing"]]
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(built)} clips built, {len(ready)} with every URL filled in")
    gaps = {}
    for c in built:
        for m in out["clips"][c]["missing"]:
            key = LAST_FRAME_RE.sub("clip-N", m.split(": ", 1)[1])
            gaps.setdefault(key, []).append(c)
    for label, ids in sorted(gaps.items(), key=lambda kv: -len(kv[1])):
        print(f"  missing URL ({len(ids)} clips): {label}")


if __name__ == "__main__":
    main()
