#!/usr/bin/env python3
"""Turn a curl commands file into a Postman collection that runs the clips one after the other.

Each clip becomes a folder with two requests, run in order by Postman's Collection Runner:
  clip-NN create   POST the clip's request; saves the task id
  clip-NN poll     GET the task until it finishes (repeats itself via setNextRequest); on success saves
                   {{clip-NN_video_url}} and {{clip-NN_last_frame_url}} and the runner moves on to the next clip

The next clip's previous-clip video and last frame are sent as those variables, so each clip uses the
output of the one before it. Any other missing URL becomes an empty variable such as {{img_yonah}}, to fill
in under the collection's Variables tab. Known URLs from references/video_urls and last_frames are prefilled,
so a run can start mid-sequence. The API key is the collection variable {{ARK_API_KEY}} and is never written.

If a create fails (e.g. an empty URL variable), or a task fails, the run stops at that clip.

Usage:
  python3 scripts/build_postman_collection.py                                   # from curl_commands_video_ref.json
  python3 scripts/build_postman_collection.py --source curl/curl_commands.json  # last-frame chaining only
  python3 scripts/build_postman_collection.py --clip clip-02 clip-03 clip-04    # only these clips
  python3 scripts/build_postman_collection.py --poll-seconds 20

Import the output in Postman (File > Import), set ARK_API_KEY under the collection's Variables,
then Run collection.
"""

import argparse
import json
import re
import uuid

from paths import ROOT

CURL = ROOT / "curl"
REFS = ROOT / ".github" / "skills" / "seedance-curl" / "references"
SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"

MISSING_RE = re.compile(r"^<missing: (.+)>$")
PREV_VIDEO_RE = re.compile(r"^video of (clip-\d+)$")
PREV_FRAME_RE = re.compile(r"^last frame of (clip-\d+)")


def read_urls(path):
    """'NAME : url' lines -> {NAME: url}; blank lines and # comments are skipped."""
    urls = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*(.+?)\s*:\s*(\S+://\S+)\s*$", line)
            if m and not line.lstrip().startswith("#"):
                urls[m.group(1)] = m.group(2)
    return urls


def var_for(label):
    """Variable name for a missing URL: the previous clip's outputs, or img_<label slug>."""
    m = PREV_VIDEO_RE.match(label)
    if m:
        return f"{m.group(1)}_video_url"
    m = PREV_FRAME_RE.match(label)
    if m:
        return f"{m.group(1)}_last_frame_url"
    label = re.sub(r"\s*(character|group|scene|style)?\s*reference\b.*$", "", label, flags=re.I)
    return "img_" + "_".join(re.findall(r"[a-z0-9]+", label.lower()))


def with_variables(body, variables):
    """Swap every '<missing: label>' URL in the body for a {{variable}}, and record the variable."""
    body = json.loads(json.dumps(body))
    for item in body["content"]:
        for key in ("image_url", "video_url", "audio_url"):
            if key in item:
                m = MISSING_RE.match(item[key]["url"])
                if m:
                    name = var_for(m.group(1))
                    variables.setdefault(name, "")
                    item[key]["url"] = "{{" + name + "}}"
    return body


def script(listen, lines):
    return {"listen": listen, "script": {"type": "text/javascript", "exec": lines}}


# Post-response script of "create": keep the task id, or stop the run.
CREATE_TEST = """\
const res = pm.response.json();
if (pm.response.code >= 300 || !res.id) {{
  console.error("{clip}: create failed", pm.response.code, JSON.stringify(res));
  pm.execution.setNextRequest(null);
}} else {{
  pm.collectionVariables.set("{clip}_task_id", res.id);
  console.log("{clip}: task", res.id);
}}"""

# Pre-request script of "poll": wait before each check.
POLL_WAIT = "setTimeout(() => {{}}, {ms});"

# Post-response script of "poll": repeat until the task finishes, then save its outputs.
POLL_TEST = """\
const res = pm.response.json();
const status = res.status;
console.log("{clip}:", status);
if (status === "succeeded") {{
  pm.collectionVariables.set("{clip}_video_url", res.content.video_url);
  pm.collectionVariables.set("{clip}_last_frame_url", res.content.last_frame_url || "");
  console.log("{clip}: video", res.content.video_url);
}} else if (status === "queued" || status === "running") {{
  pm.execution.setNextRequest(pm.info.requestName);
}} else {{
  console.error("{clip}: task ended as", status, JSON.stringify(res.error || res));
  pm.execution.setNextRequest(null);
}}"""


def folder(clip_id, entry, endpoint, variables, poll_ms):
    body = with_variables(entry["request"], variables)
    variables.setdefault(f"{clip_id}_task_id", "")
    variables.setdefault(f"{clip_id}_video_url", "")
    variables.setdefault(f"{clip_id}_last_frame_url", "")
    json_header = [{"key": "Content-Type", "value": "application/json"}]
    create = {
        "name": f"{clip_id} create",
        "event": [script("test", CREATE_TEST.format(clip=clip_id).splitlines())],
        "request": {
            "method": "POST",
            "header": json_header,
            "url": endpoint,
            "body": {"mode": "raw", "raw": json.dumps(body, indent=2, ensure_ascii=False),
                     "options": {"raw": {"language": "json"}}},
        },
    }
    poll = {
        "name": f"{clip_id} poll",
        "event": [script("prerequest", [POLL_WAIT.format(ms=poll_ms)]),
                  script("test", POLL_TEST.format(clip=clip_id).splitlines())],
        "request": {"method": "GET", "header": [], "url": endpoint + "/{{" + clip_id + "_task_id}}"},
    }
    return {"name": f"{clip_id} — {entry['scene']} ({entry['duration_seconds']}s)", "item": [create, poll]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="curl/curl_commands_video_ref.json")
    ap.add_argument("--out", help="default: curl/postman_<source name>.json")
    ap.add_argument("--clip", nargs="*", help="clip ids to include (default: all), run in clip order")
    ap.add_argument("--poll-seconds", type=int, default=15)
    args = ap.parse_args()

    source = ROOT / args.source
    data = json.loads(source.read_text(encoding="utf-8"))
    clips = data["clips"]
    wanted = args.clip or list(clips)
    unknown = [c for c in wanted if c not in clips]
    if unknown:
        ap.error("unknown clip ids: " + ", ".join(unknown))
    wanted = sorted(wanted, key=lambda c: int(c.split("-")[1]))

    variables = {"ARK_API_KEY": ""}
    items = [folder(c, clips[c], data["endpoint"], variables, args.poll_seconds * 1000) for c in wanted]

    # prefill outputs of clips that were already generated
    for clip, url in read_urls(REFS / "video_urls").items():
        if f"{clip}_video_url" in variables:
            variables[f"{clip}_video_url"] = url
    for clip, url in read_urls(REFS / "last_frames").items():
        if f"{clip}_last_frame_url" in variables:
            variables[f"{clip}_last_frame_url"] = url

    collection = {
        "info": {
            "_postman_id": str(uuid.uuid5(uuid.NAMESPACE_URL, str(source))),
            "name": f"Seedance clips ({source.stem})",
            "description": f"Built by scripts/build_postman_collection.py from {args.source}. "
                           "Set ARK_API_KEY under Variables, then Run collection: each clip is created, "
                           "polled until it finishes, and its video and last frame feed the next clip.",
            "schema": SCHEMA,
        },
        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{ARK_API_KEY}}", "type": "string"}]},
        "item": items,
        "variable": [{"key": k, "value": v, "type": "string"} for k, v in variables.items()],
    }

    out = ROOT / (args.out or f"curl/postman_{source.stem}.json")
    out.write_text(json.dumps(collection, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    empty = sorted(k for k, v in variables.items()
                   if not v and k.startswith("img_"))
    print(f"Wrote {out.relative_to(ROOT)}: {len(items)} clips, {len(items) * 2} requests")
    if empty:
        print(f"  {len(empty)} image variables to fill in before running: " + ", ".join(empty))


if __name__ == "__main__":
    main()
