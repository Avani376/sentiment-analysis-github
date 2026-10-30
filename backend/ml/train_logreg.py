"""Reproducible training of the TF-IDF + Logistic Regression sentiment model.

This script is the provenance reset for the model registry (decision D3 in
IMPLEMENTATION_PLAN.md): it trains a pipeline with the SAME hyperparameters as
the repository's legacy artifact, but on the public IMDb dataset with a
documented download, fixed seed, and a disjoint held-out test split — so every
metric it reports can actually be reproduced.

Data source
-----------
Canonical source: aclImdb v1, the Large Movie Review Dataset
(ai.stanford.edu/~amaas/data/sentiment). Where that host is unreachable, the
script downloads the official ``stanfordnlp/imdb`` conversion on Hugging Face
(same 25k/25k train/test split, same labels). The source actually used is
recorded in the evaluation artifact — never silently substituted.

What it does
------------
1. Downloads the labelled train/test data (parquet via HF, tarball fallback).
2. Records SHA-256 and size of every downloaded file for integrity/provenance.
3. Trains: TfidfVectorizer(max_features=5000, stop_words='english',
   ngram_range=(1,1)) + LogisticRegression(C=1.0, lbfgs, max_iter=1000,
   random_state=42) — deliberately identical to the legacy artifact.
4. Evaluates on the disjoint 25k test split and measures inference latency.
5. Saves the artifact and a self-describing evaluation JSON.

Usage (from backend/):
    python -m ml.train_logreg [--full-clean] [--data-dir PATH]

The evaluation artifact is committed so the Model Laboratory can display
reproduced results alongside clearly-labelled legacy reference numbers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
ARTIFACT_PATH = BACKEND_ROOT / "artifacts" / "models" / "tfidf_logreg_imdb_v1.pkl"
EVALUATION_PATH = BACKEND_ROOT / "artifacts" / "evaluations" / "tfidf_logreg_imdb_v1.json"

STANFORD_URL = "https://ai.stanford.edu/~amaas/data/sentiment/aclImdb_v1.tar.gz"
HF_DATASET_REPO = "stanfordnlp/imdb"
HF_DATASET_URL = f"https://huggingface.co/datasets/{HF_DATASET_REPO}"
HF_FILES = {
    "train": "plain_text/train-00000-of-00001.parquet",
    "test": "plain_text/test-00000-of-00001.parquet",
}

SEED = 42
LATENCY_SAMPLE_SIZE = 1000
REQUIRED_COUNTS = {"train": 25_000, "test": 25_000}
LABEL_MAP = {"negative": 0, "positive": 1}  # documented mapping

#: Data target: OUTSIDE the repository (and OneDrive) by default.
DEFAULT_DATA_DIR = Path.home() / ".sentinex" / "ml-data"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, destination: Path) -> None:
    import urllib.request

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(
        url, headers={"User-Agent": "sentinex-ai/0.2 (training script)"}
    )
    with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
    partial.replace(destination)


def download_hf_parquets(data_dir: Path) -> dict[str, Path]:
    """Download the official stanfordnlp/imdb parquet files via huggingface_hub."""
    from huggingface_hub import hf_hub_download

    paths: dict[str, Path] = {}
    for split, filename in HF_FILES.items():
        local = Path(
            hf_hub_download(
                repo_id=HF_DATASET_REPO,
                filename=filename,
                repo_type="dataset",
                local_dir=data_dir / "hf-imdb",
            )
        )
        paths[split] = local
    return paths


def read_split_parquet(path: Path, split: str) -> tuple[list[str], list[int]]:
    """Read one split from parquet (columns: text, label; 0=neg, 1=pos)."""
    import pandas as pd

    frame = pd.read_parquet(path)
    if set(["text", "label"]) - set(frame.columns):
        raise ValueError(f"Unexpected schema in {path.name}: {list(frame.columns)}")
    texts = frame["text"].astype(str).str.replace("<br />", " ", regex=False).str.strip()
    labels = frame["label"].astype(int).tolist()
    keep = texts.ne("")
    texts = texts[keep]
    labels = [label for label, k in zip(labels, keep, strict=True) if k]
    balance = dict(pd.Series(labels).value_counts().sort_index())
    print(f"      {split}: {len(texts)} rows (label balance: {balance})")
    return texts.tolist(), labels


def read_split_tarball(root: Path, split: str) -> tuple[list[str], list[int]]:
    """Fallback reader for the original aclImdb directory layout."""
    texts: list[str] = []
    labels: list[int] = []
    for label_name, label in (("neg", 0), ("pos", 1)):
        directory = root / split / label_name
        for path in sorted(directory.glob("*.txt")):
            text = path.read_text(encoding="utf-8").replace("<br />", " ").strip()
            if text:
                texts.append(text)
                labels.append(label)
    return texts, labels


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__import__("os").environ.get("SENTINEX_ML_DATA_DIR", DEFAULT_DATA_DIR)),
        help="Where to download the dataset (default: ~/.sentinex/ml-data).",
    )
    parser.add_argument(
        "--full-clean",
        action="store_true",
        help="Delete downloaded data after training.",
    )
    args = parser.parse_args()
    data_dir: Path = args.data_dir

    import joblib
    import numpy as np
    import sklearn
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
    )
    from sklearn.pipeline import Pipeline

    # ---- 1: download (HF primary, canonical Stanford fallback) -------------
    source_key = "huggingface_hub"
    file_records: list[dict] = []

    try:
        print(f"[1/6] Downloading {HF_DATASET_URL} (official aclImdb v1 conversion)...")
        paths = download_hf_parquets(data_dir)
    except Exception as hf_error:  # noqa: BLE001 - deliberate documented fallback
        print(f"      HF download failed ({type(hf_error).__name__}); trying canonical source...")
        try:
            archive = data_dir / "aclImdb_v1.tar.gz"
            if not (archive.is_file() and archive.stat().st_size > 10_000_000):
                print(f"[1/6] Downloading {STANFORD_URL} ...")
                _download(STANFORD_URL, archive)
            source_key = "stanford_tarball"
            paths = {"archive": archive}
        except Exception as stanford_error:
            print(f"FATAL: both sources unreachable. HF: {hf_error}; Stanford: {stanford_error}")
            return 1

    for _split_name, path in paths.items():
        record = {"file": path.name, "size_bytes": path.stat().st_size, "sha256": sha256_of(path)}
        file_records.append(record)
        print(f"      {path.name}: {path.stat().st_size / 1e6:.1f} MB sha256={record['sha256'][:12]}...")

    # ---- 2: read labelled splits -------------------------------------------
    print("[2/6] Reading labelled train/test splits...")
    if source_key == "huggingface_hub":
        train_texts, train_labels = read_split_parquet(paths["train"], "train")
        test_texts, test_labels = read_split_parquet(paths["test"], "test")
    else:
        import tarfile

        root = data_dir / "aclImdb"
        if not (root / ".extracted_labelled").is_file():
            with tarfile.open(paths["archive"], "r:gz") as tar:
                prefixes = (
                    "aclImdb/train/pos/", "aclImdb/train/neg/",
                    "aclImdb/test/pos/", "aclImdb/test/neg/",
                )
                members = [m for m in tar.getmembers() if m.isfile() and m.name.startswith(prefixes)]
                tar.extractall(data_dir, members=members, filter="data")
            (root / ".extracted_labelled").write_text("ok", encoding="utf-8")
        train_texts, train_labels = read_split_tarball(root, "train")
        test_texts, test_labels = read_split_tarball(root, "test")

    if len(train_texts) != REQUIRED_COUNTS["train"] or len(test_texts) != REQUIRED_COUNTS["test"]:
        print(
            f"      WARNING: split sizes {len(train_texts)}/{len(test_texts)} differ from "
            f"the canonical aclImdb v1 {REQUIRED_COUNTS['train']}/{REQUIRED_COUNTS['test']}.",
            file=sys.stderr,
        )

    # ---- 3: train ------------------------------------------------------------
    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    max_features=5000,
                    stop_words="english",
                    ngram_range=(1, 1),
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    C=1.0,
                    penalty="l2",
                    solver="lbfgs",
                    max_iter=1000,
                    random_state=SEED,
                ),
            ),
        ]
    )

    print("[3/6] Training (identical hyperparameters to the legacy artifact)...")
    started = time.perf_counter()
    pipeline.fit(train_texts, train_labels)
    train_seconds = time.perf_counter() - started
    print(f"      trained in {train_seconds:.1f}s")

    # ---- 4: evaluate on the disjoint held-out split ---------------------------
    print("[4/6] Evaluating on the disjoint held-out test split...")
    started = time.perf_counter()
    predictions = pipeline.predict(test_texts)
    eval_seconds = time.perf_counter() - started

    latency_started = time.perf_counter()
    pipeline.predict_proba(test_texts[:LATENCY_SAMPLE_SIZE])
    latency_seconds = time.perf_counter() - latency_started

    report = classification_report(
        test_labels, predictions, target_names=["negative", "positive"], output_dict=True
    )
    metrics = {
        "accuracy": round(float(accuracy_score(test_labels, predictions)), 4),
        "precision": round(float(precision_score(test_labels, predictions)), 4),
        "recall": round(float(recall_score(test_labels, predictions)), 4),
        "f1_macro": round(float(f1_score(test_labels, predictions, average="macro")), 4),
        "f1_weighted": round(float(f1_score(test_labels, predictions, average="weighted")), 4),
        "confusion_matrix": confusion_matrix(test_labels, predictions).tolist(),
        # Keep only genuine per-class rows; sklearn also emits scalar
        # 'accuracy'/'macro avg'/'weighted avg' entries we already store above.
        "per_class": {
            name: report[name] for name in ("negative", "positive") if name in report
        },
    }
    for key in ("accuracy", "precision", "recall", "f1_macro", "f1_weighted"):
        print(f"      {key:12s} {metrics[key]}")
    print(f"      confusion    {metrics['confusion_matrix']}")

    # ---- 5-6: persist artifact + evaluation record ----------------------------
    print("[5/6] Saving artifact...")
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVALUATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, ARTIFACT_PATH, compress=3)

    if source_key == "huggingface_hub":
        dataset_info = {
            "name": "aclImdb v1 — Large Movie Review Dataset (official HF conversion)",
            "source_url": HF_DATASET_URL,
            "canonical_source": STANFORD_URL,
            "source_note": (
                "Downloaded from the official stanfordnlp/imdb Hugging Face "
                "conversion of aclImdb v1 after the canonical Stanford host was "
                "unreachable from the training machine. Same 25k/25k split."
            ),
            "files": file_records,
        }
    else:
        dataset_info = {
            "name": "aclImdb v1 — Large Movie Review Dataset",
            "source_url": STANFORD_URL,
            "files": file_records,
        }

    evaluation = {
        "model_key": "tfidf_logreg_imdb_v1",
        "evaluation_type": "reproduced",
        "created_at": datetime.now(UTC).isoformat(),
        "dataset": {
            **dataset_info,
            "train_size": len(train_texts),
            "test_size": len(test_texts),
            "label_mapping": LABEL_MAP,
            "notes": "HTML <br /> markers collapsed to spaces; empty rows dropped.",
        },
        "config": {
            "vectorizer": {
                "lowercase": True,
                "max_features": 5000,
                "stop_words": "english",
                "ngram_range": [1, 1],
            },
            "classifier": {"C": 1.0, "penalty": "l2", "solver": "lbfgs", "max_iter": 1000},
            "random_seed": SEED,
            "held_out_split": "aclImdb test (disjoint from training)",
        },
        "metrics": metrics,
        "runtime": {
            "train_seconds": round(train_seconds, 2),
            "eval_seconds": round(eval_seconds, 3),
            "latency_ms_per_review": round(latency_seconds * 1000 / LATENCY_SAMPLE_SIZE, 3),
            "latency_sample_size": LATENCY_SAMPLE_SIZE,
        },
        "environment": {
            "python": sys.version.split()[0],
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "notes": (
            "Reproduced evaluation generated by backend/ml/train_logreg.py. "
            "Kept strictly separate from the legacy artifact's unreproducible "
            "historical reference metrics."
        ),
    }
    print("[6/6] Writing evaluation record...")
    EVALUATION_PATH.write_text(json.dumps(evaluation, indent=2), encoding="utf-8")

    artifact_mb = ARTIFACT_PATH.stat().st_size / 1e6
    print(f"      artifact -> {ARTIFACT_PATH.relative_to(REPO_ROOT)} ({artifact_mb:.2f} MB)")
    print(f"      metrics  -> {EVALUATION_PATH.relative_to(REPO_ROOT)}")

    if args.full_clean:
        print("Cleaning downloaded data (--full-clean)...")
        shutil.rmtree(data_dir, ignore_errors=True)

    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
