#!/usr/bin/env python3
"""Keep every character in a scene on screen until the screenplay says they leave.

Within a scene (see check_continuity.group_scenes), a character is present from the first clip that has
them as a subject until an action sentence explicitly takes them out: "hurries away", "scatter", "exits",
"leaves", "out of frame", … or "follows" right after someone leaves ("Miri hurries away. Nim follows.").
A new scene starts with nobody carried over. A character who is only heard in a clip (every line is
voice-over, e.g. Saba narrating over the hillside) is not counted as on screen there.

For each clip, a present character with no subject is carried into it:
  image   a named character (Miri, Nim, Saba, …; never Jesus) while the clip has fewer than MAX_IMAGES
          character images: a reference line and subject definition are added (scene and last-frame images
          move down one number each) and they are named "(@Image N) still present" in shot 1's Continuity line
  text    everyone else (groups, unnamed characters, Jesus, or named characters when the clip is full):
          named in shot 1's Continuity line as "… still present", with their short description, so
          Seedance keeps them in the scene without another reference image

Companions come first: wherever Miri is on screen, Nim (her fox) is too. A clip that shows Miri but not Nim
gets Nim as an image right after Miri's (later images move down one number), or by text when the clip is full,
named in shot 1's Continuity line as staying near Miri, with the "small fox, never a dog" constraint.

Every carried character is recorded on the clip ("still_present", "continuity_fixes"), a backup is saved to
data/backups/, and the camera report is rebuilt. Rebuild the curl commands for the changed clips afterwards.

Usage:
  python3 scripts/keep_present.py --dry-run          # list who is carried into which clip, and how
  python3 scripts/keep_present.py                    # apply
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from check_continuity import ORDER, group_scenes
from paths import DATA

PROMPTS = DATA / "prompt.json"
HERE = Path(__file__).resolve().parent
MAX_IMAGES = 4                       # character/group images per clip (Seedance: stability drops above 4)
TEXT_ONLY = {"Jesus"}                # shown only from behind or in silhouette; never given an extra image
EXIT = re.compile(r"\b(exits?|leaves|left the|runs? off|hurries (?:away|off|out)|walks? (?:away|off|out)|"
                  r"departs?|disappears?|scatter\w*|out of (?:frame|sight|view)|goes out)\b", re.I)
FOLLOWS = re.compile(r"\bfollows\b", re.I)
DEFINE = re.compile(r"^Define (.+?) in @Image (\d+) as (.+?)$")
GROUP_WORD = {"the children": "children", "the crowd": "crowd", "the disciples": "disciples"}
TAG = re.compile(r" \(@Image \d+\)")
COMPANIONS = {"Miri": ("Nim", "the small fox", "Miri's small fox")}  # where the first is seen, so is the second
FOLLOW = "follows at {lead}'s heels"  # what the companion does when the lead first comes into a scene
FOX_RULE = "Nim is a small fox, never a dog"


def subject_name(full):
    """'the children (a group)' -> 'the children'; 'Miri' -> 'Miri'."""
    return re.sub(r" \(a group\)$", "", full)


def subjects(clip):
    """{name: (description, full 'as' name)} for the clip's Define lines."""
    out = {}
    for s in clip["subjects"]:
        m = DEFINE.match(s)
        if m:
            out[subject_name(m.group(3))] = (m.group(1), m.group(3))
    return out


def mentions(sentence, name):
    if name in GROUP_WORD:
        return re.search(rf"\b{GROUP_WORD[name]}\b", sentence, re.I) is not None
    return re.search(rf"\b{re.escape(name)}\b", sentence) is not None


def exits(clip, present):
    """Names among `present` that the clip's action lines take off screen, in order."""
    gone, prev_exit = [], False
    for shot in clip["shot_details"]:
        for sentence in re.split(r"(?<=[.!?])\s+", TAG.sub("", shot["action"])):
            leaving = EXIT.search(sentence) or (prev_exit and FOLLOWS.search(sentence))
            if leaving:
                names = [n for n in present if mentions(sentence, n) and n not in gone]
                if "the children" in names:  # an unnamed child defined "from the children" leaves with them
                    names += [n for n in present if n not in names and n not in ORDER and n not in GROUP_WORD]
                gone += names
            prev_exit = bool(leaving)
    return gone


def voice_only(clip, name):
    """True when the character is only heard in this clip (all their lines are voice-over), not seen."""
    lines = [d for s in clip["shot_details"] for d in s["dialogue"] if d["character"].title() == name]
    return bool(lines) and all(d.get("voice_over") for d in lines)


def character_images(clip):
    return [r for r in clip["references"]
            if re.search(r"(character|group) reference|^@Image \d+: Jesus reference", r)]


def text_label(name, desc):
    desc = re.sub(r" from the (crowd|children)$", "", desc)
    if name == "Jesus":
        return "Jesus (seen only from behind or in silhouette)"
    if name in GROUP_WORD:
        return desc
    return f"{name} ({desc})"


def join(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def renumber(clip, start, by):
    """Shift every @Image token >= start up by `by` in the clip's text fields."""
    def sub(t):
        return re.sub(r"@Image (\d+)(?!\d)", lambda m: f"@Image {int(m.group(1)) + by}"
                      if int(m.group(1)) >= start else m.group(0), t)

    def walk(o):
        if isinstance(o, str):
            return sub(o)
        if isinstance(o, list):
            return [walk(x) for x in o]
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items()}
        return o

    for k in ("prompt", "references", "subjects", "scene_setting", "constraints", "audio", "shots",
              "shot_details", "continuity", "asset_preparation", "image_reference", "global_direction"):
        if k in clip:
            clip[k] = walk(clip[k])


def plan(clips):
    """[(clip, [(name, 'image'|'text', description, full name)])] for every clip that needs carries."""
    out = []
    for scene in group_scenes(clips):
        present, known = [], {}
        for clip in scene["clips"]:
            have = subjects(clip)
            for name, val in have.items():
                known.setdefault(name, val)
            already = set(clip.get("still_present_names", []))
            missing = [n for n in present if n not in have and n not in already]
            if missing:
                room = MAX_IMAGES - len(character_images(clip))
                carry = []
                for name in sorted(missing, key=lambda n: ORDER.index(n) if n in ORDER else 99):
                    how = "image" if name in ORDER and name not in TEXT_ONLY and room > 0 else "text"
                    room -= how == "image"
                    carry.append((name, how) + known[name])
                out.append((clip, carry))
            for name in have:
                if name not in present and not voice_only(clip, name):
                    present.append(name)
            for name in clip.get("still_present_names", []):
                if name not in present:
                    present.append(name)
            for name in exits(clip, present):
                present.remove(name)
    return out


def companions_missing(clips):
    """[(clip, lead, companion)] for every clip where the lead is seen and the companion is not."""
    out = []
    for clip in clips:
        have = set(subjects(clip)) | set(clip.get("still_present_names", []))
        for lead, (comp, *_) in COMPANIONS.items():
            if lead in have and comp not in have and not voice_only(clip, lead):
                out.append((clip, lead, comp))
    return out


def add_companion(clip, lead, comp):
    """Put the companion in the clip next to the lead: an image after the lead's when there is room, else text."""
    _, desc, label = COMPANIONS[lead]
    lead_ref = next((i for i, r in enumerate(clip["references"], 1) if r.endswith(f": {lead} character reference")), None)
    how = "image" if lead_ref and len(character_images(clip)) < MAX_IMAGES else "text"
    if how == "image":
        n = lead_ref + 1
        renumber(clip, n, 1)
        ref, define = f"@Image {n}: {comp} character reference", f"Define {desc} in @Image {n} as {comp}"
        lead_define = next(i for i, s in enumerate(clip["subjects"]) if s.endswith(f" in @Image {lead_ref} as {lead}"))
        lead_ref_line, lead_define_line = clip["references"][lead_ref - 1], clip["subjects"][lead_define]
        clip["references"].insert(n - 1, ref)
        if "asset_preparation" in clip:
            clip["asset_preparation"].insert(n - 1, ref)
        clip["subjects"].insert(lead_define + 1, define)
        p = clip["prompt"]
        for line, new in ((lead_ref_line, ref), (lead_define_line, define)):
            assert f"- {line}\n" in p, (clip["id"], line)
            p = p.replace(f"- {line}\n", f"- {line}\n- {new}\n", 1)
        clip["prompt"] = p
        if "image_reference" in clip:
            clip["image_reference"] = clip["image_reference"].replace(
                f"@Image {lead_ref} as {lead}, ", f"@Image {lead_ref} as {lead}, @Image {n} as {comp}, ", 1)
        who = f"{comp} (@Image {n}), {label},"
    else:
        who = f"{comp}, {label} (an orange fox with oversized ears and a cream-tipped tail),"
    note = f"{who} stays near {lead}"

    m = re.search(r"(?m)^  Continuity: (.*)$", clip["prompt"])
    assert m, clip["id"]
    old = m.group(1)
    new = f"{old}; {note}"
    clip["prompt"] = clip["prompt"].replace(f"  Continuity: {old}", f"  Continuity: {new}", 1)
    if old in clip["shots"][0]:
        clip["shots"][0] = clip["shots"][0].replace(old, new, 1)

    if FOX_RULE not in clip["constraints"]:
        before = "Each character appears only once; no duplicate or twin characters"
        i = clip["constraints"].index(before) if before in clip["constraints"] else len(clip["constraints"])
        clip["constraints"].insert(i, FOX_RULE)
        anchor = f"- {before}\n" if before in clip["prompt"] else "- Keep it subtitle-free"
        clip["prompt"] = clip["prompt"].replace(anchor, f"- {FOX_RULE}\n{anchor}", 1)
        if "global_direction" in clip and before in clip["global_direction"]:
            clip["global_direction"] = clip["global_direction"].replace(before, f"{FOX_RULE}. {before}", 1)

    clip["still_present"] = clip.get("still_present", []) + [
        {"name": comp, "how": how, "reason": f"goes everywhere with {lead}"}]
    clip["still_present_names"] = [x["name"] for x in clip["still_present"]]
    clip.setdefault("continuity_fixes", []).append(f"Companion of {lead} kept on screen: {comp} ({how})")
    return how


def follows_missing(clips):
    """[(clip, shot index, lead, companion)]: the lead's first shot in each scene, when its action leaves out the companion."""
    out = []
    for scene in group_scenes(clips):
        for lead, (comp, *_) in COMPANIONS.items():
            first = next(((clip, i) for clip in scene["clips"] for i, s in enumerate(clip["shot_details"])
                          if re.search(rf"\b{lead}\b", s["action"])), None)
            if first and not re.search(rf"\b{comp}\b", first[0]["shot_details"][first[1]]["action"]):
                out.append((*first, lead, comp))
    return out


def add_follow(clip, i, lead, comp):
    """Insert '<companion> follows at <lead>'s heels.' after the lead's first sentence in the shot's action (and after
    any sentences that go on with a pronoun, so 'He …' still means who it meant)."""
    shot = clip["shot_details"][i]
    old = shot["action"]
    sentences = re.split(r"(?<=[.!?])\s+", old)
    k = next(j for j, s in enumerate(sentences) if re.search(rf"\b{lead}\b", s))
    while k + 1 < len(sentences) and re.match(r"(He|She|It|They|His|Her|Its|Their)\b", sentences[k + 1]):
        k += 1
    n = next((m.group(1) for s in clip["subjects"] if (m := re.match(rf"^Define .+ in @Image (\d+) as {comp}$", s))), None)
    sentences.insert(k + 1, f"{comp}{f' (@Image {n})' if n else ''} {FOLLOW.format(lead=lead)}.")
    new = shot["action"] = " ".join(sentences)
    assert f"  Action: {old}\n" in clip["prompt"], clip["id"]
    clip["prompt"] = clip["prompt"].replace(f"  Action: {old}\n", f"  Action: {new}\n", 1)
    if old in clip["shots"][i]:
        clip["shots"][i] = clip["shots"][i].replace(old, new, 1)
    clip.setdefault("continuity_fixes", []).append(f"{comp} {FOLLOW.format(lead=lead)} as {lead} comes into the scene (shot {i + 1})")


def apply(clip, carry):
    scene_ref = next(i for i, r in enumerate(clip["references"], 1)
                     if not re.search(r"(character|group) reference|Jesus reference", r))
    images = [c for c in carry if c[1] == "image"]
    if images:
        scene_line = re.sub(r"^@Image \d+: ", "", clip["references"][scene_ref - 1])
        renumber(clip, scene_ref, len(images))
        new_refs, new_defs = [], []
        for k, (name, _, desc, full) in enumerate(images):
            n = scene_ref + k
            new_refs.append(f"@Image {n}: {name} character reference")
            new_defs.append(f"Define {desc} in @Image {n} as {full}")
        clip["references"][scene_ref - 1:scene_ref - 1] = new_refs
        clip["subjects"] += new_defs
        p = clip["prompt"]
        shifted = f"- @Image {scene_ref + len(images)}: {scene_line}\n"
        assert shifted in p, (clip["id"], shifted)
        p = p.replace(shifted, "".join(f"- {r}\n" for r in new_refs) + shifted, 1)
        p = re.sub(r"(?m)^(SCENE: )", "".join(f"- {d}\n" for d in new_defs).replace("\\", r"\\") + r"\1", p, count=1)
        clip["prompt"] = p

    items = [f"{name} (@Image {scene_ref + i})" for i, (name, *_ ) in enumerate(images)]
    items += [text_label(name, desc) for name, how, desc, _ in carry if how == "text"]
    m = re.search(r"(?m)^  Continuity: (.*)$", clip["prompt"])
    assert m and "Continue the same moment from" in m.group(1), clip["id"]
    old = m.group(1)
    w = re.search(r", with (.+) still present$", old)
    new = (old[:w.start()] + f", with {w.group(1)}, {join(items)} still present") if w \
        else f"{old}, with {join(items)} still present"
    clip["prompt"] = clip["prompt"].replace(f"  Continuity: {old}", f"  Continuity: {new}", 1)
    if old in clip["shots"][0]:
        clip["shots"][0] = clip["shots"][0].replace(old, new, 1)

    clip["still_present"] = clip.get("still_present", []) + [
        {"name": name, "how": how, "reason": "in the scene and has not left yet"} for name, how, *_ in carry]
    clip["still_present_names"] = [x["name"] for x in clip["still_present"]]
    clip.setdefault("continuity_fixes", []).append(
        "Kept on screen (not yet exited): " + ", ".join(f"{n} ({h})" for n, h, *_ in carry))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(PROMPTS.read_text(encoding="utf-8"), strict=False)
    original = PROMPTS.read_text(encoding="utf-8")
    pairs = companions_missing(data["clips"])
    for clip, lead, comp in pairs:  # in memory only until saved, so the dry run's carries below see them too
        print(f"{clip['id']}: {comp} with {lead} [{add_companion(clip, lead, comp)}]")
    print(f"{len(pairs)} clips: companion added")
    follows = follows_missing(data["clips"])
    for clip, i, lead, comp in follows:
        add_follow(clip, i, lead, comp)
        print(f"{clip['id']} shot {i + 1}: {comp} {FOLLOW.format(lead=lead)} as {lead} comes in")
    print(f"{len(follows)} scenes: companion follows the lead in")
    pairs += follows
    todo = plan(data["clips"])
    for clip, carry in todo:
        print(f"{clip['id']}: " + ", ".join(f"{n} [{h}]" for n, h, *_ in carry))
    images = sum(h == "image" for _, carry in todo for _, h, *_ in carry)
    texts = sum(h == "text" for _, carry in todo for _, h, *_ in carry)
    print(f"{len(todo)} clips: {images} characters carried with an image, {texts} by text")
    if args.dry_run or not (todo or pairs):
        return

    backup = DATA / "backups" / f"prompt.{datetime.now():%Y%m%d-%H%M%S}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(original, encoding="utf-8")
    for clip, carry in todo:
        apply(clip, carry)
    PROMPTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {PROMPTS.relative_to(DATA.parent)} (backup: {backup.relative_to(DATA.parent)})")
    subprocess.run([sys.executable, str(HERE / "check_camera.py")], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
