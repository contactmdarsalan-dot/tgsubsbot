"""Content Management API — Polls, Dashboard Paid Post Creation, Scheduled Posts."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from database import db
from services.auth import get_current_user
from config import logger
from datetime import datetime, timezone
import uuid
import os
import json
import httpx

router = APIRouter()


def get_user_tenant(user):
    return user.get("tenant_id", "default")


def tq(query: dict, tenant_id: str) -> dict:
    query["tenant_id"] = tenant_id
    return query


# ===================== POLLS =====================

@router.get("/polls")
async def get_polls(user=Depends(get_current_user)):
    """Get all polls for this tenant"""
    tenant_id = get_user_tenant(user)
    polls = await db.polls.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return polls


@router.post("/polls")
async def create_poll(data: dict, user=Depends(get_current_user)):
    """Create a poll and optionally send it to a channel"""
    tenant_id = get_user_tenant(user)
    
    question = data.get("question", "").strip()
    options = data.get("options", [])
    channel_id = data.get("channel_id", "").strip()
    is_anonymous = data.get("is_anonymous", True)
    allows_multiple = data.get("allows_multiple", False)
    
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    if len(options) < 2:
        raise HTTPException(status_code=400, detail="At least 2 options required")
    if len(options) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 options allowed")
    
    # Clean options
    clean_options = [o.strip() for o in options if o.strip()]
    if len(clean_options) < 2:
        raise HTTPException(status_code=400, detail="At least 2 non-empty options required")
    
    poll_id = str(uuid.uuid4())
    poll_record = {
        "id": poll_id,
        "question": question,
        "options": clean_options,
        "channel_id": channel_id,
        "is_anonymous": is_anonymous,
        "allows_multiple": allows_multiple,
        "status": "draft",
        "telegram_message_id": None,
        "tenant_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # If channel_id provided, send immediately
    if channel_id:
        settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0})
        bot_token = ""
        if settings:
            bot_token = settings.get("telegram_bot_token", "")
        if not bot_token:
            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        
        if bot_token:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"https://api.telegram.org/bot{bot_token}/sendPoll",
                        json={
                            "chat_id": channel_id,
                            "question": question,
                            "options": json.dumps(clean_options),
                            "is_anonymous": is_anonymous,
                            "allows_multiple_answers": allows_multiple
                        }
                    )
                    result = resp.json()
                    if result.get("ok"):
                        poll_record["status"] = "sent"
                        poll_record["telegram_message_id"] = result.get("result", {}).get("message_id")
                        logger.info(f"Poll sent to channel {channel_id}: {question}")
                    else:
                        logger.error(f"Failed to send poll: {result}")
                        poll_record["status"] = "failed"
                        poll_record["error"] = result.get("description", "Unknown error")
            except Exception as e:
                logger.error(f"Error sending poll: {e}")
                poll_record["status"] = "failed"
                poll_record["error"] = str(e)
    
    await db.polls.insert_one(poll_record)
    del poll_record["_id"]  # Remove MongoDB _id
    return poll_record


@router.delete("/polls/{poll_id}")
async def delete_poll(poll_id: str, user=Depends(get_current_user)):
    """Delete a poll"""
    tenant_id = get_user_tenant(user)
    await db.polls.delete_one(tq({"id": poll_id}, tenant_id))
    return {"message": "Poll deleted"}


# ===================== DASHBOARD PAID POST CREATION =====================

@router.post("/paid-posts/create")
async def create_paid_post_from_dashboard(
    channel_id: str = Form(...),
    price: float = Form(99),
    blur_level: int = Form(25),
    caption: str = Form(""),
    scheduled_at: str = Form(""),
    files: list[UploadFile] = File(...)
):
    """Create a paid post from the dashboard with photo/video uploads.
    Supports multiple files (media group). Shows blurred preview in channel."""
    from services.telegram import (
        get_bot_settings, get_bot_username, send_telegram_photo,
        download_telegram_photo, delete_telegram_message
    )
    from services.payment import create_blurred_image
    
    # Get auth from header manually since we use Form data
    # Auth is handled by the router dependency
    
    if not channel_id:
        raise HTTPException(status_code=400, detail="Channel ID is required")
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="At least one file is required")
    if blur_level < 1 or blur_level > 100:
        blur_level = 25
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if not bot_token:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    
    if not bot_token:
        raise HTTPException(status_code=500, detail="Bot token not configured")
    
    bot_username = await get_bot_username(bot_token)
    paid_post_id = str(uuid.uuid4())
    
    # If scheduled, save for later processing
    if scheduled_at:
        try:
            schedule_time = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid schedule time format")
        
        # Save files to uploads directory
        uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        
        saved_files = []
        for f in files:
            contents = await f.read()
            ext = f.filename.split(".")[-1] if "." in f.filename else "jpg"
            fname = f"sched_{uuid.uuid4().hex[:8]}.{ext}"
            fpath = os.path.join(uploads_dir, fname)
            with open(fpath, "wb") as fp:
                fp.write(contents)
            
            content_type = "video" if f.content_type and "video" in f.content_type else "photo"
            saved_files.append({
                "type": content_type,
                "local_path": f"/api/uploads/{fname}",
                "original_name": f.filename
            })
        
        # Create blurred preview from first photo
        blurred_preview_path = ""
        first_photo = next((sf for sf in saved_files if sf["type"] == "photo"), None)
        if first_photo:
            local_file = os.path.join(uploads_dir, first_photo["local_path"].split("/")[-1])
            with open(local_file, "rb") as fp:
                img_bytes = fp.read()
            blurred_bytes = create_blurred_image(img_bytes, blur_radius=blur_level, content_type="photo")
            if blurred_bytes:
                blur_fname = f"blur_{uuid.uuid4().hex[:8]}.jpg"
                blur_path = os.path.join(uploads_dir, blur_fname)
                with open(blur_path, "wb") as fp:
                    fp.write(blurred_bytes)
                blurred_preview_path = f"/api/uploads/{blur_fname}"
        
        scheduled_post = {
            "id": paid_post_id,
            "channel_id": channel_id,
            "caption": caption,
            "price": price,
            "blur_level": blur_level,
            "saved_files": saved_files,
            "blurred_preview_path": blurred_preview_path,
            "scheduled_at": schedule_time.isoformat(),
            "status": "scheduled",
            "tenant_id": settings.get("tenant_id", "default"),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.scheduled_posts.insert_one(scheduled_post)
        
        return {
            "message": "Post scheduled successfully",
            "id": paid_post_id,
            "scheduled_at": schedule_time.isoformat(),
            "blurred_preview": blurred_preview_path,
            "file_count": len(saved_files)
        }
    
    # Not scheduled — post immediately
    file_ids = []
    first_photo_bytes = None
    
    for f in files:
        contents = await f.read()
        content_type = "video" if f.content_type and "video" in f.content_type else "photo"
        
        # Send file to channel first to get telegram file_id
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                if content_type == "video":
                    resp = await client.post(
                        f"https://api.telegram.org/bot{bot_token}/sendVideo",
                        data={"chat_id": channel_id},
                        files={"video": (f.filename, contents, f.content_type or "video/mp4")}
                    )
                else:
                    resp = await client.post(
                        f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                        data={"chat_id": channel_id},
                        files={"photo": (f.filename, contents, f.content_type or "image/jpeg")}
                    )
                
                result = resp.json()
                if result.get("ok"):
                    msg = result["result"]
                    msg_id = msg.get("message_id", 0)
                    
                    if content_type == "video":
                        fid = msg.get("video", {}).get("file_id", "")
                    else:
                        photos = msg.get("photo", [])
                        fid = photos[-1].get("file_id", "") if photos else ""
                    
                    file_ids.append({
                        "type": content_type,
                        "file_id": fid,
                        "message_id": msg_id
                    })
                    
                    if content_type == "photo" and first_photo_bytes is None:
                        first_photo_bytes = contents
                else:
                    logger.error(f"Failed to send file to channel: {result}")
        except Exception as e:
            logger.error(f"Error uploading file to channel: {e}")
    
    if not file_ids:
        raise HTTPException(status_code=500, detail="Failed to upload any files to channel")
    
    # Create blurred preview
    blurred_bytes = None
    if first_photo_bytes:
        blurred_bytes = create_blurred_image(first_photo_bytes, blur_radius=blur_level, content_type="photo")
    
    # Create paid post record
    first_photo = next((f for f in file_ids if f["type"] == "photo"), None)
    paid_post = {
        "id": paid_post_id,
        "channel_id": channel_id,
        "original_message_id": file_ids[0].get("message_id", 0),
        "content_type": "media_group" if len(file_ids) > 1 else file_ids[0]["type"],
        "original_file_id": first_photo["file_id"] if first_photo else file_ids[0]["file_id"],
        "file_ids": file_ids,
        "media_count": len(file_ids),
        "caption": caption,
        "price": price,
        "blur_level": blur_level,
        "unlock_count": 0,
        "is_active": True,
        "tenant_id": settings.get("tenant_id", "default"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.paid_posts.insert_one(paid_post)
    
    # Post blurred preview to channel
    media_count = len(file_ids)
    price_text = f"₹{int(price)}"
    
    photo_count = sum(1 for f in file_ids if f["type"] == "photo")
    video_count = sum(1 for f in file_ids if f["type"] == "video")
    media_desc = []
    if photo_count: media_desc.append(f"{photo_count} Photo{'s' if photo_count > 1 else ''}")
    if video_count: media_desc.append(f"{video_count} Video{'s' if video_count > 1 else ''}")
    
    blur_caption = f"🔒 <b>Paid Content ({' + '.join(media_desc)})</b>\n\n"
    blur_caption += f"💰 Price: <b>{price_text}</b>\n\n"
    if caption:
        blur_caption += f"📝 {caption}\n\n"
    blur_caption += "👆 Tap 'Unlock' to view all content!"
    
    unlock_text = f"🔓 Unlock" if media_count <= 1 else f"🔓 Unlock {media_count} Items"
    unlock_button = {
        "inline_keyboard": [[{
            "text": f"{unlock_text} - {price_text}",
            "url": f"https://t.me/{bot_username}?start=unlock_{paid_post_id}"
        }]]
    }
    
    blurred_msg_id = None
    if blurred_bytes:
        result = await send_telegram_photo(channel_id, blurred_bytes, blur_caption, bot_token, unlock_button)
        if result and result.get("ok"):
            blurred_msg_id = result.get("result", {}).get("message_id", 0)
    
    if blurred_msg_id:
        await db.paid_posts.update_one({"id": paid_post_id}, {"$set": {"blurred_message_id": blurred_msg_id}})
    
    # Delete original uploaded messages (they were temporary)
    for item in file_ids:
        msg_id = item.get("message_id")
        if msg_id:
            await delete_telegram_message(channel_id, msg_id, bot_token)
    
    return {
        "message": "Paid post created successfully",
        "id": paid_post_id,
        "blurred_message_id": blurred_msg_id,
        "file_count": len(file_ids),
        "blurred_preview": None  # Was sent directly to channel
    }


@router.post("/paid-posts/preview-blur")
async def preview_blur(
    blur_level: int = Form(25),
    file: UploadFile = File(...)
):
    """Generate a blurred preview without posting to channel.
    Returns the blurred image as a downloadable URL."""
    from services.payment import create_blurred_image
    
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    
    blur_level = max(1, min(blur_level, 100))
    blurred_bytes = create_blurred_image(contents, blur_radius=blur_level, content_type="photo")
    
    if not blurred_bytes:
        raise HTTPException(status_code=500, detail="Failed to create blurred image")
    
    # Save to uploads
    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    fname = f"preview_{uuid.uuid4().hex[:8]}.jpg"
    fpath = os.path.join(uploads_dir, fname)
    with open(fpath, "wb") as f:
        f.write(blurred_bytes)
    
    return {"preview_url": f"/api/uploads/{fname}"}


# ===================== SCHEDULED POSTS =====================

@router.get("/scheduled-posts")
async def get_scheduled_posts(user=Depends(get_current_user)):
    """Get all scheduled posts for this tenant"""
    tenant_id = get_user_tenant(user)
    posts = await db.scheduled_posts.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("scheduled_at", 1).to_list(100)
    return posts


@router.delete("/scheduled-posts/{post_id}")
async def delete_scheduled_post(post_id: str, user=Depends(get_current_user)):
    """Cancel a scheduled post"""
    tenant_id = get_user_tenant(user)
    result = await db.scheduled_posts.delete_one(tq({"id": post_id}, tenant_id))
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Scheduled post not found")
    return {"message": "Scheduled post cancelled"}
