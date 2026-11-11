# Camera Language Reference

Standard film terms for shot size, angle, framing, movement, and focus, with notes on writing them into Seedance prompts.
For which choices suit which genre, see [camera_genres.md](./camera_genres.md).
Seedance understands standard camera terminology well (see [seedance_2_0_prompt_guide.md](../../seedance-prompting/references/seedance_2_0_prompt_guide.md) §2.4), so use these exact terms in each shot's `Camera:` line.

Three separate ideas make up a shot's camera direction. Keep them apart when writing and reviewing:

- **Shot size**: how much of the subject is in frame (how tight or loose the framing is).
- **Camera angle**: where the camera is and which way it faces, relative to the subject.
- **Camera movement**: how the camera or framing changes during the shot (pan, tilt, dolly, truck, zoom…).

Example: "A low-angle full shot of a warrior, the camera slowly dollying in as he draws a sword": *low angle* is the angle, *full shot* the size, *dollying in* the movement.

## How to use these terms in a Seedance shot

A shot's `Camera:` line combines up to three parts:

```
Camera: <shot size> [, <angle>] [, <one movement>]
e.g.    Medium close-up, low angle, slow push-in
        Wide shot, eye level, static
        Over-the-shoulder two-shot, slow lateral tracking
```

- **Movement:** use only one camera movement per shot (Seedance rule). Shot size, angle, and focus are framing choices, not movements, so you can combine them freely.
- **Static is a valid choice.** If a shot has no movement, write `static` or `fixed camera`.
- **One clear angle.** Name a single angle per shot; don't stack contradictory ones ("low angle, overhead").
- **Order of shot sizes:** within a scene, step through them, e.g. establishing/wide → medium → medium close-up → close-up. Jumping from an extreme close-up straight to a wide shot of the same moment reads as a jump cut.
- **Dialogue:** cover it with a two-shot, over-the-shoulder shots, or shot/reverse shot, and keep the 180° rule. Each character stays on the same side of the frame in every shot and every clip of the scene (see the `CONTINUITY` screen positions in `data/prompt.json`).
- **New scenes:** open them with an establishing or wide shot before cutting in closer.
- **Keep camera and action consistent.** The movement should follow what the subject does (track a walker, push in on a realisation). For continuity, give the character's screen position and direction of movement when it matters.
- **AI tools read terms loosely.** Use the standard term, keep the line short, and avoid contradictions between `Camera:`, the action, and `CONSTRAINTS`.

Shot sizes aren't exact measurements: framing varies with the subject, lens, aspect ratio, and convention. Treat the "Frames" column below as typical, not strict.

---

## 1. Shot sizes (how much of the subject is in frame)

| Shot | Abbr. | Frames | Use it for | Example |
|---|---|---|---|---|
| Extreme wide shot | EWS | The environment dominates; the subject is tiny or distant | Location, scale, distance, isolation; epic landscapes | A lone traveller crossing a vast desert |
| Establishing shot | EST | The whole location | Opening a sequence so the audience knows where they are; usually a wide or extreme wide shot | *Harry Potter and the Prisoner of Azkaban* (2004) |
| Wide shot | WS | The subject plus its surroundings | Showing the environment; can work as an establishing shot | *Deathly Hallows Part 2* (2011) |
| Long shot | LS | The full body, seen from a distance | Sense of space; placing action in a location; the subject's relationship to the setting | A person entering a large house |
| Full shot | FS | Head to toe, the body filling the frame height | Posture, costume, body language, physical action, entrances | A dancer performing a full movement |
| Medium long shot (three-quarter) | MLS | Knees to head, with some background | Gestures and movement balanced with facial expression | A police officer approaching a suspect |
| Medium shot | MS | Waist up, with some background | Conversation, gestures, everyday action | Two friends talking at a café |
| Medium close-up | MCU | Chest or shoulders up | Dialogue and expressions while keeping some body language | A character explaining a difficult decision |
| Close-up | CU | A face, an object, or a detail of the action | Emotion, reaction, intimacy; important props | A character realising they've been betrayed |
| Big close-up | BCU | Forehead to chin | Strong emotion | *Deathly Hallows Part 1* (2010) |
| Extreme close-up | ECU | One small feature (eyes, lips, fingertips, an object detail) | Intensity, suspense, intimacy; story-critical details, texture | A finger slowly pressing a button |

`check_camera.py` counts a full shot as a long shot and reads "extreme wide shot" as a wide shot; both still rank correctly for size jumps.

## 2. Camera angles (where the camera looks from)

| Angle | Abbr. | What it is | Typical feeling | Common uses |
|---|---|---|---|---|
| Eye-level shot | EL | Camera at about the subject's eye height | Neutral, natural, relatable, balanced | Dialogue, interviews, everyday scenes, character introductions |
| High-angle shot | HA | Looks down on the subject from above eye level | Vulnerable, small, isolated, overwhelmed (depends on context) | Defeated characters, emotional moments, a person within a large space |
| Low-angle shot ("up shot") | LA | Below the subject, pointing up | Powerful, dominant, heroic, imposing, threatening | Hero entrances, villains, leaders, moments of authority |
| Worm's-eye view | — | Extremely low, near the ground, pointing up | Monumental scale, awe, surreal drama | Tall buildings, towering creatures, dramatic entrances, fantasy and sci-fi |
| Overhead / bird's-eye view | OH | Almost straight down from directly above | Detached, graphic, spatially clear | Crowds, choreography, layouts, patterns, symmetrical compositions |
| Aerial shot | — | From high in the air (often drone-style); can be directly overhead | Scale, sweep, grandeur | Reveals of landscapes and crowds |
| Dutch / canted angle | — | Camera rolled sideways so the horizon is diagonal | Unsettling, unstable, confused, tense | Psychological thrillers, horror, disorientation, chaos |

- **"Up shot"** is an informal name for a low-angle shot; write `low angle` in prompts, which is clearer. The reverse is a high-angle shot.
- The same character reads as heroic from a low angle, vulnerable from a high angle, and intimate in a close-up: choose the angle for the feeling you want.
- `check_camera.py` doesn't recognise *worm's-eye* or *Dutch angle* yet (they get no term match in the report). Seedance understands both.

## 3. Framing, coverage, and special-purpose shots

These are named by purpose, point of view, or how subjects are arranged, not only by how much of a person is visible.

| Technique | Abbr. | Description | Common uses |
|---|---|---|---|
| Two-shot | 2S | Two subjects in frame, usually at medium-shot distance | Interaction, closeness, tension, conflict |
| Three-shot | 3S | Three subjects in frame | Small-group dialogue |
| Over-the-shoulder shot | OTS | Past one character's shoulder (in the foreground) toward another | The standard dialogue shot; confrontations, interviews, reactions; establishes perspective and relationships |
| Shot / reverse shot | — | Alternating opposite OTS shots in a conversation | Dialogue coverage |
| 180° rule | — | An imaginary line between characters that the camera must not cross, so screen positions stay consistent and the audience stays oriented | Every dialogue scene |
| Point-of-view shot | POV | What a character sees, through their eyes | Immersion, discovery, suspense, subjective moments |
| Insert shot | — | Isolates a story-relevant detail: a letter, key, phone screen, hand | Clues, continuity, emphasis, plot details |
| Cutaway | — | Briefly leaves the main action for a related detail or reaction (a clock ticking during an argument) | Pacing, context, comedy beats |
| Reaction shot | — | A character's response to something said or seen | Emotional storytelling, dialogue editing, comedy, suspense |
| Profile shot | — | The subject seen from the side | Contemplation, conversation, silhouettes, portraits |
| Three-quarter angle | — | The face between straight-on and full profile | Flattering portraits, character introductions, standard coverage |
| Rear angle / back shot | — | The subject seen from behind | Mystery, walking away, following a character, reveals |
| Reflection shot | — | The subject seen in a mirror, glass, water, or another reflective surface | Identity, mystery, duality, layered compositions |
| Silhouette shot | — | The subject as a dark shape against a brighter background | Mystery, romance, dramatic entrances, graphic compositions |

**Writing an OTS line:** say whose shoulder and who the camera looks at, e.g. `Medium close-up, over Miri's shoulder onto Saba, static`. A bare "over-the-shoulder shot" leaves Seedance to guess who is in the foreground.

**For this project:** rear angle, silhouette, and OTS-from-behind framing are the tools for the rule that Jesus is shown only from behind, as hands and robe, or in silhouette. Dutch angles and worm's-eye views clash with the family storybook tone; use them only for a deliberate moment and say why.

`check_camera.py` recognises two-shot, three-shot, OTS, shot/reverse shot, POV, and insert (cutaways count as inserts). It doesn't yet recognise reaction, profile, three-quarter, rear, reflection, or silhouette shots.

## 4. Camera movement (use one per shot)

| Movement | What happens | Prompt wording |
|---|---|---|
| Static | The camera does not move; the scene plays out in front of it | `static`, `fixed camera` |
| Pan | The camera stays in place and turns left or right | `slow pan left`, `pan right to follow` |
| Tilt | The camera stays in place and pivots up or down | `slow tilt up`, `tilt down` |
| Tracking / dolly / truck | The camera itself travels, often beside or with the subject | `lateral tracking`, `tracking alongside`, `following shot` |
| Push-in / pull-back | The camera travels toward or away from the subject | `slow push-in`, `slow pull back` |
| Crane / arc | The camera rises, lowers, or circles the subject | `crane down`, `slow arc around` |
| Zoom in / out | The lens magnifies or widens while the camera stays put; flatter than a push-in | `slow zoom in` |
| Dolly zoom | The camera moves while the lens zooms the opposite way, so the subject stays the same size and the background warps | `dolly zoom` (use sparingly) |

Seedance's official guide warns against combining pushes, pulls, pans, and moves in one shot because it makes the image unstable. If you need a second move, split it into a second shot.

## 5. Focus

| Technique | Description | Prompt wording |
|---|---|---|
| Shallow focus / foreground focus | The subject is sharp and the background is soft | `shallow depth of field`, `background softly blurred` |
| Deep focus | Foreground and background are both sharp (popularised by Orson Welles) | `deep focus, everything sharp` |
| Rack focus | Focus shifts from one subject to another during the shot | `rack focus from Nim to Miri` |

---

## 6. Choosing a shot by storytelling goal

| Goal | Shot choice |
|---|---|
| Establish a place | Extreme wide shot or establishing shot |
| Show body movement | Full shot or long shot |
| Show dialogue and gestures | Medium shot or medium close-up; OTS or two-shot for exchanges |
| Reveal emotion | Close-up; reaction shot |
| Highlight a clue or tiny detail | Insert shot or extreme close-up |
| Make a subject seem powerful | Low-angle shot (worm's-eye for extreme scale) |
| Suggest vulnerability or smallness | High-angle shot, depending on context |
| Reveal patterns or positions | Overhead / bird's-eye view |
| Create unease | Dutch angle |
| Show a character's perspective | Point-of-view shot |
| Keep a figure mysterious | Rear angle or silhouette |

### Example sequence: building suspense

A character discovers a mysterious letter. Each shot moves the audience from the setting to the emotion to the clue:

1. **Wide shot**: the room, and the character entering.
2. **Medium shot**: the character notices an envelope on a desk.
3. **Close-up**: their worried reaction.
4. **Insert / extreme close-up**: a revealing detail on the letter.
5. **Low-angle shot**: a looming figure, or a subject made to feel imposing.

### Wording examples for AI video prompts

Phrasings from AI-video prompt guides. In this project's prompts, the camera part goes in `Camera:` and the rest belongs in `Action:`, `SCENE`, and `STYLE`.

| Shot | Example wording |
|---|---|
| Eye level | Eye-level medium shot of a woman speaking naturally in a softly lit room |
| Low angle | Dramatic low-angle full shot of a warrior standing tall in the rain, powerful posture |
| High angle | High-angle shot looking down at a lonely person on a bench in a vast empty hall |
| Bird's-eye | Bird's-eye view of a lone person crossing a geometric plaza, symmetrical composition |
| Worm's-eye | Extreme worm's-eye view of a skyscraper rising into storm clouds, imposing scale |
| Dutch angle | Dutch-angle shot of a detective in a dim corridor, tilted horizon, deep shadows |
| OTS | Over-the-shoulder shot from behind a woman toward a man across a table, shallow depth of field |
| POV | First-person POV as a character slowly opens a creaking door, subtle handheld movement |
| Profile | Side-profile close-up of a thoughtful woman beside a window, soft daylight |
| Rear angle | Rear wide shot of a traveller walking toward a misty mountain range |
| Silhouette | A lone figure silhouetted against a golden sunset, wide shot, atmospheric haze |

---

## Placing the main character (the `Placement:` line)

Every shot names its **main character** and where they sit in the frame, on a `Placement:` line directly under
`Camera:`. The camera line says how the shot is taken; the placement line says where the person the shot is about
stands in it. `scripts/add_placement.py` writes it for every shot.

```
Camera: Medium close-up, static on Saba
Placement: Saba is the main subject, on the left third of the frame, facing right, with open space on the right
```

**Who is the main character** (first that applies):
1. The person the camera is aimed at: `on Saba`, `onto Miri`, `tracking with Miri`, `toward the small girl`, `from behind Miri`.
   In an over-the-shoulder shot it is the person facing the camera, never the shoulder's owner.
2. In a wide shot, Miri when she is in the action (she is the heroine the audience follows).
3. The first speaker in the shot, then the first character named in the action, then Miri.

**Where they go.** Use the scene's fixed screen positions (`SCENE_POSITIONS` in `scripts/add_placement.py`, the same
sides as the `CONTINUITY` notes), so each character stays on one side for the whole scene (180° rule). Place people
on the **rule-of-thirds** lines, not dead centre, unless they are alone with no one placed opposite.

| Shot | Placement |
|---|---|
| Single (CU, MCU on one person) | Main on their side's third, **facing the other side**, with open space (lead room) on the side they look toward |
| Over-the-shoulder onto X | X in focus on their third, facing the other way; the other person's shoulder soft in the opposite foreground |
| Two-/three-shot, medium | Main on their third; the others on theirs, or "beside" the person they stand with |
| Wide / establishing | Main on their third, small but clear against the setting; the others in their places |
| Tracking a walk | Main moving in the scene's travel direction (e.g. left to right) with open space ahead |
| Nim | Low in the frame, at the characters' feet, on the side of the person he is with |
| Jesus | Only from behind, as hands, robe or silhouette, centre-right |

Keep `Placement:` consistent with `Eyeline:`: a character on the left third looks right toward someone on the right.
To fix one shot by hand, set its `placement` to `{"main": ..., "line": ..., "source": "manual"}`; the script keeps it.

---

## Quick checklist for a shot's Camera line

- [ ] One shot size is named
- [ ] One angle is named if it matters (default is eye level)
- [ ] At most one movement, or `static`
- [ ] The camera direction matches what the subject does
- [ ] OTS lines say whose shoulder and who the camera looks at
- [ ] The shot size steps sensibly from the previous shot
- [ ] Dialogue shots keep each character on their established side (180° rule)
- [ ] A `Placement:` line names the main character and their third of the frame, matching the scene's screen positions
- [ ] The first shot of a new scene is establishing or wide
- [ ] The camera choices fit the scene's genre and mood (see [camera_genres.md](./camera_genres.md) and [camera_moods.md](./camera_moods.md)), or break them on purpose

For storyboarding a shot, also record its number and scene, what the subject does, the dialogue or sound, and the intended audience response.

_Sources: "Intro to Film Technique and Terminology" (classroom notes with Harry Potter film examples); "Camera Shot Types & Angles: A practical guide to framing, perspective, and visual storytelling"; "Camera Angles: A Practical Guide for Filmmaking & AI Video Generation". Tidied and adapted for Seedance prompting._
