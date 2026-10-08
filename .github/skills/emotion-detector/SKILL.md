---
name: emotion-detector
description: "Detect the emotion of every dialogue line and the mood of each conversation in this project's Seedance prompts, and write it into data/prompt.json as attributes on each character's line (emotion, intensity, delivery) plus a conversation mood per shot. The delivery is added to the prompt's Dialogue lines so Seedance acts it. Use when detecting or reviewing the mood of a conversation, the emotion of a character's line, or how a line should be delivered."
argument-hint: "[clip id, scene, or character]"
---

# Emotion Detector

Detect how each line of dialogue should feel and be delivered, record it on the line in `data/prompt.json`, and carry it into the prompts and `reports/camera_report.html`. The words of the dialogue never change.

## References

| File | Use it for |
|---|---|
| [emotion_guide.md](./references/emotion_guide.md) | The emotions, their delivery words and cues, how lines are scored, how to override, and the rules |
| [camera_moods.md](../camera-knowledge/references/camera_moods.md) | Shot moods from the action, which the detector uses as one signal |
| [breakdown.json](../../../data/breakdown.json) | The screenplay's dialogue (source of truth for the words) |

## Scripts

Run from the repository root.

| Script | When to run it |
|---|---|
| [scripts/detect_emotions.py](../../../scripts/detect_emotions.py) `--dry-run` | Preview every line's emotion, intensity, and evidence |
| `python3 scripts/detect_emotions.py [--clip clip-37]` | Write `emotion`, `intensity`, `delivery`, `emotion_evidence`, `emotion_source` on each line and `conversation_mood` on each shot (backup saved), then rebuild prompts and `reports/camera_report.html` |
| `python3 scripts/detect_emotions.py --set clip-01:1:2=teasing` | Override one line (clip:shot:line); kept on later runs |
| `python3 scripts/detect_emotions.py --clear-manual` | Return overridden lines to automatic detection |

## Workflow

1. Preview with `python3 scripts/detect_emotions.py --dry-run` (or `--clip` for one clip).
2. Review against the scene: the detector reads words, punctuation, the speaker's manner, and the shot's action, not subtext. Override lines that read wrong with `--set`, and say why.
3. Apply with `python3 scripts/detect_emotions.py`. It writes the attributes, then runs `add_continuity.py` (which adds the delivery to each Dialogue line, e.g. `Nim (@Image 2), playfully: {…}`) and `check_camera.py`.
4. Confirm in `data/prompt.json` that every line has an `emotion` and that the dialogue text matches `data/breakdown.json`.
5. In `reports/camera_report.html`, each line shows its emotion tag (hover for the evidence) and each shot's Dialogue panel shows its conversation mood.
6. Report the emotion counts and any lines you overrode.

## Rules

- Never change dialogue words, speakers, or order.
- Jesus is always calm.
- Prefer short, actable delivery words; avoid stacking several emotions on one line.
- Camera choices belong to `camera-knowledge`, continuity to `scene-continuity` and `clip-continuity`; this skill covers dialogue emotion only.
