"""Unified batch calculator for all metrics using shared data loading."""

from typing import Dict, Any
from pathlib import Path
from loguru import logger

from weekly_report.src.metrics.table1 import load_all_raw_data, calculate_table1_for_periods_with_ytd
from weekly_report.src.metrics.markets import calculate_top_markets_for_weeks
from weekly_report.src.metrics.online_kpis import calculate_online_kpis_for_weeks
from weekly_report.src.metrics.contribution import calculate_contribution_for_weeks
from weekly_report.src.metrics.gender_sales import calculate_gender_sales_for_weeks
from weekly_report.src.metrics.men_category_sales import calculate_men_category_sales_for_weeks
from weekly_report.src.metrics.women_category_sales import calculate_women_category_sales_for_weeks
from weekly_report.src.metrics.category_sales import calculate_category_sales_for_weeks
from weekly_report.src.metrics.top_products import calculate_top_products_for_weeks
from weekly_report.src.metrics.top_products_gender import calculate_top_products_by_gender_for_weeks
from weekly_report.src.metrics.sessions_per_country import calculate_sessions_per_country_for_weeks
from weekly_report.src.metrics.conversion_per_country import calculate_conversion_per_country_for_weeks
from weekly_report.src.metrics.new_customers_per_country import calculate_new_customers_per_country_for_weeks
from weekly_report.src.metrics.returning_customers_per_country import calculate_returning_customers_per_country_for_weeks
from weekly_report.src.metrics.aov_new_customers_per_country import calculate_aov_new_customers_per_country_for_weeks
from weekly_report.src.metrics.aov_returning_customers_per_country import calculate_aov_returning_customers_per_country_for_weeks
from weekly_report.src.metrics.marketing_spend_per_country import calculate_marketing_spend_per_country_for_weeks
from weekly_report.src.metrics.ncac_per_country import calculate_ncac_per_country_for_weeks
from weekly_report.src.metrics.contribution_new_per_country import calculate_contribution_new_per_country_for_weeks
from weekly_report.src.metrics.contribution_new_total_per_country import calculate_contribution_new_total_per_country_for_weeks
from weekly_report.src.metrics.contribution_returning_per_country import calculate_contribution_returning_per_country_for_weeks
from weekly_report.src.metrics.contribution_returning_total_per_country import calculate_contribution_returning_total_per_country_for_weeks
from weekly_report.src.metrics.total_contribution_per_country import calculate_total_contribution_per_country_for_weeks
from weekly_report.src.periods.calculator import get_periods_for_week


def calculate_all_metrics(base_week: str, data_root: Path, num_weeks: int = 8) -> Dict[str, Any]:
    """
    Calculate all metrics in a single batch using shared data loading.
    
    This function loads raw data once and reuses it across all metric calculations,
    eliminating redundant data loading and improving performance.
    
    Args:
        base_week: Base ISO week string like '2025-42'
        data_root: Root data directory
        num_weeks: Number of weeks to analyze (default: 8)
        
    Returns:
        Dictionary containing all calculated metrics
    """
    
    logger.info(f"Starting unified batch calculation for {base_week}")
    
    # Calculate periods once
    periods = get_periods_for_week(base_week)
    
    results = {
        'periods': periods,
        'metrics': {},
        'markets': {},
        'kpis': {},
        'contribution': {},
        'gender_sales': {},
        'men_category_sales': {},
        'women_category_sales': {},
        'category_sales': {},
        'products_new': {},
        'products_gender': {},
        'sessions_per_country': {},
        'conversion_per_country': {},
        'new_customers_per_country': {},
        'returning_customers_per_country': {},
        'aov_new_customers_per_country': {},
        'aov_returning_customers_per_country': {},
        'marketing_spend_per_country': {},
        'ncac_per_country': {},
        'contribution_new_per_country': {},
        'contribution_new_total_per_country': {},
        'contribution_returning_per_country': {},
        'contribution_returning_total_per_country': {},
        'total_contribution_per_country': {}
    }
    
    try:
        # 1. Calculate periods and table1 metrics (WITH YTD)
        logger.info("Calculating periods and table1 metrics with YTD...")
        metrics_data = calculate_table1_for_periods_with_ytd(periods, data_root)
        results['metrics'] = metrics_data
        
        # 2. Calculate top markets
        logger.info("Calculating top markets...")
        try:
            markets_data = calculate_top_markets_for_weeks(base_week, num_weeks, data_root)
            results['markets'] = markets_data
        except Exception as e:
            logger.warning(f"Markets calculation failed for {base_week}, returning empty: {e}")
            results['markets'] = {
                'markets': [],
                'period_info': {'latest_week': base_week, 'latest_dates': ''},
            }
        
        # 3. Calculate online KPIs
        logger.info("Calculating online KPIs...")
        kpis_data = calculate_online_kpis_for_weeks(base_week, num_weeks, data_root)
        results['kpis'] = kpis_data
        
        # 4. Calculate contribution
        logger.info("Calculating contribution...")
        contribution_data = calculate_contribution_for_weeks(base_week, num_weeks, data_root)
        results['contribution'] = contribution_data
        
        # 5. Calculate gender sales
        logger.info("Calculating gender sales...")
        gender_sales_data = calculate_gender_sales_for_weeks(base_week, num_weeks, data_root)
        results['gender_sales'] = gender_sales_data
        
        # 6. Calculate men category sales
        logger.info("Calculating men category sales...")
        men_category_data = calculate_men_category_sales_for_weeks(base_week, num_weeks, data_root)
        results['men_category_sales'] = men_category_data
        
        # 7. Calculate women category sales
        logger.info("Calculating women category sales...")
        women_category_data = calculate_women_category_sales_for_weeks(base_week, num_weeks, data_root)
        results['women_category_sales'] = women_category_data
        
        # 8. Calculate category sales
        logger.info("Calculating category sales...")
        category_data = calculate_category_sales_for_weeks(base_week, num_weeks, data_root)
        results['category_sales'] = category_data
        
        # 9. Calculate top products (new/returning)
        logger.info("Calculating top products...")
        products_new_data = calculate_top_products_for_weeks(base_week, 1, data_root)
        results['products_new'] = products_new_data
        
        # 10. Calculate top products (gender) – both men and women
        logger.info("Calculating top products by gender...")
        products_gender_men = calculate_top_products_by_gender_for_weeks(base_week, 1, data_root, 'men')
        products_gender_women = calculate_top_products_by_gender_for_weeks(base_week, 1, data_root, 'women')
        results['products_gender'] = {'men': products_gender_men, 'women': products_gender_women}
        
        # 11. Calculate sessions per country
        logger.info("Calculating sessions per country...")
        sessions_data = calculate_sessions_per_country_for_weeks(base_week, num_weeks, data_root)
        results['sessions_per_country'] = sessions_data
        
        # 12. Calculate conversion per country
        logger.info("Calculating conversion per country...")
        conversion_data = calculate_conversion_per_country_for_weeks(base_week, num_weeks, data_root)
        results['conversion_per_country'] = conversion_data
        
        # 13. Calculate new customers per country
        logger.info("Calculating new customers per country...")
        new_customers_data = calculate_new_customers_per_country_for_weeks(base_week, num_weeks, data_root)
        results['new_customers_per_country'] = new_customers_data
        
        # 14. Calculate returning customers per country
        logger.info("Calculating returning customers per country...")
        returning_customers_data = calculate_returning_customers_per_country_for_weeks(base_week, num_weeks, data_root)
        results['returning_customers_per_country'] = returning_customers_data
        
        # 15. Calculate AOV for new customers per country
        logger.info("Calculating AOV for new customers per country...")
        aov_new_data = calculate_aov_new_customers_per_country_for_weeks(base_week, num_weeks, data_root)
        results['aov_new_customers_per_country'] = aov_new_data
        
        # 16. Calculate AOV for returning customers per country
        logger.info("Calculating AOV for returning customers per country...")
        aov_returning_data = calculate_aov_returning_customers_per_country_for_weeks(base_week, num_weeks, data_root)
        results['aov_returning_customers_per_country'] = aov_returning_data
        
        # 17. Calculate marketing spend per country
        logger.info("Calculating marketing spend per country...")
        marketing_spend_data = calculate_marketing_spend_per_country_for_weeks(base_week, num_weeks, data_root)
        results['marketing_spend_per_country'] = marketing_spend_data
        
        # 18. Calculate nCAC per country
        logger.info("Calculating nCAC per country...")
        ncac_data = calculate_ncac_per_country_for_weeks(base_week, num_weeks, data_root)
        results['ncac_per_country'] = ncac_data
        
        # 19. Calculate contribution new per country
        logger.info("Calculating contribution new per country...")
        contribution_new_data = calculate_contribution_new_per_country_for_weeks(base_week, num_weeks, data_root)
        results['contribution_new_per_country'] = contribution_new_data
        
        # 20. Calculate contribution new total per country
        logger.info("Calculating contribution new total per country...")
        contribution_new_total_data = calculate_contribution_new_total_per_country_for_weeks(base_week, num_weeks, data_root)
        results['contribution_new_total_per_country'] = contribution_new_total_data
        
        # 21. Calculate contribution returning per country
        logger.info("Calculating contribution returning per country...")
        contribution_returning_data = calculate_contribution_returning_per_country_for_weeks(base_week, num_weeks, data_root)
        results['contribution_returning_per_country'] = contribution_returning_data
        
        # 22. Calculate contribution returning total per country
        logger.info("Calculating contribution returning total per country...")
        contribution_returning_total_data = calculate_contribution_returning_total_per_country_for_weeks(base_week, num_weeks, data_root)
        results['contribution_returning_total_per_country'] = contribution_returning_total_data
        
        # 23. Calculate total contribution per country
        logger.info("Calculating total contribution per country...")
        total_contribution_data = calculate_total_contribution_per_country_for_weeks(base_week, num_weeks, data_root)
        results['total_contribution_per_country'] = total_contribution_data
        
        logger.info(f"Successfully completed batch calculation for {base_week}")
        
    except Exception as e:
        logger.error(f"Error during batch calculation: {e}")
        raise
    
    return results

