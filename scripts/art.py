"""Procedural dithered artwork for the README panels.

Everything is a 1-bit ordered-dither of a generated height/brightness field, saved as a
transparent grey PNG so one image works on both the light and the dark GitHub themes.
"""
import base64
import io

import numpy as np
from PIL import Image


def fbm(h, w, seed, octaves=5, base=3, persist=.5):
    """Fractal value noise in 0..1, made from bicubic-upscaled random grids."""
    rng = np.random.default_rng(seed)
    out, amp, tot = np.zeros((h, w)), 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o
        grid = rng.random((n + 1, max(2, int(n * w / h) + 1)))
        img = Image.fromarray((grid * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        out += np.asarray(img) / 255 * amp
        tot += amp
        amp *= persist
    return out / tot


def _bayer(n):
    m = np.array([[0, 2], [3, 1]])
    while m.shape[0] < n:
        m = np.block([[4 * m, 4 * m + 2], [4 * m + 3, 4 * m + 1]])
    return (m + .5) / m.size


def dither(v):
    h, w = v.shape
    b = _bayer(8)
    thr = np.tile(b, (h // 8 + 1, w // 8 + 1))[:h, :w]
    return np.clip(v, 0, 1) > thr


def png_uri(mask, gray):
    """Transparent PNG whose set pixels are `gray` (8 on the light theme, 240 on the dark one)."""
    la = np.zeros(mask.shape + (2,), np.uint8)
    la[..., 0] = gray
    la[..., 1] = mask * 255
    buf = io.BytesIO()
    Image.fromarray(la, "LA").save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _stars(v, seed, density=.0016):
    rng = np.random.default_rng(seed)
    dots = rng.random(v.shape) < density
    return np.where((v < .05) & dots, 1.0, v)


def planet(w, h, seed=3):
    """Banded gas giant with a tilted ring and a scatter of stars. Returns (field, (cx, cy, R, tilt))."""
    y, x = np.mgrid[0:h, 0:w].astype(float)
    cx, cy, R = w * .44, h * .5, h * .27
    dx, dy = (x - cx) / R, (y - cy) / R
    r2 = dx * dx + dy * dy
    inside = r2 < 1
    nz = np.sqrt(np.clip(1 - r2, 0, 1))
    light = np.array([-.55, -.6, .58])
    light /= np.linalg.norm(light)
    lam = np.clip(dx * light[0] + dy * light[1] + nz * light[2], 0, 1)
    turb = fbm(h, w, seed, 5, 3)
    bands = .55 + .45 * np.sin(dy * 15 + turb * 7)
    surf = lam ** .85 * (.5 + .5 * bands) + .22 * (1 - nz) ** 3 * lam

    tilt = np.deg2rad(-17)
    rx = dx * np.cos(tilt) + dy * np.sin(tilt)
    ry = -dx * np.sin(tilt) + dy * np.cos(tilt)
    s = np.sqrt(rx ** 2 + (ry / .26) ** 2)
    ring = (s > 1.45) & (s < 2.35)
    gaps = ((s > 1.78) & (s < 1.86)) | ((s > 2.1) & (s < 2.14))
    ring &= ~gaps
    ring_v = (.55 + .4 * np.sin(s * 46 + turb * 4)) * (1 - .35 * (s - 1.45)) * np.clip(.35 + 1.1 * (1 - (ry > 0) * 0), 0, 1)
    front = ring & (ry > 0)
    back = ring & (ry <= 0) & ~inside
    v = np.where(front, ring_v, np.where(inside, surf, np.where(back, ring_v * .8, 0)))
    return _stars(v, seed + 9), (cx, cy, R, -17)


def galaxy(w, h, seed=5):
    y, x = np.mgrid[0:h, 0:w].astype(float)
    ang = np.deg2rad(-24)
    dx, dy = (x - w / 2) / (w * .62), (y - h / 2) / (h * .9)
    rx, ry = dx * np.cos(ang) + dy * np.sin(ang), (-dx * np.sin(ang) + dy * np.cos(ang)) / .42
    r = np.sqrt(rx ** 2 + ry ** 2) + 1e-6
    th = np.arctan2(ry, rx)
    arms = .5 + .5 * np.cos(2 * (th - 3.2 * np.log(r + .08)))
    noise = fbm(h, w, seed, 5, 4)
    v = (np.exp(-r * 2.4) * (.25 + 1.1 * arms) + 1.4 * np.exp(-r * 11)) * (.55 + .9 * noise)
    return _stars(v, seed + 1, .002)


def nebula(w, h, seed=8):
    n = fbm(h, w, seed, 6, 2)
    m = fbm(h, w, seed + 4, 4, 3)
    v = np.clip((n - .38) * 2.4, 0, 1) ** 1.2 * (.45 + .8 * m)
    return _stars(v, seed + 2, .0035)


def rocks(w, h, seed=11):
    n = fbm(h, w, seed, 5, 4)
    ridged = 1 - np.abs(2 * n - 1)
    m = fbm(h, w, seed + 5, 3, 5)
    return (ridged ** 4.5) * .85 * (.4 + .6 * m)
