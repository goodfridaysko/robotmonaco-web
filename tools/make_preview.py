#!/usr/bin/env python3
"""Turn dist/ into a folder that browses correctly without a web server.

    python3 tools/make_preview.py [out-dir]

Production relies on Apache for two things the file system does not give us: clean URLs (/robots ->
robots.html) and absolute asset paths (/assets/...). A preview has neither, so every internal link gets
its .html back and every absolute path is rewritten relative to the page that uses it.
"""
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "preview"

if not DIST.exists():
    raise SystemExit("build first: python3 build.py")
if OUT.exists():
    shutil.rmtree(OUT)
shutil.copytree(DIST, OUT)

ATTR = re.compile(r'((?:href|src|action|data-model)=")/([^"]*)"')


def fix_html(text, depth):
    up = "../" * depth

    def sub(m):
        head, rest = m.group(1), m.group(2)
        path, _, frag = rest.partition("#")
        frag = "#" + frag if frag else ""
        if path == "" or path.endswith("/"):
            path += "index.html"
        elif "." not in path.rsplit("/", 1)[-1]:
            path += ".html"                       # the clean URL the rewrite rule would have resolved
        return f'{head}{up}{path}{frag}"'

    return ATTR.sub(sub, text)


pages = 0
for p in OUT.rglob("*.html"):
    depth = len(p.relative_to(OUT).parts) - 1
    p.write_text(fix_html(p.read_text(encoding="utf-8"), depth), encoding="utf-8")
    pages += 1

# The stylesheet lives in assets/, so its own relative URLs already point at the right place.
css = OUT / "assets" / "styles.css"
css.write_text(css.read_text(encoding="utf-8").replace("url(/assets/", "url("), encoding="utf-8")

# app.js resolves its URLs against the page, not against itself. Only the home page carries a 3D stage,
# and that page sits at the root, so dropping the leading slash is correct wherever the code actually runs.
js = OUT / "assets" / "app.js"
src = js.read_text(encoding="utf-8").replace("'/assets/", "'assets/")
# A .hdr is not something a static preview host will serve, so the viewer falls back to its own lighting.
src = re.sub(r"'environment-image':\s*'[^']*',\s*", "", src)
js.write_text(src, encoding="utf-8")
shutil.rmtree(OUT / "assets" / "env", ignore_errors=True)

print(f"preview ready: {pages} pages -> {OUT}")
