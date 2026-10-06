# Camera Language Reference

Standard film terms for shot size, angle, framing, movement, and focus, with notes on writing them into Seedance prompts.
Seedance understands standard camera terminology well (see `seedance_2_0_prompt_guide.md` §2.4), so use these exact terms in each shot's `Camera:` line.

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
- **Order of shot sizes:** within a scene, step through them, e.g. establishing/wide → medium → medium close-up → close-up. Jumping from an extreme close-up straight to a wide shot of the same moment reads as a jump cut.
- **Dialogue:** cover it with a two-shot, over-the-shoulder shots, or shot/reverse shot, and keep the 180° rule. Each character stays on the same side of the frame in every shot and every clip of the scene (see the `CONTINUITY` screen positions in `prompt.json`).
- **New scenes:** open them with an establishing or wide shot before cutting in closer.

---

## 1. Shot sizes (how much of the subject is in frame)

| Shot | Abbr. | Frames | Use it for | Film example |
|---|---|---|---|---|
| Establishing shot | EST | The whole location | Opening a sequence so the audience knows where they are; usually a long or wide shot | *Harry Potter and the Prisoner of Azkaban* (2004) |
| Wide shot | WS | The subject plus its surroundings | Showing the environment; can work as an establishing shot | *Deathly Hallows Part 2* (2011) |
| Long shot | LS | The full body, seen from a distance | Sense of space; placing action in a location | *Deathly Hallows Part 2* (2011) |
| Medium long shot | MLS | Knees to head, with some background | Movement and body language with context | *Order of the Phoenix* (2007) |
| Medium shot | MS | Waist up, with some background | Conversation and everyday action | *Order of the Phoenix* (2007) |
| Medium close-up | MCU | Head and shoulders | Dialogue and reactions | *Deathly Hallows Part 2* (2011) |
| Close-up | CU | A face, an object, or a detail of the action | Emotion; important props | *Deathly Hallows Part 2* (2011) |
| Big close-up | BCU | Forehead to chin | Strong emotion | *Deathly Hallows Part 1* (2010) |
| Extreme close-up | ECU | One small feature (eyes, hands, an object detail) | Emphasis; story-critical details | *Deathly Hallows Part 2* (2011) |

## 2. Camera angles (where the camera looks from)

| Angle | Abbr. | Effect | Film example |
|---|---|---|---|
| Eye-level shot | EL | Neutral; the camera is level with the subject's eye line | *Deathly Hallows Part 2* |
| High-angle shot | HA | Looks down on the subject, making it seem small or vulnerable | *Deathly Hallows Part 2* |
| Low-angle shot | LA | Looks up at the subject, making it seem dominant or powerful | *Matilda* (1996) |
| Overhead shot | OH | Directly above the subject, looking straight down | *Order of the Phoenix* (2007) |
| Aerial shot | — | From high in the air (often drone-style); can be directly overhead | *Deathly Hallows Part 1* (2010) |

## 3. Framing and dialogue coverage

| Technique | Abbr. | Description |
|---|---|---|
| Two-shot | 2S | Two subjects in frame, usually at medium-shot distance |
| Over-the-shoulder shot | OTS | Framed over one character's shoulder toward another; the standard dialogue shot |
| Shot / reverse shot | — | Alternating opposite OTS shots in a conversation |
| 180° rule | — | An imaginary line between characters that the camera must not cross, so screen positions stay consistent and the audience stays oriented |

## 4. Camera movement (use one per shot)

| Movement | What happens | Prompt wording |
|---|---|---|
| Static | The camera does not move; the scene plays out in front of it | `static`, `fixed camera` |
| Pan | The camera stays in place and turns left or right | `slow pan left`, `pan right to follow` |
| Tilt | The camera stays in place and pivots up or down | `slow tilt up`, `tilt down` |
| Tracking / dolly | The camera itself travels, often beside or with the subject | `lateral tracking`, `tracking alongside`, `following shot` |
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

## Quick checklist for a shot's Camera line

- [ ] One shot size is named
- [ ] An angle is named if it matters (default is eye level)
- [ ] At most one movement, or `static`
- [ ] The shot size steps sensibly from the previous shot
- [ ] Dialogue shots keep each character on their established side (180° rule)
- [ ] The first shot of a new scene is establishing or wide

_Source: "Intro to Film Technique and Terminology" (classroom notes with Harry Potter film examples), tidied and adapted for Seedance prompting._
