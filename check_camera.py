#!/usr/bin/env python3
"""Check the camera direction of every shot in prompt.json and build an HTML report.

For each shot's Camera line the script:
  1. finds known camera terms (exact phrases and aliases, e.g. "dolly-in" -> Push-in),
  2. runs a similarity search (character-trigram TF-IDF vectors, cosine similarity) on the
     leftover words, so misspellings and unusual wording still map to the closest term,
  3. checks Seedance rules: one movement per shot, no "static" plus a move, a recognisable term,
  4. compares neighbouring shots in a scene (big jumps in shot size, scenes that open close up),
  5. works out which characters are in the shot and which of them the camera is on (from characters.json).

Usage:
  python3 check_camera.py                       # writes camera_report.html
  python3 check_camera.py --out report.html
  python3 check_camera.py --query "camera circles slowly around the boy"   # similarity search only
"""

import argparse
import difflib
import html
import json
import math
import os
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent

# term -> (category, aliases). "*" in an alias matches any single word.
TERMS = {
    "Establishing shot": ("size", ["establishing shot", "establishing", "establishing view"]),
    "Wide shot": ("size", ["wide shot", "wide", "ws", "wide angle"]),
    "Long shot": ("size", ["long shot", "full shot", "full body shot"]),
    "Medium long shot": ("size", ["medium long shot", "medium wide", "medium wide shot", "mls", "cowboy shot"]),
    "Medium shot": ("size", ["medium shot", "medium", "mid shot", "waist shot"]),
    "Medium close-up": ("size", ["medium close up", "mcu", "head and shoulders"]),
    "Close-up": ("size", ["close up", "cu", "close shot"]),
    "Big close-up": ("size", ["big close up", "bcu", "tight close up"]),
    "Extreme close-up": ("size", ["extreme close up", "ecu", "macro"]),
    "Two-shot": ("framing", ["two shot", "2 shot", "close two shot"]),
    "Three-shot": ("framing", ["three shot", "3 shot"]),
    "Over-the-shoulder shot": ("framing", ["over the shoulder", "ots", "over * shoulder"]),
    "Shot/reverse shot": ("framing", ["shot reverse shot", "reverse shot"]),
    "Point-of-view shot": ("framing", ["point of view", "pov"]),
    "Insert shot": ("framing", ["insert", "insert shot", "cutaway"]),
    "Eye-level shot": ("angle", ["eye level", "eye line"]),
    "High-angle shot": ("angle", ["high angle", "looking down", "from above"]),
    "Low-angle shot": ("angle", ["low angle", "low", "looking up", "from below"]),
    "Overhead shot": ("angle", ["overhead", "top down", "bird's eye", "birds eye", "straight down",
                                "looking straight down"]),
    "Aerial shot": ("angle", ["aerial", "drone"]),
    "Static shot": ("movement", ["static", "fixed camera", "locked off", "fixed", "still camera"]),
    "Pan": ("movement", ["pan", "pans", "panning"]),
    "Tilt": ("movement", ["tilt", "tilts", "tilting"]),
    "Tracking shot": ("movement", ["tracking", "tracking shot", "following", "following shot", "follows",
                                   "walking", "alongside", "trucking"]),
    "Push-in": ("movement", ["push in", "pushes in", "dolly in", "move in", "track in"]),
    "Pull-back": ("movement", ["pull back", "pulls back", "dolly out", "pull out", "track out"]),
    "Crane shot": ("movement", ["crane", "boom", "jib"]),
    "Arc shot": ("movement", ["arc", "arc around", "orbit", "orbits", "circles"]),
    "Zoom": ("movement", ["zoom", "zoom in", "zoom out", "zooms"]),
    "Dolly zoom": ("movement", ["dolly zoom", "vertigo effect", "zolly"]),
    "Shallow focus": ("focus", ["shallow focus", "shallow depth of field", "background blurred", "bokeh"]),
    "Deep focus": ("focus", ["deep focus", "everything sharp"]),
    "Rack focus": ("focus", ["rack focus", "focus pull", "pull focus"]),
}

# Closest (0) to widest (8), for spotting big jumps between neighbouring shots.
SIZE_RANK = {"Extreme close-up": 0, "Big close-up": 1, "Close-up": 2, "Medium close-up": 3, "Medium shot": 4,
             "Medium long shot": 5, "Long shot": 6, "Wide shot": 7, "Establishing shot": 8}
IMPLIED_RANK = {"Two-shot": 4, "Three-shot": 4, "Over-the-shoulder shot": 3, "Insert shot": 2}

STOPWORDS = set("""a an the of on to from at as and then with into through behind over in by for her his
their its slow slowly gentle gently quick quickly slight slightly toward towards up down away moving
shot shots camera frame while""".split())

SIMILARITY_THRESHOLD = 0.6
SINGLE_WORD_THRESHOLD = 0.8  # spelling similarity for one word ("trackng" -> "tracking", "closeup" -> "close up")
BIG_JUMP = 4
CATEGORY_ORDER = ["size", "angle", "framing", "movement", "focus"]


# ---------- similarity search: character-trigram TF-IDF vectors ----------

def grams(text):
    t = f"  {text}  "
    return Counter(t[i:i + 3] for i in range(len(t) - 2))


class VectorIndex:
    def __init__(self, docs):
        """docs: list of (text, term)."""
        self.docs = docs
        df = Counter(g for text, _ in docs for g in grams(text))
        n = len(docs)
        self.idf = {g: math.log((1 + n) / (1 + c)) + 1 for g, c in df.items()}
        self.vecs = [self.vector(text) for text, _ in docs]

    def vector(self, text):
        v = {g: c * self.idf.get(g, math.log(1 + len(self.docs)) + 1) for g, c in grams(text).items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {g: x / norm for g, x in v.items()}

    def search(self, text, k=5):
        q = self.vector(text)
        best = {}
        for (alias, term), v in zip(self.docs, self.vecs):
            score = sum(q[g] * v.get(g, 0.0) for g in q)
            if score > best.get(term, (0, ""))[0]:
                best[term] = (score, alias)
        ranked = sorted(best.items(), key=lambda kv: -kv[1][0])
        return [(term, round(score, 3), alias) for term, (score, alias) in ranked[:k]]


# ---------- detection ----------

TOKEN = re.compile(r"[A-Za-z0-9'*]+")


def tokenize(text):
    return [(m.group(0).lower().replace("’", "'"), m.start(), m.end()) for m in TOKEN.finditer(text)]


class Detector:
    def __init__(self, names):
        self.aliases = sorted(
            ((tokenize(a), term) for term, (_, al) in TERMS.items() for a in al + [term]),
            key=lambda x: -len(x[0]))
        self.index = VectorIndex([(" ".join(t for t, _, _ in toks), term)
                                  for toks, term in self.aliases if not any(t == "*" for t, _, _ in toks)])
        # single words are compared by spelling against each alias with spaces removed
        self.compact = [(" ".join(t for t, _, _ in toks).replace(" ", ""), " ".join(t for t, _, _ in toks), term)
                        for toks, term in self.aliases if not any(t == "*" for t, _, _ in toks)]
        self.skip = STOPWORDS | {n.lower() for n in names} | {n.lower() + "'s" for n in names}

    def word_match(self, word):
        """Closest alias by spelling; aliases much longer or shorter than the word don't count."""
        best = ("", 0.0, "")
        for compact, alias, term in self.compact:
            if abs(len(compact) - len(word)) > 1:
                continue
            score = difflib.SequenceMatcher(None, word, compact).ratio()
            if score > best[1]:
                best = (term, round(score, 3), alias)
        return best

    def detect(self, text):
        toks = tokenize(text)
        words = [t for t, _, _ in toks]
        covered = [False] * len(toks)
        found = []

        # 1. exact phrases and aliases (longest first)
        for alias, term in self.aliases:
            pat = [t for t, _, _ in alias]
            for i in range(len(words) - len(pat) + 1):
                if any(covered[i:i + len(pat)]):
                    continue
                if all(p == "*" or p == w for p, w in zip(pat, words[i:i + len(pat)])):
                    for j in range(i, i + len(pat)):
                        covered[j] = True
                    found.append({"term": term, "score": 1.0, "method": "exact",
                                  "start": toks[i][1], "end": toks[i + len(pat) - 1][2],
                                  "matched": text[toks[i][1]:toks[i + len(pat) - 1][2]]})

        # 2. similarity search on the leftover words
        candidates = []
        for size in (3, 2, 1):
            for i in range(len(words) - size + 1):
                span = range(i, i + size)
                if any(covered[j] for j in span):
                    continue
                if words[i] in self.skip or words[i + size - 1] in self.skip or len(words[i]) < 3:
                    continue
                if size == 1:
                    term, score, alias = self.word_match(words[i])
                    ok = score >= SINGLE_WORD_THRESHOLD
                else:
                    term, score, alias = self.index.search(" ".join(words[i:i + size]), k=1)[0]
                    ok = score >= SIMILARITY_THRESHOLD
                if ok:
                    candidates.append((score, i, size, term, alias))
        for score, i, size, term, alias in sorted(candidates, key=lambda c: -c[0]):
            if any(covered[j] for j in range(i, i + size)):
                continue
            for j in range(i, i + size):
                covered[j] = True
            found.append({"term": term, "score": score, "method": f"similar to \"{alias}\"",
                          "start": toks[i][1], "end": toks[i + size - 1][2],
                          "matched": text[toks[i][1]:toks[i + size - 1][2]]})

        found.sort(key=lambda f: f["start"])
        seen, unique = set(), []
        for f in found:  # one entry per term, e.g. "tracking ... alongside" is a single movement
            if f["term"] not in seen:
                seen.add(f["term"])
                f["category"] = TERMS[f["term"]][0]
                unique.append(f)
        return unique


def check_shot(matches):
    warnings, notes = [], []
    by_cat = {c: [m["term"] for m in matches if m["category"] == c] for c in CATEGORY_ORDER}
    moves = [t for t in dict.fromkeys(by_cat["movement"]) if t != "Static shot"]
    if not matches:
        warnings.append("No camera term recognised; name a shot size and one movement (or 'static').")
    if len(moves) > 1:
        warnings.append(f"{len(moves)} camera movements ({', '.join(moves)}); Seedance works best with one per shot.")
    if moves and "Static shot" in by_cat["movement"]:
        warnings.append("Marked static but also has a camera movement.")
    if matches and not by_cat["size"] and not by_cat["framing"]:
        notes.append("No shot size named (e.g. wide, medium, close-up).")
    return by_cat, warnings, notes


def size_rank(by_cat):
    ranks = [SIZE_RANK[t] for t in by_cat["size"]] or [IMPLIED_RANK[t] for t in by_cat["framing"] if t in IMPLIED_RANK]
    return (min(ranks), max(ranks)) if ranks else None


ROLE_LABEL = {"subject": "camera on", "foreground": "foreground / over shoulder", "pov": "point of view",
              "in shot": "in shot", "voice": "voice only"}
TAG = re.compile(r" \(@Image \d+\)")


def shot_cast(shot, clip_chars, roster):
    """Characters in a shot and their role relative to the camera."""
    camera, action = shot["camera"], TAG.sub("", shot["action"])
    speakers = {d["character"].split()[0].title() for d in shot.get("dialogue", [])}
    cast = []
    for name in roster:
        word = rf"\b{re.escape(name)}\b"
        in_cam, in_action, speaks = re.search(word, camera), re.search(word, action), name in speakers
        if not (in_cam or in_action or speaks):
            continue
        if in_cam and re.search(rf"over {re.escape(name)}['’]s shoulder|behind {re.escape(name)}\b", camera):
            role = "foreground"
        elif in_cam and re.search(rf"{re.escape(name)}['’]s point of view", camera):
            role = "pov"
        elif in_cam:
            role = "subject"
        elif in_action or name in clip_chars:
            role = "in shot"
        else:
            role = "voice"
        cast.append({"name": name, "role": role, "speaks": speaks})
    return cast


def camera_targets(cast):
    """The characters the shot's camera terms apply to: those named in the camera line,
    otherwise everyone visible in the shot."""
    for roles in (("subject",), ("in shot",), ("foreground",)):
        names = [c["name"] for c in cast if c["role"] in roles]
        if names:
            return names
    return []


def analyse(prompt_path, roster=()):
    data = json.loads(Path(prompt_path).read_text(), strict=False)
    clips = data["clips"]
    names = set()
    for c in clips:
        for s in c.get("subjects", []):
            m = re.search(r" as (\w+)$", s)
            if m:
                names.add(m.group(1))
        for s in c["shot_details"]:
            names.update(d["character"].split()[0].title() for d in s.get("dialogue", []))
    detector = Detector(names)
    roster = list(roster) or sorted(names)

    results, prev_rank, prev_label = [], None, None
    for c in clips:
        new_scene = c.get("continuity", {}).get("mode", "new_scene") == "new_scene"
        if new_scene:
            prev_rank = None
        shots = []
        clip_chars = {m.group(1) for x in c.get("subjects", []) for m in [re.search(r" as (\w+)$", x)] if m}
        for i, s in enumerate(c["shot_details"], 1):
            matches = detector.detect(s["camera"])
            by_cat, warnings, notes = check_shot(matches)
            rank = size_rank(by_cat)
            label = ", ".join(by_cat["size"] + [t for t in by_cat["framing"] if t in IMPLIED_RANK]) or None
            if rank and new_scene and i == 1 and rank[1] < SIZE_RANK["Long shot"] and c["scene"] != "MAIN TITLES":
                notes.append(f"Scene opens on {label}; an establishing or wide shot first helps orient viewers.")
            if rank and prev_rank and min(abs(rank[0] - prev_rank[1]), abs(rank[1] - prev_rank[0])) >= BIG_JUMP:
                notes.append(f"Big jump in shot size from the previous shot ({prev_label} → {label}).")
            if rank:
                prev_rank, prev_label = rank, label
            cast = shot_cast(s, clip_chars, roster)
            shots.append({"n": i, "title": s["title"], "camera": s["camera"], "matches": matches,
                          "by_category": by_cat, "warnings": warnings, "notes": notes,
                          "cast": cast, "targets": camera_targets(cast),
                          "dialogue": [{"speaker": d["character"].title(), "line": d["line"]}
                                       for d in s.get("dialogue", [])]})
        results.append({"id": c["id"], "act": c["act"], "scene": c["scene"],
                        "mode": "new scene" if new_scene else f"continues {c['continuity'].get('previous_clip')}",
                        "shots": shots})
    return results, detector


# ---------- HTML report ----------

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#1d2430;--muted:#5b6574;--line:#e2e6eb;--warn:#b54708;--warn-bg:#fff4e5;
--note:#175cd3;--note-bg:#eef4ff;--mark:#fff2b3;--chip:#eef1f5}
@media (prefers-color-scheme:dark){:root{--bg:#12161c;--card:#1b2129;--text:#e6e9ee;--muted:#9aa4b2;--line:#2c343f;
--warn:#f7b267;--warn-bg:#3a2a16;--note:#8fb5ff;--note-bg:#1c2a44;--mark:#5a4b12;--chip:#252d38}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1200px;margin:0 auto;padding:24px 16px}h1{margin:0 0 4px}h2{margin:32px 0 12px}
.muted{color:var(--muted)}.stats{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 16px;min-width:120px}
.stat b{display:block;font-size:24px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px}
.term{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px}
.term img{width:100%;aspect-ratio:16/9;border-radius:6px;background:#dbe7f3;display:block}
.term .n{font-weight:600;margin-top:6px}.term .c{font-size:12px;color:var(--muted)}
.clip{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:16px 0;overflow:hidden}
.clip header{padding:10px 14px;border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;gap:8px 16px;align-items:baseline}
.clip header b{font-size:16px}table{width:100%;border-collapse:collapse}td,th{padding:10px 14px;vertical-align:top;
border-bottom:1px solid var(--line);text-align:left}th{font-size:12px;color:var(--muted);font-weight:600}
tr:last-child td{border-bottom:0}mark{background:var(--mark);color:inherit;border-radius:3px;padding:0 2px}
.matches{display:flex;flex-wrap:wrap;gap:8px}.m{width:132px;background:var(--chip);border-radius:8px;padding:6px;font-size:12px}
.m img{width:100%;aspect-ratio:16/9;border-radius:4px;display:block;background:#dbe7f3}.m .s{color:var(--muted)}
.issue{border-radius:6px;padding:4px 8px;margin:0 0 6px;font-size:13px}.w{background:var(--warn-bg);color:var(--warn)}
.i{background:var(--note-bg);color:var(--note)}.ok{color:var(--muted);font-size:13px}
.controls{position:sticky;top:0;background:var(--bg);padding:8px 0;z-index:1}
input[type=search]{padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--text);width:min(420px,100%)}
.cast{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}
.person{all:unset;cursor:pointer;display:grid;grid-template-columns:64px 1fr;column-gap:12px;align-items:center;
background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px}
.person:hover,.person.on{border-color:var(--note);box-shadow:0 0 0 2px var(--note-bg)}
.person .portrait{grid-row:1/span 4;width:64px;height:64px;border-radius:50%;object-fit:cover;background:#ecdcc2}
.pn{font-weight:700}.pr,.ps,.pt{font-size:12px;color:var(--muted)}.pt{color:var(--text)}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--card)}
.matrix{border-collapse:collapse;font-size:13px}.matrix th,.matrix td{border-bottom:1px solid var(--line);padding:6px;text-align:center}
.matrix thead th{vertical-align:bottom;min-width:64px}.matrix thead img{width:58px;border-radius:4px;display:block;margin:0 auto 4px;background:#dbe7f3}
.matrix thead span{font-size:11px;font-weight:600;color:var(--text)}
.matrix .rowh{text-align:left;white-space:nowrap;position:sticky;left:0;background:var(--card)}
.matrix td{background:color-mix(in srgb,var(--note) calc(var(--a)*70%),transparent);font-weight:600}.matrix td.z{background:none}
.face{width:34px;height:34px;border-radius:50%;object-fit:cover;background:#ecdcc2;flex:none;vertical-align:middle;margin-right:6px}
.blank{display:inline-flex;align-items:center;justify-content:center;font-weight:700;color:var(--muted)}
.castcell{min-width:170px}.who{display:flex;align-items:center;font-size:12px;margin-bottom:6px;line-height:1.3}
.who.r-subject .face{box-shadow:0 0 0 2px var(--note)}.who.r-voice{opacity:.7}.who.r-pov .face,.who.r-foreground .face{opacity:.75}
.applies{font-size:12px;color:var(--muted);margin-top:6px}
.convo h3{margin:18px 0 8px}.scene{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:8px 0}
.scene summary{cursor:pointer;padding:10px 14px}.lines{padding:4px 14px 12px;border-top:1px solid var(--line)}
.line{display:flex;align-items:flex-start;gap:4px;padding:6px 0;font-size:14px}.line .face{margin-top:2px}
.line.me{background:var(--note-bg);border-radius:8px;padding:6px}.say{margin-top:1px}
.line.extra .face{opacity:.6}.ref{font-size:12px;color:var(--note);margin-left:6px;text-decoration:none}
tr.talk td{border-top:0;padding-top:0}.dlg{background:var(--chip);border-radius:10px;padding:6px 12px;
display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));column-gap:16px}
.shots tbody tr:first-child td{border-bottom:0}.shots tbody{border-bottom:1px solid var(--line)}
.shots tbody:last-child{border-bottom:0}
.controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
select{padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--text)}
@media (max-width:700px){td,th{padding:8px}.m{width:104px}.shots thead{display:none}.shots td{display:block;border:0}
.shots tr{display:block;border-bottom:1px solid var(--line);padding:6px 0}}
"""


def image_src(link, out_dir):
    if re.match(r"^[a-z]+://", link):
        return link
    return os.path.relpath(ROOT / link, out_dir)


def highlight(text, matches):
    out, pos = [], 0
    for m in matches:
        out.append(html.escape(text[pos:m["start"]]))
        out.append(f'<mark title="{html.escape(m["term"])}">{html.escape(text[m["start"]:m["end"]])}</mark>')
        pos = m["end"]
    out.append(html.escape(text[pos:]))
    return "".join(out)


def card(m, images, out_dir):
    src = images.get(m["term"])
    img = f'<img src="{html.escape(image_src(src, out_dir))}" alt="{html.escape(m["term"])}" loading="lazy">' if src else ""
    how = "exact" if m["method"] == "exact" else html.escape(m["method"])
    return (f'<div class="m">{img}<div><b>{html.escape(m["term"])}</b></div>'
            f'<div class="s">{m["category"]} · {m["score"]:.2f} · {how}</div></div>')


def head_img(name, people, out_dir, cls="face"):
    src = (people.get(name) or {}).get("head")
    if not src:
        return f'<span class="{cls} blank">{html.escape(name[:1])}</span>'
    return f'<img class="{cls}" src="{html.escape(image_src(src, out_dir))}" alt="{html.escape(name)}" loading="lazy">'


def speaker_key(name, people):
    """'Saba' for 'Saba', 'Small Girl' stays 'Small Girl'."""
    first = name.split()[0]
    return first if first in people else name


def dialogue_html(lines, people, out_dir, link=None):
    out = []
    for d in lines:
        who = speaker_key(d["speaker"], people)
        named = who in people
        out.append(f'<div class="line{"" if named else " extra"}" data-speaker="{html.escape(who.lower())}">'
                   f'{head_img(who, people, out_dir) if named else head_img(who, {}, out_dir)}'
                   f'<div><b>{html.escape(d["speaker"])}</b>'
                   + (f' <a class="ref" href="#{link[0]}">{link[0]} · shot {link[1]}</a>' if link else "")
                   + f'<div class="say">{html.escape(d["line"])}</div></div></div>')
    return "".join(out)


def render(results, images, people, out_path):
    out_dir = Path(out_path).resolve().parent
    shots = [s for c in results for s in c["shots"]]
    usage = Counter(m["term"] for s in shots for m in s["matches"])
    n_warn = sum(1 for s in shots if s["warnings"])
    n_note = sum(1 for s in shots if s["notes"])
    n_similar = sum(1 for s in shots for m in s["matches"] if m["method"] != "exact")

    # character x camera term counts (terms count toward the shot's camera targets)
    roster = [n for n in people] or sorted({c["name"] for s in shots for c in s["cast"]})
    matrix = {n: Counter() for n in roster}
    appear, camera_on = Counter(), Counter()
    lines_by = Counter(speaker_key(d["speaker"], people) for s in shots for d in s["dialogue"])
    n_lines = sum(lines_by.values())
    for s in shots:
        for c in s["cast"]:
            appear[c["name"]] += 1
        for n in s["targets"]:
            camera_on[n] += 1
            matrix.setdefault(n, Counter()).update(dict.fromkeys((m["term"] for m in s["matches"]), 1))
    used_terms = [t for t in sorted(TERMS, key=lambda t: (CATEGORY_ORDER.index(TERMS[t][0]), t)) if usage[t]]
    peak = max((v for row in matrix.values() for v in row.values()), default=1)

    parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Camera Check Report</title>
<style>{CSS}</style></head><body><main>
<h1>Camera check report</h1>
<p class="muted">Camera direction and characters for every shot in prompt.json, matched to camera_angles.json and characters.json.</p>
<div class="stats"><div class="stat"><b>{len(results)}</b>clips</div><div class="stat"><b>{len(shots)}</b>shots</div>
<div class="stat"><b>{len([n for n in roster if appear[n]])}</b>characters</div>
<div class="stat"><b>{n_lines}</b>dialogue lines</div>
<div class="stat"><b>{n_warn}</b>shots with warnings</div><div class="stat"><b>{n_note}</b>shots with notes</div>
<div class="stat"><b>{n_similar}</b>similarity matches</div></div>
<h2>Characters</h2><p class="muted">Select a character to list every shot they appear in. "Camera on" counts shots
whose camera line names them, or that show them when the camera line names no one.</p><div class="cast">"""]
    for n in roster:
        if not appear[n]:
            continue
        top = ", ".join(f"{html.escape(t)} {k}" for t, k in matrix[n].most_common(3))
        role = html.escape((people.get(n) or {}).get("role", ""))
        parts.append(f'<button class="person" data-name="{html.escape(n.lower())}">{head_img(n, people, out_dir, "portrait")}'
                     f'<span class="pn">{html.escape(n)}</span><span class="pr">{role}</span>'
                     f'<span class="ps">{appear[n]} shots · camera on {camera_on[n]} · {lines_by[n]} lines</span>'
                     f'<span class="pt">{top or "—"}</span></button>')

    parts.append('</div><h2>Camera terms by character</h2><p class="muted">How many shots apply each camera term to each '
                 'character. Darker cells mean more shots.</p><div class="scroll"><table class="matrix"><thead><tr><th></th>')
    for t in used_terms:
        parts.append(f'<th title="{html.escape(t)} ({TERMS[t][0]})"><img src="{html.escape(image_src(images[t], out_dir))}" '
                     f'alt=""><span>{html.escape(t)}</span></th>' if t in images else f'<th><span>{html.escape(t)}</span></th>')
    parts.append("</tr></thead><tbody>")
    for n in roster:
        if not camera_on[n]:
            continue
        parts.append(f'<tr><th class="rowh">{head_img(n, people, out_dir)}{html.escape(n)}</th>')
        for t in used_terms:
            v = matrix[n][t]
            parts.append(f'<td style="--a:{v/peak:.2f}" class="{"z" if not v else ""}">{v or ""}</td>')
        parts.append("</tr>")
    parts.append('</tbody></table></div><h2>Camera terms used</h2><div class="grid">')

    for term in sorted(TERMS, key=lambda t: (CATEGORY_ORDER.index(TERMS[t][0]), -usage[t], t)):
        src = images.get(term)
        img = f'<img src="{html.escape(image_src(src, out_dir))}" alt="{html.escape(term)}" loading="lazy">' if src else ""
        parts.append(f'<div class="term">{img}<div class="n">{html.escape(term)}</div>'
                     f'<div class="c">{TERMS[term][0]} · used {usage[term]}×</div></div>')
    parts.append('</div><h2>Conversations</h2><p class="muted">Every line of dialogue in story order, grouped by scene. '
                 'Select a link to jump to the shot.</p><div class="convo">')
    acts = {}  # act -> scene -> [(clip id, shot n, line)], in story order
    for c in results:
        for sh in c["shots"]:
            for d in sh["dialogue"]:
                acts.setdefault(c["act"], {}).setdefault(c["scene"], []).append((c["id"], sh["n"], d))
    for act, scenes in acts.items():
        parts.append(f"<h3>{html.escape(act)}</h3>")
        for scene, lines in scenes.items():
            speakers = list(dict.fromkeys(speaker_key(d["speaker"], people) for _, _, d in lines))
            parts.append(f'<details class="scene" data-speakers="{html.escape(" ".join(x.lower() for x in speakers))}">'
                         f'<summary><b>{html.escape(scene)}</b> <span class="muted">{len(lines)} lines · '
                         f'{html.escape(", ".join(speakers))}</span></summary><div class="lines">')
            for cid, n, d in lines:
                parts.append(dialogue_html([d], people, out_dir, link=(cid, n)))
            parts.append("</div></details>")
    parts.append('</div><h2>Shots</h2><div class="controls"><label><input type="checkbox" id="only"> '
                 'Only shots with warnings or notes</label><select id="who"><option value="">All characters</option>'
                 + "".join(f'<option value="{html.escape(n.lower())}">{html.escape(n)}</option>' for n in roster if appear[n])
                 + '</select><input type="search" id="q" placeholder="Filter by clip, scene, or camera text"></div>')

    for c in results:
        parts.append(f'<section class="clip" id="{c["id"]}" data-text="{html.escape((c["id"] + " " + c["scene"] + " " + " ".join(s["camera"] for s in c["shots"])).lower())}">'
                     f'<header><b>{c["id"]}</b><span>{html.escape(c["act"])} · {html.escape(c["scene"])}</span>'
                     f'<span class="muted">{html.escape(c["mode"])}</span></header>'
                     '<table class="shots"><thead><tr><th>Shot</th><th>Camera line</th><th>Characters</th>'
                     '<th>Detected camera view</th><th>Checks</th></tr></thead>')
        for s in c["shots"]:
            issues = "".join(f'<div class="issue w">⚠ {html.escape(w)}</div>' for w in s["warnings"])
            issues += "".join(f'<div class="issue i">ℹ {html.escape(n)}</div>' for n in s["notes"])
            cast = "".join(
                f'<div class="who r-{p["role"].replace(" ", "")}">{head_img(p["name"], people, out_dir)}'
                f'<span><b>{html.escape(p["name"])}</b><br>{ROLE_LABEL[p["role"]]}{" · speaks" if p["speaks"] else ""}</span></div>'
                for p in s["cast"]) or '<span class="ok">—</span>'
            applies = (f'<div class="applies">Applies to: {html.escape(", ".join(s["targets"]))}</div>'
                       if s["targets"] and s["matches"] else "")
            names = " ".join(p["name"].lower() for p in s["cast"])
            flagged = "flag" if s["warnings"] or s["notes"] else "clean"
            parts.append(f'<tbody class="{flagged}" data-chars="{html.escape(names)}"><tr><td>{s["n"]}<br><span class="muted">{html.escape(s["title"])}</span></td>'
                         f'<td>{highlight(s["camera"], s["matches"])}</td><td class="castcell">{cast}</td>'
                         f'<td><div class="matches">{"".join(card(m, images, out_dir) for m in s["matches"]) or "<span class=ok>—</span>"}</div>{applies}</td>'
                         f'<td>{issues or "<span class=ok>✓ OK</span>"}</td></tr>')
            if s["dialogue"]:
                parts.append(f'<tr class="talk"><td></td><td colspan="4"><div class="dlg">'
                             f'{dialogue_html(s["dialogue"], people, out_dir)}</div></td></tr>')
            parts.append("</tbody>")
        parts.append("</table></section>")

    parts.append("""</main><script>
const only=document.getElementById('only'),q=document.getElementById('q'),who=document.getElementById('who');
function apply(){const v=q.value.toLowerCase(),w=who.value,o=only.checked;
document.querySelectorAll('.clip').forEach(c=>{let shown=0;
c.querySelectorAll('tbody').forEach(r=>{const ok=(!o||r.classList.contains('flag'))&&(!w||(' '+r.dataset.chars+' ').includes(' '+w+' '));
r.style.display=ok?'':'none';if(ok)shown++});
c.style.display=shown&&(!v||c.dataset.text.includes(v))?'':'none'});
document.querySelectorAll('.person').forEach(p=>p.classList.toggle('on',p.dataset.name===w));
document.querySelectorAll('.scene').forEach(d=>{d.style.display=!w||(' '+d.dataset.speakers+' ').includes(' '+w+' ')?'':'none'});
document.querySelectorAll('.line').forEach(l=>l.classList.toggle('me',!!w&&l.dataset.speaker===w))}
[only,q,who].forEach(e=>e.addEventListener('input',apply));
document.querySelectorAll('.person').forEach(p=>p.onclick=()=>{who.value=who.value===p.dataset.name?'':p.dataset.name;apply();
document.querySelector('.controls').scrollIntoView({behavior:'smooth'})});
</script></body></html>""")
    Path(out_path).write_text("".join(parts))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompts", default=ROOT / "prompt.json")
    ap.add_argument("--angles", default=ROOT / "camera_angles.json")
    ap.add_argument("--characters", default=ROOT / "characters.json")
    ap.add_argument("--out", default=ROOT / "camera_report.html")
    ap.add_argument("--query", help="run a similarity search for this camera description and exit")
    args = ap.parse_args()

    images = json.loads(Path(args.angles).read_text())
    missing = [t for t in images if t not in TERMS]
    if missing:
        print(f"Note: no aliases defined for {', '.join(missing)}; add them to TERMS in check_camera.py")

    if args.query:
        det = Detector(set())
        print(f'Similarity search for: "{args.query}"\n')
        for term, score, alias in det.index.search(args.query.lower(), k=5):
            print(f"  {score:.3f}  {term:24} (closest alias: \"{alias}\")  {images.get(term, '')}")
        print("\nDetected terms:")
        for m in det.detect(args.query):
            print(f"  {m['term']:24} {m['category']:9} {m['score']:.2f}  {m['method']}  [{m['matched']}]")
        return

    char_path = Path(args.characters)
    people = json.loads(char_path.read_text()) if char_path.exists() else {}
    results, _ = analyse(args.prompts, roster=people.keys())
    render(results, images, people, args.out)
    shots = [s for c in results for s in c["shots"]]
    print(f"Checked {len(shots)} shots in {len(results)} clips -> {args.out}")
    print(f"  warnings: {sum(len(s['warnings']) for s in shots)}  notes: {sum(len(s['notes']) for s in shots)}")
    per = Counter(c["name"] for s in shots for c in s["cast"])
    print("  characters: " + ", ".join(f"{n} {k}" for n, k in per.most_common()))
    for c in results:
        for s in c["shots"]:
            for w in s["warnings"]:
                print(f"  ⚠ {c['id']} shot {s['n']}: {w}  [{s['camera']}]")


if __name__ == "__main__":
    main()
