"""Generate the SENTINEX AI GitHub hero banner (animated GIF + static PNG).

Everything is drawn programmatically with Pillow — no stock imagery. The
animation shows the product's real identity: a dark intelligence dashboard
with a neural network, live sentiment signals, review cards, and a data
stream flowing left to right.

Usage (from repo root):
    venv/Scripts/python.exe scripts/generate_banner.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS = REPO_ROOT / "assets"

W, H = 800, 400
FRAMES = 36
DURATION_MS = 45  # ~22 fps loop

# Palette (matches the application's design tokens)
BG = (7, 11, 22)
PANEL = (13, 20, 37)
EDGE = (28, 42, 71)
INDIGO = (99, 102, 241)
VIOLET = (168, 85, 247)
CYAN = (34, 211, 238)
GREEN = (52, 211, 153)
ROSE = (251, 113, 133)
INK = (226, 232, 240)
INK_DIM = (143, 163, 194)
INK_FAINT = (91, 111, 147)

FONT_DIR = Path("C:/Windows/Fonts")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)


def gradient_text(canvas: Image.Image, xy: tuple[int, int], text: str, fonts, c1, c2) -> None:
    """Draw text with a horizontal two-colour gradient."""
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=fonts, fill=255)
    grad = Image.new("RGB", canvas.size, c1)
    grad_draw = ImageDraw.Draw(grad)
    x0, _, x1, _ = mask.getbbox()
    for x in range(x0, x1):
        t = (x - x0) / max(1, x1 - x0)
        color = tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))
        grad_draw.line([(x, 0), (x, canvas.size[1])], fill=color)
    canvas.paste(grad, (0, 0), mask)


def base_background() -> Image.Image:
    """Static backdrop: deep navy + two soft glows + faint grid."""
    img = Image.new("RGB", (W, H), BG)

    def glow(cx: int, cy: int, radius: int, color: tuple[int, int, int], alpha: int) -> None:
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(layer).ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius], fill=color + (alpha,)
        )
        layer = layer.filter(ImageFilter.GaussianBlur(radius * 0.55))
        img.paste(Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"), (0, 0))

    glow(W - 120, -40, 260, INDIGO, 70)
    glow(60, H + 30, 240, VIOLET, 55)

    draw = ImageDraw.Draw(img, "RGBA")
    for x in range(0, W, 40):
        draw.line([(x, 0), (x, H)], fill=(255, 255, 255, 5))
    for y in range(0, H, 40):
        draw.line([(0, y), (W, y)], fill=(255, 255, 255, 5))
    return img


def neural_nodes() -> tuple[list[tuple[int, int]], list[tuple[tuple[int, int], tuple[int, int]]]]:
    cols = [630, 692, 754]
    heights = [3, 4, 3]
    nodes: list[tuple[int, int]] = []
    edges = []
    per_layer: list[list[tuple[int, int]]] = []
    for cx, count in zip(cols, heights, strict=True):
        ys = [160 + (i - (count - 1) / 2) * 56 for i in range(count)]
        per_layer.append([(cx, int(y)) for y in ys])
    nodes = [n for layer in per_layer for n in layer]
    for a, b in zip(per_layer, per_layer[1:]):
        for na in a:
            for nb in b:
                edges.append((na, nb))
    return nodes, edges


NODES, EDGES = neural_nodes()


def draw_scene(frame_img: Image.Image, t: float) -> None:
    """t in [0, 1) — the loop phase."""
    draw = ImageDraw.Draw(frame_img, "RGBA")

    # --- data stream particles (left to right across the top band) ---------
    for i in range(14):
        x = int(((t + i / 14) % 1) * (W + 80)) - 40
        y = 64 + int(10 * math.sin(2 * math.pi * (t + i / 14) * 2 + i))
        fade = 0.35 + 0.4 * math.sin(math.pi * (((t + i / 14) % 1)))
        draw.ellipse([x - 2, y - 2, x + 2, y + 2], fill=CYAN + (int(255 * fade),))

    # --- neural network -----------------------------------------------------
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * t)
    for (a, b) in EDGES:
        edge_alpha = int(38 + 50 * pulse * (0.5 + 0.5 * math.sin(6 * (a[0] + b[1]) )))
        draw.line([a, b], fill=INDIGO + (edge_alpha,), width=1)
    for i, (x, y) in enumerate(NODES):
        r = 4 + 1.6 * math.sin(2 * math.pi * t + i * 1.1)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(129, 140, 248, 230))
        halo = r + 4 + 2 * pulse
        draw.ellipse([x - halo, y - halo, x + halo, y + halo], outline=VIOLET + (90,), width=1)

    # --- sentiment signal bars (bottom-right) -------------------------------
    bx, by, bw, gap = 610, 372, 30, 21
    signals = [
        (GREEN, "POS", 0.72, 0.18),
        (ROSE, "NEG", 0.46, 1.9),
        (CYAN, "NEU", 0.30, 3.6),
    ]
    for i, (color, label, base, phase) in enumerate(signals):
        h = (base + 0.14 * math.sin(2 * math.pi * t + phase)) * 54
        x = bx + i * (bw + gap)
        draw.rounded_rectangle([x, by - 54, x + bw, by], 3, fill=(255, 255, 255, 22))
        draw.rounded_rectangle([x, by - int(h), x + bw, by], 3, fill=color + (210,))
        draw.text((x + bw / 2, by + 5), label, font=font("seguisb.ttf", 11), fill=INK_DIM, anchor="ma")

    # --- floating review cards (mid-right) -----------------------------------
    cards = [
        {"x": 606, "y": 262, "chip": ("POSITIVE", GREEN), "bob": 0.0},
        {"x": 700, "y": 262, "chip": ("NEGATIVE", ROSE), "bob": 0.45},
    ]
    for card in cards:
        y = card["y"] + int(6 * math.sin(2 * math.pi * (t + card["bob"])))
        x, w, h = card["x"], 84, 50
        draw.rounded_rectangle([x, y, x + w, y + h], 10, fill=PANEL + (235,), outline=EDGE + (255,), width=1)
        for line in range(3):
            draw.rounded_rectangle(
                [x + 9, y + 9 + line * 8, x + w - (22 if line == 1 else 14), y + 13 + line * 8],
                2, fill=(255, 255, 255, 38),
            )
        label, color = card["chip"]
        tw = 40
        draw.rounded_rectangle([x + 9, y + h - 13, x + 9 + tw, y + h - 3], 5, fill=color + (46,))
        draw.text((x + 9 + tw / 2, y + h - 14), label, font=font("seguisb.ttf", 6), fill=color, anchor="ma")

    # --- frame border --------------------------------------------------------
    draw.rounded_rectangle([1, 1, W - 2, H - 2], 14, outline=EDGE + (255,), width=1)


def draw_static(canvas: Image.Image) -> None:
    draw = ImageDraw.Draw(canvas, "RGBA")

    # eyebrow chip
    chip_text = "AI-POWERED REVIEW INTELLIGENCE"
    f_chip = font("seguisb.ttf", 13)
    tw = draw.textlength(chip_text, font=f_chip)
    draw.rounded_rectangle([64, 66, 64 + tw + 28, 98], 16, fill=(99, 102, 241, 36), outline=(129, 140, 248, 120), width=1)
    draw.text((64 + 14, 74), chip_text, font=f_chip, fill=(165, 180, 252))

    # title
    gradient_text(canvas, (60, 108), "SENTINEX AI", font("seguisb.ttf", 72), (165, 180, 252), (216, 180, 254))

    # tagline
    draw.text((64, 216), "Turn Customer Opinions Into Business Decisions.", font=font("segoeui.ttf", 23), fill=INK)
    draw.text((64, 258), "Sentiment Intelligence  |  Emotion Detection  |  Aspect Analysis  |  AI Insights",
              font=font("segoeui.ttf", 14), fill=INK_DIM)

    # footer: models line
    f_small = font("segoeui.ttf", 13)
    draw.text((64, 330), "TF-IDF + LogReg   ·   DistilBERT SST-2   ·   Reproducible evaluation on IMDb (25k held-out)",
              font=f_small, fill=INK_FAINT)
    draw.text((64, 352), "FastAPI  ·  React  ·  SQLAlchemy  ·  scikit-learn  ·  PyTorch",
              font=f_small, fill=INK_FAINT)


def main() -> None:
    ASSETS.mkdir(exist_ok=True)

    bg = base_background()
    frames: list[Image.Image] = []
    for i in range(FRAMES):
        frame = bg.copy()
        draw_scene(frame, i / FRAMES)
        draw_static(frame)
        frames.append(frame)

    # Static PNG: high-quality hero frame.
    png_path = ASSETS / "github-banner.png"
    frames[6].save(png_path, optimize=True)

    # Animated GIF: quantized for size.
    gif_path = ASSETS / "github-banner.gif"
    quantized = [f.convert("P", palette=Image.ADAPTIVE, colors=160) for f in frames]
    quantized[0].save(
        gif_path,
        save_all=True,
        append_images=quantized[1:],
        duration=DURATION_MS,
        loop=0,
        optimize=True,
    )

    print(f"banner png: {png_path} ({png_path.stat().st_size / 1024:.0f} KB)")
    print(f"banner gif: {gif_path} ({gif_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
