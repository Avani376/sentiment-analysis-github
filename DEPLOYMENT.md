# SENTINEX AI — Deployment Guide

The repository ships everything needed to deploy the **real application**: a
multi-stage `Dockerfile` (builds the React SPA, then serves it from FastAPI),
a `docker-compose.yml` for local full-stack runs, a `render.yaml`
blueprint for one-service cloud deployment, and **Vercel serverless config**
(`vercel.json` + `api/index.py`) for a FastAPI-function + static-SPA split.

> **Status (2026-11-02):** Vercel and Render configurations are prepared and
> locally validated. A public URL requires the repository owner's account
> (no cloud credentials exist on the dev machine). A temporary Cloudflare
> quick-tunnel link has been used for live verification.

---

## 0. Vercel (serverless — fastest path to a permanent URL)

**Requires: a Vercel account + token.** Create a token at
[vercel.com/account/tokens](https://vercel.com/account/tokens) (30 seconds),
then from the repository root:

```bash
npx vercel deploy --prod --yes --token <YOUR_TOKEN>
```

What the shipped config does:

| Piece | Detail |
|---|---|
| `api/index.py` | FastAPI as a serverless ASGI function (`/api/*`, `/health`, `/docs`, `/openapi.json`) |
| `frontend` | `@vercel/static-build` → React SPA served from the edge, `index.html` catch-all for client-side routes |
| Database | SQLite on `/tmp` — persists while the instance is warm; **for real persistence create Vercel Postgres** (Storage tab) and set `SENTINEX_DATABASE_URL` |
| Models | The two TF-IDF models run serverless; **DistilBERT is off** — Vercel's 250 MB function limit cannot fit torch + weights |
| Uploads | Capped at 4 MB (Vercel body limit); CSV files are consumed within the request, so `/tmp` is sufficient |

Verified locally via `scripts/simulate_vercel.py` (the exact entrypoint
import + health/analyze/models/upload round-trip).

**Known risk:** the pandas + scikit-learn + scipy function bundle is close to
Vercel's 250 MB unpacked limit. If the deploy fails on function size, use the
Render path below — the same application runs there without limits.

## 1. Local full-stack run (Docker)

```bash
docker compose up --build
# → http://localhost:8000  (dashboard + API + docs)
```

- The app starts with SQLite, runs Alembic migrations on boot, and serves the
  built SPA plus `/api/v1/*` on the same port.
- DistilBERT is **off by default** in containers (memory). Turn it on with
  `SENTINEX_ENABLE_DISTILBERT=true` — the ~270 MB checkpoint downloads on
  first use.
- Optional PostgreSQL: `docker compose --profile postgres up` (then set
  `SENTINEX_DATABASE_URL=postgresql+psycopg://sentinex:sentinex@postgres:5432/sentinex`).

Verified locally: `docker compose config` passes (syntax/structure valid) and
the app itself is verified outside Docker on this machine. **The image build
has not been executed yet** — the dev machine's Docker daemon was not running
and its disk could not absorb the build; run `docker compose up --build` on a
machine with ~2 GB free and report back. The Dockerfile is authored to match
the verified local layout exactly.

## 2. Deploy to Render (recommended free path)

**Requires: a Render account (free) owned by you.** No other prerequisites.

1. Sign in at [dashboard.render.com](https://dashboard.render.com) with GitHub.
2. **New → Blueprint** → select `Avani376/sentiment-analysis-github` → Render
   reads `render.yaml` and offers the `sentinex-ai` web service.
3. Review the env vars (pre-filled in the blueprint), then **Apply**.
4. First build takes ~5–8 minutes (Node + Python install + frontend build).
5. When it goes live, verify in this order:
   - `https://<service>.onrender.com/health` → `{"status": "ok", ...}`
   - `https://<service>.onrender.com/` → dashboard loads
   - **Analyze Review** → run the mixed example → both TF-IDF models respond
     (DistilBERT is disabled on free tier — flip `SENTINEX_ENABLE_DISTILBERT`
     to `true` on a paid plan and redeploy to enable it)
   - **Review Explorer** → import `data/demo_product_reviews.csv` (48 rows)
6. Add the verified URL to the README "Live demo" section.

**Free-tier caveats (stated plainly):**

| Constraint | Effect | Mitigation |
|---|---|---|
| Ephemeral disk | Uploaded datasets/predictions reset on redeploy | Attach a paid disk + Render Postgres, then set `SENTINEX_DATABASE_URL` |
| ~512 MB RAM | DistilBERT adapter must stay off | Upgrade plan for the transformer model |
| Cold starts | First request after idle sleeps ~30–60 s | Expected on free plans |

## 3. Alternative: Hugging Face Spaces (Docker)

The same `Dockerfile` runs as a Space:

1. Create a **Docker** Space named `sentinex-ai` under your HF account.
2. Push the repository (or upload a copy); set the Space SDK to **Docker**.
3. In Space settings, expose port **7860** — the container must listen there,
   so set `PORT=7860` (the CMD honours `$PORT`).
4. App RAM: 16 GB on free CPU hardware — `SENTINEX_ENABLE_DISTILBERT=true` is
   viable here.

## 4. Environment variables (production)

| Variable | Default | Notes |
|---|---|---|
| `SENTINEX_DATABASE_URL` | SQLite in `.runtime/` | Point at Postgres for persistence |
| `SENTINEX_ENABLE_DISTILBERT` | `true` (local) / `false` (container) | Downloads ~270 MB on first use |
| `SENTINEX_ENABLE_CARDIFFNLP` | `false` | 3-class model — arrives in Milestone 4 |
| `SENTINEX_MAX_UPLOAD_MB` | `10` | Keep small on low-RAM plans |
| `SENTINEX_BATCH_LIMIT` | `100` | Sync inference cap |
| `SENTINEX_LOG_LEVEL` | `INFO` | `WARNING` for quiet production logs |
| `PORT` | `8000` | Render injects this automatically |

No secrets are required for any shipped feature. If/when the optional LLM
insight provider lands (Milestone 7), its key goes in
`SENTINEX_LLM_API_KEY` — set it in the provider's dashboard, never in git.

## 5. Deployment verification checklist

Run all of these before claiming a deployment works:

- [ ] `/health` → `{"status":"ok","database":"ok",...}`
- [ ] `/` renders the dashboard (not the API error page)
- [ ] `/api/v1/models` lists 3 models with expected `enabled` flags
- [ ] Analyze a positive and a negative review — labels + probabilities return
- [ ] `POST /api/v1/datasets/upload` with the demo CSV → 201, stats correct
- [ ] `/docs` (OpenAPI) renders
- [ ] No secrets in logs; `SENTINEX_LOG_LEVEL=INFO` shows no review text
