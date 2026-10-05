#!/usr/bin/env python3
"""Rebuild prompt.json so consecutive clips play as one continuous story.

Reads the clips already in prompt.json and adds, per the seedance-prompting skill:
- a fixed character order, so a character always sits in the same slot of the asset list
- a per-scene CONTINUITY block (light, props, screen positions) repeated in every clip of the scene
- for clips that continue a scene: the previous clip's last frame as a reference image and a handoff line
- a held final frame on every clip, a continuing music cue, and fixed voice descriptions
- api_params.return_last_frame so each clip returns the frame the next clip needs

Safe to run more than once: prompts are rebuilt from the structured fields every time.
"""

import json
import re
from pathlib import Path

PATH = Path(__file__).with_name("prompt.json")

ORDER = ["Miri", "Nim", "Saba", "Ima", "Tav", "Yonah", "Andrew", "Philip", "Jesus"]

VOICE = {
    "Miri": "bright, earnest young girl",
    "Nim": "quick, light, playful",
    "Saba": "warm, slow, gently gravelly elder",
    "Ima": "calm, warm mother",
    "Tav": "small, eager boy",
    "Yonah": "soft, sincere boy",
    "Andrew": "gentle, steady man",
    "Philip": "anxious, practical man",
    "Jesus": "calm, warm, unhurried man",
}

CONTINUITY = {
    "EXT. MIRI’S VILLAGE — MORNING":
        "Early morning, low warm sun from frame left, long soft shadows on the lane. "
        "Miri holds the small cloth bundle with three honey-date cakes until Ima hands her the linen basket; "
        "then the cakes stay hidden in the basket's cloth. Screen positions: Miri frame left, Ima at the doorway "
        "frame right, Nim at Miri's feet.",
    "EXT. VILLAGE LANE — MOMENTS LATER":
        "Late morning, bright sun from frame left. Miri carries the linen basket on her arm, cakes hidden in the "
        "cloth. Tav's toy cart lies beside him with one wooden wheel off. Screen positions: Miri and Nim travel "
        "left to right; Tav sits by the low wall frame right.",
    "EXT. SABA ELIOR’S COURTYARD — LATE MORNING":
        "Late morning, dappled sunlight through the fig leaves. Saba holds the sandal he is repairing; his sleeve "
        "is patched; Miri's linen basket holds the linen and the hidden cake bundle. Screen positions: Saba under "
        "the fig tree frame left, Miri frame right, Nim near the roots between them.",
    "INT. SABA’S HOUSE — CONTINUOUS / INT. SCROLL ROOM — CONTINUOUS":
        "Warm, dim interior light with dust floating in shafts of light. Endless shelves of old scrolls. "
        "Screen positions: Saba leads frame right, Miri follows frame left, Nim at her heels.",
    "INT. SCROLL ROOM — CONTINUOUS":
        "Warm, dim interior light with dust floating in shafts of light; the small scroll is tied with a cord "
        "until Saba opens it. Screen positions: Saba frame right, Miri frame left, Nim beside Miri.",
    "EXT. GALILEAN HILLSIDE — DAY":
        "Bright midday sun over the lake; families and disciples fill the slopes. "
        "Screen positions: Miri frame left, Nim at her feet, the lake below in the background.",
    "EXT. HILLSIDE PATH — CONTINUOUS":
        "Bright daylight, sun slightly lower. Yonah holds his small cloth lunch bundle close. "
        "Screen positions: Miri frame left, Yonah frame right, Nim between them; they move left to right "
        "through the crowd.",
    "EXT. EDGE OF CROWD — LATER":
        "Warm afternoon light. Yonah's lunch is unwrapped on its cloth: five barley loaves and two fish. "
        "Screen positions: Miri frame left, Yonah frame right, the lunch between them, Nim in front; "
        "Andrew approaches from frame right.",
    "EXT. NEAR JESUS — CONTINUOUS":
        "Afternoon daylight; the crowd surrounds the open grass. Andrew carries Yonah's lunch bundle. "
        "Screen positions: Jesus seen only from behind, frame center-right; Andrew and Yonah approach from "
        "frame left; Miri and Nim watch from the edge, frame left.",
    "EXT. HILLSIDE — MOMENTS LATER":
        "Afternoon light; thousands seated in clusters on the grass; baskets of bread pass hand to hand. "
        "Screen positions: Miri frame left with her basket, Andrew frame right, Yonah beside Miri, Nim at her feet.",
    "EXT. HILLSIDE — LATE AFTERNOON":
        "Late afternoon, golden light; the fed crowd rests; leftover bread is gathered into baskets. "
        "Screen positions: Miri frame left, Yonah frame right, Andrew among the disciples behind them.",
    "EXT. HILLSIDE — CONTINUOUS":
        "Late afternoon, golden light; twelve baskets fill with leftover bread in a row behind the children. "
        "Screen positions: Miri frame left, Yonah frame right, Nim between them.",
    "EXT. HILLSIDE RIDGE — SUNSET":
        "Sunset, orange light from frame right over the lake. "
        "Screen positions: Miri frame left, Nim at her right; the resting crowd and lake below in the background.",
    "INT. SCROLL ROOM — LATE AFTERNOON":
        "Late-afternoon light from a small window, dust in the beams; the small scroll lies open on the floor. "
        "Screen positions: Saba frame right, Miri frame left on the floor, Nim beside Miri.",
    "EXT. VILLAGE LANE — SUNSET":
        "Sunset, long golden shadows from frame left. Tav's cart has its wheel off until Miri helps fix it; "
        "Miri carries one honey cake for Tav. Screen positions: Tav by the low wall frame right; Miri and Nim "
        "approach from frame left; Ima and Saba further down the lane.",
    "EXT. SABA’S COURTYARD — EVENING":
        "Evening, soft blue light with warm lamp glow under the fig tree. "
        "Screen positions: Saba frame left, Miri beside him frame right, Nim in front.",
}

# Openings rewritten so the clip picks up exactly where the previous one ended.
HANDOFF_FIXES = {
    "clip-32": ("Medium two-shot, tracking to a stop",
                "Still walking, Miri slows and looks at the crowd, then at the bundle Yonah holds; "
                "Nim trots between them, then sits"),
    "clip-51": ("Slow arc around Miri and Nim",
                "Miri sits down slowly beside Nim on the ridge, and they look out together"),
}

# Scene headings that change but stay in the same place and moment (script says CONTINUOUS).
CONTINUES_ACROSS_HEADING = {"clip-45"}

TAG = re.compile(r" \(@Image \d+\)")


def same_scene(prev, clip):
    return prev and prev["act"] == clip["act"] and (
        prev["scene"] == clip["scene"] or prev["scene"].endswith(" / " + clip["scene"]))


def characters(clip):
    names = [m.group(1) for s in clip["subjects"] for m in [re.search(r" as (\w+)$", s)] if m]
    return sorted(names, key=ORDER.index)


def bind(text, tags):
    """Tag the first non-possessive mention of each character with its image."""
    text = TAG.sub("", text)
    for ch, tag in tags.items():
        name = "Saba Elior" if ch == "Saba" and "Saba Elior" in text else ch
        m = re.search(rf"\b{name}\b(?!['’]s)", text)
        if m:
            text = text[:m.end()] + f" ({tag})" + text[m.end():]
    return text


def dialogue(shot, tags):
    seen, parts = set(), []
    for d in shot["dialogue"]:
        name = d["character"].title()
        if name in tags and name not in seen:
            seen.add(name)
            name = f"{name} ({tags[name]})"
        parts.append(f"{name}: {{{d['line']}}}")
    return " ".join(parts)


def main():
    data = json.loads(PATH.read_text(), strict=False)
    clips = data["clips"]
    prev = None
    for clip in clips:
        title_card = clip["scene"] == "MAIN TITLES"
        chained = (same_scene(prev, clip) or clip["id"] in CONTINUES_ACROSS_HEADING) and not title_card
        chars = characters(clip)
        tags = {ch: f"@Image {i}" for i, ch in enumerate(chars, 1)}
        loc_img = len(chars) + 1
        last_img = loc_img + 1 if chained else None

        old_loc = next(r for r in clip["references"] if r.endswith(("scene reference", "style reference")))
        loc_label = re.sub(r"^@Image \d+: ", "", old_loc)
        loc_desc = re.sub(r" \(@Image \d+\)$", "", clip["scene_setting"])
        ambience = next((a for a in clip["audio"] if a.startswith("Sound effects")), "")

        refs = [f"{tags[ch]}: {ch} character reference" if ch != "Jesus"
                else f"{tags[ch]}: Jesus reference (robe, hands, silhouette only)" for ch in chars]
        refs.append(f"@Image {loc_img}: {loc_label}")
        if chained:
            refs.append(f"@Image {last_img}: last frame of {prev['id']} (continuity reference)")

        defs = {re.search(r" as (\w+)$", s).group(1): s for s in clip["subjects"] if s.startswith("Define")}
        subjects = [re.sub(r"@Image \d+", tags[ch], defs[ch]) for ch in chars] or \
            [f"A painted parchment title card in the style of @Image {loc_img}"]

        shots = clip["shot_details"]
        if clip["id"] in HANDOFF_FIXES:
            shots[0]["camera"], shots[0]["action"] = HANDOFF_FIXES[clip["id"]]
        for s in shots:
            s["action"] = bind(s["action"], tags)

        handoff = None
        if chained:
            handoff = (f"Continue the same moment from @Image {last_img}: keep the lighting, positions, props, "
                       f"and character appearance exactly as in that frame")

        speakers = sorted({d["character"].title() for s in shots for d in s["dialogue"]} & set(VOICE),
                          key=ORDER.index)
        has_lines = any(s["dialogue"] for s in shots)
        if title_card:
            audio = [a for a in clip["audio"]]
        else:
            music = ("（the gentle storybook theme continues from the previous clip"
                     if chained else "（the gentle storybook theme begins softly")
            music += ", under the dialogue）" if has_lines else "）"
            audio = [ambience, f"Music: {music}"]
            if speakers:
                audio.append("Voices: " + "; ".join((f"{ch} ({tags[ch]}) {VOICE[ch]}" if ch in tags
                                                  else f"{ch} (voice-over) {VOICE[ch]}") for ch in speakers)
                             + "; clear English dialogue")
            else:
                audio.append("No dialogue")

        base = [c for c in clip["constraints"]
                if not c.startswith(("End on a calm", "Match lighting", "Keep it subtitle-free"))]
        if title_card:
            constraints = base
        else:
            constraints = base + ["End on a calm, held frame with no new action in the final second"]
            if chained:
                constraints.append(f"Match lighting, positions, props, and character appearance to @Image {last_img}")
            constraints.append("Keep it subtitle-free; avoid generating any text or subtitles; "
                               "do not generate a logo; do not generate a watermark")

        cont = CONTINUITY.get(clip["scene"])
        p = [f"FORMAT: {clip['format']}", f"STYLE: {clip['style']}", "REFERENCES:", *[f"- {r}" for r in refs],
             "SUBJECT:", *[f"- {s}" for s in subjects], f"SCENE: {loc_desc} (@Image {loc_img})"]
        if cont:
            p.append(f"CONTINUITY: {cont}")
        p.append("SHOTS:")
        for i, s in enumerate(shots, 1):
            p.append(f"Shot {i}: {s['title']}")
            if i == 1 and handoff:
                p.append(f"  Continuity: {handoff}")
            visual = s["visual"]
            if title_card and "【" not in visual:
                visual = visual.replace("Title text reads: ", "Title text: 【") + "】"
            p += [f"  Camera: {s['camera']}", f"  Action: {s['action']}", f"  Visual: {visual}"]
            if s["dialogue"]:
                p.append("  Dialogue: " + dialogue(s, tags))
        p += ["AUDIO:", *[f"- {a}" for a in audio], "CONSTRAINTS:", *[f"- {c}" for c in constraints]]

        clip.update({
            "references": refs,
            "subjects": subjects,
            "scene_setting": f"{loc_desc} (@Image {loc_img})",
            "continuity": {
                "previous_clip": prev["id"] if chained else None,
                "mode": "continue_scene" if chained else "new_scene",
                "last_frame_reference": f"@Image {last_img}" if chained else None,
                "scene_state": cont,
            },
            "audio": audio,
            "constraints": constraints,
            "prompt": "\n".join(p) + "\n",
            "asset_preparation": refs,
            "image_reference": (
                ("Use " + ", ".join(f"{tags[ch]} as {ch}" for ch in chars) + f", and @Image {loc_img}"
                 if chars else f"Use @Image {loc_img}")
                + " as the scene reference"
                + (f"; continue from the last frame of {prev['id']} in @Image {last_img}." if chained else ".")),
            "shots": [
                f"{s['title']}. " + (f"{handoff}. " if i == 0 and handoff else "")
                + f"{s['camera']}. {s['action']}. {s['visual']}."
                + (" " + dialogue(s, tags) if s["dialogue"] else "")
                for i, s in enumerate(shots)],
            "global_direction": (
                f"The entire video should be {clip['style'][0].lower() + clip['style'][1:]}. "
                + (f"Continuity: {cont} " if cont else "")
                + " ".join(a + "." for a in audio) + " " + ". ".join(constraints) + "."),
        })
        clip["api_params"]["return_last_frame"] = True
        prev = clip

    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    chained = sum(1 for c in clips if c["continuity"]["mode"] == "continue_scene")
    print(f"{len(clips)} clips: {chained} continue a scene, {len(clips) - chained} open a new scene")


if __name__ == "__main__":
    main()
