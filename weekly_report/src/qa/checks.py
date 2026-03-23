"""QA checks for data quality and consistency."""

from typing import Dict

import pandas as pd
from loguru import logger


def run_qa_checks(data_sources: Dict[str, pd.DataFrame], curated_data: Dict[str, pd.DataFrame], strict_mode: bool = True) -> dict:
    """Run comprehensive QA checks on data."""
    
    checks = []
    all_passed = True
    
    # Check 1: Data consistency between sources
    consistency_check = check_data_consistency(data_sources)
    checks.append(consistency_check)
    if not consistency_check['passed']:
        all_passed = False
    
    # Check 2: Negative values
    negative_check = check_negative_values(data_sources, curated_data)
    checks.append(negative_check)
    if not negative_check['passed']:
        all_passed = False
    
    # Check 3: Outliers detection
    outlier_check = check_outliers(data_sources, curated_data)
    checks.append(outlier_check)
    if not outlier_check['passed'] and strict_mode:
        all_passed = False
    
    # Check 4: Volume consistency
    volume_check = check_volume_consistency(data_sources, curated_data)
    checks.append(volume_check)
    if not volume_check['passed']:
        all_passed = False
    
    result = {
        'passed': all_passed,
        'checks': checks,
        'strict_mode': strict_mode
    }
    
    if all_passed:
        logger.success("All QA checks passed")
    else:
        logger.warning(f"QA checks failed: {len([c for c in checks if not c['passed']])} issues found")
    
    return result


def check_data_consistency(data_sources: Dict[str, pd.DataFrame]) -> dict:
    """Check consistency between different data sources."""
    
    issues = []
    
    # Compare Qlik gross vs Dema GM2 gross margin (if both available)
    if 'qlik' in data_sources and 'dema_gm2' in data_sources:
        qlik_df = data_sources['qlik']
        dema_gm2_df = data_sources['dema_gm2']
        
        # Calculate Qlik total revenue
        qlik_total = qlik_df['Gross Revenue'].sum() if 'Gross Revenue' in qlik_df.columns else 0
        
        # Get Dema GM2 gross margin
        dema_gm2_total = dema_gm2_df['Gross margin 2 - Dema MTA'].sum() if 'Gross margin 2 - Dema MTA' in dema_gm2_df.columns else 0
        
        if qlik_total > 0 and dema_gm2_total > 0:
            difference_pct = abs(qlik_total - dema_gm2_total) / qlik_total * 100
            
            if difference_pct > 10:  # More than 10% difference (relaxed threshold)
                issues.append(f"Qlik total ({qlik_total:.2f}) differs from Dema GM2 ({dema_gm2_total:.2f}) by {difference_pct:.1f}%")
    
    return {
        'name': 'Data Consistency',
        'passed': len(issues) == 0,
        'issues': issues
    }


def check_negative_values(data_sources: Dict[str, pd.DataFrame], curated_data: Dict[str, pd.DataFrame]) -> dict:
    """Check for negative values where they shouldn't exist."""
    
    issues = []
    
    # Check Qlik data for negative values
    if 'qlik' in data_sources:
        qlik_df = data_sources['qlik']
        
        # Check for negative gross revenue
        if 'Gross Revenue' in qlik_df.columns:
            negative_revenue = qlik_df[qlik_df['Gross Revenue'] < 0]
            if len(negative_revenue) > 0:
                issues.append(f"Found {len(negative_revenue)} records with negative gross revenue")
        
        # Check for negative net revenue
        if 'Net Revenue' in qlik_df.columns:
            negative_net = qlik_df[qlik_df['Net Revenue'] < 0]
            if len(negative_net) > 0:
                issues.append(f"Found {len(negative_net)} records with negative net revenue")
    
    # Check curated KPI data
    if 'kpis' in curated_data:
        kpi_df = curated_data['kpis']
        
        # Check for negative values in key metrics
        negative_metrics = kpi_df[
            (kpi_df['metric'].isin(['gross_sales', 'net_sales', 'cost_of_sales'])) &
            (kpi_df['value'] < 0)
        ]
        if len(negative_metrics) > 0:
            issues.append(f"Found {len(negative_metrics)} negative values in key metrics")
    
    return {
        'name': 'Negative Values',
        'passed': len(issues) == 0,
        'issues': issues
    }


def check_outliers(data_sources: Dict[str, pd.DataFrame], curated_data: Dict[str, pd.DataFrame]) -> dict:
    """Check for statistical outliers."""
    
    issues = []
    
    # Check Qlik gross revenue for outliers
    if 'qlik' in data_sources:
        qlik_df = data_sources['qlik']
        
        if 'Gross Revenue' in qlik_df.columns:
            revenue = qlik_df['Gross Revenue']
            mean_revenue = revenue.mean()
            std_revenue = revenue.std()
            
            # Find outliers (>3 standard deviations)
            outliers = qlik_df[abs(revenue - mean_revenue) > 3 * std_revenue]
            
            if len(outliers) > 0:
                issues.append(f"Found {len(outliers)} revenue outliers (>3 std dev from mean)")
    
    return {
        'name': 'Outliers',
        'passed': len(issues) == 0,
        'issues': issues
    }


def check_volume_consistency(data_sources: Dict[str, pd.DataFrame], curated_data: Dict[str, pd.DataFrame]) -> dict:
    """Check volume consistency across sources."""
    
    issues = []
    
    # Check if order counts make sense in Qlik data
    if 'qlik' in data_sources:
        qlik_df = data_sources['qlik']
        
        # Check for duplicate order numbers
        if 'Order No' in qlik_df.columns:
            duplicate_orders = qlik_df['Order No'].duplicated().sum()
            if duplicate_orders > 0:
                issues.append(f"Found {duplicate_orders} duplicate order numbers")
        
        # Check for reasonable sales quantities
        if 'Sales Qty' in qlik_df.columns:
            # Convert to numeric, handling any non-numeric values
            sales_qty_numeric = pd.to_numeric(qlik_df['Sales Qty'], errors='coerce')
            extreme_qty = qlik_df[sales_qty_numeric > 1000]  # More than 1000 units per order
            if len(extreme_qty) > 0:
                issues.append(f"Found {len(extreme_qty)} orders with extreme quantities (>1000 units)")
    
    return {
        'name': 'Volume Consistency',
        'passed': len(issues) == 0,
        'issues': issues
    }

