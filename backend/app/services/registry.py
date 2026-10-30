"""The model registry: one interface over every sentiment model.

Design rules enforced here:

1. Every model declares its own label mapping — the registry never guesses.
2. Binary models are NEVER forced to emit a neutral label; ``supports_neutral``
   is part of each model's metadata and the API omits neutral for them.
3. Models load lazily, guarded by per-model locks, so a request never blocks
   on a model another request is already loading, and heavy weights are never
   resident unless a feature actually needs them.
4. Confidence (predicted-class probability) is reported as-is and is NOT
   treated as calibrated probability — model cards say this explicitly.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import yaml

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ServiceUnavailableError

logger = logging.getLogger(__name__)

#: Canonical normalized labels used across the entire API.
LABEL_POSITIVE = "positive"
LABEL_NEGATIVE = "negative"
LABEL_NEUTRAL = "neutral"

_POSITIVE_ALIASES = {"1", "positive", "pos", "label_1", "p"}
_NEGATIVE_ALIASES = {"0", "negative", "neg", "label_0", "n"}
_NEUTRAL_ALIASES = {"2", "neutral", "neu", "label_2"}


def normalize_label(raw: Any) -> str:
    """Map a model-specific class to the canonical label vocabulary.

    Raises ValueError for unmappable classes — adapters validate their class
    set at load time so a bad artifact fails fast instead of mislabelling.
    """
    key = str(raw).strip().lower()
    if key in _POSITIVE_ALIASES:
        return LABEL_POSITIVE
    if key in _NEGATIVE_ALIASES:
        return LABEL_NEGATIVE
    if key in _NEUTRAL_ALIASES:
        return LABEL_NEUTRAL
    raise ValueError(f"Cannot map model class {raw!r} to a normalized sentiment label.")


@dataclass(frozen=True)
class ModelMetadata:
    """Technical identity of a model; the descriptive model card lives in YAML."""

    key: str
    display_name: str
    family: str  # "tfidf_logreg" | "transformer"
    version: str
    labels: tuple[str, ...]
    supports_neutral: bool
    source: str  # artifact path (relative) or Hugging Face id
    #: trained_in_repo | legacy_artifact | pretrained_checkpoint
    provenance: str
    card_file: str | None = None


@dataclass(frozen=True)
class PredictionResult:
    label: str
    probabilities: dict[str, float]
    confidence: float
    latency_ms: float  # total batch latency; per-item = latency_ms / n


@dataclass
class ModelCard:
    """Descriptive card loaded from ``backend/artifacts/model_cards/<key>.yaml``."""

    description: str = ""
    intended_domain: str = ""
    limitations: list[str] = field(default_factory=list)
    calibration: str = ""
    training_provenance: str = ""


class SentimentModel(ABC):
    """Base adapter. Subclasses implement loading and raw batch prediction."""

    def __init__(self, metadata: ModelMetadata, settings: Settings) -> None:
        self.metadata = metadata
        self._settings = settings
        self._loaded = False
        self._lock = threading.Lock()

    # -- lifecycle ----------------------------------------------------------
    def is_enabled(self) -> bool:
        """Config toggle; disabled models are listed but not usable."""
        return True

    def is_cached(self) -> bool | None:
        """True/False when the weights are (not) on local disk; None = N/A."""
        return None

    @property
    def download_required(self) -> bool:
        return self.is_cached() is False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:  # double-checked: another thread may have loaded
                return
            logger.info("Loading model %s (%s)...", self.metadata.key, self.metadata.source)
            started = time.perf_counter()
            self._load()
            logger.info("Model %s loaded in %.1fs", self.metadata.key, time.perf_counter() - started)
            self._loaded = True

    @abstractmethod
    def _load(self) -> None:
        """Load weights/artifacts. Must be cheap to call repeatedly via _ensure_loaded."""

    @abstractmethod
    def _predict_batch(self, texts: list[str]) -> list[dict[str, float]]:
        """Return per-text {normalized_label: probability} distributions."""

    # -- public -------------------------------------------------------------
    def predict_batch(self, texts: list[str]) -> list[PredictionResult]:
        """Validate, load lazily, predict, and time the batch."""
        if not texts:
            return []
        self._ensure_loaded()
        started = time.perf_counter()
        distributions = self._predict_batch(texts)
        latency_ms = (time.perf_counter() - started) * 1000.0

        results: list[PredictionResult] = []
        for dist in distributions:
            # Clamp+renormalize defensively so the API always returns a valid
            # distribution even if a backend drifts slightly from sum-1.
            total = sum(dist.values()) or 1.0
            clean = {k: max(0.0, min(1.0, v)) / total for k, v in dist.items()}
            label = max(clean, key=clean.__getitem__)  # type: ignore[arg-type]
            results.append(
                PredictionResult(
                    label=label,
                    probabilities={k: round(v, 6) for k, v in sorted(clean.items())},
                    confidence=round(clean[label], 6),
                    latency_ms=round(latency_ms, 3),
                )
            )
        return results

    def predict_single(self, text: str) -> PredictionResult:
        return self.predict_batch([text])[0]

    # -- card ---------------------------------------------------------------
    def load_card(self) -> ModelCard:
        if not self.metadata.card_file:
            return ModelCard()
        path = self._settings.model_cards_dir / self.metadata.card_file
        if not path.is_file():
            logger.warning("Model card missing for %s: %s", self.metadata.key, path.name)
            return ModelCard()
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return ModelCard(
            description=raw.get("description", ""),
            intended_domain=raw.get("intended_domain", ""),
            limitations=list(raw.get("limitations", [])),
            calibration=raw.get("calibration", ""),
            training_provenance=raw.get("training_provenance", ""),
        )


class ModelRegistry:
    """Holds model adapter instances; wires availability from config."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._models: dict[str, SentimentModel] = {}
        self._order: list[str] = []

    def register(self, model: SentimentModel) -> None:
        if model.metadata.key in self._models:
            raise ValueError(f"Duplicate model key: {model.metadata.key}")
        self._models[model.metadata.key] = model
        self._order.append(model.metadata.key)

    def keys(self) -> list[str]:
        return list(self._order)

    def get(self, key: str) -> SentimentModel:
        model = self._models.get(key)
        if model is None:
            raise NotFoundError(
                "model_not_found",
                f"Unknown model key {key!r}.",
                {"available": self._order},
            )
        return model

    def ensure_usable(self, key: str) -> SentimentModel:
        """Return a model that is enabled; raises 404/503 with clear codes."""
        model = self.get(key)
        if not model.is_enabled():
            raise ServiceUnavailableError(
                "model_disabled",
                f"Model {key!r} is disabled by configuration.",
                {"enable_via": f"SENTINEX_ENABLE_{key.upper()}=true"},
            )
        try:
            model._ensure_loaded()
        except FileNotFoundError as exc:
            raise ServiceUnavailableError(
                "model_artifact_missing",
                f"Artifact for {key!r} is not available: {exc}",
            ) from exc
        except Exception as exc:
            raise ServiceUnavailableError(
                "model_load_failed",
                f"Model {key!r} failed to load: {type(exc).__name__}",
            ) from exc
        return model

    def describe_all(self) -> list[dict[str, Any]]:
        """Metadata + availability for the /models listing (no weight loading)."""
        out = []
        for key in self._order:
            model = self._models[key]
            cached = model.is_cached()
            out.append(
                {
                    "key": key,
                    "display_name": model.metadata.display_name,
                    "family": model.metadata.family,
                    "version": model.metadata.version,
                    "labels": list(model.metadata.labels),
                    "supports_neutral": model.metadata.supports_neutral,
                    "provenance": model.metadata.provenance,
                    "source": model.metadata.source,
                    "enabled": model.is_enabled(),
                    "cached": cached,
                    "download_required": model.download_required,
                }
            )
        return out


_registry: ModelRegistry | None = None
_registry_lock = threading.Lock()


def build_registry(settings: Settings) -> ModelRegistry:
    """Construct the registry with every model; config toggles enable/disable.

    Disabled models stay listed in ``/models`` with ``enabled: false`` so the
    UI can explain how to turn them on, while inference endpoints refuse them.
    """
    # Imported here to avoid import cycles and heavy transformers import at startup.
    from app.services.sentiment.distilbert_sst2 import DistilBertSst2Model
    from app.services.sentiment.tfidf_logreg import TfidfLogregModel

    registry = ModelRegistry(settings)
    registry.register(TfidfLogregModel.legacy(settings))
    registry.register(TfidfLogregModel.imdb_v1(settings))
    registry.register(DistilBertSst2Model(settings))
    # cardiffnlp/twitter-roberta-base-sentiment-latest (3-class neutral) is
    # added in Milestone 4 together with its model card and download gate.
    return registry


def get_registry() -> ModelRegistry:
    """Process-wide registry singleton (built once, thread-safe)."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = build_registry(get_settings())
    return _registry


def reset_registry() -> None:
    """Test hook: drop the singleton so tests can rebuild with their settings."""
    global _registry
    with _registry_lock:
        _registry = None
