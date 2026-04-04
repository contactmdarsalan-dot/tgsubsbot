"""Telegram webhook handler - main bot logic"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from database import db
from services.auth import get_current_user
from services.telegram import (
    get_bot_settings, get_bot_username, send_telegram_message,
    send_telegram_message_with_buttons, send_telegram_message_with_buttons_and_return,
    edit_telegram_message, send_telegram_photo, send_telegram_video,
    delete_telegram_message, download_telegram_photo,
    kick_user_from_channel, add_to_channel, remove_from_channel,
    send_screenshot_reminders, urgency_timer_task,
    is_admin_or_creator, notify_admin_new_payment
)
from services.payment import detect_payment_screenshot, create_blurred_image, analyze_payment_screenshot_with_ai
from services.chat_pool import get_available_chat_group, assign_chat_group
from services.bot_activity import log_bot_activity
from services.tenant import DEFAULT_TENANT_ID, tenant_query
from config import logger, TELEGRAM_CHANNEL_ID, EMERGENT_LLM_KEY
from rate_limiter import limiter
from datetime import datetime, timezone, timedelta
import uuid
import httpx
import os
import asyncio
import json
import re
import base64
from io import BytesIO

router = APIRouter()

@router.post("/telegram/webhook")
@limiter.limit("300/minute")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        
        logger.info(f"Webhook received: {data}")
        
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
        # Resolve tenant for this bot — all data created in this webhook uses this tenant_id
        bot_tenant_id = settings.get("tenant_id") or DEFAULT_TENANT_ID
        
        # Log bot token status for debugging
        if not bot_token:
            logger.error("BOT TOKEN NOT FOUND! Check database settings or TELEGRAM_BOT_TOKEN env var")
        else:
            logger.info(f"Bot token loaded: {bot_token[:10]}...")
        
        promo_channel_id = settings.get("promo_channel_id", "")  # Public promo channel
        telegram_channel_id = settings.get("telegram_channel_id", "")  # Default channel
        
        # Use promo channel if set, otherwise use telegram channel
        target_channel_id = promo_channel_id if promo_channel_id else telegram_channel_id
        
        # Handle channel posts - Add Subscribe button on channel posts OR process paid posts
        channel_post = data.get("channel_post")
        if channel_post and bot_token:
            post_chat_id = str(channel_post.get("chat", {}).get("id", ""))
            message_id = channel_post.get("message_id")
            caption = channel_post.get("caption", "") or channel_post.get("text", "") or ""
            
            # Skip forwarded messages (they can't be edited)
            is_forwarded = channel_post.get("forward_from_chat") or channel_post.get("forward_origin")
            
            # Check if this is a PAID POST (has /paid command in caption)
            # Support formats: /paid, /paid-99, /paid 99, /paid99
            caption_lower = caption.lower()
            is_paid_post = (
                caption_lower.startswith("/paid") or 
                " /paid" in caption_lower or
                caption_lower.startswith("/paid-") or
                caption_lower.startswith("/paid_")
            )
            
            logger.info(f"Channel post - caption: {caption[:50] if caption else 'None'}, is_paid: {is_paid_post}, has_photo: {bool(channel_post.get('photo'))}")
            
            if is_paid_post and message_id and not is_forwarded:
                # Process as a PAID POST
                logger.info(f"Processing PAID POST in channel {post_chat_id}")
                
                # Ensure we have bot token
                if not bot_token:
                    settings = await get_bot_settings()
                    bot_token = settings.get("telegram_bot_token", "")
                    if not bot_token:
                        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
                
                if not bot_token:
                    logger.error("No bot token available for paid post processing")
                    return {"ok": False, "error": "No bot token"}
                
                try:
                    # Import re module explicitly to avoid scope issues
                    import re as re_module
                    
                    # Get content type and file_id FIRST (before deleting)
                    photo = channel_post.get("photo")
                    video = channel_post.get("video")
                    content_type = "photo" if photo else ("video" if video else "text")
                    original_file_id = ""
                    
                    if photo:
                        # Get largest photo
                        original_file_id = photo[-1].get("file_id", "")
                        logger.info(f"Got photo file_id: {original_file_id[:20]}...")
                    elif video:
                        original_file_id = video.get("file_id", "")
                    
                    # Download photo BEFORE deleting original
                    image_bytes = None
                    blurred_bytes = None
                    if photo and original_file_id:
                        logger.info(f"Downloading original photo...")
                        image_bytes = await download_telegram_photo(original_file_id, bot_token)
                        if image_bytes:
                            logger.info(f"Downloaded {len(image_bytes)} bytes, creating blur...")
                            blurred_bytes = create_blurred_image(image_bytes, content_type="photo")
                            if blurred_bytes:
                                logger.info(f"Created blurred image: {len(blurred_bytes)} bytes")
                            else:
                                logger.error("Failed to create blurred image - blurred_bytes is None")
                        else:
                            logger.error("Failed to download original photo - image_bytes is None")
                    
                    # Clean caption (remove /paid command and variations)
                    clean_caption = re_module.sub(r'^/paid[-_]?\s*', '', caption, flags=re_module.IGNORECASE).strip()
                    
                    # Extract price if mentioned (e.g., /paid-999, /paid 99, /paid₹99, 999 at start)
                    price_match = re_module.search(r'^[₹]?(\d+)[-_\s]*', clean_caption)
                    post_price = float(price_match.group(1)) if price_match else 0
                    logger.info(f"Extracted price: {post_price} from caption: {clean_caption[:30]}")
                    
                    # Remove price from caption if found at the beginning
                    if price_match:
                        clean_caption = clean_caption[price_match.end():].strip()
                        # Also remove leading - or _ if present
                        clean_caption = re_module.sub(r'^[-_\s]+', '', clean_caption)
                    
                    # If no price specified, get default from settings or plans
                    if post_price <= 0:
                        settings = await get_bot_settings()
                        post_price = settings.get("default_paid_post_price", 0)
                        if post_price <= 0:
                            plans = await db.plans.find({"is_active": True}, {"_id": 0}).sort("price", 1).to_list(1)
                            if plans:
                                post_price = plans[0].get("price", 99)
                            else:
                                post_price = 99
                    
                    # Create paid post record
                    paid_post_id = str(uuid.uuid4())
                    paid_post = {
                        "id": paid_post_id,
                        "channel_id": post_chat_id,
                        "original_message_id": message_id,
                        "content_type": content_type,
                        "original_file_id": original_file_id,
                        "caption": clean_caption,
                        "price": post_price,
                        "unlock_count": 0,
                        "is_active": True,
                        "tenant_id": bot_tenant_id,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    await db.paid_posts.insert_one(paid_post)
                    logger.info(f"Created paid post record: {paid_post_id} with price {post_price}")
                    
                    # Prepare Unlock button
                    bot_username = await get_bot_username(bot_token)
                    unlock_button = {
                        "inline_keyboard": [[{
                            "text": f"🔓 Unlock Post",
                            "url": f"https://t.me/{bot_username}?start=unlock_{paid_post_id}"
                        }]]
                    }
                    
                    price_text = f"₹{int(post_price)}" if post_price > 0 else "Premium"
                    blur_caption = f"🔒 <b>Paid Content</b>\n\n"
                    blur_caption += f"💰 Price: <b>{price_text}</b>\n\n"
                    # Add original caption if present
                    if clean_caption and clean_caption.strip():
                        blur_caption += f"📝 {clean_caption}\n\n"
                    blur_caption += "👆 Tap 'Unlock Post' to view full content!"
                    
                    # POST BLURRED IMAGE FIRST, THEN DELETE ORIGINAL
                    blurred_posted = False
                    
                    if photo and blurred_bytes:
                        # Send blurred photo
                        logger.info(f"Posting blurred image to channel {post_chat_id}...")
                        result = await send_telegram_photo(post_chat_id, blurred_bytes, blur_caption, bot_token, unlock_button)
                        logger.info(f"Send photo result: {result}")
                        if result and result.get("ok") and result.get("result"):
                            blurred_message_id = result["result"].get("message_id", 0)
                            await db.paid_posts.update_one({"id": paid_post_id}, {"$set": {"blurred_message_id": blurred_message_id}})
                            logger.info(f"Posted blurred image with message_id: {blurred_message_id}")
                            blurred_posted = True
                        else:
                            logger.error(f"Failed to post blurred image: {result}")
                    
                    elif photo and not blurred_bytes:
                        # Photo exists but blur failed - post text message
                        logger.warning("Blurred bytes is None, posting text fallback")
                        fallback_msg = f"🔒 <b>Paid Content</b>\n\n"
                        fallback_msg += f"💰 Price: <b>{price_text}</b>\n\n"
                        fallback_msg += "👆 Tap 'Unlock Post' to view full content!"
                        
                        result = await send_telegram_message_with_buttons(post_chat_id, fallback_msg, [[{
                            "text": f"🔓 Unlock Post",
                            "url": f"https://t.me/{bot_username}?start=unlock_{paid_post_id}"
                        }]], bot_token)
                        if result:
                            blurred_posted = True
                    
                    elif video and original_file_id:
                        # For videos, get thumbnail and blur it, or send video with blur overlay text
                        video_thumb = video.get("thumbnail") or video.get("thumb")
                        
                        if video_thumb:
                            # Download and blur thumbnail
                            thumb_file_id = video_thumb.get("file_id", "")
                            if thumb_file_id:
                                logger.info(f"Downloading video thumbnail...")
                                thumb_bytes = await download_telegram_photo(thumb_file_id, bot_token)
                                if thumb_bytes:
                                    blurred_thumb = create_blurred_image(thumb_bytes, content_type="video")
                                    if blurred_thumb:
                                        video_caption = f"🎬 <b>Paid Video Content</b>\n\n"
                                        video_caption += f"💰 Price: <b>{price_text}</b>\n\n"
                                        # Add caption if present
                                        if clean_caption and clean_caption.strip():
                                            video_caption += f"📝 {clean_caption}\n\n"
                                        video_caption += "👆 Tap 'Unlock Video' to watch!"
                                        
                                        result = await send_telegram_photo(post_chat_id, blurred_thumb, video_caption, bot_token, unlock_button)
                                        if result and result.get("ok"):
                                            blurred_message_id = result.get("result", {}).get("message_id", 0)
                                            await db.paid_posts.update_one({"id": paid_post_id}, {"$set": {"blurred_message_id": blurred_message_id}})
                                            blurred_posted = True
                                            logger.info(f"Posted blurred video thumbnail with message_id: {blurred_message_id}")
                        
                        # Fallback: send text message if thumbnail blur failed
                        if not blurred_posted:
                            video_caption = f"🎬 <b>Paid Video Content</b>\n\n"
                            video_caption += f"💰 Price: <b>{price_text}</b>\n\n"
                            video_caption += "👆 Tap 'Unlock Video' to watch full video!"
                            
                            result = await send_telegram_message_with_buttons(post_chat_id, video_caption, [[{
                                "text": f"🔓 Unlock Video - ₹{int(post_price)}",
                                "url": f"https://t.me/{bot_username}?start=unlock_{paid_post_id}"
                            }]], bot_token)
                            if result:
                                blurred_posted = True
                                logger.info(f"Posted video unlock text message (no thumbnail)")
                    
                    else:
                        # Text-only paid post
                        text_caption = f"🔒 <b>Paid Content</b>\n\n"
                        if clean_caption:
                            text_caption += f"Preview: {clean_caption[:50]}...\n\n"
                        text_caption += f"💰 Price: <b>{price_text}</b>\n\n"
                        text_caption += "👆 Tap 'Unlock Post' to view full content!"
                        
                        result = await send_telegram_message_with_buttons(post_chat_id, text_caption, [[{
                            "text": f"🔓 Unlock Post",
                            "url": f"https://t.me/{bot_username}?start=unlock_{paid_post_id}"
                        }]], bot_token)
                        if result:
                            blurred_posted = True
                    
                    # ONLY delete original if blurred was posted successfully
                    if blurred_posted:
                        delete_result = await delete_telegram_message(post_chat_id, message_id, bot_token)
                        logger.info(f"Deleted original message {message_id}: {delete_result}")
                    else:
                        logger.error("Blurred post failed - NOT deleting original to preserve content")
                    
                except Exception as e:
                    logger.error(f"Error processing paid post: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                
                return {"ok": True, "paid_post": True}
            
            # Regular channel post - Add Subscribe button
            elif message_id and not is_forwarded:
                # Add Subscribe button by editing the message (no delay)
                try:
                    bot_username = await get_bot_username(bot_token)
                    if not bot_username:
                        logger.warning("Could not get bot username for subscribe button")
                    
                    subscribe_button = [[{
                        "text": "🔔 Subscribe Now",
                        "url": f"https://t.me/{bot_username}?start=subscribe"
                    }]]
                    
                    async with httpx.AsyncClient(timeout=10.0) as http_client:
                        # Try to edit message with reply markup
                        url = f"https://api.telegram.org/bot{bot_token}/editMessageReplyMarkup"
                        response = await http_client.post(url, json={
                            "chat_id": post_chat_id,
                            "message_id": message_id,
                            "reply_markup": {"inline_keyboard": subscribe_button}
                        })
                        
                        logger.info(f"Subscribe button edit response: {response.status_code} for channel {post_chat_id}")
                        
                        if response.status_code == 200:
                            logger.info(f"Added subscribe button to channel post: SUCCESS")
                        else:
                            # If edit fails, send a reply message with button
                            logger.info(f"Edit failed ({response.status_code}: {response.text}), sending reply with button")
                            reply_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                            reply_response = await http_client.post(reply_url, json={
                                "chat_id": post_chat_id,
                                "text": "👆 <b>Interested?</b>\n\n🔔 Click below to subscribe!",
                                "parse_mode": "HTML",
                                "reply_to_message_id": message_id,
                                "reply_markup": {"inline_keyboard": subscribe_button}
                            })
                            logger.info(f"Reply message response: {reply_response.status_code}")
                            
                except Exception as e:
                    logger.error(f"Failed to add subscribe button: {e}")
            
            return {"ok": True}
        
        # Handle new channel members - Send welcome message
        chat_member_update = data.get("chat_member")
        if chat_member_update and bot_token:
            chat_id = str(chat_member_update.get("chat", {}).get("id", ""))
            new_member = chat_member_update.get("new_chat_member", {})
            old_member = chat_member_update.get("old_chat_member", {})
            user = new_member.get("user", {})
            user_id = str(user.get("id", ""))
            username = user.get("username", "")
            first_name = user.get("first_name", "")
            
            # Check if user joined (status changed to "member" or "administrator")
            old_status = old_member.get("status", "")
            new_status = new_member.get("status", "")
            
            # Only process if user is joining (not leaving)
            if new_status in ["member", "administrator"] and old_status in ["left", "kicked", ""]:
                logger.info(f"New member {user_id} (@{username}) joined channel {chat_id}")
                
                # Send welcome message with plans directly to user's private chat
                if user_id and not user.get("is_bot"):
                    # Get plans and settings
                    plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
                    settings = await get_bot_settings()
                    website_link = settings.get("website_link", "https://miraclecouplee.syke.club")
                    
                    welcome_msg = f"🎉 <b>Welcome {first_name}!</b>\n\n"
                    welcome_msg += "Thanks for joining our channel! 💕\n\n"
                    welcome_msg += f"🌐 <b>Visit:</b> {website_link}\n\n"
                    welcome_msg += "🔥 <b>Get Exclusive Content!</b>\n"
                    welcome_msg += "Subscribe now for premium access!\n\n"
                    welcome_msg += "━━━━━━━━━━━━━━━\n"
                    welcome_msg += "🎯 <b>Choose Your Plan:</b>\n\n"
                    
                    buttons = []
                    for plan in plans:
                        plan_price = int(plan['price'])
                        welcome_msg += f"📦 <b>{plan['name']}</b> - ₹{plan_price}\n"
                        buttons.append([{"text": f"📦 {plan['name']} - ₹{plan_price}", "callback_data": f"buy_{plan['id']}"}])
                    
                    buttons.append([{"text": "🌐 Visit Website", "url": website_link}])
                    buttons.append([{"text": "🎁 Special Discount!", "callback_data": "special_discount"}])
                    
                    try:
                        await send_telegram_message_with_buttons(user_id, welcome_msg, buttons, bot_token)
                        logger.info(f"Sent welcome message with plans to new member {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to send welcome message: {e}")
            
            return {"ok": True}
        
        # Skip old messages (older than 30 seconds) - but allow callback queries
        callback_query = data.get("callback_query")
        message = data.get("message") or (callback_query.get("message") if callback_query else None)
        
        # Only skip old regular messages, not callback queries (button clicks)
        if message and not callback_query:
            msg_date = message.get("date", 0)
            current_time = int(datetime.now(timezone.utc).timestamp())
            if current_time - msg_date > 30:
                logger.info(f"Skipping old message from {current_time - msg_date}s ago")
                return {"ok": True}
        
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
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                
                if plan:
                    # Check if plan has discount
                    original_price = int(plan['price'])
                    discount_pct = plan.get('discount_percentage', 0)
                    if discount_pct > 0:
                        discounted_price = int(original_price * (100 - discount_pct) / 100)
                        price_display = f"<s>₹{original_price}</s> → <b>₹{discounted_price}</b> 🔥"
                        final_price = discounted_price
                    else:
                        price_display = f"<b>₹{original_price}</b>"
                        final_price = original_price
                    
                    # Show payment options
                    qr_code_url = settings.get("qr_code_url", "")
                    
                    payment_msg = f"🔥 <b>EXCLUSIVE OFFER!</b> 🔥\n\n"
                    payment_msg += f"<b>📦 {plan['name']}</b>\n\n"
                    payment_msg += f"💰 Price: {price_display}\n"
                    payment_msg += f"⏱ Duration: <b>{plan['duration_days']} days</b>\n\n"
                    
                    if plan.get('features'):
                        payment_msg += "<b>Features:</b>\n"
                        for feat in plan['features']:
                            payment_msg += f"✅ {feat}\n"
                        payment_msg += "\n"
                    
                    payment_msg += "⏰ <b>Offer expires in 60 seconds!</b>\n"
                    payment_msg += "━━━━━━━━━━━━━━━\n"
                    payment_msg += "<b>💳 Payment Options:</b>\n\n"
                    payment_msg += "1️⃣ <b>UPI/QR Code:</b>\n"
                    payment_msg += "   Pay via any UPI app\n\n"
                    payment_msg += "2️⃣ After payment, send screenshot to admin\n\n"
                    payment_msg += f"📱 <b>Your User ID:</b> <code>{chat_id}</code>\n"
                    payment_msg += "(Share this with admin after payment)"
                    
                    buttons = []
                    if qr_code_url:
                        buttons.append([{"text": "📱 Show QR Code", "callback_data": f"qr_{plan_id}"}])
                    buttons.append([{"text": "✅ I've Paid - Contact Admin", "callback_data": f"paid_{plan_id}"}])
                    buttons.append([{"text": "◀️ Back to Plans", "callback_data": "back_plans"}])
                    
                    # Send initial message with urgency timer
                    msg_result = await send_telegram_message_with_buttons_and_return(chat_id, payment_msg, buttons, bot_token)
                    
                    if msg_result:
                        # Schedule urgency timer edits in background
                        asyncio.create_task(
                            urgency_timer_task(chat_id, msg_result, plan, price_display, final_price, buttons, bot_token)
                        )
            
            elif callback_data.startswith("qr_"):
                # Send QR code image and wait for screenshot
                plan_id = callback_data.replace("qr_", "")
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                qr_url = settings.get("qr_code_url", "")
                
                logger.info(f"QR Request - plan_id: {plan_id}, plan: {plan}, qr_url: {qr_url[:50] if qr_url else 'EMPTY'}...")
                
                # Calculate discounted price if applicable
                original_price = plan["price"] if plan else 0
                discount_pct = plan.get('discount_percentage', 0) if plan else 0
                if discount_pct > 0:
                    final_price = int(original_price * (100 - discount_pct) / 100)
                    price_display = f"<s>₹{int(original_price)}</s> → ₹{final_price}"
                else:
                    final_price = int(original_price)
                    price_display = f"₹{final_price}"
                
                # Save that we're waiting for screenshot from this user
                await db.pending_screenshots.update_one(
                    {"telegram_user_id": chat_id},
                    {"$set": {
                        "telegram_user_id": chat_id,
                        "telegram_username": username,
                        "plan_id": plan_id,
                        "plan_name": plan["name"] if plan else "",
                        "amount": original_price,
                        "discounted_price": final_price,
                        "discount_percentage": discount_pct,
                        "status": "waiting",
                        "reminder_count": 0,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }},
                    upsert=True
                )
                
                if qr_url:
                    try:
                        logger.info(f"Sending QR to {chat_id}...")
                        # For large payments (₹500+), show UPI ID along with QR
                        upi_id = settings.get("upi_id", "") or settings.get("payment_upi_id", "")
                        
                        caption_text = f"📱 <b>Scan & Pay {price_display}</b>\n\n"
                        caption_text += f"📦 Plan: <b>{plan['name'] if plan else ''}</b>\n\n"
                        
                        if final_price >= 500 and upi_id:
                            caption_text += f"💳 <b>UPI ID:</b> <code>{upi_id}</code>\n"
                            caption_text += f"<i>(Large amount? Pay directly to UPI ID)</i>\n\n"
                        
                        caption_text += f"⚠️ <b>Payment ke baad turant screenshot bhejo!</b>\n\n"
                        caption_text += f"⏳ Waiting for your screenshot..."
                        
                        # Use send_telegram_photo which handles local files properly
                        await send_telegram_photo(chat_id, qr_url, caption_text, bot_token)
                    except Exception as e:
                        logger.error(f"Failed to send QR: {e}")
                        await send_telegram_message(chat_id, f"📸 Screenshot bhejo payment ka!", bot_token)
                else:
                    logger.warning(f"QR URL is empty! Cannot send QR code.")
                
                # Send reminder message
                reminder_msg = f"👆 @{username if username else 'User'}\n\n"
                reminder_msg += "⚠️ <b>Screenshot bhejo payment ka!</b>\n\n"
                reminder_msg += "📸 Bina screenshot ke verification nahi hoga.\n"
                reminder_msg += "⏳ <b>Waiting...</b>"
                
                await send_telegram_message(chat_id, reminder_msg, bot_token)
                
                # Schedule reminders using background task
                background_tasks.add_task(send_screenshot_reminders, chat_id, username, bot_token)
            
            elif callback_data.startswith("razorpay_"):
                # Create Razorpay payment link
                plan_id = callback_data.replace("razorpay_", "")
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                
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
                        await send_telegram_message(chat_id, "❌ Payment error. Please try QR code method.", bot_token)
            
            elif callback_data.startswith("paid_"):
                plan_id = callback_data.replace("paid_", "")
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                
                if plan:
                    # Check if already has pending payment for this plan
                    existing = await db.payments.find_one({
                        "telegram_user_id": chat_id,
                        "plan_id": plan_id,
                        "status": "pending"
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
                plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
                
                welcome_msg = "🎯 <b>Choose Your Plan</b>\n\n"
                buttons = []
                for plan in plans:
                    plan_price = int(plan['price'])
                    welcome_msg += f"📦 <b>{plan['name']}</b>\n"
                    welcome_msg += f"   💰 ₹{plan_price} • ⏱ {plan['duration_days']} days\n\n"
                    buttons.append([{"text": f"📦 {plan['name']} - ₹{plan_price}", "callback_data": f"buy_{plan['id']}"}])
                
                buttons.append([{"text": "📊 Check My Status", "callback_data": "check_status"}])
                await send_telegram_message_with_buttons(chat_id, welcome_msg, buttons, bot_token)
            
            elif callback_data == "cancel_payment":
                # Cancel pending screenshot/payment
                await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                
                msg = "❌ <b>Cancelled!</b>\n\n"
                msg += "Payment process cancel ho gaya.\n\n"
                msg += "Phir se try karne ke liye /start bhejo!"
                
                buttons = [[{"text": "🔄 Start Again", "callback_data": "back_plans"}]]
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
            
            elif callback_data == "special_discount":
                # Show plan-specific discounted prices
                plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
                
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
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                pending = await db.pending_screenshots.find_one({"telegram_user_id": chat_id}, {"_id": 0})
                
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
                    await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                    
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
                    {"telegram_user_id": chat_id},
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
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                
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
                        {"telegram_user_id": chat_id},
                        {"$set": {"discounted_price": discounted_price, "discount_applied": True}}
                    )
                    
                    buttons = [
                        [{"text": "📱 Show QR Code", "callback_data": f"qr_{plan_id}"}],
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
                        plan = await db.plans.find_one({"name": {"$regex": "5.*min.*chat", "$options": "i"}}, {"_id": 0})
                    else:
                        plan = await db.plans.find_one({"name": {"$regex": "30.*min.*chat", "$options": "i"}}, {"_id": 0})
                    
                    if plan:
                        qr_code_url = settings.get("qr_code_url", "")
                        
                        renew_msg = f"🔄 <b>Renew Chat Session</b>\n\n"
                        renew_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                        renew_msg += f"💰 Price: <b>₹{plan['price']}</b>\n\n"
                        renew_msg += "━━━━━━━━━━━━━━━\n"
                        renew_msg += "<b>💳 Payment:</b>\n\n"
                        renew_msg += "1️⃣ Pay via UPI/QR Code\n"
                        renew_msg += "2️⃣ Send screenshot\n"
                        renew_msg += "3️⃣ Get more chat time!\n\n"
                        renew_msg += f"📱 <b>Your User ID:</b> <code>{chat_id}</code>"
                        
                        buttons = []
                        if qr_code_url:
                            buttons.append([{"text": "📱 Show QR Code", "callback_data": f"qr_{plan['id']}"}])
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
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                
                if plan:
                    # Show payment options directly
                    qr_code_url = settings.get("qr_code_url", "")
                    
                    renew_msg = f"🔄 <b>Renew Subscription</b>\n\n"
                    renew_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                    renew_msg += f"💰 Price: <b>₹{plan['price']}</b>\n"
                    renew_msg += f"⏱ Duration: <b>{plan['duration_days']} days</b>\n\n"
                    renew_msg += "━━━━━━━━━━━━━━━\n"
                    renew_msg += "<b>💳 Payment Options:</b>\n\n"
                    renew_msg += "1️⃣ <b>UPI/QR Code:</b> Pay via any UPI app\n"
                    renew_msg += "2️⃣ After payment, click 'I've Paid'\n\n"
                    renew_msg += f"📱 <b>Your User ID:</b> <code>{chat_id}</code>"
                    
                    buttons = []
                    if qr_code_url:
                        buttons.append([{"text": "📱 Show QR Code", "callback_data": f"qr_{plan_id}"}])
                    buttons.append([{"text": "✅ I've Paid", "callback_data": f"paid_{plan_id}"}])
                    buttons.append([{"text": "📦 View Other Plans", "callback_data": "back_plans"}])
                    
                    await send_telegram_message_with_buttons(chat_id, renew_msg, buttons, bot_token)
                else:
                    # Plan not found, show all plans
                    await send_telegram_message(chat_id, "Plan not found. Please choose from available plans:", bot_token)
                    plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
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
                qr_code_url = settings.get("qr_code_url", "")
                
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
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.video_call_bookings.insert_one(booking)
                
                msg = f"📹 <b>Video Call Booking Created!</b>\n\n"
                msg += f"🆔 Booking ID: <code>{booking['id'][:8]}</code>\n"
                msg += f"📅 Date: <b>{selected_date}</b>\n"
                msg += f"🕐 Time: <b>{selected_time}</b>\n"
                msg += f"💰 Amount: <b>₹{price}</b>\n\n"
                msg += "━━━━━━━━━━━━━━━\n"
                msg += "<b>💳 Payment Instructions:</b>\n\n"
                msg += "1️⃣ Pay ₹{} via UPI\n".format(price)
                msg += "2️⃣ Send payment screenshot here\n"
                msg += "3️⃣ Your booking will be confirmed!\n\n"
                msg += f"📱 <b>Your ID:</b> <code>{chat_id}</code>"
                
                buttons = []
                if qr_code_url:
                    buttons.append([{"text": "📱 Show QR Code", "callback_data": f"vc_qr_{booking['id']}"}])
                buttons.append([{"text": "❌ Cancel Booking", "callback_data": f"vc_cancel_{booking['id']}"}])
                
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
            
            elif callback_data.startswith("vc_qr_"):
                # Show QR code for video call payment
                booking_id = callback_data.replace("vc_qr_", "")
                qr_code_url = settings.get("qr_code_url", "")
                
                if qr_code_url:
                    await send_telegram_photo(chat_id, qr_code_url, "📱 Scan this QR code to pay\n\nAfter payment, send screenshot here.", bot_token)
                else:
                    await send_telegram_message(chat_id, "QR Code not configured. Please contact admin.", bot_token)
            
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
                    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
                    
                    if not payment:
                        await send_telegram_message(chat_id, "❌ Payment not found.", bot_token)
                    elif payment.get("status") == "verified":
                        await send_telegram_message(chat_id, "✅ This payment is already verified.", bot_token)
                    else:
                        # Update payment status to verified
                        await db.payments.update_one(
                            {"id": payment_id},
                            {"$set": {
                                "status": "verified",
                                "admin_verified": True,
                                "verified_by": chat_id,
                                "verified_at": datetime.now(timezone.utc).isoformat()
                            }}
                        )
                        
                        user_tg_id = payment.get("telegram_user_id", "")
                        plan_id = payment.get("plan_id", "")
                        plan = await db.plans.find_one({"id": plan_id}, {"_id": 0}) if plan_id else None
                        
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
                    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
                    
                    if not payment:
                        await send_telegram_message(chat_id, "❌ Payment not found.", bot_token)
                    elif payment.get("status") == "rejected":
                        await send_telegram_message(chat_id, "❌ This payment is already rejected.", bot_token)
                    else:
                        was_verified = payment.get("status") == "verified"
                        
                        # Update payment status to rejected
                        await db.payments.update_one(
                            {"id": payment_id},
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
                                {"payment_id": payment_id},
                                {"$set": {"status": "expired"}}
                            )
                            plan_id = payment.get("plan_id", "")
                            plan = await db.plans.find_one({"id": plan_id}, {"_id": 0}) if plan_id else None
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
                subscriber = await db.subscribers.find_one({"telegram_user_id": chat_id}, {"_id": 0})
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
            
            elif callback_data.startswith("unlock_qr_"):
                # Show QR code for paid post unlock
                post_id = callback_data.replace("unlock_qr_", "")
                paid_post = await db.paid_posts.find_one({"id": post_id, "is_active": True}, {"_id": 0})
                
                logger.info(f"unlock_qr_ - post_id: {post_id}, paid_post: {paid_post}")
                
                if paid_post:
                    settings = await get_bot_settings()
                    qr_code_url = settings.get("qr_code_url", "")
                    post_price = paid_post.get("price", 99)
                    
                    logger.info(f"unlock_qr_ - qr_code_url: {qr_code_url[:50] if qr_code_url else 'EMPTY'}...")
                    
                    if qr_code_url:
                        # Save pending unlock request so bot knows to expect screenshot
                        await db.pending_screenshots.update_one(
                            {"telegram_user_id": chat_id},
                            {"$set": {
                                "telegram_user_id": chat_id,
                                "telegram_username": username,
                                "unlock_post_id": post_id,
                                "expected_amount": post_price,
                                "status": "waiting_unlock",
                                "created_at": datetime.now(timezone.utc).isoformat()
                            }},
                            upsert=True
                        )
                        
                        # Get UPI ID for large payments
                        upi_id = settings.get("upi_id", "") or settings.get("payment_upi_id", "")
                        
                        qr_msg = f"📱 <b>Scan & Pay ₹{int(post_price)}</b>\n\n"
                        
                        # Show UPI ID for large amounts (₹500+)
                        if post_price >= 500 and upi_id:
                            qr_msg += f"💳 <b>UPI ID:</b> <code>{upi_id}</code>\n"
                            qr_msg += f"<i>(Large amount? Pay directly to UPI ID)</i>\n\n"
                        
                        qr_msg += "━━━━━━━━━━━━━━━\n"
                        qr_msg += "📸 <b>Payment ke baad:</b>\n"
                        qr_msg += "👉 Payment screenshot yahan bhejo\n"
                        qr_msg += "👉 Auto-verify hoke content unlock ho jayega!\n"
                        qr_msg += "━━━━━━━━━━━━━━━"
                        result = await send_telegram_photo(chat_id, qr_code_url, qr_msg, bot_token)
                        logger.info(f"unlock_qr_ - send_telegram_photo result: {result}")
                    else:
                        logger.warning("unlock_qr_ - QR Code URL is EMPTY!")
                        await send_telegram_message(chat_id, "❌ QR Code not configured. Contact admin.", bot_token)
                else:
                    logger.warning(f"unlock_qr_ - paid_post not found for id: {post_id}")
                    await send_telegram_message(chat_id, "❌ Post not found or expired.", bot_token)
            
            elif callback_data.startswith("unlock_paid_"):
                # User claims to have paid for unlock
                post_id = callback_data.replace("unlock_paid_", "")
                paid_post = await db.paid_posts.find_one({"id": post_id, "is_active": True}, {"_id": 0})
                
                if paid_post:
                    post_price = paid_post.get("price", 99)
                    
                    # Save pending unlock payment
                    await db.pending_screenshots.update_one(
                        {"telegram_user_id": chat_id},
                        {"$set": {
                            "telegram_user_id": chat_id,
                            "telegram_username": username,
                            "unlock_post_id": post_id,
                            "expected_amount": post_price,
                            "status": "waiting_unlock",
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }},
                        upsert=True
                    )
                    
                    verify_msg = "📸 <b>Send Payment Screenshot!</b>\n\n"
                    verify_msg += f"💰 Amount: ₹{int(post_price)}\n\n"
                    verify_msg += "Send your payment screenshot now and I'll verify it automatically! ✅"
                    
                    buttons = [[{"text": "❌ Cancel", "callback_data": "cancel_action"}]]
                    await send_telegram_message_with_buttons(chat_id, verify_msg, buttons, bot_token)
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
                        # Show QR and ask for payment
                        qr_url = settings.get("qr_code_url", "")
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
                            # Paid session - save pending and show QR
                            await db.pending_screenshots.update_one(
                                {"telegram_user_id": chat_id},
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
                            
                            if qr_url:
                                msg = f"🎟 <b>Get Ticket: {session.get('title')}</b>\n\n"
                                msg += f"💰 Price: <b>₹{int(price)}</b>\n\n"
                                msg += "📱 Scan QR code and pay\n"
                                msg += "📸 Then send payment screenshot here!\n\n"
                                msg += "⏳ Waiting for your screenshot..."
                                
                                await send_telegram_photo(chat_id, qr_url, msg, bot_token)
                            else:
                                msg = f"🎟 <b>Get Ticket: {session.get('title')}</b>\n\n"
                                msg += f"💰 Price: <b>₹{int(price)}</b>\n\n"
                                msg += "❌ QR not configured. Contact admin!"
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
                
                active_subs = await db.subscribers.count_documents({"status": "active"})
                total_subs = await db.subscribers.count_documents({})
                pending_payments = await db.payments.count_documents({"status": "pending"})
                payments = await db.payments.find({"status": "verified"}, {"_id": 0, "amount": 1}).to_list(100000)
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
                
                pending = await db.payments.find({"status": "pending"}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
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
                        {"telegram_user_id": chat_id},
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
                pending = await db.pending_screenshots.find_one({"telegram_user_id": chat_id}, {"_id": 0})
                
                if pending and pending.get("superchat_session_id"):
                    # Update with amount and ask for message
                    await db.pending_screenshots.update_one(
                        {"telegram_user_id": chat_id},
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
        
        # Handle regular messages
        message = data.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "")
        username = message.get("from", {}).get("username", "")
        first_name = message.get("from", {}).get("first_name", "")
        photo = message.get("photo")  # Check if message has photo
        video = message.get("video")  # Check if message has video
        caption = message.get("caption", "").lower()  # Get caption if any
        chat_type = message.get("chat", {}).get("type", "private")  # private, group, supergroup
        
        if not chat_id:
            return {"ok": True}
        
        # Log bot activity
        event_type = "command" if text and text.startswith("/") else "message"
        if photo:
            event_type = "payment_screenshot" if chat_type == "private" else "photo"
        asyncio.create_task(log_bot_activity(event_type, chat_id, username, text[:100] if text else event_type))
        
        # Track bot user (upsert)
        if chat_type == "private" and chat_id:
            await db.bot_users.update_one(
                {"user_id": str(chat_id)},
                {"$set": {
                    "user_id": str(chat_id),
                    "username": username or "",
                    "first_name": first_name or "",
                    "telegram_user_id": str(chat_id),
                    "last_seen": datetime.now(timezone.utc).isoformat()
                }, "$setOnInsert": {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "tenant_id": bot_tenant_id,
                }},
                upsert=True
            )
        
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
        
        # ============== CHAT TRACKING ==============
        # Track all user messages (DM + Group) for analytics
        if text or photo or video:
            try:
                # Determine message type
                msg_type = "text"
                if photo:
                    msg_type = "photo"
                elif video:
                    msg_type = "video"
                elif message.get("voice"):
                    msg_type = "voice"
                elif message.get("document"):
                    msg_type = "document"
                
                # Get group info if from group
                group_id = ""
                group_name = ""
                if chat_type in ["group", "supergroup"]:
                    group_id = chat_id
                    group_name = message.get("chat", {}).get("title", "")
                
                # Save chat message (don't save commands starting with /)
                if not (text and text.startswith("/")):
                    chat_record = {
                        "id": str(uuid.uuid4()),
                        "telegram_user_id": str(message.get("from", {}).get("id", chat_id)),
                        "telegram_username": username,
                        "user_first_name": first_name,
                        "chat_type": chat_type,
                        "group_id": group_id,
                        "group_name": group_name,
                        "message_text": text[:500] if text else f"[{msg_type}]",  # Limit text length
                        "message_type": msg_type,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    await db.chat_messages.insert_one(chat_record)
                    logger.info(f"Chat tracked: {username or first_name} in {chat_type}")
            except Exception as e:
                logger.error(f"Error tracking chat: {e}")
        
        # Handle /paid command via PRIVATE MESSAGE (Admin sends photo/video to bot directly)
        # This prevents original from being visible in channel
        if (photo or video) and bot_token and caption:
            import re as re_module
            caption_lower = caption.lower()
            is_paid_command = (
                caption_lower.startswith("/paid") or 
                " /paid" in caption_lower
            )
            
            if is_paid_command:
                logger.info(f"Processing /paid command via private message from {chat_id}")
                
                # Get channel ID from settings
                channel_id = settings.get("telegram_channel_id", "") or os.environ.get("TELEGRAM_CHANNEL_ID", "")
                
                if not channel_id:
                    await send_telegram_message(chat_id, "❌ Channel ID not configured. Please set it in Settings.", bot_token)
                    return {"ok": True}
                
                try:
                    # Determine content type and get file_id
                    content_type = "photo" if photo else "video"
                    original_file_id = ""
                    thumb_bytes = None
                    
                    if photo:
                        original_file_id = photo[-1].get("file_id", "") if photo else ""
                    elif video:
                        original_file_id = video.get("file_id", "")
                        # Get video thumbnail
                        video_thumb = video.get("thumbnail") or video.get("thumb")
                        if video_thumb:
                            thumb_file_id = video_thumb.get("file_id", "")
                            if thumb_file_id:
                                logger.info(f"Downloading video thumbnail...")
                                thumb_bytes = await download_telegram_photo(thumb_file_id, bot_token)
                    
                    if not original_file_id:
                        await send_telegram_message(chat_id, "❌ Could not get file. Please try again.", bot_token)
                        return {"ok": True}
                    
                    # Download and blur the content
                    blurred_bytes = None
                    if photo:
                        logger.info(f"Downloading photo for /paid command...")
                        image_bytes = await download_telegram_photo(original_file_id, bot_token)
                        if image_bytes:
                            logger.info(f"Downloaded {len(image_bytes)} bytes, creating blur...")
                            blurred_bytes = create_blurred_image(image_bytes, content_type="photo")
                    elif video and thumb_bytes:
                        logger.info(f"Creating blur from video thumbnail...")
                        blurred_bytes = create_blurred_image(thumb_bytes, content_type="video")
                    
                    # Clean caption and extract price
                    original_caption = message.get("caption", "")
                    clean_caption = re_module.sub(r'^/paid[-_]?\s*', '', original_caption, flags=re_module.IGNORECASE).strip()
                    
                    price_match = re_module.search(r'^[₹]?(\d+)[-_\s]*', clean_caption)
                    post_price = float(price_match.group(1)) if price_match else 0
                    
                    if price_match:
                        clean_caption = clean_caption[price_match.end():].strip()
                        clean_caption = re_module.sub(r'^[-_\s]+', '', clean_caption)
                    
                    # Default price from settings or plans
                    if post_price <= 0:
                        post_price = settings.get("default_paid_post_price", 0)
                        if post_price <= 0:
                            plans = await db.plans.find({"is_active": True}, {"_id": 0}).sort("price", 1).to_list(1)
                            if plans:
                                post_price = plans[0].get("price", 99)
                            else:
                                post_price = 99
                    
                    logger.info(f"Extracted price: {post_price}")
                    
                    # Create paid post record
                    paid_post_id = str(uuid.uuid4())
                    paid_post = {
                        "id": paid_post_id,
                        "channel_id": channel_id,
                        "original_message_id": None,  # Not from channel
                        "content_type": content_type,
                        "original_file_id": original_file_id,
                        "caption": clean_caption,
                        "price": post_price,
                        "unlock_count": 0,
                        "is_active": True,
                        "tenant_id": bot_tenant_id,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "created_via": "private_message"  # Mark as created via private message
                    }
                    await db.paid_posts.insert_one(paid_post)
                    logger.info(f"Created paid post record: {paid_post_id} with price {post_price}")
                    
                    # Prepare Unlock button
                    bot_username = await get_bot_username(bot_token)
                    price_text = f"₹{int(post_price)}" if post_price > 0 else "Premium"
                    button_text = f"🔓 Unlock {'Video' if content_type == 'video' else 'Post'} - {price_text}"
                    unlock_button = {
                        "inline_keyboard": [[{
                            "text": button_text,
                            "url": f"https://t.me/{bot_username}?start=unlock_{paid_post_id}"
                        }]]
                    }
                    
                    # Post to channel
                    result = None
                    if blurred_bytes:
                        if content_type == "video":
                            blur_caption = f"🎬 <b>Paid Video Content</b>\n\n"
                        else:
                            blur_caption = f"🔒 <b>Paid Content</b>\n\n"
                        blur_caption += f"💰 Price: <b>{price_text}</b>\n\n"
                        # Add original caption if present
                        if clean_caption and clean_caption.strip():
                            blur_caption += f"📝 {clean_caption}\n\n"
                        blur_caption += f"👆 Tap 'Unlock {'Video' if content_type == 'video' else 'Post'}' to view!"
                        
                        logger.info(f"Posting blurred {content_type} to channel {channel_id}...")
                        result = await send_telegram_photo(channel_id, blurred_bytes, blur_caption, bot_token, unlock_button)
                    else:
                        # Fallback: text message for video without thumbnail
                        blur_caption = f"🎬 <b>Paid Video Content</b>\n\n"
                        blur_caption += f"💰 Price: <b>{price_text}</b>\n\n"
                        blur_caption += "👆 Tap 'Unlock Video' to watch!"
                        
                        logger.info(f"Posting text message for video to channel {channel_id}...")
                        result = await send_telegram_message_with_buttons(channel_id, blur_caption, [[{
                            "text": button_text,
                            "url": f"https://t.me/{bot_username}?start=unlock_{paid_post_id}"
                        }]], bot_token)
                        if result:
                            result = {"ok": True, "result": result}
                    
                    if result and result.get("ok"):
                        blurred_message_id = result.get("result", {}).get("message_id", 0)
                        await db.paid_posts.update_one({"id": paid_post_id}, {"$set": {"blurred_message_id": blurred_message_id}})
                        
                        # Confirm to admin
                        success_msg = f"✅ <b>Paid Post Created!</b>\n\n"
                        success_msg += f"📦 Post ID: <code>{paid_post_id[:8]}</code>\n"
                        success_msg += f"💰 Price: ₹{int(post_price)}\n"
                        success_msg += f"📢 Posted to channel!\n\n"
                        success_msg += "🔒 Original image is safe - only blurred version posted!"
                        await send_telegram_message(chat_id, success_msg, bot_token)
                        logger.info(f"Successfully posted blurred image to channel, message_id: {blurred_message_id}")
                    else:
                        await send_telegram_message(chat_id, f"❌ Failed to post to channel. Make sure bot is admin in the channel.\n\nError: {result}", bot_token)
                        logger.error(f"Failed to post to channel: {result}")
                    
                except Exception as e:
                    logger.error(f"Error processing /paid via private message: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    await send_telegram_message(chat_id, f"❌ Error: {str(e)}", bot_token)
                
                return {"ok": True}
        
        # Handle screenshot/photo for payment verification with OCR
        if photo and bot_token:
            # Check if we're waiting for screenshot from this user (for subscription OR unlock OR live ticket OR superchat)
            pending = await db.pending_screenshots.find_one({
                "telegram_user_id": chat_id, 
                "status": {"$in": ["waiting", "waiting_unlock", "waiting_live_ticket", "waiting_superchat_payment"]}
            }, {"_id": 0})
            
            # Handle PAID POST UNLOCK screenshot
            if pending and pending.get("status") == "waiting_unlock":
                post_id = pending.get("unlock_post_id")
                paid_post = await db.paid_posts.find_one({"id": post_id, "is_active": True}, {"_id": 0})
                
                if paid_post:
                    logger.info(f"Processing unlock screenshot for post {post_id} from user {chat_id}")
                    
                    # Send "Analyzing" loading message
                    analyzing_msg = "🔍 <b>Analyzing your screenshot...</b>\n\n"
                    analyzing_msg += "⏳ Please wait, verifying your payment..."
                    await send_telegram_message(chat_id, analyzing_msg, bot_token)
                    
                    photo_file_id = photo[-1]["file_id"] if photo else None
                    image_bytes = await download_telegram_photo(photo_file_id, bot_token)
                    
                    if image_bytes:
                        # Run OCR + AI analysis
                        ocr_result = detect_payment_screenshot(image_bytes)
                        settings = await get_bot_settings()
                        expected_upi = settings.get("payment_upi_id", "")
                        ai_threshold = settings.get("ai_auto_approve_threshold", 85)
                        
                        ai_result = await analyze_payment_screenshot_with_ai(
                            image_bytes,
                            expected_amount=pending.get("expected_amount", 0),
                            expected_upi_id=expected_upi if expected_upi else None
                        )
                        
                        # Decision logic
                        is_valid = False
                        auto_approve = False
                        
                        if ai_result.get("ai_enabled") and ai_result.get("confidence_score", 0) >= 50:
                            is_valid = ai_result.get("is_valid_payment", False)
                            auto_approve = ai_result.get("auto_approve_recommended", False) or (ai_result.get("is_payment_screenshot", False) and ai_result.get("confidence_score", 0) >= 50)
                        else:
                            is_valid = ocr_result.get("is_valid", False)
                        
                        if is_valid and auto_approve:
                            # AUTO UNLOCK - Valid payment!
                            logger.info(f"Auto-unlocking post {post_id} for user {chat_id}")
                            
                            # Save unlock record
                            unlock_record = {
                                "id": str(uuid.uuid4()),
                                "post_id": post_id,
                                "telegram_user_id": chat_id,
                                "telegram_username": username,
                                "payment_id": "auto_verified",
                                "screenshot_file_id": photo_file_id,
                                "ai_result": ai_result,
                                "unlocked_at": datetime.now(timezone.utc).isoformat()
                            }
                            await db.paid_post_unlocks.insert_one(unlock_record)
                            
                            # Update unlock count
                            await db.paid_posts.update_one({"id": post_id}, {"$inc": {"unlock_count": 1}})
                            
                            # Remove pending status
                            await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                            
                            # Send unlocked content
                            success_msg = "✅ <b>Payment Verified!</b>\n\n🔓 Unlocking your content..."
                            await send_telegram_message(chat_id, success_msg, bot_token)
                            
                            if paid_post.get("content_type") == "photo" and paid_post.get("original_file_id"):
                                caption = f"🔓 <b>Unlocked!</b>\n\n{paid_post.get('caption', '')}"
                                await send_telegram_photo(chat_id, paid_post["original_file_id"], caption, bot_token)
                            elif paid_post.get("content_type") == "video" and paid_post.get("original_file_id"):
                                caption = f"🔓 <b>Unlocked Video!</b>\n\n{paid_post.get('caption', '')}"
                                await send_telegram_video(chat_id, paid_post["original_file_id"], caption, bot_token)
                            
                            return {"ok": True}
                        
                        elif is_valid:
                            # Valid but needs admin review
                            pending_msg = "📸 <b>Screenshot Received!</b>\n\n"
                            pending_msg += "⏳ Admin verification pending...\n"
                            pending_msg += "You'll receive the content once verified! ✅"
                            
                            # Save for admin review
                            unlock_request = {
                                "id": str(uuid.uuid4()),
                                "post_id": post_id,
                                "telegram_user_id": chat_id,
                                "telegram_username": username,
                                "screenshot_file_id": photo_file_id,
                                "expected_amount": pending.get("expected_amount", 0),
                                "status": "pending_admin",
                                "ocr_result": ocr_result,
                                "ai_result": ai_result if ai_result.get("ai_enabled") else None,
                                "created_at": datetime.now(timezone.utc).isoformat()
                            }
                            await db.unlock_requests.insert_one(unlock_request)
                            await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                            
                            await send_telegram_message(chat_id, pending_msg, bot_token)
                            return {"ok": True}
                        
                        else:
                            # Invalid screenshot - check AI result for specific reason
                            # AI result is directly in ai_result, not nested
                            is_payment_screenshot = ai_result.get("is_payment_screenshot", True) if ai_result.get("ai_enabled") else True
                            amount_matches = ai_result.get("amount_matches", True) if ai_result.get("ai_enabled") else True
                            upi_matches = ai_result.get("upi_id_matches", True) if ai_result.get("ai_enabled") else True
                            
                            # Get extracted data for amount/upi detection
                            extracted_data = ai_result.get("extracted_data", {}) if ai_result.get("ai_enabled") else {}
                            detected_amount = extracted_data.get("amount", 0)
                            if detected_amount and isinstance(detected_amount, str):
                                # Try to extract number from string like "₹2000" or "2000"
                                import re
                                amount_match = re.search(r'[\d,]+', str(detected_amount).replace(',', ''))
                                detected_amount = float(amount_match.group()) if amount_match else 0
                            detected_upi = extracted_data.get("upi_id", "")
                            
                            logger.info(f"AI Analysis - is_payment: {is_payment_screenshot}, amount_matches: {amount_matches}, upi_matches: {upi_matches}")
                            
                            if not is_payment_screenshot:
                                # Not a payment screenshot - funny message
                                funny_titles = [
                                    "😅 Ye kya bhej diya bhai?",
                                    "🤔 Bhai ye payment screenshot hai?",
                                    "😂 Galat photo bhej di!",
                                    "🙈 Ye toh payment nahi hai!",
                                    "😜 Nice try, but nope!"
                                ]
                                import random
                                title = random.choice(funny_titles)
                                invalid_msg = f"{title}\n\n"
                                invalid_msg += "Payment screenshot chahiye, selfie nahi! 🤳\n\n"
                                invalid_msg += "✅ Valid payment screenshot bhejo jisme dikhe:\n"
                                invalid_msg += "• Payment SUCCESS status\n"
                                invalid_msg += "• Amount\n"
                                invalid_msg += "• UPI Transaction ID"
                            elif amount_matches == False and detected_amount > 0:
                                # Amount mismatch
                                expected = pending.get("expected_amount", 0)
                                invalid_msg = f"💰 <b>Amount Mismatch!</b>\n\n"
                                invalid_msg += f"Expected: ₹{int(expected)}\n"
                                invalid_msg += f"Detected: ₹{int(detected_amount)}\n\n"
                                invalid_msg += "Please pay the correct amount and send screenshot again."
                            elif upi_matches == False and detected_upi:
                                # UPI ID mismatch
                                invalid_msg = f"📱 <b>Wrong UPI ID!</b>\n\n"
                                invalid_msg += f"Payment made to: {detected_upi}\n"
                                invalid_msg += f"Should be paid to: {expected_upi}\n\n"
                                invalid_msg += "Please pay to correct UPI ID and send screenshot again."
                            else:
                                # Generic invalid
                                invalid_msg = "❌ <b>Invalid Screenshot!</b>\n\n"
                                invalid_msg += "Please send a valid payment screenshot showing:\n"
                                invalid_msg += "✅ Payment Success/Completed status\n"
                                invalid_msg += "✅ Amount paid\n\n"
                                invalid_msg += "Try again or contact admin for help."
                            
                            await send_telegram_message(chat_id, invalid_msg, bot_token)
                            return {"ok": True}
                    
                    return {"ok": True}
                else:
                    await send_telegram_message(chat_id, "❌ Post not found or expired.", bot_token)
                    await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                    return {"ok": True}
            
            # Handle LIVE TICKET screenshot
            if pending and pending.get("status") == "waiting_live_ticket":
                session_id = pending.get("live_session_id")
                session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
                
                if session:
                    photo_file_id = photo[-1]["file_id"] if photo else None
                    
                    # Send analyzing message
                    await send_telegram_message(chat_id, "🔍 <b>Analyzing your screenshot...</b>\n\n⏳ AI Verifying payment...", bot_token)
                    
                    ticket_price = pending.get("expected_amount", 0) or session.get("price", 0)
                    ticket_status = "pending"
                    ai_result = {}
                    
                    # Try AI verification if we can download the image
                    try:
                        if photo_file_id:
                            image_bytes = await download_telegram_photo(photo_file_id, bot_token)
                            if image_bytes:
                                expected_upi = settings.get("payment_upi_id") or settings.get("upi_id", "")
                                ai_result = await analyze_payment_screenshot_with_ai(image_bytes, ticket_price, expected_upi)
                                
                                if ai_result.get("auto_approve_recommended"):
                                    ticket_status = "approved"
                    except Exception as e:
                        logger.error(f"AI verification for live ticket failed: {e}")
                    
                    # Create ticket
                    ticket = {
                        "id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "session_title": session.get("title", ""),
                        "telegram_user_id": chat_id,
                        "telegram_username": username,
                        "amount": ticket_price,
                        "screenshot_file_id": photo_file_id,
                        "status": ticket_status,
                        "ai_verification": ai_result if ai_result else None,
                        "tenant_id": session.get("tenant_id", bot_tenant_id),
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    await db.live_tickets.insert_one(ticket)
                    
                    # Clear pending
                    await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                    
                    if ticket_status == "approved":
                        # Auto-approved by AI
                        await db.live_sessions.update_one(
                            {"id": session_id}, {"$inc": {"tickets_sold": 1}}
                        )
                        
                        msg = "✅ <b>Ticket Approved! (AI Verified)</b>\n\n"
                        msg += f"🎟 Session: <b>{session.get('title')}</b>\n"
                        if ai_result.get("confidence_score"):
                            msg += f"🤖 Confidence: {ai_result['confidence_score']}%\n\n"
                        if session.get("stream_link") and session.get("status") == "live":
                            msg += f"🔗 Stream Link: {session['stream_link']}\n\n"
                            msg += "Enjoy the stream!"
                        else:
                            msg += "🔔 Stream link will be sent when we go live!"
                    else:
                        msg = "📸 <b>Screenshot Received!</b>\n\n"
                        msg += f"🎟 Ticket for: <b>{session.get('title')}</b>\n\n"
                        msg += "⏳ Admin will verify your payment and approve your ticket.\n"
                        msg += "You'll receive stream link once approved!"
                    
                    await send_telegram_message(chat_id, msg, bot_token)
                    
                    # Notify admins
                    admin_ids = settings.get("telegram_admin_ids", [])
                    status_emoji = "✅" if ticket_status == "approved" else "⏳"
                    admin_msg = f"{status_emoji} <b>Live Ticket Purchase</b>\n\n"
                    admin_msg += f"Session: {session.get('title', '')}\n"
                    admin_msg += f"User: {chat_id} (@{username})\n"
                    admin_msg += f"Amount: ₹{ticket_price}\n"
                    admin_msg += f"Status: {ticket_status.upper()}\n"
                    if ai_result.get("confidence_score"):
                        admin_msg += f"AI: {ai_result['confidence_score']}% confidence"
                    for aid in admin_ids:
                        try:
                            await send_telegram_message(aid, admin_msg, bot_token)
                        except Exception:
                            pass
                    
                    return {"ok": True}
                else:
                    await send_telegram_message(chat_id, "❌ Session not found or ended.", bot_token)
                    await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                    return {"ok": True}
            
            # Handle SUPER CHAT screenshot
            if pending and pending.get("status") == "waiting_superchat_payment":
                session_id = pending.get("superchat_session_id")
                session = await db.live_sessions.find_one({"id": session_id, "status": "live"}, {"_id": 0})
                
                if session:
                    photo_file_id = photo[-1]["file_id"] if photo else None
                    
                    # Create superchat with pending status
                    superchat = {
                        "id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "session_title": session.get("title", ""),
                        "telegram_user_id": chat_id,
                        "telegram_username": username,
                        "amount": pending.get("superchat_amount", 0),
                        "message": pending.get("superchat_message", ""),
                        "screenshot_file_id": photo_file_id,
                        "status": "pending",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    await db.live_superchats.insert_one(superchat)
                    
                    # Clear pending
                    await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                    
                    msg = "💬 <b>Super Chat Submitted!</b>\n\n"
                    msg += f"💰 Amount: ₹{pending.get('superchat_amount', 0)}\n"
                    msg += f"📝 Message: {pending.get('superchat_message', '')[:50]}...\n\n"
                    msg += "⏳ Admin will verify payment and show your message during the live!"
                    await send_telegram_message(chat_id, msg, bot_token)
                    return {"ok": True}
                else:
                    await send_telegram_message(chat_id, "❌ Live session ended.", bot_token)
                    await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                    return {"ok": True}
            
            # Handle REGULAR SUBSCRIPTION screenshot
            if pending and pending.get("status") == "waiting":
                plan_id = pending.get("plan_id")
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                
                if plan:
                    # Get the photo file_id (largest size)
                    photo_file_id = photo[-1]["file_id"] if photo else None
                    
                    # Send "Analyzing" loading message
                    analyzing_msg = "🔍 <b>Analyzing your screenshot...</b>\n\n"
                    analyzing_msg += "⏳ Please wait, verifying your payment..."
                    await send_telegram_message(chat_id, analyzing_msg, bot_token)
                    
                    # Download and analyze photo with OCR
                    image_bytes = await download_telegram_photo(photo_file_id, bot_token)
                    
                    if image_bytes:
                        # Run OCR detection first (fast)
                        ocr_result = detect_payment_screenshot(image_bytes)
                        logger.info(f"OCR Result for user {chat_id}: {ocr_result}")
                        
                        # Get expected UPI ID from settings
                        settings = await get_bot_settings()
                        expected_upi = settings.get("payment_upi_id", "")
                        ai_threshold = settings.get("ai_auto_approve_threshold", 85)
                        
                        # Use discounted price if available, otherwise original price
                        expected_amount = pending.get("discounted_price") or plan.get('price')
                        logger.info(f"Expected amount for AI: {expected_amount} (discounted: {pending.get('discounted_price')}, original: {plan.get('price')})")
                        
                        # Run AI analysis for better accuracy and fake detection
                        ai_result = await analyze_payment_screenshot_with_ai(
                            image_bytes,
                            expected_amount=expected_amount,
                            expected_upi_id=expected_upi if expected_upi else None
                        )
                        logger.info(f"AI Result for user {chat_id}: {ai_result}")
                        
                        # Decision: Use AI if available and confident, otherwise fall back to OCR
                        is_valid = False
                        auto_approve = False
                        verification_method = "ocr"
                        
                        if ai_result.get("ai_enabled") and ai_result.get("confidence_score", 0) >= 50:
                            # AI is available - use AI decision
                            is_valid = ai_result.get("is_valid_payment", False)
                            # If AI says it's a payment screenshot → auto approve (lenient mode)
                            auto_approve = ai_result.get("auto_approve_recommended", False) or (ai_result.get("is_payment_screenshot", False) and ai_result.get("confidence_score", 0) >= 50)
                            verification_method = "ai_gpt5.2"
                            logger.info(f"Using AI decision: valid={is_valid}, auto_approve={auto_approve}, confidence={ai_result.get('confidence_score')}, threshold={ai_threshold}")
                        else:
                            # Fall back to OCR
                            is_valid = ocr_result.get("is_valid", False)
                            auto_approve = False  # OCR alone should NOT auto-approve - send to admin
                            verification_method = "ocr"
                            logger.info(f"Using OCR decision: valid={is_valid}, auto_approve=False (OCR requires admin review)")
                        
                        if is_valid and auto_approve:
                            # Valid payment screenshot detected - AUTO VERIFY
                            logger.info(f"Valid payment screenshot detected for user {chat_id} via {verification_method}")
                            
                            # Check if user already has active subscription
                            existing_sub = await db.subscribers.find_one({
                                "telegram_user_id": chat_id,
                                "status": "active"
                            }, {"_id": 0})
                            
                            # Get discounted price if available
                            discounted_price = pending.get("discounted_price")
                            final_price = discounted_price if discounted_price else plan['price']
                            
                            if existing_sub:
                                # Extend subscription
                                current_end = datetime.fromisoformat(existing_sub["end_date"]) if isinstance(existing_sub["end_date"], str) else existing_sub["end_date"]
                                new_end = current_end + timedelta(days=plan['duration_days'])
                                
                                await db.subscribers.update_one(
                                    {"telegram_user_id": chat_id},
                                    {"$set": {
                                        "end_date": new_end.isoformat(),
                                        "plan_id": plan_id,
                                        "plan_name": plan['name']
                                    }}
                                )
                            else:
                                # Create new subscriber
                                new_subscriber = {
                                    "id": str(uuid.uuid4()),
                                    "telegram_user_id": chat_id,
                                    "telegram_username": username,
                                    "plan_id": plan_id,
                                    "plan_name": plan['name'],
                                    "status": "active",
                                    "payment_method": "qr_screenshot",
                                    "start_date": datetime.now(timezone.utc).isoformat(),
                                    "end_date": (datetime.now(timezone.utc) + timedelta(days=plan['duration_days'])).isoformat(),
                                    "tenant_id": bot_tenant_id,
                                    "created_at": datetime.now(timezone.utc).isoformat()
                                }
                                await db.subscribers.insert_one(new_subscriber)
                            
                            # Create payment record
                            payment_record = {
                                "id": str(uuid.uuid4()),
                                "telegram_user_id": chat_id,
                                "telegram_username": username,
                                "amount": final_price,
                                "plan_id": plan_id,
                                "plan_name": plan['name'],
                                "payment_method": "qr_screenshot",
                                "screenshot_file_id": photo_file_id,
                                "status": "verified",
                                "verification_method": verification_method,
                                "ocr_verified": ocr_result.get("is_valid", False),
                                "ocr_keywords": ocr_result.get("found_keywords", []),
                                "ai_verified": ai_result.get("is_valid_payment", False) if ai_result.get("ai_enabled") else None,
                                "ai_confidence": ai_result.get("confidence_score") if ai_result.get("ai_enabled") else None,
                                "ai_extracted_data": ai_result.get("extracted_data") if ai_result.get("ai_enabled") else None,
                                "ai_fake_indicators": ai_result.get("fake_indicators", []) if ai_result.get("ai_enabled") else [],
                                "tenant_id": bot_tenant_id,
                                "created_at": datetime.now(timezone.utc).isoformat(),
                                "verified_at": datetime.now(timezone.utc).isoformat()
                            }
                            await db.payments.insert_one(payment_record)
                            
                            # Delete pending screenshot record
                            await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                            
                            # Check if this is a Chat plan (5 Min or 30 Min)
                            plan_name_lower = plan['name'].lower()
                            is_chat_plan = "min chat" in plan_name_lower or "minute chat" in plan_name_lower
                            
                            if is_chat_plan:
                                # Handle time-limited chat plan
                                # Determine duration from plan name
                                if "5" in plan_name_lower:
                                    duration_minutes = 5
                                    plan_type = "5min"
                                elif "30" in plan_name_lower:
                                    duration_minutes = 30
                                    plan_type = "30min"
                                else:
                                    duration_minutes = 5  # default
                                    plan_type = "5min"
                                
                                # Get available group from pool
                                available_group = await get_available_chat_group()
                                
                                if available_group:
                                    # Assign group to user
                                    result = await assign_chat_group(
                                        available_group["group_id"],
                                        chat_id,
                                        username,
                                        plan_type,
                                        duration_minutes
                                    )
                                    
                                    if result.get("success"):
                                        invite_link = result.get("invite_link")
                                        session = result.get("session")
                                        
                                        success_msg = "✅ <b>Payment Verified!</b>\n\n"
                                        success_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                                        success_msg += f"💰 Amount: <b>₹{final_price}</b>\n"
                                        success_msg += f"⏱ Duration: <b>{duration_minutes} minutes</b>\n\n"
                                        success_msg += "🔗 <b>Join the chat now:</b>\n"
                                        success_msg += f"{invite_link}\n\n"
                                        success_msg += f"⚠️ <b>Note:</b> You have {duration_minutes} minutes to chat.\n"
                                        success_msg += "After time ends, you'll need to renew!"
                                        
                                        await send_telegram_message(chat_id, success_msg, bot_token)
                                    else:
                                        # Group assignment failed
                                        error_msg = "✅ <b>Payment Verified!</b>\n\n"
                                        error_msg += "But chat group assignment failed.\n"
                                        error_msg += "Admin will contact you shortly!\n\n"
                                        error_msg += "Your payment is safe."
                                        await send_telegram_message(chat_id, error_msg, bot_token)
                                else:
                                    # No groups available
                                    no_group_msg = "✅ <b>Payment Verified!</b>\n\n"
                                    no_group_msg += "⚠️ All chat slots are currently busy.\n\n"
                                    no_group_msg += "Admin will assign you a chat slot soon!\n"
                                    no_group_msg += "Your payment is recorded."
                                    await send_telegram_message(chat_id, no_group_msg, bot_token)
                                    
                                    # Notify admin (you can customize this)
                                    logger.warning(f"No chat groups available for user {chat_id}")
                            else:
                                # Regular subscription plan
                                success_msg = "✅ <b>Payment Verified Successfully!</b>\n\n"
                                success_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                                success_msg += f"💰 Amount: <b>₹{final_price}</b>\n"
                                success_msg += f"⏱ Duration: <b>{plan['duration_days']} days</b>\n\n"
                                
                                # Check if plan has auto_assign_group enabled
                                if plan.get("auto_assign_group"):
                                    # Auto-assign from groups pool
                                    available_group = await get_available_chat_group()
                                    
                                    if available_group:
                                        # Assign group for plan duration
                                        result = await assign_chat_group(
                                            available_group["group_id"],
                                            chat_id,
                                            username,
                                            f"plan_{plan_id}",
                                            plan['duration_days'] * 24 * 60  # Convert days to minutes
                                        )
                                        
                                        if result.get("success"):
                                            invite_link = result.get("invite_link")
                                            success_msg += f"👥 <b>Group Access:</b>\n{invite_link}\n\n"
                                            logger.info(f"Auto-assigned group {available_group['group_id']} to user {chat_id}")
                                        else:
                                            logger.warning(f"Failed to assign group to user {chat_id}")
                                    else:
                                        logger.warning(f"No groups available for auto-assign, user {chat_id}")
                                elif plan.get("group_id"):
                                    # Manual group ID specified - create invite link
                                    try:
                                        async with httpx.AsyncClient() as http_client:
                                            url = f"https://api.telegram.org/bot{bot_token}/createChatInviteLink"
                                            response = await http_client.post(url, json={
                                                "chat_id": plan["group_id"],
                                                "member_limit": 1,
                                                "expire_date": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp())
                                            })
                                            if response.status_code == 200:
                                                invite_link = response.json().get("result", {}).get("invite_link", "")
                                                if invite_link:
                                                    success_msg += f"👥 <b>Group Access:</b>\n{invite_link}\n\n"
                                    except Exception as e:
                                        logger.error(f"Error creating group invite: {e}")
                                
                                success_msg += "🎉 <b>Your subscription is now active!</b>"
                                
                                await send_telegram_message(chat_id, success_msg, bot_token)
                                
                                # Add user to premium channel (plan-specific or default)
                                plan_channel = plan.get("channel_id", "")
                                await add_to_channel(chat_id, plan_channel, plan['name'], use_default=True)
                                
                                # Notify admin about new payment
                                await notify_admin_new_payment(
                                    chat_id, username, plan['name'], final_price,
                                    screenshot_file_id=photo_file_id,
                                    payment_id=payment_record["id"],
                                    payment_status="verified"
                                )
                            
                        else:
                            # AI/OCR couldn't auto-verify - check if AI explicitly rejected
                            
                            # If AI detected FAKE indicators or invalid payment, REJECT immediately
                            ai_fake_indicators = ai_result.get("fake_indicators", [])
                            ai_is_valid = ai_result.get("is_valid_payment", True)
                            ai_reason = ai_result.get("reason", "")
                            ai_extracted = ai_result.get("extracted_data", {})
                            amount_matches = ai_result.get("amount_matches", True)
                            upi_matches = ai_result.get("upi_matches", True)
                            
                            if ai_result.get("ai_enabled") and (not ai_is_valid or len(ai_fake_indicators) > 0):
                                # AI REJECTED the payment - show specific funny rejection message
                                logger.info(f"AI REJECTED payment for user {chat_id}: {ai_reason}")
                                
                                extracted_amount = ai_extracted.get("amount", "")
                                extracted_upi = ai_extracted.get("upi_id", "")
                                # Use discounted price if available
                                expected_amount = pending.get("discounted_price") or plan.get('price', 0)
                                
                                # Determine rejection reason and give funny message
                                if not amount_matches and not upi_matches:
                                    # Both wrong
                                    reject_msg = "🤦 <b>Bhai ye kya kar diya!</b>\n\n"
                                    reject_msg += f"❌ Amount galat: Tune {extracted_amount} bheja, plan ki price <b>₹{int(expected_amount)}</b> hai\n"
                                    reject_msg += f"❌ UPI bhi galat: Tune <code>{extracted_upi}</code> pe bheja\n"
                                    if expected_upi:
                                        reject_msg += f"✅ Sahi UPI: <code>{expected_upi}</code>\n\n"
                                    reject_msg += "😅 Dobara try kar bhai, is baar dhyan se!"
                                    
                                elif not amount_matches:
                                    # Amount wrong
                                    try:
                                        paid_amount = int(''.join(filter(str.isdigit, str(extracted_amount))))
                                    except:
                                        paid_amount = 0
                                    
                                    if paid_amount > expected_amount:
                                        reject_msg = f"😮 <b>Arre bhai, zyada bhej diya!</b>\n\n"
                                        reject_msg += f"Plan price: <b>₹{int(expected_amount)}</b>\n"
                                        reject_msg += f"Tune bheja: <b>{extracted_amount}</b>\n\n"
                                        reject_msg += "🤑 Extra paisa wapas chahiye to admin se baat kar!"
                                    else:
                                        reject_msg = f"😬 <b>Bhai thoda kam pad gaya!</b>\n\n"
                                        reject_msg += f"Plan price: <b>₹{int(expected_amount)}</b>\n"
                                        reject_msg += f"Tune bheja: <b>{extracted_amount}</b>\n\n"
                                        reject_msg += "💸 Poora amount bhejo phir milega access!"
                                
                                elif not upi_matches:
                                    # UPI wrong
                                    reject_msg = f"😱 <b>Galat account mein bhej diya bhai!</b>\n\n"
                                    reject_msg += f"Tune bheja: <code>{extracted_upi}</code>\n"
                                    if expected_upi:
                                        reject_msg += f"✅ Sahi UPI: <code>{expected_upi}</code>\n\n"
                                    reject_msg += "🙏 Admin se contact kar, shayad refund mil jaye!"
                                
                                elif ai_fake_indicators:
                                    # Fake screenshot detected
                                    reject_msg = "🚨 <b>Bhai ye fake lag raha hai!</b>\n\n"
                                    reject_msg += f"⚠️ Issues: {', '.join(ai_fake_indicators[:3])}\n\n"
                                    reject_msg += "😏 Dekhna hai to dena to hoga bhai!\n"
                                    reject_msg += "Asli payment screenshot bhejo! 💯"
                                
                                else:
                                    # Generic rejection
                                    reject_msg = "❌ <b>Payment verify nahi ho paya!</b>\n\n"
                                    if ai_reason:
                                        reject_msg += f"📋 Reason: {ai_reason}\n\n"
                                    reject_msg += "😅 Valid payment screenshot bhejo bhai!"
                                
                                # Delete pending record
                                await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                                
                                await send_telegram_message(chat_id, reject_msg, bot_token)
                            
                            # Check if AI says this is NOT a payment screenshot at all (selfie, meme, random photo)
                            elif ai_result.get("ai_enabled") and ai_result.get("is_payment_screenshot") == False:
                                # AI detected it's NOT a payment screenshot
                                import random
                                funny_titles = [
                                    "😅 Ye kya bhej diya bhai?",
                                    "🤔 Bhai ye payment screenshot hai?",
                                    "😂 Galat photo bhej di!",
                                    "🙈 Ye toh payment nahi hai!",
                                    "😜 Nice try, but nope!"
                                ]
                                title = random.choice(funny_titles)
                                funny_msg = f"{title}\n\n"
                                funny_msg += "Payment screenshot chahiye, selfie nahi! 🤳\n\n"
                                funny_msg += "✅ Valid payment screenshot bhejo jisme dikhe:\n"
                                funny_msg += "• Payment SUCCESS status\n"
                                funny_msg += "• Amount\n"
                                funny_msg += "• UPI Transaction ID"
                                
                                await send_telegram_message(chat_id, funny_msg, bot_token)
                            
                            # Check if this is NOT a payment screenshot at all using OCR (selfie, car, random photo)
                            elif not ai_result.get("ai_enabled") and len(ocr_result.get("found_keywords", [])) < 2:
                                # OCR found almost nothing - likely not a payment screenshot
                                import random
                                funny_messages = [
                                    "😏 <b>Bhai dekhna hai to dena to hoga!</b>\n\nYe payment screenshot nahi lag raha...",
                                    "🤨 <b>Ye kya bhej diya bhai?</b>\n\nPayment screenshot chahiye, selfie nahi! 📸",
                                    "😅 <b>Are bhai, payment ka screenshot bhejo!</b>\n\nYe to kuch aur hi hai...",
                                    "🙄 <b>Nice try!</b>\n\nBut humein payment proof chahiye, ye nahi! 💸",
                                    "😂 <b>Seedha payment karo na bhai!</b>\n\nYe photo se kaam nahi chalega..."
                                ]
                                funny_msg = random.choice(funny_messages)
                                funny_msg += "\n\n✅ Valid payment screenshot bhejo jisme dikhe:\n"
                                funny_msg += "• Payment SUCCESS status\n"
                                funny_msg += "• Amount\n"
                                funny_msg += "• UPI Transaction ID"
                                
                                await send_telegram_message(chat_id, funny_msg, bot_token)
                            
                            else:
                                # OCR-only or AI couldn't decide - send to admin review
                                logger.info(f"Auto-verification couldn't confirm payment for user {chat_id}, showing manual confirmation")
                                
                                # Save photo file_id and AI analysis for admin review
                                await db.pending_screenshots.update_one(
                                    {"telegram_user_id": chat_id},
                                    {"$set": {
                                        "status": "confirming",
                                        "photo_file_id": photo_file_id,
                                        "ocr_result": ocr_result,
                                        "ai_result": {
                                            "enabled": ai_result.get("ai_enabled", False),
                                            "is_valid": ai_result.get("is_valid_payment"),
                                            "confidence": ai_result.get("confidence_score"),
                                            "extracted_data": ai_result.get("extracted_data"),
                                            "fake_indicators": ai_result.get("fake_indicators", []),
                                            "reason": ai_result.get("reason")
                                        } if ai_result.get("ai_enabled") else None
                                    }}
                                )
                                
                                # NO MANUAL CONFIRMATION BUTTONS - Direct admin review
                                # Security: User can't self-approve anymore
                                pending_msg = "📸 <b>Screenshot Received!</b>\n\n"
                                pending_msg += "⏳ <b>Admin verification pending...</b>\n\n"
                                
                                if ai_result.get("ai_enabled") and ai_result.get("confidence_score"):
                                    pending_msg += f"🤖 AI Confidence: <b>{ai_result.get('confidence_score')}%</b>\n"
                                    if ai_result.get("fake_indicators"):
                                        pending_msg += f"⚠️ Concerns: {', '.join(ai_result.get('fake_indicators', [])[:2])}\n"
                                
                                pending_msg += "\n📋 Your payment screenshot has been submitted for review.\n"
                                pending_msg += "✅ You'll be notified once verified!\n\n"
                                pending_msg += "⏱ Usually takes a few minutes."
                                
                                # Save for admin dashboard review
                                payment_pending = {
                                    "id": str(uuid.uuid4()),
                                    "telegram_user_id": chat_id,
                                    "telegram_username": username,
                                    "amount": plan.get('price'),
                                    "plan_id": plan_id,
                                    "plan_name": plan['name'],
                                    "payment_method": "qr_screenshot",
                                    "screenshot_file_id": photo_file_id,
                                    "status": "pending",
                                    "ocr_result": ocr_result,
                                    "ai_result": ai_result if ai_result.get("ai_enabled") else None,
                                    "tenant_id": bot_tenant_id,
                                    "created_at": datetime.now(timezone.utc).isoformat()
                                }
                                await db.payments.insert_one(payment_pending)
                                
                                # Notify admin with Approve/Reject buttons
                                await notify_admin_new_payment(
                                    chat_id, username, plan['name'], plan.get('price', 0),
                                    screenshot_file_id=photo_file_id,
                                    payment_id=payment_pending["id"],
                                    payment_status="pending"
                                )
                                
                                await send_telegram_message(chat_id, pending_msg, bot_token)
                    else:
                        # Could not download image - save for admin review
                        logger.error(f"Could not download image for user {chat_id}")
                        
                        payment_pending = {
                            "id": str(uuid.uuid4()),
                            "telegram_user_id": chat_id,
                            "telegram_username": username,
                            "amount": plan.get('price'),
                            "plan_id": plan_id,
                            "plan_name": plan['name'],
                            "payment_method": "qr_screenshot",
                            "screenshot_file_id": photo_file_id,
                            "status": "pending",
                            "tenant_id": bot_tenant_id,
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                        await db.payments.insert_one(payment_pending)
                        
                        # Notify admin with Approve/Reject buttons
                        await notify_admin_new_payment(
                            chat_id, username, plan['name'], plan.get('price', 0),
                            screenshot_file_id=photo_file_id,
                            payment_id=payment_pending["id"],
                            payment_status="pending"
                        )
                        
                        fallback_msg = "📸 <b>Screenshot Received!</b>\n\n"
                        fallback_msg += "⏳ <b>Admin verification pending...</b>\n\n"
                        fallback_msg += "📋 Your payment screenshot has been submitted for review.\n"
                        fallback_msg += "✅ You'll be notified once verified!"
                        
                        await send_telegram_message(chat_id, fallback_msg, bot_token)
                    
                    return {"ok": True}
            else:
                # User sent image but we're not waiting for it
                msg = "❌ <b>Screenshot not expected!</b>\n\n"
                msg += "Pehle plan select karo, phir QR code se payment karo, phir screenshot bhejo.\n\n"
                msg += "/start se shuru karo!"
                await send_telegram_message(chat_id, msg, bot_token)
                return {"ok": True}
        
        # Handle /start unlock_{post_id} - Unlock paid post
        if text and text.startswith("/start unlock_"):
            post_id = text.replace("/start unlock_", "").strip()
            logger.info(f"User {chat_id} trying to unlock paid post: {post_id}")
            
            # Find the paid post
            paid_post = await db.paid_posts.find_one({"id": post_id, "is_active": True}, {"_id": 0})
            
            if not paid_post:
                await send_telegram_message(chat_id, "❌ <b>Post not found!</b>\n\nThis paid content may have been removed or expired.", bot_token)
                return {"ok": True}
            
            # Check if user already unlocked this post
            existing_unlock = await db.paid_post_unlocks.find_one({
                "post_id": post_id,
                "telegram_user_id": chat_id
            }, {"_id": 0})
            
            if existing_unlock:
                # User already unlocked - send content again
                logger.info(f"User {chat_id} already unlocked post {post_id}, resending content")
                
                if paid_post.get("content_type") == "photo" and paid_post.get("original_file_id"):
                    caption = f"🔓 <b>Unlocked Content</b>\n\n{paid_post.get('caption', '')}"
                    await send_telegram_photo(chat_id, paid_post["original_file_id"], caption, bot_token)
                elif paid_post.get("content_type") == "video" and paid_post.get("original_file_id"):
                    caption = f"🔓 <b>Unlocked Video</b>\n\n{paid_post.get('caption', '')}"
                    await send_telegram_video(chat_id, paid_post["original_file_id"], caption, bot_token)
                else:
                    await send_telegram_message(chat_id, f"🔓 <b>Unlocked Content</b>\n\n{paid_post.get('caption', 'Content already unlocked!')}", bot_token)
                
                return {"ok": True}
            
            # Everyone must pay for paid posts - no free unlock for subscribers
            # Show payment options
            post_price = paid_post.get("price", 0)
            settings = await get_bot_settings()
            qr_code_url = settings.get("qr_code_url", "")
            
            # If no specific price, use default from plans
            if post_price <= 0:
                plans = await db.plans.find({"is_active": True}, {"_id": 0}).sort("price", 1).to_list(1)
                if plans:
                    post_price = plans[0].get("price", 99)
                else:
                    post_price = 99
            
            unlock_msg = f"🔒 <b>Paid Content</b>\n\n"
            unlock_msg += f"💰 Price: <b>₹{int(post_price)}</b>\n\n"
            unlock_msg += "━━━━━━━━━━━━━━━\n"
            unlock_msg += "<b>💳 Payment Options:</b>\n\n"
            unlock_msg += "1️⃣ Pay via UPI/QR Code\n"
            unlock_msg += "2️⃣ Send payment screenshot here\n"
            unlock_msg += "3️⃣ Get content instantly!\n\n"
            unlock_msg += "OR subscribe for unlimited access! 👇"
            
            buttons = []
            if qr_code_url:
                buttons.append([{"text": "📱 Show QR Code", "callback_data": f"unlock_qr_{post_id}"}])
            buttons.append([{"text": "✅ I've Paid - Verify", "callback_data": f"unlock_paid_{post_id}"}])
            buttons.append([{"text": "📦 Get Full Subscription", "callback_data": "back_plans"}])
            
            await send_telegram_message_with_buttons(chat_id, unlock_msg, buttons, bot_token)
            
            # Save pending unlock request
            await db.pending_screenshots.update_one(
                {"telegram_user_id": chat_id},
                {"$set": {
                    "telegram_user_id": chat_id,
                    "telegram_username": username,
                    "unlock_post_id": post_id,
                    "expected_amount": post_price,
                    "status": "waiting_unlock",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
            
            return {"ok": True}
        
        # Check for pending actions (like manual channel input for live announce)
        if text and not text.startswith("/"):
            pending_action = await db.pending_actions.find_one({"user_id": str(chat_id)}, {"_id": 0})
            
            if pending_action and pending_action.get("action") == "live_announce_channel":
                session_id = pending_action.get("session_id")
                target_channel = text.strip()
                
                # Delete pending action
                await db.pending_actions.delete_one({"user_id": str(chat_id)})
                
                # Validate channel ID format
                if not target_channel.startswith("-"):
                    await send_telegram_message(chat_id, "❌ Invalid channel ID. Channel IDs start with '-' (e.g., -1001234567890)", bot_token)
                    return {"ok": True}
                
                session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
                
                if session:
                    settings = await get_bot_settings()
                    bot_token = settings.get("telegram_bot_token", "")
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
                    await send_telegram_message(chat_id, "❌ Session not found", bot_token)
                
                return {"ok": True}
        
        if text == "/start" or text == "/start subscribe" or text == "/plans" or (text and text.startswith("/start buy_")):
            # Check for /start buy_{plan_id} deep link (from promote button)
            if text and text.startswith("/start buy_"):
                plan_id = text.replace("/start buy_", "").strip()
                plan = await db.plans.find_one({"id": plan_id, "is_active": True}, {"_id": 0})
                if plan:
                    # Simulate buy callback
                    settings = await get_bot_settings()
                    bot_token = settings.get("telegram_bot_token", "")
                    original_price = int(plan['price'])
                    discount_pct = plan.get('discount_percentage', 0)
                    if discount_pct > 0:
                        discounted_price = int(original_price * (100 - discount_pct) / 100)
                        price_display = f"<s>₹{original_price}</s> → <b>₹{discounted_price}</b> 🔥"
                        final_price = discounted_price
                    else:
                        price_display = f"<b>₹{original_price}</b>"
                        final_price = original_price
                    
                    qr_code_url = settings.get("qr_code_url", "")
                    
                    payment_msg = f"🔥 <b>EXCLUSIVE OFFER!</b> 🔥\n\n"
                    payment_msg += f"<b>📦 {plan['name']}</b>\n\n"
                    payment_msg += f"💰 Price: {price_display}\n"
                    payment_msg += f"⏱ Duration: <b>{plan['duration_days']} days</b>\n\n"
                    
                    if plan.get('features'):
                        for feat in plan['features']:
                            payment_msg += f"✅ {feat}\n"
                        payment_msg += "\n"
                    
                    payment_msg += "⏰ <b>Offer expires in 60 seconds!</b>\n"
                    payment_msg += "━━━━━━━━━━━━━━━\n"
                    payment_msg += "<b>💳 Pay now to get instant access!</b>\n\n"
                    payment_msg += f"📱 <b>Your User ID:</b> <code>{chat_id}</code>"
                    
                    buttons = []
                    if qr_code_url:
                        buttons.append([{"text": "📱 Show QR Code", "callback_data": f"qr_{plan_id}"}])
                    buttons.append([{"text": "✅ I've Paid - Contact Admin", "callback_data": f"paid_{plan_id}"}])
                    buttons.append([{"text": "◀️ Back to Plans", "callback_data": "back_plans"}])
                    
                    msg_result = await send_telegram_message_with_buttons_and_return(chat_id, payment_msg, buttons, bot_token)
                    if msg_result:
                        asyncio.create_task(urgency_timer_task(chat_id, msg_result, plan, price_display, final_price, buttons, bot_token))
                    return {"ok": True}
            
            # Show plans directly - fetch from database dynamically
            try:
                plans_query = {"is_active": True, "tenant_id": bot_tenant_id}
                plans = await db.plans.find(plans_query, {"_id": 0}).to_list(10)
                # Fallback: if no tenant-specific plans, try without tenant filter
                if not plans:
                    plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
                
                settings = await get_bot_settings()
                website_link = settings.get("website_link", "https://miraclecouplee.syke.club")
                
                welcome_msg = "🎉 <b>Welcome!</b>\n\n"
                welcome_msg += "🔥 <b>Exclusive Content Awaits!</b>\n\n"
                welcome_msg += f"🌐 <b>Visit:</b> {website_link}\n\n"
                welcome_msg += "━━━━━━━━━━━━━━━\n"
                welcome_msg += "🎯 <b>Choose Your Plan:</b>\n\n"
                
                buttons = []
                for plan in plans:
                    plan_price = plan.get('price', 0)
                    plan_name = plan.get('name', 'Plan')
                    plan_days = plan.get('duration_days', 30)
                    plan_id = plan.get('id', '')
                    if not plan_id:
                        continue
                    welcome_msg += f"📦 <b>{plan_name}</b>\n"
                    welcome_msg += f"   💰 ₹{int(plan_price)} • ⏱ {plan_days} days\n\n"
                    buttons.append([{"text": f"📦 {plan_name} - ₹{int(plan_price)}", "callback_data": f"buy_{plan_id}"}])
                
                if not plans:
                    welcome_msg += "No plans available at the moment.\n"
                
                buttons.append([{"text": "🌐 Visit Website", "url": website_link}])
                buttons.append([{"text": "🎁 Special Discount For You!", "callback_data": "special_discount"}])
                buttons.append([{"text": "📊 Check My Status", "callback_data": "check_status"}])
                
                result = await send_telegram_message_with_buttons(chat_id, welcome_msg, buttons, bot_token)
                if not result:
                    logger.error(f"/start failed to send welcome message to {chat_id}, bot_token present: {bool(bot_token)}")
            except Exception as start_err:
                logger.error(f"/start handler error for {chat_id}: {start_err}")
                import traceback
                logger.error(traceback.format_exc())
                await send_telegram_message(chat_id, "🎉 Welcome! Use /plans to see available plans.", bot_token)
        
        elif text == "/status":
            subscriber = await db.subscribers.find_one({"telegram_user_id": chat_id}, {"_id": 0})
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
            
            buttons = [[{"text": "📦 View Plans", "callback_data": "back_plans"}]]
            await send_telegram_message_with_buttons(chat_id, status_msg, buttons, bot_token)
        
        elif text == "/help":
            help_msg = "🤖 <b>Bot Commands</b>\n\n"
            help_msg += "/start - View subscription plans\n"
            help_msg += "/status - Check your subscription\n"
            help_msg += "/live - View & join live sessions\n"
            help_msg += "/superchat - Send super chat during live\n"
            help_msg += "/videocall - Book a video call\n"
            help_msg += "/share - Get shareable message\n"
            help_msg += "/help - Show this help message\n\n"
            help_msg += "💬 You can also ask me any questions!"
            await send_telegram_message(chat_id, help_msg, bot_token)
        
        # Handle /admin command - show admin panel for authorized users
        elif text == "/admin":
            is_admin = await is_admin_or_creator(chat_id, username)
            
            if not is_admin:
                await send_telegram_message(chat_id, "❌ You don't have admin access. Contact the bot owner to get admin permissions.", bot_token)
                return {"ok": True}
            
            # Get admin's permissions
            tg_admin = await db.telegram_admins.find_one({"telegram_user_id": str(chat_id), "is_active": True}, {"_id": 0})
            creator = await db.creators.find_one({"telegram_user_id": str(chat_id), "is_active": True}, {"_id": 0})
            
            permissions = []
            role = "Admin"
            if tg_admin:
                permissions = tg_admin.get("permissions", [])
                role = tg_admin.get("role", "admin").title()
            elif creator:
                permissions = creator.get("permissions", [])
                role = "Creator"
            else:
                permissions = ["manage_bot", "verify_payments", "broadcast", "live_manage", "superchat_view", "add_subscribers"]
                role = "Super Admin"
            
            # Get quick stats
            active_subs = await db.subscribers.count_documents({"status": "active"})
            pending_payments = await db.payments.count_documents({"status": "pending"})
            total_revenue = 0
            payments = await db.payments.find({"status": "verified"}, {"_id": 0, "amount": 1}).to_list(100000)
            total_revenue = sum(p.get("amount", 0) for p in payments)
            
            admin_msg = f"👑 <b>Admin Panel</b>\n"
            admin_msg += f"━━━━━━━━━━━━━━━\n"
            admin_msg += f"🔑 Role: <b>{role}</b>\n\n"
            
            admin_msg += f"📊 <b>Quick Stats:</b>\n"
            admin_msg += f"  👥 Active Subscribers: <b>{active_subs}</b>\n"
            admin_msg += f"  💳 Pending Payments: <b>{pending_payments}</b>\n"
            admin_msg += f"  💰 Total Revenue: <b>₹{int(total_revenue):,}</b>\n\n"
            
            admin_msg += "🛠 <b>Admin Commands:</b>\n"
            
            if "manage_bot" in permissions or role == "Super Admin":
                admin_msg += "/stats - Detailed bot statistics\n"
                admin_msg += "/users - List recent bot users\n"
            
            if "verify_payments" in permissions or role == "Super Admin":
                admin_msg += "/pending - View pending payments\n"
            
            if "broadcast" in permissions or role == "Super Admin":
                admin_msg += "/broadcast <message> - Send to all users\n"
            
            if "live_manage" in permissions or role == "Super Admin":
                admin_msg += "/newlive - Create new live session\n"
                admin_msg += "/endlive - End current live session\n"
            
            if "add_subscribers" in permissions or role == "Super Admin":
                admin_msg += "/adduser <user_id> <plan_id> - Add subscriber\n"
            
            admin_msg += "\n💡 <i>Use the dashboard for full management</i>"
            
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            buttons = [
                [{"text": "📊 View Stats", "callback_data": "admin_stats"}],
                [{"text": "💳 Pending Payments", "callback_data": "admin_pending"}],
                [{"text": "📢 New Broadcast", "callback_data": "admin_broadcast"}],
            ]
            
            await send_telegram_message_with_buttons(chat_id, admin_msg, buttons, bot_token)
        
        # Handle /stats command for admins
        elif text == "/stats":
            is_admin = await is_admin_or_creator(chat_id, username)
            if not is_admin:
                await send_telegram_message(chat_id, "❌ Admin access required.", bot_token)
                return {"ok": True}
            
            total_subs = await db.subscribers.count_documents({})
            active_subs = await db.subscribers.count_documents({"status": "active"})
            expired_subs = await db.subscribers.count_documents({"status": "expired"})
            grace_subs = await db.subscribers.count_documents({"status": "grace"})
            pending_payments = await db.payments.count_documents({"status": "pending"})
            verified_payments = await db.payments.count_documents({"status": "verified"})
            payments = await db.payments.find({"status": "verified"}, {"_id": 0, "amount": 1}).to_list(100000)
            total_revenue = sum(p.get("amount", 0) for p in payments)
            total_plans = await db.plans.count_documents({"is_active": True})
            
            stats_msg = "📊 <b>Bot Statistics</b>\n"
            stats_msg += "━━━━━━━━━━━━━━━\n\n"
            stats_msg += f"👥 <b>Subscribers:</b>\n"
            stats_msg += f"  Total: <b>{total_subs}</b>\n"
            stats_msg += f"  Active: <b>{active_subs}</b> 🟢\n"
            stats_msg += f"  Grace: <b>{grace_subs}</b> 🟡\n"
            stats_msg += f"  Expired: <b>{expired_subs}</b> 🔴\n\n"
            stats_msg += f"💳 <b>Payments:</b>\n"
            stats_msg += f"  Verified: <b>{verified_payments}</b>\n"
            stats_msg += f"  Pending: <b>{pending_payments}</b>\n\n"
            stats_msg += f"💰 <b>Revenue: ₹{int(total_revenue):,}</b>\n"
            stats_msg += f"📦 <b>Active Plans: {total_plans}</b>"
            
            await send_telegram_message(chat_id, stats_msg, bot_token)
        
        # Handle /pending command for admins
        elif text == "/pending":
            is_admin = await is_admin_or_creator(chat_id, username)
            if not is_admin:
                await send_telegram_message(chat_id, "❌ Admin access required.", bot_token)
                return {"ok": True}
            
            pending = await db.payments.find({"status": "pending"}, {"_id": 0}).sort("created_at", -1).limit(10).to_list(10)
            
            if not pending:
                await send_telegram_message(chat_id, "✅ No pending payments!", bot_token)
                return {"ok": True}
            
            msg = f"💳 <b>Pending Payments ({len(pending)})</b>\n━━━━━━━━━━━━━━━\n\n"
            for p in pending:
                msg += f"👤 User: <code>{p.get('telegram_user_id', '')}</code>\n"
                msg += f"📦 Plan: {p.get('plan_name', p.get('plan_id', 'N/A'))}\n"
                msg += f"💰 Amount: ₹{p.get('amount', 0)}\n"
                msg += f"🕐 {str(p.get('created_at', ''))[:16]}\n\n"
            
            msg += "Use the dashboard to verify payments."
            await send_telegram_message(chat_id, msg, bot_token)
        
        # Handle /broadcast command for admins
        elif text and text.startswith("/broadcast "):
            is_admin = await is_admin_or_creator(chat_id, username)
            if not is_admin:
                await send_telegram_message(chat_id, "❌ Admin access required.", bot_token)
                return {"ok": True}
            
            broadcast_text = text.replace("/broadcast ", "", 1).strip()
            if not broadcast_text:
                await send_telegram_message(chat_id, "Usage: /broadcast Your message here", bot_token)
                return {"ok": True}
            
            # Get all bot users
            bot_users = await db.bot_users.find({}, {"_id": 0, "user_id": 1}).to_list(100000)
            user_ids = [u.get("user_id", "") for u in bot_users if u.get("user_id")]
            
            settings = await get_bot_settings()
            bot_token_val = settings.get("telegram_bot_token", "")
            
            sent = 0
            failed = 0
            for uid in user_ids:
                try:
                    result = await send_telegram_message(uid, broadcast_text, bot_token_val)
                    if result:
                        sent += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
                await asyncio.sleep(0.05)
            
            await send_telegram_message(chat_id, f"📢 Broadcast sent!\n✅ Delivered: {sent}\n❌ Failed: {failed}", bot_token_val)
        
        # Handle /users command for admins
        elif text == "/users":
            is_admin = await is_admin_or_creator(chat_id, username)
            if not is_admin:
                await send_telegram_message(chat_id, "❌ Admin access required.", bot_token)
                return {"ok": True}
            
            recent_users = await db.bot_users.find({}, {"_id": 0}).sort("last_seen", -1).limit(10).to_list(10)
            
            if not recent_users:
                await send_telegram_message(chat_id, "No users found.", bot_token)
                return {"ok": True}
            
            msg = f"👥 <b>Recent Users ({len(recent_users)})</b>\n━━━━━━━━━━━━━━━\n\n"
            for u in recent_users:
                msg += f"• @{u.get('username', '')} (<code>{u.get('user_id', '')}</code>)"
                if u.get('first_name'):
                    msg += f" - {u['first_name']}"
                msg += "\n"
            
            await send_telegram_message(chat_id, msg, bot_token)
        
        # Handle /plan command - share specific plan
        elif text.startswith("/plan"):
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            bot_username = await get_bot_username(bot_token)
            
            # Extract plan name from command (e.g., /plan monthly, /plan-monthly, /plan_weekly)
            plan_query = text.replace("/plan", "").replace("-", " ").replace("_", " ").strip().lower()
            
            plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(20)
            
            if not plan_query:
                # Show list of available plans to share
                plan_list_msg = "📋 <b>Share Specific Plan</b>\n\n"
                plan_list_msg += "Use command like:\n"
                for plan in plans:
                    plan_cmd = plan['name'].lower().replace(" ", "_")
                    plan_list_msg += f"• <code>/plan {plan_cmd}</code>\n"
                plan_list_msg += "\n<i>Example: /plan monthly_membership</i>"
                await send_telegram_message(chat_id, plan_list_msg, bot_token)
            else:
                # Find matching plan
                matched_plan = None
                for plan in plans:
                    plan_name_lower = plan['name'].lower()
                    if plan_query in plan_name_lower or plan_name_lower.startswith(plan_query):
                        matched_plan = plan
                        break
                
                if matched_plan:
                    # Create shareable message for this specific plan
                    plan_msg = f"🔥 <b>{matched_plan['name']}</b> 🔥\n\n"
                    plan_msg += "━━━━━━━━━━━━━━━\n"
                    plan_msg += f"💰 <b>Price:</b> ₹{matched_plan['price']}\n"
                    plan_msg += f"⏱ <b>Duration:</b> {matched_plan['duration_days']} days\n\n"
                    
                    if matched_plan.get('features'):
                        plan_msg += "<b>Features:</b>\n"
                        for feat in matched_plan['features']:
                            plan_msg += f"✅ {feat}\n"
                        plan_msg += "\n"
                    
                    plan_msg += "━━━━━━━━━━━━━━━\n"
                    plan_msg += "👇 <b>Click to Subscribe Now!</b>"
                    
                    buttons = [[{
                        "text": f"🚀 Get {matched_plan['name']}",
                        "url": f"https://t.me/{bot_username}?start=buy_{matched_plan['id']}"
                    }]]
                    
                    await send_telegram_message_with_buttons(chat_id, plan_msg, buttons, bot_token)
                    await send_telegram_message(chat_id, "👆 Forward this to share this specific plan!", bot_token)
                else:
                    await send_telegram_message(chat_id, f"❌ Plan not found: {plan_query}\n\nUse /plan to see available options.", bot_token)
        
        elif text == "/share":
            # Get bot username
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            bot_username = ""
            
            try:
                async with httpx.AsyncClient() as http_client:
                    me_response = await http_client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
                    if me_response.status_code == 200:
                        bot_username = me_response.json().get("result", {}).get("username", "")
            except Exception:
                pass
            
            plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
            
            share_msg = "🔥 <b>Premium Subscription Service</b> 🔥\n\n"
            share_msg += "━━━━━━━━━━━━━━━━━━━\n"
            share_msg += "📦 <b>Available Plans:</b>\n\n"
            
            for plan in plans:
                share_msg += f"✨ <b>{plan['name']}</b> - ₹{plan['price']}\n"
                share_msg += f"   ⏱ {plan['duration_days']} days\n"
                if plan.get('features'):
                    for feat in plan['features'][:2]:
                        share_msg += f"   ✅ {feat}\n"
                share_msg += "\n"
            
            share_msg += "━━━━━━━━━━━━━━━━━━━\n"
            share_msg += "👇 <b>Click below to subscribe!</b>"
            
            # Create inline button with bot link
            buttons = []
            if bot_username:
                buttons.append([{"text": "🚀 Subscribe Now", "url": f"https://t.me/{bot_username}?start=subscribe"}])
            buttons.append([{"text": "📞 Contact Admin", "url": f"https://t.me/{bot_username}"}])
            
            await send_telegram_message_with_buttons(chat_id, share_msg, buttons, bot_token)
            
            # Also send instruction
            await send_telegram_message(chat_id, "👆 Forward this message to your groups!\n\nThe buttons will work for everyone.", bot_token)
        
        # Handle /videocall command
        elif text == "/videocall":
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            if not settings.get("video_call_enabled", True):
                await send_telegram_message(chat_id, "❌ Video calls are currently not available.", bot_token)
            else:
                price = settings.get("video_call_price", 500)
                duration = settings.get("video_call_duration", 30)
                instructions = settings.get("video_call_instructions", "📹 Book a 1-on-1 video call with us!")
                
                msg = f"📹 <b>Video Call Booking</b>\n\n"
                msg += f"{instructions}\n\n"
                msg += f"💰 <b>Price:</b> ₹{price}\n"
                msg += f"⏱ <b>Duration:</b> {duration} minutes\n\n"
                msg += "👇 Click below to book your video call:"
                
                buttons = [
                    [{"text": "📅 Book Video Call", "callback_data": "book_videocall"}],
                    [{"text": "❌ Cancel", "callback_data": "cancel_action"}]
                ]
                
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        # Handle /live command
        elif text and text.startswith("/live"):
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            # Get upcoming/live sessions
            live_sessions = await db.live_sessions.find({
                "status": {"$in": ["scheduled", "live"]}
            }, {"_id": 0}).sort("scheduled_date", 1).to_list(10)
            
            if not live_sessions:
                await send_telegram_message(chat_id, "📺 <b>No Live Sessions</b>\n\nNo live sessions scheduled at the moment. Check back later!", bot_token)
            else:
                msg = "🔴 <b>Live Sessions</b>\n\n"
                buttons = []
                
                for session in live_sessions:
                    status_emoji = "🔴 LIVE NOW" if session.get("status") == "live" else "📅 Upcoming"
                    msg += f"<b>{session.get('title')}</b>\n"
                    msg += f"   {status_emoji}\n"
                    msg += f"   📅 {session.get('scheduled_date')} at {session.get('scheduled_time')}\n"
                    msg += f"   💰 ₹{int(session.get('price', 0))}\n\n"
                    
                    buttons.append([{
                        "text": f"🎟 Get Ticket - {session.get('title')[:20]}... ₹{int(session.get('price', 0))}",
                        "callback_data": f"live_ticket_{session.get('id')}"
                    }])
                
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        # Handle /endlive command - End live session
        elif text and text.startswith("/endlive"):
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            # Get currently live sessions
            live_sessions = await db.live_sessions.find({"status": "live"}, {"_id": 0}).to_list(10)
            
            if not live_sessions:
                await send_telegram_message(chat_id, "📺 No live sessions currently running.", bot_token)
            else:
                msg = "🛑 <b>End Live Session</b>\n\n"
                buttons = []
                
                for session in live_sessions:
                    msg += f"🔴 <b>{session.get('title')}</b>\n"
                    msg += f"   🎟 {session.get('tickets_sold', 0)} tickets | 💰 ₹{session.get('superchat_total', 0)} superchats\n\n"
                    
                    buttons.append([{
                        "text": f"🛑 END - {session.get('title')[:25]}...",
                        "callback_data": f"admin_endlive_{session.get('id')}"
                    }])
                
                buttons.append([{"text": "❌ Cancel", "callback_data": "cancel_action"}])
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        # Handle /live command - Complete Live Stream Setup Wizard
        elif text and (text == "/live" or text.startswith("/livestream")):
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            # Check if user is admin or creator
            has_access = await is_admin_or_creator(chat_id, username)
            
            if not has_access:
                await send_telegram_message(chat_id, "❌ <b>Access Denied</b>\n\nOnly admins and creators can manage live streams.", bot_token)
            else:
                # Show Live Stream Menu
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
        
        # Handle /newlive command - Quick one-liner live setup
        elif text and text.startswith("/newlive"):
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            # Check if user is admin or creator
            has_access = await is_admin_or_creator(chat_id, username)
            
            if not has_access:
                await send_telegram_message(chat_id, "❌ <b>Access Denied</b>\n\nOnly admins and creators can create live streams.", bot_token)
            else:
                # Parse: /newlive Title | Price | Time
                parts = text.replace("/newlive", "").strip()
                
                if not parts or "|" not in parts:
                    msg = "📺 <b>Quick Live Setup</b>\n\n"
                    msg += "Format: <code>/newlive Title | Price | Time</code>\n\n"
                    msg += "<b>Examples:</b>\n"
                    msg += "• <code>/newlive Friday Party | 99 | 8PM</code>\n"
                    msg += "• <code>/newlive Free Q&A | 0 | Now</code>\n"
                    msg += "• <code>/newlive Premium Show | 499 | 10PM</code>"
                    await send_telegram_message(chat_id, msg, bot_token)
                else:
                    try:
                        split_parts = [p.strip() for p in parts.split("|")]
                        title = split_parts[0] if len(split_parts) > 0 else "Live Stream"
                        price = int(split_parts[1]) if len(split_parts) > 1 and split_parts[1].isdigit() else 0
                        time = split_parts[2] if len(split_parts) > 2 else "Now"
                        
                        # Create session
                        now = datetime.now(timezone.utc)
                        session_id = str(uuid.uuid4())
                        session = {
                            "id": session_id,
                            "title": title,
                            "description": "",
                            "scheduled_date": now.strftime("%Y-%m-%d"),
                            "scheduled_time": time,
                            "price": price,
                            "max_viewers": 100,
                            "stream_link": "",
                            "superchat_enabled": True,
                            "superchat_min_amount": 10,
                            "status": "scheduled",
                            "tickets_sold": 0,
                            "created_by": username or chat_id,
                            "tenant_id": bot_tenant_id,
                            "created_at": now.isoformat()
                        }
                        await db.live_sessions.insert_one(session)
                        
                        price_text = "FREE" if price == 0 else f"₹{price}"
                        msg = "🎉 <b>Live Created!</b>\n\n"
                        msg += f"📺 <b>{title}</b>\n"
                        msg += f"💰 {price_text} | 🕐 {time}\n"
                        msg += "💬 Superchat: ✅ ON\n\n"
                        msg += "What's next?"
                        
                        buttons = [
                            [{"text": "🔴 GO LIVE NOW", "callback_data": f"admin_golive_{session_id}"}],
                            [{"text": "📢 Announce", "callback_data": f"live_announce_{session_id}"}],
                            [{"text": "⚙️ Manage", "callback_data": f"live_manage_{session_id}"}]
                        ]
                        await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
                        
                    except Exception as e:
                        logger.error(f"Error creating quick live: {e}")
                        await send_telegram_message(chat_id, "❌ Error. Use format: /newlive Title | Price | Time", bot_token)
        
        # Handle /golive command - Admin/Creator starts live from Telegram
        elif text and text.startswith("/golive"):
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            # Check if user is admin or creator
            has_access = await is_admin_or_creator(chat_id, username)
            
            # Also check settings for admin user IDs
            admin_ids = settings.get("admin_user_ids", [])
            if chat_id in admin_ids or username in admin_ids:
                has_access = True
            
            if not has_access:
                await send_telegram_message(chat_id, "❌ <b>Access Denied</b>\n\nOnly admins and creators can start live sessions.\n\nContact admin to get creator access.", bot_token)
            else:
                # Get scheduled sessions that can be started
                scheduled_sessions = await db.live_sessions.find({
                    "status": "scheduled"
                }, {"_id": 0}).sort("scheduled_date", 1).to_list(10)
                
                if not scheduled_sessions:
                    msg = "📺 <b>No Sessions to Start</b>\n\n"
                    msg += "Create a live session from the dashboard first.\n\n"
                    msg += "Or use: /createlive <title> <price>"
                    await send_telegram_message(chat_id, msg, bot_token)
                else:
                    msg = "🔴 <b>Start Live Session</b>\n\n"
                    msg += "Select a session to go LIVE:\n\n"
                    
                    buttons = []
                    for session in scheduled_sessions:
                        msg += f"📺 <b>{session.get('title')}</b>\n"
                        msg += f"   📅 {session.get('scheduled_date')} at {session.get('scheduled_time')}\n"
                        msg += f"   🎟 {session.get('tickets_sold', 0)} tickets sold\n\n"
                        
                        buttons.append([{
                            "text": f"🔴 GO LIVE - {session.get('title')[:25]}...",
                            "callback_data": f"admin_golive_{session.get('id')}"
                        }])
                    
                    buttons.append([{"text": "❌ Cancel", "callback_data": "cancel_action"}])
                    await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        # Handle /createlive command - Quick create live session from Telegram
        elif text and text.startswith("/createlive"):
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            # Parse command: /createlive Title Here 499
            parts = text.replace("/createlive", "").strip()
            
            if not parts:
                msg = "📺 <b>Create Live Session</b>\n\n"
                msg += "Usage: <code>/createlive Title Here 499</code>\n\n"
                msg += "Example: <code>/createlive Friday Night Party 299</code>"
                await send_telegram_message(chat_id, msg, bot_token)
            else:
                # Extract price (last number) and title (rest)
                import re as re_module
                price_match = re_module.search(r'(\d+)\s*$', parts)
                price = int(price_match.group(1)) if price_match else 99
                title = re_module.sub(r'\d+\s*$', '', parts).strip() or "Live Session"
                
                # Create session
                session_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc)
                session = {
                    "id": session_id,
                    "title": title,
                    "description": "",
                    "scheduled_date": now.strftime("%Y-%m-%d"),
                    "scheduled_time": now.strftime("%H:%M"),
                    "price": price,
                    "max_viewers": 100,
                    "stream_link": "",
                    "superchat_enabled": True,
                    "superchat_min_amount": 10,
                    "status": "scheduled",
                    "tickets_sold": 0,
                    "tenant_id": bot_tenant_id,
                    "created_at": now.isoformat(),
                    "created_by": username or chat_id
                }
                await db.live_sessions.insert_one(session)
                
                msg = "✅ <b>Live Session Created!</b>\n\n"
                msg += f"📺 <b>{title}</b>\n"
                msg += f"💰 Price: ₹{price}\n\n"
                msg += "Use /golive to start the session!"
                
                buttons = [[{
                    "text": "🔴 GO LIVE NOW",
                    "callback_data": f"admin_golive_{session_id}"
                }]]
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        # Handle /superchat command
        elif text and text.startswith("/superchat"):
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            # Get currently live sessions
            live_now = await db.live_sessions.find({
                "status": "live"
            }, {"_id": 0}).to_list(10)
            
            if not live_now:
                await send_telegram_message(chat_id, "💬 <b>Super Chat</b>\n\nNo live sessions are active right now.\nSuper chats are only available during live streams!", bot_token)
            else:
                msg = "💬 <b>Super Chat</b>\n\n"
                msg += "Send a highlighted message during the live stream!\n\n"
                msg += "Select a live session to send super chat:\n\n"
                
                buttons = []
                for session in live_now:
                    buttons.append([{
                        "text": f"💬 {session.get('title')[:30]}...",
                        "callback_data": f"superchat_select_{session.get('id')}"
                    }])
                
                buttons.append([{"text": "❌ Cancel", "callback_data": "cancel_action"}])
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        # Handle text messages for superchat flow
        elif text and not text.startswith("/"):
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            # ============== LIVE SETUP WIZARD - Text Input Handlers ==============
            # Check if user is in live setup flow
            pending_live = await db.pending_live_setup.find_one({
                "telegram_user_id": chat_id
            }, {"_id": 0})
            
            if pending_live:
                step = pending_live.get("step", "")
                session_data = pending_live
                
                if step == "title":
                    # Got title, ask for description
                    await db.pending_live_setup.update_one(
                        {"telegram_user_id": chat_id},
                        {"$set": {"title": text, "step": "description"}}
                    )
                    
                    msg = "✅ <b>Title Set!</b>\n\n"
                    msg += f"📺 Title: <b>{text}</b>\n\n"
                    msg += "Now send a short description (or type 'skip'):"
                    await send_telegram_message(chat_id, msg, bot_token)
                
                elif step == "description":
                    # Got description, ask for time
                    desc = "" if text.lower() == "skip" else text
                    await db.pending_live_setup.update_one(
                        {"telegram_user_id": chat_id},
                        {"$set": {"description": desc, "step": "time"}}
                    )
                    
                    msg = "✅ <b>Description Set!</b>\n\n"
                    msg += "When will you go live?\n\n"
                    msg += "Send time like: <code>8:00 PM</code> or <code>Today 9PM</code>\n"
                    msg += "(or type 'now' to go live immediately)"
                    await send_telegram_message(chat_id, msg, bot_token)
                
                elif step == "time":
                    # Got time, ask for superchat settings
                    await db.pending_live_setup.update_one(
                        {"telegram_user_id": chat_id},
                        {"$set": {"scheduled_time": text, "step": "superchat"}}
                    )
                    
                    msg = "✅ <b>Time Set!</b>\n\n"
                    msg += "Enable Superchat for this live?\n"
                    msg += "(Viewers can pay to highlight their messages)"
                    
                    buttons = [
                        [
                            {"text": "✅ Enable Superchat", "callback_data": "live_superchat_on"},
                            {"text": "❌ Disable", "callback_data": "live_superchat_off"}
                        ]
                    ]
                    await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
                
                elif step == "stream_link":
                    # Got stream link, create the session
                    stream_link = "" if text.lower() == "skip" else text
                    
                    # Create the live session
                    now = datetime.now(timezone.utc)
                    session = {
                        "id": session_data.get("session_id", str(uuid.uuid4())),
                        "title": session_data.get("title", "Live Stream"),
                        "description": session_data.get("description", ""),
                        "scheduled_date": now.strftime("%Y-%m-%d"),
                        "scheduled_time": session_data.get("scheduled_time", "Now"),
                        "price": session_data.get("price", 0),
                        "max_viewers": 100,
                        "stream_link": stream_link,
                        "group_id": "",
                        "superchat_enabled": session_data.get("superchat_enabled", True),
                        "superchat_min_amount": session_data.get("superchat_min", 10),
                        "status": "scheduled",
                        "tickets_sold": 0,
                        "superchat_total": 0,
                        "created_by": username or chat_id,
                        "tenant_id": bot_tenant_id,
                        "created_at": now.isoformat()
                    }
                    
                    await db.live_sessions.insert_one(session)
                    
                    # Clear pending setup
                    await db.pending_live_setup.delete_one({"telegram_user_id": chat_id})
                    
                    # Show success with options
                    price_text = "FREE" if session["price"] == 0 else f"₹{session['price']}"
                    msg = "🎉 <b>Live Stream Created!</b>\n\n"
                    msg += "━━━━━━━━━━━━━━━\n"
                    msg += f"📺 <b>{session['title']}</b>\n"
                    msg += f"💰 Ticket: {price_text}\n"
                    msg += f"🕐 Time: {session['scheduled_time']}\n"
                    msg += f"💬 Superchat: {'✅ ON' if session['superchat_enabled'] else '❌ OFF'}\n"
                    msg += "━━━━━━━━━━━━━━━\n\n"
                    msg += "What would you like to do?"
                    
                    bot_username = await get_bot_username(bot_token)
                    buttons = [
                        [{"text": "🔴 GO LIVE NOW", "callback_data": f"admin_golive_{session['id']}"}],
                        [{"text": "📢 Announce to Channel", "callback_data": f"live_announce_{session['id']}"}],
                        [{"text": "⏰ Start Countdown", "callback_data": f"live_countdown_{session['id']}"}],
                        [{"text": "📋 View All Lives", "callback_data": "live_my_scheduled"}]
                    ]
                    await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
                
                return {"ok": True}
            
            # Check if waiting for superchat message
            pending = await db.pending_screenshots.find_one({
                "telegram_user_id": chat_id,
                "status": "waiting_superchat_message"
            }, {"_id": 0})
            
            if pending:
                # Got the superchat message, now ask for payment screenshot
                await db.pending_screenshots.update_one(
                    {"telegram_user_id": chat_id},
                    {"$set": {
                        "superchat_message": text,
                        "status": "waiting_superchat_payment"
                    }}
                )
                
                qr_url = settings.get("qr_code_url", "")
                amount = pending.get("superchat_amount", 0)
                
                if qr_url:
                    msg = f"💬 <b>Super Chat - ₹{amount}</b>\n\n"
                    msg += f"📝 Your message:\n<i>{text[:100]}...</i>\n\n"
                    msg += "📱 Scan QR and pay, then send screenshot!"
                    
                    await send_telegram_photo(chat_id, qr_url, msg, bot_token)
                else:
                    msg = f"💬 <b>Super Chat - ₹{amount}</b>\n\n"
                    msg += "❌ QR not configured. Contact admin!"
                    await send_telegram_message(chat_id, msg, bot_token)
        
        # Handle photo/screenshot uploads
        photo = message.get("photo")
        if photo:
            # Get the largest photo (last in array)
            file_id = photo[-1].get("file_id")
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            if file_id and bot_token:
                # Get file path from Telegram
                try:
                    async with httpx.AsyncClient() as http_client:
                        file_response = await http_client.get(
                            f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
                        )
                        if file_response.status_code == 200:
                            file_data = file_response.json()
                            file_path = file_data.get("result", {}).get("file_path", "")
                            
                            if file_path:
                                # Create the full URL for the screenshot
                                screenshot_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
                                
                                # Find user's pending payment and update with screenshot
                                pending_payment = await db.payments.find_one({
                                    "telegram_user_id": chat_id,
                                    "status": "pending"
                                }, sort=[("created_at", -1)])
                                
                                if pending_payment:
                                    await db.payments.update_one(
                                        {"id": pending_payment["id"]},
                                        {"$set": {"screenshot_url": screenshot_url, "screenshot_file_id": file_id}}
                                    )
                                    
                                    msg = "✅ <b>Screenshot Received!</b>\n\n"
                                    msg += "📸 Your payment screenshot has been saved.\n"
                                    msg += "⏳ Admin will verify it shortly.\n\n"
                                    msg += f"📱 Your ID: <code>{chat_id}</code>"
                                    await send_telegram_message(chat_id, msg, bot_token)
                                    logger.info(f"Screenshot saved for payment {pending_payment['id']}")
                                else:
                                    msg = "⚠️ No pending payment found.\n\n"
                                    msg += "Please first select a plan and click 'I've Paid' button.\n"
                                    msg += "Then send your payment screenshot."
                                    buttons = [[{"text": "📦 View Plans", "callback_data": "back_plans"}]]
                                    await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
                except Exception as e:
                    logger.error(f"Error processing screenshot: {e}")
        
        # ============ AI CHAT - Handle unknown text messages ============
        # If message is text but not a command, try to answer using FAQ or AI
        if text and not text.startswith("/") and not photo:
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            # First check FAQs for matching answer
            faqs = await db.faqs.find({"is_active": True}, {"_id": 0}).to_list(100)
            
            faq_answer = None
            text_lower = text.lower()
            
            for faq in faqs:
                keywords = faq.get("keywords", [])
                question = faq.get("question", "").lower()
                
                # Check if any keyword matches
                if any(kw.lower() in text_lower for kw in keywords):
                    faq_answer = faq.get("answer")
                    break
                # Check if question is similar
                elif any(word in text_lower for word in question.split() if len(word) > 3):
                    faq_answer = faq.get("answer")
                    break
            
            if faq_answer:
                # Found FAQ match
                await send_telegram_message(chat_id, faq_answer, bot_token)
            else:
                # No FAQ match - use AI to respond
                try:
                    # Get context about the bot/business
                    plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
                    plan_info = "\n".join([f"- {p['name']}: ₹{p['price']} for {p['duration_days']} days" for p in plans])
                    
                    system_prompt = f"""You are a helpful customer support assistant for a subscription-based Telegram service.

Available Plans:
{plan_info}

Commands users can use:
- /start - View subscription plans
- /status - Check subscription status
- /live - View live sessions
- /help - Get help

Keep responses short, friendly, and helpful. If user asks about pricing or plans, tell them to use /start command. 
If they have technical issues, ask them to describe the problem.
Always be polite and use emojis sparingly."""

                    llm = LlmChat(
                        api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
                        model="gpt-4o-mini"
                    )
                    llm.add_message("system", system_prompt)
                    llm.add_message("user", text)
                    response = await llm.chat()
                    
                    if response:
                        await send_telegram_message(chat_id, response, bot_token)
                    else:
                        # Fallback response
                        fallback_msg = "🤔 I'm not sure about that.\n\n"
                        fallback_msg += "Try these commands:\n"
                        fallback_msg += "/start - View plans\n"
                        fallback_msg += "/status - Check subscription\n"
                        fallback_msg += "/help - Get help"
                        await send_telegram_message(chat_id, fallback_msg, bot_token)
                        
                except Exception as ai_error:
                    logger.error(f"AI Chat error: {ai_error}")
                    # Fallback response
                    fallback_msg = "🤔 I'm here to help!\n\n"
                    fallback_msg += "Use /start to see our plans or /help for commands."
                    await send_telegram_message(chat_id, fallback_msg, bot_token)
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"ok": False}

# ============== BACKGROUND TASKS ==============
