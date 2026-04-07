"""Mini App User endpoints - Plans, Payments, Support AI, Referral, Notifications, Live Tickets"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form, Header
from database import db
from services.telegram import get_bot_settings, send_telegram_message, send_telegram_photo, add_to_channel
from services.payment import analyze_payment_screenshot_with_ai
from services.telegram_verify import validate_telegram_init_data
from services.tenant import DEFAULT_TENANT_ID
from config import logger, RAZORPAY_KEY_ID, razorpay_client, EMERGENT_LLM_KEY
from datetime import datetime, timezone, timedelta
import uuid
import os
import qrcode
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
            logger.warning("Invalid Telegram initData received")
    return tg_id


# ============== TENANT RESOLUTION ==============

@router.get("/resolve-tenant/{telegram_user_id}")
async def miniapp_resolve_tenant(telegram_user_id: str):
    """Resolve which tenant this user belongs to, based on bot_users collection and settings."""
    bot_user = await db.bot_users.find_one(
        {"telegram_user_id": str(telegram_user_id)}, {"_id": 0, "tenant_id": 1}
    )
    user_tenant = bot_user.get("tenant_id", "") if bot_user else ""
    if user_tenant and user_tenant != DEFAULT_TENANT_ID:
        return {"tenant_id": user_tenant}
    # Fallback to default settings tenant
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0, "tenant_id": 1})
    return {"tenant_id": (settings.get("tenant_id") if settings else None) or DEFAULT_TENANT_ID}


@router.post("/resolve-tenant-by-init")
async def miniapp_resolve_tenant_by_init(data: dict):
    """Resolve tenant by validating initData against all tenant bot tokens.
    This is the most reliable method for multi-bot multi-tenant setups."""
    init_data = data.get("init_data", "")
    telegram_user_id = data.get("telegram_user_id", "")

    if init_data:
        # Collect all unique bot tokens from settings
        all_settings = await db.settings.find(
            {"telegram_bot_token": {"$exists": True, "$ne": ""}},
            {"_id": 0, "id": 1, "telegram_bot_token": 1, "tenant_id": 1}
        ).to_list(100)

        for s in all_settings:
            bot_token = s.get("telegram_bot_token", "")
            if not bot_token:
                continue
            user = validate_telegram_init_data(init_data, bot_token)
            if user:
                # This bot token validated the initData — this is the correct tenant
                tid = s.get("tenant_id", "")
                # For "bot_settings" (no tenant_id), resolve from the settings id pattern
                if not tid or tid == DEFAULT_TENANT_ID:
                    sid = s.get("id", "")
                    if sid.startswith("bot_settings_"):
                        tid = sid.replace("bot_settings_", "")
                return {"tenant_id": tid or DEFAULT_TENANT_ID, "verified": True}

    # Fallback: use bot_users lookup
    if telegram_user_id:
        bot_user = await db.bot_users.find_one(
            {"telegram_user_id": str(telegram_user_id)}, {"_id": 0, "tenant_id": 1}
        )
        user_tenant = bot_user.get("tenant_id", "") if bot_user else ""
        if user_tenant and user_tenant != DEFAULT_TENANT_ID:
            return {"tenant_id": user_tenant, "verified": False}

    # Fallback: use settings tenant_id (resolves for single-bot setups)
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0, "tenant_id": 1})
    settings_tenant = (settings.get("tenant_id") if settings else None) or ""
    if settings_tenant and settings_tenant != DEFAULT_TENANT_ID:
        return {"tenant_id": settings_tenant, "verified": False}

    return {"tenant_id": DEFAULT_TENANT_ID, "verified": False}


# ============== PHONE LOGIN ==============

@router.post("/phone-login")
async def miniapp_phone_login(data: dict):
    phone = data.get("phone", "").strip()
    telegram_user_id = data.get("telegram_user_id", "")
    telegram_username = data.get("telegram_username", "")

    if not phone or len(phone) < 10:
        return {"success": False, "error": "Enter a valid phone number"}

    existing = await db.miniapp_users.find_one({"telegram_user_id": telegram_user_id}, {"_id": 0})
    if existing:
        return {"success": True, "discount": 20, "already_registered": True, "message": "Welcome back! Your 20% discount is active."}

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
    return {"success": True, "discount": 20, "already_registered": False, "message": "You've unlocked 20% OFF on all plans!"}


@router.get("/user-discount/{telegram_user_id}")
async def miniapp_get_user_discount(telegram_user_id: str):
    user = await db.miniapp_users.find_one({"telegram_user_id": telegram_user_id}, {"_id": 0})
    if user:
        return {"has_discount": True, "discount_percent": 20, "phone": user.get("phone", "")}
    return {"has_discount": False, "discount_percent": 0}


# ============== UPI DETAILS ==============

def _generate_upi_qr(upi_id: str, upi_name: str = "") -> str:
    from PIL import Image, ImageDraw, ImageFont
    upi_url = f"upi://pay?pa={upi_id}&pn={upi_name}&cu=INR"
    qr = qrcode.QRCode(version=4, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=12, border=3)
    qr.add_data(upi_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="white", back_color="#1a1a2e").convert("RGB")
    qr_w, qr_h = qr_img.size
    padding, text_height = 40, 50
    canvas = Image.new("RGB", (qr_w + padding * 2, qr_h + padding * 2 + text_height), color="#1a1a2e")
    canvas.paste(qr_img, ((canvas.width - qr_w) // 2, padding))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), upi_id, font=font)
    draw.text(((canvas.width - (bbox[2] - bbox[0])) // 2, padding + qr_h + 15), upi_id, fill="white", font=font)
    # Always use /app/backend/uploads/ regardless of where this file lives
    uploads_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
    os.makedirs(uploads_path, exist_ok=True)
    filename = f"qr_styled_{upi_id.replace('@','_')}.png"
    filepath = os.path.join(uploads_path, filename)
    canvas.save(filepath, "PNG")
    return f"/api/uploads/{filename}"


def _is_valid_qr_file(qr_url: str) -> bool:
    if not qr_url or qr_url.startswith("http"):
        return bool(qr_url and qr_url.startswith("http"))
    filename = qr_url.split("/")[-1]
    uploads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    filepath = os.path.join(uploads_path, filename)
    if not os.path.exists(filepath):
        return False
    try:
        img = Image.open(filepath)
        pixels = img.load()
        colors = set()
        step = max(1, img.width // 20)
        for x in range(0, img.width, step):
            for y in range(0, img.height, step):
                colors.add(pixels[x, y])
                if len(colors) > 20:
                    return False
        return True
    except Exception:
        return False


@router.get("/upi-details")
async def miniapp_get_upi_details(tenant_id: str = DEFAULT_TENANT_ID):
    # Try tenant-specific settings first
    settings_id = f"bot_settings_{tenant_id}" if tenant_id and tenant_id != DEFAULT_TENANT_ID else "bot_settings"
    settings = await db.settings.find_one({"id": settings_id}, {"_id": 0})
    if not settings:
        # Only fallback to default for the default tenant
        if tenant_id == DEFAULT_TENANT_ID:
            settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
        else:
            settings = {}
    upi_id = settings.get("payment_upi_id") or settings.get("upi_id", "")
    upi_name = settings.get("upi_name", "")
    qr_url = settings.get("qr_code_url", "")

    if upi_id and not _is_valid_qr_file(qr_url):
        qr_url = _generate_upi_qr(upi_id, upi_name)
        await db.settings.update_one({"id": "bot_settings"}, {"$set": {"qr_code_url": qr_url}}, upsert=True)
        logger.info(f"Auto-generated QR code for UPI: {upi_id} -> {qr_url}")

    return {
        "upi_id": upi_id,
        "qr_code_url": qr_url,
        "payment_message": settings.get("payment_instructions") or settings.get("payment_message", "Send payment screenshot to the bot after paying via UPI.")
    }


# ============== PLANS ==============

@router.get("/plans")
async def miniapp_get_plans(tenant_id: str = DEFAULT_TENANT_ID):
    """Get active plans for a specific tenant only."""
    plans = await db.plans.find({"is_active": True, "tenant_id": tenant_id}, {"_id": 0}).sort("price", 1).to_list(50)
    return plans


# ============== SUBSCRIPTION STATUS ==============

@router.get("/status/{telegram_user_id}")
async def miniapp_get_status(telegram_user_id: str, tenant_id: str = DEFAULT_TENANT_ID):
    sub = await db.subscribers.find_one({"telegram_user_id": telegram_user_id, "status": "active", "tenant_id": tenant_id}, {"_id": 0})
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
            "is_active": True, "plan_id": sub.get("plan_id", ""), "plan_name": sub.get("plan_name", "N/A"),
            "start_date": sub.get("start_date"), "end_date": sub.get("end_date"),
            "days_remaining": days_remaining, "total_days": total_days,
        }
    return {"is_active": False}


# ============== COUPON VALIDATION ==============

@router.post("/apply-coupon")
async def miniapp_apply_coupon(data: dict):
    code = data.get("code", "").upper().strip()
    plan_id = data.get("plan_id")
    amount = float(data.get("amount", 0))
    tenant_id = data.get("tenant_id", DEFAULT_TENANT_ID)

    if not code:
        return {"valid": False, "error": "Enter a coupon code"}

    coupon = await db.coupons.find_one({"code": code, "is_active": True, "tenant_id": tenant_id}, {"_id": 0})
    if not coupon:
        return {"valid": False, "error": "Invalid coupon code"}

    if coupon.get("valid_until"):
        expiry = datetime.fromisoformat(coupon["valid_until"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expiry:
            return {"valid": False, "error": "Coupon expired"}

    if coupon.get("max_uses", 0) > 0 and coupon.get("used_count", 0) >= coupon["max_uses"]:
        return {"valid": False, "error": "Coupon usage limit reached"}

    if amount < coupon.get("min_purchase", 0):
        return {"valid": False, "error": f"Minimum purchase Rs.{coupon['min_purchase']} required"}

    if coupon.get("applicable_plans") and plan_id not in coupon["applicable_plans"]:
        return {"valid": False, "error": "Coupon not valid for this plan"}

    if coupon["discount_type"] == "percentage":
        discount = (amount * coupon["discount_value"]) / 100
    else:
        discount = coupon["discount_value"]

    final_amount = max(0, round(amount - discount))
    return {"valid": True, "discount": round(discount), "final_amount": final_amount, "coupon_code": coupon["code"], "discount_type": coupon["discount_type"], "discount_value": coupon["discount_value"]}


# ============== RAZORPAY PAYMENT ==============

@router.post("/create-order")
async def miniapp_create_razorpay_order(data: dict):
    if not razorpay_client:
        raise HTTPException(status_code=400, detail="Razorpay not configured")

    plan_id = data.get("plan_id")
    telegram_user_id = data.get("telegram_user_id", "")
    telegram_username = data.get("telegram_username", "")
    coupon_code = data.get("coupon_code")
    amount = float(data.get("amount", 0))
    tenant_id = data.get("tenant_id", DEFAULT_TENANT_ID)

    plan = await db.plans.find_one({"id": plan_id, "tenant_id": tenant_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    final_amount = amount if amount > 0 else plan["price"]

    if coupon_code:
        coupon = await db.coupons.find_one({"code": coupon_code.upper().strip(), "is_active": True, "tenant_id": tenant_id}, {"_id": 0})
        if coupon:
            if coupon["discount_type"] == "percentage":
                discount = (plan["price"] * coupon["discount_value"]) / 100
            else:
                discount = coupon["discount_value"]
            final_amount = max(1, round(plan["price"] - discount))

    order_data = {"amount": int(final_amount * 100), "currency": "INR", "receipt": f"miniapp_{uuid.uuid4().hex[:20]}", "payment_capture": 1}

    try:
        razor_order = razorpay_client.order.create(order_data)
    except Exception as e:
        logger.error(f"Razorpay order creation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create payment order")

    tenant_id = data.get("tenant_id", DEFAULT_TENANT_ID)
    order_doc = {
        "id": str(uuid.uuid4()), "razorpay_order_id": razor_order["id"], "plan_id": plan_id, "plan_name": plan["name"],
        "amount": final_amount, "original_amount": plan["price"], "coupon_code": coupon_code,
        "telegram_user_id": telegram_user_id, "telegram_username": telegram_username,
        "status": "created", "source": "miniapp", "tenant_id": tenant_id, "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.bot_orders.insert_one(order_doc)
    return {"order_id": razor_order["id"], "amount": final_amount, "key_id": RAZORPAY_KEY_ID, "plan_name": plan["name"], "currency": "INR"}


@router.post("/verify-payment")
async def miniapp_verify_payment(data: dict, background_tasks: BackgroundTasks):
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

    order = await db.bot_orders.find_one({"razorpay_order_id": data['razorpay_order_id']}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    await db.bot_orders.update_one({"razorpay_order_id": data['razorpay_order_id']}, {"$set": {"status": "paid", "razorpay_payment_id": data['razorpay_payment_id']}})

    plan = await db.plans.find_one({"id": order["plan_id"]}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    telegram_user_id = data.get("telegram_user_id") or order.get("telegram_user_id")
    telegram_username = order.get("telegram_username", "")

    if order.get("coupon_code"):
        await db.coupons.update_one({"code": order["coupon_code"].upper()}, {"$inc": {"used_count": 1}})

    payment_obj = {
        "id": str(uuid.uuid4()), "subscriber_id": None, "telegram_user_id": telegram_user_id,
        "telegram_username": telegram_username, "amount": order["amount"], "plan_id": order["plan_id"],
        "plan_name": plan["name"], "payment_method": "razorpay", "razorpay_order_id": data['razorpay_order_id'],
        "razorpay_payment_id": data['razorpay_payment_id'], "coupon_code": order.get("coupon_code"),
        "status": "verified", "source": "miniapp", "tenant_id": order.get("tenant_id", DEFAULT_TENANT_ID),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payments.insert_one(payment_obj)

    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    grace_days = settings.get("grace_period_days", 2)
    bot_token = settings.get("telegram_bot_token", "")

    end_date = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])
    grace_end = end_date + timedelta(days=grace_days)

    subscriber_obj = {
        "id": str(uuid.uuid4()), "telegram_user_id": telegram_user_id, "telegram_username": telegram_username,
        "plan_id": plan["id"], "plan_name": plan["name"], "payment_method": "razorpay", "payment_id": payment_obj["id"],
        "status": "active", "start_date": datetime.now(timezone.utc).isoformat(), "end_date": end_date.isoformat(),
        "grace_end_date": grace_end.isoformat(), "reminder_sent": False,
        "tenant_id": order.get("tenant_id", DEFAULT_TENANT_ID), "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.subscribers.insert_one(subscriber_obj)

    plan_channel = plan.get("channel_id", "")
    if plan_channel and bot_token:
        background_tasks.add_task(add_to_channel, telegram_user_id, plan_channel, plan["name"])

    if bot_token and telegram_user_id:
        success_msg = "<b>Payment Successful!</b>\n\n"
        success_msg += f"Plan: <b>{plan['name']}</b>\n"
        success_msg += f"Amount: <b>Rs.{order['amount']}</b>\n"
        success_msg += f"Valid till: <b>{end_date.strftime('%d %b %Y')}</b>\n\n"
        success_msg += "Your subscription is now active!"
        background_tasks.add_task(send_telegram_message, telegram_user_id, success_msg)

    return {"success": True, "plan_name": plan["name"], "end_date": end_date.isoformat(), "amount": order["amount"]}


# ============== PAYMENT HISTORY ==============

@router.get("/payments/{telegram_user_id}")
async def miniapp_payment_history(telegram_user_id: str, tenant_id: str = DEFAULT_TENANT_ID):
    payments = await db.payments.find({"telegram_user_id": telegram_user_id, "tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return payments


@router.post("/upload-screenshot")
async def miniapp_upload_screenshot(
    file: UploadFile = File(...),
    telegram_user_id: str = Form(""),
    plan_id: str = Form(""),
    plan_name: str = Form(""),
    amount: float = Form(0),
    tenant_id: str = Form(""),
):
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    uploads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(uploads_path, exist_ok=True)
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"ss_{uuid.uuid4().hex[:10]}.{ext}"
    with open(os.path.join(uploads_path, filename), "wb") as f:
        f.write(image_bytes)

    screenshot_url = f"/api/uploads/{filename}"

    # Resolve correct tenant_id: explicit param > plan's tenant > bot_user's tenant > default
    resolved_tenant = tenant_id.strip() if tenant_id else ""
    plan = None
    if plan_id:
        plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
        if not resolved_tenant and plan:
            resolved_tenant = plan.get("tenant_id", "")
    if not resolved_tenant:
        bot_user = await db.bot_users.find_one({"telegram_user_id": str(telegram_user_id)}, {"_id": 0})
        resolved_tenant = (bot_user.get("tenant_id", "") if bot_user else "") or DEFAULT_TENANT_ID
    else:
        bot_user = await db.bot_users.find_one({"telegram_user_id": str(telegram_user_id)}, {"_id": 0})

    # Get tenant-specific settings for UPI
    settings_id = f"bot_settings_{resolved_tenant}" if resolved_tenant and resolved_tenant != DEFAULT_TENANT_ID else "bot_settings"
    settings = await db.settings.find_one({"id": settings_id}, {"_id": 0})
    if not settings:
        settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    expected_upi = settings.get("payment_upi_id") or settings.get("upi_id", "")

    payment_id = str(uuid.uuid4())

    payment = {
        "id": payment_id, "telegram_user_id": str(telegram_user_id),
        "telegram_username": (bot_user.get("telegram_username", "") or bot_user.get("username", "")) if bot_user else "",
        "plan_id": plan_id, "plan_name": plan_name or (plan.get("name", "") if plan else ""),
        "amount": amount,
        "status": "pending", "payment_method": "miniapp_upi", "screenshot_url": screenshot_url,
        "created_at": datetime.now(timezone.utc).isoformat(), "source": "miniapp",
        "tenant_id": resolved_tenant,
    }

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

    if payment["status"] == "verified":
        if not plan and plan_id:
            plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
        duration = plan.get("duration_days", 30) if plan else 30
        channel_id = ""
        if plan:
            channel_id = plan.get("channel_id", "") or settings.get("telegram_channel_id", "")

        await db.subscribers.update_one(
            {"telegram_user_id": str(telegram_user_id), "tenant_id": resolved_tenant},
            {"$set": {
                "telegram_user_id": str(telegram_user_id), "plan_id": plan_id, "plan_name": plan_name,
                "amount_paid": amount, "status": "active",
                "start_date": datetime.now(timezone.utc).isoformat(),
                "end_date": (datetime.now(timezone.utc) + timedelta(days=duration)).isoformat(),
                "payment_id": payment_id, "tenant_id": resolved_tenant,
            }},
            upsert=True
        )

        bot_token = settings.get("telegram_bot_token", "")
        if channel_id and bot_token and telegram_user_id:
            try:
                await add_to_channel(telegram_user_id, channel_id, bot_token)
            except Exception as e:
                logger.error(f"Failed to add to channel: {e}")

    bot_token = settings.get("telegram_bot_token", "")
    admin_ids = settings.get("telegram_admin_ids", [])
    if bot_token and admin_ids:
        status_emoji = "V" if payment["status"] == "verified" else "P"
        admin_msg = f"{status_emoji} <b>New Mini App Payment</b>\n\n"
        admin_msg += f"User: {payment.get('telegram_username') or telegram_user_id}\n"
        admin_msg += f"Plan: {plan_name}\nAmount: Rs.{amount}\nStatus: {payment['status'].upper()}\n"
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
        "success": True, "payment_id": payment_id, "status": payment["status"],
        "ai_verified": payment["status"] == "verified",
        "ai_result": {
            "enabled": ai_result.get("ai_enabled", False), "is_payment": ai_result.get("is_payment_screenshot", False),
            "confidence": ai_result.get("confidence_score", 0), "reason": ai_result.get("reason", ""),
            "auto_approved": ai_result.get("auto_approve_recommended", False), "extracted": ai_result.get("extracted_data", {}),
        }
    }


# ============== AI SUPPORT CHAT ==============

@router.post("/support/chat")
async def miniapp_support_chat(data: dict):
    telegram_user_id = data.get("telegram_user_id", "")
    message = data.get("message", "").strip()
    session_id = data.get("session_id", f"support-{telegram_user_id}")

    if not message:
        return {"reply": "Please type your question.", "escalated": False}

    chat_msg = {
        "id": str(uuid.uuid4()), "telegram_user_id": telegram_user_id, "session_id": session_id,
        "role": "user", "message": message, "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.miniapp_support_chats.insert_one(chat_msg)

    plans = await db.plans.find({"is_active": True}, {"_id": 0, "name": 1, "price": 1, "duration_days": 1}).to_list(20)
    plans_info = ", ".join([f"{p['name']} (Rs.{p['price']}/{p['duration_days']}days)" for p in plans])

    sub = await db.subscribers.find_one({"telegram_user_id": telegram_user_id, "status": "active"}, {"_id": 0})
    user_status = f"Active plan: {sub['plan_name']}, expires {sub.get('end_date', 'N/A')}" if sub else "No active subscription"

    history = await db.miniapp_support_chats.find({"session_id": session_id}, {"_id": 0, "role": 1, "message": 1}).sort("created_at", -1).to_list(10)
    history.reverse()
    history_text = "\n".join([f"{'User' if m['role'] == 'user' else 'AI'}: {m['message']}" for m in history[:-1]])

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
                ai_reply = "I've forwarded your issue to our support team. An admin will get back to you soon!"

                ticket = {
                    "id": str(uuid.uuid4()), "telegram_user_id": telegram_user_id,
                    "subject": "Mini App Escalation", "message": message,
                    "escalation_reason": escalation_reason, "status": "open", "source": "miniapp_ai",
                    "messages": [{"id": str(uuid.uuid4()), "sender": "user", "message": message, "created_at": datetime.now(timezone.utc).isoformat()}],
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.support_tickets.insert_one(ticket)

        except Exception as e:
            logger.error(f"AI Support chat error: {e}")
            ai_reply = None

    if not ai_reply:
        ai_reply = "I'm having trouble processing your request right now. Please try again or contact the admin directly via the bot."

    ai_msg = {
        "id": str(uuid.uuid4()), "telegram_user_id": telegram_user_id, "session_id": session_id,
        "role": "assistant", "message": ai_reply, "escalated": escalated, "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.miniapp_support_chats.insert_one(ai_msg)
    return {"reply": ai_reply, "escalated": escalated}


@router.get("/support/history/{telegram_user_id}")
async def miniapp_support_history(telegram_user_id: str):
    chats = await db.miniapp_support_chats.find({"telegram_user_id": telegram_user_id}, {"_id": 0}).sort("created_at", 1).to_list(100)
    return chats


# ============== REFERRAL SYSTEM ==============

@router.get("/referral/{telegram_user_id}")
async def miniapp_get_referral(telegram_user_id: str, tenant_id: str = DEFAULT_TENANT_ID):
    referral = await db.referrals.find_one({"referrer_id": telegram_user_id, "tenant_id": tenant_id}, {"_id": 0})

    if not referral:
        code = f"REF{telegram_user_id[-6:].upper()}{uuid.uuid4().hex[:4].upper()}"
        referral = {
            "id": str(uuid.uuid4()), "referrer_id": telegram_user_id, "referral_code": code,
            "referred_users": [], "total_earnings": 0, "is_active": True, "tenant_id": tenant_id, "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.referrals.insert_one(referral)
        referral.pop("_id", None)

    settings_id = f"referral_settings_{tenant_id}" if tenant_id and tenant_id != DEFAULT_TENANT_ID else "referral_settings"
    settings = await db.referral_settings.find_one({"id": settings_id}, {"_id": 0})
    if not settings:
        settings = await db.referral_settings.find_one({"id": "referral_settings"}, {"_id": 0})
    if not settings:
        settings = {"referrer_reward_type": "discount", "referrer_reward_value": 10, "referee_reward_type": "discount", "referee_reward_value": 10}

    return {
        "referral_code": referral["referral_code"], "referred_count": len(referral.get("referred_users", [])),
        "total_earnings": referral.get("total_earnings", 0),
        "referrer_reward": f"{settings['referrer_reward_value']}% off", "referee_reward": f"{settings['referee_reward_value']}% off"
    }


@router.post("/referral/apply")
async def miniapp_apply_referral(data: dict):
    code = data.get("code", "").upper().strip()
    telegram_user_id = data.get("telegram_user_id", "")
    tenant_id = data.get("tenant_id", DEFAULT_TENANT_ID)

    if not code or not telegram_user_id:
        return {"valid": False, "error": "Missing referral code or user ID"}

    referral = await db.referrals.find_one({"referral_code": code, "is_active": True, "tenant_id": tenant_id}, {"_id": 0})
    if not referral:
        return {"valid": False, "error": "Invalid referral code"}

    if referral["referrer_id"] == telegram_user_id:
        return {"valid": False, "error": "Can't use your own referral code"}

    if telegram_user_id in referral.get("referred_users", []):
        return {"valid": False, "error": "You've already used a referral code"}

    await db.referrals.update_one({"referral_code": code, "tenant_id": tenant_id}, {"$push": {"referred_users": telegram_user_id}})
    settings_id = f"referral_settings_{tenant_id}" if tenant_id and tenant_id != DEFAULT_TENANT_ID else "referral_settings"
    settings = await db.referral_settings.find_one({"id": settings_id}, {"_id": 0})
    referee_discount = settings.get("referee_reward_value", 10) if settings else 10
    return {"valid": True, "discount_percent": referee_discount, "message": f"Referral applied! You get {referee_discount}% off on your next purchase!"}


# ============== NOTIFICATIONS ==============

@router.get("/notifications/{telegram_user_id}")
async def miniapp_get_notifications(telegram_user_id: str, tenant_id: str = DEFAULT_TENANT_ID):
    notifications = []

    sub = await db.subscribers.find_one({"telegram_user_id": telegram_user_id, "status": "active", "tenant_id": tenant_id}, {"_id": 0})
    if sub:
        end_date = sub.get("end_date", "")
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                days_left = (end_dt - datetime.now(timezone.utc)).days
                if days_left <= 3:
                    notifications.append({
                        "id": "expiry_warning", "type": "warning", "title": "Subscription Expiring Soon!",
                        "message": f"Your {sub['plan_name']} plan expires in {days_left} day(s). Renew now!",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    })
            except Exception:
                pass

    pending = await db.payments.find({"telegram_user_id": telegram_user_id, "status": "pending", "tenant_id": tenant_id}, {"_id": 0}).to_list(5)
    for p in pending:
        notifications.append({
            "id": f"pending_{p.get('id', '')}", "type": "info", "title": "Payment Under Review",
            "message": f"Your payment of Rs.{p.get('amount', 0)} for {p.get('plan_name', 'plan')} is being verified.",
            "created_at": p.get("created_at", "")
        })

    recent_plans = await db.plans.find({"is_active": True, "tenant_id": tenant_id}, {"_id": 0, "name": 1, "price": 1, "created_at": 1}).sort("created_at", -1).to_list(3)
    if not sub and recent_plans:
        notifications.append({
            "id": "new_plans", "type": "promo", "title": "Check Out Our Plans!",
            "message": f"Starting from just Rs.{recent_plans[-1].get('price', 0)}. Subscribe now!",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    return notifications


# ============== MENU BUTTON CONFIG ==============

@router.post("/set-menu-button")
async def set_miniapp_menu_button(data: dict):
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
        resp = await client.post(f"https://api.telegram.org/bot{bot_token}/setChatMenuButton", json={"menu_button": {"type": "web_app", "text": button_text, "web_app": {"url": webapp_url}}})
        result = resp.json()
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("description", "Failed"))
    return {"message": "Menu button set!", "url": webapp_url, "text": button_text}


@router.get("/menu-button-status")
async def get_menu_button_status():
    import httpx
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if not bot_token:
        return {"status": "not_configured", "reason": "Bot token not set"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"https://api.telegram.org/bot{bot_token}/getChatMenuButton", json={})
        result = resp.json()
        if result.get("ok"):
            return {"status": "configured", "button": result.get("result", {})}
    return {"status": "unknown"}


# ============== LIVE TICKET PURCHASE WITH AI VERIFY ==============

@router.post("/live-ticket/upload-screenshot")
async def miniapp_live_ticket_upload_screenshot(
    file: UploadFile = File(...),
    telegram_user_id: str = Form(""),
    session_id: str = Form(""),
):
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    session = await db.live_sessions.find_one({"id": session_id, "status": {"$in": ["scheduled", "announced", "live"]}}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Live session not found")

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    uploads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(uploads_path, exist_ok=True)
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"live_ss_{uuid.uuid4().hex[:10]}.{ext}"
    with open(os.path.join(uploads_path, filename), "wb") as f:
        f.write(image_bytes)

    screenshot_url = f"/api/uploads/{filename}"

    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    expected_upi = settings.get("payment_upi_id") or settings.get("upi_id", "")
    ticket_price = session.get("price", 0)

    ticket_id = str(uuid.uuid4())
    ticket = {
        "id": ticket_id, "session_id": session_id, "telegram_user_id": str(telegram_user_id),
        "amount": ticket_price, "screenshot_url": screenshot_url, "status": "pending",
        "payment_method": "miniapp_upi", "tenant_id": session.get("tenant_id", DEFAULT_TENANT_ID),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

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

    if ticket["status"] == "approved":
        await db.live_sessions.update_one({"id": session_id}, {"$inc": {"tickets_sold": 1}})
        if session.get("stream_link") and session.get("status") == "live":
            bot_token = settings.get("telegram_bot_token", "")
            if bot_token and telegram_user_id:
                msg = "<b>Ticket Approved!</b>\n\n"
                msg += f"Session: <b>{session.get('title', '')}</b>\n"
                msg += f"Stream: {session['stream_link']}\n\nEnjoy the stream!"
                try:
                    await send_telegram_message(telegram_user_id, msg, bot_token)
                except Exception:
                    pass

    bot_token = settings.get("telegram_bot_token", "")
    admin_ids = settings.get("telegram_admin_ids", [])
    if bot_token and admin_ids:
        status_emoji = "V" if ticket["status"] == "approved" else "P"
        admin_msg = f"{status_emoji} <b>New Live Ticket Purchase</b>\n\n"
        admin_msg += f"Session: {session.get('title', '')}\nUser: {telegram_user_id}\n"
        admin_msg += f"Amount: Rs.{ticket_price}\nStatus: {ticket['status'].upper()}\n"
        if ai_result.get("ai_enabled"):
            admin_msg += f"AI Confidence: {ai_result.get('confidence_score', 0)}%"
        for admin_id in admin_ids:
            try:
                await send_telegram_message(admin_id, admin_msg, bot_token)
            except Exception:
                pass

    return {
        "success": True, "ticket_id": ticket_id, "status": ticket["status"],
        "ai_verified": ticket["status"] == "approved",
        "ai_result": {
            "enabled": ai_result.get("ai_enabled", False), "is_payment": ai_result.get("is_payment_screenshot", False),
            "confidence": ai_result.get("confidence_score", 0), "reason": ai_result.get("reason", ""),
            "auto_approved": ai_result.get("auto_approve_recommended", False),
        }
    }


@router.get("/live-sessions/public")
async def miniapp_get_live_sessions_public(tenant_id: str = DEFAULT_TENANT_ID):
    sessions = await db.live_sessions.find({"status": {"$in": ["scheduled", "announced", "live"]}, "tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return sessions


@router.get("/live-ticket/status/{telegram_user_id}/{session_id}")
async def miniapp_live_ticket_status(telegram_user_id: str, session_id: str, tenant_id: str = DEFAULT_TENANT_ID):
    ticket = await db.live_tickets.find_one(
        {"telegram_user_id": str(telegram_user_id), "session_id": session_id, "status": {"$in": ["approved", "pending"]}, "tenant_id": tenant_id}, {"_id": 0}
    )
    if ticket:
        return {"has_ticket": True, "status": ticket["status"], "ticket_id": ticket["id"]}
    return {"has_ticket": False}
