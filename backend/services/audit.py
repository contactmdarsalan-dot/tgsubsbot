"""Audit logging service for tracking admin actions.
Every admin mutation MUST be logged with actor, tenant, action, and entity details."""
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
    before_state: dict = None,
    after_state: dict = None,
    request_id: str = "",
):
    """Log an admin action to the audit_logs collection.
    
    Args:
        tenant_id: Tenant scope ("platform" for platform-level actions)
        actor_id: User ID performing the action
        actor_email: Email of the actor
        action: Action name (e.g., "create_plan", "delete_tenant", "approve_payment")
        entity_type: Type of entity affected (e.g., "plan", "tenant", "user")
        entity_id: ID of the specific entity
        metadata: Additional context data
        before_state: State before the action (for update/delete)
        after_state: State after the action (for create/update)
        request_id: Request ID from middleware for traceability
    """
    log_entry = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id or "platform",
        "actor_user_id": actor_id,
        "actor_email": actor_email,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if before_state:
        log_entry["before_state"] = before_state
    if after_state:
        log_entry["after_state"] = after_state
    if request_id:
        log_entry["request_id"] = request_id
    
    await db.audit_logs.insert_one(log_entry)
