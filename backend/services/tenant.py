"""Strict Tenant isolation utilities for multi-creator SaaS architecture.

Each creator (tenant) has their own bot, users, payments, plans etc.
- tenant_id: unique identifier for each creator/tenant
- STRICT MODE: Every operation MUST have an explicit tenant_id
- No fallbacks, no defaults — missing tenant_id raises 403
"""
from database import db
from config import logger
from core.exceptions import AccessDeniedError

# Sentinel value — queries using this match NOTHING, preventing data leaks.
# Used ONLY as a safe dead-filter when code cannot raise (e.g., webhook background tasks).
UNRESOLVED_TENANT = "__unresolved_tenant__"
PLATFORM_TENANT = "__platform__"


async def resolve_tenant_from_bot_token(bot_token: str) -> str:
    """Given a bot token, find which tenant owns it. Raises 403 if not found."""
    if not bot_token:
        logger.error("TENANT_STRICT: resolve_tenant_from_bot_token called with empty bot_token")
        raise AccessDeniedError("Bot token is required for tenant resolution")

    # Check tenants collection first (primary source of truth)
    tenant = await db.tenants.find_one(
        {"bot_token": bot_token},
        {"_id": 0, "tenant_id": 1}
    )
    if tenant and tenant.get("tenant_id"):
        return tenant["tenant_id"]

    # Fallback: Check settings collection
    settings = await db.settings.find_one(
        {"telegram_bot_token": bot_token},
        {"_id": 0, "tenant_id": 1}
    )
    if settings and settings.get("tenant_id"):
        return settings["tenant_id"]

    logger.error(f"TENANT_STRICT: No tenant found for bot_token ...{bot_token[-8:] if len(bot_token) > 8 else '***'}")
    raise AccessDeniedError("No tenant registered for this bot token")


async def resolve_tenant_from_admin_tg_id(telegram_user_id: str) -> str:
    """Given an admin's Telegram ID, find their tenant_id. Raises 403 if not found."""
    if not telegram_user_id:
        logger.error("TENANT_STRICT: resolve_tenant_from_admin_tg_id called with empty telegram_user_id")
        raise AccessDeniedError("Telegram user ID is required for tenant resolution")

    admin = await db.telegram_admins.find_one(
        {"telegram_user_id": str(telegram_user_id), "is_active": True},
        {"_id": 0, "tenant_id": 1}
    )
    if admin and admin.get("tenant_id"):
        return admin["tenant_id"]

    logger.error(f"TENANT_STRICT: No tenant found for admin telegram_user_id={telegram_user_id}")
    raise AccessDeniedError("No tenant registered for this admin")


async def get_tenant_settings(tenant_id: str) -> dict:
    """Get bot settings for a specific tenant. Raises if invalid."""
    if not tenant_id or tenant_id in (UNRESOLVED_TENANT, ""):
        logger.error("TENANT_STRICT: get_tenant_settings called without valid tenant_id")
        raise AccessDeniedError("Valid tenant_id is required to fetch settings")

    settings = await db.settings.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0}
    )
    if settings:
        return settings

    # Try global settings as last resort (for single-tenant setups during migration)
    global_settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0})
    return global_settings or {}


def tenant_query(base_query: dict, tenant_id: str) -> dict:
    """Add tenant_id filter to a query dict. STRICT: requires valid tenant_id."""
    if not tenant_id or tenant_id in (UNRESOLVED_TENANT, ""):
        logger.error(f"TENANT_STRICT: tenant_query called without valid tenant_id, query={base_query}")
        raise AccessDeniedError("Tenant scope is required for this operation")
    base_query["tenant_id"] = tenant_id
    return base_query
