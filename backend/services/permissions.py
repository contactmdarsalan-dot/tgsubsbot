"""Centralized permissions and role management.
Single source of truth for authorization logic."""
from fastapi import HTTPException
from config import SUPER_ADMIN_EMAILS

# Valid roles (ordered by privilege)
ROLES = {"super_admin", "tenant_owner", "tenant_admin", "admin", "creator", "customer", "user"}


def is_super_admin(user: dict) -> bool:
    """Check if user is a platform super admin."""
    return user.get("role") == "super_admin" or user.get("email") in SUPER_ADMIN_EMAILS


def is_tenant_admin(user: dict) -> bool:
    """Check if user is a tenant admin (can manage their own tenant)."""
    return user.get("role") in {"tenant_owner", "tenant_admin"}


def is_any_admin(user: dict) -> bool:
    """Check if user has any admin-level access."""
    return user.get("role") in {"super_admin", "tenant_owner", "tenant_admin", "admin"} or user.get("email") in SUPER_ADMIN_EMAILS


def get_user_tenant(user: dict) -> str:
    """Get tenant_id from user. Super admins see all (returns empty string).
    Non-super-admins without a tenant_id get a dead value to prevent data leaks."""
    if is_super_admin(user):
        return ""  # No filter — sees everything
    tenant_id = user.get("tenant_id", "")
    if not tenant_id:
        # SECURITY: Return impossible value so tq() adds a filter matching nothing
        return "__no_tenant__"
    return tenant_id


def tq(base_query: dict, tenant_id: str) -> dict:
    """Add tenant_id filter to query. ALWAYS filters for non-empty tenant_id.
    Empty tenant_id (super admin) means no filter = see all data."""
    if tenant_id:
        base_query["tenant_id"] = tenant_id
    return base_query


def ensure_super_admin(user: dict):
    """Raise 403 if user is not super admin."""
    if not is_super_admin(user):
        raise HTTPException(status_code=403, detail="Super Admin access required")


def ensure_admin(user: dict):
    """Raise 403 if user has no admin access."""
    if not is_any_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")


def ensure_tenant_access(user: dict, tenant_id: str):
    """Verify user can access a specific tenant."""
    if is_super_admin(user):
        return  # Super admin can access any tenant
    if user.get("tenant_id") == tenant_id and is_tenant_admin(user):
        return  # Tenant admin can access their own tenant
    raise HTTPException(status_code=403, detail="Access denied to this tenant")
