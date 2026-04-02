"""Mini App Video Calls & Live Streaming - Separate from Bot features.
Uses existing collections: live_sessions, plans, payments.
Adds fields: session_type, source, room_id, booked_by, call_duration_minutes"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from database import db
from services.tenant import DEFAULT_TENANT_ID, tenant_query
from datetime import datetime, timezone, timedelta
import uuid, json, logging, asyncio

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory room management for WebRTC signaling
call_rooms = {}  # room_id -> {participants: {user_id: websocket}, created_at}
live_rooms = {}  # session_id -> {broadcaster: websocket, viewers: {user_id: websocket}}


# ============== VIDEO CALL BOOKING ==============

@router.post("/miniapp/book-video-call")
async def book_video_call(data: dict):
    """User books a video call after purchasing a video call plan."""
    telegram_user_id = str(data.get("telegram_user_id", ""))
    plan_id = data.get("plan_id", "")
    tenant_id = data.get("tenant_id", DEFAULT_TENANT_ID)

    if not telegram_user_id or not plan_id:
        raise HTTPException(status_code=400, detail="Missing required fields")

    # Verify plan exists and is a video call type
    plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Get user info
    bot_user = await db.bot_users.find_one({"telegram_user_id": telegram_user_id}, {"_id": 0})
    username = ""
    if bot_user:
        username = bot_user.get("telegram_username", "") or bot_user.get("username", "")

    booking_id = str(uuid.uuid4())
    room_id = str(uuid.uuid4())[:8]

    booking = {
        "id": booking_id,
        "session_type": "video_call_booking",
        "source": "miniapp",
        "title": f"Video Call - {plan.get('name', 'Call')}",
        "description": f"Video call booked by @{username or telegram_user_id}",
        "booked_by": telegram_user_id,
        "booked_by_name": username or telegram_user_id,
        "plan_id": plan_id,
        "plan_name": plan.get("name", ""),
        "call_duration_minutes": plan.get("duration_minutes", 10),
        "room_id": room_id,
        "status": "pending",
        "scheduled_date": "",
        "scheduled_time": "",
        "actual_start": "",
        "actual_end": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_id,
    }

    await db.live_sessions.insert_one(booking)
    del booking["_id"]

    return {"success": True, "booking": booking}


@router.get("/miniapp/my-bookings/{telegram_user_id}")
async def get_my_bookings(telegram_user_id: str, tenant_id: str = DEFAULT_TENANT_ID):
    """Get user's video call bookings."""
    query = {"booked_by": str(telegram_user_id), "session_type": "video_call_booking", "source": "miniapp"}
    if tenant_id:
        query["tenant_id"] = tenant_id
    bookings = await db.live_sessions.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    return bookings


@router.get("/miniapp/active-live")
async def get_active_live(tenant_id: str = DEFAULT_TENANT_ID):
    """Get currently active live stream for this tenant."""
    query = {"session_type": "live_stream", "source": "miniapp", "status": "live"}
    if tenant_id:
        query["tenant_id"] = tenant_id
    session = await db.live_sessions.find_one(query, {"_id": 0})
    return session or {"active": False}


# ============== ADMIN: VIDEO CALL MANAGEMENT ==============

async def _verify_admin(telegram_user_id: str):
    admin = await db.telegram_admins.find_one({"telegram_user_id": str(telegram_user_id)}, {"_id": 0})
    return admin


@router.get("/miniapp/admin/video-bookings/{telegram_user_id}")
async def admin_get_video_bookings(telegram_user_id: str, status: str = None):
    """Admin gets all video call bookings for their tenant."""
    admin = await _verify_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    admin_tenant = admin.get("tenant_id", DEFAULT_TENANT_ID)
    query = tenant_query({"session_type": "video_call_booking", "source": "miniapp"}, admin_tenant)
    if status:
        query["status"] = status

    bookings = await db.live_sessions.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return bookings


@router.post("/miniapp/admin/booking-action")
async def admin_booking_action(data: dict):
    """Admin schedules, starts, or completes a video call booking."""
    telegram_user_id = str(data.get("telegram_user_id", ""))
    admin = await _verify_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    admin_tenant = admin.get("tenant_id", DEFAULT_TENANT_ID)
    booking_id = data.get("booking_id", "")
    action = data.get("action", "")

    if action == "schedule":
        await db.live_sessions.update_one(
            tenant_query({"id": booking_id}, admin_tenant),
            {"$set": {
                "status": "scheduled",
                "scheduled_date": data.get("scheduled_date", ""),
                "scheduled_time": data.get("scheduled_time", ""),
            }}
        )
    elif action == "start":
        await db.live_sessions.update_one(
            tenant_query({"id": booking_id}, admin_tenant),
            {"$set": {"status": "in_call", "actual_start": datetime.now(timezone.utc).isoformat()}}
        )
    elif action == "complete":
        await db.live_sessions.update_one(
            tenant_query({"id": booking_id}, admin_tenant),
            {"$set": {"status": "completed", "actual_end": datetime.now(timezone.utc).isoformat()}}
        )
    elif action == "reject":
        await db.live_sessions.update_one(
            tenant_query({"id": booking_id}, admin_tenant),
            {"$set": {"status": "rejected"}}
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    return {"success": True, "action": action}


# ============== ADMIN: LIVE STREAM MANAGEMENT ==============

@router.post("/miniapp/admin/start-live")
async def admin_start_live(data: dict):
    """Creator starts a live stream in Mini App."""
    telegram_user_id = str(data.get("telegram_user_id", ""))
    admin = await _verify_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    admin_tenant = admin.get("tenant_id", DEFAULT_TENANT_ID)
    session_id = str(uuid.uuid4())
    room_id = str(uuid.uuid4())[:8]

    session = {
        "id": session_id,
        "session_type": "live_stream",
        "source": "miniapp",
        "title": data.get("title", "Live Stream"),
        "description": data.get("description", ""),
        "room_id": room_id,
        "status": "live",
        "started_by": telegram_user_id,
        "started_by_name": admin.get("name", "Creator"),
        "viewer_count": 0,
        "actual_start": datetime.now(timezone.utc).isoformat(),
        "actual_end": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": admin_tenant,
    }

    await db.live_sessions.insert_one(session)
    del session["_id"]
    return {"success": True, "session": session}


@router.post("/miniapp/admin/end-live")
async def admin_end_live(data: dict):
    """Creator ends a live stream."""
    telegram_user_id = str(data.get("telegram_user_id", ""))
    admin = await _verify_admin(telegram_user_id)
    if not admin:
        raise HTTPException(status_code=403, detail="Not an admin")

    admin_tenant = admin.get("tenant_id", DEFAULT_TENANT_ID)
    session_id = data.get("session_id", "")

    await db.live_sessions.update_one(
        tenant_query({"id": session_id, "session_type": "live_stream"}, admin_tenant),
        {"$set": {"status": "ended", "actual_end": datetime.now(timezone.utc).isoformat()}}
    )

    # Clean up live room
    if session_id in live_rooms:
        del live_rooms[session_id]

    return {"success": True}


# ============== DASHBOARD API: MINI APP MANAGEMENT ==============

from services.auth import get_current_user
from services.permissions import get_user_tenant, tq
from fastapi import Depends

@router.get("/miniapp-manage/video-bookings")
async def dashboard_get_video_bookings(status: str = None, user=Depends(get_current_user)):
    """Dashboard: Get all video call bookings for this tenant."""
    tenant_id = get_user_tenant(user)
    query = tq({"session_type": "video_call_booking", "source": "miniapp"}, tenant_id)
    if status:
        query["status"] = status
    bookings = await db.live_sessions.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    
    stats = {
        "total": await db.live_sessions.count_documents(tq({"session_type": "video_call_booking", "source": "miniapp"}, tenant_id)),
        "pending": await db.live_sessions.count_documents(tq({"session_type": "video_call_booking", "source": "miniapp", "status": "pending"}, tenant_id)),
        "scheduled": await db.live_sessions.count_documents(tq({"session_type": "video_call_booking", "source": "miniapp", "status": "scheduled"}, tenant_id)),
        "completed": await db.live_sessions.count_documents(tq({"session_type": "video_call_booking", "source": "miniapp", "status": "completed"}, tenant_id)),
    }
    return {"bookings": bookings, "stats": stats}


@router.post("/miniapp-manage/booking-action")
async def dashboard_booking_action(data: dict, user=Depends(get_current_user)):
    """Dashboard: Schedule/start/complete/reject a video call booking."""
    tenant_id = get_user_tenant(user)
    booking_id = data.get("booking_id", "")
    action = data.get("action", "")

    update = {}
    if action == "schedule":
        update = {"status": "scheduled", "scheduled_date": data.get("scheduled_date", ""), "scheduled_time": data.get("scheduled_time", "")}
    elif action == "start":
        update = {"status": "in_call", "actual_start": datetime.now(timezone.utc).isoformat()}
    elif action == "complete":
        update = {"status": "completed", "actual_end": datetime.now(timezone.utc).isoformat()}
    elif action == "reject":
        update = {"status": "rejected"}
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    await db.live_sessions.update_one(tq({"id": booking_id}, tenant_id), {"$set": update})
    return {"success": True}


@router.get("/miniapp-manage/live-streams")
async def dashboard_get_live_streams(user=Depends(get_current_user)):
    """Dashboard: Get Mini App live stream history."""
    tenant_id = get_user_tenant(user)
    streams = await db.live_sessions.find(
        tq({"session_type": "live_stream", "source": "miniapp"}, tenant_id), {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return streams


@router.post("/miniapp-manage/start-live")
async def dashboard_start_live(data: dict, user=Depends(get_current_user)):
    """Dashboard: Creator starts a live stream."""
    tenant_id = get_user_tenant(user)
    session_id = str(uuid.uuid4())
    room_id = str(uuid.uuid4())[:8]

    session = {
        "id": session_id,
        "session_type": "live_stream",
        "source": "miniapp",
        "title": data.get("title", "Live Stream"),
        "description": data.get("description", ""),
        "room_id": room_id,
        "status": "live",
        "started_by": user.get("id", ""),
        "started_by_name": user.get("name", user.get("email", "Creator")),
        "viewer_count": 0,
        "actual_start": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_id if tenant_id else DEFAULT_TENANT_ID,
    }

    await db.live_sessions.insert_one(session)
    del session["_id"]
    return {"success": True, "session": session}


@router.post("/miniapp-manage/end-live")
async def dashboard_end_live(data: dict, user=Depends(get_current_user)):
    """Dashboard: End a live stream."""
    tenant_id = get_user_tenant(user)
    session_id = data.get("session_id", "")
    await db.live_sessions.update_one(
        tq({"id": session_id, "session_type": "live_stream"}, tenant_id),
        {"$set": {"status": "ended", "actual_end": datetime.now(timezone.utc).isoformat()}}
    )
    if session_id in live_rooms:
        del live_rooms[session_id]
    return {"success": True}


# ============== WEBSOCKET: VIDEO CALL SIGNALING ==============

@router.websocket("/ws/call/{room_id}")
async def websocket_call(websocket: WebSocket, room_id: str):
    """WebRTC signaling for 1:1 video calls."""
    await websocket.accept()
    user_id = str(uuid.uuid4())[:8]

    if room_id not in call_rooms:
        call_rooms[room_id] = {"participants": {}, "created_at": datetime.now(timezone.utc).isoformat()}

    room = call_rooms[room_id]
    if len(room["participants"]) >= 2:
        await websocket.send_json({"type": "error", "message": "Room is full"})
        await websocket.close()
        return

    room["participants"][user_id] = websocket

    try:
        # Notify others about new participant
        for uid, ws in room["participants"].items():
            if uid != user_id:
                await ws.send_json({"type": "user-joined", "userId": user_id})

        await websocket.send_json({"type": "joined", "userId": user_id, "participants": list(room["participants"].keys())})

        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg["from"] = user_id

            # Forward signaling messages to other participants
            for uid, ws in room["participants"].items():
                if uid != user_id:
                    try:
                        await ws.send_json(msg)
                    except Exception:
                        pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket call error: {e}")
    finally:
        if room_id in call_rooms and user_id in call_rooms[room_id]["participants"]:
            del call_rooms[room_id]["participants"][user_id]
            for uid, ws in call_rooms[room_id]["participants"].items():
                try:
                    await ws.send_json({"type": "user-left", "userId": user_id})
                except Exception:
                    pass
            if not call_rooms[room_id]["participants"]:
                del call_rooms[room_id]


# ============== WEBSOCKET: LIVE STREAM ==============

@router.websocket("/ws/live/{session_id}")
async def websocket_live(websocket: WebSocket, session_id: str):
    """WebRTC signaling for live streaming + live chat."""
    await websocket.accept()
    user_id = str(uuid.uuid4())[:8]
    is_broadcaster = False

    if session_id not in live_rooms:
        live_rooms[session_id] = {"broadcaster": None, "broadcaster_ws": None, "viewers": {}, "chat": []}

    room = live_rooms[session_id]

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "broadcaster-join":
                room["broadcaster"] = user_id
                room["broadcaster_ws"] = websocket
                is_broadcaster = True
                await websocket.send_json({"type": "broadcaster-ready", "viewerCount": len(room["viewers"])})

            elif msg.get("type") == "viewer-join":
                room["viewers"][user_id] = websocket
                # Update viewer count
                await db.live_sessions.update_one({"id": session_id}, {"$set": {"viewer_count": len(room["viewers"])}})
                await websocket.send_json({"type": "viewer-ready", "viewerCount": len(room["viewers"])})
                if room["broadcaster_ws"]:
                    await room["broadcaster_ws"].send_json({"type": "new-viewer", "viewerId": user_id, "viewerCount": len(room["viewers"])})

            elif msg.get("type") in ("offer", "answer", "ice-candidate"):
                target = msg.get("target")
                msg["from"] = user_id
                if target and target in room["viewers"]:
                    await room["viewers"][target].send_json(msg)
                elif target == room["broadcaster"] and room["broadcaster_ws"]:
                    await room["broadcaster_ws"].send_json(msg)

            elif msg.get("type") == "chat":
                chat_msg = {"from": user_id, "name": msg.get("name", "User"), "text": msg.get("text", ""), "time": datetime.now(timezone.utc).isoformat()}
                room["chat"].append(chat_msg)
                # Broadcast chat to everyone
                all_ws = list(room["viewers"].values())
                if room["broadcaster_ws"]:
                    all_ws.append(room["broadcaster_ws"])
                for ws in all_ws:
                    try:
                        await ws.send_json({"type": "chat", **chat_msg})
                    except Exception:
                        pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket live error: {e}")
    finally:
        if session_id in live_rooms:
            if is_broadcaster:
                # Broadcaster left — notify viewers
                for vid, vws in live_rooms[session_id]["viewers"].items():
                    try:
                        await vws.send_json({"type": "broadcaster-left"})
                    except Exception:
                        pass
                live_rooms[session_id]["broadcaster"] = None
                live_rooms[session_id]["broadcaster_ws"] = None
            else:
                live_rooms[session_id]["viewers"].pop(user_id, None)
                await db.live_sessions.update_one({"id": session_id}, {"$set": {"viewer_count": len(live_rooms[session_id]["viewers"])}})
                if live_rooms[session_id]["broadcaster_ws"]:
                    try:
                        await live_rooms[session_id]["broadcaster_ws"].send_json({"type": "viewer-left", "viewerId": user_id, "viewerCount": len(live_rooms[session_id]["viewers"])})
                    except Exception:
                        pass
