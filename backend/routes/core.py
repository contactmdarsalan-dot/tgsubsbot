"""Plans, Subscribers, Payments, Settings, Analytics, Upload routes"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request, File, UploadFile
from database import db, cache_delete
from services.auth import get_current_user
from services.telegram import (
    get_bot_settings, send_telegram_message, send_telegram_message_with_buttons,
    add_to_channel, remove_from_channel, notify_admin_new_payment
)
from services.payment import detect_payment_screenshot, analyze_payment_screenshot_with_ai
from services.bot_activity import log_bot_activity
from services.tenant import DEFAULT_TENANT_ID, tenant_query
from services.permissions import is_super_admin, is_any_admin, get_user_tenant, tq, ensure_admin
from services.audit import log_action
from config import logger, RAZORPAY_KEY_ID, razorpay_client, SUPER_ADMIN_EMAILS
from models import (
    SubscriptionPlanCreate, SubscriptionPlan, SubscriberCreate, Subscriber,
    PaymentCreate, Payment, BotSettings
)
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path
import uuid
import httpx
import os
import base64
import json
from io import BytesIO

router = APIRouter()

# ============== PLANS ROUTES ==============

@router.get("/plans", response_model=List[SubscriptionPlan])
async def get_plans(user = Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    plans = await db.plans.find(tq({}, tenant_id), {"_id": 0}).to_list(100)
    for plan in plans:
        if isinstance(plan.get('created_at'), str):
            plan['created_at'] = datetime.fromisoformat(plan['created_at'])
    return plans

@router.get("/plans/active", response_model=List[SubscriptionPlan])
async def get_active_plans():
    # Try cache first
    cached = await cache_get("active_plans")
    if cached:
        for plan in cached:
            if isinstance(plan.get('created_at'), str):
                plan['created_at'] = datetime.fromisoformat(plan['created_at'])
        return cached
    
    plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(100)
    for plan in plans:
        if isinstance(plan.get('created_at'), str):
            plan['created_at'] = datetime.fromisoformat(plan['created_at'])
    
    # Cache plans for 5 minutes
    plans_for_cache = [{**p, 'created_at': p['created_at'].isoformat() if hasattr(p.get('created_at'), 'isoformat') else p.get('created_at')} for p in plans]
    await cache_set("active_plans", plans_for_cache, ttl=300)
    
    return plans

@router.post("/plans", response_model=SubscriptionPlan)
async def create_plan(plan: SubscriptionPlanCreate, user = Depends(get_current_user)):
    plan_obj = SubscriptionPlan(**plan.model_dump())
    doc = plan_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['tenant_id'] = user.get("tenant_id") or DEFAULT_TENANT_ID
    await db.plans.insert_one(doc)
    return plan_obj

@router.put("/plans/{plan_id}", response_model=SubscriptionPlan)
async def update_plan(plan_id: str, plan: SubscriptionPlanCreate, user = Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    existing = await db.plans.find_one(tq({"id": plan_id}, tenant_id), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    await db.plans.update_one(tq({"id": plan_id}, tenant_id), {"$set": plan.model_dump()})
    updated = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return updated

@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str, user = Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    result = await db.plans.delete_one(tq({"id": plan_id}, tenant_id))
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"message": "Plan deleted"}

# ============== SUBSCRIBERS ROUTES ==============

@router.get("/subscribers")
async def get_subscribers(status: Optional[str] = None, user = Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    query = tq({}, tenant_id)
    if status:
        query["status"] = status
    subscribers = await db.subscribers.find(query, {"_id": 0}).to_list(1000)
    
    # Fetch all plans and groups for enrichment
    plans = await db.plans.find({}, {"_id": 0}).to_list(100)
    plans_map = {p["id"]: p for p in plans}
    
    groups = await db.chat_groups_pool.find({}, {"_id": 0}).to_list(100)
    # Map by assigned_to_user_id for quick lookup
    groups_by_user = {g.get("assigned_to_user_id", ""): g for g in groups if g.get("assigned_to_user_id")}
    # Also map by group_id
    groups_by_id = {g.get("group_id", ""): g for g in groups}
    
    for sub in subscribers:
        for field in ['start_date', 'end_date', 'grace_end_date', 'created_at']:
            if isinstance(sub.get(field), str):
                sub[field] = datetime.fromisoformat(sub[field])
        
        # Enrich with plan's channel_id
        plan = plans_map.get(sub.get("plan_id", ""), {})
        sub["channel_id"] = plan.get("channel_id", "")
        
        # Enrich with group info - check assigned group or plan's group_id
        assigned_group = groups_by_user.get(sub.get("telegram_user_id", ""))
        if assigned_group:
            sub["group_name"] = assigned_group.get("group_name", assigned_group.get("group_id", ""))
            sub["group_id"] = assigned_group.get("group_id", "")
        elif plan.get("group_id"):
            group = groups_by_id.get(plan["group_id"], {})
            sub["group_name"] = group.get("group_name", plan.get("group_id", ""))
            sub["group_id"] = plan.get("group_id", "")
        else:
            sub["group_name"] = ""
            sub["group_id"] = ""
    
    return subscribers

@router.post("/subscribers", response_model=Subscriber)
async def create_subscriber(subscriber: SubscriberCreate, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    plan = await db.plans.find_one({"id": subscriber.plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    grace_days = settings.get("grace_period_days", 2)
    
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=plan["duration_days"])
    grace_end_date = end_date + timedelta(days=grace_days)
    
    sub_obj = Subscriber(
        telegram_user_id=subscriber.telegram_user_id,
        telegram_username=subscriber.telegram_username,
        plan_id=subscriber.plan_id,
        plan_name=plan["name"],
        payment_method=subscriber.payment_method,
        payment_id=subscriber.payment_id,
        start_date=start_date,
        end_date=end_date,
        grace_end_date=grace_end_date
    )
    
    doc = sub_obj.model_dump()
    for field in ['start_date', 'end_date', 'grace_end_date', 'created_at']:
        if doc.get(field):
            doc[field] = doc[field].isoformat()
    doc['tenant_id'] = plan.get("tenant_id") or user.get("tenant_id") or DEFAULT_TENANT_ID
    await db.subscribers.insert_one(doc)
    
    # Send welcome message and channel invite (use plan's channel if set)
    plan_channel = plan.get("channel_id", "")
    background_tasks.add_task(add_to_channel, subscriber.telegram_user_id, plan_channel, plan["name"])
    
    website_link = settings.get("website_link", "")
    if website_link:
        background_tasks.add_task(send_telegram_message, subscriber.telegram_user_id, 
            f"🌟 Check out our services: {website_link}")
    
    return sub_obj

@router.put("/subscribers/{subscriber_id}/renew")
async def renew_subscriber(subscriber_id: str, plan_id: str, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    subscriber = await db.subscribers.find_one({"id": subscriber_id}, {"_id": 0})
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    grace_days = settings.get("grace_period_days", 2)
    
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=plan["duration_days"])
    grace_end_date = end_date + timedelta(days=grace_days)
    
    await db.subscribers.update_one(
        {"id": subscriber_id},
        {"$set": {
            "plan_id": plan_id,
            "plan_name": plan["name"],
            "status": "active",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "grace_end_date": grace_end_date.isoformat(),
            "reminder_sent": False
        }}
    )
    
    # Send renewal notification with channel invite
    plan_channel = plan.get("channel_id", "")
    background_tasks.add_task(send_renewal_notification, subscriber["telegram_user_id"], plan, plan_channel, end_date)
    
    return {"message": "Subscription renewed"}

async def send_renewal_notification(user_id: str, plan: dict, plan_channel: str, end_date: datetime):
    """Send renewal notification with channel invite"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    msg = f"🎉 <b>Subscription Renewed!</b>\n\n"
    msg += f"📦 Plan: <b>{plan['name']}</b>\n"
    msg += f"⏱ Duration: <b>{plan['duration_days']} days</b>\n"
    msg += f"📅 Valid till: <b>{end_date.strftime('%d %b %Y')}</b>\n\n"
    msg += "Thank you for continuing with us! 🙏"
    
    await send_telegram_message(user_id, msg, bot_token)
    
    # Send new channel invite
    await add_to_channel(user_id, plan_channel, plan['name'])

@router.delete("/subscribers/{subscriber_id}")
async def delete_subscriber(subscriber_id: str, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    subscriber = await db.subscribers.find_one({"id": subscriber_id}, {"_id": 0})
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    # Get plan to find channel
    plan = await db.plans.find_one({"id": subscriber.get("plan_id")}, {"_id": 0})
    plan_channel = plan.get("channel_id", "") if plan else ""
    
    await db.subscribers.delete_one({"id": subscriber_id})
    background_tasks.add_task(remove_from_channel, subscriber["telegram_user_id"], plan_channel)
    
    return {"message": "Subscriber removed"}


# ============== CHAT GROUPS POOL ROUTES ==============

class AddChatGroupRequest(BaseModel):
    group_id: str
    group_name: str = ""

@router.get("/chat-groups")
async def get_chat_groups(user = Depends(get_current_user)):
    """Get all chat groups in the pool"""
    groups = await db.chat_groups_pool.find({}, {"_id": 0}).to_list(100)
    return groups

@router.post("/chat-groups")
async def add_chat_group(request: AddChatGroupRequest, user = Depends(get_current_user)):
    """Add a group to the chat pool"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    # Auto-fix group ID format — Telegram group IDs are always negative
    group_id = request.group_id.strip()
    if group_id and not group_id.startswith("-"):
        group_id = f"-{group_id}"
    
    # Verify bot is admin in the group
    try:
        async with httpx.AsyncClient() as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/getChatAdministrators?chat_id={group_id}"
            response = await http_client.get(url)
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Bot is not admin in this group or group doesn't exist. Make sure bot is added as admin to the group.")
            
            admins = response.json().get("result", [])
            bot_is_admin = False
            for admin in admins:
                if admin.get("user", {}).get("is_bot"):
                    bot_is_admin = True
                    break
            
            if not bot_is_admin:
                raise HTTPException(status_code=400, detail="Bot must be admin in this group")
            
            # Get group info
            info_url = f"https://api.telegram.org/bot{bot_token}/getChat?chat_id={group_id}"
            info_response = await http_client.get(info_url)
            group_name = request.group_name
            if info_response.status_code == 200:
                group_name = info_response.json().get("result", {}).get("title", group_name)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying group: {e}")
        raise HTTPException(status_code=400, detail=f"Error verifying group: {str(e)}")
    
    # Check if group already in pool
    existing = await db.chat_groups_pool.find_one({"group_id": group_id})
    if existing:
        raise HTTPException(status_code=400, detail="Group already in pool")
    
    # Add to pool
    group_doc = {
        "id": str(uuid.uuid4()),
        "group_id": group_id,
        "group_name": group_name,
        "status": "available",
        "assigned_to_user_id": "",
        "assigned_to_username": "",
        "plan_type": "",
        "session_start": None,
        "session_end": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.chat_groups_pool.insert_one(group_doc)
    
    return {"message": "Group added to pool", "group": group_doc}

@router.delete("/chat-groups/{group_id}")
async def remove_chat_group(group_id: str, user = Depends(get_current_user)):
    """Remove a group from the pool"""
    result = await db.chat_groups_pool.delete_one({"group_id": group_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Group not found in pool")
    return {"message": "Group removed from pool"}

@router.get("/chat-sessions")
async def get_chat_sessions(status: Optional[str] = None, user = Depends(get_current_user)):
    """Get all chat sessions"""
    query = {}
    if status:
        query["status"] = status
    sessions = await db.chat_sessions.find(query, {"_id": 0}).to_list(100)
    return sessions

@router.post("/chat-groups/{group_id}/release")
async def force_release_group(group_id: str, user = Depends(get_current_user)):
    """Force release a group back to pool"""
    group = await db.chat_groups_pool.find_one({"group_id": group_id}, {"_id": 0})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    await release_chat_group(group_id)
    return {"message": "Group released"}


# ============== CHANNELS ROUTES ==============

@router.get("/channels")
async def get_channels(user = Depends(get_current_user)):
    """Get all managed Telegram channels"""
    channels = await db.channels.find({}, {"_id": 0}).to_list(100)
    return channels


@router.post("/channels")
async def add_channel(data: dict, user = Depends(get_current_user)):
    """Add a new Telegram channel to manage"""
    channel_id = data.get("channel_id", "").strip()
    channel_name = data.get("channel_name", "").strip()
    channel_type = data.get("channel_type", "private")
    description = data.get("description", "").strip()

    if not channel_id:
        raise HTTPException(status_code=400, detail="Channel ID is required")

    if not channel_id.startswith("-"):
        channel_id = f"-{channel_id}"

    existing = await db.channels.find_one({"channel_id": channel_id})
    if existing:
        raise HTTPException(status_code=400, detail="Channel already exists")

    # Try to get channel info from Telegram
    member_count = 0
    try:
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
        if bot_token:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"https://api.telegram.org/bot{bot_token}/getChatMemberCount?chat_id={channel_id}")
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("ok"):
                        member_count = result.get("result", 0)
    except Exception as e:
        logger.warning(f"Could not fetch channel member count: {e}")

    channel_doc = {
        "id": str(uuid.uuid4()),
        "channel_id": channel_id,
        "channel_name": channel_name or f"Channel {channel_id}",
        "channel_type": channel_type,
        "description": description,
        "member_count": member_count,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.channels.insert_one(channel_doc)
    channel_doc.pop("_id", None)
    return channel_doc


@router.put("/channels/{channel_id}")
async def update_channel(channel_id: str, data: dict, user = Depends(get_current_user)):
    """Update channel details"""
    update_data = {}
    if "channel_name" in data:
        update_data["channel_name"] = data["channel_name"].strip()
    if "description" in data:
        update_data["description"] = data["description"].strip()
    if "channel_type" in data:
        update_data["channel_type"] = data["channel_type"]
    if "status" in data:
        update_data["status"] = data["status"]

    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    result = await db.channels.update_one({"channel_id": channel_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"message": "Channel updated"}


@router.post("/channels/{channel_id}/refresh")
async def refresh_channel_info(channel_id: str, user = Depends(get_current_user)):
    """Refresh channel member count from Telegram"""
    channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    member_count = 0
    channel_title = channel.get("channel_name", "")
    try:
        if bot_token:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Get member count
                resp = await client.get(f"https://api.telegram.org/bot{bot_token}/getChatMemberCount?chat_id={channel_id}")
                if resp.status_code == 200 and resp.json().get("ok"):
                    member_count = resp.json().get("result", 0)

                # Get chat info for title
                resp2 = await client.get(f"https://api.telegram.org/bot{bot_token}/getChat?chat_id={channel_id}")
                if resp2.status_code == 200 and resp2.json().get("ok"):
                    chat_info = resp2.json().get("result", {})
                    channel_title = chat_info.get("title", channel_title)
    except Exception as e:
        logger.warning(f"Could not refresh channel info: {e}")

    await db.channels.update_one(
        {"channel_id": channel_id},
        {"$set": {"member_count": member_count, "channel_name": channel_title, "last_refreshed": datetime.now(timezone.utc).isoformat()}}
    )
    return {"member_count": member_count, "channel_name": channel_title}


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: str, user = Depends(get_current_user)):
    """Remove a channel"""
    result = await db.channels.delete_one({"channel_id": channel_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"message": "Channel removed"}


# ============== PAYMENTS ROUTES ==============

@router.get("/payments")
async def get_payments(status: Optional[str] = None, user = Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    query = tq({}, tenant_id)
    if status:
        query["status"] = status
    # Sort by created_at descending (newest first)
    payments = await db.payments.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    for p in payments:
        if isinstance(p.get('created_at'), str):
            p['created_at'] = datetime.fromisoformat(p['created_at'])
        
        # Keep screenshot_file_id for lazy loading via /api/telegram/file/{file_id}
        if p.get('screenshot_file_id'):
            p['has_screenshot'] = True
        else:
            p['has_screenshot'] = False
    
    return payments

@router.get("/payments/{payment_id}/screenshot")
async def get_payment_screenshot(payment_id: str, user = Depends(get_current_user)):
    """Get screenshot URL for a payment"""
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if not payment.get("screenshot_file_id"):
        raise HTTPException(status_code=404, detail="No screenshot available")
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot token not configured")
    
    # Get file path from Telegram
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={payment['screenshot_file_id']}"
            response = await http_client.get(file_info_url)
            if response.status_code == 200:
                file_path = response.json().get("result", {}).get("file_path")
                if file_path:
                    download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
                    return {"screenshot_url": download_url}
    except Exception as e:
        logger.error(f"Error getting screenshot: {e}")
    
    raise HTTPException(status_code=400, detail="Could not retrieve screenshot")

@router.put("/payments/{payment_id}/unverify")
async def unverify_payment(payment_id: str, user = Depends(get_current_user)):
    """Unverify a payment - changes status back to pending AND kick user from channel"""
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.get("status") != "verified":
        raise HTTPException(status_code=400, detail="Payment is not verified")
    
    telegram_user_id = payment.get("telegram_user_id")
    
    # Update payment status to rejected (not just pending)
    await db.payments.update_one(
        {"id": payment_id},
        {"$set": {
            "status": "rejected",
            "unverified_at": datetime.now(timezone.utc).isoformat(),
            "unverified_by": user.get("email", "admin"),
            "rejection_reason": "Unverified by admin after review"
        }}
    )
    
    # Remove subscriber if exists
    if telegram_user_id:
        await db.subscribers.delete_one({"telegram_user_id": telegram_user_id, "plan_id": payment.get("plan_id")})
    
    # KICK USER FROM CHANNEL
    kicked = False
    if telegram_user_id:
        kicked = await kick_user_from_channel(telegram_user_id)
        logger.info(f"Kicked user {telegram_user_id} from channel: {kicked}")
        
        # Also kick from any assigned chat groups
        assigned_group = await db.chat_groups_pool.find_one(
            {"assigned_to_user_id": telegram_user_id},
            {"_id": 0}
        )
        if assigned_group:
            await kick_user_from_group(assigned_group["group_id"], telegram_user_id)
            await release_chat_group(assigned_group["group_id"])
    
    # Notify user
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if bot_token and telegram_user_id:
        msg = "❌ <b>Payment Rejected</b>\n\n"
        msg += f"Your payment for {payment.get('plan_name', 'subscription')} has been rejected after review.\n\n"
        msg += "🚫 You have been removed from the channel.\n"
        msg += "📞 Contact support if you believe this is a mistake."
        await send_telegram_message(telegram_user_id, msg, bot_token)
    
    return {
        "message": "Payment unverified and user kicked from channel",
        "user_kicked": kicked
    }


# ============== BOT CHECKOUT ROUTES ==============

@router.get("/bot-checkout/{order_id}")
async def get_bot_checkout(order_id: str):
    """Get order details for bot checkout page"""
    order = await db.bot_orders.find_one({"razorpay_order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    plan = await db.plans.find_one({"id": order["plan_id"]}, {"_id": 0})
    
    return {
        "order_id": order_id,
        "plan_id": order["plan_id"],
        "plan_name": order.get("plan_name", plan["name"] if plan else ""),
        "amount": order["amount"],
        "key_id": RAZORPAY_KEY_ID,
        "telegram_user_id": order.get("telegram_user_id", "")
    }

@router.post("/bot-checkout/verify")
async def verify_bot_checkout(data: dict, background_tasks: BackgroundTasks):
    """Verify Razorpay payment and activate subscription"""
    if not razorpay_client:
        raise HTTPException(status_code=400, detail="Razorpay not configured")
    
    try:
        # Verify signature
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })
    except Exception as e:
        logger.error(f"Payment verification failed: {e}")
        raise HTTPException(status_code=400, detail="Payment verification failed")
    
    # Get order
    order = await db.bot_orders.find_one({"razorpay_order_id": data['razorpay_order_id']}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Update order status
    await db.bot_orders.update_one(
        {"razorpay_order_id": data['razorpay_order_id']},
        {"$set": {"status": "paid", "razorpay_payment_id": data['razorpay_payment_id']}}
    )
    
    # Get plan details
    plan = await db.plans.find_one({"id": order["plan_id"]}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    telegram_user_id = data.get("telegram_user_id") or order.get("telegram_user_id")
    telegram_username = order.get("telegram_username", "")
    
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
        "status": "verified",
        "tenant_id": plan.get("tenant_id", DEFAULT_TENANT_ID),
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
        "tenant_id": plan.get("tenant_id", DEFAULT_TENANT_ID),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.subscribers.insert_one(subscriber_obj)
    
    # Add to channel
    plan_channel = plan.get("channel_id", "")
    if plan_channel and bot_token:
        background_tasks.add_task(add_to_channel, telegram_user_id, plan_channel, plan["name"])
    
    # Send success message to user
    if bot_token and telegram_user_id:
        success_msg = "🎉 <b>Payment Successful!</b>\n\n"
        success_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
        success_msg += f"💰 Amount: <b>₹{order['amount']}</b>\n"
        success_msg += f"⏱ Valid till: <b>{end_date.strftime('%d %b %Y')}</b>\n\n"
        success_msg += "✅ Your subscription is now active!\n"
        success_msg += "📢 You will receive channel invite link shortly."
        await send_telegram_message(telegram_user_id, success_msg, bot_token)
    
    logger.info(f"Bot subscription activated for user {telegram_user_id}, plan {plan['name']}")
    
    return {"success": True, "message": "Subscription activated"}

@router.post("/payments/create-order")
async def create_razorpay_order(payment: PaymentCreate, user = Depends(get_current_user)):
    if not razorpay_client:
        raise HTTPException(status_code=400, detail="Razorpay not configured")
    
    plan = await db.plans.find_one({"id": payment.plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    order = razorpay_client.order.create({
        "amount": int(payment.amount * 100),
        "currency": "INR",
        "payment_capture": 1
    })
    
    payment_obj = Payment(
        telegram_user_id=payment.telegram_user_id,
        amount=payment.amount,
        plan_id=payment.plan_id,
        payment_method="razorpay",
        razorpay_order_id=order["id"]
    )
    
    doc = payment_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    plan_for_tenant = await db.plans.find_one({"id": payment.plan_id}, {"_id": 0, "tenant_id": 1})
    doc['tenant_id'] = (plan_for_tenant or {}).get("tenant_id") or user.get("tenant_id") or DEFAULT_TENANT_ID
    await db.payments.insert_one(doc)
    
    return {"order_id": order["id"], "payment_id": payment_obj.id, "key_id": RAZORPAY_KEY_ID}

@router.post("/payments/verify")
async def verify_razorpay_payment(data: dict, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    if not razorpay_client:
        raise HTTPException(status_code=400, detail="Razorpay not configured")
    
    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Payment verification failed")
    
    payment = await db.payments.find_one({"razorpay_order_id": data['razorpay_order_id']}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    await db.payments.update_one(
        {"razorpay_order_id": data['razorpay_order_id']},
        {"$set": {"status": "verified", "razorpay_payment_id": data['razorpay_payment_id']}}
    )
    
    # Create subscriber
    plan = await db.plans.find_one({"id": payment["plan_id"]}, {"_id": 0})
    if plan:
        subscriber_create = SubscriberCreate(
            telegram_user_id=payment["telegram_user_id"],
            plan_id=payment["plan_id"],
            payment_method="razorpay",
            payment_id=payment["id"]
        )
        await create_subscriber(subscriber_create, background_tasks)
    
    return {"message": "Payment verified"}

@router.post("/payments/manual")
async def create_manual_payment(payment: PaymentCreate, user = Depends(get_current_user)):
    plan = await db.plans.find_one({"id": payment.plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    payment_obj = Payment(
        telegram_user_id=payment.telegram_user_id,
        amount=payment.amount,
        plan_id=payment.plan_id,
        payment_method="manual"
    )
    
    doc = payment_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    plan_for_tenant2 = await db.plans.find_one({"id": data.get("plan_id")}, {"_id": 0, "tenant_id": 1})
    doc['tenant_id'] = (plan_for_tenant2 or {}).get("tenant_id") or user.get("tenant_id") or DEFAULT_TENANT_ID
    await db.payments.insert_one(doc)
    
    return {"payment_id": payment_obj.id, "message": "Manual payment created, waiting for verification"}

@router.put("/payments/{payment_id}/verify-manual")
async def verify_manual_payment(payment_id: str, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Check if already verified
    if payment.get("status") == "verified":
        raise HTTPException(status_code=400, detail="Payment already verified")
    
    await db.payments.update_one({"id": payment_id}, {"$set": {"status": "verified", "verified_at": datetime.now(timezone.utc).isoformat()}})
    
    # Create subscriber
    plan = await db.plans.find_one({"id": payment["plan_id"]}, {"_id": 0})
    if plan:
        # Check if subscriber already exists
        existing = await db.subscribers.find_one({
            "telegram_user_id": payment["telegram_user_id"],
            "plan_id": payment["plan_id"],
            "status": "active"
        }, {"_id": 0})
        
        if not existing:
            subscriber_create = SubscriberCreate(
                telegram_user_id=payment["telegram_user_id"],
                telegram_username=payment.get("telegram_username"),
                plan_id=payment["plan_id"],
                payment_method="manual",
                payment_id=payment["id"]
            )
            # Run subscriber creation in background
            background_tasks.add_task(create_subscriber_task, subscriber_create, plan)
        else:
            # Subscriber exists, just send invite link again
            settings = await get_bot_settings()
            plan_channel = plan.get("channel_id", "") or settings.get("telegram_channel_id", "")
            if plan_channel:
                background_tasks.add_task(add_to_channel, payment["telegram_user_id"], plan_channel, plan["name"])
    
    # Send success message to user
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if bot_token and payment.get("telegram_user_id"):
        success_msg = "✅ <b>Payment Verified!</b>\n\n"
        success_msg += f"📦 Plan: <b>{payment.get('plan_name', 'N/A')}</b>\n"
        success_msg += f"💰 Amount: ₹{payment.get('amount', 0)}\n\n"
        success_msg += "🎉 Your subscription is now active!\n"
        success_msg += "📨 You'll receive the channel invite link shortly."
        await send_telegram_message(payment["telegram_user_id"], success_msg, bot_token)
    
    # Notify admin on Telegram (with screenshot)
    background_tasks.add_task(
        notify_admin_new_payment,
        payment.get("telegram_user_id", ""),
        payment.get("telegram_username", ""),
        payment.get("plan_name", "N/A"),
        payment.get("amount", 0),
        payment.get("screenshot_file_id", "")
    )
    
    return {"message": "Payment verified and subscriber created"}

@router.put("/payments/{payment_id}/reject")
async def reject_payment(payment_id: str, data: dict = None, user = Depends(get_current_user)):
    """Reject a payment"""
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Can reject pending or verified payments
    if payment.get("status") == "rejected":
        raise HTTPException(status_code=400, detail="Payment is already rejected")
    
    reason = data.get("reason", "Payment rejected by admin") if data else "Payment rejected by admin"
    
    await db.payments.update_one(
        {"id": payment_id}, 
        {"$set": {"status": "rejected", "rejection_reason": reason, "rejected_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Optionally notify user via Telegram
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if bot_token and payment.get("telegram_user_id"):
        msg = f"❌ <b>Payment Rejected</b>\n\n"
        msg += f"📦 Plan: {payment.get('plan_name', 'N/A')}\n"
        msg += f"💰 Amount: ₹{payment.get('amount', 0)}\n\n"
        msg += f"📝 Reason: {reason}\n\n"
        msg += "Please contact support if you believe this is an error."
        await send_telegram_message(payment["telegram_user_id"], msg, bot_token)
    
    return {"message": "Payment rejected"}

@router.delete("/payments/{payment_id}")
async def delete_payment(payment_id: str, user = Depends(get_current_user)):
    """Delete a payment record - Admin/Super Admin only"""
    ensure_admin(user)
    
    tenant_id = get_user_tenant(user)
    payment = await db.payments.find_one(tq({"id": payment_id}, tenant_id), {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    await db.payments.delete_one(tq({"id": payment_id}, tenant_id))
    return {"message": "Payment deleted"}

@router.post("/payments/bulk-verify")
async def bulk_verify_payments(data: dict, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    """Verify multiple payments at once"""
    payment_ids = data.get("payment_ids", [])
    if not payment_ids:
        raise HTTPException(status_code=400, detail="No payment IDs provided")
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    verified_count = 0
    for payment_id in payment_ids:
        payment = await db.payments.find_one({"id": payment_id, "status": "pending"}, {"_id": 0})
        if payment:
            await db.payments.update_one({"id": payment_id}, {"$set": {"status": "verified", "verified_at": datetime.now(timezone.utc).isoformat()}})
            
            # Create subscriber
            plan = await db.plans.find_one({"id": payment["plan_id"]}, {"_id": 0})
            if plan:
                # Check if subscriber already exists
                existing = await db.subscribers.find_one({
                    "telegram_user_id": payment["telegram_user_id"],
                    "plan_id": payment["plan_id"],
                    "status": "active"
                }, {"_id": 0})
                
                if not existing:
                    subscriber_create = SubscriberCreate(
                        telegram_user_id=payment["telegram_user_id"],
                        telegram_username=payment.get("telegram_username"),
                        plan_id=payment["plan_id"],
                        payment_method=payment.get("payment_method", "manual"),
                        payment_id=payment["id"]
                    )
                    background_tasks.add_task(create_subscriber_task, subscriber_create, plan)
                else:
                    # Just send invite link
                    plan_channel = plan.get("channel_id", "") or settings.get("telegram_channel_id", "")
                    if plan_channel:
                        background_tasks.add_task(add_to_channel, payment["telegram_user_id"], plan_channel, plan["name"])
                
                # Send success message
                if bot_token and payment.get("telegram_user_id"):
                    success_msg = "✅ <b>Payment Verified!</b>\n\n"
                    success_msg += f"📦 Plan: <b>{payment.get('plan_name', plan.get('name', 'N/A'))}</b>\n"
                    success_msg += f"💰 Amount: ₹{payment.get('amount', 0)}\n\n"
                    success_msg += "🎉 Your subscription is now active!"
                    await send_telegram_message(payment["telegram_user_id"], success_msg, bot_token)
            
            verified_count += 1
    
    return {"message": f"{verified_count} payments verified", "verified_count": verified_count}

@router.post("/payments/bulk-reject")
async def bulk_reject_payments(data: dict, user = Depends(get_current_user)):
    """Reject multiple payments at once"""
    payment_ids = data.get("payment_ids", [])
    reason = data.get("reason", "Payment rejected by admin")
    if not payment_ids:
        raise HTTPException(status_code=400, detail="No payment IDs provided")
    
    rejected_count = 0
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    for payment_id in payment_ids:
        payment = await db.payments.find_one({"id": payment_id, "status": "pending"}, {"_id": 0})
        if payment:
            await db.payments.update_one(
                {"id": payment_id}, 
                {"$set": {"status": "rejected", "rejection_reason": reason, "rejected_at": datetime.now(timezone.utc).isoformat()}}
            )
            
            # Notify user via Telegram
            if bot_token and payment.get("telegram_user_id"):
                msg = f"❌ <b>Payment Rejected</b>\n\n"
                msg += f"📦 Plan: {payment.get('plan_name', 'N/A')}\n"
                msg += f"💰 Amount: ₹{payment.get('amount', 0)}\n\n"
                msg += f"📝 Reason: {reason}"
                await send_telegram_message(payment["telegram_user_id"], msg, bot_token)
            rejected_count += 1
    
    return {"message": f"{rejected_count} payments rejected", "rejected_count": rejected_count}

@router.post("/payments/bulk-delete")
async def bulk_delete_payments(data: dict, user = Depends(get_current_user)):
    """Delete multiple payments at once - Admin only"""
    ensure_admin(user)
    
    payment_ids = data.get("payment_ids", [])
    if not payment_ids:
        raise HTTPException(status_code=400, detail="No payment IDs provided")
    
    tenant_id = get_user_tenant(user)
    result = await db.payments.delete_many(tq({"id": {"$in": payment_ids}}, tenant_id))
    return {"message": f"{result.deleted_count} payments deleted", "deleted_count": result.deleted_count}

async def create_subscriber_task(subscriber_create: SubscriberCreate, plan: dict):
    """Background task to create subscriber after payment verification"""
    try:
        settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
        grace_days = settings.get("grace_period_days", 2)
        plan_channel = plan.get("channel_id", "")
        
        end_date = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])
        grace_end = end_date + timedelta(days=grace_days)
        
        subscriber_obj = Subscriber(
            telegram_user_id=subscriber_create.telegram_user_id,
            telegram_username=subscriber_create.telegram_username,
            plan_id=subscriber_create.plan_id,
            plan_name=plan["name"],
            payment_method=subscriber_create.payment_method,
            payment_id=subscriber_create.payment_id,
            end_date=end_date,
            grace_end_date=grace_end
        )
        
        doc = subscriber_obj.model_dump()
        doc['start_date'] = doc['start_date'].isoformat()
        doc['end_date'] = doc['end_date'].isoformat()
        doc['grace_end_date'] = doc['grace_end_date'].isoformat()
        doc['created_at'] = doc['created_at'].isoformat()
        doc['tenant_id'] = plan.get("tenant_id", DEFAULT_TENANT_ID)
        
        await db.subscribers.insert_one(doc)
        
        # Add to channel (uses default channel if plan has no specific channel)
        added = await add_to_channel(subscriber_create.telegram_user_id, plan_channel, plan["name"], use_default=True)
        logger.info(f"Add to channel result for {subscriber_create.telegram_user_id}: {added}")
        
        # Handle group assignment if plan has auto_assign_group or group_id
        if plan.get("auto_assign_group"):
            available_group = await get_available_chat_group()
            if available_group:
                result = await assign_chat_group(
                    available_group["group_id"],
                    subscriber_create.telegram_user_id,
                    subscriber_create.telegram_username or "",
                    f"plan_{plan['id']}",
                    plan['duration_days'] * 24 * 60
                )
                logger.info(f"Auto-assigned group for {subscriber_create.telegram_user_id}: {result}")
        elif plan.get("group_id"):
            # Send group invite link
            bot_token = settings.get("telegram_bot_token", "")
            if bot_token:
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
                                msg = f"👥 <b>Group Access for {plan['name']}:</b>\n{invite_link}"
                                await send_telegram_message(subscriber_create.telegram_user_id, msg, bot_token)
                except Exception as e:
                    logger.error(f"Error creating group invite: {e}")
        
        # Notify admin
        from services.telegram import notify_admin_new_payment as _notify_admin
        await _notify_admin(
            subscriber_create.telegram_user_id,
            subscriber_create.telegram_username or "",
            plan["name"],
            plan.get("price", 0),
            payment_status="verified"
        )
        
        # Send welcome message
        welcome_msg = settings.get("success_message", "🎉 Payment verified! Your subscription is now active.")
        bot_token = settings.get("telegram_bot_token", "")
        if bot_token and welcome_msg:
            full_msg = f"{welcome_msg}\n\n📦 Plan: <b>{plan['name']}</b>\n⏱ Duration: <b>{plan['duration_days']} days</b>"
            await send_telegram_message(subscriber_create.telegram_user_id, full_msg, bot_token)
    except Exception as e:
        logger.error(f"Error in create_subscriber_task: {e}")



@router.post("/subscribers/bulk-add-to-channel")
async def bulk_add_subscribers_to_channel(user = Depends(get_current_user)):
    """Add all active subscribers to the default channel - one time fix"""
    settings = await get_bot_settings()
    channel_id = settings.get("telegram_channel_id", "")
    bot_token = settings.get("telegram_bot_token", "")
    
    if not channel_id or not bot_token:
        raise HTTPException(status_code=400, detail="Channel ID or Bot Token not configured")
    
    active_subs = await db.subscribers.find({"status": "active"}, {"_id": 0}).to_list(1000)
    
    results = {"success": 0, "failed": 0, "total": len(active_subs), "details": []}
    
    for sub in active_subs:
        user_id = sub.get("telegram_user_id", "")
        if not user_id:
            continue
        
        # Look up plan for channel override
        plan = await db.plans.find_one({"id": sub.get("plan_id", "")}, {"_id": 0})
        plan_channel = plan.get("channel_id", "") if plan else ""
        plan_name = sub.get("plan_name", "")
        
        added = await add_to_channel(user_id, plan_channel, plan_name, use_default=True)
        if added:
            results["success"] += 1
            results["details"].append({"user_id": user_id, "status": "invite_sent"})
        else:
            results["failed"] += 1
            results["details"].append({"user_id": user_id, "error": "Failed - bot may not be admin in channel"})
        
        # Small delay to avoid Telegram rate limits
        await asyncio.sleep(0.5)
    
    logger.info(f"Bulk add results: {results['success']} success, {results['failed']} failed out of {results['total']}")
    return results

# ============== SETTINGS ROUTES ==============

@router.get("/settings")
async def get_settings(user = Depends(get_current_user)):
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0})
    if not settings:
        settings = BotSettings().model_dump()
    return settings

@router.put("/settings")
async def update_settings(settings: BotSettings, user = Depends(get_current_user)):
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
    
    doc = settings.model_dump()
    await db.settings.update_one({"id": "bot_settings"}, {"$set": doc}, upsert=True)
    
    TELEGRAM_BOT_TOKEN = settings.telegram_bot_token
    TELEGRAM_CHANNEL_ID = settings.telegram_channel_id
    
    return {"message": "Settings updated"}

# ============== FILE UPLOAD ROUTES ==============

@router.post("/upload/qr-code")
async def upload_qr_code(file: UploadFile = File(...), user = Depends(get_current_user)):
    """Upload QR code image"""
    # Validate file type
    allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only image files are allowed (PNG, JPG, WEBP, GIF)")
    
    # Validate file size (max 5MB)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be less than 5MB")
    
    # Generate unique filename
    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    filename = f"qr_code_{uuid.uuid4().hex[:8]}.{ext}"
    
    # Save file
    import os as os_mod
    uploads_path = os_mod.path.join(os_mod.path.dirname(os_mod.path.dirname(__file__)), "uploads")
    os_mod.makedirs(uploads_path, exist_ok=True)
    file_path = os_mod.path.join(uploads_path, filename)
    
    with open(file_path, "wb") as f:
        f.write(contents)
    
    # Return the URL - use REACT_APP_BACKEND_URL from environment or construct it
    base_url = os.environ.get("BACKEND_URL", "")
    if not base_url:
        # Fallback to constructing URL
        base_url = os.environ.get("REACT_APP_BACKEND_URL", "").replace("/api", "")
    
    file_url = f"/api/uploads/{filename}"
    
    return {"url": file_url, "filename": filename}

@router.post("/upload/image")
async def upload_image(file: UploadFile = File(...), user = Depends(get_current_user)):
    """Upload general image"""
    # Validate file type
    allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    
    # Validate file size (max 10MB)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")
    
    # Generate unique filename
    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    filename = f"img_{uuid.uuid4().hex[:8]}.{ext}"
    
    # Save file
    import os as os_mod
    uploads_path = os_mod.path.join(os_mod.path.dirname(os_mod.path.dirname(__file__)), "uploads")
    os_mod.makedirs(uploads_path, exist_ok=True)
    file_path = os_mod.path.join(uploads_path, filename)
    
    with open(file_path, "wb") as f:
        f.write(contents)
    
    file_url = f"/api/uploads/{filename}"
    
    return {"url": file_url, "filename": filename}

# ============== ANALYTICS ROUTES ==============

@router.get("/analytics")
async def get_analytics(user = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    tenant_id = get_user_tenant(user)
    
    total_subscribers = await db.subscribers.count_documents(tq({}, tenant_id))
    active_subscribers = await db.subscribers.count_documents(tq({"status": "active"}, tenant_id))
    expired_subscribers = await db.subscribers.count_documents(tq({"status": "expired"}, tenant_id))
    grace_subscribers = await db.subscribers.count_documents(tq({"status": "grace"}, tenant_id))
    
    # Revenue calculation
    verified_payments = await db.payments.find(tq({"status": "verified"}, tenant_id), {"_id": 0}).to_list(10000)
    total_revenue = sum(p.get("amount", 0) for p in verified_payments)
    
    # This month's revenue
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_payments = [p for p in verified_payments 
                       if datetime.fromisoformat(p["created_at"]) >= month_start]
    monthly_revenue = sum(p.get("amount", 0) for p in monthly_payments)
    
    # Recent activity
    recent_subscribers = await db.subscribers.find(tq({}, tenant_id), {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
    recent_payments = await db.payments.find(tq({}, tenant_id), {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
    
    # Plans stats
    plans = await db.plans.find(tq({}, tenant_id), {"_id": 0}).to_list(100)
    plan_stats = []
    for plan in plans:
        count = await db.subscribers.count_documents(tq({"plan_id": plan["id"], "status": "active"}, tenant_id))
        plan_stats.append({"name": plan["name"], "count": count, "price": plan["price"]})
    
    return {
        "total_subscribers": total_subscribers,
        "active_subscribers": active_subscribers,
        "expired_subscribers": expired_subscribers,
        "grace_subscribers": grace_subscribers,
        "total_revenue": total_revenue,
        "monthly_revenue": monthly_revenue,
        "recent_subscribers": recent_subscribers,
        "recent_payments": recent_payments,
        "plan_stats": plan_stats
    }


# ============== PDF EXPORT ==============

@router.get("/analytics/export-pdf")
async def export_revenue_pdf(user = Depends(get_current_user)):
    """Export revenue analytics as PDF"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    
    now = datetime.now(timezone.utc)
    
    # Fetch data
    total_subscribers = await db.subscribers.count_documents({})
    active_subscribers = await db.subscribers.count_documents({"status": "active"})
    expired_subscribers = await db.subscribers.count_documents({"status": "expired"})
    
    verified_payments = await db.payments.find({"status": "verified"}, {"_id": 0}).to_list(10000)
    total_revenue = sum(p.get("amount", 0) for p in verified_payments)
    
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_payments = [p for p in verified_payments if datetime.fromisoformat(p["created_at"]) >= month_start]
    monthly_revenue = sum(p.get("amount", 0) for p in monthly_payments)
    
    plans = await db.plans.find({}, {"_id": 0}).to_list(100)
    plan_stats = []
    for plan in plans:
        count = await db.subscribers.count_documents({"plan_id": plan["id"], "status": "active"})
        plan_stats.append({"name": plan["name"], "count": count, "price": plan["price"]})
    
    # Recent payments
    recent = await db.payments.find({"status": "verified"}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
    
    # Build PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=22, textColor=colors.HexColor('#e11d48'))
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=14, textColor=colors.HexColor('#666666'))
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=16, textColor=colors.HexColor('#333333'))
    
    elements = []
    
    # Header
    elements.append(Paragraph("TGSubsBot Revenue Report", title_style))
    elements.append(Paragraph(f"Generated: {now.strftime('%d %B %Y, %I:%M %p')} UTC", subtitle_style))
    elements.append(Spacer(1, 20))
    
    # Summary Table
    elements.append(Paragraph("Summary", heading_style))
    summary_data = [
        ["Metric", "Value"],
        ["Total Revenue", f"Rs. {total_revenue:,.0f}"],
        ["Monthly Revenue", f"Rs. {monthly_revenue:,.0f}"],
        ["Total Subscribers", str(total_subscribers)],
        ["Active Subscribers", str(active_subscribers)],
        ["Expired Subscribers", str(expired_subscribers)],
        ["ARPU", f"Rs. {(total_revenue / active_subscribers if active_subscribers else 0):,.0f}"],
    ]
    t = Table(summary_data, colWidths=[3*inch, 3*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e11d48')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))
    
    # Plan Stats
    if plan_stats:
        elements.append(Paragraph("Plan Performance", heading_style))
        plan_data = [["Plan Name", "Active Subs", "Price"]]
        for ps in plan_stats:
            plan_data.append([ps["name"], str(ps["count"]), f"Rs. {ps['price']:,.0f}"])
        t2 = Table(plan_data, colWidths=[2.5*inch, 1.5*inch, 2*inch])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t2)
        elements.append(Spacer(1, 20))
    
    # Recent Payments
    if recent:
        elements.append(Paragraph("Recent Payments (Last 20)", heading_style))
        pay_data = [["User", "Plan", "Amount", "Date"]]
        for p in recent:
            pay_data.append([
                p.get("telegram_username", p.get("telegram_user_id", "N/A"))[:20],
                p.get("plan_name", "N/A")[:25],
                f"Rs. {p.get('amount', 0):,.0f}",
                datetime.fromisoformat(p["created_at"]).strftime("%d %b %Y") if p.get("created_at") else "N/A"
            ])
        t3 = Table(pay_data, colWidths=[1.5*inch, 2*inch, 1.2*inch, 1.3*inch])
        t3.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e11d48')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(t3)
    
    doc.build(elements)
    buffer.seek(0)
    
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=TGSubsBot_Revenue_{now.strftime('%Y%m%d')}.pdf"}
    )


# ============== WHITE-LABEL BRANDING ==============

@router.get("/branding")
async def get_branding(user = Depends(get_current_user)):
    """Get white-label branding settings"""
    defaults = {
        "brand_name": "TGSubsBot",
        "tagline": "Premium Subscriptions",
        "primary_color": "#e11d48",
        "secondary_color": "#1a1a2e",
        "logo_url": "",
        "favicon_url": "",
        "custom_css": "",
        "footer_text": "Powered by TGSubsBot"
    }
    branding = await db.branding.find_one({}, {"_id": 0})
    if branding:
        # Merge with defaults
        for key in defaults:
            if key not in branding:
                branding[key] = defaults[key]
    else:
        branding = defaults
    return branding

@router.put("/branding")
async def update_branding(data: dict, user = Depends(get_current_user)):
    """Update white-label branding settings (Super Admin only)"""
    if not is_super_admin(user):
        raise HTTPException(status_code=403, detail="Only super admins can update branding")
    
    allowed_fields = ["brand_name", "tagline", "primary_color", "secondary_color", "logo_url", "favicon_url", "custom_css", "footer_text"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    await db.branding.update_one({}, {"$set": update_data}, upsert=True)
    return {"message": "Branding updated", "branding": update_data}


# ============== BOT LANGUAGE SETTINGS ==============

@router.get("/bot-language")
async def get_bot_language(user = Depends(get_current_user)):
    """Get bot language settings"""
    defaults = {
        "default_language": "hinglish",
        "available_languages": ["english", "hindi", "hinglish"],
        "messages": {
            "english": {
                "welcome": "Welcome! Choose your subscription plan:",
                "payment_verified": "Payment Verified! Your subscription is now active.",
                "payment_rejected": "Payment Rejected! Please try again with a valid screenshot.",
                "expired": "Your subscription has expired. Renew now!",
                "choose_plan": "Choose Your Plan",
                "back_to_plans": "Back to Plans",
                "check_status": "Check My Status",
                "send_screenshot": "Send payment screenshot to verify",
                "screenshot_received": "Screenshot Received! Admin verification pending...",
                "cancel": "Cancelled! Send /start to try again."
            },
            "hindi": {
                "welcome": "Namaste! Apna subscription plan chuniye:",
                "payment_verified": "Payment Verify Ho Gaya! Aapka subscription active hai.",
                "payment_rejected": "Payment Reject Ho Gaya! Sahi screenshot bhejiye.",
                "expired": "Aapka subscription khatam ho gaya. Abhi renew kariye!",
                "choose_plan": "Apna Plan Chuniye",
                "back_to_plans": "Plans Pe Wapas Jaayein",
                "check_status": "Apna Status Check Karein",
                "send_screenshot": "Payment screenshot bhejiye verify karne ke liye",
                "screenshot_received": "Screenshot Mila! Admin verification pending hai...",
                "cancel": "Cancel Ho Gaya! /start bhejiye dobara try karne ke liye."
            },
            "hinglish": {
                "welcome": "Welcome! Apna subscription plan choose karo:",
                "payment_verified": "Payment Verified! Tera subscription ab active hai.",
                "payment_rejected": "Payment Reject! Sahi screenshot bhejo bhai.",
                "expired": "Tera subscription expire ho gaya. Abhi renew kar!",
                "choose_plan": "Apna Plan Choose Karo",
                "back_to_plans": "Plans Pe Wapas Jao",
                "check_status": "Apna Status Check Karo",
                "send_screenshot": "Payment screenshot bhejo verify karne ke liye",
                "screenshot_received": "Screenshot Mil Gaya! Admin verify karega thodi der mein...",
                "cancel": "Cancel ho gaya! /start bhejo phir se try karne ke liye."
            }
        }
    }
    lang_settings = await db.bot_language.find_one({}, {"_id": 0})
    if lang_settings:
        # Merge with defaults - ensure all fields exist
        for key in defaults:
            if key not in lang_settings:
                lang_settings[key] = defaults[key]
            elif key == "messages":
                for lang in defaults["messages"]:
                    if lang not in lang_settings.get("messages", {}):
                        lang_settings.setdefault("messages", {})[lang] = defaults["messages"][lang]
    else:
        lang_settings = defaults
    return lang_settings

@router.put("/bot-language")
async def update_bot_language(data: dict, user = Depends(get_current_user)):
    """Update bot language settings"""
    default_lang = data.get("default_language")
    custom_messages = data.get("messages")
    
    update = {}
    if default_lang and default_lang in ["english", "hindi", "hinglish"]:
        update["default_language"] = default_lang
    if custom_messages and isinstance(custom_messages, dict):
        for lang, msgs in custom_messages.items():
            for key, val in msgs.items():
                update[f"messages.{lang}.{key}"] = val
    
    if not update:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    await db.bot_language.update_one({}, {"$set": update}, upsert=True)
    return {"message": "Language settings updated"}

# ============== MESSAGE TEMPLATES ROUTES ==============
