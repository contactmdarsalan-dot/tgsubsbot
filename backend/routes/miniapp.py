"""Mini App endpoints - Plans, Payments, Support AI, Referral, Notifications"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from database import db
from services.telegram import get_bot_settings, send_telegram_message, add_to_channel
from config import logger, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, razorpay_client, EMERGENT_LLM_KEY
from datetime import datetime, timezone, timedelta
import uuid
import json

router = APIRouter(prefix="/miniapp")


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
    user_doc = {
        "id": str(uuid.uuid4()),
        "phone": phone,
        "telegram_user_id": telegram_user_id,
        "telegram_username": telegram_username,
        "discount_percent": 20,
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

@router.get("/upi-details")
async def miniapp_get_upi_details():
    """Get UPI payment details for manual payment"""
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    return {
        "upi_id": settings.get("payment_upi_id") or settings.get("upi_id", ""),
        "qr_code_url": settings.get("qr_code_url", ""),
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
