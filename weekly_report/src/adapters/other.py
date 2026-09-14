"""CSV adapters for loading data from different sources."""

from pathlib import Path

import pandas as pd
from loguru import logger

from weekly_report.src.adapters.csv_util import NA_VALUES, read_csv_auto


def load_csv_files(source_path: Path, source_name: str) -> pd.DataFrame:
    """Load all CSV files from a source directory."""
    if not source_path.exists():
        raise FileNotFoundError(
            f"{source_name} data directory not found: {source_path}\n"
            f"Expected structure: data/raw/{{WEEK}}/{source_name}/\n"
            f"Please place your CSV files in: {source_path}"
        )
    
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
    
    logger.info(f"Combined {source_name} data: {combined_df.shape}")
    return combined_df


def load_data(raw_data_path: Path) -> pd.DataFrame:
    """Load other data from CSV files."""
    source_path = raw_data_path / "other"
    return load_csv_files(source_path, "other")
