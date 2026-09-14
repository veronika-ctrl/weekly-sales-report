"""CSV adapters for loading data from different sources."""

from pathlib import Path

import pandas as pd
from loguru import logger

from weekly_report.src.adapters.csv_util import NA_VALUES, read_csv_auto


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


def load_data(raw_data_path: Path) -> pd.DataFrame:
    """Load Qlik data from CSV/Excel files."""
    # Try week-specific path first (data/raw/{week}/qlik/)
    source_path = raw_data_path / "qlik"
    
    if not source_path.exists():
        # Fall back to old structure (data/raw/qlik/)
        fallback_path = raw_data_path.parent / "qlik"
        if fallback_path.exists():
            logger.info(f"Using fallback path: {fallback_path}")
            return load_csv_files(fallback_path, "qlik")
    
    return load_csv_files(source_path, "qlik")
