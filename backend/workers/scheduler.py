"""Scheduler worker — manages all periodic/cron jobs.
Cleanly separated from the API process for future horizontal scaling.
Uses MongoDB-based distributed lock to prevent duplicate execution."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import db
from config import logger
from datetime import datetime, timezone, timedelta
from services.background_tasks import (
    check_subscriptions, send_followups, send_daily_reminders,
    check_upcoming_live_sessions
)
from services.chat_pool import check_expired_chat_sessions


# MongoDB-based distributed lock for leader election
async def acquire_lock(lock_name: str, ttl_seconds: int = 300) -> bool:
    """Try to acquire a distributed lock. Returns True if acquired."""
    now = datetime.now(timezone.utc)
    try:
        result = await db.scheduler_locks.find_one_and_update(
            {
                "lock_name": lock_name,
                "$or": [
                    {"expires_at": {"$lt": now.isoformat()}},
                    {"expires_at": {"$exists": False}},
                ]
            },
            {
                "$set": {
                    "lock_name": lock_name,
                    "acquired_at": now.isoformat(),
                    "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
                }
            },
            upsert=True,
            return_document=True,
        )
        return result is not None
    except Exception:
        # Duplicate key = another worker got the lock first
        return False


async def release_lock(lock_name: str):
    """Release a distributed lock."""
    await db.scheduler_locks.delete_one({"lock_name": lock_name})


# Wrapped job functions with distributed locking
async def locked_check_subscriptions():
    if await acquire_lock("check_subscriptions", ttl_seconds=600):
        try:
            await check_subscriptions()
        finally:
            await release_lock("check_subscriptions")


async def locked_send_followups():
    if await acquire_lock("send_followups", ttl_seconds=600):
        try:
            await send_followups()
        finally:
            await release_lock("send_followups")


async def locked_check_expired_chats():
    if await acquire_lock("check_expired_chats", ttl_seconds=60):
        try:
            await check_expired_chat_sessions()
        finally:
            await release_lock("check_expired_chats")


async def locked_send_daily_reminders():
    if await acquire_lock("send_daily_reminders", ttl_seconds=600):
        try:
            await send_daily_reminders()
        finally:
            await release_lock("send_daily_reminders")


async def locked_check_live_sessions():
    if await acquire_lock("check_live_sessions", ttl_seconds=300):
        try:
            await check_upcoming_live_sessions()
        finally:
            await release_lock("check_live_sessions")


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the scheduler with all periodic jobs.
    Returns scheduler instance — caller is responsible for starting it."""
    scheduler = AsyncIOScheduler()

    # Subscription health check — every 6 hours
    scheduler.add_job(locked_check_subscriptions, 'interval', hours=6, id='check_subscriptions')

    # Follow-up messages — Mon & Thu at 10:00 UTC
    scheduler.add_job(locked_send_followups, 'cron', day_of_week='mon,thu', hour=10, id='send_followups')

    # Chat session expiry — every 30 seconds
    scheduler.add_job(locked_check_expired_chats, 'interval', seconds=30, id='check_expired_chats')

    # Daily reminders — 3 times a day
    scheduler.add_job(locked_send_daily_reminders, 'cron', hour=9, minute=0, id='daily_reminder_9am')
    scheduler.add_job(locked_send_daily_reminders, 'cron', hour=14, minute=30, id='daily_reminder_2pm')
    scheduler.add_job(locked_send_daily_reminders, 'cron', hour=20, minute=0, id='daily_reminder_8pm')

    # Live session checks — every 5 minutes
    scheduler.add_job(locked_check_live_sessions, 'interval', minutes=5, id='check_live_sessions')

    logger.info("Scheduler configured with 7 jobs (all with distributed locking)")
    return scheduler
