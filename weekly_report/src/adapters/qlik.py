"""CSV adapters for loading data from different sources."""

import hashlib
from pathlib import Path
from typing import List, Optional, Sequence

import pandas as pd
from loguru import logger

from weekly_report.src.adapters.csv_util import NA_VALUES, read_csv_auto

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


def _parquet_column_names(path: Path) -> Optional[List[str]]:
    """Column names from parquet metadata, without reading the row groups."""
    try:
        import pyarrow.parquet as pq

        return [str(name) for name in pq.ParquetFile(path).schema_arrow.names]
    except Exception:
        pass
    try:
        from fastparquet import ParquetFile

        return [str(name) for name in ParquetFile(str(path)).columns]
    except Exception:
        return None


def _read_parquet_columns(path: Path, columns: Sequence[str]) -> pd.DataFrame:
    """Read a parquet file, projecting to the requested columns when possible."""
    wanted = [str(col).strip() for col in columns]
    names = _parquet_column_names(path)
    if names is None:
        try:
            frame = pd.read_parquet(path, columns=wanted)
        except Exception as exc:
            logger.warning(f"Column projection failed for {path.name} ({exc}); reading full file")
            frame = pd.read_parquet(path)
    else:
        by_name = {str(name).strip(): name for name in names}
        selected = [by_name[col] for col in wanted if col in by_name]
        if not selected:
            raise ValueError(f"None of {wanted} found in {path.name}")
        frame = pd.read_parquet(path, columns=selected)
    frame.columns = [str(col).strip() for col in frame.columns]
    keep = [col for col in wanted if col in frame.columns]
    if keep:
        return frame.loc[:, keep]
    return frame


def _attach_iso_week(frame: pd.DataFrame) -> pd.DataFrame:
    """Same ISO-week column load_all_raw_data adds before metrics run."""
    if frame.empty or "iso_week" in frame.columns or "Date" not in frame.columns:
        return frame
    out = frame.copy()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    iso_cal = out["Date"].dt.isocalendar()
    out["iso_week"] = iso_cal["year"].astype(str) + "-" + iso_cal["week"].astype(str).str.zfill(2)
    return out


def load_qlik_columns(raw_data_path: Path, columns: Sequence[str]) -> pd.DataFrame:
    """Load selected Qlik columns for one week folder.

    Parquet reads only those columns. CSV and Excel fall back to a full read
    and then drop the rest. Does not load Dema or Shopify and does not touch
    the shared raw-data cache.
    """
    source = _resolve_qlik_dir(raw_data_path)
    parquet_files = list(source.glob("**/*.parquet"))
    if parquet_files:
        path = parquet_files[0]
        logger.info(f"Loading Qlik columns from Parquet {path.name}: {list(columns)}")
        frame = _read_parquet_columns(path, columns)
    else:
        frame = load_csv_files(source, "qlik")
        frame.columns = [str(col).strip() for col in frame.columns]
        keep = [col for col in columns if col in frame.columns]
        if keep:
            frame = frame.loc[:, keep].copy()
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
