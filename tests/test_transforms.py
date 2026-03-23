"""Test transform functions."""

import pandas as pd
import pytest

from weekly_report.src.transform.kpis import transform_to_kpis
from weekly_report.src.transform.markets import transform_to_markets
from weekly_report.src.transform.products import transform_to_products


class TestTransforms:
    """Test transformation functions."""
    
    def test_transform_to_kpis(self):
        """Test KPI transformation."""
        data_sources = {
            'qlik': pd.DataFrame({
                'date': ['2025-01-01', '2025-01-02'],
                'metric': ['gross_sales', 'net_sales'],
                'value': [1000.0, 800.0],
                '_source_file': ['qlik_data.csv', 'qlik_data.csv'],
                '_source_type': ['qlik', 'qlik']
            }),
            'dema': pd.DataFrame({
                'week': ['2025-42'],
                'cos': [500.0],
                'gross_sales': [1000.0],
                'net_sales': [800.0],
                'returns': [50.0],
                '_source_file': ['dema_data.csv'],
                '_source_type': ['dema']
            }),
            'shopify': pd.DataFrame({
                'order_id': ['ORD001', 'ORD002'],
                'created_at': ['2025-01-01 10:00:00', '2025-01-02 11:00:00'],
                'country': ['SE', 'NO'],
                'product_key': ['PROD001', 'PROD002'],
                'unit_price': [100.0, 150.0],
                'qty': [2, 1],
                'refund_amount': [0.0, 50.0],
                '_source_file': ['shopify_data.csv', 'shopify_data.csv'],
                '_source_type': ['shopify', 'shopify']
            })
        }
        
        result = transform_to_kpis(data_sources, '2025-42')
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
        assert 'week' in result.columns
        assert 'metric' in result.columns
        assert 'value' in result.columns
        assert 'source' in result.columns
    
    def test_transform_to_markets(self):
        """Test market transformation."""
        data_sources = {
            'shopify': pd.DataFrame({
                'order_id': ['ORD001', 'ORD002', 'ORD003'],
                'created_at': ['2025-01-01 10:00:00', '2025-01-02 11:00:00', '2025-01-03 12:00:00'],
                'country': ['SE', 'NO', 'SE'],
                'product_key': ['PROD001', 'PROD002', 'PROD003'],
                'unit_price': [100.0, 150.0, 200.0],
                'qty': [2, 1, 3],
                'refund_amount': [0.0, 50.0, 0.0],
                '_source_file': ['shopify_data.csv', 'shopify_data.csv', 'shopify_data.csv'],
                '_source_type': ['shopify', 'shopify', 'shopify']
            })
        }
        
        result = transform_to_markets(data_sources, '2025-42')
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
        assert 'country' in result.columns
        assert 'revenue' in result.columns
        assert 'units' in result.columns
        assert 'orders' in result.columns
        assert 'week' in result.columns
        assert 'source' in result.columns
    
    def test_transform_to_products(self):
        """Test product transformation."""
        data_sources = {
            'shopify': pd.DataFrame({
                'order_id': ['ORD001', 'ORD002', 'ORD003'],
                'created_at': ['2025-01-01 10:00:00', '2025-01-02 11:00:00', '2025-01-03 12:00:00'],
                'country': ['SE', 'NO', 'SE'],
                'product_key': ['PROD001', 'PROD002', 'PROD001'],
                'unit_price': [100.0, 150.0, 200.0],
                'qty': [2, 1, 3],
                'refund_amount': [0.0, 50.0, 0.0],
                '_source_file': ['shopify_data.csv', 'shopify_data.csv', 'shopify_data.csv'],
                '_source_type': ['shopify', 'shopify', 'shopify']
            })
        }
        
        result = transform_to_products(data_sources, '2025-42')
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
        assert 'product_key' in result.columns
        assert 'revenue' in result.columns
        assert 'units' in result.columns
        assert 'orders' in result.columns
        assert 'week' in result.columns
        assert 'source' in result.columns
    
    def test_empty_data_sources(self):
        """Test transformation with empty data sources."""
        data_sources = {}
        
        result = transform_to_kpis(data_sources, '2025-42')
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

