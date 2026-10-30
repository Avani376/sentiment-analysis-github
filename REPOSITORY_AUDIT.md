# Repository Audit — Milestone 0

**Date:** 2026-10-30
**Audited commit:** `21b10d2` ("Added Dev Container Folder")
**Method:** Every source file read; pickle artifact inspected programmatically; dataset statistics computed; all README metric claims re-executed and verified. No files were modified during this audit.

---

## 1. Current Architecture

The repository is a compact, honest, single-page Streamlit demonstration:

```
sentiment-analysis-github/
├── app/app.py                  # Entire product: 185-line Streamlit app
├── models/tfidf_logreg.pkl     # 224 KB committed sklearn pipeline
├── data/
│   ├── evaluation_metrics.csv  # 2-row reference metrics (NOT reproducible)
│   └── sample_test_reviews.csv # 100 labelled reviews (52 positive / 48 negative)
├── notebooks/experiment.ipynb  # 805 bytes, 3 cells, never executed (stub)
├── assets/                     # 7 genuine screenshots + 0.9 MB banner GIF
├── requirements.txt            # 6 pinned runtime dependencies
├── .gitignore                  # secrets/venv aware
└── .devcontainer/devcontainer.json  # Codespaces config (Python 3.11)
```

There is no database, no API layer, no tests, no CI, no Dockerfile, and no LICENSE.

## 2. Existing Features Verified Working

| Claim | Verification |
|---|---|
| Committed artifact loads and predicts | ✅ `Pipeline(TfidfVectorizer → LogisticRegression)`, serialized with scikit-learn **1.6.1**, matching the pinned version exactly |
| README smoke check: accuracy 97.00%, confusion matrix `[[47,1],[2,50]]` | ✅ **Reproduced exactly** on the 100-row sample: ACC 97.00 / PRE 98.04 / REC 96.15 / F1 97.09 |
| Confusion-matrix image matches the smoke check | ✅ Visual inspection confirms cells `47 / 1 / 2 / 50` |
| Baseline single-review latency | ✅ ~0.9 ms (measured during audit) |
| Rooted artifact paths, blank-input validation, graceful DistilBERT degradation | ✅ Confirmed at `app/app.py:8-12`, `89-96`, `121-139` |
| README does not fabricate deployment or metrics | ✅ Deployment and demo video explicitly marked "not yet"; reference metrics explicitly labeled non-reproducible |
| Model caches | ✅ Hugging Face cache contains SST-2 **and** `sentence-transformers/all-MiniLM-L6-v2` |

**Extracted artifact card (`models/tfidf_logreg.pkl`):**

- `TfidfVectorizer(lowercase=True, max_features=5000, stop_words="english", ngram_range=(1,1))`
- `LogisticRegression(C=1.0, penalty="l2", solver="lbfgs", max_iter=1000)`
- `classes_ = [0, 1]` (binary; no neutral capability)
- Vocabulary saturated at exactly 5000 features — the training corpus was large enough to hit the cap.

## 3. Bugs and Technical Debt

1. **Swallowed exceptions** — `app/app.py:124` and `app/app.py:151` catch broad `Exception` and show generic messages with **no logging**. Failures are undebuggable.
2. **Double inference per call** — `app/app.py:65-66` runs `predict()` and then `predict_proba()` (two full vectorizations per review).
3. **Truncation asymmetry** — DistilBERT sees only the first 512 tokens (`app/app.py:77`) while the TF-IDF baseline sees the full text. Given the sample mean length of 3,887 characters, the two models systematically evaluate different effective inputs, and nothing in the UI discloses this.
4. **Notebook is dead code** — never executed (`execution_count: null`, no outputs); its header says "trains the model" but no training code exists; cell 3 uses a `../data/...` relative path that breaks when run from the repo root.
5. **Stray divergent environment** — `.venv/` (Python 3.13.5) contains only `torch 2.15.0, joblib 1.6.0, numpy 2.5.4`; inconsistent with pins and half-installed.
6. **Unpinned numpy drift** — `numpy 2.4.6` is installed but not pinned in `requirements.txt`.
7. **`evaluation_metrics.csv` DistilBERT row (90.2%) has zero provenance** — no script, split, or config exists that could regenerate it.
8. **Missing engineering surface** — no tests, no CI, no lint config, no Dockerfile, no `.env.example`, no LICENSE.
9. **Devcontainer** disables XSRF protection (`--server.enableXsrfProtection false`) and installs requirements via a brittle shell one-liner.

## 4. ML Model Audit

| | TF-IDF + LogReg | DistilBERT SST-2 |
|---|---|---|
| Type | Trained (artifact committed) | Pretrained checkpoint only (correctly **not** claimed as fine-tuned) |
| Labels | Binary 0/1 → POSITIVE/NEGATIVE | Binary POSITIVE/NEGATIVE (SST-2 has **no neutral class**) |
| Calibration | None | None (README correctly warns probabilities are not cross-comparable) |
| Input handling | Full text, 5,000 unigram vocabulary | 512-token truncation |
| Metrics | 84.5% "reference" (unreproducible) + 97.0% smoke check (reproduced ✅) | 90.2% "reference" (**nothing exists to reproduce it**) |

## 5. Dataset Audit — `data/sample_test_reviews.csv`

- 100 rows, columns `text` + `label`; 52 positive / 48 negative; 0 nulls; 0 duplicate texts.
- Text length: mean **3,887 chars** (min 1,120 / max 11,646) — long-form reviews.
- **Provenance verdict: UNVERIFIED.** The typography (spaces before punctuation, e.g. `"in 1994 , an insider's look ..."`) is the signature of a token-index-decoded Keras IMDb variant, **not** raw aclImdb text. This is strong stylistic evidence, not proof. The upstream source, the training corpus, and the train/test split are all absent from the repository.
- **Consequence:** the 97% smoke-check accuracy may include rows the baseline saw during training. It is honestly labelled a smoke check and must never be promoted to a benchmark.
- **Domain mismatch to carry forward:** the shipped data is long-form *movie* reviews; SST-2 was trained on short sentence-level snippets; the target platform serves product/app/restaurant reviews. All three domains differ.

## 6. Dependency and Hardware Risks

- **Hardware: CPU-only** (`torch 2.5.1+cpu`, `cuda_available: False`), **15.4 GB RAM**. All design choices must assume CPU inference. Approximate model footprints: DistilBERT ≈ 270 MB, MiniLM-L6 ≈ 90 MB (already cached), RoBERTa-base models ≈ 500 MB each.
- **Disk: only ~3.7 GB free (99% full)** at audit time. Consequences: SQLite-first local development, Docker provided but optional, large model downloads deferred behind configuration, single frontend `node_modules`.
- Pins are coherent (streamlit 1.41.1 / scikit-learn 1.6.1 / transformers 4.48.3 / torch 2.5.1 / pandas 2.2.3 / joblib 1.4.2); numpy is the only unpinned drift.
- **OneDrive sync:** the working copy lives inside OneDrive — venv churn and file-lock risk for dev servers and watchers.

## 7. What Must Be Preserved

- The committed baseline artifact and its historical metrics (as legacy references, clearly separated from new results).
- The 100-row sample CSV (useful as a smoke-test fixture).
- All screenshots and the README's honest-claim discipline.
- The two-model comparison concept, which becomes the Model Laboratory's foundation.
