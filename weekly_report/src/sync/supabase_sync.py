"""Supabase sync function that can be called from CLI or API."""

from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import time
import json

from loguru import logger

from weekly_report.src.adapters.supabase_client import get_supabase_client
from weekly_report.src.config import load_config
from weekly_report.src.export.budget_general import map_budget_general_to_rows
from weekly_report.src.export.budget_markets import map_budget_markets_to_rows
from weekly_report.src.export.weekly_reports import map_batch_metrics_to_supabase
from weekly_report.src.compute.budget import (
    compute_budget_general,
    compute_actuals_general,
    compute_actuals_markets_detailed
)
from weekly_report.src.metrics.batch_calculator import calculate_all_metrics
from weekly_report.src.utils.file_hashes import get_file_hashes_for_week, hashes_match


def sync_supabase_data(base_week: Optional[str] = None, num_weeks: int = 8) -> Dict[str, Any]:
    """
    Sync precomputed report data to Supabase for read-optimized frontend access.
    
    Args:
        base_week: ISO week format (YYYY-WW). If None, uses default from config.
        num_weeks: Number of weeks to analyze (default: 8)
    
    Returns:
        Dict with 'success', 'row_counts', 'elapsed_seconds', and optionally 'error'
    """
    start_time = time.time()
    
    # Load configuration
    config = load_config(week=base_week)
    week = config.week
    
    logger.info(f"Starting Supabase sync for week {week}")
    
    # Initialize Supabase client
    supabase = get_supabase_client()
    if not supabase:
        error_msg = "Failed to initialize Supabase client. Check environment variables."
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "elapsed_seconds": time.time() - start_time
        }
    
    # Track sync run
    sync_id = str(uuid.uuid4())
    sync_started = datetime.utcnow()
    
    try:
        # Record weeks entry
        supabase.table("weeks").upsert({
            "id": week,
            "created_at": sync_started.isoformat()
        }).execute()
        
        row_counts = {}
        
        # Step 0: Check cache and compute Weekly Report Metrics
        logger.info("Computing Weekly Report Metrics...")
        
        # Calculate current file hashes
        current_file_hashes = get_file_hashes_for_week(week, config.data_root)
        logger.info(f"File hashes for week {week}: {list(current_file_hashes.keys())}")
        
        # Check if cached metrics exist and file hashes match
        cached_metrics = None
        try:
            cached_result = supabase.table("weekly_report_metrics").select("*").eq("base_week", week).limit(1).execute()
            if cached_result.data and len(cached_result.data) > 0:
                cached_row = cached_result.data[0]
                stored_hashes = cached_row.get("file_hashes")
                if stored_hashes and isinstance(stored_hashes, str):
                    stored_hashes = json.loads(stored_hashes)
                elif isinstance(stored_hashes, dict):
                    pass  # Already dict
                else:
                    stored_hashes = {}
                
                # Check if file hashes match
                hashes_match_result = hashes_match(stored_hashes, current_file_hashes)
                
                # Also check if cached data has YTD metrics (ytd_actual, ytd_last_year, ytd_2023)
                has_ytd_data = False
                if hashes_match_result:
                    try:
                        cached_metrics_json = cached_row.get("metrics")
                        if isinstance(cached_metrics_json, str):
                            cached_metrics_json = json.loads(cached_metrics_json)
                        
                        # Check if metrics.metrics contains YTD keys
                        if isinstance(cached_metrics_json, dict):
                            metrics_data = cached_metrics_json.get("metrics", {})
                            if isinstance(metrics_data, dict):
                                has_ytd_data = all(key in metrics_data for key in ["ytd_actual", "ytd_last_year", "ytd_2023"])
                        
                        if has_ytd_data:
                            logger.info(f"✅ Cached metrics found for week {week} with matching file hashes and YTD data - skipping computation")
                        else:
                            logger.info(f"⚠️ Cached metrics found for week {week} but missing YTD data - will recompute")
                    except Exception as ytd_check_error:
                        logger.warning(f"Error checking YTD data in cache: {ytd_check_error} - will recompute")
                
                if hashes_match_result and has_ytd_data:
                    cached_metrics = cached_row
                else:
                    if not hashes_match_result:
                        logger.info(f"⚠️ File hashes changed for week {week} - will recompute metrics")
                    else:
                        logger.info(f"⚠️ Cached metrics missing YTD data for week {week} - will recompute metrics")
        except Exception as cache_check_error:
            logger.warning(f"Error checking cache: {cache_check_error}")
        
        # Compute metrics if not cached or hashes don't match
        if not cached_metrics:
            try:
                logger.info(f"Computing all weekly report metrics for {week}...")
                all_metrics = calculate_all_metrics(week, config.data_root, num_weeks)
                
                # Map to Supabase format
                weekly_metrics_row = map_batch_metrics_to_supabase(
                    base_week=week,
                    metrics=all_metrics,
                    file_hashes=current_file_hashes,
                    num_weeks=num_weeks
                )
                
                # Save to Supabase
                logger.info(f"Upserting weekly_report_metrics for week {week}...")
                logger.debug(f"Weekly metrics row structure: {list(weekly_metrics_row.keys())}")
                logger.debug(f"Metrics type: {type(weekly_metrics_row.get('metrics'))}")
                logger.debug(f"Metrics size: {len(str(weekly_metrics_row.get('metrics', '')))} chars")
                logger.debug(f"File hashes type: {type(weekly_metrics_row.get('file_hashes'))}")
                
                try:
                    result = supabase.table("weekly_report_metrics").upsert(weekly_metrics_row, on_conflict="base_week").execute()
                    
                    if result.data and len(result.data) > 0:
                        logger.info(f"✅ Upsert successful! Returned {len(result.data)} rows")
                        logger.debug(f"Sample returned data: {list(result.data[0].keys()) if result.data else 'None'}")
                    else:
                        logger.warning(f"⚠️ Upsert returned no data - this might indicate an issue")
                    
                    # Verify the data was actually saved
                    verify_result = supabase.table("weekly_report_metrics").select("base_week,computed_at").eq("base_week", week).limit(1).execute()
                    if verify_result.data and len(verify_result.data) > 0:
                        logger.info(f"✅ Verified: Data exists in Supabase for week {week} (computed at {verify_result.data[0].get('computed_at')})")
                    else:
                        logger.error(f"❌ Verification failed: Data NOT found in Supabase for week {week}")
                        raise ValueError(f"Data verification failed: upsert succeeded but data not found in Supabase")
                    
                    row_counts["weekly_report_metrics"] = 1
                    logger.info(f"✅ Saved weekly report metrics to Supabase for week {week}")
                except Exception as upsert_error:
                    logger.error(f"❌ Upsert failed: {upsert_error}")
                    import traceback
                    logger.error(f"Full traceback:\n{traceback.format_exc()}")
                    raise
            except Exception as metrics_error:
                logger.error(f"❌ Failed to compute/save weekly report metrics: {metrics_error}")
                import traceback
                logger.error(f"Full traceback:\n{traceback.format_exc()}")
                # Don't continue with budget sync if weekly report metrics fail - this is critical
                raise  # Re-raise to fail the entire sync
        
        # Step 1: Compute and sync Budget General
        logger.info("Computing Budget General...")
        budget_data = compute_budget_general(week)
        
        if "error" in budget_data:
            logger.warning(f"Budget General error (skipping sync): {budget_data['error']}")
            # Continue with other steps even if budget fails
        else:
            budget_rows, budget_totals = map_budget_general_to_rows(budget_data, kind="budget")
            if budget_rows:
                # Batch upsert (1000 rows at a time)
                batch_size = 1000
                for i in range(0, len(budget_rows), batch_size):
                    batch = budget_rows[i:i+batch_size]
                    supabase.table("budget_general").upsert(batch, on_conflict="base_week,metric,customer,month,kind").execute()
                row_counts["budget_general"] = len(budget_rows)
                logger.info(f"Upserted {len(budget_rows)} budget general rows")
            
            if budget_totals:
                supabase.table("budget_general_totals").upsert(budget_totals, on_conflict="base_week,metric,customer,scope,kind").execute()
                row_counts["budget_general_totals"] = len(budget_totals)
                logger.info(f"Upserted {len(budget_totals)} budget general totals")
        
        # Step 2: Compute and sync Actuals General
        logger.info("Computing Actuals General...")
        actuals_data = compute_actuals_general(week)
        
        if "error" in actuals_data:
            logger.warning(f"Actuals General error: {actuals_data['error']}")
        else:
            actuals_rows, actuals_totals = map_budget_general_to_rows(actuals_data, kind="actuals")
            if actuals_rows:
                batch_size = 1000
                for i in range(0, len(actuals_rows), batch_size):
                    batch = actuals_rows[i:i+batch_size]
                    supabase.table("budget_general").upsert(batch, on_conflict="base_week,metric,customer,month,kind").execute()
                row_counts["budget_general_actuals"] = len(actuals_rows)
                logger.info(f"Upserted {len(actuals_rows)} actuals general rows")
            
            if actuals_totals:
                supabase.table("budget_general_totals").upsert(actuals_totals, on_conflict="base_week,metric,customer,scope,kind").execute()
                row_counts["budget_general_totals_actuals"] = len(actuals_totals)
                logger.info(f"Upserted {len(actuals_totals)} actuals general totals")
        
        # Step 3: Compute and sync Actuals Markets Detailed
        logger.info("Computing Actuals Markets Detailed...")
        markets_data = compute_actuals_markets_detailed(week)
        
        if "error" in markets_data or not markets_data.get("markets"):
            logger.warning(f"Actuals Markets Detailed error or empty: {markets_data.get('error', 'No markets')}")
        else:
            markets_rows, markets_totals = map_budget_markets_to_rows(markets_data, kind="actuals")
            if markets_rows:
                batch_size = 1000
                for i in range(0, len(markets_rows), batch_size):
                    batch = markets_rows[i:i+batch_size]
                    supabase.table("budget_markets_detailed").upsert(batch, on_conflict="base_week,market,metric,month,kind").execute()
                row_counts["budget_markets_detailed"] = len(markets_rows)
                logger.info(f"Upserted {len(markets_rows)} markets detailed rows")
            
            if markets_totals:
                supabase.table("budget_markets_totals").upsert(markets_totals, on_conflict="base_week,market,metric,scope,kind").execute()
                row_counts["budget_markets_totals"] = len(markets_totals)
                logger.info(f"Upserted {len(markets_totals)} markets totals")
        
        # Record successful sync
        sync_finished = datetime.utcnow()
        elapsed = (sync_finished - sync_started).total_seconds()
        
        # Schema has row_counts JSONB (no 'details' column). Store counts + elapsed in row_counts.
        supabase.table("sync_runs").insert({
            "id": sync_id,
            "base_week": week,
            "started_at": sync_started.isoformat(),
            "finished_at": sync_finished.isoformat(),
            "success": True,
            "row_counts": { "elapsed_seconds": elapsed, **row_counts }
        }).execute()
        
        logger.success(f"Sync completed successfully in {elapsed:.2f} seconds")
        logger.info(f"Row counts: {row_counts}")
        
        return {
            "success": True,
            "row_counts": row_counts,
            "elapsed_seconds": elapsed,
            "sync_id": sync_id
        }
        
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        try:
            sync_finished = datetime.utcnow()
            if supabase:
                supabase.table("sync_runs").insert({
                    "id": sync_id,
                    "base_week": week,
                    "started_at": sync_started.isoformat(),
                    "finished_at": sync_finished.isoformat(),
                    "success": False,
                    "error_message": str(e),
                    "row_counts": None
                }).execute()
        except Exception as log_error:
            logger.error(f"Failed to log sync error: {log_error}")
        
        return {
            "success": False,
            "error": str(e),
            "elapsed_seconds": time.time() - start_time,
            "sync_id": sync_id
        }

