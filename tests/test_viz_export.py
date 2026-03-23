"""Test visualization export functions."""

import pandas as pd
import pytest
from pathlib import Path
import tempfile
import os

from weekly_report.src.viz.charts import trend_sales, bar_yoy_wow, waterfall_contrib
from weekly_report.src.viz.tables import kpi_table, market_table


class TestVizExport:
    """Test visualization export functions."""
    
    def test_trend_sales_export(self):
        """Test trend sales chart export."""
        # Create test data
        kpi_data = pd.DataFrame({
            'week': ['2025-42', '2025-43'],
            'metric': ['gross_sales', 'net_sales'],
            'value': [1000.0, 800.0],
            'source': ['qlik', 'qlik']
        })
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            
            # Generate chart
            result_path = trend_sales(kpi_data, output_path)
            
            # Verify file was created
            assert result_path.exists()
            assert result_path.suffix == '.png'
            assert result_path.stat().st_size > 0
    
    def test_bar_yoy_wow_export(self):
        """Test YoY/WoW bar chart export."""
        # Create test data
        market_data = pd.DataFrame({
            'country': ['SE', 'NO', 'DK'],
            'revenue': [1000.0, 800.0, 600.0],
            'units': [100, 80, 60],
            'orders': [50, 40, 30],
            'refunds': [50.0, 40.0, 30.0],
            'yoy_growth_pct': [10.0, 5.0, -2.0],
            'wow_growth_pct': [2.0, 1.0, -1.0],
            'week': ['2025-42', '2025-42', '2025-42'],
            'source': ['shopify', 'shopify', 'shopify']
        })
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            
            # Generate chart
            result_path = bar_yoy_wow(market_data, output_path)
            
            # Verify file was created
            assert result_path.exists()
            assert result_path.suffix == '.png'
            assert result_path.stat().st_size > 0
    
    def test_waterfall_contrib_export(self):
        """Test waterfall contribution chart export."""
        # Create test data
        kpi_data = pd.DataFrame({
            'week': ['2025-42', '2025-42', '2025-42', '2025-42'],
            'metric': ['gross_sales', 'cost_of_sales', 'returns', 'net_sales'],
            'value': [1000.0, 500.0, 50.0, 450.0],
            'source': ['dema', 'dema', 'dema', 'dema']
        })
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            
            # Generate chart
            result_path = waterfall_contrib(kpi_data, output_path)
            
            # Verify file was created
            assert result_path.exists()
            assert result_path.suffix == '.png'
            assert result_path.stat().st_size > 0
    
    def test_kpi_table_export(self):
        """Test KPI table export."""
        # Create test data
        kpi_data = pd.DataFrame({
            'week': ['2025-42', '2025-42', '2025-42'],
            'metric': ['gross_sales', 'net_sales', 'cost_of_sales'],
            'value': [1000.0, 800.0, 500.0],
            'source': ['dema', 'dema', 'dema']
        })
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            
            # Generate table
            result_path = kpi_table(kpi_data, output_path)
            
            # Verify file was created
            assert result_path.exists()
            assert result_path.suffix == '.png'
            assert result_path.stat().st_size > 0
    
    def test_market_table_export(self):
        """Test market table export."""
        # Create test data
        market_data = pd.DataFrame({
            'country': ['SE', 'NO', 'DK'],
            'revenue': [1000.0, 800.0, 600.0],
            'units': [100, 80, 60],
            'orders': [50, 40, 30],
            'refunds': [50.0, 40.0, 30.0],
            'yoy_growth_pct': [10.0, 5.0, -2.0],
            'wow_growth_pct': [2.0, 1.0, -1.0],
            'week': ['2025-42', '2025-42', '2025-42'],
            'source': ['shopify', 'shopify', 'shopify']
        })
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            
            # Generate table
            result_path = market_table(market_data, output_path)
            
            # Verify file was created
            assert result_path.exists()
            assert result_path.suffix == '.png'
            assert result_path.stat().st_size > 0
    
    def test_empty_data_handling(self):
        """Test handling of empty data."""
        # Create empty DataFrame
        empty_data = pd.DataFrame()
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            
            # Generate chart with empty data
            result_path = trend_sales(empty_data, output_path)
            
            # Verify file was created (should be empty chart)
            assert result_path.exists()
            assert result_path.suffix == '.png'
            assert result_path.stat().st_size > 0
