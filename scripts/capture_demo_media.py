"""Capture REAL demo media of the running SENTINEX app — no mocks.

Produces (via Playwright video recording + ffmpeg):

    assets/demo/analyzer-scene.gif        # single-review analysis, animated
    assets/demo/explorer-scene.gif        # search & filter, animated
    assets/demo/app-tour-scene.gif        # overview + model laboratory, animated
    assets/demo/sentinex-app-walkthrough.mp4   # full narrated-by-motion walkthrough

Every frame is the genuine application UI captured live on http://127.0.0.1:8000.

Usage (from repo root, backend running):
    venv/Scripts/python.exe scripts/capture_demo_media.py
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "assets" / "demo"
BASE = "http://127.0.0.1:8000"


def wait_backend() -> None:
    import httpx

    for _ in range(30):
        try:
            if httpx.get(f"{BASE}/health", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("Backend not reachable on :8000")


def ffmpeg_to_mp4(webm: Path, mp4: Path) -> None:
    exe = __import__("imageio_ffmpeg").get_ffmpeg_exe()
    subprocess.run(
        [exe, "-y", "-i", str(webm), "-c:v", "libx264", "-preset", "medium", "-crf", "23",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def ffmpeg_to_gif(video: Path, gif: Path, fps: int = 12, width: int = 880) -> None:
    exe = __import__("imageio_ffmpeg").get_ffmpeg_exe()
    subprocess.run(
        [exe, "-y", "-i", str(video), "-vf",
         f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
         str(gif)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def main() -> None:
    wait_backend()
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="sentinex-demo-"))

    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        # ---- A. analyzer scene ------------------------------------------------
        ctx = browser.new_context(viewport={"width": 1280, "height": 800}, record_video_dir=str(tmp), record_video_size={"width": 1280, "height": 800})
        page = ctx.new_page()
        page.goto(f"{BASE}/analyze")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Analyze").click()
        page.wait_for_selector("text=3 models analyzed", timeout=60_000)
        page.wait_for_timeout(2500)
        ctx.close()
        analyzer_webm = Path(page.video.path())
        print("captured analyzer scene")

        # ---- B. explorer scene ------------------------------------------------
        ctx = browser.new_context(viewport={"width": 1280, "height": 800}, record_video_dir=str(tmp), record_video_size={"width": 1280, "height": 800})
        page = ctx.new_page()
        page.goto(f"{BASE}/explorer")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)
        page.get_by_placeholder("Search review text…").fill("battery")
        page.get_by_role("button", name="Search").click()
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Search").click()
        page.get_by_placeholder("Search review text…").fill("")
        page.get_by_role("button", name="Search").click()
        page.wait_for_timeout(1200)
        page.get_by_role("button", name="Negative", exact=True).click()
        page.wait_for_timeout(1800)
        page.get_by_role("button", name="All labels").click()
        page.wait_for_timeout(1200)
        ctx.close()
        explorer_webm = Path(page.video.path())
        print("captured explorer scene")

        # ---- C. app tour scene -------------------------------------------------
        ctx = browser.new_context(viewport={"width": 1280, "height": 800}, record_video_dir=str(tmp), record_video_size={"width": 1280, "height": 800})
        page = ctx.new_page()
        page.goto(f"{BASE}/")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2500)
        page.goto(f"{BASE}/models")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2500)
        ctx.close()
        tour_webm = Path(page.video.path())
        print("captured app tour scene")

        # ---- D. full walkthrough (longer, all pages + a real analysis) ----------
        ctx = browser.new_context(viewport={"width": 1280, "height": 800}, record_video_dir=str(tmp), record_video_size={"width": 1280, "height": 800})
        page = ctx.new_page()
        page.goto(f"{BASE}/")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)
        page.goto(f"{BASE}/analyze")
        page.wait_for_timeout(1200)
        page.get_by_role("button", name="Analyze").click()
        page.wait_for_selector("text=3 models analyzed", timeout=60_000)
        page.wait_for_timeout(3000)
        page.goto(f"{BASE}/explorer")
        page.wait_for_timeout(2200)
        page.get_by_role("button", name="Positive", exact=True).click()
        page.wait_for_timeout(1800)
        page.goto(f"{BASE}/models")
        page.wait_for_timeout(2600)
        ctx.close()
        walkthrough_webm = Path(page.video.path())
        print("captured walkthrough")

        browser.close()

    # ---- convert ------------------------------------------------------------
    outputs = {
        analyzer_webm: OUT / "analyzer-scene.gif",
        explorer_webm: OUT / "explorer-scene.gif",
        tour_webm: OUT / "app-tour-scene.gif",
    }
    for webm, gif in outputs.items():
        ffmpeg_to_gif(webm, gif)
        print(f"{gif.name}: {gif.stat().st_size / 1e6:.2f} MB")

    walkthrough = OUT / "sentinex-app-walkthrough.mp4"
    ffmpeg_to_mp4(walkthrough_webm, walkthrough)
    print(f"{walkthrough.name}: {walkthrough.stat().st_size / 1e6:.2f} MB")

    for f in (analyzer_webm, explorer_webm, tour_webm, walkthrough_webm):
        f.unlink(missing_ok=True)
    print("DONE")


if __name__ == "__main__":
    main()
