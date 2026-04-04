"""Telegram Bot API helpers - messaging, channels, rate limiting"""
import os
import asyncio
import httpx
from datetime import datetime, timezone
from database import db, cache_get, cache_set
from config import logger, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

# Rate limiting for Telegram API
telegram_last_request = {}
TELEGRAM_MIN_INTERVAL = 0.05  # 50ms between messages per chat

# Cache for bot username
_bot_username_cache = {}


async def get_bot_settings():
    """Get bot settings from database, with Redis cache and environment variable fallback"""
    cached = await cache_get("bot_settings")
    if cached:
        return cached

    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0})
    settings = settings or {}

    if not settings.get("telegram_bot_token"):
        env_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if env_token:
            settings["telegram_bot_token"] = env_token
            logger.info("Using TELEGRAM_BOT_TOKEN from environment variable")

    await cache_set("bot_settings", settings, ttl=60)
    return settings


async def get_bot_username(bot_token: str) -> str:
    """Get bot username from Telegram API (cached)"""
    if bot_token in _bot_username_cache:
        return _bot_username_cache[bot_token]

    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/getMe"
            response = await http_client.get(url)
            if response.status_code == 200:
                data = response.json()
                username = data.get("result", {}).get("username", "")
                if username:
                    _bot_username_cache[bot_token] = username
                return username
    except Exception as e:
        logger.error(f"Failed to get bot username: {e}")
    return ""


async def send_telegram_message(chat_id: str, message: str, bot_token: str = None, retries: int = 3):
    """Send message via Telegram Bot API with rate limiting and retry"""
    if not bot_token:
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")

    if not bot_token:
        logger.warning("Telegram bot token not configured")
        return False

    now = asyncio.get_event_loop().time()
    last = telegram_last_request.get(chat_id, 0)
    if now - last < TELEGRAM_MIN_INTERVAL:
        await asyncio.sleep(TELEGRAM_MIN_INTERVAL - (now - last))
    telegram_last_request[chat_id] = asyncio.get_event_loop().time()

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                response = await http_client.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})
                logger.info(f"Telegram response: {response.status_code}")

                if response.status_code == 200:
                    return True
                elif response.status_code == 429:
                    retry_after = response.json().get("parameters", {}).get("retry_after", 1)
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                else:
                    logger.error(f"Telegram error: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(0.5)
    return False


async def send_telegram_message_with_buttons(chat_id: str, message: str, buttons: list = None, bot_token: str = None, retries: int = 3):
    """Send message with inline keyboard buttons with rate limiting"""
    if not bot_token:
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")

    if not bot_token:
        return False

    now = asyncio.get_event_loop().time()
    last = telegram_last_request.get(chat_id, 0)
    if now - last < TELEGRAM_MIN_INTERVAL:
        await asyncio.sleep(TELEGRAM_MIN_INTERVAL - (now - last))
    telegram_last_request[chat_id] = asyncio.get_event_loop().time()

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                if buttons:
                    payload["reply_markup"] = {"inline_keyboard": buttons}

                response = await http_client.post(url, json=payload)
                logger.info(f"Telegram response: {response.status_code}")

                if response.status_code == 200:
                    return True
                elif response.status_code == 429:
                    retry_after = response.json().get("parameters", {}).get("retry_after", 1)
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                else:
                    logger.error(f"Telegram sendMessage failed ({response.status_code}): {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(0.5)
    return False


async def send_telegram_message_with_buttons_and_return(chat_id: str, message: str, buttons: list = None, bot_token: str = None):
    """Send message with buttons and return the message_id for later editing"""
    if not bot_token:
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
    if not bot_token:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            if buttons:
                payload["reply_markup"] = {"inline_keyboard": buttons}
            response = await http_client.post(url, json=payload)
            if response.status_code == 200:
                return response.json().get("result", {}).get("message_id")
    except Exception as e:
        logger.error(f"Failed to send message with return: {e}")
    return None


async def edit_telegram_message(chat_id: str, message_id: int, text: str, buttons: list = None, bot_token: str = None):
    """Edit an existing Telegram message"""
    if not bot_token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML"
            }
            if buttons:
                payload["reply_markup"] = {"inline_keyboard": buttons}
            response = await http_client.post(url, json=payload)
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")
    return False


async def download_telegram_photo(file_id: str, bot_token: str) -> bytes:
    """Download photo from Telegram servers"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
            logger.info(f"Getting file info for: {file_id[:20]}...")
            response = await http_client.get(file_info_url)

            if response.status_code == 200:
                result = response.json()
                if not result.get("ok"):
                    logger.error(f"Telegram API error: {result}")
                    return None

                file_path = result.get("result", {}).get("file_path")
                if file_path:
                    download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
                    logger.info(f"Downloading from: {download_url[:50]}...")
                    file_response = await http_client.get(download_url)
                    if file_response.status_code == 200:
                        logger.info(f"Downloaded {len(file_response.content)} bytes")
                        return file_response.content
                    else:
                        logger.error(f"Download failed with status: {file_response.status_code}")
                else:
                    logger.error(f"No file_path in response: {result}")
            else:
                logger.error(f"getFile failed with status: {response.status_code}, response: {response.text}")
    except Exception as e:
        logger.error(f"Error downloading photo: {e}")
        import traceback
        logger.error(traceback.format_exc())
    return None


async def send_telegram_photo(chat_id: str, photo_url_or_bytes, caption: str, bot_token: str, reply_markup: dict = None) -> dict:
    """Send photo to Telegram chat. Handles URLs, local /api/uploads/ paths, and raw bytes."""
    import os
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            import json
            data = {
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": "HTML"
            }

            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)

            if isinstance(photo_url_or_bytes, str):
                # Check if it's a local /api/uploads/ path - read file and upload directly
                if photo_url_or_bytes.startswith("/api/uploads/"):
                    filename = photo_url_or_bytes.split("/")[-1]
                    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
                    filepath = os.path.join(uploads_dir, filename)
                    if os.path.exists(filepath):
                        with open(filepath, "rb") as f:
                            file_bytes = f.read()
                        files = {"photo": (filename, file_bytes, "image/png")}
                        response = await http_client.post(url, data=data, files=files)
                    else:
                        logger.error(f"Local QR file not found: {filepath}")
                        return None
                else:
                    data["photo"] = photo_url_or_bytes
                    response = await http_client.post(url, data=data)
            else:
                files = {"photo": ("image.jpg", photo_url_or_bytes, "image/jpeg")}
                response = await http_client.post(url, data=data, files=files)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to send photo: {response.text}")
                return None
    except Exception as e:
        logger.error(f"Error sending photo: {e}")
        return None


async def send_telegram_video(chat_id: str, video_file_id: str, caption: str, bot_token: str, reply_markup: dict = None) -> dict:
    """Send video to Telegram chat"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
            import json
            data = {
                "chat_id": chat_id,
                "video": video_file_id,
                "caption": caption,
                "parse_mode": "HTML"
            }

            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)

            response = await http_client.post(url, json=data)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to send video: {response.text}")
                return None
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        return None


async def delete_telegram_message(chat_id: str, message_id: int, bot_token: str) -> bool:
    """Delete a message from Telegram"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/deleteMessage"
            response = await http_client.post(url, json={
                "chat_id": chat_id,
                "message_id": message_id
            })
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        return False


async def kick_user_from_channel(telegram_user_id: str):
    """Kick user from the main channel when payment is unverified"""
    from datetime import datetime, timezone, timedelta
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    channel_id = settings.get("telegram_channel_id", "") or TELEGRAM_CHANNEL_ID

    if not bot_token or not channel_id or not telegram_user_id:
        logger.warning(f"Cannot kick user - missing: token={bool(bot_token)}, channel={bool(channel_id)}, user={bool(telegram_user_id)}")
        return False

    try:
        async with httpx.AsyncClient() as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/banChatMember"
            response = await http_client.post(url, json={
                "chat_id": channel_id,
                "user_id": int(telegram_user_id),
                "until_date": int((datetime.now(timezone.utc) + timedelta(seconds=35)).timestamp())
            })
            logger.info(f"Kick from channel response: {response.status_code} - {response.text}")
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Error kicking user from channel: {e}")
        return False


async def add_to_channel(user_id: str, plan_channel_id: str = None, plan_name: str = "", use_default: bool = True):
    """Add user to private channel by sending invite link"""
    from datetime import datetime, timezone, timedelta
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    if plan_channel_id:
        channel_id = plan_channel_id
        logger.info(f"Using plan-specific channel: {channel_id} for plan '{plan_name}'")
    elif use_default:
        channel_id = settings.get("telegram_channel_id", "") or TELEGRAM_CHANNEL_ID
        logger.warning(f"Plan '{plan_name}' has no channel_id set! Falling back to default channel: {channel_id}")
    else:
        channel_id = ""

    if not bot_token or not channel_id:
        logger.warning("Bot token or channel ID not configured")
        return False
    try:
        async with httpx.AsyncClient() as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/createChatInviteLink"
            response = await http_client.post(url, json={
                "chat_id": channel_id,
                "member_limit": 1,
                "expire_date": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp())
            })
            logger.info(f"Create invite link response: {response.status_code} - {response.text}")
            if response.status_code == 200:
                data = response.json()
                invite_link = data.get("result", {}).get("invite_link")
                if invite_link:
                    msg = f"<b>Welcome!</b>\n\n"
                    if plan_name:
                        msg += f"Plan: <b>{plan_name}</b>\n\n"
                    msg += f"Join your premium channel:\n{invite_link}"
                    await send_telegram_message(user_id, msg, bot_token)
                    return True
        return False
    except Exception as e:
        logger.error(f"Failed to add user to channel: {e}")
        return False


async def remove_from_channel(user_id: str, plan_channel_id: str = None):
    """Remove user from private channel"""
    from datetime import datetime, timezone, timedelta
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    channel_id = plan_channel_id if plan_channel_id else settings.get("telegram_channel_id", "")

    if not bot_token or not channel_id:
        return False
    try:
        async with httpx.AsyncClient() as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/banChatMember"
            response = await http_client.post(url, json={
                "chat_id": channel_id,
                "user_id": int(user_id),
                "until_date": int((datetime.now(timezone.utc) + timedelta(seconds=30)).timestamp())
            })
            logger.info(f"Ban member response: {response.status_code} - {response.text}")
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to remove user from channel: {e}")
        return False


async def send_screenshot_reminders(chat_id: str, username: str, bot_token: str):
    """Send reminder messages until user sends screenshot"""
    reminder_messages = [
        "<b>Reminder!</b>\n\nScreenshot bhejo payment ka!",
        "<b>Hey!</b>\n\nPayment screenshot upload karo!",
        "<b>Screenshot pending!</b>\n\nBina screenshot ke access nahi milega!",
        "<b>Reminder!</b>\n\nScreenshot bhejo!",
        "<b>Waiting...</b>\n\nScreenshot upload karo!",
        "<b>Jaldi karo!</b>\n\nScreenshot bhejo payment ka!",
        "<b>Payment kiya?</b>\n\nScreenshot bhejo!",
        "<b>Pending!</b>\n\nScreenshot upload karo!",
        "<b>Quick!</b>\n\nScreenshot bhejo verify ke liye!",
        "<b>Screenshot?</b>\n\nPayment proof bhejo!",
        "<b>Still waiting...</b>\n\nScreenshot bhejo!",
        "<b>Kaha ho?</b>\n\nScreenshot upload karo!",
        "<b>Hello!</b>\n\nPayment screenshot bhejo!",
        "<b>Pending!</b>\n\nScreenshot bhejo jaldi!",
        "<b>Last chance!</b>\n\nScreenshot bhejo ya discount lo!"
    ]

    for i in range(20):
        await asyncio.sleep(10)

        pending = await db.pending_screenshots.find_one({"telegram_user_id": chat_id, "status": "waiting"}, {"_id": 0})
        if not pending:
            return

        msg = reminder_messages[i] if i < len(reminder_messages) else reminder_messages[i % len(reminder_messages)]
        full_msg = f"@{username if username else 'User'}\n\n{msg}"

        buttons = []
        if i >= 7:
            buttons.append([{"text": "Get Discount!", "callback_data": f"discount_{pending.get('plan_id', '')}"}])
        buttons.append([{"text": "Cancel", "callback_data": "cancel_payment"}])

        await send_telegram_message_with_buttons(chat_id, full_msg, buttons, bot_token)

        await db.pending_screenshots.update_one(
            {"telegram_user_id": chat_id},
            {"$set": {"reminder_count": i + 1}}
        )

    pending = await db.pending_screenshots.find_one({"telegram_user_id": chat_id, "status": "waiting"}, {"_id": 0})
    if pending:
        final_msg = f"<b>Special Offer!</b>\n\n"
        final_msg += "Screenshot nahi mila, but aapke liye special discount!\n\n"
        final_msg += "Screenshot bhejo ya discount lo!"

        buttons = [
            [{"text": "Get Discount!", "callback_data": f"discount_{pending.get('plan_id', '')}"}],
            [{"text": "Cancel", "callback_data": "cancel_payment"}]
        ]
        await send_telegram_message_with_buttons(chat_id, final_msg, buttons, bot_token)


async def urgency_timer_task(chat_id: str, message_id: int, plan: dict, price_display: str, final_price: float, buttons: list, bot_token: str):
    """Background task - live countdown timer with professional styling"""
    try:
        plan_name = plan.get('name', '')
        duration = plan.get('duration_days', 0)

        features_text = ""
        if plan.get('features'):
            for feat in plan['features']:
                features_text += f"    {feat}\n"

        def build_progress_bar(percent):
            """Create sexy Unicode progress bar"""
            total = 15
            filled = int(total * percent / 100)
            empty = total - filled
            bar = "\u2588" * filled + "\u2591" * empty
            return bar

        def format_time(secs):
            """Format seconds as MM:SS"""
            m, s = divmod(secs, 60)
            return f"{m:01d}:{s:02d}"

        payment_info = "\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        payment_info += "\n<b>Payment Methods:</b>\n"
        payment_info += "  \u25b8 UPI / QR Code \u2014 Any UPI app\n"
        payment_info += "  \u25b8 Send screenshot after payment\n\n"
        payment_info += f"<b>Your ID:</b> <code>{chat_id}</code>"

        # Phase 1: Smooth countdown (60s)
        countdown_steps = [55, 50, 45, 40, 35, 30, 25, 20, 15, 10, 5]
        for remaining in countdown_steps:
            await asyncio.sleep(5)

            percent = int((remaining / 60) * 100)
            bar = build_progress_bar(percent)

            if remaining > 30:
                pulse = "\u23f3"
            elif remaining > 15:
                pulse = "\u26a1"
            else:
                pulse = "\ud83d\udd25"

            msg = f"{pulse} <b>LIMITED TIME OFFER</b> {pulse}\n"
            msg += "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
            msg += f"\ud83c\udf1f <b>{plan_name}</b>\n\n"
            msg += f"    \ud83d\udcb0 Price: <b>{price_display}</b>\n"
            msg += f"    \ud83d\udcc5 Duration: <b>{duration} days</b>\n"
            if features_text:
                msg += f"    \ud83c\udfaf Features:\n{features_text}"
            msg += f"\n\u23f1 <b>Offer ends in {format_time(remaining)}</b>\n\n"
            msg += f"<code>{bar}</code>  {percent}%"
            msg += payment_info

            await edit_telegram_message(chat_id, message_id, msg, buttons, bot_token)

        # Phase 2: LAST CHANCE - high urgency (60s)
        await asyncio.sleep(5)

        urgency_steps = list(range(55, -1, -5))
        for i, remaining in enumerate(urgency_steps):
            warn = "\ud83d\udea8" if i % 2 == 0 else "\u26a0\ufe0f"
            percent = int((remaining / 60) * 100)
            bar = build_progress_bar(percent)

            msg = f"{warn} <b>LAST CHANCE</b> {warn}\n"
            msg += "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
            msg += f"\ud83d\udc8e <b>{plan_name}</b>\n\n"
            msg += f"    \ud83d\udcb0 <b>{price_display}</b>  \u00b7  {duration} days\n"
            if features_text:
                msg += f"    \ud83c\udfaf Features:\n{features_text}"

            if remaining > 30:
                msg += f"\n\u23f1 <b>{remaining}s remaining</b>\n\n"
            elif remaining > 10:
                msg += f"\n\ud83d\udd25 <b>Only {remaining}s left!</b>\n\n"
            elif remaining > 0:
                msg += f"\n\ud83d\udea8 <b>HURRY! {remaining}s!</b>\n\n"
            else:
                msg += f"\n\u203c\ufe0f <b>TIME'S UP!</b>\n\n"

            msg += f"<code>{bar}</code>  {percent}%"
            msg += payment_info

            await edit_telegram_message(chat_id, message_id, msg, buttons, bot_token)

            if remaining > 0:
                await asyncio.sleep(5)

        # Phase 3: Timer ended - still encouraging
        await asyncio.sleep(5)

        msg = "\u2728 <b>OFFER STILL AVAILABLE</b> \u2728\n"
        msg += "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
        msg += f"\ud83d\udc8e <b>{plan_name}</b>\n\n"
        msg += f"    \ud83d\udcb0 Price: <b>{price_display}</b>\n"
        msg += f"    \ud83d\udcc5 Duration: <b>{duration} days</b>\n"
        if features_text:
            msg += f"    \ud83c\udfaf Features:\n{features_text}"
        msg += "\n\ud83d\udcac Timer ended but you can still grab this!\n"
        msg += "<b>Don't miss out \u2014 purchase now!</b>"
        msg += payment_info

        await edit_telegram_message(chat_id, message_id, msg, buttons, bot_token)

    except Exception as e:
        logger.error(f"Error in urgency timer: {e}")


async def is_admin_or_creator(telegram_user_id: str, telegram_username: str = "") -> bool:
    """Check if user is admin, creator, or telegram admin"""
    tg_admin = await db.telegram_admins.find_one({
        "$or": [
            {"telegram_user_id": str(telegram_user_id)},
            {"telegram_username": telegram_username}
        ],
        "is_active": True
    }, {"_id": 0})

    if tg_admin:
        return True

    creator = await db.creators.find_one({
        "$or": [
            {"telegram_user_id": str(telegram_user_id)},
            {"telegram_username": telegram_username}
        ],
        "is_active": True
    }, {"_id": 0})

    if creator:
        return True

    admin_user = await db.users.find_one({
        "$or": [
            {"telegram_user_id": str(telegram_user_id)},
            {"telegram_username": telegram_username}
        ],
        "role": {"$in": ["admin", "super_admin"]}
    }, {"_id": 0})

    return admin_user is not None


async def notify_admin_new_payment(user_id: str, username: str, plan_name: str, amount: float, screenshot_file_id: str = None, payment_id: str = None, payment_status: str = "pending"):
    """Notify admin about new payment via Telegram with screenshot and Approve/Reject buttons"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    admins = await db.telegram_admins.find({"is_active": True}, {"_id": 0}).to_list(100)
    creators = await db.creators.find({"is_active": True}, {"_id": 0}).to_list(100)

    admin_ids = set()
    for a in admins:
        if a.get("telegram_user_id"):
            admin_ids.add(a["telegram_user_id"])
    for c in creators:
        if c.get("telegram_user_id"):
            admin_ids.add(c["telegram_user_id"])

    if not admin_ids:
        return

    if payment_status == "verified":
        msg = "✅ <b>Payment Auto-Verified!</b>\n\n"
    else:
        msg = "🔔 <b>New Payment - Admin Review Required!</b>\n\n"
    
    msg += f"👤 User: @{username} (<code>{user_id}</code>)\n" if username else f"👤 User: <code>{user_id}</code>\n"
    msg += f"📦 Plan: <b>{plan_name}</b>\n"
    msg += f"💰 Amount: <b>Rs.{amount}</b>\n"
    msg += f"🕐 Time: <b>{datetime.now(timezone.utc).strftime('%d %b %Y %I:%M %p')} UTC</b>\n"
    
    if payment_id:
        msg += f"🆔 Payment: <code>{payment_id[:8]}...</code>\n"

    # Build inline keyboard for Approve/Reject
    reply_markup = None
    if payment_id:
        if payment_status == "verified":
            reply_markup = {"inline_keyboard": [
                [{"text": "✅ Auto-Verified", "callback_data": "noop"}],
                [{"text": "❌ Revoke & Reject", "callback_data": f"admin_reject_{payment_id}"}]
            ]}
        else:
            reply_markup = {"inline_keyboard": [
                [
                    {"text": "✅ Approve", "callback_data": f"admin_approve_{payment_id}"},
                    {"text": "❌ Reject", "callback_data": f"admin_reject_{payment_id}"}
                ]
            ]}

    for admin_id in admin_ids:
        try:
            if screenshot_file_id and bot_token:
                await send_telegram_photo(
                    admin_id,
                    screenshot_file_id,
                    msg,
                    bot_token,
                    reply_markup
                )
            elif reply_markup:
                await send_telegram_message_with_buttons(
                    admin_id,
                    msg,
                    reply_markup["inline_keyboard"],
                    bot_token
                )
            else:
                await send_telegram_message(admin_id, msg, bot_token)
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
