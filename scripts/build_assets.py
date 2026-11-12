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
GAP = 64        # GitHub stacks the images with no gap of their own
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


def picture(s, ink, kind, x, y, w, h, fade=0):
    f = field(kind, w, h)
    v = f[0] if isinstance(f, tuple) else f
    if fade:  # thin the art out toward the bottom so the caption stays readable
        v = v * np.clip((h - 30 - np.arange(h)[:, None]) / fade, 0, 1)
    s.raw(f'<image x="{x}" y="{y}" width="{w}" height="{h}" href="{art.png_uri(art.dither(v), GRAY[ink])}"/>')
    return f[1] if isinstance(f, tuple) else None


def box(s, ink, x, y, w, h, op=FRAME):
    s.raw(f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1}" height="{h - 1}" fill="none" stroke="{ink}" stroke-opacity="{op}"/>')


def corners(s, ink, x, y, w, h, n=9):
    """Small registration ticks just inside a framed cell."""
    d = []
    for cx, cy, sx, sy in ((x + 6, y + 6, 1, 1), (x + w - 6, y + 6, -1, 1), (x + 6, y + h - 6, 1, -1), (x + w - 6, y + h - 6, -1, -1)):
        d.append(f"M{cx} {cy + sy * n}V{cy}H{cx + sx * n}")
    s.raw(f'<path d="{"".join(d)}" fill="none" stroke="{ink}" stroke-opacity=".7"/>')


def mono(s, x, y, text, ink, size=LABEL, anchor="start", dim=False, tracking=1.5):
    s.text(x, y, text, "mono", size, ink, anchor=anchor, tracking=tracking, extra=' fill-opacity=".55"' if dim else "")


def twinkle(s, ink, x, y, r, dur, begin=0):
    s.raw(f'<path d="M{x} {y - r}L{x + r * .2} {y - r * .2}L{x + r} {y}L{x + r * .2} {y + r * .2}L{x} {y + r}'
          f'L{x - r * .2} {y + r * .2}L{x - r} {y}L{x - r * .2} {y - r * .2}Z" fill="{ink}">'
          f'<animate attributeName="opacity" values="1;.1;1" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/></path>')


def pulse_dot(s, ink, cx, cy):
    s.raw(f'<circle cx="{cx}" cy="{cy}" r="4.5" fill="{ink}"><animate attributeName="opacity" values="1;.2;1" dur="2.4s" repeatCount="indefinite"/>'
          f'<animate attributeName="r" values="4.5;3.2;4.5" dur="2.4s" repeatCount="indefinite"/></circle>')


def bar(s, ink, y, num, title, right):
    """Section bar: numbered tab, title with a trailing rule, and a boxed status on the right."""
    h = 44
    box(s, ink, 0, y, 56, h)
    mono(s, 28, y + 28, num, ink, anchor="middle")
    box(s, ink, 56, y, 640, h)
    mono(s, 82, y + 28, title, ink, size=18, tracking=3)
    tw = measure(title, "mono", 18, 3)
    s.raw(f'<line x1="{82 + tw + 18:.0f}" y1="{y + 22}" x2="672" y2="{y + 22}" stroke="{ink}" stroke-opacity=".4"/>')
    box(s, ink, 696 + GUT, y, W - 696 - GUT, h)
    return y + h


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
    s = Svg(name, 452 + GAP)
    s.css.append(RISE_CSS)

    # row A: tab, rotating keyword strip, barcode, tagline, star
    y = 0
    box(s, ink, 0, y, 56, 44)
    mono(s, 28, y + 28, "01", ink, anchor="middle")
    box(s, ink, 56, y, 764, 44)
    x = 84
    for k, word in enumerate(["FRONTEND", "MOTION", "CODE", "REPEAT"]):
        vals = ";".join("1" if j == k else ".4" for j in range(4))
        s.text(x, y + 28, word, "mono", 17, ink, tracking=3,
               inner=f'<animate attributeName="fill-opacity" values="{vals}" keyTimes="0;.25;.5;.75" calcMode="discrete" dur="6s" repeatCount="indefinite"/>')
        x += measure(word, "mono", 17, 3)
        if k < 3:
            mono(s, x + 14, y + 28, "+", ink, size=17, dim=True)
            x += 14 + measure("+", "mono", 17, 1.5) + 14
    box(s, ink, 832, y, 150, 44)
    bars, bx = [], 846
    for i in range(34):
        wid = 1 + (i * 7 % 3)
        bars.append(f'<rect x="{bx}" y="{y + 11}" width="{wid}" height="22" fill="{ink}" fill-opacity=".75"/>')
        bx += wid + 1.6 + (i * 5 % 2)
        if bx > 968:
            break
    s.raw("".join(bars))
    box(s, ink, 994, y, 168, 44)
    mono(s, 1004, y + 19, "B.TECH CS & IT '28", ink, size=11, tracking=1)
    mono(s, 1004, y + 35, "DEWAS, INDIA", ink, size=11, tracking=1)
    box(s, ink, 1174, y, 26, 44)
    twinkle(s, ink, 1187, 22, 8, 3.2)

    # row B: name panel + planet
    y = 56
    box(s, ink, 0, y, 720, 300)
    letters = [(ch, "light") for ch in "ADARSH"] + [(ch, "eiko") for ch in "'26"]
    gap = .04
    size = (720 - 56) / (sum(measure(ch, f, 1) for ch, f in letters) + gap)
    px, base = 28, y + 62 + size * .74
    for i, (ch, f) in enumerate(letters):
        if ch == "'":
            px += gap * size
        shimmer = (f'<animate attributeName="fill-opacity" values="1;.7;1" dur="4.5s" begin="{2 + i * .3:.1f}s" repeatCount="indefinite"/>'
                   if f == "eiko" else "")
        s.text(px, base, ch, f, f"{size:.1f}", ink, cls="rise", extra=f' style="animation-delay:{.1 + i * .06:.2f}s"', inner=shimmer)
        px += measure(ch, f, size)
    ty = y + 214
    s.raw(f'<line x1="28" y1="{ty}" x2="692" y2="{ty}" stroke="{ink}" stroke-opacity=".35"/>')
    s.rich(28, ty + 46, [("FRONTEND — ", "regular", 30), ("Developer", "eiko", 34)], 30, ink)
    mono(s, 28, ty + 74, "INTERFACES THAT FEEL ALIVE", ink, size=14, dim=True)
    mono(s, 692, ty + 74, "(26)", ink, size=14, anchor="end", dim=True)

    pxx, pw = 720 + GUT, W - 720 - GUT
    box(s, ink, pxx, y, pw, 300)
    cx, cy, R, tilt = picture(s, ink, "planet", pxx + 1, y + 1, pw - 2, 298)
    ox, oy = pxx + 1 + cx, y + 1 + cy
    s.raw(f'<g transform="rotate({tilt} {ox:.1f} {oy:.1f})"><circle r="4" fill="{ink}"><animateMotion dur="11s" repeatCount="indefinite" '
          f'path="M {ox - R * 1.8:.1f} {oy:.1f} A {R * 1.8:.1f} {R * .5:.1f} 0 1 1 {ox + R * 1.8:.1f} {oy:.1f} A {R * 1.8:.1f} {R * .5:.1f} 0 1 1 {ox - R * 1.8:.1f} {oy:.1f}"/></circle></g>')
    s.raw(f'<rect y="{y + 2}" width="1.5" height="296" fill="{ink}" opacity="0"><animate attributeName="x" values="{pxx};{W};{W}" keyTimes="0;.5;1" dur="10s" repeatCount="indefinite"/>'
          '<animate attributeName="opacity" values="0;.5;.5;0;0" keyTimes="0;.05;.45;.5;1" dur="10s" repeatCount="indefinite"/></rect>')
    corners(s, ink, pxx, y, pw, 300)
    mono(s, pxx + 18, y + 284, "FIG. 01 / PLANET", ink, size=12, dim=True)
    mono(s, W - 18, y + 30, "11 / 11", ink, size=12, anchor="end", dim=True)

    # row C: galaxy, globe, tagline, rocks, index
    y = 368
    h = 84
    box(s, ink, 0, y, 200, h)
    picture(s, ink, "galaxy", 1, y + 1, 198, h - 2)
    box(s, ink, 212, y, 84, h)
    globe(s, ink, 254, y + 42, 28)
    box(s, ink, 308, y, 312, h)
    for i, line in enumerate(["SAME UNIVERSE.", "DIFFERENT IDEAS.", "ONE SCREEN AT A TIME."]):
        mono(s, 326, y + 28 + i * 20, line, ink, size=14, tracking=1.5)
    box(s, ink, 632, y, 378, h)
    picture(s, ink, "rocks", 633, y + 1, 376, h - 2)
    box(s, ink, 1022, y, 178, h)
    for i, line in enumerate(["BUILD", "LEARN", "SHIP", "REPEAT"]):
        mono(s, 1040, y + 20 + i * 17, line, ink, size=12, tracking=2.5)
    s.write("ADARSH'26 — frontend developer, B.Tech CS & IT '28")


def about(name, ink):
    s = Svg(name, 56 + 384 + GAP)
    bar(s, ink, 0, "02", "ABOUT", "")
    # status box
    pulse_dot(s, ink, 696 + GUT + 24, 22)
    mono(s, 696 + GUT + 42, 28, "STATUS: ONLINE & LEARNING", ink, size=15, tracking=2)

    y, h = 56, 384
    box(s, ink, 0, y, 300, h)
    orbit_figure(s, ink, 150, y + 170, 118)
    corners(s, ink, 0, y, 300, h)
    mono(s, 18, y + h - 18, "FIG. 02 / ORBIT", ink, size=12, dim=True)

    cx0, cw = 312, 576
    box(s, ink, cx0, y, cw, h)
    mono(s, cx0 + 24, y + 34, "FRONTEND DEVELOPER", ink, size=13, dim=True)
    s.raw(f'<line x1="{cx0 + 24}" y1="{y + 48}" x2="{cx0 + cw - 24}" y2="{y + 48}" stroke="{ink}" stroke-opacity=".35"/>')
    words = [
        ("I", "light"), ("build", "light"), ("interfaces", "light"), ("that", "light"), ("feel", "eiko"),
        ("alive", "light"), ("—", "light"), ("responsive,", "light"), ("accessible", "light"), ("and", "light"),
        ("quietly", "eiko"), ("animated.", "light"), ("Right", "light"), ("now", "light"), ("I'm", "light"),
        ("growing", "light"), ("into", "light"), ("full-stack", "eiko"), ("architecture", "light"), ("while", "light"),
        ("sharpening", "light"), ("my", "light"), ("problem", "light"), ("solving", "light"), ("with", "light"),
        ("DSA", "light"), ("in", "light"), ("Java.", "light"),
    ]
    size, lh, left, right = 29, 35, cx0 + 24, cx0 + cw - 24
    x, yy = left, y + 90
    for word, font in words:
        fs = size + (3 if font == "eiko" else 0)
        w = measure(word, font, fs)
        if x + w > right:
            x, yy = left, yy + lh
        s.text(x, yy, word, font, fs, ink)
        x += w + measure(" ", "light", size)
    s.raw(f'<rect x="{x - measure(" ", "light", size) + 6:.1f}" y="{yy - 26}" width="3" height="32" fill="{ink}">'
          '<animate attributeName="opacity" values="1;1;0;0;1" keyTimes="0;.5;.5;.99;1" dur="1.1s" repeatCount="indefinite"/></rect>')

    rows = [("ROLE", "Frontend Developer"), ("EDUCATION", "B.Tech CS & IT, 2024—28"),
            ("FOCUS", "UI engineering & motion"), ("PRACTICE", "DSA in Java")]
    top = y + h - 4 * 30 - 10
    for i, (k, v) in enumerate(rows):
        ry = top + i * 30
        s.raw(f'<line x1="{cx0 + 24}" y1="{ry}" x2="{cx0 + cw - 24}" y2="{ry}" stroke="{ink}" stroke-opacity=".3"/>')
        mono(s, cx0 + 24, ry + 21, k, ink, size=13, dim=True)
        s.text(cx0 + 200, ry + 22, v, "regular", 20, ink)

    nx = cx0 + cw + GUT
    nw = W - nx
    box(s, ink, nx, y, nw, h)
    picture(s, ink, "nebula", nx + 1, y + 1, nw - 2, h - 2, fade=60)
    for i, (tx, ty, r, d) in enumerate([(.22, .2, 7, 2.6), (.7, .34, 5, 3.4), (.45, .62, 9, 4.1), (.82, .78, 5, 2.9), (.16, .8, 4, 3.7)]):
        twinkle(s, ink, nx + nw * tx, y + h * ty, r, d, i * .6)
    corners(s, ink, nx, y, nw, h)
    mono(s, nx + 18, y + h - 18, "FIG. 03 / NEBULA", ink, size=12, dim=True)
    s.write("About: I build interfaces that feel alive — responsive, accessible and quietly animated. "
            "Right now I'm growing into full-stack architecture while sharpening my problem solving with DSA in Java.")


def toolkit(name, ink):
    rows = [
        ("LANGUAGES", ["Java", "JavaScript", "TypeScript", "HTML", "CSS"]),
        ("FRONTEND", ["React", "Next.js", "Tailwind CSS", "GSAP", "Framer Motion", "Three.js"]),
        ("BACKEND", ["Node.js", "Express", "PostgreSQL", "MongoDB", "Drizzle ORM", "Supabase"]),
        ("TOOLS", ["Git", "GitHub", "VS Code", "Figma", "Postman", "Vercel"]),
    ]
    h = 56 + 58 + 6 * 34 + 22
    s = Svg(name, 56 + h + GAP)
    bar(s, ink, 0, "03", "TOOLKIT", "")
    mono(s, 696 + GUT + 24, 28, "23 TOOLS / 4 LAYERS", ink, size=15, tracking=2)
    cw = (W - 3 * GUT) / 4
    for i, (label, items) in enumerate(rows):
        x, y = round(i * (cw + GUT)), 56
        box(s, ink, x, y, round(cw), h)
        wave_band(s, ink, f"wb{i}", x + 1, y + 1, round(cw) - 2, 56, 9 + i * 2, phase=i * 1.3)
        s.raw(f'<line x1="{x}" y1="{y + 57}" x2="{x + round(cw)}" y2="{y + 57}" stroke="{ink}" stroke-opacity=".5"/>')
        mono(s, x + 20, y + 90, f"{i + 1:02d} / {label}", ink, size=14, tracking=2)
        s.raw(f'<line x1="{x + 20}" y1="{y + 104}" x2="{x + round(cw) - 20}" y2="{y + 104}" stroke="{ink}" stroke-opacity=".3"/>')
        for j, item in enumerate(items):
            ly = y + 140 + j * 34
            mono(s, x + 20, ly, "+", ink, size=16, dim=True)
            s.text(x + 44, ly, item, "regular", 23, ink)
        corners(s, ink, x, y, round(cw), h)
    s.write("Toolkit — " + ". ".join(f"{label.title()}: {', '.join(items)}" for label, items in rows))


def portfolio(name, ink):
    """Whole image is the link to the portfolio."""
    h = 230
    s = Svg(name, 56 + h + GAP)
    bar(s, ink, 0, "04", "PORTFOLIO", "")
    mono(s, 696 + GUT + 24, 28, "ADRZ-26.VERCEL.APP", ink, size=15, tracking=2)
    y = 56
    tw = 790
    box(s, ink, 0, y, tw, h)
    line = [("VISIT MY ", "light", 1), ("portfolio", "eiko", 1.08), (" ↗", "light", 1)]
    size = (tw - 56) / sum(measure(t, f, sc) for t, f, sc in line)
    s.rich(28, y + 40 + size * .78, [(t, f, f"{size * sc:.1f}") for t, f, sc in line], f"{size:.1f}", ink)
    mono(s, 28, y + h - 22, "CODE, AI, MOTION & VISUALS", ink, size=13, dim=True)
    mono(s, tw - 28, y + h - 22, "(CLICK TO OPEN ↗)", ink, size=13, anchor="end")
    corners(s, ink, 0, y, tw, h)
    rx = tw + GUT
    box(s, ink, rx, y, W - rx, h)
    picture(s, ink, "rocks", rx + 1, y + 1, W - rx - 2, h - 2, fade=60)
    corners(s, ink, rx, y, W - rx, h)
    mono(s, rx + 18, y + h - 18, "FIG. 04 / TERRAIN", ink, size=12, dim=True)
    s.write("Visit my portfolio — adrz-26.vercel.app")


def contact(name, ink):
    s = Svg(name, 46)
    bar(s, ink, 0, "05", "CONTACT", "")
    mono(s, 696 + GUT + 24, 28, "SAY HELLO", ink, size=15, tracking=2)
    s.write("Contact")


LINK_W = 400


def contact_link(name, ink, num, word):
    """One clickable third of the contact row; the README places three side by side."""
    s = Svg(name, 150, width=LINK_W)
    box(s, ink, 1, 6, LINK_W - 14, 138)
    corners(s, ink, 1, 6, LINK_W - 14, 138)
    mono(s, 24, 38, f"({num})", ink, size=14, dim=True)
    s.rich(24, 112, [(word + " ", "light", 56), ("↗", "light", 46)], 56, ink)
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
