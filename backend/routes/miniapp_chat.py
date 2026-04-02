"""Mini App Private Messaging - Separate from Bot features.
Uses existing collections: chat_messages, chat_sessions."""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from database import db
from services.tenant import DEFAULT_TENANT_ID, tenant_query
from services.auth import get_current_user
from services.permissions import get_user_tenant, tq
from datetime import datetime, timezone
import uuid, json, logging

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory chat connections
active_chats = {}  # user_id -> websocket


# ============== USER: PRIVATE MESSAGING ==============

@router.post("/miniapp/chat/send")
async def send_message(data: dict):
    """User sends a private message to creator."""
    telegram_user_id = str(data.get("telegram_user_id", ""))
    message = data.get("message", "").strip()
    tenant_id = data.get("tenant_id", DEFAULT_TENANT_ID)

    if not telegram_user_id or not message:
        raise HTTPException(status_code=400, detail="Missing fields")

    bot_user = await db.bot_users.find_one({"telegram_user_id": telegram_user_id}, {"_id": 0})
    sender_name = ""
    if bot_user:
        sender_name = bot_user.get("telegram_username", "") or bot_user.get("first_name", "") or telegram_user_id

    msg_doc = {
        "id": str(uuid.uuid4()),
        "chat_type": "private",
        "source": "miniapp",
        "sender_type": "user",
        "sender_id": telegram_user_id,
        "sender_name": sender_name,
        "message": message,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_id,
    }

    await db.chat_messages.insert_one(msg_doc)
    del msg_doc["_id"]

    # Notify admin if connected via WebSocket
    admin_key = f"admin_{tenant_id}"
    if admin_key in active_chats:
        try:
            await active_chats[admin_key].send_json({"type": "new-message", **msg_doc})
        except Exception:
            pass

    return {"success": True, "message": msg_doc}


@router.get("/miniapp/chat/history/{telegram_user_id}")
async def get_chat_history(telegram_user_id: str, tenant_id: str = DEFAULT_TENANT_ID):
    """Get chat history for a user."""
    query = {
        "source": "miniapp",
        "chat_type": "private",
        "$or": [
            {"sender_id": str(telegram_user_id)},
            {"recipient_id": str(telegram_user_id)},
        ]
    }
    if tenant_id:
        query["tenant_id"] = tenant_id

    messages = await db.chat_messages.find(query, {"_id": 0}).sort("created_at", 1).to_list(200)
    return messages


# ============== ADMIN: CHAT MANAGEMENT (via Telegram Mini App Admin) ==============

@router.get("/miniapp/admin/chats/{telegram_user_id}")
async def admin_get_chats(telegram_user_id: str):
    """Admin gets all private chat conversations."""
    admin = await db.telegram_admins.find_one({"telegram_user_id": str(telegram_user_id)}, {"_id": 0})
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    admin_tenant = admin.get("tenant_id", DEFAULT_TENANT_ID)

    # Get unique users who have sent messages
    pipeline = [
        {"$match": tenant_query({"source": "miniapp", "chat_type": "private", "sender_type": "user"}, admin_tenant)},
        {"$group": {
            "_id": "$sender_id",
            "sender_name": {"$last": "$sender_name"},
            "last_message": {"$last": "$message"},
            "last_time": {"$last": "$created_at"},
            "unread": {"$sum": {"$cond": [{"$eq": ["$read", False]}, 1, 0]}},
            "total": {"$sum": 1},
        }},
        {"$sort": {"last_time": -1}},
    ]

    conversations = await db.chat_messages.aggregate(pipeline).to_list(100)
    return [{"user_id": c["_id"], "name": c.get("sender_name", ""), "last_message": c["last_message"], "last_time": c["last_time"], "unread": c["unread"], "total": c["total"]} for c in conversations]


@router.post("/miniapp/admin/chat/reply")
async def admin_reply(data: dict):
    """Admin replies to a user's message."""
    telegram_user_id = str(data.get("telegram_user_id", ""))
    admin = await db.telegram_admins.find_one({"telegram_user_id": str(telegram_user_id)}, {"_id": 0})
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    admin_tenant = admin.get("tenant_id", DEFAULT_TENANT_ID)
    recipient_id = data.get("recipient_id", "")
    message = data.get("message", "").strip()

    if not message or not recipient_id:
        raise HTTPException(status_code=400, detail="Missing fields")

    msg_doc = {
        "id": str(uuid.uuid4()),
        "chat_type": "private",
        "source": "miniapp",
        "sender_type": "admin",
        "sender_id": telegram_user_id,
        "sender_name": admin.get("name", "Creator"),
        "recipient_id": recipient_id,
        "message": message,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": admin_tenant,
    }

    await db.chat_messages.insert_one(msg_doc)
    del msg_doc["_id"]

    # Notify user via WebSocket if connected
    user_key = f"user_{recipient_id}"
    if user_key in active_chats:
        try:
            await active_chats[user_key].send_json({"type": "new-message", **msg_doc})
        except Exception:
            pass

    return {"success": True, "message": msg_doc}


@router.get("/miniapp/admin/chat/messages/{user_id}")
async def admin_get_user_messages(user_id: str, admin_id: str = ""):
    """Admin gets messages for a specific user."""
    admin = await db.telegram_admins.find_one({"telegram_user_id": str(admin_id)}, {"_id": 0})
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    admin_tenant = admin.get("tenant_id", DEFAULT_TENANT_ID)

    query = tenant_query({
        "source": "miniapp", "chat_type": "private",
        "$or": [{"sender_id": user_id}, {"recipient_id": user_id}]
    }, admin_tenant)

    messages = await db.chat_messages.find(query, {"_id": 0}).sort("created_at", 1).to_list(200)

    # Mark user messages as read
    await db.chat_messages.update_many(
        tenant_query({"sender_id": user_id, "sender_type": "user", "read": False, "source": "miniapp"}, admin_tenant),
        {"$set": {"read": True}}
    )

    return messages


# ============== DASHBOARD API: CHAT MANAGEMENT ==============

@router.get("/miniapp-manage/chats")
async def dashboard_get_chats(user=Depends(get_current_user)):
    """Dashboard: Get all Mini App chat conversations."""
    tenant_id = get_user_tenant(user)

    pipeline = [
        {"$match": tq({"source": "miniapp", "chat_type": "private", "sender_type": "user"}, tenant_id)},
        {"$group": {
            "_id": "$sender_id",
            "sender_name": {"$last": "$sender_name"},
            "last_message": {"$last": "$message"},
            "last_time": {"$last": "$created_at"},
            "unread": {"$sum": {"$cond": [{"$eq": ["$read", False]}, 1, 0]}},
            "total": {"$sum": 1},
        }},
        {"$sort": {"last_time": -1}},
    ]

    conversations = await db.chat_messages.aggregate(pipeline).to_list(100)

    stats = {
        "total_conversations": len(conversations),
        "unread_total": sum(c.get("unread", 0) for c in conversations),
    }

    return {
        "conversations": [{"user_id": c["_id"], "name": c.get("sender_name", ""), "last_message": c["last_message"], "last_time": c["last_time"], "unread": c["unread"], "total": c["total"]} for c in conversations],
        "stats": stats,
    }


@router.get("/miniapp-manage/chat/{user_id}")
async def dashboard_get_chat_messages(user_id: str, user=Depends(get_current_user)):
    """Dashboard: Get messages for a specific user."""
    tenant_id = get_user_tenant(user)

    query = tq({
        "source": "miniapp", "chat_type": "private",
        "$or": [{"sender_id": user_id}, {"recipient_id": user_id}]
    }, tenant_id)

    messages = await db.chat_messages.find(query, {"_id": 0}).sort("created_at", 1).to_list(200)

    # Mark user messages as read
    await db.chat_messages.update_many(
        tq({"sender_id": user_id, "sender_type": "user", "read": False, "source": "miniapp"}, tenant_id),
        {"$set": {"read": True}}
    )

    return messages


@router.post("/miniapp-manage/chat/reply")
async def dashboard_reply(data: dict, user=Depends(get_current_user)):
    """Dashboard: Reply to a user's message."""
    tenant_id = get_user_tenant(user)
    recipient_id = data.get("recipient_id", "")
    message = data.get("message", "").strip()

    if not message or not recipient_id:
        raise HTTPException(status_code=400, detail="Missing fields")

    msg_doc = {
        "id": str(uuid.uuid4()),
        "chat_type": "private",
        "source": "miniapp",
        "sender_type": "admin",
        "sender_id": user.get("id", ""),
        "sender_name": user.get("name", user.get("email", "Creator")),
        "recipient_id": recipient_id,
        "message": message,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_id if tenant_id else DEFAULT_TENANT_ID,
    }

    await db.chat_messages.insert_one(msg_doc)
    del msg_doc["_id"]

    # Notify user via WebSocket
    user_key = f"user_{recipient_id}"
    if user_key in active_chats:
        try:
            await active_chats[user_key].send_json({"type": "new-message", **msg_doc})
        except Exception:
            pass

    return {"success": True, "message": msg_doc}


# ============== WEBSOCKET: REAL-TIME CHAT ==============

@router.websocket("/ws/chat/{user_type}/{user_id}")
async def websocket_chat(websocket: WebSocket, user_type: str, user_id: str):
    """Real-time chat WebSocket. user_type: 'user' or 'admin'."""
    await websocket.accept()
    key = f"{user_type}_{user_id}"
    active_chats[key] = websocket

    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        active_chats.pop(key, None)
