"""Test schemas validation."""

import pandas as pd
import pytest
from pathlib import Path

from weekly_report.src.validate.schemas import (
    validate_qlik, validate_dema, validate_shopify, validate_other,
    QlikKpiSchema, DemaKpiSchema, ShopifyOrdersSchema
)


class TestSchemas:
    """Test schema validation functions."""
    
    def test_qlik_schema_valid(self):
        """Test Qlik schema with valid data."""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2025-01-01', '2025-01-02']),
            'metric': ['gross_sales', 'net_sales'],
            'value': [1000.0, 800.0],
            '_source_file': ['qlik_data.csv', 'qlik_data.csv'],
            '_source_type': ['qlik', 'qlik']
        })
        
        result = validate_qlik(df)
        assert result['valid'] is True
        assert len(result['errors']) == 0
    
    def test_qlik_schema_invalid(self):
        """Test Qlik schema with invalid data."""
        df = pd.DataFrame({
            'date': ['invalid_date', '2025-01-02'],
            'metric': ['gross_sales', 'net_sales'],
            'value': [1000.0, 800.0],
            '_source_file': ['qlik_data.csv', 'qlik_data.csv'],
            '_source_type': ['qlik', 'qlik']
        })
        
        result = validate_qlik(df)
        assert result['valid'] is False
        assert len(result['errors']) > 0
    
    def test_dema_schema_valid(self):
        """Test Dema schema with valid data."""
        df = pd.DataFrame({
            'week': ['2025-42', '2025-43'],
            'cos': [500.0, 600.0],
            'gross_sales': [1000.0, 1200.0],
            'net_sales': [800.0, 900.0],
            'returns': [50.0, 60.0],
            '_source_file': ['dema_data.csv', 'dema_data.csv'],
            '_source_type': ['dema', 'dema']
        })
        
        result = validate_dema(df)
        assert result['valid'] is True
        assert len(result['errors']) == 0
    
    def test_shopify_schema_valid(self):
        """Test Shopify schema with valid data."""
        df = pd.DataFrame({
            'order_id': ['ORD001', 'ORD002'],
            'created_at': pd.to_datetime(['2025-01-01 10:00:00', '2025-01-02 11:00:00']),
            'country': ['SE', 'NO'],
            'product_key': ['PROD001', 'PROD002'],
            'unit_price': [100.0, 150.0],
            'qty': [2, 1],
            'refund_amount': [0.0, 50.0],
            '_source_file': ['shopify_data.csv', 'shopify_data.csv'],
            '_source_type': ['shopify', 'shopify']
        })
        
        result = validate_shopify(df)
        assert result['valid'] is True
        assert len(result['errors']) == 0
    
    def test_other_schema_flexible(self):
        """Test other schema with flexible data."""
        df = pd.DataFrame({
            'any_column': ['value1', 'value2'],
            '_source_file': ['other_data.csv', 'other_data.csv'],
            '_source_type': ['other', 'other']
        })
        
        result = validate_other(df)
        assert result['valid'] is True
        assert len(result['errors']) == 0
    
    def test_empty_dataframe(self):
        """Test validation with empty DataFrame."""
        df = pd.DataFrame()
        
        result = validate_other(df, strict_mode=True)
        assert result['valid'] is False
        assert len(result['errors']) > 0
