"""TgSubsBot - Telegram Subscription Bot SaaS Platform
Main application entry point - app setup, middleware, router inclusion, startup/shutdown
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import logging

from config import logger
from database import client as mongo_client
from rate_limiter import limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

# Import route modules
from routes.auth import router as auth_router
from routes.admin import router as admin_router
from routes.core import router as core_router
from routes.features import router as features_router
from routes.telegram_webhook import router as webhook_router
from routes.miniapp import router as miniapp_router

# Import background tasks
from services.background_tasks import (
    check_subscriptions, send_followups, send_daily_reminders,
    check_upcoming_live_sessions
)
from services.chat_pool import check_expired_chat_sessions

# Create FastAPI app
app = FastAPI()

# Rate limiter setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Scheduler
scheduler = AsyncIOScheduler()

# Include all route modules under /api prefix
app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(core_router, prefix="/api")
app.include_router(features_router, prefix="/api")
app.include_router(webhook_router, prefix="/api")
app.include_router(miniapp_router, prefix="/api")

# Mount static files for uploads
uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
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
