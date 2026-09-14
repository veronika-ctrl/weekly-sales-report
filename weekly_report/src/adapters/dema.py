"""CSV adapters for loading Dema spend data."""

from pathlib import Path

import pandas as pd
from loguru import logger

from weekly_report.src.adapters.csv_util import NA_VALUES, read_csv_auto


def normalize_dema_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip headers and map Day -> Days (some weekly exports use singular Day)."""
    if df.empty:
        return df
    out = df.copy()
    out.columns = out.columns.astype(str).str.strip().str.strip('"')
    if "Days" not in out.columns and "Day" in out.columns:
        out = out.rename(columns={"Day": "Days"})
    return out


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
    
    # Fallback to CSV (slower)
    logger.info(f"No Parquet found, loading CSV files...")
    
    csv_files = list(source_path.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in {source_path}\n"
            f"Expected CSV files in: {source_path}/*.csv"
        )
    
    logger.info(f"Found {len(csv_files)} CSV files in {source_name}: {[f.name for f in csv_files]}")
    
    dataframes = []
    for csv_file in csv_files:
        try:
            df = read_csv_auto(csv_file, na_values=NA_VALUES)
            logger.debug(f"Loaded {csv_file.name}: {df.shape}")
            
            # Add source file metadata
            df['_source_file'] = csv_file.name
            df['_source_type'] = source_name
            
            dataframes.append(df)
            logger.debug(f"Loaded {csv_file.name}: {df.shape}")
            
        except Exception as e:
            logger.error(f"Failed to load {csv_file}: {e}")
            raise
    
    # Combine all dataframes
    if len(dataframes) == 1:
        combined_df = dataframes[0]
    else:
        combined_df = pd.concat(dataframes, ignore_index=True)

    combined_df = normalize_dema_columns(combined_df)
    
    logger.info(f"Combined {source_name} data: {combined_df.shape}")
    return combined_df


def load_data(raw_data_path: Path) -> pd.DataFrame:
    """Load Dema spend data from CSV files."""
    source_path = raw_data_path / "dema_spend"
    
    if not source_path.exists():
        # Fall back to old structure (data/raw/dema_spend/)
        fallback_path = raw_data_path.parent / "dema_spend"
        if fallback_path.exists():
            logger.info(f"Using fallback path: {fallback_path}")
            return load_csv_files(fallback_path, "dema_spend")
    
    return load_csv_files(source_path, "dema_spend")