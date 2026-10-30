"""SENTINEX AI — cinematic product showcase video (independent of the banner).

An 18-second, 8-scene promotional film rendered programmatically:

  1. Neural field fading in                     (dark environment)
  2. Holographic AI brain activating            (sequential node ignition)
  3. Customer reviews as floating holo-cards
  4. Cards streaming into the AI core
  5. Sentiment signals identified (POS/NEG/NEU)
  6. Emotion + aspect intelligence panels
  7. Holographic analytics dashboard
  8. Brand reveal: SENTINEX AI + tagline

Cinematic techniques: a virtual 1840x1040 stage with an eased camera crop
(real pans), 0.5 s cross-fades between scenes, layered glow compositing,
parallax city depth, and progressive reveals. All art is original and
programmatic (Pillow), assembled with ffmpeg (imageio-ffmpeg).

Outputs (only these):
    assets/sentinex-product-showcase.mp4    (1600x900, 24 fps, H.264)
    assets/sentinex-product-showcase.png    (poster: brand-reveal frame)

Usage (from repo root):
    venv/Scripts/python.exe scripts/generate_product_showcase.py
"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

# Reuse the banner's verified art primitives (sprites, graph, city, logo).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_cinematic_banner import (  # noqa: E402
    AMBER,
    BG_BOT,
    BG_TOP,
    BRAIN_EDGES,
    BRAIN_NODES,
    CITY_BACK,
    CITY_FRONT,
    CYAN,
    EDGE,
    GLOWS,
    GREEN,
    INK,
    INK_DIM,
    INK_FAINT,
    INDIGO,
    INDIGO_L,
    LOGO,
    PINK,
    PANEL,
    ROSE,
    SKY,
    VIOLET,
    build_emoji,
    font,
    glow_sprite,
    gradient_text,
    paste_glow,
    polyline_point,
)

import imageio_ffmpeg  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS = REPO_ROOT / "assets"

OUT_W, OUT_H = 1600, 900          # camera crop
STAGE_W, STAGE_H = 1840, 1040     # virtual stage (camera pans inside it)
FPS = 24
DURATION = 18.0
FRAME_COUNT = int(DURATION * FPS)
XFADE = 0.5                       # cross-fade between scenes

CX, CY = STAGE_W / 2, STAGE_H / 2 - 20

#: camera travel per scene — wide world scenes pan, precise layouts lock.
CAM_AMP = {"neural": 1.0, "activate": 0.8, "reviews": 0.9, "flow": 0.6,
           "signals": 0.25, "panels": 0.0, "dashboard": 0.0, "reveal": 0.0}

SCENES = [
    ("neural",    0.0, 1.8),
    ("activate",  1.8, 2.2),
    ("reviews",   4.0, 2.4),
    ("flow",      6.4, 2.0),
    ("signals",   8.4, 2.2),
    ("panels",   10.6, 2.4),
    ("dashboard", 13.0, 1.8),
    ("reveal",   14.8, 3.2),
]

EMOJI_BADGES = {
    "happy": build_emoji("happy"),
    "sad": build_emoji("sad"),
    "wow": build_emoji("wow"),
}

#: soft dark spotlight behind the reveal typography
_band = Image.new("RGBA", (STAGE_W, 380), (0, 0, 0, 0))
ImageDraw.Draw(_band).rectangle([0, 30, STAGE_W, 350], fill=(6, 9, 18, 215))
TEXT_BAND = _band.filter(ImageFilter.GaussianBlur(28))

REVIEW_CARDS = [
    {"x": 250, "y": 300, "chip": ("POSITIVE", GREEN), "w": 300, "delay": 0.00},
    {"x": 700, "y": 210, "chip": ("NEGATIVE", ROSE), "w": 330, "delay": 0.22},
    {"x": 1130, "y": 330, "chip": ("NEUTRAL", CYAN), "w": 280, "delay": 0.44},
    {"x": 430, "y": 560, "chip": ("POSITIVE", GREEN), "w": 260, "delay": 0.62},
]


def ease(t: float) -> float:
    """Smoothstep easing."""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def environment(v: Image.Image, draw: ImageDraw.ImageDraw, t: float) -> None:
    """Shared dark futuristic environment (sky + parallax city)."""
    v.paste(SKY, (0, 0))
    off = (int(8 * math.sin(2 * math.pi * t / 12)), int(4 * math.sin(4 * math.pi * t / 12)))
    v.paste(CITY_BACK, off, CITY_BACK)
    v.paste(CITY_FRONT, (-off[0], -off[1]), CITY_FRONT)
    # drifting atmosphere
    for i in range(24):
        x = (i * 173 + 90 * t) % STAGE_W
        y = 120 + (i * 61) % 420 + 14 * math.sin(2 * math.pi * t / 6 + i)
        draw.ellipse([x - 1.4, y - 1.4, x + 1.4, y + 1.4], fill=CYAN + (60,))


# ------------------------------------------------------------------ scenes --
def scene_neural(v: Image.Image, d: ImageDraw.ImageDraw, u: float, t: float) -> None:
    """S1 — wide neural field igniting."""
    n_nodes = 46
    lit = int(ease(u / 0.8) * n_nodes)
    nodes = []
    for i in range(n_nodes):
        ang = i * 2.399  # golden-angle scatter
        r = 90 + (i % 7) * 78
        x = CX + math.cos(ang) * r * 1.55
        y = CY - 30 + math.sin(ang) * r * 0.85
        nodes.append((x, y))
    for i in range(lit):
        for j in range(i + 1, min(i + 3, lit)):
            if math.hypot(nodes[i][0] - nodes[j][0], nodes[i][1] - nodes[j][1]) < 300:
                d.line([nodes[i], nodes[j]], fill=INDIGO_L + (56,), width=1)
    for i in range(lit):
        x, y = nodes[i]
        sprite = GLOWS["cyan_s"] if i % 2 else GLOWS["violet_s"]
        paste_glow(v, sprite, x, y)
        d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(225, 232, 255, 235))


def scene_activate(v: Image.Image, d: ImageDraw.ImageDraw, u: float, t: float) -> None:
    """S2 — holographic brain igniting node by node."""
    ignite = ease(u / 0.75)
    lit = int(ignite * len(BRAIN_NODES))
    glow_a = int(200 * min(1, u * 1.4))
    g = GLOWS["brain"].copy()
    g.putalpha(g.split()[3].point(lambda x: x * glow_a // 255))
    paste_glow(v, g, CX, CY - 20)
    for i, (x, y) in enumerate(BRAIN_NODES):
        on = i < lit or (i - lit) / max(1, len(BRAIN_NODES) - lit) < ignite * 0.3
        if not on:
            d.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=INK_FAINT + (90,))
            continue
        r = 2.6 + 1.0 * math.sin(6 * t + i)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(210, 218, 255, 240))
    for k, (i, j) in enumerate(BRAIN_EDGES):
        if k / len(BRAIN_EDGES) < ignite:
            d.line([BRAIN_NODES[i], BRAIN_NODES[j]], fill=INDIGO_L + (120,), width=1)
    if u > 0.55:  # travelling pulses once the core is awake
        for k, off in enumerate((0.0, 0.33, 0.66)):
            p = (t * 0.35 + off) % 1
            path = [BRAIN_NODES[(k * 7) % len(BRAIN_NODES)], BRAIN_NODES[(k * 11 + 3) % len(BRAIN_NODES)], BRAIN_NODES[(k * 5 + 9) % len(BRAIN_NODES)]]
            px, py = polyline_point(path, p)
            paste_glow(v, GLOWS["cyan_m"] if k % 2 else GLOWS["indigo_m"], px, py)


def draw_review_card(v: Image.Image, card: dict, appear: float, x: float, y: float, scale: float) -> None:
    w, h = int(card["w"] * scale), int(120 * scale)
    img = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([20, 20, 20 + w, 20 + h], 12, fill=(13, 20, 37, 235), outline=(28, 42, 71, 255), width=1)
    for line in range(3):
        d.rounded_rectangle([34, 34 + line * 20, 20 + w - (70 if line == 1 else 34), 42 + line * 20], 3, fill=(255, 255, 255, 46))
    label, color = card["chip"]
    d.rounded_rectangle([34, 34 + 3 * 20, 34 + 92, 30 + 3 * 20 + 22], 8, fill=color + (44,))
    d.text((80, 34 + 3 * 20 + 11), label, font=font("seguisb.ttf", 11), fill=color, anchor="mm")
    a = img.split()[3].point(lambda p: int(p * appear))
    img.putalpha(a)
    v.paste(img, (int(x - (w + 40) / 2), int(y - (h + 40) / 2)), img)


def scene_reviews(v: Image.Image, d: ImageDraw.ImageDraw, u: float, t: float) -> None:
    """S3 — floating holographic review cards."""
    for card in REVIEW_CARDS:
        appear = ease((u - card["delay"]) / 0.5)
        if appear <= 0:
            continue
        bob = 8 * math.sin(2 * math.pi * t / 4 + card["delay"] * 9)
        draw_review_card(v, card, appear, card["x"], card["y"] + bob, 1.0)
    d.text((CX, 120), "CUSTOMER REVIEWS — INCOMING", font=font("seguisb.ttf", 20), fill=INK_DIM, anchor="mm")


def scene_flow(v: Image.Image, d: ImageDraw.ImageDraw, u: float, t: float) -> None:
    """S4 — cards stream into the AI core."""
    flow = ease(u)
    cx, cy = CX, CY - 20
    for card in REVIEW_CARDS:
        p = min(1.0, max(0.0, (flow - card["delay"] * 0.35) / 0.75))
        if p <= 0:
            draw_review_card(v, card, 1.0, card["x"], card["y"], 1.0)
            continue
        # bezier from card position into the core
        mx, my = (card["x"] + cx) / 2, min(card["y"], cy) - 140
        bx = (1 - p) ** 2 * card["x"] + 2 * (1 - p) * p * mx + p**2 * cx
        by = (1 - p) ** 2 * card["y"] + 2 * (1 - p) * p * my + p**2 * cy
        scale = 1.0 - 0.75 * p
        appear = 1.0 - max(0.0, (p - 0.8) / 0.2)
        if appear > 0:
            draw_review_card(v, card, appear, bx, by, scale)
        if 0.35 < p < 1.0:  # energy trail behind the card
            for k in range(1, 5):
                tp = max(0.0, p - k * 0.03)
                tx = (1 - tp) ** 2 * card["x"] + 2 * (1 - tp) * tp * mx + tp**2 * cx
                ty = (1 - tp) ** 2 * card["y"] + 2 * (1 - tp) * tp * my + tp**2 * cy
                d.ellipse([tx - 3, ty - 3, tx + 3, ty + 3], fill=CYAN + (int(140 * (1 - k / 5)),))
    # core brightens as reviews arrive
    pulse = 0.5 + 0.5 * math.sin(8 * t)
    paste_glow(v, GLOWS["brain"], cx, cy)
    paste_glow(v, GLOWS["brain2"], cx, cy)
    d.ellipse([cx - 10 - 6 * pulse, cy - 16 - 6 * pulse, cx + 10 + 6 * pulse, cy + 4 + 6 * pulse], fill=(235, 240, 255, 230))


def scene_signals(v: Image.Image, d: ImageDraw.ImageDraw, u: float, t: float) -> None:
    """S5 — positive / negative / neutral signals identified."""
    appear = ease(min(1, u / 0.5))
    signals = [
        ("POSITIVE", GREEN, 0.58, -330),
        ("NEGATIVE", ROSE, 0.27, 0),
        ("NEUTRAL", CYAN, 0.15, 330),
    ]
    for label, color, share, dx in signals:
        a = ease(max(0.0, min(1.0, (u - 0.1 - abs(dx) / 900) / 0.45)))
        x, y = CX + dx, CY - 20
        r = 64 + 6 * math.sin(6 * t + dx)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(13, 20, 37, 235), outline=color + (235,), width=4)
        for k in range(2):  # radiating energy rings
            ph = ((1.5 * t) - k / 2) % 1
            rr = r + ph * 46
            d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=color + (int((1 - ph) * 90),), width=2)
        d.text((x, y - 16), f"{int(share * 100 * a)}%", font=font("seguisb.ttf", 30), fill=color, anchor="mm")
        d.text((x, y + 22), label, font=font("seguisb.ttf", 14), fill=INK_DIM, anchor="mm")
    paste_glow(v, GLOWS["brain"], CX, CY - 20)
    d.text((CX, CY + 150), "SENTIMENT INTELLIGENCE", font=font("seguisb.ttf", 18), fill=INK_DIM, anchor="mm")
    _ = appear  # gates handled per-signal


def scene_panels(v: Image.Image, d: ImageDraw.ImageDraw, u: float, t: float) -> None:
    """S6 — emotion + aspect intelligence visualizations."""
    appear = ease(min(1, u / 0.6))
    slide = int((1 - appear) * 60)

    # left panel: emotion intelligence
    ex, ey, ew, eh = 150 + slide, 170, 480, 420
    d.rounded_rectangle([ex, ey, ex + ew, ey + eh], 16, fill=(13, 20, 37, 232), outline=EDGE + (255,), width=1)
    d.text((ex + 24, ey + 20), "EMOTION INTELLIGENCE", font=font("seguisb.ttf", 17), fill=PINK)
    emotions = [("Joy", 0.62, GREEN), ("Anger", 0.38, ROSE), ("Sadness", 0.24, CYAN), ("Frustration", 0.31, AMBER), ("Disappointment", 0.19, VIOLET)]
    for i, (label, val, color) in enumerate(emotions):
        y = ey + 66 + i * 62
        d.text((ex + 24, y), label, font=font("segoeui.ttf", 14), fill=INK_DIM)
        d.rounded_rectangle([ex + 24, y + 24, ex + ew - 24, y + 38], 7, fill=(255, 255, 255, 18))
        w = int((ew - 48) * val * ease(min(1, max(0, (u - 0.15 - i * 0.08) / 0.5))))
        d.rounded_rectangle([ex + 24, y + 24, ex + 24 + w, y + 38], 7, fill=color + (215,))

    # right panel: aspect intelligence with evidence chips
    ax, ay, aw, ah = STAGE_W - 630 - slide, 170, 480, 420
    d.rounded_rectangle([ax, ay, ax + aw, ay + ah], 16, fill=(13, 20, 37, 232), outline=EDGE + (255,), width=1)
    d.text((ax + 24, ay + 20), "ASPECT INTELLIGENCE", font=font("seguisb.ttf", 17), fill=INDIGO_L)
    aspects = [("battery life", "POSITIVE", GREEN), ("delivery", "NEGATIVE", ROSE), ("app performance", "POSITIVE", GREEN), ("customer support", "NEGATIVE", ROSE), ("pricing", "NEUTRAL", CYAN)]
    for i, (label, sentiment, color) in enumerate(aspects):
        y = ay + 66 + i * 62
        chip_a = ease(max(0.0, min(1.0, (u - 0.2 - i * 0.1) / 0.4)))
        d.rounded_rectangle([ax + 24, y, ax + aw - 24, y + 46], 10, fill=(255, 255, 255, int(14 * chip_a)), outline=(28, 42, 71, int(255 * chip_a)), width=1)
        d.text((ax + 40, y + 23), label, font=font("segoeui.ttf", 14), fill=INK, anchor="lm")
        d.text((ax + aw - 40, y + 23), sentiment, font=font("seguisb.ttf", 11), fill=color, anchor="rm")
        d.ellipse([ax + aw - 150, y + 19, ax + aw - 144, y + 25], fill=color + (int(255 * chip_a),))

    paste_glow(v, GLOWS["brain"], CX, CY - 20)
    v.paste(EMOJI_BADGES["happy"], (int(CX - 160), int(CY - 30)), EMOJI_BADGES["happy"])
    v.paste(EMOJI_BADGES["sad"], (int(CX + 60), int(CY - 30)), EMOJI_BADGES["sad"])
    _ = t


def scene_dashboard(v: Image.Image, d: ImageDraw.ImageDraw, u: float, t: float) -> None:
    """S7 — holographic analytics dashboard assembling."""
    appear = ease(min(1, u / 0.5))
    px0, py0, px1, py1 = 170, 200, STAGE_W - 170, STAGE_H - 210
    slide = int((1 - appear) * 50)
    d.rounded_rectangle([px0 + slide, py0, px1 - slide, py1], 18, fill=(11, 17, 32, 238), outline=EDGE + (255,), width=1)
    d.text((px0 + slide + 28, py0 + 24), "SENTINEX ANALYTICS", font=font("seguisb.ttf", 20), fill=INDIGO_L)
    d.text((px0 + slide + 28, py0 + 52), "48 reviews · 3 models · evidence-first", font=font("segoeui.ttf", 13), fill=INK_FAINT)

    # KPI row
    kpis = [("87.9%", "reproduced accuracy", INDIGO_L), ("3", "registered models", CYAN), ("48", "reviews analysed", GREEN), ("0", "unverified claims", VIOLET)]
    for i, (val, label, color) in enumerate(kpis):
        x = px0 + slide + 60 + i * 370
        y = py0 + 120
        d.rounded_rectangle([x, y, x + 330, y + 110], 14, fill=(255, 255, 255, 12))
        d.text((x + 24, y + 18), val, font=font("seguisb.ttf", 34), fill=color)
        d.text((x + 24, y + 74), label, font=font("segoeui.ttf", 13), fill=INK_DIM)
        a = int(130 + 110 * math.sin(4 * t + i))
        d.ellipse([x + 290, y + 26, x + 302, y + 38], fill=color + (a,))

    # waveform strip
    pts = []
    for i in range(80):
        x = px0 + slide + 60 + (px1 - px0 - 120 - slide * 2) * i / 79
        y = py1 - 80 + 16 * math.sin(2 * math.pi * (3 * i / 79 + 2 * t / 5)) + 7 * math.sin(2 * math.pi * (7 * i / 79 - t / 3))
        pts.append((x, y))
    d.line(pts, fill=CYAN + (200,), width=2)
    d.text((px0 + slide + 60, py1 - 46), "review intelligence over time", font=font("segoeui.ttf", 11), fill=INK_FAINT)


def scene_reveal(v: Image.Image, d: ImageDraw.ImageDraw, u: float, t: float) -> None:
    """S8 — cinematic brand reveal."""
    # focus veil: dim the world so typography owns the frame
    veil = Image.new("RGBA", (STAGE_W, STAGE_H), (0, 0, 0, 0))
    ImageDraw.Draw(veil).rectangle([0, 0, STAGE_W, STAGE_H], fill=(6, 9, 18, 165))
    v.paste(veil, (0, 0), veil)
    appear = ease(min(1, u / 0.35))
    sweep = ease(min(1, max(0, (u - 0.15) / 0.5)))
    v.paste(TEXT_BAND, (0, int(CY - 170)), TEXT_BAND)
    # logo mark scales in with a light sweep
    scale = 0.6 + 0.4 * appear
    logo = LOGO.resize((int(LOGO.size[0] * scale),) * 2, Image.BICUBIC)
    lx, ly = CX - logo.size[0] / 2, CY - 210 - logo.size[1] / 2
    paste_glow(v, GLOWS["logo_glow"], CX, CY - 210)
    v.paste(logo, (int(lx), int(ly)), logo)
    sw_x = CX - 500 + sweep * 1000
    d.line([(sw_x, CY - 280), (sw_x - 60, CY - 140)], fill=CYAN + (int(200 * (1 - abs(sweep - 0.5) * 2)),), width=3)

    if u > 0.28:
        a2 = ease(min(1, (u - 0.28) / 0.3))
        title = Image.new("RGBA", (STAGE_W, STAGE_H), (0, 0, 0, 0))
        gradient_text(title, (int(CX - 330), int(CY - 120)), "SENTINEX AI", font("seguisb.ttf", 84), (165, 180, 252), (216, 180, 254))
        title.putalpha(title.split()[3].point(lambda p: int(p * a2)))
        v.paste(title, (0, 0), title)
    if u > 0.5:
        a3 = ease(min(1, (u - 0.5) / 0.3))
        sub = Image.new("RGBA", (STAGE_W, STAGE_H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sub)
        sd.text((CX, CY + 62), "TURN CUSTOMER OPINIONS INTO BUSINESS DECISIONS.", font=font("segoeuil.ttf", 30), fill=(240, 244, 252), anchor="mm")
        sd.text((CX, CY + 124), "AI-POWERED REVIEW INTELLIGENCE", font=font("seguisb.ttf", 18), fill=(184, 196, 255), anchor="mm")
        sub.putalpha(sub.split()[3].point(lambda p: int(p * a3)))
        v.paste(sub, (0, 0), sub)
    # final soft glow bloom behind everything
    paste_glow(v, GLOWS["brain"], CX, CY)


# ------------------------------------------------------------------ render --
def render_showcase_frame(t: float) -> Image.Image:
    """t in [0, DURATION)."""
    # find active scene(s) with cross-fade
    active = []
    for i, (name, start, dur) in enumerate(SCENES):
        if start - XFADE / 2 <= t < start + dur + XFADE / 2:
            active.append((i, name, start, dur))
    if len(active) == 1:
        i, name, start, dur = active[0]
        return render_scene(i, name, start, dur, t, 1.0)
    # blend the two overlapping scenes
    i1, name1, start1, dur1 = active[0]
    i2, name2, start2, dur2 = active[1]
    w2 = ease((t - (start2 - XFADE / 2)) / XFADE)
    a = render_scene(i1, name1, start1, dur1, t, 1.0)
    b = render_scene(i2, name2, start2, dur2, t, 1.0)
    return Image.blend(a, b, min(1.0, max(0.0, w2)))


def render_scene(i: int, name: str, start: float, dur: float, t: float, alpha: float) -> Image.Image:
    stage = Image.new("RGB", (STAGE_W, STAGE_H), BG_TOP)
    d = ImageDraw.Draw(stage, "RGBA")
    environment(stage, d, t)
    u = (t - start) / dur
    draw_fn = {
        "neural": scene_neural,
        "activate": scene_activate,
        "reviews": scene_reviews,
        "flow": scene_flow,
        "signals": scene_signals,
        "panels": scene_panels,
        "dashboard": scene_dashboard,
        "reveal": scene_reveal,
    }[name]
    draw_fn(stage, d, max(0.0, min(1.0, u)), t)
    # fade-in/out at the film edges
    edge = 1.0
    if t < 0.5:
        edge = t / 0.5
    elif t > DURATION - 0.5:
        edge = (DURATION - t) / 0.5
    stage = stage.point(lambda p: int(p * (0.25 + 0.75 * edge))) if edge < 1 else stage

    # eased camera crop across the virtual stage
    scene_t = (t - start) / dur
    amp = CAM_AMP[name]
    pan_x = int((STAGE_W - OUT_W) / 2 + (STAGE_W - OUT_W) / 2 * 0.85 * amp * math.sin(2 * math.pi * (i * 0.37 + scene_t * 0.5)))
    pan_y = int((STAGE_H - OUT_H) / 2 + (STAGE_H - OUT_H) / 2 * 0.5 * amp * math.sin(2 * math.pi * (i * 0.53 + scene_t * 0.4)))
    frame = stage.crop((pan_x, pan_y, pan_x + OUT_W, pan_y + OUT_H))

    if alpha < 1.0:
        frame = frame.point(lambda p: int(p * alpha))
    return frame


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    mp4_path = ASSETS / "sentinex-product-showcase.mp4"
    poster_path = ASSETS / "sentinex-product-showcase.png"

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.Popen(
        [
            ffmpeg, "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{OUT_W}x{OUT_H}", "-pix_fmt", "rgb24", "-r", str(FPS),
            "-i", "-",
            "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(mp4_path),
        ],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    for i in range(FRAME_COUNT):
        frame = render_showcase_frame(DURATION * i / FRAME_COUNT)
        proc.stdin.write(frame.tobytes())  # type: ignore[union-attr]
        if i % 60 == 0:
            print(f"  rendered {i}/{FRAME_COUNT}", flush=True)
    proc.stdin.close()  # type: ignore[union-attr]
    proc.wait(timeout=180)

    # poster: the brand-reveal frame, fully composed
    poster = render_showcase_frame(17.3)
    poster.save(poster_path, optimize=True)

    print(f"mp4:   {mp4_path}  {mp4_path.stat().st_size / 1e6:.2f} MB")
    print(f"poster:{poster_path}  {poster_path.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
