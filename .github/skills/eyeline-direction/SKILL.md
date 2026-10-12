---
name: eyeline-direction
description: "Set where characters look while they talk in this project's Seedance prompts: when two people talk they face and look at each other; when a character addresses a group they look around at the listeners as they speak. Finds who each line is said to, and writes an eyeline per shot and an addressee per line into data/prompt.json (rendered as 'Eyeline: …' and '…, to Nim: {…}'). Use when checking or fixing eyelines, eye contact, who a character is talking to, or how characters face each other in a conversation."
argument-hint: "[clip id, scene, or character]"
---

# Eyeline Direction

Make every conversation read naturally: two people talking look at each other, and a character addressing several people looks around at them as they speak. The skill decides who each line is said to and where everyone looks, records it in `data/prompt.json`, and carries it into the prompts. Actions and dialogue text never change.

## References

| File | Use it for |
|---|---|
| [eyeline_rules.md](./references/eyeline_rules.md) | The eyeline rules, special cases (Nim's height, Jesus from behind, voice-over), how each line's listener is found, and how to review |
| [camera_language.md](../camera-knowledge/references/camera_language.md) | Over-the-shoulder and shot/reverse-shot coverage, and the 180° rule that eyelines should respect |

## Scripts

Run from the repository root.

| Script | When to run it |
|---|---|
| [scripts/add_eyelines.py](../../../scripts/add_eyelines.py) `--dry-run` | Preview every shot's eyeline and every line's listener |
| `python3 scripts/add_eyelines.py [--clip clip-02]` | Write `eyeline` on each shot and `addressee` on each line (backup saved), then rebuild prompts and `reports/camera_report.html` |
| `python3 scripts/add_eyelines.py --set "clip-47:1:1=Yonah\|'young one' is Yonah"` | Set a line's listener on review; kept on later runs and when `build_prompt_json.py` rebuilds |

## Workflow

1. Preview with `python3 scripts/add_eyelines.py --dry-run`.
2. Review the listeners against the screenplay: replies that skip a turn, lines called to a crowd, remarks to oneself, and anyone named only in a memory. Fix them with `--set` and say why.
3. Apply with `python3 scripts/add_eyelines.py` (it runs `add_continuity.py` and `check_camera.py`).
4. Confirm in `data/prompt.json` that shots with dialogue have an `Eyeline:` line, lines read `…, to <listener>: {…}`, voice-over lines have no listener, and Jesus is only ever "seen from behind".
5. Report the counts (two-person, group, several-speaker shots) and the lines you set by hand.

## Rules

- Two people talking always face and look at each other; a character addressing a group looks around at them, meeting their eyes in turn.
- Never change actions, dialogue words, speakers, or order; only add `eyeline` and `addressee` fields.
- Jesus's face is never shown: he turns toward people only as "seen from behind".
- Keep eyelines consistent with the scene's screen positions (180° rule); camera choices belong to `camera-knowledge`.
