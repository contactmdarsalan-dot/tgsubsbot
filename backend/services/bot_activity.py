"""Bot activity logging service"""
from database import db
from config import logger
from datetime import datetime, timezone
import uuid


async def log_bot_activity(event_type: str, user_id: str = "", username: str = "", details: str = "", metadata: dict = None):
    """Log bot activity for dashboard monitoring"""
    try:
        log_entry = {
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "user_id": user_id,
            "username": username,
            "details": details,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.bot_activity_logs.insert_one(log_entry)
    except Exception as e:
        logger.error(f"Failed to log bot activity: {e}")
