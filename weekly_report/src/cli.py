"""CLI interface for weekly report pipeline."""

import time
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

from weekly_report.src.config import load_config
from weekly_report.src.adapters import qlik, dema, dema_gm2, shopify, other
from weekly_report.src.validate.schemas import validate_all_sources
from weekly_report.src.transform import kpis, markets, products
from weekly_report.src.qa.checks import run_qa_checks
from weekly_report.src.viz import charts, tables
from weekly_report.src.pdf.builder import build_pdfs, build_general_pdf, build_market_pdf
from weekly_report.src.storage.io import write_manifest


app = typer.Typer(help="Weekly Report PDF Pipeline")


@app.command()
def generate(
    week: Optional[str] = typer.Option(None, "--week", "-w", help="ISO week format: YYYY-WW"),
    config_file: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    report: str = typer.Option("all", "--report", "-r", help="Which report to generate: general | market | all"),
) -> None:
    """Generate weekly reports from CSV data sources."""
    
    start_time = time.time()
    
    # Load configuration
    config = load_config(week=week, config_file=config_file)
    
    # Setup logging
    logger.remove()
    log_level = "DEBUG" if verbose else config.log_level
    logger.add(
        lambda msg: print(msg, end=""),
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    logger.info(f"Starting weekly report generation for week {config.week}")
    logger.info(f"Data root: {config.data_root}")
    logger.info(f"Strict mode: {config.strict_mode}")
    
    try:
        # Step 1: Load and validate data
        logger.info("Step 1: Loading CSV data from adapters")
        
        # Create output directories
        config.curated_data_path.mkdir(parents=True, exist_ok=True)
        config.charts_path.mkdir(parents=True, exist_ok=True)
        config.reports_path.mkdir(parents=True, exist_ok=True)
        
        # Load data from all sources
        data_sources = {}
        
        try:
            data_sources['qlik'] = qlik.load_data(config.raw_data_path)
            logger.info(f"Loaded Qlik data: {data_sources['qlik'].shape}")
        except FileNotFoundError as e:
            logger.error(f"Qlik data not found: {e}")
            if config.strict_mode:
                raise
        
        try:
            data_sources['dema_spend'] = dema.load_data(config.raw_data_path)
            logger.info(f"Loaded Dema spend data: {data_sources['dema_spend'].shape}")
        except FileNotFoundError as e:
            logger.error(f"Dema spend data not found: {e}")
            if config.strict_mode:
                raise
        
        try:
            data_sources['dema_gm2'] = dema_gm2.load_data(config.raw_data_path)
            logger.info(f"Loaded Dema GM2 data: {data_sources['dema_gm2'].shape}")
        except FileNotFoundError as e:
            logger.error(f"Dema GM2 data not found: {e}")
            if config.strict_mode:
                raise
        
        try:
            data_sources['shopify'] = shopify.load_data(config.raw_data_path)
            logger.info(f"Loaded Shopify data: {data_sources['shopify'].shape}")
        except FileNotFoundError as e:
            logger.error(f"Shopify data not found: {e}")
            if config.strict_mode:
                raise
        
        try:
            data_sources['other'] = other.load_data(config.raw_data_path)
            logger.info(f"Loaded other data: {data_sources['other'].shape}")
        except FileNotFoundError as e:
            logger.warning(f"Other data not found: {e}")
            # Other source is optional
        
        # Step 2: Validate data schemas
        logger.info("Step 2: Validating data schemas")
        validation_results = validate_all_sources(data_sources, strict_mode=config.strict_mode)
        
        if not validation_results['valid'] and config.strict_mode:
            logger.error("Schema validation failed in strict mode")
            raise typer.Exit(1)
        
        # Step 3: Transform data
        logger.info("Step 3: Transforming data to curated format")
        
        curated_data = {}
        
        # Transform KPIs
        kpi_data = kpis.transform_to_kpis(data_sources, config.week)
        curated_data['kpis'] = kpi_data
        logger.info(f"Generated KPI data: {kpi_data.shape}")
        
        # Transform markets
        market_data = markets.transform_to_markets(data_sources, config.week)
        curated_data['markets'] = market_data
        logger.info(f"Generated market data: {market_data.shape}")
        
        # Transform products
        product_data = products.transform_to_products(data_sources, config.week)
        curated_data['products'] = product_data
        logger.info(f"Generated product data: {product_data.shape}")
        
        # Save curated data
        for name, df in curated_data.items():
            output_path = config.curated_data_path / f"{name}.csv"
            df.to_csv(output_path, index=False)
            logger.info(f"Saved curated {name} to {output_path}")
        
        # Step 4: QA checks
        logger.info("Step 4: Running QA checks")
        qa_results = run_qa_checks(data_sources, curated_data, strict_mode=config.strict_mode)
        
        if not qa_results['passed'] and config.strict_mode:
            logger.error("QA checks failed in strict mode")
            raise typer.Exit(1)
        
        # Step 5: Generate visualizations
        logger.info("Step 5: Generating charts and tables")
        
        chart_files = {}
        
        # Generate charts
        chart_files['trend_sales'] = charts.trend_sales(kpi_data, config.charts_path)
        chart_files['bar_yoy_wow'] = charts.bar_yoy_wow(market_data, config.charts_path)
        chart_files['waterfall_contrib'] = charts.waterfall_contrib(kpi_data, config.charts_path)
        
        # Generate tables
        chart_files['kpi_table'] = tables.kpi_table(kpi_data, config.charts_path)
        chart_files['market_table'] = tables.market_table(market_data, config.charts_path)
        
        logger.info(f"Generated {len(chart_files)} chart/table files")
        
        # Step 6: Build PDFs
        logger.info("Step 6: Building PDF reports")
        pdf_files = {}
        report_lower = (report or "all").lower()
        if report_lower not in {"general", "market", "all"}:
            logger.warning(f"Unknown --report value '{report}', defaulting to 'all'")
            report_lower = "all"

        if report_lower == "general":
            pdf_files["general"] = build_general_pdf(curated_data, chart_files, load_pdf_layout(config.template_path), config)
        elif report_lower == "market":
            pdf_files["market"] = build_market_pdf(curated_data, chart_files, load_pdf_layout(config.template_path), config)
        else:
            pdf_files = build_pdfs(
                curated_data=curated_data,
                chart_files=chart_files,
                config=config
            )

        logger.info(f"Generated PDFs: {list(pdf_files.keys())}")
        
        # Step 7: Write manifest
        logger.info("Step 7: Writing manifest")
        
        manifest_path = write_manifest(
            curated_data=curated_data,
            chart_files=chart_files,
            pdf_files=pdf_files,
            config=config
        )
        
        # Final summary
        elapsed_time = time.time() - start_time
        logger.success(f"Pipeline completed successfully in {elapsed_time:.2f} seconds")
        logger.info(f"Outputs:")
        logger.info(f"  Curated data: {config.curated_data_path}")
        logger.info(f"  Charts: {config.charts_path}")
        logger.info(f"  Reports: {config.reports_path}")
        logger.info(f"  Manifest: {manifest_path}")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        if config.strict_mode:
            raise typer.Exit(1)
        else:
            logger.warning("Continuing despite errors (strict_mode=False)")


@app.command()
def validate(
    week: Optional[str] = typer.Option(None, "--week", "-w", help="ISO week format: YYYY-WW"),
) -> None:
    """Validate CSV data without generating reports."""
    
    config = load_config(week=week)
    
    logger.info(f"Validating data for week {config.week}")
    
    # Load and validate data
    data_sources = {}
    
    try:
        data_sources['qlik'] = qlik.load_data(config.raw_data_path)
        data_sources['dema_spend'] = dema.load_data(config.raw_data_path)
        data_sources['dema_gm2'] = dema_gm2.load_data(config.raw_data_path)
        data_sources['shopify'] = shopify.load_data(config.raw_data_path)
        data_sources['other'] = other.load_data(config.raw_data_path)
    except FileNotFoundError as e:
        logger.error(f"Data not found: {e}")
        raise typer.Exit(1)
    
    validation_results = validate_all_sources(data_sources, strict_mode=True)
    
    if validation_results['valid']:
        logger.success("All data sources validated successfully")
    else:
        logger.error("Validation failed")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
