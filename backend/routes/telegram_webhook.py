"""Telegram webhook — thin dispatcher that delegates to handler modules.
Refactored from 4300+ lines into modular handlers:
- webhook_handlers/channel_posts.py — channel post + member welcome
- webhook_handlers/callbacks.py — all button click handlers
- webhook_handlers/messages.py — commands, screenshots, AI chat, admin
"""
from fastapi import APIRouter, BackgroundTasks, Request
from services.telegram import get_bot_settings
from services.tenant import DEFAULT_TENANT_ID
from config import logger
from rate_limiter import limiter

# Handler modules
from webhook_handlers.channel_posts import handle_channel_post, handle_member_update
from webhook_handlers.callbacks import handle_callback
from webhook_handlers.messages import handle_message

router = APIRouter()


@router.post("/telegram/webhook")
@limiter.limit("300/minute")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        logger.info(f"Webhook received: {data}")

        # Resolve bot context
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
        bot_tenant_id = settings.get("tenant_id") or DEFAULT_TENANT_ID

        if not bot_token:
            logger.error("BOT TOKEN NOT FOUND! Check database settings or TELEGRAM_BOT_TOKEN env var")
        else:
            logger.info(f"Bot token loaded: {bot_token[:10]}...")

        # Dispatch to appropriate handler
        if data.get("channel_post"):
            return await handle_channel_post(data, bot_token, bot_tenant_id, settings)

        elif data.get("chat_member"):
            return await handle_member_update(data, bot_token, bot_tenant_id, settings)

        elif data.get("callback_query"):
            return await handle_callback(data, bot_token, bot_tenant_id, settings, background_tasks)

        elif data.get("message"):
            return await handle_message(data, bot_token, bot_tenant_id, settings, background_tasks)

        return {"ok": True}

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"ok": True}
