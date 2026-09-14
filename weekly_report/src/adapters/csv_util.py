"""Robust CSV loading that does not depend on csv.Sniffer.

Python's Sniffer raises ``Could not determine delimiter`` on wide Qlik exports
(sample is a partial row) and on Excel "everything in column A" files (each
line is one quoted field containing commas). pandas can also "succeed" with
the wrong separator and return a single giant column.

This helper picks comma / semicolon / tab / pipe from the header, retries when
the result looks unsplit, and only then tries quote-stripping.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pandas as pd
from loguru import logger

NA_VALUES: List[str] = ["", "NULL", "null", "N/A", "n/a"]
_ENCODINGS: Sequence[str] = ("utf-8-sig", "utf-8", "cp1252", "latin-1", "utf-16")
_SEPARATORS: Sequence[str] = (",", ";", "\t", "|")


def _peek_first_nonempty_line(path: Path, encoding: str) -> str:
    with path.open("r", encoding=encoding, errors="strict", newline="") as handle:
        for raw in handle:
            line = raw.strip("\r\n").lstrip("\ufeff").strip()
            if line:
                return line
    return ""


def _unwrap_fully_quoted_line(line: str) -> str:
    """If the entire row was saved as one quoted Excel cell, unwrap it."""
    if len(line) >= 2 and line[0] == '"' and line[-1] == '"':
        inner = line[1:-1]
        if '"' not in inner.replace('""', ""):
            return inner.replace('""', '"')
    return line


def guess_csv_separator(header_line: str) -> str:
    line = _unwrap_fully_quoted_line(header_line.strip())
    counts = {sep: line.count(sep) for sep in _SEPARATORS}
    best = max(counts, key=counts.get)
    if counts[best] == 0:
        return ","
    return best


def _header_looks_unsplit(df: pd.DataFrame, used_sep: str) -> bool:
    """True when pandas kept the whole header in one column (wrong sep or wrapping quotes)."""
    if df.shape[1] != 1:
        return False
    header = str(df.columns[0])
    if used_sep in header:
        return True
    others = [sep for sep in _SEPARATORS if sep != used_sep]
    return any(sep in header for sep in others)


def _strip_field_quotes(value: str) -> str:
    text = str(value).strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text.lstrip('"').rstrip('"')


def _clean_parsed_frame(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [_strip_field_quotes(col) for col in df.columns]
    if df.shape[1] == 0:
        return df
    first = df.columns[0]
    last = df.columns[-1]
    if df[first].dtype == object:
        df[first] = df[first].map(
            lambda v: v.lstrip('"') if isinstance(v, str) else v
        )
    if df.shape[1] > 1 and df[last].dtype == object:
        df[last] = df[last].map(
            lambda v: v.rstrip('"') if isinstance(v, str) else v
        )
    return df


def _read_with_options(
    path: Path,
    *,
    sep: str,
    encoding: str,
    nrows: Optional[int],
    na_values: Iterable[str],
    quoting: int,
    extra: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    kwargs: Dict[str, Any] = {
        "sep": sep,
        "encoding": encoding,
        "nrows": nrows,
        "na_values": list(na_values),
        "quoting": quoting,
    }
    if extra:
        kwargs.update(extra)
    return pd.read_csv(path, **kwargs)


def read_csv_auto(
    path: Path,
    nrows: Optional[int] = None,
    na_values: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Read a CSV with comma/semicolon/tab/pipe detection and quoted-row recovery."""
    na = list(na_values) if na_values is not None else NA_VALUES
    last_error: Optional[BaseException] = None
    path = Path(path)

    for encoding in _ENCODINGS:
        try:
            first = _peek_first_nonempty_line(path, encoding)
        except UnicodeDecodeError:
            continue
        if not first or "\x00" in first:
            continue

        guessed = guess_csv_separator(first)
        seps = [guessed] + [sep for sep in _SEPARATORS if sep != guessed]
        logger.debug(
            f"CSV {path.name}: encoding={encoding}, guessed sep={repr(guessed)}, "
            f"header={first[:120]!r}"
        )

        for sep in seps:
            quoting_attempts: List[tuple[int, Optional[Dict[str, Any]]]] = [
                (csv.QUOTE_MINIMAL, None),
                (csv.QUOTE_NONE, None),
                (csv.QUOTE_NONE, {"engine": "python"}),
            ]
            for quoting, extra in quoting_attempts:
                try:
                    df = _read_with_options(
                        path,
                        sep=sep,
                        encoding=encoding,
                        nrows=nrows,
                        na_values=na,
                        quoting=quoting,
                        extra=extra,
                    )
                except Exception as exc:  # noqa: BLE001 — try next encoding/sep
                    last_error = exc
                    continue
                if _header_looks_unsplit(df, sep):
                    last_error = ValueError(
                        f"Likely wrong separator {sep!r} for {path.name} "
                        f"(single column {df.columns[0]!r})"
                    )
                    continue
                cleaned = _clean_parsed_frame(df)
                logger.debug(
                    f"Loaded CSV {path.name} sep={sep!r} quoting={quoting} shape={cleaned.shape}"
                )
                return cleaned

    if last_error is not None:
        raise last_error
    raise ValueError(f"Could not parse CSV: {path}")
