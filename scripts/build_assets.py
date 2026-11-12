"""Builds the README's SVG panels with subsetted, embedded fonts.

Usage: python scripts/build_assets.py [path/to/fonts]
Fonts default to the sibling portfolio project's src/fonts.
"""
import base64
import hashlib
import io
import math
import re
import sys
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

import numpy as np

import art

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "adrz - Portfolio" / "src" / "fonts"
OUT = ROOT / "assets"

INK, PAPER = "#080808", "#F0F0F0"
W = 1200

FONTS = {
    "light": ("PPNeueMontreal-Light.woff2", "NM Light"),
    "regular": ("PPNeueMontreal-Regular.woff2", "NM Regular"),
    "eiko": ("PPEiko-RegularItalic.woff2", "Eiko Italic"),
    "mono": ("FragmentMono-Regular.woff2", "Fragment Mono"),
}
FALLBACK = {
    "light": "'Helvetica Neue',Arial,sans-serif",
    "regular": "'Helvetica Neue',Arial,sans-serif",
    "eiko": "Georgia,serif",
    "mono": "Consolas,monospace",
}
_tt = {k: TTFont(FONT_DIR / f) for k, (f, _) in FONTS.items()}


def measure(text, font, size, tracking=0.0):
    tt = _tt[font]
    cmap, hmtx, upm = tt.getBestCmap(), tt["hmtx"], tt["head"].unitsPerEm
    units = 0
    for ch in text:
        glyph = cmap.get(ord(ch))
        if glyph is None:
            raise ValueError(f"{FONTS[font][0]} has no glyph for {ch!r} in {text!r}")
        units += hmtx[glyph][0]
    return units * size / upm + tracking * len(text)


class Svg:
    """Collects elements and the characters each font needs."""

    def __init__(self, name, height, width=W):
        self.name, self.h, self.w = name, height, width
        self.css, self.body = [], []
        self.used = {k: set() for k in FONTS}

    def text(self, x, y, s, font, size, fill, anchor="start", tracking=0, cls="", extra="", inner=""):
        self.used[font].update(s)
        self.body.append(
            f'<text x="{x:.1f}" y="{y:.1f}" class="{font} {cls}" font-size="{size}" fill="{fill}"'
            f' text-anchor="{anchor}" letter-spacing="{tracking}" xml:space="preserve"{extra}>{escape(s)}{inner}</text>'
        )

    def rich(self, x, y, segments, size, fill):
        """One text line with inline font changes, so the browser does the spacing. segments: [(text, font, size)]."""
        spans = []
        for t, font, fs in segments:
            self.used[font].update(t)
            spans.append(f'<tspan class="{font}" font-size="{fs}">{escape(t)}</tspan>')
        self.body.append(f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" xml:space="preserve">{"".join(spans)}</text>')

    def raw(self, markup):
        self.body.append(markup)

    def font_faces(self):
        faces = []
        for key, (file, family) in FONTS.items():
            chars = self.used[key]
            if not chars:
                continue
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern", "liga"]
            sub = subset.Subsetter(opts)
            sub.populate(text="".join(sorted(chars)))
            font = TTFont(FONT_DIR / file)
            sub.subset(font)
            buf = io.BytesIO()
            font.flavor = "woff2"
            font.save(buf)
            data = base64.b64encode(buf.getvalue()).decode()
            faces.append(f"@font-face{{font-family:'{family}';src:url(data:font/woff2;base64,{data}) format('woff2');}}")
            faces.append(f".{key}{{font-family:'{family}',{FALLBACK[key]};}}")
        return "\n".join(faces)

    def write(self, label):
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(label)}">\n'
            f"<style>\n{self.font_faces()}\n{''.join(self.css)}\n</style>\n"
            + "\n".join(self.body)
            + "\n</svg>\n"
        )
        (OUT / self.name).write_text(svg, encoding="utf-8")
        print(f"{self.name}: {len(svg) / 1024:.0f} KB")


RISE_CSS = (
    ".rise{opacity:0;transform-box:fill-box;animation:rise 1.1s cubic-bezier(.16,1,.3,1) forwards}"
    "@keyframes rise{from{opacity:0;transform:translateY(40%)}to{opacity:1;transform:translateY(0)}}"
    ".fade{opacity:0;animation:fade 1.6s ease .4s forwards}@keyframes fade{to{opacity:1}}"
)

LABEL = 16
GAP = 96        # GitHub stacks the images with no gap of their own
GUT = 12        # space between framed cells
FRAME = .5      # border opacity
GRAY = {INK: 8, PAPER: 240}

# generated once, encoded per theme
FIELDS = {}


def field(kind, w, h):
    key = (kind, w, h)
    if key not in FIELDS:
        FIELDS[key] = {"planet": art.planet, "galaxy": art.galaxy, "nebula": art.nebula, "rocks": art.rocks}[kind](w, h)
    return FIELDS[key]


def picture(s, ink, kind, x, y, w, h, vignette=0):
    """Dithered art. `vignette` thins the edges out so the art floats instead of sitting in a frame."""
    f = field(kind, w, h)
    v = f[0] if isinstance(f, tuple) else f
    if vignette:
        edge = np.minimum(np.arange(h), h - 1 - np.arange(h))[:, None], np.minimum(np.arange(w), w - 1 - np.arange(w))[None, :]
        v = v * np.clip(np.minimum(*np.broadcast_arrays(*edge)) / vignette, 0, 1)
    s.raw(f'<image x="{x}" y="{y}" width="{w}" height="{h}" href="{art.png_uri(art.dither(v), GRAY[ink])}"/>')
    return f[1] if isinstance(f, tuple) else None


def box(*_a, **_k):
    """Frames were removed on purpose; kept as a no-op so nothing else has to change."""


def corners(*_a, **_k):
    pass


def hairline(s, ink, y, x1=0, x2=W, op=.25):
    s.raw(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{ink}" stroke-opacity="{op}"/>')


def mono(s, x, y, text, ink, size=LABEL, anchor="start", dim=False, tracking=1.5):
    s.text(x, y, text, "mono", size, ink, anchor=anchor, tracking=tracking, extra=' fill-opacity=".55"' if dim else "")


def twinkle(s, ink, x, y, r, dur, begin=0):
    s.raw(f'<path d="M{x} {y - r}L{x + r * .2} {y - r * .2}L{x + r} {y}L{x + r * .2} {y + r * .2}L{x} {y + r}'
          f'L{x - r * .2} {y + r * .2}L{x - r} {y}L{x - r * .2} {y - r * .2}Z" fill="{ink}">'
          f'<animate attributeName="opacity" values="1;.1;1" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/></path>')


def pulse_dot(s, ink, cx, cy):
    s.raw(f'<circle cx="{cx}" cy="{cy}" r="4.5" fill="{ink}"><animate attributeName="opacity" values="1;.2;1" dur="2.4s" repeatCount="indefinite"/>'
          f'<animate attributeName="r" values="4.5;3.2;4.5" dur="2.4s" repeatCount="indefinite"/></circle>')


def bar(s, ink, y, num, title, right=None):
    """Section heading: (02) — TITLE on the left, optional note on the right, one hairline under it."""
    mono(s, 0, y + 24, f"({num})", ink, size=18, dim=True, tracking=1)
    mono(s, measure(f"({num}) ", "mono", 18, 1), y + 24, f"— {title}", ink, size=18, tracking=1)
    if right:
        mono(s, W, y + 24, right, ink, size=18, anchor="end", dim=True, tracking=1)
    hairline(s, ink, y + 44)
    return y + 44


def wave_band(s, ink, uid, x, y, w, h, dur, phase=0.0, lines=14):
    """Flowing lines that slide by exactly one wavelength, so the loop is seamless."""
    s.raw(f'<clipPath id="{uid}"><rect x="{x}" y="{y}" width="{w}" height="{h}"/></clipPath><g clip-path="url(#{uid})">')
    pts_x = range(x - 130, x + w + 131, 6)
    body = []
    for i in range(lines):
        base = y + 8 + i * (h - 16) / (lines - 1)
        pts = " ".join(
            f"{px},{base + 5 * math.sin(2 * math.pi * (px - x) / 130 + i * .55 + phase) + 3 * math.sin(2 * math.pi * (px - x) / 65 + i * .3):.1f}"
            for px in pts_x)
        body.append(f'<polyline points="{pts}" fill="none" stroke="{ink}" stroke-opacity="{.25 + .45 * i / (lines - 1):.2f}" stroke-width="1"/>')
    s.raw(f'<g>{"".join(body)}<animateTransform attributeName="transform" type="translate" values="0 0;-130 0" dur="{dur}s" repeatCount="indefinite"/></g></g>')


def globe(s, ink, cx, cy, R):
    s.raw(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{ink}" stroke-opacity=".8"/>')
    for lat in (-.55, 0, .55):
        ry = R * math.sqrt(1 - lat * lat)
        s.raw(f'<ellipse cx="{cx}" cy="{cy + lat * R:.1f}" rx="{ry:.1f}" ry="{ry * .18:.1f}" fill="none" stroke="{ink}" stroke-opacity=".45"/>')
    for k in range(4):  # meridians turning like a slowly spinning globe
        vals = ";".join(f"{R * abs(math.cos(math.pi * (k / 4 + j / 16))):.1f}" for j in range(17))
        s.raw(f'<ellipse cx="{cx}" cy="{cy}" rx="{R}" ry="{R}" fill="none" stroke="{ink}" stroke-opacity=".5">'
              f'<animate attributeName="rx" values="{vals}" dur="16s" repeatCount="indefinite"/></ellipse>')


def orbit_figure(s, ink, cx, cy, R):
    """Wobbly contour rings turning in opposite directions, with a dot on an orbit."""
    def spin(deg, dur):
        return (f'<animateTransform attributeName="transform" type="rotate" values="0 {cx} {cy};{deg} {cx} {cy}"'
                f' dur="{dur}s" repeatCount="indefinite"/>')

    rings, groups = 12, ([], [])
    for k in range(rings):
        base = R * (.16 + .84 * k / (rings - 1))
        pts = []
        for n in range(97):
            th = n / 96 * 2 * math.pi
            r = base * (1 + .05 * math.sin(3 * th + k * .9) + .03 * math.sin(5 * th + k * 1.7))
            pts.append(f"{cx + r * math.cos(th):.1f},{cy + r * math.sin(th):.1f}")
        groups[k % 2].append(
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{ink}" stroke-opacity="{.2 + .45 * k / (rings - 1):.2f}"/>')
    s.raw("<g>" + "".join(groups[0]) + spin(360, 120) + "</g>")
    s.raw("<g>" + "".join(groups[1]) + spin(-360, 160) + "</g>")
    s.raw(f'<path d="M{cx - R - 8} {cy}H{cx + R + 8}M{cx} {cy - R - 8}V{cy + R + 8}" stroke="{ink}" stroke-opacity=".3"/>')
    s.raw(f'<g><circle cx="{cx}" cy="{cy}" r="{R * .62:.1f}" fill="none" stroke="{ink}" stroke-opacity=".6" stroke-dasharray="1 7"/>'
          f'<circle cx="{cx + R * .62:.1f}" cy="{cy}" r="4" fill="{ink}"/>' + spin(360, 14) + "</g>")
    s.raw(f'<circle cx="{cx}" cy="{cy}" r="3" fill="{ink}"/>')


def header(name, ink):
    top, ph = 104, 300
    s = Svg(name, top + ph + 190 + GAP)
    s.css.append(RISE_CSS)

    # heading strip: rotating keywords left, place right
    mono(s, 0, 24, "(01)", ink, size=18, dim=True, tracking=1)
    x = measure("(01) ", "mono", 18, 1) + 14
    for k, word in enumerate(["FRONTEND", "MOTION", "CODE", "REPEAT"]):
        vals = ";".join("1" if j == k else ".4" for j in range(4))
        s.text(x, 24, word, "mono", 18, ink, tracking=2,
               inner=f'<animate attributeName="fill-opacity" values="{vals}" keyTimes="0;.25;.5;.75" calcMode="discrete" dur="6s" repeatCount="indefinite"/>')
        x += measure(word, "mono", 18, 2)
        if k < 3:
            mono(s, x + 14, 24, "+", ink, size=18, dim=True)
            x += 28 + measure("+", "mono", 18, 1.5)
    place = "DEWAS, INDIA"
    pw = measure(place, "mono", 18, 1)
    pulse_dot(s, ink, W - pw - 20, 18)
    mono(s, W, 24, place, ink, size=18, anchor="end", dim=True, tracking=1)
    hairline(s, ink, 44)

    # name + planet
    planet_w = 480
    pxx = W - planet_w
    letters = [(ch, "light") for ch in "ADARSH"] + [(ch, "eiko") for ch in "'26"]
    gap = .04
    size = (pxx - 56) / (sum(measure(ch, f, 1) for ch, f in letters) + gap)
    px, base = 0, top + 20 + size * .74
    for i, (ch, f) in enumerate(letters):
        if ch == "'":
            px += gap * size
        shimmer = (f'<animate attributeName="fill-opacity" values="1;.7;1" dur="4.5s" begin="{2 + i * .3:.1f}s" repeatCount="indefinite"/>'
                   if f == "eiko" else "")
        s.text(px, base, ch, f, f"{size:.1f}", ink, cls="rise", extra=f' style="animation-delay:{.1 + i * .06:.2f}s"', inner=shimmer)
        px += measure(ch, f, size)
    ty = top + ph - 74
    s.rich(0, ty + 30, [("FRONTEND — ", "regular", 32), ("Developer", "eiko", 36)], 32, ink)
    mono(s, 0, ty + 66, "INTERFACES THAT FEEL ALIVE", ink, size=14, dim=True)

    cx, cy, R, tilt = picture(s, ink, "planet", pxx, top, planet_w, ph)
    ox, oy = pxx + cx, top + cy
    s.raw(f'<g transform="rotate({tilt} {ox:.1f} {oy:.1f})"><circle r="4" fill="{ink}"><animateMotion dur="11s" repeatCount="indefinite" '
          f'path="M {ox - R * 1.8:.1f} {oy:.1f} A {R * 1.8:.1f} {R * .5:.1f} 0 1 1 {ox + R * 1.8:.1f} {oy:.1f} A {R * 1.8:.1f} {R * .5:.1f} 0 1 1 {ox - R * 1.8:.1f} {oy:.1f}"/></circle></g>')
    s.raw(f'<rect y="{top}" width="1.5" height="{ph}" fill="{ink}" opacity="0"><animate attributeName="x" values="{pxx};{W};{W}" keyTimes="0;.5;1" dur="10s" repeatCount="indefinite"/>'
          '<animate attributeName="opacity" values="0;.5;.5;0;0" keyTimes="0;.05;.45;.5;1" dur="10s" repeatCount="indefinite"/></rect>')
    mono(s, pxx, top + ph + 26, "FIG. 01 / PLANET", ink, size=12, dim=True)

    # lower row: galaxy, globe, tagline, rocks, index
    y, h = top + ph + 84, 96
    picture(s, ink, "galaxy", 0, y, 230, h, vignette=34)
    globe(s, ink, 316, y + h / 2, 34)
    for i, line in enumerate(["SAME UNIVERSE.", "DIFFERENT IDEAS.", "ONE SCREEN AT A TIME."]):
        mono(s, 400, y + 28 + i * 24, line, ink, size=14, tracking=1.5)
    picture(s, ink, "rocks", 690, y, 320, h)
    for i, line in enumerate(["BUILD", "LEARN", "SHIP", "REPEAT"]):
        mono(s, 1070, y + 22 + i * 21, line, ink, size=13, tracking=3, dim=i < 3)
    s.write("ADARSH'26 — frontend developer, B.Tech CS & IT '28")


def about(name, ink):
    top, ch = 96, 400
    s = Svg(name, top + ch + 56 + GAP)
    status = "STATUS: ONLINE & LEARNING"
    bar(s, ink, 0, "02", "ABOUT", status)
    pulse_dot(s, ink, W - measure(status, "mono", 18, 1) - 20, 18)

    orbit_figure(s, ink, 150, top + 190, 128)
    mono(s, 0, top + ch + 26, "FIG. 02 / ORBIT", ink, size=12, dim=True)

    cx0, right = 350, 880
    words = [
        ("I", "light"), ("build", "light"), ("interfaces", "light"), ("that", "light"), ("feel", "eiko"),
        ("alive", "light"), ("—", "light"), ("responsive,", "light"), ("accessible", "light"), ("and", "light"),
        ("quietly", "eiko"), ("animated.", "light"), ("Right", "light"), ("now", "light"), ("I'm", "light"),
        ("growing", "light"), ("into", "light"), ("full-stack", "eiko"), ("architecture", "light"), ("while", "light"),
        ("sharpening", "light"), ("my", "light"), ("problem", "light"), ("solving", "light"), ("with", "light"),
        ("DSA", "light"), ("in", "light"), ("Java.", "light"),
    ]
    size, lh = 30, 42
    x, yy = cx0, top + 36
    for word, font in words:
        fs = size + (3 if font == "eiko" else 0)
        w = measure(word, font, fs)
        if x + w > right:
            x, yy = cx0, yy + lh
        s.text(x, yy, word, font, fs, ink)
        x += w + measure(" ", "light", size)
    s.raw(f'<rect x="{x - measure(" ", "light", size) + 6:.1f}" y="{yy - 27}" width="3" height="34" fill="{ink}">'
          '<animate attributeName="opacity" values="1;1;0;0;1" keyTimes="0;.5;.5;.99;1" dur="1.1s" repeatCount="indefinite"/></rect>')

    rows = [("ROLE", "Frontend Developer"), ("EDUCATION", "B.Tech CS & IT, 2024—28"),
            ("FOCUS", "UI engineering & motion"), ("PRACTICE", "DSA in Java")]
    for i, (k, v) in enumerate(rows):
        ry = top + 276 + i * 38
        mono(s, cx0, ry, k, ink, size=13, dim=True)
        s.text(cx0 + 180, ry + 1, v, "regular", 21, ink)

    nx, nw = 930, W - 930
    picture(s, ink, "nebula", nx, top, nw, ch, vignette=56)
    for i, (tx, ty, r, d) in enumerate([(.3, .18, 7, 2.6), (.7, .36, 5, 3.4), (.45, .62, 9, 4.1), (.78, .8, 5, 2.9), (.2, .84, 4, 3.7)]):
        twinkle(s, ink, nx + nw * tx, top + ch * ty, r, d, i * .6)
    mono(s, nx, top + ch + 26, "FIG. 03 / NEBULA", ink, size=12, dim=True)
    s.write("About: I build interfaces that feel alive — responsive, accessible and quietly animated. "
            "Right now I'm growing into full-stack architecture while sharpening my problem solving with DSA in Java.")


def toolkit(name, ink):
    rows = [
        ("LANGUAGES", ["Java", "JavaScript", "TypeScript", "HTML", "CSS"]),
        ("FRONTEND", ["React", "Next.js", "Tailwind CSS", "GSAP", "Framer Motion", "Three.js"]),
        ("BACKEND", ["Node.js", "Express", "PostgreSQL", "MongoDB", "Drizzle ORM", "Supabase"]),
        ("TOOLS", ["Git", "GitHub", "VS Code", "Figma", "Postman", "Vercel"]),
    ]
    top, gut = 96, 40
    cw = (W - 3 * gut) // 4
    s = Svg(name, top + 372 + GAP)
    bar(s, ink, 0, "03", "TOOLKIT", "23 TOOLS / 4 LAYERS")
    for i, (label, items) in enumerate(rows):
        x = i * (cw + gut)
        wave_band(s, ink, f"wb{i}", x, top, cw, 56, 9 + i * 2, phase=i * 1.3)
        mono(s, x, top + 104, f"{i + 1:02d} / {label}", ink, size=14, tracking=2, dim=True)
        for j, item in enumerate(items):
            ly = top + 156 + j * 38
            mono(s, x, ly, "+", ink, size=16, dim=True)
            s.text(x + 26, ly, item, "regular", 24, ink)
    s.write("Toolkit — " + ". ".join(f"{label.title()}: {', '.join(items)}" for label, items in rows))


def portfolio(name, ink):
    """Whole image is the link to the portfolio."""
    top, ah = 96, 190
    s = Svg(name, top + ah + 56 + GAP)
    bar(s, ink, 0, "04", "PORTFOLIO", "ADRZ-26.VERCEL.APP")
    tw = 780
    line = [("VISIT MY ", "light", 1), ("portfolio", "eiko", 1.08), (" ↗", "light", 1)]
    size = tw / sum(measure(t, f, sc) for t, f, sc in line)
    s.rich(0, top + 20 + size * .78, [(t, f, f"{size * sc:.1f}") for t, f, sc in line], f"{size:.1f}", ink)
    mono(s, 0, top + ah - 4, "CODE, AI, MOTION & VISUALS", ink, size=14, dim=True)
    mono(s, tw, top + ah - 4, "(CLICK TO OPEN ↗)", ink, size=14, anchor="end")
    rx = 880
    picture(s, ink, "rocks", rx, top, W - rx, ah)
    mono(s, rx, top + ah + 26, "FIG. 04 / DRIFT", ink, size=12, dim=True)
    s.write("Visit my portfolio — adrz-26.vercel.app")


def contact(name, ink):
    s = Svg(name, 46)
    bar(s, ink, 0, "05", "CONTACT", "SAY HELLO")
    s.write("Contact")


LINK_W = 400


def contact_link(name, ink, num, word):
    """One clickable third of the contact row; the README places three side by side."""
    s = Svg(name, 150, width=LINK_W)
    mono(s, 0, 40, f"({num})", ink, size=16, dim=True, tracking=1)
    s.rich(0, 118, [(word + " ", "light", 64), ("↗", "light", 52)], 64, ink)
    s.write(f"{word} ↗")


def bust_readme_cache():
    """GitHub caches images by URL, so stamp each asset link with a hash of its content."""
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    for svg in OUT.glob("*.svg"):
        digest = hashlib.sha1(svg.read_bytes()).hexdigest()[:8]
        text = re.sub(rf"assets/{re.escape(svg.name)}(\?v=\w+)?", f"assets/{svg.name}?v={digest}", text)
    readme.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for theme, ink in (("light", INK), ("dark", PAPER)):
        header(f"header-{theme}.svg", ink)
        about(f"about-{theme}.svg", ink)
        toolkit(f"toolkit-{theme}.svg", ink)
        portfolio(f"portfolio-{theme}.svg", ink)
        contact(f"contact-{theme}.svg", ink)
        for num, word in (("01", "LinkedIn"), ("02", "Email"), ("03", "GitHub")):
            contact_link(f"contact-{word.lower()}-{theme}.svg", ink, num, word)
    bust_readme_cache()
