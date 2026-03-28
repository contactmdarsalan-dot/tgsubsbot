"""Authentication, OTP, Support ticket routes"""
from fastapi import APIRouter, HTTPException, Depends, Request
from database import db
from services.auth import get_current_user, hash_password, verify_password, create_token
from config import logger, twilio_client, TWILIO_PHONE_NUMBER
from rate_limiter import limiter
from models import UserCreate, UserLogin, User
from datetime import datetime, timezone, timedelta
import uuid
import random
import httpx

router = APIRouter()

SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"

# ============== AUTH ROUTES ==============

@router.post("/auth/register")
@limiter.limit("5/minute")
async def register(request: Request, user: UserCreate):
    existing = await db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_obj = User(email=user.email, name=user.name, phone=user.phone)
    doc = user_obj.model_dump()
    doc["password_hash"] = hash_password(user.password)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["is_admin"] = False  # Default not admin
    if doc.get("dashboard_subscription_end"):
        doc["dashboard_subscription_end"] = doc["dashboard_subscription_end"].isoformat()
    
    await db.users.insert_one(doc)
    token = create_token(user_obj.id)
    return {
        "token": token, 
        "user": {
            "id": user_obj.id, 
            "email": user_obj.email, 
            "name": user_obj.name,
            "dashboard_subscription_status": "inactive",
            "dashboard_plan": "",
            "dashboard_subscription_end": None,
            "is_admin": False
        }
    }

@router.post("/auth/login")
@limiter.limit("10/minute")
async def login(request: Request, user: UserLogin):
    existing = await db.users.find_one({"email": user.email}, {"_id": 0})
    if not existing or not verify_password(user.password, existing.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Check subscription status
    sub_status = existing.get("dashboard_subscription_status", "inactive")
    sub_end = existing.get("dashboard_subscription_end")
    user_role = existing.get("role", "user")
    
    if sub_end and isinstance(sub_end, str):
        sub_end = datetime.fromisoformat(sub_end)
    
    # Super admin bypasses subscription check
    if user_role == "super_admin":
        sub_status = "active"  # Always active for super admin
    elif sub_status == "active" and sub_end and datetime.now(timezone.utc) > sub_end:
        # Check if subscription expired
        sub_status = "expired"
        await db.users.update_one({"id": existing["id"]}, {"$set": {"dashboard_subscription_status": "expired"}})
    
    token = create_token(existing["id"])
    return {
        "token": token, 
        "user": {
            "id": existing["id"], 
            "email": existing["email"], 
            "name": existing.get("name", ""),
            "role": user_role,
            "dashboard_subscription_status": sub_status,
            "dashboard_plan": existing.get("dashboard_plan", ""),
            "dashboard_subscription_end": sub_end.isoformat() if sub_end else None,
            "is_admin": existing.get("is_admin", False) or user_role in ["admin", "super_admin"]
        }
    }

# ============== GOOGLE OAUTH ROUTES ==============

@router.post("/auth/google/session")
async def process_google_session(data: dict):
    """Process Google OAuth session and create/login user"""
    session_id = data.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID required")
    
    # Get user data from Emergent Auth
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": session_id}
            )
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid session")
            
            google_user = response.json()
    except Exception as e:
        logger.error(f"Google auth error: {e}")
        raise HTTPException(status_code=401, detail="Failed to verify Google session")
    
    email = google_user.get("email")
    name = google_user.get("name", email.split("@")[0])
    picture = google_user.get("picture", "")
    
    # Check if user exists
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    
    if existing:
        # Update existing user with Google info
        await db.users.update_one(
            {"email": email},
            {"$set": {"name": name, "picture": picture, "google_id": google_user.get("id")}}
        )
        user_id = existing["id"]
        sub_status = existing.get("dashboard_subscription_status", "inactive")
        sub_end = existing.get("dashboard_subscription_end")
        is_admin = existing.get("is_admin", False)
    else:
        # Create new user
        user_id = str(uuid.uuid4())
        new_user = {
            "id": user_id,
            "email": email,
            "name": name,
            "phone": "",
            "picture": picture,
            "google_id": google_user.get("id"),
            "dashboard_plan": "",
            "dashboard_subscription_end": None,
            "dashboard_subscription_status": "inactive",
            "is_admin": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one(new_user)
        sub_status = "inactive"
        sub_end = None
        is_admin = False
    
    # Create JWT token
    token = create_token(user_id)
    
    # Check if sub expired
    if sub_end and isinstance(sub_end, str):
        sub_end = datetime.fromisoformat(sub_end)
    if sub_status == "active" and sub_end and datetime.now(timezone.utc) > sub_end:
        sub_status = "expired"
        await db.users.update_one({"id": user_id}, {"$set": {"dashboard_subscription_status": "expired"}})
    
    return {
        "token": token,
        "user": {
            "id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "dashboard_subscription_status": sub_status,
            "dashboard_plan": existing.get("dashboard_plan", "") if existing else "",
            "dashboard_subscription_end": sub_end.isoformat() if sub_end else None,
            "is_admin": is_admin
        }
    }

@router.get("/auth/me")
async def get_me(user = Depends(get_current_user)):
    sub_end = user.get("dashboard_subscription_end")
    if sub_end and isinstance(sub_end, str):
        sub_end = datetime.fromisoformat(sub_end)
    
    user_role = user.get("role", "user")
    sub_status = user.get("dashboard_subscription_status", "inactive")
    
    # Super admin always has active status
    if user_role == "super_admin":
        sub_status = "active"
    
    return {
        "id": user["id"], 
        "email": user["email"], 
        "name": user.get("name", ""),
        "phone": user.get("phone", ""),
        "picture": user.get("picture", ""),
        "role": user_role,
        "dashboard_subscription_status": sub_status,
        "dashboard_plan": user.get("dashboard_plan", ""),
        "dashboard_subscription_end": sub_end.isoformat() if sub_end else None,
        "is_admin": user.get("is_admin", False) or user_role in ["admin", "super_admin"]
    }

# ============== TWILIO OTP ROUTES ==============

@router.post("/auth/otp/send")
async def send_otp(data: dict):
    """Send OTP to phone number"""
    phone = data.get("phone", "").strip()
    
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number required")
    
    # Format phone number (add +91 if not present for India)
    if not phone.startswith("+"):
        if phone.startswith("91"):
            phone = "+" + phone
        else:
            phone = "+91" + phone
    
    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    
    # Store OTP in database with expiry (5 minutes)
    await db.otps.update_one(
        {"phone": phone},
        {"$set": {
            "phone": phone,
            "otp": otp,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            "verified": False
        }},
        upsert=True
    )
    
    # Send OTP via Twilio
    if twilio_client and TWILIO_PHONE_NUMBER:
        try:
            message = twilio_client.messages.create(
                body=f"Your OTP for SubsBot is: {otp}. Valid for 5 minutes.",
                from_=TWILIO_PHONE_NUMBER,
                to=phone
            )
            logger.info(f"OTP sent to {phone}: {message.sid}")
            return {"message": "OTP sent successfully", "phone": phone}
        except Exception as e:
            logger.error(f"Twilio error: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")
    else:
        # For testing without Twilio
        logger.warning(f"Twilio not configured. OTP for {phone}: {otp}")
        return {"message": "OTP sent (test mode)", "phone": phone, "test_otp": otp}

@router.post("/auth/otp/verify")
async def verify_otp(data: dict):
    """Verify OTP and login/register user"""
    phone = data.get("phone", "").strip()
    otp = data.get("otp", "").strip()
    name = data.get("name", "")
    
    if not phone or not otp:
        raise HTTPException(status_code=400, detail="Phone and OTP required")
    
    # Format phone number
    if not phone.startswith("+"):
        if phone.startswith("91"):
            phone = "+" + phone
        else:
            phone = "+91" + phone
    
    # Find OTP record
    otp_record = await db.otps.find_one({"phone": phone}, {"_id": 0})
    
    if not otp_record:
        raise HTTPException(status_code=400, detail="OTP not found. Please request a new one.")
    
    # Check if OTP expired
    expires_at = datetime.fromisoformat(otp_record["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="OTP expired. Please request a new one.")
    
    # Verify OTP
    if otp_record["otp"] != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    # Mark OTP as verified
    await db.otps.update_one({"phone": phone}, {"$set": {"verified": True}})
    
    # Find or create user
    existing = await db.users.find_one({"phone": phone}, {"_id": 0})
    
    if existing:
        # Existing user - login
        user_id = existing["id"]
        user_name = existing.get("name", name or phone)
        user_email = existing.get("email", "")
        sub_status = existing.get("dashboard_subscription_status", "inactive")
        sub_end = existing.get("dashboard_subscription_end")
        is_admin = existing.get("is_admin", False)
    else:
        # New user - register
        user_id = str(uuid.uuid4())
        user_name = name or phone
        user_email = ""
        
        new_user = {
            "id": user_id,
            "email": "",
            "name": user_name,
            "phone": phone,
            "dashboard_plan": "",
            "dashboard_subscription_end": None,
            "dashboard_subscription_status": "inactive",
            "is_admin": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one(new_user)
        sub_status = "inactive"
        sub_end = None
        is_admin = False
    
    # Create JWT token
    token = create_token(user_id)
    
    # Format subscription end date
    if sub_end and isinstance(sub_end, str):
        sub_end = datetime.fromisoformat(sub_end)
    
    return {
        "token": token,
        "user": {
            "id": user_id,
            "email": user_email,
            "name": user_name,
            "phone": phone,
            "dashboard_subscription_status": sub_status,
            "dashboard_plan": existing.get("dashboard_plan", "") if existing else "",
            "dashboard_subscription_end": sub_end.isoformat() if sub_end else None,
            "is_admin": is_admin
        }
    }

# ============== PROFILE & PASSWORD ROUTES ==============

@router.put("/auth/profile")
async def update_profile(data: dict, user = Depends(get_current_user)):
    """Update user profile"""
    update_data = {}
    if "name" in data and data["name"].strip():
        update_data["name"] = data["name"].strip()
    if "phone" in data:
        update_data["phone"] = data["phone"].strip()

    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")

    await db.users.update_one({"id": user["id"]}, {"$set": update_data})
    updated = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password": 0})
    return updated


@router.put("/auth/change-password")
async def change_password(data: dict, user = Depends(get_current_user)):
    """Change password for logged-in user"""
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        raise HTTPException(status_code=400, detail="Both current and new password required")

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    full_user = await db.users.find_one({"id": user["id"]})
    if not full_user:
        raise HTTPException(status_code=400, detail="User not found")

    pw_field = "password_hash" if "password_hash" in full_user else "password"
    if not full_user.get(pw_field):
        raise HTTPException(status_code=400, detail="Password not set for this account")

    if not verify_password(current_password, full_user[pw_field]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    hashed = hash_password(new_password)
    await db.users.update_one({"id": user["id"]}, {"$set": {pw_field: hashed}})
    return {"message": "Password changed successfully"}


@router.post("/auth/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, data: dict):
    """Send password reset OTP to email"""
    email = data.get("email", "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        return {"message": "If the email exists, a reset code has been sent"}

    otp = str(random.randint(100000, 999999))
    await db.password_resets.update_one(
        {"email": email},
        {"$set": {
            "email": email,
            "otp": otp,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
            "used": False
        }},
        upsert=True
    )
    logger.info(f"Password reset OTP for {email}: {otp}")
    return {"message": "If the email exists, a reset code has been sent", "test_otp": otp}


@router.post("/auth/reset-password")
@limiter.limit("5/minute")
async def reset_password(request: Request, data: dict):
    """Reset password using OTP"""
    email = data.get("email", "").strip().lower()
    otp = data.get("otp", "").strip()
    new_password = data.get("new_password", "")

    if not email or not otp or not new_password:
        raise HTTPException(status_code=400, detail="Email, OTP and new password are required")

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    reset_record = await db.password_resets.find_one({"email": email, "otp": otp, "used": False}, {"_id": 0})
    if not reset_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")

    expires_at = datetime.fromisoformat(reset_record["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="Reset code has expired")

    hashed = hash_password(new_password)
    # Support both password field names
    existing_user = await db.users.find_one({"email": email})
    pw_field = "password_hash" if existing_user and "password_hash" in existing_user else "password"
    await db.users.update_one({"email": email}, {"$set": {pw_field: hashed}})
    await db.password_resets.update_one({"email": email, "otp": otp}, {"$set": {"used": True}})
    return {"message": "Password reset successfully"}


# ============== SUPPORT TICKET ROUTES (Chat-style) ==============

@router.post("/support/tickets")
async def create_support_ticket(data: dict, user = Depends(get_current_user)):
    """Create a new support ticket"""
    initial_message = {
        "sender": "user",
        "sender_name": user.get("name", "User"),
        "sender_email": user["email"],
        "message": data.get("message", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    ticket = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_email": user["email"],
        "user_name": user.get("name", ""),
        "subject": data.get("subject", "General Query"),
        "messages": [initial_message],
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.support_tickets.insert_one(ticket)
    return {"message": "Support ticket created", "ticket_id": ticket["id"]}

@router.get("/support/tickets")
async def get_user_support_tickets(user = Depends(get_current_user)):
    """Get user's own support tickets"""
    tickets = await db.support_tickets.find(
        {"user_id": user["id"]}, 
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return tickets

@router.post("/support/tickets/{ticket_id}/message")
async def add_user_message_to_ticket(ticket_id: str, data: dict, user = Depends(get_current_user)):
    """Add a message to existing ticket (user)"""
    ticket = await db.support_tickets.find_one({"id": ticket_id, "user_id": user["id"]}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if ticket.get("status") in ["resolved", "closed"]:
        raise HTTPException(status_code=400, detail="Cannot add message to resolved/closed ticket")
    
    new_message = {
        "sender": "user",
        "sender_name": user.get("name", "User"),
        "sender_email": user["email"],
        "message": data.get("message", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    await db.support_tickets.update_one(
        {"id": ticket_id},
        {"$push": {"messages": new_message}}
    )
    
    return {"message": "Message added"}

@router.get("/admin/support/tickets")
async def get_all_support_tickets(user = Depends(get_current_user)):
    """Get all support tickets (super admin or admin only)"""
    is_super_admin = user.get("email") == SUPER_ADMIN_EMAIL
    is_admin = user.get("is_admin", False)
    
    if not is_super_admin and not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    tickets = await db.support_tickets.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return tickets

@router.post("/admin/support/tickets/{ticket_id}/reply")
async def admin_reply_to_ticket(ticket_id: str, data: dict, user = Depends(get_current_user)):
    """Add admin reply to a ticket (can reply multiple times)"""
    is_super_admin = user.get("email") == SUPER_ADMIN_EMAIL
    is_admin = user.get("is_admin", False)
    
    if not is_super_admin and not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    ticket = await db.support_tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    new_message = {
        "sender": "admin",
        "sender_name": user.get("name", "Admin"),
        "sender_email": user["email"],
        "message": data.get("message", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Update status if provided, otherwise set to in_progress
    new_status = data.get("status", "in_progress")
    
    await db.support_tickets.update_one(
        {"id": ticket_id},
        {
            "$push": {"messages": new_message},
            "$set": {"status": new_status}
        }
    )
    
    return {"message": "Reply sent"}

@router.put("/admin/support/tickets/{ticket_id}/status")
async def update_ticket_status(ticket_id: str, data: dict, user = Depends(get_current_user)):
    """Update ticket status (super admin or admin only)"""
    is_super_admin = user.get("email") == SUPER_ADMIN_EMAIL
    is_admin = user.get("is_admin", False)
    
    if not is_super_admin and not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.support_tickets.update_one(
        {"id": ticket_id},
        {"$set": {"status": data.get("status", "open")}}
    )
    
    return {"message": "Status updated"}

# ============== DASHBOARD SUBSCRIPTION ROUTES ==============
