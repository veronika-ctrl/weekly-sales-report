"""Extract metadata from uploaded data files."""
from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

# Excel's 1900 leap-year bug: this origin matches pandas/openpyxl for modern dates.
_EXCEL_EPOCH = datetime(1899, 12, 30)

_DATE_COLUMN_MAP = {
    "qlik": "Date",
    "dema_spend": "Days",
    "dema_gm2": "Days",
    "shopify": "Day",
    "discounts": "Date",
}

# Qlik / Dema / Shopify exports mix Date, Day, and Days.
_DATE_NAME_ALIASES = {
    "date": ("date", "day", "days"),
    "day": ("day", "days", "date"),
    "days": ("days", "day", "date"),
}

_DIMENSION_RE = re.compile(
    rb'dimension[^>]*ref="(?:[A-Z]+)(\d+):(?:[A-Z]+)(\d+)"', re.IGNORECASE
)
_HEADER_CELL_RE = re.compile(
    rb'<c r="([A-Z]+)(\d+)"([^>]*)>(?:<v>([^<]*)</v>|<is><t[^>]*>([^<]*)</t></is>)</c>'
)
_SHARED_STRING_RE = re.compile(rb"<t[^>]*>([^<]*)</t>")


def _column_index_to_letter(idx: int) -> str:
    """Convert a 0-based column index to an Excel column letter."""
    n = idx + 1
    letters: List[str] = []
    while n:
        n, rem = divmod(n - 1, 26)
        letters.append(chr(65 + rem))
    return "".join(reversed(letters))


def _parse_excel_date_value(raw: str, cell_attrs: str) -> Optional[datetime]:
    attrs = cell_attrs.lower()
    if 't="s"' in attrs or "t='s'" in attrs:
        return None
    if 't="inlinestr"' in attrs or 't="str"' in attrs:
        parsed = pd.to_datetime(raw, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime().replace(tzinfo=None)

    try:
        serial = float(raw)
    except (TypeError, ValueError):
        parsed = pd.to_datetime(raw, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime().replace(tzinfo=None)

    # Shared-string indices and most numeric non-dates are far below Excel day serials.
    if serial < 20000 or serial > 80000:
        parsed = pd.to_datetime(raw, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime().replace(tzinfo=None)

    dt = _EXCEL_EPOCH + timedelta(days=serial)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _cell_date_re(col_letter: str) -> re.Pattern[bytes]:
    return re.compile(
        (
            rb'<c r="'
            + col_letter.encode("ascii")
            + rb'(\d+)"([^>]*)>(?:<v>([^<]*)</v>|<is><t[^>]*>([^<]*)</t></is>)</c>'
        )
    )


def _dates_from_sheet_chunk(chunk: bytes, col_letter: str) -> List[Tuple[int, datetime]]:
    found: List[Tuple[int, datetime]] = []
    for match in _cell_date_re(col_letter).finditer(chunk):
        row_num = int(match.group(1))
        if row_num <= 1:
            continue
        raw = (match.group(3) or match.group(4) or b"").decode("utf-8", errors="replace")
        parsed = _parse_excel_date_value(raw, match.group(2).decode("utf-8", errors="replace"))
        if parsed is not None:
            found.append((row_num, parsed))
    return found


def _first_worksheet_xml_name(zf: zipfile.ZipFile) -> str:
    sheets = [
        name
        for name in zf.namelist()
        if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
    ]
    if not sheets:
        raise FileNotFoundError("No worksheet XML found in xlsx")
    sheets.sort()
    return sheets[0]


def _shared_strings_prefix(zf: zipfile.ZipFile, limit: int = 256) -> List[str]:
    name = "xl/sharedStrings.xml"
    if name not in zf.namelist():
        return []
    strings: List[str] = []
    with zf.open(name) as handle:
        buf = b""
        while len(strings) < limit:
            chunk = handle.read(64 * 1024)
            if not chunk:
                break
            buf += chunk
            for match in _SHARED_STRING_RE.finditer(buf):
                strings.append(match.group(1).decode("utf-8", errors="replace"))
                if len(strings) >= limit:
                    break
            # Keep a small tail in case a <t> tag spans chunks.
            buf = buf[-128:]
    return strings


def _date_name_aliases(expected: Optional[str]) -> Tuple[str, ...]:
    if not expected:
        return ()
    return _DATE_NAME_ALIASES.get(expected.lower(), (expected.lower(),))


def _match_header_date_column(
    headers: Dict[str, str], expected: Optional[str]
) -> Tuple[Optional[str], Optional[str]]:
    wanted = set(_date_name_aliases(expected))
    if wanted:
        for letter, name in headers.items():
            if name.lower() in wanted:
                return letter, name
    for letter, name in headers.items():
        if name.lower() in {"date", "day", "days"}:
            return letter, name
    return None, None


def _match_csv_date_column(columns: List[str], expected: Optional[str]) -> Optional[str]:
    wanted = set(_date_name_aliases(expected))
    if not wanted:
        return None
    for col in columns:
        if str(col).strip().strip('"').strip("'").lower() in wanted:
            return col
    return None


def xlsx_header_names(file_path: Path) -> List[str]:
    """Header row from xlsx zip XML. Does not load the workbook into pandas."""
    with zipfile.ZipFile(file_path) as zf:
        sheet_name = _first_worksheet_xml_name(zf)
        shared_strings = _shared_strings_prefix(zf)
        with zf.open(sheet_name) as handle:
            first = handle.read(64 * 1024)
    headers = _header_columns(first, shared_strings)
    return [headers[letter] for letter in sorted(headers, key=lambda item: (len(item), item))]


def _header_columns(first_chunk: bytes, shared_strings: List[str]) -> Dict[str, str]:
    """Map Excel column letter -> header name for row 1."""
    headers: Dict[str, str] = {}
    for match in _HEADER_CELL_RE.finditer(first_chunk):
        if int(match.group(2)) != 1:
            continue
        letter = match.group(1).decode("ascii")
        attrs = match.group(3).decode("utf-8", errors="replace").lower()
        raw = (match.group(4) or match.group(5) or b"").decode("utf-8", errors="replace")
        if 't="s"' in attrs or "t='s'" in attrs:
            try:
                idx = int(float(raw))
                if 0 <= idx < len(shared_strings):
                    raw = shared_strings[idx]
            except ValueError:
                pass
        headers[letter] = raw.strip().strip('"').strip("'")
    return headers


def _xlsx_bounds(file_path: Path, expected_date_col: Optional[str]) -> Dict[str, Any]:
    """Row count + first/last date from xlsx zip XML. Never loads the workbook into pandas."""
    with zipfile.ZipFile(file_path) as zf:
        sheet_name = _first_worksheet_xml_name(zf)
        shared_strings = _shared_strings_prefix(zf)
        with zf.open(sheet_name) as handle:
            first = handle.read(64 * 1024)
            tail = first
            while True:
                chunk = handle.read(8 * 1024 * 1024)
                if not chunk:
                    break
                tail = (tail + chunk)[-512 * 1024 :]

    dim = _DIMENSION_RE.search(first)
    if dim:
        max_row = int(dim.group(2))
        row_count = max(0, max_row - 1)
    else:
        row_matches = list(re.finditer(rb'<row r="(\d+)"', tail))
        max_row = int(row_matches[-1].group(1)) if row_matches else 1
        row_count = max(0, max_row - 1)

    headers = _header_columns(first, shared_strings)
    date_letter, date_column_name = _match_header_date_column(headers, expected_date_col)
    if date_letter is None:
        date_letter = "A"

    dates = _dates_from_sheet_chunk(first, date_letter) + _dates_from_sheet_chunk(
        tail, date_letter
    )
    if not dates:
        return {
            "row_count": row_count,
            "date_column": date_column_name,
        }

    first_date = min(dt for _, dt in dates)
    last_date = max(dt for _, dt in dates)
    result: Dict[str, Any] = {
        "first_date": first_date.strftime("%Y-%m-%d"),
        "last_date": last_date.strftime("%Y-%m-%d"),
        "row_count": row_count,
    }
    if date_column_name:
        result["date_column"] = date_column_name
    return result


def _read_csv_sample(file_path: Path, nrows: Optional[int] = 10000) -> pd.DataFrame:
    """Read CSV without treating the wrong separator as success."""
    for sep in [";", ","]:
        for enc in ["utf-8", "latin-1"]:
            try:
                df = pd.read_csv(
                    file_path, sep=sep, encoding=enc, nrows=nrows, quotechar='"'
                )
                if len(df.columns) == 1:
                    header = str(df.columns[0])
                    if (sep == ";" and "," in header) or (sep == "," and ";" in header):
                        continue
                return df
            except Exception:
                continue
    return pd.read_csv(file_path, nrows=nrows, quotechar='"')


def _count_csv_data_rows(file_path: Path) -> int:
    for enc in ("utf-8", "latin-1"):
        try:
            with open(file_path, "r", encoding=enc) as handle:
                return max(0, sum(1 for _ in handle) - 1)
        except Exception:
            continue
    df = _read_csv_sample(file_path, nrows=None)
    return len(df)


def _csv_last_line(file_path: Path) -> str:
    with open(file_path, "rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - 65536))
        tail = handle.read().decode("utf-8", errors="replace")
    lines = [line for line in tail.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def extract_file_metadata(file_path: Path, file_type: str) -> Dict[str, Any]:
    """
    Extract first date, last date, and row count from data file.

    Returns dict with: first_date, last_date, row_count, date_column
    """
    file_path = Path(file_path)
    expected_date_col = _DATE_COLUMN_MAP.get(file_type)

    try:
        if file_path.suffix.lower() == ".xlsx":
            logger.info(f"Extracting xlsx metadata from zip XML: {file_path.name}")
            meta = _xlsx_bounds(file_path, expected_date_col)
            if expected_date_col and not meta.get("first_date"):
                meta["error"] = f"Expected date column '{expected_date_col}' not found"
            logger.info(
                f"xlsx metadata {file_path.name}: rows={meta.get('row_count')} "
                f"{meta.get('first_date')} → {meta.get('last_date')}"
            )
            return meta

        df = _read_csv_sample(file_path, nrows=5)
        df.columns = df.columns.str.strip('"').str.strip("'")
        logger.info(f"File {file_path.name} columns: {df.columns.tolist()}")

        row_count = _count_csv_data_rows(file_path)

        if not expected_date_col:
            return {"row_count": row_count}

        date_col = _match_csv_date_column(list(df.columns), expected_date_col)
        if not date_col:
            logger.warning(
                f"Column '{expected_date_col}' not found in {file_path.name}. "
                f"Available columns: {df.columns.tolist()}"
            )
            return {
                "error": f"Expected date column '{expected_date_col}' not found",
                "row_count": row_count,
            }
        date_idx = list(df.columns).index(date_col)

        sample = _read_csv_sample(file_path, nrows=10000)
        sample.columns = sample.columns.str.strip('"').str.strip("'")
        sample[date_col] = pd.to_datetime(sample[date_col], errors="coerce")
        valid = sample.dropna(subset=[date_col])
        if len(valid) == 0:
            return {"error": "No valid dates found in file", "row_count": row_count}

        first_date = valid[date_col].min()
        last_date = valid[date_col].max()

        last_line = _csv_last_line(file_path)
        if last_line:
            # Reconstruct a one-row frame with the same separator used in the sample.
            sep = ";" if last_line.count(";") >= last_line.count(",") else ","
            try:
                last_df = pd.read_csv(
                    io.StringIO(last_line),
                    sep=sep,
                    header=None,
                    quotechar='"',
                )
                if date_idx < len(last_df.columns):
                    last_parsed = pd.to_datetime(last_df.iloc[0, date_idx], errors="coerce")
                    if not pd.isna(last_parsed):
                        first_date = min(first_date, last_parsed)
                        last_date = max(last_date, last_parsed)
            except Exception:
                pass

        return {
            "first_date": pd.Timestamp(first_date).strftime("%Y-%m-%d"),
            "last_date": pd.Timestamp(last_date).strftime("%Y-%m-%d"),
            "row_count": row_count,
            "date_column": date_col,
        }

    except Exception as e:
        logger.error(f"Error extracting metadata from {file_path}: {e}")
        return {
            "error": str(e),
            "row_count": 0,
        }
