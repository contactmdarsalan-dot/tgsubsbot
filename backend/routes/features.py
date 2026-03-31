"""Templates, Broadcast, Coupons, Notes, Tags, Referrals, FAQ, Video calls,
Renewal, Creators, TG Admins, Live stream, Revenue analytics, Exports,
Chat messages, Bot activity, Paid posts routes"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from database import db
from services.auth import get_current_user
from services.telegram import (
    get_bot_settings, get_bot_username, send_telegram_message,
    send_telegram_message_with_buttons, send_telegram_message_with_buttons_and_return,
    send_telegram_photo, send_telegram_video, delete_telegram_message,
    download_telegram_photo, is_admin_or_creator
)
from services.payment import create_blurred_image
from services.bot_activity import log_bot_activity
from config import logger
from models import MessageTemplate
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import httpx
import os
import asyncio
import json
import re

router = APIRouter()

# ============== MESSAGE TEMPLATES ROUTES ==============

@router.get("/templates")
async def get_templates(user = Depends(get_current_user)):
    templates = await db.templates.find({}, {"_id": 0}).to_list(100)
    return templates

@router.post("/templates")
async def create_template(template: MessageTemplate, user = Depends(get_current_user)):
    doc = template.model_dump()
    await db.templates.insert_one(doc)
    return template

@router.put("/templates/{template_id}")
async def update_template(template_id: str, template: MessageTemplate, user = Depends(get_current_user)):
    doc = template.model_dump()
    doc["id"] = template_id
    await db.templates.update_one({"id": template_id}, {"$set": doc}, upsert=True)
    return {"message": "Template updated"}

@router.delete("/templates/{template_id}")
async def delete_template(template_id: str, user = Depends(get_current_user)):
    await db.templates.delete_one({"id": template_id})
    return {"message": "Template deleted"}


@router.post("/promote-plan")
async def promote_plan_to_group(data: dict, user = Depends(get_current_user)):
    """Promote a specific plan/service to a selected group"""
    plan_id = data.get("plan_id", "")
    group_id = data.get("group_id", "")
    
    if not plan_id or not group_id:
        raise HTTPException(status_code=400, detail="plan_id and group_id required")
    
    plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot token not configured")
    
    original_price = int(plan['price'])
    discount_pct = plan.get('discount_percentage', 0)
    if discount_pct > 0:
        final_price = int(original_price * (100 - discount_pct) / 100)
        price_display = f"<s>₹{original_price}</s> → ₹{final_price} 🔥"
    else:
        price_display = f"₹{original_price}"
    
    promo_msg = "🔥 <b>EXCLUSIVE OFFER!</b> 🔥\n\n"
    promo_msg += f"📦 <b>{plan['name']}</b>\n"
    promo_msg += f"💰 Price: {price_display}\n"
    promo_msg += f"⏱ Duration: <b>{plan['duration_days']} days</b>\n\n"
    
    if plan.get('features'):
        for feat in plan['features']:
            promo_msg += f"✅ {feat}\n"
        promo_msg += "\n"
    
    promo_msg += "🚀 <b>Grab this offer now!</b>"
    
    # Get bot username for deep link
    try:
        async with httpx.AsyncClient() as http_client:
            me_response = await http_client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
            bot_username = me_response.json().get("result", {}).get("username", "")
    except Exception:
        bot_username = ""
    
    buttons = []
    if bot_username:
        buttons.append([{"text": "💳 Buy Now!", "url": f"https://t.me/{bot_username}?start=buy_{plan_id}"}])
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": group_id,
                "text": promo_msg,
                "parse_mode": "HTML"
            }
            if buttons:
                payload["reply_markup"] = {"inline_keyboard": buttons}
            response = await http_client.post(url, json=payload)
            if response.status_code == 200:
                return {"message": "Plan promoted successfully", "success": True}
            else:
                return {"message": f"Failed: {response.text}", "success": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== BROADCAST ROUTES ==============

class BroadcastRequest(BaseModel):
    message: str
    target: str = "all"  # all, subscribers, channel_members
    include_button: bool = False
    button_text: str = "🔔 Subscribe Now"
    button_url: str = ""

@router.post("/broadcast")
async def send_broadcast(request: BroadcastRequest, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    """Send broadcast message to users"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot token not configured")
    
    # Get target users based on selection
    user_ids = set()
    
    if request.target in ["all", "subscribers"]:
        # Get all subscribers
        subscribers = await db.subscribers.find({"status": "active"}, {"_id": 0}).to_list(10000)
        for sub in subscribers:
            if sub.get("telegram_user_id"):
                user_ids.add(str(sub["telegram_user_id"]))
    
    if request.target in ["all", "channel_members"]:
        # Get users from payments (they interacted with bot)
        payments = await db.payments.find({}, {"_id": 0, "telegram_user_id": 1}).to_list(10000)
        for p in payments:
            if p.get("telegram_user_id"):
                user_ids.add(str(p["telegram_user_id"]))
        
        # Get from pending screenshots
        pending = await db.pending_screenshots.find({}, {"_id": 0, "telegram_user_id": 1}).to_list(10000)
        for p in pending:
            if p.get("telegram_user_id"):
                user_ids.add(str(p["telegram_user_id"]))
    
    if not user_ids:
        raise HTTPException(status_code=400, detail="No users found to broadcast to")
    
    # Prepare button if needed
    buttons = None
    if request.include_button and request.button_url:
        buttons = [[{"text": request.button_text, "url": request.button_url}]]
    elif request.include_button:
        bot_username = await get_bot_username(bot_token)
        buttons = [[{"text": request.button_text, "url": f"https://t.me/{bot_username}?start=subscribe"}]]
    
    # Create broadcast record
    broadcast_id = str(uuid.uuid4())
    broadcast_record = {
        "id": broadcast_id,
        "message": request.message,
        "target": request.target,
        "total_users": len(user_ids),
        "sent_count": 0,
        "failed_count": 0,
        "status": "in_progress",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("email", "")
    }
    await db.broadcasts.insert_one(broadcast_record)
    
    # Send in background
    background_tasks.add_task(
        send_broadcast_messages, 
        broadcast_id, 
        list(user_ids), 
        request.message, 
        buttons, 
        bot_token
    )
    
    return {
        "message": f"Broadcast started to {len(user_ids)} users",
        "broadcast_id": broadcast_id,
        "total_users": len(user_ids)
    }

async def send_broadcast_messages(broadcast_id: str, user_ids: list, message: str, buttons: list, bot_token: str):
    """Background task to send broadcast messages"""
    sent_count = 0
    failed_count = 0
    
    for user_id in user_ids:
        try:
            success = await send_telegram_message_with_buttons(user_id, message, buttons, bot_token)
            if success:
                sent_count += 1
            else:
                failed_count += 1
        except Exception as e:
            logger.error(f"Broadcast failed for {user_id}: {e}")
            failed_count += 1
        
        # Rate limiting - wait between messages
        await asyncio.sleep(0.1)
        
        # Update progress every 10 messages
        if (sent_count + failed_count) % 10 == 0:
            await db.broadcasts.update_one(
                {"id": broadcast_id},
                {"$set": {"sent_count": sent_count, "failed_count": failed_count}}
            )
    
    # Final update
    await db.broadcasts.update_one(
        {"id": broadcast_id},
        {"$set": {
            "sent_count": sent_count,
            "failed_count": failed_count,
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    logger.info(f"Broadcast {broadcast_id} completed: {sent_count} sent, {failed_count} failed")

@router.get("/broadcasts")
async def get_broadcasts(user = Depends(get_current_user)):
    """Get all broadcast history"""
    broadcasts = await db.broadcasts.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return broadcasts

@router.get("/broadcasts/{broadcast_id}")
async def get_broadcast(broadcast_id: str, user = Depends(get_current_user)):
    """Get broadcast status"""
    broadcast = await db.broadcasts.find_one({"id": broadcast_id}, {"_id": 0})
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    return broadcast

# ============== PAID POST BROADCAST ==============

@router.post("/paid-posts/{post_id}/broadcast")
async def broadcast_paid_post(post_id: str, data: dict, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    """Broadcast a paid post to all users"""
    paid_post = await db.paid_posts.find_one({"id": post_id, "is_active": True}, {"_id": 0})
    if not paid_post:
        raise HTTPException(status_code=404, detail="Paid post not found")
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot token not configured")
    
    # Get target users
    target = data.get("target", "all")
    user_ids = set()
    
    if target in ["all", "subscribers"]:
        subscribers = await db.subscribers.find({"status": "active"}, {"_id": 0}).to_list(10000)
        for sub in subscribers:
            if sub.get("telegram_user_id"):
                user_ids.add(str(sub["telegram_user_id"]))
    
    if target in ["all", "channel_members"]:
        payments = await db.payments.find({}, {"_id": 0, "telegram_user_id": 1}).to_list(10000)
        for p in payments:
            if p.get("telegram_user_id"):
                user_ids.add(str(p["telegram_user_id"]))
    
    if not user_ids:
        raise HTTPException(status_code=400, detail="No users to broadcast to")
    
    # Create broadcast record
    broadcast_id = str(uuid.uuid4())
    broadcast_record = {
        "id": broadcast_id,
        "type": "paid_post",
        "paid_post_id": post_id,
        "target": target,
        "total_users": len(user_ids),
        "sent_count": 0,
        "failed_count": 0,
        "status": "in_progress",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.broadcasts.insert_one(broadcast_record)
    
    # Send in background
    background_tasks.add_task(
        send_paid_post_broadcast,
        broadcast_id,
        post_id,
        list(user_ids),
        bot_token
    )
    
    return {"broadcast_id": broadcast_id, "total_users": len(user_ids)}

async def send_paid_post_broadcast(broadcast_id: str, post_id: str, user_ids: list, bot_token: str):
    """Background task to send paid post to all users"""
    paid_post = await db.paid_posts.find_one({"id": post_id}, {"_id": 0})
    if not paid_post:
        return
    
    bot_username = await get_bot_username(bot_token)
    price = paid_post.get("price", 0)
    caption = paid_post.get("caption", "")
    
    # Create message
    msg = f"🔒 <b>Exclusive Paid Content!</b>\n\n"
    msg += f"💰 <b>Price:</b> ₹{int(price)}\n\n"
    if caption:
        msg += f"📝 {caption}\n\n"
    msg += "👇 <b>Unlock Now!</b>"
    
    buttons = [[{
        "text": f"🔓 Unlock - ₹{int(price)}",
        "url": f"https://t.me/{bot_username}?start=unlock_{post_id}"
    }]]
    
    sent_count = 0
    failed_count = 0
    
    for user_id in user_ids:
        try:
            # Try to send blurred photo if available
            if paid_post.get("blurred_file_id"):
                await send_telegram_photo(user_id, paid_post["blurred_file_id"], msg, bot_token, {"inline_keyboard": buttons})
            else:
                await send_telegram_message_with_buttons(user_id, msg, buttons, bot_token)
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send paid post broadcast to {user_id}: {e}")
            failed_count += 1
        
        await asyncio.sleep(0.1)  # Rate limiting
    
    # Update broadcast status
    await db.broadcasts.update_one(
        {"id": broadcast_id},
        {"$set": {
            "sent_count": sent_count,
            "failed_count": failed_count,
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat()
        }}
    )


# ============== COUPON/DISCOUNT APIs ==============

@router.get("/coupons")
async def get_coupons(user = Depends(get_current_user)):
    """Get all coupons"""
    coupons = await db.coupons.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return coupons

@router.post("/coupons")
async def create_coupon(coupon: dict, user = Depends(get_current_user)):
    """Create a new coupon"""
    coupon_data = {
        "id": str(uuid.uuid4()),
        "code": coupon.get("code", "").upper().strip(),
        "discount_type": coupon.get("discount_type", "percentage"),
        "discount_value": float(coupon.get("discount_value", 0)),
        "min_purchase": float(coupon.get("min_purchase", 0)),
        "max_uses": int(coupon.get("max_uses", 0)),
        "used_count": 0,
        "valid_from": coupon.get("valid_from"),
        "valid_until": coupon.get("valid_until"),
        "applicable_plans": coupon.get("applicable_plans", []),
        "is_active": coupon.get("is_active", True),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Check if code already exists
    existing = await db.coupons.find_one({"code": coupon_data["code"]})
    if existing:
        raise HTTPException(status_code=400, detail="Coupon code already exists")
    
    await db.coupons.insert_one(coupon_data)
    return {"message": "Coupon created", "coupon": coupon_data}

@router.put("/coupons/{coupon_id}")
async def update_coupon(coupon_id: str, coupon: dict, user = Depends(get_current_user)):
    """Update a coupon"""
    await db.coupons.update_one(
        {"id": coupon_id},
        {"$set": {
            "code": coupon.get("code", "").upper().strip(),
            "discount_type": coupon.get("discount_type"),
            "discount_value": float(coupon.get("discount_value", 0)),
            "min_purchase": float(coupon.get("min_purchase", 0)),
            "max_uses": int(coupon.get("max_uses", 0)),
            "valid_from": coupon.get("valid_from"),
            "valid_until": coupon.get("valid_until"),
            "applicable_plans": coupon.get("applicable_plans", []),
            "is_active": coupon.get("is_active", True)
        }}
    )
    return {"message": "Coupon updated"}

@router.delete("/coupons/{coupon_id}")
async def delete_coupon(coupon_id: str, user = Depends(get_current_user)):
    """Delete a coupon"""
    await db.coupons.delete_one({"id": coupon_id})
    return {"message": "Coupon deleted"}

@router.post("/coupons/validate")
async def validate_coupon(data: dict):
    """Validate a coupon code (public endpoint for bot)"""
    code = data.get("code", "").upper().strip()
    plan_id = data.get("plan_id")
    amount = float(data.get("amount", 0))
    
    coupon = await db.coupons.find_one({"code": code, "is_active": True}, {"_id": 0})
    if not coupon:
        return {"valid": False, "error": "Invalid coupon code"}
    
    # Check expiry
    if coupon.get("valid_until"):
        expiry = datetime.fromisoformat(coupon["valid_until"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expiry:
            return {"valid": False, "error": "Coupon expired"}
    
    # Check usage limit
    if coupon.get("max_uses", 0) > 0 and coupon.get("used_count", 0) >= coupon["max_uses"]:
        return {"valid": False, "error": "Coupon usage limit reached"}
    
    # Check minimum purchase
    if amount < coupon.get("min_purchase", 0):
        return {"valid": False, "error": f"Minimum purchase ₹{coupon['min_purchase']} required"}
    
    # Check applicable plans
    if coupon.get("applicable_plans") and plan_id not in coupon["applicable_plans"]:
        return {"valid": False, "error": "Coupon not valid for this plan"}
    
    # Calculate discount
    if coupon["discount_type"] == "percentage":
        discount = (amount * coupon["discount_value"]) / 100
    else:
        discount = coupon["discount_value"]
    
    final_amount = max(0, amount - discount)
    
    return {
        "valid": True,
        "discount": discount,
        "final_amount": final_amount,
        "coupon": coupon
    }


# ============== USER NOTES APIs ==============

@router.get("/users/{user_id}/notes")
async def get_user_notes(user_id: str, user = Depends(get_current_user)):
    """Get notes for a user"""
    notes = await db.user_notes.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return notes

@router.post("/users/{user_id}/notes")
async def add_user_note(user_id: str, data: dict, user = Depends(get_current_user)):
    """Add a note to user"""
    note_data = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "note": data.get("note", ""),
        "added_by": user.get("email", "admin"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_notes.insert_one(note_data)
    return {"message": "Note added", "note": note_data}

@router.delete("/users/{user_id}/notes/{note_id}")
async def delete_user_note(user_id: str, note_id: str, user = Depends(get_current_user)):
    """Delete a user note"""
    await db.user_notes.delete_one({"id": note_id, "user_id": user_id})
    return {"message": "Note deleted"}


# ============== USER TAGS APIs ==============

@router.get("/tags")
async def get_tags(user = Depends(get_current_user)):
    """Get all tags"""
    tags = await db.user_tags.find({}, {"_id": 0}).to_list(100)
    return tags

@router.post("/tags")
async def create_tag(data: dict, user = Depends(get_current_user)):
    """Create a new tag"""
    tag_data = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", ""),
        "color": data.get("color", "blue"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_tags.insert_one(tag_data)
    return {"message": "Tag created", "tag": tag_data}

@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: str, user = Depends(get_current_user)):
    """Delete a tag"""
    await db.user_tags.delete_one({"id": tag_id})
    # Remove tag from all users
    await db.bot_users.update_many({}, {"$pull": {"tags": tag_id}})
    return {"message": "Tag deleted"}

@router.post("/users/{user_id}/tags")
async def add_tag_to_user(user_id: str, data: dict, user = Depends(get_current_user)):
    """Add tag to user"""
    tag_id = data.get("tag_id")
    await db.bot_users.update_one(
        {"telegram_user_id": user_id},
        {"$addToSet": {"tags": tag_id}}
    )
    return {"message": "Tag added to user"}

@router.delete("/users/{user_id}/tags/{tag_id}")
async def remove_tag_from_user(user_id: str, tag_id: str, user = Depends(get_current_user)):
    """Remove tag from user"""
    await db.bot_users.update_one(
        {"telegram_user_id": user_id},
        {"$pull": {"tags": tag_id}}
    )
    return {"message": "Tag removed from user"}


# ============== BLOCKED USERS APIs ==============

@router.get("/blocked-users")
async def get_blocked_users(user = Depends(get_current_user)):
    """Get all blocked users"""
    blocked = await db.blocked_users.find({}, {"_id": 0}).sort("blocked_at", -1).to_list(1000)
    return blocked

@router.post("/users/{user_id}/block")
async def block_user(user_id: str, data: dict, user = Depends(get_current_user)):
    """Block a user"""
    # Check if already blocked
    existing = await db.blocked_users.find_one({"telegram_user_id": user_id})
    if existing:
        raise HTTPException(status_code=400, detail="User already blocked")
    
    # Get user info
    bot_user = await db.bot_users.find_one({"telegram_user_id": user_id}, {"_id": 0})
    
    blocked_data = {
        "id": str(uuid.uuid4()),
        "telegram_user_id": user_id,
        "telegram_username": bot_user.get("username", "") if bot_user else "",
        "reason": data.get("reason", ""),
        "blocked_by": user.get("email", "admin"),
        "blocked_at": datetime.now(timezone.utc).isoformat()
    }
    await db.blocked_users.insert_one(blocked_data)
    return {"message": "User blocked", "blocked": blocked_data}

@router.delete("/users/{user_id}/block")
async def unblock_user(user_id: str, user = Depends(get_current_user)):
    """Unblock a user"""
    await db.blocked_users.delete_one({"telegram_user_id": user_id})
    return {"message": "User unblocked"}


# ============== REFERRAL APIs ==============

@router.get("/referrals")
async def get_referrals(user = Depends(get_current_user)):
    """Get all referrals"""
    referrals = await db.referrals.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return referrals

@router.get("/referrals/settings")
async def get_referral_settings(user = Depends(get_current_user)):
    """Get referral program settings"""
    settings = await db.referral_settings.find_one({"id": "referral_settings"}, {"_id": 0})
    if not settings:
        settings = {
            "id": "referral_settings",
            "enabled": True,
            "referrer_reward_type": "discount",
            "referrer_reward_value": 10,
            "referee_reward_type": "discount",
            "referee_reward_value": 10
        }
        await db.referral_settings.insert_one(settings)
    return settings

@router.put("/referrals/settings")
async def update_referral_settings(data: dict, user = Depends(get_current_user)):
    """Update referral program settings"""
    await db.referral_settings.update_one(
        {"id": "referral_settings"},
        {"$set": {
            "enabled": data.get("enabled", True),
            "referrer_reward_type": data.get("referrer_reward_type", "discount"),
            "referrer_reward_value": float(data.get("referrer_reward_value", 10)),
            "referee_reward_type": data.get("referee_reward_type", "discount"),
            "referee_reward_value": float(data.get("referee_reward_value", 10))
        }},
        upsert=True
    )
    return {"message": "Referral settings updated"}

@router.post("/referrals/validate")
async def validate_referral(data: dict):
    """Validate a referral code (public endpoint for bot)"""
    code = data.get("code", "").upper().strip()
    user_id = data.get("user_id")
    
    referral = await db.referrals.find_one({"referral_code": code, "is_active": True}, {"_id": 0})
    if not referral:
        return {"valid": False, "error": "Invalid referral code"}
    
    # Can't use own referral code
    if referral["referrer_id"] == user_id:
        return {"valid": False, "error": "Can't use your own referral code"}
    
    # Check if user already used a referral
    if user_id in referral.get("referred_users", []):
        return {"valid": False, "error": "You've already used a referral code"}
    
    settings = await db.referral_settings.find_one({"id": "referral_settings"}, {"_id": 0})
    
    return {
        "valid": True,
        "referral": referral,
        "referee_reward": {
            "type": settings.get("referee_reward_type", "discount") if settings else "discount",
            "value": settings.get("referee_reward_value", 10) if settings else 10
        }
    }


# ============== SCHEDULED BROADCAST APIs ==============

@router.get("/scheduled-broadcasts")
async def get_scheduled_broadcasts(user = Depends(get_current_user)):
    """Get all scheduled broadcasts"""
    broadcasts = await db.scheduled_broadcasts.find({}, {"_id": 0}).sort("scheduled_at", 1).to_list(1000)
    return broadcasts

@router.post("/scheduled-broadcasts")
async def create_scheduled_broadcast(data: dict, user = Depends(get_current_user)):
    """Create a scheduled broadcast"""
    broadcast_data = {
        "id": str(uuid.uuid4()),
        "message": data.get("message", ""),
        "target_segment": data.get("target_segment", "all"),
        "scheduled_at": data.get("scheduled_at"),
        "status": "pending",
        "sent_count": 0,
        "created_by": user.get("email", "admin"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.scheduled_broadcasts.insert_one(broadcast_data)
    return {"message": "Broadcast scheduled", "broadcast": broadcast_data}

@router.delete("/scheduled-broadcasts/{broadcast_id}")
async def cancel_scheduled_broadcast(broadcast_id: str, user = Depends(get_current_user)):
    """Cancel a scheduled broadcast"""
    await db.scheduled_broadcasts.update_one(
        {"id": broadcast_id},
        {"$set": {"status": "cancelled"}}
    )
    return {"message": "Broadcast cancelled"}


# ============== FAQ / AUTO-REPLY APIs ==============

@router.get("/faqs")
async def get_faqs(user = Depends(get_current_user)):
    """Get all FAQs"""
    faqs = await db.faqs.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return faqs

@router.post("/faqs")
async def create_faq(data: dict, user = Depends(get_current_user)):
    """Create a new FAQ"""
    faq_data = {
        "id": str(uuid.uuid4()),
        "keywords": [k.strip().lower() for k in data.get("keywords", "").split(",") if k.strip()],
        "response": data.get("response", ""),
        "is_active": data.get("is_active", True),
        "usage_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.faqs.insert_one(faq_data)
    return {"message": "FAQ created", "faq": faq_data}

@router.put("/faqs/{faq_id}")
async def update_faq(faq_id: str, data: dict, user = Depends(get_current_user)):
    """Update a FAQ"""
    await db.faqs.update_one(
        {"id": faq_id},
        {"$set": {
            "keywords": [k.strip().lower() for k in data.get("keywords", "").split(",") if k.strip()],
            "response": data.get("response", ""),
            "is_active": data.get("is_active", True)
        }}
    )
    return {"message": "FAQ updated"}

@router.delete("/faqs/{faq_id}")
async def delete_faq(faq_id: str, user = Depends(get_current_user)):
    """Delete a FAQ"""
    await db.faqs.delete_one({"id": faq_id})
    return {"message": "FAQ deleted"}


# ============== VIDEO CALL BOOKINGS APIs ==============

@router.get("/video-calls")
async def get_video_call_bookings(user = Depends(get_current_user)):
    """Get all video call bookings"""
    bookings = await db.video_call_bookings.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return bookings

@router.put("/video-calls/{booking_id}")
async def update_video_call_booking(booking_id: str, data: dict, user = Depends(get_current_user)):
    """Update a video call booking (confirm, add meeting link, etc.)"""
    update_data = {}
    
    if "status" in data:
        update_data["status"] = data["status"]
    if "meeting_link" in data:
        update_data["meeting_link"] = data["meeting_link"]
    if "notes" in data:
        update_data["notes"] = data["notes"]
    
    if update_data:
        await db.video_call_bookings.update_one(
            {"id": booking_id},
            {"$set": update_data}
        )
        
        # If confirmed, send notification to user
        if data.get("status") == "confirmed":
            booking = await db.video_call_bookings.find_one({"id": booking_id}, {"_id": 0})
            if booking:
                settings = await get_bot_settings()
                bot_token = settings.get("telegram_bot_token", "")
                
                msg = "✅ <b>Video Call Confirmed!</b>\n\n"
                msg += f"📅 Date: <b>{booking.get('scheduled_date')}</b>\n"
                msg += f"🕐 Time: <b>{booking.get('scheduled_time')}</b>\n"
                msg += f"⏱ Duration: <b>{booking.get('duration_minutes', 30)} minutes</b>\n"
                
                if data.get("meeting_link"):
                    msg += f"\n🔗 Meeting Link:\n{data['meeting_link']}"
                
                await send_telegram_message(booking.get("telegram_user_id"), msg, bot_token)
    
    return {"message": "Booking updated"}

@router.delete("/video-calls/{booking_id}")
async def delete_video_call_booking(booking_id: str, user = Depends(get_current_user)):
    """Delete a video call booking"""
    await db.video_call_bookings.delete_one({"id": booking_id})
    return {"message": "Booking deleted"}

@router.get("/video-calls/queue")
async def get_video_call_queue(user = Depends(get_current_user)):
    """Get video call queue - who's waiting"""
    # Get pending/waiting bookings sorted by creation time
    queue = await db.video_call_bookings.find(
        {"status": {"$in": ["pending", "paid", "waiting"]}},
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    
    # Get current active call
    active_call = await db.video_call_bookings.find_one(
        {"status": "in_progress"},
        {"_id": 0}
    )
    
    return {
        "queue": queue,
        "queue_length": len(queue),
        "active_call": active_call
    }

@router.post("/video-calls/{booking_id}/start")
async def start_video_call(booking_id: str, user = Depends(get_current_user)):
    """Start a video call (marks as in_progress)"""
    booking = await db.video_call_bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Check if another call is already in progress
    active = await db.video_call_bookings.find_one({"status": "in_progress"}, {"_id": 0})
    if active:
        raise HTTPException(status_code=400, detail="Another call is already in progress")
    
    await db.video_call_bookings.update_one(
        {"id": booking_id},
        {"$set": {"status": "in_progress", "started_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Notify user
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    msg = "📞 <b>Your video call is starting NOW!</b>\n\n"
    msg += "👆 Check the meeting link above and join!"
    await send_telegram_message(booking.get("telegram_user_id"), msg, bot_token)
    
    return {"message": "Call started"}

@router.post("/video-calls/{booking_id}/end")
async def end_video_call(booking_id: str, user = Depends(get_current_user)):
    """End a video call and notify next in queue"""
    await db.video_call_bookings.update_one(
        {"id": booking_id},
        {"$set": {"status": "completed", "ended_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Notify next in queue
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    next_in_queue = await db.video_call_bookings.find_one(
        {"status": {"$in": ["pending", "paid", "waiting"]}},
        {"_id": 0},
        sort=[("created_at", 1)]
    )
    
    if next_in_queue:
        msg = "⏰ <b>You're Next!</b>\n\n"
        msg += "🎯 Get ready! Your video call will start soon.\n"
        msg += "📱 Make sure you have good internet connection."
        await send_telegram_message(next_in_queue.get("telegram_user_id"), msg, bot_token)
    
    return {"message": "Call ended", "next_in_queue": next_in_queue}

# ============== RENEWAL BROADCAST ==============

@router.post("/renewal-broadcast")
async def send_renewal_broadcast(data: dict, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    """Send renewal reminder to expired/expiring subscribers"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot token not configured")
    
    target = data.get("target", "expired")  # expired, expiring_soon, all
    message = data.get("message", "")
    video_note_file_id = data.get("video_note_file_id")  # Optional video note
    discount_percent = data.get("discount_percent", 0)
    
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    
    user_ids = set()
    
    if target in ["expired", "all"]:
        # Get expired subscribers
        expired = await db.subscribers.find(
            {"status": {"$in": ["expired", "cancelled"]}},
            {"_id": 0}
        ).to_list(10000)
        for sub in expired:
            if sub.get("telegram_user_id"):
                user_ids.add(str(sub["telegram_user_id"]))
    
    if target in ["expiring_soon", "all"]:
        # Get subscribers expiring in next 3 days
        three_days_later = (now + timedelta(days=3)).isoformat()
        expiring = await db.subscribers.find(
            {"status": "active", "end_time": {"$lte": three_days_later}},
            {"_id": 0}
        ).to_list(10000)
        for sub in expiring:
            if sub.get("telegram_user_id"):
                user_ids.add(str(sub["telegram_user_id"]))
    
    if not user_ids:
        return {"message": "No users to send renewal to", "count": 0}
    
    # Create broadcast record
    broadcast_id = str(uuid.uuid4())
    broadcast_record = {
        "id": broadcast_id,
        "type": "renewal",
        "target": target,
        "message": message,
        "total_users": len(user_ids),
        "sent_count": 0,
        "failed_count": 0,
        "status": "in_progress",
        "created_at": now.isoformat()
    }
    await db.broadcasts.insert_one(broadcast_record)
    
    # Send in background
    background_tasks.add_task(
        send_renewal_messages,
        broadcast_id,
        list(user_ids),
        message,
        discount_percent,
        video_note_file_id,
        bot_token
    )
    
    return {"broadcast_id": broadcast_id, "total_users": len(user_ids)}

async def send_renewal_messages(broadcast_id: str, user_ids: list, message: str, discount_percent: int, video_note_file_id: str, bot_token: str):
    """Background task to send renewal messages"""
    bot_username = await get_bot_username(bot_token)
    
    sent_count = 0
    failed_count = 0
    
    for user_id in user_ids:
        try:
            # Build renewal message
            msg = "🔔 <b>Time to Renew!</b>\n\n"
            if message:
                msg += f"{message}\n\n"
            else:
                msg += "Your subscription has expired or is about to expire.\n"
                msg += "Don't miss out on exclusive content!\n\n"
            
            if discount_percent > 0:
                msg += f"🎁 <b>Special Offer: {discount_percent}% OFF!</b>\n\n"
            
            msg += "👇 <b>Renew Now!</b>"
            
            buttons = [[{
                "text": "🔄 Renew Subscription",
                "url": f"https://t.me/{bot_username}?start=subscribe"
            }]]
            
            # Send video note if available
            if video_note_file_id:
                try:
                    async with httpx.AsyncClient() as http_client:
                        await http_client.post(
                            f"https://api.telegram.org/bot{bot_token}/sendVideoNote",
                            json={"chat_id": user_id, "video_note": video_note_file_id}
                        )
                except Exception:
                    pass
            
            await send_telegram_message_with_buttons(user_id, msg, buttons, bot_token)
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send renewal to {user_id}: {e}")
            failed_count += 1
        
        await asyncio.sleep(0.1)
    
    await db.broadcasts.update_one(
        {"id": broadcast_id},
        {"$set": {
            "sent_count": sent_count,
            "failed_count": failed_count,
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat()
        }}
    )


# ============== CREATOR APIs ==============

@router.get("/creators")
async def get_creators(user = Depends(get_current_user)):
    """Get all creators"""
    creators = await db.creators.find({}, {"_id": 0}).to_list(100)
    return creators

@router.post("/creators")
async def create_creator(data: dict, user = Depends(get_current_user)):
    """Create a new creator (Admin only)"""
    creator = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", ""),
        "telegram_user_id": data.get("telegram_user_id", ""),
        "telegram_username": data.get("telegram_username", ""),
        "email": data.get("email", ""),
        "role": "creator",
        "permissions": data.get("permissions", ["live_manage", "superchat_view"]),
        "revenue_share": float(data.get("revenue_share", 0)),
        "total_earnings": 0,
        "is_active": True,
        "created_by": user.get("email", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.creators.insert_one(creator)
    return {"message": "Creator created", "id": creator["id"]}

@router.put("/creators/{creator_id}")
async def update_creator(creator_id: str, data: dict, user = Depends(get_current_user)):
    """Update creator details"""
    update_data = {}
    for field in ["name", "telegram_user_id", "telegram_username", "email", "permissions", "revenue_share", "is_active"]:
        if field in data:
            update_data[field] = data[field]
    
    await db.creators.update_one({"id": creator_id}, {"$set": update_data})
    return {"message": "Creator updated"}

@router.delete("/creators/{creator_id}")
async def delete_creator(creator_id: str, user = Depends(get_current_user)):
    """Delete a creator"""
    await db.creators.delete_one({"id": creator_id})
    return {"message": "Creator deleted"}

@router.post("/creators/link-telegram")
async def link_creator_telegram(data: dict, user = Depends(get_current_user)):
    """Link Telegram account to creator by username or user_id"""
    creator_id = data.get("creator_id")
    telegram_username = data.get("telegram_username", "").replace("@", "")
    telegram_user_id = data.get("telegram_user_id", "")
    
    if not creator_id:
        raise HTTPException(status_code=400, detail="Creator ID required")
    
    update_data = {}
    if telegram_username:
        update_data["telegram_username"] = telegram_username
    if telegram_user_id:
        update_data["telegram_user_id"] = telegram_user_id
    
    await db.creators.update_one({"id": creator_id}, {"$set": update_data})
    return {"message": "Telegram account linked"}

async def is_admin_or_creator(telegram_user_id: str, telegram_username: str = "") -> bool:
    """Check if user is admin, creator, or telegram admin"""
    # Check telegram_admins collection
    tg_admin = await db.telegram_admins.find_one({
        "$or": [
            {"telegram_user_id": str(telegram_user_id)},
            {"telegram_username": telegram_username}
        ],
        "is_active": True
    }, {"_id": 0})
    
    if tg_admin:
        return True
    
    # Check creators collection
    creator = await db.creators.find_one({
        "$or": [
            {"telegram_user_id": str(telegram_user_id)},
            {"telegram_username": telegram_username}
        ],
        "is_active": True
    }, {"_id": 0})
    
    if creator:
        return True
    
    # Check users collection for admin
    admin_user = await db.users.find_one({
        "$or": [
            {"telegram_user_id": str(telegram_user_id)},
            {"telegram_username": telegram_username}
        ],
        "role": {"$in": ["admin", "super_admin"]}
    }, {"_id": 0})
    
    return admin_user is not None


# ============== TELEGRAM ADMIN MANAGEMENT ==============

@router.get("/telegram-admins")
async def get_telegram_admins(user = Depends(get_current_user)):
    """Get all Telegram admins"""
    admins = await db.telegram_admins.find({}, {"_id": 0}).to_list(100)
    return admins

@router.post("/telegram-admins")
async def create_telegram_admin(data: dict, user = Depends(get_current_user)):
    """Create a new Telegram admin who can manage the bot"""
    name = data.get("name", "")
    telegram_user_id = str(data.get("telegram_user_id", "")).strip()
    telegram_username = data.get("telegram_username", "").strip().replace("@", "")
    role = data.get("role", "admin")
    permissions = data.get("permissions", ["manage_bot", "verify_payments", "broadcast", "live_manage"])
    
    if not telegram_user_id and not telegram_username:
        raise HTTPException(status_code=400, detail="Telegram User ID or Username required")
    
    # Check if already exists
    query_conditions = []
    if telegram_user_id:
        query_conditions.append({"telegram_user_id": telegram_user_id})
    if telegram_username:
        query_conditions.append({"telegram_username": telegram_username})
    
    existing = await db.telegram_admins.find_one({"$or": query_conditions})
    if existing:
        raise HTTPException(status_code=400, detail="This Telegram user is already an admin")
    
    admin_doc = {
        "id": str(uuid.uuid4()),
        "name": name,
        "telegram_user_id": telegram_user_id,
        "telegram_username": telegram_username,
        "role": role,
        "permissions": permissions,
        "is_active": True,
        "created_by": user.get("email", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.telegram_admins.insert_one(admin_doc)
    
    # Send notification to the new admin on Telegram
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if bot_token and telegram_user_id:
        msg = "🎉 <b>You've been added as a Bot Admin!</b>\n\n"
        msg += f"👤 Name: <b>{name}</b>\n"
        msg += f"🔑 Role: <b>{role.title()}</b>\n\n"
        msg += "<b>Your permissions:</b>\n"
        perm_labels = {
            "manage_bot": "🤖 Manage Bot",
            "verify_payments": "💳 Verify Payments",
            "broadcast": "📢 Send Broadcasts",
            "live_manage": "🎬 Manage Live Streams",
            "superchat_view": "💬 View Super Chats",
            "add_subscribers": "👥 Add Subscribers",
        }
        for p in permissions:
            msg += f"  {perm_labels.get(p, p)}\n"
        msg += "\nUse /admin to see available admin commands."
        await send_telegram_message(telegram_user_id, msg, bot_token)
    
    return {"message": "Telegram admin created", "id": admin_doc["id"]}

@router.put("/telegram-admins/{admin_id}")
async def update_telegram_admin(admin_id: str, data: dict, user = Depends(get_current_user)):
    """Update a Telegram admin"""
    update_data = {}
    for field in ["name", "telegram_user_id", "telegram_username", "role", "permissions", "is_active"]:
        if field in data:
            update_data[field] = data[field]
    
    await db.telegram_admins.update_one({"id": admin_id}, {"$set": update_data})
    return {"message": "Telegram admin updated"}

@router.delete("/telegram-admins/{admin_id}")
async def delete_telegram_admin(admin_id: str, user = Depends(get_current_user)):
    """Remove a Telegram admin"""
    # Get admin info before deleting
    admin = await db.telegram_admins.find_one({"id": admin_id}, {"_id": 0})
    await db.telegram_admins.delete_one({"id": admin_id})
    
    # Notify removed admin
    if admin:
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
        if bot_token and admin.get("telegram_user_id"):
            msg = "⚠️ Your bot admin access has been revoked."
            await send_telegram_message(admin["telegram_user_id"], msg, bot_token)
    
    return {"message": "Telegram admin removed"}


# ============== LIVE STREAM APIs ==============

@router.get("/live/sessions")
async def get_live_sessions(user = Depends(get_current_user)):
    """Get all live sessions"""
    sessions = await db.live_sessions.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return sessions

@router.post("/live/sessions")
async def create_live_session(data: dict, user = Depends(get_current_user)):
    """Create a new live session"""
    session = {
        "id": str(uuid.uuid4()),
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "scheduled_date": data.get("scheduled_date", ""),
        "scheduled_time": data.get("scheduled_time", ""),
        "price": float(data.get("price", 0)),
        "max_viewers": int(data.get("max_viewers", 100)),
        "stream_link": data.get("stream_link", ""),
        "group_id": data.get("group_id", ""),  # Telegram group where live will happen
        "superchat_enabled": data.get("superchat_enabled", True),
        "superchat_min_amount": float(data.get("superchat_min_amount", 10)),
        "status": "scheduled",  # scheduled, live, ended
        "tickets_sold": 0,
        "superchat_total": 0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.live_sessions.insert_one(session)
    logger.info(f"Created live session: {session['title']}")
    return {"message": "Session created", "id": session["id"]}

@router.post("/live/sessions/{session_id}/announce")
async def announce_live_session(session_id: str, user = Depends(get_current_user)):
    """Announce live session to channel/group"""
    session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    channel_id = settings.get("telegram_channel_id", "")
    bot_username = await get_bot_username(bot_token)
    
    # Create announcement message
    msg = "🔴 <b>LIVE SESSION ANNOUNCEMENT!</b>\n\n"
    msg += f"📺 <b>{session.get('title')}</b>\n\n"
    if session.get('description'):
        msg += f"📝 {session['description']}\n\n"
    msg += f"📅 <b>Date:</b> {session.get('scheduled_date')}\n"
    msg += f"🕐 <b>Time:</b> {session.get('scheduled_time')}\n"
    msg += f"💰 <b>Ticket Price:</b> ₹{int(session.get('price', 0))}\n\n"
    if session.get('superchat_enabled'):
        msg += f"💬 <b>Superchat Enabled!</b> (Min ₹{int(session.get('superchat_min_amount', 10))})\n\n"
    msg += "👇 <b>Get Your Ticket Now!</b>"
    
    buttons = [[{
        "text": f"🎫 Buy Ticket - ₹{int(session.get('price', 0))}",
        "url": f"https://t.me/{bot_username}?start=live_{session_id}"
    }]]
    
    # Post to channel
    await send_telegram_message_with_buttons(channel_id, msg, buttons, bot_token)
    
    # Also post to group if specified
    if session.get('group_id'):
        await send_telegram_message_with_buttons(session['group_id'], msg, buttons, bot_token)
    
    return {"message": "Announcement sent"}

@router.post("/live/sessions/{session_id}/go-live")
async def go_live(session_id: str, data: dict, user = Depends(get_current_user)):
    """Start live session and notify all ticket holders"""
    session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    # Update stream link if provided
    update_data = {"status": "live", "started_at": datetime.now(timezone.utc).isoformat()}
    if data.get("stream_link"):
        update_data["stream_link"] = data["stream_link"]
    
    await db.live_sessions.update_one({"id": session_id}, {"$set": update_data})
    
    # Get updated session
    session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
    
    # Notify all approved ticket holders
    approved_tickets = await db.live_tickets.find({
        "session_id": session_id,
        "status": "approved"
    }, {"_id": 0}).to_list(1000)
    
    bot_username = await get_bot_username(bot_token)
    
    for ticket in approved_tickets:
        msg = "🔴 <b>WE ARE LIVE NOW!</b>\n\n"
        msg += f"📺 <b>{session.get('title')}</b>\n\n"
        
        if session.get("stream_link"):
            msg += f"🔗 <b>Join here:</b>\n{session['stream_link']}\n\n"
        
        if session.get("superchat_enabled"):
            msg += f"💬 Send Superchat: /superchat {session_id} <amount> <message>\n"
            msg += f"📢 Min Amount: ₹{int(session.get('superchat_min_amount', 10))}\n\n"
        
        msg += "🎉 Enjoy the stream!"
        
        # Add superchat button
        if session.get("superchat_enabled"):
            buttons = [[{
                "text": "💬 Send Superchat",
                "url": f"https://t.me/{bot_username}?start=superchat_{session_id}"
            }]]
            await send_telegram_message_with_buttons(ticket.get("telegram_user_id"), msg, buttons, bot_token)
        else:
            await send_telegram_message(ticket.get("telegram_user_id"), msg, bot_token)
    
    return {"message": "Live started", "notified": len(approved_tickets)}

@router.post("/live/sessions/{session_id}/start-countdown")
async def start_countdown_timer(session_id: str, data: dict, user = Depends(get_current_user)):
    """Post countdown timer to group - 30 mins before live"""
    session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    channel_id = settings.get("telegram_channel_id", "")
    bot_username = await get_bot_username(bot_token)
    
    # Get target group (from session or default channel)
    target_group = data.get("group_id") or session.get("group_id") or channel_id
    minutes_remaining = data.get("minutes", 30)
    
    # Create countdown message
    msg = "⏰ <b>LIVE STARTING SOON!</b>\n\n"
    msg += "━━━━━━━━━━━━━━━\n"
    msg += f"📺 <b>{session.get('title')}</b>\n\n"
    msg += f"🕐 <b>Starting in: {minutes_remaining} minutes!</b>\n"
    msg += "━━━━━━━━━━━━━━━\n\n"
    
    if session.get('description'):
        msg += f"📝 {session['description']}\n\n"
    
    msg += f"💰 <b>Ticket Price:</b> ₹{int(session.get('price', 0))}\n"
    
    if session.get('superchat_enabled'):
        msg += f"💬 <b>Superchat:</b> Enabled!\n\n"
    
    msg += "👇 <b>Get your ticket now before it starts!</b>"
    
    buttons = [
        [{
            "text": f"🎫 Buy Ticket - ₹{int(session.get('price', 0))}",
            "url": f"https://t.me/{bot_username}?start=live_{session_id}"
        }],
        [{
            "text": "🔔 Subscribe for Updates",
            "url": f"https://t.me/{bot_username}?start=subscribe"
        }]
    ]
    
    # Post to group
    result = await send_telegram_message_with_buttons(target_group, msg, buttons, bot_token)
    
    # Store message_id so we can update it later
    if result:
        await db.live_sessions.update_one(
            {"id": session_id},
            {"$set": {
                "countdown_message_id": result.get("message_id"),
                "countdown_chat_id": target_group,
                "countdown_started_at": datetime.now(timezone.utc).isoformat()
            }}
        )
    
    return {"message": "Countdown started", "group_id": target_group}

@router.post("/live/sessions/{session_id}/update-countdown")
async def update_countdown_timer(session_id: str, data: dict, user = Depends(get_current_user)):
    """Update countdown timer message"""
    session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not session.get("countdown_message_id"):
        raise HTTPException(status_code=400, detail="No countdown active")
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    bot_username = await get_bot_username(bot_token)
    
    minutes_remaining = data.get("minutes", 10)
    
    # Create updated message
    if minutes_remaining <= 0:
        msg = "🔴 <b>WE ARE LIVE NOW!</b>\n\n"
        msg += "━━━━━━━━━━━━━━━\n"
        msg += f"📺 <b>{session.get('title')}</b>\n"
        msg += "━━━━━━━━━━━━━━━\n\n"
        msg += "🎉 <b>Join the stream now!</b>"
        
        buttons = [[{
            "text": "🔴 JOIN LIVE NOW",
            "url": session.get('stream_link') or f"https://t.me/{bot_username}?start=live_{session_id}"
        }]]
    else:
        msg = "⏰ <b>LIVE STARTING SOON!</b>\n\n"
        msg += "━━━━━━━━━━━━━━━\n"
        msg += f"📺 <b>{session.get('title')}</b>\n\n"
        
        if minutes_remaining >= 60:
            hours = minutes_remaining // 60
            mins = minutes_remaining % 60
            time_str = f"{hours}h {mins}m" if mins > 0 else f"{hours}h"
        else:
            time_str = f"{minutes_remaining} minutes"
        
        msg += f"🕐 <b>Starting in: {time_str}!</b>\n"
        msg += "━━━━━━━━━━━━━━━\n\n"
        msg += f"💰 Ticket: ₹{int(session.get('price', 0))}\n\n"
        msg += "👇 <b>Get your ticket!</b>"
        
        buttons = [
            [{
                "text": f"🎫 Buy Ticket - ₹{int(session.get('price', 0))}",
                "url": f"https://t.me/{bot_username}?start=live_{session_id}"
            }],
            [{
                "text": "🔔 Subscribe",
                "url": f"https://t.me/{bot_username}?start=subscribe"
            }]
        ]
    
    # Edit the countdown message
    try:
        async with httpx.AsyncClient() as http_client:
            await http_client.post(
                f"https://api.telegram.org/bot{bot_token}/editMessageText",
                json={
                    "chat_id": session.get("countdown_chat_id"),
                    "message_id": session.get("countdown_message_id"),
                    "text": msg,
                    "parse_mode": "HTML",
                    "reply_markup": {"inline_keyboard": buttons}
                }
            )
    except Exception as e:
        logger.error(f"Failed to update countdown: {e}")
    
    return {"message": "Countdown updated"}

@router.put("/live/sessions/{session_id}")
async def update_live_session(session_id: str, data: dict, user = Depends(get_current_user)):
    """Update a live session"""
    update_data = {}
    for key in ["title", "description", "scheduled_date", "scheduled_time", "price", "max_viewers", "stream_link", "status"]:
        if key in data:
            update_data[key] = data[key]
    
    if update_data:
        await db.live_sessions.update_one({"id": session_id}, {"$set": update_data})
        
        # If going live, notify all approved ticket holders
        if data.get("status") == "live":
            session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
            if session:
                settings = await get_bot_settings()
                bot_token = settings.get("telegram_bot_token", "")
                
                # Get all approved tickets for this session
                approved_tickets = await db.live_tickets.find({
                    "session_id": session_id,
                    "status": "approved"
                }, {"_id": 0}).to_list(1000)
                
                for ticket in approved_tickets:
                    msg = "🔴 <b>LIVE NOW!</b>\n\n"
                    msg += f"📺 <b>{session.get('title')}</b>\n\n"
                    if session.get("stream_link"):
                        msg += f"🔗 Join here:\n{session['stream_link']}"
                    else:
                        msg += "Stream link coming soon..."
                    
                    await send_telegram_message(ticket.get("telegram_user_id"), msg, bot_token)
    
    return {"message": "Session updated"}

@router.delete("/live/sessions/{session_id}")
async def delete_live_session(session_id: str, user = Depends(get_current_user)):
    """Delete a live session"""
    await db.live_sessions.delete_one({"id": session_id})
    await db.live_tickets.delete_many({"session_id": session_id})
    return {"message": "Session deleted"}

@router.get("/live/tickets")
async def get_live_tickets(user = Depends(get_current_user)):
    """Get all live tickets"""
    tickets = await db.live_tickets.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return tickets

@router.post("/live/tickets/{ticket_id}/approve")
async def approve_live_ticket(ticket_id: str, user = Depends(get_current_user)):
    """Approve a live ticket and send stream link"""
    ticket = await db.live_tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    await db.live_tickets.update_one({"id": ticket_id}, {"$set": {"status": "approved"}})
    
    # Increment tickets_sold
    await db.live_sessions.update_one(
        {"id": ticket.get("session_id")},
        {"$inc": {"tickets_sold": 1}}
    )
    
    # Send stream link to user
    session = await db.live_sessions.find_one({"id": ticket.get("session_id")}, {"_id": 0})
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    msg = "✅ <b>Ticket Approved!</b>\n\n"
    msg += f"📺 Session: <b>{session.get('title', '')}</b>\n"
    msg += f"📅 Date: <b>{session.get('scheduled_date', '')}</b>\n"
    msg += f"🕐 Time: <b>{session.get('scheduled_time', '')}</b>\n\n"
    
    if session and session.get("stream_link"):
        msg += f"🔗 Stream Link:\n{session['stream_link']}\n\n"
    else:
        msg += "🔔 Stream link will be sent when we go live!\n\n"
    
    msg += "🎉 See you there!"
    
    await send_telegram_message(ticket.get("telegram_user_id"), msg, bot_token)
    
    return {"message": "Ticket approved"}

@router.post("/live/tickets/{ticket_id}/reject")
async def reject_live_ticket(ticket_id: str, user = Depends(get_current_user)):
    """Reject a live ticket"""
    ticket = await db.live_tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    await db.live_tickets.update_one({"id": ticket_id}, {"$set": {"status": "rejected"}})
    
    # Notify user
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    msg = "❌ <b>Ticket Request Rejected</b>\n\n"
    msg += "Your payment could not be verified.\n"
    msg += "Please contact admin for assistance."
    
    await send_telegram_message(ticket.get("telegram_user_id"), msg, bot_token)
    
    return {"message": "Ticket rejected"}

@router.get("/live/superchats")
async def get_superchats(user = Depends(get_current_user)):
    """Get all super chats"""
    chats = await db.live_superchats.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return chats

@router.post("/live/superchats/{chat_id}/approve")
async def approve_superchat(chat_id: str, user = Depends(get_current_user)):
    """Approve a super chat"""
    await db.live_superchats.update_one({"id": chat_id}, {"$set": {"status": "approved"}})
    return {"message": "Super chat approved"}

@router.post("/live/superchats/{chat_id}/reject")
async def reject_superchat(chat_id: str, user = Depends(get_current_user)):
    """Reject a super chat"""
    chat = await db.live_superchats.find_one({"id": chat_id}, {"_id": 0})
    await db.live_superchats.update_one({"id": chat_id}, {"$set": {"status": "rejected"}})
    
    # Notify user
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    msg = "❌ <b>Super Chat Not Verified</b>\n\n"
    msg += "Your payment could not be verified.\n"
    msg += "Please try again or contact admin."
    
    if chat:
        await send_telegram_message(chat.get("telegram_user_id"), msg, bot_token)
    
    return {"message": "Super chat rejected"}


# ============== ANALYTICS / EXPORT APIs ==============

@router.get("/analytics/revenue")
async def get_revenue_analytics(user = Depends(get_current_user)):
    """Advanced revenue analytics with daily/weekly/monthly breakdowns"""
    now = datetime.now(timezone.utc)
    
    # Get ALL verified payments
    payments = await db.payments.find(
        {"status": "verified"},
        {"_id": 0, "amount": 1, "created_at": 1, "plan_id": 1, "plan_name": 1}
    ).to_list(100000)
    
    # Get all subscribers
    subscribers = await db.subscribers.find({}, {"_id": 0}).to_list(100000)
    
    # Get all plans
    plans = await db.plans.find({}, {"_id": 0}).to_list(100)
    
    # === TOTAL METRICS ===
    total_revenue = sum(p.get("amount", 0) for p in payments)
    total_payments = len(payments)
    
    # This month's revenue
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    monthly_payments = [p for p in payments if str(p.get("created_at", "")) >= month_start]
    monthly_revenue = sum(p.get("amount", 0) for p in monthly_payments)
    
    # Last month's revenue for comparison
    last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
    last_month_end = now.replace(day=1).isoformat()
    last_month_payments = [p for p in payments if last_month_start <= str(p.get("created_at", "")) < last_month_end]
    last_month_revenue = sum(p.get("amount", 0) for p in last_month_payments)
    
    # Revenue growth %
    revenue_growth = 0
    if last_month_revenue > 0:
        revenue_growth = round(((monthly_revenue - last_month_revenue) / last_month_revenue) * 100, 1)
    
    # === DAILY CHART (Last 30 days) ===
    daily_revenue = {}
    for p in payments:
        date = str(p.get("created_at", ""))[:10]
        if date:
            daily_revenue[date] = daily_revenue.get(date, 0) + p.get("amount", 0)
    
    daily_chart = []
    for i in range(30):
        date = (now - timedelta(days=29-i)).strftime("%Y-%m-%d")
        daily_chart.append({"date": date, "revenue": daily_revenue.get(date, 0)})
    
    # === WEEKLY CHART (Last 12 weeks) ===
    weekly_chart = []
    for w in range(12):
        week_end = now - timedelta(weeks=11-w)
        week_start = week_end - timedelta(days=6)
        week_rev = sum(
            p.get("amount", 0) for p in payments 
            if week_start.strftime("%Y-%m-%d") <= str(p.get("created_at", ""))[:10] <= week_end.strftime("%Y-%m-%d")
        )
        weekly_chart.append({
            "week": f"W{12-11+w}",
            "label": f"{week_start.strftime('%d %b')} - {week_end.strftime('%d %b')}",
            "revenue": week_rev
        })
    
    # === MONTHLY CHART (Last 6 months) ===
    monthly_chart = []
    for m in range(6):
        month_date = now - timedelta(days=30 * (5 - m))
        m_start = month_date.replace(day=1).strftime("%Y-%m-%d")
        if m < 5:
            next_month = (month_date.replace(day=1) + timedelta(days=32)).replace(day=1)
            m_end = next_month.strftime("%Y-%m-%d")
        else:
            m_end = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        
        m_rev = sum(
            p.get("amount", 0) for p in payments
            if m_start <= str(p.get("created_at", ""))[:10] < m_end
        )
        monthly_chart.append({
            "month": month_date.strftime("%b %Y"),
            "revenue": m_rev
        })
    
    # === PLAN PERFORMANCE ===
    plan_revenue = {}
    plan_count = {}
    for p in payments:
        pname = p.get("plan_name", p.get("plan_id", "Unknown"))
        plan_revenue[pname] = plan_revenue.get(pname, 0) + p.get("amount", 0)
        plan_count[pname] = plan_count.get(pname, 0) + 1
    
    plan_performance = [
        {"name": name, "revenue": rev, "sales": plan_count.get(name, 0)}
        for name, rev in sorted(plan_revenue.items(), key=lambda x: x[1], reverse=True)
    ]
    
    # === SUBSCRIBER METRICS ===
    active_subs = len([s for s in subscribers if s.get("status") == "active"])
    grace_subs = len([s for s in subscribers if s.get("status") == "grace"])
    expired_subs = len([s for s in subscribers if s.get("status") == "expired"])
    
    # Churn rate (expired / total * 100)
    churn_rate = round((expired_subs / max(len(subscribers), 1)) * 100, 1)
    
    # Average Revenue Per User (ARPU)
    arpu = round(total_revenue / max(len(subscribers), 1), 0)
    
    # Customer Lifetime Value (simple: ARPU * avg subscription months)
    avg_duration = 0
    for s in subscribers:
        try:
            start = s.get("start_date", "")
            end = s.get("end_date", "")
            if start and end:
                s_date = datetime.fromisoformat(str(start)) if isinstance(start, str) else start
                e_date = datetime.fromisoformat(str(end)) if isinstance(end, str) else end
                avg_duration += (e_date - s_date).days
        except Exception:
            pass
    avg_duration = avg_duration / max(len(subscribers), 1) / 30  # in months
    ltv = round(arpu * max(avg_duration, 1), 0)
    
    # === TODAY'S STATS ===
    today = now.strftime("%Y-%m-%d")
    today_revenue = daily_revenue.get(today, 0)
    today_payments = len([p for p in payments if str(p.get("created_at", ""))[:10] == today])
    
    # === CONVERSION FUNNEL ===
    total_bot_users = await db.bot_users.count_documents({})
    total_pending = await db.payments.count_documents({"status": "pending"})
    
    funnel = [
        {"stage": "Bot Users", "count": total_bot_users},
        {"stage": "Payment Started", "count": total_pending + total_payments},
        {"stage": "Payment Verified", "count": total_payments},
        {"stage": "Active Subscribers", "count": active_subs},
    ]
    
    return {
        "total_revenue": total_revenue,
        "total_payments": total_payments,
        "monthly_revenue": monthly_revenue,
        "last_month_revenue": last_month_revenue,
        "revenue_growth": revenue_growth,
        "today_revenue": today_revenue,
        "today_payments": today_payments,
        "active_subscribers": active_subs,
        "grace_subscribers": grace_subs,
        "expired_subscribers": expired_subs,
        "churn_rate": churn_rate,
        "arpu": arpu,
        "ltv": ltv,
        "daily_chart": daily_chart,
        "weekly_chart": weekly_chart,
        "monthly_chart": monthly_chart,
        "plan_performance": plan_performance,
        "funnel": funnel
    }

@router.get("/analytics/users")
async def get_user_analytics(user = Depends(get_current_user)):
    """Get user growth analytics"""
    users = await db.bot_users.find({}, {"_id": 0, "created_at": 1}).to_list(100000)
    
    # Group by date
    daily_users = {}
    for u in users:
        date = str(u.get("created_at", ""))[:10]
        if date:
            daily_users[date] = daily_users.get(date, 0) + 1
    
    # Last 30 days data
    chart_data = []
    cumulative = 0
    for i in range(30):
        date = (datetime.now(timezone.utc) - timedelta(days=29-i)).strftime("%Y-%m-%d")
        new_users = daily_users.get(date, 0)
        cumulative += new_users
        chart_data.append({
            "date": date,
            "new_users": new_users,
            "total_users": cumulative
        })
    
    return {
        "total_users": len(users),
        "chart_data": chart_data
    }

@router.get("/export/subscribers")
async def export_subscribers(user = Depends(get_current_user)):
    """Export subscribers as CSV data"""
    subscribers = await db.subscribers.find({}, {"_id": 0}).to_list(100000)
    
    # Convert to CSV format
    csv_data = "telegram_user_id,username,plan_name,start_date,end_date,status\n"
    for s in subscribers:
        csv_data += f"{s.get('telegram_user_id','')},{s.get('username','')},{s.get('plan_name','')},{s.get('start_date','')},{s.get('end_date','')},{s.get('status','')}\n"
    
    return {"csv_data": csv_data, "count": len(subscribers)}

@router.get("/export/payments")
async def export_payments(user = Depends(get_current_user)):
    """Export payments as CSV data"""
    payments = await db.payments.find({}, {"_id": 0}).to_list(100000)
    
    # Convert to CSV format
    csv_data = "id,telegram_user_id,username,amount,plan_name,status,payment_method,created_at,verified_at\n"
    for p in payments:
        csv_data += f"{p.get('id','')},{p.get('telegram_user_id','')},{p.get('telegram_username','')},{p.get('amount','')},{p.get('plan_name','')},{p.get('status','')},{p.get('payment_method','')},{p.get('created_at','')},{p.get('verified_at','')}\n"
    
    return {"csv_data": csv_data, "count": len(payments)}

# ============== CHAT TRACKING API ==============

@router.get("/chat-messages")
async def get_chat_messages(user = Depends(get_current_user), limit: int = 100, chat_type: str = None):
    """Get chat messages from users (Bot DM + Groups)"""
    query = {}
    if chat_type:
        query["chat_type"] = chat_type
    
    messages = await db.chat_messages.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return messages

@router.get("/chat-messages/stats")
async def get_chat_stats(user = Depends(get_current_user)):
    """Get chat statistics"""
    # Count by chat type
    private_count = await db.chat_messages.count_documents({"chat_type": "private"})
    group_count = await db.chat_messages.count_documents({"chat_type": {"$in": ["group", "supergroup"]}})
    
    # Unique users who chatted
    unique_users = await db.chat_messages.distinct("telegram_user_id")
    
    # Recent active users (last 24 hours)
    from datetime import timedelta
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    recent_messages = await db.chat_messages.find(
        {"created_at": {"$gte": yesterday}}, 
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    return {
        "total_messages": private_count + group_count,
        "private_messages": private_count,
        "group_messages": group_count,
        "unique_users": len(unique_users),
        "recent_messages": recent_messages
    }

@router.get("/chat-messages/user/{user_id}")
async def get_user_chat_history(user_id: str, user = Depends(get_current_user)):
    """Get chat history for a specific user"""
    messages = await db.chat_messages.find(
        {"telegram_user_id": user_id}, 
        {"_id": 0}
    ).sort("created_at", -1).limit(100).to_list(100)
    return messages


# ============== BOT ACTIVITY LOGS ==============

async def log_bot_activity(event_type: str, user_id: str = "", username: str = "", details: str = "", metadata: dict = None):
    """Log bot activity for admin dashboard"""
    try:
        log_entry = {
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "telegram_user_id": user_id,
            "telegram_username": username,
            "details": details,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.bot_activity_logs.insert_one(log_entry)
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")

@router.get("/bot-activity")
async def get_bot_activity(user = Depends(get_current_user), limit: int = 100, event_type: str = None):
    """Get bot activity logs"""
    query = {}
    if event_type:
        query["event_type"] = event_type
    
    logs = await db.bot_activity_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return logs

@router.get("/bot-activity/stats")
async def get_bot_activity_stats(user = Depends(get_current_user)):
    """Get bot activity stats for last 24 hours"""
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    today = datetime.now(timezone.utc).isoformat()
    
    total_24h = await db.bot_activity_logs.count_documents({"created_at": {"$gte": yesterday}})
    
    # Count by event type
    event_types = ["command", "payment_screenshot", "callback", "message", "payment_verified", "new_subscriber"]
    type_counts = {}
    for et in event_types:
        type_counts[et] = await db.bot_activity_logs.count_documents({
            "event_type": et,
            "created_at": {"$gte": yesterday}
        })
    
    # Unique active users in 24h
    active_users_24h = len(await db.bot_activity_logs.distinct("telegram_user_id", {"created_at": {"$gte": yesterday}}))
    
    # Total all time
    total_all = await db.bot_activity_logs.count_documents({})
    
    return {
        "total_24h": total_24h,
        "total_all": total_all,
        "active_users_24h": active_users_24h,
        "by_type": type_counts
    }

# ============== ENHANCED EXPORT ==============

@router.get("/export/revenue-report")
async def export_revenue_report(user = Depends(get_current_user)):
    """Export full revenue report as CSV"""
    payments = await db.payments.find({"status": "verified"}, {"_id": 0}).to_list(100000)
    subscribers = await db.subscribers.find({}, {"_id": 0}).to_list(100000)
    
    # Revenue CSV
    revenue_csv = "Date,User ID,Username,Plan,Amount,Payment Method,Status\n"
    for p in sorted(payments, key=lambda x: x.get("created_at", ""), reverse=True):
        revenue_csv += f"{str(p.get('created_at',''))[:10]},{p.get('telegram_user_id','')},{p.get('telegram_username','')},{p.get('plan_name','')},{p.get('amount',0)},{p.get('payment_method','')},{p.get('status','')}\n"
    
    # Summary
    total_revenue = sum(p.get("amount", 0) for p in payments)
    active_count = len([s for s in subscribers if s.get("status") == "active"])
    
    summary = {
        "total_revenue": total_revenue,
        "total_payments": len(payments),
        "active_subscribers": active_count,
        "total_subscribers": len(subscribers),
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
    
    return {"csv_data": revenue_csv, "summary": summary}



# ============== TELEGRAM WEBHOOK ==============

async def send_telegram_message_with_buttons(chat_id: str, message: str, buttons: list = None, bot_token: str = None, retries: int = 3):
    """Send message with inline keyboard buttons with rate limiting"""
    if not bot_token:
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
    
    if not bot_token:
        return False
    
    # Rate limiting per chat
    now = asyncio.get_event_loop().time()
    last = telegram_last_request.get(chat_id, 0)
    if now - last < TELEGRAM_MIN_INTERVAL:
        await asyncio.sleep(TELEGRAM_MIN_INTERVAL - (now - last))
    telegram_last_request[chat_id] = asyncio.get_event_loop().time()
    
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                if buttons:
                    payload["reply_markup"] = {"inline_keyboard": buttons}
                
                response = await http_client.post(url, json=payload)
                logger.info(f"Telegram response: {response.status_code}")
                
                if response.status_code == 200:
                    return True
                elif response.status_code == 429:
                    retry_after = response.json().get("parameters", {}).get("retry_after", 1)
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                else:
                    return False
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(0.5)
    return False


async def send_telegram_message_with_buttons_and_return(chat_id: str, message: str, buttons: list = None, bot_token: str = None):
    """Send message with buttons and return the message_id for later editing"""
    if not bot_token:
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
    if not bot_token:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            if buttons:
                payload["reply_markup"] = {"inline_keyboard": buttons}
            response = await http_client.post(url, json=payload)
            if response.status_code == 200:
                return response.json().get("result", {}).get("message_id")
    except Exception as e:
        logger.error(f"Failed to send message with return: {e}")
    return None


async def edit_telegram_message(chat_id: str, message_id: int, text: str, buttons: list = None, bot_token: str = None):
    """Edit an existing Telegram message"""
    if not bot_token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML"
            }
            if buttons:
                payload["reply_markup"] = {"inline_keyboard": buttons}
            response = await http_client.post(url, json=payload)
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")
    return False


async def urgency_timer_task(chat_id: str, message_id: int, plan: dict, price_display: str, final_price: float, buttons: list, bot_token: str):
    """Background task - live countdown timer on plan message"""
    try:
        plan_name = plan.get('name', '')
        features_text = ""
        if plan.get('features'):
            features_text = "<b>Features:</b>\n"
            for feat in plan['features']:
                features_text += f"✅ {feat}\n"
            features_text += "\n"
        
        base_msg = f"🔥 <b>EXCLUSIVE OFFER!</b> 🔥\n\n"
        base_msg += f"<b>📦 {plan_name}</b>\n\n"
        base_msg += f"💰 Price: {price_display}\n"
        base_msg += f"⏱ Duration: <b>{plan['duration_days']} days</b>\n\n"
        base_msg += features_text
        
        payment_info = "━━━━━━━━━━━━━━━\n"
        payment_info += "<b>💳 Payment Options:</b>\n\n"
        payment_info += "1️⃣ <b>UPI/QR Code:</b> Pay via any UPI app\n"
        payment_info += "2️⃣ After payment, send screenshot\n\n"
        payment_info += f"📱 <b>Your User ID:</b> <code>{chat_id}</code>"
        
        # Phase 1: Countdown from 60 to 0 (every 5 seconds)
        for remaining in [55, 50, 45, 40, 35, 30, 25, 20, 15, 10, 5]:
            await asyncio.sleep(5)
            
            bar_filled = remaining // 5
            bar_empty = 12 - bar_filled
            progress_bar = "🟢" * bar_filled + "⚪" * bar_empty
            
            timer_msg = base_msg
            timer_msg += f"⏰ <b>Offer expires in {remaining} seconds!</b>\n"
            timer_msg += f"{progress_bar}\n"
            timer_msg += payment_info
            
            await edit_telegram_message(chat_id, message_id, timer_msg, buttons, bot_token)
        
        # Phase 2: LAST CHANCE (5 sec intervals for 60 more seconds)
        await asyncio.sleep(5)
        
        for i in range(12):
            remaining = 60 - (i * 5)
            
            urgency_msg = "⚡ <b>LAST CHANCE TO GRAB THIS OFFER!</b> ⚡\n\n"
            urgency_msg += f"<b>📦 {plan_name}</b>\n\n"
            urgency_msg += f"💰 Price: {price_display}\n"
            urgency_msg += f"⏱ Duration: <b>{plan['duration_days']} days</b>\n\n"
            urgency_msg += features_text
            urgency_msg += f"🚨 <b>Only {remaining}s left! Don't miss out!</b>\n"
            urgency_msg += "🔴🔴🔴🔴🔴🔴\n"
            urgency_msg += payment_info
            
            await edit_telegram_message(chat_id, message_id, urgency_msg, buttons, bot_token)
            
            if i < 11:
                await asyncio.sleep(5)
        
        # Phase 3: Timer ended
        await asyncio.sleep(5)
        
        expired_msg = "⏰ <b>Offer timer ended!</b>\n\n"
        expired_msg += f"<b>📦 {plan_name}</b>\n\n"
        expired_msg += f"💰 Price: {price_display}\n"
        expired_msg += f"⏱ Duration: <b>{plan['duration_days']} days</b>\n\n"
        expired_msg += features_text
        expired_msg += "💡 <b>You can still purchase — but hurry!</b>\n"
        expired_msg += payment_info
        
        await edit_telegram_message(chat_id, message_id, expired_msg, buttons, bot_token)
        
    except Exception as e:
        logger.error(f"Error in urgency timer: {e}")


# ============== PAID POSTS ADMIN APIs ==============

@router.get("/paid-posts")
async def get_paid_posts(user = Depends(get_current_user)):
    """Get all paid posts for admin dashboard"""
    posts = await db.paid_posts.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return posts

@router.get("/paid-posts/{post_id}")
async def get_paid_post(post_id: str, user = Depends(get_current_user)):
    """Get single paid post details"""
    post = await db.paid_posts.find_one({"id": post_id}, {"_id": 0})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Get unlock history
    unlocks = await db.paid_post_unlocks.find({"post_id": post_id}, {"_id": 0}).to_list(100)
    post["unlocks"] = unlocks
    
    return post

@router.put("/paid-posts/{post_id}")
async def update_paid_post(post_id: str, data: dict, user = Depends(get_current_user)):
    """Update paid post (price, active status)"""
    await db.paid_posts.update_one(
        {"id": post_id},
        {"$set": {
            "price": data.get("price", 0),
            "is_active": data.get("is_active", True),
            "caption": data.get("caption", "")
        }}
    )
    return {"message": "Post updated"}

@router.delete("/paid-posts/{post_id}")
async def delete_paid_post(post_id: str, user = Depends(get_current_user)):
    """Delete/deactivate a paid post"""
    await db.paid_posts.update_one({"id": post_id}, {"$set": {"is_active": False}})
    return {"message": "Post deactivated"}

@router.get("/unlock-requests")
async def get_unlock_requests(user = Depends(get_current_user)):
    """Get all unlock requests for admin (pending, approved, rejected)"""
    requests = await db.unlock_requests.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return requests

@router.post("/unlock-requests/{request_id}/approve")
async def approve_unlock_request(request_id: str, user = Depends(get_current_user)):
    """Approve unlock request and send content to user"""
    request = await db.unlock_requests.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    post_id = request.get("post_id")
    paid_post = await db.paid_posts.find_one({"id": post_id}, {"_id": 0})
    
    if not paid_post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    chat_id = request.get("telegram_user_id")
    username = request.get("telegram_username", "")
    
    # Save unlock record
    unlock_record = {
        "id": str(uuid.uuid4()),
        "post_id": post_id,
        "telegram_user_id": chat_id,
        "telegram_username": username,
        "payment_id": "admin_approved",
        "unlocked_at": datetime.now(timezone.utc).isoformat()
    }
    await db.paid_post_unlocks.insert_one(unlock_record)
    
    # Update unlock count
    await db.paid_posts.update_one({"id": post_id}, {"$inc": {"unlock_count": 1}})
    
    # Update request status
    await db.unlock_requests.update_one({"id": request_id}, {"$set": {"status": "approved"}})
    
    # Send content to user
    if bot_token and chat_id:
        success_msg = "✅ <b>Payment Approved!</b>\n\n🔓 Here's your unlocked content:"
        await send_telegram_message(chat_id, success_msg, bot_token)
        
        if paid_post.get("content_type") == "photo" and paid_post.get("original_file_id"):
            caption = f"🔓 <b>Unlocked!</b>\n\n{paid_post.get('caption', '')}"
            await send_telegram_photo(chat_id, paid_post["original_file_id"], caption, bot_token)
        elif paid_post.get("content_type") == "video" and paid_post.get("original_file_id"):
            caption = f"🔓 <b>Unlocked Video!</b>\n\n{paid_post.get('caption', '')}"
            await send_telegram_video(chat_id, paid_post["original_file_id"], caption, bot_token)
    
    return {"message": "Unlock approved and content sent"}

@router.post("/unlock-requests/{request_id}/reject")
async def reject_unlock_request(request_id: str, user = Depends(get_current_user)):
    """Reject unlock request"""
    request = await db.unlock_requests.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    await db.unlock_requests.update_one({"id": request_id}, {"$set": {"status": "rejected"}})
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    chat_id = request.get("telegram_user_id")
    
    if bot_token and chat_id:
        reject_msg = "❌ <b>Payment Not Verified</b>\n\n"
        reject_msg += "Your screenshot could not be verified.\n"
        reject_msg += "Please try again with a valid payment screenshot."
        await send_telegram_message(chat_id, reject_msg, bot_token)
    
    return {"message": "Unlock request rejected"}

@router.get("/telegram/file/{file_id}")
async def get_telegram_file(file_id: str):
    """Serve Telegram file (screenshot) for admin preview - Public endpoint (file_id is security)"""
    from fastapi.responses import Response
    from config import TELEGRAM_BOT_TOKEN
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "") or TELEGRAM_BOT_TOKEN
    
    if not bot_token:
        raise HTTPException(status_code=500, detail="Bot token not configured")
    
    # Download file from Telegram
    image_bytes = await download_telegram_photo(file_id, bot_token)
    
    if not image_bytes:
        raise HTTPException(status_code=404, detail="File not found or expired")
    
    # Return as image with cache headers
    return Response(
        content=image_bytes, 
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"}
    )




# ============== MINI APP ENDPOINTS ==============

@router.get("/miniapp/plans")
async def miniapp_get_plans():
    """Get active plans for Mini App (public, no auth)"""
    plans = await db.plans.find({"is_active": True}, {"_id": 0}).sort("price", 1).to_list(50)
    return plans

@router.get("/miniapp/status/{telegram_user_id}")
async def miniapp_get_status(telegram_user_id: str):
    """Get user subscription status for Mini App (public, identified by TG ID)"""
    # Find active subscription
    sub = await db.subscribers.find_one(
        {"telegram_user_id": telegram_user_id, "status": "active"},
        {"_id": 0}
    )
    
    if sub:
        # Calculate days remaining
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

@router.post("/miniapp/set-menu-button")
async def set_miniapp_menu_button(data: dict, user = Depends(get_current_user)):
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
        # Set chat menu button (appears for all users)
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
            raise HTTPException(status_code=400, detail=result.get("description", "Failed to set menu button"))
    
    return {"message": "Menu button set!", "url": webapp_url, "text": button_text}

@router.get("/miniapp/menu-button-status")
async def get_menu_button_status(user = Depends(get_current_user)):
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
    
    return {"status": "ok", "menu_button": result.get("result", {})}
