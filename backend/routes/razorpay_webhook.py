"""Razorpay Payment Link callback handler - auto-verify bot payments"""
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
    """Handle Razorpay payment link callback after successful payment"""
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

    # Payment verified! Process subscription
    chat_id = order.get("chat_id", "")
    plan_id = order.get("plan_id", "")
    plan_name = order.get("plan_name", "")
    duration_days = order.get("duration_days", 30)
    amount = order.get("amount", 0)
    username = order.get("username", "")
    tenant_id = order.get("tenant_id", "default")

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

        # Create/update payment record
        payment_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)
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

            # Try to add user to channel
            channel_id = settings.get("telegram_channel_id", "")
            if channel_id:
                try:
                    await add_to_channel(chat_id, bot_token)
                except Exception as e:
                    logger.error(f"Failed to add user to channel after Razorpay payment: {e}")

        # Log activity
        asyncio.create_task(log_bot_activity(
            "razorpay_payment", chat_id, username,
            f"Paid ₹{int(amount)} for {plan_name} via Razorpay"
        ))

        logger.info(f"Razorpay payment processed: user={chat_id}, plan={plan_name}, amount=₹{amount}")
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
