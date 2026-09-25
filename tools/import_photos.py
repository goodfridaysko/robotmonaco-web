#!/usr/bin/env python3
"""Bring real photographs of the robot into photos/, cropped to one ratio.

    python3 tools/import_photos.py <folder-with-originals>

The originals arrive at wildly different sizes, so every card in the rail would otherwise be a different
shape. Each photo is centre-cropped to 3:4 and capped at 1200 px wide, which is as much as a card ever
shows. Names are given by NAMES below, in the order the files sort.
"""
import pathlib
import sys

from PIL import Image, ImageOps

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "photos"
SRC = pathlib.Path(sys.argv[1])

RATIO = 3 / 4          # the rail shows portrait cards
MAX_W = 1200

NAMES = [
    "real-internals",     # the robot opened up on the bench
    "real-lab",           # sitting in the workshop
    "real-demo-hand",     # a visitor reaching for its hand
    "real-expo-floor",    # walking an exhibition floor
    "real-audience",      # working a crowd
    "real-testing",       # walking test indoors
    "real-rig",           # on the service rig
    "real-venue",         # indoors at a venue
]

files = sorted(p for p in SRC.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png") and not p.name.startswith("."))
if len(files) != len(NAMES):
    raise SystemExit(f"expected {len(NAMES)} photos, found {len(files)}: rename NAMES to match")

for name, f in zip(NAMES, files):
    im = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
    w, h = im.size
    if w / h > RATIO:                       # too wide: trim the sides
        nw = int(h * RATIO)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:                                   # too tall: trim from the bottom, the subject sits high
        nh = int(w / RATIO)
        top = min(int(h * 0.06), h - nh)
        im = im.crop((0, top, w, top + nh))
    if im.width > MAX_W:
        im = im.resize((MAX_W, round(im.height * MAX_W / im.width)), Image.LANCZOS)
    im.save(OUT / f"{name}.jpg", quality=84, optimize=True, progressive=True)
    print(f"{name}.jpg  {im.size[0]}x{im.size[1]}  <- {f.name}")
