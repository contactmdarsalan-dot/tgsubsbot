"""TgSubsBot - Telegram Subscription Bot SaaS Platform
Main application entry point - app setup, middleware, router inclusion, startup/shutdown

Architecture:
  core/          → Config, DB, security, exceptions, constants
  dependencies/  → FastAPI dependencies (auth, permissions)
  middleware/    → Request context, idempotency
  api/           → Routes organized by audience
    public/      → Auth, registration (unauthenticated)
    tenant_admin/→ Tenant-scoped operations
    platform_admin/ → Super admin operations
    customer/    → End-user facing (mini app, wallet)
    webhooks/    → Telegram, Razorpay callbacks
  repositories/  → Strict tenant-scoped DB access
  services/      → Business logic (telegram, payments, etc.)
  schemas/       → Pydantic request/response models
  workers/       → Background jobs (scheduler)
  webhook_handlers/ → Telegram bot message handlers
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi.responses import Response
from core.config import logger, SUPER_ADMIN_EMAILS
from core.db import client as mongo_client, db
from core.rate_limiter import limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

# ============== API ROUTERS (organized by audience) ==============

# Public routes (auth, registration)
from api.public.auth import router as auth_router

# Platform Admin routes (super admin)
from api.platform_admin.admin import router as admin_router
from api.platform_admin.wallet import router as wallet_router

# Tenant Admin routes (tenant-scoped operations)
from api.tenant_admin.plans import router as plans_router
from api.tenant_admin.subscribers import router as subscribers_router
from api.tenant_admin.payments import router as payments_router
from api.tenant_admin.dashboard import router as dashboard_router
from api.tenant_admin.broadcasts import router as broadcasts_router
from api.tenant_admin.engagement import router as engagement_router
from api.tenant_admin.live_content import router as live_content_router
from api.tenant_admin.analytics_exports import router as analytics_exports_router
from api.tenant_admin.tenant import router as tenant_router
from api.tenant_admin.miniapp_admin import router as miniapp_admin_router

# Customer routes (end-user facing)
from api.customer.miniapp_user import router as miniapp_user_router
from api.customer.miniapp_calls import router as miniapp_calls_router
from api.customer.miniapp_chat import router as miniapp_chat_router
from api.customer.global_wallet import router as global_wallet_router
from api.customer.global_app import router as global_app_router

# Webhook routes
from api.webhooks.telegram import router as webhook_router
from api.webhooks.razorpay import router as razorpay_router

# Import worker scheduler
from workers.scheduler import create_scheduler


# ============== REQUEST CONTEXT MIDDLEWARE ==============
class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request_id to every request for traceability."""
    async def dispatch(self, request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response


# Create FastAPI app
app = FastAPI()

# Rate limiter setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add RequestContext middleware
app.add_middleware(RequestContextMiddleware)

# Scheduler — cleanly separated in workers module
scheduler = create_scheduler()

# Include all route modules under /api prefix
app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(wallet_router, prefix="/api")
app.include_router(plans_router, prefix="/api")
app.include_router(subscribers_router, prefix="/api")
app.include_router(payments_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(broadcasts_router, prefix="/api")
app.include_router(engagement_router, prefix="/api")
app.include_router(live_content_router, prefix="/api")
app.include_router(analytics_exports_router, prefix="/api")
app.include_router(webhook_router, prefix="/api")
app.include_router(miniapp_user_router, prefix="/api")
app.include_router(miniapp_admin_router, prefix="/api")
app.include_router(miniapp_calls_router, prefix="/api")
app.include_router(miniapp_chat_router, prefix="/api")
app.include_router(tenant_router, prefix="/api")
app.include_router(global_wallet_router, prefix="/api")
app.include_router(global_app_router, prefix="/api")
app.include_router(razorpay_router, prefix="/api")

# Mount static files for uploads
uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=uploads_dir), name="uploads")

@app.get("/api/debug/razorpay-status")
async def razorpay_debug():
    from core.config import razorpay_client, RAZORPAY_KEY_ID
    return {
        "razorpay_key_set": bool(RAZORPAY_KEY_ID),
        "razorpay_key_prefix": RAZORPAY_KEY_ID[:8] + "..." if RAZORPAY_KEY_ID else "NOT_SET",
        "razorpay_client_initialized": razorpay_client is not None,
    }

@app.get("/api/pay/{order_id}")
async def bot_payment_page(order_id: str):
    """Payment page for Telegram bot — uses Razorpay Checkout JS"""
    from core.config import RAZORPAY_KEY_ID
    from fastapi.responses import HTMLResponse

    order = await db.razorpay_bot_orders.find_one({"razorpay_order_id": order_id, "status": "created"}, {"_id": 0})
    if not order:
        return HTMLResponse("<h2>Order not found or already paid</h2>", status_code=404)

    amount = order.get("amount", 0)
    plan_name = order.get("plan_name", "Plan")
    chat_id = order.get("chat_id", "")
    username = order.get("username", "")
    tenant_id = order.get("tenant_id", "")
    callback_url = os.environ.get("RAZORPAY_CALLBACK_URL", os.environ.get("REACT_APP_BACKEND_URL", ""))

    html = f"""<!DOCTYPE html>
<html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pay ₹{amount} - {plan_name}</title>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #0a0a0a; color: #fff;
    display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
  .card {{ background: #1a1a1a; border-radius: 16px; padding: 32px; text-align: center; max-width: 400px; width: 90%; }}
  .price {{ font-size: 2.5rem; font-weight: 700; color: #BFFF00; margin: 16px 0; }}
  .plan {{ font-size: 1.2rem; color: #ccc; margin-bottom: 24px; }}
  .btn {{ background: #BFFF00; color: #000; border: none; padding: 16px 32px; font-size: 1.1rem;
    font-weight: 700; border-radius: 12px; cursor: pointer; width: 100%; }}
  .btn:hover {{ background: #d4ff33; }}
  .success {{ color: #BFFF00; font-size: 1.3rem; display: none; }}
  .loading {{ display: none; }}
</style>
</head><body>
<div class="card">
  <div id="pay-section">
    <h2>💳 Complete Payment</h2>
    <div class="plan">{plan_name}</div>
    <div class="price">₹{amount}</div>
    <button class="btn" onclick="startPayment()">Pay Now</button>
  </div>
  <div id="success-section" class="success">
    <h2>✅ Payment Successful!</h2>
    <p>Your subscription is now active.</p>
    <p>Go back to Telegram to continue.</p>
  </div>
  <div id="loading-section" class="loading">
    <h2>⏳ Verifying payment...</h2>
  </div>
</div>
<script>
function startPayment() {{
  var options = {{
    key: "{RAZORPAY_KEY_ID}",
    amount: {amount * 100},
    currency: "INR",
    name: "TGSubsBot",
    description: "{plan_name}",
    order_id: "{order_id}",
    handler: function(response) {{
      document.getElementById("pay-section").style.display = "none";
      document.getElementById("loading-section").style.display = "block";
      fetch("{callback_url}/api/bot-payment/verify", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{
          razorpay_order_id: response.razorpay_order_id,
          razorpay_payment_id: response.razorpay_payment_id,
          razorpay_signature: response.razorpay_signature,
          chat_id: "{chat_id}",
          tenant_id: "{tenant_id}"
        }})
      }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
        document.getElementById("loading-section").style.display = "none";
        document.getElementById("success-section").style.display = "block";
      }}).catch(function() {{
        document.getElementById("loading-section").style.display = "none";
        document.getElementById("success-section").style.display = "block";
      }});
    }},
    prefill: {{ name: "{username}" }},
    theme: {{ color: "#BFFF00" }},
  }};
  var rzp = new Razorpay(options);
  rzp.open();
}}
</script>
</body></html>"""
    return HTMLResponse(html)

@app.post("/api/bot-payment/verify")
async def bot_payment_verify(data: dict):
    """Verify Razorpay payment from bot payment page"""
    from core.config import razorpay_client
    from services.telegram import get_bot_settings, send_telegram_message, add_to_channel

    if not razorpay_client:
        raise HTTPException(status_code=400, detail="Razorpay not configured")

    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })
    except Exception as e:
        logger.error(f"Bot payment verification failed: {e}")
        raise HTTPException(status_code=400, detail="Payment verification failed")

    order = await db.razorpay_bot_orders.find_one({"razorpay_order_id": data['razorpay_order_id']}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Mark order as paid
    await db.razorpay_bot_orders.update_one(
        {"razorpay_order_id": data['razorpay_order_id']},
        {"$set": {"status": "paid", "razorpay_payment_id": data['razorpay_payment_id'], "paid_at": datetime.now(timezone.utc).isoformat()}}
    )

    chat_id = order.get("chat_id", data.get("chat_id", ""))
    tenant_id = order.get("tenant_id", data.get("tenant_id", ""))
    plan_name = order.get("plan_name", "Plan")
    duration_days = order.get("duration_days", 30)
    amount = order.get("amount", 0)
    username = order.get("username", "")
    plan_id = order.get("plan_id", "")
    unlock_post_id = order.get("unlock_post_id", "")
    order_type = order.get("type", "subscription")

    now = datetime.now(timezone.utc)

    # Handle paid post unlock
    if order_type == "paid_post_unlock" and unlock_post_id:
        paid_post = await db.paid_posts.find_one({"id": unlock_post_id, "tenant_id": tenant_id}, {"_id": 0})
        payment_id = str(uuid.uuid4())[:8]
        await db.payments.insert_one({
            "id": payment_id, "telegram_user_id": chat_id, "telegram_username": username,
            "amount": amount, "payment_method": "razorpay", "razorpay_payment_id": data['razorpay_payment_id'],
            "status": "verified", "type": "paid_post_unlock", "unlock_post_id": unlock_post_id,
            "verified_at": now.isoformat(), "tenant_id": tenant_id, "created_at": now.isoformat()
        })
        await db.paid_post_unlocks.insert_one({
            "id": str(uuid.uuid4()), "post_id": unlock_post_id, "telegram_user_id": chat_id,
            "payment_id": payment_id, "amount": amount, "tenant_id": tenant_id, "unlocked_at": now.isoformat()
        })
        await db.paid_posts.update_one({"id": unlock_post_id, "tenant_id": tenant_id}, {"$inc": {"unlock_count": 1}})

        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
        if bot_token and paid_post:
            from services.telegram import send_telegram_photo, send_telegram_video
            await send_telegram_message(chat_id, "✅ <b>Payment Successful!</b>\n\n🔓 Unlocking content...", bot_token)
            
            # Send ALL media items for media_group posts
            file_ids = paid_post.get("file_ids", [])
            caption = f"🔓 <b>Unlocked!</b>\n\n{paid_post.get('caption', '')}"
            if file_ids and len(file_ids) > 0:
                for i, item in enumerate(file_ids):
                    item_caption = caption if i == 0 else ""
                    if item.get("type") == "video":
                        await send_telegram_video(chat_id, item["file_id"], item_caption, bot_token)
                    else:
                        await send_telegram_photo(chat_id, item["file_id"], item_caption, bot_token)
            elif paid_post.get("content_type") == "photo" and paid_post.get("original_file_id"):
                await send_telegram_photo(chat_id, paid_post["original_file_id"], caption, bot_token)
            elif paid_post.get("content_type") == "video" and paid_post.get("original_file_id"):
                await send_telegram_video(chat_id, paid_post["original_file_id"], caption, bot_token)

        return {"success": True, "type": "unlock"}

    # Handle subscription payment
    payment_id = str(uuid.uuid4())[:8]
    end_date = now + timedelta(days=duration_days)

    payment_record = {
        "id": payment_id, "subscriber_id": None, "telegram_user_id": chat_id,
        "telegram_username": username, "amount": amount, "plan_id": plan_id,
        "plan_name": plan_name, "payment_method": "razorpay",
        "razorpay_payment_id": data['razorpay_payment_id'],
        "status": "verified", "source": "telegram_bot", "tenant_id": tenant_id,
        "created_at": now.isoformat()
    }
    await db.payments.insert_one(payment_record)

    await db.subscribers.update_one(
        {"telegram_user_id": chat_id, "tenant_id": tenant_id},
        {"$set": {
            "telegram_user_id": chat_id, "telegram_username": username,
            "plan_id": plan_id, "plan_name": plan_name,
            "amount_paid": amount, "subscription_start": now.isoformat(),
            "subscription_end": end_date.isoformat(), "is_active": True,
            "payment_method": "razorpay", "tenant_id": tenant_id,
            "updated_at": now.isoformat()
        }, "$setOnInsert": {"created_at": now.isoformat()}},
        upsert=True
    )

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if bot_token:
        success_msg = f"✅ <b>Payment Verified!</b>\n\n"
        success_msg += f"📦 Plan: {plan_name}\n💰 Amount: ₹{amount}\n📅 Valid till: {end_date.strftime('%d %B %Y')}\n\n"
        success_msg += "🎉 Welcome! You now have full access."
        await send_telegram_message(chat_id, success_msg, bot_token)

        # Get plan's specific channel_id from DB
        plan_data = await db.plans.find_one({"id": plan_id, "tenant_id": tenant_id}, {"_id": 0, "channel_id": 1})
        plan_channel_id = plan_data.get("channel_id", "") if plan_data else ""
        
        try:
            await add_to_channel(chat_id, plan_channel_id=plan_channel_id, plan_name=plan_name)
        except Exception as e:
            logger.error(f"Failed to add user to channel: {e}")

    return {"success": True, "type": "subscription"}


# CORS middleware — strict allowlist
_default_origins = "https://tgsubsbot.com,https://www.tgsubsbot.com,https://api.tgsubsbot.com,https://trial-management-hub-1.preview.emergentagent.com"
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', _default_origins).split(','),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


async def bootstrap_super_admins():
    """Ensure SUPER_ADMIN_EMAILS users have role='super_admin' in DB.
    This runs once at startup so authorization is ALWAYS role-based."""
    for email in SUPER_ADMIN_EMAILS:
        user = await db.users.find_one({"email": email})
        if user and user.get("role") != "super_admin":
            await db.users.update_one(
                {"email": email},
                {"$set": {"role": "super_admin", "is_admin": True}}
            )
            logger.info(f"Bootstrap: Set role='super_admin' for {email}")
        elif user:
            logger.info(f"Bootstrap: {email} already has role='super_admin'")
        else:
            logger.warning(f"Bootstrap: Super admin email {email} not found in DB — will be bootstrapped on first registration/login")


@app.on_event("startup")
async def startup():
    # Create MongoDB indexes
    from core.db import ensure_indexes
    await ensure_indexes()
    
    # Bootstrap super admin roles
    await bootstrap_super_admins()
    
    # Start scheduler only in embedded mode (default for single-instance)
    # Set SCHEDULER_MODE=standalone to run scheduler as a separate worker
    import os
    if os.environ.get("SCHEDULER_MODE", "embedded") == "embedded":
        scheduler.start()
        logger.info("Scheduler started in EMBEDDED mode (all jobs have distributed locking)")
    else:
        logger.info("Scheduler SKIPPED — running in standalone worker mode")


@app.on_event("shutdown")
async def shutdown():
    import os
    if os.environ.get("SCHEDULER_MODE", "embedded") == "embedded":
        scheduler.shutdown()
    mongo_client.close()
