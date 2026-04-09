"""Channel post handlers — paid posts, subscribe buttons, member welcome."""
from database import db
from services.telegram import (
    get_bot_settings, get_bot_username, send_telegram_message, send_telegram_message_with_buttons,
    send_telegram_photo, send_telegram_video, is_admin_or_creator,
    download_telegram_photo, delete_telegram_message
)
from services.payment import create_blurred_image
from services.bot_activity import log_bot_activity
from config import logger
from datetime import datetime, timezone
import httpx
import asyncio
import uuid
import os

# In-memory buffer for media groups (cleared after processing)
_media_group_tasks = {}


async def _process_media_group(media_group_id: str, bot_token: str, bot_tenant_id: str, settings: dict):
    """Process buffered media group items as a single paid post after delay."""
    await asyncio.sleep(2.5)  # Wait for all items to arrive
    
    try:
        items = await db.media_group_buffer.find(
            {"media_group_id": media_group_id, "tenant_id": bot_tenant_id},
            {"_id": 0}
        ).sort("message_id", 1).to_list(20)
        
        if not items:
            return
        
        # Clean up buffer
        await db.media_group_buffer.delete_many({"media_group_id": media_group_id, "tenant_id": bot_tenant_id})
        _media_group_tasks.pop(media_group_id, None)
        
        first_item = items[0]
        post_chat_id = first_item["channel_id"]
        caption = first_item.get("caption", "") or ""
        blur_level = first_item.get("blur_level", 25)
        post_price = first_item.get("price", 99)
        
        # Collect all file_ids
        file_ids = []
        for item in items:
            file_ids.append({
                "type": item.get("content_type", "photo"),
                "file_id": item.get("file_id", ""),
                "message_id": item.get("message_id", 0)
            })
        
        # Download first photo for blur preview
        first_photo = next((f for f in file_ids if f["type"] == "photo" and f["file_id"]), None)
        blurred_bytes = None
        if first_photo:
            image_bytes = await download_telegram_photo(first_photo["file_id"], bot_token)
            if image_bytes:
                blurred_bytes = create_blurred_image(image_bytes, blur_radius=blur_level, content_type="photo")
        
        # Create paid post record with all file_ids
        paid_post_id = str(uuid.uuid4())
        
        # Clean caption
        import re as re_module
        clean_caption = re_module.sub(r'/paid[-_]?\s*', '', caption, flags=re_module.IGNORECASE).strip()
        price_match = re_module.search(r'^[₹]?(\d+)[-_\s]*', clean_caption)
        if price_match:
            clean_caption = clean_caption[price_match.end():].strip()
            clean_caption = re_module.sub(r'^[-_\s]+', '', clean_caption)
        # Remove blur param from caption
        clean_caption = re_module.sub(r'\s*blur:\s*\d+', '', clean_caption, flags=re_module.IGNORECASE).strip()
        
        paid_post = {
            "id": paid_post_id,
            "channel_id": post_chat_id,
            "original_message_id": first_item.get("message_id", 0),
            "content_type": "media_group",
            "original_file_id": first_photo["file_id"] if first_photo else (file_ids[0]["file_id"] if file_ids else ""),
            "file_ids": file_ids,
            "media_count": len(file_ids),
            "caption": clean_caption,
            "price": post_price,
            "blur_level": blur_level,
            "unlock_count": 0,
            "is_active": True,
            "tenant_id": bot_tenant_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.paid_posts.insert_one(paid_post)
        
        # Post blurred preview
        bot_username = await get_bot_username(bot_token)
        unlock_button = {
            "inline_keyboard": [[{
                "text": f"🔓 Unlock {len(file_ids)} Items - ₹{int(post_price)}",
                "url": f"https://t.me/{bot_username}?start=unlock_{paid_post_id}"
            }]]
        }
        
        price_text = f"₹{int(post_price)}" if post_price > 0 else "Premium"
        photo_count = sum(1 for f in file_ids if f["type"] == "photo")
        video_count = sum(1 for f in file_ids if f["type"] == "video")
        media_desc = []
        if photo_count: media_desc.append(f"{photo_count} Photo{'s' if photo_count > 1 else ''}")
        if video_count: media_desc.append(f"{video_count} Video{'s' if video_count > 1 else ''}")
        
        blur_caption = f"🔒 <b>Paid Content ({' + '.join(media_desc)})</b>\n\n"
        blur_caption += f"💰 Price: <b>{price_text}</b>\n\n"
        if clean_caption:
            blur_caption += f"📝 {clean_caption}\n\n"
        blur_caption += "👆 Tap 'Unlock' to view all content!"
        
        blurred_posted = False
        if blurred_bytes:
            result = await send_telegram_photo(post_chat_id, blurred_bytes, blur_caption, bot_token, unlock_button)
            if result and result.get("ok"):
                blurred_message_id = result.get("result", {}).get("message_id", 0)
                await db.paid_posts.update_one({"id": paid_post_id}, {"$set": {"blurred_message_id": blurred_message_id}})
                blurred_posted = True
        
        if not blurred_posted:
            result = await send_telegram_message_with_buttons(post_chat_id, blur_caption, [[{
                "text": f"🔓 Unlock {len(file_ids)} Items - ₹{int(post_price)}",
                "url": f"https://t.me/{bot_username}?start=unlock_{paid_post_id}"
            }]], bot_token)
            if result:
                blurred_posted = True
        
        # Delete all original messages
        if blurred_posted:
            for item in items:
                msg_id = item.get("message_id")
                if msg_id:
                    await delete_telegram_message(post_chat_id, msg_id, bot_token)
        
        logger.info(f"Media group paid post created: {paid_post_id} with {len(file_ids)} items")
    
    except Exception as e:
        logger.error(f"Error processing media group: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def handle_channel_post(data, bot_token, bot_tenant_id, settings):
    """Handle channel_post updates — paid posts and subscribe buttons."""
    channel_post = data.get("channel_post", {})
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
                
                # Parse blur level from caption: blur:30 or blur:high/medium/low
                blur_level = 25  # default
                blur_match = re_module.search(r'blur:\s*(\w+)', caption, re_module.IGNORECASE)
                if blur_match:
                    blur_val = blur_match.group(1).lower()
                    blur_map = {"low": 10, "medium": 25, "high": 50, "extreme": 80, "max": 100}
                    if blur_val in blur_map:
                        blur_level = blur_map[blur_val]
                    elif blur_val.isdigit():
                        blur_level = max(1, min(int(blur_val), 100))
                
                # Extract price
                clean_caption_temp = re_module.sub(r'^/paid[-_]?\s*', '', caption, flags=re_module.IGNORECASE).strip()
                price_match = re_module.search(r'^[₹]?(\d+)[-_\s]*', clean_caption_temp)
                post_price = float(price_match.group(1)) if price_match else 0
                
                if post_price <= 0:
                    s = await get_bot_settings()
                    post_price = s.get("default_paid_post_price", 0)
                    if post_price <= 0:
                        plans = await db.plans.find({"is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0}).sort("price", 1).to_list(1)
                        post_price = plans[0].get("price", 99) if plans else 99
                
                # Check if this is part of a media group
                media_group_id = channel_post.get("media_group_id")
                
                if media_group_id:
                    # Buffer this item for media group processing
                    photo = channel_post.get("photo")
                    video = channel_post.get("video")
                    file_id = ""
                    content_type = "photo"
                    
                    if photo:
                        file_id = photo[-1].get("file_id", "")
                        content_type = "photo"
                    elif video:
                        file_id = video.get("file_id", "")
                        content_type = "video"
                    
                    await db.media_group_buffer.insert_one({
                        "media_group_id": media_group_id,
                        "channel_id": post_chat_id,
                        "message_id": message_id,
                        "content_type": content_type,
                        "file_id": file_id,
                        "caption": caption if caption.lower().startswith("/paid") else "",
                        "price": post_price,
                        "blur_level": blur_level,
                        "tenant_id": bot_tenant_id,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    })
                    
                    # Start delayed processing task (only once per group)
                    if media_group_id not in _media_group_tasks:
                        _media_group_tasks[media_group_id] = True
                        asyncio.create_task(_process_media_group(media_group_id, bot_token, bot_tenant_id, settings))
                    
                    logger.info(f"Buffered media group item: {media_group_id}, file_id: {file_id[:20] if file_id else 'none'}")
                    return {"ok": True, "media_group_buffered": True}
                
                # Single item paid post (not media group)
                
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
                        logger.info(f"Downloaded {len(image_bytes)} bytes, creating blur with level {blur_level}...")
                        blurred_bytes = create_blurred_image(image_bytes, blur_radius=blur_level, content_type="photo")
                        if blurred_bytes:
                            logger.info(f"Created blurred image: {len(blurred_bytes)} bytes")
                        else:
                            logger.error("Failed to create blurred image - blurred_bytes is None")
                    else:
                        logger.error("Failed to download original photo - image_bytes is None")
                
                # Clean caption (remove /paid command and variations)
                clean_caption = re_module.sub(r'^/paid[-_]?\s*', '', caption, flags=re_module.IGNORECASE).strip()
                
                # Extract price if mentioned (e.g., /paid-999, /paid 99)
                price_match_single = re_module.search(r'^[₹]?(\d+)[-_\s]*', clean_caption)
                if price_match_single:
                    clean_caption = clean_caption[price_match_single.end():].strip()
                    clean_caption = re_module.sub(r'^[-_\s]+', '', clean_caption)
                
                # Remove blur param from clean caption
                clean_caption = re_module.sub(r'\s*blur:\s*\w+', '', clean_caption, flags=re_module.IGNORECASE).strip()
                
                # Create paid post record
                paid_post_id = str(uuid.uuid4())
                paid_post = {
                    "id": paid_post_id,
                    "channel_id": post_chat_id,
                    "original_message_id": message_id,
                    "content_type": content_type,
                    "original_file_id": original_file_id,
                    "file_ids": [{"type": content_type, "file_id": original_file_id}] if original_file_id else [],
                    "media_count": 1,
                    "caption": clean_caption,
                    "price": post_price,
                    "blur_level": blur_level,
                    "unlock_count": 0,
                    "is_active": True,
                    "tenant_id": bot_tenant_id,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.paid_posts.insert_one(paid_post)
                logger.info(f"Created paid post record: {paid_post_id} with price {post_price}, blur {blur_level}")
                
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
                        await db.paid_posts.update_one({"id": paid_post_id, "tenant_id": bot_tenant_id}, {"$set": {"blurred_message_id": blurred_message_id}})
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
                                blurred_thumb = create_blurred_image(thumb_bytes, blur_radius=blur_level, content_type="video")
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
                                        await db.paid_posts.update_one({"id": paid_post_id, "tenant_id": bot_tenant_id}, {"$set": {"blurred_message_id": blurred_message_id}})
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


async def handle_member_update(data, bot_token, bot_tenant_id, settings):
    """Handle chat_member updates — welcome messages for new channel members."""
    chat_member_update = data.get("chat_member")
    if not chat_member_update or not bot_token:
        return {"ok": True}
    
    chat_id = str(chat_member_update.get("chat", {}).get("id", ""))
    new_member = chat_member_update.get("new_chat_member", {})
    old_member = chat_member_update.get("old_chat_member", {})
    user = new_member.get("user", {})
    user_id = str(user.get("id", ""))
    username = user.get("username", "")
    first_name = user.get("first_name", "")
    
    old_status = old_member.get("status", "")
    new_status = new_member.get("status", "")
    
    if new_status in ["member", "administrator"] and old_status in ["left", "kicked", ""]:
        logger.info(f"New member {user_id} (@{username}) joined channel {chat_id}")
        
        if user_id and not user.get("is_bot"):
            plans = await db.plans.find({"is_active": True, "tenant_id": bot_tenant_id}, {"_id": 0}).to_list(10)
            website_link = settings.get("website_link", "") or ""
            
            welcome_msg = f"\U0001f389 <b>Welcome {first_name}!</b>\n\n"
            welcome_msg += "Thanks for joining our channel! \U0001f495\n\n"
            if website_link and website_link.startswith("http"):
                welcome_msg += f"\U0001f310 <b>Visit:</b> {website_link}\n\n"
            welcome_msg += "\U0001f525 <b>Get Exclusive Content!</b>\n"
            welcome_msg += "Subscribe now for premium access!\n\n"
            welcome_msg += "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            welcome_msg += "\U0001f3af <b>Choose Your Plan:</b>\n\n"
            
            buttons = []
            for plan in plans:
                plan_price = int(plan.get("price", 0))
                plan_name = plan.get("name", "Plan")
                plan_id = plan.get("id", "")
                if not plan_id:
                    continue
                welcome_msg += f"\U0001f4e6 <b>{plan_name}</b> - \u20b9{plan_price}\n"
                buttons.append([{"text": f"\U0001f4e6 {plan_name} - \u20b9{plan_price}", "callback_data": f"buy_{plan_id}"}])
            
            if website_link and website_link.startswith("http"):
                buttons.append([{"text": "\U0001f310 Visit Website", "url": website_link}])
            buttons.append([{"text": "\U0001f381 Special Discount!", "callback_data": "special_discount"}])
            
            try:
                from services.telegram import send_telegram_message_with_buttons
                await send_telegram_message_with_buttons(user_id, welcome_msg, buttons, bot_token)
                logger.info(f"Sent welcome message with plans to new member {user_id}")
            except Exception as e:
                logger.error(f"Failed to send welcome message: {e}")
    
    return {"ok": True}
