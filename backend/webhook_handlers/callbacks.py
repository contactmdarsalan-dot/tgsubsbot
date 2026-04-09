"""Callback query handlers — button clicks for plans, payments, video calls, admin, live stream, etc."""
from database import db
from services.telegram import (
    get_bot_settings, get_bot_username, send_telegram_message, send_telegram_message_with_buttons,
    send_telegram_message_with_buttons_and_return, edit_telegram_message,
    send_telegram_photo, send_telegram_video, delete_telegram_message,
    add_to_channel, is_admin_or_creator, notify_admin_new_payment,
    urgency_timer_task
)
from services.chat_pool import get_available_chat_group, assign_chat_group
from services.bot_activity import log_bot_activity
from services.payment import create_blurred_image
from config import logger, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, razorpay_client
from datetime import datetime, timezone, timedelta
import uuid
import httpx
import os
import asyncio
import json


async def handle_callback(data, bot_token, bot_tenant_id, settings, background_tasks):
    """Handle all callback_query events — button clicks from inline keyboards."""
    callback_query = data.get("callback_query", {})
    # Handle callback queries (button clicks)
    if callback_query:
        callback_data = callback_query.get("data", "")
        chat_id = str(callback_query.get("from", {}).get("id", ""))
        username = callback_query.get("from", {}).get("username", "")
        
        # Log callback activity
        asyncio.create_task(log_bot_activity("callback", chat_id, username, f"Button: {callback_data}"))
        
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
        
        if callback_data.startswith("buy_"):
            plan_id = callback_data.replace("buy_", "")
            plan = await db.plans.find_one({"id": plan_id, "tenant_id": bot_tenant_id}, {"_id": 0})
            
            if plan:
                # Check if plan has discount
                original_price = int(plan.get('price', 0))
                discount_pct = plan.get('discount_percentage', 0)
                if discount_pct > 0:
                    discounted_price = int(original_price * (100 - discount_pct) / 100)
                    price_display = f"<s>₹{original_price}</s> → <b>₹{discounted_price}</b> 🔥"
                    final_price = discounted_price
                else:
                    price_display = f"<b>₹{original_price}</b>"
                    final_price = original_price
                
                
                payment_msg = f"🔥 <b>EXCLUSIVE OFFER!</b> 🔥\n\n"
                payment_msg += f"<b>📦 {plan.get('name', 'Plan')}</b>\n\n"
                payment_msg += f"💰 Price: {price_display}\n"
                payment_msg += f"⏱ Duration: <b>{plan.get('duration_days', 30)} days</b>\n\n"
                
                if plan.get('features'):
                    payment_msg += "<b>Features:</b>\n"
                    for feat in plan['features']:
                        payment_msg += f"✅ {feat}\n"
                    payment_msg += "\n"
                
                payment_msg += "━━━━━━━━━━━━━━━\n"
                payment_msg += "<b>💳 Payment Options:</b>\n\n"
                
                buttons = []
                
                # Create Razorpay Order (same as Mini App - proven to work)
                razorpay_link = None
                if razorpay_client:
                    try:
                        order_data = {
                            "amount": final_price * 100,
                            "currency": "INR",
                            "receipt": f"bot_{uuid.uuid4().hex[:20]}",
                            "payment_capture": 1
                        }
                        razor_order = await asyncio.to_thread(razorpay_client.order.create, order_data)
                        razorpay_order_id = razor_order.get("id", "")
                        
                        if razorpay_order_id:
                            # Save order in DB
                            await db.razorpay_bot_orders.update_one(
                                {"chat_id": str(chat_id), "plan_id": plan_id, "status": "created"},
                                {"$set": {
                                    "chat_id": str(chat_id),
                                    "username": username or "",
                                    "plan_id": plan_id,
                                    "plan_name": plan.get('name', 'Plan'),
                                    "duration_days": plan.get('duration_days', 30),
                                    "amount": final_price,
                                    "razorpay_order_id": razorpay_order_id,
                                    "status": "created",
                                    "type": "subscription",
                                    "tenant_id": bot_tenant_id,
                                    "created_at": datetime.now(timezone.utc).isoformat()
                                }},
                                upsert=True
                            )
                            
                            # Build payment page URL
                            base_url = os.environ.get("RAZORPAY_CALLBACK_URL", "")
                            if not base_url:
                                website_link = settings.get("website_link", "")
                                if website_link and website_link.startswith("http"):
                                    base_url = website_link.rstrip("/")
                            if not base_url:
                                base_url = os.environ.get("REACT_APP_BACKEND_URL", "")
                            
                            razorpay_link = f"{base_url}/api/pay/{razorpay_order_id}"
                            logger.info(f"Razorpay order created for {chat_id}: {razorpay_order_id}")
                        else:
                            logger.error(f"Razorpay returned empty order_id: {razor_order}")
                    except Exception as rp_err:
                        logger.error(f"Razorpay order creation failed: {type(rp_err).__name__}: {rp_err}")
                        razorpay_link = None
                else:
                    logger.error(f"Razorpay client is None! RAZORPAY_KEY_ID={bool(RAZORPAY_KEY_ID)}")
                
                # Add Razorpay button first (if available)
                if razorpay_link:
                    payment_msg += "💳 <b>Pay via Razorpay (Cards/UPI/NetBanking)</b>\n"
                    payment_msg += "   Click below to pay instantly!\n\n"
                    buttons.append([{"text": "💳 Pay with Razorpay", "url": razorpay_link}])
                
                # Add QR/UPI button if QR code is configured
                qr_code_url = settings.get("qr_code_url", "")
                upi_id = settings.get("payment_upi_id", "") or settings.get("upi_id", "")
                if qr_code_url or upi_id:
                    payment_msg += "📱 <b>Pay via QR/UPI</b>\n"
                    payment_msg += "   Scan QR & send screenshot!\n\n"
                    buttons.append([{"text": "📱 Pay via QR/UPI", "callback_data": f"qr_{plan_id}"}])
                
                payment_msg += f"📱 <b>Your ID:</b> <code>{chat_id}</code>"
                
                buttons.append([{"text": "◀️ Back to Plans", "callback_data": "back_plans"}])
                
                # Send initial message with urgency timer
                msg_result = await send_telegram_message_with_buttons_and_return(chat_id, payment_msg, buttons, bot_token)
                
                if msg_result:
                    # Schedule urgency timer edits in background
                    asyncio.create_task(
                        urgency_timer_task(chat_id, msg_result, plan, price_display, final_price, buttons, bot_token)
                    )
        
        
        elif callback_data.startswith("qr_unlock_"):
            # QR payment for paid post unlock
            post_id = callback_data.replace("qr_unlock_", "")
            paid_post = await db.paid_posts.find_one({"id": post_id, "is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0})
            
            if paid_post:
                post_price = paid_post.get("price", 0)
                if post_price <= 0:
                    plans = await db.plans.find({"is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0}).sort("price", 1).to_list(1)
                    post_price = plans[0].get("price", 99) if plans else 99
                
                qr_code_url = settings.get("qr_code_url", "")
                upi_id = settings.get("payment_upi_id", "") or settings.get("upi_id", "")
                content_label = "Video" if paid_post.get("content_type") == "video" else "Post"
                
                # Set pending screenshot for unlock
                await db.pending_screenshots.update_one(
                    {"telegram_user_id": chat_id, "tenant_id": bot_tenant_id},
                    {"$set": {
                        "telegram_user_id": chat_id,
                        "telegram_username": username,
                        "unlock_post_id": post_id,
                        "expected_amount": post_price,
                        "status": "waiting_unlock",
                        "tenant_id": bot_tenant_id,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }},
                    upsert=True
                )
                
                qr_msg = f"📱 <b>Pay via QR/UPI - Unlock {content_label}</b>\n\n"
                qr_msg += f"💰 Amount: <b>₹{int(post_price)}</b>\n\n"
                qr_msg += "━━━━━━━━━━━━━━━\n"
                if upi_id:
                    qr_msg += f"📱 UPI ID: <code>{upi_id}</code>\n\n"
                qr_msg += "📸 <b>Payment karne ke baad screenshot bhejo!</b>\n"
                qr_msg += "✅ Auto-verify ho jayega!"
                
                cancel_btn = [[{"text": "❌ Cancel", "callback_data": "cancel_payment"}]]
                
                if qr_code_url:
                    await send_telegram_photo(chat_id, qr_code_url, qr_msg, bot_token, {"inline_keyboard": cancel_btn})
                else:
                    await send_telegram_message_with_buttons(chat_id, qr_msg, cancel_btn, bot_token)
            else:
                await send_telegram_message(chat_id, "❌ Post not found or expired.", bot_token)
        
        elif callback_data.startswith("qr_vc_"):
            # QR payment for video call
            parts = callback_data.replace("qr_vc_", "").rsplit("_", 1)
            booking_id = parts[0] if parts else ""
            vc_price = int(parts[1]) if len(parts) > 1 else 0
            
            qr_code_url = settings.get("qr_code_url", "")
            upi_id = settings.get("payment_upi_id", "") or settings.get("upi_id", "")
            
            # Set pending screenshot for video call
            await db.pending_screenshots.update_one(
                {"telegram_user_id": chat_id, "tenant_id": bot_tenant_id},
                {"$set": {
                    "telegram_user_id": chat_id,
                    "telegram_username": username,
                    "booking_id": booking_id,
                    "expected_amount": vc_price,
                    "status": "waiting",
                    "tenant_id": bot_tenant_id,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
            
            qr_msg = f"📱 <b>Pay via QR/UPI - Video Call</b>\n\n"
            qr_msg += f"💰 Amount: <b>₹{vc_price}</b>\n\n"
            qr_msg += "━━━━━━━━━━━━━━━\n"
            if upi_id:
                qr_msg += f"📱 UPI ID: <code>{upi_id}</code>\n\n"
            qr_msg += "📸 <b>Payment karne ke baad screenshot bhejo!</b>\n"
            qr_msg += "✅ Auto-verify ho jayega!"
            
            cancel_btn = [[{"text": "❌ Cancel", "callback_data": "cancel_payment"}]]
            
            if qr_code_url:
                await send_telegram_photo(chat_id, qr_code_url, qr_msg, bot_token, {"inline_keyboard": cancel_btn})
            else:
                await send_telegram_message_with_buttons(chat_id, qr_msg, cancel_btn, bot_token)
        
        elif callback_data.startswith("qr_") and not callback_data.startswith("qr_unlock_") and not callback_data.startswith("qr_vc_"):
            # QR payment for subscription plan
            plan_id = callback_data.replace("qr_", "")
            plan = await db.plans.find_one({"id": plan_id, "tenant_id": bot_tenant_id}, {"_id": 0})
            
            if plan:
                qr_code_url = settings.get("qr_code_url", "")
                upi_id = settings.get("payment_upi_id", "") or settings.get("upi_id", "")
                
                # Calculate final price with discount
                original_price = int(plan.get('price', 0))
                discount_pct = plan.get('discount_percentage', 0)
                if discount_pct > 0:
                    final_price = int(original_price * (100 - discount_pct) / 100)
                else:
                    final_price = original_price
                
                # Set pending screenshot status
                await db.pending_screenshots.update_one(
                    {"telegram_user_id": chat_id, "tenant_id": bot_tenant_id},
                    {"$set": {
                        "telegram_user_id": chat_id,
                        "telegram_username": username,
                        "plan_id": plan_id,
                        "plan_name": plan.get("name", ""),
                        "expected_amount": final_price,
                        "discounted_price": final_price if discount_pct > 0 else None,
                        "status": "waiting",
                        "tenant_id": bot_tenant_id,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }},
                    upsert=True
                )
                
                qr_msg = f"📱 <b>Pay via QR/UPI</b>\n\n"
                qr_msg += f"📦 Plan: <b>{plan.get('name', 'Plan')}</b>\n"
                qr_msg += f"💰 Amount: <b>₹{final_price}</b>\n"
                if discount_pct > 0:
                    qr_msg += f"🔥 <s>₹{original_price}</s> → <b>₹{final_price}</b> ({discount_pct}% OFF)\n"
                qr_msg += f"\n━━━━━━━━━━━━━━━\n"
                if upi_id:
                    qr_msg += f"📱 UPI ID: <code>{upi_id}</code>\n\n"
                qr_msg += "📸 <b>Payment karne ke baad screenshot bhejo!</b>\n"
                qr_msg += "✅ Auto-verify ho jayega!"
                
                cancel_btn = [[{"text": "❌ Cancel", "callback_data": "cancel_payment"}]]
                
                if qr_code_url:
                    await send_telegram_photo(chat_id, qr_code_url, qr_msg, bot_token, {"inline_keyboard": cancel_btn})
                else:
                    await send_telegram_message_with_buttons(chat_id, qr_msg, cancel_btn, bot_token)
            else:
                await send_telegram_message(chat_id, "❌ Plan not found. /start se try karo.", bot_token)
        
        elif callback_data.startswith("razorpay_"):
            # Create Razorpay payment link
            plan_id = callback_data.replace("razorpay_", "")
            plan = await db.plans.find_one({"id": plan_id, "tenant_id": bot_tenant_id}, {"_id": 0})
            
            if plan and razorpay_client:
                try:
                    # Create Razorpay order
                    order = razorpay_client.order.create({
                        "amount": int(plan["price"] * 100),  # paise
                        "currency": "INR",
                        "payment_capture": 1,
                        "notes": {
                            "telegram_user_id": chat_id,
                            "telegram_username": username,
                            "plan_id": plan_id,
                            "plan_name": plan["name"],
                            "type": "bot_subscription"
                        }
                    })
                    
                    # Store order in database
                    order_obj = {
                        "id": str(uuid.uuid4()),
                        "razorpay_order_id": order["id"],
                        "telegram_user_id": chat_id,
                        "telegram_username": username,
                        "plan_id": plan_id,
                        "plan_name": plan["name"],
                        "amount": plan["price"],
                        "status": "created",
                        "tenant_id": bot_tenant_id,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    await db.bot_orders.insert_one(order_obj)
                    
                    # Create payment link
                    payment_link = f"https://rzp.io/l/{order['id']}"
                    
                    # Actually we need to use Razorpay payment page
                    # Send user to a web page that handles Razorpay checkout
                    settings = await get_bot_settings()
                    website_url = settings.get("website_link", "https://tgsubsbot.com")
                    checkout_url = f"{website_url}/bot-checkout?order_id={order['id']}&plan_id={plan_id}&user_id={chat_id}"
                    
                    msg = "💳 <b>Pay via Razorpay</b>\n\n"
                    msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                    msg += f"💰 Amount: <b>₹{plan['price']}</b>\n\n"
                    msg += "Click below to complete payment.\n"
                    msg += "<b>Auto-verify hoga payment ke baad!</b>"
                    
                    buttons = [
                        [{"text": "💳 Pay Now", "url": checkout_url}],
                        [{"text": "◀️ Back to Plans", "callback_data": "back_plans"}]
                    ]
                    await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
                    
                except Exception as e:
                    logger.error(f"Razorpay error: {e}")
                    await send_telegram_message(chat_id, "❌ Payment error. Please try again or contact admin.", bot_token)
        
        elif callback_data.startswith("paid_"):
            plan_id = callback_data.replace("paid_", "")
            plan = await db.plans.find_one({"id": plan_id, "tenant_id": bot_tenant_id}, {"_id": 0})
            
            if plan:
                # Check if already has pending payment for this plan
                existing = await db.payments.find_one({
                    "telegram_user_id": chat_id,
                    "plan_id": plan_id,
                    "status": "pending",
                    "tenant_id": bot_tenant_id
                })
                
                if not existing:
                    # Create pending payment record
                    payment_obj = {
                        "id": str(uuid.uuid4()),
                        "subscriber_id": None,
                        "telegram_user_id": chat_id,
                        "telegram_username": username or "",
                        "amount": plan["price"],
                        "plan_id": plan_id,
                        "plan_name": plan["name"],
                        "payment_method": "manual",
                        "razorpay_order_id": None,
                        "razorpay_payment_id": None,
                        "status": "pending",
                        "tenant_id": bot_tenant_id,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    await db.payments.insert_one(payment_obj)
                    logger.info(f"Created pending payment for user {chat_id}, plan {plan['name']}")
                
                msg = "✅ <b>Payment Recorded!</b>\n\n"
                msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                msg += f"💰 Amount: <b>₹{plan['price']}</b>\n\n"
                msg += "━━━━━━━━━━━━━━━\n"
                msg += "📝 <b>Next Steps:</b>\n\n"
                msg += "1️⃣ Send payment screenshot to admin\n"
                msg += "2️⃣ Admin will verify your payment\n"
                msg += "3️⃣ You'll get channel access!\n\n"
                msg += f"📱 Your ID: <code>{chat_id}</code>\n"
                if username:
                    msg += f"👤 Username: @{username}\n"
                msg += "\n⏳ <i>Verification usually takes 5-30 minutes</i>"
            else:
                msg = "❌ Plan not found. Please try again with /start"
            
            buttons = [[{"text": "◀️ Back to Plans", "callback_data": "back_plans"}]]
            await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        elif callback_data == "back_plans":
            # Show plans again
            plans = await db.plans.find({"is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0}).to_list(10)
            
            welcome_msg = "🎯 <b>Choose Your Plan</b>\n\n"
            buttons = []
            for plan in plans:
                plan_price = int(plan.get('price', 0))
                plan_name = plan.get('name', 'Plan')
                plan_days = plan.get('duration_days', 30)
                plan_id = plan.get('id', '')
                discount = plan.get('discount_percentage', 0)
                if not plan_id:
                    continue
                
                if discount and discount > 0:
                    discounted_price = round(plan_price * (1 - discount / 100))
                    welcome_msg += f"📦 <b>{plan_name}</b>\n"
                    welcome_msg += f"   💰 <s>₹{plan_price}</s> ₹{discounted_price} ({discount}% OFF) • ⏱ {plan_days} days\n\n"
                    buttons.append([{"text": f"📦 {plan_name} - ₹{discounted_price}", "callback_data": f"buy_{plan_id}"}])
                else:
                    welcome_msg += f"📦 <b>{plan_name}</b>\n"
                    welcome_msg += f"   💰 ₹{plan_price} • ⏱ {plan_days} days\n\n"
                    buttons.append([{"text": f"📦 {plan_name} - ₹{plan_price}", "callback_data": f"buy_{plan_id}"}])
            
            buttons.append([{"text": "📊 Check My Status", "callback_data": "check_status"}])
            await send_telegram_message_with_buttons(chat_id, welcome_msg, buttons, bot_token)
        
        elif callback_data == "cancel_payment":
            # Cancel pending screenshot/payment
            await db.pending_screenshots.delete_one({"telegram_user_id": chat_id, "tenant_id": bot_tenant_id})
            
            msg = "❌ <b>Cancelled!</b>\n\n"
            msg += "Payment process cancel ho gaya.\n\n"
            msg += "Phir se try karne ke liye /start bhejo!"
            
            buttons = [[{"text": "🔄 Start Again", "callback_data": "back_plans"}]]
            await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        elif callback_data == "special_discount":
            # Show plan-specific discounted prices
            plans = await db.plans.find({"is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0}).to_list(10)
            
            msg = "🎁 <b>Special Discount Unlocked!</b>\n\n"
            msg += "🔥 <b>Sirf aapke liye special prices:</b>\n\n"
            
            buttons = []
            has_discount = False
            for plan in plans:
                plan_price = int(plan['price'])
                discount_pct = plan.get('discount_percentage', 0)
                
                if discount_pct > 0:
                    has_discount = True
                    discounted_price = int(plan_price * (100 - discount_pct) / 100)
                    msg += f"📦 <b>{plan['name']}</b>\n"
                    msg += f"   <s>₹{plan_price}</s> → 💰 <b>₹{discounted_price}</b> 🔥\n\n"
                    buttons.append([{"text": f"🔥 {plan['name']} - ₹{discounted_price}", "callback_data": f"buy_{plan['id']}"}])
                else:
                    # No discount for this plan - show normal price
                    msg += f"📦 <b>{plan['name']}</b>\n"
                    msg += f"   ₹{plan_price}\n\n"
                    buttons.append([{"text": f"📦 {plan['name']} - ₹{plan_price}", "callback_data": f"buy_{plan['id']}"}])
            
            if has_discount:
                msg += "⚡ <i>Limited time offer!</i>"
            else:
                msg = "📦 <b>Available Plans:</b>\n\n" + msg.split("special prices:</b>\n\n")[1]
            
            buttons.append([{"text": "📊 Check My Status", "callback_data": "check_status"}])
            await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        elif callback_data.startswith("confirm_ss_"):
            # User confirmed it's a payment screenshot - VERIFY
            plan_id = callback_data.replace("confirm_ss_", "")
            plan = await db.plans.find_one({"id": plan_id, "tenant_id": bot_tenant_id}, {"_id": 0})
            pending = await db.pending_screenshots.find_one({"telegram_user_id": chat_id, "tenant_id": bot_tenant_id}, {"_id": 0})
            
            if plan and pending:
                photo_file_id = pending.get("photo_file_id")
                final_amount = pending.get("discounted_price") or plan["price"]
                
                # Create payment record
                payment_obj = {
                    "id": str(uuid.uuid4()),
                    "subscriber_id": None,
                    "telegram_user_id": chat_id,
                    "telegram_username": username or pending.get("telegram_username", ""),
                    "amount": final_amount,
                    "plan_id": plan_id,
                    "plan_name": plan["name"],
                    "payment_method": "qr_screenshot",
                    "screenshot_file_id": photo_file_id,
                    "status": "verified",
                    "auto_verified": True,
                    "tenant_id": bot_tenant_id,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.payments.insert_one(payment_obj)
                
                # Delete pending screenshot record
                await db.pending_screenshots.delete_one({"telegram_user_id": chat_id, "tenant_id": bot_tenant_id})
                
                # Check if this is a Chat plan (5 Min or 30 Min)
                plan_name_lower = plan['name'].lower()
                is_chat_plan = "min chat" in plan_name_lower or "minute chat" in plan_name_lower
                
                if is_chat_plan:
                    # Handle time-limited chat plan
                    if "5" in plan_name_lower:
                        duration_minutes = 5
                        plan_type = "5min"
                    elif "30" in plan_name_lower:
                        duration_minutes = 30
                        plan_type = "30min"
                    else:
                        duration_minutes = 5
                        plan_type = "5min"
                    
                    # Get available group from pool
                    available_group = await get_available_chat_group()
                    
                    if available_group:
                        result = await assign_chat_group(
                            available_group["group_id"],
                            chat_id,
                            username,
                            plan_type,
                            duration_minutes
                        )
                        
                        if result.get("success"):
                            invite_link = result.get("invite_link")
                            
                            success_msg = "✅ <b>Payment Verified!</b>\n\n"
                            success_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                            success_msg += f"💰 Amount: <b>₹{final_amount}</b>\n"
                            success_msg += f"⏱ Duration: <b>{duration_minutes} minutes</b>\n\n"
                            success_msg += "🔗 <b>Join the chat now:</b>\n"
                            success_msg += f"{invite_link}\n\n"
                            success_msg += f"⚠️ <b>Note:</b> You have {duration_minutes} minutes to chat.\n"
                            success_msg += "After time ends, you'll need to renew!"
                            
                            await send_telegram_message(chat_id, success_msg, bot_token)
                        else:
                            error_msg = "✅ <b>Payment Verified!</b>\n\n"
                            error_msg += "But chat group assignment failed.\n"
                            error_msg += "Admin will contact you shortly!"
                            await send_telegram_message(chat_id, error_msg, bot_token)
                    else:
                        no_group_msg = "✅ <b>Payment Verified!</b>\n\n"
                        no_group_msg += "⚠️ All chat slots are currently busy.\n\n"
                        no_group_msg += "Admin will assign you a chat slot soon!"
                        await send_telegram_message(chat_id, no_group_msg, bot_token)
                else:
                    # Regular subscription - create subscriber and add to channel
                    grace_days = settings.get("grace_period_days", 2)
                    end_date = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])
                    grace_end = end_date + timedelta(days=grace_days)
                    
                    subscriber_obj = {
                        "id": str(uuid.uuid4()),
                        "telegram_user_id": chat_id,
                        "telegram_username": username or pending.get("telegram_username", ""),
                        "plan_id": plan["id"],
                        "plan_name": plan["name"],
                        "payment_method": "qr_screenshot",
                        "payment_id": payment_obj["id"],
                        "status": "active",
                        "start_date": datetime.now(timezone.utc).isoformat(),
                        "end_date": end_date.isoformat(),
                        "grace_end_date": grace_end.isoformat(),
                        "reminder_sent": False,
                        "tenant_id": bot_tenant_id,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    await db.subscribers.insert_one(subscriber_obj)
                    
                    success_msg = "✅ <b>Payment Verified!</b>\n\n"
                    success_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                    success_msg += f"💰 Amount: <b>₹{final_amount}</b>\n"
                    success_msg += f"⏱ Valid till: <b>{end_date.strftime('%d %b %Y')}</b>\n\n"
                    success_msg += "🎉 <b>Subscription Activated!</b>\n\n"
                    success_msg += f"🌐 <b>Visit:</b> {settings.get('website_link', 'https://miraclecouplee.syke.club')}\n\n"
                    success_msg += "📢 Channel link aa raha hai..."
                    
                    await send_telegram_message(chat_id, success_msg, bot_token)
                    
                    plan_channel = plan.get("channel_id", "")
                    if plan_channel:
                        await add_to_channel(chat_id, plan_channel, plan["name"])
                
                logger.info(f"Payment verified for user {chat_id}, plan {plan['name']}")
                
                # Notify admin about verified payment
                await notify_admin_new_payment(
                    chat_id, username or pending.get("telegram_username", ""),
                    plan['name'], final_amount,
                    screenshot_file_id=photo_file_id,
                    payment_id=payment_obj["id"],
                    payment_status="verified"
                )
            else:
                await send_telegram_message(chat_id, "❌ Error. /start se dobara try karo.", bot_token)
        
        elif callback_data == "wrong_ss":
            # User sent wrong image - decline and ask for correct one
            await db.pending_screenshots.update_one(
                {"telegram_user_id": chat_id, "tenant_id": bot_tenant_id},
                {"$set": {"status": "waiting"}}  # Reset to waiting
            )
            
            msg = "❌ <b>Galat Image!</b>\n\n"
            msg += "📸 <b>Sirf payment screenshot bhejo:</b>\n"
            msg += "• GPay ✅\n"
            msg += "• PhonePe ✅\n"
            msg += "• Paytm ✅\n"
            msg += "• UPI ✅\n\n"
            msg += "⏳ <b>Sahi screenshot ka wait kar raha hun...</b>"
            
            buttons = [[{"text": "❌ Cancel", "callback_data": "cancel_payment"}]]
            await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        elif callback_data.startswith("discount_"):
            # Show discounted price
            plan_id = callback_data.replace("discount_", "")
            plan = await db.plans.find_one({"id": plan_id, "tenant_id": bot_tenant_id}, {"_id": 0})
            
            if plan:
                original_price = plan["price"]
                discounted_price = int(original_price * 0.7)  # 30% discount
                
                msg = "🎁 <b>Special Discount!</b>\n\n"
                msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                msg += f"💰 Original: <s>₹{original_price}</s>\n"
                msg += f"🔥 <b>Discounted: ₹{discounted_price}</b> (30% OFF!)\n\n"
                msg += "📸 Payment karke screenshot bhejo!\n"
                msg += "✅ Turant verify ho jayega!"
                
                # Update pending screenshot with discounted price
                await db.pending_screenshots.update_one(
                    {"telegram_user_id": chat_id, "tenant_id": bot_tenant_id},
                    {"$set": {"discounted_price": discounted_price, "discount_applied": True}}
                )
                
                buttons = [
                    [{"text": "✅ I've Paid", "callback_data": f"paid_{plan_id}"}],
                    [{"text": "❌ Cancel", "callback_data": "cancel_payment"}]
                ]
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
            else:
                await send_telegram_message(chat_id, "❌ Plan not found. /start karke dobara try karo.", bot_token)
        
        elif callback_data.startswith("renew_chat_"):
            # Handle chat session renewal
            session_id = callback_data.replace("renew_chat_", "")
            session = await db.chat_sessions.find_one({"id": session_id}, {"_id": 0})
            
            if session:
                plan_type = session.get("plan_type", "5min")
                
                # Find matching plan
                if plan_type == "5min":
                    plan = await db.plans.find_one({"name": {"$regex": "5.*min.*chat", "$options": "i"}, "tenant_id": bot_tenant_id}, {"_id": 0})
                else:
                    plan = await db.plans.find_one({"name": {"$regex": "30.*min.*chat", "$options": "i"}, "tenant_id": bot_tenant_id}, {"_id": 0})
                
                if plan:
                    renew_msg = f"🔄 <b>Renew Chat Session</b>\n\n"
                    renew_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                    renew_msg += f"💰 Price: <b>₹{plan['price']}</b>\n\n"
                    renew_msg += "━━━━━━━━━━━━━━━\n"
                    renew_msg += "💳 <b>Pay via Razorpay and click I've Paid</b>\n\n"
                    renew_msg += f"📱 <b>Your User ID:</b> <code>{chat_id}</code>"
                    
                    buttons = []
                    buttons.append([{"text": "✅ I've Paid", "callback_data": f"paid_{plan['id']}"}])
                    
                    await send_telegram_message_with_buttons(chat_id, renew_msg, buttons, bot_token)
                else:
                    await send_telegram_message(chat_id, "Plan not found. Use /start to see plans.", bot_token)
            else:
                await send_telegram_message(chat_id, "Session not found. Use /start to buy new plan.", bot_token)
        
        elif callback_data.startswith("exit_chat_"):
            # Handle chat session exit/cancel
            session_id = callback_data.replace("exit_chat_", "")
            session = await db.chat_sessions.find_one({"id": session_id}, {"_id": 0})
            
            if session:
                group_id = session.get("group_id")
                user_id = session.get("user_id")
                
                # Release the group and kick user
                if group_id:
                    await release_chat_group(group_id)
                
                # Update session status
                await db.chat_sessions.update_one(
                    {"id": session_id},
                    {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}}
                )
                
                # Send goodbye message
                exit_msg = "👋 <b>Chat Session Ended</b>\n\n"
                exit_msg += "Thank you for using our service!\n\n"
                exit_msg += "💬 Want to chat again?\n"
                exit_msg += "Use /start to buy a new session."
                
                await send_telegram_message(chat_id, exit_msg, bot_token)
                
                logger.info(f"User {chat_id} exited chat session {session_id}")
            else:
                await send_telegram_message(chat_id, "Session not found.", bot_token)
        
        elif callback_data.startswith("renew_"):
            # Handle renewal - go directly to payment for the same plan
            plan_id = callback_data.replace("renew_", "")
            plan = await db.plans.find_one({"id": plan_id, "tenant_id": bot_tenant_id}, {"_id": 0})
            
            if plan:
                # Show payment options directly
                renew_msg = f"🔄 <b>Renew Subscription</b>\n\n"
                renew_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                renew_msg += f"💰 Price: <b>₹{plan['price']}</b>\n"
                renew_msg += f"⏱ Duration: <b>{plan['duration_days']} days</b>\n\n"
                renew_msg += "━━━━━━━━━━━━━━━\n"
                renew_msg += "💳 <b>Pay via Razorpay and click I've Paid</b>\n\n"
                renew_msg += f"📱 <b>Your User ID:</b> <code>{chat_id}</code>"
                
                buttons = []
                buttons.append([{"text": "✅ I've Paid", "callback_data": f"paid_{plan_id}"}])
                buttons.append([{"text": "📦 View Other Plans", "callback_data": "back_plans"}])
                
                await send_telegram_message_with_buttons(chat_id, renew_msg, buttons, bot_token)
            else:
                # Plan not found, show all plans
                await send_telegram_message(chat_id, "Plan not found. Please choose from available plans:", bot_token)
                plans = await db.plans.find({"is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0}).to_list(10)
                buttons = []
                for p in plans:
                    buttons.append([{"text": f"📦 {p['name']} - ₹{p['price']}", "callback_data": f"buy_{p['id']}"}])
                await send_telegram_message_with_buttons(chat_id, "🎯 <b>Available Plans:</b>", buttons, bot_token)
        
        # ============ VIDEO CALL BOOKING HANDLERS ============
        elif callback_data == "book_videocall":
            # Show date selection for video call
            today = datetime.now(timezone.utc).date()
            
            msg = "📅 <b>Select Date for Video Call</b>\n\n"
            msg += "Choose a date from below:"
            
            buttons = []
            for i in range(7):  # Next 7 days
                date = today + timedelta(days=i)
                date_str = date.strftime("%Y-%m-%d")
                day_name = date.strftime("%A")
                display = date.strftime("%d %b") + f" ({day_name})"
                buttons.append([{"text": f"📆 {display}", "callback_data": f"vc_date_{date_str}"}])
            
            buttons.append([{"text": "❌ Cancel", "callback_data": "cancel_action"}])
            await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        elif callback_data.startswith("vc_date_"):
            # Date selected, show time slots
            selected_date = callback_data.replace("vc_date_", "")
            
            msg = f"🕐 <b>Select Time Slot</b>\n\n"
            msg += f"📅 Date: <b>{selected_date}</b>\n\n"
            msg += "Choose a time:"
            
            time_slots = ["10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00"]
            buttons = []
            row = []
            for i, time in enumerate(time_slots):
                row.append({"text": f"🕐 {time}", "callback_data": f"vc_time_{selected_date}_{time}"})
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            
            buttons.append([{"text": "◀️ Back to Dates", "callback_data": "book_videocall"}])
            buttons.append([{"text": "❌ Cancel", "callback_data": "cancel_action"}])
            await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        elif callback_data.startswith("vc_time_"):
            # Time selected, confirm booking
            parts = callback_data.replace("vc_time_", "").split("_")
            selected_date = parts[0]
            selected_time = parts[1]
            
            settings = await get_bot_settings()
            price = settings.get("video_call_price", 500)
            duration = settings.get("video_call_duration", 30)
            
            msg = f"✅ <b>Confirm Video Call Booking</b>\n\n"
            msg += f"📅 Date: <b>{selected_date}</b>\n"
            msg += f"🕐 Time: <b>{selected_time}</b>\n"
            msg += f"⏱ Duration: <b>{duration} minutes</b>\n"
            msg += f"💰 Price: <b>₹{price}</b>\n\n"
            msg += "Click confirm to proceed with payment:"
            
            buttons = [
                [{"text": "✅ Confirm & Pay", "callback_data": f"vc_confirm_{selected_date}_{selected_time}"}],
                [{"text": "◀️ Change Time", "callback_data": f"vc_date_{selected_date}"}],
                [{"text": "❌ Cancel", "callback_data": "cancel_action"}]
            ]
            await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        elif callback_data.startswith("vc_confirm_"):
            # Create booking and show payment
            parts = callback_data.replace("vc_confirm_", "").split("_")
            selected_date = parts[0]
            selected_time = parts[1]
            
            settings = await get_bot_settings()
            price = settings.get("video_call_price", 500)
            duration = settings.get("video_call_duration", 30)
            
            # Create booking record
            booking = {
                "id": str(uuid.uuid4()),
                "telegram_user_id": chat_id,
                "telegram_username": username,
                "scheduled_date": selected_date,
                "scheduled_time": selected_time,
                "duration_minutes": duration,
                "price": price,
                "status": "pending_payment",
                "tenant_id": bot_tenant_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.video_call_bookings.insert_one(booking)
            
            msg = f"📹 <b>Video Call Booking Created!</b>\n\n"
            msg += f"🆔 Booking ID: <code>{booking['id'][:8]}</code>\n"
            msg += f"📅 Date: <b>{selected_date}</b>\n"
            msg += f"🕐 Time: <b>{selected_time}</b>\n"
            msg += f"💰 Amount: <b>₹{price}</b>\n\n"
            msg += "━━━━━━━━━━━━━━━\n"
            msg += "💳 <b>Payment Options:</b>\n\n"
            
            buttons = []
            
            # Add Razorpay button if available
            if razorpay_client:
                try:
                    order_data = {"amount": int(price) * 100, "currency": "INR",
                                  "receipt": f"vc_{uuid.uuid4().hex[:16]}", "payment_capture": 1}
                    razor_order = await asyncio.to_thread(razorpay_client.order.create, order_data)
                    razorpay_order_id = razor_order.get("id", "")
                    if razorpay_order_id:
                        await db.razorpay_bot_orders.update_one(
                            {"chat_id": str(chat_id), "booking_id": booking['id'], "status": "created"},
                            {"$set": {
                                "chat_id": str(chat_id), "username": username or "",
                                "booking_id": booking['id'],
                                "plan_id": "", "plan_name": "Video Call",
                                "duration_days": 0, "amount": int(price),
                                "razorpay_order_id": razorpay_order_id,
                                "status": "created", "type": "video_call",
                                "tenant_id": bot_tenant_id,
                                "created_at": datetime.now(timezone.utc).isoformat()
                            }}, upsert=True
                        )
                        base_url = os.environ.get("RAZORPAY_CALLBACK_URL", "")
                        if not base_url:
                            base_url = settings.get("website_link", os.environ.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
                        rp_link = f"{base_url}/api/pay/{razorpay_order_id}"
                        buttons.append([{"text": "💳 Pay with Razorpay", "url": rp_link}])
                except Exception as rp_err:
                    logger.error(f"Razorpay order for video call failed: {rp_err}")
            
            # Add QR/UPI button
            qr_code_url = settings.get("qr_code_url", "")
            upi_id = settings.get("payment_upi_id", "") or settings.get("upi_id", "")
            if qr_code_url or upi_id:
                buttons.append([{"text": "📱 Pay via QR/UPI", "callback_data": f"qr_vc_{booking['id']}_{price}"}])
            
            msg += f"📱 <b>Your ID:</b> <code>{chat_id}</code>"
            buttons.append([{"text": "❌ Cancel Booking", "callback_data": f"vc_cancel_{booking['id']}"}])
            
            await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        elif callback_data.startswith("vc_cancel_"):
            # Cancel video call booking
            booking_id = callback_data.replace("vc_cancel_", "")
            await db.video_call_bookings.update_one(
                {"id": booking_id},
                {"$set": {"status": "cancelled"}}
            )
            await send_telegram_message(chat_id, "❌ Video call booking cancelled.\n\nUse /videocall to book again.", bot_token)
        
        elif callback_data == "cancel_action":
            await send_telegram_message(chat_id, "❌ Action cancelled.\n\nUse /start to see plans or /help for commands.", bot_token)
        
        # ========== ADMIN APPROVE/REJECT PAYMENT CALLBACKS ==========
        
        elif callback_data == "noop":
            # Do nothing - just acknowledge the callback
            pass
        
        elif callback_data.startswith("admin_approve_"):
            payment_id = callback_data.replace("admin_approve_", "")
            
            # Verify the clicking user is an admin
            is_admin = await is_admin_or_creator(chat_id, username)
            if not is_admin:
                await send_telegram_message(chat_id, "❌ Only admins can approve payments.", bot_token)
            else:
                payment = await db.payments.find_one({"id": payment_id, "tenant_id": bot_tenant_id}, {"_id": 0})
                
                if not payment:
                    await send_telegram_message(chat_id, "❌ Payment not found.", bot_token)
                elif payment.get("status") == "verified":
                    await send_telegram_message(chat_id, "✅ This payment is already verified.", bot_token)
                else:
                    # Update payment status to verified
                    await db.payments.update_one(
                        {"id": payment_id, "tenant_id": bot_tenant_id},
                        {"$set": {
                            "status": "verified",
                            "admin_verified": True,
                            "verified_by": chat_id,
                            "verified_at": datetime.now(timezone.utc).isoformat()
                        }}
                    )
                    
                    user_tg_id = payment.get("telegram_user_id", "")
                    plan_id = payment.get("plan_id", "")
                    plan = await db.plans.find_one({"id": plan_id, "tenant_id": bot_tenant_id}, {"_id": 0}) if plan_id else None
                    
                    if plan:
                        # Create subscriber
                        grace_days = settings.get("grace_period_days", 2)
                        end_date = datetime.now(timezone.utc) + timedelta(days=plan.get("duration_days", 30))
                        grace_end = end_date + timedelta(days=grace_days)
                        
                        subscriber_obj = {
                            "id": str(uuid.uuid4()),
                            "telegram_user_id": user_tg_id,
                            "telegram_username": payment.get("telegram_username", ""),
                            "plan_id": plan["id"],
                            "plan_name": plan["name"],
                            "payment_method": payment.get("payment_method", "manual"),
                            "payment_id": payment_id,
                            "status": "active",
                            "start_date": datetime.now(timezone.utc).isoformat(),
                            "end_date": end_date.isoformat(),
                            "grace_end_date": grace_end.isoformat(),
                            "reminder_sent": False,
                            "tenant_id": payment.get("tenant_id", bot_tenant_id),
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                        await db.subscribers.insert_one(subscriber_obj)
                        
                        # Add user to channel
                        plan_channel = plan.get("channel_id", "")
                        await add_to_channel(user_tg_id, plan_channel, plan['name'], use_default=True)
                        
                        # Notify user
                        user_msg = "✅ <b>Payment Approved!</b>\n\n"
                        user_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                        user_msg += f"💰 Amount: <b>₹{payment.get('amount', 0)}</b>\n"
                        user_msg += f"⏱ Valid till: <b>{end_date.strftime('%d %b %Y')}</b>\n\n"
                        user_msg += "🎉 <b>Subscription Activated!</b>\n"
                        user_msg += "Channel access mil gaya hai!"
                        await send_telegram_message(user_tg_id, user_msg, bot_token)
                    else:
                        # No plan found, just notify user
                        user_msg = "✅ <b>Payment Approved by Admin!</b>\n\nAdmin se contact karo for access."
                        await send_telegram_message(user_tg_id, user_msg, bot_token)
                    
                    # Edit the admin message to show approved status
                    callback_msg = callback_query.get("message", {})
                    msg_id = callback_msg.get("message_id")
                    admin_confirm = f"✅ <b>APPROVED</b> by Admin\n\n"
                    admin_confirm += f"👤 User: <code>{user_tg_id}</code>\n"
                    admin_confirm += f"📦 Plan: <b>{payment.get('plan_name', 'N/A')}</b>\n"
                    admin_confirm += f"💰 Amount: <b>₹{payment.get('amount', 0)}</b>"
                    
                    try:
                        # Try editMessageCaption first (for photo messages)
                        async with httpx.AsyncClient(timeout=10.0) as http_client:
                            resp = await http_client.post(
                                f"https://api.telegram.org/bot{bot_token}/editMessageCaption",
                                json={
                                    "chat_id": chat_id,
                                    "message_id": msg_id,
                                    "caption": admin_confirm,
                                    "parse_mode": "HTML"
                                }
                            )
                            if resp.status_code != 200:
                                # Fallback to editMessageText (for text-only messages)
                                await edit_telegram_message(chat_id, msg_id, admin_confirm, bot_token=bot_token)
                    except Exception:
                        await send_telegram_message(chat_id, admin_confirm, bot_token)
                    
                    logger.info(f"Admin {chat_id} approved payment {payment_id}")
        
        elif callback_data.startswith("admin_reject_"):
            payment_id = callback_data.replace("admin_reject_", "")
            
            # Verify the clicking user is an admin
            is_admin = await is_admin_or_creator(chat_id, username)
            if not is_admin:
                await send_telegram_message(chat_id, "❌ Only admins can reject payments.", bot_token)
            else:
                payment = await db.payments.find_one({"id": payment_id, "tenant_id": bot_tenant_id}, {"_id": 0})
                
                if not payment:
                    await send_telegram_message(chat_id, "❌ Payment not found.", bot_token)
                elif payment.get("status") == "rejected":
                    await send_telegram_message(chat_id, "❌ This payment is already rejected.", bot_token)
                else:
                    was_verified = payment.get("status") == "verified"
                    
                    # Update payment status to rejected
                    await db.payments.update_one(
                        {"id": payment_id, "tenant_id": bot_tenant_id},
                        {"$set": {
                            "status": "rejected",
                            "rejected_by": chat_id,
                            "rejected_at": datetime.now(timezone.utc).isoformat()
                        }}
                    )
                    
                    user_tg_id = payment.get("telegram_user_id", "")
                    
                    # If was verified, also deactivate subscriber and remove from channel
                    if was_verified:
                        await db.subscribers.update_one(
                            {"payment_id": payment_id, "tenant_id": bot_tenant_id},
                            {"$set": {"status": "expired"}}
                        )
                        plan_id = payment.get("plan_id", "")
                        plan = await db.plans.find_one({"id": plan_id, "tenant_id": bot_tenant_id}, {"_id": 0}) if plan_id else None
                        if plan:
                            plan_channel = plan.get("channel_id", "")
                            await remove_from_channel(user_tg_id, plan_channel, plan['name'])
                    
                    # Notify user
                    user_msg = "❌ <b>Payment Rejected!</b>\n\n"
                    user_msg += f"📦 Plan: <b>{payment.get('plan_name', 'N/A')}</b>\n"
                    user_msg += f"💰 Amount: <b>₹{payment.get('amount', 0)}</b>\n\n"
                    user_msg += "Admin ne payment reject kar diya.\n"
                    user_msg += "Sahi payment screenshot bhejo ya /start se dobara try karo."
                    await send_telegram_message(user_tg_id, user_msg, bot_token)
                    
                    # Edit the admin message to show rejected status
                    callback_msg = callback_query.get("message", {})
                    msg_id = callback_msg.get("message_id")
                    admin_confirm = f"❌ <b>REJECTED</b> by Admin\n\n"
                    admin_confirm += f"👤 User: <code>{user_tg_id}</code>\n"
                    admin_confirm += f"📦 Plan: <b>{payment.get('plan_name', 'N/A')}</b>\n"
                    admin_confirm += f"💰 Amount: <b>₹{payment.get('amount', 0)}</b>"
                    
                    try:
                        # Try editMessageCaption first (for photo messages)
                        async with httpx.AsyncClient(timeout=10.0) as http_client:
                            resp = await http_client.post(
                                f"https://api.telegram.org/bot{bot_token}/editMessageCaption",
                                json={
                                    "chat_id": chat_id,
                                    "message_id": msg_id,
                                    "caption": admin_confirm,
                                    "parse_mode": "HTML"
                                }
                            )
                            if resp.status_code != 200:
                                # Fallback to editMessageText (for text-only messages)
                                await edit_telegram_message(chat_id, msg_id, admin_confirm, bot_token=bot_token)
                    except Exception:
                        await send_telegram_message(chat_id, admin_confirm, bot_token)
                    
                    logger.info(f"Admin {chat_id} rejected payment {payment_id}")
        
        elif callback_data == "check_status":
            subscriber = await db.subscribers.find_one({"telegram_user_id": chat_id, "tenant_id": bot_tenant_id}, {"_id": 0})
            if subscriber:
                end_date = datetime.fromisoformat(subscriber["end_date"]) if isinstance(subscriber["end_date"], str) else subscriber["end_date"]
                days_left = (end_date - datetime.now(timezone.utc)).days
                
                status_emoji = "✅" if subscriber['status'] == 'active' else "⚠️" if subscriber['status'] == 'grace' else "❌"
                status_msg = f"{status_emoji} <b>Your Subscription</b>\n\n"
                status_msg += f"📦 Plan: <b>{subscriber['plan_name']}</b>\n"
                status_msg += f"📊 Status: <b>{subscriber['status'].upper()}</b>\n"
                status_msg += f"📅 Expires: <b>{end_date.strftime('%d %b %Y')}</b>\n"
                status_msg += f"⏳ Days Left: <b>{days_left}</b>"
            else:
                status_msg = "❌ You don't have an active subscription.\n\nUse /start to see available plans!"
            
            buttons = [[{"text": "◀️ Back to Plans", "callback_data": "back_plans"}]]
            await send_telegram_message_with_buttons(chat_id, status_msg, buttons, bot_token)
        
        # ========== PAID POST UNLOCK CALLBACKS ==========
        
        elif callback_data.startswith("unlock_paid_"):
            # User clicked old "I've Paid" button - redirect to use Razorpay link
            post_id = callback_data.replace("unlock_paid_", "")
            paid_post = await db.paid_posts.find_one({"id": post_id, "is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0})
            
            if paid_post:
                # Check if already unlocked
                existing = await db.paid_post_unlocks.find_one({
                    "post_id": post_id, "telegram_user_id": chat_id, "tenant_id": bot_tenant_id
                }, {"_id": 0})
                if existing:
                    # Already unlocked - resend content
                    if paid_post.get("content_type") == "photo" and paid_post.get("original_file_id"):
                        caption = f"🔓 <b>Already Unlocked!</b>\n\n{paid_post.get('caption', '')}"
                        await send_telegram_photo(chat_id, paid_post["original_file_id"], caption, bot_token)
                    elif paid_post.get("content_type") == "video" and paid_post.get("original_file_id"):
                        caption = f"🔓 <b>Already Unlocked!</b>\n\n{paid_post.get('caption', '')}"
                        await send_telegram_video(chat_id, paid_post["original_file_id"], caption, bot_token)
                    else:
                        await send_telegram_message(chat_id, "✅ You've already unlocked this content!", bot_token)
                else:
                    verify_msg = "💳 <b>Please use the Razorpay payment button above to pay!</b>\n\n"
                    verify_msg += "After payment, content will be unlocked automatically. ✅"
                    await send_telegram_message(chat_id, verify_msg, bot_token)
            else:
                await send_telegram_message(chat_id, "❌ Post not found or expired.", bot_token)
        
        # Live ticket purchase
        elif callback_data.startswith("live_ticket_"):
            session_id = callback_data.replace("live_ticket_", "")
            session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
            
            if session:
                # Check if already has ticket
                existing_ticket = await db.live_tickets.find_one({
                    "session_id": session_id,
                    "telegram_user_id": chat_id,
                    "status": {"$in": ["pending", "approved"]}
                }, {"_id": 0})
                
                if existing_ticket:
                    if existing_ticket.get("status") == "approved":
                        msg = "✅ <b>You already have a ticket!</b>\n\n"
                        if session.get("stream_link"):
                            msg += f"🔗 Stream Link:\n{session['stream_link']}"
                        else:
                            msg += "Stream link will be sent when we go live!"
                    else:
                        msg = "⏳ <b>Ticket Pending</b>\n\nYour ticket is pending approval. Please wait!"
                    await send_telegram_message(chat_id, msg, bot_token)
                else:
                    # Paid session - save pending and ask for payment
                    price = session.get("price", 0)
                    
                    if price <= 0:
                        # Free session - auto approve
                        ticket = {
                            "id": str(uuid.uuid4()),
                            "session_id": session_id,
                            "session_title": session.get("title", ""),
                            "telegram_user_id": chat_id,
                            "telegram_username": username,
                            "amount": 0,
                            "status": "approved",
                            "tenant_id": session.get("tenant_id", bot_tenant_id),
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                        await db.live_tickets.insert_one(ticket)
                        await db.live_sessions.update_one({"id": session_id}, {"$inc": {"tickets_sold": 1}})
                        
                        msg = "✅ <b>Free Ticket Confirmed!</b>\n\n"
                        msg += f"📺 Session: <b>{session.get('title')}</b>\n"
                        msg += f"📅 Date: <b>{session.get('scheduled_date')}</b>\n"
                        msg += f"🕐 Time: <b>{session.get('scheduled_time')}</b>\n\n"
                        if session.get("stream_link"):
                            msg += f"🔗 Stream Link:\n{session['stream_link']}"
                        else:
                            msg += "🔔 Stream link will be sent when we go live!"
                        await send_telegram_message(chat_id, msg, bot_token)
                    else:
                        # Paid session - save pending
                        await db.pending_screenshots.update_one(
                            {"telegram_user_id": chat_id, "tenant_id": bot_tenant_id},
                            {"$set": {
                                "telegram_user_id": chat_id,
                                "telegram_username": username,
                                "live_session_id": session_id,
                                "live_session_title": session.get("title", ""),
                                "expected_amount": price,
                                "status": "waiting_live_ticket",
                                "created_at": datetime.now(timezone.utc).isoformat()
                            }},
                            upsert=True
                        )
                        
                        msg = f"🎟 <b>Get Ticket: {session.get('title')}</b>\n\n"
                        msg += f"💰 Price: <b>₹{int(price)}</b>\n\n"
                        msg += "━━━━━━━━━━━━━━━\n"
                        msg += "💳 <b>Payment Options:</b>\n\n"
                        
                        ticket_buttons = []
                        
                        # Add Razorpay button
                        if razorpay_client:
                            try:
                                order_data = {"amount": int(price) * 100, "currency": "INR",
                                              "receipt": f"live_{uuid.uuid4().hex[:16]}", "payment_capture": 1}
                                razor_order = await asyncio.to_thread(razorpay_client.order.create, order_data)
                                razorpay_order_id = razor_order.get("id", "")
                                if razorpay_order_id:
                                    await db.razorpay_bot_orders.update_one(
                                        {"chat_id": str(chat_id), "live_session_id": session_id, "status": "created"},
                                        {"$set": {
                                            "chat_id": str(chat_id), "username": username or "",
                                            "live_session_id": session_id,
                                            "plan_id": "", "plan_name": f"Live: {session.get('title', '')}",
                                            "duration_days": 0, "amount": int(price),
                                            "razorpay_order_id": razorpay_order_id,
                                            "status": "created", "type": "live_ticket",
                                            "tenant_id": bot_tenant_id,
                                            "created_at": datetime.now(timezone.utc).isoformat()
                                        }}, upsert=True
                                    )
                                    base_url = os.environ.get("RAZORPAY_CALLBACK_URL", "")
                                    if not base_url:
                                        base_url = settings.get("website_link", os.environ.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
                                    rp_link = f"{base_url}/api/pay/{razorpay_order_id}"
                                    ticket_buttons.append([{"text": "💳 Pay with Razorpay", "url": rp_link}])
                            except Exception as rp_err:
                                logger.error(f"Razorpay order for live ticket failed: {rp_err}")
                        
                        # Add QR/UPI option - sends QR image when clicked
                        qr_code_url = settings.get("qr_code_url", "")
                        upi_id = settings.get("payment_upi_id", "") or settings.get("upi_id", "")
                        if qr_code_url or upi_id:
                            msg += "📱 Or pay via QR and send screenshot!\n\n"
                            # QR image will be sent when pending screenshot is waiting
                            if qr_code_url:
                                await send_telegram_photo(chat_id, qr_code_url, msg, bot_token, {"inline_keyboard": ticket_buttons} if ticket_buttons else None)
                            else:
                                if upi_id:
                                    msg += f"📱 UPI ID: <code>{upi_id}</code>\n\n"
                                msg += "📸 Screenshot bhejo payment ke baad!"
                                await send_telegram_message_with_buttons(chat_id, msg, ticket_buttons, bot_token) if ticket_buttons else await send_telegram_message(chat_id, msg, bot_token)
                        else:
                            msg += "📸 Pay and send screenshot here!\n\n"
                            msg += "⏳ Waiting for your screenshot..."
                            if ticket_buttons:
                                await send_telegram_message_with_buttons(chat_id, msg, ticket_buttons, bot_token)
                            else:
                                await send_telegram_message(chat_id, msg, bot_token)
            else:
                await send_telegram_message(chat_id, "❌ Session not found.", bot_token)
        
        # Admin GO LIVE callback
        elif callback_data.startswith("admin_golive_"):
            session_id = callback_data.replace("admin_golive_", "")
            session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
            
            if session:
                # Update session to live
                await db.live_sessions.update_one(
                    {"id": session_id},
                    {"$set": {
                        "status": "live",
                        "started_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                # Get channel/group to post
                channel_id = settings.get("telegram_channel_id", "")
                group_id = session.get("group_id") or channel_id
                bot_username = await get_bot_username(bot_token)
                
                # Post to channel/group
                live_msg = "🔴 <b>WE ARE LIVE NOW!</b>\n\n"
                live_msg += f"📺 <b>{session.get('title')}</b>\n\n"
                
                if session.get("superchat_enabled"):
                    live_msg += f"💬 Superchat: /superchat\n"
                    live_msg += f"📢 Min Amount: ₹{int(session.get('superchat_min_amount', 10))}\n\n"
                
                live_msg += "🎉 Join now!"
                
                channel_buttons = [[{
                    "text": "🎫 Get Ticket Now!",
                    "url": f"https://t.me/{bot_username}?start=live_{session_id}"
                }]]
                
                await send_telegram_message_with_buttons(group_id, live_msg, channel_buttons, bot_token)
                
                # Notify all approved ticket holders
                approved_tickets = await db.live_tickets.find({
                    "session_id": session_id,
                    "status": "approved"
                }, {"_id": 0}).to_list(1000)
                
                for ticket in approved_tickets:
                    ticket_msg = "🔴 <b>LIVE STARTED!</b>\n\n"
                    ticket_msg += f"📺 <b>{session.get('title')}</b>\n\n"
                    
                    if session.get("stream_link"):
                        ticket_msg += f"🔗 Join: {session['stream_link']}\n\n"
                    
                    if session.get("superchat_enabled"):
                        ticket_msg += "💬 Send Superchat: /superchat"
                    
                    superchat_buttons = [[{
                        "text": "💬 Send Superchat",
                        "url": f"https://t.me/{bot_username}?start=superchat_{session_id}"
                    }]]
                    
                    await send_telegram_message_with_buttons(ticket.get("telegram_user_id"), ticket_msg, superchat_buttons, bot_token)
                
                # Confirm to admin
                admin_msg = f"✅ <b>LIVE STARTED!</b>\n\n"
                admin_msg += f"📺 {session.get('title')}\n"
                admin_msg += f"🎟 {len(approved_tickets)} ticket holders notified\n\n"
                admin_msg += "Commands:\n"
                admin_msg += "• /endlive - End the session\n"
                admin_msg += "• /superchat - View superchats"
                
                await send_telegram_message(chat_id, admin_msg, bot_token)
            else:
                await send_telegram_message(chat_id, "❌ Session not found.", bot_token)
        
        # Admin END LIVE callback
        elif callback_data.startswith("admin_endlive_"):
            session_id = callback_data.replace("admin_endlive_", "")
            session = await db.live_sessions.find_one({"id": session_id, "status": "live"}, {"_id": 0})
            
            if session:
                # Update session to ended
                await db.live_sessions.update_one(
                    {"id": session_id},
                    {"$set": {
                        "status": "ended",
                        "ended_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                # Calculate stats
                tickets_sold = session.get("tickets_sold", 0)
                superchat_total = await db.live_superchats.aggregate([
                    {"$match": {"session_id": session_id, "status": "approved"}},
                    {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
                ]).to_list(1)
                total_superchat = superchat_total[0]["total"] if superchat_total else 0
                
                # Confirm to admin
                end_msg = "🛑 <b>LIVE ENDED!</b>\n\n"
                end_msg += f"📺 {session.get('title')}\n\n"
                end_msg += f"📊 <b>Stats:</b>\n"
                end_msg += f"   🎟 Tickets Sold: {tickets_sold}\n"
                end_msg += f"   💰 Superchat Revenue: ₹{int(total_superchat)}\n"
                end_msg += f"   💵 Total: ₹{int(session.get('price', 0) * tickets_sold + total_superchat)}"
                
                await send_telegram_message(chat_id, end_msg, bot_token)
            else:
                await send_telegram_message(chat_id, "❌ Session not found or not live.", bot_token)
        
        # ============== LIVE SETUP WIZARD CALLBACKS ==============
        
        # Live Setup - New
        elif callback_data == "live_setup_new":
            msg = "🆕 <b>Setup New Live Stream</b>\n\n"
            msg += "━━━━━━━━━━━━━━━\n"
            msg += "Send me the live details in this format:\n\n"
            msg += "<code>/newlive Title | Price | Time</code>\n\n"
            msg += "<b>Example:</b>\n"
            msg += "<code>/newlive Friday Night Party | 299 | 8:00 PM</code>\n\n"
            msg += "━━━━━━━━━━━━━━━\n"
            msg += "Or use quick setup buttons below:"
            
            buttons = [
                [{"text": "🎉 Free Live (₹0)", "callback_data": "live_quick_free"}],
                [{"text": "💰 Paid Live (₹99)", "callback_data": "live_quick_99"}],
                [{"text": "💎 Premium Live (₹299)", "callback_data": "live_quick_299"}],
                [{"text": "⬅️ Back", "callback_data": "live_menu"}]
            ]
            await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        # Quick Live Setup
        elif callback_data.startswith("live_quick_"):
            price = int(callback_data.replace("live_quick_", "").replace("free", "0"))
            
            # Create session with default values
            session_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            
            # Store pending live setup
            await db.pending_live_setup.update_one(
                {"telegram_user_id": chat_id},
                {"$set": {
                    "telegram_user_id": chat_id,
                    "telegram_username": username,
                    "session_id": session_id,
                    "price": price,
                    "step": "title",
                    "created_at": now.isoformat()
                }},
                upsert=True
            )
            
            price_text = "FREE" if price == 0 else f"₹{price}"
            msg = f"🎬 <b>Quick Live Setup ({price_text})</b>\n\n"
            msg += "What's the title of your live stream?\n\n"
            msg += "<i>Just type the title and send...</i>"
            
            await send_telegram_message(chat_id, msg, bot_token)
        
        # My Scheduled Lives
        elif callback_data == "live_my_scheduled":
            my_sessions = await db.live_sessions.find({
                "status": "scheduled"
            }, {"_id": 0}).sort("scheduled_date", -1).to_list(10)
            
            if not my_sessions:
                msg = "📋 <b>No Scheduled Lives</b>\n\n"
                msg += "You don't have any scheduled live streams.\n"
                msg += "Create one using the Setup option!"
                
                buttons = [[{"text": "🆕 Setup New Live", "callback_data": "live_setup_new"}]]
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
            else:
                msg = "📋 <b>Your Scheduled Lives</b>\n\n"
                buttons = []
                
                for session in my_sessions:
                    msg += f"📺 <b>{session.get('title')}</b>\n"
                    msg += f"   💰 ₹{int(session.get('price', 0))} | 🎟 {session.get('tickets_sold', 0)} sold\n"
                    msg += f"   📅 {session.get('scheduled_date')} {session.get('scheduled_time')}\n\n"
                    
                    buttons.append([
                        {"text": f"⚙️ {session.get('title')[:15]}...", "callback_data": f"live_manage_{session.get('id')}"},
                        {"text": "🔴 GO LIVE", "callback_data": f"admin_golive_{session.get('id')}"}
                    ])
                
                buttons.append([{"text": "⬅️ Back", "callback_data": "live_menu"}])
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        # Live Menu (Back button)
        elif callback_data == "live_menu":
            msg = "📺 <b>Live Stream Manager</b>\n\n"
            msg += "━━━━━━━━━━━━━━━\n"
            msg += "What would you like to do?\n"
            msg += "━━━━━━━━━━━━━━━"
            
            buttons = [
                [{"text": "🆕 Setup New Live", "callback_data": "live_setup_new"}],
                [{"text": "📋 My Scheduled Lives", "callback_data": "live_my_scheduled"}],
                [{"text": "🔴 Go Live Now", "callback_data": "live_go_now"}],
                [{"text": "📊 Live Analytics", "callback_data": "live_analytics"}],
                [{"text": "❌ Close", "callback_data": "cancel_action"}]
            ]
            await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        # Go Live Now - Show scheduled sessions
        elif callback_data == "live_go_now":
            scheduled = await db.live_sessions.find({"status": "scheduled"}, {"_id": 0}).to_list(10)
            
            if not scheduled:
                msg = "📺 <b>No Sessions to Start</b>\n\n"
                msg += "Create a live session first!"
                buttons = [[{"text": "🆕 Setup New Live", "callback_data": "live_setup_new"}]]
            else:
                msg = "🔴 <b>Select Session to Go LIVE</b>\n\n"
                buttons = []
                
                for session in scheduled:
                    buttons.append([{
                        "text": f"🔴 {session.get('title')[:30]} - ₹{int(session.get('price', 0))}",
                        "callback_data": f"admin_golive_{session.get('id')}"
                    }])
                
                buttons.append([{"text": "⬅️ Back", "callback_data": "live_menu"}])
            
            await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        # Live Analytics
        elif callback_data == "live_analytics":
            # Get stats
            total_sessions = await db.live_sessions.count_documents({})
            live_sessions = await db.live_sessions.count_documents({"status": "live"})
            total_tickets = await db.live_tickets.count_documents({})
            
            # Calculate revenue
            revenue_result = await db.live_tickets.aggregate([
                {"$match": {"status": "approved"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
            ]).to_list(1)
            total_revenue = revenue_result[0]["total"] if revenue_result else 0
            
            superchat_result = await db.live_superchats.aggregate([
                {"$match": {"status": "approved"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
            ]).to_list(1)
            total_superchat = superchat_result[0]["total"] if superchat_result else 0
            
            msg = "📊 <b>Live Stream Analytics</b>\n\n"
            msg += "━━━━━━━━━━━━━━━\n"
            msg += f"📺 Total Sessions: <b>{total_sessions}</b>\n"
            msg += f"🔴 Currently Live: <b>{live_sessions}</b>\n"
            msg += f"🎟 Tickets Sold: <b>{total_tickets}</b>\n"
            msg += "━━━━━━━━━━━━━━━\n"
            msg += f"💰 Ticket Revenue: <b>₹{int(total_revenue)}</b>\n"
            msg += f"💬 Superchat Revenue: <b>₹{int(total_superchat)}</b>\n"
            msg += f"📈 <b>Total: ₹{int(total_revenue + total_superchat)}</b>\n"
            msg += "━━━━━━━━━━━━━━━"
            
            buttons = [[{"text": "⬅️ Back", "callback_data": "live_menu"}]]
            await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        # Manage specific live session
        elif callback_data.startswith("live_manage_"):
            session_id = callback_data.replace("live_manage_", "")
            session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
            
            if session:
                msg = f"⚙️ <b>Manage: {session.get('title')}</b>\n\n"
                msg += "━━━━━━━━━━━━━━━\n"
                msg += f"💰 Price: ₹{int(session.get('price', 0))}\n"
                msg += f"🎟 Tickets: {session.get('tickets_sold', 0)}\n"
                msg += f"💬 Superchat: {'✅ ON' if session.get('superchat_enabled') else '❌ OFF'}\n"
                msg += f"📅 Scheduled: {session.get('scheduled_date')} {session.get('scheduled_time')}\n"
                msg += "━━━━━━━━━━━━━━━"
                
                buttons = [
                    [{"text": "🔴 GO LIVE NOW", "callback_data": f"admin_golive_{session_id}"}],
                    [{"text": "📢 Announce", "callback_data": f"live_announce_{session_id}"}],
                    [{"text": "⏰ Start Countdown", "callback_data": f"live_countdown_{session_id}"}],
                    [
                        {"text": "✏️ Edit", "callback_data": f"live_edit_{session_id}"},
                        {"text": "🗑 Delete", "callback_data": f"live_delete_{session_id}"}
                    ],
                    [{"text": "⬅️ Back", "callback_data": "live_my_scheduled"}]
                ]
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
            else:
                await send_telegram_message(chat_id, "❌ Session not found", bot_token)
        
        # Announce live session - Show channel selection menu
        elif callback_data.startswith("live_announce_") and "_to_" not in callback_data and not callback_data.startswith("live_announce_manual_"):
            session_id = callback_data.replace("live_announce_", "")
            session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
            
            if session:
                # Get settings and channels/groups
                settings = await get_bot_settings()
                bot_token = settings.get("telegram_bot_token", "")
                groups = await db.groups.find({"is_active": True}, {"_id": 0}).to_list(50)
                default_channel = settings.get("telegram_channel_id", "")
                
                msg = "📢 <b>Select Channel for Announcement</b>\n\n"
                msg += f"📺 Live: <b>{session.get('title')}</b>\n\n"
                msg += "Choose where to send:"
                
                buttons = []
                
                # Add default channel option
                if default_channel:
                    buttons.append([{"text": "📢 Default Channel", "callback_data": f"live_announce_{session_id}_to_{default_channel}"}])
                
                # Add other groups/channels
                for group in groups[:8]:  # Max 8 groups
                    group_name = group.get("name", group.get("group_id", "Unknown"))[:20]
                    group_id = group.get("group_id", "")
                    if group_id and group_id != default_channel:
                        buttons.append([{"text": f"📣 {group_name}", "callback_data": f"live_announce_{session_id}_to_{group_id}"}])
                
                # Add manual input option
                buttons.append([{"text": "✏️ Enter Channel ID Manually", "callback_data": f"live_announce_manual_{session_id}"}])
                buttons.append([{"text": "❌ Cancel", "callback_data": "cancel"}])
                
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
            else:
                await send_telegram_message(chat_id, "❌ Session not found", bot_token)
        
        # Announce to specific channel
        elif callback_data.startswith("live_announce_") and "_to_" in callback_data:
            parts = callback_data.replace("live_announce_", "").split("_to_")
            session_id = parts[0]
            target_channel = parts[1] if len(parts) > 1 else ""
            
            session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
            
            if session and target_channel:
                bot_username = await get_bot_username(bot_token)
                
                announce_msg = "🔴 <b>LIVE STREAM ANNOUNCEMENT!</b>\n\n"
                announce_msg += f"📺 <b>{session.get('title')}</b>\n\n"
                if session.get('description'):
                    announce_msg += f"📝 {session['description']}\n\n"
                announce_msg += f"📅 <b>Date:</b> {session.get('scheduled_date')}\n"
                announce_msg += f"🕐 <b>Time:</b> {session.get('scheduled_time')}\n"
                announce_msg += f"💰 <b>Ticket:</b> ₹{int(session.get('price', 0))}\n\n"
                announce_msg += "👇 <b>Get Your Ticket Now!</b>"
                
                announce_buttons = [[{
                    "text": f"🎫 Buy Ticket - ₹{int(session.get('price', 0))}",
                    "url": f"https://t.me/{bot_username}?start=live_{session_id}"
                }]]
                
                try:
                    await send_telegram_message_with_buttons(target_channel, announce_msg, announce_buttons, bot_token)
                    await send_telegram_message(chat_id, f"✅ Announcement posted to channel: {target_channel}", bot_token)
                except Exception as e:
                    logger.error(f"Failed to send announcement: {e}")
                    await send_telegram_message(chat_id, f"❌ Failed to send to {target_channel}. Make sure bot is admin in that channel.", bot_token)
            else:
                await send_telegram_message(chat_id, "❌ Session not found or invalid channel", bot_token)
        
        # Manual channel input for announcement
        elif callback_data.startswith("live_announce_manual_"):
            session_id = callback_data.replace("live_announce_manual_", "")
            session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
            
            if session:
                # Store pending action
                await db.pending_actions.update_one(
                    {"user_id": str(chat_id)},
                    {"$set": {
                        "user_id": str(chat_id),
                        "action": "live_announce_channel",
                        "session_id": session_id,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }},
                    upsert=True
                )
                
                msg = "📢 <b>Enter Channel ID</b>\n\n"
                msg += "Send the channel ID (e.g., <code>-1001234567890</code>)\n\n"
                msg += "💡 <b>How to get Channel ID:</b>\n"
                msg += "1. Forward any message from channel to @userinfobot\n"
                msg += "2. Or use @getidsbot in your channel"
                
                await send_telegram_message(chat_id, msg, bot_token)
            else:
                await send_telegram_message(chat_id, "❌ Session not found", bot_token)
        
        # Start countdown
        elif callback_data.startswith("live_countdown_"):
            session_id = callback_data.replace("live_countdown_", "")
            session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
            
            if session:
                channel_id = settings.get("telegram_channel_id", "") 
                group_id = session.get("group_id") or channel_id
                bot_username = await get_bot_username(bot_token)
                
                countdown_msg = "⏰ <b>LIVE STARTING SOON!</b>\n\n"
                countdown_msg += "━━━━━━━━━━━━━━━\n"
                countdown_msg += f"📺 <b>{session.get('title')}</b>\n\n"
                countdown_msg += "🕐 <b>Starting in 30 minutes!</b>\n"
                countdown_msg += "━━━━━━━━━━━━━━━\n\n"
                countdown_msg += f"💰 Ticket: ₹{int(session.get('price', 0))}\n\n"
                countdown_msg += "👇 <b>Get your ticket NOW!</b>"
                
                countdown_buttons = [
                    [{"text": f"🎫 Buy Ticket - ₹{int(session.get('price', 0))}", "url": f"https://t.me/{bot_username}?start=live_{session_id}"}],
                    [{"text": "🔔 Subscribe", "url": f"https://t.me/{bot_username}?start=subscribe"}]
                ]
                
                await send_telegram_message_with_buttons(group_id, countdown_msg, countdown_buttons, bot_token)
                
                await db.live_sessions.update_one(
                    {"id": session_id},
                    {"$set": {"countdown_started": True}}
                )
                
                await send_telegram_message(chat_id, "✅ Countdown posted!", bot_token)
            else:
                await send_telegram_message(chat_id, "❌ Session not found", bot_token)
        
        # Delete live session
        elif callback_data.startswith("live_delete_"):
            session_id = callback_data.replace("live_delete_", "")
            await db.live_sessions.delete_one({"id": session_id})
            await send_telegram_message(chat_id, "✅ Live session deleted!", bot_token)
        
        # Superchat enable/disable in setup
        elif callback_data == "live_superchat_on":
            await db.pending_live_setup.update_one(
                {"telegram_user_id": chat_id},
                {"$set": {"superchat_enabled": True, "step": "superchat_min"}}
            )
            
            msg = "✅ <b>Superchat Enabled!</b>\n\n"
            msg += "What's the minimum superchat amount?\n\n"
            msg += "Choose below or type a custom amount:"
            
            buttons = [
                [
                    {"text": "₹10", "callback_data": "live_scmin_10"},
                    {"text": "₹29", "callback_data": "live_scmin_29"},
                    {"text": "₹49", "callback_data": "live_scmin_49"}
                ],
                [
                    {"text": "₹99", "callback_data": "live_scmin_99"},
                    {"text": "₹199", "callback_data": "live_scmin_199"}
                ]
            ]
            await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        elif callback_data == "live_superchat_off":
            await db.pending_live_setup.update_one(
                {"telegram_user_id": chat_id},
                {"$set": {"superchat_enabled": False, "step": "stream_link"}}
            )
            
            msg = "✅ <b>Superchat Disabled</b>\n\n"
            msg += "Send the stream link (YouTube/Telegram):\n\n"
            msg += "(or type 'skip' if you'll add it later)"
            await send_telegram_message(chat_id, msg, bot_token)
        
        elif callback_data.startswith("live_scmin_"):
            min_amount = int(callback_data.replace("live_scmin_", ""))
            await db.pending_live_setup.update_one(
                {"telegram_user_id": chat_id},
                {"$set": {"superchat_min": min_amount, "step": "stream_link"}}
            )
            
            msg = f"✅ <b>Min Superchat: ₹{min_amount}</b>\n\n"
            msg += "Send the stream link (YouTube/Telegram):\n\n"
            msg += "(or type 'skip' if you'll add it later)"
            await send_telegram_message(chat_id, msg, bot_token)
        

        # Admin panel callback buttons
        elif callback_data == "admin_stats":
            is_admin = await is_admin_or_creator(chat_id, username)
            if not is_admin:
                return {"ok": True}
            
            active_subs = await db.subscribers.count_documents({"status": "active", "tenant_id": bot_tenant_id})
            total_subs = await db.subscribers.count_documents({"tenant_id": bot_tenant_id})
            pending_payments = await db.payments.count_documents({"status": "pending", "tenant_id": bot_tenant_id})
            payments = await db.payments.find({"status": "verified", "tenant_id": bot_tenant_id}, {"_id": 0, "amount": 1}).to_list(100000)
            total_revenue = sum(p.get("amount", 0) for p in payments)
            
            stats_msg = "📊 <b>Quick Stats</b>\n━━━━━━━━━━━━━━━\n"
            stats_msg += f"👥 Active: <b>{active_subs}</b> / {total_subs} total\n"
            stats_msg += f"💳 Pending: <b>{pending_payments}</b>\n"
            stats_msg += f"💰 Revenue: <b>₹{int(total_revenue):,}</b>"
            
            await send_telegram_message(chat_id, stats_msg, bot_token)
        
        elif callback_data == "admin_pending":
            is_admin = await is_admin_or_creator(chat_id, username)
            if not is_admin:
                return {"ok": True}
            
            pending = await db.payments.find({"status": "pending", "tenant_id": bot_tenant_id}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
            if not pending:
                await send_telegram_message(chat_id, "✅ No pending payments!", bot_token)
            else:
                msg = f"💳 <b>Pending ({len(pending)})</b>\n\n"
                for p in pending:
                    msg += f"• <code>{p.get('telegram_user_id','')}</code> - {p.get('plan_name','N/A')} - ₹{p.get('amount',0)}\n"
                msg += "\nVerify from dashboard."
                await send_telegram_message(chat_id, msg, bot_token)
        
        elif callback_data == "admin_broadcast":
            is_admin = await is_admin_or_creator(chat_id, username)
            if not is_admin:
                return {"ok": True}
            
            msg = "📢 <b>Send Broadcast</b>\n\n"
            msg += "To send a broadcast, use:\n"
            msg += "<code>/broadcast Your message here</code>\n\n"
            msg += "This will be sent to ALL bot users."
            await send_telegram_message(chat_id, msg, bot_token)
        

        # Super chat session selection
        elif callback_data.startswith("superchat_select_"):
            session_id = callback_data.replace("superchat_select_", "")
            session = await db.live_sessions.find_one({"id": session_id, "status": "live"}, {"_id": 0})
            
            if session:
                # Ask for amount and message
                await db.pending_screenshots.update_one(
                    {"telegram_user_id": chat_id, "tenant_id": bot_tenant_id},
                    {"$set": {
                        "telegram_user_id": chat_id,
                        "telegram_username": username,
                        "superchat_session_id": session_id,
                        "superchat_session_title": session.get("title", ""),
                        "status": "waiting_superchat_amount",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }},
                    upsert=True
                )
                
                msg = "💬 <b>Super Chat</b>\n\n"
                msg += f"📺 Session: <b>{session.get('title')}</b>\n\n"
                msg += "Choose amount:\n"
                
                buttons = [
                    [{"text": "₹50", "callback_data": "superchat_amount_50"}],
                    [{"text": "₹100", "callback_data": "superchat_amount_100"}],
                    [{"text": "₹200", "callback_data": "superchat_amount_200"}],
                    [{"text": "₹500", "callback_data": "superchat_amount_500"}],
                    [{"text": "❌ Cancel", "callback_data": "cancel_action"}]
                ]
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
            else:
                await send_telegram_message(chat_id, "❌ Session ended or not found.", bot_token)
        
        # Super chat amount selection
        elif callback_data.startswith("superchat_amount_"):
            amount = int(callback_data.replace("superchat_amount_", ""))
            pending = await db.pending_screenshots.find_one({"telegram_user_id": chat_id, "tenant_id": bot_tenant_id}, {"_id": 0})
            
            if pending and pending.get("superchat_session_id"):
                # Update with amount and ask for message
                await db.pending_screenshots.update_one(
                    {"telegram_user_id": chat_id, "tenant_id": bot_tenant_id},
                    {"$set": {
                        "superchat_amount": amount,
                        "status": "waiting_superchat_message"
                    }}
                )
                
                msg = f"💬 <b>Super Chat - ₹{amount}</b>\n\n"
                msg += "📝 Type your message below:\n"
                msg += "(This message will be highlighted during the live stream)"
                
                await send_telegram_message(chat_id, msg, bot_token)
            else:
                await send_telegram_message(chat_id, "❌ Please start again with /superchat", bot_token)
        
        # Answer callback to remove loading state
        try:
            async with httpx.AsyncClient() as http_client:
                await http_client.post(
                    f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery",
                    json={"callback_query_id": callback_query.get("id")}
                )
        except Exception:
            pass
        
        return {"ok": True}

    return {"ok": True}
