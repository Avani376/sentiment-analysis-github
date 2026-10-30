# SENTINEX AI — Target Architecture

Modular monolith (FastAPI) + SPA (React), one repository, additive migration from the existing Streamlit app.

```
sentiment-analysis-github/
├── legacy/                           # existing Streamlit app (moved after parity is proven)
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI factory, /health, exception handlers, logging
│   │   ├── core/
│   │   │   ├── config.py             # pydantic-settings, .env driven, no hardcoded secrets
│   │   │   └── logging.py            # structured logging (no raw review text in logs)
│   │   ├── api/v1/
│   │   │   ├── analyze.py            # POST /analyze/single, /analyze/batch
│   │   │   ├── datasets.py           # POST /datasets/upload, GET /datasets, /datasets/{id},
│   │   │   │                         #   /datasets/{id}/reviews
│   │   │   ├── analytics.py          # GET /analytics/overview|sentiment|emotions|aspects|topics|trends
│   │   │   ├── models.py             # GET /models, /models/compare
│   │   │   ├── insights.py           # POST /insights/generate
│   │   │   ├── jobs.py               # GET /jobs/{id}  (background job status)
│   │   │   └── reports.py            # GET /reports/{id}
│   │   ├── db/                       # SQLAlchemy 2.0 engine/session, Alembic migrations
│   │   ├── schemas/                  # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── registry.py           # model registry + SentimentModel protocol
│   │   │   ├── sentiment/            # tfidf_logreg.py · distilbert_sst2.py · cardiffnlp_3class.py
│   │   │   ├── emotion/              # go_emotions adapter + documented label mapping
│   │   │   ├── absa/                 # clause segmentation, aspect lexicon, polarity binding
│   │   │   ├── topics/               # tfidf_kmeans.py (default) · bertopic_optional.py
│   │   │   ├── insights/             # deterministic evidence-grounded generator (+ optional LLM)
│   │   │   ├── analytics/            # aggregations powering dashboards
│   │   │   └── datasets/             # CSV validation, column mapping, cleaning, stats
│   │   └── workers/jobs.py           # job table + thread-pool batch inference with progress
│   ├── ml/
│   │   ├── train_logreg.py           # reproducible training on public IMDb (seeded, split saved)
│   │   ├── evaluate.py               # paired evaluation of all registered models
│   │   └── data/                     # dataset download + provenance scripts
│   ├── artifacts/                    # YAML model cards + JSON evaluation artifacts
│   ├── alembic/                      # migrations
│   └── tests/                        # unit · API integration · model · evidence-traceability
├── frontend/
│   └── src/
│       ├── app/                      # router, sidebar layout, dataset context provider
│       ├── pages/                    # 14 pages per PRODUCT_REQUIREMENTS.md
│       ├── components/               # charts, KPI cards, tables, states (loading/empty/error)
│       ├── lib/                      # typed API client, response types
│       └── hooks/                    # TanStack Query hooks
├── docker-compose.yml                # postgres + backend + frontend (OPTIONAL — see constraints)
├── .env.example
├── REPOSITORY_AUDIT.md · PRODUCT_REQUIREMENTS.md · ARCHITECTURE.md · IMPLEMENTATION_PLAN.md
└── README.md                         # rebuilt in the final phase with verified evidence only
```

## Core Design

### 1. Model Registry (the central abstraction)

```python
class SentimentModel(Protocol):
    metadata: ModelMetadata          # name, version, family, label_map, supports_neutral, artifact ref
    def predict_batch(self, texts: list[str]) -> list[Prediction]  # labels, probs, per-item latency
```

- Each adapter owns its label mapping; **binary models never emit neutral** (the schema omits it).
- Lazy loading with a small LRU cache: at most two heavy transformers resident at once (RAM budget on the 16 GB audit machine).
- Every model ships a YAML model card in `backend/artifacts/` — provenance, label map, limitations, intended domain.

### 2. Registered Models

| Key | Model | Classes | Provenance |
|---|---|---|---|
| `tfidf_logreg_v2` | TF-IDF + LogReg, retrained on public IMDb | binary | Trained in-repo, seeded, split saved |
| `tfidf_logreg_legacy` | Committed 2024 artifact | binary | Unknown provenance — historical reference only |
| `distilbert_sst2` | `distilbert-base-uncased-finetuned-sst-2-english` | binary | Pretrained checkpoint (not fine-tuned by us) |
| `cardiffnlp_3class` | `twitter-roberta-base-sentiment-latest` | pos/neu/neg | Pretrained checkpoint; downloaded on first use (config-gated) |

### 3. Data Flow

```
CSV upload → validation/mapping → Dataset + Reviews rows
   → background job (thread pool) → batch predictions → Prediction/EmotionResult/AspectResult rows
   → analytics service aggregates on demand → dashboard / explorer / insights / reports
```

- Long-running batches never block an HTTP request: `POST /analyze/batch` enqueues a job, the client polls `GET /jobs/{id}` with progress.
- Job runner: FastAPI thread pool + `jobs` table. Celery/Redis is deliberately deferred until a measured workload justifies it.

### 4. Database (PostgreSQL target, SQLite dev default)

Tables: `datasets`, `reviews`, `predictions`, `emotion_results`, `aspect_results`, `topics`, `jobs`, `model_metadata`, `insights`, `reports`. UUID primary keys where appropriate; indexes on `(dataset_id, sentiment)`, review text search, job status; timestamps on everything. Large binaries (models, CSVs) stay on the filesystem, never in the DB.

The SQLAlchemy layer makes **SQLite the zero-install dev default** (audit constraint: ~3.7 GB free disk); `docker-compose.yml` provides PostgreSQL for users who can run it.

### 5. API Principles

`/api/v1/` prefix; Pydantic-validated requests; consistent error envelope; pagination on collections; proper status codes (422 validation, 404 missing, 409 conflict, 413 upload too large); OpenAPI docs automatic; structured logs without raw review text.

### 6. Frontend

React 18 + TypeScript + Vite + Tailwind + shadcn/ui + Recharts + React Router + TanStack Query. Global dataset selector in the sidebar; typed API client generated against the OpenAPI schema; loading skeletons, empty states, error states, toasts on every async surface.

### 7. Evaluation & Provenance

- `ml/train_logreg.py`: downloads public IMDb (documented source + SHA or row-count check), fixed seed, versioned split → new artifact + metrics JSON.
- `ml/evaluate.py`: same held-out set for every model; writes `artifacts/evaluations/<run>.json` with dataset version, split config, seeds, package versions.
- Historical (legacy) metrics and reproduced metrics are stored and rendered **separately, always labelled**.

### 8. Configuration & Security

`.env` via pydantic-settings (`.env.example` committed); upload size limits + extension sniffing; no `eval`/`pickle` on user files; job cancellation; request timeouts; health endpoint; optional LLM provider keys never logged.
