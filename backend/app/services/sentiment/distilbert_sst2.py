"""Adapter for the pretrained DistilBERT SST-2 sentiment model.

Model: ``distilbert/distilbert-base-uncased-finetuned-sst-2-english``
(Hugging Face). This is a **pretrained checkpoint, not a model we fine-tuned**.
It is binary (POSITIVE/NEGATIVE) — SST-2 has no neutral class, and this adapter
never invents one.

Known limitations, enforced and documented:
* Input is truncated to 512 tokens; longer reviews are effectively summarized
  by truncation. The TF-IDF baseline sees the full text — comparisons must
  acknowledge this asymmetry (the original Streamlit app did not disclose it).
* SST-2 was trained on short movie-review snippets; long product/restaurant
  reviews are out of its training domain.
* torch/transformers import lazily inside ``_load`` so API startup stays fast
  and pure-CPU deployments only pay for what they use.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.services.registry import (
    LABEL_NEGATIVE,
    LABEL_POSITIVE,
    ModelMetadata,
    SentimentModel,
    normalize_label,
)

HF_MODEL_ID = "distilbert/distilbert-base-uncased-finetuned-sst-2-english"
MAX_LENGTH = 512


class DistilBertSst2Model(SentimentModel):
    """Hugging Face checkpoint adapter with lazy torch/transformers loading."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(
            metadata=ModelMetadata(
                key="distilbert_sst2",
                display_name="DistilBERT SST-2",
                family="transformer",
                version="1.0.0",
                labels=(LABEL_POSITIVE, LABEL_NEGATIVE),
                supports_neutral=False,
                source=HF_MODEL_ID,
                provenance="pretrained_checkpoint",
                card_file="distilbert_sst2.yaml",
            ),
            settings=settings,
        )
        self._tokenizer: Any = None
        self._model: Any = None
        self._torch: Any = None

    # -- lifecycle ----------------------------------------------------------
    def is_enabled(self) -> bool:
        return self._settings.enable_distilbert

    def is_cached(self) -> bool | None:
        """Check the local HF cache without network access."""
        try:
            from huggingface_hub import try_to_load_from_cache
        except ImportError:  # pragma: no cover - transformers ships huggingface_hub
            return None
        hit = try_to_load_from_cache(repo_id=HF_MODEL_ID, filename="config.json")
        return isinstance(hit, str)

    def _load(self) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_ID)
        model = AutoModelForSequenceClassification.from_pretrained(HF_MODEL_ID)
        model.eval()
        self._model = model

    @property
    def device(self) -> str:
        if self._torch is not None and self._torch.cuda.is_available():
            return "cuda"
        return "cpu"

    # -- inference ----------------------------------------------------------
    def _predict_batch(self, texts: list[str]) -> list[dict[str, float]]:
        torch = self._torch
        assert self._tokenizer is not None and self._model is not None

        encoded = self._tokenizer(
            texts,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_LENGTH,
            padding=True,
        )
        with torch.inference_mode():
            logits = self._model(**encoded).logits
            probs = torch.softmax(logits, dim=-1)

        id2label = self._model.config.id2label
        normalized = [normalize_label(id2label[int(i)]) for i in range(probs.shape[1])]

        distributions: list[dict[str, float]] = []
        for row in probs.tolist():
            dist = {label: float(p) for label, p in zip(normalized, row, strict=True)}
            distributions.append(dist)
        return distributions
