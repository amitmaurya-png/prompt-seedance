# Continuity Rules

What "continuous" means for this project's Seedance clips, how each kind of continuity is carried in `data/prompt.json`, and how to fix a break.
Each Seedance generation is independent, so continuity only exists if every clip repeats the same facts and the next clip starts from where the last one ended.

## 1. Scenes and chains

- A **scene** is one clip that opens it (`continuity.mode: "new_scene"`) plus the clips that continue it (`"continue_scene"`).
- Clips continue when they share the act and scene heading, or when listed in `CONTINUES_ACROSS_HEADING` in `scripts/add_continuity.py` (e.g. clip-45: the heading changes but the script says CONTINUOUS on the same hillside).
- A scene opener is a deliberate cut: no previous last frame, music "begins".

## 2. Kinds of continuity

| Kind | What must stay the same | Where it lives | How it's checked |
|---|---|---|---|
| **Chain** | Each continuing clip starts from the previous clip's last frame | `REFERENCES` "@Image N: last frame of clip-XX", Shot 1 "Continuity: Continue the same moment from @Image N…", rule "Match lighting, positions, props…" | `check_continuity.py` (chain) |
| **Scene state** | Time of day, light direction, props, screen positions | `CONTINUITY:` block, identical in every clip with the same heading (`CONTINUITY` dict in `add_continuity.py`) | `check_continuity.py` (state, time of day) |
| **Handoff** | A clip opens where the previous one ended (still walking → keeps walking or slows) | First shot's action | `check_continuity.py` (handoff); fix with `HANDOFF_FIXES` |
| **Characters** | Same look and image slot in every clip; nobody vanishes mid-scene | `SUBJECT` "Define … in @Image N as Name", fixed `ORDER` | `check_continuity.py` (characters) |
| **Screen direction** | Each character stays on the same side of frame within a scene (180° rule) | Screen positions in the `CONTINUITY` block | `check_continuity.py` (positions) |
| **Sound** | Same voice per character; music "begins" then "continues"; same ambience per location | `AUDIO` (`VOICE` dict) | `check_continuity.py` (music, voices) |
| **Dialogue** | Every line once, in script order, word for word | `Dialogue:` lines | `check_continuity.py` (dialogue vs `data/breakdown.json`) |
| **Camera** | Shot sizes step gradually; new scenes open wide | `Camera:` lines | `check_camera.py` (camera-knowledge skill) |
| **Props over time** | Story state carried between scenes: three cakes → hidden in the basket → one given to Tav; Tav's wheel off → fixed in Act Four; lunch bundle → twelve baskets | `CONTINUITY` blocks of consecutive scenes | Manual review: read the blocks in story order |

## 3. Fixing a break

| Issue from the checker | Fix |
|---|---|
| Missing last-frame reference, handoff line, or match rule | Run `python3 scripts/add_continuity.py` (it rebuilds all three) |
| Wrong chain (`previous_clip`), or a clip that should/shouldn't continue | Check the scene heading in `data/prompt.json`; add or remove the clip id in `CONTINUES_ACROSS_HEADING`, then rerun `add_continuity.py` |
| CONTINUITY block differs or is missing | Edit the scene's entry in the `CONTINUITY` dict, then rerun `add_continuity.py` |
| Time of day doesn't match the heading | Mention the time in that scene's `CONTINUITY` entry |
| Clip ends moving but the next opens settled (or the reverse) | Add the next clip to `HANDOFF_FIXES` with an opening that bridges the two (e.g. "Still walking, Miri slows and sits"), then rerun |
| Character in the last shot has no image in the next clip | If they should stay, add `"Define <description> in @Image 1 as <Name>"` to that clip's `subjects` (use the same description as other clips), then rerun `add_continuity.py` (it renumbers images); otherwise show them leaving in the previous clip's last shot. Keep 4 characters or fewer per clip |
| Character defined or voiced differently across clips | Make the `subjects` description and the `VOICE` entry identical everywhere |
| Screen position contradicts the scene | Change the shot's wording, or the scene's positions in `CONTINUITY`, so they agree |
| Dialogue differs from the breakdown | Restore the exact line; never paraphrase dialogue |
| Big jump in shot size, scene opens close | Use the camera-knowledge skill |

## 4. Review checklist (per scene)

- [ ] Opener has no last-frame reference; every following clip has one, plus the handoff line and match rule
- [ ] Same CONTINUITY block in every clip with the same heading, and it names the time of day
- [ ] Each clip opens where the previous one ended
- [ ] Everyone visible at the end of a clip is still referenced (or leaves on screen)
- [ ] Characters keep their frame side; voices and definitions identical
- [ ] Music begins once, then continues
- [ ] Dialogue in order, word for word
- [ ] Props match the story so far (cakes, basket, wheel, lunch, baskets, scroll)
