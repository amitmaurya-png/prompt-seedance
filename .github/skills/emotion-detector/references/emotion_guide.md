# Emotion Guide

How the emotion of each dialogue line, and the mood of each conversation, is detected and used in this project's Seedance prompts.

## 1. Emotions and their delivery

The `delivery` word is written into the prompt before the line, e.g. `Nim (@Image 2), playfully: {Is it bread pretending not to be bread?}`.

| Emotion | Delivery | Typical cues |
|---|---|---|
| playful | playfully | Nim's dry jokes ("A gifted child. Dangerous.", "Numbers of beauty") |
| curious | curiously | Questions, "what happened", "how many", "I wonder" |
| earnest | earnestly | Plain, sincere statements (Miri's and Yonah's default) |
| warm | warmly | "little one", "small hands … open hands", "you tell me", "peace to you" |
| wise | thoughtfully | Saba's story lines and lessons: "perhaps", "some gifts", "sometimes that is" |
| reassuring | gently | "That is usually how giving works", "Nothing lost", "You were." |
| worried | anxiously | "not enough", "what if", "the day is fading", "afraid", "hungry" |
| reluctant | reluctantly | Pushing back: "Again?", "Tav had a cake yesterday", "You keep it" |
| hesitant | hesitantly | "Maybe", "…", "Do you think so?" |
| determined | firmly | "Wait.", "Because if I keep it, it stays small", "I need to find Tav" |
| regretful | regretfully | "should have", "I was afraid", "I told you not to" |
| disappointed | disappointedly | "Oh.", a hope let down |
| joyful | joyfully | "Thank you!", "It works!", "Blessed be the Lord" |
| excited | excitedly | Short exclamations: "Come on!", "Go!", "Miri!" |
| amazed | in wonder | "We are inside the story", "more baskets left", "more than enough" |
| calm | calmly | Jesus's lines, always |
| teasing | teasingly | Set on review: playing along or gently mocking ("No." in the guessing game) |
| eager | eagerly | Set on review: keen anticipation (Nim's guesses, Tav smelling the cakes) |
| proud | proudly | Set on review: owning something ("Ima made them for after chores.") |
| guilty | guiltily | Set on review: evasive or ashamed ("The linen.") |
| tender | tenderly | Set on review: soft, caring ("Were you afraid?") |
| hopeful | hopefully | Set on review: wishing ("Could I have one?", "For me?") |
| doubtful | doubtfully | Set on review: disbelief ("With five loaves?", "All of them?") |
| silent | silently, a held pause | A line that is only "…" |
| neutral | (none) | No cue at all |

**Intensity** (low / medium / high) comes from how many cues agree, and from repeated `!`.
**Conversation mood** on each shot is the strongest emotion across its lines (weighted by intensity).

## 2. How a line is scored

1. **Words:** cue phrases (weight 2) and word stems (weight 1) from the table above.
2. **Marks:** `!` (excited for short lines, joyful for longer), `?` (curious), `…` (hesitant).
3. **Speaker manner:** Nim playful, Saba wise, Ima and Andrew warm, Philip worried, Tav excited, Miri and Yonah earnest (weight 0.8).
4. **Shot mood:** from the shot's title and action, e.g. "hesitates" → hesitant, "beams" → joyful (weight 0.7).
The highest score wins; `emotion_evidence` lists what decided it.

## 3. Reviewing and overriding

- Read lines where the emotion seems off against the scene (the script reads words, not subtext).
- Override with `--set "clip:shot:line=<emotion>|<reason>"`, e.g. `--set "clip-01:1:2=teasing|plays along with Nim's game"`; the reason is stored in `emotion_evidence`. Manual emotions are kept on reruns (`emotion_source: "manual"`); a custom emotion name becomes its own delivery word.
- Use `--clear-manual` to return all lines to automatic detection.

## 4. Rules

- Never change a line's words, speaker, or order; only add `emotion`, `intensity`, `delivery`, `emotion_evidence`, `emotion_source`, and the shot's `conversation_mood`.
- Keep delivery words short and actable; Seedance reads them as voice and expression direction.
- Jesus is always calm; keep delivery gentle for children unless the script says otherwise.
