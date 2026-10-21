"""CSV adapters for loading data from different sources."""

import gc
import hashlib
import struct
import threading
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import pandas as pd
from loguru import logger

from weekly_report.src.adapters.csv_util import NA_VALUES, read_csv_auto
from weekly_report.src.cache.manager import raw_data_cache

# One projected read at a time. A second full export beside a cached week
# is what restarted the 2GB Render instance.
_qlik_read_lock = threading.Lock()

# Columns the category and gender slides aggregate. Reading just these avoids
# loading Dema, Shopify, and the rest of the Qlik export into memory.
CATEGORY_QLIK_COLUMNS: Sequence[str] = (
    "Date",
    "Sales Channel",
    "Gender",
    "Product Category",
    "Gross Revenue",
)


def load_csv_files(source_path: Path, source_name: str) -> pd.DataFrame:
    """Load all CSV files from a source directory (with Parquet optimization)."""
    if not source_path.exists():
        raise FileNotFoundError(
            f"{source_name} data directory not found: {source_path}\n"
            f"Expected structure: data/raw/{{WEEK}}/{source_name}/\n"
            f"Please place your CSV files in: {source_path}"
        )
    
    # OPTIMIZATION: Try Parquet first (10-100x faster)
    parquet_files = list(source_path.glob("**/*.parquet"))
    if parquet_files:
        logger.info(f"Loading Parquet file: {parquet_files[0].name}")
        df = pd.read_parquet(parquet_files[0])
        logger.debug(f"Loaded Parquet {parquet_files[0].name}: {df.shape}")
        return df
    
    # Fallback to Excel/CSV (slower)
    logger.info(f"No Parquet found, loading Excel/CSV files...")
    
    # Look for CSV and Excel files
    csv_files = list(source_path.glob("*.csv")) + list(source_path.glob("*.xlsx"))
    if not csv_files:
        raise FileNotFoundError(
            f"No CSV/Excel files found in {source_path}\n"
            f"Expected CSV/Excel files in: {source_path}/*.csv or {source_path}/*.xlsx"
        )
    
    logger.info(f"Found {len(csv_files)} files in {source_name}: {[f.name for f in csv_files]}")
    
    dataframes = []
    for file_path in csv_files:
        try:
            if file_path.suffix.lower() == '.xlsx':
                # Load Excel file
                df = pd.read_excel(file_path, na_values=NA_VALUES)
                logger.debug(f"Loaded Excel {file_path.name}: {df.shape}")
            else:
                df = read_csv_auto(file_path, na_values=NA_VALUES)
                logger.debug(f"Loaded CSV {file_path.name}: {df.shape}")
            
            # Add source file metadata
            df['_source_file'] = file_path.name
            df['_source_type'] = source_name
            
            dataframes.append(df)
            
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            raise
    
    # Combine all dataframes
    if len(dataframes) == 1:
        combined_df = dataframes[0]
    else:
        combined_df = pd.concat(dataframes, ignore_index=True)
    
    logger.info(f"Combined {source_name} data: {combined_df.shape}")
    return combined_df


def _resolve_qlik_dir(raw_data_path: Path) -> Path:
    """Week folder qlik/ first, then the legacy data/raw/qlik/ layout."""
    source_path = raw_data_path / "qlik"
    if source_path.exists():
        return source_path
    fallback_path = raw_data_path.parent / "qlik"
    if fallback_path.exists():
        logger.info(f"Using fallback path: {fallback_path}")
        return fallback_path
    return source_path


def load_data(raw_data_path: Path) -> pd.DataFrame:
    """Load Qlik data from CSV/Excel files."""
    return load_csv_files(_resolve_qlik_dir(raw_data_path), "qlik")


def _read_varint(buf: bytes, index: int) -> Tuple[int, int]:
    shift = 0
    result = 0
    while index < len(buf) and shift <= 63:
        byte = buf[index]
        index += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, index
        shift += 7
    raise ValueError("truncated parquet footer varint")


def _read_zigzag(buf: bytes, index: int) -> Tuple[int, int]:
    value, index = _read_varint(buf, index)
    return (value >> 1) ^ -(value & 1), index


def _read_list_header(buf: bytes, index: int) -> Tuple[int, int, int]:
    byte = buf[index]
    index += 1
    element_type = byte & 0x0F
    size = byte >> 4
    if size == 15:
        size, index = _read_varint(buf, index)
    return element_type, size, index


def _skip_value(buf: bytes, index: int, field_type: int) -> int:
    """Skip one Thrift compact value. Used only to walk a parquet footer."""
    if field_type in (1, 2):
        return index
    if field_type in (3, 4, 5, 6):
        _, index = _read_varint(buf, index)
        return index
    if field_type == 7:
        return index + 8
    if field_type == 8:
        length, index = _read_varint(buf, index)
        return index + length
    if field_type in (9, 10):
        element_type, size, index = _read_list_header(buf, index)
        for _ in range(size):
            index = _skip_value(buf, index, element_type)
        return index
    if field_type == 11:
        byte = buf[index]
        index += 1
        key_type = byte & 0x0F
        value_type = byte >> 4
        size, index = _read_varint(buf, index)
        for _ in range(size):
            index = _skip_value(buf, index, key_type)
            index = _skip_value(buf, index, value_type)
        return index
    if field_type == 12:
        return _skip_struct(buf, index)
    raise ValueError(f"unsupported parquet footer type {field_type}")


def _skip_struct(buf: bytes, index: int) -> int:
    last_id = 0
    while index < len(buf):
        byte = buf[index]
        index += 1
        field_type = byte & 0x0F
        delta = byte >> 4
        if field_type == 0:
            return index
        if delta == 0:
            field_id, index = _read_zigzag(buf, index)
        else:
            field_id = last_id + delta
        last_id = field_id
        index = _skip_value(buf, index, field_type)
    raise ValueError("truncated parquet footer struct")


def _schema_element(buf: bytes, index: int) -> Tuple[Optional[str], Optional[int], int]:
    """One parquet SchemaElement: name, num_children, and the next offset."""
    last_id = 0
    name: Optional[str] = None
    num_children: Optional[int] = None
    while index < len(buf):
        byte = buf[index]
        index += 1
        field_type = byte & 0x0F
        delta = byte >> 4
        if field_type == 0:
            return name, num_children, index
        if delta == 0:
            field_id, index = _read_zigzag(buf, index)
        else:
            field_id = last_id + delta
        last_id = field_id
        if field_id == 4 and field_type == 8:
            length, index = _read_varint(buf, index)
            name = buf[index : index + length].decode("utf-8", errors="replace")
            index += length
        elif field_id == 5 and field_type in (3, 4, 5, 6):
            num_children, index = _read_zigzag(buf, index)
        else:
            index = _skip_value(buf, index, field_type)
    raise ValueError("truncated parquet schema element")


def _schema_names_from_footer(footer: bytes) -> Optional[List[str]]:
    """Leaf column names from a parquet FileMetaData footer."""
    index = 0
    last_id = 0
    while index < len(footer):
        byte = footer[index]
        index += 1
        field_type = byte & 0x0F
        delta = byte >> 4
        if field_type == 0:
            return None
        if delta == 0:
            field_id, index = _read_zigzag(footer, index)
        else:
            field_id = last_id + delta
        last_id = field_id
        if field_id == 2 and field_type in (9, 10):
            element_type, size, index = _read_list_header(footer, index)
            if element_type != 12:
                return None
            leaves: List[str] = []
            for _ in range(size):
                name, num_children, index = _schema_element(footer, index)
                if name and not num_children:
                    leaves.append(name)
            return leaves
        index = _skip_value(footer, index, field_type)
        if field_id > 2:
            return None
    return None


def _parquet_footer_column_names(path: Path) -> Optional[List[str]]:
    """Column names from the parquet footer. Does not import pyarrow or numpy."""
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            if size < 12:
                return None
            handle.seek(-8, 2)
            footer_len, magic = struct.unpack("<I4s", handle.read(8))
            if magic != b"PAR1" or footer_len <= 0 or footer_len + 8 > size:
                return None
            handle.seek(-(8 + footer_len), 2)
            footer = handle.read(footer_len)
        return _schema_names_from_footer(footer)
    except Exception as exc:
        logger.debug(f"Parquet footer schema unread for {path.name}: {exc}")
        return None


def _parquet_column_names(path: Path) -> Optional[List[str]]:
    """Column names without reading row groups.

    pyarrow's schema API needs a working pyarrow build. When that import fails
    (numpy 2 mismatch, or pyarrow not installed) the footer is parsed directly
    so projection can still be requested from whichever engine can read data.
    """
    try:
        import pyarrow.parquet as pq

        return [str(name) for name in pq.ParquetFile(path).schema_arrow.names]
    except Exception:
        pass
    try:
        from fastparquet import ParquetFile

        return [str(name) for name in ParquetFile(str(path)).columns]
    except Exception:
        pass
    return _parquet_footer_column_names(path)


def _header_keep(columns: Sequence[str]):
    """usecols callback: keep only the headers this report aggregates."""
    wanted = {str(col).strip() for col in columns}

    def keep(name: object) -> bool:
        return str(name).strip() in wanted

    return keep


def _read_csv_columns(path: Path, columns: Sequence[str]) -> pd.DataFrame:
    """Read a CSV without pulling the unused Qlik columns into memory."""
    keep = _header_keep(columns)
    last_error: Optional[BaseException] = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        for sep in (",", ";", "\t", "|"):
            try:
                frame = pd.read_csv(
                    path,
                    sep=sep,
                    encoding=encoding,
                    usecols=keep,
                    na_values=NA_VALUES,
                    low_memory=False,
                )
            except Exception as exc:
                last_error = exc
                continue
            frame.columns = [str(col).strip() for col in frame.columns]
            if frame.shape[1] == 0:
                continue
            return frame
    logger.warning(f"Column CSV read failed for {path.name} ({last_error}); reading full file")
    wide = read_csv_auto(path, na_values=NA_VALUES)
    return _take_columns(wide, columns)


def _read_excel_columns(path: Path, columns: Sequence[str]) -> pd.DataFrame:
    """Read an Excel export by column.

    The live week file is a ~100MB xlsx. openpyxl on the whole workbook takes
    long enough that Cloudflare drops the browser connection. calamine reads
    the same sheet in seconds; openpyxl remains the fallback.
    """
    keep = _header_keep(columns)
    last_error: Optional[BaseException] = None
    for engine in ("calamine", "openpyxl"):
        try:
            frame = pd.read_excel(path, engine=engine, usecols=keep, na_values=NA_VALUES)
        except Exception as exc:
            last_error = exc
            continue
        frame.columns = [str(col).strip() for col in frame.columns]
        if frame.shape[1] == 0:
            continue
        logger.info(f"Loaded Excel columns from {path.name} via {engine}: {frame.shape}")
        return frame
    logger.warning(
        f"Column Excel read failed for {path.name} ({last_error}); reading full sheet and dropping unused columns"
    )
    wide = pd.read_excel(path, na_values=NA_VALUES)
    slim = _take_columns(wide, columns)
    del wide
    gc.collect()
    return slim


def _take_columns(frame: pd.DataFrame, wanted: Sequence[str]) -> pd.DataFrame:
    """Own a copy of the requested columns. Caller must drop the wide frame."""
    frame.columns = [str(col).strip() for col in frame.columns]
    keep = [col for col in wanted if col in frame.columns]
    if not keep:
        return frame
    return frame.loc[:, keep].copy()


def _read_parquet_columns(path: Path, columns: Sequence[str]) -> pd.DataFrame:
    """Read a parquet file, projecting to the requested columns when possible.

    If the engine cannot project, the full file is read and unused columns are
    dropped before any other work. The wide frame is not returned.
    """
    wanted = [str(col).strip() for col in columns]
    names = _parquet_column_names(path)
    selected: Optional[List[str]] = None
    if names is not None:
        by_name = {str(name).strip(): name for name in names}
        selected = [by_name[col] for col in wanted if col in by_name]
        if not selected:
            raise ValueError(f"None of {wanted} found in {path.name}")
    try:
        projected = pd.read_parquet(path, columns=selected or wanted)
    except Exception as exc:
        logger.warning(
            f"Column projection failed for {path.name} ({exc}); reading full file and dropping unused columns"
        )
        wide = pd.read_parquet(path)
        slim = _take_columns(wide, wanted)
        del wide
        gc.collect()
        return slim
    projected.columns = [str(col).strip() for col in projected.columns]
    keep = [col for col in wanted if col in projected.columns]
    if keep and list(projected.columns) != keep:
        slim = _take_columns(projected, wanted)
        del projected
        gc.collect()
        return slim
    return projected


def _attach_iso_week(frame: pd.DataFrame) -> pd.DataFrame:
    """Same ISO-week column load_all_raw_data adds before metrics run.

    Adds the column on the frame that was already narrowed. Does not copy the
    wide export.
    """
    if frame.empty or "iso_week" in frame.columns or "Date" not in frame.columns:
        return frame
    dates = pd.to_datetime(frame["Date"], errors="coerce")
    iso_cal = dates.dt.isocalendar()
    frame["Date"] = dates
    frame["iso_week"] = iso_cal["year"].astype(str) + "-" + iso_cal["week"].astype(str).str.zfill(2)
    return frame


def load_qlik_columns(raw_data_path: Path, columns: Sequence[str]) -> pd.DataFrame:
    """Load selected Qlik columns for one week folder.

    Parquet reads only those columns. CSV and Excel fall back to a full read,
    then immediately drop the rest. Does not load Dema or Shopify. Drops any
    cached full raw week first so this read does not sit beside it.
    """
    with _qlik_read_lock:
        raw_data_cache.clear()
        gc.collect()
        source = _resolve_qlik_dir(raw_data_path)
        parquet_files = list(source.glob("**/*.parquet"))
        if parquet_files:
            path = parquet_files[0]
            logger.info(f"Loading Qlik columns from Parquet {path.name}: {list(columns)}")
            frame = _read_parquet_columns(path, columns)
        else:
            files = list(source.glob("*.csv")) + list(source.glob("*.xlsx"))
            if not files:
                raise FileNotFoundError(
                    f"No CSV/Excel files found in {source}\n"
                    f"Expected CSV/Excel files in: {source}/*.csv or {source}/*.xlsx"
                )
            frames = [
                _read_excel_columns(path, columns)
                if path.suffix.lower() == ".xlsx"
                else _read_csv_columns(path, columns)
                for path in files
            ]
            frame = frames[0] if len(frames) == 1 else pd.concat(frames, ignore_index=True)
        return _attach_iso_week(frame)


def load_category_qlik(raw_data_path: Path) -> pd.DataFrame:
    """Qlik slice used by the gender and category sales slides."""
    return load_qlik_columns(raw_data_path, CATEGORY_QLIK_COLUMNS)


def qlik_source_files(raw_data_path: Path) -> List[Path]:
    """Files load_qlik_columns would read. Raises FileNotFoundError when none exist."""
    source = _resolve_qlik_dir(raw_data_path)
    if not source.exists():
        raise FileNotFoundError(f"Qlik data directory not found: {source}")
    parquet_files = list(source.glob("**/*.parquet"))
    if parquet_files:
        return [parquet_files[0]]
    files = list(source.glob("*.csv")) + list(source.glob("*.xlsx"))
    if not files:
        raise FileNotFoundError(f"No CSV/Excel files found in {source}")
    return files


def qlik_source_signature(raw_data_path: Path) -> str:
    """Changes when the Qlik file that this week folder reads is replaced."""
    parts = []
    for path in qlik_source_files(raw_data_path):
        stat = path.stat()
        parts.append(f"{path.name}:{stat.st_size}:{getattr(stat, 'st_mtime_ns', int(stat.st_mtime * 1e9))}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]
