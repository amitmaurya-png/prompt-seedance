# Camera by Mood

How to choose a camera for a single shot from its **mood**, then adjust for the scene's **genre** ([camera_genres.md](./camera_genres.md)), who is speaking, and continuity.
`scripts/camera_suggest.py` applies these same tables automatically; this file explains them so the agent can reason about a shot, and override the script, with good reasons.

## 1. Detect the mood

Read the shot's title, action, visual note, and dialogue, and ask what the audience should feel. Signal words (the script looks for these):

| Mood | Signals in the shot |
|---|---|
| **Wonder / awe** | wonder, amazed, endless, transforms, glow, miracle, bless, thousands, gasp, "inside the story" |
| **Fear / vulnerability** | afraid, fear, nervous, worried, trembling, panic, danger, tears |
| **Tension / hesitation** | hesitates, freezes, pauses, silence, "says nothing", guards, shields, imagines, doubt |
| **Courage / resolve** | stands, rises, brave, offers, "holds out", decides, "step forward" |
| **Intimacy / comfort** | kneels, gently, warm, comfort, softly, quiet, "sits beside", "rests a hand" |
| **Joy / celebration** | beams, laughs, smiles, cheers, "thank you", waves, "lights up", exclamations |
| **Comedy** | sly, grave, importantly, innocently, whiskers, bargains, "pats his own belly", Nim speaking |
| **Sadness / regret** | disappointed, regret, guilt, sighs, exhales, "looks down", "should have" |
| **Curiosity / discovery** | peeks, asks, question, sniffs, inspects, scans, spots, counting |
| **Reveal / realisation** | realises, remembers, understands, notices, unwraps, unties, "more baskets" |
| **Energy / movement** | runs, hurries, rushes, trots, chases, darts, bounds, leaps |
| **Conversation** (no stronger mood) | dialogue with no other signals |

When two moods appear, use the strongest one for the camera and let the second shape the performance (e.g. *courage* over *tension*: "hesitates, then stands and offers").

## 2. Camera defaults per mood

| Mood | Shot size | Angle | Movement (one) | Focus | Why |
|---|---|---|---|---|---|
| Wonder | Wide shot | Low angle (aerial for huge crowds) | Slow crane up | Deep | Scale; the moment feels larger than the characters |
| Fear | Close-up | High angle* | Slow push-in | Shallow | Isolates the worry |
| Tension | Medium close-up | Eye level | Static | Shallow | A held, still frame lets the pause play |
| Courage | Medium close-up | Low angle | Slow push-in | Shallow | A small character's decision feels big |
| Intimacy | Medium close-up | Eye level | Static | Shallow | Close and personal |
| Joy | Medium shot | Eye level | Gentle tracking | Deep | Shares the energy, everyone visible |
| Comedy | Medium shot | Eye level | Static | Deep | Timing and body language carry the joke |
| Sadness | Close-up | Eye level | Static | Shallow | Room for the feeling without pushing it |
| Curiosity | Medium close-up | Eye level | Slow push-in | Shallow | Follows the character's attention |
| Reveal | Close-up | Eye level | Slow pull-back | Deep | Starting close and widening reveals the meaning |
| Energy | Medium long shot | Eye level | Tracking | Deep | Keeps up with movement, shows the whole body |
| Conversation | Medium shot / two-shot | Eye level | Static | Shallow | Steady coverage, speakers together |

\* High angles become eye level when the shot is about a child (see section 3).

## 3. Adjust for genre, speakers, and continuity

Apply in this order:

1. **Coverage:** two characters talking → two-shot (or over-the-shoulder for tension, sadness, courage), at least medium close-up. Three or more → three-shot at medium.
2. **Genre:**
   - *Storybook:* avoid extreme close-ups, dolly zooms, and fast zooms.
   - *Epic/biblical:* when nobody on screen is talking, wonder, joy, and crowd moments open to a wide shot; "thousands" → aerial.
   - *Title card:* slow push-in on the card.
3. **Talking characters:** if someone on screen is speaking, don't go wider than a medium shot (medium long shot when the crowd matters), so faces stay readable.
4. **Children:** never frame Miri, Tav, Yonah, or Nim from a high angle that makes them look small and powerless; use eye level. Nim is small: meet him with a low camera at his height.
5. **Continuity:** the first shot of a new scene opens wide.
6. **Sacred figure:** if Jesus is in the shot, frame from behind him (over the shoulder or silhouette); never his face.
7. Off-screen narration (voice only) does not change the framing.

## 4. Write the result

`<shot size>[, <angle>][, <one movement>] [on <character>]`, e.g. `Medium close-up, low angle, slow push-in on Yonah`.
Then compare with the existing line: shot sizes three or more steps apart, opposite angles (low vs high), or a genre-avoided move mean it "differs"; review those shots first.
