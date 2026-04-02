"""Dashboard routes: Channels, Chat Groups, Settings, File Upload, Analytics, Branding, Bot Language"""
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from database import db
from services.auth import get_current_user
from services.telegram import get_bot_settings
from services.tenant import DEFAULT_TENANT_ID
from services.permissions import is_super_admin, get_user_tenant, tq
from services.chat_pool import release_chat_group
from config import logger
from models import BotSettings
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from io import BytesIO
import uuid
import httpx
import os

router = APIRouter()


# ============== CHAT GROUPS POOL ROUTES ==============

class AddChatGroupRequest(BaseModel):
    group_id: str
    group_name: str = ""


@router.get("/chat-groups")
async def get_chat_groups(user=Depends(get_current_user)):
    """Get all chat groups in the pool"""
    groups = await db.chat_groups_pool.find({}, {"_id": 0}).to_list(100)
    return groups


@router.post("/chat-groups")
async def add_chat_group(request: AddChatGroupRequest, user=Depends(get_current_user)):
    """Add a group to the chat pool"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    group_id = request.group_id.strip()
    if group_id and not group_id.startswith("-"):
        group_id = f"-{group_id}"

    try:
        async with httpx.AsyncClient() as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/getChatAdministrators?chat_id={group_id}"
            response = await http_client.get(url)
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Bot is not admin in this group or group doesn't exist. Make sure bot is added as admin to the group.")

            admins = response.json().get("result", [])
            bot_is_admin = any(admin.get("user", {}).get("is_bot") for admin in admins)

            if not bot_is_admin:
                raise HTTPException(status_code=400, detail="Bot must be admin in this group")

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

    existing = await db.chat_groups_pool.find_one({"group_id": group_id})
    if existing:
        raise HTTPException(status_code=400, detail="Group already in pool")

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
async def remove_chat_group(group_id: str, user=Depends(get_current_user)):
    """Remove a group from the pool"""
    result = await db.chat_groups_pool.delete_one({"group_id": group_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Group not found in pool")
    return {"message": "Group removed from pool"}


@router.get("/chat-sessions")
async def get_chat_sessions(status: Optional[str] = None, user=Depends(get_current_user)):
    """Get all chat sessions"""
    query = {}
    if status:
        query["status"] = status
    sessions = await db.chat_sessions.find(query, {"_id": 0}).to_list(100)
    return sessions


@router.post("/chat-groups/{group_id}/release")
async def force_release_group(group_id: str, user=Depends(get_current_user)):
    """Force release a group back to pool"""
    group = await db.chat_groups_pool.find_one({"group_id": group_id}, {"_id": 0})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    await release_chat_group(group_id)
    return {"message": "Group released"}


# ============== CHANNELS ROUTES ==============

@router.get("/channels")
async def get_channels(user=Depends(get_current_user)):
    """Get all managed Telegram channels"""
    channels = await db.channels.find({}, {"_id": 0}).to_list(100)
    return channels


@router.post("/channels")
async def add_channel(data: dict, user=Depends(get_current_user)):
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
async def update_channel(channel_id: str, data: dict, user=Depends(get_current_user)):
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
async def refresh_channel_info(channel_id: str, user=Depends(get_current_user)):
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
                resp = await client.get(f"https://api.telegram.org/bot{bot_token}/getChatMemberCount?chat_id={channel_id}")
                if resp.status_code == 200 and resp.json().get("ok"):
                    member_count = resp.json().get("result", 0)

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
async def delete_channel(channel_id: str, user=Depends(get_current_user)):
    """Remove a channel"""
    result = await db.channels.delete_one({"channel_id": channel_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"message": "Channel removed"}


# ============== SETTINGS ROUTES ==============

@router.get("/settings")
async def get_settings(user=Depends(get_current_user)):
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0})
    if not settings:
        settings = BotSettings().model_dump()
    return settings


@router.put("/settings")
async def update_settings(settings: BotSettings, user=Depends(get_current_user)):
    doc = settings.model_dump()
    await db.settings.update_one({"id": "bot_settings"}, {"$set": doc}, upsert=True)
    return {"message": "Settings updated"}


# ============== FILE UPLOAD ROUTES ==============

@router.post("/upload/qr-code")
async def upload_qr_code(file: UploadFile = File(...), user=Depends(get_current_user)):
    """Upload QR code image"""
    allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only image files are allowed (PNG, JPG, WEBP, GIF)")

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be less than 5MB")

    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    filename = f"qr_code_{uuid.uuid4().hex[:8]}.{ext}"
    uploads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(uploads_path, exist_ok=True)
    with open(os.path.join(uploads_path, filename), "wb") as f:
        f.write(contents)

    return {"url": f"/api/uploads/{filename}", "filename": filename}


@router.post("/upload/image")
async def upload_image(file: UploadFile = File(...), user=Depends(get_current_user)):
    """Upload general image"""
    allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")

    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    filename = f"img_{uuid.uuid4().hex[:8]}.{ext}"
    uploads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(uploads_path, exist_ok=True)
    with open(os.path.join(uploads_path, filename), "wb") as f:
        f.write(contents)

    return {"url": f"/api/uploads/{filename}", "filename": filename}


# ============== ANALYTICS ROUTES ==============

@router.get("/analytics")
async def get_analytics(user=Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    tenant_id = get_user_tenant(user)

    total_subscribers = await db.subscribers.count_documents(tq({}, tenant_id))
    active_subscribers = await db.subscribers.count_documents(tq({"status": "active"}, tenant_id))
    expired_subscribers = await db.subscribers.count_documents(tq({"status": "expired"}, tenant_id))
    grace_subscribers = await db.subscribers.count_documents(tq({"status": "grace"}, tenant_id))

    verified_payments = await db.payments.find(tq({"status": "verified"}, tenant_id), {"_id": 0}).to_list(10000)
    total_revenue = sum(p.get("amount", 0) for p in verified_payments)

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_payments = [p for p in verified_payments
                       if datetime.fromisoformat(p["created_at"]) >= month_start]
    monthly_revenue = sum(p.get("amount", 0) for p in monthly_payments)

    recent_subscribers = await db.subscribers.find(tq({}, tenant_id), {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
    recent_payments = await db.payments.find(tq({}, tenant_id), {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)

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
async def export_revenue_pdf(user=Depends(get_current_user)):
    """Export revenue analytics as PDF"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from fastapi.responses import StreamingResponse

    now = datetime.now(timezone.utc)

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

    recent = await db.payments.find({"status": "verified"}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=22, textColor=colors.HexColor('#e11d48'))
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=14, textColor=colors.HexColor('#666666'))
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=16, textColor=colors.HexColor('#333333'))

    elements = []

    elements.append(Paragraph("TGSubsBot Revenue Report", title_style))
    elements.append(Paragraph(f"Generated: {now.strftime('%d %B %Y, %I:%M %p')} UTC", subtitle_style))
    elements.append(Spacer(1, 20))

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

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=TGSubsBot_Revenue_{now.strftime('%Y%m%d')}.pdf"}
    )


# ============== WHITE-LABEL BRANDING ==============

@router.get("/branding")
async def get_branding(user=Depends(get_current_user)):
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
        for key in defaults:
            if key not in branding:
                branding[key] = defaults[key]
    else:
        branding = defaults
    return branding


@router.put("/branding")
async def update_branding(data: dict, user=Depends(get_current_user)):
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
async def get_bot_language(user=Depends(get_current_user)):
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
async def update_bot_language(data: dict, user=Depends(get_current_user)):
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
