"""Subscribers CRUD, renewal, and bulk operations"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from database import db
from services.auth import get_current_user
from services.telegram import get_bot_settings, send_telegram_message, add_to_channel, remove_from_channel, notify_admin_new_payment
from services.tenant import DEFAULT_TENANT_ID
from services.permissions import get_user_tenant, tq
from services.chat_pool import get_available_chat_group, assign_chat_group
from config import logger
from models import SubscriberCreate, Subscriber
from typing import Optional
from datetime import datetime, timezone, timedelta
import uuid
import httpx
import asyncio

router = APIRouter()


@router.get("/subscribers")
async def get_subscribers(status: Optional[str] = None, page: int = 1, limit: int = 50, search: str = None, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    base_query = tq({"source": {"$ne": "miniapp"}}, tenant_id)
    
    list_query = dict(base_query)
    if status:
        list_query["status"] = status
    if search:
        search = search.strip()
        list_query["$or"] = [
            {"telegram_user_id": {"$regex": search, "$options": "i"}},
            {"telegram_username": {"$regex": search, "$options": "i"}},
        ]
    
    # Pagination
    skip = (max(1, page) - 1) * limit
    limit = min(limit, 200)
    
    subscribers = await db.subscribers.find(list_query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    plans = await db.plans.find({}, {"_id": 0}).to_list(100)
    plans_map = {p["id"]: p for p in plans}

    groups = await db.chat_groups_pool.find({}, {"_id": 0}).to_list(100)
    groups_by_user = {g.get("assigned_to_user_id", ""): g for g in groups if g.get("assigned_to_user_id")}
    groups_by_id = {g.get("group_id", ""): g for g in groups}

    for sub in subscribers:
        for field in ['start_date', 'end_date', 'grace_end_date', 'created_at']:
            if isinstance(sub.get(field), str):
                sub[field] = datetime.fromisoformat(sub[field])

        plan = plans_map.get(sub.get("plan_id", ""), {})
        sub["channel_id"] = plan.get("channel_id", "")

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

    # Server-side counts
    total_count = await db.subscribers.count_documents(list_query)
    all_query = dict(base_query)
    total_all = await db.subscribers.count_documents(all_query)
    active_count = await db.subscribers.count_documents({**base_query, "status": "active"})
    expired_count = await db.subscribers.count_documents({**base_query, "status": "expired"})

    return {
        "subscribers": subscribers,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit if limit > 0 else 1,
        "stats": {
            "total_subscribers": total_all,
            "active_count": active_count,
            "expired_count": expired_count
        }
    }


@router.post("/subscribers", response_model=Subscriber)
async def create_subscriber(subscriber: SubscriberCreate, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
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

    plan_channel = plan.get("channel_id", "")
    background_tasks.add_task(add_to_channel, subscriber.telegram_user_id, plan_channel, plan["name"])

    website_link = settings.get("website_link", "")
    if website_link:
        background_tasks.add_task(send_telegram_message, subscriber.telegram_user_id,
            f"Check out our services: {website_link}")

    return sub_obj


@router.put("/subscribers/{subscriber_id}/renew")
async def renew_subscriber(subscriber_id: str, plan_id: str, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
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

    plan_channel = plan.get("channel_id", "")
    background_tasks.add_task(send_renewal_notification, subscriber["telegram_user_id"], plan, plan_channel, end_date)

    return {"message": "Subscription renewed"}


async def send_renewal_notification(user_id: str, plan: dict, plan_channel: str, end_date: datetime):
    """Send renewal notification with channel invite"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    msg = f"<b>Subscription Renewed!</b>\n\n"
    msg += f"Plan: <b>{plan['name']}</b>\n"
    msg += f"Duration: <b>{plan['duration_days']} days</b>\n"
    msg += f"Valid till: <b>{end_date.strftime('%d %b %Y')}</b>\n\n"
    msg += "Thank you for continuing with us!"

    await send_telegram_message(user_id, msg, bot_token)
    await add_to_channel(user_id, plan_channel, plan['name'])


@router.delete("/subscribers/{subscriber_id}")
async def delete_subscriber(subscriber_id: str, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    subscriber = await db.subscribers.find_one({"id": subscriber_id}, {"_id": 0})
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    plan = await db.plans.find_one({"id": subscriber.get("plan_id")}, {"_id": 0})
    plan_channel = plan.get("channel_id", "") if plan else ""

    await db.subscribers.delete_one({"id": subscriber_id})
    background_tasks.add_task(remove_from_channel, subscriber["telegram_user_id"], plan_channel)

    return {"message": "Subscriber removed"}


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

        added = await add_to_channel(subscriber_create.telegram_user_id, plan_channel, plan["name"], use_default=True)
        logger.info(f"Add to channel result for {subscriber_create.telegram_user_id}: {added}")

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
                                msg = f"<b>Group Access for {plan['name']}:</b>\n{invite_link}"
                                await send_telegram_message(subscriber_create.telegram_user_id, msg, bot_token)
                except Exception as e:
                    logger.error(f"Error creating group invite: {e}")

        await notify_admin_new_payment(
            subscriber_create.telegram_user_id,
            subscriber_create.telegram_username or "",
            plan["name"],
            plan.get("price", 0),
            payment_status="verified"
        )

        welcome_msg = settings.get("success_message", "Payment verified! Your subscription is now active.")
        bot_token = settings.get("telegram_bot_token", "")
        if bot_token and welcome_msg:
            full_msg = f"{welcome_msg}\n\nPlan: <b>{plan['name']}</b>\nDuration: <b>{plan['duration_days']} days</b>"
            await send_telegram_message(subscriber_create.telegram_user_id, full_msg, bot_token)
    except Exception as e:
        logger.error(f"Error in create_subscriber_task: {e}")


@router.post("/subscribers/bulk-add-to-channel")
async def bulk_add_subscribers_to_channel(user=Depends(get_current_user)):
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

        await asyncio.sleep(0.5)

    logger.info(f"Bulk add results: {results['success']} success, {results['failed']} failed out of {results['total']}")
    return results
