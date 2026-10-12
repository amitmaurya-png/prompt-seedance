#!/usr/bin/env python3
"""Check the camera direction of every shot in prompt.json and build an HTML report.

For each shot's Camera line the script:
  1. finds known camera terms (exact phrases and aliases, e.g. "dolly-in" -> Push-in),
  2. runs a similarity search (character-trigram TF-IDF vectors, cosine similarity) on the
     leftover words, so misspellings and unusual wording still map to the closest term,
  3. checks Seedance rules: one movement per shot, no "static" plus a move, a recognisable term,
  4. compares neighbouring shots in a scene (big jumps in shot size, scenes that open close up),
  5. works out which characters are in the shot and which of them the camera is on (from characters.json),
  6. detects the shot's genre and mood and suggests a camera, compared with the current line (camera_suggest.py).

Usage:
  python3 scripts/check_camera.py                # writes reports/camera_report.html
  python3 scripts/check_camera.py --out other.html
  python3 scripts/check_camera.py --query "camera circles slowly around the boy"   # similarity search only
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

from camera_suggest import GENRES, compare, genre_for, suggest
from check_clips import check as check_clip_continuity
from check_continuity import check_scene, group_scenes
from paths import DATA, REPORTS, ROOT

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


def behind_names(camera, roster):
    """Names framed from behind or over the shoulder: 'over Miri's shoulder', 'behind Ima and Saba'."""
    found = set()
    for m in re.finditer(r"over ([\w']+?)['’]s shoulder", camera):
        found.add(m.group(1))
    for m in re.finditer(r"behind ((?:[A-Z]\w+)(?:\s*(?:,|and)\s*[A-Z]\w+)*)", camera):
        found.update(n for n in re.split(r"\s*(?:,|and)\s*", m.group(1)) if n)
    return found & set(roster)


def shot_cast(shot, clip_chars, roster):
    """Characters in a shot and their role relative to the camera."""
    camera, action = shot["camera"], TAG.sub("", shot["action"])
    behind = behind_names(camera, roster)
    speakers = {d["character"].split()[0].title() for d in shot.get("dialogue", [])}
    cast = []
    for name in roster:
        word = rf"\b{re.escape(name)}\b"
        in_cam, in_action, speaks = re.search(word, camera), re.search(word, action), name in speakers
        if not (in_cam or in_action or speaks):
            continue
        if name in behind:
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
    cont_issues = {}
    from collections import defaultdict as _dd
    defs, voices = _dd(set), _dd(set)
    for sc in group_scenes(clips):
        for lv, cid, msg in check_scene(sc, defs, voices):
            cont_issues.setdefault(cid, []).append((lv, msg))
    clip_issues, boundaries = check_clip_continuity(clips)
    for cid, items in clip_issues.items():
        for lv, kind, msg in items:
            if (lv, msg) not in cont_issues.get(cid, []):
                cont_issues.setdefault(cid, []).append((lv, f"[{kind}] {msg}"))
    analyse.boundaries = boundaries
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
            dlg = [{"speaker": d["character"].title(), "line": d["line"]} for d in s.get("dialogue", [])]
            genre = genre_for(c["scene"])
            sug = suggest(s["title"], TAG.sub("", s["action"]), s.get("visual", ""), dlg, cast, genre,
                          opens_scene=new_scene and i == 1)
            fit, fit_notes = compare(sug, matches, genre)
            shots.append({"previous": s.get("camera_previous"), "reason": s.get("camera_reason", ""),
                          "suggestion": sug, "fit": fit, "fit_notes": fit_notes,"n": i, "title": s["title"], "camera": s["camera"], "matches": matches,
                          "by_category": by_cat, "warnings": warnings, "notes": notes,
                          "cast": cast, "targets": camera_targets(cast),
                          "conversation_mood": s.get("conversation_mood"),
                          "dialogue": [{"speaker": d["character"].title(), "line": d["line"],
                                        "emotion": d.get("emotion"), "intensity": d.get("intensity"),
                                        "emotion_evidence": d.get("emotion_evidence", [])}
                                       for d in s.get("dialogue", [])]})
        results.append({"continuity_issues": cont_issues.get(c["id"], []),
                        "continuity_fixes": c.get("continuity_fixes", []) + c.get("clip_fixes", []),
                        "transition": c.get("continuity_transition"),
                        "continuity_added": c.get("continuity_added", []),
                        "previous_clip": c.get("continuity", {}).get("previous_clip"),
                        "id": c["id"], "act": c["act"], "scene": c["scene"],
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
.acth{margin:28px 0 4px;font-size:20px}.sceneh{margin:14px 0 6px;color:var(--muted);font-size:14px;letter-spacing:.02em}
.shot{border-top:1px solid var(--line);padding:12px 14px}.shot:first-of-type{border-top:0}
.sh{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:baseline;margin-bottom:8px}.sh .ok{margin-left:auto}
.num{font-size:12px;font-weight:700;color:var(--note);background:var(--note-bg);border-radius:6px;padding:1px 8px}
.body{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:16px}
.label{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:700;margin-bottom:6px}
.camline{margin-bottom:8px}.talk{background:var(--chip);border-radius:10px;padding:10px 12px}
.inshot{margin-top:8px}.incams{display:flex;flex-wrap:wrap;gap:8px}
.incam{display:flex;align-items:center;gap:8px;background:var(--chip);border-radius:12px;padding:6px 12px 6px 6px;font-size:13px}
.incam .blank{width:44px;height:44px;border-radius:50%;font-size:18px}
.incam .portrait{width:44px;height:44px;border-radius:50%;object-fit:cover;background:#ecdcc2;box-shadow:0 0 0 2px var(--note)}
.chip{display:inline-flex;align-items:center;font-size:12px;background:var(--card);border-radius:999px;padding:2px 10px 2px 2px}
.chip .face{width:26px;height:26px}.chip .ots{width:40px;height:22px;border-radius:4px;margin-left:6px;object-fit:cover}.chip.r-subject{box-shadow:0 0 0 2px var(--note)}.chip.r-voice{opacity:.7}
.tag{font-size:11px;color:var(--note);margin-left:4px}
.emo{font-size:11px;font-weight:700;border-radius:999px;padding:0 8px;margin-left:4px;background:var(--card);border:1px solid var(--line)}
.emo-joyful,.emo-excited,.emo-amazed{color:#3f9b5f}.emo-worried,.emo-regretful,.emo-disappointed,.emo-reluctant{color:#c4553f}
.emo-playful,.emo-teasing,.emo-eager,.emo-proud{color:#c79a2b}.emo-hopeful,.emo-tender{color:#3f9b5f}.emo-guilty,.emo-doubtful{color:#c4553f}.emo-warm,.emo-reassuring,.emo-calm,.emo-wise{color:var(--note)}.emo-hesitant,.emo-silent{color:var(--muted)}
.cont{font-size:12px;font-weight:700;margin-left:auto}.cont.ok{color:#3f9b5f}.cont.bad{color:#c79a2b}
.contbox{margin:0;padding:8px 14px;border-bottom:1px solid var(--line);font-size:13px}.contbox ul{margin:2px 0 0;padding-left:18px}
.contbox li.fixd{color:#3f9b5f}.contbox li.trans{color:var(--muted);list-style:none;margin-left:-14px}
.changed{margin:0 0 8px;padding:6px 10px;border-left:3px solid var(--note);background:var(--note-bg);border-radius:6px;font-size:13px}
.was{text-decoration:line-through;color:var(--muted)}.chg{font-size:11px;font-weight:700;color:var(--note);border:1px solid var(--note);border-radius:999px;padding:0 8px}
.chtable{border-collapse:collapse;width:100%;font-size:13px}.chtable th,.chtable td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.chtable a{color:var(--note);text-decoration:none;white-space:nowrap}.fitcell{font-weight:700}.fitcell.fit-matches{color:#3f9b5f}.fitcell.fit-close{color:#c79a2b}.fitcell.fit-differs{color:#c4553f}
.sug{margin-top:10px;border:1px dashed var(--line);border-radius:10px;padding:8px 10px}
.sug.fit-matches{border-color:#3f9b5f}.sug.fit-close{border-color:#c79a2b}.sug.fit-differs{border-color:#c4553f}
.sline{font-weight:700;margin:2px 0 6px}.thumbs{display:flex;flex-wrap:wrap;gap:6px}
.thumbs figure{margin:0;width:84px;font-size:10px;color:var(--muted)}.thumbs img{width:84px;aspect-ratio:16/9;border-radius:4px;background:#dbe7f3;display:block}
.fit{font-size:12px;font-weight:700;margin-top:6px}.fit-matches .fit{color:#3f9b5f}.fit-close .fit{color:#c79a2b}.fit-differs .fit{color:#c4553f}
.fitnote{font-size:12px;color:var(--muted)}.sug details{font-size:12px;margin-top:4px}.sug summary{cursor:pointer;color:var(--muted)}
.jump{display:flex;gap:10px;margin:4px 0 8px}.jump a{color:var(--note);text-decoration:none;font-weight:600;
background:var(--note-bg);border-radius:8px;padding:4px 12px}
@media (max-width:760px){.body{grid-template-columns:1fr}}
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


def shot_card(s, images, people, out_dir):
    """One component per shot: camera direction, who it applies to, and the dialogue spoken in it."""
    issues = "".join(f'<div class="issue w">⚠ {html.escape(w)}</div>' for w in s["warnings"])
    issues += "".join(f'<div class="issue i">ℹ {html.escape(n)}</div>' for n in s["notes"])
    roles = {p["name"]: p["role"] for p in s["cast"]}
    framing = [m["term"] for m in s["matches"] if m["category"] in ("size", "framing", "angle")]
    # only the characters the camera framing applies to
    frame_txt = " · ".join(dict.fromkeys(framing)) or "in frame"
    extras = [] if s["targets"] else re.findall(r"\bon (Small Girl|Girl|Mother|Child)\b", s["camera"])
    in_shot = "".join(
        f'<div class="incam">{head_img(n, people, out_dir, "portrait")}<div><b>{html.escape(n)}</b>'
        f'<div class="muted">{html.escape(frame_txt)}{"" if n in people else " · unnamed extra"}</div></div></div>'
        for n in s["targets"] + extras)
    lines = []
    for d in s["dialogue"]:
        who = speaker_key(d["speaker"], people)
        named = who in people
        role = roles.get(who, "voice" if named else "")
        shot_on = " · ".join(framing) if who in s["targets"] and framing else ""
        tag = " · ".join(x for x in (ROLE_LABEL.get(role, "") if role else "", shot_on) if x)
        lines.append(f'<div class="line{"" if named else " extra"}" data-speaker="{html.escape(who.lower())}">'
                     f'{head_img(who, people if named else {}, out_dir)}<div><b>{html.escape(d["speaker"])}</b>'
                     + (f' <span class="emo emo-{html.escape(d["emotion"])}" title="{html.escape(", ".join(d.get("emotion_evidence", [])))}">'
                        f'{html.escape(d["emotion"])}{" · " + d["intensity"] if d.get("intensity") not in (None, "low") else ""}</span>'
                        if d.get("emotion") else "")
                     + (f' <span class="tag">{html.escape(tag)}</span>' if tag else "")
                     + f'<div class="say">{html.escape(d["line"])}</div></div></div>')
    shown = list(s["matches"])
    fg = [p["name"] for p in s["cast"] if p["role"] == "foreground"]
    if fg and not any(m["term"] == "Over-the-shoulder shot" for m in shown):
        shown.append({"term": "Over-the-shoulder shot", "category": "framing", "score": 1.0,
                      "method": f"implied: framed from behind {' and '.join(fg)}"})
    ots_note = (f'<div class="applies">Over the shoulder of: <b>{html.escape(", ".join(fg))}</b></div>' if fg else "")
    applies = (f'<div class="inshot"><div class="label">Characters in this camera shot</div>'
               f'<div class="incams">{in_shot}</div></div>' if in_shot
               else '<div class="inshot"><div class="label">Characters in this camera shot</div>'
                    '<span class="ok">No named characters (crowd, place, or object)</span></div>')
    sug = s["suggestion"]
    thumbs = "".join(
        f'<figure><img src="{html.escape(image_src(images[t], out_dir))}" alt="{html.escape(t)}" loading="lazy">'
        f'<figcaption>{html.escape(t)}</figcaption></figure>' for t in sug["terms"] if t in images)
    mood_txt = ", ".join(f'{m} ({", ".join(ev[:3])})' for m, _, ev in sug["moods"]) or sug["mood"]
    fit_label = {"matches": "✓ Current camera fits", "close": "≈ Close to the suggestion",
                 "differs": "✗ Differs from the suggestion"}[s["fit"]]
    suggestion = (f'<div class="sug fit-{s["fit"]}"><div class="label">Suggested camera · {html.escape(GENRES[sug["genre"]])}'
                  f' · mood: {html.escape(sug["mood"])}</div><div class="sline">{html.escape(sug["line"])}</div>'
                  f'<div class="thumbs">{thumbs}</div><div class="fit">{fit_label}</div>'
                  + "".join(f'<div class="fitnote">{html.escape(n)}</div>' for n in s["fit_notes"])
                  + f'<details><summary>Why</summary><div class="muted">Detected mood: {html.escape(mood_txt)}</div>'
                  + "".join(f'<div>• {html.escape(r)}</div>' for r in sug["reasons"]) + '</details></div>')
    changed = (f'<div class="changed"><div class="label">Changed by camera-knowledge</div>'
               f'<div><span class="was">{html.escape(s["previous"])}</span> → <b>{html.escape(s["camera"])}</b></div>'
               + (f'<div class="muted">{html.escape(s["reason"])}</div>' if s["reason"] else "") + '</div>'
               if s["previous"] else "")
    flagged = "flag" if s["warnings"] or s["notes"] else "clean"
    names = " ".join(n.lower() for n in s["targets"])
    return (f'<article class="shot {flagged}" id="{s["anchor"]}" data-changed="{"yes" if s["previous"] else "no"}" data-fit="{s["fit"]}" data-chars="{html.escape(names)}">'
            f'<div class="sh"><span class="num">Shot {s["n"]}</span><b>{html.escape(s["title"])}</b>'
            f'{"<span class=chg>changed</span>" if s["previous"] else ""}'
            f'{"<span class=ok>✓ OK</span>" if flagged == "clean" else ""}</div>'
            f'<div class="body"><div class="cam"><div class="label">Camera</div>'
            f'<div class="camline">{highlight(s["camera"], s["matches"])}</div>{changed}'
            f'<div class="matches">{"".join(card(m, images, out_dir) for m in shown) or "<span class=ok>No camera term found</span>"}</div>'
            f'{applies}{ots_note}{suggestion}</div>'
            f'<div class="talk"><div class="label">Dialogue'
            f'{" · conversation mood: " + html.escape(s["conversation_mood"]) if s.get("conversation_mood") else ""}</div>'
            f'{"".join(lines) or "<div class=ok>No dialogue in this shot</div>"}</div></div>'
            f'{f"<div class=issues>{issues}</div>" if issues else ""}</article>')


def continuity_box(c):
    """Per-clip continuity: what the clip continues from, fixes applied, and remaining notes."""
    if not (c["continuity_issues"] or c["continuity_fixes"] or c["transition"]):
        return ""
    items = (f'<li class="trans">↳ {html.escape(c["transition"])}</li>' if c["transition"] else "")
    items += "".join(f'<li class="fixd">✓ {html.escape(f)}</li>' for f in c["continuity_fixes"])
    items += "".join(f'<li class="{lv}">{"⚠" if lv == "warn" else "ℹ"} {html.escape(m)}</li>' for lv, m in c["continuity_issues"])
    return f'<div class="contbox"><div class="label">Scene continuity</div><ul>{items}</ul></div>'


def changes_section(results):
    """Before/after table of camera lines changed by the camera-knowledge skill (apply_camera.py)."""
    rows = [(c, s) for c in results for s in c["shots"] if s["previous"]]
    if not rows:
        return '<h2 id="changes">Camera changes</h2><p class="muted">No camera lines have been changed yet.</p>'
    out = [f'<h2 id="changes">Camera changes</h2><p class="muted">{len(rows)} camera lines changed by the '
           'camera-knowledge skill. Undo one with <code>python3 scripts/apply_camera.py --undo clip-NN:N</code>.</p>'
           '<div class="scroll"><table class="chtable"><thead><tr><th>Shot</th><th>Before</th><th>After</th>'
           '<th>Why</th><th>Fit now</th></tr></thead><tbody>']
    for c, s in rows:
        out.append(f'<tr><td><a href="#{s["anchor"]}">{c["id"]} · {s["n"]}</a></td>'
                   f'<td class="was">{html.escape(s["previous"])}</td><td><b>{html.escape(s["camera"])}</b></td>'
                   f'<td class="muted">{html.escape(s["reason"])}</td><td class="fitcell fit-{s["fit"]}">{s["fit"]}</td></tr>')
    out.append("</tbody></table></div>")
    return "".join(out)


def render(results, images, people, out_path):
    out_dir = Path(out_path).resolve().parent
    shots = [s for c in results for s in c["shots"]]
    usage = Counter(m["term"] for s in shots for m in s["matches"])
    n_warn = sum(1 for s in shots if s["warnings"])
    n_note = sum(1 for s in shots if s["notes"])
    n_similar = sum(1 for s in shots for m in s["matches"] if m["method"] != "exact")
    fits = Counter(s["fit"] for s in shots)
    n_changed = sum(1 for s in shots if s["previous"])

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
<div class="stat"><b>{n_similar}</b>similarity matches</div>
<div class="stat"><b>{fits["matches"]}/{fits["close"]}/{fits["differs"]}</b>fit / close / differ from suggestion</div>
<div class="stat"><b>{n_changed}</b>camera lines changed</div>
<div class="stat"><b>{sum(1 for c in results if not c["continuity_issues"])}/{len(results)}</b>clips continuous</div>
<div class="stat"><b>{sum(len(c["continuity_fixes"]) for c in results)}</b>continuity fixes</div></div>
<nav class="jump"><a href="#changes">Camera changes</a><a href="#shots">Shots</a></nav>
<h2>Characters</h2><p class="muted">Select a character to list every shot the camera is on them. "Camera on" counts shots
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
    for c in results:
        for sh in c["shots"]:
            sh["anchor"] = f'{c["id"]}-shot-{sh["n"]}'
    parts.append('</div>' + changes_section(results))
    parts.append('<h2 id="shots">Shots</h2><div class="controls"><label><input type="checkbox" id="only"> '
                 'Only shots with warnings or notes</label><select id="who"><option value="">All characters</option>'
                 + "".join(f'<option value="{html.escape(n.lower())}">{html.escape(n)}</option>' for n in roster if appear[n])
                 + '</select><select id="fit"><option value="">All suggestion fits</option><option value="differs">Differs from suggestion</option>'
                 '<option value="close">Close to suggestion</option><option value="matches">Fits suggestion</option>'
                 '<option value="changed">Changed by camera-knowledge</option><option value="cont">Clips with continuity notes</option></select>'
                 '<input type="search" id="q" placeholder="Filter by clip, scene, or camera text"></div>')

    act = scene = None
    for c in results:
        if c["act"] != act:
            act = c["act"]
            parts.append(f'<h3 class="acth">{html.escape(act)}</h3>')
        if c["scene"] != scene:
            scene = c["scene"]
            parts.append(f'<h4 class="sceneh">{html.escape(scene)}</h4>')
        parts.append(f'<section class="clip" id="{c["id"]}" data-cont="{"yes" if c["continuity_issues"] else "no"}" data-text="{html.escape((c["id"] + " " + c["scene"] + " " + " ".join(s["camera"] + " " + " ".join(d["line"] for d in s["dialogue"]) for s in c["shots"])).lower())}">'
                     f'<header><b>{c["id"]}</b><span class="muted">{html.escape(c["mode"])}</span>'
                     + ('<span class="cont ok">✓ continuous</span>' if not c["continuity_issues"]
                        else f'<span class="cont bad">{len(c["continuity_issues"])} continuity note(s)</span>')
                     + '</header>' + continuity_box(c))
        for s in c["shots"]:
            parts.append(shot_card(s, images, people, out_dir))
        parts.append("</section>")

    parts.append("""</main><script>
const only=document.getElementById('only'),q=document.getElementById('q'),who=document.getElementById('who'),fit=document.getElementById('fit');
function apply(){const v=q.value.toLowerCase(),w=who.value,o=only.checked,f=fit.value;
document.querySelectorAll('.clip').forEach(c=>{let shown=0;
c.querySelectorAll('.shot').forEach(r=>{const ok=(!o||r.classList.contains('flag'))&&(!f||(f==='cont'?c.dataset.cont==='yes':f==='changed'?r.dataset.changed==='yes':r.dataset.fit===f))&&(!w||(' '+r.dataset.chars+' ').includes(' '+w+' '));
r.style.display=ok?'':'none';if(ok)shown++});
c.style.display=shown&&(!v||c.dataset.text.includes(v))?'':'none'});
document.querySelectorAll('.sceneh,.acth').forEach(h=>{let n=h.nextElementSibling,any=false;
while(n&&!n.matches('.sceneh,.acth')){if(n.matches('.clip')&&n.style.display!=='none')any=true;n=n.nextElementSibling}
if(h.matches('.sceneh'))h.style.display=any?'':'none'});
document.querySelectorAll('.person').forEach(p=>p.classList.toggle('on',p.dataset.name===w));
document.querySelectorAll('.line').forEach(l=>l.classList.toggle('me',!!w&&l.dataset.speaker===w));
}
[only,q,who,fit].forEach(e=>e.addEventListener('input',apply));
document.querySelectorAll('.person').forEach(p=>p.onclick=()=>{who.value=who.value===p.dataset.name?'':p.dataset.name;apply();
document.querySelector('.controls').scrollIntoView({behavior:'smooth'})});
</script></body></html>""")
    Path(out_path).write_text("".join(parts))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompts", default=DATA / "prompt.json")
    ap.add_argument("--angles", default=DATA / "camera_angles.json")
    ap.add_argument("--characters", default=DATA / "characters.json")
    ap.add_argument("--out", default=REPORTS / "camera_report.html")
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
