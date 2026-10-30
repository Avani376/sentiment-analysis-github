"""Capture REAL screenshots of the running SENTINEX application.

Nothing is mocked: the script imports the committed demo dataset through the
real API, runs a real analysis through all cached models, and photographs the
actual rendered UI. Only pages that exist are captured.

Usage (from repo root, with the backend running on :8000):
    venv/Scripts/python.exe scripts/capture_screenshots.py
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"
SHOTS = REPO_ROOT / "assets" / "screenshots"
CSV_PATH = REPO_ROOT / "data" / "demo_product_reviews.csv"

VIEWPORT = {"width": 1280, "height": 800}


def wait_backend() -> None:
    for _ in range(30):
        try:
            if httpx.get(f"{BASE}/health", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("Backend on :8000 is not reachable — start it first.")


def seed_dataset() -> None:
    """Import the demo CSV through the real API (idempotent: skips if present)."""
    datasets = httpx.get(f"{BASE}/api/v1/datasets", timeout=10).json()
    if any(d["name"] == "Demo Product Reviews" for d in datasets):
        print("demo dataset already imported")
        return
    with CSV_PATH.open("rb") as fh:
        response = httpx.post(
            f"{BASE}/api/v1/datasets/upload",
            files={"file": ("demo_product_reviews.csv", fh, "text/csv")},
            data={"name": "Demo Product Reviews"},
            timeout=60,
        )
    response.raise_for_status()
    stats = response.json()["stats"]
    print(f"imported demo dataset: {stats['valid_rows']}/{stats['row_count']} rows kept")


def main() -> None:
    wait_backend()
    seed_dataset()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=2)
        page.set_default_timeout(45_000)

        # 1. Overview dashboard
        page.goto(f"{BASE}/")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2500)
        page.screenshot(path=SHOTS / "dashboard.png")
        print("dashboard.png")

        # 2. Single review analysis — run the real inference through the UI
        page.goto(f"{BASE}/analyze")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1200)
        page.get_by_role("button", name="Analyze").click()
        # DistilBERT may need its first load; wait until all 3 result cards render
        page.wait_for_selector("text=DistilBERT SST-2", timeout=60_000)
        page.wait_for_timeout(600)
        page.screenshot(path=SHOTS / "single-review-analysis.png")
        print("single-review-analysis.png")

        # 3. Review explorer with imported data
        page.goto(f"{BASE}/explorer")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)
        page.screenshot(path=SHOTS / "review-explorer.png")
        print("review-explorer.png")

        # 4. Model laboratory
        page.goto(f"{BASE}/models")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)
        page.screenshot(path=SHOTS / "model-comparison.png")
        print("model-comparison.png")

        browser.close()

    # 5. Architecture diagram PNG: render the SVG at 2x for crispness.
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1120, "height": 720}, device_scale_factor=2)
        page.goto((REPO_ROOT / "assets" / "architecture.svg").as_uri())
        page.wait_for_timeout(600)
        page.screenshot(path=REPO_ROOT / "assets" / "architecture.png")
        browser.close()
        print("architecture.png")


if __name__ == "__main__":
    main()
