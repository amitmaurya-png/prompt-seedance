# Universal Seedance Prompt Syntax

A single, general structure distilled from the patterns in [prompt_examples.txt](./prompt_examples.txt).
Every example in the corpus, whether a one-paragraph prompt or a 15-shot timeline, fits this skeleton.
Label vocabulary and variants are listed in [prompt_labels.txt](./prompt_labels.txt).

---

## 1. Core rule

A prompt is an ordered list of **blocks**. Each block is a **label** followed by **content**:

```
LABEL: content
```

- Labels are plain words in Title Case or UPPERCASE, ending with a colon.
- Use one block per line (or per paragraph for long blocks).
- Keep the canonical order below. The model reads top to bottom: global context first, then time, then rules.
- Leave out any block that does not apply. Never leave an empty label.

---

## 2. Canonical block order

| # | Block | Required | Purpose | Common aliases in corpus |
|---|-------|----------|---------|--------------------------|
| 1 | `FORMAT` | yes | Duration, aspect ratio, shot count, cut style, tempo | Duration, Basic Settings, Quality |
| 2 | `STYLE` | yes | Visual genre, rendering look, color, lighting, mood | Tone, Mood, Atmosphere, Lighting, Color Grade |
| 3 | `REFERENCES` | if assets given | Role of each supplied image / video / audio | Input, Start / End frame |
| 4 | `SUBJECT` | yes | Who/what is on screen and how it looks | Character, Subjects, Protagonist, Product |
| 5 | `SCENE` | yes | Location, time of day, weather, environment | Environment, Location, Scene Setup |
| 6 | `CAMERA` | optional | Global camera behavior (if not per shot) | Camera Language, Camera Movement |
| 7 | `SHOTS` | yes | The timeline: what happens, in order | Timeline, Sequence, Shot Script, Shot Breakdown |
| 8 | `AUDIO` | optional | Music, SFX, ambience, dialogue, lyrics | Sound Design, Music, Dialogue, Background Music |
| 9 | `CONSTRAINTS` | optional | Allowed / prohibited, hard rules | Rules, Requirement, Note, Important, Negative |

Minimum valid prompt = `FORMAT` + `STYLE` + `SUBJECT` + `SCENE` + `SHOTS`.

---

## 3. Block grammar

### FORMAT
Slash-separated tokens, most important first:

```
FORMAT: <duration> / <aspect ratio> / <shot count or "one continuous shot"> / <cut style> [/ <BPM>]
```
Example: `FORMAT: 15s / 16:9 / 3 shots / hard cuts on the beat / 120 BPM`

### STYLE
Comma-separated descriptors, going from broad to specific:

```
STYLE: <genre or medium>, <render quality>, <color palette>, <lighting>, <mood>
```

### REFERENCES
One line per asset. Use the same token everywhere in the prompt:

```
REFERENCES:
- @image1: <role>        e.g. character appearance
- @image2: <role>        e.g. end frame
- @video1: <role>        e.g. motion/choreography only
- @audio1: <role>        e.g. voice timbre
```
Only list assets that actually exist. Do not re-describe what the image already shows.

### SUBJECT
One line per subject. Give each a short, stable tag (`A`, `B`, or a name) so the shots can refer to it:

```
SUBJECT:
- A (<name/role>): <age/species>, <build>, <hair>, <face>, <wardrobe>, <props>
- B (<name/role>): ...
```

### SCENE
```
SCENE: <location>, <time of day>, <weather/air>, <key background elements>
```

### CAMERA (global)
```
CAMERA: <lens/feel>, <default movement>, <stabilization>, <depth of field>
```

### SHOTS
One entry per shot or beat. The time range comes first, then the shot label, then fixed sub-fields:

```
[<start>-<end>s] Shot <n>: <short title>
  Camera: <framing> + <one primary move>
  Action: <concrete visible action by subject tag>
  Visual: <environment response, effects, light changes>
  Audio: <sound tied to this beat>            (optional)
```

Timecode forms. Pick one and use it for the whole prompt:
- `[0-3s]` (recommended), `[00:00-00:03]`, or `0-3 seconds:`
- Ranges must be continuous and must add up to the `FORMAT` duration.
- Single continuous shot: use beats (`Start:`, `Middle:`, `End:`) instead of shots.

### AUDIO
```
AUDIO:
- Music: <genre>, <BPM>, <arc>
- SFX: <key sounds>
- Ambience: <background bed>
- Dialogue: A: "<exact line>" (<delivery>)
```
Dialogue and lyrics go in double quotes, exactly once, with the speaker tag.

### CONSTRAINTS
```
CONSTRAINTS:
- Allowed: <...>
- Prohibited: <...>
- <hard rule>
```
Write a few concrete rules. Avoid long lists of generic quality tags.

---

## 4. Template (copy and fill)

```
FORMAT: <duration> / <aspect ratio> / <shot count> / <cut style>
STYLE: <genre>, <quality>, <palette>, <lighting>, <mood>
REFERENCES:
- @image1: <role>
SUBJECT:
- A (<name>): <appearance>, <wardrobe>, <props>
SCENE: <location>, <time>, <weather>, <background>
CAMERA: <default camera behavior>
SHOTS:
[0-5s] Shot 1: <title>
  Camera: <framing + move>
  Action: <A does ...>
  Visual: <environment response>
[5-10s] Shot 2: <title>
  Camera: ...
  Action: ...
  Visual: ...
[10-15s] Shot 3: <title>
  Camera: ...
  Action: ...
  Visual: ...
AUDIO:
- Music: <...>
- SFX: <...>
- Dialogue: A: "<line>"
CONSTRAINTS:
- Prohibited: <...>
- <rule>
```

---

## 5. Worked example (original)

```
FORMAT: 10s / 16:9 / 3 shots / hard cuts
STYLE: Live-action cinematic, 4K, teal-and-amber palette, low sun backlight, quiet tension
SUBJECT:
- A (Courier): woman in her 30s, short black hair, rain-soaked olive jacket, silver case chained to wrist
SCENE: Empty elevated train platform at dusk, light rain, flickering signage
SHOTS:
[0-3s] Shot 1: Arrival
  Camera: Wide shot, slow push-in
  Action: A steps off the train and scans the platform
  Visual: Train doors hiss shut behind her, rain streaks through the backlight
[3-7s] Shot 2: The signal
  Camera: Medium close-up, handheld
  Action: A's phone buzzes; she reads it and tightens her grip on the case
  Visual: Signage flickers off, platform drops into shadow
[7-10s] Shot 3: Departure
  Camera: Low-angle tracking shot following A
  Action: A walks briskly toward the exit stairs without looking back
  Visual: Puddles ripple under each step, the train pulls away in the background
AUDIO:
- SFX: train hiss, phone buzz, footsteps on wet concrete
- Ambience: steady rain, distant city hum
CONSTRAINTS:
- One camera move per shot
- Prohibited: text overlays, face distortion, flicker
```

---

## 6. Compact (paragraph) form

For short clips the same order can be written as one paragraph, as in Cases 1 and 2 of the corpus:

```
<FORMAT>, <STYLE>. <SUBJECT> in <SCENE>. <0-3s: camera + action>. <3-7s: camera + action>. ... <AUDIO>. <CONSTRAINTS>.
```

The order and content are the same. Only the labels are left out.

---

## 7. Validation checklist

- [ ] Blocks appear in canonical order; no empty labels
- [ ] Shot time ranges are continuous and add up to the `FORMAT` duration
- [ ] Each shot has one primary camera move and one concrete visible action
- [ ] Subject tags (`A`, `B`, names) and asset tokens (`@image1`) are consistent throughout
- [ ] Dialogue is quoted exactly, attributed, and appears once
- [ ] No contradictions between `STYLE`, `CAMERA`, shots, and `CONSTRAINTS`
- [ ] Only assets that were actually supplied are referenced
