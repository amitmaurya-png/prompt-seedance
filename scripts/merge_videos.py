#!/usr/bin/env python3
"""Merge every video in a folder (default Videos/) in order, choosing each cut by MAD.

At every cut the last frame of one clip and the first frame of the next are compared at 64x36: MAD is the
mean absolute difference of their R, G, B values (0 = identical, 255 = black against white).
  MAD > 20   hard cut (a change of camera angle or scene: interpolating across it would warp the picture)
  otherwise  interpolate: --frames new frames (default 6, 0.25 s at 24 fps) morph from the one frame into
             the other, made by RIFE (a deep-learning frame interpolation model, run by rife-ncnn-vulkan
             on the GPU) or with --interpolator minterpolate by ffmpeg's motion interpolation
A bridge takes the place of the same length of the first clip's ending (clips end on a held frame), so the
merged video is as long as the clips added together and every clip's sound plays whole and in sync.

Color balance (on unless --no-balance): every clip is brought to one look, the average brightness, color, and
contrast of all the clips (or of --reference CLIP). Per channel, a frame's mean m and spread s (standard
deviation) are moved to the target's: out = g (x - m) + target mean, g = target spread / s (kept to 0.8-1.25).
The clips drift in color from start to end, so m and s are measured per frame and, inside each shot (a jump of
MAD > 20 between frames starts a new shot, whatever --threshold is), drawn as a straight line from the shot's
first second to its last; ffmpeg's colorlevels is updated every frame through sendcmd. MAD at the cuts is
measured after it.

Videos are taken in natural name order (2.mp4 before 10.mp4); .mp4, .mov, .mkv, .webm, and .m4v are read and
outputs named merged_* are skipped. Every clip is scaled and padded to the first clip's size and frame rate;
clips without sound get silence. The output is re-encoded (H.264 CRF 18 + AAC 48 kHz). Uses ffmpeg (see
trim_video.find_ffmpeg) and, for RIFE, rife-ncnn-vulkan: --rife PATH, else on PATH, else
tools/rife-ncnn-vulkan/ (release from https://github.com/nihui/rife-ncnn-vulkan/releases, model rife-v4.6).

Usage:
  python3 scripts/merge_videos.py                        # Videos/ -> Videos/merged_13-19.mp4
  python3 scripts/merge_videos.py --list                 # print each cut's MAD and choice only
  python3 scripts/merge_videos.py ~/Movies/shots --frames 8 -o final.mp4
  python3 scripts/merge_videos.py --threshold 25         # hard cut only above MAD 25
  python3 scripts/merge_videos.py --reference 16.mp4     # balance every clip to 16.mp4's color
  python3 scripts/merge_videos.py --interpolator minterpolate   # no RIFE: ffmpeg's motion interpolation
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from paths import ROOT
from trim_video import duration, find_ffmpeg

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
SW, SH = 64, 36  # frame size for measuring MAD
SHOT_CUT = 20  # a MAD jump between neighbouring frames above this is a camera cut inside a clip


def natural(p):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]


def videos_in(folder):
    return sorted((p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXT and not p.name.startswith("merged_")),
                  key=natural)


def probe(ffmpeg, path):
    """(width, height, fps, has sound) of a video."""
    info = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    video = next((line for line in info.splitlines() if "Video:" in line), "")
    size = re.search(r"\b(\d{2,5})x(\d{2,5})\b", video)
    rate = re.search(r"(\d+(?:\.\d+)?) fps", video)
    if not size:
        sys.exit(f"no video stream in {path}")
    return int(size[1]), int(size[2]), round(float(rate[1])) if rate else 24, "Audio:" in info


def grab(ffmpeg, path, vf, out, end=None):
    """Save one frame: the first, or with end the last one decoded in the half second before end."""
    pick = ["-ss", f"{max(end - 0.5, 0):.3f}", "-i", str(path), "-t", "0.5", "-update", "1"] if end is not None \
        else ["-i", str(path), "-frames:v", "1"]
    subprocess.run([ffmpeg, "-v", "error", "-y", *pick, "-vf", vf, str(out)], check=True)
    if not out.exists():
        sys.exit(f"could not read a frame from {path}")


def small(ffmpeg, png):
    return subprocess.run([ffmpeg, "-v", "error", "-i", str(png), "-vf", f"scale={SW}:{SH}", "-f", "rawvideo",
                           "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout


def mad(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def frames_of(ffmpeg, path, chain):
    """Every frame of the clip as it goes into the merge, at 64x36 rgb24."""
    raw = subprocess.run([ffmpeg, "-v", "error", "-i", str(path), "-vf", f"{chain},scale={SW}:{SH}", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    size = SW * SH * 3
    return [raw[i:i + size] for i in range(0, len(raw) - size + 1, size)]


def channel_stats(frame):
    """(mean, spread) of R, G, B."""
    out = []
    for c in range(3):
        v = frame[c::3]
        mean = sum(v) / len(v)
        out.append((mean, max(sum(x * x for x in v) / len(v) - mean * mean, 0) ** 0.5))
    return out


def average(stats):
    return [tuple(sum(f[c][j] for f in stats) / len(stats) for j in range(2)) for c in range(3)]


def shot_lines(frames, fps):
    """Per frame (mean, spread) of R, G, B, drawn as a straight line through each shot from the average of its
    first second to that of its last (a shot under 2 s gets its own average throughout)."""
    stats = [channel_stats(f) for f in frames]
    starts = [0] + [k for k in range(1, len(frames)) if mad(frames[k - 1], frames[k]) > SHOT_CUT] + [len(frames)]
    out = []
    for a, b in zip(starts, starts[1:]):
        if b - a < 2 * fps:
            out += [average(stats[a:b])] * (b - a)
            continue
        head, tail = average(stats[a:a + fps]), average(stats[b - fps:b])
        ca, cb = a + fps / 2, b - fps / 2
        for k in range(a, b):
            f = min(max((k - ca) / (cb - ca), 0), 1)
            out.append([tuple(h + (t - h) * f for h, t in zip(hc, tc)) for hc, tc in zip(head, tail)])
    return out


def levels(stats, target):
    """colorlevels options that move (mean, spread) per channel to the target's: out = g (x - m) + target mean."""
    opts = {}
    for c, (m, s), (tm, ts) in zip("rgb", stats, target):
        g = min(max(ts / s, 0.8), 1.25) if s else 1
        lo, hi = tm - g * m, tm + g * (255 - m)  # where black and white land
        # colorlevels' outputs must stay within 0..1: past an edge, the input point moves instead
        imin, omin = ((m - tm / g) / 255, 0) if lo < 0 else (0, lo / 255)
        imax, omax = ((m + (255 - tm) / g) / 255, 1) if hi > 255 else (1, hi / 255)
        opts |= {f"{c}imin": imin, f"{c}omin": omin, f"{c}imax": imax, f"{c}omax": omax}
    return opts


def find_rife(path):
    exe = path or shutil.which("rife-ncnn-vulkan") or ROOT / "tools" / "rife-ncnn-vulkan" / "rife-ncnn-vulkan"
    if not Path(exe).is_file():
        sys.exit("rife-ncnn-vulkan not found: download the macOS release from "
                 "https://github.com/nihui/rife-ncnn-vulkan/releases into tools/rife-ncnn-vulkan/, pass --rife, "
                 "or use --interpolator minterpolate")
    return Path(exe)


def bridge_rife(ffmpeg, rife, model, a_png, b_png, n, fps, out):
    """n frames morphing from a_png to b_png, each made by RIFE at its own time step k / (n + 1)."""
    seq = out.parent / "rife"
    seq.mkdir()
    for k in range(1, n + 1):
        done = subprocess.run([str(rife), "-0", str(a_png), "-1", str(b_png), "-o", str(seq / f"{k}.png"),
                               "-s", f"{k / (n + 1):.6f}", "-m", str(model)], capture_output=True, text=True)
        if done.returncode or not (seq / f"{k}.png").exists():
            sys.exit(f"rife-ncnn-vulkan failed:\n{done.stderr.strip()}")
    subprocess.run([ffmpeg, "-v", "error", "-y", "-framerate", str(fps), "-i", str(seq / "%d.png"),
                    "-frames:v", str(n), "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", str(out)], check=True)


def bridge(ffmpeg, a_png, b_png, n, fps, out):
    """n frames morphing from a_png to b_png. minterpolate outputs nothing from two stills, so each is
    doubled (a a b b, n + 1 frames apart); frames n + 2 .. 2n + 1 are the ones between a and b."""
    seq = out.parent / "seq"
    seq.mkdir()
    for i, png in enumerate((a_png, a_png, b_png, b_png), 1):
        (seq / f"{i}.png").write_bytes(png.read_bytes())
    subprocess.run([ffmpeg, "-v", "error", "-y", "-framerate", f"{fps}/{n + 1}", "-i", str(seq / "%d.png"),
                    "-vf", f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
                           f"select='between(n,{n + 2},{2 * n + 1})',setpts=N/{fps}/TB",
                    "-frames:v", str(n), "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", str(out)], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path, nargs="?", default=ROOT / "Videos", help="folder of videos (default Videos/)")
    ap.add_argument("-o", "--output", type=Path, help="output path (default: merged_<first>-<last>.mp4 in the folder)")
    ap.add_argument("--threshold", type=float, default=20, help="hard cut above this MAD (default 20)")
    ap.add_argument("--frames", type=int, default=6, help="interpolated frames per bridge (default 6)")
    ap.add_argument("--list", action="store_true", help="print each cut's MAD and choice, then stop")
    ap.add_argument("--reference", help="balance every clip to this clip's color (e.g. 16.mp4; default: the "
                                        "average of all the clips)")
    ap.add_argument("--no-balance", action="store_true", help="keep each clip's own color")
    ap.add_argument("--interpolator", choices=["rife", "minterpolate"], default="rife",
                    help="what makes the in-between frames (default rife)")
    ap.add_argument("--rife", help="path to rife-ncnn-vulkan (default: on PATH, else tools/rife-ncnn-vulkan/)")
    args = ap.parse_args()

    if not args.folder.is_dir():
        sys.exit(f"no such folder: {args.folder}")
    clips = videos_in(args.folder)
    if len(clips) < 2:
        sys.exit(f"need at least 2 videos in {args.folder}, found {len(clips)}")
    if not 1 <= args.frames <= 48:
        sys.exit("--frames must be between 1 and 48")

    ffmpeg = find_ffmpeg()
    if args.interpolator == "rife" and not args.list:
        rife = find_rife(args.rife)
        model = rife.parent / "rife-v4.6"  # v4 models take any time step (-s)
    w, h, fps, _ = probe(ffmpeg, clips[0])
    w, h = w // 2 * 2, h // 2 * 2  # H.264 needs even sizes
    fit = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    lengths = [duration(ffmpeg, p) for p in clips]
    sound = [probe(ffmpeg, p)[3] for p in clips]
    bridge_s = args.frames / fps
    # tpad: the picture can end a frame before the file does; every clip fills its full length
    chain = lambda length: (f"{fit},fps={fps},tpad=stop_mode=clone:stop_duration=0.5,trim=0:{length:.4f},"
                            "setpts=PTS-STARTPTS")

    balance = None  # per clip, per frame: colorlevels options
    if not args.no_balance:
        lines = [shot_lines(frames_of(ffmpeg, p, chain(n)), fps) for p, n in zip(clips, lengths)]
        if args.reference:
            ref = [i for i, p in enumerate(clips) if args.reference in (p.name, p.stem)]
            if not ref:
                sys.exit(f"--reference {args.reference} is not one of the videos in {args.folder}")
            target = average(lines[ref[0]])
        else:
            target = average([f for line in lines for f in line])
        balance = [[levels(f, target) for f in line] for line in lines]
        rgb = lambda st: "/".join(f"{m:.0f}" for m, _ in st)
        print(f"  color balance to R/G/B {rgb(target)} ({args.reference or 'average of all clips'}); before:")
        print("   " + ", ".join(f"{p.stem} {rgb(line[0])}->{rgb(line[-1])}" for p, line in zip(clips, lines)))
    look = lambda i, k: (f",colorlevels=" + ":".join(f"{o}={v:.5f}" for o, v in balance[i][k].items())
                         if balance else "")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cuts = []  # per cut: (MAD, bridge file or None)
        print(f"  {clips[0].name}  {lengths[0]:.2f} s")
        for i in range(1, len(clips)):
            d = tmp / f"cut{i}"
            d.mkdir()
            end = lengths[i - 1] - bridge_s  # the bridge replaces the first clip's last bridge_s seconds
            last = min(round(end * fps), len(balance[i - 1])) - 1 if balance else 0
            grab(ffmpeg, clips[i - 1], fit + look(i - 1, last), d / "a.png", end=end)
            grab(ffmpeg, clips[i], fit + look(i, 0), d / "b.png")
            m = mad(small(ffmpeg, d / "a.png"), small(ffmpeg, d / "b.png"))
            hard = m > args.threshold
            if not hard and not args.list:
                if args.interpolator == "rife":
                    bridge_rife(ffmpeg, rife, model, d / "a.png", d / "b.png", args.frames, fps, d / "bridge.mp4")
                else:
                    bridge(ffmpeg, d / "a.png", d / "b.png", args.frames, fps, d / "bridge.mp4")
            cuts.append((m, None if hard else d / "bridge.mp4"))
            how = "hard cut" if hard else f"interpolate {args.frames} frames ({bridge_s:.2f} s, {args.interpolator})"
            print(f"  -> MAD {m:5.1f}: {how}\n  {clips[i].name}  {lengths[i]:.2f} s")
        if args.list:
            return

        inputs, parts, video, audio = [], [], [], []
        for i, (p, length) in enumerate(zip(clips, lengths)):
            inputs += ["-i", str(p)]
        extra = len(clips)
        for i, (p, length) in enumerate(zip(clips, lengths)):
            vlen = length - (bridge_s if i < len(cuts) and cuts[i][1] else 0)
            grade = ""
            if balance:
                cmds = tmp / f"levels{i}.txt"
                cmds.write_text("".join(f"{k / fps:.4f} " + ", ".join(f"colorlevels@b{i} {o} {v:.5f}"
                                                                     for o, v in f.items()) + ";\n"
                                        for k, f in enumerate(balance[i])))
                grade = f",sendcmd=f='{cmds}',colorlevels@b{i}"
            parts.append(f"[{i}:v]{chain(vlen)}{grade},format=yuv420p[v{i}]")
            if sound[i]:
                src = f"{i}:a"
            else:
                inputs += ["-f", "lavfi", "-t", f"{length:.4f}", "-i", "anullsrc=r=48000:cl=stereo"]
                src, extra = f"{extra}:a", extra + 1
            parts.append(f"[{src}]aresample=48000,aformat=channel_layouts=stereo,apad,"
                         f"atrim=0:{length:.4f},asetpts=PTS-STARTPTS[a{i}]")
            video.append(f"[v{i}]")
            audio.append(f"[a{i}]")
            if i < len(cuts) and cuts[i][1]:
                inputs += ["-i", str(cuts[i][1])]
                parts.append(f"[{extra}:v]fps={fps},setpts=PTS-STARTPTS,format=yuv420p[b{i}]")
                video.append(f"[b{i}]")
                extra += 1
        parts.append(f"{''.join(video)}concat=n={len(video)}:v=1:a=0[v]")
        parts.append(f"{''.join(audio)}concat=n={len(audio)}:v=0:a=1[a]")

        out = args.output or args.folder / f"merged_{clips[0].stem}-{clips[-1].stem}.mp4"
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(parts),
               "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt",
               "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)]
        if subprocess.run(cmd).returncode:
            sys.exit("ffmpeg failed")

    hard = sum(1 for _, b in cuts if not b)
    print(f"Wrote {out}: {duration(ffmpeg, out):.2f} s ({len(clips)} clips, {len(cuts) - hard} interpolated, "
          f"{hard} hard cuts; clips add up to {sum(lengths):.2f} s)")


if __name__ == "__main__":
    main()
