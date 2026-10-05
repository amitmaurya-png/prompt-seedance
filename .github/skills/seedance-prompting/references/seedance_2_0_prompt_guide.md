# Seedance 2.0 Prompt Guide (official notes)

Condensed notes from the BytePlus ModelArk **Dreamina Seedance 2.0 series prompt guide**.
Source: https://ai.byteplus.com/ark/region:ap-southeast-1/docs/ModelArk/seedance-2-0-prompt-guide
(read 2026-09-30). Check the source for the full text, example videos, and updates.
Applies to Seedance 2.0, 2.0 Fast, and 2.0 Mini.

---

## 1. Task types and basic patterns

| Task | Use for | Pattern |
|---|---|---|
| Omni reference: image | Reuse a subject, style, or scene | Reference `<Subject_N>` in `<Image_N>` to generate ... |
| Omni reference: video | Copy action, camera movement, style, or sound effects | Reference `<Action/Camera_movement/Style/Sound_effect>` in `<Video_N>` to generate ... |
| Omni reference: audio | Copy a voice timbre | Reference the timbre in `<Audio_N>` to generate ... |
| Edit: add | Insert an element | Describe `<Element_Features>` + `<Timing>` + `<Location>` |
| Edit: modify | Change an attribute | Strictly edit `<Video_N>`, and modify `<Original>` in it to `<New>` |
| Edit: delete | Remove an element | Name what to delete; restate what must stay unchanged |
| Extend | Continue in time | Extend `<Video_N>` forward/backward to generate ... |
| Track completion | Bridge clips | `<Video_1>` + `<Transition>` + followed by `<Video_2>` + `<Transition>` + followed by `<Video_3>` |
| Combined | Reference one asset, edit another | Reference `[Dimension]` of `<Image/Video_N>`, strictly edit `<Video_X>`, `[Edits]` |

- In edit and extend tasks, refer to the video directly as `Video N`. Do not write "reference Video N", or the model treats it as a reference task.
- Parts of a video that the prompt does not mention stay unchanged in edit tasks.

---

## 2. Advanced formula

```
precise subject + action details + scene/environment + lighting & color tone
+ camera movement + visual style + image quality + constraints
```

The model splits a prompt into a **spatial layer** (what is in the frame) and a **temporal layer** (how it changes).
Write engineering-style instructions, not marketing copy. Establish who is doing what first, then where and what atmosphere, then how it is shot, and finish with style, quality, and constraints.

### 2.1 Define the subject
- Pattern: Define `[2-3 stable features]` in `<Image/Video_N>` as `<Subject_N>`.
  Example: "Define the woman wearing a red dress and a straw hat in Image 1 as Zhang Hong."
- **Same subject in several assets:** define the subject in Image 1 and the subject in Image 2 as one `<Subject_N>`.
- **Several subjects:** give each a unique, stable label and use exactly that label every time.
- **Subjects not defined up front:** bind each mention with `@`, e.g. "Zhang San@Image 1".
- **Asset IDs:** still refer to the subject as `Image N` / `Video N` in the prompt, never by the asset ID.
- Keep descriptions short and non-contradictory. Let reference images carry spatial layout instead of long text.

### 2.2 Shot sequencing
- Write a storyboard: `Shot 1`, `Shot 2`, `Shot 3`, in the order events happen.
- **Do not force per-shot durations.** Precise timing such as "0-3 seconds" is unstable and can break generation. Let the model set the pace.
- Order inside each shot:
  1. Camera move or transition (slow push-in from a wide shot, fixed camera, cut to ...)
  2. Subject action and expression
  3. Position and spatial change
  4. Audio (sound effects, voice, music)

### 2.3 Action description
- Name the body part and quantify the motion's range, speed, and force: "slowly raise a hand", "slightly lower the head".
- Prefer slow, gentle, continuous small movements. Avoid sprints, big jumps, and violent rolls.
- Describe the transitions between actions, e.g. "use the inertia of turning to raise a hand".
- Show emotion through physical detail instead of abstract words:

| Emotion | Show it as |
|---|---|
| Sadness | head lowered, shoulders trembling, eyes reddening, fingers clutching clothing |
| Joy | mouth corners rising, relaxed brows, light steps, humming, a small spin |
| Nervousness | checking a watch, tapping fingers, rapid breathing, darting eyes |
| Anger | clenched fists, tense jaw, heaving chest, words through gritted teeth |
| Relief | long exhale, shoulders dropping, faint smile, looking into the distance |

### 2.4 Camera
- Standard terms work well: medium shot, close-up, wide shot, slow push-in, smooth lateral tracking, fixed shot.
- **Use one camera movement per shot.** Combining push, pull, pan, and move makes the image unstable.

### 2.5 Quality, style, constraints
- **Quality:** HD, rich details, cinematic texture, natural colors, soft lighting.
- **Style:** name it explicitly, e.g. "retro film", "2D Japanese anime style", "3D Chinese-style comic".
- **Constraints:** "keep it subtitle-free", "avoid generating any text or subtitles", "do not generate a logo", "do not generate a watermark".

### 2.6 Official case layout
```
Asset preparation:
- @Image 1: <character>    - @Image 2: <scene>
- @Video 1: <camera-movement reference>    - @Audio 1: <ambience / music>

Prompt:
Use <subject> in @Image 1 as the main character, use @Image 2 as the scene reference,
and refer to the camera movement in @Video 1.

**Shot 1**: <time/place>, <subject @Image 1> <action>. <camera>. <light/space>.
**Shot 2**: ... says {dialogue} ...
**Shot 3**: ...

The entire video should have <style>, <tone/lighting>. Faces stay stable without deformation;
movements are natural and smooth, with no stutter or flicker. <audio direction>.
```

---

## 3. Special symbols

| Information | Symbol | Example |
|---|---|---|
| Music | `（ ）` | （fast-paced rock music is playing in the background） |
| Sound effect | `< >` | < dog barking can be heard in the distance > |
| Dialogue | `{ }` | {Hello, world}. For languages other than Chinese or English, name the language: says in Japanese {こんにちは} |
| Subtitles / on-screen text | `【 】` | 【Chapter One: Departure】 |

- Keep dialogue in one language. Do not mix Chinese and English, except for proper nouns.
- **`【 】` asks for rendered on-screen text.** Do not use it for section labels in Seedance 2.0 prompts.

---

## 4. Production tips

- **Extension vs stitching:**
  - Use extension (one continuous long take) for dialogue in a single place.
  - Generate separate clips and cut them together for plot turns, chases, fights, and montages.
  - Combining the two is normal.
- **Assets:**
  - Aim for 4-5 in total: 1-2 character images (headshot and/or full body) + 1 scene image + 1 camera-movement video + 1 audio clip.
  - Do not max out the limit. Too many assets cause style conflicts and blurred subject identity.
- **Characters:** stability drops above **4 reference people** (wrong head count, duplicates). If you need more, generate grouped images of 4 or fewer people first, then use those images as references.
- **Text in video:** slogans, subtitles, and speech bubbles are supported. Use common characters only.
  - Slogan: `[Text] + [Timing] + [Position] + [Entrance style], [Color, font]`
  - Subtitles: "Display subtitles at the bottom-center ... synchronized with the audio."
  - Speech bubble: `[Character] says, "[Line]." Speech bubbles appear around the character containing the spoken text.`
- **Reference templates:**
  - Image: Refer to / Extract / Combine the `[subject]` from `[Image N]` to generate `[scene]`, keeping `[subject]` features consistent.
  - Video: Refer to the `[motion / camera movement / special effect]` from `[Video N]` to generate `[scene]`, keeping it consistent.
  - Upload images in the order you want them used, and refer to them as `Image 1 ... Image N`.

---

## 5. Troubleshooting (FAQ)

| Problem | Fix |
|---|---|
| Face drifts or looks like a celebrity | Add a separate headshot-only image (neutral expression, minimal background) beside the full-body image; state which image gives facial features and which gives styling; put the most important assets first. Avoid multi-view character sheets. |
| Unwanted subtitles | Add "keep it subtitle-free / avoid any text or subtitles"; remove text from the reference assets; prefer landscape (subtitles appear less often). |
| Logo or watermark | Add "do not generate watermarks / logos". |
| Style drifts to live action | Name the style explicitly; convert realistic reference images to the target style first. |
| Jump at an extension join | In the edit, trim 6 frames from the end of the earlier clip and 1 frame from the start of the later clip; end clips at natural cut points. |
| Duplicate "twin" characters | Tag every name with its image, e.g. "Zhang San (Image 1)"; add a no-duplicates constraint at the end; use single-person reference images; do not paste the whole script as the prompt. |
| Quality loss over repeated extensions | Convert the source to a white 3D-model video before extending; use HD references; limit how many times you extend. |
| Effect doesn't match the description | Give a reference video of the effect instead of describing it. |
| Click or noise at the end | Regenerate, or fade out the final audio in an editor. |
| Voice doesn't match the audio reference | Describe the voice in detail, e.g. "the low, warm, grainy middle-aged male voice of @Audio 1 says ..."; keep the lines' tone close to the reference audio. |
| Mispronounced Chinese | Swap hard characters for common homophones. |
