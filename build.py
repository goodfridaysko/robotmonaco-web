#!/usr/bin/env python3
"""robotmonaco.com static site generator.

    python3 build.py            build content/ + src/ + photos/ into dist/
    python3 build.py --serve    build, then serve dist/ on http://localhost:4175 with clean URLs

English lives at the root, French mirrors every path under /fr/. No dependencies.
Every page goes through page() so meta, schema, breadcrumbs, hreflang and the sitemap
can never drift apart.
"""
import datetime
import hashlib
import html
import http.server
import json
import os
import pathlib
import re
import shutil
import struct
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).parent
CONTENT, SRC, PHOTOS, STATIC, DIST = (ROOT / d for d in ("content", "src", "photos", "static", "dist"))

CONFIG = json.loads((CONTENT / "config.json").read_text(encoding="utf-8"))
DOMAIN = CONFIG["domain"]
LANGS = ["en", "fr"]
LANG_META = {
    "en": {"name": "English", "short": "EN", "locale": "en_GB"},
    "fr": {"name": "Français", "short": "FR", "locale": "fr_FR"},
}

LANG = "en"
BUILT = ["en"]   # languages this build actually produced: hreflang and the switcher only point at pages that exist
T = {}          # the current language's content tree
PAGES = []      # (url path, source mtime) collected for the sitemap
CUR_PATH = "/"


def load_lang(lang):
    """Every JSON under content/<lang>/ becomes T[<stem>]; subfolders become nested dicts."""
    global LANG, T
    LANG = lang
    base = CONTENT / lang
    T = {}
    for p in sorted(base.rglob("*.json")):
        rel = p.relative_to(base)
        node = T
        for part in rel.parts[:-1]:
            node = node.setdefault(part, {})
        node[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return T


def lp(path, lang=None):
    """Language-prefixed path: '/x' -> '/fr/x', '/' -> '/fr/'."""
    lang = lang or LANG
    if lang == "en":
        return path
    return f"/{lang}/" if path == "/" else f"/{lang}{path}"


def e(s):
    return html.escape(str(s), quote=True)


def seo_title(t, limit=60):
    """Brand suffix only when it fits; the keyword part must never be truncated in the SERP."""
    suffix = " | ROBOTMONACO"
    if "|" in t:
        return t
    return t + suffix if len(t + suffix) <= limit else t


# ---------------------------------------------------------------- assets
def image_size(path):
    """Width/height straight from the file header, so <img> can always carry dimensions."""
    try:
        data = path.read_bytes()[:64]
    except OSError:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        with open(path, "rb") as f:
            f.read(2)
            while True:
                b = f.read(1)
                while b and b != b"\xff":
                    b = f.read(1)
                marker = f.read(1)
                if not marker:
                    return None
                if marker[0] in range(0xC0, 0xCF) and marker[0] not in (0xC4, 0xC8, 0xCC):
                    f.read(3)
                    h, w = struct.unpack(">HH", f.read(4))
                    return w, h
                ln = struct.unpack(">H", f.read(2))[0]
                f.seek(ln - 2, 1)
    return None


def asset_version():
    h = hashlib.sha1()
    for f in sorted(SRC.rglob("*")):
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()[:8]


VER = asset_version()
LOGO = image_size(SRC / "img" / "logo.png") or (1400, 105)


def photo_url(path):
    """/assets/photos/<name>?v=<content hash>: a changed photo gets a new URL, so caches never go stale."""
    h = hashlib.md5(path.read_bytes()).hexdigest()[:8]
    return f"/assets/photos/{path.name}?v={h}"


def photo(name, alt, ratio="r-169", eager=False, label=None, cls=""):
    """Real photo if photos/<name>.* exists, otherwise a labelled slot with the same geometry."""
    found = {p.suffix.lower().lstrip("."): p for p in PHOTOS.glob(name + ".*")}
    classes = " ".join(c for c in ("ph", ratio, cls) if c)
    fallback = next((found[x] for x in ("jpg", "jpeg", "png", "webp") if x in found), None)
    if not fallback:
        return f'<div class="{classes}" data-empty data-label="{e(label or name)}" role="img" aria-label="{e(alt)}"></div>'
    size = image_size(fallback)
    dims = f' width="{size[0]}" height="{size[1]}"' if size else ""
    sources = "".join(f'<source srcset="{photo_url(found[x])}" type="image/{x}">' for x in ("avif", "webp") if x in found and found[x] != fallback)
    loading = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
    return f'<picture class="{classes}">{sources}<img src="{photo_url(fallback)}" alt="{e(alt)}"{dims} {loading}></picture>'


def stage(model, alt, ratio="r-45", label="", cls=""):
    """Interactive 3D robot. The viewer script and the GLB load only once the stage nears the viewport.
    The .glb is committed, so every build machine renders the stage, not a placeholder."""
    if os.environ.get("NO_3D") or not (SRC / "models" / f"{model}.glb").exists():
        return None      # NO_3D=1: a preview host that cannot serve .glb falls back to the hero photo
    classes = " ".join(c for c in ("ph", "stage", ratio, cls) if c)
    return (f'<div class="{classes}" data-model="/assets/models/{model}.glb?v={VER}" data-alt="{e(alt)}">'
            f'<span class="stage-hint">{e(label or T["ui"]["dragHint"])}</span></div>')


def og_for(name, default="/assets/photos/og-default.jpg"):
    for ext in ("jpg", "jpeg", "png"):
        if (PHOTOS / f"{name}.{ext}").exists():
            return photo_url(PHOTOS / f"{name}.{ext}")
    return default


_ICONS = {}


def icon(name):
    """Inline Lucide icon (ISC licence, src/icons/<name>.svg), stripped to its paths."""
    if not name:
        return ""
    if name not in _ICONS:
        f = SRC / "icons" / f"{name}.svg"
        body = f.read_text(encoding="utf-8") if f.exists() else ""
        inner = body[body.find(">", body.find("<svg")) + 1:body.rfind("</svg>")] if body else ""
        inner = re.sub(r"<title>.*?</title>", "", inner, flags=re.S)
        filled = 'role="img"' in body[:200]
        attrs = 'fill="currentColor"' if filled else 'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"'
        _ICONS[name] = f'<svg class="ic" viewBox="0 0 24 24" {attrs} aria-hidden="true">{inner.strip()}</svg>' if inner else ""
    return _ICONS[name]


# ---------------------------------------------------------------- schema
def ld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "</script>"


ORG_ID = DOMAIN + "/#organization"


def ld_org():
    a = CONFIG["areaServed"]
    return {
        "@context": "https://schema.org", "@type": ["Organization", "ProfessionalService"], "@id": ORG_ID,
        "name": CONFIG["brand"], "url": DOMAIN + "/", "email": CONFIG["email"], "telephone": CONFIG["phone"],
        "logo": DOMAIN + "/assets/img/logo.png",
        "description": T["ui"]["orgDescription"],
        "address": {"@type": "PostalAddress", "streetAddress": CONFIG["address"]["street"],
                    "postalCode": CONFIG["address"]["zip"], "addressLocality": CONFIG["address"]["city"],
                    "addressCountry": "MC"},
        "areaServed": [{"@type": "Country", "name": a[0]}] + [{"@type": "City", "name": c} for c in a[1:]],
        "knowsLanguage": ["en", "fr"],
        "sameAs": CONFIG.get("sameAs", []),
    }


def ld_crumbs(crumbs):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": DOMAIN + lp(h)} for i, (n, h) in enumerate(crumbs)]}


def ld_faq(faq):
    return {"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faq]}


def ld_service(name, desc, path, service_type):
    a = CONFIG["areaServed"]
    return {"@context": "https://schema.org", "@type": "Service", "name": name, "description": desc,
            "serviceType": service_type, "url": DOMAIN + lp(path), "provider": {"@id": ORG_ID},
            "areaServed": [{"@type": "Country", "name": a[0]}] + [{"@type": "City", "name": c} for c in a[1:]]}


# ---------------------------------------------------------------- chrome
def lang_switch(inline=False):
    if len(BUILT) < 2:
        return ""

    def href(l):
        return lp(CUR_PATH, l)
    if inline:
        links = "".join(f'<a href="{href(l)}" hreflang="{l}" lang="{l}"{" aria-current=true" if l == LANG else ""}>{LANG_META[l]["short"]}</a>' for l in BUILT)
        return f'<nav class="lang" aria-label="{e(T["ui"]["language"])}">{links}</nav>'
    items = "".join(f'<li><a href="{href(l)}" hreflang="{l}" lang="{l}"{" aria-current=true" if l == LANG else ""}><b>{LANG_META[l]["short"]}</b><span>{LANG_META[l]["name"]}</span></a></li>' for l in BUILT)
    return f'<details class="lang-dd"><summary aria-label="{e(T["ui"]["language"])}">{icon("globe")}<span>{LANG_META[LANG]["short"]}</span>{icon("chevron-down")}</summary><ul>{items}</ul></details>'


def nav(current):
    links = "".join(
        f'<li><a href="{lp(n["href"])}"{" aria-current=page" if n["href"] == current else ""}>{e(n["label"])}'
        f'{"<small>" + e(n["hint"]) + "</small>" if n.get("hint") else ""}</a></li>' for n in T["ui"]["nav"])
    return f"""<header class="nav"><div class="wrap">
<button class="burger" aria-label="{e(T['ui']['menu'])}" aria-expanded="false" aria-controls="menu"><span></span><span></span></button>
<a class="logo" href="{lp('/')}" aria-label="{e(CONFIG['brand'])}"><img src="/assets/img/logo.png" alt="{e(CONFIG['brand'])}" width="{LOGO[0]}" height="{LOGO[1]}" decoding="async"></a>
<div class="nav-end">{lang_switch()}<a class="btn btn-s btn-ink" href="{lp('/contact')}">{e(T['ui']['cta'])}</a></div>
</div>
<nav class="menu" id="menu" aria-label="{e(T['ui']['mainNav'])}"><div class="wrap"><ol class="menu-links">{links}</ol>
<div class="menu-foot"><a href="mailto:{e(CONFIG['email'])}">{e(CONFIG['email'])}</a><span>{e(T['ui']['tagline'])}</span>{lang_switch(inline=True)}</div></div></nav>
</header>"""


def footer():
    u, A = T["ui"], CONFIG["address"]
    cols = "".join(
        f'<div><h3>{e(c["h"])}</h3><ul>' + "".join(f'<li><a href="{lp(i["href"])}">{e(i["label"])}</a></li>' for i in c["items"]) + "</ul></div>"
        for c in u["footerCols"])
    year = datetime.date.today().year
    return f"""<footer class="footer"><div class="wrap">
<div class="footer-top">
<p class="footer-claim">{e(u['footerClaim'])}</p>
<div class="footer-contact"><a class="footer-mail" href="mailto:{e(CONFIG['email'])}">{e(CONFIG['email'])}</a>
<p><a href="tel:{e(CONFIG['phoneHref'])}">{e(CONFIG['phone'])}</a></p>
<a class="btn" href="{lp('/contact')}">{e(u['cta'])}</a></div>
</div>
<div class="footer-dir">{cols}</div>
</div>
<div class="wrap footer-brand">
<a class="footer-mark" href="{lp('/')}" aria-label="{e(CONFIG['brand'])}"><img src="/assets/img/logo-white.png" alt="{e(CONFIG['brand'])}" width="{LOGO[0]}" height="{LOGO[1]}" loading="lazy"></a>
</div>
<div class="wrap footer-company"><p><span>{e(A['street'])}, {e(A['zip'])} {e(A['city'])}</span> · <span>{e(A['region'])}</span> · <a href="tel:{e(CONFIG['phoneHref'])}">{e(CONFIG['phone'])}</a></p></div>
<div class="wrap footer-legal"><span>© {year} {e(CONFIG['brand'])}</span><span>{e(u['tagline'])}</span>
<a href="https://robotrental.sk/" rel="noopener">{e(u['partner'])}</a><a href="{lp('/privacy')}">{e(u['privacy'])}</a><a href="mailto:{e(CONFIG['email'])}">{e(CONFIG['email'])}</a></div>
</footer>"""


# ---------------------------------------------------------------- shared sections
def whatsapp_fab():
    """A floating WhatsApp button on every page. The number is the office one, and the message is
    prefilled so an enquiry arrives with its context instead of a bare hello."""
    w = T["ui"].get("whatsapp")
    if not w:
        return ""
    href = "https://wa.me/" + CONFIG["phoneHref"].lstrip("+") + "?text=" + urllib.parse.quote(w["text"])
    return (f'<a class="wa-fab" href="{href}" target="_blank" rel="noopener" aria-label="{e(w["label"])}">'
            f'{icon("whatsapp")}<span>{e(w["label"])}</span></a>')


def crumbs_html(crumbs):
    items = "".join(f"<li>{e(n)}</li>" if i == len(crumbs) - 1 else f'<li><a href="{lp(h)}">{e(n)}</a></li>' for i, (n, h) in enumerate(crumbs))
    return f'<nav aria-label="{e(T["ui"]["breadcrumb"])}" class="wrap"><ol class="crumbs">{items}</ol></nav>'


def cells(items, cls=""):
    return "".join(f'<div class="cell {cls} reveal" style="--i:{i % 4}">{icon(c.get("icon"))}<h3>{e(c["h"])}</h3><p>{e(c["p"])}</p></div>' for i, c in enumerate(items))


def steps(items):
    return "".join(f'<div class="step reveal" style="--i:{i}"><h3 class="t-h3">{e(s["h"])}</h3><p>{e(s["p"])}</p></div>' for i, s in enumerate(items))


def stats(pairs):
    return "".join(f'<div class="stat"><b>{e(v)}</b><span>{e(k)}</span></div>' for v, k in pairs)


def dir_tiles(items):
    return '<div class="dir">' + "".join(
        f'<a class="dir-item reveal" style="--i:{i % 3}" href="{lp(x["path"])}"><h3>{e(x["label"])}</h3><p>{e(x["teaser"])}</p></a>'
        for i, x in enumerate(items)) + "</div>"


def paddles(prev_label, next_label):
    """The two round scroll buttons for a rail. app.js finds them by .paddle inside the same <section>."""
    return (f'<button class="paddle" type="button" aria-label="{e(prev_label)}">{icon("arrow-left")}</button>'
            f'<button class="paddle" type="button" aria-label="{e(next_label)}">{icon("arrow-right")}</button>')


def video_section(dark=True):
    """A click-to-play facade for the YouTube film. Nothing loads from YouTube until the visitor asks for it,
    which keeps the page fast and sets no third-party cookie on arrival."""
    v = T["ui"].get("video")
    if not v:
        return ""
    src = f"https://www.youtube-nocookie.com/embed/{v['id']}?autoplay=1&rel=0&modestbranding=1"
    return f"""
<section class="section {'dark' if dark else ''}" id="video"><div class="wrap">
<div class="section-head reveal center"><h2 class="t-h2">{e(v['h2'])}</h2><p class="t-lead">{e(v['lead'])}</p></div>
<div class="video reveal" data-src="{e(src)}">
<button class="video-play" type="button" aria-label="{e(v['play'])}">
{photo('video-poster', v['alt'], 'r-169')}
<span class="video-btn">{icon('play')}</span></button>
</div>
<p class="video-credit t-small">{e(v['credit'])}</p>
</div></section>
"""


def gallery_strip(bg="tilebg"):
    """A rail of photographs of the robot. The lead and the credit keep the two sources apart: our own
    pictures come first, the manufacturer's follow, and neither is passed off as the other."""
    g = T["ui"].get("gallery")
    if not g:
        return ""
    cards = "".join(
        f'<figure class="card gal-card reveal">{photo(i["file"], i["alt"], "")}'
        f'<figcaption class="card-copy"><p class="t-small">{e(i["caption"])}</p></figcaption></figure>'
        for i in g["items"])
    return f"""
<section class="section {bg}" id="photos"><div class="wrap">
<div class="head-row reveal"><div class="section-head"><h2 class="t-h2">{e(g['h2'])}</h2><p class="t-lead">{e(g['lead'])}</p></div>
<div class="paddles">{paddles(T['ui']['prev'], T['ui']['next'])}</div></div>
</div><div class="gallery"><div class="rail">{cards}</div></div>
<div class="wrap"><p class="rail-credit t-small">{e(g['credit'])}</p></div></section>
"""


def faq_section(faq, h2=None, bg=""):
    rows = "".join(f"<details><summary>{e(f['q'])}</summary><p>{e(f['a'])}</p></details>" for f in faq)
    u = T["ui"]
    return f"""<section class="section {bg}" id="faq"><div class="wrap faq">
<div class="reveal"><h2 class="t-h2">{e(h2 or u['faqH2'])}</h2><p class="t-lead" style="margin-top:20px">{e(u['faqLead'])}</p>
<div class="actions"><a class="link" href="{lp('/contact')}">{e(u['faqCta'])}</a></div></div>
<div class="faq-list reveal" style="--i:1">{rows}</div>
</div></section>"""


def contact_section(h2=None, p=None, preset="", dark=False, on_white=False):
    u = T["ui"]
    c = T["ui"]["contact"]
    section_cls = "section dark contact-dark" if dark else ("section" if on_white else "section tilebg")
    form_style = "--i:1;background:var(--tile)" if on_white else "--i:1"
    types = "".join(f'<option{" selected" if t == preset else ""}>{e(t)}</option>' for t in c["types"])
    return f"""<section class="{section_cls}" id="contact"><div class="wrap contact">
<div class="reveal"><h2 class="t-h2">{e(h2 or c['h2'])}</h2><p class="t-lead" style="margin-top:20px">{e(p or c['p'])}</p>
<dl class="contact-meta"><div><dt>{e(c['emailLabel'])}</dt><dd><a href="mailto:{e(CONFIG['email'])}">{e(CONFIG['email'])}</a></dd></div>
<div><dt>{e(c['phoneLabel'])}</dt><dd><a href="tel:{e(CONFIG['phoneHref'])}">{e(CONFIG['phone'])}</a></dd></div>
<div><dt>{e(c['areaLabel'])}</dt><dd>{e(c['areaValue'])}</dd></div>
<div><dt>{e(c['replyLabel'])}</dt><dd>{e(c['replyValue'])}</dd></div></dl></div>
<form class="form reveal" style="{form_style}" data-lead action="/send.php" method="post">
<div class="field"><label for="f-name">{e(c['name'])}</label><input id="f-name" name="Name" autocomplete="name" required></div>
<div class="field"><label for="f-company">{e(c['company'])}</label><input id="f-company" name="Company" autocomplete="organization"></div>
<div class="field"><label for="f-email">{e(c['email'])}</label><input id="f-email" name="E-mail" type="email" autocomplete="email" required></div>
<div class="field"><label for="f-phone">{e(c['phoneField'])}</label><input id="f-phone" name="Phone" type="tel" autocomplete="tel"></div>
<div class="field"><label for="f-date">{e(c['date'])}</label><input id="f-date" name="Date" type="date"></div>
<div class="field"><label for="f-place">{e(c['place'])}</label><input id="f-place" name="Place"></div>
<div class="field full"><label for="f-type">{e(c['type'])}</label><select id="f-type" name="Type"><option value="">{e(c['choose'])}</option>{types}</select></div>
<div class="field full"><label for="f-msg">{e(c['message'])}</label><textarea id="f-msg" name="Message" placeholder="{e(c['messageHint'])}"></textarea></div>
<label class="consent"><input type="checkbox" name="Consent" value="yes" required><span>{e(c['consent'])} <a href="{lp('/privacy')}">{e(u['privacy'])}</a>.</span></label>
<button class="btn" type="submit">{e(c['submit'])}</button>
<p class="form-ok" role="status">{e(c['ok'])}</p>
<p class="form-err" role="alert">{e(c['err'])} {e(CONFIG['email'])}.</p>
</form></div></section>"""


# ---------------------------------------------------------------- page funnel
def page(path, title, desc, body, schema, current="", og_image=None, src_files=()):
    global CUR_PATH
    CUR_PATH = path
    url = DOMAIN + lp(path)
    og_image = og_image or og_for("og-default")
    alternates = ("".join(f'<link rel="alternate" hreflang="{l}" href="{DOMAIN}{lp(path, l)}">' for l in BUILT)
                  + f'<link rel="alternate" hreflang="x-default" href="{DOMAIN}{lp(path, "en")}">') if len(BUILT) > 1 else ""
    doc = f"""<!doctype html>
<html lang="{LANG}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
{alternates}
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:type" content="website">
<meta property="og:locale" content="{LANG_META[LANG]['locale']}">
<meta property="og:site_name" content="{e(CONFIG['brand'])}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{e(DOMAIN + og_image.split('?')[0])}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#ffffff">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<script>try{{if(sessionStorage.getItem("rr-loaded"))document.documentElement.classList.add("no-loader")}}catch(e){{}}</script>
<link rel="preload" href="/assets/fonts/space-grotesk-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/styles.css?v={VER}">
<script src="/assets/app.js?v={VER}" defer></script>
{"".join(ld(s) for s in schema)}
</head>
<body>
<div class="loader" aria-hidden="true"><div class="loader-mark"><img src="/assets/img/logo.png" alt="" width="{LOGO[0]}" height="{LOGO[1]}"><span class="loader-shine"></span></div><span class="loader-bar"></span></div>
<a class="sr" href="#main">{e(T['ui']['skip'])}</a>
{nav(current)}
<main id="main">
{body}
</main>
{footer()}
{whatsapp_fab()}
</body>
</html>
"""
    lpath = lp(path)
    out = DIST / ("index.html" if lpath == "/" else lpath.strip("/") + ("/index.html" if lpath.endswith("/") else ".html"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    mtimes = [f.stat().st_mtime for f in src_files if f.exists()]
    PAGES.append((lpath, max(mtimes) if mtimes else None))


# ---------------------------------------------------------------- pages
def robot_by_slug(slug):
    return next(r for r in CONFIG["robots"] if r["slug"] == slug)


def price_line(kind):
    u = T["ui"]
    amount = u.get("prices", {}).get(kind) or CONFIG["prices"][kind]["amount"]   # each language writes the figure its own way
    return f'<p class="from"><span>{e(u["from"])}</span> <b>{e(amount)}</b> <span>{e(u["perDay"])}</span> <small>{e(u["priceNote"])}</small></p>'


def build_home():
    d = T["home"]
    hero_robot = robot_by_slug(d["heroRobot"])
    tiles = "".join(
        f"""<article class="tile{' is-dark' if r['tone'] == 'dark' else ''} reveal" style="--i:{i}">
<div class="tile-copy"><p class="t-eyebrow">{e(r['model'])}</p><h3>{e(T['robots'][r['slug']]['name'])}</h3><p>{e(T['robots'][r['slug']]['tagline'])}</p>
<div class="actions"><a class="btn" href="{lp('/robots/' + r['slug'])}">{e(T['ui']['rentFrom'])} {e(T['ui']['prices'][r['priceKind']])}</a></div>
<p class="t-small">{e(T['ui']['perDayOperator'])} · {e(T['ui']['robotValue'])} {e(T['ui']['values'][r['slug']])}</p></div>
{photo(r['slug'] + '-tile', T['robots'][r['slug']]['alt'], 'r-43', cls='on-dark' if r['tone'] == 'dark' else '')}
</article>""" for i, r in enumerate(CONFIG["robots"]))
    uses = [{"path": "/use-cases/" + s, "label": T["use-cases"][s]["label"], "teaser": T["use-cases"][s]["teaser"]}
            for s in CONFIG["useCaseOrder"][:6]]
    body = f"""<section class="hero"><div class="wrap">
<p class="t-eyebrow">{e(d['eyebrow'])}</p>
<h1 class="t-hero">{e(d['h1'])}</h1>
<p class="t-lead">{e(d['lead'])}</p>
<div class="actions"><a class="btn" href="{lp('/contact')}">{e(T['ui']['cta'])}</a><a class="link" href="{lp('/robots')}">{e(T['ui']['seeFleet'])}</a><a class="link" href="{lp('/use-cases')}">{e(d['ctaSecondary'])}</a></div>
</div>
<div class="hero-media">{stage('montari', d['heroAlt'], 'r-219') or photo('hero', d['heroAlt'], 'r-219', eager=True)}</div>
</section>

<section class="section" id="fleet" style="padding-top:clamp(48px,6vw,88px)"><div class="wrap">
<div class="section-head reveal center"><h2 class="t-h2">{e(d['fleet']['h2'])}</h2><p class="t-lead">{e(d['fleet']['lead'])}</p></div>
<div class="tiles">{tiles}</div>
<div class="center reveal" style="margin-top:clamp(32px,4vw,56px)">
<div class="actions"><a class="btn" href="{lp('/contact')}">{e(T['ui']['rentCta'])}</a><a class="link" href="{lp('/pricing')}">{e(T['ui']['seePricing'])}</a></div>
</div></div></section>

<section class="section" style="padding-top:0"><div class="wrap"><div class="stats reveal">{stats(d['stats'])}</div></div></section>

<section class="section tilebg" id="why"><div class="wrap">
<div class="section-head reveal"><h2 class="t-h2">{e(d['why']['h2'])}</h2><p class="t-lead">{e(d['why']['lead'])}</p></div>
<div class="grid-3">{cells(d['why']['items'])}</div>
</div></section>

<section class="section dark" id="use-cases"><div class="wrap">
<div class="section-head reveal"><h2 class="t-h2">{e(d['uses']['h2'])}</h2><p class="t-lead">{e(d['uses']['lead'])}</p></div>
{dir_tiles(uses)}
<div class="actions reveal" style="margin-top:32px"><a class="link" href="{lp('/use-cases')}">{e(d['uses']['cta'])}</a></div>
</div></section>

{gallery_strip()}

<section class="section"><div class="wrap">
<div class="section-head reveal"><h2 class="t-h2">{e(d['how']['h2'])}</h2></div>
<div class="steps s4">{steps(d['how']['steps'])}</div>
</div></section>

{video_section()}

<section class="section tilebg"><div class="wrap">
<div class="band reveal">{photo('software', d['software']['alt'], 'r-219')}<div class="band-copy"><h3>{e(d['software']['h3'])}</h3><p>{e(d['software']['p'])}</p>
<div class="actions"><a class="link" href="{lp('/services/robot-software-development')}">{e(d['software']['cta'])}</a></div></div></div>
</div></section>

{faq_section(d['faq'])}
{contact_section(dark=True)}"""
    schema = [ld_org(), ld_service(d["h1"], d["desc"], "/", T["ui"]["serviceType"]), ld_faq(d["faq"]),
              {"@context": "https://schema.org", "@type": "WebSite", "name": CONFIG["brand"], "url": DOMAIN + lp("/"),
               "inLanguage": LANG, "publisher": {"@id": ORG_ID}}]
    page("/", seo_title(d["title"]), d["desc"], body, schema, current="/", og_image=og_for("hero"),
         src_files=[CONTENT / LANG / "home.json"])


def build_robots_hub():
    d = T["robots"]["_hub"]
    items = [{"path": "/robots/" + r["slug"], "label": f"{T['robots'][r['slug']]['name']} · {r['model']}",
              "teaser": T["robots"][r["slug"]]["teaser"]} for r in CONFIG["robots"]]
    crumbs = [(T["ui"]["home"], "/"), (d["crumb"], "/robots")]
    body = f"""{crumbs_html(crumbs)}
<section class="phero"><div class="wrap"><p class="t-eyebrow">{e(d['eyebrow'])}</p>
<h1 class="t-hero">{e(d['h1'])}</h1><p class="t-lead">{e(d['lead'])}</p></div></section>
<section class="section" style="padding-top:0"><div class="wrap">{dir_tiles(items)}</div></section>
{faq_section(d['faq'], bg='tilebg')}
{contact_section(dark=True)}"""
    schema = [ld_org(), ld_crumbs(crumbs), ld_faq(d["faq"]),
              {"@context": "https://schema.org", "@type": "CollectionPage", "name": d["h1"], "url": DOMAIN + lp("/robots"),
               "hasPart": [{"@type": "WebPage", "name": i["label"], "url": DOMAIN + lp(i["path"])} for i in items]}]
    page("/robots", seo_title(d["title"]), d["desc"], body, schema, current="/robots", src_files=[CONTENT / LANG / "robots.json"])


def build_robot(r):
    d = T["robots"][r["slug"]]
    path = "/robots/" + r["slug"]
    crumbs = [(T["ui"]["home"], "/"), (T["robots"]["_hub"]["crumb"], "/robots"), (d["name"], path)]
    specs = "".join(f'<div class="stat"><b>{e(v)}</b><span>{e(k)}</span></div>' for k, v in d["specs"])
    body = f"""{crumbs_html(crumbs)}
<section class="phero split"><div class="wrap split-grid">
<div class="split-copy"><p class="t-eyebrow">{e(r['model'])}</p>
<h1 class="t-hero">{e(d['h1'])}</h1><p class="t-lead">{e(d['lead'])}</p>
{price_line(r['priceKind'])}
<div class="actions"><a class="btn" href="{lp('/contact')}">{e(T['ui']['cta'])}</a><a class="link" href="{lp('/use-cases')}">{e(T['ui']['seeUses'])}</a></div></div>
{photo(r['slug'] + '-hero', d['alt'], 'r-45', eager=True, cls='split-photo')}
</div></section>

<section class="section" style="padding-top:0"><div class="wrap"><div class="stats reveal">{specs}</div></div></section>

{gallery_strip()}

<section class="section dark" id="branding" style="padding-top:clamp(48px,6vw,88px)"><div class="wrap">
<div class="section-head reveal center"><h2 class="t-h2">{e(T['ui']['branding']['h2'])}</h2><p class="t-lead">{e(T['ui']['branding']['p'])}</p></div>
</div>
<div class="hero-media">{stage('montari-branding', T['ui']['branding']['alt'], 'r-219') or photo(r['slug'] + '-hero', T['ui']['branding']['alt'], 'r-219')}</div>
</section>

<section class="section tilebg"><div class="wrap">
<div class="section-head reveal"><h2 class="t-h2">{e(d['does']['h2'])}</h2></div>
<div class="grid-3">{cells(d['does']['items'])}</div>
</div></section>

<section class="section"><div class="wrap"><div class="row reveal">
{photo(r['slug'] + '-hero', d['alt'], 'r-45')}
<div class="row-copy"><h2 class="t-h2">{e(d['fit']['h2'])}</h2><p class="t-lead">{e(d['fit']['lead'])}</p>
<ul class="ticks">{''.join(f'<li>{e(x)}</li>' for x in d['fit']['list'])}</ul></div></div></div></section>

{video_section()}

{faq_section(d['faq'], bg='tilebg')}
{contact_section(preset=d.get('preset', ''), dark=True)}"""
    schema = [ld_org(), ld_crumbs(crumbs), ld_service(d["h1"], d["desc"], path, T["ui"]["serviceType"]), ld_faq(d["faq"])]
    page(path, seo_title(d["title"]), d["desc"], body, schema, current="/robots", og_image=og_for(r["slug"] + "-hero"),
         src_files=[CONTENT / LANG / "robots.json"])


def build_uses_hub():
    d = T["use-cases"]["_hub"]
    items = [{"path": "/use-cases/" + s, "label": T["use-cases"][s]["label"], "teaser": T["use-cases"][s]["teaser"]}
             for s in CONFIG["useCaseOrder"]]
    crumbs = [(T["ui"]["home"], "/"), (d["crumb"], "/use-cases")]
    body = f"""{crumbs_html(crumbs)}
<section class="phero"><div class="wrap"><p class="t-eyebrow">{e(d['eyebrow'])}</p>
<h1 class="t-hero">{e(d['h1'])}</h1><p class="t-lead">{e(d['lead'])}</p></div></section>
<section class="section" style="padding-top:0"><div class="wrap">{dir_tiles(items)}</div></section>
{faq_section(d['faq'], bg='tilebg')}
{contact_section(dark=True)}"""
    schema = [ld_org(), ld_crumbs(crumbs), ld_faq(d["faq"]),
              {"@context": "https://schema.org", "@type": "CollectionPage", "name": d["h1"], "url": DOMAIN + lp("/use-cases"),
               "hasPart": [{"@type": "WebPage", "name": i["label"], "url": DOMAIN + lp(i["path"])} for i in items]}]
    page("/use-cases", seo_title(d["title"]), d["desc"], body, schema, current="/use-cases", src_files=[CONTENT / LANG / "use-cases.json"])


def build_use_case(slug):
    d = T["use-cases"][slug]
    path = "/use-cases/" + slug
    crumbs = [(T["ui"]["home"], "/"), (T["use-cases"]["_hub"]["crumb"], "/use-cases"), (d["label"], path)]
    others = [{"path": "/use-cases/" + s, "label": T["use-cases"][s]["label"], "teaser": T["use-cases"][s]["teaser"]}
              for s in d["related"]]
    intro = "".join(f"<p>{e(x)}</p>" for x in d["intro"]["p"])
    body = f"""{crumbs_html(crumbs)}
<section class="phero split"><div class="wrap split-grid">
<div class="split-copy"><p class="t-eyebrow">{e(d['eyebrow'])}</p>
<h1 class="t-hero" style="font-size:clamp(38px,5.4vw,76px)">{e(d['h1'])}</h1><p class="t-lead">{e(d['lead'])}</p>
<div class="actions"><a class="btn" href="{lp('/contact')}">{e(T['ui']['cta'])}</a><a class="link" href="{lp('/robots')}">{e(T['ui']['seeFleet'])}</a></div></div>
{photo(d['photo'], d['alt'], 'r-45', eager=True, cls='split-photo')}
</div></section>

<section class="section" style="padding-top:0"><div class="wrap"><div class="prose reveal"><h2>{e(d['intro']['h2'])}</h2>{intro}</div></div></section>

<section class="section tilebg"><div class="wrap">
<div class="section-head reveal"><h2 class="t-h2">{e(d['ideas']['h2'])}</h2></div>
<div class="grid-3">{cells(d['ideas']['items'])}</div>
</div></section>

<section class="section"><div class="wrap"><div class="row reveal">
{photo(d.get('photo2', d['photo']), d['alt'], 'r-45')}
<div class="row-copy"><h2 class="t-h2">{e(d['included']['h2'])}</h2><p class="t-lead">{e(d['included']['lead'])}</p>
<ul class="ticks">{''.join(f'<li>{e(x)}</li>' for x in d['included']['list'])}</ul></div></div></div></section>

<section class="section dark"><div class="wrap">
<div class="section-head reveal"><h2 class="t-h2">{e(T['ui']['relatedUses'])}</h2></div>
{dir_tiles(others)}
</div></section>

{faq_section(d['faq'])}
{contact_section(preset=d.get('preset', ''), dark=True)}"""
    schema = [ld_org(), ld_crumbs(crumbs), ld_service(d["h1"], d["desc"], path, T["ui"]["serviceType"]), ld_faq(d["faq"])]
    page(path, seo_title(d["title"]), d["desc"], body, schema, current="/use-cases", og_image=og_for(d["photo"]),
         src_files=[CONTENT / LANG / "use-cases.json"])


def build_service(slug):
    d = T["services"][slug]
    path = "/services/" + slug
    crumbs = [(T["ui"]["home"], "/"), (d["label"], path)]
    intro = "".join(f"<p>{e(x)}</p>" for x in d["intro"]["p"])
    body = f"""{crumbs_html(crumbs)}
<section class="phero split"><div class="wrap split-grid">
<div class="split-copy"><p class="t-eyebrow">{e(d['eyebrow'])}</p>
<h1 class="t-hero" style="font-size:clamp(38px,5.4vw,76px)">{e(d['h1'])}</h1><p class="t-lead">{e(d['lead'])}</p>
<div class="actions"><a class="btn" href="{lp('/contact')}">{e(T['ui']['cta'])}</a></div></div>
{photo(d['photo'], d['alt'], 'r-45', eager=True, cls='split-photo')}
</div></section>

<section class="section" style="padding-top:0"><div class="wrap"><div class="prose reveal"><h2>{e(d['intro']['h2'])}</h2>{intro}</div></div></section>

<section class="section tilebg"><div class="wrap">
<div class="section-head reveal"><h2 class="t-h2">{e(d['features']['h2'])}</h2></div>
<div class="grid-3">{cells(d['features']['items'])}</div>
</div></section>

<section class="section"><div class="wrap"><div class="row reveal">
{photo(d.get('photo2', d['photo']), d['alt'], 'r-45')}
<div class="row-copy"><h2 class="t-h2">{e(d['scope']['h2'])}</h2><p class="t-lead">{e(d['scope']['lead'])}</p>
<ul class="ticks">{''.join(f'<li>{e(x)}</li>' for x in d['scope']['list'])}</ul></div></div>
<div class="section-head reveal" style="margin-top:clamp(48px,6vw,88px)"><h2 class="t-h2">{e(d['process']['h2'])}</h2></div>
<div class="steps s4">{steps(d['process']['steps'])}</div>
</div></section>

{faq_section(d['faq'], bg='tilebg')}
{contact_section(preset=d.get('preset', ''), dark=True)}"""
    schema = [ld_org(), ld_crumbs(crumbs), ld_service(d["h1"], d["desc"], path, d["label"]), ld_faq(d["faq"])]
    page(path, seo_title(d["title"]), d["desc"], body, schema, og_image=og_for(d["photo"]), src_files=[CONTENT / LANG / "services.json"])


def build_pricing():
    d = T["pricing"]
    crumbs = [(T["ui"]["home"], "/"), (d["crumb"], "/pricing")]
    cards = "".join(
        f"""<div class="cell reveal" style="--i:{i}"><span class="cell-n">{e(c['k'])}</span><h3>{e(c['h'])}</h3>
<p class="from"><b>{e(c['amount'])}</b> <span>{e(c['unit'])}</span></p><p>{e(c['p'])}</p>
<ul class="ticks">{''.join(f'<li>{e(x)}</li>' for x in c['list'])}</ul></div>""" for i, c in enumerate(d["cards"]))
    body = f"""{crumbs_html(crumbs)}
<section class="phero"><div class="wrap"><p class="t-eyebrow">{e(d['eyebrow'])}</p>
<h1 class="t-hero">{e(d['h1'])}</h1><p class="t-lead">{e(d['lead'])}</p></div></section>
<section class="section" style="padding-top:0"><div class="wrap"><div class="grid-3">{cards}</div>
<div class="prose reveal" style="margin-top:clamp(48px,6vw,80px)"><h2>{e(d['includes']['h2'])}</h2>
<ul>{''.join(f'<li>{e(x)}</li>' for x in d['includes']['list'])}</ul></div></div></section>
{faq_section(d['faq'], bg='tilebg')}
{contact_section(dark=True)}"""
    schema = [ld_org(), ld_crumbs(crumbs), ld_faq(d["faq"])]
    page("/pricing", seo_title(d["title"]), d["desc"], body, schema, current="/pricing", src_files=[CONTENT / LANG / "pricing.json"])


def build_faq_page():
    d = T["faq"]
    crumbs = [(T["ui"]["home"], "/"), (d["crumb"], "/faq")]
    groups = "".join(
        f"""<section class="section {'tilebg' if i % 2 else ''}"><div class="wrap faq">
<div class="reveal"><h2 class="t-h2">{e(g['h2'])}</h2></div>
<div class="faq-list reveal" style="--i:1">{''.join(f"<details><summary>{e(f['q'])}</summary><p>{e(f['a'])}</p></details>" for f in g['items'])}</div>
</div></section>""" for i, g in enumerate(d["groups"]))
    body = f"""{crumbs_html(crumbs)}
<section class="phero"><div class="wrap"><p class="t-eyebrow">{e(d['eyebrow'])}</p>
<h1 class="t-hero">{e(d['h1'])}</h1><p class="t-lead">{e(d['lead'])}</p></div></section>
{groups}
{contact_section(dark=True)}"""
    allq = [f for g in d["groups"] for f in g["items"]]
    schema = [ld_org(), ld_crumbs(crumbs), ld_faq(allq)]
    page("/faq", seo_title(d["title"]), d["desc"], body, schema, current="/faq", src_files=[CONTENT / LANG / "faq.json"])


def build_contact():
    d = T["contactPage"]
    crumbs = [(T["ui"]["home"], "/"), (d["crumb"], "/contact")]
    body = f"""{crumbs_html(crumbs)}
<section class="phero"><div class="wrap"><p class="t-eyebrow">{e(d['eyebrow'])}</p>
<h1 class="t-hero">{e(d['h1'])}</h1><p class="t-lead">{e(d['lead'])}</p></div></section>
{contact_section(h2=d['formH2'], p=d['formP'], on_white=True)}
{faq_section(d['faq'], bg='tilebg')}"""
    schema = [ld_org(), ld_crumbs(crumbs), ld_faq(d["faq"]),
              {"@context": "https://schema.org", "@type": "ContactPage", "name": d["h1"], "url": DOMAIN + lp("/contact")}]
    page("/contact", seo_title(d["title"]), d["desc"], body, schema, current="/contact", src_files=[CONTENT / LANG / "contactPage.json"])


def build_privacy():
    d = T["privacy"]
    crumbs = [(T["ui"]["home"], "/"), (d["crumb"], "/privacy")]
    blocks = "".join(f"<h2>{e(s['h2'])}</h2>" + "".join(f"<p>{e(p)}</p>" for p in s["p"]) for s in d["sections"])
    body = f"""{crumbs_html(crumbs)}
<section class="phero"><div class="wrap"><p class="t-eyebrow">{e(d['eyebrow'])}</p><h1 class="t-hero" style="font-size:clamp(36px,4.6vw,64px)">{e(d['h1'])}</h1></div></section>
<section class="section" style="padding-top:0"><div class="wrap"><div class="prose reveal">{blocks}</div></div></section>"""
    page("/privacy", seo_title(d["title"]), d["desc"], body, [ld_org(), ld_crumbs(crumbs)], src_files=[CONTENT / LANG / "privacy.json"])


# ---------------------------------------------------------------- site files
def write_sitemap():
    groups = {}
    for path, mtime in PAGES:
        m = re.match(r"^/(fr)(/.*)?$", path)
        lang, base = (m.group(1), m.group(2) or "/") if m else ("en", path)
        groups.setdefault(base, {})[lang] = (path, mtime)
    rows = []
    for b in sorted(groups):
        alts = groups[b]
        links = "".join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{DOMAIN}{alts[l][0]}"/>' for l in LANGS if l in alts)
        if "en" in alts:
            links += f'<xhtml:link rel="alternate" hreflang="x-default" href="{DOMAIN}{alts["en"][0]}"/>'
        for l in LANGS:
            if l not in alts:
                continue
            path, mtime = alts[l]
            lastmod = f"<lastmod>{datetime.date.fromtimestamp(mtime).isoformat()}</lastmod>" if mtime else ""
            rows.append(f"<url><loc>{DOMAIN}{path}</loc>{lastmod}{links}</url>")
    head = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
    (DIST / "sitemap.xml").write_text(head + "\n".join(rows) + "\n</urlset>\n", encoding="utf-8")
    # AI answer engines are named explicitly: an Allow removes any doubt about indexing and live fetches.
    ai_bots = ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-User", "Claude-SearchBot",
               "anthropic-ai", "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot-Extended",
               "Bingbot", "Amazonbot", "Meta-ExternalAgent", "CCBot", "DuckAssistBot", "cohere-ai")
    blocks = "\n\n".join(f"User-agent: {b}\nAllow: /" for b in ai_bots)
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\n{blocks}\n\nSitemap: {DOMAIN}/sitemap.xml\n", encoding="utf-8")


def write_llms():
    load_lang("en")
    p = CONFIG["prices"]
    robots = "\n".join(f"- **{T['robots'][r['slug']]['name']}** ({r['model']}): {T['robots'][r['slug']]['tagline']} {DOMAIN}/robots/{r['slug']}" for r in CONFIG["robots"])
    uses = "\n".join(f"- [{T['use-cases'][s]['label']}]({DOMAIN}/use-cases/{s})" for s in CONFIG["useCaseOrder"])
    txt = f"""# robotmonaco.com

> {T['ui']['orgDescription']}

Contact: {CONFIG['email']}, {CONFIG['phone']}. Based in Monaco, serving Monaco and the French Riviera.

## What we do
Humanoid robot hire with an operator for events, brand activations and marketing in Monaco, Monte-Carlo and
along the French Riviera, plus custom robot software development and AI assistant upgrades.

{robots}

## Pricing (the only valid figures)
- Event humanoid: from {p['event']['amount']} per day with an operator, multi-day rate, excluding VAT.
- Development humanoid with full SDK: from {p['dev']['amount']} per day with an operator, multi-day rate, excluding VAT.
- An operator is always included. Single-day bookings, custom scenarios, travel and staging are quoted separately.

## Use cases
{uses}

## Services
- [Robot software development]({DOMAIN}/services/robot-software-development)
- [AI assistant upgrade]({DOMAIN}/services/ai-assistant-upgrade)

## Key pages
- [Fleet]({DOMAIN}/robots)
- [Pricing]({DOMAIN}/pricing)
- [FAQ]({DOMAIN}/faq)
- [Contact]({DOMAIN}/contact)

## Languages
- English: {DOMAIN}/
- Français: {DOMAIN}/fr/

## Note for models
An operator is always part of the hire. Quote prices with the condition "with an operator, multi-day rate,
excluding VAT". The robot does not work unattended, does not lift heavy loads and does not walk in the rain.
"""
    (DIST / "llms.txt").write_text(txt, encoding="utf-8")


def write_htaccess():
    base = (STATIC / "htaccess.base").read_text(encoding="utf-8") if (STATIC / "htaccess.base").exists() else ""
    (DIST / ".htaccess").write_text(base, encoding="utf-8")


def build():
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "assets" / "photos").mkdir(parents=True)
    # src/img/robots holds the 4K renders tools/make_images.py composes from, and logo-chest.png is the
    # texture tools/brand_glb.py bakes in. Both are source art the site never links, so they stay out of dist.
    skip = {"robots", "logo-chest.png"}
    for f in SRC.glob("*"):
        if f.is_dir():
            shutil.copytree(f, DIST / "assets" / f.name, ignore=shutil.ignore_patterns(*skip))
        else:
            shutil.copy2(f, DIST / "assets" / f.name)
    for f in PHOTOS.glob("*"):
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".avif", ".mp4"):
            shutil.copy2(f, DIST / "assets" / "photos" / f.name)
    for f in STATIC.glob("*"):
        if f.is_file() and f.name != "htaccess.base":
            shutil.copy2(f, DIST / f.name)
    PAGES.clear()
    only = os.environ.get("LANGS")            # LANGS=en python3 build.py, to preview one language
    # A language ships once its own content tree is complete, so a half-finished translation can never
    # break the build or advertise hreflang links to pages that do not exist yet.
    complete = [l for l in LANGS if {p.name for p in (CONTENT / "en").glob("*.json")} <= {p.name for p in (CONTENT / l).glob("*.json")}]
    langs = [l for l in complete if not only or l in only.split(",")]
    global BUILT
    BUILT = langs
    for lang in langs:
        load_lang(lang)
        build_home()
        build_robots_hub()
        for r in CONFIG["robots"]:
            build_robot(r)
        build_uses_hub()
        for s in CONFIG["useCaseOrder"]:
            build_use_case(s)
        for s in CONFIG["serviceOrder"]:
            build_service(s)
        build_pricing()
        build_faq_page()
        build_contact()
        build_privacy()
    write_sitemap()
    write_llms()
    write_htaccess()
    print(f"built {len(PAGES)} pages in {len(langs)} languages -> {DIST}")


class CleanURLHandler(http.server.SimpleHTTPRequestHandler):
    """Mirrors the production .htaccess rule /x -> /x.html."""

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DIST), **kw)

    def do_GET(self):
        path = self.path.split("?")[0].split("#")[0]
        if path != "/" and "." not in path.rsplit("/", 1)[-1] and (DIST / (path.strip("/") + ".html")).exists():
            self.path = path.rstrip("/") + ".html"
        super().do_GET()

    def do_POST(self):
        """Local stand-in for send.php (PHP on the production host): logs the lead, answers like the real one."""
        if self.path.split("?")[0] != "/send.php":
            self.send_error(404)
            return
        import urllib.parse
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8", "replace")
        print("LEAD (local stub, nothing was sent):", {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()})
        body = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    build()
    if "--serve" in sys.argv:
        port = 4175
        print(f"serving http://localhost:{port}")
        http.server.ThreadingHTTPServer(("127.0.0.1", port), CleanURLHandler).serve_forever()
