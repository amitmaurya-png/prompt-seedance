#!/usr/bin/env python3
"""Detect a shot's genre and mood, and suggest the camera that suits it.

Rule-based, explainable suggestions (not a final answer): the genre comes from the scene,
the mood from keywords in the shot's title, action, visual note, and dialogue. The mood's
camera defaults are then adjusted for the genre, who is speaking, and scene continuity.
The tables mirror .github/skills/camera-knowledge/references/camera_moods.md.

Usage:
  python3 scripts/camera_suggest.py --describe "Yonah hesitates, then stands and offers his lunch"
  python3 scripts/camera_suggest.py --describe "thousands sit on the hillside" --genre epic
  python3 scripts/camera_suggest.py --all          # every shot in data/prompt.json
"""

import argparse
import json
import re
from collections import Counter

from paths import DATA

# ---------- genre ----------

GENRES = {
    "storybook": "Family / children's storybook",
    "epic": "Epic / biblical",
    "title": "Title card",
}

# Scene headings (or parts of them) -> genre. Anything not listed is storybook.
SCENE_GENRE = [
    ("MAIN TITLES", "title"),
    ("GALILEAN", "epic"), ("HILLSIDE", "epic"), ("NEAR JESUS", "epic"), ("EDGE OF CROWD", "epic"),
]

GENRE_AVOID = {
    "storybook": {"Dolly zoom", "Extreme close-up", "Zoom"},
    "epic": {"Dolly zoom", "Zoom"},
    "title": set(),
}


def genre_for(scene):
    for key, genre in SCENE_GENRE:
        if key in scene.upper():
            return genre
    return "storybook"


# ---------- mood ----------

# mood -> keyword stems (a word that starts with the stem counts), phrases, and camera defaults
MOODS = {
    "wonder": dict(
        stems="wonder amaz endless transform glow miracle bless thousand gasp behold reveal awe shimmer vast "
              "sunlit reverent",
        phrases=["inside the story"],
        size="Wide shot", angle="Low-angle shot", move="Crane shot", focus="Deep focus",
        why="Wide and low with a rising move shows scale and makes the moment feel larger than the characters."),
    "fear": dict(
        stems="afraid fear frighten scared nervous worried trembl panic danger tears",
        phrases=[],
        size="Close-up", angle="High-angle shot", move="Push-in", focus="Shallow focus",
        why="A close, slightly high view makes the character look small and isolates their worry."),
    "tension": dict(
        stems="hesitat freez paus silen guard shield instinctive suspicious uncertain doubt imagin",
        phrases=["says nothing", "does not force", "not forcing", "about to return"],
        size="Medium close-up", angle="Eye-level shot", move="Static shot", focus="Shallow focus",
        why="A held, still frame at eye level lets the pause play out without distraction."),
    "courage": dict(
        stems="stands rises brave resolve offer determin decid",
        phrases=["holds out", "step forward", "gives it", "take it"],
        size="Medium close-up", angle="Low-angle shot", move="Push-in", focus="Shallow focus",
        why="A low angle and slow push-in make a small character's decision feel big."),
    "intimacy": dict(
        stems="kneel gentl warm comfort softly quiet together heart tender",
        phrases=["sits beside", "rests a hand", "studies her", "pats the ground"],
        size="Medium close-up", angle="Eye-level shot", move="Static shot", focus="Shallow focus",
        why="Eye-level framing and a still camera keep the moment close and personal."),
    "joy": dict(
        stems="beam laugh smil cheer delight bliss wave wags celebrat happy grin brighten",
        phrases=["lights up", "light up", "thank you", "it works"],
        size="Medium shot", angle="Eye-level shot", move="Tracking shot", focus="Deep focus",
        why="A medium frame with gentle movement shares the energy and keeps everyone visible."),
    "comedy": dict(
        stems="sly grave importantly innocent whisker proposal bargain solemnly",
        phrases=["pats his own belly", "chin high", "puffs up", "nods along", "eyes the bundle", "eyes tav",
                 "climb inside", "sniffs the basket"],
        size="Medium shot", angle="Eye-level shot", move="Static shot", focus="Deep focus",
        why="A steady medium frame lets the timing and body language carry the joke."),
    "sadness": dict(
        stems="disappoint sad regret guilt sigh exhal sorry",
        phrases=["looks down", "should have", "not satisfied", "face falls"],
        size="Close-up", angle="Eye-level shot", move="Static shot", focus="Shallow focus",
        why="A still close-up gives the feeling room without pushing it."),
    "curiosity": dict(
        stems="peek peeks asks question sniff noses inspect scan spot curious explor counting",
        phrases=["looking up at the shelves", "looks around"],
        size="Medium close-up", angle="Eye-level shot", move="Push-in", focus="Shallow focus",
        why="A slow push-in follows the character's attention toward what they discover."),
    "reveal": dict(
        stems="realis realiz remember understand notices unfurl unties unwrap",
        phrases=["more baskets", "begins the story"],
        size="Close-up", angle="Eye-level shot", move="Pull-back", focus="Deep focus",
        why="Starting close and pulling back reveals the wider meaning of the moment."),
    "energy": dict(
        stems="runs running hurr rush scatter trott chase dart briskly bound leap",
        phrases=[],
        size="Medium long shot", angle="Eye-level shot", move="Tracking shot", focus="Deep focus",
        why="A tracking medium-long shot keeps up with the movement and shows the whole body."),
}
DEFAULT_MOOD = dict(size="Medium shot", angle="Eye-level shot", move="Static shot", focus="",
                    why="A neutral medium shot at eye level.")
CONVERSATION = dict(size="Medium shot", angle="Eye-level shot", move="Static shot", focus="Shallow focus",
                    why="Steady coverage of a conversation, framed to keep speakers together.")
COMIC_CHARACTERS = {"Nim"}  # a line from the comic-relief character nudges the mood toward comedy

SIZE_ORDER = ["Extreme close-up", "Big close-up", "Close-up", "Medium close-up", "Medium shot",
              "Medium long shot", "Long shot", "Wide shot", "Establishing shot"]
OPPOSITE_ANGLES = {("Low-angle shot", "High-angle shot"), ("High-angle shot", "Low-angle shot")}
SMALL_CHARACTERS = {"Nim"}
CHILDREN = {"Miri", "Tav", "Yonah", "Nim"}  # never framed to look small and powerless
CROWD_WORDS = re.compile(r"\b(crowd|thousand|hillside|cluster|families|everyone|landscape|lake)\w*")
STEMS = {m: re.compile(r"\b(?:" + "|".join(map(re.escape, spec["stems"].split())) + r")\w*")
         for m, spec in MOODS.items()}


def detect_mood(title="", action="", visual="", lines=(), speakers=()):
    """Return [(mood, score, [evidence words])] best first."""
    sources = [(title.lower(), 1.5), (action.lower(), 2.0), (visual.lower(), 0.5),
               (" ".join(lines).lower(), 1.0)]
    scores, evidence = Counter(), {}
    for mood, spec in MOODS.items():
        hits = []
        for text, weight in sources:
            for phrase in spec["phrases"]:
                if phrase in text:
                    scores[mood] += weight * 1.5
                    hits.append(phrase)
            for m in STEMS[mood].finditer(text):
                scores[mood] += weight
                hits.append(m.group(0))
        if hits:
            evidence[mood] = list(dict.fromkeys(hits))
    exclaims = sum(l.count("!") for l in lines)
    if exclaims:
        scores["joy"] += 0.5 * exclaims
        evidence.setdefault("joy", []).append("!")
    comic = [s for s in speakers if s in COMIC_CHARACTERS]
    if comic:
        scores["comedy"] += 1.0
        evidence.setdefault("comedy", []).append(f"{comic[0]} speaks")
    return [(m, round(sc, 1), evidence.get(m, [])) for m, sc in scores.most_common() if sc > 0]


# ---------- suggestion ----------

def suggest(title="", action="", visual="", dialogue=(), cast=(), genre="storybook",
            opens_scene=False, subject=None):
    """Suggest a camera for one shot.

    dialogue: [{"speaker": "Miri", "line": "..."}]; cast: [{"name": "Miri", "role": "in shot"}]
    Returns dict with genre, mood, terms (size/angle/move/focus/framing), line, and reasons.
    """
    lines = [d["line"] for d in dialogue]
    speakers = list(dict.fromkeys(d["speaker"].split()[0].title() for d in dialogue))
    moods = detect_mood(title, action, visual, lines, speakers)
    visible = [c["name"] for c in cast if c.get("role") in ("subject", "in shot")]
    voices = {c["name"] for c in cast if c.get("role") == "voice"}
    speakers = [x for x in speakers if x not in voices]  # off-screen narration does not drive framing
    lines = [d["line"] for d in dialogue if d["speaker"].split()[0].title() not in voices]
    on_screen_speakers = [x for x in speakers if x in visible] if visible else speakers

    if voices and not speakers:
        moods = detect_mood(title, action, visual, (), ())
    if moods:
        mood = moods[0][0]
        spec = dict(MOODS[mood])
    elif lines:
        mood, spec = "conversation", dict(CONVERSATION)
    else:
        mood, spec = "neutral", dict(DEFAULT_MOOD)
    reasons = [spec["why"]]
    size, angle, move, focus, framing = spec["size"], spec["angle"], spec["move"], spec["focus"], None

    # coverage: who is speaking on screen (wide moods keep their scale)
    if SIZE_ORDER.index(size) >= SIZE_ORDER.index("Wide shot"):
        pass
    elif len(on_screen_speakers) >= 3 or (len(visible) >= 3 and mood in ("joy", "conversation", "comedy")):
        framing, size = "Three-shot", "Medium shot"
        reasons.append("Three or more characters share the moment, so keep them in one frame.")
    elif len(on_screen_speakers) == 2:
        framing = "Over-the-shoulder shot" if mood in ("tension", "sadness", "courage") else "Two-shot"
        reasons.append("Two characters talk: " + ("over-the-shoulder coverage keeps the exchange personal."
                                                  if framing.startswith("Over") else
                                                  "a two-shot keeps both reactions visible."))
        if SIZE_ORDER.index(size) < SIZE_ORDER.index("Medium close-up"):
            size = "Medium close-up"

    crowd = bool(CROWD_WORDS.search(action.lower()))
    talking = bool(on_screen_speakers)

    # genre adjustments
    if size in GENRE_AVOID.get(genre, set()):
        size = "Close-up"
    if genre == "epic" and not talking and (mood in ("wonder", "joy") or crowd):
        if SIZE_ORDER.index(size) < SIZE_ORDER.index("Wide shot"):
            size = "Wide shot"
            reasons.append("Epic: open wide to show the crowd and landscape.")
        if mood == "wonder" and "thousand" in (action + visual).lower():
            angle = "Aerial shot"
    if talking and SIZE_ORDER.index(size) >= SIZE_ORDER.index("Wide shot"):
        size = "Medium long shot" if crowd else "Medium shot"
        reasons.append("Characters are talking: stay close enough to read their faces"
                       + (", with the crowd behind them." if crowd else "."))

    # children are never framed to look small and powerless
    focus_child = [n for n in (on_screen_speakers or visible) if n in CHILDREN]
    if angle == "High-angle shot" and (genre == "storybook" or focus_child):
        angle = "Eye-level shot"
        reasons.append("Children lead this story: stay at eye level rather than looking down on them.")

    # small characters: meet them at their height
    who = subject or (on_screen_speakers[0] if on_screen_speakers else (visible[0] if visible else None))
    if who in SMALL_CHARACTERS and angle == "Eye-level shot":
        angle = "Low-angle shot"
        reasons.append(f"{who} is small; a low camera at his height keeps him the hero of the frame.")

    # continuity: a new scene opens wide
    if opens_scene and genre != "title":
        if SIZE_ORDER.index(size) < SIZE_ORDER.index("Wide shot"):
            size = "Wide shot"
            framing = None
            reasons.append("First shot of a new scene: open wide so viewers know where they are.")

    # Jesus is only shown from behind
    if any(c["name"] == "Jesus" for c in cast):
        framing = "Over-the-shoulder shot"
        reasons.append("Jesus is shown only from behind or in silhouette: frame from behind him.")

    if genre == "title":
        size, angle, move, focus, framing = "Close-up", "Eye-level shot", "Push-in", "", None
        mood, reasons = "title", ["Title card: a slow push-in on the painted card."]

    parts = [f"{size.replace(' shot', '')} {framing.lower()}" if framing else size]
    if angle != "Eye-level shot":
        parts.append(angle.replace(" shot", "").lower())
    parts.append({"Static shot": "static", "Push-in": "slow push-in", "Pull-back": "slow pull back",
                  "Tracking shot": "gentle tracking", "Crane shot": "slow crane up", "Arc shot": "slow arc",
                  "Pan": "slow pan"}.get(move, move.lower()))
    target = f" on {who}" if who and framing is None and size not in ("Wide shot", "Establishing shot") else ""
    line = ", ".join(parts) + target
    return {"genre": genre, "mood": mood, "moods": moods[:3], "size": size, "angle": angle, "move": move,
            "focus": focus, "framing": framing, "subject": who,
            "terms": [t for t in (size, framing, angle, move, focus) if t], "line": line[0].upper() + line[1:],
            "reasons": reasons}


def compare(suggestion, matches, genre):
    """Compare a suggestion with the camera terms found in the current line."""
    current = {m["category"]: [] for m in matches}
    for m in matches:
        current[m["category"]].append(m["term"])
    major, minor = [], []
    cur_sizes = [t for t in current.get("size", []) if t in SIZE_ORDER]
    if cur_sizes:
        gap = min(abs(SIZE_ORDER.index(t) - SIZE_ORDER.index(suggestion["size"])) for t in cur_sizes)
        if gap >= 3:
            major.append(f"Shot size {', '.join(cur_sizes)} is far from the suggested {suggestion['size']}.")
        elif gap == 2:
            minor.append(f"Shot size {', '.join(cur_sizes)} is a little {'wider' if SIZE_ORDER.index(cur_sizes[0]) > SIZE_ORDER.index(suggestion['size']) else 'closer'} than suggested.")
    for a in current.get("angle", []):
        if (a, suggestion["angle"]) in OPPOSITE_ANGLES:
            major.append(f"{a} works against the {suggestion['mood']} mood (suggested {suggestion['angle']}).")
    for t in current.get("movement", []) + current.get("size", []):
        if t in GENRE_AVOID.get(genre, set()):
            major.append(f"{t} is unusual for {GENRES[genre].lower()}.")
    moves = [t for t in current.get("movement", []) if t != "Static shot"]
    if suggestion["move"] == "Static shot" and moves:
        minor.append(f"The {suggestion['mood']} mood suits a still camera; current line moves ({', '.join(moves)}).")
    fit = "differs" if major else ("close" if minor else "matches")
    return fit, major + minor


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--describe", help="free-text description of a shot")
    ap.add_argument("--genre", choices=list(GENRES), default="storybook")
    ap.add_argument("--new-scene", action="store_true", help="the shot opens a new scene")
    ap.add_argument("--all", action="store_true", help="suggest for every shot in data/prompt.json")
    args = ap.parse_args()

    if args.describe:
        s = suggest(action=args.describe, genre=args.genre, opens_scene=args.new_scene)
        print(f"Genre: {GENRES[s['genre']]}")
        print("Mood:  " + (", ".join(f"{m} ({sc}: {', '.join(ev)})" for m, sc, ev in s["moods"]) or s["mood"]))
        print(f"Suggested camera: {s['line']}")
        print("Terms: " + ", ".join(s["terms"]))
        for r in s["reasons"]:
            print(f"  - {r}")
        return

    if args.all:
        data = json.loads((DATA / "prompt.json").read_text(), strict=False)
        prev_scene = None
        for c in data["clips"]:
            new_scene = c.get("continuity", {}).get("mode") == "new_scene"
            for i, sh in enumerate(c["shot_details"], 1):
                dlg = [{"speaker": d["character"].title(), "line": d["line"]} for d in sh["dialogue"]]
                s = suggest(sh["title"], re.sub(r" \(@Image \d+\)", "", sh["action"]), sh["visual"], dlg,
                            genre=genre_for(c["scene"]), opens_scene=new_scene and i == 1)
                print(f"{c['id']} shot {i}: [{s['genre']}/{s['mood']}]  now: {sh['camera']}  ->  {s['line']}")
        return
    ap.print_help()


if __name__ == "__main__":
    main()
