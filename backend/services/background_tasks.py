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

            now_utc = datetime.now(timezone.utc)
            days_left = (end_date - now_utc).days

            # Only send "expiring soon" if actually expiring in the future (days_left >= 0)
            if days_left < 0:
                # Already expired - skip (handled by expired_subs section above)
                continue

            if end_date <= three_days_later:
                msg = f"<b>Subscription Expiring Soon!</b>\n\n"
                if days_left == 0:
                    msg += f"Your {sub.get('plan_name', 'subscription')} expires <b>today</b>!\n\n"
                else:
                    msg += f"Your {sub.get('plan_name', 'subscription')} expires in <b>{days_left} day{'s' if days_left != 1 else ''}</b>.\n\n"
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



async def process_scheduled_posts():
    """Process scheduled paid posts that are due."""
    from services.telegram import (
        get_bot_username, send_telegram_photo, delete_telegram_message
    )
    from services.payment import create_blurred_image
    import httpx
    import uuid
    import os

    now = datetime.now(timezone.utc)
    
    # Find scheduled posts that are due
    due_posts = await db.scheduled_posts.find(
        {"status": "scheduled", "scheduled_at": {"$lte": now.isoformat()}},
        {"_id": 0}
    ).to_list(50)
    
    if not due_posts:
        return
    
    logger.info(f"Processing {len(due_posts)} scheduled posts")
    
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    bot_token = settings.get("telegram_bot_token", "")
    if not bot_token:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    
    if not bot_token:
        logger.error("No bot token for scheduled posts")
        return
    
    bot_username = await get_bot_username(bot_token)
    
    for sched in due_posts:
        try:
            post_id = sched["id"]
            channel_id = sched["channel_id"]
            saved_files = sched.get("saved_files", [])
            price = sched.get("price", 99)
            blur_level = sched.get("blur_level", 25)
            caption = sched.get("caption", "")
            tenant_id = sched.get("tenant_id", "default")
            
            uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
            
            # Upload files to channel and collect file_ids
            file_ids = []
            first_photo_bytes = None
            
            for sf in saved_files:
                local_fname = sf["local_path"].split("/")[-1]
                local_fpath = os.path.join(uploads_dir, local_fname)
                
                if not os.path.exists(local_fpath):
                    logger.error(f"Scheduled file not found: {local_fpath}")
                    continue
                
                with open(local_fpath, "rb") as fp:
                    contents = fp.read()
                
                content_type = sf.get("type", "photo")
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    if content_type == "video":
                        resp = await client.post(
                            f"https://api.telegram.org/bot{bot_token}/sendVideo",
                            data={"chat_id": channel_id},
                            files={"video": (local_fname, contents, "video/mp4")}
                        )
                    else:
                        resp = await client.post(
                            f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                            data={"chat_id": channel_id},
                            files={"photo": (local_fname, contents, "image/jpeg")}
                        )
                    
                    result = resp.json()
                    if result.get("ok"):
                        msg = result["result"]
                        if content_type == "video":
                            fid = msg.get("video", {}).get("file_id", "")
                        else:
                            photos = msg.get("photo", [])
                            fid = photos[-1].get("file_id", "") if photos else ""
                        
                        file_ids.append({
                            "type": content_type,
                            "file_id": fid,
                            "message_id": msg.get("message_id", 0)
                        })
                        
                        if content_type == "photo" and first_photo_bytes is None:
                            first_photo_bytes = contents
            
            if not file_ids:
                await db.scheduled_posts.update_one({"id": post_id}, {"$set": {"status": "failed", "error": "No files uploaded"}})
                continue
            
            # Create blurred preview
            blurred_bytes = None
            if first_photo_bytes:
                blurred_bytes = create_blurred_image(first_photo_bytes, blur_radius=blur_level, content_type="photo")
            
            # Save paid post
            first_photo = next((f for f in file_ids if f["type"] == "photo"), None)
            paid_post = {
                "id": post_id,
                "channel_id": channel_id,
                "original_message_id": file_ids[0].get("message_id", 0),
                "content_type": "media_group" if len(file_ids) > 1 else file_ids[0]["type"],
                "original_file_id": first_photo["file_id"] if first_photo else file_ids[0]["file_id"],
                "file_ids": file_ids,
                "media_count": len(file_ids),
                "caption": caption,
                "price": price,
                "blur_level": blur_level,
                "unlock_count": 0,
                "is_active": True,
                "tenant_id": tenant_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.paid_posts.insert_one(paid_post)
            
            # Post blurred preview
            media_count = len(file_ids)
            price_text = f"₹{int(price)}"
            blur_caption = f"🔒 <b>Paid Content</b>\n\n💰 Price: <b>{price_text}</b>\n\n"
            if caption:
                blur_caption += f"📝 {caption}\n\n"
            if media_count > 1:
                blur_caption += f"📦 {media_count} items inside\n\n"
            blur_caption += "👆 Tap 'Unlock' to view!"
            
            unlock_text = f"🔓 Unlock" if media_count <= 1 else f"🔓 Unlock {media_count} Items"
            unlock_button = {
                "inline_keyboard": [[{
                    "text": f"{unlock_text} - {price_text}",
                    "url": f"https://t.me/{bot_username}?start=unlock_{post_id}"
                }]]
            }
            
            blurred_msg_id = None
            if blurred_bytes:
                result = await send_telegram_photo(channel_id, blurred_bytes, blur_caption, bot_token, unlock_button)
                if result and result.get("ok"):
                    blurred_msg_id = result.get("result", {}).get("message_id", 0)
            
            if blurred_msg_id:
                await db.paid_posts.update_one({"id": post_id}, {"$set": {"blurred_message_id": blurred_msg_id}})
            
            # Delete original uploaded messages
            for item in file_ids:
                msg_id = item.get("message_id")
                if msg_id:
                    await delete_telegram_message(channel_id, msg_id, bot_token)
            
            # Mark scheduled post as published
            await db.scheduled_posts.update_one({"id": post_id}, {"$set": {"status": "published"}})
            logger.info(f"Scheduled post {post_id} published to channel {channel_id}")
            
        except Exception as e:
            logger.error(f"Error processing scheduled post {sched.get('id')}: {e}")
            await db.scheduled_posts.update_one(
                {"id": sched.get("id")}, 
                {"$set": {"status": "failed", "error": str(e)}}
            )
