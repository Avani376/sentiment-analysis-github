# SENTINEX AI — Implementation Plan

Working strategy: **all work happens in this repository and is pushed directly to GitHub** after every milestone (owner directive, 2026-10-30). The development machine is disk-constrained (~3.7 GB free), so heavy operations are designed around.

## Decision Log

| # | Decision | Rationale | Source |
|---|---|---|---|
| D1 | Build additively on `main` in the same repo; Streamlit app preserved until parity is proven, then moved to `legacy/` | Owner chose in-repo build and delegated the exact structure; single-author repo, master directive discourages extra branches | Owner (2026-10-30) |
| D2 | Develop in the local clone, **push every milestone to GitHub**; SQLite-first dev DB; Docker optional; large model downloads config-gated and deferred | Owner: "do this directly to github"; local disk ~3.7 GB free | Owner (2026-10-30) + audit finding |
| D3 | **Retrain** TF-IDF + LogReg on public IMDb with documented provenance; keep the committed artifact as `legacy` with its historical metrics clearly separated | The only path to honest reproducibility claims in the Model Lab | Engineer judgment (owner delegated unanswered questions) |
| D4 | Add `cardiffnlp/twitter-roberta-base-sentiment-latest` (~500 MB, lazy-loaded, config-gated download) as the neutral-capable 3-class model | Binary models must never fake neutral; a real 3-class model is the honest solution | Engineer judgment (delegated) |
| D5 | Emotion engine: `SamLowe/roberta-base-go_emotions` with a documented label mapping to the product emotion set | Multi-label 28-emotion model maps onto the requested emotion set; mapping documented as approximation | Engineer judgment (delegated) |
| D6 | Background jobs via job table + thread pool; Celery/Redis deferred until a measured workload justifies them | Master directive: heavy infra only when justified | Master directive |
| D7 | Authentication deferred beyond the MVP; single-workspace design, documented honestly in limitations | Portfolio scope control; auth adds surface without portfolio value early | Engineer judgment |

## Milestones & Gates

| Milestone | Scope | Gate (must pass before next) | Est. sessions |
|---|---|---|---|
| M0 ✅ | Audit + these four planning docs | Owner approval | 1 |
| M1 | Scaffolding: backend+frontend skeletons, config, logging, health, CI workflow, LICENSE, .env.example, devcontainer refresh | `docker compose config` valid; CI green on push; FastAPI `/health` responds | 2–3 |
| M2 | Model registry + TF-IDF/DistilBERT adapters; datasets service (upload/validate/mapping); DB schema + Alembic; `/analyze/*`, `/datasets/*`; `ml/train_logreg.py` retrain + eval script | pytest green incl. artifact round-trip; new IMDb-trained artifact + metrics JSON committed; API docs render | 4–6 |
| M3 | Frontend shell (sidebar, dataset context, API client), Single Analyzer, Overview Dashboard, Review Explorer | Playwright E2E: analyze → dashboard reflects → explorer filters | 4–6 |
| M4 | Bulk upload + job runner + analytics endpoints + charts + CSV export | 10k-row CSV processes as a background job with live progress; **MVP gate** | 3–4 |
| M5 | Emotion engine + ABSA baseline | Emotion/sentiment stay separate; every aspect result shows its evidence span | 3–5 |
| M6 | Topic Explorer + trends/anomalies with minimum-sample thresholds | 30-row dataset handled gracefully | 2–4 |
| M7 | Evidence-grounded Business Insights (+ optional LLM provider) | Automated test: every insight cites valid review IDs | 2–3 |
| M8 | Model Laboratory: paired evaluation, MLflow tracking, evaluation reports | Same test set for all models; artifacts saved; legacy vs reproduced separated | 2–4 |
| M9 | Security hardening, full test pyramid, benchmarks (latency/throughput/memory) | Measured numbers published with methodology | 3–5 |
| M10 | Production Docker, README rebuild, real screenshots, demo script | No unverified claims anywhere | 2–4 |

Total estimate: **27–44 focused sessions** (~5–9 part-time weeks).

## Phase-End Reporting Contract

Every milestone ends with: what was implemented; files created/modified; how to run it; actual test output; remaining issues; push to GitHub; owner approval requested before the next major phase.

## Environment Constraints & Mitigations

| Constraint | Mitigation |
|---|---|
| ~3.7 GB free disk | SQLite dev default; no local Docker requirement; reuse existing py3.11 venv (torch already installed); single `node_modules`; config-gated model downloads (cardiffnlp, go_emotions downloaded only when their feature phase starts) |
| CPU-only inference | Batch inference, lazy loading + LRU model cache, latency budgets measured and published |
| OneDrive-synced working copy | Commits pushed after every milestone so GitHub always holds the durable copy |
| 15.4 GB RAM | Max two heavy transformers resident; documented per-model RAM in model cards |

## Top Risks

1. **Provenance reset (D3)** — Model Lab credibility depends on the retrain; mitigated by keeping the legacy artifact untouched and separated.
2. **Neutral-class honesty (D4)** — no threshold-band pseudo-neutral; real 3-class model, clearly carded.
3. **ABSA overpromising** — shipped as a documented rule-based baseline; SemEval-trained model is explicitly future work.
4. **Job-runner correctness** — progress, cancellation, and timeouts must actually work; covered by integration tests at M4.
5. **Scope vs. single developer** — strict MVP gate at M4; no new module starts before the previous one passes its E2E gate.
