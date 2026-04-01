"""Live Sessions, Creators, Telegram Admins, Paid Posts, Unlock Requests routes"""
from fastapi import APIRouter, HTTPException, Depends
from database import db
from services.auth import get_current_user
from services.telegram import (
    get_bot_settings, get_bot_username, send_telegram_message,
    send_telegram_message_with_buttons, send_telegram_photo,
    send_telegram_video, download_telegram_photo
)
from services.permissions import get_user_tenant, tq
from config import logger
from datetime import datetime, timezone
import uuid
import httpx

router = APIRouter()


# ============== CREATOR APIs ==============

@router.get("/creators")
async def get_creators(user=Depends(get_current_user)):
    """Get all creators"""
    creators = await db.creators.find({}, {"_id": 0}).to_list(100)
    return creators

@router.post("/creators")
async def create_creator(data: dict, user=Depends(get_current_user)):
    """Create a new creator"""
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
async def update_creator(creator_id: str, data: dict, user=Depends(get_current_user)):
    """Update creator details"""
    update_data = {}
    for field in ["name", "telegram_user_id", "telegram_username", "email", "permissions", "revenue_share", "is_active"]:
        if field in data:
            update_data[field] = data[field]

    await db.creators.update_one({"id": creator_id}, {"$set": update_data})
    return {"message": "Creator updated"}

@router.delete("/creators/{creator_id}")
async def delete_creator(creator_id: str, user=Depends(get_current_user)):
    """Delete a creator"""
    await db.creators.delete_one({"id": creator_id})
    return {"message": "Creator deleted"}

@router.post("/creators/link-telegram")
async def link_creator_telegram(data: dict, user=Depends(get_current_user)):
    """Link Telegram account to creator"""
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


# ============== TELEGRAM ADMIN MANAGEMENT ==============

@router.get("/telegram-admins")
async def get_telegram_admins(user=Depends(get_current_user)):
    """Get all Telegram admins"""
    tenant_id = get_user_tenant(user)
    admins = await db.telegram_admins.find(tq({}, tenant_id), {"_id": 0}).to_list(100)
    return admins

@router.post("/telegram-admins")
async def create_telegram_admin(data: dict, user=Depends(get_current_user)):
    """Create a new Telegram admin"""
    name = data.get("name", "")
    telegram_user_id = str(data.get("telegram_user_id", "")).strip()
    telegram_username = data.get("telegram_username", "").strip().replace("@", "")
    role = data.get("role", "admin")
    permissions = data.get("permissions", ["manage_bot", "verify_payments", "broadcast", "live_manage"])

    if not telegram_user_id and not telegram_username:
        raise HTTPException(status_code=400, detail="Telegram User ID or Username required")

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

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if bot_token and telegram_user_id:
        msg = "<b>You've been added as a Bot Admin!</b>\n\n"
        msg += f"Name: <b>{name}</b>\n"
        msg += f"Role: <b>{role.title()}</b>\n\n"
        msg += "<b>Your permissions:</b>\n"
        perm_labels = {
            "manage_bot": "Manage Bot",
            "verify_payments": "Verify Payments",
            "broadcast": "Send Broadcasts",
            "live_manage": "Manage Live Streams",
            "superchat_view": "View Super Chats",
            "add_subscribers": "Add Subscribers",
        }
        for p in permissions:
            msg += f"  - {perm_labels.get(p, p)}\n"
        msg += "\nUse /admin to see available admin commands."
        await send_telegram_message(telegram_user_id, msg, bot_token)

    return {"message": "Telegram admin created", "id": admin_doc["id"]}

@router.put("/telegram-admins/{admin_id}")
async def update_telegram_admin(admin_id: str, data: dict, user=Depends(get_current_user)):
    """Update a Telegram admin"""
    update_data = {}
    for field in ["name", "telegram_user_id", "telegram_username", "role", "permissions", "is_active"]:
        if field in data:
            update_data[field] = data[field]

    await db.telegram_admins.update_one({"id": admin_id}, {"$set": update_data})
    return {"message": "Telegram admin updated"}

@router.delete("/telegram-admins/{admin_id}")
async def delete_telegram_admin(admin_id: str, user=Depends(get_current_user)):
    """Remove a Telegram admin"""
    admin = await db.telegram_admins.find_one({"id": admin_id}, {"_id": 0})
    await db.telegram_admins.delete_one({"id": admin_id})

    if admin:
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
        if bot_token and admin.get("telegram_user_id"):
            msg = "Your bot admin access has been revoked."
            await send_telegram_message(admin["telegram_user_id"], msg, bot_token)

    return {"message": "Telegram admin removed"}


# ============== LIVE STREAM APIs ==============

@router.get("/live/sessions")
async def get_live_sessions(user=Depends(get_current_user)):
    """Get all live sessions"""
    tenant_id = get_user_tenant(user)
    sessions = await db.live_sessions.find(tq({}, tenant_id), {"_id": 0}).sort("created_at", -1).to_list(100)
    return sessions

@router.post("/live/sessions")
async def create_live_session(data: dict, user=Depends(get_current_user)):
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
        "group_id": data.get("group_id", ""),
        "superchat_enabled": data.get("superchat_enabled", True),
        "superchat_min_amount": float(data.get("superchat_min_amount", 10)),
        "status": "scheduled",
        "tickets_sold": 0,
        "superchat_total": 0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.live_sessions.insert_one(session)
    logger.info(f"Created live session: {session['title']}")
    return {"message": "Session created", "id": session["id"]}

@router.post("/live/sessions/{session_id}/announce")
async def announce_live_session(session_id: str, user=Depends(get_current_user)):
    """Announce live session to channel/group"""
    session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    channel_id = settings.get("telegram_channel_id", "")
    bot_username = await get_bot_username(bot_token)

    msg = "<b>LIVE SESSION ANNOUNCEMENT!</b>\n\n"
    msg += f"<b>{session.get('title')}</b>\n\n"
    if session.get('description'):
        msg += f"{session['description']}\n\n"
    msg += f"<b>Date:</b> {session.get('scheduled_date')}\n"
    msg += f"<b>Time:</b> {session.get('scheduled_time')}\n"
    msg += f"<b>Ticket Price:</b> Rs.{int(session.get('price', 0))}\n\n"
    if session.get('superchat_enabled'):
        msg += f"<b>Superchat Enabled!</b> (Min Rs.{int(session.get('superchat_min_amount', 10))})\n\n"
    msg += "<b>Get Your Ticket Now!</b>"

    buttons = [[{
        "text": f"Buy Ticket - Rs.{int(session.get('price', 0))}",
        "url": f"https://t.me/{bot_username}?start=live_{session_id}"
    }]]

    await send_telegram_message_with_buttons(channel_id, msg, buttons, bot_token)

    if session.get('group_id'):
        await send_telegram_message_with_buttons(session['group_id'], msg, buttons, bot_token)

    return {"message": "Announcement sent"}

@router.post("/live/sessions/{session_id}/go-live")
async def go_live(session_id: str, data: dict, user=Depends(get_current_user)):
    """Start live session and notify ticket holders"""
    session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    update_data = {"status": "live", "started_at": datetime.now(timezone.utc).isoformat()}
    if data.get("stream_link"):
        update_data["stream_link"] = data["stream_link"]

    await db.live_sessions.update_one({"id": session_id}, {"$set": update_data})
    session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})

    approved_tickets = await db.live_tickets.find({
        "session_id": session_id,
        "status": "approved"
    }, {"_id": 0}).to_list(1000)

    bot_username = await get_bot_username(bot_token)

    for ticket in approved_tickets:
        msg = "<b>WE ARE LIVE NOW!</b>\n\n"
        msg += f"<b>{session.get('title')}</b>\n\n"

        if session.get("stream_link"):
            msg += f"<b>Join here:</b>\n{session['stream_link']}\n\n"

        if session.get("superchat_enabled"):
            msg += f"Send Superchat: /superchat {session_id} <amount> <message>\n"
            msg += f"Min Amount: Rs.{int(session.get('superchat_min_amount', 10))}\n\n"

        msg += "Enjoy the stream!"

        if session.get("superchat_enabled"):
            buttons = [[{
                "text": "Send Superchat",
                "url": f"https://t.me/{bot_username}?start=superchat_{session_id}"
            }]]
            await send_telegram_message_with_buttons(ticket.get("telegram_user_id"), msg, buttons, bot_token)
        else:
            await send_telegram_message(ticket.get("telegram_user_id"), msg, bot_token)

    return {"message": "Live started", "notified": len(approved_tickets)}

@router.post("/live/sessions/{session_id}/start-countdown")
async def start_countdown_timer(session_id: str, data: dict, user=Depends(get_current_user)):
    """Post countdown timer to group"""
    session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    channel_id = settings.get("telegram_channel_id", "")
    bot_username = await get_bot_username(bot_token)

    target_group = data.get("group_id") or session.get("group_id") or channel_id
    minutes_remaining = data.get("minutes", 30)

    msg = "<b>LIVE STARTING SOON!</b>\n\n"
    msg += f"<b>{session.get('title')}</b>\n\n"
    msg += f"<b>Starting in: {minutes_remaining} minutes!</b>\n\n"
    if session.get('description'):
        msg += f"{session['description']}\n\n"
    msg += f"<b>Ticket Price:</b> Rs.{int(session.get('price', 0))}\n"
    if session.get('superchat_enabled'):
        msg += f"<b>Superchat:</b> Enabled!\n\n"
    msg += "<b>Get your ticket now before it starts!</b>"

    buttons = [
        [{"text": f"Buy Ticket - Rs.{int(session.get('price', 0))}", "url": f"https://t.me/{bot_username}?start=live_{session_id}"}],
        [{"text": "Subscribe for Updates", "url": f"https://t.me/{bot_username}?start=subscribe"}]
    ]

    result = await send_telegram_message_with_buttons(target_group, msg, buttons, bot_token)

    if result:
        await db.live_sessions.update_one(
            {"id": session_id},
            {"$set": {
                "countdown_message_id": result.get("message_id") if isinstance(result, dict) else None,
                "countdown_chat_id": target_group,
                "countdown_started_at": datetime.now(timezone.utc).isoformat()
            }}
        )

    return {"message": "Countdown started", "group_id": target_group}

@router.post("/live/sessions/{session_id}/update-countdown")
async def update_countdown_timer(session_id: str, data: dict, user=Depends(get_current_user)):
    """Update countdown timer message"""
    from services.telegram import edit_telegram_message

    session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.get("countdown_message_id"):
        raise HTTPException(status_code=400, detail="No countdown active")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    bot_username = await get_bot_username(bot_token)

    minutes_remaining = data.get("minutes", 10)

    if minutes_remaining <= 0:
        msg = "<b>WE ARE LIVE NOW!</b>\n\n"
        msg += f"<b>{session.get('title')}</b>\n\n"
        msg += "<b>Join the stream now!</b>"
        buttons = [[{"text": "JOIN LIVE NOW", "url": session.get('stream_link') or f"https://t.me/{bot_username}?start=live_{session_id}"}]]
    else:
        if minutes_remaining >= 60:
            hours = minutes_remaining // 60
            mins = minutes_remaining % 60
            time_str = f"{hours}h {mins}m" if mins > 0 else f"{hours}h"
        else:
            time_str = f"{minutes_remaining} minutes"

        msg = "<b>LIVE STARTING SOON!</b>\n\n"
        msg += f"<b>{session.get('title')}</b>\n\n"
        msg += f"<b>Starting in: {time_str}!</b>\n\n"
        msg += f"Ticket: Rs.{int(session.get('price', 0))}\n\n"
        msg += "<b>Get your ticket!</b>"
        buttons = [
            [{"text": f"Buy Ticket - Rs.{int(session.get('price', 0))}", "url": f"https://t.me/{bot_username}?start=live_{session_id}"}],
            [{"text": "Subscribe", "url": f"https://t.me/{bot_username}?start=subscribe"}]
        ]

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
async def update_live_session(session_id: str, data: dict, user=Depends(get_current_user)):
    """Update a live session"""
    update_data = {}
    for key in ["title", "description", "scheduled_date", "scheduled_time", "price", "max_viewers", "stream_link", "status"]:
        if key in data:
            update_data[key] = data[key]

    if update_data:
        await db.live_sessions.update_one({"id": session_id}, {"$set": update_data})

        if data.get("status") == "live":
            session = await db.live_sessions.find_one({"id": session_id}, {"_id": 0})
            if session:
                settings = await get_bot_settings()
                bot_token = settings.get("telegram_bot_token", "")

                approved_tickets = await db.live_tickets.find({
                    "session_id": session_id,
                    "status": "approved"
                }, {"_id": 0}).to_list(1000)

                for ticket in approved_tickets:
                    msg = "<b>LIVE NOW!</b>\n\n"
                    msg += f"<b>{session.get('title')}</b>\n\n"
                    if session.get("stream_link"):
                        msg += f"Join here:\n{session['stream_link']}"
                    else:
                        msg += "Stream link coming soon..."

                    await send_telegram_message(ticket.get("telegram_user_id"), msg, bot_token)

    return {"message": "Session updated"}

@router.delete("/live/sessions/{session_id}")
async def delete_live_session(session_id: str, user=Depends(get_current_user)):
    """Delete a live session"""
    await db.live_sessions.delete_one({"id": session_id})
    await db.live_tickets.delete_many({"session_id": session_id})
    return {"message": "Session deleted"}

@router.get("/live/tickets")
async def get_live_tickets(user=Depends(get_current_user)):
    """Get all live tickets"""
    tickets = await db.live_tickets.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return tickets

@router.post("/live/tickets/{ticket_id}/approve")
async def approve_live_ticket(ticket_id: str, user=Depends(get_current_user)):
    """Approve a live ticket and send stream link"""
    ticket = await db.live_tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    await db.live_tickets.update_one({"id": ticket_id}, {"$set": {"status": "approved"}})
    await db.live_sessions.update_one({"id": ticket.get("session_id")}, {"$inc": {"tickets_sold": 1}})

    session = await db.live_sessions.find_one({"id": ticket.get("session_id")}, {"_id": 0})
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    msg = "<b>Ticket Approved!</b>\n\n"
    msg += f"Session: <b>{session.get('title', '')}</b>\n"
    msg += f"Date: <b>{session.get('scheduled_date', '')}</b>\n"
    msg += f"Time: <b>{session.get('scheduled_time', '')}</b>\n\n"

    if session and session.get("stream_link"):
        msg += f"Stream Link:\n{session['stream_link']}\n\n"
    else:
        msg += "Stream link will be sent when we go live!\n\n"

    msg += "See you there!"

    await send_telegram_message(ticket.get("telegram_user_id"), msg, bot_token)

    return {"message": "Ticket approved"}

@router.post("/live/tickets/{ticket_id}/reject")
async def reject_live_ticket(ticket_id: str, user=Depends(get_current_user)):
    """Reject a live ticket"""
    ticket = await db.live_tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    await db.live_tickets.update_one({"id": ticket_id}, {"$set": {"status": "rejected"}})

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    msg = "<b>Ticket Request Rejected</b>\n\nYour payment could not be verified.\nPlease contact admin for assistance."
    await send_telegram_message(ticket.get("telegram_user_id"), msg, bot_token)

    return {"message": "Ticket rejected"}

@router.get("/live/superchats")
async def get_superchats(user=Depends(get_current_user)):
    """Get all super chats"""
    chats = await db.live_superchats.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return chats

@router.post("/live/superchats/{chat_id}/approve")
async def approve_superchat(chat_id: str, user=Depends(get_current_user)):
    """Approve a super chat"""
    await db.live_superchats.update_one({"id": chat_id}, {"$set": {"status": "approved"}})
    return {"message": "Super chat approved"}

@router.post("/live/superchats/{chat_id}/reject")
async def reject_superchat(chat_id: str, user=Depends(get_current_user)):
    """Reject a super chat"""
    chat = await db.live_superchats.find_one({"id": chat_id}, {"_id": 0})
    await db.live_superchats.update_one({"id": chat_id}, {"$set": {"status": "rejected"}})

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    msg = "<b>Super Chat Not Verified</b>\n\nYour payment could not be verified.\nPlease try again or contact admin."

    if chat:
        await send_telegram_message(chat.get("telegram_user_id"), msg, bot_token)

    return {"message": "Super chat rejected"}


# ============== PAID POSTS ADMIN APIs ==============

@router.get("/paid-posts")
async def get_paid_posts(user=Depends(get_current_user)):
    """Get all paid posts for admin dashboard"""
    posts = await db.paid_posts.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return posts

@router.get("/paid-posts/{post_id}")
async def get_paid_post(post_id: str, user=Depends(get_current_user)):
    """Get single paid post details"""
    post = await db.paid_posts.find_one({"id": post_id}, {"_id": 0})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    unlocks = await db.paid_post_unlocks.find({"post_id": post_id}, {"_id": 0}).to_list(100)
    post["unlocks"] = unlocks

    return post

@router.put("/paid-posts/{post_id}")
async def update_paid_post(post_id: str, data: dict, user=Depends(get_current_user)):
    """Update paid post"""
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
async def delete_paid_post(post_id: str, user=Depends(get_current_user)):
    """Delete/deactivate a paid post"""
    await db.paid_posts.update_one({"id": post_id}, {"$set": {"is_active": False}})
    return {"message": "Post deactivated"}

@router.get("/unlock-requests")
async def get_unlock_requests(user=Depends(get_current_user)):
    """Get all unlock requests"""
    requests = await db.unlock_requests.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return requests

@router.post("/unlock-requests/{request_id}/approve")
async def approve_unlock_request(request_id: str, user=Depends(get_current_user)):
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

    unlock_record = {
        "id": str(uuid.uuid4()),
        "post_id": post_id,
        "telegram_user_id": chat_id,
        "telegram_username": username,
        "payment_id": "admin_approved",
        "unlocked_at": datetime.now(timezone.utc).isoformat()
    }
    await db.paid_post_unlocks.insert_one(unlock_record)
    await db.paid_posts.update_one({"id": post_id}, {"$inc": {"unlock_count": 1}})
    await db.unlock_requests.update_one({"id": request_id}, {"$set": {"status": "approved"}})

    if bot_token and chat_id:
        success_msg = "<b>Payment Approved!</b>\n\nHere's your unlocked content:"
        await send_telegram_message(chat_id, success_msg, bot_token)

        if paid_post.get("content_type") == "photo" and paid_post.get("original_file_id"):
            caption = f"<b>Unlocked!</b>\n\n{paid_post.get('caption', '')}"
            await send_telegram_photo(chat_id, paid_post["original_file_id"], caption, bot_token)
        elif paid_post.get("content_type") == "video" and paid_post.get("original_file_id"):
            caption = f"<b>Unlocked Video!</b>\n\n{paid_post.get('caption', '')}"
            await send_telegram_video(chat_id, paid_post["original_file_id"], caption, bot_token)

    return {"message": "Unlock approved and content sent"}

@router.post("/unlock-requests/{request_id}/reject")
async def reject_unlock_request(request_id: str, user=Depends(get_current_user)):
    """Reject unlock request"""
    request = await db.unlock_requests.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    await db.unlock_requests.update_one({"id": request_id}, {"$set": {"status": "rejected"}})

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    chat_id = request.get("telegram_user_id")

    if bot_token and chat_id:
        reject_msg = "<b>Payment Not Verified</b>\n\nYour screenshot could not be verified.\nPlease try again with a valid payment screenshot."
        await send_telegram_message(chat_id, reject_msg, bot_token)

    return {"message": "Unlock request rejected"}


@router.delete("/unlock-requests/{request_id}")
async def delete_unlock_request(request_id: str, user=Depends(get_current_user)):
    """Delete an unlock request"""
    result = await db.unlock_requests.delete_one({"id": request_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"message": "Unlock request deleted"}



@router.get("/telegram/file/{file_id}")
async def get_telegram_file(file_id: str):
    """Serve Telegram file for admin preview"""
    from fastapi.responses import Response
    from config import TELEGRAM_BOT_TOKEN

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "") or TELEGRAM_BOT_TOKEN

    if not bot_token:
        raise HTTPException(status_code=500, detail="Bot token not configured")

    image_bytes = await download_telegram_photo(file_id, bot_token)

    if not image_bytes:
        raise HTTPException(status_code=404, detail="File not found or expired")

    return Response(
        content=image_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"}
    )
