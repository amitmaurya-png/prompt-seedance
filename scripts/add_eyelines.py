#!/usr/bin/env python3
"""Add eyelines to every shot in data/prompt.json: who each line is said to, and where characters look.

Rules
  two people   when two characters talk with each other, they turn toward each other and hold eye contact
  group        when a character addresses a group (two or more listeners, or a crowd/children/disciples),
               they look around at the listeners as they speak, meeting their eyes in turn, and the listeners
               look back at them
  several      when three or more characters trade lines, each speaker looks at the person they are answering
               and the others turn to whoever is speaking
Special cases: voice-over lines get no eyeline; Jesus is only framed from behind (he turns toward the person,
face unseen); Nim is small, so humans look down at him and he looks up at them.

Writes, without changing actions or dialogue text:
  each dialogue line   "addressee"  (a character's name, or a group such as "the children")
  each shot            "eyeline"    {"type", "speaker"(s), "listeners", "direction"}
add_continuity.py then renders "Eyeline: …" in the shot and "Miri (@Image 1), earnestly, to Nim: {…}" in Dialogue.

Usage:
  python3 scripts/add_eyelines.py --dry-run         # preview
  python3 scripts/add_eyelines.py                   # write, then rebuild prompts and the camera report
  python3 scripts/add_eyelines.py --clip clip-02
  python3 scripts/add_eyelines.py --set "clip-47:1:1=Yonah|'young one' is Yonah"   # override on review
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from check_continuity import ORDER, TAG, names_in
from paths import DATA

PROMPTS = DATA / "prompt.json"
HERE = Path(__file__).resolve().parent
GROUPS = [("children", "the children"), ("crowd", "the crowd"), ("disciples", "the disciples"),
          ("families", "the families"), ("people", "the people"), ("everyone", "everyone")]
SMALL = {"Nim"}


def speaker_of(d):
    return d["character"].split()[0].title()


GROUP_WORDS = "|".join(w for w, _ in GROUPS)
TOWARD_RE = re.compile(r"\b(?:toward|towards|to|at|faces|facing|calls to|addresses)\s+(?:the\s+)?("
                       + "|".join(ORDER) + "|" + GROUP_WORDS + r")\b", re.I)


def group_in(text):
    """A group the speaker is addressing: 'calls to the crowd', 'surrounded by several village children'."""
    low = text.lower()
    m = re.search(rf"\b(?:to|toward|towards|at|addresses|surrounded by)\s+(?:the\s+|several\s+|many\s+)?"
                  rf"(?:\w+\s+){{0,2}}({GROUP_WORDS})\b", low)
    if not m:
        return None
    return next(label for word, label in GROUPS if word == m.group(1))


def target_in(action, me):
    """A character the speaker moves or speaks toward in the action, e.g. 'steps toward Andrew'."""
    for m in TOWARD_RE.finditer(action):
        who = m.group(1).title()
        if who != me and who in ORDER:
            return who
    return None


def look(a, b):
    """'Miri looks at Nim' with height: humans look down at Nim, Nim looks up at humans; Jesus from behind."""
    if a == "Jesus":
        return f"Jesus, seen only from behind, turns toward {b}"
    verb = "looks up at" if a in SMALL and b not in SMALL else "looks down at" if b in SMALL and a not in SMALL else "looks at"
    return f"{a} {verb} {b}"


def plan_shot(shot, clip_chars, last_speaker=None):
    """Return (eyeline dict or None, [addressee per line])."""
    action = TAG.sub("", shot["action"])
    lines = shot["dialogue"]
    speakers = [speaker_of(d) for d in lines if not d.get("voice_over")]
    present = list(dict.fromkeys([n for n in ORDER if n in names_in(action)] + speakers))
    if last_speaker and last_speaker in clip_chars and last_speaker not in present:
        present.append(last_speaker)  # whoever just spoke is still in the scene
    if len(present) < 2:  # someone speaks to a character who is in the clip but not named in this shot
        present = list(dict.fromkeys(present + [c for c in clip_chars if c not in present]))
    group = group_in(action)
    addressees = []
    for i, d in enumerate(lines):
        me = speaker_of(d)
        if d.get("voice_over"):
            addressees.append(None)
            continue
        # Jesus in the background is never an addressee unless he is named or turned toward
        others = [p for p in present if p != me and p != "Jesus"]
        if "Jesus" in present and me != "Jesus" and (re.search(r"\bJesus\b", d["line"]) or target_in(action, me) == "Jesus"):
            others.append("Jesus")
        named = [p for p in others if re.search(rf"\b{p}\b", d["line"])]
        prev = next((speaker_of(x) for x in reversed(lines[:i]) if speaker_of(x) != me and not x.get("voice_over")),
                    last_speaker if last_speaker != me and last_speaker in present else None)
        nxt = next((speaker_of(x) for x in lines[i + 1:] if speaker_of(x) != me and not x.get("voice_over")), None)
        toward = target_in(action, me) if len(set(speakers)) == 1 else None
        if d.get("addressee_source") == "manual":
            to = d["addressee"]
        elif named:
            to = named[0]
        elif toward:
            to = toward
        elif len(others) == 1 and not group:
            to = others[0]
        elif len(set(speakers)) == 1 and prev:
            to = prev  # replying to whoever spoke last (in this shot, the previous shot, or the previous clip)
        elif len(set(speakers)) == 1 and (group or len(others) >= 2):
            to = group or " and ".join(others)  # one person addressing several
        else:
            to = prev or nxt or group or (others[0] if others else None)
        addressees.append(to)

    talkers = list(dict.fromkeys(s for s in speakers))
    if not lines or not talkers:
        return None, addressees
    if len(talkers) == 1:
        me = talkers[0]
        targets = [a for a in addressees if a]
        listeners = [p for p in present if p != me and (p != "Jesus" or p in targets)]
        single = {t for t in targets if t in ORDER}
        groups = [t for t in targets if t not in ORDER and " and " not in t]
        if groups and set(targets) == set(groups):  # said to a group (e.g. set on review: "the crowd")
            group = groups[0]
        if len(single) == 1 and set(targets) == single:  # every line is said to one person
            other = next(iter(single))
            watchers = [p for p in listeners if p != other]
            direction = f"{me} and {other} face each other; {look(me, other)} while speaking, and {look(other, me)}"
            if watchers:
                direction += f"; {' and '.join(watchers)} watch{'es' if len(watchers) == 1 else ''} them"
            return {"type": "two-person", "speakers": [me, other], "listeners": watchers, "direction": direction}, addressees
        if group or len(listeners) >= 2:
            who = group or " and ".join(listeners)
            if me == "Jesus":
                direction = (f"Jesus, seen only from behind, turns toward {who} while speaking; "
                             f"{who} look back at him")
            else:
                direction = (f"{me} looks around at {who} while speaking, meeting their eyes one by one; "
                             f"{who} look back at {me}")
            return {"type": "group", "speaker": me, "listeners": listeners or [who], "direction": direction}, addressees
        if targets:
            other = targets[0]
            return {"type": "two-person", "speakers": [me, other], "direction":
                    f"{me} and {other} face each other; {look(me, other)} while speaking, and {look(other, me)}"}, addressees
        return None, addressees
    if len(talkers) == 2:
        a, b = talkers
        direction = (f"{a} and {b} turn toward each other and hold eye contact as they talk: "
                     f"{look(a, b)}, {look(b, a)}")
        listeners = [p for p in present if p not in talkers and p != "Jesus"]
        if listeners:
            direction += f"; {' and '.join(listeners)} watch{'es' if len(listeners) == 1 else ''} them"
        return {"type": "two-person", "speakers": [a, b], "listeners": listeners, "direction": direction}, addressees
    return {"type": "several", "speakers": talkers, "direction":
            f"Each speaker ({', '.join(talkers)}) looks at the person they are answering, and the others turn "
            f"to whoever is speaking"}, addressees


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--clip", default="")
    ap.add_argument("--set", action="append", help='addressee on review: "clip:shot:line=Name|reason" (kept on reruns)')
    ap.add_argument("--no-rebuild", action="store_true")
    args = ap.parse_args()

    data = json.loads(PROMPTS.read_text(), strict=False)
    only = {x.strip() for x in args.clip.split(",") if x.strip()}
    clips = {c["id"]: c for c in data["clips"]}
    for item in args.set or []:
        target, _, value = item.partition("=")
        who, _, why = value.partition("|")
        cid, n, k = target.split(":")
        d = clips[cid]["shot_details"][int(n) - 1]["dialogue"][int(k) - 1]
        d.update(addressee=who.strip(), addressee_source="manual", addressee_reason=why.strip() or "set on review")
    counts = {"two-person": 0, "group": 0, "several": 0}
    last_speaker = None
    for c in data["clips"]:
        if c.get("continuity", {}).get("mode") != "continue_scene":
            last_speaker = None
        chars = [m.group(1) for s in c["subjects"] for m in [re.search(r" as (\w+)$", s)] if m]
        for n, s in enumerate(c["shot_details"], 1):
            eyeline, addressees = plan_shot(s, chars, last_speaker)
            spoken = [speaker_of(d) for d in s["dialogue"] if not d.get("voice_over")]
            if spoken:
                last_speaker = spoken[-1]
            if only and c["id"] not in only:
                continue
            for d, to in zip(s["dialogue"], addressees):
                if to:
                    d["addressee"] = to
                else:
                    d.pop("addressee", None)
            if eyeline:
                s["eyeline"] = eyeline
                counts[eyeline["type"]] += 1
            else:
                s.pop("eyeline", None)
            if args.dry_run and (eyeline or addressees):
                print(f"{c['id']}:{n} [{eyeline['type'] if eyeline else '-'}] {eyeline['direction'] if eyeline else ''}")
                for d, to in zip(s["dialogue"], addressees):
                    print(f"      {d['character'].title():16} → {to or '(voice-over)'}: {d['line'][:55]}")
    print(f"{'Preview' if args.dry_run else 'Eyelines'}: {counts['two-person']} two-person, {counts['group']} group, "
          f"{counts['several']} several-speaker shots")
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
