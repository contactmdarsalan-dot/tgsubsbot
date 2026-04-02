"""Broadcast, Templates, Scheduled Broadcast, Renewal Broadcast routes"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from database import db
from services.auth import get_current_user
from services.telegram import (
    get_bot_settings, get_bot_username, send_telegram_message,
    send_telegram_message_with_buttons
)
from services.tenant import DEFAULT_TENANT_ID
from services.permissions import get_user_tenant, tq
from config import logger
from models import MessageTemplate
from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone, timedelta
import uuid
import httpx
import asyncio

router = APIRouter()


# ============== MESSAGE TEMPLATES ROUTES ==============

@router.get("/templates")
async def get_templates(user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    templates = await db.templates.find(tq({}, tenant_id), {"_id": 0}).to_list(100)
    return templates

@router.post("/templates")
async def create_template(template: MessageTemplate, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    doc = template.model_dump()
    doc["tenant_id"] = tenant_id
    await db.templates.insert_one(doc)
    return {"message": "Template created", "id": template.id}

@router.put("/templates/{template_id}")
async def update_template(template_id: str, template: MessageTemplate, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    doc = template.model_dump()
    await db.templates.update_one(tq({"id": template_id}, tenant_id), {"$set": doc})
    return {"message": "Template updated"}

@router.delete("/templates/{template_id}")
async def delete_template(template_id: str, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    await db.templates.delete_one(tq({"id": template_id}, tenant_id))
    return {"message": "Template deleted"}

@router.post("/promote-plan")
async def promote_plan_to_group(data: dict, user=Depends(get_current_user)):
    """Promote a plan to Telegram group/channel"""
    tenant_id = get_user_tenant(user)
    plan_id = data.get("plan_id")
    target = data.get("target", "channel")

    plan = await db.plans.find_one(tq({"id": plan_id}, tenant_id), {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    channel_id = settings.get("telegram_channel_id", "")
    bot_username = await get_bot_username(bot_token)

    msg = f"<b>{plan['name']}</b>\n\n"
    msg += f"Price: <b>Rs.{plan['price']}</b>\n"
    msg += f"Duration: <b>{plan['duration_days']} days</b>\n\n"

    if plan.get('features'):
        msg += "<b>Features:</b>\n"
        for feat in plan['features']:
            msg += f"  {feat}\n"
        msg += "\n"

    if plan.get('discount_percentage', 0) > 0:
        original = plan['price']
        discounted = original * (1 - plan['discount_percentage'] / 100)
        msg += f"<b>SPECIAL OFFER: {plan['discount_percentage']}% OFF!</b>\n"
        msg += f"<s>Rs.{original}</s> Rs.{discounted:.0f}\n\n"

    msg += "Subscribe now!"

    buttons = [[{
        "text": f"Subscribe - Rs.{plan['price']}",
        "url": f"https://t.me/{bot_username}?start=plan_{plan['id']}"
    }]]

    target_id = channel_id
    if target == "group" and plan.get("group_id"):
        target_id = plan["group_id"]

    if not target_id:
        raise HTTPException(status_code=400, detail="No target channel/group configured")

    await send_telegram_message_with_buttons(target_id, msg, buttons, bot_token)
    return {"message": "Plan promoted successfully"}


# ============== BROADCAST ROUTES ==============

class BroadcastRequest(BaseModel):
    message: str
    target_segment: str = "all"
    buttons: list = []
    include_promo: bool = False

@router.post("/broadcast")
async def send_broadcast(request: BroadcastRequest, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    """Send broadcast to all/targeted subscribers"""
    tenant_id = get_user_tenant(user)
    query = tq({}, tenant_id)

    if request.target_segment == "active":
        query["status"] = "active"
    elif request.target_segment == "expired":
        query["status"] = {"$in": ["expired", "cancelled"]}
    elif request.target_segment == "grace":
        query["status"] = "grace"

    subscribers = await db.subscribers.find(query, {"_id": 0}).to_list(50000)
    user_ids = list(set(str(sub.get("telegram_user_id")) for sub in subscribers if sub.get("telegram_user_id")))

    if request.include_promo:
        promo_users = await db.bot_users.find(tq({}, tenant_id), {"_id": 0}).to_list(50000)
        for pu in promo_users:
            uid = str(pu.get("telegram_user_id", ""))
            if uid and uid not in user_ids:
                user_ids.append(uid)

    if not user_ids:
        raise HTTPException(status_code=400, detail="No users to broadcast to")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    broadcast_id = str(uuid.uuid4())
    broadcast_record = {
        "id": broadcast_id,
        "type": "broadcast",
        "message": request.message,
        "target_segment": request.target_segment,
        "total_users": len(user_ids),
        "sent_count": 0,
        "failed_count": 0,
        "status": "in_progress",
        "tenant_id": tenant_id,
        "created_by": user.get("email", "admin"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.broadcasts.insert_one(broadcast_record)

    background_tasks.add_task(
        send_broadcast_messages,
        broadcast_id,
        user_ids,
        request.message,
        request.buttons,
        bot_token
    )

    return {"broadcast_id": broadcast_id, "total_users": len(user_ids)}

async def send_broadcast_messages(broadcast_id: str, user_ids: list, message: str, buttons: list, bot_token: str):
    """Background task to send broadcast messages"""
    sent_count = 0
    failed_count = 0

    for user_id in user_ids:
        try:
            if buttons:
                await send_telegram_message_with_buttons(user_id, message, buttons, bot_token)
            else:
                await send_telegram_message(user_id, message, bot_token)
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
            failed_count += 1

        await asyncio.sleep(0.05)

    await db.broadcasts.update_one(
        {"id": broadcast_id},
        {"$set": {
            "sent_count": sent_count,
            "failed_count": failed_count,
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat()
        }}
    )

@router.get("/broadcasts")
async def get_broadcasts(user=Depends(get_current_user)):
    """Get all broadcast history"""
    tenant_id = get_user_tenant(user)
    broadcasts = await db.broadcasts.find(tq({}, tenant_id), {"_id": 0}).sort("created_at", -1).to_list(100)
    return broadcasts

@router.get("/broadcasts/{broadcast_id}")
async def get_broadcast(broadcast_id: str, user=Depends(get_current_user)):
    """Get single broadcast details"""
    tenant_id = get_user_tenant(user)
    broadcast = await db.broadcasts.find_one(tq({"id": broadcast_id}, tenant_id), {"_id": 0})
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    return broadcast


# ============== PAID POST BROADCAST ==============

@router.post("/paid-posts/{post_id}/broadcast")
async def broadcast_paid_post(post_id: str, data: dict, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    """Broadcast a paid post preview to all subscribers"""
    tenant_id = get_user_tenant(user)
    post = await db.paid_posts.find_one(tq({"id": post_id}, tenant_id), {"_id": 0})
    if not post:
        raise HTTPException(status_code=404, detail="Paid post not found")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    bot_username = await get_bot_username(bot_token)

    target = data.get("target", "all")
    query = tq({}, tenant_id)
    if target == "active":
        query["status"] = "active"

    subscribers = await db.subscribers.find(query, {"_id": 0}).to_list(50000)
    user_ids = list(set(str(sub.get("telegram_user_id")) for sub in subscribers if sub.get("telegram_user_id")))

    if data.get("include_non_subscribers"):
        all_users = await db.bot_users.find(tq({}, tenant_id), {"_id": 0}).to_list(50000)
        for u in all_users:
            uid = str(u.get("telegram_user_id", ""))
            if uid and uid not in user_ids:
                user_ids.append(uid)

    if not user_ids:
        raise HTTPException(status_code=400, detail="No users to send to")

    broadcast_id = str(uuid.uuid4())
    broadcast_record = {
        "id": broadcast_id,
        "type": "paid_post_broadcast",
        "post_id": post_id,
        "total_users": len(user_ids),
        "sent_count": 0,
        "failed_count": 0,
        "status": "in_progress",
        "tenant_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.broadcasts.insert_one(broadcast_record)

    background_tasks.add_task(send_paid_post_broadcast, broadcast_id, post_id, user_ids, bot_token)

    return {"broadcast_id": broadcast_id, "total_users": len(user_ids)}

async def send_paid_post_broadcast(broadcast_id: str, post_id: str, user_ids: list, bot_token: str):
    """Background task to send paid post broadcasts"""
    from services.telegram import send_telegram_photo, send_telegram_video

    post = await db.paid_posts.find_one({"id": post_id}, {"_id": 0})
    if not post:
        return

    bot_username = await get_bot_username(bot_token)
    sent_count = 0
    failed_count = 0

    for user_id in user_ids:
        try:
            if post.get("content_type") == "photo" and post.get("blurred_file_id"):
                caption = f"<b>Premium Content</b>\n\n"
                if post.get("caption"):
                    caption += f"{post['caption']}\n\n"
                caption += f"Price: Rs.{int(post.get('price', 0))}\n"
                caption += "Unlock to see full content!"

                await send_telegram_photo(user_id, post["blurred_file_id"], caption, bot_token)
            elif post.get("content_type") == "video":
                msg = f"<b>Premium Video Content</b>\n\n"
                if post.get("caption"):
                    msg += f"{post['caption']}\n\n"
                msg += f"Price: Rs.{int(post.get('price', 0))}\n"
                msg += "Pay to unlock!"

                buttons = [[{
                    "text": f"Unlock - Rs.{int(post.get('price', 0))}",
                    "url": f"https://t.me/{bot_username}?start=unlock_{post_id}"
                }]]
                await send_telegram_message_with_buttons(user_id, msg, buttons, bot_token)
            else:
                msg = f"<b>Premium Content Available!</b>\n\n"
                msg += f"Price: Rs.{int(post.get('price', 0))}\n"
                msg += "Pay to unlock!"

                buttons = [[{
                    "text": f"Unlock - Rs.{int(post.get('price', 0))}",
                    "url": f"https://t.me/{bot_username}?start=unlock_{post_id}"
                }]]
                await send_telegram_message_with_buttons(user_id, msg, buttons, bot_token)

            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
            failed_count += 1

        await asyncio.sleep(0.05)

    await db.broadcasts.update_one(
        {"id": broadcast_id},
        {"$set": {
            "sent_count": sent_count,
            "failed_count": failed_count,
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat()
        }}
    )


# ============== SCHEDULED BROADCAST APIs ==============

@router.get("/scheduled-broadcasts")
async def get_scheduled_broadcasts(user=Depends(get_current_user)):
    """Get all scheduled broadcasts"""
    tenant_id = get_user_tenant(user)
    broadcasts = await db.scheduled_broadcasts.find(tq({}, tenant_id), {"_id": 0}).sort("scheduled_at", 1).to_list(1000)
    return broadcasts

@router.post("/scheduled-broadcasts")
async def create_scheduled_broadcast(data: dict, user=Depends(get_current_user)):
    """Create a scheduled broadcast"""
    tenant_id = get_user_tenant(user)
    broadcast_data = {
        "id": str(uuid.uuid4()),
        "message": data.get("message", ""),
        "target_segment": data.get("target_segment", "all"),
        "scheduled_at": data.get("scheduled_at"),
        "status": "pending",
        "sent_count": 0,
        "tenant_id": tenant_id,
        "created_by": user.get("email", "admin"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.scheduled_broadcasts.insert_one(broadcast_data)
    return {"message": "Broadcast scheduled", "broadcast": broadcast_data}

@router.delete("/scheduled-broadcasts/{broadcast_id}")
async def cancel_scheduled_broadcast(broadcast_id: str, user=Depends(get_current_user)):
    """Cancel a scheduled broadcast"""
    tenant_id = get_user_tenant(user)
    await db.scheduled_broadcasts.update_one(
        tq({"id": broadcast_id}, tenant_id),
        {"$set": {"status": "cancelled"}}
    )
    return {"message": "Broadcast cancelled"}


# ============== RENEWAL BROADCAST ==============

@router.post("/renewal-broadcast")
async def send_renewal_broadcast(data: dict, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    """Send renewal reminder to expired/expiring subscribers"""
    tenant_id = get_user_tenant(user)
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot token not configured")

    target = data.get("target", "expired")
    message = data.get("message", "")
    video_note_file_id = data.get("video_note_file_id")
    discount_percent = data.get("discount_percent", 0)

    now = datetime.now(timezone.utc)
    user_ids = set()

    if target in ["expired", "all"]:
        expired = await db.subscribers.find(
            tq({"status": {"$in": ["expired", "cancelled"]}}, tenant_id),
            {"_id": 0}
        ).to_list(10000)
        for sub in expired:
            if sub.get("telegram_user_id"):
                user_ids.add(str(sub["telegram_user_id"]))

    if target in ["expiring_soon", "all"]:
        three_days_later = (now + timedelta(days=3)).isoformat()
        expiring = await db.subscribers.find(
            tq({"status": "active", "end_time": {"$lte": three_days_later}}, tenant_id),
            {"_id": 0}
        ).to_list(10000)
        for sub in expiring:
            if sub.get("telegram_user_id"):
                user_ids.add(str(sub["telegram_user_id"]))

    if not user_ids:
        return {"message": "No users to send renewal to", "count": 0}

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
            msg = "<b>Time to Renew!</b>\n\n"
            if message:
                msg += f"{message}\n\n"
            else:
                msg += "Your subscription has expired or is about to expire.\n"
                msg += "Don't miss out on exclusive content!\n\n"

            if discount_percent > 0:
                msg += f"<b>Special Offer: {discount_percent}% OFF!</b>\n\n"

            msg += "<b>Renew Now!</b>"

            buttons = [[{
                "text": "Renew Subscription",
                "url": f"https://t.me/{bot_username}?start=subscribe"
            }]]

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
