"""Message handlers — commands, screenshots, chat tracking, AI chat, live stream, admin commands."""
from database import db
from services.telegram import (
    get_bot_settings, get_bot_username, send_telegram_message,
    send_telegram_message_with_buttons, send_telegram_message_with_buttons_and_return,
    edit_telegram_message, send_telegram_photo, send_telegram_video,
    download_telegram_photo, add_to_channel, remove_from_channel,
    send_screenshot_reminders, urgency_timer_task,
    is_admin_or_creator, notify_admin_new_payment
)
from services.payment import detect_payment_screenshot, create_blurred_image, analyze_payment_screenshot_with_ai
from services.chat_pool import get_available_chat_group, assign_chat_group
from services.bot_activity import log_bot_activity
from config import logger, EMERGENT_LLM_KEY
from emergentintegrations.llm.chat import LlmChat
from datetime import datetime, timezone, timedelta
import uuid
import httpx
import os
import asyncio
import json
import re
import base64
from io import BytesIO


async def handle_message(data, bot_token, bot_tenant_id, settings, background_tasks):
    """Handle all regular messages — commands, photos, text, screenshots, AI chat."""
    message = data.get("message", {})
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
            {"user_id": str(chat_id), "tenant_id": bot_tenant_id},
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
                    "tenant_id": bot_tenant_id,
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
                        plans = await db.plans.find({"is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0}).sort("price", 1).to_list(1)
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
                    await db.paid_posts.update_one({"id": paid_post_id, "tenant_id": bot_tenant_id}, {"$set": {"blurred_message_id": blurred_message_id}})
                    
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
            "telegram_user_id": chat_id, "tenant_id": bot_tenant_id,
            "status": {"$in": ["waiting", "waiting_unlock", "waiting_live_ticket", "waiting_superchat_payment"]}
        }, {"_id": 0})
        
        # Handle PAID POST UNLOCK screenshot
        if pending and pending.get("status") == "waiting_unlock":
            post_id = pending.get("unlock_post_id")
            paid_post = await db.paid_posts.find_one({"id": post_id, "is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0})
            
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
                            "tenant_id": bot_tenant_id,
                            "unlocked_at": datetime.now(timezone.utc).isoformat()
                        }
                        await db.paid_post_unlocks.insert_one(unlock_record)
                        
                        # Update unlock count
                        await db.paid_posts.update_one({"id": post_id, "tenant_id": bot_tenant_id}, {"$inc": {"unlock_count": 1}})
                        
                        # Remove pending status
                        await db.pending_screenshots.delete_one({"telegram_user_id": chat_id, "tenant_id": bot_tenant_id})
                        
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
                            "tenant_id": bot_tenant_id,
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                        await db.unlock_requests.insert_one(unlock_request)
                        await db.pending_screenshots.delete_one({"telegram_user_id": chat_id, "tenant_id": bot_tenant_id})
                        
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
                await db.pending_screenshots.delete_one({"telegram_user_id": chat_id, "tenant_id": bot_tenant_id})
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
                await db.pending_screenshots.delete_one({"telegram_user_id": chat_id, "tenant_id": bot_tenant_id})
                
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
                await db.pending_screenshots.delete_one({"telegram_user_id": chat_id, "tenant_id": bot_tenant_id})
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
                    "tenant_id": bot_tenant_id,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.live_superchats.insert_one(superchat)
                
                # Clear pending
                await db.pending_screenshots.delete_one({"telegram_user_id": chat_id, "tenant_id": bot_tenant_id})
                
                msg = "💬 <b>Super Chat Submitted!</b>\n\n"
                msg += f"💰 Amount: ₹{pending.get('superchat_amount', 0)}\n"
                msg += f"📝 Message: {pending.get('superchat_message', '')[:50]}...\n\n"
                msg += "⏳ Admin will verify payment and show your message during the live!"
                await send_telegram_message(chat_id, msg, bot_token)
                return {"ok": True}
            else:
                await send_telegram_message(chat_id, "❌ Live session ended.", bot_token)
                await db.pending_screenshots.delete_one({"telegram_user_id": chat_id, "tenant_id": bot_tenant_id})
                return {"ok": True}
        
        # Handle REGULAR SUBSCRIPTION screenshot
        if pending and pending.get("status") == "waiting":
            plan_id = pending.get("plan_id")
            plan = await db.plans.find_one({"id": plan_id, "tenant_id": bot_tenant_id}, {"_id": 0})
            
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
                            "status": "active",
                            "tenant_id": bot_tenant_id
                        }, {"_id": 0})
                        
                        # Get discounted price if available
                        discounted_price = pending.get("discounted_price")
                        final_price = discounted_price if discounted_price else plan['price']
                        
                        if existing_sub:
                            # Extend subscription
                            current_end = datetime.fromisoformat(existing_sub["end_date"]) if isinstance(existing_sub["end_date"], str) else existing_sub["end_date"]
                            new_end = current_end + timedelta(days=plan['duration_days'])
                            
                            await db.subscribers.update_one(
                                {"telegram_user_id": chat_id, "tenant_id": bot_tenant_id},
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
                        await db.pending_screenshots.delete_one({"telegram_user_id": chat_id, "tenant_id": bot_tenant_id})
                        
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
                            await db.pending_screenshots.delete_one({"telegram_user_id": chat_id, "tenant_id": bot_tenant_id})
                            
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
                                {"telegram_user_id": chat_id, "tenant_id": bot_tenant_id},
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
        paid_post = await db.paid_posts.find_one({"id": post_id, "is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0})
        
        if not paid_post:
            # Also try without is_active filter (post may have been deactivated)
            paid_post = await db.paid_posts.find_one({"id": post_id, "tenant_id": bot_tenant_id}, {"_id": 0})
        
        settings = await get_bot_settings()
        from config import razorpay_client
        
        if not paid_post:
            # Post not in DB — show Razorpay unlock with cheapest plan price
            logger.info(f"Post {post_id} not found for tenant {bot_tenant_id}, showing generic unlock")
            plans = await db.plans.find({"is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0}).sort("price", 1).to_list(1)
            fallback_price = plans[0].get("price", 99) if plans else 99
            
            unlock_msg = "🔒 <b>Premium Content</b>\n\n"
            unlock_msg += f"💰 Price: <b>₹{int(fallback_price)}</b>\n\n"
            unlock_msg += "━━━━━━━━━━━━━━━\n"
            unlock_msg += "💳 <b>Tap below to pay & unlock instantly!</b>"
            
            buttons = []
            if razorpay_client:
                try:
                    callback_base = os.environ.get("RAZORPAY_CALLBACK_URL", "")
                    if not callback_base:
                        website_link = settings.get("website_link", "")
                        if website_link and website_link.startswith("http"):
                            callback_base = website_link.rstrip("/")
                    
                    link_data = {
                        "amount": int(fallback_price) * 100,
                        "currency": "INR",
                        "accept_partial": False,
                        "description": f"Unlock Premium Content - ₹{int(fallback_price)}",
                        "customer": {"name": username or f"User_{chat_id}"},
                        "notify": {"sms": False, "email": False},
                        "reminder_enable": False,
                        "notes": {
                            "chat_id": str(chat_id),
                            "unlock_post_id": post_id,
                            "username": username or "",
                            "tenant_id": bot_tenant_id,
                            "type": "paid_post_unlock",
                        },
                        "expire_by": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
                    }
                    if callback_base:
                        link_data["callback_url"] = f"{callback_base}/api/razorpay/callback"
                        link_data["callback_method"] = "get"
                    
                    rp_result = await asyncio.to_thread(razorpay_client.payment_link.create, link_data)
                    rp_link = rp_result.get("short_url", "")
                    if rp_link:
                        await db.razorpay_bot_orders.update_one(
                            {"chat_id": str(chat_id), "unlock_post_id": post_id, "status": "created"},
                            {"$set": {
                                "chat_id": str(chat_id), "username": username or "",
                                "unlock_post_id": post_id,
                                "plan_id": "", "plan_name": "Unlock Content",
                                "duration_days": 0, "amount": int(fallback_price),
                                "payment_link_id": rp_result.get("id", ""),
                                "payment_link_url": rp_link, "status": "created",
                                "type": "paid_post_unlock",
                                "tenant_id": bot_tenant_id,
                                "created_at": datetime.now(timezone.utc).isoformat()
                            }}, upsert=True
                        )
                        buttons.append([{"text": f"💳 Pay ₹{int(fallback_price)} - Unlock Now", "url": rp_link}])
                except Exception as rp_err:
                    logger.error(f"Razorpay unlock (fallback) failed: {rp_err}")
            
            buttons.append([{"text": "📦 View All Plans", "callback_data": "back_plans"}])
            await send_telegram_message_with_buttons(chat_id, unlock_msg, buttons, bot_token)
            return {"ok": True}
        
        # ---- Post found in DB ----
        
        # Check if user already unlocked this post
        existing_unlock = await db.paid_post_unlocks.find_one({
            "post_id": post_id,
            "telegram_user_id": chat_id,
            "tenant_id": bot_tenant_id
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
        
        # Everyone must pay — send blurred preview + Razorpay button
        post_price = paid_post.get("price", 0)
        
        # If no specific price, use cheapest plan
        if post_price <= 0:
            plans = await db.plans.find({"is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0}).sort("price", 1).to_list(1)
            post_price = plans[0].get("price", 99) if plans else 99
        
        content_type = paid_post.get("content_type", "photo")
        content_label = "Video" if content_type == "video" else "Post"
        original_file_id = paid_post.get("original_file_id", "")
        
        # Try to send blurred preview
        blurred_sent = False
        if original_file_id:
            try:
                if content_type == "photo":
                    image_bytes = await download_telegram_photo(original_file_id, bot_token)
                    if image_bytes:
                        blurred_bytes = create_blurred_image(image_bytes, content_type="photo")
                        if blurred_bytes:
                            blur_caption = f"🔒 <b>Paid {content_label}</b>\n\n"
                            blur_caption += f"💰 Price: <b>₹{int(post_price)}</b>\n"
                            if paid_post.get("caption"):
                                blur_caption += f"\n📝 {paid_post['caption']}\n"
                            blur_caption += "\n👆 <b>Pay below to unlock this content!</b>"
                            await send_telegram_photo(chat_id, blurred_bytes, blur_caption, bot_token)
                            blurred_sent = True
                elif content_type == "video":
                    # For video, try to get a thumbnail and blur it
                    # We need to get file info first
                    async with httpx.AsyncClient(timeout=30.0) as http_client:
                        file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={original_file_id}"
                        resp = await http_client.get(file_info_url)
                        if resp.status_code == 200:
                            file_data = resp.json()
                            # Video files can't easily be thumbnailed from file_id
                            # Send a styled text message instead with play icon
                            pass
                    
                    # Send video preview message
                    blur_caption = f"🎬 <b>Paid Video Content</b>\n\n"
                    blur_caption += f"💰 Price: <b>₹{int(post_price)}</b>\n"
                    if paid_post.get("caption"):
                        blur_caption += f"\n📝 {paid_post['caption']}\n"
                    blur_caption += "\n▶️ <b>Pay below to watch this video!</b>"
                    await send_telegram_message(chat_id, blur_caption, bot_token)
                    blurred_sent = True
            except Exception as blur_err:
                logger.error(f"Error sending blurred preview: {blur_err}")
        
        # If blur failed, send text-only unlock message
        if not blurred_sent:
            unlock_msg = f"🔒 <b>Paid {content_label}</b>\n\n"
            unlock_msg += f"💰 Price: <b>₹{int(post_price)}</b>\n"
            if paid_post.get("caption"):
                unlock_msg += f"\n📝 {paid_post['caption']}\n"
            unlock_msg += "\n━━━━━━━━━━━━━━━\n"
            unlock_msg += "💳 <b>Tap below to pay & unlock!</b>"
            await send_telegram_message(chat_id, unlock_msg, bot_token)
        
        # Create Razorpay Payment Link
        buttons = []
        if razorpay_client:
            try:
                callback_base = os.environ.get("RAZORPAY_CALLBACK_URL", "")
                if not callback_base:
                    website_link = settings.get("website_link", "")
                    if website_link and website_link.startswith("http"):
                        callback_base = website_link.rstrip("/")
                
                link_data = {
                    "amount": int(post_price) * 100,
                    "currency": "INR",
                    "accept_partial": False,
                    "description": f"Unlock {content_label} - ₹{int(post_price)}",
                    "customer": {"name": username or f"User_{chat_id}"},
                    "notify": {"sms": False, "email": False},
                    "reminder_enable": False,
                    "notes": {
                        "chat_id": str(chat_id),
                        "unlock_post_id": post_id,
                        "username": username or "",
                        "tenant_id": bot_tenant_id,
                        "type": "paid_post_unlock",
                    },
                    "expire_by": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
                }
                if callback_base:
                    link_data["callback_url"] = f"{callback_base}/api/razorpay/callback"
                    link_data["callback_method"] = "get"
                
                rp_result = await asyncio.to_thread(razorpay_client.payment_link.create, link_data)
                rp_link = rp_result.get("short_url", "")
                if rp_link:
                    await db.razorpay_bot_orders.update_one(
                        {"chat_id": str(chat_id), "unlock_post_id": post_id, "status": "created"},
                        {"$set": {
                            "chat_id": str(chat_id), "username": username or "",
                            "unlock_post_id": post_id,
                            "plan_id": "", "plan_name": f"Unlock {content_label}",
                            "duration_days": 0, "amount": int(post_price),
                            "payment_link_id": rp_result.get("id", ""),
                            "payment_link_url": rp_link, "status": "created",
                            "type": "paid_post_unlock",
                            "tenant_id": bot_tenant_id,
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }}, upsert=True
                    )
                    buttons.append([{"text": f"💳 Pay ₹{int(post_price)} - Unlock {content_label}", "url": rp_link}])
            except Exception as rp_err:
                logger.error(f"Razorpay link creation for unlock failed: {rp_err}")
        
        buttons.append([{"text": "📦 Get Full Subscription", "callback_data": "back_plans"}])
        
        # Send Razorpay button as separate message
        pay_msg = f"💳 <b>Pay ₹{int(post_price)} to unlock this {content_label.lower()}!</b>\n\n"
        pay_msg += "✅ Instant access after payment"
        await send_telegram_message_with_buttons(chat_id, pay_msg, buttons, bot_token)
        
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
            plan = await db.plans.find_one({"id": plan_id, "is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0})
            if plan:
                settings = await get_bot_settings()
                bot_token = settings.get("telegram_bot_token", "")
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
                    for feat in plan['features']:
                        payment_msg += f"✅ {feat}\n"
                    payment_msg += "\n"
                
                payment_msg += "━━━━━━━━━━━━━━━\n"
                payment_msg += "<b>💳 Pay now to get instant access!</b>\n\n"
                
                buttons = []
                
                # Create Razorpay Payment Link
                if razorpay_client:
                    try:
                        callback_base = os.environ.get("RAZORPAY_CALLBACK_URL", "")
                        if not callback_base:
                            website_link = settings.get("website_link", "")
                            if website_link and website_link.startswith("http"):
                                callback_base = website_link.rstrip("/")
                        
                        link_data = {
                            "amount": final_price * 100,
                            "currency": "INR",
                            "accept_partial": False,
                            "description": f"{plan.get('name', 'Plan')} - {plan.get('duration_days', 30)} days",
                            "customer": {"name": username or f"User_{chat_id}"},
                            "notify": {"sms": False, "email": False},
                            "reminder_enable": False,
                            "notes": {
                                "chat_id": str(chat_id),
                                "plan_id": plan_id,
                                "username": username or "",
                                "tenant_id": bot_tenant_id,
                            },
                            "expire_by": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
                        }
                        if callback_base:
                            link_data["callback_url"] = f"{callback_base}/api/razorpay/callback"
                            link_data["callback_method"] = "get"
                        
                        rp_result = await asyncio.to_thread(razorpay_client.payment_link.create, link_data)
                        rp_link = rp_result.get("short_url", "")
                        if rp_link:
                            await db.razorpay_bot_orders.update_one(
                                {"chat_id": str(chat_id), "plan_id": plan_id, "status": "created"},
                                {"$set": {
                                    "chat_id": str(chat_id), "username": username or "",
                                    "plan_id": plan_id, "plan_name": plan.get('name', 'Plan'),
                                    "duration_days": plan.get('duration_days', 30),
                                    "amount": final_price, "payment_link_id": rp_result.get("id", ""),
                                    "payment_link_url": rp_link, "status": "created",
                                    "tenant_id": bot_tenant_id,
                                    "created_at": datetime.now(timezone.utc).isoformat()
                                }}, upsert=True
                            )
                            buttons.append([{"text": "💳 Pay with Razorpay", "url": rp_link}])
                    except Exception as rp_err:
                        logger.error(f"Razorpay link creation failed in deep link: {rp_err}")
                
                
                payment_msg += f"📱 <b>Your ID:</b> <code>{chat_id}</code>"
                
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
                plans = await db.plans.find({"is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0}).to_list(10)
            
            settings = await get_bot_settings()
            website_link = settings.get("website_link", "") or ""
            
            welcome_msg = "🎉 <b>Welcome!</b>\n\n"
            welcome_msg += "🔥 <b>Exclusive Content Awaits!</b>\n\n"
            if website_link and website_link.startswith("http"):
                welcome_msg += f"🌐 <b>Visit:</b> {website_link}\n\n"
            welcome_msg += "━━━━━━━━━━━━━━━\n"
            welcome_msg += "🎯 <b>Choose Your Plan:</b>\n\n"
            
            buttons = []
            for plan in plans:
                plan_price = plan.get('price', 0)
                plan_name = plan.get('name', 'Plan')
                plan_days = plan.get('duration_days', 30)
                plan_id = plan.get('id', '')
                discount = plan.get('discount_percentage', 0)
                if not plan_id:
                    continue
                
                # Calculate discounted price
                if discount and discount > 0:
                    discounted_price = round(plan_price * (1 - discount / 100))
                    # Escape HTML special chars in plan name
                    safe_name = str(plan_name).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    welcome_msg += f"📦 <b>{safe_name}</b>\n"
                    welcome_msg += f"   💰 <s>₹{int(plan_price)}</s> ₹{discounted_price} ({discount}% OFF) • ⏱ {plan_days} days\n\n"
                    buttons.append([{"text": f"📦 {plan_name} - ₹{discounted_price}", "callback_data": f"buy_{plan_id}"}])
                else:
                    safe_name = str(plan_name).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    welcome_msg += f"📦 <b>{safe_name}</b>\n"
                    welcome_msg += f"   💰 ₹{int(plan_price)} • ⏱ {plan_days} days\n\n"
                    buttons.append([{"text": f"📦 {plan_name} - ₹{int(plan_price)}", "callback_data": f"buy_{plan_id}"}])
            
            if not plans:
                welcome_msg += "No plans available at the moment.\n"
            
            # Only add URL button if website_link is a valid URL
            if website_link and website_link.startswith("http"):
                buttons.append([{"text": "🌐 Visit Website", "url": website_link}])
            buttons.append([{"text": "🎁 Special Discount For You!", "callback_data": "special_discount"}])
            buttons.append([{"text": "📊 Check My Status", "callback_data": "check_status"}])
            
            logger.info(f"/start sending welcome to {chat_id} with {len(plans)} plans, {len(buttons)} button rows, website_link='{website_link[:50] if website_link else 'EMPTY'}'")
            result = await send_telegram_message_with_buttons(chat_id, welcome_msg, buttons, bot_token)
            if not result:
                logger.error(f"/start failed to send welcome message to {chat_id}, bot_token present: {bool(bot_token)}")
                # Try sending without buttons as last resort
                await send_telegram_message(chat_id, welcome_msg, bot_token)
        except Exception as start_err:
            logger.error(f"/start handler error for {chat_id}: {start_err}")
            import traceback
            logger.error(traceback.format_exc())
            await send_telegram_message(chat_id, "🎉 Welcome! Use /plans to see available plans.", bot_token)
    
    elif text == "/status":
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
        active_subs = await db.subscribers.count_documents({"status": "active", "tenant_id": bot_tenant_id})
        pending_payments = await db.payments.count_documents({"status": "pending", "tenant_id": bot_tenant_id})
        total_revenue = 0
        payments = await db.payments.find({"status": "verified", "tenant_id": bot_tenant_id}, {"_id": 0, "amount": 1}).to_list(100000)
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
        
        total_subs = await db.subscribers.count_documents({"tenant_id": bot_tenant_id})
        active_subs = await db.subscribers.count_documents({"status": "active", "tenant_id": bot_tenant_id})
        expired_subs = await db.subscribers.count_documents({"status": "expired", "tenant_id": bot_tenant_id})
        grace_subs = await db.subscribers.count_documents({"status": "grace", "tenant_id": bot_tenant_id})
        pending_payments = await db.payments.count_documents({"status": "pending", "tenant_id": bot_tenant_id})
        verified_payments = await db.payments.count_documents({"status": "verified", "tenant_id": bot_tenant_id})
        payments = await db.payments.find({"status": "verified", "tenant_id": bot_tenant_id}, {"_id": 0, "amount": 1}).to_list(100000)
        total_revenue = sum(p.get("amount", 0) for p in payments)
        total_plans = await db.plans.count_documents({"is_active": True, "tenant_id": bot_tenant_id})
        
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
        
        pending = await db.payments.find({"status": "pending", "tenant_id": bot_tenant_id}, {"_id": 0}).sort("created_at", -1).limit(10).to_list(10)
        
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
        bot_users = await db.bot_users.find({"tenant_id": bot_tenant_id}, {"_id": 0, "user_id": 1}).to_list(100000)
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
        
        recent_users = await db.bot_users.find({"tenant_id": bot_tenant_id}, {"_id": 0}).sort("last_seen", -1).limit(10).to_list(10)
        
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
        
        plans = await db.plans.find({"is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0}).to_list(20)
        
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
        
        plans = await db.plans.find({"is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0}).to_list(10)
        
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
            "telegram_user_id": chat_id, "tenant_id": bot_tenant_id,
            "status": "waiting_superchat_message"
        }, {"_id": 0})
        
        if pending:
            # Got the superchat message, now ask for payment screenshot
            await db.pending_screenshots.update_one(
                {"telegram_user_id": chat_id, "tenant_id": bot_tenant_id},
                {"$set": {
                    "superchat_message": text,
                    "status": "waiting_superchat_payment"
                }}
            )
            
            amount = pending.get("superchat_amount", 0)
            
            msg = f"💬 <b>Super Chat - ₹{amount}</b>\n\n"
            msg += f"📝 Your message:\n<i>{text[:100]}...</i>\n\n"
            msg += "💳 Pay via Razorpay and send screenshot here!"
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
                                "status": "pending",
                                "tenant_id": bot_tenant_id
                            }, sort=[("created_at", -1)])
                            
                            if pending_payment:
                                await db.payments.update_one(
                                    {"id": pending_payment["id"], "tenant_id": bot_tenant_id},
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
                plans = await db.plans.find({"is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0}).to_list(10)
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
                    api_key=EMERGENT_LLM_KEY,
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
