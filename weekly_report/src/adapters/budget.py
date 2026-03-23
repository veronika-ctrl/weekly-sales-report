"""CSV adapter for loading budget data."""
import csv
import io
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
            # Detect dialect
            dialect = detect_csv_dialect(csv_file)
            
            # Load CSV
            df = pd.read_csv(
                csv_file,
                dialect=dialect,
                encoding='utf-8',
                na_values=['', 'NULL', 'null', 'N/A', 'n/a']
            )
            
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


def load_data(raw_data_path: Path, base_week: Optional[str] = None) -> pd.DataFrame:
    """
    Load Budget data, preferring Supabase storage (reused by year) over local files.
    
    Args:
        raw_data_path: Path to raw data directory (e.g., data/raw/2025-42)
        base_week: ISO week format (YYYY-WW) - used to extract year for Supabase lookup
    
    Returns:
        DataFrame with budget data
    """
    # Try Supabase first (if week is provided)
    if base_week:
        try:
            from weekly_report.src.adapters.supabase_client import get_supabase_client
            supabase = get_supabase_client()
            if supabase:
                # Extract year from week (ISO format: YYYY-WW)
                year = int(base_week.split("-")[0])
                
                # Query Supabase for budget file for this year
                result = supabase.table("budget_files").select("*").eq("year", year).limit(1).execute()
                
                if result.data and len(result.data) > 0:
                    budget_file = result.data[0]
                    content = budget_file["content"]
                    filename = budget_file.get("filename", "budget.csv")
                    
                    logger.info(f"📦 Loading budget file from Supabase (year {year}, uploaded week {budget_file.get('week', 'unknown')})")
                    
                    # Read CSV from string content
                    df = pd.read_csv(
                        io.StringIO(content),
                        na_values=['', 'NULL', 'null', 'N/A', 'n/a']
                    )
                    
                    # Add source metadata
                    df['_source_file'] = filename
                    df['_source_type'] = "budget"
                    df['_source_location'] = "supabase"
                    
                    logger.info(f"✅ Loaded budget from Supabase: {df.shape}")
                    return df
                else:
                    logger.info(f"No budget file found in Supabase for year {year}, falling back to local files")
        except Exception as e:
            logger.warning(f"Failed to load budget from Supabase (falling back to local): {e}")
    
    # Fallback to local files
    source_path = raw_data_path / "budget"
    
    if not source_path.exists():
        # Fall back to old structure (data/raw/budget/)
        fallback_path = raw_data_path.parent / "budget"
        if fallback_path.exists():
            logger.info(f"Using fallback path: {fallback_path}")
            return load_csv_files(fallback_path, "budget")
        else:
            raise FileNotFoundError(
                f"Budget data directory not found: {source_path}\n"
                f"Expected structure: {raw_data_path}/budget/\n"
                f"Fallback tried: {fallback_path}"
            )
    
    logger.info(f"📁 Loading budget file from local path: {source_path}")
    return load_csv_files(source_path, "budget")



