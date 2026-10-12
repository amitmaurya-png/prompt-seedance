#!/usr/bin/env python3
"""Check continuity in every scene of data/prompt.json and write reports/continuity_report.html.

A scene is a run of clips: one clip that opens a new scene plus the clips that continue it.
For each scene the script checks:
  chain      continuing clips reference the previous clip's last frame, open with a handoff line,
             and have the matching rule; scene openers do not
  state      every clip in the scene carries the same CONTINUITY block, and its time of day fits the heading
  music      the theme "begins" in the first clip and "continues" after
  characters the same definition and voice for a character in every clip; image order follows ORDER;
             characters at the end of a clip don't vanish at the start of the next
  handoff    a clip that ends mid-movement isn't followed by one that opens settled (or the reverse)
  positions  shots don't contradict the scene's screen positions (frame left/right)
  dialogue   lines appear in the same order as data/breakdown.json

Usage:
  python3 scripts/check_continuity.py              # all scenes, prints issues, writes the report
  python3 scripts/check_continuity.py --scene LANE # scenes whose heading contains LANE
"""

import argparse
import html
import json
import re
from collections import defaultdict

from paths import DATA, REPORTS

ORDER = ["Miri", "Nim", "Saba", "Ima", "Tav", "Yonah", "Andrew", "Philip", "Jesus"]
TAG = re.compile(r" \(@Image \d+\)")
MOVING = re.compile(r"\b(run|runs|running|walk|walks|walking|trot|trots|hurr\w*|rush\w*|track\w*|following|chase\w*)\b", re.I)
SETTLED = re.compile(r"\b(sits?|sitting|seated|stands still|static|kneels?|lies)\b", re.I)
CARRY_ON = re.compile(r"\b(still|continu\w*|keeps?|slows?)\b", re.I)
TIME_WORDS = {
    "MORNING": ["morning", "early"], "LATE MORNING": ["late morning", "morning"], "DAY": ["day", "midday", "daylight"],
"LATE AFTERNOON": ["late afternoon", "late-afternoon", "afternoon"],
    "SUNSET": ["sunset", "golden"], "EVENING": ["evening", "lamp"],
}


def motion_state(text, last=True):
    """'moving' or 'settled' from the last (or first) motion word in an action, else None."""
    hits = [(m.start(), "moving") for m in MOVING.finditer(text)] + \
           [(m.start(), "settled") for m in SETTLED.finditer(text)]
    if not hits:
        return None
    return (max if last else min)(hits)[1]


def heading_time(scene):
    tail = scene.split("—")[-1].strip().upper()
    for key in sorted(TIME_WORDS, key=len, reverse=True):
        if key in tail:
            return key
    return None


MEMORY_RE = re.compile(r"\b(remembers?|imagines?|imagining|thinks? of|thinking of|pictures?)\b[^.]*", re.I)


def names_in(text):
    """Characters present in a text; names inside a memory ("She remembers Tav's face") don't count."""
    text = MEMORY_RE.sub("", text)
    return {n for n in ORDER if re.search(rf"\b{n}\b", text)}


def group_scenes(clips):
    scenes, current = [], None
    for c in clips:
        if c["continuity"]["mode"] == "new_scene" or current is None:
            current = {"heading": c["scene"], "act": c["act"], "clips": []}
            scenes.append(current)
        current["clips"].append(c)
    return scenes


def check_scene(scene, char_defs, char_voices):
    issues = []  # (level, clip id, message)
    clips = scene["clips"]

    def add(level, clip, msg):
        issues.append((level, clip["id"], msg))

    states_by_heading = defaultdict(set)
    for c in clips:
        states_by_heading[c["scene"]].add(c["continuity"].get("scene_state"))
    for i, c in enumerate(clips):
        refs, prompt, cont = c["references"], c["prompt"], c["continuity"]
        lastframe = [r for r in refs if "last frame of" in r]
        music = next((a for a in c["audio"] if a.startswith("Music")), "")
        title = c["scene"] == "MAIN TITLES"

        # chain
        if i == 0:
            if lastframe:
                add("warn", c, "Opens a scene but still references a previous clip's last frame.")
            if "begins" not in music and not title:
                add("note", c, "First clip of the scene: music should say the theme 'begins'.")
        else:
            prev = clips[i - 1]
            if cont.get("previous_clip") != prev["id"]:
                add("warn", c, f"Continues the scene but previous_clip is {cont.get('previous_clip')}, not {prev['id']}.")
            if not any(prev["id"] in r for r in lastframe):
                add("warn", c, f"Missing the last frame of {prev['id']} in REFERENCES.")
            if "Continue the same moment from" not in prompt:
                add("warn", c, "Shot 1 has no handoff line ('Continue the same moment from …').")
            if not any(x.startswith("Match lighting") for x in c["constraints"]):
                add("warn", c, "Missing the 'Match lighting, positions, props…' rule.")
            if "continues" not in music:
                add("note", c, "Music should say the theme 'continues from the previous clip'.")

            # handoff between the end of the previous clip and the start of this one
            end, start = prev["shot_details"][-1], c["shot_details"][0]
            end_txt, start_txt = TAG.sub("", end["action"]), TAG.sub("", start["action"])
            end_state, start_state = motion_state(end_txt, last=True), motion_state(start_txt, last=False)
            if end_state == "moving" and start_state == "settled" and not CARRY_ON.search(start_txt):
                add("warn", c, f"{prev['id']} ends with characters moving ('{end_txt[:60]}…') but this clip opens "
                               "settled; add a transition (e.g. 'Still walking, … slows and sits').")
            if end_state == "settled" and start_state == "moving" and not re.search(r"\b(rises|stands|gets up|jumps)\b", start_txt):
                add("note", c, f"{prev['id']} ends settled but this clip opens with characters already moving.")
            next_chars = {m.group(1) for x in c["subjects"] for m in [re.search(r" as (\w+)$", x)] if m}
            for n in sorted(names_in(end_txt) - next_chars):
                add("note", c, f"{n} is in the last shot of {prev['id']} but has no image reference in this clip, "
                               f"so {n} may vanish mid-scene (add {n} or show them leaving).")

        # scene state
        if not title:
            if not cont.get("scene_state"):
                add("warn", c, "No CONTINUITY block for this scene.")
            elif len(states_by_heading[c["scene"]]) > 1:
                add("warn", c, "CONTINUITY block differs from other clips with the same scene heading.")

        # characters
        chars = [m.group(1) for s in c["subjects"] for m in [re.search(r" as (\w+)$", s)] if m]
        if chars != sorted(chars, key=lambda n: ORDER.index(n) if n in ORDER else 99):
            add("warn", c, f"Character images are out of the fixed order: {', '.join(chars)}.")
        for s in c["subjects"]:
            m = re.search(r"^Define (.+) in @Image \d+ as (\w+)$", s)
            if m:
                char_defs[m.group(2)].add(m.group(1))
        for a in c["audio"]:
            if a.startswith("Voices:"):
                for name, desc in re.findall(r"(\w+) \((?:@Image \d+|voice-over)\) ([^;]+)", a):
                    char_voices[name].add(desc.strip())

        # screen positions from the scene state
        state = cont.get("scene_state") or ""
        sides = dict(re.findall(r"(\w+) frame (left|right)", state))
        for k, s in enumerate(c["shot_details"], 1):
            text = TAG.sub("", s["action"] + " " + s["camera"])
            for name, side in re.findall(r"(\w+) (?:\w+ ){0,3}frame (left|right)", text):
                if name in sides and sides[name] != side:
                    add("warn", c, f"Shot {k}: {name} is frame {side}, but the scene places {name} frame {sides[name]}.")

    # time of day
    t = heading_time(scene["heading"])
    state = clips[0]["continuity"].get("scene_state")
    if t and state and not any(w in state.lower() for w in TIME_WORDS[t]):
        issues.append(("note", clips[0]["id"], f"Heading says {t} but the CONTINUITY block doesn't mention it."))
    return issues


def check_dialogue(clips):
    bd = json.loads((DATA / "breakdown.json").read_text())
    want = [l["line"] for a in bd["acts"] for s in a["scenes"] for sh in s["shots"] for l in sh.get("dialogue", [])]
    got = [(c["id"], l["line"]) for c in clips for s in c["shot_details"] for l in s["dialogue"]]
    for i, (w, (cid, g)) in enumerate(zip(want, got)):
        if w != g:
            return [("warn", cid, f"Dialogue differs from breakdown.json at line {i + 1}: '{g}' (expected '{w}').")]
    if len(want) != len(got):
        return [("warn", got[-1][0] if got else "-", f"{len(got)} dialogue lines in prompts, {len(want)} in breakdown.")]
    return []


def render(scenes, results, film_issues, path):
    def badge(level):
        return {"warn": "⚠", "note": "ℹ"}[level]
    total_w = sum(1 for r in results for i in r if i[0] == "warn") + sum(1 for i in film_issues if i[0] == "warn")
    total_n = sum(1 for r in results for i in r if i[0] == "note") + sum(1 for i in film_issues if i[0] == "note")
    rows = []
    for sc, issues in zip(scenes, results):
        ok = not issues
        items = "".join(f'<li class="{lv}">{badge(lv)} <b>{cid}</b> {html.escape(msg)}</li>' for lv, cid, msg in issues)
        chain = " → ".join(c["id"] for c in sc["clips"])
        rows.append(f'<section class="scene {"ok" if ok else "bad"}"><header><b>{html.escape(sc["heading"])}</b>'
                    f'<span class="muted">{html.escape(sc["act"])} · {len(sc["clips"])} clips</span>'
                    f'<span class="st">{"✓ continuous" if ok else f"{len(issues)} issue(s)"}</span></header>'
                    f'<div class="chain">{chain}</div>'
                    + (f'<div class="state">{html.escape(sc["clips"][0]["continuity"].get("scene_state") or "")}</div>'
                       if sc["clips"][0]["continuity"].get("scene_state") else "")
                    + (f"<ul>{items}</ul>" if items else "") + "</section>")
    film = "".join(f'<li class="{lv}">{badge(lv)} <b>{cid}</b> {html.escape(msg)}</li>' for lv, cid, msg in film_issues)
    REPORTS.mkdir(exist_ok=True)
    path.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Continuity Report</title><style>
:root{{--bg:#f6f7f9;--card:#fff;--text:#1d2430;--muted:#5b6574;--line:#e2e6eb;--warn:#b54708;--note:#175cd3;--ok:#3f9b5f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#12161c;--card:#1b2129;--text:#e6e9ee;--muted:#9aa4b2;--line:#2c343f;--warn:#f7b267;--note:#8fb5ff;--ok:#6fcf8f}}}}
body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px}}.muted{{color:var(--muted)}}
.stats{{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}}.stat{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 16px}}
.stat b{{display:block;font-size:22px}}.scene{{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--ok);border-radius:10px;margin:12px 0;padding:12px 14px}}
.scene.bad{{border-left-color:var(--warn)}}header{{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline}}.st{{margin-left:auto;font-weight:700}}
.ok .st{{color:var(--ok)}}.bad .st{{color:var(--warn)}}.chain{{font-size:13px;color:var(--muted);margin:4px 0}}
.state{{font-size:13px;background:var(--bg);border-radius:8px;padding:6px 10px;margin:6px 0}}ul{{margin:6px 0 0;padding-left:18px}}
li.warn{{color:var(--warn)}}li.note{{color:var(--note)}}
</style></head><body><main><h1>Continuity report</h1>
<p class="muted">Scene-by-scene continuity checks for data/prompt.json.</p>
<div class="stats"><div class="stat"><b>{len(scenes)}</b>scenes</div>
<div class="stat"><b>{sum(1 for r in results if not r)}</b>fully continuous</div>
<div class="stat"><b>{total_w}</b>warnings</div><div class="stat"><b>{total_n}</b>notes</div></div>
{f'<h2>Whole film</h2><ul>{film}</ul>' if film else ''}
<h2>Scenes</h2>{''.join(rows)}</main></body></html>""")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scene", default="", help="only scenes whose heading contains this text")
    ap.add_argument("--out", default=REPORTS / "continuity_report.html")
    args = ap.parse_args()

    clips = json.loads((DATA / "prompt.json").read_text(), strict=False)["clips"]
    scenes = [s for s in group_scenes(clips) if args.scene.upper() in s["heading"].upper()]
    char_defs, char_voices = defaultdict(set), defaultdict(set)
    results = [check_scene(s, char_defs, char_voices) for s in scenes]

    film = check_dialogue(clips) if not args.scene else []
    for name, defs in sorted(char_defs.items()):
        if len(defs) > 1:
            film.append(("warn", name, f"{name} is defined differently across clips: {' / '.join(sorted(defs))}."))
    for name, voices in sorted(char_voices.items()):
        if len(voices) > 1:
            film.append(("warn", name, f"{name} has different voice descriptions: {' / '.join(sorted(voices))}."))

    from pathlib import Path
    render(scenes, results, film, Path(args.out))
    n_issues = sum(len(r) for r in results) + len(film)
    print(f"Checked {len(scenes)} scenes ({sum(len(s['clips']) for s in scenes)} clips): "
          f"{sum(1 for r in results if not r)} fully continuous, {n_issues} issue(s) -> {args.out}")
    for lv, cid, msg in film:
        print(f"  {'⚠' if lv == 'warn' else 'ℹ'} [film] {cid}: {msg}")
    for sc, issues in zip(scenes, results):
        for lv, cid, msg in issues:
            print(f"  {'⚠' if lv == 'warn' else 'ℹ'} {sc['heading']} · {cid}: {msg}")


if __name__ == "__main__":
    main()
