"""Mini App endpoints - Plans, Payments, Support AI, Referral, Notifications"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form, Query, Header
from database import db
from services.telegram import get_bot_settings, send_telegram_message, send_telegram_photo, add_to_channel
from services.payment import analyze_payment_screenshot_with_ai
from services.telegram_verify import validate_telegram_init_data
from services.tenant import (
    DEFAULT_TENANT_ID, resolve_tenant_from_admin_tg_id, tenant_query
)
from config import logger, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, razorpay_client, EMERGENT_LLM_KEY
from datetime import datetime, timezone, timedelta
import uuid
import json
import os
import base64
import qrcode
from io import BytesIO
from PIL import Image

router = APIRouter(prefix="/miniapp")


async def _get_verified_tg_user(
    tg_id: str = "",
    x_telegram_init_data: str = Header(default="", alias="X-Telegram-Init-Data"),
) -> str:
    """Get verified Telegram user ID. Checks initData first, falls back to tg_id param for dev."""
    if x_telegram_init_data:
        settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
        bot_token = settings.get("telegram_bot_token", "")
        if bot_token:
            user = validate_telegram_init_data(x_telegram_init_data, bot_token)
            if user:
                return str(user.get("id", ""))
            logger.warning(f"Invalid Telegram initData received")
    # Fallback to tg_id param (dev/browser testing)
    return tg_id


# ============== PHONE LOGIN ==============

@router.post("/phone-login")
async def miniapp_phone_login(data: dict):
    """Register/login with phone number for Mini App, gives 20% discount"""
    phone = data.get("phone", "").strip()
    telegram_user_id = data.get("telegram_user_id", "")
    telegram_username = data.get("telegram_username", "")

    if not phone or len(phone) < 10:
        return {"success": False, "error": "Enter a valid phone number"}

    # Check if already registered
    existing = await db.miniapp_users.find_one(
        {"telegram_user_id": telegram_user_id}, {"_id": 0}
    )
    if existing:
        return {
            "success": True,
            "discount": 20,
            "already_registered": True,
            "message": "Welcome back! Your 20% discount is active."
        }

    # Register new user
    tenant_id = data.get("tenant_id", DEFAULT_TENANT_ID)
    user_doc = {
        "id": str(uuid.uuid4()),
        "phone": phone,
        "telegram_user_id": telegram_user_id,
        "telegram_username": telegram_username,
        "discount_percent": 20,
        "tenant_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.miniapp_users.insert_one(user_doc)

    return {
        "success": True,
        "discount": 20,
        "already_registered": False,
        "message": "You've unlocked 20% OFF on all plans!"
    }


@router.get("/user-discount/{telegram_user_id}")
async def miniapp_get_user_discount(telegram_user_id: str):
    """Check if user has phone login discount"""
    user = await db.miniapp_users.find_one(
        {"telegram_user_id": telegram_user_id}, {"_id": 0}
    )
    if user:
        return {"has_discount": True, "discount_percent": 20, "phone": user.get("phone", "")}
    return {"has_discount": False, "discount_percent": 0}


# ============== UPI DETAILS ==============

def _generate_upi_qr(upi_id: str, upi_name: str = "") -> str:
    """Generate a UPI QR code image and save to uploads, returns relative URL"""
    upi_url = f"upi://pay?pa={upi_id}&pn={upi_name}&cu=INR"
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    uploads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(uploads_path, exist_ok=True)
    filename = f"qr_auto_{upi_id.replace('@','_')}.png"
    filepath = os.path.join(uploads_path, filename)
    img.save(filepath)
    return f"/api/uploads/{filename}"


def _is_valid_qr_file(qr_url: str) -> bool:
    """Check if a local QR code file exists and is actually a QR code (not a random photo)"""
    if not qr_url or qr_url.startswith("http"):
        return bool(qr_url and qr_url.startswith("http"))
    # Local file - check if it exists
    filename = qr_url.split("/")[-1]
    uploads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    filepath = os.path.join(uploads_path, filename)
    if not os.path.exists(filepath):
        return False
    # Quick check: QR codes have very few unique colors (2-5), photos have 100+
    try:
        img = Image.open(filepath)
        pixels = img.load()
        colors = set()
        step = max(1, img.width // 20)  # Sample every Nth pixel for speed
        for x in range(0, img.width, step):
            for y in range(0, img.height, step):
                colors.add(pixels[x, y])
                if len(colors) > 20:
                    return False  # Too many colors = photo, not QR
        return True
    except Exception:
        return False


@router.get("/upi-details")
async def miniapp_get_upi_details():
    """Get UPI payment details for manual payment. Auto-generates QR from UPI ID if missing."""
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    upi_id = settings.get("payment_upi_id") or settings.get("upi_id", "")
    upi_name = settings.get("upi_name", "")
    qr_url = settings.get("qr_code_url", "")
    
    # Auto-generate QR if: no URL, file missing, or file is not actually a QR code
    if upi_id and not _is_valid_qr_file(qr_url):
        qr_url = _generate_upi_qr(upi_id, upi_name)
        # Save back to DB so it persists
        await db.settings.update_one(
            {"id": "bot_settings"}, 
            {"$set": {"qr_code_url": qr_url}},
            upsert=True
        )
        logger.info(f"Auto-generated QR code for UPI: {upi_id} -> {qr_url}")
    
    return {
        "upi_id": upi_id,
        "qr_code_url": qr_url,
        "payment_message": settings.get("payment_instructions") or settings.get("payment_message", "Send payment screenshot to the bot after paying via UPI.")
    }


# ============== PLANS ==============

@router.get("/plans")
async def miniapp_get_plans():
    """Get active plans for Mini App (public, no auth)"""
    plans = await db.plans.find({"is_active": True}, {"_id": 0}).sort("price", 1).to_list(50)
    return plans


# ============== SUBSCRIPTION STATUS ==============

@router.get("/status/{telegram_user_id}")
async def miniapp_get_status(telegram_user_id: str):
    """Get user subscription status"""
    sub = await db.subscribers.find_one(
        {"telegram_user_id": telegram_user_id, "status": "active"},
        {"_id": 0}
    )
    if sub:
        end_date = sub.get("end_date", "")
        days_remaining = 0
        total_days = 30
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                days_remaining = max(0, (end_dt - now).days)
                start_date = sub.get("start_date", "")
                if start_date:
                    start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                    total_days = max(1, (end_dt - start_dt).days)
            except Exception:
                pass
        return {
            "is_active": True,
            "plan_id": sub.get("plan_id", ""),
            "plan_name": sub.get("plan_name", "N/A"),
            "start_date": sub.get("start_date"),
            "end_date": sub.get("end_date"),
            "days_remaining": days_remaining,
            "total_days": total_days,
        }
    return {"is_active": False}


# ============== COUPON VALIDATION ==============

@router.post("/apply-coupon")
async def miniapp_apply_coupon(data: dict):
    """Validate and apply coupon code in Mini App"""
    code = data.get("code", "").upper().strip()
    plan_id = data.get("plan_id")
    amount = float(data.get("amount", 0))

    if not code:
        return {"valid": False, "error": "Enter a coupon code"}

    coupon = await db.coupons.find_one({"code": code, "is_active": True}, {"_id": 0})
    if not coupon:
        return {"valid": False, "error": "Invalid coupon code"}

    # Check expiry
    if coupon.get("valid_until"):
        expiry = datetime.fromisoformat(coupon["valid_until"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expiry:
            return {"valid": False, "error": "Coupon expired"}

    # Usage limit
    if coupon.get("max_uses", 0) > 0 and coupon.get("used_count", 0) >= coupon["max_uses"]:
        return {"valid": False, "error": "Coupon usage limit reached"}

    # Min purchase
    if amount < coupon.get("min_purchase", 0):
        return {"valid": False, "error": f"Minimum purchase ₹{coupon['min_purchase']} required"}

    # Applicable plans
    if coupon.get("applicable_plans") and plan_id not in coupon["applicable_plans"]:
        return {"valid": False, "error": "Coupon not valid for this plan"}

    # Calculate discount
    if coupon["discount_type"] == "percentage":
        discount = (amount * coupon["discount_value"]) / 100
    else:
        discount = coupon["discount_value"]

    final_amount = max(0, round(amount - discount))

    return {
        "valid": True,
        "discount": round(discount),
        "final_amount": final_amount,
        "coupon_code": coupon["code"],
        "discount_type": coupon["discount_type"],
        "discount_value": coupon["discount_value"]
    }


# ============== RAZORPAY PAYMENT ==============

@router.post("/create-order")
async def miniapp_create_razorpay_order(data: dict):
    """Create a Razorpay order for Mini App payment"""
    if not razorpay_client:
        raise HTTPException(status_code=400, detail="Razorpay not configured")

    plan_id = data.get("plan_id")
    telegram_user_id = data.get("telegram_user_id", "")
    telegram_username = data.get("telegram_username", "")
    coupon_code = data.get("coupon_code")
    amount = float(data.get("amount", 0))

    plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # If coupon applied, use the provided discounted amount, else use plan price
    final_amount = amount if amount > 0 else plan["price"]

    # Verify coupon discount server-side
    if coupon_code:
        coupon = await db.coupons.find_one({"code": coupon_code.upper().strip(), "is_active": True}, {"_id": 0})
        if coupon:
            if coupon["discount_type"] == "percentage":
                discount = (plan["price"] * coupon["discount_value"]) / 100
            else:
                discount = coupon["discount_value"]
            final_amount = max(1, round(plan["price"] - discount))

    # Create Razorpay order (amount in paise)
    order_data = {
        "amount": int(final_amount * 100),
        "currency": "INR",
        "receipt": f"miniapp_{uuid.uuid4().hex[:20]}",
        "payment_capture": 1
    }

    try:
        razor_order = razorpay_client.order.create(order_data)
    except Exception as e:
        logger.error(f"Razorpay order creation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create payment order")

    # Store order in DB
    tenant_id = data.get("tenant_id", DEFAULT_TENANT_ID)
    order_doc = {
        "id": str(uuid.uuid4()),
        "razorpay_order_id": razor_order["id"],
        "plan_id": plan_id,
        "plan_name": plan["name"],
        "amount": final_amount,
        "original_amount": plan["price"],
        "coupon_code": coupon_code,
        "telegram_user_id": telegram_user_id,
        "telegram_username": telegram_username,
        "status": "created",
        "source": "miniapp",
        "tenant_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.bot_orders.insert_one(order_doc)

    return {
        "order_id": razor_order["id"],
        "amount": final_amount,
        "key_id": RAZORPAY_KEY_ID,
        "plan_name": plan["name"],
        "currency": "INR"
    }


@router.post("/verify-payment")
async def miniapp_verify_payment(data: dict, background_tasks: BackgroundTasks):
    """Verify Razorpay payment from Mini App and activate subscription"""
    if not razorpay_client:
        raise HTTPException(status_code=400, detail="Razorpay not configured")

    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })
    except Exception as e:
        logger.error(f"Mini App payment verification failed: {e}")
        raise HTTPException(status_code=400, detail="Payment verification failed")

    # Get order
    order = await db.bot_orders.find_one({"razorpay_order_id": data['razorpay_order_id']}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Update order
    await db.bot_orders.update_one(
        {"razorpay_order_id": data['razorpay_order_id']},
        {"$set": {"status": "paid", "razorpay_payment_id": data['razorpay_payment_id']}}
    )

    # Get plan
    plan = await db.plans.find_one({"id": order["plan_id"]}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    telegram_user_id = data.get("telegram_user_id") or order.get("telegram_user_id")
    telegram_username = order.get("telegram_username", "")

    # Increment coupon usage
    if order.get("coupon_code"):
        await db.coupons.update_one(
            {"code": order["coupon_code"].upper()},
            {"$inc": {"used_count": 1}}
        )

    # Create payment record
    payment_obj = {
        "id": str(uuid.uuid4()),
        "subscriber_id": None,
        "telegram_user_id": telegram_user_id,
        "telegram_username": telegram_username,
        "amount": order["amount"],
        "plan_id": order["plan_id"],
        "plan_name": plan["name"],
        "payment_method": "razorpay",
        "razorpay_order_id": data['razorpay_order_id'],
        "razorpay_payment_id": data['razorpay_payment_id'],
        "coupon_code": order.get("coupon_code"),
        "status": "verified",
        "source": "miniapp",
        "tenant_id": order.get("tenant_id", DEFAULT_TENANT_ID),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payments.insert_one(payment_obj)

    # Create subscriber
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    grace_days = settings.get("grace_period_days", 2)
    bot_token = settings.get("telegram_bot_token", "")

    end_date = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])
    grace_end = end_date + timedelta(days=grace_days)

    subscriber_obj = {
        "id": str(uuid.uuid4()),
        "telegram_user_id": telegram_user_id,
        "telegram_username": telegram_username,
        "plan_id": plan["id"],
        "plan_name": plan["name"],
        "payment_method": "razorpay",
        "payment_id": payment_obj["id"],
        "status": "active",
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": end_date.isoformat(),
        "grace_end_date": grace_end.isoformat(),
        "reminder_sent": False,
        "tenant_id": order.get("tenant_id", DEFAULT_TENANT_ID),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.subscribers.insert_one(subscriber_obj)

    # Add to channel
    plan_channel = plan.get("channel_id", "")
    if plan_channel and bot_token:
        background_tasks.add_task(add_to_channel, telegram_user_id, plan_channel, plan["name"])

    # Send Telegram success message
    if bot_token and telegram_user_id:
        success_msg = "🎉 <b>Payment Successful!</b>\n\n"
        success_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
        success_msg += f"💰 Amount: <b>₹{order['amount']}</b>\n"
        success_msg += f"📅 Valid till: <b>{end_date.strftime('%d %b %Y')}</b>\n\n"
        success_msg += "✅ Your subscription is now active!"
        background_tasks.add_task(send_telegram_message, telegram_user_id, success_msg)

    return {
        "success": True,
        "plan_name": plan["name"],
        "end_date": end_date.isoformat(),
        "amount": order["amount"]
    }


# ============== PAYMENT HISTORY ==============

@router.get("/payments/{telegram_user_id}")
async def miniapp_payment_history(telegram_user_id: str):
    """Get payment history for a Telegram user"""
    payments = await db.payments.find(
        {"telegram_user_id": telegram_user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return payments



@router.post("/upload-screenshot")
async def miniapp_upload_screenshot(
    file: UploadFile = File(...),
    telegram_user_id: str = Form(""),
    plan_id: str = Form(""),
    plan_name: str = Form(""),
    amount: float = Form(0),
):
    """Upload payment screenshot from Mini App, run AI verification, create payment record"""
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    # Read image bytes
    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    
    # Save screenshot locally
    uploads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(uploads_path, exist_ok=True)
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"ss_{uuid.uuid4().hex[:10]}.{ext}"
    filepath = os.path.join(uploads_path, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    
    screenshot_url = f"/api/uploads/{filename}"
    
    # Get settings for AI verification context
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    expected_upi = settings.get("payment_upi_id") or settings.get("upi_id", "")
    
    # Create payment record
    payment_id = str(uuid.uuid4())
    bot_user = await db.bot_users.find_one({"telegram_user_id": str(telegram_user_id)}, {"_id": 0})
    
    payment = {
        "id": payment_id,
        "telegram_user_id": str(telegram_user_id),
        "telegram_username": bot_user.get("telegram_username", "") if bot_user else "",
        "plan_id": plan_id,
        "plan_name": plan_name,
        "amount": amount,
        "status": "pending",
        "payment_method": "miniapp_upi",
        "screenshot_url": screenshot_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "miniapp",
        "tenant_id": DEFAULT_TENANT_ID,
    }
    
    # Run AI Verification
    ai_result = {}
    try:
        ai_result = await analyze_payment_screenshot_with_ai(image_bytes, amount, expected_upi)
        payment["ai_verification"] = ai_result
        
        if ai_result.get("auto_approve_recommended"):
            payment["status"] = "verified"
            payment["verified_by"] = "AI (GPT-5.2)"
            payment["verified_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        logger.error(f"AI verification error: {e}")
        ai_result = {"error": str(e), "ai_enabled": False}
    
    await db.payments.insert_one(payment)
    del payment["_id"]
    
    # If AI verified, activate subscription
    if payment["status"] == "verified":
        plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
        duration = plan.get("duration_days", 30) if plan else 30
        channel_id = ""
        if plan:
            channel_id = plan.get("channel_id", "") or settings.get("telegram_channel_id", "")
        
        await db.subscribers.update_one(
            {"telegram_user_id": str(telegram_user_id)},
            {"$set": {
                "telegram_user_id": str(telegram_user_id),
                "plan_id": plan_id,
                "plan_name": plan_name,
                "amount_paid": amount,
                "status": "active",
                "start_date": datetime.now(timezone.utc).isoformat(),
                "end_date": (datetime.now(timezone.utc) + timedelta(days=duration)).isoformat(),
                "payment_id": payment_id,
            }},
            upsert=True
        )
        
        # Add to channel
        bot_token = settings.get("telegram_bot_token", "")
        if channel_id and bot_token and telegram_user_id:
            try:
                await add_to_channel(telegram_user_id, channel_id, bot_token)
            except Exception as e:
                logger.error(f"Failed to add to channel: {e}")
    
    # Notify admins about new payment
    bot_token = settings.get("telegram_bot_token", "")
    admin_ids = settings.get("telegram_admin_ids", [])
    if bot_token and admin_ids:
        status_emoji = "✅" if payment["status"] == "verified" else "⏳"
        admin_msg = f"{status_emoji} <b>New Mini App Payment</b>\n\n"
        admin_msg += f"User: {payment.get('telegram_username') or telegram_user_id}\n"
        admin_msg += f"Plan: {plan_name}\n"
        admin_msg += f"Amount: ₹{amount}\n"
        admin_msg += f"Status: {payment['status'].upper()}\n"
        if ai_result.get("ai_enabled"):
            admin_msg += f"AI Confidence: {ai_result.get('confidence_score', 0)}%\n"
            admin_msg += f"AI Verdict: {'Approved' if ai_result.get('auto_approve_recommended') else 'Manual Review Needed'}"
        
        for admin_id in admin_ids:
            try:
                await send_telegram_photo(admin_id, screenshot_url, admin_msg, bot_token)
            except Exception:
                try:
                    await send_telegram_message(admin_id, admin_msg, bot_token)
                except Exception:
                    pass
    
    return {
        "success": True,
        "payment_id": payment_id,
        "status": payment["status"],
        "ai_verified": payment["status"] == "verified",
        "ai_result": {
            "enabled": ai_result.get("ai_enabled", False),
            "is_payment": ai_result.get("is_payment_screenshot", False),
            "confidence": ai_result.get("confidence_score", 0),
            "reason": ai_result.get("reason", ""),
            "auto_approved": ai_result.get("auto_approve_recommended", False),
            "extracted": ai_result.get("extracted_data", {}),
        }
    }


# ============== AI SUPPORT CHAT ==============

@router.post("/support/chat")
async def miniapp_support_chat(data: dict):
    """AI-powered support chat. Responds to user queries, escalates complex ones."""
    telegram_user_id = data.get("telegram_user_id", "")
    message = data.get("message", "").strip()
    session_id = data.get("session_id", f"support-{telegram_user_id}")

    if not message:
        return {"reply": "Please type your question.", "escalated": False}

    # Store user message
    chat_msg = {
        "id": str(uuid.uuid4()),
        "telegram_user_id": telegram_user_id,
        "session_id": session_id,
        "role": "user",
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.miniapp_support_chats.insert_one(chat_msg)

    # Fetch context: plans, user status
    plans = await db.plans.find({"is_active": True}, {"_id": 0, "name": 1, "price": 1, "duration_days": 1}).to_list(20)
    plans_info = ", ".join([f"{p['name']} (₹{p['price']}/{p['duration_days']}days)" for p in plans])

    sub = await db.subscribers.find_one(
        {"telegram_user_id": telegram_user_id, "status": "active"}, {"_id": 0}
    )
    user_status = f"Active plan: {sub['plan_name']}, expires {sub.get('end_date', 'N/A')}" if sub else "No active subscription"

    # Get recent chat history for context
    history = await db.miniapp_support_chats.find(
        {"session_id": session_id},
        {"_id": 0, "role": 1, "message": 1}
    ).sort("created_at", -1).to_list(10)
    history.reverse()
    history_text = "\n".join([f"{'User' if m['role'] == 'user' else 'AI'}: {m['message']}" for m in history[:-1]])

    # Try AI response
    ai_reply = None
    escalated = False

    if EMERGENT_LLM_KEY:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage

            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"miniapp-support-{uuid.uuid4()}",
                system_message=f"""You are a friendly support assistant for a Telegram subscription bot service.

Available Plans: {plans_info}
User Status: {user_status}

RULES:
1. Answer questions about plans, pricing, payment methods, subscription status, and how the bot works.
2. Be concise and helpful. Use simple language.
3. If the user has a complex issue you cannot resolve (account problems, refunds, technical bugs, billing disputes), respond with EXACTLY this prefix: "ESCALATE:" followed by a brief summary.
4. Payment methods: UPI screenshot (manual, takes time for admin verification) or Razorpay (instant, automated).
5. Keep responses under 150 words.
6. Be warm and use casual Hindi-English mix if the user writes in Hindi/Hinglish.

Recent conversation:
{history_text}"""
            ).with_model("openai", "gpt-5.2")

            response = await chat.send_message(UserMessage(text=message))
            ai_reply = response.strip()

            if ai_reply.startswith("ESCALATE:"):
                escalated = True
                escalation_reason = ai_reply.replace("ESCALATE:", "").strip()
                ai_reply = "I've forwarded your issue to our support team. An admin will get back to you soon! 🙏"

                # Create support ticket
                ticket = {
                    "id": str(uuid.uuid4()),
                    "telegram_user_id": telegram_user_id,
                    "subject": "Mini App Escalation",
                    "message": message,
                    "escalation_reason": escalation_reason,
                    "status": "open",
                    "source": "miniapp_ai",
                    "messages": [{
                        "id": str(uuid.uuid4()),
                        "sender": "user",
                        "message": message,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }],
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.support_tickets.insert_one(ticket)

        except Exception as e:
            logger.error(f"AI Support chat error: {e}")
            ai_reply = None

    if not ai_reply:
        ai_reply = "I'm having trouble processing your request right now. Please try again or contact the admin directly via the bot."

    # Store AI response
    ai_msg = {
        "id": str(uuid.uuid4()),
        "telegram_user_id": telegram_user_id,
        "session_id": session_id,
        "role": "assistant",
        "message": ai_reply,
        "escalated": escalated,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.miniapp_support_chats.insert_one(ai_msg)

    return {"reply": ai_reply, "escalated": escalated}


@router.get("/support/history/{telegram_user_id}")
async def miniapp_support_history(telegram_user_id: str):
    """Get support chat history"""
    chats = await db.miniapp_support_chats.find(
        {"telegram_user_id": telegram_user_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    return chats


# ============== REFERRAL SYSTEM ==============

@router.get("/referral/{telegram_user_id}")
async def miniapp_get_referral(telegram_user_id: str):
    """Get or create referral code for user"""
    referral = await db.referrals.find_one(
        {"referrer_id": telegram_user_id}, {"_id": 0}
    )

    if not referral:
        # Create new referral code
        code = f"REF{telegram_user_id[-6:].upper()}{uuid.uuid4().hex[:4].upper()}"
        referral = {
            "id": str(uuid.uuid4()),
            "referrer_id": telegram_user_id,
            "referral_code": code,
            "referred_users": [],
            "total_earnings": 0,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.referrals.insert_one(referral)
        referral.pop("_id", None)

    # Get referral settings
    settings = await db.referral_settings.find_one({"id": "referral_settings"}, {"_id": 0})
    if not settings:
        settings = {
            "referrer_reward_type": "discount",
            "referrer_reward_value": 10,
            "referee_reward_type": "discount",
            "referee_reward_value": 10
        }

    return {
        "referral_code": referral["referral_code"],
        "referred_count": len(referral.get("referred_users", [])),
        "total_earnings": referral.get("total_earnings", 0),
        "referrer_reward": f"{settings['referrer_reward_value']}% off",
        "referee_reward": f"{settings['referee_reward_value']}% off"
    }


@router.post("/referral/apply")
async def miniapp_apply_referral(data: dict):
    """Apply a referral code"""
    code = data.get("code", "").upper().strip()
    telegram_user_id = data.get("telegram_user_id", "")

    if not code or not telegram_user_id:
        return {"valid": False, "error": "Missing referral code or user ID"}

    referral = await db.referrals.find_one({"referral_code": code, "is_active": True}, {"_id": 0})
    if not referral:
        return {"valid": False, "error": "Invalid referral code"}

    if referral["referrer_id"] == telegram_user_id:
        return {"valid": False, "error": "Can't use your own referral code"}

    if telegram_user_id in referral.get("referred_users", []):
        return {"valid": False, "error": "You've already used a referral code"}

    # Add user to referred list
    await db.referrals.update_one(
        {"referral_code": code},
        {"$push": {"referred_users": telegram_user_id}}
    )

    settings = await db.referral_settings.find_one({"id": "referral_settings"}, {"_id": 0})
    referee_discount = settings.get("referee_reward_value", 10) if settings else 10

    return {
        "valid": True,
        "discount_percent": referee_discount,
        "message": f"Referral applied! You get {referee_discount}% off on your next purchase!"
    }


# ============== NOTIFICATIONS ==============

@router.get("/notifications/{telegram_user_id}")
async def miniapp_get_notifications(telegram_user_id: str):
    """Get notifications for user"""
    notifications = []

    # Check subscription expiry
    sub = await db.subscribers.find_one(
        {"telegram_user_id": telegram_user_id, "status": "active"}, {"_id": 0}
    )
    if sub:
        end_date = sub.get("end_date", "")
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                days_left = (end_dt - datetime.now(timezone.utc)).days
                if days_left <= 3:
                    notifications.append({
                        "id": "expiry_warning",
                        "type": "warning",
                        "title": "Subscription Expiring Soon!",
                        "message": f"Your {sub['plan_name']} plan expires in {days_left} day(s). Renew now!",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    })
            except Exception:
                pass

    # Check pending payments
    pending = await db.payments.find(
        {"telegram_user_id": telegram_user_id, "status": "pending"},
        {"_id": 0}
    ).to_list(5)
    for p in pending:
        notifications.append({
            "id": f"pending_{p.get('id', '')}",
            "type": "info",
            "title": "Payment Under Review",
            "message": f"Your payment of ₹{p.get('amount', 0)} for {p.get('plan_name', 'plan')} is being verified.",
            "created_at": p.get("created_at", "")
        })

    # New plans notification
    recent_plans = await db.plans.find(
        {"is_active": True},
        {"_id": 0, "name": 1, "price": 1, "created_at": 1}
    ).sort("created_at", -1).to_list(3)

    if not sub and recent_plans:
        notifications.append({
            "id": "new_plans",
            "type": "promo",
            "title": "Check Out Our Plans!",
            "message": f"Starting from just ₹{recent_plans[-1].get('price', 0)}. Subscribe now!",
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    return notifications


# ============== MENU BUTTON CONFIG ==============

@router.post("/set-menu-button")
async def set_miniapp_menu_button(data: dict):
    """Set the bot's menu button to open the Mini App"""
    import httpx

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot token not configured")

    webapp_url = data.get("url", "")
    button_text = data.get("text", "Menu")

    if not webapp_url:
        raise HTTPException(status_code=400, detail="WebApp URL required")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{bot_token}/setChatMenuButton",
            json={
                "menu_button": {
                    "type": "web_app",
                    "text": button_text,
                    "web_app": {"url": webapp_url}
                }
            }
        )
        result = resp.json()

        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("description", "Failed"))

    return {"message": "Menu button set!", "url": webapp_url, "text": button_text}


@router.get("/menu-button-status")
async def get_menu_button_status():
    """Check current menu button status"""
    import httpx

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    if not bot_token:
        return {"status": "not_configured", "reason": "Bot token not set"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{bot_token}/getChatMenuButton",
            json={}
        )
        result = resp.json()
        if result.get("ok"):
            btn = result.get("result", {})
            return {"status": "configured", "button": btn}
    return {"status": "unknown"}


# ============== ADMIN PANEL ENDPOINTS ==============

async def _verify_miniapp_admin(telegram_user_id: str):
    """Check if a telegram user is a registered admin, return admin doc or None"""
    admin = await db.telegram_admins.find_one(
        {"telegram_user_id": str(telegram_user_id), "is_active": True}, {"_id": 0}
    )
    return admin


async def _get_admin_tenant(telegram_user_id: str) -> str:
    """Get the tenant_id for an admin. Falls back to default."""
    admin = await _verify_miniapp_admin(telegram_user_id)
    if admin and admin.get("tenant_id"):
        return admin["tenant_id"]
    return DEFAULT_TENANT_ID


@router.get("/admin/check/{telegram_user_id}")
async def miniapp_admin_check(telegram_user_id: str):
    """Check if user is an admin and return their permissions"""
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        return {"is_admin": False, "permissions": [], "name": ""}
    return {
        "is_admin": True,
        "name": admin.get("name", "Admin"),
        "permissions": admin.get("permissions", []),
        "role": admin.get("role", "admin"),
    }


@router.get("/admin/stats/{telegram_user_id}")
async def miniapp_admin_stats(telegram_user_id: str):
    """Get quick dashboard stats for admin"""
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    tenant_id = admin.get("tenant_id", DEFAULT_TENANT_ID)

    def tq(q):
        return tenant_query(q, tenant_id)

    total_subs = await db.subscribers.count_documents(tq({}))
    active_subs = await db.subscribers.count_documents(tq({"status": "active"}))
    pending_payments = await db.payments.count_documents(tq({"status": "pending"}))
    
    # Calculate revenue
    pipeline = [
        {"$match": tq({"status": {"$in": ["verified", "approved"]}})},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    rev_result = await db.payments.aggregate(pipeline).to_list(1)
    total_revenue = rev_result[0]["total"] if rev_result else 0

    return {
        "total_subscribers": total_subs,
        "active_subscribers": active_subs,
        "pending_payments": pending_payments,
        "total_revenue": total_revenue,
    }


@router.get("/admin/pending-payments/{telegram_user_id}")
async def miniapp_admin_pending_payments(telegram_user_id: str):
    """Get pending payments for admin to verify"""
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")
    if "verify_payments" not in admin.get("permissions", []):
        raise HTTPException(status_code=403, detail="No payment verification permission")

    payments_list = await db.payments.find(
        tenant_query({"status": "pending"}, admin.get("tenant_id", DEFAULT_TENANT_ID)), {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return payments_list


@router.post("/admin/payment-action")
async def miniapp_admin_payment_action(data: dict):
    """Approve or reject a payment"""
    telegram_user_id = data.get("telegram_user_id", "")
    payment_id = data.get("payment_id", "")
    action = data.get("action", "")  # "approve" or "reject"

    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")
    if "verify_payments" not in admin.get("permissions", []):
        raise HTTPException(status_code=403, detail="No permission")

    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Invalid action")

    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    new_status = "verified" if action == "approve" else "rejected"
    await db.payments.update_one(
        {"id": payment_id},
        {"$set": {"status": new_status, "verified_by": admin.get("name", "Admin"), "verified_at": datetime.now(timezone.utc).isoformat()}}
    )

    # Notify user via Telegram
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    user_chat_id = payment.get("telegram_user_id", "")

    if bot_token and user_chat_id:
        if action == "approve":
            msg = f"✅ <b>Payment Approved!</b>\n\n"
            msg += f"Amount: ₹{payment.get('amount', 0)}\n"
            msg += f"Plan: {payment.get('plan_name', '')}\n\n"
            msg += f"Your subscription is now active! 🎉"
            await send_telegram_message(user_chat_id, msg, bot_token)

            # Add to channel
            plan = await db.plans.find_one({"id": payment.get("plan_id")}, {"_id": 0})
            channel_id = ""
            if plan:
                channel_id = plan.get("channel_id", "") or settings.get("telegram_channel_id", "")
            else:
                channel_id = settings.get("telegram_channel_id", "")
            if channel_id:
                await add_to_channel(user_chat_id, channel_id, bot_token)

            # Create/update subscription
            await db.subscribers.update_one(
                {"telegram_user_id": user_chat_id},
                {"$set": {
                    "telegram_user_id": user_chat_id,
                    "telegram_username": payment.get("telegram_username", ""),
                    "plan_id": payment.get("plan_id", ""),
                    "plan_name": payment.get("plan_name", ""),
                    "amount_paid": payment.get("amount", 0),
                    "status": "active",
                    "start_date": datetime.now(timezone.utc).isoformat(),
                    "end_date": (datetime.now(timezone.utc) + timedelta(days=plan.get("duration_days", 30) if plan else 30)).isoformat(),
                    "payment_id": payment_id,
                }},
                upsert=True
            )
        else:
            msg = f"❌ <b>Payment Rejected</b>\n\n"
            msg += f"Amount: ₹{payment.get('amount', 0)}\n"
            msg += f"Plan: {payment.get('plan_name', '')}\n\n"
            msg += f"Please try again or contact support."
            await send_telegram_message(user_chat_id, msg, bot_token)

    return {"success": True, "new_status": new_status}


@router.get("/admin/subscribers/{telegram_user_id}")
async def miniapp_admin_subscribers(telegram_user_id: str):
    """Get subscribers list for admin"""
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    subs = await db.subscribers.find(
        tenant_query({}, admin.get("tenant_id", DEFAULT_TENANT_ID)), {"_id": 0}
    ).sort("start_date", -1).to_list(100)
    return subs


@router.post("/admin/broadcast")
async def miniapp_admin_broadcast(data: dict, background_tasks: BackgroundTasks):
    """Send broadcast message from Mini App"""
    telegram_user_id = data.get("telegram_user_id", "")
    message = data.get("message", "").strip()

    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")
    if "broadcast" not in admin.get("permissions", []):
        raise HTTPException(status_code=403, detail="No broadcast permission")
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot token not configured")

    # Get all bot users
    tenant_id = admin.get("tenant_id", DEFAULT_TENANT_ID)
    bot_users = await db.bot_users.find(tenant_query({}, tenant_id), {"_id": 0, "telegram_user_id": 1}).to_list(10000)
    user_ids = [u["telegram_user_id"] for u in bot_users if u.get("telegram_user_id")]

    # Also get subscribers
    subs = await db.subscribers.find(tenant_query({}, tenant_id), {"_id": 0, "telegram_user_id": 1}).to_list(10000)
    sub_ids = [s["telegram_user_id"] for s in subs if s.get("telegram_user_id")]
    
    all_ids = list(set(user_ids + sub_ids))

    # Send in background
    broadcast_id = str(uuid.uuid4())
    await db.broadcasts.insert_one({
        "id": broadcast_id,
        "message": message,
        "sent_by": admin.get("name", "Admin"),
        "sent_by_id": telegram_user_id,
        "total_recipients": len(all_ids),
        "sent": 0,
        "failed": 0,
        "status": "sending",
        "tenant_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    async def _send_broadcast():
        sent = 0
        failed = 0
        for uid in all_ids:
            try:
                await send_telegram_message(uid, message, bot_token)
                sent += 1
            except Exception:
                failed += 1
        await db.broadcasts.update_one(
            {"id": broadcast_id},
            {"$set": {"sent": sent, "failed": failed, "status": "completed"}}
        )

    background_tasks.add_task(_send_broadcast)

    return {"success": True, "broadcast_id": broadcast_id, "total_recipients": len(all_ids)}


@router.get("/admin/live-sessions/{telegram_user_id}")
async def miniapp_admin_live_sessions(telegram_user_id: str):
    """Get live sessions for admin"""
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    sessions = await db.live_sessions.find(
        tenant_query({}, admin.get("tenant_id", DEFAULT_TENANT_ID)), {"_id": 0}
    ).sort("created_at", -1).to_list(20)
    return sessions


@router.post("/admin/live-session")
async def miniapp_admin_create_live(data: dict):
    """Create a live session from Mini App"""
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    session_id = str(uuid.uuid4())
    session = {
        "id": session_id,
        "title": data.get("title", "Live Session"),
        "description": data.get("description", ""),
        "scheduled_date": data.get("scheduled_date", ""),
        "scheduled_time": data.get("scheduled_time", ""),
        "price": data.get("price", 0),
        "max_viewers": data.get("max_viewers", 100),
        "stream_link": data.get("stream_link", ""),
        "superchat_enabled": data.get("superchat_enabled", False),
        "superchat_min_amount": data.get("superchat_min_amount", 50),
        "status": "scheduled",
        "tickets_sold": 0,
        "started_at": "",
        "created_by": admin.get("name", "Admin"),
        "tenant_id": admin.get("tenant_id", DEFAULT_TENANT_ID),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.live_sessions.insert_one(session)
    del session["_id"]
    return session


@router.post("/admin/announce-live/{session_id}")
async def miniapp_admin_announce_live(session_id: str, data: dict):
    """Announce a live session to all users"""
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    # Build announcement message
    msg = f"🔴 <b>LIVE SESSION ANNOUNCED!</b>\n\n"
    msg += f"📺 <b>{session.get('title', 'Live')}</b>\n"
    if session.get("description"):
        msg += f"{session['description']}\n\n"
    msg += f"📅 Date: {session.get('scheduled_date', 'TBA')}\n"
    msg += f"⏰ Time: {session.get('scheduled_time', 'TBA')}\n"
    if session.get("price", 0) > 0:
        msg += f"💰 Price: ₹{session['price']}\n"
    else:
        msg += f"💰 Price: FREE\n"
    msg += f"\n🔗 Don't miss it!"

    # Get all users
    admin_tenant = admin.get("tenant_id", DEFAULT_TENANT_ID)
    bot_users = await db.bot_users.find(tenant_query({}, admin_tenant), {"_id": 0, "telegram_user_id": 1}).to_list(10000)
    sent = 0
    for u in bot_users:
        uid = u.get("telegram_user_id")
        if uid:
            try:
                await send_telegram_message(uid, msg, bot_token)
                sent += 1
            except Exception:
                pass

    await db.live_sessions.update_one({"id": session_id}, {"$set": {"status": "announced"}})
    return {"success": True, "sent_to": sent}


# ============== PAID POSTS ADMIN ==============

@router.get("/admin/paid-posts/{telegram_user_id}")
async def miniapp_admin_paid_posts(telegram_user_id: str):
    """Get paid posts for admin"""
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    posts = await db.paid_posts.find(
        tenant_query({}, admin.get("tenant_id", DEFAULT_TENANT_ID)), {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return posts


@router.post("/admin/paid-post")
async def miniapp_admin_create_paid_post(data: dict):
    """Create a paid post from Mini App (JSON without file)"""
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    post_id = str(uuid.uuid4())
    post = {
        "id": post_id,
        "channel_id": data.get("channel_id", ""),
        "caption": data.get("caption", ""),
        "price": data.get("price", 0),
        "blur_level": data.get("blur_level", 10),
        "content_type": data.get("content_type", "text"),
        "original_file_id": data.get("original_file_id", ""),
        "media_url": data.get("media_url", ""),
        "original_message_id": data.get("original_message_id", 0),
        "blurred_message_id": data.get("blurred_message_id", 0),
        "is_active": True,
        "unlock_count": 0,
        "created_by": admin.get("name", "Admin"),
        "tenant_id": admin.get("tenant_id", DEFAULT_TENANT_ID),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.paid_posts.insert_one(post)
    del post["_id"]
    return post


@router.post("/admin/paid-post-with-media")
async def miniapp_admin_create_paid_post_with_media(
    file: UploadFile = File(...),
    telegram_user_id: str = Form(""),
    caption: str = Form(""),
    price: int = Form(0),
    blur_level: int = Form(10),
    channel_id: str = Form(""),
    content_type: str = Form("photo"),
):
    """Create a paid post with an uploaded image or video"""
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    # Read file
    file_bytes = await file.read()
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    # Save file
    uploads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(uploads_path, exist_ok=True)
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"post_{uuid.uuid4().hex[:10]}.{ext}"
    filepath = os.path.join(uploads_path, filename)
    with open(filepath, "wb") as f:
        f.write(file_bytes)

    media_url = f"/api/uploads/{filename}"

    # Detect content type
    if content_type == "auto":
        if ext.lower() in ("mp4", "mov", "avi", "mkv", "webm"):
            content_type = "video"
        elif ext.lower() in ("jpg", "jpeg", "png", "gif", "webp"):
            content_type = "photo"
        else:
            content_type = "document"

    post_id = str(uuid.uuid4())
    post = {
        "id": post_id,
        "channel_id": channel_id,
        "caption": caption,
        "price": price,
        "blur_level": blur_level,
        "content_type": content_type,
        "original_file_id": "",
        "media_url": media_url,
        "media_filename": filename,
        "original_message_id": 0,
        "blurred_message_id": 0,
        "is_active": True,
        "unlock_count": 0,
        "created_by": admin.get("name", "Admin"),
        "tenant_id": admin.get("tenant_id", DEFAULT_TENANT_ID),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.paid_posts.insert_one(post)
    del post["_id"]
    return post


@router.post("/admin/paid-post/{post_id}/toggle")
async def miniapp_toggle_paid_post(post_id: str, data: dict):
    """Toggle paid post active/inactive"""
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    post = await db.paid_posts.find_one({"id": post_id}, {"_id": 0})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    new_status = not post.get("is_active", True)
    await db.paid_posts.update_one({"id": post_id}, {"$set": {"is_active": new_status}})
    return {"success": True, "is_active": new_status}


@router.post("/admin/paid-post/{post_id}/blur")
async def miniapp_update_blur(post_id: str, data: dict):
    """Update blur level for a paid post"""
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    blur_level = data.get("blur_level", 10)
    if blur_level < 0:
        blur_level = 0
    if blur_level > 50:
        blur_level = 50

    await db.paid_posts.update_one({"id": post_id}, {"$set": {"blur_level": blur_level}})
    return {"success": True, "blur_level": blur_level}



@router.post("/admin/paid-post/{post_id}/broadcast")
async def miniapp_broadcast_paid_post(post_id: str, data: dict, background_tasks: BackgroundTasks):
    """Broadcast a paid post to all users from Mini App"""
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    post = await db.paid_posts.find_one({"id": post_id, "is_active": True}, {"_id": 0})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found or inactive")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    admin_tenant = admin.get("tenant_id", DEFAULT_TENANT_ID)
    bot_users = await db.bot_users.find(tenant_query({}, admin_tenant), {"_id": 0, "telegram_user_id": 1}).to_list(10000)
    user_ids = [u["telegram_user_id"] for u in bot_users if u.get("telegram_user_id")]

    price = post.get("price", 0)
    caption = post.get("caption", "")
    msg = f"{'🔒' if price > 0 else '📢'} <b>{'Paid Content' if price > 0 else 'Free Post'}</b>\n\n"
    msg += f"{caption}\n\n"
    if price > 0:
        msg += f"💰 Unlock for ₹{price}"

    sent = 0
    for uid in user_ids:
        try:
            await send_telegram_message(uid, msg, bot_token)
            sent += 1
        except Exception:
            pass

    return {"success": True, "sent_to": sent}


@router.post("/admin/live-session/{session_id}/go-live")
async def miniapp_go_live(session_id: str, data: dict):
    """Mark a live session as live and notify users"""
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.live_sessions.update_one({"id": session_id}, {"$set": {"status": "live", "started_at": datetime.now(timezone.utc).isoformat()}})

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    admin_tenant = admin.get("tenant_id", DEFAULT_TENANT_ID)
    bot_users = await db.bot_users.find(tenant_query({}, admin_tenant), {"_id": 0, "telegram_user_id": 1}).to_list(10000)

    msg = f"🔴 <b>LIVE NOW!</b>\n\n"
    msg += f"📺 {session.get('title', 'Live Session')}\n"
    if session.get("stream_link"):
        msg += f"🔗 {session['stream_link']}\n"
    msg += f"\nJoin now!"

    sent = 0
    for u in bot_users:
        uid = u.get("telegram_user_id")
        if uid:
            try:
                await send_telegram_message(uid, msg, bot_token)
                sent += 1
            except Exception:
                pass

    return {"success": True, "status": "live", "notified": sent}


@router.delete("/admin/live-session/{session_id}")
async def miniapp_delete_live(session_id: str, data: dict):
    """Delete a live session"""
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    result = await db.live_sessions.delete_one({"id": session_id})
    return {"success": result.deleted_count > 0}


@router.post("/admin/live-session/{session_id}/end")
async def miniapp_end_live(session_id: str, data: dict):
    """End a live session"""
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    result = await db.live_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "ended", "ended_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"success": result.modified_count > 0, "status": "ended"}



# ============== TENANT MANAGEMENT ==============

@router.get("/admin/tenant/{telegram_user_id}")
async def miniapp_get_tenant(telegram_user_id: str):
    """Get current tenant info for an admin"""
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")
    
    tenant_id = admin.get("tenant_id", DEFAULT_TENANT_ID)
    tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not tenant:
        tenant = {"tenant_id": tenant_id, "name": "Default Creator", "status": "active"}
    return tenant


@router.post("/admin/tenant/create")
async def miniapp_create_tenant(data: dict):
    """Register a new tenant (creator). Called when a new creator onboards."""
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    tenant_name = data.get("name", "").strip()
    if not tenant_name:
        raise HTTPException(status_code=400, detail="Tenant name required")

    tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"
    tenant = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "name": tenant_name,
        "owner_telegram_id": telegram_user_id,
        "bot_token": data.get("bot_token", ""),
        "upi_id": data.get("upi_id", ""),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.tenants.insert_one(tenant)

    # Update the admin's tenant_id
    await db.telegram_admins.update_one(
        {"telegram_user_id": str(telegram_user_id)},
        {"$set": {"tenant_id": tenant_id}}
    )

    tenant.pop("_id", None)
    return {"success": True, "tenant": tenant}




# ============== LIVE TICKET PURCHASE WITH AI VERIFY ==============

@router.post("/live-ticket/upload-screenshot")
async def miniapp_live_ticket_upload_screenshot(
    file: UploadFile = File(...),
    telegram_user_id: str = Form(""),
    session_id: str = Form(""),
):
    """Upload payment screenshot for live ticket purchase, AI auto-verify."""
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Live session not found")

    # Read image bytes
    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    # Save screenshot locally
    uploads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(uploads_path, exist_ok=True)
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"live_ss_{uuid.uuid4().hex[:10]}.{ext}"
    filepath = os.path.join(uploads_path, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    screenshot_url = f"/api/uploads/{filename}"

    # Get settings for AI verification
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    expected_upi = settings.get("payment_upi_id") or settings.get("upi_id", "")
    ticket_price = session.get("price", 0)

    # Create live ticket record
    ticket_id = str(uuid.uuid4())
    ticket = {
        "id": ticket_id,
        "session_id": session_id,
        "telegram_user_id": str(telegram_user_id),
        "amount": ticket_price,
        "screenshot_url": screenshot_url,
        "status": "pending",
        "payment_method": "miniapp_upi",
        "tenant_id": session.get("tenant_id", DEFAULT_TENANT_ID),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Run AI Verification (same as plan screenshot verification)
    ai_result = {}
    try:
        ai_result = await analyze_payment_screenshot_with_ai(image_bytes, ticket_price, expected_upi)
        ticket["ai_verification"] = ai_result

        if ai_result.get("auto_approve_recommended"):
            ticket["status"] = "approved"
            ticket["verified_by"] = "AI (GPT-5.2)"
            ticket["verified_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        logger.error(f"AI verification error for live ticket: {e}")
        ai_result = {"error": str(e), "ai_enabled": False}

    await db.live_tickets.insert_one(ticket)
    del ticket["_id"]

    # If AI approved, increment tickets_sold
    if ticket["status"] == "approved":
        await db.live_sessions.update_one(
            {"id": session_id},
            {"$inc": {"tickets_sold": 1}}
        )

        # Send stream link if live
        if session.get("stream_link") and session.get("status") == "live":
            bot_token = settings.get("telegram_bot_token", "")
            if bot_token and telegram_user_id:
                msg = "✅ <b>Ticket Approved!</b>\n\n"
                msg += f"📺 Session: <b>{session.get('title', '')}</b>\n"
                msg += f"🔗 Stream: {session['stream_link']}\n\n"
                msg += "Enjoy the stream!"
                try:
                    await send_telegram_message(telegram_user_id, msg, bot_token)
                except Exception:
                    pass

    # Notify admins about new ticket
    bot_token = settings.get("telegram_bot_token", "")
    admin_ids = settings.get("telegram_admin_ids", [])
    if bot_token and admin_ids:
        status_emoji = "✅" if ticket["status"] == "approved" else "⏳"
        admin_msg = f"{status_emoji} <b>New Live Ticket Purchase</b>\n\n"
        admin_msg += f"Session: {session.get('title', '')}\n"
        admin_msg += f"User: {telegram_user_id}\n"
        admin_msg += f"Amount: ₹{ticket_price}\n"
        admin_msg += f"Status: {ticket['status'].upper()}\n"
        if ai_result.get("ai_enabled"):
            admin_msg += f"AI Confidence: {ai_result.get('confidence_score', 0)}%"

        for admin_id in admin_ids:
            try:
                await send_telegram_message(admin_id, admin_msg, bot_token)
            except Exception:
                pass

    return {
        "success": True,
        "ticket_id": ticket_id,
        "status": ticket["status"],
        "ai_verified": ticket["status"] == "approved",
        "ai_result": {
            "enabled": ai_result.get("ai_enabled", False),
            "is_payment": ai_result.get("is_payment_screenshot", False),
            "confidence": ai_result.get("confidence_score", 0),
            "reason": ai_result.get("reason", ""),
            "auto_approved": ai_result.get("auto_approve_recommended", False),
        }
    }


@router.get("/live-sessions/public")
async def miniapp_get_live_sessions_public():
    """Get active/scheduled live sessions for regular users (public, no auth)"""
    sessions = await db.live_sessions.find(
        {"status": {"$in": ["scheduled", "announced", "live"]}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(20)
    return sessions


@router.get("/live-ticket/status/{telegram_user_id}/{session_id}")
async def miniapp_live_ticket_status(telegram_user_id: str, session_id: str):
    """Check if user already has a ticket for a live session"""
    ticket = await db.live_tickets.find_one(
        {"telegram_user_id": str(telegram_user_id), "session_id": session_id,
         "status": {"$in": ["approved", "pending"]}},
        {"_id": 0}
    )
    if ticket:
        return {"has_ticket": True, "status": ticket["status"], "ticket_id": ticket["id"]}
    return {"has_ticket": False}
