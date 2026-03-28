"""Dashboard subscription, Super admin management routes"""
from fastapi import APIRouter, HTTPException, Depends, Request
from database import db
from services.auth import get_current_user
from config import logger, RAZORPAY_KEY_ID, razorpay_client, DASHBOARD_PLANS
from models import User
from datetime import datetime, timezone, timedelta
import uuid

router = APIRouter()

SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"

async def verify_super_admin(user: dict):
    """Verify if user is super admin (by email OR role)"""
    if user.get("email") == SUPER_ADMIN_EMAIL or user.get("role") == "super_admin" or user.get("is_admin"):
        return True
    raise HTTPException(status_code=403, detail="Super Admin access required")

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
    """Check if current user is admin/super_admin"""
    is_admin = user.get("is_admin", False) or user.get("role") in ["admin", "super_admin"] or user.get("email") == SUPER_ADMIN_EMAIL
    if not is_admin:
        first_user = await db.users.find_one({}, {"_id": 0}, sort=[("created_at", 1)])
        is_admin = first_user and first_user["id"] == user["id"]
    return {"is_admin": is_admin}

@router.get("/dashboard-subscription/requests")
async def get_subscription_requests(user = Depends(get_current_user)):
    """Get all subscription requests (admin/super_admin sees all)"""
    is_admin = user.get("is_admin", False) or user.get("role") in ["admin", "super_admin"] or user.get("email") == SUPER_ADMIN_EMAIL
    if not is_admin:
        first_user = await db.users.find_one({}, {"_id": 0}, sort=[("created_at", 1)])
        is_admin = first_user and first_user["id"] == user["id"]

    if is_admin:
        requests = await db.dashboard_subscriptions.find({}, {"_id": 0}).to_list(100)
    else:
        requests = await db.dashboard_subscriptions.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
    return requests

@router.get("/tenant-users")
async def get_tenant_users(user = Depends(get_current_user)):
    """Get all registered tenant users with subscription details (super admin only)"""
    await verify_super_admin(user)
    users = await db.users.find({}, {"_id": 0, "password": 0, "password_hash": 0}).to_list(500)

    for u in users:
        # Get active subscription details
        sub = await db.dashboard_subscriptions.find_one(
            {"user_id": u["id"], "status": "approved"},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        u["subscription"] = sub
        u["has_active_plan"] = u.get("dashboard_subscription_status") == "active"

    return users

# Super Admin email
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"

async def verify_super_admin(user: dict):
    """Verify if user is super admin (by email OR role)"""
    if user.get("email") == SUPER_ADMIN_EMAIL or user.get("role") == "super_admin" or user.get("is_admin"):
        return True
    raise HTTPException(status_code=403, detail="Super Admin access required")

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
    """Get dashboard stats for super admin"""
    await verify_super_admin(user)
    
    total_users = await db.users.count_documents({})
    active_subscribers = await db.users.count_documents({"dashboard_subscription_status": "active"})
    pending_requests = await db.dashboard_subscriptions.count_documents({"status": "pending"})
    
    # Calculate revenue from approved subscriptions
    approved_subs = await db.dashboard_subscriptions.find({"status": "approved"}, {"_id": 0}).to_list(10000)
    total_revenue = sum(sub.get("amount", 0) for sub in approved_subs)
    
    return {
        "total_users": total_users,
        "active_subscribers": active_subscribers,
        "pending_requests": pending_requests,
        "total_revenue": total_revenue
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
    if target_user.get("email") == SUPER_ADMIN_EMAIL:
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
    
    # Can't change super admin's status
    if target_user.get("email") == SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=400, detail="Cannot modify super admin")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_admin": True}}
    )
    
    return {"message": "User is now an admin"}

@router.put("/admin/remove-admin/{user_id}")
async def remove_user_admin(user_id: str, user = Depends(get_current_user)):
    """Remove admin status from a user (super admin only)"""
    await verify_super_admin(user)
    
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Can't change super admin's status
    if target_user.get("email") == SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=400, detail="Cannot modify super admin")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_admin": False}}
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
    first_user = await db.users.find_one({}, {"_id": 0}, sort=[("created_at", 1)])
    is_first_user = first_user and first_user["id"] == user["id"]
    is_super_admin = user.get("email") == SUPER_ADMIN_EMAIL
    
    if not is_first_user and not is_super_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
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

# ============== PLANS ROUTES ==============
