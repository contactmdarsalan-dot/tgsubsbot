"""Coupons, User Notes, Tags, Blocked Users, Referrals, FAQs, Video Call Bookings routes"""
from fastapi import APIRouter, HTTPException, Depends
from database import db
from services.auth import get_current_user
from services.telegram import get_bot_settings, send_telegram_message
from services.permissions import get_user_tenant, tq
from repositories.base import (
    coupons_repo, user_notes_repo, user_tags_repo, blocked_users_repo,
    referrals_repo, faqs_repo, video_call_bookings_repo, subscribers_repo
)
from config import logger
from datetime import datetime, timezone
import uuid

router = APIRouter()


# ============== COUPON/DISCOUNT APIs ==============

@router.get("/coupons")
async def get_coupons(user=Depends(get_current_user)):
    """Get all coupons"""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        coupons = await coupons_repo.find_many_global()
    else:
        coupons = await coupons_repo.find_many(tenant_id)
    return coupons

@router.post("/coupons")
async def create_coupon(coupon: dict, user=Depends(get_current_user)):
    """Create a new coupon"""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
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
    }
    await coupons_repo.insert_one(tenant_id, coupon_data)
    return {"message": "Coupon created", "id": coupon_data["id"]}

@router.put("/coupons/{coupon_id}")
async def update_coupon(coupon_id: str, coupon: dict, user=Depends(get_current_user)):
    """Update a coupon"""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    update_data = {}
    for key in ["code", "discount_type", "discount_value", "min_purchase", "max_uses", "valid_from", "valid_until", "applicable_plans", "is_active"]:
        if key in coupon:
            update_data[key] = coupon[key]
    if "code" in update_data:
        update_data["code"] = update_data["code"].upper().strip()
    if "discount_value" in update_data:
        update_data["discount_value"] = float(update_data["discount_value"])

    await coupons_repo.update_one(tenant_id, {"id": coupon_id}, {"$set": update_data})
    return {"message": "Coupon updated"}

@router.delete("/coupons/{coupon_id}")
async def delete_coupon(coupon_id: str, user=Depends(get_current_user)):
    """Delete a coupon"""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    await coupons_repo.delete_one(tenant_id, {"id": coupon_id})
    return {"message": "Coupon deleted"}

@router.post("/coupons/validate")
async def validate_coupon(data: dict):
    """Validate a coupon code (public endpoint for bot)"""
    code = data.get("code", "").upper().strip()
    plan_id = data.get("plan_id", "")
    amount = float(data.get("amount", 0))

    coupon = await db.coupons.find_one({"code": code, "is_active": True}, {"_id": 0})
    if not coupon:
        return {"valid": False, "error": "Invalid coupon code"}

    if coupon.get("max_uses") and coupon.get("used_count", 0) >= coupon["max_uses"]:
        return {"valid": False, "error": "Coupon has been fully used"}

    if coupon.get("min_purchase") and amount < coupon["min_purchase"]:
        return {"valid": False, "error": f"Minimum purchase amount is Rs.{coupon['min_purchase']}"}

    if coupon.get("applicable_plans") and plan_id and plan_id not in coupon["applicable_plans"]:
        return {"valid": False, "error": "Coupon not valid for this plan"}

    now = datetime.now(timezone.utc).isoformat()
    if coupon.get("valid_from") and now < coupon["valid_from"]:
        return {"valid": False, "error": "Coupon is not yet active"}
    if coupon.get("valid_until") and now > coupon["valid_until"]:
        return {"valid": False, "error": "Coupon has expired"}

    if coupon["discount_type"] == "percentage":
        discount_amount = amount * (coupon["discount_value"] / 100)
    else:
        discount_amount = coupon["discount_value"]

    return {
        "valid": True,
        "coupon": coupon,
        "discount_amount": min(discount_amount, amount),
        "final_amount": max(amount - discount_amount, 0)
    }


# ============== USER NOTES APIs ==============

@router.get("/users/{user_id}/notes")
async def get_user_notes(user_id: str, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        notes = await user_notes_repo.find_many_global({"user_id": user_id}, sort=[("created_at", -1)])
    else:
        notes = await user_notes_repo.find_many(tenant_id, {"user_id": user_id}, sort=[("created_at", -1)])
    return notes

@router.post("/users/{user_id}/notes")
async def add_user_note(user_id: str, data: dict, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    note = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "note": data.get("note", ""),
        "added_by": user.get("email", "admin"),
    }
    await user_notes_repo.insert_one(tenant_id, note)
    return {"message": "Note added", "id": note["id"]}

@router.delete("/users/{user_id}/notes/{note_id}")
async def delete_user_note(user_id: str, note_id: str, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    await user_notes_repo.delete_one(tenant_id, {"id": note_id, "user_id": user_id})
    return {"message": "Note deleted"}


# ============== USER TAGS APIs ==============

@router.get("/tags")
async def get_tags(user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        tags = await user_tags_repo.find_many_global()
    else:
        tags = await user_tags_repo.find_many(tenant_id)
    return tags

@router.post("/tags")
async def create_tag(data: dict, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    tag = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", ""),
        "color": data.get("color", "blue"),
    }
    await user_tags_repo.insert_one(tenant_id, tag)
    return {"message": "Tag created", "id": tag["id"]}

@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: str, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    await user_tags_repo.delete_one(tenant_id, {"id": tag_id})
    await subscribers_repo.update_many(tenant_id, {}, {"$pull": {"tags": tag_id}})
    return {"message": "Tag deleted"}

@router.post("/users/{user_id}/tags")
async def add_tag_to_user(user_id: str, data: dict, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    tag_id = data.get("tag_id")
    await subscribers_repo.collection.update_one(
        {"telegram_user_id": user_id, "tenant_id": tenant_id},
        {"$addToSet": {"tags": tag_id}}
    )
    return {"message": "Tag added to user"}

@router.delete("/users/{user_id}/tags/{tag_id}")
async def remove_tag_from_user(user_id: str, tag_id: str, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    await subscribers_repo.collection.update_one(
        {"telegram_user_id": user_id, "tenant_id": tenant_id},
        {"$pull": {"tags": tag_id}}
    )
    return {"message": "Tag removed from user"}


# ============== BLOCKED USERS APIs ==============

@router.get("/blocked-users")
async def get_blocked_users(user=Depends(get_current_user)):
    """Get all blocked users"""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        blocked = await blocked_users_repo.find_many_global(sort=[("blocked_at", -1)])
    else:
        blocked = await blocked_users_repo.find_many(tenant_id, sort=[("blocked_at", -1)])
    return blocked

@router.post("/users/{user_id}/block")
async def block_user(user_id: str, data: dict, user=Depends(get_current_user)):
    """Block a user"""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    existing = await blocked_users_repo.find_one(tenant_id, {"telegram_user_id": user_id})
    if existing:
        raise HTTPException(status_code=400, detail="User already blocked")

    block_doc = {
        "id": str(uuid.uuid4()),
        "telegram_user_id": user_id,
        "telegram_username": data.get("telegram_username", ""),
        "reason": data.get("reason", ""),
        "blocked_by": user.get("email", "admin"),
        "blocked_at": datetime.now(timezone.utc).isoformat()
    }
    await blocked_users_repo.insert_one(tenant_id, block_doc)
    return {"message": "User blocked"}

@router.delete("/users/{user_id}/block")
async def unblock_user(user_id: str, user=Depends(get_current_user)):
    """Unblock a user"""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    await blocked_users_repo.delete_one(tenant_id, {"telegram_user_id": user_id})
    return {"message": "User unblocked"}


# ============== REFERRAL APIs ==============

@router.get("/referrals")
async def get_referrals(user=Depends(get_current_user)):
    """Get all referrals"""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        referral_list = await referrals_repo.find_many_global(sort=[("created_at", -1)])
    else:
        referral_list = await referrals_repo.find_many(tenant_id, sort=[("created_at", -1)])
    return referral_list

@router.get("/referrals/settings")
async def get_referral_settings(user=Depends(get_current_user)):
    """Get referral program settings"""
    tenant_id = get_user_tenant(user)
    settings_id = f"referral_settings_{tenant_id}" if tenant_id else "referral_settings"
    settings = await db.referral_settings.find_one({"id": settings_id}, {"_id": 0})
    if not settings:
        settings = {
            "id": settings_id,
            "enabled": True,
            "referrer_reward_type": "discount",
            "referrer_reward_value": 10,
            "referee_reward_type": "discount",
            "referee_reward_value": 10
        }
        await db.referral_settings.insert_one(settings)
    return settings

@router.put("/referrals/settings")
async def update_referral_settings(data: dict, user=Depends(get_current_user)):
    """Update referral program settings"""
    tenant_id = get_user_tenant(user)
    settings_id = f"referral_settings_{tenant_id}" if tenant_id else "referral_settings"
    await db.referral_settings.update_one(
        {"id": settings_id},
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

    if referral["referrer_id"] == user_id:
        return {"valid": False, "error": "Can't use your own referral code"}

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


# ============== FAQ / AUTO-REPLY APIs ==============

@router.get("/faqs")
async def get_faqs(user=Depends(get_current_user)):
    """Get all FAQs"""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        faq_list = await faqs_repo.find_many_global(sort=[("created_at", -1)])
    else:
        faq_list = await faqs_repo.find_many(tenant_id, sort=[("created_at", -1)])
    return faq_list

@router.post("/faqs")
async def create_faq(data: dict, user=Depends(get_current_user)):
    """Create a new FAQ"""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    faq_data = {
        "id": str(uuid.uuid4()),
        "keywords": [k.strip().lower() for k in data.get("keywords", "").split(",") if k.strip()],
        "response": data.get("response", ""),
        "is_active": data.get("is_active", True),
        "usage_count": 0,
    }
    await faqs_repo.insert_one(tenant_id, faq_data)
    return {"message": "FAQ created", "faq": faq_data}

@router.put("/faqs/{faq_id}")
async def update_faq(faq_id: str, data: dict, user=Depends(get_current_user)):
    """Update a FAQ"""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    await faqs_repo.update_one(
        tenant_id, {"id": faq_id},
        {"$set": {
            "keywords": [k.strip().lower() for k in data.get("keywords", "").split(",") if k.strip()],
            "response": data.get("response", ""),
            "is_active": data.get("is_active", True)
        }}
    )
    return {"message": "FAQ updated"}

@router.delete("/faqs/{faq_id}")
async def delete_faq(faq_id: str, user=Depends(get_current_user)):
    """Delete a FAQ"""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    await faqs_repo.delete_one(tenant_id, {"id": faq_id})
    return {"message": "FAQ deleted"}


# ============== VIDEO CALL BOOKINGS APIs ==============

@router.get("/video-calls")
async def get_video_call_bookings(user=Depends(get_current_user)):
    """Get all video call bookings"""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        bookings = await video_call_bookings_repo.find_many_global(sort=[("created_at", -1)])
    else:
        bookings = await video_call_bookings_repo.find_many(tenant_id, sort=[("created_at", -1)])
    return bookings

@router.put("/video-calls/{booking_id}")
async def update_video_call_booking(booking_id: str, data: dict, user=Depends(get_current_user)):
    """Update a video call booking"""
    tenant_id = get_user_tenant(user)
    update_data = {}
    if "status" in data:
        update_data["status"] = data["status"]
    if "meeting_link" in data:
        update_data["meeting_link"] = data["meeting_link"]
    if "notes" in data:
        update_data["notes"] = data["notes"]

    if update_data:
        if tenant_id:
            await video_call_bookings_repo.update_one(tenant_id, {"id": booking_id}, {"$set": update_data})
        else:
            await db.video_call_bookings.update_one({"id": booking_id}, {"$set": update_data})

        if data.get("status") == "confirmed":
            if tenant_id:
                booking = await video_call_bookings_repo.find_one(tenant_id, {"id": booking_id})
            else:
                booking = await db.video_call_bookings.find_one({"id": booking_id}, {"_id": 0})
            if booking:
                settings = await get_bot_settings()
                bot_token = settings.get("telegram_bot_token", "")

                msg = "<b>Video Call Confirmed!</b>\n\n"
                msg += f"Date: <b>{booking.get('scheduled_date')}</b>\n"
                msg += f"Time: <b>{booking.get('scheduled_time')}</b>\n"
                msg += f"Duration: <b>{booking.get('duration_minutes', 30)} minutes</b>\n"

                if data.get("meeting_link"):
                    msg += f"\nMeeting Link:\n{data['meeting_link']}"

                await send_telegram_message(booking.get("telegram_user_id"), msg, bot_token)

    return {"message": "Booking updated"}

@router.delete("/video-calls/{booking_id}")
async def delete_video_call_booking(booking_id: str, user=Depends(get_current_user)):
    """Delete a video call booking"""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    await video_call_bookings_repo.delete_one(tenant_id, {"id": booking_id})
    return {"message": "Booking deleted"}

@router.get("/video-calls/queue")
async def get_video_call_queue(user=Depends(get_current_user)):
    """Get video call queue"""
    tenant_id = get_user_tenant(user)
    if tenant_id:
        queue = await video_call_bookings_repo.find_many(
            tenant_id, {"status": {"$in": ["pending", "paid", "waiting"]}},
            sort=[("created_at", 1)], limit=100
        )
        active_call = await video_call_bookings_repo.find_one(tenant_id, {"status": "in_progress"})
    else:
        queue = await video_call_bookings_repo.find_many_global(
            {"status": {"$in": ["pending", "paid", "waiting"]}},
            sort=[("created_at", 1)], limit=100
        )
        active_call = await video_call_bookings_repo.find_one_global({"status": "in_progress"})

    return {
        "queue": queue,
        "queue_length": len(queue),
        "active_call": active_call
    }

@router.post("/video-calls/{booking_id}/start")
async def start_video_call(booking_id: str, user=Depends(get_current_user)):
    """Start a video call"""
    tenant_id = get_user_tenant(user)
    if tenant_id:
        booking = await video_call_bookings_repo.find_one(tenant_id, {"id": booking_id})
    else:
        booking = await video_call_bookings_repo.find_one_global({"id": booking_id})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if tenant_id:
        active = await video_call_bookings_repo.find_one(tenant_id, {"status": "in_progress"})
    else:
        active = await video_call_bookings_repo.find_one_global({"status": "in_progress"})
    if active:
        raise HTTPException(status_code=400, detail="Another call is already in progress")

    if tenant_id:
        await video_call_bookings_repo.update_one(
            tenant_id, {"id": booking_id},
            {"$set": {"status": "in_progress", "started_at": datetime.now(timezone.utc).isoformat()}}
        )
    else:
        await db.video_call_bookings.update_one(
            {"id": booking_id},
            {"$set": {"status": "in_progress", "started_at": datetime.now(timezone.utc).isoformat()}}
        )

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    msg = "<b>Your video call is starting NOW!</b>\n\nCheck the meeting link above and join!"
    await send_telegram_message(booking.get("telegram_user_id"), msg, bot_token)

    return {"message": "Call started"}

@router.post("/video-calls/{booking_id}/end")
async def end_video_call(booking_id: str, user=Depends(get_current_user)):
    """End a video call and notify next in queue"""
    tenant_id = get_user_tenant(user)
    if tenant_id:
        await video_call_bookings_repo.update_one(
            tenant_id, {"id": booking_id},
            {"$set": {"status": "completed", "ended_at": datetime.now(timezone.utc).isoformat()}}
        )
    else:
        await db.video_call_bookings.update_one(
            {"id": booking_id},
            {"$set": {"status": "completed", "ended_at": datetime.now(timezone.utc).isoformat()}}
        )

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    if tenant_id:
        next_in_queue = await video_call_bookings_repo.find_one(
            tenant_id, {"status": {"$in": ["pending", "paid", "waiting"]}}
        )
    else:
        next_in_queue = await video_call_bookings_repo.find_one_global(
            {"status": {"$in": ["pending", "paid", "waiting"]}}
        )

    if next_in_queue:
        msg = "<b>You're Next!</b>\n\nGet ready! Your video call will start soon.\nMake sure you have good internet connection."
        await send_telegram_message(next_in_queue.get("telegram_user_id"), msg, bot_token)

    return {"message": "Call ended", "next_in_queue": next_in_queue}
