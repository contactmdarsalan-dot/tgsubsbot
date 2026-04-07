"""TgSubsBot - Telegram Subscription Bot SaaS Platform
Main application entry point - app setup, middleware, router inclusion, startup/shutdown
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
from config import logger, SUPER_ADMIN_EMAILS
from database import client as mongo_client, db
from rate_limiter import limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

# Import route modules
from routes.auth import router as auth_router
from routes.admin import router as admin_router
from routes.plans import router as plans_router
from routes.subscribers import router as subscribers_router
from routes.payments import router as payments_router
from routes.dashboard import router as dashboard_router
from routes.broadcasts import router as broadcasts_router
from routes.engagement import router as engagement_router
from routes.live_content import router as live_content_router
from routes.analytics_exports import router as analytics_exports_router
from routes.telegram_webhook import router as webhook_router
from routes.miniapp_user import router as miniapp_user_router
from routes.miniapp_admin import router as miniapp_admin_router
from routes.miniapp_calls import router as miniapp_calls_router
from routes.miniapp_chat import router as miniapp_chat_router
from routes.tenant import router as tenant_router
from routes.global_wallet import router as global_wallet_router
from routes.global_app import router as global_app_router
from routes.razorpay_webhook import router as razorpay_router

# Import background tasks
from services.background_tasks import (
    check_subscriptions, send_followups, send_daily_reminders,
    check_upcoming_live_sessions
)
from services.chat_pool import check_expired_chat_sessions


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

# Scheduler
scheduler = AsyncIOScheduler()

# Include all route modules under /api prefix
app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
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

# CORS middleware — strict allowlist
_default_origins = "https://tgsubsbot.com,https://www.tgsubsbot.com,https://trial-management-hub-1.preview.emergentagent.com"
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
    from database import ensure_indexes
    await ensure_indexes()
    
    # Bootstrap super admin roles
    await bootstrap_super_admins()
    
    scheduler.add_job(check_subscriptions, 'interval', hours=6)
    scheduler.add_job(send_followups, 'cron', day_of_week='mon,thu', hour=10)
    scheduler.add_job(check_expired_chat_sessions, 'interval', seconds=30)
    scheduler.add_job(send_daily_reminders, 'cron', hour=9, minute=0)
    scheduler.add_job(send_daily_reminders, 'cron', hour=14, minute=30)
    scheduler.add_job(send_daily_reminders, 'cron', hour=20, minute=0)
    scheduler.add_job(check_upcoming_live_sessions, 'interval', minutes=5)
    scheduler.start()
    logger.info("Scheduler started with daily reminders")


@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()
    mongo_client.close()
