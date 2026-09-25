#!/usr/bin/env python3
"""Compose every photo the site needs from the transparent robot renders in src/img/robots/.

    python3 tools/make_images.py

The site has no event photography of its own, so each visual is the real robot render placed on a
brand gradient. Output goes to photos/, which build.py copies to /assets/photos/.
"""
import pathlib

from PIL import Image, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[1]
RENDERS, OUT = ROOT / "src" / "img" / "robots", ROOT / "photos"
OUT.mkdir(exist_ok=True)

# Two background families keep the set coherent while giving neighbouring pages a different feel.
BG = {
    "dark": ((9, 9, 11), (48, 47, 53), (120, 122, 140), 70),
    "light": ((248, 248, 250), (214, 214, 221), (255, 255, 255), 90),
}


def gradient(w, h, kind):
    c0, c1, glow_rgb, glow_a = BG[kind]
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        ty = y / max(1, h - 1)
        for x in range(w):
            t = (x / max(1, w - 1)) * 0.62 + ty * 0.38
            px[x, y] = tuple(int(a + (b - a) * t) for a, b in zip(c0, c1))
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    cx, cy, r = int(w * 0.5), int(h * 0.44), int(max(w, h) * 0.55)
    for y in range(max(0, cy - r), min(h, cy + r)):
        for x in range(max(0, cx - r), min(w, cx + r)):
            d = (((x - cx) / r) ** 2 + ((y - cy) / r) ** 2) ** 0.5
            if d < 1:
                mp[x, y] = int(glow_a * (1 - d) ** 2)
    mask = mask.filter(ImageFilter.GaussianBlur(int(max(w, h) * 0.07)))
    return Image.composite(Image.new("RGB", (w, h), glow_rgb), im, mask)


def compose(name, render, kind, size, height=0.86, dx=0.0, dy=0.0):
    w, h = size
    canvas = gradient(w, h, kind).convert("RGBA")
    art = Image.open(RENDERS / f"{render}.png").convert("RGBA")
    th = int(h * height)
    art = art.resize((max(1, round(art.width * th / art.height)), th), Image.LANCZOS)
    if art.width > w * 0.96:                      # wide subjects (the dog) are fitted by width instead
        tw = int(w * 0.96)
        art = art.resize((tw, max(1, round(art.height * tw / art.width))), Image.LANCZOS)
    x = int((w - art.width) / 2 + w * dx)
    y = int(h - art.height - h * 0.06 + h * dy)
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow.paste(Image.new("RGBA", art.size, (0, 0, 0, 90 if kind == "dark" else 60)), (x + int(w * 0.012), y + int(h * 0.012)), art)
    canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(int(max(w, h) * 0.02))))
    canvas.paste(art, (x, y), art)
    canvas.convert("RGB").save(OUT / f"{name}.jpg", quality=88, optimize=True, progressive=True)
    print(name, canvas.size)


P = (1200, 1500)      # 4:5, the split hero
W = (2000, 858)       # 21:9, the wide band
OG = (1200, 630)

JOBS = [
    ("hero", "montari-wave-4k", "dark", P, 0.9, 0.02, 0),
    ("og-default", "montari-wave-4k", "dark", OG, 0.92, 0.22, 0),
    ("montari-hero", "montari-wave-4k", "dark", P, 0.9, 0, 0),
    ("nova-hero", "montari-4k", "light", P, 0.92, 0, 0),
    ("oryx-hero", "oryx-side-4k", "dark", P, 0.55, 0, -0.12),
    ("software", "montari-walk-4k", "dark", W, 0.86, -0.22, 0),
    ("brand-activations", "montari-wave-4k", "dark", P, 0.9, 0, 0),
    ("product-launches", "montari-4k", "light", P, 0.92, 0, 0),
    ("corporate-events", "montari-wave-4k", "light", P, 0.88, 0, 0),
    ("trade-shows", "montari-walk-4k", "dark", P, 0.88, 0, 0),
    ("yacht-shows", "oryx-side-4k", "light", P, 0.55, 0, -0.12),
    ("grand-prix-hospitality", "montari-walk-4k", "dark", P, 0.9, 0.04, 0),
    ("luxury-retail", "montari-4k", "dark", P, 0.92, 0, 0),
    ("galas-and-awards", "montari-wave-4k", "dark", P, 0.88, -0.03, 0),
    ("private-parties", "oryx-front-4k", "dark", P, 0.5, 0, -0.14),
    ("conferences", "montari-4k", "light", P, 0.9, 0.03, 0),
    ("ai-assistant", "montari-4k", "dark", P, 0.9, 0, 0),
]

for job in JOBS:
    compose(*job)


def og_card():
    """The link preview carries the wordmark as well, so a shared URL reads as the brand at thumbnail size."""
    w, h = OG
    canvas = gradient(w, h, "dark").convert("RGBA")
    art = Image.open(RENDERS / "montari-wave-4k.png").convert("RGBA")
    th = int(h * 0.92)
    art = art.resize((round(art.width * th / art.height), th), Image.LANCZOS)
    x, y = int(w * 0.60), h - art.height - int(h * 0.04)
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow.paste(Image.new("RGBA", art.size, (0, 0, 0, 110)), (x + 10, y + 12), art)
    canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(22)))
    canvas.paste(art, (x, y), art)
    logo = Image.open(ROOT / "src" / "img" / "logo-white.png").convert("RGBA")
    lw = int(w * 0.42)
    logo = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
    canvas.paste(logo, (int(w * 0.06), (h - logo.height) // 2), logo)
    canvas.convert("RGB").save(OUT / "og-default.jpg", quality=90, optimize=True, progressive=True)
    print("og-default (with wordmark)", canvas.size)


og_card()
print("done:", len(JOBS), "images ->", OUT)
