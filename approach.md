# Approach: from the screenplay PDF to Seedance text prompts

## Source

The episode is the screenplay PDF "Little Witnesses: The Smallest Lunch."
The goal is a set of text prompts that can be pasted into Seedance 2.0, one short clip at a time.

## Step 1. Read the screenplay as acts, scenes, and shots

`extract_breakdown.py` sends the PDF text to Google Gemini (`gemini-3.5-flash`, falling back to a lighter Gemini model if that one is busy).
The model returns JSON, saved as `breakdown.json`.

- An **act** is a heading such as `ACT ONE`. Text before the first act is the cold open.
- A **scene** is a heading that starts with `INT.` or `EXT.`
- A **shot** is one visible action plus the dialogue spoken during that action.

The current breakdown has 4 acts, 16 scenes, and 48 shots.

## Step 2. Follow the Seedance 2.0 prompt guide

The guide is the BytePlus page [Dreamina Seedance 2.0 series prompt guide](https://docs.byteplus.com/en/docs/ModelArk/2222480).

Seedance does not use acts or scenes. One generation is one clip of 4 to 15 seconds.
Inside a clip, the story is written as `Shot 1`, `Shot 2`, and `Shot 3`.
Each shot has no fixed length. The model sets the pace. Times such as `0-3 seconds` are not used.
Each shot gets one camera move, the action, the place, and the sound.
Spoken lines go in `{curly braces}`.

The basic formula for a new clip is a short reference sentence:

> Reference the subject in Image 1 to generate the action, the place, one camera move, and the spoken lines.

A voice, when needed, is a second sentence: Reference the timbre in Audio 1 to generate that voice.
A video reference is used only when the clip copies a move from an existing video.

A longer film is assembled afterward. A conversation that stays in one place can be extended.
A change of place, a chase, or the hillside miracle is rendered as separate clips and cut together.

## Step 3. Turn script shots into Seedance clips

`build_prompts.py` reads `breakdown.json` and calls Gemini twice.

1. Gemini groups the script shots into clips. Shots stay together when the place, the people, and the feeling stay the same. A new clip starts when one of those changes. A clip holds about two or three shots, short enough for 4 to 15 seconds. A script shot with too many spoken lines is split.
2. Gemini writes the basic formula: an image reference sentence, and an audio reference sentence when a voice is needed. The script joins those sentences into one text prompt.

The result is `prompts.json`. Each clip stores the basic-formula sentences and a finished `prompt` string. Re-run `build_prompts.py` to replace prompts that were written with the advanced formula.

## Step 4. Use the text prompt

The value of `prompt` is what gets pasted into Seedance. No reference image is required for a text-only test. Lines that say `Image 1` are descriptions of the characters and the place.

Before generating, read the prompt. Character details can drift. In the script Nim is a fox; an early prompt described Nim as a dog. Jesus is shown only by hands, robe, and silhouette, never by a face.

Generate one village clip first. If the look holds, reuse the same style line for the later clips.

## Files

| File | Role |
|---|---|
| `extract_breakdown.py` | PDF to `breakdown.json` |
| `breakdown.json` | Acts, scenes, and shots |
| `build_prompts.py` | `breakdown.json` to `prompts.json` |
| `prompts.json` | Formula fields and the text prompt for each clip |
| `.env` | `GEMINI_API_KEY`, not committed |
