"""Authentication, OTP, Support ticket routes"""
from fastapi import APIRouter, HTTPException, Depends, Request
from database import db
from services.auth import get_current_user, hash_password, verify_password, create_token, create_refresh_token, decode_token
from services.permissions import is_super_admin, is_any_admin
from config import logger, twilio_client, TWILIO_PHONE_NUMBER
from rate_limiter import limiter
from models import UserCreate, UserLogin, User
from datetime import datetime, timezone, timedelta
import uuid
import random
import httpx

router = APIRouter()

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
    doc["is_admin"] = False
    if doc.get("dashboard_subscription_end"):
        doc["dashboard_subscription_end"] = doc["dashboard_subscription_end"].isoformat()
    
    # Auto-create a unique tenant for every new user
    tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"
    doc["tenant_id"] = tenant_id
    doc["role"] = "tenant_owner"
    
    # Create tenant record
    tenant_doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "name": user.name or user.email,
        "email": user.email,
        "status": "active",
        "created_at": doc["created_at"]
    }
    await db.tenants.insert_one(tenant_doc)
    
    # Auto-activate trial if enabled
    trial_cfg = await db.trial_config.find_one({"id": "default_trial"}, {"_id": 0})
    if trial_cfg and trial_cfg.get("enabled") and trial_cfg.get("auto_activate_on_register"):
        trial_days = trial_cfg.get("duration_days", 7)
        trial_end = datetime.now(timezone.utc) + timedelta(days=trial_days)
        doc["dashboard_subscription_status"] = "trial"
        doc["dashboard_plan"] = "trial"
        doc["dashboard_subscription_end"] = trial_end.isoformat()
        doc["trial_started_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.users.insert_one(doc)
    token = create_token(user_obj.id, role="tenant_owner", tenant_id=tenant_id)
    refresh = create_refresh_token(user_obj.id)
    return {
        "token": token,
        "refresh_token": refresh,
        "user": {
            "id": user_obj.id, 
            "email": user_obj.email, 
            "name": user_obj.name,
            "role": "tenant_owner",
            "tenant_id": tenant_id,
            "dashboard_subscription_status": doc.get("dashboard_subscription_status", "inactive"),
            "dashboard_plan": doc.get("dashboard_plan", ""),
            "dashboard_subscription_end": doc.get("dashboard_subscription_end"),
            "is_admin": True
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
    elif user_role == "tenant_admin":
        sub_status = "active"  # Tenant admins always have access
    elif sub_status in ("active", "trial") and sub_end and datetime.now(timezone.utc) > sub_end:
        # Check if subscription/trial expired
        sub_status = "expired"
        await db.users.update_one({"id": existing["id"]}, {"$set": {"dashboard_subscription_status": "expired"}})
    
    token = create_token(existing["id"], role=user_role, tenant_id=existing.get("tenant_id", ""), token_version=existing.get("token_version", 0))
    refresh = create_refresh_token(existing["id"])
    return {
        "token": token,
        "refresh_token": refresh,
        "user": {
            "id": existing["id"], 
            "email": existing["email"], 
            "name": existing.get("name", ""),
            "role": user_role,
            "tenant_id": existing.get("tenant_id", ""),
            "dashboard_subscription_status": sub_status,
            "dashboard_plan": existing.get("dashboard_plan", ""),
            "dashboard_subscription_end": sub_end.isoformat() if sub_end else None,
            "is_admin": existing.get("is_admin", False) or user_role in ["admin", "super_admin", "tenant_admin"]
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
        # Create new user with auto-tenant
        user_id = str(uuid.uuid4())
        tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"
        
        # Create tenant record
        tenant_doc = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "name": name,
            "email": email,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.tenants.insert_one(tenant_doc)
        
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
            "is_admin": True,
            "role": "tenant_owner",
            "tenant_id": tenant_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one(new_user)
        sub_status = "inactive"
        sub_end = None
        is_admin = True
    
    # Create JWT token — include role and tenant context
    _g_role = existing.get("role", "tenant_owner") if existing else "tenant_owner"
    _g_tid = existing.get("tenant_id", "") if existing else tenant_id
    _g_tv = existing.get("token_version", 0) if existing else 0
    token = create_token(user_id, role=_g_role, tenant_id=_g_tid, token_version=_g_tv)
    refresh = create_refresh_token(user_id)
    
    # Check if sub expired
    if sub_end and isinstance(sub_end, str):
        sub_end = datetime.fromisoformat(sub_end)
    if sub_status == "active" and sub_end and datetime.now(timezone.utc) > sub_end:
        sub_status = "expired"
        await db.users.update_one({"id": user_id}, {"$set": {"dashboard_subscription_status": "expired"}})
    
    return {
        "token": token,
        "refresh_token": refresh,
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
        "tenant_id": user.get("tenant_id", ""),
        "dashboard_subscription_status": sub_status,
        "dashboard_plan": user.get("dashboard_plan", ""),
        "dashboard_subscription_end": sub_end.isoformat() if sub_end else None,
        "is_admin": user.get("is_admin", False) or user_role in ["admin", "super_admin", "tenant_admin"]
    }


# ============== TOKEN REFRESH & FORCE LOGOUT ==============

@router.post("/auth/refresh")
async def refresh_access_token(data: dict):
    """Exchange a valid refresh token for a new access token."""
    refresh_token = data.get("refresh_token", "")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Refresh token required")
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        # Issue new access token
        new_access = create_token(
            user["id"],
            role=user.get("role", ""),
            tenant_id=user.get("tenant_id", ""),
            token_version=user.get("token_version", 0)
        )
        return {"token": new_access}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")


@router.post("/auth/force-logout/{user_id}")
async def force_logout_user(user_id: str, user=Depends(get_current_user)):
    """Force logout a user by incrementing their token_version.
    All existing tokens become invalid. Super Admin only."""
    from services.permissions import ensure_super_admin
    ensure_super_admin(user)
    result = await db.users.update_one(
        {"id": user_id},
        {"$inc": {"token_version": 1}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User forcefully logged out. All active sessions invalidated."}


@router.post("/auth/logout")
async def logout_self(user=Depends(get_current_user)):
    """Logout current user by incrementing their own token_version."""
    await db.users.update_one(
        {"id": user["id"]},
        {"$inc": {"token_version": 1}}
    )
    return {"message": "Logged out successfully. All sessions invalidated."}


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
        # New user - register with auto-tenant
        user_id = str(uuid.uuid4())
        user_name = name or phone
        user_email = ""
        tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"
        
        # Create tenant record
        tenant_doc = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "name": user_name,
            "email": "",
            "phone": phone,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.tenants.insert_one(tenant_doc)
        
        new_user = {
            "id": user_id,
            "email": "",
            "name": user_name,
            "phone": phone,
            "dashboard_plan": "",
            "dashboard_subscription_end": None,
            "dashboard_subscription_status": "inactive",
            "is_admin": True,
            "role": "tenant_owner",
            "tenant_id": tenant_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one(new_user)
        sub_status = "inactive"
        sub_end = None
        is_admin = True
    
    # Create JWT token — include role and tenant context
    _otp_role = existing.get("role", "tenant_owner") if existing else "tenant_owner"
    _otp_tid = existing.get("tenant_id", "") if existing else tenant_id
    _otp_tv = existing.get("token_version", 0) if existing else 0
    token = create_token(user_id, role=_otp_role, tenant_id=_otp_tid, token_version=_otp_tv)
    refresh = create_refresh_token(user_id)
    
    # Format subscription end date
    if sub_end and isinstance(sub_end, str):
        sub_end = datetime.fromisoformat(sub_end)
    
    return {
        "token": token,
        "refresh_token": refresh,
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
    
    # Send OTP via email
    from services.email_service import send_email
    email_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #1a1a2e; color: #eee; padding: 30px; border-radius: 12px;">
        <h1 style="color: #e11d48; text-align: center;">TGSubsBot</h1>
        <h2 style="text-align: center;">Password Reset Code</h2>
        <p>Your password reset OTP is:</p>
        <div style="background: #16213e; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
            <span style="font-size: 32px; letter-spacing: 8px; color: #e11d48; font-weight: bold;">{otp}</span>
        </div>
        <p style="color: #aaa;">This code expires in 15 minutes. If you didn't request this, ignore this email.</p>
        <p style="color: #666; margin-top: 30px; text-align: center;">TGSubsBot Team</p>
    </div>
    """
    email_result = await send_email(email, "Password Reset - TGSubsBot", email_html)
    
    response = {"message": "If the email exists, a reset code has been sent"}
    if email_result.get("status") != "success":
        # Email not sent (API key missing or sending failed), return OTP for testing
        response["test_otp"] = otp
    return response


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
    if not is_any_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    tickets = await db.support_tickets.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return tickets

@router.post("/admin/support/tickets/{ticket_id}/reply")
async def admin_reply_to_ticket(ticket_id: str, data: dict, user = Depends(get_current_user)):
    """Add admin reply to a ticket (can reply multiple times)"""
    if not is_any_admin(user):
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
    if not is_any_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.support_tickets.update_one(
        {"id": ticket_id},
        {"$set": {"status": data.get("status", "open")}}
    )
    
    return {"message": "Status updated"}


@router.delete("/support/tickets/{ticket_id}")
async def delete_ticket(ticket_id: str, user = Depends(get_current_user)):
    """Delete a support ticket (own ticket or admin)"""
    ticket = await db.support_tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    is_admin_user = is_any_admin(user)
    is_owner = ticket.get("user_id") == user.get("id")

    if not is_admin_user and not is_owner:
        raise HTTPException(status_code=403, detail="Not authorized to delete this ticket")

    await db.support_tickets.delete_one({"id": ticket_id})
    return {"message": "Ticket deleted"}


@router.put("/support/tickets/{ticket_id}/close")
async def close_ticket(ticket_id: str, user = Depends(get_current_user)):
    """Close own ticket"""
    ticket = await db.support_tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    admin_check = is_any_admin(user)
    is_owner = ticket.get("user_id") == user.get("id")

    if not admin_check and not is_owner:
        raise HTTPException(status_code=403, detail="Not authorized")

    await db.support_tickets.update_one({"id": ticket_id}, {"$set": {"status": "closed"}})
    return {"message": "Ticket closed"}


@router.put("/support/tickets/{ticket_id}/reopen")
async def reopen_ticket(ticket_id: str, user = Depends(get_current_user)):
    """Reopen a closed/resolved ticket"""
    ticket = await db.support_tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    admin_check = is_any_admin(user)
    is_owner = ticket.get("user_id") == user.get("id")

    if not admin_check and not is_owner:
        raise HTTPException(status_code=403, detail="Not authorized")

    await db.support_tickets.update_one({"id": ticket_id}, {"$set": {"status": "open"}})
    return {"message": "Ticket reopened"}


# ============== DASHBOARD SUBSCRIPTION ROUTES ==============
