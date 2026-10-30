"""SENTINEX AI — cinematic animated GitHub banner.

A layered motion-graphics composition rendered programmatically (Pillow +
ffmpeg via imageio-ffmpeg). Every layer animates independently with
seamless-loop mathematics: every periodic term completes an integer number of
cycles across the loop duration T, so frame(t=0) == frame(t=T) by
construction.

Layers (visual hierarchy: brain + heart are the focal point):
  G. city skyline (2 parallax rows, flickering windows) + atmosphere
  E. neural data streams with travelling particles
  A. AI brain — breathing glow, shimmering synapses, light pulses
  B. central heart — heartbeat, cyan/purple/pink transitions, energy waves
  C. holographic rings — multi-speed rotation, scanning light, indicators
  D. floating emotion badges — orbital drift, gentle rotation/scale
  F. analytics deck — bars, waveform, gauge, KPI chips
  + animated SENTINEX logo mark, gradient title, subtitle chip, tagline

Outputs (only these):
    assets/github-banner.gif           (quantized, optimized)
    assets/github-banner.png           (static high-quality fallback)
    assets/github-banner-preview.mp4   (full-quality H.264 preview)

Usage (from repo root):
    venv/Scripts/python.exe scripts/generate_cinematic_banner.py
"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS = REPO_ROOT / "assets"

# ---------------------------------------------------------------- config ---
W, H = 1600, 900
T = 10.5          # loop duration (s) — every periodic term uses integer cycles
FPS = 20          # 20 fps → 210 frames
COLORS = 112      # GIF adaptive palette
CX, CY = 1120, 400  # brain / heart / rings focal centre

BG_TOP = (6, 9, 18)
BG_BOT = (13, 18, 34)
INDIGO = (99, 102, 241)
INDIGO_L = (129, 140, 248)
VIOLET = (168, 85, 247)
CYAN = (34, 211, 238)
GREEN = (52, 211, 153)
ROSE = (251, 113, 133)
PINK = (244, 114, 182)
AMBER = (251, 191, 36)
INK = (226, 232, 240)
INK_DIM = (143, 163, 194)
INK_FAINT = (91, 111, 147)
PANEL = (13, 20, 37)
EDGE = (28, 42, 71)

FONT_DIR = Path("C:/Windows/Fonts")
FRAME_COUNT = int(T * FPS)

_rng_state = {"seed": 20261031}


def rng() -> float:
    """Small deterministic LCG so the composition is reproducible."""
    _rng_state["seed"] = (_rng_state["seed"] * 1103515245 + 12345) % (2**31)
    return _rng_state["seed"] / 2**31


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)


# ------------------------------------------------------------ glow sprites ---
def glow_sprite(radius: int, color: tuple[int, int, int], peak_alpha: int = 255) -> Image.Image:
    """Pre-blurred radial glow with alpha → 0 at the sprite edge (no square
    cutoff), sized 2.6× the core radius so falloff never touches the border."""
    size = int(radius * 2.6)
    c = size // 2
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    steps = 10
    for i in range(steps, 0, -1):
        r = radius * i / steps
        a = int(peak_alpha * (1 - i / (steps + 1)) ** 1.8)
        ImageDraw.Draw(layer).ellipse([c - r, c - r, c + r, c + r], fill=color + (a,))
    return layer.filter(ImageFilter.GaussianBlur(radius * 0.10))


def paste_glow(img: Image.Image, sprite: Image.Image, cx: float, cy: float) -> None:
    half = sprite.size[0] // 2
    img.paste(sprite, (int(cx - half), int(cy - half)), sprite)


GLOWS = {
    "cyan_s": glow_sprite(14, CYAN, 235),
    "violet_s": glow_sprite(14, VIOLET, 235),
    "indigo_m": glow_sprite(26, INDIGO_L, 220),
    "cyan_m": glow_sprite(26, CYAN, 220),
    "pink_m": glow_sprite(26, PINK, 220),
    "brain": glow_sprite(300, INDIGO, 120),
    "brain2": glow_sprite(230, VIOLET, 90),
    "heart_glow": glow_sprite(150, PINK, 150),
    "logo_glow": glow_sprite(90, INDIGO_L, 130),
    "dot": glow_sprite(5, (255, 255, 255), 220),
}


# ------------------------------------------------------------------ city ---
def build_city() -> tuple[Image.Image, Image.Image, list[dict]]:
    """Two skyline rows (back = hazy tall, front = darker) + window flicker specs."""
    def row(count: int, base_y: int, min_w: int, max_w: int, min_h: int, max_h: int, color, alpha: int) -> tuple[Image.Image, list[dict]]:
        img = Image.new("RGBA", (W + 40, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        windows: list[dict] = []
        x = -10
        while x < W + 30:
            bw = int(min_w + rng() * (max_w - min_w))
            bh = int(min_h + rng() * (max_h - min_h))
            top = base_y - bh
            draw.rectangle([x, top, x + bw, base_y], fill=color + (alpha,))
            # antenna on some buildings
            if rng() > 0.72:
                draw.line([(x + bw // 2, top), (x + bw // 2, top - 18)], fill=color + (alpha,), width=2)
                draw.ellipse([x + bw // 2 - 2, top - 22, x + bw // 2 + 2, top - 18], fill=(255, 80, 80, alpha))
            # window grid
            for wy in range(top + 12, base_y - 10, 16):
                for wx in range(x + 6, x + bw - 6, 12):
                    if rng() > 0.45:
                        lit = 110 + int(rng() * 90)
                        # cyan-ish or warm windows
                        col = (168, 220, 255) if rng() > 0.5 else (255, 214, 150)
                        draw.rectangle([wx, wy, wx + 4, wy + 6], fill=col + (min(lit, alpha),))
                        if rng() > 0.93:  # a few windows flicker (periodic)
                            windows.append({"x": wx, "y": wy, "phase": rng(), "cycles": 1 + int(rng() * 3), "col": col})
            x += bw + int(3 + rng() * 10)
        return img, windows

    back, _ = row(30, 830, 60, 130, 260, 430, (24, 34, 62), 235)
    front, flicker = row(22, 860, 80, 170, 160, 320, (14, 21, 40), 255)
    return back, front, flicker


CITY_BACK, CITY_FRONT, FLICKER = build_city()


# ------------------------------------------------------------------ brain ---
def build_brain() -> tuple[list[tuple[int, int]], list[tuple[int, int]], list[list[tuple[int, int]]]]:
    """Node cloud shaped like a brain with nearest-neighbour synapses."""
    nodes: list[tuple[int, int]] = []
    # boundary nodes: two lobes with a slight indent at the centre bottom
    for i in range(30):
        theta = 2 * math.pi * i / 30
        r_mod = 1 + 0.10 * math.sin(3 * theta + 1.2) + 0.05 * math.sin(7 * theta)
        x = CX + math.cos(theta) * 218 * r_mod
        y = CY - 6 + math.sin(theta) * 158 * r_mod
        # vertical centre crease
        if abs(math.cos(theta)) < 0.16:
            x += (8 if math.sin(theta) > 0 else -8)
        nodes.append((int(x), int(y)))
    # interior nodes
    for _ in range(16):
        ang, r = rng() * 2 * math.pi, math.sqrt(rng()) * 0.78
        nodes.append((int(CX + math.cos(ang) * 190 * r), int(CY - 6 + math.sin(ang) * 135 * r)))

    edges: list[tuple[int, int]] = []
    for i, (x1, y1) in enumerate(nodes):
        dists = sorted(
            ((math.hypot(x2 - x1, y2 - y1), j) for j, (x2, y2) in enumerate(nodes) if j != i),
        )
        for _, j in dists[:2]:
            if (i, j) not in edges and (j, i) not in edges:
                edges.append((i, j))
    # a few long-range association fibres
    for _ in range(10):
        a, b = int(rng() * len(nodes)), int(rng() * len(nodes))
        if a != b and math.hypot(nodes[a][0] - nodes[b][0], nodes[a][1] - nodes[b][1]) > 150:
            edges.append((a, b))

    # pulse paths: chains of consecutive edges starting from the left lobe
    paths: list[list[tuple[int, int]]] = []
    for start in range(0, 12, 3):
        path = [nodes[start]]
        current = start
        for _ in range(4):
            nxt = [j for (i, j) in edges if i == current] or [j for (i, j) in edges if j == current]
            if not nxt:
                break
            current = nxt[int(rng() * len(nxt))]
            path.append(nodes[current])
        if len(path) >= 3:
            paths.append(path)
    return nodes, edges, paths


BRAIN_NODES, BRAIN_EDGES, BRAIN_PATHS = build_brain()


def polyline_point(path: list[tuple[int, int]], p: float) -> tuple[float, float]:
    segs = [math.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1]) for i in range(len(path) - 1)]
    total = sum(segs)
    target = p * total
    for i, seg in enumerate(segs):
        if target <= seg or i == len(segs) - 1:
            f = target / seg
            return (
                path[i][0] + (path[i + 1][0] - path[i][0]) * f,
                path[i][1] + (path[i + 1][1] - path[i][1]) * f,
            )
        target -= seg
    return path[-1]


# ------------------------------------------------------------ heart sprite ---
def heart_points(cx: float, cy: float, scale: float) -> list[tuple[float, float]]:
    pts = []
    for i in range(120):
        th = 2 * math.pi * i / 120
        x = 16 * math.sin(th) ** 3
        y = -(13 * math.cos(th) - 5 * math.cos(2 * th) - 2 * math.cos(3 * th) - math.cos(4 * th))
        pts.append((cx + x * scale, cy + y * scale))
    return pts


def build_heart_sprites() -> list[Image.Image]:
    """Three tinted gradient hearts; per-frame we blend between them."""
    sprites = []
    size = 300
    for color in (CYAN, VIOLET, PINK):
        layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).polygon(heart_points(size / 2, size / 2 + 6, 6.2), fill=255)
        grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for y in range(size):
            t = y / size
            c = tuple(int(a + (b - a) * t) for a, b in zip((255, 255, 255), color))
            gd.line([(0, y), (size, y)], fill=c + (255,))
        layer.paste(grad, (0, 0), mask)
        layer = layer.filter(ImageFilter.GaussianBlur(1.5))
        sprites.append(layer)
    return sprites


HEART_SPRITES = build_heart_sprites()


# ------------------------------------------------------- emoji badges -------
def build_emoji(kind: str) -> Image.Image:
    """Flat vector emotion badge with soft glow — clean, minimal faces."""
    size = 116
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = {"happy": GREEN, "sad": ROSE, "calm": AMBER, "wow": CYAN, "love": PINK, "angry": (235, 87, 110)}[kind]
    glow = glow_sprite(40, c, 110)
    img.alpha_composite(glow, (size // 2 - glow.size[0] // 2, size // 2 - glow.size[1] // 2))
    d.ellipse([22, 22, size - 22, size - 22], fill=PANEL + (238,), outline=c + (235,), width=4)
    ex, ey = size / 2, size / 2 + 2

    if kind in ("happy", "love"):
        d.ellipse([ex - 24, ey - 22, ex - 10, ey - 8], fill=c + (255,))   # eyes
        d.ellipse([ex + 10, ey - 22, ex + 24, ey - 8], fill=c + (255,))
        d.arc([ex - 24, ey - 10, ex + 24, ey + 26], 15, 165, fill=c, width=5)  # smile
        if kind == "love":
            d.text((ex, ey - 34), "♥", font=font("segoeui.ttf", 16), fill=c, anchor="mm")
    elif kind in ("sad", "angry"):
        d.ellipse([ex - 24, ey - 20, ex - 10, ey - 6], fill=c + (255,))
        d.ellipse([ex + 10, ey - 20, ex + 24, ey - 6], fill=c + (255,))
        d.arc([ex - 24, ey + 4, ex + 24, ey + 40], 185, 355, fill=c, width=5)  # frown
        if kind == "angry":
            d.line([ex - 27, ey - 28, ex - 9, ey - 22], fill=c, width=4)   # brows
            d.line([ex + 9, ey - 22, ex + 27, ey - 28], fill=c, width=4)
    elif kind == "wow":
        d.ellipse([ex - 24, ey - 24, ex - 8, ey - 8], fill=c + (255,))     # round eyes
        d.ellipse([ex + 8, ey - 24, ex + 24, ey - 8], fill=c + (255,))
        d.ellipse([ex - 12, ey + 2, ex + 12, ey + 30], outline=c, width=5)  # O mouth
    else:  # calm
        d.line([ex - 26, ey - 12, ex - 8, ey - 12], fill=c, width=5)
        d.line([ex + 8, ey - 12, ex + 26, ey - 12], fill=c, width=5)
        d.line([ex - 16, ey + 18, ex + 16, ey + 18], fill=c, width=5)
    return img


EMOJIS = [
    {"sprite": build_emoji("happy"), "r": 305, "a": 1, "phase": 0.00, "base": -140, "bob": 2, "scale_c": 1},
    {"sprite": build_emoji("sad"), "r": 305, "a": 1, "phase": 0.50, "base": -40, "bob": 3, "scale_c": 2},
    {"sprite": build_emoji("wow"), "r": 368, "a": 1, "phase": 0.25, "base": 50, "bob": 1, "scale_c": 1},
    {"sprite": build_emoji("calm"), "r": 368, "a": 1, "phase": 0.75, "base": 130, "bob": 3, "scale_c": 2},
    {"sprite": build_emoji("love"), "r": 238, "a": 2, "phase": 0.12, "base": 105, "bob": 2, "scale_c": 1},
    {"sprite": build_emoji("angry"), "r": 238, "a": 2, "phase": 0.62, "base": -75, "bob": 1, "scale_c": 2},
]


# ------------------------------------------------------------ logo/text -----
def gradient_text(canvas: Image.Image, xy: tuple[int, int], text, fnt, c1, c2) -> None:
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=fnt, fill=255)
    grad = Image.new("RGB", canvas.size, c1)
    gd = ImageDraw.Draw(grad)
    x0, _, x1, _ = mask.getbbox()
    for x in range(x0, x1):
        t = (x - x0) / max(1, x1 - x0)
        gd.line([(x, 0), (x, canvas.size[1])], fill=tuple(int(a + (b - a) * t) for a, b in zip(c1, c2)))
    canvas.paste(grad, (0, 0), mask)


def build_logo(scale: int = 2) -> Image.Image:
    """The SENTINEX mark: gradient rounded square + signal arc + core dot."""
    s = 96 * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for y in range(s):
        t = y / s
        d.line([(0, y), (s, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(INDIGO, VIOLET)))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.28), fill=255)
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    od = ImageDraw.Draw(out)
    od.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.28), outline=(255, 255, 255, 60), width=scale)
    # signal arc + core dot (matches the app icon)
    od.arc([int(s * 0.22), int(s * 0.30), int(s * 0.78), int(s * 0.86)], 200, 340, fill="white", width=3 * scale)
    r = 4.5 * scale
    od.ellipse([s / 2 - r, s * 0.72 - r, s / 2 + r, s * 0.72 + r], fill="white")
    return out


LOGO = build_logo(1)


# ------------------------------------------------------------- vignette -----
def build_vignette() -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(40):
        inset = i * 3
        a = int(1.6 * i)
        d.rectangle([inset, inset, W - inset, H - inset], outline=(0, 0, 0, a), width=3)
    return img.filter(ImageFilter.GaussianBlur(28))


VIGNETTE = build_vignette()


# --------------------------------------------------------- static canvases --
def base_sky() -> Image.Image:
    img = Image.new("RGB", (W, H), BG_TOP)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOT)))
    # stars
    for _ in range(70):
        x, y = int(rng() * W), int(rng() * 420)
        a = int(40 + rng() * 110)
        d.ellipse([x, y, x + 1, y + 1], fill=(200, 215, 255, a) if False else (int(200 * a / 255), int(215 * a / 255), 255))
    return img


SKY = base_sky()

PANEL_RECT = (64, 782, 1536, 862)
PANEL_BASE = Image.new("RGBA", (W, H), (0, 0, 0, 0))
_pd = ImageDraw.Draw(PANEL_BASE)
_pd.rounded_rectangle(PANEL_RECT, 14, fill=PANEL + (225,), outline=EDGE + (255,), width=1)
_pd.text((PANEL_RECT[0] + 18, PANEL_RECT[1] + 8), "SENTIMENT ANALYTICS — LIVE", font=font("seguisb.ttf", 11), fill=INK_FAINT)

TEXT_BASE = Image.new("RGBA", (W, H), (0, 0, 0, 0))
_td = ImageDraw.Draw(TEXT_BASE)
# subtitle chip
sub = "AI-POWERED REVIEW INTELLIGENCE"
f_sub = font("seguisb.ttf", 19)
sw = _td.textlength(sub, font=f_sub)
_td.rounded_rectangle([180, 148, 180 + sw + 36, 186], 19, fill=(99, 102, 241, 44), outline=(129, 140, 248, 130), width=1)
_td.text((180 + 18, 154), sub, font=f_sub, fill=(165, 180, 252))
# title
gradient_text(TEXT_BASE, (180, 58), "SENTINEX AI", font("seguisb.ttf", 60), (165, 180, 252), (216, 180, 254))
# tagline
_td.text((180, 208), "TURN CUSTOMER OPINIONS INTO BUSINESS DECISIONS.", font=font("segoeuil.ttf", 24), fill=INK)


# ------------------------------------------------------------- particles ----
ATMOS = [
    {"x": rng() * W, "y": rng() * H, "speed": (1 + int(rng() * 2)), "r": 1 + rng() * 1.6, "phase": rng(), "col": CYAN if rng() > 0.5 else VIOLET}
    for _ in range(34)
]

STREAMS = [
    {"y": 268, "x0": 330, "x1": 850, "n": 9, "amp": 10, "col": CYAN},
    {"y": 540, "x0": 330, "x1": 850, "n": 9, "amp": 12, "col": VIOLET},
    {"y": 400, "x0": 1400, "x1": 1560, "n": 5, "amp": 8, "col": CYAN},
]

BARS = [
    {"base": 0.42, "amp": 0.16, "cycles": 1, "phase": 0.0, "col": INDIGO_L},
    {"base": 0.62, "amp": 0.18, "cycles": 2, "phase": 0.15, "col": CYAN},
    {"base": 0.34, "amp": 0.20, "cycles": 1, "phase": 0.5, "col": VIOLET},
    {"base": 0.72, "amp": 0.14, "cycles": 3, "phase": 0.3, "col": GREEN},
    {"base": 0.50, "amp": 0.18, "cycles": 2, "phase": 0.7, "col": PINK},
    {"base": 0.84, "amp": 0.10, "cycles": 1, "phase": 0.9, "col": INDIGO_L},
]


# ------------------------------------------------------------ frame draw ----
def render_frame(t: float) -> Image.Image:
    """t in [0, T). Pure function of t → the loop is mathematically seamless."""
    img = SKY.copy()

    # G. city with restrained parallax (integer sine cycles across the loop)
    back_off = (int(6 * math.sin(2 * math.pi * t / T)), int(3 * math.sin(4 * math.pi * t / T)))
    front_off = (-4 * int(math.sin(2 * math.pi * t / T)), -2 * int(math.sin(4 * math.pi * t / T)))
    img.paste(CITY_BACK, back_off, CITY_BACK)
    img.paste(CITY_FRONT, front_off, CITY_FRONT)

    draw = ImageDraw.Draw(img, "RGBA")

    # flickering windows (periodic)
    for wdw in FLICKER:
        a = 0.5 + 0.5 * math.sin(2 * math.pi * wdw["cycles"] * t / T + wdw["phase"] * 2 * math.pi)
        col = wdw["col"]
        draw.rectangle([wdw["x"] + front_off[0], wdw["y"] + front_off[1], wdw["x"] + 4 + front_off[0], wdw["y"] + 6 + front_off[1]], fill=col + (int(90 + 130 * a),))

    # G. atmospheric particles drifting up (integer vertical wraps → seamless)
    for p in ATMOS:
        y = (p["y"] - p["speed"] * H * t / T) % H
        x = p["x"] + 14 * math.sin(2 * math.pi * t / T + p["phase"] * 2 * math.pi)
        a = int(70 + 60 * math.sin(2 * math.pi * t / T + p["phase"] * 2 * math.pi))
        draw.ellipse([x - p["r"], y - p["r"], x + p["r"], y + p["r"]], fill=p["col"] + (max(28, a),))

    # E. neural data streams
    for s in STREAMS:
        pts = []
        n_pts = 26
        for i in range(n_pts + 1):
            x = s["x0"] + (s["x1"] - s["x0"]) * i / n_pts
            y = s["y"] + s["amp"] * math.sin(2 * math.pi * (2 * i / n_pts + 1 * t / T))
            pts.append((x, y))
        draw.line(pts, fill=s["col"] + (44,), width=2)
        for i in range(s["n"]):
            f = ((t / T) + i / s["n"]) % 1
            idx = f * n_pts
            x0, y0 = pts[int(idx)]
            x1, y1 = pts[min(int(idx) + 1, n_pts)]
            frac = idx - int(idx)
            px, py = x0 + (x1 - x0) * frac, y0 + (y1 - y0) * frac
            trail = 4
            for k in range(1, trail + 1):
                ti = max(0, int(idx) - k)
                draw.ellipse([pts[ti][0] - 2, pts[ti][1] - 2, pts[ti][0] + 2, pts[ti][1] + 2], fill=s["col"] + (int(150 * (1 - k / trail)),))
            sprite = GLOWS["cyan_s"] if s["col"] == CYAN else GLOWS["violet_s"]
            paste_glow(img, sprite, px, py)

    # A. brain — breathing glow (5 cycles), synapses shimmer, light pulses
    breath = 0.5 + 0.5 * math.sin(2 * math.pi * 5 * t / T)
    glow = GLOWS["brain"]
    gx = int(CX - glow.size[0] / 2)
    gy = int(CY - 6 - glow.size[1] / 2)
    img.paste(glow, (gx, gy), glow)
    glow2 = GLOWS["brain2"]
    img.paste(glow2, (int(CX - glow2.size[0] / 2), int(CY - 6 - glow2.size[1] / 2)), glow2)

    synapse_alpha = int(70 + 50 * breath)
    for (i, j) in BRAIN_EDGES:
        draw.line([BRAIN_NODES[i], BRAIN_NODES[j]], fill=INDIGO_L + (synapse_alpha,), width=1)
    for i, (x, y) in enumerate(BRAIN_NODES):
        r = 2.4 + 0.9 * math.sin(2 * math.pi * 4 * t / T + i * 1.05)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(196, 205, 255, 235))
    for k, path in enumerate(BRAIN_PATHS):
        p = ((t / T) * (1 + k) + k * 0.31) % 1
        px, py = polyline_point(path, p)
        sprite = GLOWS["cyan_m"] if k % 2 == 0 else GLOWS["indigo_m"]
        paste_glow(img, sprite, px, py)
        draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(230, 235, 255, 240))

    # B. heart — heartbeat (11 beats), colour cycle, energy waves (6 per loop)
    beat_phase = (11 * t / T) % 1
    beat = 1.0
    if beat_phase < 0.14:            # lub
        beat = 1.0 + 0.16 * math.sin(math.pi * beat_phase / 0.14)
    elif 0.20 < beat_phase < 0.34:    # dub
        beat = 1.0 + 0.10 * math.sin(math.pi * (beat_phase - 0.20) / 0.14)
    hue_t = (0.5 + 0.5 * math.sin(2 * math.pi * t / T))  # 1 cycle across loop
    if hue_t < 0.5:
        # blend cyan→violet
        fa = hue_t * 2
        h0, h1 = HEART_SPRITES[0], HEART_SPRITES[1]
    else:
        # blend violet→pink
        fa = (hue_t - 0.5) * 2
        h0, h1 = HEART_SPRITES[1], HEART_SPRITES[2]
    blended = Image.new("RGBA", h0.size, (0, 0, 0, 0))
    blended.alpha_composite(h0)
    # Scale the existing alpha channel — putalpha with a constant would make
    # the transparent corners opaque and paste a dark box behind the heart.
    overlay = h1.copy()
    overlay.putalpha(overlay.split()[3].point(lambda v: int(v * min(1.0, fa))))
    blended.alpha_composite(overlay)

    wave_r = 40 + beat * 6
    for k in range(6):
        ph = ((6 * t / T) - k / 6) % 1
        r = 46 + ph * 170
        a = int((1 - ph) * 110)
        draw.ellipse([CX - r, CY - 6 - r, CX + r, CY - 6 + r], outline=PINK + (a,), width=2)

    hs = int(blended.size[0] * 0.62 * beat)
    heart_frame = blended.resize((hs, hs), Image.BICUBIC)
    img.paste(heart_frame, (int(CX - hs / 2), int(CY - 6 - hs / 2)), heart_frame)
    hg = GLOWS["heart_glow"]
    hg_frame = hg.resize((int(hg.size[0] * beat),) * 2, Image.BICUBIC)
    img.paste(hg_frame, (int(CX - hg_frame.size[0] / 2), int(CY - 6 - hg_frame.size[1] / 2)), hg_frame)

    # C. holographic rings — rotations at integer cycles, scanning arcs
    rings = [
        {"r": 238, "cycles": 2, "col": INDIGO_L, "scan": 3},
        {"r": 292, "cycles": -3, "col": VIOLET, "scan": -4},
        {"r": 346, "cycles": 1, "col": CYAN, "scan": 5},
    ]
    for ring in rings:
        r = ring["r"]
        rot = 360 * ring["cycles"] * t / T
        # dashed base ring: 5 arcs with gaps
        for seg in range(5):
            a0 = rot + seg * 72
            draw.arc([CX - r, CY - 6 - r, CX + r, CY - 6 + r], a0, a0 + 52, fill=ring["col"] + (105,), width=2)
        # scanning highlight arc + glow bead at its centre
        scan = ring["scan"] * 360 * t / T
        draw.arc([CX - r, CY - 6 - r, CX + r, CY - 6 + r], scan, scan + 26, fill=ring["col"] + (235,), width=3)
        mid = math.radians(scan + 13)
        sx, sy = CX + r * math.cos(mid), CY - 6 + r * math.sin(mid)
        sprite = GLOWS["cyan_m"] if ring["col"] != VIOLET else GLOWS["indigo_m"]
        paste_glow(img, sprite, sx, sy)
        # interface indicator dots riding the ring
        for dot in range(3):
            ang = math.radians(rot + dot * 120 + ring["r"])
            dx, dy = CX + r * math.cos(ang), CY - 6 + r * math.sin(ang)
            draw.ellipse([dx - 3, dy - 3, dx + 3, dy + 3], fill=INK + (210,))

    # D. floating emotion badges — orbital drift, gentle rotate + scale
    for e in EMOJIS:
        ang = 2 * math.pi * (e["a"] * t / T + e["phase"]) + math.radians(e["base"])
        ex = CX + e["r"] * math.cos(ang)
        ey = CY - 6 + e["r"] * 0.62 * math.sin(ang)
        ey += 10 * math.sin(2 * math.pi * e["bob"] * t / T)
        sc = 0.9 + 0.07 * math.sin(2 * math.pi * e["scale_c"] * t / T + e["phase"] * 5)
        rot = 9 * math.sin(2 * math.pi * e["scale_c"] * t / T + e["phase"] * 3)
        size = int(e["sprite"].size[0] * sc)
        spr = e["sprite"].resize((size, size), Image.BICUBIC).rotate(rot, expand=True, resample=Image.BICUBIC)
        img.paste(spr, (int(ex) - size // 2, int(ey) - size // 2), spr)

    # F. analytics deck
    img.paste(PANEL_BASE, (0, 0), PANEL_BASE)
    pd = ImageDraw.Draw(img, "RGBA")
    px0, py0, px1, py1 = PANEL_RECT
    # bars
    bar_w, bar_gap, bar_base_y = 26, 18, py1 - 12
    for i, b in enumerate(BARS):
        x = px0 + 96 + i * (bar_w + bar_gap)
        hgt = int((b["base"] + b["amp"] * math.sin(2 * math.pi * b["cycles"] * t / T + b["phase"] * 2 * math.pi)) * 54)
        pd.rounded_rectangle([x, bar_base_y - hgt, x + bar_w, bar_base_y], 4, fill=b["col"] + (215,))
    # waveform
    wl_x0, wl_x1 = px0 + 356, px0 + 956
    pts = []
    for i in range(90):
        x = wl_x0 + (wl_x1 - wl_x0) * i / 89
        y = (py0 + py1) / 2 + 4 + 12 * math.sin(2 * math.pi * (2 * i / 89 + t / T)) + 6 * math.sin(2 * math.pi * (5 * i / 89 - 2 * t / T))
        pts.append((x, y))
    pd.line(pts, fill=CYAN + (190,), width=2)
    # gauge
    gcx, gcy, gr = px0 + 1040, (py0 + py1) / 2, 26
    pd.arc([gcx - gr, gcy - gr, gcx + gr, gcy + gr], 0, 360, fill=EDGE + (255,), width=4)
    needle = -90 + 360 * 2 * t / T
    nang = math.radians(needle)
    pd.line([gcx, gcy, gcx + (gr - 5) * math.cos(nang), gcy + (gr - 5) * math.sin(nang)], fill=INDIGO_L + (230,), width=3)
    pd.ellipse([gcx - 3, gcy - 3, gcx + 3, gcy + 3], fill=INK + (255,))
    pd.text((gcx + gr + 14, gcy - 8), "87.9%", font=font("seguisb.ttf", 15), fill=INK)
    pd.text((gcx + gr + 14, gcy + 8), "reproduced acc.", font=font("segoeui.ttf", 9), fill=INK_FAINT)
    # KPI chips
    chips = [("MODELS", "3", INDIGO_L), ("REVIEWS", "48", CYAN), ("SEED", "42", VIOLET)]
    for i, (k, v, c) in enumerate(chips):
        x = px0 + 1240 + i * 84
        y = py0 + 24
        pd.text((x, y + 14), v, font=font("seguisb.ttf", 17), fill=c)
        pd.text((x, y + 36), k, font=font("segoeui.ttf", 8), fill=INK_FAINT)
        dot_a = int(120 + 100 * math.sin(2 * math.pi * (i + 1) * t / T))
        pd.ellipse([x - 12, y + 18, x - 6, y + 24], fill=c + (dot_a,))

    # logo (animated glow ring) + text block
    lg = GLOWS["logo_glow"]
    la = int(90 + 70 * (0.5 + 0.5 * math.sin(2 * math.pi * 2 * t / T)))
    lgf = lg.copy()
    lgf.putalpha(lgf.split()[3].point(lambda v: v * la // 255))
    img.paste(lgf, (int(118 - lgf.size[0] / 2), int(104 - lgf.size[1] / 2)), lgf)
    img.paste(LOGO, (70, 56), LOGO)
    img.paste(TEXT_BASE, (0, 0), TEXT_BASE)

    img.paste(VIGNETTE, (0, 0), VIGNETTE)
    return img


# ------------------------------------------------------------------ main ----
def main() -> None:
    import imageio_ffmpeg

    ASSETS.mkdir(exist_ok=True)
    gif_path = ASSETS / "github-banner.gif"
    png_path = ASSETS / "github-banner.png"
    mp4_path = ASSETS / "github-banner-preview.mp4"

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.Popen(
        [
            ffmpeg, "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{W}x{H}", "-pix_fmt", "rgb24", "-r", str(FPS),
            "-i", "-",
            "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(mp4_path),
        ],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    frames: list[Image.Image] = []
    for i in range(FRAME_COUNT):
        frame = render_frame(T * i / FRAME_COUNT)
        proc.stdin.write(frame.tobytes())  # type: ignore[union-attr]
        frames.append(frame.quantize(colors=COLORS, dither=Image.Dither.NONE))
        if i % 40 == 0:
            print(f"  rendered {i}/{FRAME_COUNT}", flush=True)

    proc.stdin.close()  # type: ignore[union-attr]
    proc.wait(timeout=120)

    png = render_frame(T * 0.12)
    png.save(png_path, optimize=True)

    frames[0].save(
        gif_path, save_all=True, append_images=frames[1:],
        duration=int(1000 / FPS), loop=0, optimize=True,
    )

    # ---- quality report -----------------------------------------------------
    seam_a = render_frame(0.0)
    seam_b = render_frame(T - 1.0 / FPS)
    import numpy as np

    diff = np.abs(np.asarray(seam_a, dtype=int) - np.asarray(seam_b, dtype=int)).mean()
    print(f"LOOP SEAM CHECK — mean abs pixel diff frame(0) vs frame(T-1/fps): {diff:.3f} (target < 3.0)")
    print(f"gif: {gif_path}  {gif_path.stat().st_size / 1e6:.2f} MB, frames={FRAME_COUNT}, duration={FRAME_COUNT * 1000 / FPS:.0f} ms")
    print(f"png: {png_path}  {png_path.stat().st_size / 1e6:.2f} MB")
    print(f"mp4: {mp4_path}  {mp4_path.stat().st_size / 1e6:.2f} MB")
    if diff >= 3.0:
        print("SEAM CHECK FAILED", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
