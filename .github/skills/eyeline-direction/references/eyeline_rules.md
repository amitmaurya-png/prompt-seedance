# Eyeline Rules

Where characters look while they talk, so conversations read naturally on screen.

## 1. The rules

| Situation | Direction written into the shot |
|---|---|
| **Two people talking** | They turn toward each other and hold eye contact: "Miri and Ima turn toward each other and hold eye contact as they talk: Miri looks at Ima, Ima looks at Miri". Anyone else present watches them |
| **One character speaking to one other** | "Tav and Miri face each other; Tav looks at Miri while speaking, and Miri looks at Tav" |
| **A character addressing a group** (two or more listeners, or a crowd, the children, the disciples) | They look around at the listeners while speaking, meeting their eyes one by one, and the listeners look back: "Saba looks around at the children while speaking, meeting their eyes one by one; the children look back at Saba" |
| **Three or more characters trading lines** | "Each speaker looks at the person they are answering, and the others turn to whoever is speaking" |

Each dialogue line also names its listener, which is written into the prompt as `Miri (@Image 1), earnestly, to Nim: {…}`.

## 2. Special cases

- **Nim is small:** humans look down at him and he looks up at them ("Nim looks up at Miri").
- **Jesus is only framed from behind:** "Jesus, seen only from behind, turns toward Philip"; he is never a passive watcher, and is an addressee only when named or turned toward.
- **Voice-over** (Saba's narration) has no eyeline or listener.
- A name inside a memory ("She remembers Tav's hopeful face") doesn't put that character in the shot.

## 3. How the listener of each line is found

In this order:
1. Set on review (`--set`), kept on reruns.
2. A present character named in the line ("Miri, take these…", "Yonah.").
3. A character the speaker moves or speaks toward in the action ("steps toward Andrew").
4. The only other character present.
5. Whoever spoke last, in this shot, the previous shot, or the previous clip of the same scene (a reply).
6. A group the speaker addresses ("calls to the crowd", "surrounded by several village children"), or everyone present.

## 4. Reviewing

The rules read the words, not the staging. Check lines where the listener is ambiguous (a reply that skips a turn, a remark to oneself, a line called to a crowd) and set them with `--set "clip:shot:line=<listener>|<reason>"`, e.g. `--set "clip-47:1:1=Yonah|'young one' is Yonah"`.
