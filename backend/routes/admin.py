"""Dashboard subscription, Super admin management routes"""
from fastapi import APIRouter, HTTPException, Depends, Request
from database import db
from services.auth import get_current_user, hash_password
from services.permissions import ensure_super_admin, is_super_admin, get_user_tenant
from services.audit import log_action
from config import logger, RAZORPAY_KEY_ID, razorpay_client, DASHBOARD_PLANS, SUPER_ADMIN_EMAILS
from models import User
from datetime import datetime, timezone, timedelta
import uuid
import bcrypt

router = APIRouter()


# ============== TRIAL MANAGEMENT SYSTEM ==============

DEFAULT_TRIAL_CONFIG = {
    "id": "default_trial",
    "enabled": True,
    "duration_days": 7,
    "auto_activate_on_register": True,
    "features": ["Subscription Management", "Payment Verification", "Broadcasts", "Analytics"],
    "max_subscribers_trial": 50,
    "max_broadcasts_trial": 5,
    "trial_plan_name": "Free Trial",
    "show_upgrade_banner": True,
    "auto_expire_action": "deactivate",
    "updated_at": datetime.now(timezone.utc).isoformat(),
}

async def get_trial_config():
    """Get trial configuration from DB, init if missing"""
    cfg = await db.trial_config.find_one({"id": "default_trial"}, {"_id": 0})
    if not cfg:
        await db.trial_config.insert_one(DEFAULT_TRIAL_CONFIG.copy())
        cfg = DEFAULT_TRIAL_CONFIG.copy()
    return cfg

@router.get("/trial/config")
async def get_trial_config_api(user: dict = Depends(get_current_user)):
    """Get current trial settings"""
    await verify_super_admin(user)
    return await get_trial_config()

@router.put("/trial/config")
async def update_trial_config(data: dict, user: dict = Depends(get_current_user)):
    """Update trial configuration"""
    await verify_super_admin(user)
    
    allowed = ["enabled", "duration_days", "auto_activate_on_register", "features",
               "max_subscribers_trial", "max_broadcasts_trial", "trial_plan_name",
               "show_upgrade_banner", "auto_expire_action"]
    update = {k: v for k, v in data.items() if k in allowed}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.trial_config.update_one(
        {"id": "default_trial"},
        {"$set": update},
        upsert=True
    )
    await log_action("platform", user["id"], user.get("email", ""), "update_trial_config", "trial", "default_trial", update)
    return {"message": "Trial config updated", **update}

@router.get("/trial/accounts")
async def get_trial_accounts(user: dict = Depends(get_current_user)):
    """Get all users currently on trial"""
    await verify_super_admin(user)
    trials = await db.users.find(
        {"dashboard_subscription_status": "trial"},
        {"_id": 0, "password_hash": 0, "password": 0}
    ).to_list(500)
    
    now = datetime.now(timezone.utc)
    for t in trials:
        end = t.get("dashboard_subscription_end")
        if end:
            if isinstance(end, str):
                end = datetime.fromisoformat(end)
            t["days_remaining"] = max(0, (end - now).days)
            t["is_expired"] = now > end
        else:
            t["days_remaining"] = 0
            t["is_expired"] = True
        # Enrich with tenant name
        tid = t.get("tenant_id")
        if tid:
            tn = await db.tenants.find_one({"tenant_id": tid}, {"_id": 0, "name": 1})
            t["tenant_name"] = tn.get("name", "") if tn else ""
        else:
            t["tenant_name"] = ""
    return trials

@router.post("/trial/activate")
async def activate_trial(data: dict, user: dict = Depends(get_current_user)):
    """Manually activate trial for a user"""
    await verify_super_admin(user)
    
    user_id = data.get("user_id")
    duration_days = data.get("duration_days")
    
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get trial config for default duration if not specified
    if not duration_days:
        cfg = await get_trial_config()
        duration_days = cfg.get("duration_days", 7)
    
    end_date = datetime.now(timezone.utc) + timedelta(days=duration_days)
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "dashboard_subscription_status": "trial",
            "dashboard_plan": "trial",
            "dashboard_subscription_end": end_date.isoformat(),
            "trial_started_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    
    await log_action("platform", user["id"], user.get("email", ""), "activate_trial", "user", user_id, {"duration_days": duration_days})
    return {"message": f"Trial activated for {duration_days} days", "expires": end_date.isoformat()}

@router.post("/trial/extend")
async def extend_trial(data: dict, user: dict = Depends(get_current_user)):
    """Extend a user's trial period"""
    await verify_super_admin(user)
    
    user_id = data.get("user_id")
    extra_days = data.get("extra_days", 7)
    
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    current_end = target.get("dashboard_subscription_end")
    if current_end and isinstance(current_end, str):
        current_end = datetime.fromisoformat(current_end)
    
    base = max(current_end or datetime.now(timezone.utc), datetime.now(timezone.utc))
    new_end = base + timedelta(days=extra_days)
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "dashboard_subscription_status": "trial",
            "dashboard_subscription_end": new_end.isoformat(),
        }}
    )
    
    await log_action("platform", user["id"], user.get("email", ""), "extend_trial", "user", user_id, {"extra_days": extra_days})
    return {"message": f"Trial extended by {extra_days} days", "new_end": new_end.isoformat()}

@router.post("/trial/cancel")
async def cancel_trial(data: dict, user: dict = Depends(get_current_user)):
    """Cancel a user's trial"""
    await verify_super_admin(user)
    
    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "dashboard_subscription_status": "inactive",
            "dashboard_plan": "",
        }}
    )
    
    await log_action("platform", user["id"], user.get("email", ""), "cancel_trial", "user", user_id, {})
    return {"message": "Trial cancelled"}

@router.post("/trial/convert")
async def convert_trial_to_paid(data: dict, user: dict = Depends(get_current_user)):
    """Convert trial account to paid subscription"""
    await verify_super_admin(user)
    
    user_id = data.get("user_id")
    plan_id = data.get("plan_id")
    duration_days = data.get("duration_days", 30)
    
    if not user_id or not plan_id:
        raise HTTPException(status_code=400, detail="user_id and plan_id required")
    
    end_date = datetime.now(timezone.utc) + timedelta(days=duration_days)
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "dashboard_subscription_status": "active",
            "dashboard_plan": plan_id,
            "dashboard_subscription_end": end_date.isoformat(),
            "trial_converted_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    
    sub_record = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "plan_id": plan_id,
        "status": "approved",
        "source": "trial_conversion",
        "assigned_by": user["id"],
        "duration_days": duration_days,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.dashboard_subscriptions.insert_one(sub_record)
    
    await log_action("platform", user["id"], user.get("email", ""), "convert_trial", "user", user_id, {"plan_id": plan_id})
    return {"message": "Trial converted to paid subscription"}



async def verify_super_admin(user: dict):
    """Verify user is a REAL super admin. Strict check — role-based only."""
    ensure_super_admin(user)

# ============== DASHBOARD SUBSCRIPTION ROUTES ==============

# Default dashboard plans (will be stored in DB)
DEFAULT_DASHBOARD_PLANS = [
    {"id": "1month", "name": "1 Month", "price": 4999, "duration_days": 30, "popular": False, "save": "", "contact": False, "is_active": True},
    {"id": "6month", "name": "6 Months", "price": 24999, "duration_days": 180, "popular": True, "save": "17%", "contact": False, "is_active": True},
    {"id": "12month", "name": "12 Months", "price": 44999, "duration_days": 365, "popular": False, "save": "25%", "contact": False, "is_active": True},
    {"id": "lifetime", "name": "Lifetime", "price": 0, "duration_days": 36500, "popular": False, "save": "", "contact": True, "is_active": True}
]

async def get_dashboard_plans_from_db():
    """Get dashboard plans from database, initialize if empty"""
    plans = await db.dashboard_plans.find({}, {"_id": 0}).to_list(100)
    if not plans:
        # Initialize with defaults
        for plan in DEFAULT_DASHBOARD_PLANS:
            await db.dashboard_plans.insert_one(plan)
        plans = DEFAULT_DASHBOARD_PLANS
    return plans

@router.get("/dashboard-plans")
async def get_dashboard_plans():
    """Get available dashboard subscription plans"""
    plans = await get_dashboard_plans_from_db()
    # Format for frontend
    formatted = []
    for p in plans:
        if p.get("is_active", True):
            formatted.append({
                "id": p["id"],
                "name": p["name"],
                "price": p["price"],
                "duration": f"{p.get('duration_days', 30)} days" if p["id"] != "lifetime" else "Forever",
                "popular": p.get("popular", False),
                "save": p.get("save", ""),
                "contact": p.get("contact", False)
            })
    return {"plans": formatted}

@router.get("/admin/dashboard-plans")
async def get_admin_dashboard_plans(user = Depends(get_current_user)):
    """Get all dashboard plans for editing (super admin only)"""
    await verify_super_admin(user)
    plans = await get_dashboard_plans_from_db()
    return plans

@router.put("/admin/dashboard-plans/{plan_id}")
async def update_dashboard_plan(plan_id: str, data: dict, user = Depends(get_current_user)):
    """Update a dashboard plan (super admin only)"""
    await verify_super_admin(user)
    
    existing = await db.dashboard_plans.find_one({"id": plan_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    update_data = {
        "name": data.get("name", existing["name"]),
        "price": data.get("price", existing["price"]),
        "duration_days": data.get("duration_days", existing.get("duration_days", 30)),
        "popular": data.get("popular", existing.get("popular", False)),
        "save": data.get("save", existing.get("save", "")),
        "contact": data.get("contact", existing.get("contact", False)),
        "is_active": data.get("is_active", existing.get("is_active", True))
    }
    
    await db.dashboard_plans.update_one({"id": plan_id}, {"$set": update_data})
    
    # Also update DASHBOARD_PLANS dict for subscription approval
    global DASHBOARD_PLANS
    DASHBOARD_PLANS[plan_id] = {
        "name": update_data["name"],
        "price": update_data["price"],
        "days": update_data["duration_days"]
    }
    
    return {"message": "Plan updated"}

@router.post("/dashboard-subscription/request")
async def request_dashboard_subscription(data: dict, user = Depends(get_current_user)):
    """Request dashboard subscription - creates pending request"""
    plan_id = data.get("plan_id")
    
    # Get plan from database
    plans = await get_dashboard_plans_from_db()
    plan_info = next((p for p in plans if p["id"] == plan_id), None)
    
    if not plan_info:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    # Create subscription request
    request_obj = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_email": user["email"],
        "user_name": user["name"],
        "plan_id": plan_id,
        "plan_name": plan_info.get("name", ""),
        "amount": plan_info.get("price", 0),
        "status": "pending",  # pending, approved, rejected
        "screenshot_url": data.get("screenshot_url", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.dashboard_subscriptions.insert_one(request_obj)
    
    return {"message": "Subscription request submitted", "request_id": request_obj["id"]}

@router.post("/dashboard-subscription/create-order")
async def create_dashboard_razorpay_order(data: dict, user = Depends(get_current_user)):
    """Create Razorpay order for dashboard subscription"""
    if not razorpay_client:
        raise HTTPException(status_code=400, detail="Razorpay not configured")
    
    plan_id = data.get("plan_id")
    
    # Get plan from database
    plans = await get_dashboard_plans_from_db()
    plan_info = next((p for p in plans if p["id"] == plan_id), None)
    
    if not plan_info:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    amount = plan_info.get("price", 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid plan price")
    
    # Create Razorpay order
    order = razorpay_client.order.create({
        "amount": int(amount * 100),  # Convert to paise
        "currency": "INR",
        "payment_capture": 1,
        "notes": {
            "user_id": user["id"],
            "user_email": user["email"],
            "plan_id": plan_id,
            "plan_name": plan_info.get("name", ""),
            "type": "dashboard_subscription"
        }
    })
    
    # Store order info
    order_obj = {
        "id": str(uuid.uuid4()),
        "razorpay_order_id": order["id"],
        "user_id": user["id"],
        "user_email": user["email"],
        "plan_id": plan_id,
        "plan_name": plan_info.get("name", ""),
        "amount": amount,
        "status": "created",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.dashboard_orders.insert_one(order_obj)
    
    return {
        "order_id": order["id"],
        "amount": amount,
        "currency": "INR",
        "key_id": RAZORPAY_KEY_ID
    }

@router.post("/dashboard-subscription/verify-payment")
async def verify_dashboard_razorpay_payment(data: dict, user = Depends(get_current_user)):
    """Verify Razorpay payment for dashboard subscription"""
    if not razorpay_client:
        raise HTTPException(status_code=400, detail="Razorpay not configured")
    
    try:
        # Verify signature
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Payment verification failed")
    
    # Get order
    order = await db.dashboard_orders.find_one({"razorpay_order_id": data['razorpay_order_id']}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Update order status
    await db.dashboard_orders.update_one(
        {"razorpay_order_id": data['razorpay_order_id']},
        {"$set": {"status": "paid", "razorpay_payment_id": data['razorpay_payment_id']}}
    )
    
    # Activate subscription
    plan_id = order["plan_id"]
    plans = await get_dashboard_plans_from_db()
    plan_info = next((p for p in plans if p["id"] == plan_id), None)
    
    if plan_info:
        duration_days = plan_info.get("duration_days", 30)
        end_date = datetime.now(timezone.utc) + timedelta(days=duration_days)
        
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {
                "dashboard_plan": plan_id,
                "dashboard_subscription_status": "active",
                "dashboard_subscription_end": end_date.isoformat()
            }}
        )
        
        # Update localStorage user data
        return {
            "message": "Payment verified and subscription activated!",
            "subscription": {
                "plan": plan_id,
                "plan_name": plan_info.get("name", ""),
                "status": "active",
                "end_date": end_date.isoformat()
            }
        }
    
    return {"message": "Payment verified but plan not found"}

@router.get("/auth/check-admin")
async def check_if_admin(user = Depends(get_current_user)):
    """Check if current user is admin/super_admin/tenant_admin"""
    role = user.get("role", "user")
    is_admin_user = role in ["admin", "super_admin", "tenant_admin"] or user.get("email") in SUPER_ADMIN_EMAILS
    return {"is_admin": is_admin_user, "role": role}

@router.get("/dashboard-subscription/requests")
async def get_subscription_requests(user = Depends(get_current_user)):
    """Get all subscription requests (super_admin sees all)"""
    role = user.get("role", "user")
    is_platform_admin = role == "super_admin" or user.get("email") in SUPER_ADMIN_EMAILS

    if is_platform_admin:
        requests = await db.dashboard_subscriptions.find({}, {"_id": 0}).to_list(100)
    else:
        requests = await db.dashboard_subscriptions.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
    return requests

@router.get("/tenant-users")
async def get_tenant_users(user = Depends(get_current_user)):
    """Get all registered tenant users with subscription details and platform stats"""
    await verify_super_admin(user)
    users = await db.users.find({}, {"_id": 0, "password": 0, "password_hash": 0}).to_list(500)

    # Get platform stats
    total_bot_users = await db.bot_users.count_documents({})
    total_subscribers = await db.subscribers.count_documents({})
    total_payments = await db.payments.count_documents({})

    for u in users:
        sub = await db.dashboard_subscriptions.find_one(
            {"user_id": u["id"], "status": "approved"},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        u["subscription"] = sub
        u["has_active_plan"] = u.get("dashboard_subscription_status") == "active"

    return {
        "users": users,
        "platform_stats": {
            "total_bot_users": total_bot_users,
            "total_subscribers": total_subscribers,
            "total_payments": total_payments
        }
    }


@router.get("/platform-users")
async def get_platform_users(user = Depends(get_current_user)):
    """Get all bot users (people who interacted with the Telegram bot)"""
    await verify_super_admin(user)

    bot_users = await db.bot_users.find({}, {"_id": 0}).to_list(1000)

    for bu in bot_users:
        # Check if this user has active subscription
        sub = await db.subscribers.find_one(
            {"telegram_user_id": bu.get("user_id"), "status": "active"},
            {"_id": 0}
        )
        bu["is_subscriber"] = sub is not None
        bu["plan_name"] = sub.get("plan_name", "") if sub else ""

        # Get payment count
        payment_count = await db.payments.count_documents({"telegram_user_id": bu.get("user_id")})
        bu["payment_count"] = payment_count

    return bot_users

# ============== SUPER ADMIN ROUTES ==============

@router.get("/admin/all-users")
async def get_all_users(user = Depends(get_current_user)):
    """Get all users with their subscription details (super admin only)"""
    await verify_super_admin(user)
    
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return users

@router.get("/admin/users")
async def get_admin_users(user = Depends(get_current_user)):
    """Get all admin/super_admin users for user management"""
    await verify_super_admin(user)
    
    # Get users who are admins or super admins
    users = await db.users.find(
        {"role": {"$in": ["admin", "super_admin"]}},
        {"_id": 0, "password_hash": 0}
    ).to_list(100)
    return users

@router.post("/admin/users")
async def create_admin_user(data: dict, user = Depends(get_current_user)):
    """Create a new admin/super_admin user (super admin only)"""
    await verify_super_admin(user)
    
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    name = data.get("name", "").strip()
    role = data.get("role", "admin")
    
    if not email or not password or not name:
        raise HTTPException(status_code=400, detail="Email, password and name are required")
    
    if role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    # Check if user already exists
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    
    # Hash password
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    new_user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": password_hash,
        "name": name,
        "role": role,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(new_user)
    logger.info(f"Created new {role} user: {email}")
    
    return {"message": "User created successfully", "id": new_user["id"]}

@router.put("/admin/users/{user_id}/role")
async def update_user_role(user_id: str, data: dict, user = Depends(get_current_user)):
    """Update user role (super admin only)"""
    await verify_super_admin(user)
    
    new_role = data.get("role", "")
    if new_role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    # Find user
    target_user = await db.users.find_one({"id": user_id})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update role
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"role": new_role}}
    )
    
    logger.info(f"Updated user {target_user.get('email')} role to {new_role}")
    return {"message": "Role updated successfully"}

@router.delete("/admin/users/{user_id}")
async def delete_admin_user(user_id: str, user = Depends(get_current_user)):
    """Delete a user (super admin only)"""
    await verify_super_admin(user)
    
    # Find user
    target_user = await db.users.find_one({"id": user_id})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent self-deletion
    if target_user.get("email") == user.get("email"):
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    # Delete user
    await db.users.delete_one({"id": user_id})
    
    logger.info(f"Deleted user: {target_user.get('email')}")
    return {"message": "User deleted successfully"}

@router.get("/admin/stats")
async def get_admin_stats(user = Depends(get_current_user)):
    """Comprehensive platform-level stats for Super Admin Control Center"""
    await verify_super_admin(user)

    # Core counts
    total_users = await db.users.count_documents({})
    total_tenants = await db.tenants.count_documents({})
    active_tenants = await db.tenants.count_documents({"status": "active"})
    total_tenant_admins = await db.users.count_documents({"role": "tenant_admin"})
    active_dash_subs = await db.users.count_documents({"dashboard_subscription_status": "active"})
    pending_requests = await db.dashboard_subscriptions.count_documents({"status": "pending"})

    # Bot-level stats across all tenants
    total_bot_users = await db.bot_users.count_documents({})
    total_subscribers = await db.subscribers.count_documents({})
    active_bot_subs = await db.subscribers.count_documents({"status": "active"})
    expired_bot_subs = await db.subscribers.count_documents({"status": "expired"})
    total_payments = await db.payments.count_documents({})
    pending_payments = await db.payments.count_documents({"status": "pending"})
    verified_payments = await db.payments.count_documents({"status": {"$in": ["verified", "approved"]}})

    # Trial stats
    trial_cfg = await get_trial_config()
    trial_users = await db.users.count_documents({"trial_end_date": {"$exists": True}})

    # Revenue — platform (dashboard subs)
    platform_rev_pipeline = [
        {"$match": {"status": "approved"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    platform_rev = await db.dashboard_subscriptions.aggregate(platform_rev_pipeline).to_list(1)
    platform_revenue = platform_rev[0]["total"] if platform_rev else 0

    # Revenue — all tenants (bot payments)
    tenant_rev_pipeline = [
        {"$match": {"status": {"$in": ["verified", "approved"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    tenant_rev = await db.payments.aggregate(tenant_rev_pipeline).to_list(1)
    total_tenant_revenue = tenant_rev[0]["total"] if tenant_rev else 0

    # Monthly revenue (last 30 days)
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    monthly_pipeline = [
        {"$match": {"status": {"$in": ["verified", "approved"]}, "created_at": {"$gte": thirty_days_ago}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    monthly_rev = await db.payments.aggregate(monthly_pipeline).to_list(1)
    monthly_revenue = monthly_rev[0]["total"] if monthly_rev else 0

    # Top tenants by revenue
    top_tenants_pipeline = [
        {"$match": {"status": {"$in": ["verified", "approved"]}}},
        {"$group": {"_id": "$tenant_id", "revenue": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        {"$sort": {"revenue": -1}},
        {"$limit": 5}
    ]
    top_tenants_raw = await db.payments.aggregate(top_tenants_pipeline).to_list(5)
    top_tenants = []
    for tr in top_tenants_raw:
        t = await db.tenants.find_one({"tenant_id": tr["_id"]}, {"_id": 0, "name": 1, "tenant_id": 1, "email": 1})
        top_tenants.append({
            "tenant_id": tr["_id"],
            "name": t.get("name", tr["_id"]) if t else tr["_id"],
            "email": t.get("email", "") if t else "",
            "revenue": tr["revenue"],
            "payment_count": tr["count"],
        })

    # Recent platform activity
    recent_tenants = await db.tenants.find({}, {"_id": 0, "name": 1, "tenant_id": 1, "status": 1, "created_at": 1, "email": 1}).sort("created_at", -1).to_list(5)
    recent_subs = await db.dashboard_subscriptions.find({}, {"_id": 0}).sort("created_at", -1).to_list(5)
    for s in recent_subs:
        u = await db.users.find_one({"id": s.get("user_id")}, {"_id": 0, "name": 1, "email": 1})
        s["user_name"] = u.get("name", "") if u else ""
        s["user_email"] = u.get("email", "") if u else ""

    # Revenue by day (last 14 days chart)
    fourteen_days_ago = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    daily_pipeline = [
        {"$match": {"status": {"$in": ["verified", "approved"]}, "created_at": {"$gte": fourteen_days_ago}}},
        {"$addFields": {"date_str": {"$substr": ["$created_at", 0, 10]}}},
        {"$group": {"_id": "$date_str", "revenue": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    daily_rev = await db.payments.aggregate(daily_pipeline).to_list(14)
    daily_chart = [{"date": d["_id"], "revenue": d["revenue"], "payments": d["count"]} for d in daily_rev]

    return {
        "platform": {
            "total_users": total_users,
            "total_tenants": total_tenants,
            "active_tenants": active_tenants,
            "total_tenant_admins": total_tenant_admins,
            "active_dash_subscriptions": active_dash_subs,
            "pending_requests": pending_requests,
            "platform_revenue": platform_revenue,
        },
        "bot_ecosystem": {
            "total_bot_users": total_bot_users,
            "total_subscribers": total_subscribers,
            "active_subscribers": active_bot_subs,
            "expired_subscribers": expired_bot_subs,
            "total_payments": total_payments,
            "pending_payments": pending_payments,
            "verified_payments": verified_payments,
        },
        "revenue": {
            "total_tenant_revenue": total_tenant_revenue,
            "monthly_revenue": monthly_revenue,
            "daily_chart": daily_chart,
        },
        "trials": {
            "enabled": trial_cfg.get("enabled", False),
            "duration_days": trial_cfg.get("duration_days", 7),
            "total_trial_users": trial_users,
        },
        "top_tenants": top_tenants,
        "recent_tenants": recent_tenants,
        "recent_subscriptions": recent_subs,
    }


@router.get("/admin/tenant-profile/{tenant_id}")
async def get_tenant_profile(tenant_id: str, user = Depends(get_current_user)):
    """Get comprehensive profile data for a specific tenant"""
    await verify_super_admin(user)

    tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Dashboard admin users for this tenant
    dashboard_admins = await db.users.find(
        {"tenant_id": tenant_id, "role": "tenant_admin"},
        {"_id": 0, "password": 0, "password_hash": 0}
    ).to_list(50)

    # Telegram admins
    tg_admins = await db.telegram_admins.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).to_list(50)

    # Plans
    plans = await db.plans.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).to_list(100)

    # Subscribers
    subscribers = await db.subscribers.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    active_subs = sum(1 for s in subscribers if s.get("status") == "active")
    expired_subs = sum(1 for s in subscribers if s.get("status") == "expired")

    # Payments
    payments = await db.payments.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    total_payments = len(payments)
    verified_payments = sum(1 for p in payments if p.get("status") in ("verified", "approved"))
    pending_payments = sum(1 for p in payments if p.get("status") == "pending")

    # Revenue
    rev_pipeline = [
        {"$match": {"tenant_id": tenant_id, "status": {"$in": ["verified", "approved"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    rev = await db.payments.aggregate(rev_pipeline).to_list(1)
    total_revenue = rev[0]["total"] if rev else 0

    # Monthly revenue
    thirty_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    monthly_pipeline = [
        {"$match": {"tenant_id": tenant_id, "status": {"$in": ["verified", "approved"]}, "created_at": {"$gte": thirty_ago}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    monthly_rev = await db.payments.aggregate(monthly_pipeline).to_list(1)
    monthly_revenue = monthly_rev[0]["total"] if monthly_rev else 0

    # Bot users
    bot_users_count = await db.bot_users.count_documents({"tenant_id": tenant_id})

    # Broadcasts
    broadcasts = await db.broadcasts.count_documents({"tenant_id": tenant_id})

    # Revenue chart (last 30 days)
    daily_pipeline = [
        {"$match": {"tenant_id": tenant_id, "status": {"$in": ["verified", "approved"]}, "created_at": {"$gte": thirty_ago}}},
        {"$addFields": {"date_str": {"$substr": ["$created_at", 0, 10]}}},
        {"$group": {"_id": "$date_str", "revenue": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    daily_rev = await db.payments.aggregate(daily_pipeline).to_list(30)
    revenue_chart = [{"date": d["_id"], "revenue": d["revenue"], "payments": d["count"]} for d in daily_rev]

    # Plan distribution
    plan_dist = []
    for p in plans:
        count = sum(1 for s in subscribers if s.get("plan_id") == p.get("id"))
        plan_dist.append({"name": p.get("name", ""), "count": count, "price": p.get("price", 0)})

    return {
        "tenant": tenant,
        "stats": {
            "total_revenue": total_revenue,
            "monthly_revenue": monthly_revenue,
            "bot_users": bot_users_count,
            "total_subscribers": len(subscribers),
            "active_subscribers": active_subs,
            "expired_subscribers": expired_subs,
            "total_payments": total_payments,
            "verified_payments": verified_payments,
            "pending_payments": pending_payments,
            "total_plans": len(plans),
            "total_broadcasts": broadcasts,
        },
        "dashboard_admins": dashboard_admins,
        "telegram_admins": tg_admins,
        "plans": plans,
        "subscribers": subscribers[:50],
        "recent_payments": payments[:20],
        "revenue_chart": revenue_chart,
        "plan_distribution": plan_dist,
    }

@router.get("/admin/subscription-requests")
async def get_all_subscription_requests(user = Depends(get_current_user)):
    """Get all subscription requests (super admin only)"""
    await verify_super_admin(user)
    
    requests = await db.dashboard_subscriptions.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return requests

@router.put("/admin/reject-subscription/{request_id}")
async def reject_subscription_request(request_id: str, user = Depends(get_current_user)):
    """Reject subscription request (super admin only)"""
    await verify_super_admin(user)
    
    request = await db.dashboard_subscriptions.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    await db.dashboard_subscriptions.update_one(
        {"id": request_id},
        {"$set": {"status": "rejected", "rejected_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": "Subscription request rejected"}

@router.put("/admin/set-lifetime/{user_id}")
async def set_user_lifetime(user_id: str, user = Depends(get_current_user)):
    """Grant lifetime access to a user (super admin only)"""
    await verify_super_admin(user)
    
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Set lifetime - 100 years from now
    lifetime_end = datetime.now(timezone.utc) + timedelta(days=36500)
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "dashboard_plan": "lifetime",
            "dashboard_subscription_status": "active",
            "dashboard_subscription_end": lifetime_end.isoformat()
        }}
    )
    
    return {"message": "Lifetime access granted"}

@router.put("/admin/revoke-access/{user_id}")
async def revoke_user_access(user_id: str, user = Depends(get_current_user)):
    """Revoke user's dashboard access (super admin only)"""
    await verify_super_admin(user)
    
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Don't allow revoking super admin's own access
    if target_user.get("email") in SUPER_ADMIN_EMAILS:
        raise HTTPException(status_code=400, detail="Cannot revoke super admin's access")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "dashboard_subscription_status": "inactive",
            "dashboard_plan": ""
        }}
    )
    
    return {"message": "Access revoked"}

@router.put("/admin/make-admin/{user_id}")
async def make_user_admin(user_id: str, user = Depends(get_current_user)):
    """Make a user an admin (super admin only)"""
    await verify_super_admin(user)
    
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if target_user.get("email") in SUPER_ADMIN_EMAILS:
        raise HTTPException(status_code=400, detail="Cannot modify super admin")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"role": "admin", "is_admin": True}}
    )
    
    return {"message": "User is now an admin"}

@router.put("/admin/remove-admin/{user_id}")
async def remove_user_admin(user_id: str, user = Depends(get_current_user)):
    """Remove admin status from a user (super admin only)"""
    await verify_super_admin(user)
    
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if target_user.get("email") in SUPER_ADMIN_EMAILS:
        raise HTTPException(status_code=400, detail="Cannot modify super admin")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"role": "user", "is_admin": False}}
    )
    
    return {"message": "Admin status removed"}

@router.put("/admin/change-subscription/{user_id}")
async def change_user_subscription(user_id: str, data: dict, user = Depends(get_current_user)):
    """Change a user's subscription plan (super admin only)"""
    await verify_super_admin(user)
    
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    plan_id = data.get("plan_id")
    if plan_id not in DASHBOARD_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    plan_info = DASHBOARD_PLANS.get(plan_id, {})
    days = plan_info.get("days", 30)
    end_date = datetime.now(timezone.utc) + timedelta(days=days)
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "dashboard_plan": plan_id,
            "dashboard_subscription_status": "active",
            "dashboard_subscription_end": end_date.isoformat()
        }}
    )
    
    return {"message": f"Subscription changed to {plan_info.get('name', plan_id)}"}

@router.put("/dashboard-subscription/approve/{request_id}")
async def approve_subscription(request_id: str, user = Depends(get_current_user)):
    """Approve subscription request (admin only)"""
    # Check if admin (first user) or super admin
    is_super_admin = user.get("role") == "super_admin" or user.get("email") in SUPER_ADMIN_EMAILS
    
    if not is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin access required")
    
    request = await db.dashboard_subscriptions.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    plan_id = request["plan_id"]
    plan_info = DASHBOARD_PLANS.get(plan_id, {})
    days = plan_info.get("days", 30)
    
    end_date = datetime.now(timezone.utc) + timedelta(days=days)
    
    # Update user subscription
    await db.users.update_one(
        {"id": request["user_id"]},
        {"$set": {
            "dashboard_plan": plan_id,
            "dashboard_subscription_status": "active",
            "dashboard_subscription_end": end_date.isoformat()
        }}
    )
    
    # Update request status
    await db.dashboard_subscriptions.update_one(
        {"id": request_id},
        {"$set": {"status": "approved", "approved_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": "Subscription approved"}


# ============== SUBSCRIPTION MANAGEMENT (SUPER ADMIN) ==============

@router.get("/saas/subscriptions")
async def get_all_subscriptions(user: dict = Depends(get_current_user)):
    """Get all dashboard subscriptions with user info"""
    await verify_super_admin(user)
    subs = await db.dashboard_subscriptions.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    # Enrich with user info
    for s in subs:
        u = await db.users.find_one({"id": s.get("user_id")}, {"_id": 0, "name": 1, "email": 1, "role": 1, "tenant_id": 1, "dashboard_plan": 1, "dashboard_subscription_status": 1, "dashboard_subscription_end": 1})
        if u:
            s["user_name"] = u.get("name", "")
            s["user_email"] = u.get("email", "")
            s["user_role"] = u.get("role", "")
            s["tenant_id"] = u.get("tenant_id", "")
            s["current_plan"] = u.get("dashboard_plan", "")
            s["current_status"] = u.get("dashboard_subscription_status", "")
            s["subscription_end"] = u.get("dashboard_subscription_end", "")
    return subs

@router.post("/saas/assign-subscription")
async def assign_subscription_to_user(data: dict, user: dict = Depends(get_current_user)):
    """Directly assign a dashboard subscription to a user (Super Admin only)"""
    await verify_super_admin(user)
    
    user_id = data.get("user_id")
    plan_id = data.get("plan_id")
    duration_days = data.get("duration_days", 30)
    
    if not user_id or not plan_id:
        raise HTTPException(status_code=400, detail="user_id and plan_id required")
    
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    end_date = datetime.now(timezone.utc) + timedelta(days=duration_days)
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "dashboard_plan": plan_id,
            "dashboard_subscription_status": "active",
            "dashboard_subscription_end": end_date.isoformat()
        }}
    )
    
    # Create subscription record
    sub_record = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "plan_id": plan_id,
        "status": "approved",
        "assigned_by": user["id"],
        "duration_days": duration_days,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.dashboard_subscriptions.insert_one(sub_record)
    
    await log_action("platform", user["id"], user.get("email", ""), "assign_subscription", "user", user_id, {"plan_id": plan_id, "duration_days": duration_days})
    
    return {"message": f"Subscription assigned to {target.get('email', user_id)}"}

@router.delete("/saas/subscriptions/{sub_id}")
async def delete_subscription(sub_id: str, user: dict = Depends(get_current_user)):
    """Delete a subscription record"""
    await verify_super_admin(user)
    result = await db.dashboard_subscriptions.delete_one({"id": sub_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"message": "Subscription deleted"}

@router.get("/saas/tenant-admins")
async def get_all_tenant_admins(user: dict = Depends(get_current_user)):
    """Get ALL tenant admins across all tenants with subscription info"""
    await verify_super_admin(user)
    admins = await db.users.find(
        {"role": "tenant_admin"},
        {"_id": 0, "password": 0}
    ).to_list(500)
    # Enrich with tenant name
    for a in admins:
        t = await db.tenants.find_one({"tenant_id": a.get("tenant_id")}, {"_id": 0, "name": 1})
        a["tenant_name"] = t.get("name", "") if t else ""
    return admins

@router.put("/saas/tenant-admins/{admin_id}")
async def update_tenant_admin(admin_id: str, data: dict, user: dict = Depends(get_current_user)):
    """Update a tenant admin's details"""
    await verify_super_admin(user)
    
    update = {}
    for field in ["name", "email", "tenant_id"]:
        if field in data:
            update[field] = data[field]
    
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    result = await db.users.update_one({"id": admin_id, "role": "tenant_admin"}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tenant admin not found")
    return {"message": "Tenant admin updated"}

@router.delete("/saas/tenant-admins/{admin_id}")
async def delete_tenant_admin_direct(admin_id: str, user: dict = Depends(get_current_user)):
    """Delete a tenant admin user"""
    await verify_super_admin(user)
    result = await db.users.delete_one({"id": admin_id, "role": "tenant_admin"})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tenant admin not found")
    return {"message": "Tenant admin deleted"}

@router.post("/saas/tenant-admins")
async def create_tenant_admin_direct(data: dict, user: dict = Depends(get_current_user)):
    """Create a new tenant admin directly with tenant assignment"""
    await verify_super_admin(user)
    
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    name = data.get("name", "").strip()
    tenant_id = data.get("tenant_id", "").strip()
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    import bcrypt
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    new_user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": name,
        "password": hashed,
        "role": "tenant_admin",
        "tenant_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dashboard_subscription_status": "inactive",
    }
    await db.users.insert_one(new_user)
    
    return {"message": f"Tenant admin created: {email}", "user_id": new_user["id"]}



# ============== PLANS ROUTES ==============



# ============== MINI APP USERS ==============

@router.get("/miniapp-users")
async def get_miniapp_users(user: dict = Depends(get_current_user)):
    """Get all phone numbers collected from Mini App"""
    users = await db.miniapp_users.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return users


@router.get("/miniapp-users/stats")
async def get_miniapp_users_stats(user: dict = Depends(get_current_user)):
    """Get Mini App user stats"""
    total = await db.miniapp_users.count_documents({})
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = await db.miniapp_users.count_documents({"created_at": {"$gte": today.isoformat()}})
    return {"total": total, "today": today_count}


# ============== SAAS MANAGEMENT - BOT SUBSCRIPTION PLANS ==============

@router.get("/saas/bot-plans")
async def get_bot_plans(user: dict = Depends(get_current_user)):
    """Get all bot subscription plans with features"""
    await verify_super_admin(user)
    plans = await db.bot_subscription_plans.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return plans


@router.post("/saas/bot-plans")
async def create_bot_plan(data: dict, user: dict = Depends(get_current_user)):
    """Create a new bot subscription plan"""
    await verify_super_admin(user)

    plan = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", "New Plan"),
        "price": data.get("price", 0),
        "duration_days": data.get("duration_days", 30),
        "features": data.get("features", []),
        "max_subscribers": data.get("max_subscribers", 500),
        "max_broadcasts": data.get("max_broadcasts", 10),
        "ai_verify_enabled": data.get("ai_verify_enabled", True),
        "live_stream_enabled": data.get("live_stream_enabled", True),
        "paid_posts_enabled": data.get("paid_posts_enabled", True),
        "is_active": True,
        "is_popular": data.get("is_popular", False),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.bot_subscription_plans.insert_one(plan)
    del plan["_id"]
    return plan


@router.put("/saas/bot-plans/{plan_id}")
async def update_bot_plan(plan_id: str, data: dict, user: dict = Depends(get_current_user)):
    """Update a bot subscription plan"""
    await verify_super_admin(user)

    existing = await db.bot_subscription_plans.find_one({"id": plan_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")

    update_fields = {}
    allowed = ["name", "price", "duration_days", "features", "max_subscribers",
               "max_broadcasts", "ai_verify_enabled", "live_stream_enabled",
               "paid_posts_enabled", "is_active", "is_popular"]
    for key in allowed:
        if key in data:
            update_fields[key] = data[key]

    if update_fields:
        await db.bot_subscription_plans.update_one({"id": plan_id}, {"$set": update_fields})

    updated = await db.bot_subscription_plans.find_one({"id": plan_id}, {"_id": 0})
    return updated


@router.delete("/saas/bot-plans/{plan_id}")
async def delete_bot_plan(plan_id: str, user: dict = Depends(get_current_user)):
    """Delete a bot subscription plan"""
    await verify_super_admin(user)
    result = await db.bot_subscription_plans.delete_one({"id": plan_id})
    return {"success": result.deleted_count > 0}


# ============== SAAS MANAGEMENT - TENANT CRUD ==============

@router.get("/saas/tenants")
async def get_all_tenants(user: dict = Depends(get_current_user)):
    """Get all tenants with stats"""
    await verify_super_admin(user)

    tenants = await db.tenants.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)

    # Enrich with stats
    for t in tenants:
        tid = t.get("tenant_id", "")
        t["stats"] = {
            "total_users": await db.bot_users.count_documents({"tenant_id": tid}),
            "active_subs": await db.subscribers.count_documents({"tenant_id": tid, "status": "active"}),
            "total_payments": await db.payments.count_documents({"tenant_id": tid}),
        }
        # Revenue
        pipeline = [
            {"$match": {"tenant_id": tid, "status": {"$in": ["verified", "approved"]}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        rev = await db.payments.aggregate(pipeline).to_list(1)
        t["stats"]["revenue"] = rev[0]["total"] if rev else 0

        # Get admins
        admins = await db.telegram_admins.find(
            {"tenant_id": tid, "is_active": True}, {"_id": 0}
        ).to_list(20)
        t["admins"] = admins

    return tenants


@router.post("/saas/tenants")
async def create_tenant_admin(data: dict, user: dict = Depends(get_current_user)):
    """Create a new tenant from super admin"""
    await verify_super_admin(user)

    tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"
    tenant = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "name": data.get("name", ""),
        "email": data.get("email", ""),
        "owner_telegram_id": data.get("owner_telegram_id", ""),
        "bot_token": data.get("bot_token", ""),
        "bot_username": data.get("bot_username", ""),
        "upi_id": data.get("upi_id", ""),
        "channel_id": data.get("channel_id", ""),
        "razorpay_key_id": data.get("razorpay_key_id", ""),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.tenants.insert_one(tenant)
    del tenant["_id"]
    return tenant


@router.put("/saas/tenants/{tenant_id}")
async def update_tenant_admin(tenant_id: str, data: dict, user: dict = Depends(get_current_user)):
    """Update a tenant"""
    await verify_super_admin(user)

    allowed = ["name", "email", "bot_token", "bot_username", "upi_id",
               "channel_id", "razorpay_key_id", "status"]
    update_fields = {k: data[k] for k in allowed if k in data}

    if update_fields:
        await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": update_fields})

    updated = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
    return updated


@router.delete("/saas/tenants/{tenant_id}")
async def delete_tenant_admin(tenant_id: str, user: dict = Depends(get_current_user)):
    """Deactivate/delete a tenant"""
    await verify_super_admin(user)
    result = await db.tenants.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"status": "inactive"}}
    )
    return {"success": result.modified_count > 0}


# ============== TENANT ADMIN ASSIGNMENT ==============

@router.get("/saas/tenants/{tenant_id}/admins")
async def get_tenant_admins(tenant_id: str, user: dict = Depends(get_current_user)):
    """Get admins for a specific tenant"""
    await verify_super_admin(user)
    admins = await db.telegram_admins.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).to_list(50)
    return admins


@router.post("/saas/tenants/{tenant_id}/admins")
async def assign_tenant_admin(tenant_id: str, data: dict, user: dict = Depends(get_current_user)):
    """Assign a new admin to a tenant"""
    await verify_super_admin(user)

    telegram_user_id = str(data.get("telegram_user_id", "")).strip()
    if not telegram_user_id:
        raise HTTPException(status_code=400, detail="Telegram User ID required")

    # Check if already admin for this tenant
    existing = await db.telegram_admins.find_one(
        {"telegram_user_id": telegram_user_id, "tenant_id": tenant_id},
        {"_id": 0}
    )
    if existing:
        raise HTTPException(status_code=409, detail="Already an admin for this tenant")

    admin_doc = {
        "id": str(uuid.uuid4()),
        "telegram_user_id": telegram_user_id,
        "name": data.get("name", "Admin"),
        "email": data.get("email", ""),
        "role": data.get("role", "admin"),
        "is_active": True,
        "permissions": data.get("permissions", [
            "manage_bot", "verify_payments", "broadcast",
            "live_streams", "super_chats", "add_subscribers"
        ]),
        "tenant_id": tenant_id,
        "assigned_by": user.get("email", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.telegram_admins.insert_one(admin_doc)
    del admin_doc["_id"]
    return admin_doc


@router.delete("/saas/tenants/{tenant_id}/admins/{admin_id}")
async def remove_tenant_admin(tenant_id: str, admin_id: str, user: dict = Depends(get_current_user)):
    """Remove an admin from a tenant"""
    await verify_super_admin(user)
    result = await db.telegram_admins.delete_one({"id": admin_id, "tenant_id": tenant_id})
    return {"success": result.deleted_count > 0}



# ============== TENANT ADMIN USER MANAGEMENT ==============

@router.post("/saas/tenants/{tenant_id}/dashboard-admin")
async def create_tenant_dashboard_admin(tenant_id: str, data: dict, user: dict = Depends(get_current_user)):
    """Create a web dashboard admin user for a specific tenant. Super Admin only."""
    await verify_super_admin(user)

    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()
    name = data.get("name", "").strip()

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    # Check tenant exists
    tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Check if user already exists
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        # Update existing user to tenant_admin role if not already
        await db.users.update_one(
            {"email": email},
            {"$set": {
                "role": "tenant_admin",
                "tenant_id": tenant_id,
                "name": name or existing.get("name", ""),
                "is_admin": True,
                "dashboard_subscription_status": "active",
            }}
        )
        return {"message": f"User {email} updated to tenant admin for {tenant.get('name', tenant_id)}"}

    # Create new user
    user_doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": name or email.split("@")[0],
        "password_hash": hash_password(password),
        "role": "tenant_admin",
        "tenant_id": tenant_id,
        "is_admin": True,
        "dashboard_subscription_status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user_doc)
    del user_doc["_id"]

    logger.info(f"Created tenant admin: {email} for tenant {tenant_id}")
    await log_action(tenant_id, user["id"], user.get("email", ""), "tenant_admin_created", "user", user_doc["id"], {"email": email, "tenant_name": tenant.get("name", "")})
    return {
        "message": f"Tenant admin created: {email} for {tenant.get('name', tenant_id)}",
        "user_id": user_doc["id"],
        "email": email,
    }


@router.get("/saas/tenants/{tenant_id}/dashboard-admins")
async def get_tenant_dashboard_admins(tenant_id: str, user: dict = Depends(get_current_user)):
    """Get all web dashboard admin users for a tenant."""
    await verify_super_admin(user)
    admins = await db.users.find(
        {"tenant_id": tenant_id, "role": "tenant_admin"},
        {"_id": 0, "password_hash": 0}
    ).to_list(100)
    return admins


@router.delete("/saas/tenants/{tenant_id}/dashboard-admins/{user_id}")
async def remove_tenant_dashboard_admin(tenant_id: str, user_id: str, user: dict = Depends(get_current_user)):
    """Remove a tenant dashboard admin."""
    await verify_super_admin(user)
    result = await db.users.update_one(
        {"id": user_id, "tenant_id": tenant_id},
        {"$set": {"role": "user", "tenant_id": "", "is_admin": False}}
    )
    return {"success": result.modified_count > 0}



# ============== DATA MIGRATION ENDPOINT ==============

@router.post("/saas/migrate-to-tenant")
async def migrate_data_to_tenant(data: dict, user: dict = Depends(get_current_user)):
    """Migrate all data from 'default' (or no tenant) to a specific tenant. Super Admin only."""
    await verify_super_admin(user)

    target_tenant_id = data.get("target_tenant_id", "tenant_85ee971d0285")
    target_tenant_name = data.get("target_tenant_name", "Anamika")

    # Ensure target tenant exists
    existing = await db.tenants.find_one({"tenant_id": target_tenant_id})
    if not existing:
        tenant = {
            "id": str(uuid.uuid4()),
            "tenant_id": target_tenant_id,
            "name": target_tenant_name,
            "email": data.get("email", ""),
            "owner_telegram_id": data.get("owner_telegram_id", ""),
            "bot_token": data.get("bot_token", ""),
            "bot_username": data.get("bot_username", ""),
            "upi_id": data.get("upi_id", ""),
            "channel_id": data.get("channel_id", ""),
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.tenants.insert_one(tenant)
    else:
        await db.tenants.update_one(
            {"tenant_id": target_tenant_id},
            {"$set": {"name": target_tenant_name}}
        )

    # Ensure 'default' tenant exists as Kaloo
    kaloo = await db.tenants.find_one({"tenant_id": "default"})
    if not kaloo:
        await db.tenants.insert_one({
            "id": "default-tenant",
            "tenant_id": "default",
            "name": "Kaloo",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "bot_token": "",
            "bot_username": "KalooBot",
            "owner_telegram_id": "",
        })

    # Collections to migrate
    collections = [
        "bot_users", "subscribers", "payments", "plans", "paid_posts",
        "live_sessions", "paid_post_unlocks", "pending_screenshots",
        "miniapp_users", "miniapp_support_chats", "referrals", "broadcasts",
        "chat_messages", "chat_sessions", "bot_activity_logs", "bot_orders",
        "telegram_admins",
    ]

    results = {}
    total = 0

    for coll_name in collections:
        coll = db[coll_name]
        migrated = 0

        # Migrate 'default' tenant_id
        r1 = await coll.update_many(
            {"tenant_id": "default"},
            {"$set": {"tenant_id": target_tenant_id}}
        )
        migrated += r1.modified_count

        # Migrate docs without tenant_id
        r2 = await coll.update_many(
            {"tenant_id": {"$exists": False}},
            {"$set": {"tenant_id": target_tenant_id}}
        )
        migrated += r2.modified_count

        # Migrate empty tenant_id
        r3 = await coll.update_many(
            {"tenant_id": ""},
            {"$set": {"tenant_id": target_tenant_id}}
        )
        migrated += r3.modified_count

        if migrated > 0:
            results[coll_name] = migrated
            total += migrated

    # Get post-migration stats
    stats = {
        "subscribers": await db.subscribers.count_documents({"tenant_id": target_tenant_id}),
        "active_subs": await db.subscribers.count_documents({"tenant_id": target_tenant_id, "status": "active"}),
        "payments": await db.payments.count_documents({"tenant_id": target_tenant_id}),
        "bot_users": await db.bot_users.count_documents({"tenant_id": target_tenant_id}),
    }

    # Revenue
    pipeline = [
        {"$match": {"tenant_id": target_tenant_id, "status": {"$in": ["verified", "approved"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    rev = await db.payments.aggregate(pipeline).to_list(1)
    stats["revenue"] = rev[0]["total"] if rev else 0

    logger.info(f"Migration complete: {total} docs migrated to {target_tenant_id}")
    await log_action("platform", user["id"], user.get("email", ""), "data_migration", "tenant", target_tenant_id, {"total_migrated": total, "target": target_tenant_name})

    return {
        "message": f"Migration complete! {total} documents migrated to '{target_tenant_name}'",
        "total_migrated": total,
        "details": results,
        "post_migration_stats": stats
    }
