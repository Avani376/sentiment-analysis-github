"""Local simulation of the Vercel serverless environment (Windows-adjusted)."""
import os
import sqlite3
import sys
from pathlib import Path

temp = Path(os.environ.get("TEMP", "C:/Temp"))
os.environ["SENTINEX_DATABASE_URL"] = f"sqlite:///{temp.as_posix()}/vercel-sim.db"
os.environ["SENTINEX_UPLOAD_DIR"] = (temp / "vercel-sim-uploads").as_posix()
os.environ["SENTINEX_ENABLE_DISTILBERT"] = "false"
os.environ["SENTINEX_AUTO_CREATE_TABLES"] = "true"
os.environ["SENTINEX_MAX_UPLOAD_MB"] = "4"

sys.path.insert(0, "api")
from fastapi.testclient import TestClient  # noqa: E402

from index import app  # noqa: E402  — the exact entrypoint Vercel imports

with TestClient(app) as client:  # context manager triggers lifespan (cold start)
    print("health  :", client.get("/health").json())
    r = client.post(
        "/api/v1/analyze/single",
        json={"text": "Outstanding service, truly wonderful experience."},
    )
    p = r.json()["predictions"][0]
    print("analyze :", p["model_key"], p["label"], round(p["confidence"], 3))
    print("models  :", len(client.get("/api/v1/models").json()), "registered")
    csv = "text,label\nGreat product,positive\nTerrible support,negative\n"
    up = client.post(
        "/api/v1/datasets/upload", files={"file": ("sim.csv", csv.encode(), "text/csv")}
    )
    print("upload  :", up.status_code, up.json()["stats"])
    dup = client.post(
        "/api/v1/datasets/upload", files={"file": ("sim.csv", csv.encode(), "text/csv")}
    )
    print("upload2 :", dup.status_code, dup.json()["stats"])
print("SERVERLESS ENTRY OK")
