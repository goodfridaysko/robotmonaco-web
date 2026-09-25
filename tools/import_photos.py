#!/usr/bin/env python3
"""Bring photographs of the robot into photos/, all cropped to the one shape the rail shows.

    python3 tools/import_photos.py <folder-with-originals> [<folder> ...]

The originals arrive at wildly different sizes and orientations, so every card in the rail would
otherwise be a different shape. Each photo is cropped to 3:4 and capped at 1200 px wide, which is as
much as a card ever shows.

MANIFEST maps an original's file name to the name the site uses, plus where the subject sits in the
frame, because a centre crop of a wide press shot cuts the subject in half. focus is a fraction of the
width (0.5 is the middle); for a portrait original, focus_y does the same vertically.

Two families live here, and build.py keeps them apart in the captions:
  real-*      our own photographs, in the workshop, on test and at shows
  unitree-*   the manufacturer's pictures of the same G1 platform
"""
import pathlib
import sys

from PIL import Image, ImageOps

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "photos"

RATIO = 3 / 4          # the rail shows portrait cards
MAX_W = 1200

MANIFEST = {
    # our own, shot on a phone: the subject is upright and centred, so the default crop is right
    "image_2026-09-26_01-09-11.png": ("real-internals", 0.5, 0.06),
    "image_2026-09-26_01-09-15 (3).png": ("real-expo-floor", 0.5, 0.06),
    "image_2026-09-26_01-09-15 (5).png": ("real-audience", 0.5, 0.06),
    "image_2026-09-26_01-09-15 (6).png": ("real-testing", 0.5, 0.06),
    "image_2026-09-26_01-09-15 (7).png": ("real-rig", 0.5, 0.06),
    "image_2026-09-26_01-09-15.png": ("real-venue", 0.5, 0.06),
    # the manufacturer's, all landscape: each one needs its own horizontal focus
    "260819-unitree-3-rs-e73211.webp": ("unitree-booth", 0.24, 0.5),
    "98320701215429.jpg": ("unitree-stage", 0.52, 0.5),
    "Unitree.jpg": ("unitree-expo", 0.36, 0.5),
    "a7b5b5440859bdcd8578a0082acd3b60.jpg": ("unitree-kitchen", 0.42, 0.5),
    "c3d4bb3a1b7be485876be22d0f60640f.jpg": ("unitree-head", 0.5, 0.5),
    "f165f440-9b6c-11f1-b1cb-859c01609bc4.jpg": ("unitree-launch", 0.68, 0.5),
    "images.jpg": ("unitree-studio", 0.5, 0.5),
    "unitree-omni-modal-interaction-robot-cleaning-room-through-whole-body-mobile-manipulation.webp":
        ("unitree-manipulation", 0.62, 0.5),
}


def crop(im, focus_x, focus_y):
    """Crop to RATIO, keeping focus_x / focus_y in view rather than whatever sits in the middle."""
    w, h = im.size
    if w / h > RATIO:                       # too wide: trim the sides around focus_x
        nw = int(h * RATIO)
        left = min(max(int(w * focus_x - nw / 2), 0), w - nw)
        return im.crop((left, 0, left + nw, h))
    nh = int(w / RATIO)                     # too tall: trim around focus_y
    top = min(max(int(h * focus_y), 0), h - nh)
    return im.crop((0, top, w, top + nh))


sources = {}
for folder in sys.argv[1:] or sys.exit(__doc__):
    for p in pathlib.Path(folder).rglob("*"):
        if p.is_file() and p.name in MANIFEST:
            sources[p.name] = p

missing = [n for n in MANIFEST if n not in sources]
if missing:
    print(f"not found, left as they are: {', '.join(missing)}")

for src_name, path in sorted(sources.items()):
    name, fx, fy = MANIFEST[src_name]
    im = crop(ImageOps.exif_transpose(Image.open(path)).convert("RGB"), fx, fy)
    if im.width > MAX_W:
        im = im.resize((MAX_W, round(im.height * MAX_W / im.width)), Image.LANCZOS)
    im.save(OUT / f"{name}.jpg", quality=84, optimize=True, progressive=True)
    print(f"{name}.jpg  {im.size[0]}x{im.size[1]}  <- {src_name}")
