"""Emotion classification — a task deliberately SEPARATE from sentiment.

Model: ``j-hartmann/emotion-english-distilroberta-base`` (public checkpoint,
NOT fine-tuned by this project). Native labels: anger, disgust, fear, joy,
neutral, sadness, surprise.

The product emotion vocabulary maps onto these with a documented,
approximate correspondence — "frustration", "excitement" and
"disappointment" are NOT native labels of any public model we evaluated, so
they are presented as mappings of the closest native emotions and the UI
shows the mapping. Emotion and sentiment pipelines never merge.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

HF_MODEL_ID = "j-hartmann/emotion-english-distilroberta-base"
MAX_LENGTH = 512

#: canonical emotion -> product-facing presentation name (approximation noted)
EMOTION_PRESENTATION: dict[str, str] = {
    "joy": "Happiness / Joy / Excitement",
    "anger": "Anger / Frustration",
    "sadness": "Sadness / Disappointment",
    "disgust": "Disgust",
    "fear": "Fear",
    "surprise": "Surprise",
    "neutral": "Neutral",
}


@dataclass(frozen=True)
class EmotionPrediction:
    emotions: dict[str, float]  # canonical label -> probability
    dominant_emotion: str
    confidence: float
    latency_ms: float


class EmotionAnalyzer:
    """Lazy, lock-guarded HF checkpoint adapter — mirrors the sentiment registry pattern."""

    def __init__(self, settings: Settings) -> None:
        self.metadata_version = "1.0.0"
        self._settings = settings
        self._loaded = False
        self._lock = threading.Lock()
        self._tokenizer: Any = None
        self._model: Any = None
        self._torch: Any = None

    @property
    def model_key(self) -> str:
        return "emotion_distilroberta"

    def is_enabled(self) -> bool:
        return self._settings.enable_emotion

    def is_cached(self) -> bool | None:
        try:
            from huggingface_hub import try_to_load_from_cache
        except ImportError:  # pragma: no cover
            return None
        return isinstance(try_to_load_from_cache(repo_id=HF_MODEL_ID, filename="config.json"), str)

    def _load(self) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_ID)
        model = AutoModelForSequenceClassification.from_pretrained(HF_MODEL_ID)
        model.eval()
        self._model = model

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            logger.info("Loading emotion model %s ...", HF_MODEL_ID)
            started = time.perf_counter()
            self._load()
            logger.info("Emotion model loaded in %.1fs", time.perf_counter() - started)
            self._loaded = True

    def predict_batch(self, texts: list[str]) -> list[EmotionPrediction]:
        if not texts:
            return []
        self._ensure_loaded()
        started = time.perf_counter()
        encoded = self._tokenizer(
            texts, return_tensors="pt", truncation=True, max_length=MAX_LENGTH, padding=True
        )
        with self._torch.inference_mode():
            logits = self._model(**encoded).logits
            probs = self._torch.softmax(logits, dim=-1)
        latency_ms = (time.perf_counter() - started) * 1000.0

        id2label = self._model.config.id2label
        out: list[EmotionPrediction] = []
        for row in probs.tolist():
            emotions = {
                id2label[int(idx)].lower(): float(p) for idx, p in enumerate(row)
            }
            dominant = max(emotions, key=emotions.__getitem__)  # type: ignore[arg-type]
            out.append(
                EmotionPrediction(
                    emotions={k: round(v, 6) for k, v in sorted(emotions.items())},
                    dominant_emotion=dominant,
                    confidence=round(emotions[dominant], 6),
                    latency_ms=round(latency_ms / len(texts), 3),
                )
            )
        return out


_analyzer: EmotionAnalyzer | None = None
_lock = threading.Lock()


def get_emotion_analyzer() -> EmotionAnalyzer:
    global _analyzer
    if _analyzer is None:
        with _lock:
            if _analyzer is None:
                _analyzer = EmotionAnalyzer(get_settings())
    return _analyzer

