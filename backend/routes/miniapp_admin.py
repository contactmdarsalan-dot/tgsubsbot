"""Mini App Admin endpoints - Stats, Payment Actions, Subscribers, Broadcast, Live, Paid Posts, Tenant"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form
from database import db
from services.telegram import get_bot_settings, send_telegram_message, add_to_channel
from services.tenant import DEFAULT_TENANT_ID, tenant_query
from config import logger
from datetime import datetime, timezone, timedelta
import uuid
import os

router = APIRouter(prefix="/miniapp")


async def _verify_miniapp_admin(telegram_user_id: str):
    """Check if a telegram user is a registered admin, return admin doc or None"""
    admin = await db.telegram_admins.find_one(
        {"telegram_user_id": str(telegram_user_id), "is_active": True}, {"_id": 0}
    )
    return admin


async def _get_admin_tenant(telegram_user_id: str) -> str:
    """Get the tenant_id for an admin. Falls back to default."""
    admin = await _verify_miniapp_admin(telegram_user_id)
    if admin and admin.get("tenant_id"):
        return admin["tenant_id"]
    return DEFAULT_TENANT_ID


@router.get("/admin/check/{telegram_user_id}")
async def miniapp_admin_check(telegram_user_id: str):
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        return {"is_admin": False, "permissions": [], "name": ""}
    return {
        "is_admin": True, "name": admin.get("name", "Admin"),
        "permissions": admin.get("permissions", []), "role": admin.get("role", "admin"),
    }


@router.get("/admin/stats/{telegram_user_id}")
async def miniapp_admin_stats(telegram_user_id: str):
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    tenant_id = admin.get("tenant_id", DEFAULT_TENANT_ID)

    def tq(q):
        return tenant_query(q, tenant_id)

    total_subs = await db.subscribers.count_documents(tq({}))
    active_subs = await db.subscribers.count_documents(tq({"status": "active"}))
    pending_payments = await db.payments.count_documents(tq({"status": "pending"}))

    pipeline = [
        {"$match": tq({"status": {"$in": ["verified", "approved"]}})},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    rev_result = await db.payments.aggregate(pipeline).to_list(1)
    total_revenue = rev_result[0]["total"] if rev_result else 0

    return {
        "total_subscribers": total_subs, "active_subscribers": active_subs,
        "pending_payments": pending_payments, "total_revenue": total_revenue,
    }


@router.get("/admin/pending-payments/{telegram_user_id}")
async def miniapp_admin_pending_payments(telegram_user_id: str):
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")
    if "verify_payments" not in admin.get("permissions", []):
        raise HTTPException(status_code=403, detail="No payment verification permission")

    payments_list = await db.payments.find(
        tenant_query({"status": "pending"}, admin.get("tenant_id", DEFAULT_TENANT_ID)), {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return payments_list


@router.post("/admin/payment-action")
async def miniapp_admin_payment_action(data: dict):
    telegram_user_id = data.get("telegram_user_id", "")
    payment_id = data.get("payment_id", "")
    action = data.get("action", "")

    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")
    if "verify_payments" not in admin.get("permissions", []):
        raise HTTPException(status_code=403, detail="No permission")

    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Invalid action")

    payment = await db.payments.find_one(tenant_query({"id": payment_id}, admin.get("tenant_id", DEFAULT_TENANT_ID)), {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    new_status = "verified" if action == "approve" else "rejected"
    await db.payments.update_one(
        {"id": payment_id},
        {"$set": {"status": new_status, "verified_by": admin.get("name", "Admin"), "verified_at": datetime.now(timezone.utc).isoformat()}}
    )

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    user_chat_id = payment.get("telegram_user_id", "")

    if bot_token and user_chat_id:
        if action == "approve":
            msg = f"<b>Payment Approved!</b>\n\nAmount: Rs.{payment.get('amount', 0)}\nPlan: {payment.get('plan_name', '')}\n\nYour subscription is now active!"
            await send_telegram_message(user_chat_id, msg, bot_token)

            plan = await db.plans.find_one({"id": payment.get("plan_id")}, {"_id": 0})
            channel_id = ""
            if plan:
                channel_id = plan.get("channel_id", "") or settings.get("telegram_channel_id", "")
            else:
                channel_id = settings.get("telegram_channel_id", "")
            if channel_id:
                await add_to_channel(user_chat_id, channel_id, bot_token)

            await db.subscribers.update_one(
                {"telegram_user_id": user_chat_id},
                {"$set": {
                    "telegram_user_id": user_chat_id, "telegram_username": payment.get("telegram_username", ""),
                    "plan_id": payment.get("plan_id", ""), "plan_name": payment.get("plan_name", ""),
                    "amount_paid": payment.get("amount", 0), "status": "active",
                    "start_date": datetime.now(timezone.utc).isoformat(),
                    "end_date": (datetime.now(timezone.utc) + timedelta(days=plan.get("duration_days", 30) if plan else 30)).isoformat(),
                    "payment_id": payment_id,
                }},
                upsert=True
            )
        else:
            msg = f"<b>Payment Rejected</b>\n\nAmount: Rs.{payment.get('amount', 0)}\nPlan: {payment.get('plan_name', '')}\n\nPlease try again or contact support."
            await send_telegram_message(user_chat_id, msg, bot_token)

    return {"success": True, "new_status": new_status}


@router.get("/admin/subscribers/{telegram_user_id}")
async def miniapp_admin_subscribers(telegram_user_id: str):
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    subs = await db.subscribers.find(
        tenant_query({}, admin.get("tenant_id", DEFAULT_TENANT_ID)), {"_id": 0}
    ).sort("start_date", -1).to_list(100)
    return subs


@router.post("/admin/broadcast")
async def miniapp_admin_broadcast(data: dict, background_tasks: BackgroundTasks):
    telegram_user_id = data.get("telegram_user_id", "")
    message = data.get("message", "").strip()

    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")
    if "broadcast" not in admin.get("permissions", []):
        raise HTTPException(status_code=403, detail="No broadcast permission")
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot token not configured")

    tenant_id = admin.get("tenant_id", DEFAULT_TENANT_ID)
    bot_users = await db.bot_users.find(tenant_query({}, tenant_id), {"_id": 0, "telegram_user_id": 1}).to_list(10000)
    user_ids = [u["telegram_user_id"] for u in bot_users if u.get("telegram_user_id")]

    subs = await db.subscribers.find(tenant_query({}, tenant_id), {"_id": 0, "telegram_user_id": 1}).to_list(10000)
    sub_ids = [s["telegram_user_id"] for s in subs if s.get("telegram_user_id")]

    all_ids = list(set(user_ids + sub_ids))

    broadcast_id = str(uuid.uuid4())
    await db.broadcasts.insert_one({
        "id": broadcast_id, "message": message, "sent_by": admin.get("name", "Admin"),
        "sent_by_id": telegram_user_id, "total_recipients": len(all_ids),
        "sent": 0, "failed": 0, "status": "sending", "tenant_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    async def _send_broadcast():
        sent = 0
        failed = 0
        for uid in all_ids:
            try:
                await send_telegram_message(uid, message, bot_token)
                sent += 1
            except Exception:
                failed += 1
        await db.broadcasts.update_one({"id": broadcast_id}, {"$set": {"sent": sent, "failed": failed, "status": "completed"}})

    background_tasks.add_task(_send_broadcast)
    return {"success": True, "broadcast_id": broadcast_id, "total_recipients": len(all_ids)}


@router.get("/admin/live-sessions/{telegram_user_id}")
async def miniapp_admin_live_sessions(telegram_user_id: str):
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    sessions = await db.live_sessions.find(
        tenant_query({}, admin.get("tenant_id", DEFAULT_TENANT_ID)), {"_id": 0}
    ).sort("created_at", -1).to_list(20)
    return sessions


@router.post("/admin/live-session")
async def miniapp_admin_create_live(data: dict):
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    session_id = str(uuid.uuid4())
    session = {
        "id": session_id, "title": data.get("title", "Live Session"), "description": data.get("description", ""),
        "scheduled_date": data.get("scheduled_date", ""), "scheduled_time": data.get("scheduled_time", ""),
        "price": data.get("price", 0), "max_viewers": data.get("max_viewers", 100),
        "stream_link": data.get("stream_link", ""), "superchat_enabled": data.get("superchat_enabled", False),
        "superchat_min_amount": data.get("superchat_min_amount", 50),
        "status": "scheduled", "tickets_sold": 0, "started_at": "",
        "created_by": admin.get("name", "Admin"), "tenant_id": admin.get("tenant_id", DEFAULT_TENANT_ID),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.live_sessions.insert_one(session)
    del session["_id"]
    return session


@router.post("/admin/announce-live/{session_id}")
async def miniapp_admin_announce_live(session_id: str, data: dict):
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    msg = "<b>LIVE SESSION ANNOUNCED!</b>\n\n"
    msg += f"<b>{session.get('title', 'Live')}</b>\n"
    if session.get("description"):
        msg += f"{session['description']}\n\n"
    msg += f"Date: {session.get('scheduled_date', 'TBA')}\n"
    msg += f"Time: {session.get('scheduled_time', 'TBA')}\n"
    if session.get("price", 0) > 0:
        msg += f"Price: Rs.{session['price']}\n"
    else:
        msg += "Price: FREE\n"
    msg += "\nDon't miss it!"

    admin_tenant = admin.get("tenant_id", DEFAULT_TENANT_ID)
    bot_users = await db.bot_users.find(tenant_query({}, admin_tenant), {"_id": 0, "telegram_user_id": 1}).to_list(10000)
    sent = 0
    for u in bot_users:
        uid = u.get("telegram_user_id")
        if uid:
            try:
                await send_telegram_message(uid, msg, bot_token)
                sent += 1
            except Exception:
                pass

    await db.live_sessions.update_one({"id": session_id}, {"$set": {"status": "announced"}})
    return {"success": True, "sent_to": sent}


# ============== PAID POSTS ADMIN ==============

@router.get("/admin/paid-posts/{telegram_user_id}")
async def miniapp_admin_paid_posts(telegram_user_id: str):
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")
    posts = await db.paid_posts.find(
        tenant_query({}, admin.get("tenant_id", DEFAULT_TENANT_ID)), {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return posts


@router.post("/admin/paid-post")
async def miniapp_admin_create_paid_post(data: dict):
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    post_id = str(uuid.uuid4())
    post = {
        "id": post_id, "channel_id": data.get("channel_id", ""), "caption": data.get("caption", ""),
        "price": data.get("price", 0), "blur_level": data.get("blur_level", 10),
        "content_type": data.get("content_type", "text"), "original_file_id": data.get("original_file_id", ""),
        "media_url": data.get("media_url", ""), "original_message_id": data.get("original_message_id", 0),
        "blurred_message_id": data.get("blurred_message_id", 0), "is_active": True, "unlock_count": 0,
        "created_by": admin.get("name", "Admin"), "tenant_id": admin.get("tenant_id", DEFAULT_TENANT_ID),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.paid_posts.insert_one(post)
    del post["_id"]
    return post


@router.post("/admin/paid-post-with-media")
async def miniapp_admin_create_paid_post_with_media(
    file: UploadFile = File(...),
    telegram_user_id: str = Form(""),
    caption: str = Form(""),
    price: int = Form(0),
    blur_level: int = Form(10),
    channel_id: str = Form(""),
    content_type: str = Form("photo"),
):
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    file_bytes = await file.read()
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    uploads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(uploads_path, exist_ok=True)
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"post_{uuid.uuid4().hex[:10]}.{ext}"
    with open(os.path.join(uploads_path, filename), "wb") as f:
        f.write(file_bytes)

    media_url = f"/api/uploads/{filename}"

    if content_type == "auto":
        if ext.lower() in ("mp4", "mov", "avi", "mkv", "webm"):
            content_type = "video"
        elif ext.lower() in ("jpg", "jpeg", "png", "gif", "webp"):
            content_type = "photo"
        else:
            content_type = "document"

    post_id = str(uuid.uuid4())
    post = {
        "id": post_id, "channel_id": channel_id, "caption": caption, "price": price,
        "blur_level": blur_level, "content_type": content_type, "original_file_id": "",
        "media_url": media_url, "media_filename": filename, "original_message_id": 0,
        "blurred_message_id": 0, "is_active": True, "unlock_count": 0,
        "created_by": admin.get("name", "Admin"), "tenant_id": admin.get("tenant_id", DEFAULT_TENANT_ID),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.paid_posts.insert_one(post)
    del post["_id"]
    return post


@router.post("/admin/paid-post/{post_id}/toggle")
async def miniapp_toggle_paid_post(post_id: str, data: dict):
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    post = await db.paid_posts.find_one({"id": post_id}, {"_id": 0})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    new_status = not post.get("is_active", True)
    await db.paid_posts.update_one({"id": post_id}, {"$set": {"is_active": new_status}})
    return {"success": True, "is_active": new_status}


@router.post("/admin/paid-post/{post_id}/blur")
async def miniapp_update_blur(post_id: str, data: dict):
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    blur_level = data.get("blur_level", 10)
    blur_level = max(0, min(50, blur_level))
    await db.paid_posts.update_one({"id": post_id}, {"$set": {"blur_level": blur_level}})
    return {"success": True, "blur_level": blur_level}


@router.post("/admin/paid-post/{post_id}/broadcast")
async def miniapp_broadcast_paid_post(post_id: str, data: dict, background_tasks: BackgroundTasks):
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    post = await db.paid_posts.find_one({"id": post_id, "is_active": True}, {"_id": 0})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found or inactive")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    admin_tenant = admin.get("tenant_id", DEFAULT_TENANT_ID)
    bot_users = await db.bot_users.find(tenant_query({}, admin_tenant), {"_id": 0, "telegram_user_id": 1}).to_list(10000)
    user_ids = [u["telegram_user_id"] for u in bot_users if u.get("telegram_user_id")]

    price = post.get("price", 0)
    caption = post.get("caption", "")
    msg = f"<b>{'Paid Content' if price > 0 else 'Free Post'}</b>\n\n{caption}\n\n"
    if price > 0:
        msg += f"Unlock for Rs.{price}"

    sent = 0
    for uid in user_ids:
        try:
            await send_telegram_message(uid, msg, bot_token)
            sent += 1
        except Exception:
            pass
    return {"success": True, "sent_to": sent}


@router.post("/admin/live-session/{session_id}/go-live")
async def miniapp_go_live(session_id: str, data: dict):
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.live_sessions.update_one({"id": session_id}, {"$set": {"status": "live", "started_at": datetime.now(timezone.utc).isoformat()}})

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    admin_tenant = admin.get("tenant_id", DEFAULT_TENANT_ID)
    bot_users = await db.bot_users.find(tenant_query({}, admin_tenant), {"_id": 0, "telegram_user_id": 1}).to_list(10000)

    msg = f"<b>LIVE NOW!</b>\n\n{session.get('title', 'Live Session')}\n"
    if session.get("stream_link"):
        msg += f"{session['stream_link']}\n"
    msg += "\nJoin now!"

    sent = 0
    for u in bot_users:
        uid = u.get("telegram_user_id")
        if uid:
            try:
                await send_telegram_message(uid, msg, bot_token)
                sent += 1
            except Exception:
                pass
    return {"success": True, "status": "live", "notified": sent}


@router.delete("/admin/live-session/{session_id}")
async def miniapp_delete_live(session_id: str, data: dict):
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")
    result = await db.live_sessions.delete_one({"id": session_id})
    return {"success": result.deleted_count > 0}


@router.post("/admin/live-session/{session_id}/end")
async def miniapp_end_live(session_id: str, data: dict):
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")
    result = await db.live_sessions.update_one(
        {"id": session_id}, {"$set": {"status": "ended", "ended_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"success": result.modified_count > 0, "status": "ended"}


# ============== TENANT MANAGEMENT ==============

@router.get("/admin/tenant/{telegram_user_id}")
async def miniapp_get_tenant(telegram_user_id: str):
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")
    tenant_id = admin.get("tenant_id", DEFAULT_TENANT_ID)
    tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not tenant:
        tenant = {"tenant_id": tenant_id, "name": "Default Creator", "status": "active"}
    return tenant


@router.post("/admin/tenant/create")
async def miniapp_create_tenant(data: dict):
    telegram_user_id = data.get("telegram_user_id", "")
    admin = await _verify_miniapp_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    tenant_name = data.get("name", "").strip()
    if not tenant_name:
        raise HTTPException(status_code=400, detail="Tenant name required")

    tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"
    tenant = {
        "id": str(uuid.uuid4()), "tenant_id": tenant_id, "name": tenant_name,
        "owner_telegram_id": telegram_user_id, "bot_token": data.get("bot_token", ""),
        "upi_id": data.get("upi_id", ""), "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.tenants.insert_one(tenant)
    await db.telegram_admins.update_one({"telegram_user_id": str(telegram_user_id)}, {"$set": {"tenant_id": tenant_id}})
    tenant.pop("_id", None)
    return {"success": True, "tenant": tenant}
