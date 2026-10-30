"""Unit tests for CSV ingestion heuristics and cleaning."""

from __future__ import annotations

import io

import pandas as pd
import pytest

from app.core.errors import PayloadTooLargeError, UnprocessableError
from app.services.datasets.ingest import (
    ColumnMapping,
    auto_detect_columns,
    ingest_frame,
    normalize_label,
    read_csv_with_fallback,
)


def test_normalize_label_conservative():
    assert normalize_label("Positive") == ("positive", True)
    assert normalize_label("0") == ("negative", True)
    assert normalize_label("") == (None, False)
    assert normalize_label(None) == (None, False)
    assert normalize_label("meh") == (None, True)  # present but invalid


def test_auto_detect_columns_picks_text_label_id_timestamp():
    frame = pd.DataFrame(
        {
            "review_id": ["a", "b", "c"],
            "text": ["long text one", "long text two", "long text three"],
            "rating": ["positive", "negative", "positive"],
            "posted_at": ["2024-01-01", "2024-01-02", "2024-01-03"],
        }
    )
    mapping = auto_detect_columns(frame, list(frame.columns))
    assert mapping.text == "text"
    assert mapping.label == "rating"
    assert mapping.id == "review_id"
    assert mapping.timestamp == "posted_at"


def test_ingest_counts_every_drop_reason():
    frame = pd.DataFrame(
        {
            "text": ["good", "good", "", "fine", "bad"],
            "label": ["positive", "positive", "negative", "meh", "negative"],
        }
    )
    result = ingest_frame(
        frame, ColumnMapping(text="text", label="label"), max_rows=100
    )
    assert result.row_count == 5
    assert result.duplicate_rows == 1
    assert result.missing_text_rows == 1
    assert result.invalid_label_rows == 1
    # Kept: "good"(positive), "fine"(invalid label -> None), "bad"(negative).
    assert result.valid_rows == 3
    assert result.labels == ["positive", None, "negative"]
    assert result.raw_labels == ["positive", "meh", "negative"]


def test_ingest_rejects_row_overflow():
    frame = pd.DataFrame({"text": ["a"] * 11})
    with pytest.raises(PayloadTooLargeError):
        ingest_frame(frame, ColumnMapping(text="text"), max_rows=10)


def test_ingest_requires_some_valid_rows():
    frame = pd.DataFrame({"text": ["", "  "]})
    with pytest.raises(UnprocessableError):
        ingest_frame(frame, ColumnMapping(text="text"), max_rows=10)


def test_read_csv_latin1_fallback_warns():
    latin1_bytes = "id,text\n1,caf\xe9 was great\n".encode("latin-1")
    path = io.BytesIO(latin1_bytes)
    frame, encoding, warnings = read_csv_with_fallback(path, max_rows=100)
    assert encoding == "latin-1"
    assert any("latin-1" in w for w in warnings)
    assert frame.iloc[0]["text"] == "café was great"


def test_read_csv_rejects_garbage():
    with pytest.raises(UnprocessableError):
        read_csv_with_fallback(io.BytesIO(b"\x00\xff\x00\xfe"), max_rows=10)
