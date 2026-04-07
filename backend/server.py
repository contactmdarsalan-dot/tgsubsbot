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
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import logging
import uuid as _uuid

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
        request.state.request_id = str(_uuid.uuid4())
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
