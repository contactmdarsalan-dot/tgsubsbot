"""Tenant isolation utilities for multi-creator SaaS architecture.

Each creator (tenant) has their own bot, users, payments, plans etc.
- tenant_id: unique identifier for each creator/tenant
- "default": DEPRECATED — used only for backwards compatibility during migration
- Tenant is determined from: bot_token, admin telegram_user_id, or explicit parameter
"""
from database import db
from config import logger
from datetime import datetime, timezone
import uuid


DEFAULT_TENANT_ID = "default"


async def get_or_create_default_tenant():
    """Ensure the default tenant exists (for backwards compatibility during migration)"""
    tenant = await db.tenants.find_one({"tenant_id": DEFAULT_TENANT_ID}, {"_id": 0})
    if not tenant:
        tenant = {
            "id": str(uuid.uuid4()),
            "tenant_id": DEFAULT_TENANT_ID,
            "name": "Default Creator",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.tenants.insert_one(tenant)
        logger.info("Created default tenant")
    return tenant


async def resolve_tenant_from_bot_token(bot_token: str) -> str:
    """Given a bot token, find which tenant owns it. Logs warning on default fallback."""
    if not bot_token:
        logger.warning("TENANT_ISOLATION: resolve_tenant_from_bot_token called with empty bot_token — falling back to 'default'")
        return DEFAULT_TENANT_ID
    # Check settings collection for a match
    settings = await db.settings.find_one(
        {"telegram_bot_token": bot_token},
        {"_id": 0, "tenant_id": 1}
    )
    if settings and settings.get("tenant_id"):
        return settings["tenant_id"]
    # Check tenants collection
    tenant = await db.tenants.find_one(
        {"bot_token": bot_token},
        {"_id": 0, "tenant_id": 1}
    )
    if tenant:
        return tenant["tenant_id"]
    logger.warning(f"TENANT_ISOLATION: No tenant found for bot_token ending ...{bot_token[-8:] if len(bot_token) > 8 else '***'} — falling back to 'default'")
    return DEFAULT_TENANT_ID


async def resolve_tenant_from_admin_tg_id(telegram_user_id: str) -> str:
    """Given an admin's Telegram ID, find their tenant_id. Logs warning on default fallback."""
    if not telegram_user_id:
        logger.warning("TENANT_ISOLATION: resolve_tenant_from_admin_tg_id called with empty telegram_user_id — falling back to 'default'")
        return DEFAULT_TENANT_ID
    admin = await db.telegram_admins.find_one(
        {"telegram_user_id": str(telegram_user_id), "is_active": True},
        {"_id": 0, "tenant_id": 1}
    )
    if admin and admin.get("tenant_id"):
        return admin["tenant_id"]
    logger.warning(f"TENANT_ISOLATION: No tenant found for admin telegram_user_id={telegram_user_id} — falling back to 'default'")
    return DEFAULT_TENANT_ID


async def get_tenant_settings(tenant_id: str) -> dict:
    """Get bot settings for a specific tenant."""
    if not tenant_id or tenant_id == DEFAULT_TENANT_ID:
        settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0})
        return settings or {}
    settings = await db.settings.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0}
    )
    if settings:
        return settings
    # Fallback to default
    return await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}


def tenant_query(base_query: dict, tenant_id: str) -> dict:
    """Add tenant_id filter to a query dict. ALWAYS filters by tenant_id
    including 'default' to ensure proper multi-tenant isolation."""
    if tenant_id:
        base_query["tenant_id"] = tenant_id
    return base_query
