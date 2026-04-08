"""Razorpay Payment Link callback handler - auto-verify bot payments with idempotency"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from database import db
from services.telegram import get_bot_settings, send_telegram_message, send_telegram_message_with_buttons, add_to_channel
from services.bot_activity import log_bot_activity
from config import logger, RAZORPAY_KEY_SECRET
from datetime import datetime, timezone, timedelta
import hmac
import hashlib
import uuid
import asyncio

router = APIRouter()


async def acquire_idempotency_lock(key: str, ttl_seconds: int = 300) -> bool:
    """Acquire an idempotency lock to prevent double-processing.
    Returns True if this is the FIRST call with this key."""
    now = datetime.now(timezone.utc)
    try:
        result = await db.idempotency_keys.find_one_and_update(
            {
                "key": key,
                "$or": [
                    {"expires_at": {"$lt": now.isoformat()}},
                    {"expires_at": {"$exists": False}},
                ]
            },
            {
                "$setOnInsert": {
                    "key": key,
                    "created_at": now.isoformat(),
                },
                "$set": {
                    "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
                    "status": "processing",
                }
            },
            upsert=True,
            return_document=False,  # Returns the doc BEFORE update (None if new)
        )
        # If result is None, this was an insert (first call) → lock acquired
        # If result exists but expired, we got the update → lock acquired
        return True
    except Exception as e:
        # DuplicateKeyError means another worker got there first
        if "duplicate" in str(e).lower() or "E11000" in str(e):
            return False
        logger.error(f"Idempotency lock error: {e}")
        return False


async def mark_idempotency_complete(key: str, result_data: dict = None):
    """Mark an idempotency key as complete with optional result data."""
    await db.idempotency_keys.update_one(
        {"key": key},
        {"$set": {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result": result_data or {},
        }}
    )


def verify_razorpay_signature(params: dict) -> bool:
    """Verify Razorpay payment link callback signature"""
    if not RAZORPAY_KEY_SECRET:
        logger.error("RAZORPAY_KEY_SECRET not configured")
        return False

    try:
        payment_link_id = params.get("razorpay_payment_link_id", "")
        payment_link_ref = params.get("razorpay_payment_link_reference_id", "")
        payment_link_status = params.get("razorpay_payment_link_status", "")
        razorpay_payment_id = params.get("razorpay_payment_id", "")
        signature = params.get("razorpay_signature", "")

        message = f"{payment_link_id}|{payment_link_ref}|{payment_link_status}|{razorpay_payment_id}"

        expected = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)
    except Exception as e:
        logger.error(f"Razorpay signature verification error: {e}")
        return False


@router.get("/razorpay/callback")
async def razorpay_payment_callback(request: Request):
    """Handle Razorpay payment link callback after successful payment.
    Protected by idempotency lock to prevent double-crediting."""
    params = dict(request.query_params)
    logger.info(f"Razorpay callback received: {params}")

    payment_link_id = params.get("razorpay_payment_link_id", "")
    razorpay_payment_id = params.get("razorpay_payment_id", "")
    payment_status = params.get("razorpay_payment_link_status", "")

    # Find the pending order in our DB
    order = await db.razorpay_bot_orders.find_one(
        {"payment_link_id": payment_link_id},
        {"_id": 0}
    )

    if not order:
        logger.error(f"Razorpay callback - order not found for link: {payment_link_id}")
        return HTMLResponse(content=_error_html("Payment record not found. Contact admin."), status_code=404)

    # Check if already processed
    if order.get("status") == "paid":
        return HTMLResponse(content=_success_html(order.get("plan_name", "Plan")))

    # Verify signature
    if not verify_razorpay_signature(params):
        logger.error(f"Razorpay callback - invalid signature for link: {payment_link_id}")
        return HTMLResponse(content=_error_html("Payment verification failed. Contact admin."), status_code=400)

    if payment_status != "paid":
        logger.warning(f"Razorpay callback - status not paid: {payment_status}")
        return HTMLResponse(content=_error_html("Payment not completed. Try again."), status_code=400)

    # Idempotency lock — prevents double-crediting on retry/duplicate callbacks
    idempotency_key = f"razorpay_callback_{payment_link_id}_{razorpay_payment_id}"
    if not await acquire_idempotency_lock(idempotency_key, ttl_seconds=600):
        logger.warning(f"Razorpay callback duplicate detected: {idempotency_key}")
        return HTMLResponse(content=_success_html(order.get("plan_name", "Plan")))

    # Payment verified! Process subscription or paid post unlock
    chat_id = order.get("chat_id", "")
    plan_id = order.get("plan_id", "")
    plan_name = order.get("plan_name", "")
    duration_days = order.get("duration_days", 30)
    amount = order.get("amount", 0)
    username = order.get("username", "")
    tenant_id = order.get("tenant_id", "default")
    unlock_post_id = order.get("unlock_post_id", "")
    order_type = order.get("type", "subscription")

    try:
        # Update order status
        await db.razorpay_bot_orders.update_one(
            {"payment_link_id": payment_link_id},
            {"$set": {
                "status": "paid",
                "razorpay_payment_id": razorpay_payment_id,
                "paid_at": datetime.now(timezone.utc).isoformat()
            }}
        )

        now = datetime.now(timezone.utc)

        # ===== PAID POST UNLOCK =====
        if order_type == "paid_post_unlock" and unlock_post_id:
            paid_post = await db.paid_posts.find_one(
                {"id": unlock_post_id, "is_active": True, "tenant_id": tenant_id},
                {"_id": 0}
            )

            # Create payment record
            payment_id = str(uuid.uuid4())[:8]
            payment_record = {
                "id": payment_id,
                "telegram_user_id": chat_id,
                "telegram_username": username,
                "plan_id": "", "plan_name": plan_name,
                "amount": amount,
                "payment_method": "razorpay",
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_payment_link_id": payment_link_id,
                "status": "verified",
                "type": "paid_post_unlock",
                "unlock_post_id": unlock_post_id,
                "verified_at": now.isoformat(),
                "tenant_id": tenant_id,
                "created_at": now.isoformat()
            }
            await db.payments.insert_one(payment_record)

            # Save unlock record
            unlock_record = {
                "id": str(uuid.uuid4()),
                "post_id": unlock_post_id,
                "telegram_user_id": chat_id,
                "telegram_username": username,
                "payment_id": payment_id,
                "payment_method": "razorpay",
                "amount": amount,
                "tenant_id": tenant_id,
                "unlocked_at": now.isoformat()
            }
            await db.paid_post_unlocks.insert_one(unlock_record)

            # Update unlock count
            await db.paid_posts.update_one(
                {"id": unlock_post_id, "tenant_id": tenant_id},
                {"$inc": {"unlock_count": 1}}
            )

            # Clean up pending screenshots
            await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})

            # Send unlocked content via Telegram
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")

            if bot_token and paid_post:
                from services.telegram import send_telegram_photo, send_telegram_video

                success_msg = "✅ <b>Payment Successful!</b>\n\n🔓 Unlocking your content..."
                await send_telegram_message(chat_id, success_msg, bot_token)

                if paid_post.get("content_type") == "photo" and paid_post.get("original_file_id"):
                    caption = f"🔓 <b>Unlocked!</b>\n\n{paid_post.get('caption', '')}"
                    await send_telegram_photo(chat_id, paid_post["original_file_id"], caption, bot_token)
                elif paid_post.get("content_type") == "video" and paid_post.get("original_file_id"):
                    caption = f"🔓 <b>Unlocked Video!</b>\n\n{paid_post.get('caption', '')}"
                    await send_telegram_video(chat_id, paid_post["original_file_id"], caption, bot_token)
                else:
                    await send_telegram_message(chat_id, f"🔓 <b>Unlocked!</b>\n\n{paid_post.get('caption', 'Content unlocked!')}", bot_token)
            elif bot_token:
                await send_telegram_message(chat_id, "✅ <b>Payment Successful!</b>\n\n⚠️ Content not found. Contact admin.", bot_token)

            asyncio.create_task(log_bot_activity(
                "razorpay_unlock", chat_id, username,
                f"Paid ₹{int(amount)} to unlock post {unlock_post_id[:8]}"
            ))

            logger.info(f"Razorpay unlock processed: user={chat_id}, post={unlock_post_id}, amount=₹{amount}")
            await mark_idempotency_complete(idempotency_key, {"payment_id": payment_id, "post_id": unlock_post_id})
            return HTMLResponse(content=_success_html(f"Content Unlocked - ₹{int(amount)}"))

        # ===== REGULAR SUBSCRIPTION =====
        # Create/update payment record
        payment_id = str(uuid.uuid4())[:8]
        end_date = now + timedelta(days=duration_days)

        payment_record = {
            "id": payment_id,
            "telegram_user_id": chat_id,
            "telegram_username": username,
            "plan_id": plan_id,
            "plan_name": plan_name,
            "amount": amount,
            "payment_method": "razorpay",
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_payment_link_id": payment_link_id,
            "status": "verified",
            "verified_at": now.isoformat(),
            "tenant_id": tenant_id,
            "created_at": now.isoformat()
        }
        await db.payments.insert_one(payment_record)

        # Create/update subscriber
        await db.subscribers.update_one(
            {"telegram_user_id": chat_id, "tenant_id": tenant_id},
            {"$set": {
                "telegram_user_id": chat_id,
                "telegram_username": username,
                "plan_id": plan_id,
                "plan_name": plan_name,
                "status": "active",
                "start_date": now.isoformat(),
                "end_date": end_date.isoformat(),
                "payment_method": "razorpay",
                "last_payment_id": payment_id,
                "tenant_id": tenant_id,
                "updated_at": now.isoformat()
            }, "$setOnInsert": {
                "id": str(uuid.uuid4())[:8],
                "created_at": now.isoformat()
            }},
            upsert=True
        )

        # Clean up pending screenshots if any
        await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})

        # Send success message via Telegram
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")

        if bot_token:
            success_msg = "🎉 <b>Payment Successful!</b>\n\n"
            success_msg += f"📦 Plan: <b>{plan_name}</b>\n"
            success_msg += f"💰 Amount: <b>₹{int(amount)}</b>\n"
            success_msg += f"⏱ Duration: <b>{duration_days} days</b>\n"
            success_msg += f"📅 Expires: <b>{end_date.strftime('%d %b %Y')}</b>\n\n"
            success_msg += "✅ <b>Your subscription is now active!</b>\n"
            success_msg += "Enjoy premium content! 🔥"

            buttons = [[{"text": "📊 Check My Status", "callback_data": "check_status"}]]
            await send_telegram_message_with_buttons(chat_id, success_msg, buttons, bot_token)

            # Try to add user to plan-specific channel
            plan_data = await db.plans.find_one({"id": plan_id, "tenant_id": tenant_id}, {"_id": 0, "channel_id": 1})
            plan_channel_id = plan_data.get("channel_id", "") if plan_data else ""
            try:
                await add_to_channel(chat_id, plan_channel_id=plan_channel_id, plan_name=plan_name)
            except Exception as e:
                logger.error(f"Failed to add user to channel after Razorpay payment: {e}")

        # Log activity
        asyncio.create_task(log_bot_activity(
            "razorpay_payment", chat_id, username,
            f"Paid ₹{int(amount)} for {plan_name} via Razorpay"
        ))

        logger.info(f"Razorpay payment processed: user={chat_id}, plan={plan_name}, amount=₹{amount}")
        await mark_idempotency_complete(idempotency_key, {"payment_id": payment_id, "plan": plan_name})
        return HTMLResponse(content=_success_html(plan_name))

    except Exception as e:
        logger.error(f"Razorpay callback processing error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return HTMLResponse(content=_error_html("Something went wrong. Contact admin."), status_code=500)


def _success_html(plan_name: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Payment Successful</title>
<style>
body{{margin:0;padding:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#0a0a0a;font-family:system-ui,sans-serif;color:#fff}}
.card{{background:#111;border:2px solid #a3e635;border-radius:20px;padding:40px;text-align:center;max-width:400px}}
.icon{{font-size:64px;margin-bottom:16px}}
h1{{color:#a3e635;margin:0 0 12px}}
p{{color:#999;margin:8px 0}}
.plan{{color:#fff;font-weight:bold;font-size:18px}}
.btn{{display:inline-block;margin-top:20px;padding:12px 32px;background:#a3e635;color:#000;
border-radius:12px;text-decoration:none;font-weight:bold;font-size:16px}}
</style></head>
<body><div class="card">
<div class="icon">✅</div>
<h1>Payment Successful!</h1>
<p class="plan">{plan_name}</p>
<p>Your subscription is now active. Go back to Telegram to enjoy premium content!</p>
<a class="btn" href="https://t.me">Open Telegram</a>
</div></body></html>"""


def _error_html(message: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Payment Error</title>
<style>
body{{margin:0;padding:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#0a0a0a;font-family:system-ui,sans-serif;color:#fff}}
.card{{background:#111;border:2px solid #ef4444;border-radius:20px;padding:40px;text-align:center;max-width:400px}}
.icon{{font-size:64px;margin-bottom:16px}}
h1{{color:#ef4444;margin:0 0 12px}}
p{{color:#999;margin:8px 0}}
.btn{{display:inline-block;margin-top:20px;padding:12px 32px;background:#333;color:#fff;
border-radius:12px;text-decoration:none;font-weight:bold}}
</style></head>
<body><div class="card">
<div class="icon">❌</div>
<h1>Payment Error</h1>
<p>{message}</p>
<a class="btn" href="https://t.me">Back to Telegram</a>
</div></body></html>"""
