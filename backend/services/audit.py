"""Audit logging service for tracking admin actions."""
from database import db
from datetime import datetime, timezone
import uuid


async def log_action(
    tenant_id: str,
    actor_id: str,
    actor_email: str,
    action: str,
    entity_type: str,
    entity_id: str = "",
    metadata: dict = None,
):
    """Log an admin action to the audit_logs collection."""
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id or "platform",
        "actor_user_id": actor_id,
        "actor_email": actor_email,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
