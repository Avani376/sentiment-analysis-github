# SENTINEX AI — Product Requirements

**Product:** SENTINEX AI — AI Review Intelligence Platform
**Tagline:** Understand Opinions. Discover Patterns. Make Smarter Decisions.
**Source:** Derived from the project master directive; constrained by the findings in [REPOSITORY_AUDIT.md](REPOSITORY_AUDIT.md).

Primary users: product managers, business analysts, customer-experience teams, marketing teams, researchers, developers.

---

## Module Requirements

### A. Sentiment Intelligence Engine

- Model-independent prediction interface (registry pattern); every model declares its own label map, version, and model card.
- Models: (1) TF-IDF + Logistic Regression — retrained with documented provenance; (2) DistilBERT SST-2 (pretrained); (3) `cardiffnlp/twitter-roberta-base-sentiment-latest` as the neutral-capable 3-class model (configurable, lazy-loaded).
- **Binary models are never forced to emit neutral.** The API marks neutral as absent for models that do not support it.
- Positive/negative/neutral per model capability; probabilities; batch inference; input validation; configurable model selection; latency measurement; model metadata and version tracking.
- Confidence (predicted-class probability) is explicitly distinguished from calibrated probability.

**Acceptance criteria:** `/api/v1/analyze/single` returns label(s), probabilities, latency, and model metadata for each registered model; a binary model's response contains no neutral field; invalid input returns HTTP 422 with a structured error.

### B. Emotion Intelligence Engine

- Pretrained model: `SamLowe/roberta-base-go_emotions` (28-label multi-label) with an **explicit published mapping** to the product emotion set (joy→happiness/excitement, anger→frustration, sadness→disappointment, fear, …). Mappings are approximations and will be documented as such.
- Emotion classification remains a **separate pipeline** from sentiment classification — never merged or compared as if equivalent.
- Dominant emotion, per-emotion scores, distribution across a dataset, representative examples.

**Acceptance criteria:** an emotion result always coexists with (not replaces) the sentiment result; the mapping table is shipped in the model card and shown in the UI.

### C. Aspect-Based Sentiment Analysis (ABSA)

- **Transparent two-stage baseline first:** clause segmentation → aspect term extraction (noun phrases + curated category lexicon: quality, pricing, delivery, support, performance, UX, design, reliability) → clause-level polarity via registered sentiment models → evidence spans + review IDs.
- Clearly labelled as a **rule-based baseline**, not a trained ABSA model. SemEval-2014 Task 4 is documented as the path to a trained model (future work).
- Per aspect: mention detection, polarity, supporting text span, confidence indicator; aggregation across reviews; multi-aspect review handling.

**Acceptance criteria:** every aspect result carries the exact supporting text span; the UI states the method is a rule-based baseline.

### D. Topic Discovery

- Baseline: TF-IDF + K-Means (works offline, CPU, small datasets). Optional: BERTopic with `all-MiniLM-L6-v2` embeddings (already cached locally) behind a config flag for larger datasets.
- Topic keywords, representative reviews, topic size, outlier handling where the algorithm supports it; topic-level sentiment; configurable `min_topic_size`.
- Small datasets handled gracefully; never force every review into a "meaningful" topic.

**Acceptance criteria:** a 30-row dataset produces a graceful result (few topics or an explicit "too few reviews" state), never a crash or fabricated topics.

### E. Review Explorer

Full-text search; sentiment/emotion/aspect/topic filters; date filtering when timestamps exist; sorting; pagination; review detail view with prediction evidence; export of filtered results (CSV).

### F. Business Intelligence Engine

- Deterministic, **evidence-grounded** insight generation: executive summary, positive themes, negative themes, recurring complaints, improvement opportunities, priority recommendations.
- Every insight links to supporting review IDs and/or computed statistics, with an evidence-strength indicator (sample size + Wilson confidence interval).
- Optional LLM provider: disabled by default; env-keyed; receives only aggregates + representative quotes; returns Pydantic-validated structured JSON; citations restricted to review IDs supplied in the prompt. Observed facts and suggested actions are labelled distinctly.

**Acceptance criteria:** an automated test asserts every generated insight contains ≥1 valid review-ID citation or statistic reference; no insight is produced for an empty dataset.

### G. Trends & Anomalies (added-value module)

- Time-bucketed sentiment/aspect/topic trends when timestamps exist; minimum sample thresholds; time window and baseline always displayed; no significance claims without a real statistical test.

### H. ML Model Laboratory

- Paired evaluation of all registered models on the **identical held-out test set**; accuracy, precision, recall, macro/weighted F1, per-class metrics, confusion matrix, ROC-AUC where applicable, inference latency, throughput, model size.
- Fixed random seeds; documented splits; reproducible scripts (`ml/train_logreg.py`, `ml/evaluate.py`); saved evaluation artifacts (JSON); historical metrics and newly reproduced metrics **never mixed in one chart**.
- MLflow tracking (file-based local backend; server optional).

**Acceptance criteria:** running the eval script twice yields identical metrics; the report lists dataset version, split config, seeds, and package versions.

### I. Dataset Management

CSV upload with validation, size limits, preview, column mapping (text/label/timestamp/id), missing-value detection, duplicate detection, text cleaning stats, invalid-row handling, encoding handling, dataset statistics, processing progress, export. Clear error messages; no schema assumptions; safe file handling.

### J. Reports

Export CSV results; executive report; model comparison report; aspect report; topic report — all generated from actual analysis results, including dataset info, period, model versions, and limitations.

---

## User Experience Requirements

Premium dark-first SaaS interface (React + TypeScript + Vite + Tailwind + shadcn/ui + Recharts + TanStack Query + React Router). Pages:

1. Overview Dashboard (KPIs computed from actual records only)
2. Single Review Analyzer
3. Bulk Analysis (upload → job progress → results)
4. Review Explorer
5. Sentiment Intelligence
6. Emotion Intelligence
7. Aspect Intelligence
8. Topic Explorer
9. Trends & Anomalies
10. Business Insights
11. Model Laboratory
12. Dataset Management
13. Reports
14. Settings & About

Every page has real loading, empty, error, and success states. No decorative buttons; every control is functional. Responsive layout; accessible contrast; tooltips on non-obvious metrics.

## MVP Definition (gate at end of Milestone 4)

Upload CSV → map columns → batch sentiment across registered models → Overview Dashboard (real distributions, confidence, latency) → Review Explorer (search/filter/sort/paginate/export) → Model Laboratory with the reproducible IMDb evaluation. Everything else lands as vertical slices in later milestones.

## Non-Functional Requirements

- CPU-only inference is a first-class path; models lazy-load and are reused across requests.
- Environment-based configuration; no secrets committed; no raw review text in logs.
- Pagination and upload limits on all collection endpoints.
- Structured logging; health checks; graceful model-loading failures.
- Reproducible environments; pinned dependencies.
- **Environment constraint (recorded at audit time):** ~3.7 GB free disk on the development machine — SQLite-first local dev, Docker optional, large model downloads deferred/config-gated.
