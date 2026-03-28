"""Background scheduled tasks - subscription checks, reminders, live sessions"""
from datetime import datetime, timezone, timedelta
from database import db
from config import logger
from services.telegram import (
    get_bot_settings, get_bot_username, send_telegram_message,
    send_telegram_message_with_buttons, remove_from_channel
)
from services.chat_pool import check_expired_chat_sessions
import asyncio


async def check_subscriptions():
    """Check and update subscription statuses"""
    now = datetime.now(timezone.utc)
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    reminder_days = settings.get("reminder_days_before", 3)
    bot_token = settings.get("telegram_bot_token", "")

    subscribers = await db.subscribers.find({"status": {"$in": ["active", "grace"]}}, {"_id": 0}).to_list(10000)

    for sub in subscribers:
        end_date = datetime.fromisoformat(sub["end_date"]) if isinstance(sub["end_date"], str) else sub["end_date"]
        grace_end = datetime.fromisoformat(sub["grace_end_date"]) if isinstance(sub.get("grace_end_date"), str) else sub.get("grace_end_date")

        days_to_expiry = (end_date - now).days

        if days_to_expiry <= reminder_days and days_to_expiry > 0 and not sub.get("reminder_sent"):
            reminder_msg = f"<b>Subscription Expiring Soon!</b>\n\n"
            reminder_msg += f"Plan: <b>{sub.get('plan_name', 'Premium')}</b>\n"
            reminder_msg += f"Expires in: <b>{days_to_expiry} days</b>\n"
            reminder_msg += f"End Date: <b>{end_date.strftime('%d %b %Y')}</b>\n\n"
            reminder_msg += "Renew now to continue access!"

            buttons = [
                [{"text": "Renew Now", "callback_data": f"renew_{sub.get('plan_id', '')}"}],
                [{"text": "View All Plans", "callback_data": "back_plans"}]
            ]
            await send_telegram_message_with_buttons(sub["telegram_user_id"], reminder_msg, buttons, bot_token)
            await db.subscribers.update_one({"id": sub["id"]}, {"$set": {"reminder_sent": True}})

        if now > end_date and sub["status"] == "active":
            await db.subscribers.update_one({"id": sub["id"]}, {"$set": {"status": "grace"}})

            grace_msg = "<b>Subscription Expired!</b>\n\n"
            grace_msg += f"Plan: <b>{sub.get('plan_name', 'Premium')}</b>\n"
            grace_msg += f"Grace Period: <b>{settings.get('grace_period_days', 2)} days</b>\n\n"
            grace_msg += "Renew now to keep your access!"

            buttons = [
                [{"text": "Renew Now", "callback_data": f"renew_{sub.get('plan_id', '')}"}],
                [{"text": "View All Plans", "callback_data": "back_plans"}]
            ]
            await send_telegram_message_with_buttons(sub["telegram_user_id"], grace_msg, buttons, bot_token)

        if grace_end and now > grace_end and sub["status"] == "grace":
            await db.subscribers.update_one({"id": sub["id"]}, {"$set": {"status": "expired"}})

            plan = await db.plans.find_one({"id": sub.get("plan_id")}, {"_id": 0})
            plan_channel = plan.get("channel_id", "") if plan else ""
            await remove_from_channel(sub["telegram_user_id"], plan_channel)

            expired_msg = "<b>Subscription Ended</b>\n\n"
            expired_msg += "Your subscription and grace period have ended.\n"
            expired_msg += "You've been removed from the premium channel.\n\n"
            expired_msg += "Resubscribe anytime!"

            buttons = [
                [{"text": "Resubscribe", "callback_data": "back_plans"}]
            ]
            await send_telegram_message_with_buttons(sub["telegram_user_id"], expired_msg, buttons, bot_token)


async def send_followups():
    """Send follow-up messages twice a week"""
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}

    if not settings.get("followup_enabled"):
        return

    followup_msg = settings.get("followup_message", "Check out our premium services!")
    website_link = settings.get("website_link", "")

    if website_link:
        followup_msg += f"\n\nVisit: {website_link}"

    subscribers = await db.subscribers.find({"status": "active"}, {"_id": 0}).to_list(10000)

    for sub in subscribers:
        await send_telegram_message(sub["telegram_user_id"], followup_msg)


async def send_daily_reminders():
    """Send daily reminders to expired subscribers and non-subscribers"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    website_link = settings.get("website_link", "https://miraclecouplee.syke.club")

    if not bot_token:
        return

    logger.info("Starting daily reminders...")

    plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)

    buttons = []
    for plan in plans:
        plan_price = int(plan['price'])
        buttons.append([{"text": f"{plan['name']} - Rs.{plan_price}", "callback_data": f"buy_{plan['id']}"}])
    buttons.append([{"text": "Visit Website", "url": website_link}])
    buttons.append([{"text": "Special Discount!", "callback_data": "special_discount"}])

    sent_count = 0

    # 1. Expired subscribers
    expired_subs = await db.subscribers.find({
        "status": {"$in": ["expired", "grace"]}
    }, {"_id": 0}).to_list(10000)

    for sub in expired_subs:
        try:
            msg = "<b>Subscription Expired!</b>\n\n"
            msg += f"Your {sub.get('plan_name', 'subscription')} has expired.\n\n"
            msg += f"<b>Visit:</b> {website_link}\n\n"
            msg += "<b>Don't miss out on exclusive content!</b>\n"
            msg += "Renew now to continue access:\n\n"

            await send_telegram_message_with_buttons(sub["telegram_user_id"], msg, buttons, bot_token)
            sent_count += 1
            await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Failed to send reminder to {sub.get('telegram_user_id')}: {e}")

    # 2. Subscribers expiring soon (within 3 days)
    three_days_later = datetime.now(timezone.utc) + timedelta(days=3)
    active_subs = await db.subscribers.find({"status": "active"}, {"_id": 0}).to_list(10000)

    for sub in active_subs:
        try:
            end_date = datetime.fromisoformat(sub["end_date"]) if isinstance(sub["end_date"], str) else sub["end_date"]
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)

            if end_date <= three_days_later:
                days_left = (end_date - datetime.now(timezone.utc)).days
                msg = f"<b>Subscription Expiring Soon!</b>\n\n"
                msg += f"Your {sub.get('plan_name', 'subscription')} expires in <b>{days_left} days</b>.\n\n"
                msg += f"<b>Visit:</b> {website_link}\n\n"
                msg += "<b>Renew now to avoid interruption:</b>\n\n"

                await send_telegram_message_with_buttons(sub["telegram_user_id"], msg, buttons, bot_token)
                sent_count += 1
                await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Failed to send expiry reminder: {e}")

    # 3. Non-subscribers who interacted but never bought
    non_buyers = await db.payments.find({
        "status": {"$in": ["pending", "rejected"]}
    }, {"_id": 0, "telegram_user_id": 1}).to_list(10000)

    active_ids = {s["telegram_user_id"] for s in await db.subscribers.find({"status": "active"}, {"telegram_user_id": 1}).to_list(10000)}

    sent_user_ids = set()
    for p in non_buyers:
        user_id = p.get("telegram_user_id")
        if user_id and user_id not in active_ids and user_id not in sent_user_ids:
            try:
                msg = "<b>You're Missing Out!</b>\n\n"
                msg += "We noticed you haven't subscribed yet.\n\n"
                msg += f"<b>Visit:</b> {website_link}\n\n"
                msg += "<b>Get exclusive content today!</b>\n"
                msg += "Limited time offers available:\n\n"

                await send_telegram_message_with_buttons(user_id, msg, buttons, bot_token)
                sent_user_ids.add(user_id)
                sent_count += 1
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.error(f"Failed to send non-buyer reminder: {e}")

    logger.info(f"Daily reminders completed: {sent_count} messages sent")


async def check_upcoming_live_sessions():
    """Auto-post countdown for live sessions starting in 30 mins"""
    try:
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
        channel_id = settings.get("telegram_channel_id", "")

        if not bot_token:
            return

        now = datetime.now(timezone.utc)

        sessions = await db.live_sessions.find({
            "status": "scheduled",
            "countdown_started": {"$ne": True}
        }, {"_id": 0}).to_list(100)

        for session in sessions:
            try:
                scheduled_date = session.get("scheduled_date", "")
                scheduled_time = session.get("scheduled_time", "")

                if not scheduled_date or not scheduled_time:
                    continue

                try:
                    scheduled_dt = datetime.strptime(f"{scheduled_date} {scheduled_time}", "%Y-%m-%d %H:%M")
                    scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
                except Exception:
                    continue

                time_until = (scheduled_dt - now).total_seconds() / 60

                if 25 <= time_until <= 35:
                    logger.info(f"Auto-posting countdown for session: {session.get('title')}")

                    bot_username = await get_bot_username(bot_token)
                    target_group = session.get("group_id") or channel_id

                    msg = "<b>LIVE STARTING IN 30 MINUTES!</b>\n\n"
                    msg += "---\n"
                    msg += f"<b>{session.get('title')}</b>\n\n"
                    msg += f"<b>Time: {scheduled_time}</b>\n"
                    msg += "---\n\n"
                    msg += f"<b>Ticket:</b> Rs.{int(session.get('price', 0))}\n\n"
                    msg += "<b>Get your ticket NOW!</b>"

                    buttons = [
                        [{
                            "text": f"Buy Ticket - Rs.{int(session.get('price', 0))}",
                            "url": f"https://t.me/{bot_username}?start=live_{session.get('id')}"
                        }],
                        [{
                            "text": "Subscribe",
                            "url": f"https://t.me/{bot_username}?start=subscribe"
                        }]
                    ]

                    result = await send_telegram_message_with_buttons(target_group, msg, buttons, bot_token)

                    await db.live_sessions.update_one(
                        {"id": session.get("id")},
                        {"$set": {
                            "countdown_started": True,
                            "countdown_message_id": result.get("message_id") if result else None,
                            "countdown_chat_id": target_group
                        }}
                    )

            except Exception as e:
                logger.error(f"Error processing session countdown: {e}")

    except Exception as e:
        logger.error(f"Error in check_upcoming_live_sessions: {e}")
