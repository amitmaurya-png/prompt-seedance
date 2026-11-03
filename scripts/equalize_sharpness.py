#!/usr/bin/env python3
"""Bring the sharpness of every frame of a video to the video's average.

Sharpness is measured as blur_score's blur (0 sharp - 1 blurred, Crete-Roffet), which depends little on what the
frame shows, so a close-up and a wide shot are judged alike. The target is the average blur of all frames (or
--target). Each frame's lightness L (Lab) is changed by
    L + t (L - L blurred with a Gaussian of --radius pixels)
t > 0 sharpens (unsharp mask), t < 0 softens (a blend toward the blurred image), and t is found per frame by
bisection so that the frame's blur equals the target (t is kept to --min..--max). To avoid flicker, t is then
averaged over --smooth seconds inside each shot (a MAD > 20 jump between frames starts a new shot).

Two passes over the video: one measures and solves t (in parallel on all cores), one applies it. ffmpeg decodes
and encodes (H.264 CRF 18); the sound is copied unchanged. Needs numpy and OpenCV (pip install -r requirements.txt).

Usage:
  .venv/bin/python scripts/equalize_sharpness.py Videos/merged_13-19.mp4      # -> ..._sharpness_eq.mp4 next to it
  .venv/bin/python scripts/equalize_sharpness.py in.mp4 --target 0.30 -o out.mp4
"""

import argparse
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

from blur_score import blur_amount
from merge_videos import probe
from trim_video import duration, find_ffmpeg

SHOT_CUT = 20  # MAD between neighbouring frames (64x36, 0-255) above which a new shot starts
STEPS = 9  # bisection steps for t


def frames(ffmpeg, path, w, h):
    """Every frame as an h x w x 3 rgb24 array."""
    decode = subprocess.Popen([ffmpeg, "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                              stdout=subprocess.PIPE)
    size = w * h * 3
    while len(raw := decode.stdout.read(size)) == size:
        yield np.frombuffer(raw, np.uint8).reshape(h, w, 3)
    if decode.wait():
        sys.exit("ffmpeg could not decode the video")


def lightness(rgb):
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)[..., 0].astype(np.float64)


def adjust(light, t, radius):
    return np.clip(light + t * (light - cv2.GaussianBlur(light, (0, 0), radius)), 0, 255)


def solve(job):
    """(blur before, t that brings the frame's blur to the target) for one frame's lightness."""
    light, target, radius, lo, hi = job
    before = blur_amount(light)
    for _ in range(STEPS):  # blur falls as t rises
        mid = (lo + hi) / 2
        if blur_amount(adjust(light, mid, radius)) > target:
            lo = mid
        else:
            hi = mid
    return before, (lo + hi) / 2


def measure(job):
    return blur_amount(job)


def batches(it, n):
    batch = []
    for x in it:
        batch.append(x)
        if len(batch) == n:
            yield batch
            batch = []
    if batch:
        yield batch


def shots(small):
    starts = [0] + [k for k in range(1, len(small)) if np.abs(small[k] - small[k - 1]).mean() > SHOT_CUT]
    return list(zip(starts, starts[1:] + [len(small)]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path, help="path to the input video")
    ap.add_argument("-o", "--output", type=Path,
                    help="output path (default: <name>_sharpness_eq.mp4 next to the input)")
    ap.add_argument("--target", type=float, help="blur to bring every frame to (default: the video's average)")
    ap.add_argument("--radius", type=float, default=1.5, help="Gaussian radius in pixels (default 1.5)")
    ap.add_argument("--min", type=float, default=-1.0, help="most softening, t (default -1)")
    ap.add_argument("--max", type=float, default=3.0, help="most sharpening, t (default 3)")
    ap.add_argument("--smooth", type=float, default=0.5, help="seconds t is averaged over within a shot (default 0.5)")
    args = ap.parse_args()

    if not args.video.is_file():
        sys.exit(f"no such file: {args.video}")
    if args.radius <= 0 or args.min > 0 or args.max < 0 or args.smooth < 0:
        sys.exit("--radius must be above 0, --min 0 or below, --max and --smooth 0 or above")
    if args.target is not None and not 0 < args.target < 1:
        sys.exit("--target must be between 0 and 1")
    out = args.output or args.video.with_name(f"{args.video.stem}_sharpness_eq.mp4")
    if out.resolve() == args.video.resolve():
        sys.exit("output must differ from the input")

    ffmpeg = find_ffmpeg()
    w, h, fps, sound = probe(ffmpeg, args.video)
    with Pool() as pool:
        small, before = [], []
        for batch in batches(frames(ffmpeg, args.video, w, h), 64):
            small += [cv2.resize(f, (64, 36), interpolation=cv2.INTER_AREA).astype(np.int16) for f in batch]
            before += pool.map(measure, [lightness(f) for f in batch])
        target = args.target if args.target is not None else float(np.mean(before))
        print(f"{len(before)} frames; blur mean {np.mean(before):.3f} (spread {np.std(before):.3f}, "
              f"{min(before):.3f}-{max(before):.3f}); target {target:.3f}")

        t = []
        for batch in batches(frames(ffmpeg, args.video, w, h), 64):
            t += [s for _, s in pool.map(solve, [(lightness(f), target, args.radius, args.min, args.max)
                                                 for f in batch])]
    t = np.array(t)
    half = round(args.smooth * fps / 2)
    smooth = t.copy()
    for a, b in shots(small):
        for k in range(a, b):
            smooth[k] = t[max(a, k - half):min(b, k + half + 1)].mean()
    print(f"t per frame: {smooth.min():+.2f} to {smooth.max():+.2f} (+ sharpens, - softens); "
          f"{(smooth > 0.05).sum()} frames sharpened, {(smooth < -0.05).sum()} softened")

    encode = subprocess.Popen([ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                               "-framerate", str(fps), "-i", "-", "-i", str(args.video), "-map", "0:v",
                               *(["-map", "1:a", "-c:a", "copy"] if sound else []), "-c:v", "libx264", "-crf", "18",
                               "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
                              stdin=subprocess.PIPE)
    for k, rgb in enumerate(frames(ffmpeg, args.video, w, h)):
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
        lab[..., 0] = adjust(lab[..., 0].astype(np.float64), smooth[min(k, len(smooth) - 1)], args.radius).round()
        encode.stdin.write(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB).tobytes())
    encode.stdin.close()
    if encode.wait():
        sys.exit("ffmpeg could not encode the video")
    print(f"Wrote {out}: {duration(ffmpeg, out):.2f} s")


if __name__ == "__main__":
    main()
