#!/usr/bin/env python3
"""Parse the screenplay PDF into data/breakdown.json, capturing every action and dialogue line verbatim.

No AI model is used. The script reads each text fragment's position on the page and classifies lines by
standard screenplay indentation:
  x ~108   scene headings (INT./EXT.), act headings, and action
  x ~180   dialogue
  x ~210   parentheticals, e.g. (SOFTLY)
  x ~250   character cues, e.g. NIM, ANDREW (SOFTLY), SABA (CONT'D)
Lines are joined into paragraphs (a larger vertical gap starts a new paragraph).

Each scene becomes a list of shots. A shot is one action paragraph (or several in a row) followed by the
dialogue spoken after it, until the next action paragraph. Every shot keeps:
  "action"   all of its action paragraphs joined, word for word
  "actions"  the separate action paragraphs
  "dialogue" [{"character", "line", "parenthetical"?}], word for word, in order
Text before ACT ONE is labelled TEASER; MAIN TITLES becomes its own scene.

Usage:
  python3 scripts/parse_screenplay.py                 # pdf_document/TSL.pdf
  python3 scripts/parse_screenplay.py path/to/script.pdf
  python3 scripts/parse_screenplay.py --dry-run       # print a summary, don't write
"""

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from paths import DATA, ROOT

OUT = DATA / "breakdown.json"
DEFAULT_PDF = ROOT / "pdf_document" / "TSL.pdf"
ACT_RE = re.compile(r"^ACT (ONE|TWO|THREE|FOUR|FIVE)$")
SCENE_RE = re.compile(r"^(INT\.|EXT\.|INT/EXT\.)")
SKIP_RE = re.compile(r"^(\d+\.|FADE (IN|OUT)\.?|CUT TO:|THE END|END OF EPISODE)$")


def page_lines(page):
    """[(x, y, text)] for each printed line on a page, top to bottom."""
    frags = []

    def visit(text, cm, tm, font, size):
        if text.strip():
            frags.append((tm[4] + cm[4], tm[5] + cm[5], text))

    page.extract_text(visitor_text=visit)
    rows = {}
    for x, y, text in frags:
        key = round(y)
        rows.setdefault(key, []).append((x, text))
    lines = []
    for y in sorted(rows, reverse=True):
        parts = sorted(rows[y])
        text = re.sub(r"\s+", " ", "".join(t for _, t in parts)).strip()
        lines.append((parts[0][0], y, text))
    return lines


def kind(x, text):
    if x < 130:
        if ACT_RE.match(text):
            return "act"
        if SCENE_RE.match(text) or text == "MAIN TITLES":
            return "scene"
        return "action"
    if x >= 400 or SKIP_RE.match(text):
        return "skip"
    if x >= 235:
        return "cue"
    if text.startswith("(") and x >= 195:
        return "paren"
    return "dialogue"


def blocks(pdf_path):
    """Yield (kind, text) blocks in reading order, joining wrapped lines into paragraphs."""
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    current, last_y, last_kind = None, None, None
    names = set()  # character names seen in cues so far
    for page_no, page in enumerate(reader.pages):
        for x, y, text in page_lines(page):
            k = kind(x, text)
            if k == "cue":
                names.add(re.split(r"\s*\(", text)[0].strip().title())
            # an action mis-indented as dialogue: "Miri laughs and eats her piece." after a finished sentence
            if (k == "dialogue" and current and current[0] == "dialogue" and re.search(r"[.!?]$", current[1])
                    and re.match(r"^([A-Z][a-z]+) [a-z]+s\b", text) and text.split()[0] in names):
                k = "action"
            if k == "skip" or (page_no == 0 and k != "scene" and current is None and k == "action"):
                continue  # title page and page numbers
            new_para = (current is None or k != last_kind or k in ("act", "scene", "cue")
                        or (last_y is not None and last_y - y > 16))
            if k == "dialogue" and last_kind in ("dialogue", "paren") and current and current[0] in ("dialogue", "paren"):
                new_para = k != current[0] or (last_y is not None and last_y - y > 16 and current[0] != "dialogue")
            if new_para:
                if current:
                    yield current
                current = [k, text]
            else:
                sep = "" if current[1].endswith("-") else " "
                current[1] = f"{current[1]}{sep}{text}"
            last_y, last_kind = y, k
        last_y = None  # a new page never continues a paragraph's spacing
    if current:
        yield current


def parse(pdf_path):
    acts = [{"act": "TEASER", "scenes": []}]
    scene = shot = None
    speaker, paren, extension = None, None, None

    def new_shot():
        nonlocal shot
        shot = {"order": len(scene["shots"]) + 1, "action": "", "actions": [], "dialogue": []}
        scene["shots"].append(shot)

    for k, text in blocks(pdf_path):
        if k == "act":
            acts.append({"act": text, "scenes": []})
            scene = shot = None
        elif k == "scene":
            scene = {"scene": text, "shots": []}
            acts[-1]["scenes"].append(scene)
            shot = None
            if text == "MAIN TITLES":
                new_shot()
        elif scene is None:
            continue
        elif k == "action":
            if shot is None or shot["dialogue"]:
                new_shot()
            shot["actions"].append(text)
            shot["action"] = " ".join(shot["actions"])
        elif k == "cue":
            m = re.match(r"^(.*?)(?:\s*\((CONT'D|CONT’D|O\.S\.|V\.O\.|O\.C\.)\))?\s*(\(.*\))?$", text)
            speaker = m.group(1).strip()
            extension = m.group(2)
            paren = m.group(3)
            if shot is None:
                new_shot()
        elif k == "paren":
            paren = text
        elif k == "dialogue" and speaker:
            if shot is None:
                new_shot()
            line = {"character": speaker, "line": text}
            if extension in ("V.O.", "O.S.", "O.C."):
                line["voice_over" if extension == "V.O." else "off_screen"] = True
            if paren:
                line["parenthetical"] = paren.strip("()").strip()
                paren = None
            shot["dialogue"].append(line)
    for act in acts:
        act["scenes"] = [s for s in act["scenes"] if s["shots"]]
    return {"acts": [a for a in acts if a["scenes"]]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", nargs="?", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    pdf = args.pdf or (DEFAULT_PDF if DEFAULT_PDF.is_file() else Path(old.get("source", "")))
    if not pdf.is_file():
        raise SystemExit(f"Screenplay PDF not found: {pdf}")
    source = pdf.resolve()
    source = source.relative_to(ROOT) if source.is_relative_to(ROOT) else source
    data = {"source": str(source), "method": "parse_screenplay.py (verbatim, no AI)", **parse(pdf)}

    shots = [sh for a in data["acts"] for s in a["scenes"] for sh in s["shots"]]
    n_lines = sum(len(sh["dialogue"]) for sh in shots)
    n_actions = sum(len(sh["actions"]) for sh in shots)
    print(f"{len(data['acts'])} acts, {sum(len(a['scenes']) for a in data['acts'])} scenes, {len(shots)} shots, "
          f"{n_actions} action paragraphs, {n_lines} dialogue lines")
    for a in data["acts"]:
        print(f"  {a['act']}: " + ", ".join(f"{s['scene']} ({len(s['shots'])})" for s in a["scenes"]))
    if args.dry_run:
        return
    backup = DATA / "backups" / f"breakdown.{datetime.now():%Y%m%d-%H%M%S}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        shutil.copy2(OUT, backup)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"Saved {OUT.relative_to(DATA.parent)} (backup: {backup.relative_to(DATA.parent)})")


if __name__ == "__main__":
    main()
