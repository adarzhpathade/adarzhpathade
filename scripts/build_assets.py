"""Builds the README's SVG panels with subsetted, embedded fonts.

Usage: python scripts/build_assets.py [path/to/fonts]
Fonts default to the sibling portfolio project's src/fonts.
"""
import base64
import hashlib
import io
import re
import sys
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

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

    def __init__(self, name, height):
        self.name, self.h = name, height
        self.css, self.body = [], []
        self.used = {k: set() for k in FONTS}

    def text(self, x, y, s, font, size, fill, anchor="start", tracking=0, cls="", extra=""):
        self.used[font].update(s)
        self.body.append(
            f'<text x="{x:.1f}" y="{y:.1f}" class="{font} {cls}" font-size="{size}" fill="{fill}"'
            f' text-anchor="{anchor}" letter-spacing="{tracking}"{extra}>{escape(s)}</text>'
        )

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
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{self.h}" viewBox="0 0 {W} {self.h}" role="img" aria-label="{escape(label)}">\n'
            f"<style>\n{self.font_faces()}\n{''.join(self.css)}\n</style>\n"
            + "\n".join(self.body)
            + "\n</svg>\n"
        )
        (OUT / self.name).write_text(svg, encoding="utf-8")
        print(f"{self.name}: {len(svg) / 1024:.0f} KB")


RISE_CSS = (
    ".rise{opacity:0;transform-box:fill-box;animation:rise 1.1s cubic-bezier(.16,1,.3,1) forwards}"
    "@keyframes rise{from{opacity:0;transform:translateY(40%)}to{opacity:1;transform:translateY(0)}}"
)


def header(name, ink):
    """Transparent header; one file per GitHub theme so the ink matches the page."""
    s = Svg(name, 390)
    s.css.append(RISE_CSS)
    s.text(0, 24, "(FRONTEND DEVELOPER)", "mono", 13, ink, tracking=1)
    s.text(W, 24, "(B.TECH CS & IT '28)", "mono", 13, ink, anchor="end", tracking=1)
    s.raw(f'<line x1="0" y1="46" x2="{W}" y2="46" stroke="{ink}" stroke-opacity=".2"/>')

    letters = [(ch, "light") for ch in "ADARSH"] + [(ch, "eiko") for ch in "'26"]
    gap = .04  # breathing room between the sans name and the italic year, in em
    size = W / (sum(measure(ch, font, 1) for ch, font in letters) + gap)
    x, baseline = 0, 290
    for i, (ch, font) in enumerate(letters):
        if ch == "'":
            x += gap * size
        s.text(x, baseline, ch, font, f"{size:.1f}", ink, cls="rise", extra=f' style="animation-delay:{.1 + i * .06:.2f}s"')
        x += measure(ch, font, size)

    tagline = [("FRONTEND — ", "regular"), ("Developer", "eiko")]
    tsize = 34
    x = (W - sum(measure(t, f, tsize) for t, f in tagline)) / 2
    for t, font in tagline:
        s.text(x, 362, t, font, tsize + (4 if font == "eiko" else 0), ink)
        x += measure(t, font, tsize)
    s.write("ADARSH'26 — frontend developer, B.Tech CS & IT '28")


def about(name, ink):
    s = Svg(name, 400)
    s.text(0, 24, "(01)", "mono", 13, ink, tracking=1, extra=' fill-opacity=".5"')
    s.text(44, 24, "— ABOUT", "mono", 13, ink, tracking=1)
    s.raw(f'<line x1="0" y1="46" x2="{W}" y2="46" stroke="{ink}" stroke-opacity=".2"/>')

    words = [
        ("I", "light"), ("build", "light"), ("interfaces", "light"), ("that", "light"), ("feel", "eiko"),
        ("alive", "light"), ("—", "light"), ("responsive,", "light"), ("accessible", "light"), ("and", "light"),
        ("quietly", "eiko"), ("animated.", "light"), ("Right", "light"), ("now", "light"), ("I'm", "light"),
        ("growing", "light"), ("into", "light"), ("full-stack", "eiko"), ("architecture", "light"), ("while", "light"),
        ("sharpening", "light"), ("my", "light"), ("problem", "light"), ("solving", "light"), ("with", "light"),
        ("DSA", "light"), ("in", "light"), ("Java.", "light"),
    ]
    size, lh, left = 42, 54, 300
    x, y = left, 120
    for word, font in words:
        fs = size + (4 if font == "eiko" else 0)
        w = measure(word, font, fs)
        if x + w > W:
            x, y = left, y + lh
        s.text(x, y, word, font, fs, ink)
        x += w + measure(" ", "light", size)

    s.raw(f'<line x1="0" y1="316" x2="{W}" y2="316" stroke="{ink}" stroke-opacity=".2"/>')
    meta = [
        ("ROLE", "Frontend Developer"),
        ("EDUCATION", "B.Tech CS & IT, 2024—28"),
        ("FOCUS", "UI engineering & motion"),
        ("PRACTICE", "DSA in Java"),
    ]
    col = W / 4
    for i, (k, v) in enumerate(meta):
        s.text(i * col, 352, k, "mono", 12, ink, tracking=1, extra=' fill-opacity=".5"')
        s.text(i * col, 384, v, "regular", 20, ink)
    s.write("About: I build interfaces that feel alive — responsive, accessible and quietly animated. "
            "Right now I'm growing into full-stack architecture while sharpening my problem solving with DSA in Java.")


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
    bust_readme_cache()
