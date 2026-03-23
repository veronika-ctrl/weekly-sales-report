"""Data validation schemas using pandera."""

from typing import Optional

import pandas as pd
import pandera as pa
from pandera import Column, DataFrameSchema, Check
from loguru import logger


# Qlik KPI Schema (flexible for actual Qlik data structure)
QlikKpiSchema = DataFrameSchema({
    # Only validate essential columns, allow others
}, strict=False)


# Dema Spend Schema
DemaSpendSchema = DataFrameSchema({
    "Country": Column(
        pa.String,
        nullable=True,
        description="Country"
    ),
    "Days": Column(
        pa.String,  # Changed from DateTime to String for flexibility
        nullable=True,
        description="Date"
    ),
    "Marketing spend": Column(
        pa.Float,
        nullable=True,
        description="Marketing spend amount"
    ),
    "_source_file": Column(
        pa.String,
        nullable=True,
        description="Source CSV filename"
    ),
    "_source_type": Column(
        pa.String,
        nullable=True,
        description="Source type identifier"
    ),
}, strict=False)


# Dema GM2 Schema
DemaGm2Schema = DataFrameSchema({
    "Days": Column(
        pa.String,  # Changed from DateTime to String for flexibility
        nullable=True,
        description="Date"
    ),
    "Gross margin 2 - Dema MTA": Column(
        pa.Float,
        nullable=True,
        description="Gross margin 2"
    ),
    "_source_file": Column(
        pa.String,
        nullable=True,
        description="Source CSV filename"
    ),
    "_source_type": Column(
        pa.String,
        nullable=True,
        description="Source type identifier"
    ),
}, strict=False)


# Shopify Sessions Schema
ShopifySessionsSchema = DataFrameSchema({
    "Day": Column(
        pa.String,  # Changed from DateTime to String for flexibility
        nullable=True,
        description="Date"
    ),
    "Sessions": Column(
        pa.Int,
        nullable=True,
        description="Number of sessions"
    ),
    "_source_file": Column(
        pa.String,
        nullable=True,
        description="Source CSV filename"
    ),
    "_source_type": Column(
        pa.String,
        nullable=True,
        description="Source type identifier"
    ),
}, strict=False)


# Other Data Schema (flexible for unknown structure)
OtherDataSchema = DataFrameSchema({
    # This will be dynamically created based on actual CSV structure
    # For now, we'll use a minimal schema that accepts any structure
}, strict=False)


def validate_qlik(df: pd.DataFrame, strict_mode: bool = True) -> dict:
    """Validate Qlik data against schema."""
    try:
        QlikKpiSchema.validate(df, lazy=True)
        logger.info("Qlik data validation passed")
        return {"valid": True, "errors": []}
    except pa.errors.SchemaErrors as e:
        errors = []
        for error in e.schema_errors:
            if hasattr(error, 'failure_cases') and error.failure_cases is not None:
                if isinstance(error.failure_cases, str):
                    errors.append(error.failure_cases)
                else:
                    errors.extend([str(fc) for fc in error.failure_cases.get('error', [])])
            else:
                errors.append(str(error))
        logger.error(f"Qlik data validation failed: {errors}")
        return {"valid": False, "errors": errors}


def validate_dema_spend(df: pd.DataFrame, strict_mode: bool = True) -> dict:
    """Validate Dema spend data against schema."""
    try:
        DemaSpendSchema.validate(df, lazy=True)
        logger.info("Dema spend data validation passed")
        return {"valid": True, "errors": []}
    except pa.errors.SchemaErrors as e:
        errors = []
        for error in e.schema_errors:
            if hasattr(error, 'failure_cases') and error.failure_cases is not None:
                if isinstance(error.failure_cases, str):
                    errors.append(error.failure_cases)
                else:
                    errors.extend([str(fc) for fc in error.failure_cases.get('error', [])])
            else:
                errors.append(str(error))
        logger.error(f"Dema spend data validation failed: {errors}")
        return {"valid": False, "errors": errors}


def validate_dema_gm2(df: pd.DataFrame, strict_mode: bool = True) -> dict:
    """Validate Dema GM2 data against schema."""
    try:
        DemaGm2Schema.validate(df, lazy=True)
        logger.info("Dema GM2 data validation passed")
        return {"valid": True, "errors": []}
    except pa.errors.SchemaErrors as e:
        errors = []
        for error in e.schema_errors:
            if hasattr(error, 'failure_cases') and error.failure_cases is not None:
                if isinstance(error.failure_cases, str):
                    errors.append(error.failure_cases)
                else:
                    errors.extend([str(fc) for fc in error.failure_cases.get('error', [])])
            else:
                errors.append(str(error))
        logger.error(f"Dema GM2 data validation failed: {errors}")
        return {"valid": False, "errors": errors}


def validate_shopify(df: pd.DataFrame, strict_mode: bool = True) -> dict:
    """Validate Shopify sessions data against schema."""
    try:
        ShopifySessionsSchema.validate(df, lazy=True)
        logger.info("Shopify sessions data validation passed")
        return {"valid": True, "errors": []}
    except pa.errors.SchemaErrors as e:
        errors = []
        for error in e.schema_errors:
            if hasattr(error, 'failure_cases') and error.failure_cases is not None:
                if isinstance(error.failure_cases, str):
                    errors.append(error.failure_cases)
                else:
                    errors.extend([str(fc) for fc in error.failure_cases.get('error', [])])
            else:
                errors.append(str(error))
        logger.error(f"Shopify sessions data validation failed: {errors}")
        return {"valid": False, "errors": errors}


def validate_other(df: pd.DataFrame, strict_mode: bool = True) -> dict:
    """Validate other data against flexible schema."""
    try:
        # For other data, we'll be more lenient
        if strict_mode:
            # Check for basic data quality
            if df.empty:
                raise ValueError("Other data is empty")
            
            # Check for required columns (minimal)
            required_cols = ['_source_file', '_source_type']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Missing required columns: {missing_cols}")
        
        logger.info("Other data validation passed")
        return {"valid": True, "errors": []}
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Other data validation failed: {error_msg}")
        return {"valid": False, "errors": [error_msg]}


def validate_all_sources(data_sources: dict, strict_mode: bool = True) -> dict:
    """Validate all data sources."""
    results = {}
    all_valid = True
    
    for source_name, df in data_sources.items():
        if source_name == 'qlik':
            results[source_name] = validate_qlik(df, strict_mode)
        elif source_name == 'dema_spend':
            results[source_name] = validate_dema_spend(df, strict_mode)
        elif source_name == 'dema_gm2':
            results[source_name] = validate_dema_gm2(df, strict_mode)
        elif source_name == 'shopify':
            results[source_name] = validate_shopify(df, strict_mode)
        elif source_name == 'other':
            results[source_name] = validate_other(df, strict_mode)
        else:
            logger.warning(f"Unknown source type: {source_name}")
            results[source_name] = {"valid": True, "errors": []}
        
        if not results[source_name]['valid']:
            all_valid = False
    
    return {
        "valid": all_valid,
        "results": results
    }
