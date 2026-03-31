"""Creator Tenant Onboarding & Dashboard APIs.
Allows new creators to self-register and manage their tenant."""
from fastapi import APIRouter, HTTPException, Depends
from database import db
from services.tenant import DEFAULT_TENANT_ID
from services.auth import get_current_user
from config import logger, SUPER_ADMIN_EMAILS
from datetime import datetime, timezone
import uuid
import httpx

router = APIRouter(prefix="/tenant")


async def _verify_tenant_access(user: dict, tenant_id: str):
    """Verify user has access to this tenant (owner, tenant_admin, or super_admin)."""
    role = user.get("role", "user")
    # Super admin can access any tenant
    if role == "super_admin" or user.get("email") in SUPER_ADMIN_EMAILS:
        return True
    # Tenant admin can access their own tenant
    if role == "tenant_admin" and user.get("tenant_id") == tenant_id:
        return True
    raise HTTPException(status_code=403, detail="Access denied to this tenant")


async def _validate_bot_token(bot_token: str) -> dict:
    """Validate a Telegram bot token by calling getMe"""
    if not bot_token or ":" not in bot_token:
        return {"valid": False, "error": "Invalid token format"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
            data = resp.json()
            if data.get("ok"):
                bot_info = data["result"]
                return {
                    "valid": True,
                    "bot_id": bot_info.get("id"),
                    "bot_username": bot_info.get("username", ""),
                    "bot_name": bot_info.get("first_name", ""),
                }
            return {"valid": False, "error": data.get("description", "Token rejected")}
    except Exception as e:
        return {"valid": False, "error": str(e)}


@router.post("/validate-bot")
async def validate_bot_token(data: dict):
    """Validate a Telegram bot token before onboarding"""
    bot_token = data.get("bot_token", "").strip()
    result = await _validate_bot_token(bot_token)
    return result


@router.post("/onboard")
async def onboard_creator(data: dict):
    """Register a new creator as a tenant.
    Creates: tenant doc, telegram_admin entry, bot settings.
    Returns: tenant_id and unique Mini App URL."""

    creator_name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    bot_token = data.get("bot_token", "").strip()
    telegram_user_id = str(data.get("telegram_user_id", "")).strip()
    upi_id = data.get("upi_id", "").strip()
    channel_id = data.get("channel_id", "").strip()
    razorpay_key_id = data.get("razorpay_key_id", "").strip()
    razorpay_key_secret = data.get("razorpay_key_secret", "").strip()

    if not creator_name:
        raise HTTPException(status_code=400, detail="Creator name is required")
    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot token is required")
    if not telegram_user_id:
        raise HTTPException(status_code=400, detail="Your Telegram User ID is required")
    if not upi_id:
        raise HTTPException(status_code=400, detail="UPI ID is required")

    # Check if bot_token already used
    existing = await db.tenants.find_one({"bot_token": bot_token}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="This bot token is already registered")

    # Check if telegram_user_id already has a tenant
    existing_admin = await db.telegram_admins.find_one(
        {"telegram_user_id": telegram_user_id, "tenant_id": {"$ne": DEFAULT_TENANT_ID}},
        {"_id": 0}
    )
    if existing_admin:
        raise HTTPException(status_code=409, detail="You already have a registered tenant")

    # Validate bot token
    bot_info = await _validate_bot_token(bot_token)
    if not bot_info.get("valid"):
        raise HTTPException(status_code=400, detail=f"Invalid bot token: {bot_info.get('error', 'unknown')}")

    tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"

    # 1. Create tenant
    tenant_doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "name": creator_name,
        "email": email,
        "owner_telegram_id": telegram_user_id,
        "bot_token": bot_token,
        "bot_username": bot_info.get("bot_username", ""),
        "bot_name": bot_info.get("bot_name", ""),
        "upi_id": upi_id,
        "channel_id": channel_id,
        "razorpay_key_id": razorpay_key_id,
        "razorpay_key_secret": razorpay_key_secret,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.tenants.insert_one(tenant_doc)

    # 2. Create telegram_admin entry
    admin_doc = {
        "id": str(uuid.uuid4()),
        "telegram_user_id": telegram_user_id,
        "name": creator_name,
        "email": email,
        "role": "owner",
        "is_active": True,
        "permissions": ["broadcast", "live_streams", "paid_posts", "manage_users", "manage_plans"],
        "tenant_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.telegram_admins.insert_one(admin_doc)

    # 3. Create tenant-specific bot settings
    settings_doc = {
        "id": f"bot_settings_{tenant_id}",
        "tenant_id": tenant_id,
        "telegram_bot_token": bot_token,
        "telegram_admin_ids": [telegram_user_id],
        "payment_upi_id": upi_id,
        "upi_id": upi_id,
        "channel_id": channel_id,
        "razorpay_key_id": razorpay_key_id,
        "razorpay_key_secret": razorpay_key_secret,
        "grace_period_days": 2,
        "website_link": "",
        "welcome_message": f"Welcome to {creator_name}! Use /plans to see available plans.",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.settings.insert_one(settings_doc)

    # 4. Create a default plan for the creator
    plan_doc = {
        "id": str(uuid.uuid4()),
        "name": "Basic Plan",
        "price": 99,
        "duration_days": 30,
        "is_active": True,
        "features": ["Channel Access", "Exclusive Content"],
        "channel_id": channel_id,
        "tenant_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.plans.insert_one(plan_doc)

    logger.info(f"New creator onboarded: {creator_name} (tenant: {tenant_id})")

    tenant_doc.pop("_id", None)
    return {
        "success": True,
        "tenant_id": tenant_id,
        "bot_username": bot_info.get("bot_username", ""),
        "miniapp_url": f"/miniapp?tenant={tenant_id}",
        "tenant": {
            "id": tenant_doc["id"],
            "tenant_id": tenant_id,
            "name": creator_name,
            "bot_username": bot_info.get("bot_username", ""),
            "status": "active",
        }
    }


@router.get("/dashboard/{tenant_id}")
async def get_creator_dashboard(tenant_id: str, user: dict = Depends(get_current_user)):
    """Get full dashboard data for a creator's tenant — requires auth"""
    await _verify_tenant_access(user, tenant_id)
    
    tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Stats
    total_subs = await db.subscribers.count_documents({"tenant_id": tenant_id})
    active_subs = await db.subscribers.count_documents({"tenant_id": tenant_id, "status": "active"})
    pending_pay = await db.payments.count_documents({"tenant_id": tenant_id, "status": "pending"})
    total_users = await db.bot_users.count_documents({"tenant_id": tenant_id})

    # Revenue
    pipeline = [
        {"$match": {"tenant_id": tenant_id, "status": {"$in": ["verified", "approved"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    rev = await db.payments.aggregate(pipeline).to_list(1)
    total_revenue = rev[0]["total"] if rev else 0

    # Plans
    plans = await db.plans.find({"tenant_id": tenant_id}, {"_id": 0}).to_list(50)

    # Recent payments
    recent_payments = await db.payments.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(10)

    # Live sessions
    live_sessions = await db.live_sessions.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(10)

    # Settings (remove secrets from response)
    settings = await db.settings.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if settings:
        settings.pop("razorpay_key_secret", None)
        settings.pop("telegram_bot_token", None)

    return {
        "tenant": {
            "tenant_id": tenant.get("tenant_id"),
            "name": tenant.get("name"),
            "email": tenant.get("email"),
            "bot_username": tenant.get("bot_username", ""),
            "status": tenant.get("status"),
            "created_at": tenant.get("created_at"),
        },
        "stats": {
            "total_subscribers": total_subs,
            "active_subscribers": active_subs,
            "pending_payments": pending_pay,
            "total_users": total_users,
            "total_revenue": total_revenue,
        },
        "plans": plans,
        "recent_payments": recent_payments,
        "live_sessions": live_sessions,
        "settings": settings,
    }


@router.put("/settings/{tenant_id}")
async def update_creator_settings(tenant_id: str, data: dict, user: dict = Depends(get_current_user)):
    """Update creator's bot settings — requires auth + tenant access"""
    await _verify_tenant_access(user, tenant_id)
    
    tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    update_fields = {}
    allowed = ["upi_id", "channel_id", "welcome_message", "website_link", "grace_period_days"]
    for key in allowed:
        if key in data:
            update_fields[key] = data[key]

    # Handle bot token update (re-validate)
    if "bot_token" in data and data["bot_token"].strip():
        new_token = data["bot_token"].strip()
        bot_info = await _validate_bot_token(new_token)
        if not bot_info.get("valid"):
            raise HTTPException(status_code=400, detail=f"Invalid bot token: {bot_info.get('error')}")
        update_fields["telegram_bot_token"] = new_token
        # Also update tenant doc
        await db.tenants.update_one(
            {"tenant_id": tenant_id},
            {"$set": {"bot_token": new_token, "bot_username": bot_info.get("bot_username", "")}}
        )

    # Handle UPI update on tenant doc too
    if "upi_id" in data:
        update_fields["payment_upi_id"] = data["upi_id"]
        await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": {"upi_id": data["upi_id"]}})

    # Handle Razorpay keys
    if "razorpay_key_id" in data:
        update_fields["razorpay_key_id"] = data["razorpay_key_id"]
        await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": {"razorpay_key_id": data["razorpay_key_id"]}})
    if "razorpay_key_secret" in data:
        update_fields["razorpay_key_secret"] = data["razorpay_key_secret"]
        await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": {"razorpay_key_secret": data["razorpay_key_secret"]}})

    if "channel_id" in data:
        await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": {"channel_id": data["channel_id"]}})

    if update_fields:
        await db.settings.update_one(
            {"tenant_id": tenant_id},
            {"$set": update_fields}
        )

    return {"success": True, "updated": list(update_fields.keys())}


@router.post("/plans/{tenant_id}")
async def create_tenant_plan(tenant_id: str, data: dict, user: dict = Depends(get_current_user)):
    """Create a new plan for a tenant — requires auth"""
    await _verify_tenant_access(user, tenant_id)
    
    tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    plan = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", "New Plan"),
        "price": data.get("price", 99),
        "duration_days": data.get("duration_days", 30),
        "is_active": True,
        "features": data.get("features", []),
        "channel_id": data.get("channel_id", tenant.get("channel_id", "")),
        "tenant_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.plans.insert_one(plan)
    plan.pop("_id", None)
    return {"success": True, "plan": plan}


@router.delete("/plans/{tenant_id}/{plan_id}")
async def delete_tenant_plan(tenant_id: str, plan_id: str, user: dict = Depends(get_current_user)):
    """Delete a plan for a tenant — requires auth"""
    await _verify_tenant_access(user, tenant_id)
    result = await db.plans.delete_one({"id": plan_id, "tenant_id": tenant_id})
    return {"success": result.deleted_count > 0}


@router.get("/lookup/{bot_username}")
async def lookup_tenant_by_bot(bot_username: str):
    """Find a tenant by their bot username (for Mini App URL resolution)"""
    tenant = await db.tenants.find_one(
        {"bot_username": bot_username, "status": "active"},
        {"_id": 0, "tenant_id": 1, "name": 1, "bot_username": 1}
    )
    if not tenant:
        return {"found": False}
    return {"found": True, "tenant_id": tenant["tenant_id"], "name": tenant.get("name", "")}
