#!/usr/bin/env python3
"""Check the camera direction of every shot in prompt.json and build an HTML report.

For each shot's Camera line the script:
  1. finds known camera terms (exact phrases and aliases, e.g. "dolly-in" -> Push-in),
  2. runs a similarity search (character-trigram TF-IDF vectors, cosine similarity) on the
     leftover words, so misspellings and unusual wording still map to the closest term,
  3. checks Seedance rules: one movement per shot, no "static" plus a move, a recognisable term,
  4. compares neighbouring shots in a scene (big jumps in shot size, scenes that open close up).

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


def analyse(prompt_path):
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

    results, prev_rank, prev_label = [], None, None
    for c in clips:
        new_scene = c.get("continuity", {}).get("mode", "new_scene") == "new_scene"
        if new_scene:
            prev_rank = None
        shots = []
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
            shots.append({"n": i, "title": s["title"], "camera": s["camera"], "matches": matches,
                          "by_category": by_cat, "warnings": warnings, "notes": notes})
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
body.issues-only tr.clean{display:none}body.issues-only .clip.clean{display:none}
input[type=search]{padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--text);width:min(420px,100%)}
@media (max-width:700px){td,th{padding:8px}.m{width:104px}}
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


def render(results, images, out_path):
    out_dir = Path(out_path).resolve().parent
    shots = [s for c in results for s in c["shots"]]
    usage = Counter(m["term"] for s in shots for m in s["matches"])
    n_warn = sum(1 for s in shots if s["warnings"])
    n_note = sum(1 for s in shots if s["notes"])
    n_similar = sum(1 for s in shots for m in s["matches"] if m["method"] != "exact")

    parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Camera Check Report</title>
<style>{CSS}</style></head><body><main>
<h1>Camera check report</h1>
<p class="muted">Camera direction for every shot in prompt.json, matched to camera_angles.json.</p>
<div class="stats"><div class="stat"><b>{len(results)}</b>clips</div><div class="stat"><b>{len(shots)}</b>shots</div>
<div class="stat"><b>{n_warn}</b>shots with warnings</div><div class="stat"><b>{n_note}</b>shots with notes</div>
<div class="stat"><b>{n_similar}</b>similarity matches</div></div>
<h2>Camera terms used</h2><div class="grid">"""]
    for term in sorted(TERMS, key=lambda t: (CATEGORY_ORDER.index(TERMS[t][0]), -usage[t], t)):
        src = images.get(term)
        img = f'<img src="{html.escape(image_src(src, out_dir))}" alt="{html.escape(term)}" loading="lazy">' if src else ""
        parts.append(f'<div class="term">{img}<div class="n">{html.escape(term)}</div>'
                     f'<div class="c">{TERMS[term][0]} · used {usage[term]}×</div></div>')
    parts.append('</div><h2>Shots</h2><div class="controls"><label><input type="checkbox" id="only"> '
                 'Show only shots with warnings or notes</label> &nbsp; <input type="search" id="q" '
                 'placeholder="Filter by clip, scene, or camera text"></div>')

    for c in results:
        clean = all(not s["warnings"] and not s["notes"] for s in c["shots"])
        parts.append(f'<section class="clip{" clean" if clean else ""}" data-text="{html.escape((c["id"] + " " + c["scene"] + " " + " ".join(s["camera"] for s in c["shots"])).lower())}">'
                     f'<header><b>{c["id"]}</b><span>{html.escape(c["act"])} · {html.escape(c["scene"])}</span>'
                     f'<span class="muted">{html.escape(c["mode"])}</span></header>'
                     '<table><thead><tr><th>Shot</th><th>Camera line</th><th>Detected camera view</th><th>Checks</th></tr></thead><tbody>')
        for s in c["shots"]:
            issues = "".join(f'<div class="issue w">⚠ {html.escape(w)}</div>' for w in s["warnings"])
            issues += "".join(f'<div class="issue i">ℹ {html.escape(n)}</div>' for n in s["notes"])
            row_clean = not s["warnings"] and not s["notes"]
            parts.append(f'<tr class="{"clean" if row_clean else ""}"><td>{s["n"]}<br><span class="muted">{html.escape(s["title"])}</span></td>'
                         f'<td>{highlight(s["camera"], s["matches"])}</td>'
                         f'<td><div class="matches">{"".join(card(m, images, out_dir) for m in s["matches"]) or "<span class=ok>—</span>"}</div></td>'
                         f'<td>{issues or "<span class=ok>✓ OK</span>"}</td></tr>')
        parts.append("</tbody></table></section>")

    parts.append("""</main><script>
const only=document.getElementById('only'),q=document.getElementById('q');
only.onchange=()=>document.body.classList.toggle('issues-only',only.checked);
q.oninput=()=>{const v=q.value.toLowerCase();document.querySelectorAll('.clip').forEach(c=>{
c.style.display=!v||c.dataset.text.includes(v)?'':'none'})};
</script></body></html>""")
    Path(out_path).write_text("".join(parts))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompts", default=ROOT / "prompt.json")
    ap.add_argument("--angles", default=ROOT / "camera_angles.json")
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

    results, _ = analyse(args.prompts)
    render(results, images, args.out)
    shots = [s for c in results for s in c["shots"]]
    print(f"Checked {len(shots)} shots in {len(results)} clips -> {args.out}")
    print(f"  warnings: {sum(len(s['warnings']) for s in shots)}  notes: {sum(len(s['notes']) for s in shots)}")
    for c in results:
        for s in c["shots"]:
            for w in s["warnings"]:
                print(f"  ⚠ {c['id']} shot {s['n']}: {w}  [{s['camera']}]")


if __name__ == "__main__":
    main()
