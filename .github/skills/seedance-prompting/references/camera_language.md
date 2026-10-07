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
- **Dialogue:** cover it with a two-shot, over-the-shoulder shots, or shot/reverse shot, and keep the 180° rule. Each character stays on the same side of the frame in every shot and every clip of the scene (see the `CONTINUITY` screen positions in `data/prompt.json`).
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

## 6. Camera language by genre

Genres have conventions, not hard rules. Use this table to pick defaults that fit the genre, and break them on purpose when a moment needs it (a sudden low angle in a gentle drama lands because it is rare). Term names match sections 1-5.

| Genre | Typical shot sizes | Typical angles | Typical movement | Focus / framing | Use sparingly or avoid |
|---|---|---|---|---|---|
| **Family / children's storybook** (this project) | Wide and establishing shots for each new place; medium and two-shots for conversation; close-ups for feelings and key props | Eye level at the child's height; low angle for small characters (Nim, Miri) and for wonder | Slow push-in, gentle tracking, static | Shallow focus on faces; two-shot and three-shot to keep friends together | Fast cuts, dolly zoom, extreme close-ups of faces (can scare young viewers), high angles that make children look small and powerless unless the story intends it |
| **Drama** | Medium shot, medium close-up, close-up | Eye level | Static, slow push-in at emotional turns | Over-the-shoulder, shot/reverse shot; shallow focus | Busy movement that pulls focus from performance |
| **Romance** | Medium close-up, close-up, two-shot | Eye level, slightly low for a hero moment | Slow arc, slow push-in | Shallow focus, soft backgrounds; two-shot to show closeness | Wide shots during intimate dialogue; harsh high angles |
| **Comedy** | Medium and medium long shots so physical action reads; two-shot and three-shot | Eye level | Mostly static; quick pan or zoom for a punchline | Deep focus so background gags stay visible | Tight close-ups that hide the joke's physical setup |
| **Action / adventure** | Wide shots for geography; medium for the fight; close-ups for impact | Low angle for the hero; high angle for danger | Tracking, crane, aerial; fast pans | Deep focus for clarity of space | So many moves that geography gets lost; break into one move per shot for Seedance |
| **Horror / thriller** | Close-up and extreme close-up; long shots that isolate a character | High angle (vulnerable), low angle (threat), overhead | Slow push-in, slow tracking, static held too long; dolly zoom for shock | Shallow focus with blurred background threats; point-of-view shot | Bright eye-level coverage that drains tension |
| **Mystery / noir** | Medium close-up, close-up, insert shots of clues | Low angle, tilted framing | Slow push-in, slow pan | Deep shadows; insert shot on objects; rack focus to reveal clues | Flat, evenly lit wide coverage |
| **Epic / fantasy / biblical** | Establishing, wide and long shots for scale and crowds; close-ups for faith and emotion | Low angle for awe; aerial and high angle for crowds | Crane, aerial, slow arc, slow pull-back reveals | Deep focus for landscapes; silhouette and backlight for sacred figures | Constant tight framing that hides the scale |
| **Documentary / realism** | Medium and medium close-up | Eye level | Handheld-style tracking, static interviews | Natural focus; over-the-shoulder for observation | Stylised angles and dolly zooms that feel staged |
| **Music video / dance** | Full range, with frequent changes | Low angle, overhead | Tracking, arc, crane, whip pans | Beat-matched cuts; rack focus | Long static holds (unless the style calls for it) |
| **Commercial / product** | Close-up, extreme close-up, insert shots of the product | Eye level, slight high angle for packshots | Slow push-in, arc around the product, slow dolly | Shallow focus on the product; clean backgrounds | Busy backgrounds; movement that hides the product |
| **Sports** | Wide for play, medium and close-up for athletes | Low angle for power; aerial for the field | Tracking, fast pan | Deep focus for play; shallow for reactions | Shots that lose the ball or the score |

### Applying it in a Seedance prompt

- Name the genre in `STYLE`, then let the `Camera:` lines follow its defaults (e.g. "Warm, painterly 2D storybook animation" -> eye level at child height, gentle moves).
- Keep the Seedance rules on top of any genre: one movement per shot, open new scenes wide, keep the 180° rule.
- Mixed genres: pick the dominant genre for each scene. In this project, the village and scroll-room scenes follow family storybook conventions, while the Galilean hillside scenes borrow epic/biblical conventions (wide crowds, aerial reveals, Jesus shown only from behind or in silhouette).
- To check a prompt against a genre, compare its camera terms with the "Typical" columns and look for anything in "Use sparingly or avoid" (`scripts/check_camera.py` lists the terms used in every shot).

---

## Quick checklist for a shot's Camera line

- [ ] One shot size is named
- [ ] An angle is named if it matters (default is eye level)
- [ ] At most one movement, or `static`
- [ ] The shot size steps sensibly from the previous shot
- [ ] Dialogue shots keep each character on their established side (180° rule)
- [ ] The first shot of a new scene is establishing or wide
- [ ] The camera choices fit the scene's genre (section 6), or break it on purpose

_Source: "Intro to Film Technique and Terminology" (classroom notes with Harry Potter film examples), tidied and adapted for Seedance prompting._
