"""Generate SENTINEX project animations that illustrate REAL functionality.

Two animations (both programmatically drawn, no stock imagery):

1. sentiment-pipeline.gif — the actual data flow implemented in the backend:
   CSV ingest -> column mapping & cleaning -> model registry (3 registered
   models) -> normalized prediction labels. A highlight sweeps the stages.

2. model-comparison.gif — the ACTUAL committed evaluation values:
   * tfidf_logreg_legacy 84.5%  (historical reference, grey)
   * tfidf_logreg_imdb_v1 87.9% (reproduced, indigo)
   * distilbert_sst2 has NO reproduced evaluation yet — shown as an outlined
     "pending" bar. We never invent a number.

Usage (from repo root):
    venv/Scripts/python.exe scripts/generate_animations.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "assets" / "animations"

W, H = 720, 340
BG = (7, 11, 22)
PANEL = (13, 20, 37)
EDGE = (28, 42, 71)
INDIGO = (99, 102, 241)
INDIGO_LIGHT = (129, 140, 248)
VIOLET = (168, 85, 247)
CYAN = (34, 211, 238)
GREEN = (52, 211, 153)
ROSE = (251, 113, 133)
GREY = (82, 96, 125)
INK = (226, 232, 240)
INK_DIM = (143, 163, 194)
INK_FAINT = (91, 111, 147)

FRAMES = 48
DURATION_MS = 50


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


def base_canvas() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([W - 200, -120, W + 160, 180], fill=INDIGO + (42,))
    layer = layer.filter(ImageFilter.GaussianBlur(90))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def frame_border(draw: ImageDraw.ImageDraw) -> None:
    draw.rounded_rectangle([1, 1, W - 2, H - 2], 12, outline=EDGE, width=1)


def arrow(draw: ImageDraw.ImageDraw, x1: int, y: int, x2: int, color, active: float) -> None:
    """Arrow between stages; travelling dot when active."""
    draw.line([(x1, y), (x2 - 8, y)], fill=color + (90,), width=2)
    draw.polygon([(x2, y), (x2 - 9, y - 5), (x2 - 9, y + 5)], fill=color + (150,))
    if active > 0:
        dot_x = x1 + (x2 - x1) * active
        draw.ellipse([dot_x - 3, y - 3, dot_x + 3, y + 3], fill=CYAN + (230,))


def sentiment_pipeline() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stages = [
        ("CSV INGEST", "upload · validation", INDIGO_LIGHT),
        ("CLEAN & MAP", "dedupe · labels · dates", INDIGO_LIGHT),
        ("MODEL REGISTRY", "legacy · imdb v1 · sst-2", VIOLET),
        ("PREDICTIONS", "positive / negative", CYAN),
    ]
    stage_w, stage_h, gap = 138, 96, 36
    x0 = (W - 4 * stage_w - 3 * gap) // 2
    y0 = 108

    frames: list[Image.Image] = []
    for f in range(FRAMES):
        t = f / FRAMES
        img = base_canvas()
        draw = ImageDraw.Draw(img, "RGBA")

        # Which stage is highlighted + arrows animating in sequence.
        phase = t * 4 * 2  # two full sweeps per loop
        active_stage = int(phase) % 4
        arrow_active = phase % 1

        for i, (title, sub, color) in enumerate(stages):
            x = x0 + i * (stage_w + gap)
            is_active = i == active_stage
            glow_alpha = 46 if is_active else 16
            outline = color if is_active else EDGE
            draw.rounded_rectangle(
                [x, y0, x + stage_w, y0 + stage_h], 12,
                fill=PANEL + (255,), outline=outline + (230 if is_active else 120,), width=2,
            )
            draw.rounded_rectangle(
                [x, y0, x + stage_w, y0 + stage_h], 12,
                fill=color + (glow_alpha,),
            )
            # icon rows
            for line in range(3):
                draw.rounded_rectangle(
                    [x + 14, y0 + 14 + line * 11, x + stage_w - (34 if line == 1 else 20), y0 + 20 + line * 11],
                    3, fill=(255, 255, 255, 36),
                )
            draw.text((x + stage_w / 2, y0 + 58), title, font=font("seguisb.ttf", 13),
                      fill=INK if is_active else INK_DIM, anchor="ma")
            draw.text((x + stage_w / 2, y0 + 76), sub, font=font("segoeui.ttf", 9),
                      fill=INK_FAINT, anchor="ma")

        for i in range(3):
            x1 = x0 + stage_w + i * (stage_w + gap) - gap + 6
            x2 = x1 + gap - 12
            active = arrow_active if i == active_stage - 1 or (active_stage == 0 and i == 2 and phase % 4 >= 3) else 0.0
            if active_stage == i + 1:
                active = arrow_active
            arrow(draw, x1, y0 + stage_h // 2, x2, stages[i + 1][2], active)

        draw.text((W // 2, 34), "SENTINEX — SENTIMENT ANALYSIS PIPELINE", font=font("seguisb.ttf", 15),
                  fill=INK, anchor="ma")
        draw.text((W // 2, 262), "Every stage runs exactly as implemented in the FastAPI backend — no mock data.",
                  font=font("segoeui.ttf", 12), fill=INK_FAINT, anchor="ma")
        labels = "CSV upload → column auto-detection → dedupe & label normalization → registry models → persisted predictions"
        draw.text((W // 2, 284), labels, font=font("segoeui.ttf", 10), fill=INK_FAINT, anchor="ma")
        frame_border(draw)
        frames.append(img)

    quantized = [f.convert("P", palette=Image.ADAPTIVE, colors=128) for f in frames]
    out = OUT_DIR / "sentiment-pipeline.gif"
    quantized[0].save(out, save_all=True, append_images=quantized[1:], duration=DURATION_MS, loop=0, optimize=True)
    print(f"sentiment-pipeline.gif: {out.stat().st_size / 1024:.0f} KB")


def model_comparison() -> None:
    """Bars animate to the real committed evaluation values; no invented numbers."""
    records = [
        ("tfidf_logreg_legacy", 0.845, GREY, "historical reference — pipeline lost"),
        ("tfidf_logreg_imdb_v1", 0.879, INDIGO, "reproduced · 25k held-out · seed 42"),
        ("distilbert_sst2", None, VIOLET, "pretrained checkpoint — no reproduced eval yet"),
    ]
    bar_x, bar_y, bar_max_w, bar_h, gap = 250, 92, 330, 26, 26

    frames: list[Image.Image] = []
    for f in range(FRAMES):
        t = f / FRAMES
        img = base_canvas()
        draw = ImageDraw.Draw(img, "RGBA")

        draw.text((W // 2, 34), "MODEL EVALUATION — WHAT WE CAN AND CANNOT CLAIM", font=font("seguisb.ttf", 15),
                  fill=INK, anchor="ma")

        for i, (name, value, color, note) in enumerate(records):
            y = bar_y + i * (bar_h + gap)
            draw.text((bar_x - 14, y + bar_h / 2), name.replace("tfidf_logreg_", "").replace("_", " "),
                      font=font("segoeui.ttf", 13), fill=INK_DIM, anchor="rm")

            if value is not None:
                # ease-out growth, then a gentle shimmer on the value label so
                # the hold phase keeps frames distinct (GIF dedupes identical ones)
                grow = min(1.0, t * 1.8)
                eased = 1 - (1 - grow) ** 3
                w = int(bar_max_w * value * eased)
                shimmer = int(196 + 44 * (0.5 + 0.5 * math.sin(2 * math.pi * t * 3)))
                draw.rounded_rectangle([bar_x, y, bar_x + bar_max_w, y + bar_h], 6, fill=(255, 255, 255, 16))
                draw.rounded_rectangle([bar_x, y, bar_x + w, y + bar_h], 6, fill=color + (shimmer,))
                draw.text((bar_x + w + 12, y + bar_h / 2), f"{value * 100:.1f}%",
                          font=font("seguisb.ttf", 14), fill=INK, anchor="lm")
            else:
                # dashed outline bar — explicitly NOT measured
                dash, x = 10, bar_x
                while x < bar_x + bar_max_w:
                    draw.line([(x, y + bar_h / 2), (min(x + dash, bar_x + bar_max_w), y + bar_h / 2)],
                              fill=INK_FAINT + (120,), width=2)
                    x += dash + 6
                draw.text((bar_x + bar_max_w + 12, y + bar_h / 2), "not measured",
                          font=font("segoeui.ttf", 12), fill=INK_FAINT, anchor="lm")

            draw.text((bar_x - 14, y + bar_h + 4), note, font=font("segoeui.ttf", 9), fill=INK_FAINT, anchor="ra")

        draw.text((W // 2, 288), "Historical reference numbers are committed values whose pipeline no longer exists.",
                  font=font("segoeui.ttf", 10), fill=INK_FAINT, anchor="ma")
        frame_border(draw)
        frames.append(img)

    quantized = [f.convert("P", palette=Image.ADAPTIVE, colors=128) for f in frames]
    out = OUT_DIR / "model-comparison.gif"
    quantized[0].save(out, save_all=True, append_images=quantized[1:], duration=DURATION_MS, loop=0, optimize=True)
    print(f"model-comparison.gif: {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    sentiment_pipeline()
    model_comparison()
