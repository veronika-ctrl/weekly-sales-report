"""Supabase client adapter for backend services."""

import os
from typing import Optional
from loguru import logger

try:
    from supabase import create_client, Client
except ImportError:
    logger.warning("Supabase Python client not installed. Install with: pip install supabase")
    Client = None
    create_client = None


def get_supabase_client() -> Optional[Client]:
    """
    Get Supabase client instance if configured.
    
    Returns:
        Supabase client instance or None if not configured
    """
    if Client is None or create_client is None:
        return None
    
    if os.getenv("DISABLE_SUPABASE", "").lower() in {"1", "true", "yes"}:
        logger.info("Supabase disabled via DISABLE_SUPABASE")
        return None

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        logger.debug("Supabase credentials not found in environment variables")
        return None
    
    try:
        client = create_client(supabase_url, supabase_key)
        return client
    except Exception as e:
        logger.warning(f"Failed to create Supabase client: {e}")
        return None
