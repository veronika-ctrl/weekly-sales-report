"""Storage and I/O utilities."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import pandas as pd
from loguru import logger

from weekly_report.src.config import Config


def write_manifest(
    curated_data: Dict[str, pd.DataFrame],
    chart_files: Dict[str, Path],
    pdf_files: Dict[str, Path],
    config: Config
) -> Path:
    """Write manifest file with metadata and checksums."""
    
    manifest = {
        'generated_at': datetime.now().isoformat(),
        'week': config.week,
        'config': {
            'data_root': str(config.data_root),
            'output_root': str(config.output_root),
            'strict_mode': config.strict_mode,
            'chart_format': config.chart_format,
            'pdf_width': config.pdf_width,
            'pdf_height': config.pdf_height
        },
        'data_sources': {},
        'curated_files': {},
        'chart_files': {},
        'pdf_files': {},
        'summary': {
            'total_curated_records': 0,
            'total_chart_files': len(chart_files),
            'total_pdf_files': len(pdf_files)
        }
    }
    
    # Add curated data metadata
    for name, df in curated_data.items():
        if isinstance(df, pd.DataFrame):
            manifest['curated_files'][name] = {
                'rows': len(df),
                'columns': len(df.columns),
                'columns_list': df.columns.tolist(),
                'file_path': str(config.curated_data_path / f"{name}.csv")
            }
            manifest['summary']['total_curated_records'] += len(df)
    
    # Add chart files metadata
    for name, file_path in chart_files.items():
        if file_path.exists():
            file_hash = calculate_file_hash(file_path)
            file_size = file_path.stat().st_size
            
            manifest['chart_files'][name] = {
                'file_path': str(file_path),
                'file_size': file_size,
                'sha256': file_hash,
                'created_at': datetime.fromtimestamp(file_path.stat().st_ctime).isoformat()
            }
    
    # Add PDF files metadata
    for name, file_path in pdf_files.items():
        if file_path.exists():
            file_hash = calculate_file_hash(file_path)
            file_size = file_path.stat().st_size
            
            manifest['pdf_files'][name] = {
                'file_path': str(file_path),
                'file_size': file_size,
                'sha256': file_hash,
                'created_at': datetime.fromtimestamp(file_path.stat().st_ctime).isoformat()
            }
    
    # Write manifest file
    manifest_path = config.manifest_path
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Written manifest: {manifest_path}")
    return manifest_path


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    
    hash_sha256 = hashlib.sha256()
    
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logger.error(f"Failed to calculate hash for {file_path}: {e}")
        return ""


def load_manifest(manifest_path: Path) -> Dict[str, Any]:
    """Load manifest file."""
    
    if not manifest_path.exists():
        logger.warning(f"Manifest file not found: {manifest_path}")
        return {}
    
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        logger.info(f"Loaded manifest from {manifest_path}")
        return manifest
        
    except Exception as e:
        logger.error(f"Failed to load manifest: {e}")
        return {}


def verify_manifest(manifest_path: Path) -> bool:
    """Verify manifest file integrity."""
    
    manifest = load_manifest(manifest_path)
    
    if not manifest:
        return False
    
    # Verify chart files
    for name, file_info in manifest.get('chart_files', {}).items():
        file_path = Path(file_info['file_path'])
        
        if not file_path.exists():
            logger.warning(f"Chart file missing: {file_path}")
            return False
        
        # Verify file size
        if file_path.stat().st_size != file_info['file_size']:
            logger.warning(f"Chart file size mismatch: {file_path}")
            return False
        
        # Verify hash
        current_hash = calculate_file_hash(file_path)
        if current_hash != file_info['sha256']:
            logger.warning(f"Chart file hash mismatch: {file_path}")
            return False
    
    # Verify PDF files
    for name, file_info in manifest.get('pdf_files', {}).items():
        file_path = Path(file_info['file_path'])
        
        if not file_path.exists():
            logger.warning(f"PDF file missing: {file_path}")
            return False
        
        # Verify file size
        if file_path.stat().st_size != file_info['file_size']:
            logger.warning(f"PDF file size mismatch: {file_path}")
            return False
        
        # Verify hash
        current_hash = calculate_file_hash(file_path)
        if current_hash != file_info['sha256']:
            logger.warning(f"PDF file hash mismatch: {file_path}")
            return False
    
    logger.info("Manifest verification passed")
    return True

