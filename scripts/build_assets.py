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

    def __init__(self, name, height, width=W):
        self.name, self.h, self.w = name, height, width
        self.css, self.body = [], []
        self.used = {k: set() for k in FONTS}

    def text(self, x, y, s, font, size, fill, anchor="start", tracking=0, cls="", extra=""):
        self.used[font].update(s)
        self.body.append(
            f'<text x="{x:.1f}" y="{y:.1f}" class="{font} {cls}" font-size="{size}" fill="{fill}"'
            f' text-anchor="{anchor}" letter-spacing="{tracking}" xml:space="preserve"{extra}>{escape(s)}</text>'
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
)


# Labels are sized for phones too: the panels scale down to ~30% of their width there.
LABEL = 18
# Every section hangs off one vertical axis: section markers live left of it, content starts on it.
AXIS = 300


def marker(s, x, baseline, num, title, ink):
    """Big faded Eiko numeral with a mono caption: marks a section without a dividing line."""
    s.text(x, baseline, num, "eiko", 84, ink, extra=' fill-opacity=".28"')
    s.text(x + 4, baseline + 36, title, "mono", 16, ink, tracking=1.5, extra=' fill-opacity=".65"')


def intro(name, ink):
    """Header and About in one image, so the name flows straight into the statement."""
    s = Svg(name, 880)
    s.css.append(RISE_CSS)
    s.text(0, 30, "(PORTFOLIO '26)", "mono", LABEL, ink, tracking=1, extra=' fill-opacity=".65"')
    s.text(W, 30, "(B.TECH CS & IT '28)", "mono", LABEL, ink, anchor="end", tracking=1, extra=' fill-opacity=".65"')

    letters = [(ch, "light") for ch in "ADARSH"] + [(ch, "eiko") for ch in "'26"]
    gap = .04  # breathing room between the sans name and the italic year, in em
    size = W / (sum(measure(ch, font, 1) for ch, font in letters) + gap)
    x, baseline = 0, 280
    for i, (ch, font) in enumerate(letters):
        if ch == "'":
            x += gap * size
        s.text(x, baseline, ch, font, f"{size:.1f}", ink, cls="rise", extra=f' style="animation-delay:{.1 + i * .06:.2f}s"')
        x += measure(ch, font, size)
    s.rich(AXIS, 352, [("FRONTEND — ", "regular", 36), ("Developer", "eiko", 40)], 36, ink)

    top = 520
    marker(s, 0, top, "01", "ABOUT", ink)
    words = [
        ("I", "light"), ("build", "light"), ("interfaces", "light"), ("that", "light"), ("feel", "eiko"),
        ("alive", "light"), ("—", "light"), ("responsive,", "light"), ("accessible", "light"), ("and", "light"),
        ("quietly", "eiko"), ("animated.", "light"), ("Right", "light"), ("now", "light"), ("I'm", "light"),
        ("growing", "light"), ("into", "light"), ("full-stack", "eiko"), ("architecture", "light"), ("while", "light"),
        ("sharpening", "light"), ("my", "light"), ("problem", "light"), ("solving", "light"), ("with", "light"),
        ("DSA", "light"), ("in", "light"), ("Java.", "light"),
    ]
    fsize, lh = 42, 54
    x, y = AXIS, top - 20
    for word, font in words:
        fs = fsize + (4 if font == "eiko" else 0)
        w = measure(word, font, fs)
        if x + w > W:
            x, y = AXIS, y + lh
        s.text(x, y, word, font, fs, ink)
        x += w + measure(" ", "light", fsize)

    meta = [
        ("ROLE", "Frontend Developer"),
        ("EDUCATION", "B.Tech CS & IT, 2024—28"),
        ("FOCUS", "UI engineering & motion"),
        ("PRACTICE", "DSA in Java"),
    ]
    col = (W - AXIS) / 2
    for i, (k, v) in enumerate(meta):
        cx, cy = AXIS + (i % 2) * col, y + 80 + (i // 2) * 78
        s.text(cx, cy, k, "mono", 16, ink, tracking=1.5, extra=' fill-opacity=".55"')
        s.text(cx, cy + 34, v, "regular", 26, ink)
    s.write("ADARSH'26 — frontend developer. About: I build interfaces that feel alive — responsive, accessible "
            "and quietly animated. Right now I'm growing into full-stack architecture while sharpening my "
            "problem solving with DSA in Java.")


def toolkit(name, ink):
    rows = [
        ("LANGUAGES", ["Java", "JavaScript", "TypeScript", "HTML", "CSS"]),
        ("FRONTEND", ["React", "Next.js", "Tailwind CSS", "GSAP", "Framer Motion", "Three.js"]),
        ("BACKEND", ["Node.js", "Express", "PostgreSQL", "MongoDB", "Drizzle ORM", "Supabase"]),
        ("TOOLS", ["Git", "GitHub", "VS Code", "Figma", "Postman", "Vercel"]),
    ]

    def line(items):
        """Comma-separated list whose final joiner is an Eiko italic ampersand."""
        return [(", ".join(items[:-1]) + " ", "light"), ("&", "eiko"), (" " + items[-1], "light")]

    size = min(40, min((W - AXIS) / sum(measure(t, f, 1) for t, f in line(items)) for _, items in rows))
    top, row_h = 100, 104

    s = Svg(name, top + row_h * len(rows) - 20)
    marker(s, 0, top, "02", "TOOLKIT", ink)
    for i, (label, items) in enumerate(rows):
        y = top - 48 + i * row_h
        s.text(AXIS, y, label, "mono", 16, ink, tracking=1.5, extra=' fill-opacity=".55"')
        s.rich(AXIS, y + 46, [(t, font, f"{size + (3 if font == 'eiko' else 0):.1f}") for t, font in line(items)],
               f"{size:.1f}", ink)
    s.write("Toolkit — " + ". ".join(f"{label.title()}: {', '.join(items)}" for label, items in rows))


def portfolio(name, ink):
    """Whole image is the link to the portfolio, so it reads as one big call to action."""
    eiko_scale = 1.08
    line = [("VISIT MY ", "light", 1), ("portfolio", "eiko", eiko_scale), (" ↗", "light", 1)]
    size = W / sum(measure(t, f, scale) for t, f, scale in line) * .985
    top = 100
    baseline = top + 60 + size * .95  # clears the tall italic f
    caption = baseline + size * .42 + 20  # clears the italic p descender

    s = Svg(name, round(caption + 16))
    marker(s, 0, top, "03", "PORTFOLIO", ink)
    s.rich(0, baseline, [(t, f, f"{size * scale:.1f}") for t, f, scale in line], f"{size:.1f}", ink)
    s.text(AXIS, caption, "ADRZ-26.VERCEL.APP", "mono", LABEL, ink, tracking=1, extra=' fill-opacity=".55"')
    s.text(W, caption, "(CLICK TO OPEN ↗)", "mono", LABEL, ink, anchor="end", tracking=1)
    s.write("Visit my portfolio — adrz-26.vercel.app")


CELL = AXIS  # contact row: a marker cell plus three link cells, each as wide as the margin column
CELL_H = 150


def contact_marker(name, ink):
    s = Svg(name, CELL_H, width=CELL)
    marker(s, 0, 84, "04", "CONTACT", ink)
    s.write("Contact")


def contact_link(name, ink, word, handle):
    """One clickable quarter of the contact row."""
    s = Svg(name, CELL_H, width=CELL)
    s.rich(0, 76, [(word + " ", "light", 50), ("↗", "light", 40)], 50, ink)
    s.text(2, 120, handle, "mono", 15, ink, tracking=.5, extra=' fill-opacity=".55"')
    s.write(f"{word} ↗ {handle}")


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
    for old in OUT.glob("*.svg"):
        old.unlink()
    for theme, ink in (("light", INK), ("dark", PAPER)):
        intro(f"intro-{theme}.svg", ink)
        toolkit(f"toolkit-{theme}.svg", ink)
        portfolio(f"portfolio-{theme}.svg", ink)
        contact_marker(f"contact-{theme}.svg", ink)
        for word, handle in (("LinkedIn", "in/adarzhpathade"),
                             ("Email", "adarzhpathade@gmail.com"),
                             ("GitHub", "@adarzhpathade")):
            contact_link(f"contact-{word.lower()}-{theme}.svg", ink, word, handle)
    bust_readme_cache()
