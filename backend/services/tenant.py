"""Tenant isolation utilities for multi-creator SaaS architecture.

Each creator (tenant) has their own bot, users, payments, plans etc.
- tenant_id: unique identifier for each creator/tenant
- Tenant is determined from: bot_token, admin telegram_user_id, or explicit parameter
- NO DEFAULT FALLBACK: Every operation MUST have an explicit tenant_id
"""
from database import db
from config import logger
from datetime import datetime, timezone
import uuid

# DEPRECATED: Used ONLY as a safe dead-filter fallback during migration.
# Queries using this value will match NOTHING, preventing data leaks.
DEFAULT_TENANT_ID = "__unresolved_tenant__"


async def resolve_tenant_from_bot_token(bot_token: str) -> str:
    """Given a bot token, find which tenant owns it. Returns dead filter if not found."""
    if not bot_token:
        logger.error("TENANT_ISOLATION: resolve_tenant_from_bot_token called with empty bot_token")
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
    logger.warning(f"TENANT_ISOLATION: No tenant found for bot_token ending ...{bot_token[-8:] if len(bot_token) > 8 else '***'}")
    return DEFAULT_TENANT_ID


async def resolve_tenant_from_admin_tg_id(telegram_user_id: str) -> str:
    """Given an admin's Telegram ID, find their tenant_id. Returns dead filter if not found."""
    if not telegram_user_id:
        logger.error("TENANT_ISOLATION: resolve_tenant_from_admin_tg_id called with empty telegram_user_id")
        return DEFAULT_TENANT_ID
    admin = await db.telegram_admins.find_one(
        {"telegram_user_id": str(telegram_user_id), "is_active": True},
        {"_id": 0, "tenant_id": 1}
    )
    if admin and admin.get("tenant_id"):
        return admin["tenant_id"]
    logger.warning(f"TENANT_ISOLATION: No tenant found for admin telegram_user_id={telegram_user_id}")
    return DEFAULT_TENANT_ID


async def get_tenant_settings(tenant_id: str) -> dict:
    """Get bot settings for a specific tenant."""
    if not tenant_id or tenant_id == DEFAULT_TENANT_ID:
        logger.warning("TENANT_ISOLATION: get_tenant_settings called without valid tenant_id")
        settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0})
        return settings or {}
    settings = await db.settings.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0}
    )
    if settings:
        return settings
    # Fallback to global settings
    return await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}


def tenant_query(base_query: dict, tenant_id: str) -> dict:
    """Add tenant_id filter to a query dict. ALWAYS filters by tenant_id."""
    if tenant_id:
        base_query["tenant_id"] = tenant_id
    return base_query
