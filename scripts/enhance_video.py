#!/usr/bin/env python3
"""Standardize every frame of a video: gamma correction, color cast removal, saturation, contrast, CLAHE, and
sharpening, in that order.

  gamma  out = 255 (in / 255) ^ (1 / gamma) on R, G, B: gamma above 1 lifts the shadows and midtones and leaves
         black and white where they are (default 1.2)
  CLAHE  contrast-limited adaptive histogram equalisation (OpenCV) on the lightness channel L of Lab, so colors
         keep their hue: the frame is cut into --tiles x --tiles tiles, each tile's histogram is equalised with
         its counts capped at --clip times the average (which keeps noise and flat areas from being blown up),
         and neighbouring tiles are blended so no seams show (--clip 0 = off)
  neutral  removes each frame's own color cast (e.g. a yellow tint): in Lab, a (green-red) and b (blue-yellow)
         are shifted so that the frame's average is grey; --neutral 1 removes all of it, 0.5 half (default off)
  saturation  a and b are scaled away from grey by this factor (default 1 = off): after --neutral the cast is
         gone, so this brings back the colors of the things in the frame without bringing back the tint
  contrast  L is scaled away from the frame's average lightness by this factor (default 1 = off)
  sharpen  unsharp mask on L: L + amount (L - L blurred with a Gaussian of --radius pixels) brings back edges
         and fine detail that look soft (--sharpen 0.8 is moderate; default off)

ffmpeg decodes the frames and encodes the result (H.264 CRF 18); the sound is copied unchanged. Needs numpy and
OpenCV (pip install -r requirements.txt) and ffmpeg (see trim_video.find_ffmpeg).

Usage:
  .venv/bin/python scripts/enhance_video.py Videos/merged_13-19_ffmpeg.mp4    # -> ..._clahe.mp4 next to it
  .venv/bin/python scripts/enhance_video.py in.mp4 --gamma 1.1 --clip 1.5 --tiles 8 -o out.mp4
  .venv/bin/python scripts/enhance_video.py in.mp4 --gamma 1 --clip 0 --neutral 1 --sharpen 0.8 -o out.mp4
  .venv/bin/python scripts/enhance_video.py in.mp4 --gamma 1 --clip 0 --neutral 1 --saturation 1.6 --contrast 1.1 \
      --sharpen 0.8 -o out.mp4
"""

import argparse
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from merge_videos import probe
from trim_video import duration, find_ffmpeg


def enhancer(gamma, clip, tiles, neutral, saturation, contrast, sharpen, radius):
    lut = (255 * (np.arange(256) / 255) ** (1 / gamma)).round().astype(np.uint8)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(tiles, tiles)) if clip else None

    def enhance(rgb):
        lab = cv2.cvtColor(cv2.LUT(rgb, lut), cv2.COLOR_RGB2LAB)
        if neutral:
            for c in (1, 2):  # 8-bit Lab: a and b are 128 for grey
                shift = round(neutral * (128 - lab[..., c].mean()))
                lab[..., c] = np.clip(lab[..., c].astype(np.int16) + shift, 0, 255)
        if saturation != 1:
            lab[..., 1:] = np.clip(128 + (lab[..., 1:].astype(np.float32) - 128) * saturation, 0, 255)
        if contrast != 1:
            light = lab[..., 0].astype(np.float32)
            lab[..., 0] = np.clip(light.mean() + (light - light.mean()) * contrast, 0, 255)
        if clahe:
            lab[..., 0] = clahe.apply(lab[..., 0])
        if sharpen:
            light = lab[..., 0]
            lab[..., 0] = cv2.addWeighted(light, 1 + sharpen, cv2.GaussianBlur(light, (0, 0), radius), -sharpen, 0)
        return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    return enhance


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path, help="path to the input video")
    ap.add_argument("-o", "--output", type=Path, help="output path (default: <name>_clahe.mp4 next to the input)")
    ap.add_argument("--gamma", type=float, default=1.2, help="gamma; above 1 brightens (default 1.2, 1 = off)")
    ap.add_argument("--clip", type=float, default=2.0,
                    help="CLAHE clip limit (default 2.0; higher = stronger, 0 = off)")
    ap.add_argument("--tiles", type=int, default=8, help="CLAHE tiles per side (default 8)")
    ap.add_argument("--neutral", type=float, default=0,
                    help="share of each frame's color cast to remove, 0-1 (default 0)")
    ap.add_argument("--saturation", type=float, default=1, help="color strength factor (default 1 = off)")
    ap.add_argument("--contrast", type=float, default=1, help="contrast factor (default 1 = off)")
    ap.add_argument("--sharpen", type=float, default=0, help="unsharp mask amount (default 0 = off; 0.8 moderate)")
    ap.add_argument("--radius", type=float, default=1.5, help="unsharp mask blur radius in pixels (default 1.5)")
    args = ap.parse_args()

    if not args.video.is_file():
        sys.exit(f"no such file: {args.video}")
    if args.gamma <= 0 or args.clip < 0 or args.tiles < 1 or not 0 <= args.neutral <= 1 or args.sharpen < 0 \
            or args.radius <= 0 or args.saturation < 0 or args.contrast <= 0:
        sys.exit("--gamma, --contrast, and --radius must be above 0, --clip, --saturation, and --sharpen 0 or more, "
                 "--neutral 0-1, "
                 "--tiles 1 or more")
    out = args.output or args.video.with_name(f"{args.video.stem}_clahe.mp4")
    if out.resolve() == args.video.resolve():
        sys.exit("output must differ from the input")

    ffmpeg = find_ffmpeg()
    w, h, fps, sound = probe(ffmpeg, args.video)
    decode = subprocess.Popen([ffmpeg, "-v", "error", "-i", str(args.video), "-f", "rawvideo", "-pix_fmt", "rgb24",
                               "-"], stdout=subprocess.PIPE)
    encode = subprocess.Popen([ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                               "-framerate", str(fps), "-i", "-", "-i", str(args.video), "-map", "0:v",
                               *(["-map", "1:a", "-c:a", "copy"] if sound else []), "-c:v", "libx264", "-crf", "18",
                               "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
                              stdin=subprocess.PIPE)
    enhance = enhancer(args.gamma, args.clip, args.tiles, args.neutral, args.saturation, args.contrast, args.sharpen,
                       args.radius)
    size, frames = w * h * 3, 0
    while (raw := decode.stdout.read(size)) and len(raw) == size:
        frame = np.frombuffer(raw, np.uint8).reshape(h, w, 3)
        encode.stdin.write(enhance(frame).tobytes())
        frames += 1
    encode.stdin.close()
    if decode.wait() or encode.wait():
        sys.exit("ffmpeg failed")
    print(f"Wrote {out}: {duration(ffmpeg, out):.2f} s, {frames} frames (gamma {args.gamma:g}, CLAHE clip "
          f"{args.clip:g}, {args.tiles}x{args.tiles} tiles, neutral {args.neutral:g}, saturation "
          f"{args.saturation:g}, contrast {args.contrast:g}, sharpen {args.sharpen:g})")


if __name__ == "__main__":
    main()
