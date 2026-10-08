#!/usr/bin/env python3
"""Detect the emotion of every dialogue line and the mood of each conversation in data/prompt.json.

For each line it scores emotions from four signals:
  words      cue phrases and words in the line ("what if", "should have", "thank you", ...)
  marks      punctuation: "!" excitement or urgency, "?" curiosity, "…"/"..." hesitation
  speaker    the character's usual manner (Nim playful, Saba wise, Ima warm, Philip worried, ...)
  shot       the shot's mood from its title and action (camera_suggest.detect_mood)
and writes onto the line, without changing its text:
  "emotion", "intensity" (low/medium/high), "delivery" (how to say it), "emotion_evidence", "emotion_source"
Each shot gets "conversation_mood" (the dominant emotion of its lines).
Manual overrides (--set) are kept on later runs. Afterwards add_continuity.py renders the delivery into each
prompt's Dialogue line (e.g. "Nim (@Image 2), playfully: {...}") and check_camera.py rebuilds the report.

Usage:
  python3 scripts/detect_emotions.py --dry-run            # preview every line's emotion
  python3 scripts/detect_emotions.py                      # write emotions into data/prompt.json
  python3 scripts/detect_emotions.py --clip clip-37       # one clip
  python3 scripts/detect_emotions.py --set "clip-01:1:2=teasing|plays along with Nim's game"   # override, with reason
  python3 scripts/detect_emotions.py --clear-manual       # drop manual overrides
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from camera_suggest import detect_mood
from paths import DATA

PROMPTS = DATA / "prompt.json"
HERE = Path(__file__).resolve().parent

# emotion -> delivery adverb used in the prompt, plus cue phrases and word stems
EMOTIONS = {
    "playful":    dict(delivery="playfully", phrases=["perhaps there are two", "a gifted child", "at last, wisdom",
                       "withdraw all objections", "noble crumb", "statue of patience", "bold policy", "numbers of beauty",
                       "excellent judgment", "security was appropriate", "no evidence", "structural weakness",
                       "note the sacrifice", "emotionally significant", "six cakes", "service is recognized",
                       "lunch boy", "cake-hopeful", "generously", "pretending", "serious matters", "my elbows",
                       "suspects nothing", "palaces less beautiful", "echoing in sympathy", "declining crumbs"],
                       stems=[]),
    "curious":    dict(delivery="curiously", phrases=["what happened", "what does that mean", "do they see",
                       "did the boy know", "how did he", "will the story", "how many", "i wonder"], stems=[]),
    "worried":    dict(delivery="anxiously", phrases=["not enough", "what if", "where shall we", "the day is fading",
                       "no village near", "full of hungry", "kind of danger", "only have", "less than a little"],
                       stems=["worr", "afraid", "fear", "danger", "hungry"]),
    "regretful":  dict(delivery="regretfully", phrases=["should have", "i was afraid", "i wanted to keep",
                       "i told you not", "would not be enough"], stems=["sorry", "regret"]),
    "hesitant":   dict(delivery="hesitantly", phrases=["maybe later", "i can try", "do you think so", "i… have",
                       "maybe."], stems=[]),
    "reluctant":  dict(delivery="reluctantly", phrases=["again?", "had a cake yesterday", "did not help make",
                       "i will only have", "save one for later", "you keep it", "should probably keep"],
                       stems=[]),
    "determined": dict(delivery="firmly", phrases=["wait.", "if i keep it, it stays small", "i need to find",
                       "you may take it", "come with me", "i know.", "have the people sit", "all of them.",
                       "in groups!"], stems=[]),
    "warm":       dict(delivery="warmly", phrases=["little one", "small hands", "open hands", "you tell me",
                       "the right question", "a place for you", "take these to", "for you.", "peace to you",
                       "thank you, children", "filled many hands", "little fox"], stems=["love", "heart"]),
    "wise":       dict(delivery="thoughtfully", phrases=["perhaps he knew", "sometimes that is", "true story",
                       "best stories", "the sparrow", "the camel", "willing to look", "when offered", "some gifts",
                       "listen closely", "a story with a very small", "in our hands", "not in his"],
                       stems=["perhaps", "wisdom"]),
    "joyful":     dict(delivery="joyfully", phrases=["thank you!", "it works", "there is enough", "peace, miri",
                       "peace, yonah", "blessed be"], stems=["bless"]),
    "amazed":     dict(delivery="in wonder", phrases=["inside the story", "more baskets left", "more than enough",
                       "i see… more", "god made it", "but he gave it to everyone"], stems=["amaz"]),
    "excited":    dict(delivery="excitedly", phrases=["come on!", "go!", "miri!"], stems=[]),
    "reassuring": dict(delivery="gently", phrases=["you were.", "i heard.", "nothing lost", "that is usually how",
                       "and you have three today", "for you"], stems=[]),
    "calm":       dict(delivery="calmly", phrases=[], stems=[]),
    # set on review (--set) when context, not wording, carries the feeling
    "teasing":    dict(delivery="teasingly", phrases=[], stems=[]),
    "eager":      dict(delivery="eagerly", phrases=[], stems=[]),
    "proud":      dict(delivery="proudly", phrases=[], stems=[]),
    "guilty":     dict(delivery="guiltily", phrases=[], stems=[]),
    "tender":     dict(delivery="tenderly", phrases=[], stems=[]),
    "hopeful":    dict(delivery="hopefully", phrases=[], stems=[]),
    "doubtful":   dict(delivery="doubtfully", phrases=[], stems=[]),
    "disappointed": dict(delivery="disappointedly", phrases=["oh.", "the cakes?"], stems=["disappoint"]),
    "earnest":    dict(delivery="earnestly", phrases=[], stems=[]),
    "silent":     dict(delivery="silently, a held pause", phrases=[], stems=[]),
    "neutral":    dict(delivery="", phrases=[], stems=[]),
}

# a character's usual manner nudges ambiguous lines
SPEAKER_DEFAULT = {
    "Nim": "playful", "Saba": "wise", "Ima": "warm", "Philip": "worried", "Andrew": "warm", "Jesus": "warm",
    "Tav": "excited", "Yonah": "earnest", "Miri": "earnest",
}
# shot mood (camera_suggest) -> emotion it supports
SHOT_MOOD_EMOTION = {
    "tension": "hesitant", "courage": "determined", "intimacy": "warm", "joy": "joyful", "comedy": "playful",
    "sadness": "regretful", "curiosity": "curious", "wonder": "amazed", "fear": "worried", "reveal": "amazed",
    "energy": "excited",
}
STEM_RE = {e: re.compile(r"\b(?:" + "|".join(map(re.escape, v["stems"])) + r")\w*") for e, v in EMOTIONS.items() if v["stems"]}


def detect_line(line, speaker, shot_mood=None):
    """Return (emotion, intensity, evidence, scores)."""
    text = line.lower().replace("’", "'")
    scores, evidence = Counter(), {}

    def hit(emotion, weight, why):
        scores[emotion] += weight
        evidence.setdefault(emotion, []).append(why)

    for emotion, spec in EMOTIONS.items():
        for p in spec["phrases"]:
            if p in text:
                hit(emotion, 2.0, f'"{p}"')
        if emotion in STEM_RE:
            for m in STEM_RE[emotion].finditer(text):
                hit(emotion, 1.0, m.group(0))
    bangs = line.count("!")
    if bangs:
        hit("excited" if len(line.split()) <= 4 else "joyful", 1.0 + 0.5 * bangs, "!")
    if line.rstrip().endswith("?"):
        hit("curious", 1.0, "?")
    if "…" in line or "..." in line:
        hit("hesitant", 1.5, "…")
    if speaker in SPEAKER_DEFAULT:
        hit(SPEAKER_DEFAULT[speaker], 0.8, f"{speaker}'s manner")
    if shot_mood in SHOT_MOOD_EMOTION:
        hit(SHOT_MOOD_EMOTION[shot_mood], 0.7, f"shot mood: {shot_mood}")

    if speaker == "Jesus":  # always calm and unhurried
        return "calm", "low", ["Jesus speaks calmly"], scores
    if line.strip() in ("...", "…"):
        return "silent", "low", ["silent pause"], scores
    if not scores:
        return "neutral", "low", [], scores
    emotion, top = scores.most_common(1)[0]
    intensity = "high" if top >= 3.5 or bangs >= 2 else "medium" if top >= 2 else "low"
    return emotion, intensity, list(dict.fromkeys(evidence[emotion])), scores


def conversation_mood(lines):
    weights = Counter()
    for d in lines:
        weights[d["emotion"]] += {"high": 3, "medium": 2, "low": 1}[d.get("intensity", "low")]
    return weights.most_common(1)[0][0] if weights else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--clip", default="", help="comma list of clip ids")
    ap.add_argument("--set", action="append", help="clip:shot:line=emotion, e.g. clip-01:1:2=teasing")
    ap.add_argument("--clear-manual", action="store_true")
    ap.add_argument("--no-rebuild", action="store_true")
    args = ap.parse_args()

    data = json.loads(PROMPTS.read_text(), strict=False)
    clips = {c["id"]: c for c in data["clips"]}
    only = {x.strip() for x in args.clip.split(",") if x.strip()}

    for item in args.set or []:
        target, _, emotion = item.partition("=")
        cid, n, k = target.split(":")
        d = clips[cid]["shot_details"][int(n) - 1]["dialogue"][int(k) - 1]
        emotion, _, why = emotion.partition("|")
        d.update(emotion=emotion.strip(), intensity=d.get("intensity") or "medium", emotion_source="manual",
                 delivery=EMOTIONS.get(emotion.strip(), {}).get("delivery", emotion.strip()),
                 emotion_evidence=[why.strip() or "set on review"])

    counts, rows = Counter(), []
    for c in data["clips"]:
        if only and c["id"] not in only:
            continue
        for n, s in enumerate(c["shot_details"], 1):
            moods = detect_mood(s["title"], re.sub(r" \(@Image \d+\)", "", s["action"]), s.get("visual", ""))
            shot_mood = moods[0][0] if moods else None
            for k, d in enumerate(s["dialogue"], 1):
                if args.clear_manual and d.get("emotion_source") == "manual":
                    d["emotion_source"] = "auto"
                if d.get("emotion_source") == "manual":
                    counts[d["emotion"]] += 1
                    rows.append((c["id"], n, k, d["character"].title(), d["line"], d["emotion"], d["intensity"], "manual"))
                    continue
                speaker = d["character"].split()[0].title()
                emotion, intensity, evidence, _ = detect_line(d["line"], speaker, shot_mood)
                d.update(emotion=emotion, intensity=intensity, delivery=EMOTIONS[emotion]["delivery"],
                         emotion_evidence=evidence, emotion_source="auto")
                counts[emotion] += 1
                rows.append((c["id"], n, k, d["character"].title(), d["line"], emotion, intensity, ", ".join(evidence[:3])))
            mood = conversation_mood(s["dialogue"])
            if mood:
                s["conversation_mood"] = mood
            else:
                s.pop("conversation_mood", None)

    for cid, n, k, who, line, emo, inten, why in rows if args.dry_run else rows[:0]:
        print(f"  {cid}:{n}:{k}  {who:16} {emo:11} {inten:6}  {line[:60]}   [{why}]")
    print(f"{'Preview' if args.dry_run else 'Detected'}: {len(rows)} lines — "
          + ", ".join(f"{e} {k}" for e, k in counts.most_common()))
    if args.dry_run:
        return

    backup = DATA / "backups" / f"prompt.{datetime.now():%Y%m%d-%H%M%S}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PROMPTS, backup)
    PROMPTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"Saved {PROMPTS.name} (backup: {backup.relative_to(DATA.parent)})")
    if not args.no_rebuild:
        for script in ("add_continuity.py", "check_camera.py"):
            subprocess.run([sys.executable, str(HERE / script)], check=True)


if __name__ == "__main__":
    main()
