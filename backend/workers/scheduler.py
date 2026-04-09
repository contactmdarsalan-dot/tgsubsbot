"""Scheduler worker — manages all periodic/cron jobs.
Can be run EITHER:
  1. Embedded in FastAPI (default, for single-instance deployments)
  2. As a standalone worker process via `python -m workers.scheduler`

Uses MongoDB-based distributed lock to prevent duplicate execution
when scaling horizontally."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import db
from config import logger
from datetime import datetime, timezone, timedelta
from services.background_tasks import (
    check_subscriptions, send_followups, send_daily_reminders,
    check_upcoming_live_sessions, process_scheduled_posts
)
from services.chat_pool import check_expired_chat_sessions
import os


SCHEDULER_MODE = os.environ.get("SCHEDULER_MODE", "embedded")  # "embedded" or "standalone"


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


async def locked_process_scheduled_posts():
    if await acquire_lock("process_scheduled_posts", ttl_seconds=120):
        try:
            await process_scheduled_posts()
        finally:
            await release_lock("process_scheduled_posts")


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the scheduler with all periodic jobs.
    Returns scheduler instance — caller is responsible for starting it."""
    scheduler = AsyncIOScheduler()

    scheduler.add_job(locked_check_subscriptions, 'interval', hours=6, id='check_subscriptions')
    scheduler.add_job(locked_send_followups, 'cron', day_of_week='mon,thu', hour=10, id='send_followups')
    scheduler.add_job(locked_check_expired_chats, 'interval', seconds=30, id='check_expired_chats')
    scheduler.add_job(locked_send_daily_reminders, 'cron', hour=9, minute=0, id='daily_reminder_9am')
    scheduler.add_job(locked_send_daily_reminders, 'cron', hour=14, minute=30, id='daily_reminder_2pm')
    scheduler.add_job(locked_send_daily_reminders, 'cron', hour=20, minute=0, id='daily_reminder_8pm')
    scheduler.add_job(locked_check_live_sessions, 'interval', minutes=5, id='check_live_sessions')
    scheduler.add_job(locked_process_scheduled_posts, 'interval', minutes=1, id='process_scheduled_posts')

    logger.info("Scheduler configured with 8 jobs (all with distributed locking)")
    return scheduler


# Standalone entry point — run as: SCHEDULER_MODE=standalone python -m workers.scheduler
if __name__ == "__main__":
    import asyncio
    import signal

    async def run_standalone():
        logger.info("Starting scheduler in STANDALONE worker mode...")
        scheduler = create_scheduler()
        scheduler.start()
        logger.info("Scheduler worker running. Press Ctrl+C to stop.")

        stop_event = asyncio.Event()
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        await stop_event.wait()
        scheduler.shutdown()
        logger.info("Scheduler worker stopped.")

    asyncio.run(run_standalone())
