#!/usr/bin/env python3
"""Measure how blurred an image, or one frame of a video, is.

Two measures, both on the grey (lightness) image scaled to --width pixels wide so different sizes compare fairly:

  blur       0 (sharp) to 1 (fully blurred). The no-reference blur metric of Crete-Roffet et al. (2007): the image
             is blurred again with a 9-pixel box filter, and blur = the share of its pixel-to-pixel differences
             (detail) that this extra blur does NOT remove. A sharp image loses much of its detail when blurred
             (low score); an already blurred one barely changes (high score). It is taken in the horizontal and
             vertical directions and the larger is kept, so motion blur in one direction counts. As it compares
             the image with itself, it depends little on the content.
  sharpness  variance of the Laplacian (the second derivative, which responds to edges): higher = more and
             crisper edges. It depends on the content, so compare it between frames of the same scene.

  blur below 0.30 sharp, 0.30-0.45 slightly soft, 0.45-0.60 blurry, above 0.60 very blurry

A video frame is picked with --time (seconds) or --frame (number, from 0); --every SECONDS scores the whole video
and prints the least and most blurred frames. Needs numpy and OpenCV (pip install -r requirements.txt).

Usage:
  .venv/bin/python scripts/blur_score.py photo.png
  .venv/bin/python scripts/blur_score.py a.png b.jpg c.webp
  .venv/bin/python scripts/blur_score.py Videos/merged_13-19.mp4 --time 25.5
  .venv/bin/python scripts/blur_score.py Videos/merged_13-19.mp4 --frame 600
  .venv/bin/python scripts/blur_score.py Videos/merged_13-19.mp4 --every 1
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
LEVELS = [(0.30, "sharp"), (0.45, "slightly soft"), (0.60, "blurry"), (1.01, "very blurry")]


def grey(image, width):
    g = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    h, w = g.shape
    if w != width:
        g = cv2.resize(g, (width, round(h * width / w)), interpolation=cv2.INTER_AREA if w > width else cv2.INTER_CUBIC)
    return g.astype(np.float64)


def blur_amount(g):
    """Crete-Roffet blur, 0 (sharp) to 1 (blurred)."""
    scores = []
    # axis 0: vertical differences, blurred by a 9-tall box; axis 1: horizontal, 9-wide (cv2 sizes are width, height)
    for axis, box in ((0, (1, 9)), (1, (9, 1))):
        blurred = cv2.blur(g, box)
        d_image = np.abs(np.diff(g, axis=axis))
        d_blurred = np.abs(np.diff(blurred, axis=axis))
        lost = np.maximum(0, d_image - d_blurred)  # detail the extra blur removed
        total = d_image.sum()
        scores.append((total - lost.sum()) / total if total else 1.0)
    return max(scores)


def sharpness(g):
    return cv2.Laplacian(g, cv2.CV_64F).var()


def verdict(blur):
    return next(name for limit, name in LEVELS if blur < limit)


def score(image, width):
    g = grey(image, width)
    b = blur_amount(g)
    return b, sharpness(g), verdict(b)


def line(name, image, width):
    b, s, v = score(image, width)
    return f"{name}: blur {b:.3f} ({v}), sharpness {s:.0f}"


def video_frame(cap, fps, args):
    index = args.frame if args.frame is not None else round(args.time * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, image = cap.read()
    if not ok:
        sys.exit(f"no frame {index} (the video has {int(cap.get(cv2.CAP_PROP_FRAME_COUNT))} frames)")
    return index, image


def scan(cap, fps, every, width, name):
    step, rows, k = max(1, round(every * fps)), [], 0
    while True:
        ok, image = cap.read()
        if not ok:
            break
        if k % step == 0:
            rows.append((k, *score(image, width)))
        k += 1
    if not rows:
        sys.exit(f"could not read any frame of {name}")
    blurs = np.array([r[1] for r in rows])
    print(f"{name}: {len(rows)} frames scored (every {every:g} s); blur mean {blurs.mean():.3f}, "
          f"min {blurs.min():.3f}, max {blurs.max():.3f}")
    for v in [name for _, name in LEVELS]:
        n = sum(r[3] == v for r in rows)
        if n:
            print(f"  {v:14s} {n:5d} frames ({100 * n / len(rows):.0f}%)")
    ranked = sorted(rows, key=lambda r: r[1])
    for title, part in (("sharpest", ranked[:3]), ("most blurred", ranked[::-1][:3])):
        print(f"  {title}: " + ", ".join(f"frame {k} ({k / fps:.2f} s) blur {b:.3f}" for k, b, _, _ in part))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", type=Path, nargs="+", help="images, or a video")
    pick = ap.add_mutually_exclusive_group()
    pick.add_argument("--time", type=float, help="video: the frame at this many seconds")
    pick.add_argument("--frame", type=int, help="video: this frame number (from 0)")
    pick.add_argument("--every", type=float, help="video: score a frame every this many seconds, then summarise")
    ap.add_argument("--width", type=int, default=1280, help="scale to this width before measuring (default 1280)")
    args = ap.parse_args()

    if args.width < 16:
        sys.exit("--width must be at least 16")
    for path in args.files:
        if not path.is_file():
            sys.exit(f"no such file: {path}")
        if path.suffix.lower() not in VIDEO_EXT:
            image = cv2.imread(str(path))
            if image is None:
                sys.exit(f"could not read the image {path}")
            print(line(str(path), image, args.width))
            continue
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            sys.exit(f"could not open the video {path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 24
        if args.every:
            scan(cap, fps, args.every, args.width, str(path))
        else:
            if args.time is None and args.frame is None:
                args.frame = 0
            index, image = video_frame(cap, fps, args)
            print(line(f"{path} frame {index} ({index / fps:.2f} s)", image, args.width))
        cap.release()


if __name__ == "__main__":
    main()
