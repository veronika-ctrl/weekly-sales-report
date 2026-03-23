"""CSV adapters for loading Dema GM2 data."""

import csv
from pathlib import Path
from typing import List, Optional

import pandas as pd
from loguru import logger


def detect_csv_dialect(file_path: Path) -> csv.Dialect:
    """Detect CSV dialect from file content."""
    with open(file_path, 'r', encoding='utf-8') as f:
        sample = f.read(1024)
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample)
        logger.debug(f"Detected CSV dialect for {file_path.name}: delimiter='{dialect.delimiter}', quotechar='{dialect.quotechar}'")
        return dialect


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
            # Try semicolon separator first (common in European CSV files)
            try:
                df = pd.read_csv(
                    csv_file,
                    sep=';',
                    encoding='utf-8',
                    na_values=['', 'NULL', 'null', 'N/A', 'n/a']
                )
                logger.debug(f"Loaded {csv_file.name} with semicolon separator: {df.shape}")
            except Exception:
                # Fallback to auto-detection
                dialect = detect_csv_dialect(csv_file)
                df = pd.read_csv(
                    csv_file,
                    dialect=dialect,
                    encoding='utf-8',
                    na_values=['', 'NULL', 'null', 'N/A', 'n/a']
                )
                logger.debug(f"Loaded {csv_file.name} with auto-detected separator: {df.shape}")
            
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
    """Load Dema GM2 data from CSV files."""
    source_path = raw_data_path / "dema_gm2"
    
    if not source_path.exists():
        # Fall back to old structure (data/raw/dema_gm2/)
        fallback_path = raw_data_path.parent / "dema_gm2"
        if fallback_path.exists():
            logger.info(f"Using fallback path: {fallback_path}")
            return load_csv_files(fallback_path, "dema_gm2")
    
    return load_csv_files(source_path, "dema_gm2")
