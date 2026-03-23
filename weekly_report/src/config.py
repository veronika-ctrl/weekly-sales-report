"""Configuration management for weekly report pipeline."""

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator


class Config(BaseModel):
    """Configuration model for the weekly report pipeline."""
    
    week: str = Field(..., description="ISO week format: YYYY-WW")
    data_root: Path = Field(default=Path("./data"), description="Root directory for data files")
    template_path: Path = Field(default=Path("./templates/pdf_layout.yaml"), description="PDF layout template")
    output_root: Path = Field(default=Path("./reports"), description="Output root directory")
    strict_mode: bool = Field(default=True, description="Stop on validation errors")
    log_level: str = Field(default="INFO", description="Logging level")
    chart_format: str = Field(default="png", description="Chart export format")
    pdf_width: int = Field(default=842, description="PDF page width in points")
    pdf_height: int = Field(default=595, description="PDF page height in points")
    
    @validator('week')
    def validate_week_format(cls, v):
        """Validate ISO week format."""
        if not v or len(v) != 7 or v[4] != '-':
            raise ValueError("Week must be in format YYYY-WW (e.g., 2025-42)")
        try:
            year, week = v.split('-')
            int(year)
            int(week)
            if not (1 <= int(week) <= 53):
                raise ValueError("Week must be between 1-53")
        except ValueError as e:
            raise ValueError(f"Invalid week format: {e}")
        return v
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate logging level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    @validator('chart_format')
    def validate_chart_format(cls, v):
        """Validate chart format."""
        valid_formats = ['png', 'svg']
        if v.lower() not in valid_formats:
            raise ValueError(f"Chart format must be one of: {valid_formats}")
        return v.lower()
    
    @property
    def raw_data_path(self) -> Path:
        """Path to raw data for the current week."""
        return self.data_root / "raw" / self.week
    
    @property
    def curated_data_path(self) -> Path:
        """Path to curated data for the current week."""
        return self.data_root / "curated" / self.week
    
    @property
    def charts_path(self) -> Path:
        """Path to charts for the current week."""
        return Path("./charts") / self.week
    
    @property
    def reports_path(self) -> Path:
        """Path to reports for the current week."""
        return self.output_root / self.week
    
    @property
    def manifest_path(self) -> Path:
        """Path to manifest file for the current week."""
        return self.reports_path / "manifest.json"


def load_config(week: Optional[str] = None, config_file: Optional[Path] = None) -> Config:
    """Load configuration from environment and optional config file."""
    
    # Load environment variables
    load_dotenv()
    
    # Get week from parameter or environment
    week = week or os.getenv("DEFAULT_WEEK", "2025-42")
    
    # Create config from environment variables
    config_data = {
        "week": week,
        "data_root": Path(os.getenv("DATA_ROOT", "./data")),
        "template_path": Path(os.getenv("TEMPLATE_PATH", "./templates/pdf_layout.yaml")),
        "output_root": Path(os.getenv("OUTPUT_ROOT", "./reports")),
        "strict_mode": os.getenv("STRICT_MODE", "true").lower() == "true",
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "chart_format": os.getenv("CHART_FORMAT", "png"),
        "pdf_width": int(os.getenv("PDF_WIDTH", "842")),
        "pdf_height": int(os.getenv("PDF_HEIGHT", "595")),
    }
    
    # Load additional config from YAML file if provided
    if config_file and config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f)
            config_data.update(yaml_config)
    
    return Config(**config_data)

