"""CSV ingestion: reading, column mapping, cleaning, and statistics.

No schema is assumed. Column mapping can be supplied explicitly by the caller
(the UI sends it) or auto-detected with conservative, documented heuristics.
Original review text is preserved — only surrounding whitespace is stripped —
so analysis always runs on what the customer actually wrote.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from app.core.errors import PayloadTooLargeError, UnprocessableError

#: Ground-truth label aliases accepted in uploaded CSVs (conservative on purpose).
_LABEL_ALIASES: dict[str, str] = {
    "positive": "positive",
    "pos": "positive",
    "1": "positive",
    "negative": "negative",
    "neg": "negative",
    "0": "negative",
}

#: Matched against whole words of a column name ("posted_at" -> {posted, at}),
#: NOT substrings — otherwise "senTIMEment" would match "time".
_ID_NAME_HINTS = {"id", "reviewid", "rowid"}
_TIMESTAMP_NAME_HINTS = {"timestamp", "date", "time", "created", "posted"}
_LABEL_NAME_HINTS = {"label", "sentiment", "polarity", "rating"}


def _name_words(column: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", column.strip().lower()) if w}


def _parsable_date_fraction(series: pd.Series) -> float:
    sample = series.head(50).astype(str)
    sample = sample[sample.str.strip() != ""]
    if sample.empty:
        return 0.0
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    return float(parsed.notna().mean())


@dataclass(frozen=True)
class ColumnMapping:
    text: str
    label: str | None = None
    id: str | None = None
    timestamp: str | None = None


@dataclass
class IngestResult:
    """Cleaned rows plus the honest statistics of everything dropped."""

    row_count: int
    text: list[str] = field(default_factory=list)
    labels: list[str | None] = field(default_factory=list)
    raw_labels: list[str | None] = field(default_factory=list)
    external_ids: list[str | None] = field(default_factory=list)
    timestamps: list[pd.Timestamp | None] = field(default_factory=list)
    valid_rows: int = 0
    duplicate_rows: int = 0
    missing_text_rows: int = 0
    invalid_label_rows: int = 0
    unparseable_timestamp_rows: int = 0
    warnings: list[str] = field(default_factory=list)


def read_csv_with_fallback(path, max_rows: int) -> tuple[pd.DataFrame, str, list[str]]:
    """Read a CSV trying utf-8-sig first, latin-1 as a lossless last resort.

    Everything is read as str with NA handling disabled so label and id values
    survive exactly as written ("0" must not become NaN).
    """
    warnings: list[str] = []
    errors: list[str] = []
    for encoding in ("utf-8-sig", "latin-1"):
        if hasattr(path, "seek"):
            path.seek(0)  # a failed attempt leaves file-like objects drained
        try:
            frame = pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                encoding=encoding,
            )
            if encoding == "latin-1":
                warnings.append(
                    "File is not valid UTF-8; decoded with latin-1. Non-ASCII "
                    "characters may not display as intended."
                )
            if len(frame) > max_rows:
                raise PayloadTooLargeError(
                    "dataset_too_large",
                    f"CSV has {len(frame)} rows; the synchronous limit is {max_rows}.",
                    {"rows": len(frame), "max_rows": max_rows},
                )
            if frame.empty:
                raise UnprocessableError("empty_csv", "The CSV contains no data rows.")
            if frame.shape[1] < 1:
                raise UnprocessableError("no_columns", "The CSV contains no columns.")
            return frame, encoding, warnings
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
            errors.append(f"{encoding}: {exc}")
    raise UnprocessableError(
        "invalid_csv",
        "The file could not be parsed as CSV.",
        {"attempts": errors},
    )


def resolve_mapping(frame: pd.DataFrame, requested: ColumnMapping | None) -> ColumnMapping:
    """Validate an explicit mapping or auto-detect one; never silently guess."""
    columns = list(frame.columns)
    if requested is not None:
        missing = [
            name
            for name in (requested.text, requested.label, requested.id, requested.timestamp)
            if name is not None and name not in frame.columns
        ]
        if missing:
            raise UnprocessableError(
                "unknown_columns",
                "Mapped columns not present in the CSV.",
                {"missing": missing, "available": columns},
            )
        return requested
    return auto_detect_columns(frame, columns)


def auto_detect_columns(frame: pd.DataFrame, columns: list[str]) -> ColumnMapping:
    """Conservative heuristics; the response always reports what was chosen."""
    # Text: object column with the longest average content wins.
    text_col = max(
        columns,
        key=lambda c: frame[c].astype(str).str.len().mean(),
    )

    # Timestamp: word-boundary name hint (verified by parsing), then parse rate.
    timestamp_col = next(
        (
            c
            for c in columns
            if _name_words(c) & _TIMESTAMP_NAME_HINTS and _parsable_date_fraction(frame[c]) >= 0.8
        ),
        None,
    )
    if timestamp_col is None:
        for c in columns:
            if c == text_col:
                continue
            if _parsable_date_fraction(frame[c]) >= 0.8:
                timestamp_col = c
                break

    # Label: highest fraction of values that map onto the alias table.
    # Columns named like a label get a lower bar, because a stray value such
    # as "meh" among positive/negative is clearly still a sentiment column;
    # unmappable values become tracked invalid-label rows, never silent drops.
    label_col = None
    best_fraction = 0.0
    for c in columns:
        if c in (text_col, timestamp_col):
            continue
        series = frame[c].astype(str).str.strip().str.lower()
        nonempty = series[series != ""]
        if nonempty.empty:
            continue
        fraction = float(nonempty.isin(_LABEL_ALIASES).mean())
        threshold = 0.5 if _name_words(c) & _LABEL_NAME_HINTS else 0.6
        if fraction >= threshold and fraction > best_fraction:
            best_fraction = fraction
            label_col = c

    # ID: word-boundary name hint, else an all-unique short column.
    id_col = next((c for c in columns if _name_words(c) & _ID_NAME_HINTS), None)
    if id_col is None:
        for c in columns:
            if c in (text_col, label_col, timestamp_col):
                continue
            values = frame[c].astype(str)
            if values.str.len().max() <= 64 and values.nunique() == len(values) and len(values) > 1:
                id_col = c
                break

    return ColumnMapping(text=text_col, label=label_col, id=id_col, timestamp=timestamp_col)


def normalize_label(raw: str | None) -> tuple[str | None, bool]:
    """Return (normalized_label, is_present). Unmappable non-empty labels are 'invalid'."""
    if raw is None:
        return None, False
    key = str(raw).strip().lower()
    if key == "":
        return None, False
    mapped = _LABEL_ALIASES.get(key)
    return (mapped, True) if mapped else (None, True)


def ingest_frame(
    frame: pd.DataFrame,
    mapping: ColumnMapping,
    max_rows: int,
) -> IngestResult:
    """Clean rows and compute the full drop accounting."""
    result = IngestResult(row_count=len(frame))
    if result.row_count > max_rows:
        raise PayloadTooLargeError(
            "dataset_too_large",
            f"CSV has {result.row_count} rows; the synchronous limit is {max_rows}.",
            {"rows": result.row_count, "max_rows": max_rows},
        )

    texts_raw = frame[mapping.text].astype(str).str.strip()

    keep = texts_raw.ne("")
    result.missing_text_rows = int((~keep).sum())

    # Duplicates on the cleaned text; first occurrence wins.
    duplicate_mask = texts_raw.where(keep).duplicated(keep="first") & keep
    result.duplicate_rows = int(duplicate_mask.sum())
    keep = keep & ~duplicate_mask

    labels: list[str | None] = []
    raw_labels: list[str | None] = []
    if mapping.label is not None:
        for raw in frame[mapping.label].tolist():
            raw_str = str(raw).strip() if raw is not None and str(raw).strip() != "" else None
            normalized, present = normalize_label(raw_str)
            labels.append(normalized)
            raw_labels.append(raw_str if present else None)
            if present and normalized is None:
                result.invalid_label_rows += 1
    else:
        labels = [None] * result.row_count
        raw_labels = [None] * result.row_count

    timestamps: list[pd.Timestamp | None] = [None] * result.row_count
    if mapping.timestamp is not None:
        parsed = pd.to_datetime(frame[mapping.timestamp], errors="coerce", format="mixed")
        raw_ts = frame[mapping.timestamp].astype(str).str.strip()
        for i, (value, raw) in enumerate(zip(parsed, raw_ts, strict=True)):
            if raw == "":
                continue
            if pd.isna(value):
                result.unparseable_timestamp_rows += 1
            else:
                timestamps[i] = value

    external_ids: list[str | None] = [None] * result.row_count
    if mapping.id is not None:
        external_ids = frame[mapping.id].astype(str).where(
            frame[mapping.id].astype(str).str.strip().ne(""), None
        ).tolist()

    for i in range(result.row_count):
        if not keep.iloc[i]:
            continue
        result.text.append(texts_raw.iloc[i])
        result.labels.append(labels[i])
        result.raw_labels.append(raw_labels[i])
        result.external_ids.append(external_ids[i])
        result.timestamps.append(timestamps[i])
        result.valid_rows += 1

    if result.valid_rows == 0:
        raise UnprocessableError(
            "no_valid_rows",
            "No usable review rows were found after cleaning.",
            {
                "missing_text_rows": result.missing_text_rows,
                "duplicate_rows": result.duplicate_rows,
            },
        )
    return result
