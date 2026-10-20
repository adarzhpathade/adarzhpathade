"""Builds the README's SVG panels with subsetted, embedded fonts.

Usage: python scripts/build_assets.py [path/to/fonts]
Fonts default to the sibling portfolio project's src/fonts.
"""
import base64
import io
import sys
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "adrz - Portfolio" / "src" / "fonts"
OUT = ROOT / "assets"

DARK, LIGHT, INK, PAPER = "#080808", "#ECECEC", "#080808", "#F0F0F0"
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

    def __init__(self, name, height, bg):
        self.name, self.h, self.bg = name, height, bg
        self.defs, self.css, self.body = [], [], []
        self.used = {k: set() for k in FONTS}

    def text(self, x, y, s, font, size, fill, anchor="start", tracking=0, cls="", extra=""):
        self.used[font].update(s)
        self.body.append(
            f'<text x="{x:.1f}" y="{y:.1f}" class="{font} {cls}" font-size="{size}" fill="{fill}"'
            f' text-anchor="{anchor}" letter-spacing="{tracking}"{extra}>{escape(s)}</text>'
        )

    def runs(self, x, y, segments, size, fill, tracking=0, cls=""):
        """Inline mixed-font line. segments: [(text, font)]. Returns end x."""
        for s, font in segments:
            self.text(x, y, s, font, size, fill, tracking=tracking, cls=cls)
            x += measure(s, font, size, tracking)
        return x

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
        grain = (
            '<filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" stitchTiles="stitch"/>'
            '<feColorMatrix values="0 0 0 0 .5  0 0 0 0 .5  0 0 0 0 .5  0 0 0 .6 0"/></filter>'
        )
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{self.h}" viewBox="0 0 {W} {self.h}" role="img" aria-label="{escape(label)}">\n'
            f'<defs><clipPath id="frame"><rect width="{W}" height="{self.h}" rx="10"/></clipPath>{grain}{"".join(self.defs)}</defs>\n'
            f"<style>\n{self.font_faces()}\n{''.join(self.css)}\n</style>\n"
            f'<g clip-path="url(#frame)">\n<rect width="{W}" height="{self.h}" fill="{self.bg}"/>\n'
            + "\n".join(self.body)
            + f'\n<rect width="{W}" height="{self.h}" filter="url(#grain)" opacity=".05"/>\n</g>\n</svg>\n'
        )
        (OUT / self.name).write_text(svg, encoding="utf-8")
        print(f"{self.name}: {len(svg) / 1024:.0f} KB")


def section_label(s, num, title, fill, right=None):
    s.text(40, 52, f"({num})", "mono", 12, fill, tracking=1, extra=' fill-opacity=".55"')
    s.text(84, 52, f"— {title}", "mono", 12, fill, tracking=1)
    if right:
        s.text(W - 40, 52, right, "mono", 12, fill, anchor="end", tracking=1, extra=' fill-opacity=".55"')
    s.raw(f'<line x1="40" y1="72" x2="{W - 40}" y2="72" stroke="{fill}" stroke-opacity=".14"/>')


RISE_CSS = (
    ".rise{opacity:0;animation:rise 1.1s cubic-bezier(.16,1,.3,1) forwards}"
    "@keyframes rise{from{opacity:0;transform:translateY(60%)}to{opacity:1;transform:translateY(0)}}"
    ".fade{opacity:0;animation:fade 1s ease forwards}"
    "@keyframes fade{to{opacity:1}}"
    ".blur{opacity:0;filter:blur(10px);animation:blurin .9s ease forwards}"
    "@keyframes blurin{to{opacity:1;filter:blur(0)}}"
)


def hero():
    s = Svg("hero.svg", 620, DARK)
    s.css.append(RISE_CSS)
    s.css.append(
        ".blob{animation:drift 16s ease-in-out infinite}"
        "@keyframes drift{0%,100%{transform:translate(0,0)}33%{transform:translate(380px,60px)}66%{transform:translate(160px,-50px)}}"
        ".diff{mix-blend-mode:difference}"
        ".rise{transform-box:fill-box}"
    )
    s.defs.append(
        '<radialGradient id="blob"><stop offset="0" stop-color="#fff" stop-opacity=".95"/>'
        '<stop offset=".55" stop-color="#fff" stop-opacity=".35"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        f'<clipPath id="nameClip"><rect x="0" y="150" width="{W}" height="300"/></clipPath>'
    )
    s.raw('<ellipse class="blob" cx="330" cy="330" rx="260" ry="190" fill="url(#blob)"/>')
    s.raw('<g class="diff">')

    s.text(40, 52, "(FRONTEND DEVELOPER)", "mono", 12, PAPER, tracking=1, cls="fade", extra=' style="animation-delay:.2s"')
    s.text(W - 40, 52, "(B.TECH CS & IT '28)", "mono", 12, PAPER, anchor="end", tracking=1, cls="fade", extra=' style="animation-delay:.2s"')
    s.text(W / 2, 150, "MIXING CODE, AI, MOTION, & VISUALS", "regular", 20, PAPER, anchor="middle", tracking=1.5,
           cls="fade", extra=' style="animation-delay:.9s"')

    name, target = "ADARSH", 1000
    size = round(target / measure(name, "light", 1))
    x = (W - measure(name, "light", size)) / 2 - 20
    baseline = 418
    s.raw('<g clip-path="url(#nameClip)">')
    for i, ch in enumerate(name):
        s.text(x, baseline, ch, "light", size, PAPER, cls="rise", extra=f' style="animation-delay:{.25 + i * .07:.2f}s"')
        x += measure(ch, "light", size)
    s.raw("</g>")
    s.text(x + 8, baseline - size * .62, "'26", "regular", 34, PAPER, cls="fade", extra=' style="animation-delay:1s"')

    seg = [("PATHADE — ", "regular"), ("Readme", "eiko")]
    total = sum(measure(t, f, 30, 0) for t, f in seg)
    s.raw('<g class="fade" style="animation-delay:1.2s">')
    s.runs((W - total) / 2, 520, seg, 30, PAPER)
    s.raw("</g>")

    s.text(40, 588, "SCROLL ↓", "mono", 12, PAPER, tracking=1, cls="fade", extra=' style="animation-delay:1.4s"')
    s.text(W - 40, 588, "©2026", "mono", 12, PAPER, anchor="end", tracking=1, cls="fade", extra=' style="animation-delay:1.4s"')
    s.raw("</g>")
    s.write("Adarsh Pathade — frontend developer mixing code, AI, motion and visuals")


def about():
    s = Svg("about.svg", 540, LIGHT)
    s.css.append(RISE_CSS)
    section_label(s, "01", "ABOUT", INK, right="INTRO")

    words = [
        ("I", "light"), ("build", "light"), ("interfaces", "light"), ("that", "light"), ("feel", "eiko"),
        ("alive", "light"), ("—", "light"), ("responsive,", "light"), ("accessible", "light"), ("and", "light"),
        ("quietly", "eiko"), ("animated.", "light"), ("Right", "light"), ("now", "light"), ("I'm", "light"),
        ("growing", "light"), ("into", "light"), ("full-stack", "eiko"), ("architecture", "light"), ("while", "light"),
        ("sharpening", "light"), ("my", "light"), ("problem", "light"), ("solving", "light"), ("with", "light"),
        ("DSA", "light"), ("in", "light"), ("Java.", "light"),
    ]
    size, lh, left, right = 42, 52, 300, W - 40
    x, y, delay = left, 140, .2
    for word, font in words:
        fs = size + (4 if font == "eiko" else 0)
        w = measure(word, font, fs)
        if x + w > right:
            x, y = left, y + lh
        s.text(x, y, word, font, fs, INK, cls="blur", extra=f' style="animation-delay:{delay:.2f}s"')
        x += w + measure(" ", "light", size)
        delay += .045

    s.raw(f'<line x1="40" y1="410" x2="{W - 40}" y2="410" stroke="{INK}" stroke-opacity=".14"/>')
    meta = [
        ("ROLE", "Frontend Developer"),
        ("EDUCATION", "B.Tech CS & IT, 2024—28"),
        ("FOCUS", "UI engineering & motion"),
        ("PRACTICE", "DSA in Java"),
    ]
    col = (W - 80) / 4
    for i, (k, v) in enumerate(meta):
        cx = 40 + i * col
        s.text(cx, 448, k, "mono", 11, INK, tracking=1, cls="fade", extra=f' fill-opacity=".5" style="animation-delay:{1.4 + i * .1:.1f}s"')
        s.text(cx, 482, v, "regular", 19, INK, cls="fade", extra=f' style="animation-delay:{1.5 + i * .1:.1f}s"')
    s.write("About: I build interfaces that feel alive — responsive, accessible and quietly animated.")


def toolkit():
    s = Svg("toolkit.svg", 520, DARK)
    s.css.append(RISE_CSS)
    section_label(s, "02", "TOOLKIT", PAPER, right="STACK")
    s.runs(40, 170, [("TOOLS OF THE ", "light"), ("trade", "eiko")], 64, PAPER, cls="fade")

    cols = [
        ("LANGUAGES", ["Java", "JavaScript", "TypeScript", "HTML5", "CSS3"]),
        ("FRONTEND", ["React.js", "Next.js", "Tailwind CSS", "GSAP", "Framer Motion", "Three.js"]),
        ("BACKEND", ["Node.js", "Express.js", "PostgreSQL", "MongoDB", "Drizzle ORM", "Supabase"]),
        ("TOOLS", ["Git & GitHub", "VS Code", "Figma", "Postman", "Vercel"]),
    ]
    col = (W - 80) / 4
    for i, (head, items) in enumerate(cols):
        cx = 40 + i * col
        s.text(cx, 242, f"0{i + 1}", "mono", 11, PAPER, tracking=1, extra=' fill-opacity=".4"')
        s.text(cx + 30, 242, head, "mono", 11, PAPER, tracking=1)
        s.raw(f'<line x1="{cx}" y1="258" x2="{cx + col - 24}" y2="258" stroke="{PAPER}" stroke-opacity=".18"/>')
        for j, item in enumerate(items):
            s.text(cx, 296 + j * 34, item, "regular", 21, PAPER, cls="blur",
                   extra=f' style="animation-delay:{.3 + i * .12 + j * .06:.2f}s"')
    s.write("Toolkit: Java, JavaScript, TypeScript, React, Next.js, Tailwind, GSAP, Framer Motion, Three.js, Node.js, Express, PostgreSQL, MongoDB, Drizzle, Supabase, Git, Figma, Vercel")


def work_header():
    s = Svg("work.svg", 220, LIGHT)
    s.css.append(RISE_CSS)
    section_label(s, "03", "SELECTED WORK", INK, right="2 PROJECTS")
    s.runs(40, 180, [("SELECTED ", "light"), ("work", "eiko")], 76, INK, cls="fade")
    s.text(W - 40, 180, "(CLICK A PROJECT ↗)", "mono", 12, INK, anchor="end", tracking=1, extra=' fill-opacity=".55"')
    s.write("Selected work")


def project(file, num, title, accent, kicker, lines, tags):
    s = Svg(file, 230, LIGHT)
    s.css.append(RISE_CSS)
    s.css.append(".nudge{animation:nudge 2.4s ease-in-out infinite}@keyframes nudge{0%,100%{transform:translate(0,0)}50%{transform:translate(5px,-5px)}}")
    s.raw(f'<line x1="40" y1="1" x2="{W - 40}" y2="1" stroke="{INK}" stroke-opacity=".14"/>')
    s.text(40, 62, f"({num})", "mono", 12, INK, tracking=1, extra=' fill-opacity=".55"')
    s.text(40, 200, kicker, "mono", 11, INK, tracking=1, extra=' fill-opacity=".55"')
    s.raw('<g class="fade" style="animation-delay:.2s">')
    s.runs(120, 132, [(title, "light"), (accent, "eiko")], 96, INK)
    s.raw("</g>")
    for i, line in enumerate(lines):
        s.text(720, 74 + i * 26, line, "regular", 17, INK, extra=' fill-opacity=".7"')
    s.text(720, 176, "  /  ".join(tags), "mono", 11, INK, tracking=.8)
    s.raw('<g class="nudge">')
    s.text(W - 40, 205, "(VIEW) ↗", "mono", 12, INK, anchor="end", tracking=1)
    s.raw("</g>")
    s.write(f"{title}{accent} — {' '.join(lines)}")


def contact():
    s = Svg("contact.svg", 460, DARK)
    s.css.append(RISE_CSS)
    s.css.append(".rise{transform-box:fill-box}")
    s.defs.append(f'<clipPath id="talkClip"><rect x="0" y="110" width="{W}" height="230"/></clipPath>')
    section_label(s, "04", "CONTACT", PAPER, right="SAY HELLO")
    seg = [("LET'S ", "light"), ("talk", "eiko")]
    size = 190
    total = sum(measure(t, f, size) for t, f in seg)
    s.raw('<g clip-path="url(#talkClip)"><g class="rise" style="animation-delay:.2s">')
    s.runs((W - total) / 2, 300, seg, size, PAPER)
    s.raw("</g></g>")
    s.text(W / 2, 360, "LINKS BELOW ↓", "mono", 12, PAPER, anchor="middle", tracking=1, cls="fade", extra=' style="animation-delay:.9s"')
    s.raw(f'<line x1="40" y1="400" x2="{W - 40}" y2="400" stroke="{PAPER}" stroke-opacity=".14"/>')
    s.text(40, 432, "ADARSH PATHADE ©2026", "mono", 11, PAPER, tracking=1, extra=' fill-opacity=".55"')
    s.text(W - 40, 432, "MIXING CODE, AI, MOTION, & VISUALS", "mono", 11, PAPER, anchor="end", tracking=1, extra=' fill-opacity=".55"')
    s.write("Let's talk")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    hero()
    about()
    toolkit()
    work_header()
    project("project-eligify.svg", "01", "ELIGIFY ", "ai", "GOVERNMENT SCHEME DISCOVERY",
            ["AI-powered platform that helps citizens find", "the schemes they're eligible for in minutes,",
             "with secure auth and document verification."],
            ["NEXT.JS", "TYPESCRIPT", "SUPABASE", "DRIZZLE"])
    project("project-storesync.svg", "02", "STORE", "sync", "STORE MANAGEMENT PLATFORM",
            ["Fast, no-bloat operations hub for single-store", "owners: POS billing, inventory, worker",
             "management and PDF invoices."],
            ["NEXT.JS", "TYPESCRIPT", "POSTGRESQL", "DRIZZLE"])
    contact()
