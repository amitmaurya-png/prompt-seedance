# Camera Language by Genre

Genres have conventions, not hard rules. Use this table to pick defaults that fit the genre, and break them on purpose when a moment needs it (a sudden low angle in a gentle drama lands because it is rare). Term names match [camera_language.md](./camera_language.md).

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

## Applying it in a Seedance prompt

- Name the genre in `STYLE`, then let the `Camera:` lines follow its defaults (e.g. "Warm, painterly 2D storybook animation" -> eye level at child height, gentle moves).
- Keep the Seedance rules on top of any genre: one movement per shot, open new scenes wide, keep the 180° rule.
- Mixed genres: pick the dominant genre for each scene. In this project, the village and scroll-room scenes follow family storybook conventions, while the Galilean hillside scenes borrow epic/biblical conventions (wide crowds, aerial reveals, Jesus shown only from behind or in silhouette).
- To check a prompt against a genre, compare its camera terms with the "Typical" columns and look for anything in "Use sparingly or avoid" (`scripts/check_camera.py` lists the terms used in every shot).
