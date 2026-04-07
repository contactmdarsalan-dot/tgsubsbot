"""Idempotency middleware — MongoDB-based dedup for critical operations."""
from database import db
from config import logger
from datetime import datetime, timezone, timedelta


async def acquire_idempotency_lock(key: str, ttl_seconds: int = 300) -> bool:
    """Acquire an idempotency lock to prevent double-processing.
    Returns True if this is the FIRST call with this key."""
    now = datetime.now(timezone.utc)
    try:
        result = await db.idempotency_keys.find_one_and_update(
            {
                "key": key,
                "$or": [
                    {"expires_at": {"$lt": now.isoformat()}},
                    {"expires_at": {"$exists": False}},
                ]
            },
            {
                "$setOnInsert": {
                    "key": key,
                    "created_at": now.isoformat(),
                },
                "$set": {
                    "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
                    "status": "processing",
                }
            },
            upsert=True,
            return_document=False,
        )
        return True
    except Exception as e:
        if "duplicate" in str(e).lower() or "E11000" in str(e):
            return False
        logger.error(f"Idempotency lock error: {e}")
        return False


async def mark_idempotency_complete(key: str, result_data: dict = None):
    """Mark an idempotency key as complete with optional result data."""
    await db.idempotency_keys.update_one(
        {"key": key},
        {"$set": {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result": result_data or {},
        }}
    )
