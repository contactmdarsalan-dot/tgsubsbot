"""Chat pool management - group assignment, expiry, release"""
import asyncio
import uuid
import httpx
from datetime import datetime, timezone, timedelta
from database import db
from config import logger
from services.telegram import get_bot_settings, send_telegram_message_with_buttons


async def get_available_chat_group():
    """Get an available group from the pool"""
    group = await db.chat_groups_pool.find_one({"status": "available"}, {"_id": 0})
    return group


async def assign_chat_group(group_id: str, user_id: str, username: str, plan_type: str, duration_minutes: int):
    """Assign a group to a user for time-limited chat"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    now = datetime.now(timezone.utc)
    end_time = now + timedelta(minutes=duration_minutes)

    await db.chat_groups_pool.update_one(
        {"group_id": group_id},
        {"$set": {
            "status": "in_use",
            "assigned_to_user_id": user_id,
            "assigned_to_username": username,
            "plan_type": plan_type,
            "session_start": now.isoformat(),
            "session_end": end_time.isoformat()
        }}
    )

    session = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "username": username,
        "group_id": group_id,
        "plan_type": plan_type,
        "duration_minutes": duration_minutes,
        "start_time": now.isoformat(),
        "end_time": end_time.isoformat(),
        "status": "active",
        "renewal_message_sent": False,
        "created_at": now.isoformat()
    }
    await db.chat_sessions.insert_one(session)

    try:
        async with httpx.AsyncClient() as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/createChatInviteLink"
            response = await http_client.post(url, json={
                "chat_id": group_id,
                "member_limit": 1,
                "expire_date": int((now + timedelta(minutes=10)).timestamp())
            })
            if response.status_code == 200:
                data = response.json()
                invite_link = data.get("result", {}).get("invite_link")
                return {"success": True, "invite_link": invite_link, "session": session}
    except Exception as e:
        logger.error(f"Error creating invite link: {e}")

    return {"success": False, "error": "Could not create invite link"}


async def restrict_user_in_group(group_id: str, user_id: str, can_send: bool = False):
    """Restrict or unrestrict user from sending messages in group"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    try:
        async with httpx.AsyncClient() as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/restrictChatMember"
            permissions = {
                "can_send_messages": can_send,
                "can_send_audios": can_send,
                "can_send_documents": can_send,
                "can_send_photos": can_send,
                "can_send_videos": can_send,
                "can_send_video_notes": can_send,
                "can_send_voice_notes": can_send,
                "can_send_polls": can_send,
                "can_send_other_messages": can_send,
                "can_add_web_page_previews": can_send
            }
            response = await http_client.post(url, json={
                "chat_id": group_id,
                "user_id": int(user_id),
                "permissions": permissions
            })
            logger.info(f"Restrict user response: {response.status_code} - {response.text}")
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Error restricting user: {e}")
        return False


async def kick_user_from_group(group_id: str, user_id: str):
    """Kick user from group"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    try:
        async with httpx.AsyncClient() as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/banChatMember"
            response = await http_client.post(url, json={
                "chat_id": group_id,
                "user_id": int(user_id),
                "until_date": int((datetime.now(timezone.utc) + timedelta(seconds=35)).timestamp())
            })
            logger.info(f"Kick user response: {response.status_code}")
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Error kicking user: {e}")
        return False


async def release_chat_group(group_id: str):
    """Release a group back to the pool after session ends"""
    group = await db.chat_groups_pool.find_one({"group_id": group_id}, {"_id": 0})

    if group and group.get("assigned_to_user_id"):
        user_id = group.get("assigned_to_user_id")
        await kick_user_from_group(group_id, user_id)

    await db.chat_groups_pool.update_one(
        {"group_id": group_id},
        {"$set": {
            "status": "available",
            "assigned_to_user_id": "",
            "assigned_to_username": "",
            "plan_type": "",
            "session_start": None,
            "session_end": None
        }}
    )


async def check_expired_chat_sessions():
    """Background task to check and handle expired chat sessions"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    now = datetime.now(timezone.utc)

    expired_sessions = await db.chat_sessions.find({
        "status": "active",
        "end_time": {"$lte": now.isoformat()}
    }, {"_id": 0}).to_list(100)

    for session in expired_sessions:
        user_id = session.get("user_id")
        group_id = session.get("group_id")
        plan_type = session.get("plan_type")

        await restrict_user_in_group(group_id, user_id, can_send=False)

        if not session.get("renewal_message_sent"):
            renewal_msg = "<b>Time's Up!</b>\n\n"
            renewal_msg += f"Your {plan_type} chat session has ended.\n\n"
            renewal_msg += "<b>Want to continue?</b>\n"
            renewal_msg += "Click below to renew or exit!"

            try:
                async with httpx.AsyncClient() as http_client:
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    buttons = [
                        [
                            {"text": "Renew Chat", "callback_data": f"renew_chat_{session['id']}"},
                            {"text": "Exit Chat", "callback_data": f"exit_chat_{session['id']}"}
                        ]
                    ]
                    await http_client.post(url, json={
                        "chat_id": group_id,
                        "text": renewal_msg,
                        "parse_mode": "HTML",
                        "reply_markup": {"inline_keyboard": buttons}
                    })
            except Exception as e:
                logger.error(f"Error sending renewal message: {e}")

            try:
                async with httpx.AsyncClient() as http_client:
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    private_msg = "<b>Chat Session Ended!</b>\n\n"
                    private_msg += f"Your {plan_type} chat time is over.\n\n"
                    private_msg += "To continue chatting, buy another session!\n\n"
                    private_msg += "/start - See available plans"
                    await http_client.post(url, json={
                        "chat_id": user_id,
                        "text": private_msg,
                        "parse_mode": "HTML"
                    })
            except Exception as e:
                logger.error(f"Error sending private renewal message: {e}")

            await db.chat_sessions.update_one(
                {"id": session["id"]},
                {"$set": {"renewal_message_sent": True, "status": "expired"}}
            )

        session_end = datetime.fromisoformat(session["end_time"]) if isinstance(session["end_time"], str) else session["end_time"]
        if now > session_end + timedelta(minutes=5):
            renewed = await db.chat_sessions.find_one({
                "user_id": user_id,
                "group_id": group_id,
                "status": "active",
                "start_time": {"$gt": session["end_time"]}
            })

            if not renewed:
                await release_chat_group(group_id)
                logger.info(f"Released group {group_id} after session expiry")
