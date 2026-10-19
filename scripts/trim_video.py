#!/usr/bin/env python3
"""Keep only the last N seconds (default 2) of a video, or cut them off instead with --drop-tail.

Uses ffmpeg: the one on PATH, or else the binary bundled with the imageio-ffmpeg package
(pip install imageio-ffmpeg). The cut is re-encoded (H.264 + AAC) so it lands on the exact frame;
--copy skips re-encoding, which is instant but cuts on the nearest keyframe.

Usage:
  python3 scripts/trim_video.py clip-13.mp4                    # -> clip-13_last2s.mp4, only the last 2 s
  python3 scripts/trim_video.py clip-13.mp4 --seconds 3 -o out.mp4
  python3 scripts/trim_video.py clip-13.mp4 --drop-tail        # -> clip-13_trimmed.mp4, last 2 s removed
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg not found: install it (brew install ffmpeg) or run: pip install imageio-ffmpeg")


def duration(ffmpeg, path):
    """Video length in seconds, read from ffmpeg's 'Duration: HH:MM:SS.ss' line."""
    info = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", info)
    if not m:
        sys.exit(f"could not read the duration of {path}:\n{info.strip()}")
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path, help="path to the input video")
    ap.add_argument("--seconds", type=float, default=2.0, help="seconds at the end of the video (default 2)")
    ap.add_argument("--drop-tail", action="store_true", help="remove the last N seconds instead of keeping only them")
    ap.add_argument("-o", "--output", type=Path, help="output path (default: next to the input)")
    ap.add_argument("--copy", action="store_true", help="no re-encode: faster, but cuts on a keyframe")
    args = ap.parse_args()

    if not args.video.is_file():
        sys.exit(f"no such file: {args.video}")
    if args.seconds <= 0:
        sys.exit("--seconds must be greater than 0")

    ffmpeg = find_ffmpeg()
    total = duration(ffmpeg, args.video)
    if args.seconds >= total:
        sys.exit(f"{args.video} is only {total:.2f} s long; it must be longer than {args.seconds:g} s")

    keep_tail = not args.drop_tail
    suffix = f"_last{args.seconds:g}s" if keep_tail else "_trimmed"
    out = args.output or args.video.with_name(args.video.stem + suffix + args.video.suffix)
    if out.resolve() == args.video.resolve():
        sys.exit("output must differ from the input")

    # keep [total - N, total] by default, or [0, total - N] with --drop-tail
    span = ["-ss", f"{total - args.seconds:.3f}"] if keep_tail else ["-t", f"{total - args.seconds:.3f}"]
    codec = ["-c", "copy"] if args.copy else ["-c:v", "libx264", "-crf", "18", "-preset", "medium",
                                              "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"]
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(args.video), *span, *codec,
           "-movflags", "+faststart", str(out)]
    if subprocess.run(cmd).returncode:
        sys.exit("ffmpeg failed")

    kept = args.seconds if keep_tail else total - args.seconds
    print(f"Wrote {out}: {duration(ffmpeg, out):.2f} s (input {total:.2f} s, expected {kept:.2f} s)")


if __name__ == "__main__":
    main()
