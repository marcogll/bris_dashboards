import logging
import os

from supabase import create_client, Client

logger = logging.getLogger("vanity_common.supabase")

_supabase_client: Client | None = None


def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            logger.critical("SUPABASE_URL or SUPABASE_SERVICE_KEY not set — auth sessions will fail")
            raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY env vars")
        logger.info("Connecting to Supabase at %s (service_role)", url.split("//")[1].split(".")[0] + "***")
        _supabase_client = create_client(url, key)
    return _supabase_client


def get_supabase_anon() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        logger.error("SUPABASE_URL or SUPABASE_ANON_KEY not set — public queries will fail")
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY env vars")
    return create_client(url, key)