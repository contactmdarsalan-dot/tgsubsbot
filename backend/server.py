from fastapi import FastAPI, APIRouter, HTTPException, Depends, BackgroundTasks, Request, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import random
import base64
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
import razorpay
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
from twilio.rest import Client as TwilioClient
import pytesseract
from PIL import Image
from io import BytesIO
import re
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Razorpay client (optional - only if keys provided)
razorpay_client = None
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Twilio client (optional - only if keys provided)
twilio_client = None
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHANNEL_ID = os.environ.get('TELEGRAM_CHANNEL_ID', '')

# Emergent LLM Key for AI payment analysis
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# JWT Secret
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key-change-in-production')

app = FastAPI()
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Scheduler
scheduler = AsyncIOScheduler()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============== MODELS ==============

class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    phone: str = ""

class UserLogin(BaseModel):
    email: str
    password: str

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    name: str
    phone: str = ""
    # Dashboard subscription fields
    dashboard_plan: str = ""  # 1month, 6month, 12month, lifetime
    dashboard_subscription_end: Optional[datetime] = None
    dashboard_subscription_status: str = "inactive"  # active, inactive, trial
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Dashboard subscription plans (for the SaaS)
DASHBOARD_PLANS = {
    "1month": {"name": "1 Month", "price": 4999, "days": 30},
    "6month": {"name": "6 Months", "price": 24999, "days": 180},
    "12month": {"name": "12 Months", "price": 44999, "days": 365},
    "lifetime": {"name": "Lifetime", "price": 0, "days": 36500}  # 100 years
}

class SubscriptionPlanCreate(BaseModel):
    name: str
    price: float
    duration_days: int
    features: List[str] = []
    is_active: bool = True
    channel_id: str = ""  # Each plan can have its own channel
    group_id: str = ""    # Manual group ID for this plan
    auto_assign_group: bool = False  # Auto-assign from groups pool

class SubscriptionPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    price: float
    duration_days: int
    features: List[str] = []
    is_active: bool = True
    channel_id: str = ""  # Each plan can have its own channel
    group_id: str = ""    # Manual group ID for this plan
    auto_assign_group: bool = False  # Auto-assign from groups pool
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SubscriberCreate(BaseModel):
    telegram_user_id: str
    telegram_username: Optional[str] = None
    plan_id: str
    payment_method: str = "manual"  # razorpay, manual
    payment_id: Optional[str] = None

class Subscriber(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_user_id: str
    telegram_username: Optional[str] = None
    plan_id: str
    plan_name: str = ""
    status: str = "active"  # active, expired, grace
    payment_method: str = "manual"
    payment_id: Optional[str] = None
    start_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    grace_end_date: Optional[datetime] = None
    reminder_sent: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PaymentCreate(BaseModel):
    subscriber_id: Optional[str] = None
    telegram_user_id: str
    amount: float
    plan_id: str
    payment_method: str = "manual"

class Payment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subscriber_id: Optional[str] = None
    telegram_user_id: str
    amount: float
    plan_id: str
    payment_method: str
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    status: str = "pending"  # pending, verified, failed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BotSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = "bot_settings"
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""  # Private subscriber channel
    promo_channel_id: str = ""     # Public promo channel (Subscribe button will appear here)
    website_link: str = ""
    qr_code_url: str = ""
    payment_upi_id: str = ""       # UPI ID for payment verification (e.g., miraclecouplee@oksbi)
    reminder_days_before: int = 3
    grace_period_days: int = 2
    followup_enabled: bool = True
    followup_message: str = "Check out our premium services!"
    # New Settings - Batch 1
    ai_auto_approve_threshold: int = 85  # AI confidence % for auto-approve (50-100)
    support_username: str = ""  # @username for support contact
    welcome_message: str = "👋 Welcome to our subscription bot! Use /plans to see available plans."
    payment_instructions: str = "📱 Scan the QR code above and send payment screenshot here."
    success_message: str = "🎉 Payment verified! Your subscription is now active."
    # Video Call Settings
    video_call_enabled: bool = True
    video_call_price: float = 500  # Price per video call
    video_call_duration: int = 30  # Default duration in minutes
    video_call_instructions: str = "📹 Book a 1-on-1 video call with us! Choose a date and time."

class MessageTemplate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str  # welcome, reminder, followup, expiry
    message: str
    is_active: bool = True

# ============== COUPON/DISCOUNT MODEL ==============
class Coupon(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    code: str  # e.g., SAVE20, WELCOME50
    discount_type: str = "percentage"  # percentage, flat
    discount_value: float  # 20 for 20% or 50 for ₹50 off
    min_purchase: float = 0  # Minimum purchase amount
    max_uses: int = 0  # 0 = unlimited
    used_count: int = 0
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None  # ISO date string
    applicable_plans: List[str] = []  # Empty = all plans
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============== USER NOTES & TAGS MODEL ==============
class UserNote(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str  # telegram_user_id
    note: str
    added_by: str  # admin email
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserTag(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str  # VIP, New, Trusted, etc.
    color: str = "blue"  # For UI display
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============== REFERRAL MODEL ==============
class Referral(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    referrer_id: str  # telegram_user_id of referrer
    referrer_username: str
    referral_code: str  # Unique code like REF_abc123
    referred_users: List[str] = []  # List of telegram_user_ids who used this code
    reward_type: str = "discount"  # discount, cash, free_days
    reward_value: float = 10  # 10% discount or ₹10 or 10 days
    total_earnings: float = 0
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============== SCHEDULED BROADCAST MODEL ==============
class ScheduledBroadcast(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    message: str
    target_segment: str = "all"  # all, active, expired, new
    scheduled_at: str  # ISO datetime string
    status: str = "pending"  # pending, sent, cancelled
    sent_count: int = 0
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============== FAQ / AUTO-REPLY MODEL ==============
class FAQ(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    keywords: List[str]  # ["price", "cost", "kitna"]
    response: str
    is_active: bool = True
    usage_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============== BLOCKED USERS MODEL ==============
class BlockedUser(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_user_id: str
    telegram_username: str = ""
    reason: str = ""
    blocked_by: str
    blocked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============== VIDEO CALL BOOKING MODEL ==============
class VideoCallBooking(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_user_id: str
    telegram_username: str = ""
    user_name: str = ""
    plan_id: str = ""
    plan_name: str = ""
    call_type: str = "video"  # video, audio
    scheduled_date: str = ""  # YYYY-MM-DD
    scheduled_time: str = ""  # HH:MM
    duration_minutes: int = 30
    price: float = 0
    status: str = "pending"  # pending, confirmed, completed, cancelled
    meeting_link: str = ""
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Support Ticket model (Chat-style with multiple messages)
class SupportTicket(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    user_email: str
    user_name: str
    subject: str
    messages: List[dict] = []  # List of {sender, message, timestamp}
    status: str = "open"  # open, in_progress, resolved, closed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============== CHAT GROUPS POOL MODEL ==============

class ChatGroupPool(BaseModel):
    """Pool of pre-created groups for time-limited chat feature"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_id: str  # Telegram group/supergroup ID
    group_name: str = ""
    group_invite_link: str = ""
    status: str = "available"  # available, in_use, needs_cleanup
    assigned_to_user_id: str = ""  # Telegram user ID
    assigned_to_username: str = ""
    plan_type: str = ""  # "5min" or "30min"
    session_start: Optional[datetime] = None
    session_end: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ActiveChatSession(BaseModel):
    """Track active time-limited chat sessions"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str  # Telegram user ID
    username: str = ""
    group_id: str  # Telegram group ID
    plan_type: str  # "5min" or "30min"
    duration_minutes: int
    start_time: datetime
    end_time: datetime
    status: str = "active"  # active, expired, renewed
    renewal_message_sent: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============== PAID POST MODEL ==============
class PaidPost(BaseModel):
    """Model for paid/locked posts in channel"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str  # Channel where post was made
    original_message_id: int  # Original message ID in channel
    blurred_message_id: int = 0  # Blurred message ID (replaces original)
    content_type: str = "photo"  # photo, video, document
    original_file_id: str = ""  # Original file ID for delivery
    blurred_file_id: str = ""  # Blurred/preview file ID
    caption: str = ""  # Caption for the content
    price: float = 0  # Price for unlocking (0 = use default plan price)
    unlock_count: int = 0  # How many users unlocked
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PaidPostUnlock(BaseModel):
    """Track which users unlocked which paid posts"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    post_id: str  # PaidPost ID
    telegram_user_id: str
    telegram_username: str = ""
    payment_id: str = ""  # Payment record ID
    unlocked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))



# ============== AUTH HELPERS ==============

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ============== TELEGRAM HELPERS ==============

# Rate limiting for Telegram API
telegram_last_request = {}
TELEGRAM_MIN_INTERVAL = 0.05  # 50ms between messages per chat

# Cache for bot username
_bot_username_cache = {}

async def get_bot_settings():
    """Get bot settings from database, with environment variable fallback"""
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0})
    settings = settings or {}
    
    # Fallback to environment variable if not in database
    if not settings.get("telegram_bot_token"):
        env_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if env_token:
            settings["telegram_bot_token"] = env_token
            logger.info("Using TELEGRAM_BOT_TOKEN from environment variable")
    
    return settings

async def get_bot_username(bot_token: str) -> str:
    """Get bot username from Telegram API (cached)"""
    if bot_token in _bot_username_cache:
        return _bot_username_cache[bot_token]
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/getMe"
            response = await http_client.get(url)
            if response.status_code == 200:
                data = response.json()
                username = data.get("result", {}).get("username", "")
                if username:
                    _bot_username_cache[bot_token] = username
                return username
    except Exception as e:
        logger.error(f"Failed to get bot username: {e}")
    return ""

async def send_telegram_message(chat_id: str, message: str, bot_token: str = None, retries: int = 3):
    """Send message via Telegram Bot API with rate limiting and retry"""
    if not bot_token:
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
    
    if not bot_token:
        logger.warning("Telegram bot token not configured")
        return False
    
    # Rate limiting per chat
    now = asyncio.get_event_loop().time()
    last = telegram_last_request.get(chat_id, 0)
    if now - last < TELEGRAM_MIN_INTERVAL:
        await asyncio.sleep(TELEGRAM_MIN_INTERVAL - (now - last))
    telegram_last_request[chat_id] = asyncio.get_event_loop().time()
    
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                response = await http_client.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})
                logger.info(f"Telegram response: {response.status_code}")
                
                if response.status_code == 200:
                    return True
                elif response.status_code == 429:
                    # Rate limited - wait and retry
                    retry_after = response.json().get("parameters", {}).get("retry_after", 1)
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                else:
                    logger.error(f"Telegram error: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(0.5)
    return False


# ============== OCR PAYMENT DETECTION ==============

async def download_telegram_photo(file_id: str, bot_token: str) -> bytes:
    """Download photo from Telegram servers"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            # First get file path
            file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
            response = await http_client.get(file_info_url)
            if response.status_code == 200:
                file_path = response.json().get("result", {}).get("file_path")
                if file_path:
                    # Download the actual file
                    download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
                    file_response = await http_client.get(download_url)
                    if file_response.status_code == 200:
                        return file_response.content
    except Exception as e:
        logger.error(f"Error downloading photo: {e}")
    return None

def detect_payment_screenshot(image_bytes: bytes) -> dict:
    """
    FAST OCR to detect if image is a valid payment screenshot.
    Simplified for speed - tries only 2 versions.
    """
    from PIL import ImageOps
    
    payment_keywords = [
        "gpay", "google pay", "phonepe", "paytm", "bhim", "amazon pay",
        "upi", "paid", "payment", "successful", "completed", "transaction",
        "success", "done", "approved", "₹", "rs"
    ]
    
    try:
        image = Image.open(BytesIO(image_bytes))
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        
        extracted_text = ""
        
        # Try only 2 versions for speed
        # Version 1: Grayscale
        gray = image.convert('L')
        try:
            text1 = pytesseract.image_to_string(gray, lang='eng', config='--psm 6 --oem 1')
            extracted_text += " " + text1
        except Exception:
            pass
        
        # Version 2: Inverted grayscale (for dark mode)
        try:
            inv_gray = ImageOps.invert(gray)
            text2 = pytesseract.image_to_string(inv_gray, lang='eng', config='--psm 6 --oem 1')
            extracted_text += " " + text2
        except Exception:
            pass
        
        text_lower = extracted_text.lower()
        
        # Find keywords
        found_keywords = [k for k in payment_keywords if k in text_lower]
        
        # Simple validation - any 1 keyword = valid (very lenient for speed)
        is_valid = len(found_keywords) >= 1 or "success" in text_lower or "paid" in text_lower
        
        logger.info(f"Fast OCR: found {len(found_keywords)} keywords, valid={is_valid}")
        
        return {
            "is_valid": is_valid,
            "found_keywords": found_keywords,
            "extracted_text_preview": text_lower[:200]
        }
        
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return {"is_valid": False, "error": str(e), "found_keywords": []}


# ============== IMAGE BLUR FOR PAID POSTS ==============

def create_blurred_image(image_bytes: bytes, blur_radius: int = 30) -> bytes:
    """
    Create a heavily blurred version of an image for paid post preview.
    Also adds a lock overlay text.
    """
    from PIL import ImageFilter, ImageDraw, ImageFont
    
    try:
        image = Image.open(BytesIO(image_bytes))
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        
        # Apply heavy blur
        blurred = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        # Add semi-transparent overlay
        overlay = Image.new('RGBA', blurred.size, (0, 0, 0, 100))
        blurred = blurred.convert('RGBA')
        blurred = Image.alpha_composite(blurred, overlay)
        blurred = blurred.convert('RGB')
        
        # Add lock emoji/text in center
        draw = ImageDraw.Draw(blurred)
        text = "🔒 UNLOCK TO VIEW"
        
        # Get image dimensions
        width, height = blurred.size
        
        # Try to use a font, fallback to default
        try:
            font_size = max(width // 15, 20)
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        
        # Get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Center the text
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        # Draw text with shadow for visibility
        draw.text((x+2, y+2), text, font=font, fill=(0, 0, 0))
        draw.text((x, y), text, font=font, fill=(255, 255, 255))
        
        # Convert back to bytes
        output = BytesIO()
        blurred.save(output, format='JPEG', quality=85)
        return output.getvalue()
        
    except Exception as e:
        logger.error(f"Error creating blurred image: {e}")
        return None


async def send_telegram_photo(chat_id: str, photo_url_or_bytes: str, caption: str, bot_token: str, reply_markup: dict = None) -> dict:
    """Send photo to Telegram chat"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            
            data = {
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": "HTML"
            }
            
            if reply_markup:
                import json
                data["reply_markup"] = json.dumps(reply_markup)
            
            # Check if it's a URL or file_id
            if isinstance(photo_url_or_bytes, str):
                data["photo"] = photo_url_or_bytes
                response = await http_client.post(url, data=data)
            else:
                # It's bytes - send as file
                files = {"photo": ("image.jpg", photo_url_or_bytes, "image/jpeg")}
                response = await http_client.post(url, data=data, files=files)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to send photo: {response.text}")
                return None
    except Exception as e:
        logger.error(f"Error sending photo: {e}")
        return None


async def send_telegram_video(chat_id: str, video_file_id: str, caption: str, bot_token: str, reply_markup: dict = None) -> dict:
    """Send video to Telegram chat"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
            
            data = {
                "chat_id": chat_id,
                "video": video_file_id,
                "caption": caption,
                "parse_mode": "HTML"
            }
            
            if reply_markup:
                import json
                data["reply_markup"] = json.dumps(reply_markup)
            
            response = await http_client.post(url, json=data)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to send video: {response.text}")
                return None
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        return None


async def delete_telegram_message(chat_id: str, message_id: int, bot_token: str) -> bool:
    """Delete a message from Telegram"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/deleteMessage"
            response = await http_client.post(url, json={
                "chat_id": chat_id,
                "message_id": message_id
            })
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        return False


# ============== AI PAYMENT ANALYSIS (GPT-4o Vision) ==============

async def analyze_payment_screenshot_with_ai(image_bytes: bytes, expected_amount: float = None, expected_upi_id: str = None) -> dict:
    """
    Use GPT-4o Vision to analyze payment screenshot.
    Returns: is_valid, confidence, extracted_data, fake_indicators, auto_approve
    """
    if not EMERGENT_LLM_KEY:
        logger.warning("EMERGENT_LLM_KEY not configured, skipping AI analysis")
        return {"ai_enabled": False, "error": "AI not configured"}
    
    try:
        # Convert image to base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Create AI chat instance
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"payment-analysis-{uuid.uuid4()}",
            system_message="""You are an expert payment screenshot analyzer. Your job is to:
1. Extract payment details (amount, UPI ID, transaction ID, date/time, payment app, status)
2. Detect if the screenshot is fake/edited (look for: inconsistent fonts, pixel artifacts, wrong shadows, misaligned elements, suspicious timestamps)
3. Verify if payment status shows "Success", "Completed", or "Paid"
4. Match amount and UPI ID if provided

RESPOND ONLY IN THIS JSON FORMAT:
{
    "is_valid_payment": true/false,
    "confidence_score": 0-100,
    "extracted_data": {
        "amount": "extracted amount or null",
        "upi_id": "extracted UPI ID or null",
        "transaction_id": "extracted transaction ID or null",
        "payment_app": "GPay/PhonePe/Paytm/etc or null",
        "status": "Success/Completed/Failed/Pending or null",
        "timestamp": "extracted date/time or null"
    },
    "fake_indicators": ["list of suspicious elements found"],
    "amount_matches": true/false/null,
    "upi_matches": true/false/null,
    "auto_approve_recommended": true/false,
    "reason": "brief explanation"
}"""
        ).with_model("openai", "gpt-4o")
        
        # Build prompt
        prompt = "Analyze this payment screenshot and extract all details. Check if it's a genuine payment confirmation."
        if expected_amount:
            prompt += f"\n\nExpected payment amount: ₹{expected_amount}"
        if expected_upi_id:
            prompt += f"\nExpected UPI ID: {expected_upi_id}"
        
        # Create message with image
        image_content = ImageContent(image_base64=image_base64)
        user_message = UserMessage(
            text=prompt,
            file_contents=[image_content]
        )
        
        # Send to AI
        response = await chat.send_message(user_message)
        logger.info(f"AI Payment Analysis Response: {response[:500]}")
        
        # Parse JSON response
        import json
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            
            result = json.loads(json_str)
            result["ai_enabled"] = True
            result["raw_response"] = response[:500]
            
            # Auto-approve logic: confidence >= 85 AND is_valid AND no major fake indicators
            if result.get("confidence_score", 0) >= 85 and result.get("is_valid_payment", False):
                if not result.get("fake_indicators") or len(result.get("fake_indicators", [])) == 0:
                    result["auto_approve_recommended"] = True
                else:
                    result["auto_approve_recommended"] = False
            
            return result
            
        except json.JSONDecodeError as je:
            logger.error(f"Failed to parse AI response as JSON: {je}")
            return {
                "ai_enabled": True,
                "is_valid_payment": False,
                "confidence_score": 0,
                "auto_approve_recommended": False,
                "error": "Failed to parse AI response",
                "raw_response": response[:500]
            }
            
    except Exception as e:
        logger.error(f"AI Payment Analysis Error: {e}")
        return {
            "ai_enabled": True,
            "is_valid_payment": False,
            "confidence_score": 0,
            "auto_approve_recommended": False,
            "error": str(e)
        }


async def kick_user_from_channel(telegram_user_id: str):
    """Kick user from the main channel when payment is unverified"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    channel_id = settings.get("telegram_channel_id", "") or TELEGRAM_CHANNEL_ID
    
    if not bot_token or not channel_id or not telegram_user_id:
        logger.warning(f"Cannot kick user - missing: token={bool(bot_token)}, channel={bool(channel_id)}, user={bool(telegram_user_id)}")
        return False
    
    try:
        async with httpx.AsyncClient() as http_client:
            # Ban temporarily (35 seconds) to kick
            url = f"https://api.telegram.org/bot{bot_token}/banChatMember"
            response = await http_client.post(url, json={
                "chat_id": channel_id,
                "user_id": int(telegram_user_id),
                "until_date": int((datetime.now(timezone.utc) + timedelta(seconds=35)).timestamp())
            })
            logger.info(f"Kick from channel response: {response.status_code} - {response.text}")
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Error kicking user from channel: {e}")
        return False


async def send_screenshot_reminders(chat_id: str, username: str, bot_token: str):
    """Send reminder messages until user sends screenshot"""
    reminder_messages = [
        "⏰ <b>Reminder!</b>\n\n📸 Screenshot bhejo payment ka!",
        "👀 <b>Hey!</b>\n\n📸 Payment screenshot upload karo!",
        "⚠️ <b>Screenshot pending!</b>\n\n📸 Bina screenshot ke access nahi milega!",
        "🔔 <b>Reminder!</b>\n\n📸 Screenshot bhejo!",
        "📸 <b>Waiting...</b>\n\nScreenshot upload karo!",
        "⏳ <b>Jaldi karo!</b>\n\n📸 Screenshot bhejo payment ka!",
        "👆 <b>Payment kiya?</b>\n\n📸 Screenshot bhejo!",
        "🔄 <b>Pending!</b>\n\n📸 Screenshot upload karo!",
        "⚡ <b>Quick!</b>\n\n📸 Screenshot bhejo verify ke liye!",
        "📱 <b>Screenshot?</b>\n\n📸 Payment proof bhejo!",
        "⏰ <b>Still waiting...</b>\n\n📸 Screenshot bhejo!",
        "👀 <b>Kaha ho?</b>\n\n📸 Screenshot upload karo!",
        "🔔 <b>Hello!</b>\n\n📸 Payment screenshot bhejo!",
        "⚠️ <b>Pending!</b>\n\n📸 Screenshot bhejo jaldi!",
        "📸 <b>Last chance!</b>\n\nScreenshot bhejo ya discount lo!"
    ]
    
    for i in range(20):  # 20 reminders max
        # Wait 10 seconds between reminders
        await asyncio.sleep(10)
        
        # Check if still waiting for screenshot
        pending = await db.pending_screenshots.find_one({"telegram_user_id": chat_id, "status": "waiting"}, {"_id": 0})
        if not pending:
            # Screenshot received or cancelled
            return
        
        # Get message (cycle through if more than 15)
        msg = reminder_messages[i] if i < len(reminder_messages) else reminder_messages[i % len(reminder_messages)]
        full_msg = f"👆 @{username if username else 'User'}\n\n{msg}"
        
        # Buttons - Cancel always, Discount after 8 reminders
        buttons = []
        if i >= 7:  # After 8 reminders (0-indexed, so 7)
            buttons.append([{"text": "🎁 Get Discount!", "callback_data": f"discount_{pending.get('plan_id', '')}"}])
        buttons.append([{"text": "❌ Cancel", "callback_data": "cancel_payment"}])
        
        await send_telegram_message_with_buttons(chat_id, full_msg, buttons, bot_token)
        
        # Update reminder count
        await db.pending_screenshots.update_one(
            {"telegram_user_id": chat_id},
            {"$set": {"reminder_count": i + 1}}
        )
    
    # After all reminders, send final message with discount
    pending = await db.pending_screenshots.find_one({"telegram_user_id": chat_id, "status": "waiting"}, {"_id": 0})
    if pending:
        final_msg = f"🎁 <b>Special Offer!</b>\n\n"
        final_msg += "Screenshot nahi mila, but aapke liye special discount!\n\n"
        final_msg += "📸 Screenshot bhejo ya discount lo!"
        
        buttons = [
            [{"text": "🎁 Get Discount!", "callback_data": f"discount_{pending.get('plan_id', '')}"}],
            [{"text": "❌ Cancel", "callback_data": "cancel_payment"}]
        ]
        await send_telegram_message_with_buttons(chat_id, final_msg, buttons, bot_token)

async def add_to_channel(user_id: str, plan_channel_id: str = None, plan_name: str = ""):
    """Add user to private channel by sending invite link"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    # Use plan's channel if provided, otherwise use default
    channel_id = plan_channel_id if plan_channel_id else settings.get("telegram_channel_id", "")
    
    if not bot_token or not channel_id:
        logger.warning("Bot token or channel ID not configured")
        return False
    try:
        async with httpx.AsyncClient() as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/createChatInviteLink"
            response = await http_client.post(url, json={
                "chat_id": channel_id,
                "member_limit": 1,
                "expire_date": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp())
            })
            logger.info(f"Create invite link response: {response.status_code} - {response.text}")
            if response.status_code == 200:
                data = response.json()
                invite_link = data.get("result", {}).get("invite_link")
                if invite_link:
                    msg = f"🎉 <b>Welcome!</b>\n\n"
                    if plan_name:
                        msg += f"📦 Plan: <b>{plan_name}</b>\n\n"
                    msg += f"🔗 Join your premium channel:\n{invite_link}"
                    await send_telegram_message(user_id, msg, bot_token)
                    return True
        return False
    except Exception as e:
        logger.error(f"Failed to add user to channel: {e}")
        return False

async def remove_from_channel(user_id: str, plan_channel_id: str = None):
    """Remove user from private channel"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    channel_id = plan_channel_id if plan_channel_id else settings.get("telegram_channel_id", "")
    
    if not bot_token or not channel_id:
        return False
    try:
        async with httpx.AsyncClient() as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/banChatMember"
            response = await http_client.post(url, json={
                "chat_id": channel_id,
                "user_id": int(user_id),
                "until_date": int((datetime.now(timezone.utc) + timedelta(seconds=30)).timestamp())
            })
            logger.info(f"Ban member response: {response.status_code} - {response.text}")
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to remove user from channel: {e}")
        return False


# ============== CHAT POOL HELPER FUNCTIONS ==============

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
    
    # Update group status
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
    
    # Create active session record
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
    
    # Create invite link for the group
    try:
        async with httpx.AsyncClient() as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/createChatInviteLink"
            response = await http_client.post(url, json={
                "chat_id": group_id,
                "member_limit": 1,
                "expire_date": int((now + timedelta(minutes=10)).timestamp())  # Link valid for 10 min
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
            # First kick (ban temporarily)
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
    # Get session info before releasing
    group = await db.chat_groups_pool.find_one({"group_id": group_id}, {"_id": 0})
    
    if group and group.get("assigned_to_user_id"):
        user_id = group.get("assigned_to_user_id")
        # Kick user from group
        await kick_user_from_group(group_id, user_id)
    
    # Reset group to available
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
    
    # Find active sessions that have expired
    expired_sessions = await db.chat_sessions.find({
        "status": "active",
        "end_time": {"$lte": now.isoformat()}
    }, {"_id": 0}).to_list(100)
    
    for session in expired_sessions:
        user_id = session.get("user_id")
        group_id = session.get("group_id")
        plan_type = session.get("plan_type")
        
        # Restrict user from sending messages
        await restrict_user_in_group(group_id, user_id, can_send=False)
        
        # Send renewal message
        if not session.get("renewal_message_sent"):
            renewal_msg = "⏰ <b>Time's Up!</b>\n\n"
            renewal_msg += f"Your {plan_type} chat session has ended.\n\n"
            renewal_msg += "🔄 <b>Want to continue?</b>\n"
            renewal_msg += "Click below to renew or exit!"
            
            # Send message in group with Renew and Cancel buttons
            try:
                async with httpx.AsyncClient() as http_client:
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    buttons = [
                        [
                            {"text": "🔄 Renew Chat", "callback_data": f"renew_chat_{session['id']}"},
                            {"text": "❌ Exit Chat", "callback_data": f"exit_chat_{session['id']}"}
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
            
            # Also send to user's private chat
            try:
                async with httpx.AsyncClient() as http_client:
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    private_msg = "⏰ <b>Chat Session Ended!</b>\n\n"
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
            
            # Update session
            await db.chat_sessions.update_one(
                {"id": session["id"]},
                {"$set": {"renewal_message_sent": True, "status": "expired"}}
            )
        
        # Wait 5 minutes after expiry, then kick user if not renewed
        session_end = datetime.fromisoformat(session["end_time"]) if isinstance(session["end_time"], str) else session["end_time"]
        if now > session_end + timedelta(minutes=5):
            # Check if renewed
            renewed = await db.chat_sessions.find_one({
                "user_id": user_id,
                "group_id": group_id,
                "status": "active",
                "start_time": {"$gt": session["end_time"]}
            })
            
            if not renewed:
                # Kick user and release group
                await release_chat_group(group_id)
                logger.info(f"Released group {group_id} after session expiry")




# ============== AUTH ROUTES ==============

@api_router.post("/auth/register")
async def register(user: UserCreate):
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

@api_router.post("/auth/login")
async def login(user: UserLogin):
    existing = await db.users.find_one({"email": user.email}, {"_id": 0})
    if not existing or not verify_password(user.password, existing.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Check subscription status
    sub_status = existing.get("dashboard_subscription_status", "inactive")
    sub_end = existing.get("dashboard_subscription_end")
    
    if sub_end and isinstance(sub_end, str):
        sub_end = datetime.fromisoformat(sub_end)
    
    # Check if subscription expired
    if sub_status == "active" and sub_end and datetime.now(timezone.utc) > sub_end:
        sub_status = "expired"
        await db.users.update_one({"id": existing["id"]}, {"$set": {"dashboard_subscription_status": "expired"}})
    
    token = create_token(existing["id"])
    return {
        "token": token, 
        "user": {
            "id": existing["id"], 
            "email": existing["email"], 
            "name": existing["name"],
            "dashboard_subscription_status": sub_status,
            "dashboard_plan": existing.get("dashboard_plan", ""),
            "dashboard_subscription_end": sub_end.isoformat() if sub_end else None,
            "is_admin": existing.get("is_admin", False)
        }
    }

# ============== GOOGLE OAUTH ROUTES ==============

@api_router.post("/auth/google/session")
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

@api_router.get("/auth/me")
async def get_me(user = Depends(get_current_user)):
    sub_end = user.get("dashboard_subscription_end")
    if sub_end and isinstance(sub_end, str):
        sub_end = datetime.fromisoformat(sub_end)
    
    return {
        "id": user["id"], 
        "email": user["email"], 
        "name": user["name"],
        "phone": user.get("phone", ""),
        "picture": user.get("picture", ""),
        "dashboard_subscription_status": user.get("dashboard_subscription_status", "inactive"),
        "dashboard_plan": user.get("dashboard_plan", ""),
        "dashboard_subscription_end": sub_end.isoformat() if sub_end else None,
        "is_admin": user.get("is_admin", False)
    }

# ============== TWILIO OTP ROUTES ==============

@api_router.post("/auth/otp/send")
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

@api_router.post("/auth/otp/verify")
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

# ============== SUPPORT TICKET ROUTES (Chat-style) ==============

@api_router.post("/support/tickets")
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

@api_router.get("/support/tickets")
async def get_user_support_tickets(user = Depends(get_current_user)):
    """Get user's own support tickets"""
    tickets = await db.support_tickets.find(
        {"user_id": user["id"]}, 
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return tickets

@api_router.post("/support/tickets/{ticket_id}/message")
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

@api_router.get("/admin/support/tickets")
async def get_all_support_tickets(user = Depends(get_current_user)):
    """Get all support tickets (super admin or admin only)"""
    is_super_admin = user.get("email") == SUPER_ADMIN_EMAIL
    is_admin = user.get("is_admin", False)
    
    if not is_super_admin and not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    tickets = await db.support_tickets.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return tickets

@api_router.post("/admin/support/tickets/{ticket_id}/reply")
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

@api_router.put("/admin/support/tickets/{ticket_id}/status")
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

# Default dashboard plans (will be stored in DB)
DEFAULT_DASHBOARD_PLANS = [
    {"id": "1month", "name": "1 Month", "price": 4999, "duration_days": 30, "popular": False, "save": "", "contact": False, "is_active": True},
    {"id": "6month", "name": "6 Months", "price": 24999, "duration_days": 180, "popular": True, "save": "17%", "contact": False, "is_active": True},
    {"id": "12month", "name": "12 Months", "price": 44999, "duration_days": 365, "popular": False, "save": "25%", "contact": False, "is_active": True},
    {"id": "lifetime", "name": "Lifetime", "price": 0, "duration_days": 36500, "popular": False, "save": "", "contact": True, "is_active": True}
]

async def get_dashboard_plans_from_db():
    """Get dashboard plans from database, initialize if empty"""
    plans = await db.dashboard_plans.find({}, {"_id": 0}).to_list(100)
    if not plans:
        # Initialize with defaults
        for plan in DEFAULT_DASHBOARD_PLANS:
            await db.dashboard_plans.insert_one(plan)
        plans = DEFAULT_DASHBOARD_PLANS
    return plans

@api_router.get("/dashboard-plans")
async def get_dashboard_plans():
    """Get available dashboard subscription plans"""
    plans = await get_dashboard_plans_from_db()
    # Format for frontend
    formatted = []
    for p in plans:
        if p.get("is_active", True):
            formatted.append({
                "id": p["id"],
                "name": p["name"],
                "price": p["price"],
                "duration": f"{p.get('duration_days', 30)} days" if p["id"] != "lifetime" else "Forever",
                "popular": p.get("popular", False),
                "save": p.get("save", ""),
                "contact": p.get("contact", False)
            })
    return {"plans": formatted}

@api_router.get("/admin/dashboard-plans")
async def get_admin_dashboard_plans(user = Depends(get_current_user)):
    """Get all dashboard plans for editing (super admin only)"""
    await verify_super_admin(user)
    plans = await get_dashboard_plans_from_db()
    return plans

@api_router.put("/admin/dashboard-plans/{plan_id}")
async def update_dashboard_plan(plan_id: str, data: dict, user = Depends(get_current_user)):
    """Update a dashboard plan (super admin only)"""
    await verify_super_admin(user)
    
    existing = await db.dashboard_plans.find_one({"id": plan_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    update_data = {
        "name": data.get("name", existing["name"]),
        "price": data.get("price", existing["price"]),
        "duration_days": data.get("duration_days", existing.get("duration_days", 30)),
        "popular": data.get("popular", existing.get("popular", False)),
        "save": data.get("save", existing.get("save", "")),
        "contact": data.get("contact", existing.get("contact", False)),
        "is_active": data.get("is_active", existing.get("is_active", True))
    }
    
    await db.dashboard_plans.update_one({"id": plan_id}, {"$set": update_data})
    
    # Also update DASHBOARD_PLANS dict for subscription approval
    global DASHBOARD_PLANS
    DASHBOARD_PLANS[plan_id] = {
        "name": update_data["name"],
        "price": update_data["price"],
        "days": update_data["duration_days"]
    }
    
    return {"message": "Plan updated"}

@api_router.post("/dashboard-subscription/request")
async def request_dashboard_subscription(data: dict, user = Depends(get_current_user)):
    """Request dashboard subscription - creates pending request"""
    plan_id = data.get("plan_id")
    
    # Get plan from database
    plans = await get_dashboard_plans_from_db()
    plan_info = next((p for p in plans if p["id"] == plan_id), None)
    
    if not plan_info:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    # Create subscription request
    request_obj = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_email": user["email"],
        "user_name": user["name"],
        "plan_id": plan_id,
        "plan_name": plan_info.get("name", ""),
        "amount": plan_info.get("price", 0),
        "status": "pending",  # pending, approved, rejected
        "screenshot_url": data.get("screenshot_url", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.dashboard_subscriptions.insert_one(request_obj)
    
    return {"message": "Subscription request submitted", "request_id": request_obj["id"]}

@api_router.post("/dashboard-subscription/create-order")
async def create_dashboard_razorpay_order(data: dict, user = Depends(get_current_user)):
    """Create Razorpay order for dashboard subscription"""
    if not razorpay_client:
        raise HTTPException(status_code=400, detail="Razorpay not configured")
    
    plan_id = data.get("plan_id")
    
    # Get plan from database
    plans = await get_dashboard_plans_from_db()
    plan_info = next((p for p in plans if p["id"] == plan_id), None)
    
    if not plan_info:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    amount = plan_info.get("price", 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid plan price")
    
    # Create Razorpay order
    order = razorpay_client.order.create({
        "amount": int(amount * 100),  # Convert to paise
        "currency": "INR",
        "payment_capture": 1,
        "notes": {
            "user_id": user["id"],
            "user_email": user["email"],
            "plan_id": plan_id,
            "plan_name": plan_info.get("name", ""),
            "type": "dashboard_subscription"
        }
    })
    
    # Store order info
    order_obj = {
        "id": str(uuid.uuid4()),
        "razorpay_order_id": order["id"],
        "user_id": user["id"],
        "user_email": user["email"],
        "plan_id": plan_id,
        "plan_name": plan_info.get("name", ""),
        "amount": amount,
        "status": "created",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.dashboard_orders.insert_one(order_obj)
    
    return {
        "order_id": order["id"],
        "amount": amount,
        "currency": "INR",
        "key_id": RAZORPAY_KEY_ID
    }

@api_router.post("/dashboard-subscription/verify-payment")
async def verify_dashboard_razorpay_payment(data: dict, user = Depends(get_current_user)):
    """Verify Razorpay payment for dashboard subscription"""
    if not razorpay_client:
        raise HTTPException(status_code=400, detail="Razorpay not configured")
    
    try:
        # Verify signature
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Payment verification failed")
    
    # Get order
    order = await db.dashboard_orders.find_one({"razorpay_order_id": data['razorpay_order_id']}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Update order status
    await db.dashboard_orders.update_one(
        {"razorpay_order_id": data['razorpay_order_id']},
        {"$set": {"status": "paid", "razorpay_payment_id": data['razorpay_payment_id']}}
    )
    
    # Activate subscription
    plan_id = order["plan_id"]
    plans = await get_dashboard_plans_from_db()
    plan_info = next((p for p in plans if p["id"] == plan_id), None)
    
    if plan_info:
        duration_days = plan_info.get("duration_days", 30)
        end_date = datetime.now(timezone.utc) + timedelta(days=duration_days)
        
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {
                "dashboard_plan": plan_id,
                "dashboard_subscription_status": "active",
                "dashboard_subscription_end": end_date.isoformat()
            }}
        )
        
        # Update localStorage user data
        return {
            "message": "Payment verified and subscription activated!",
            "subscription": {
                "plan": plan_id,
                "plan_name": plan_info.get("name", ""),
                "status": "active",
                "end_date": end_date.isoformat()
            }
        }
    
    return {"message": "Payment verified but plan not found"}

@api_router.get("/auth/check-admin")
async def check_if_admin(user = Depends(get_current_user)):
    """Check if current user is admin (first registered user)"""
    first_user = await db.users.find_one({}, {"_id": 0}, sort=[("created_at", 1)])
    is_admin = first_user and first_user["id"] == user["id"]
    return {"is_admin": is_admin}

@api_router.get("/dashboard-subscription/requests")
async def get_subscription_requests(user = Depends(get_current_user)):
    """Get all subscription requests (admin only - first user is admin)"""
    # Check if first user (admin)
    first_user = await db.users.find_one({}, {"_id": 0}, sort=[("created_at", 1)])
    if not first_user or first_user["id"] != user["id"]:
        # Only show own requests
        requests = await db.dashboard_subscriptions.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
    else:
        # Admin sees all
        requests = await db.dashboard_subscriptions.find({}, {"_id": 0}).to_list(100)
    
    return requests

# Super Admin email
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"

async def verify_super_admin(user: dict):
    """Verify if user is super admin"""
    if user.get("email") != SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Super Admin access required")
    return True

# ============== SUPER ADMIN ROUTES ==============

@api_router.get("/admin/all-users")
async def get_all_users(user = Depends(get_current_user)):
    """Get all users with their subscription details (super admin only)"""
    await verify_super_admin(user)
    
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return users

@api_router.get("/admin/stats")
async def get_admin_stats(user = Depends(get_current_user)):
    """Get dashboard stats for super admin"""
    await verify_super_admin(user)
    
    total_users = await db.users.count_documents({})
    active_subscribers = await db.users.count_documents({"dashboard_subscription_status": "active"})
    pending_requests = await db.dashboard_subscriptions.count_documents({"status": "pending"})
    
    # Calculate revenue from approved subscriptions
    approved_subs = await db.dashboard_subscriptions.find({"status": "approved"}, {"_id": 0}).to_list(10000)
    total_revenue = sum(sub.get("amount", 0) for sub in approved_subs)
    
    return {
        "total_users": total_users,
        "active_subscribers": active_subscribers,
        "pending_requests": pending_requests,
        "total_revenue": total_revenue
    }

@api_router.get("/admin/subscription-requests")
async def get_all_subscription_requests(user = Depends(get_current_user)):
    """Get all subscription requests (super admin only)"""
    await verify_super_admin(user)
    
    requests = await db.dashboard_subscriptions.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return requests

@api_router.put("/admin/reject-subscription/{request_id}")
async def reject_subscription_request(request_id: str, user = Depends(get_current_user)):
    """Reject subscription request (super admin only)"""
    await verify_super_admin(user)
    
    request = await db.dashboard_subscriptions.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    await db.dashboard_subscriptions.update_one(
        {"id": request_id},
        {"$set": {"status": "rejected", "rejected_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": "Subscription request rejected"}

@api_router.put("/admin/set-lifetime/{user_id}")
async def set_user_lifetime(user_id: str, user = Depends(get_current_user)):
    """Grant lifetime access to a user (super admin only)"""
    await verify_super_admin(user)
    
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Set lifetime - 100 years from now
    lifetime_end = datetime.now(timezone.utc) + timedelta(days=36500)
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "dashboard_plan": "lifetime",
            "dashboard_subscription_status": "active",
            "dashboard_subscription_end": lifetime_end.isoformat()
        }}
    )
    
    return {"message": "Lifetime access granted"}

@api_router.put("/admin/revoke-access/{user_id}")
async def revoke_user_access(user_id: str, user = Depends(get_current_user)):
    """Revoke user's dashboard access (super admin only)"""
    await verify_super_admin(user)
    
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Don't allow revoking super admin's own access
    if target_user.get("email") == SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=400, detail="Cannot revoke super admin's access")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "dashboard_subscription_status": "inactive",
            "dashboard_plan": ""
        }}
    )
    
    return {"message": "Access revoked"}

@api_router.put("/admin/make-admin/{user_id}")
async def make_user_admin(user_id: str, user = Depends(get_current_user)):
    """Make a user an admin (super admin only)"""
    await verify_super_admin(user)
    
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Can't change super admin's status
    if target_user.get("email") == SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=400, detail="Cannot modify super admin")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_admin": True}}
    )
    
    return {"message": "User is now an admin"}

@api_router.put("/admin/remove-admin/{user_id}")
async def remove_user_admin(user_id: str, user = Depends(get_current_user)):
    """Remove admin status from a user (super admin only)"""
    await verify_super_admin(user)
    
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Can't change super admin's status
    if target_user.get("email") == SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=400, detail="Cannot modify super admin")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_admin": False}}
    )
    
    return {"message": "Admin status removed"}

@api_router.put("/admin/change-subscription/{user_id}")
async def change_user_subscription(user_id: str, data: dict, user = Depends(get_current_user)):
    """Change a user's subscription plan (super admin only)"""
    await verify_super_admin(user)
    
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    plan_id = data.get("plan_id")
    if plan_id not in DASHBOARD_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    plan_info = DASHBOARD_PLANS.get(plan_id, {})
    days = plan_info.get("days", 30)
    end_date = datetime.now(timezone.utc) + timedelta(days=days)
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "dashboard_plan": plan_id,
            "dashboard_subscription_status": "active",
            "dashboard_subscription_end": end_date.isoformat()
        }}
    )
    
    return {"message": f"Subscription changed to {plan_info.get('name', plan_id)}"}

@api_router.put("/dashboard-subscription/approve/{request_id}")
async def approve_subscription(request_id: str, user = Depends(get_current_user)):
    """Approve subscription request (admin only)"""
    # Check if admin (first user) or super admin
    first_user = await db.users.find_one({}, {"_id": 0}, sort=[("created_at", 1)])
    is_first_user = first_user and first_user["id"] == user["id"]
    is_super_admin = user.get("email") == SUPER_ADMIN_EMAIL
    
    if not is_first_user and not is_super_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    request = await db.dashboard_subscriptions.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    plan_id = request["plan_id"]
    plan_info = DASHBOARD_PLANS.get(plan_id, {})
    days = plan_info.get("days", 30)
    
    end_date = datetime.now(timezone.utc) + timedelta(days=days)
    
    # Update user subscription
    await db.users.update_one(
        {"id": request["user_id"]},
        {"$set": {
            "dashboard_plan": plan_id,
            "dashboard_subscription_status": "active",
            "dashboard_subscription_end": end_date.isoformat()
        }}
    )
    
    # Update request status
    await db.dashboard_subscriptions.update_one(
        {"id": request_id},
        {"$set": {"status": "approved", "approved_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": "Subscription approved"}

# ============== PLANS ROUTES ==============

@api_router.get("/plans", response_model=List[SubscriptionPlan])
async def get_plans(user = Depends(get_current_user)):
    plans = await db.plans.find({}, {"_id": 0}).to_list(100)
    for plan in plans:
        if isinstance(plan.get('created_at'), str):
            plan['created_at'] = datetime.fromisoformat(plan['created_at'])
    return plans

@api_router.get("/plans/active", response_model=List[SubscriptionPlan])
async def get_active_plans():
    plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(100)
    for plan in plans:
        if isinstance(plan.get('created_at'), str):
            plan['created_at'] = datetime.fromisoformat(plan['created_at'])
    return plans

@api_router.post("/plans", response_model=SubscriptionPlan)
async def create_plan(plan: SubscriptionPlanCreate, user = Depends(get_current_user)):
    plan_obj = SubscriptionPlan(**plan.model_dump())
    doc = plan_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.plans.insert_one(doc)
    return plan_obj

@api_router.put("/plans/{plan_id}", response_model=SubscriptionPlan)
async def update_plan(plan_id: str, plan: SubscriptionPlanCreate, user = Depends(get_current_user)):
    existing = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    await db.plans.update_one({"id": plan_id}, {"$set": plan.model_dump()})
    updated = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return updated

@api_router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str, user = Depends(get_current_user)):
    result = await db.plans.delete_one({"id": plan_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"message": "Plan deleted"}

# ============== SUBSCRIBERS ROUTES ==============

@api_router.get("/subscribers", response_model=List[Subscriber])
async def get_subscribers(status: Optional[str] = None, user = Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    subscribers = await db.subscribers.find(query, {"_id": 0}).to_list(1000)
    for sub in subscribers:
        for field in ['start_date', 'end_date', 'grace_end_date', 'created_at']:
            if isinstance(sub.get(field), str):
                sub[field] = datetime.fromisoformat(sub[field])
    return subscribers

@api_router.post("/subscribers", response_model=Subscriber)
async def create_subscriber(subscriber: SubscriberCreate, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    plan = await db.plans.find_one({"id": subscriber.plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    grace_days = settings.get("grace_period_days", 2)
    
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=plan["duration_days"])
    grace_end_date = end_date + timedelta(days=grace_days)
    
    sub_obj = Subscriber(
        telegram_user_id=subscriber.telegram_user_id,
        telegram_username=subscriber.telegram_username,
        plan_id=subscriber.plan_id,
        plan_name=plan["name"],
        payment_method=subscriber.payment_method,
        payment_id=subscriber.payment_id,
        start_date=start_date,
        end_date=end_date,
        grace_end_date=grace_end_date
    )
    
    doc = sub_obj.model_dump()
    for field in ['start_date', 'end_date', 'grace_end_date', 'created_at']:
        if doc.get(field):
            doc[field] = doc[field].isoformat()
    
    await db.subscribers.insert_one(doc)
    
    # Send welcome message and channel invite (use plan's channel if set)
    plan_channel = plan.get("channel_id", "")
    background_tasks.add_task(add_to_channel, subscriber.telegram_user_id, plan_channel, plan["name"])
    
    website_link = settings.get("website_link", "")
    if website_link:
        background_tasks.add_task(send_telegram_message, subscriber.telegram_user_id, 
            f"🌟 Check out our services: {website_link}")
    
    return sub_obj

@api_router.put("/subscribers/{subscriber_id}/renew")
async def renew_subscriber(subscriber_id: str, plan_id: str, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    subscriber = await db.subscribers.find_one({"id": subscriber_id}, {"_id": 0})
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    grace_days = settings.get("grace_period_days", 2)
    
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=plan["duration_days"])
    grace_end_date = end_date + timedelta(days=grace_days)
    
    await db.subscribers.update_one(
        {"id": subscriber_id},
        {"$set": {
            "plan_id": plan_id,
            "plan_name": plan["name"],
            "status": "active",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "grace_end_date": grace_end_date.isoformat(),
            "reminder_sent": False
        }}
    )
    
    # Send renewal notification with channel invite
    plan_channel = plan.get("channel_id", "")
    background_tasks.add_task(send_renewal_notification, subscriber["telegram_user_id"], plan, plan_channel, end_date)
    
    return {"message": "Subscription renewed"}

async def send_renewal_notification(user_id: str, plan: dict, plan_channel: str, end_date: datetime):
    """Send renewal notification with channel invite"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    msg = f"🎉 <b>Subscription Renewed!</b>\n\n"
    msg += f"📦 Plan: <b>{plan['name']}</b>\n"
    msg += f"⏱ Duration: <b>{plan['duration_days']} days</b>\n"
    msg += f"📅 Valid till: <b>{end_date.strftime('%d %b %Y')}</b>\n\n"
    msg += "Thank you for continuing with us! 🙏"
    
    await send_telegram_message(user_id, msg, bot_token)
    
    # Send new channel invite
    await add_to_channel(user_id, plan_channel, plan['name'])

@api_router.delete("/subscribers/{subscriber_id}")
async def delete_subscriber(subscriber_id: str, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    subscriber = await db.subscribers.find_one({"id": subscriber_id}, {"_id": 0})
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    # Get plan to find channel
    plan = await db.plans.find_one({"id": subscriber.get("plan_id")}, {"_id": 0})
    plan_channel = plan.get("channel_id", "") if plan else ""
    
    await db.subscribers.delete_one({"id": subscriber_id})
    background_tasks.add_task(remove_from_channel, subscriber["telegram_user_id"], plan_channel)
    
    return {"message": "Subscriber removed"}


# ============== CHAT GROUPS POOL ROUTES ==============

class AddChatGroupRequest(BaseModel):
    group_id: str
    group_name: str = ""

@api_router.get("/chat-groups")
async def get_chat_groups(user = Depends(get_current_user)):
    """Get all chat groups in the pool"""
    groups = await db.chat_groups_pool.find({}, {"_id": 0}).to_list(100)
    return groups

@api_router.post("/chat-groups")
async def add_chat_group(request: AddChatGroupRequest, user = Depends(get_current_user)):
    """Add a group to the chat pool"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    # Verify bot is admin in the group
    try:
        async with httpx.AsyncClient() as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/getChatAdministrators?chat_id={request.group_id}"
            response = await http_client.get(url)
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Bot is not admin in this group or group doesn't exist")
            
            admins = response.json().get("result", [])
            bot_is_admin = False
            for admin in admins:
                if admin.get("user", {}).get("is_bot"):
                    bot_is_admin = True
                    break
            
            if not bot_is_admin:
                raise HTTPException(status_code=400, detail="Bot must be admin in this group")
            
            # Get group info
            info_url = f"https://api.telegram.org/bot{bot_token}/getChat?chat_id={request.group_id}"
            info_response = await http_client.get(info_url)
            group_name = request.group_name
            if info_response.status_code == 200:
                group_name = info_response.json().get("result", {}).get("title", group_name)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying group: {e}")
        raise HTTPException(status_code=400, detail=f"Error verifying group: {str(e)}")
    
    # Check if group already in pool
    existing = await db.chat_groups_pool.find_one({"group_id": request.group_id})
    if existing:
        raise HTTPException(status_code=400, detail="Group already in pool")
    
    # Add to pool
    group_doc = {
        "id": str(uuid.uuid4()),
        "group_id": request.group_id,
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

@api_router.delete("/chat-groups/{group_id}")
async def remove_chat_group(group_id: str, user = Depends(get_current_user)):
    """Remove a group from the pool"""
    result = await db.chat_groups_pool.delete_one({"group_id": group_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Group not found in pool")
    return {"message": "Group removed from pool"}

@api_router.get("/chat-sessions")
async def get_chat_sessions(status: Optional[str] = None, user = Depends(get_current_user)):
    """Get all chat sessions"""
    query = {}
    if status:
        query["status"] = status
    sessions = await db.chat_sessions.find(query, {"_id": 0}).to_list(100)
    return sessions

@api_router.post("/chat-groups/{group_id}/release")
async def force_release_group(group_id: str, user = Depends(get_current_user)):
    """Force release a group back to pool"""
    group = await db.chat_groups_pool.find_one({"group_id": group_id}, {"_id": 0})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    await release_chat_group(group_id)
    return {"message": "Group released"}


# ============== PAYMENTS ROUTES ==============

@api_router.get("/payments")
async def get_payments(status: Optional[str] = None, user = Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    # Sort by created_at descending (newest first)
    payments = await db.payments.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    for p in payments:
        if isinstance(p.get('created_at'), str):
            p['created_at'] = datetime.fromisoformat(p['created_at'])
        
        # Add screenshot URL if available
        if p.get('screenshot_file_id') and bot_token:
            p['screenshot_url'] = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={p['screenshot_file_id']}"
    
    return payments

@api_router.get("/payments/{payment_id}/screenshot")
async def get_payment_screenshot(payment_id: str, user = Depends(get_current_user)):
    """Get screenshot URL for a payment"""
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if not payment.get("screenshot_file_id"):
        raise HTTPException(status_code=404, detail="No screenshot available")
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot token not configured")
    
    # Get file path from Telegram
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={payment['screenshot_file_id']}"
            response = await http_client.get(file_info_url)
            if response.status_code == 200:
                file_path = response.json().get("result", {}).get("file_path")
                if file_path:
                    download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
                    return {"screenshot_url": download_url}
    except Exception as e:
        logger.error(f"Error getting screenshot: {e}")
    
    raise HTTPException(status_code=400, detail="Could not retrieve screenshot")

@api_router.put("/payments/{payment_id}/unverify")
async def unverify_payment(payment_id: str, user = Depends(get_current_user)):
    """Unverify a payment - changes status back to pending AND kick user from channel"""
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.get("status") != "verified":
        raise HTTPException(status_code=400, detail="Payment is not verified")
    
    telegram_user_id = payment.get("telegram_user_id")
    
    # Update payment status to rejected (not just pending)
    await db.payments.update_one(
        {"id": payment_id},
        {"$set": {
            "status": "rejected",
            "unverified_at": datetime.now(timezone.utc).isoformat(),
            "unverified_by": user.get("email", "admin"),
            "rejection_reason": "Unverified by admin after review"
        }}
    )
    
    # Remove subscriber if exists
    if telegram_user_id:
        await db.subscribers.delete_one({"telegram_user_id": telegram_user_id, "plan_id": payment.get("plan_id")})
    
    # KICK USER FROM CHANNEL
    kicked = False
    if telegram_user_id:
        kicked = await kick_user_from_channel(telegram_user_id)
        logger.info(f"Kicked user {telegram_user_id} from channel: {kicked}")
        
        # Also kick from any assigned chat groups
        assigned_group = await db.chat_groups_pool.find_one(
            {"assigned_to_user_id": telegram_user_id},
            {"_id": 0}
        )
        if assigned_group:
            await kick_user_from_group(assigned_group["group_id"], telegram_user_id)
            await release_chat_group(assigned_group["group_id"])
    
    # Notify user
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if bot_token and telegram_user_id:
        msg = "❌ <b>Payment Rejected</b>\n\n"
        msg += f"Your payment for {payment.get('plan_name', 'subscription')} has been rejected after review.\n\n"
        msg += "🚫 You have been removed from the channel.\n"
        msg += "📞 Contact support if you believe this is a mistake."
        await send_telegram_message(telegram_user_id, msg, bot_token)
    
    return {
        "message": "Payment unverified and user kicked from channel",
        "user_kicked": kicked
    }


# ============== BOT CHECKOUT ROUTES ==============

@api_router.get("/bot-checkout/{order_id}")
async def get_bot_checkout(order_id: str):
    """Get order details for bot checkout page"""
    order = await db.bot_orders.find_one({"razorpay_order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    plan = await db.plans.find_one({"id": order["plan_id"]}, {"_id": 0})
    
    return {
        "order_id": order_id,
        "plan_id": order["plan_id"],
        "plan_name": order.get("plan_name", plan["name"] if plan else ""),
        "amount": order["amount"],
        "key_id": RAZORPAY_KEY_ID,
        "telegram_user_id": order.get("telegram_user_id", "")
    }

@api_router.post("/bot-checkout/verify")
async def verify_bot_checkout(data: dict, background_tasks: BackgroundTasks):
    """Verify Razorpay payment and activate subscription"""
    if not razorpay_client:
        raise HTTPException(status_code=400, detail="Razorpay not configured")
    
    try:
        # Verify signature
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })
    except Exception as e:
        logger.error(f"Payment verification failed: {e}")
        raise HTTPException(status_code=400, detail="Payment verification failed")
    
    # Get order
    order = await db.bot_orders.find_one({"razorpay_order_id": data['razorpay_order_id']}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Update order status
    await db.bot_orders.update_one(
        {"razorpay_order_id": data['razorpay_order_id']},
        {"$set": {"status": "paid", "razorpay_payment_id": data['razorpay_payment_id']}}
    )
    
    # Get plan details
    plan = await db.plans.find_one({"id": order["plan_id"]}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    telegram_user_id = data.get("telegram_user_id") or order.get("telegram_user_id")
    telegram_username = order.get("telegram_username", "")
    
    # Create payment record
    payment_obj = {
        "id": str(uuid.uuid4()),
        "subscriber_id": None,
        "telegram_user_id": telegram_user_id,
        "telegram_username": telegram_username,
        "amount": order["amount"],
        "plan_id": order["plan_id"],
        "plan_name": plan["name"],
        "payment_method": "razorpay",
        "razorpay_order_id": data['razorpay_order_id'],
        "razorpay_payment_id": data['razorpay_payment_id'],
        "status": "verified",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payments.insert_one(payment_obj)
    
    # Create subscriber
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    grace_days = settings.get("grace_period_days", 2)
    bot_token = settings.get("telegram_bot_token", "")
    
    end_date = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])
    grace_end = end_date + timedelta(days=grace_days)
    
    subscriber_obj = {
        "id": str(uuid.uuid4()),
        "telegram_user_id": telegram_user_id,
        "telegram_username": telegram_username,
        "plan_id": plan["id"],
        "plan_name": plan["name"],
        "payment_method": "razorpay",
        "payment_id": payment_obj["id"],
        "status": "active",
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": end_date.isoformat(),
        "grace_end_date": grace_end.isoformat(),
        "reminder_sent": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.subscribers.insert_one(subscriber_obj)
    
    # Add to channel
    plan_channel = plan.get("channel_id", "")
    if plan_channel and bot_token:
        background_tasks.add_task(add_to_channel, telegram_user_id, plan_channel, plan["name"])
    
    # Send success message to user
    if bot_token and telegram_user_id:
        success_msg = "🎉 <b>Payment Successful!</b>\n\n"
        success_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
        success_msg += f"💰 Amount: <b>₹{order['amount']}</b>\n"
        success_msg += f"⏱ Valid till: <b>{end_date.strftime('%d %b %Y')}</b>\n\n"
        success_msg += "✅ Your subscription is now active!\n"
        success_msg += "📢 You will receive channel invite link shortly."
        await send_telegram_message(telegram_user_id, success_msg, bot_token)
    
    logger.info(f"Bot subscription activated for user {telegram_user_id}, plan {plan['name']}")
    
    return {"success": True, "message": "Subscription activated"}

@api_router.post("/payments/create-order")
async def create_razorpay_order(payment: PaymentCreate, user = Depends(get_current_user)):
    if not razorpay_client:
        raise HTTPException(status_code=400, detail="Razorpay not configured")
    
    plan = await db.plans.find_one({"id": payment.plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    order = razorpay_client.order.create({
        "amount": int(payment.amount * 100),
        "currency": "INR",
        "payment_capture": 1
    })
    
    payment_obj = Payment(
        telegram_user_id=payment.telegram_user_id,
        amount=payment.amount,
        plan_id=payment.plan_id,
        payment_method="razorpay",
        razorpay_order_id=order["id"]
    )
    
    doc = payment_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.payments.insert_one(doc)
    
    return {"order_id": order["id"], "payment_id": payment_obj.id, "key_id": RAZORPAY_KEY_ID}

@api_router.post("/payments/verify")
async def verify_razorpay_payment(data: dict, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    if not razorpay_client:
        raise HTTPException(status_code=400, detail="Razorpay not configured")
    
    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Payment verification failed")
    
    payment = await db.payments.find_one({"razorpay_order_id": data['razorpay_order_id']}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    await db.payments.update_one(
        {"razorpay_order_id": data['razorpay_order_id']},
        {"$set": {"status": "verified", "razorpay_payment_id": data['razorpay_payment_id']}}
    )
    
    # Create subscriber
    plan = await db.plans.find_one({"id": payment["plan_id"]}, {"_id": 0})
    if plan:
        subscriber_create = SubscriberCreate(
            telegram_user_id=payment["telegram_user_id"],
            plan_id=payment["plan_id"],
            payment_method="razorpay",
            payment_id=payment["id"]
        )
        await create_subscriber(subscriber_create, background_tasks)
    
    return {"message": "Payment verified"}

@api_router.post("/payments/manual")
async def create_manual_payment(payment: PaymentCreate, user = Depends(get_current_user)):
    plan = await db.plans.find_one({"id": payment.plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    payment_obj = Payment(
        telegram_user_id=payment.telegram_user_id,
        amount=payment.amount,
        plan_id=payment.plan_id,
        payment_method="manual"
    )
    
    doc = payment_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.payments.insert_one(doc)
    
    return {"payment_id": payment_obj.id, "message": "Manual payment created, waiting for verification"}

@api_router.put("/payments/{payment_id}/verify-manual")
async def verify_manual_payment(payment_id: str, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    await db.payments.update_one({"id": payment_id}, {"$set": {"status": "verified"}})
    
    # Create subscriber
    plan = await db.plans.find_one({"id": payment["plan_id"]}, {"_id": 0})
    if plan:
        subscriber_create = SubscriberCreate(
            telegram_user_id=payment["telegram_user_id"],
            plan_id=payment["plan_id"],
            payment_method="manual",
            payment_id=payment["id"]
        )
        await create_subscriber(subscriber_create, background_tasks)
    
    return {"message": "Payment verified and subscriber created"}

@api_router.put("/payments/{payment_id}/reject")
async def reject_payment(payment_id: str, data: dict = None, user = Depends(get_current_user)):
    """Reject a payment"""
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Can reject pending or verified payments
    if payment.get("status") == "rejected":
        raise HTTPException(status_code=400, detail="Payment is already rejected")
    
    reason = data.get("reason", "Payment rejected by admin") if data else "Payment rejected by admin"
    
    await db.payments.update_one(
        {"id": payment_id}, 
        {"$set": {"status": "rejected", "rejection_reason": reason, "rejected_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Optionally notify user via Telegram
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if bot_token and payment.get("telegram_user_id"):
        msg = f"❌ <b>Payment Rejected</b>\n\n"
        msg += f"📦 Plan: {payment.get('plan_name', 'N/A')}\n"
        msg += f"💰 Amount: ₹{payment.get('amount', 0)}\n\n"
        msg += f"📝 Reason: {reason}\n\n"
        msg += "Please contact support if you believe this is an error."
        await send_telegram_message(payment["telegram_user_id"], msg, bot_token)
    
    return {"message": "Payment rejected"}

@api_router.delete("/payments/{payment_id}")
async def delete_payment(payment_id: str, user = Depends(get_current_user)):
    """Delete a payment record - Admin only"""
    # Check if user is admin
    if user.get("email") != SUPER_ADMIN_EMAIL and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Only admin can delete payments")
    
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    await db.payments.delete_one({"id": payment_id})
    return {"message": "Payment deleted"}

@api_router.post("/payments/bulk-verify")
async def bulk_verify_payments(data: dict, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    """Verify multiple payments at once"""
    payment_ids = data.get("payment_ids", [])
    if not payment_ids:
        raise HTTPException(status_code=400, detail="No payment IDs provided")
    
    verified_count = 0
    for payment_id in payment_ids:
        payment = await db.payments.find_one({"id": payment_id, "status": "pending"}, {"_id": 0})
        if payment:
            await db.payments.update_one({"id": payment_id}, {"$set": {"status": "verified"}})
            
            # Create subscriber
            plan = await db.plans.find_one({"id": payment["plan_id"]}, {"_id": 0})
            if plan:
                subscriber_create = SubscriberCreate(
                    telegram_user_id=payment["telegram_user_id"],
                    telegram_username=payment.get("telegram_username"),
                    plan_id=payment["plan_id"],
                    payment_method=payment.get("payment_method", "manual"),
                    payment_id=payment["id"]
                )
                background_tasks.add_task(create_subscriber_task, subscriber_create, plan)
            verified_count += 1
    
    return {"message": f"{verified_count} payments verified", "verified_count": verified_count}

@api_router.post("/payments/bulk-reject")
async def bulk_reject_payments(data: dict, user = Depends(get_current_user)):
    """Reject multiple payments at once"""
    payment_ids = data.get("payment_ids", [])
    reason = data.get("reason", "Payment rejected by admin")
    if not payment_ids:
        raise HTTPException(status_code=400, detail="No payment IDs provided")
    
    rejected_count = 0
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    for payment_id in payment_ids:
        payment = await db.payments.find_one({"id": payment_id, "status": "pending"}, {"_id": 0})
        if payment:
            await db.payments.update_one(
                {"id": payment_id}, 
                {"$set": {"status": "rejected", "rejection_reason": reason, "rejected_at": datetime.now(timezone.utc).isoformat()}}
            )
            
            # Notify user via Telegram
            if bot_token and payment.get("telegram_user_id"):
                msg = f"❌ <b>Payment Rejected</b>\n\n"
                msg += f"📦 Plan: {payment.get('plan_name', 'N/A')}\n"
                msg += f"💰 Amount: ₹{payment.get('amount', 0)}\n\n"
                msg += f"📝 Reason: {reason}"
                await send_telegram_message(payment["telegram_user_id"], msg, bot_token)
            rejected_count += 1
    
    return {"message": f"{rejected_count} payments rejected", "rejected_count": rejected_count}

@api_router.post("/payments/bulk-delete")
async def bulk_delete_payments(data: dict, user = Depends(get_current_user)):
    """Delete multiple payments at once - Admin only"""
    # Check if user is admin
    if user.get("email") != SUPER_ADMIN_EMAIL and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Only admin can delete payments")
    
    payment_ids = data.get("payment_ids", [])
    if not payment_ids:
        raise HTTPException(status_code=400, detail="No payment IDs provided")
    
    result = await db.payments.delete_many({"id": {"$in": payment_ids}})
    return {"message": f"{result.deleted_count} payments deleted", "deleted_count": result.deleted_count}

async def create_subscriber_task(subscriber_create: SubscriberCreate, plan: dict):
    """Background task to create subscriber after payment verification"""
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    grace_days = settings.get("grace_period_days", 2)
    plan_channel = plan.get("channel_id", "")
    
    end_date = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])
    grace_end = end_date + timedelta(days=grace_days)
    
    subscriber_obj = Subscriber(
        telegram_user_id=subscriber_create.telegram_user_id,
        telegram_username=subscriber_create.telegram_username,
        plan_id=subscriber_create.plan_id,
        plan_name=plan["name"],
        payment_method=subscriber_create.payment_method,
        payment_id=subscriber_create.payment_id,
        end_date=end_date,
        grace_end_date=grace_end
    )
    
    doc = subscriber_obj.model_dump()
    doc['start_date'] = doc['start_date'].isoformat()
    doc['end_date'] = doc['end_date'].isoformat()
    doc['grace_end_date'] = doc['grace_end_date'].isoformat()
    doc['created_at'] = doc['created_at'].isoformat()
    
    await db.subscribers.insert_one(doc)
    await add_to_channel(subscriber_create.telegram_user_id, plan_channel, plan["name"])

# ============== SETTINGS ROUTES ==============

@api_router.get("/settings")
async def get_settings(user = Depends(get_current_user)):
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0})
    if not settings:
        settings = BotSettings().model_dump()
    return settings

@api_router.put("/settings")
async def update_settings(settings: BotSettings, user = Depends(get_current_user)):
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
    
    doc = settings.model_dump()
    await db.settings.update_one({"id": "bot_settings"}, {"$set": doc}, upsert=True)
    
    TELEGRAM_BOT_TOKEN = settings.telegram_bot_token
    TELEGRAM_CHANNEL_ID = settings.telegram_channel_id
    
    return {"message": "Settings updated"}

# ============== FILE UPLOAD ROUTES ==============

@api_router.post("/upload/qr-code")
async def upload_qr_code(file: UploadFile = File(...), user = Depends(get_current_user)):
    """Upload QR code image"""
    # Validate file type
    allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only image files are allowed (PNG, JPG, WEBP, GIF)")
    
    # Validate file size (max 5MB)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be less than 5MB")
    
    # Generate unique filename
    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    filename = f"qr_code_{uuid.uuid4().hex[:8]}.{ext}"
    
    # Save file
    import os as os_mod
    uploads_path = os_mod.path.join(os_mod.path.dirname(__file__), "uploads")
    os_mod.makedirs(uploads_path, exist_ok=True)
    file_path = os_mod.path.join(uploads_path, filename)
    
    with open(file_path, "wb") as f:
        f.write(contents)
    
    # Return the URL - use REACT_APP_BACKEND_URL from environment or construct it
    base_url = os.environ.get("BACKEND_URL", "")
    if not base_url:
        # Fallback to constructing URL
        base_url = os.environ.get("REACT_APP_BACKEND_URL", "").replace("/api", "")
    
    file_url = f"/uploads/{filename}"
    
    return {"url": file_url, "filename": filename}

@api_router.post("/upload/image")
async def upload_image(file: UploadFile = File(...), user = Depends(get_current_user)):
    """Upload general image"""
    # Validate file type
    allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    
    # Validate file size (max 10MB)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")
    
    # Generate unique filename
    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    filename = f"img_{uuid.uuid4().hex[:8]}.{ext}"
    
    # Save file
    import os as os_mod
    uploads_path = os_mod.path.join(os_mod.path.dirname(__file__), "uploads")
    os_mod.makedirs(uploads_path, exist_ok=True)
    file_path = os_mod.path.join(uploads_path, filename)
    
    with open(file_path, "wb") as f:
        f.write(contents)
    
    file_url = f"/uploads/{filename}"
    
    return {"url": file_url, "filename": filename}

# ============== ANALYTICS ROUTES ==============

@api_router.get("/analytics")
async def get_analytics(user = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    
    total_subscribers = await db.subscribers.count_documents({})
    active_subscribers = await db.subscribers.count_documents({"status": "active"})
    expired_subscribers = await db.subscribers.count_documents({"status": "expired"})
    grace_subscribers = await db.subscribers.count_documents({"status": "grace"})
    
    # Revenue calculation
    verified_payments = await db.payments.find({"status": "verified"}, {"_id": 0}).to_list(10000)
    total_revenue = sum(p.get("amount", 0) for p in verified_payments)
    
    # This month's revenue
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_payments = [p for p in verified_payments 
                       if datetime.fromisoformat(p["created_at"]) >= month_start]
    monthly_revenue = sum(p.get("amount", 0) for p in monthly_payments)
    
    # Recent activity
    recent_subscribers = await db.subscribers.find({}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
    recent_payments = await db.payments.find({}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
    
    # Plans stats
    plans = await db.plans.find({}, {"_id": 0}).to_list(100)
    plan_stats = []
    for plan in plans:
        count = await db.subscribers.count_documents({"plan_id": plan["id"], "status": "active"})
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

# ============== MESSAGE TEMPLATES ROUTES ==============

@api_router.get("/templates")
async def get_templates(user = Depends(get_current_user)):
    templates = await db.templates.find({}, {"_id": 0}).to_list(100)
    return templates

@api_router.post("/templates")
async def create_template(template: MessageTemplate, user = Depends(get_current_user)):
    doc = template.model_dump()
    await db.templates.insert_one(doc)
    return template

@api_router.put("/templates/{template_id}")
async def update_template(template_id: str, template: MessageTemplate, user = Depends(get_current_user)):
    doc = template.model_dump()
    doc["id"] = template_id
    await db.templates.update_one({"id": template_id}, {"$set": doc}, upsert=True)
    return {"message": "Template updated"}

@api_router.delete("/templates/{template_id}")
async def delete_template(template_id: str, user = Depends(get_current_user)):
    await db.templates.delete_one({"id": template_id})
    return {"message": "Template deleted"}

# ============== BROADCAST ROUTES ==============

class BroadcastRequest(BaseModel):
    message: str
    target: str = "all"  # all, subscribers, channel_members
    include_button: bool = False
    button_text: str = "🔔 Subscribe Now"
    button_url: str = ""

@api_router.post("/broadcast")
async def send_broadcast(request: BroadcastRequest, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    """Send broadcast message to users"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    
    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot token not configured")
    
    # Get target users based on selection
    user_ids = set()
    
    if request.target in ["all", "subscribers"]:
        # Get all subscribers
        subscribers = await db.subscribers.find({"status": "active"}, {"_id": 0}).to_list(10000)
        for sub in subscribers:
            if sub.get("telegram_user_id"):
                user_ids.add(str(sub["telegram_user_id"]))
    
    if request.target in ["all", "channel_members"]:
        # Get users from payments (they interacted with bot)
        payments = await db.payments.find({}, {"_id": 0, "telegram_user_id": 1}).to_list(10000)
        for p in payments:
            if p.get("telegram_user_id"):
                user_ids.add(str(p["telegram_user_id"]))
        
        # Get from pending screenshots
        pending = await db.pending_screenshots.find({}, {"_id": 0, "telegram_user_id": 1}).to_list(10000)
        for p in pending:
            if p.get("telegram_user_id"):
                user_ids.add(str(p["telegram_user_id"]))
    
    if not user_ids:
        raise HTTPException(status_code=400, detail="No users found to broadcast to")
    
    # Prepare button if needed
    buttons = None
    if request.include_button and request.button_url:
        buttons = [[{"text": request.button_text, "url": request.button_url}]]
    elif request.include_button:
        bot_username = await get_bot_username(bot_token)
        buttons = [[{"text": request.button_text, "url": f"https://t.me/{bot_username}?start=subscribe"}]]
    
    # Create broadcast record
    broadcast_id = str(uuid.uuid4())
    broadcast_record = {
        "id": broadcast_id,
        "message": request.message,
        "target": request.target,
        "total_users": len(user_ids),
        "sent_count": 0,
        "failed_count": 0,
        "status": "in_progress",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("email", "")
    }
    await db.broadcasts.insert_one(broadcast_record)
    
    # Send in background
    background_tasks.add_task(
        send_broadcast_messages, 
        broadcast_id, 
        list(user_ids), 
        request.message, 
        buttons, 
        bot_token
    )
    
    return {
        "message": f"Broadcast started to {len(user_ids)} users",
        "broadcast_id": broadcast_id,
        "total_users": len(user_ids)
    }

async def send_broadcast_messages(broadcast_id: str, user_ids: list, message: str, buttons: list, bot_token: str):
    """Background task to send broadcast messages"""
    sent_count = 0
    failed_count = 0
    
    for user_id in user_ids:
        try:
            success = await send_telegram_message_with_buttons(user_id, message, buttons, bot_token)
            if success:
                sent_count += 1
            else:
                failed_count += 1
        except Exception as e:
            logger.error(f"Broadcast failed for {user_id}: {e}")
            failed_count += 1
        
        # Rate limiting - wait between messages
        await asyncio.sleep(0.1)
        
        # Update progress every 10 messages
        if (sent_count + failed_count) % 10 == 0:
            await db.broadcasts.update_one(
                {"id": broadcast_id},
                {"$set": {"sent_count": sent_count, "failed_count": failed_count}}
            )
    
    # Final update
    await db.broadcasts.update_one(
        {"id": broadcast_id},
        {"$set": {
            "sent_count": sent_count,
            "failed_count": failed_count,
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    logger.info(f"Broadcast {broadcast_id} completed: {sent_count} sent, {failed_count} failed")

@api_router.get("/broadcasts")
async def get_broadcasts(user = Depends(get_current_user)):
    """Get all broadcast history"""
    broadcasts = await db.broadcasts.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return broadcasts

@api_router.get("/broadcasts/{broadcast_id}")
async def get_broadcast(broadcast_id: str, user = Depends(get_current_user)):
    """Get broadcast status"""
    broadcast = await db.broadcasts.find_one({"id": broadcast_id}, {"_id": 0})
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    return broadcast


# ============== COUPON/DISCOUNT APIs ==============

@api_router.get("/coupons")
async def get_coupons(user = Depends(get_current_user)):
    """Get all coupons"""
    coupons = await db.coupons.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return coupons

@api_router.post("/coupons")
async def create_coupon(coupon: dict, user = Depends(get_current_user)):
    """Create a new coupon"""
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
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Check if code already exists
    existing = await db.coupons.find_one({"code": coupon_data["code"]})
    if existing:
        raise HTTPException(status_code=400, detail="Coupon code already exists")
    
    await db.coupons.insert_one(coupon_data)
    return {"message": "Coupon created", "coupon": coupon_data}

@api_router.put("/coupons/{coupon_id}")
async def update_coupon(coupon_id: str, coupon: dict, user = Depends(get_current_user)):
    """Update a coupon"""
    await db.coupons.update_one(
        {"id": coupon_id},
        {"$set": {
            "code": coupon.get("code", "").upper().strip(),
            "discount_type": coupon.get("discount_type"),
            "discount_value": float(coupon.get("discount_value", 0)),
            "min_purchase": float(coupon.get("min_purchase", 0)),
            "max_uses": int(coupon.get("max_uses", 0)),
            "valid_from": coupon.get("valid_from"),
            "valid_until": coupon.get("valid_until"),
            "applicable_plans": coupon.get("applicable_plans", []),
            "is_active": coupon.get("is_active", True)
        }}
    )
    return {"message": "Coupon updated"}

@api_router.delete("/coupons/{coupon_id}")
async def delete_coupon(coupon_id: str, user = Depends(get_current_user)):
    """Delete a coupon"""
    await db.coupons.delete_one({"id": coupon_id})
    return {"message": "Coupon deleted"}

@api_router.post("/coupons/validate")
async def validate_coupon(data: dict):
    """Validate a coupon code (public endpoint for bot)"""
    code = data.get("code", "").upper().strip()
    plan_id = data.get("plan_id")
    amount = float(data.get("amount", 0))
    
    coupon = await db.coupons.find_one({"code": code, "is_active": True}, {"_id": 0})
    if not coupon:
        return {"valid": False, "error": "Invalid coupon code"}
    
    # Check expiry
    if coupon.get("valid_until"):
        expiry = datetime.fromisoformat(coupon["valid_until"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expiry:
            return {"valid": False, "error": "Coupon expired"}
    
    # Check usage limit
    if coupon.get("max_uses", 0) > 0 and coupon.get("used_count", 0) >= coupon["max_uses"]:
        return {"valid": False, "error": "Coupon usage limit reached"}
    
    # Check minimum purchase
    if amount < coupon.get("min_purchase", 0):
        return {"valid": False, "error": f"Minimum purchase ₹{coupon['min_purchase']} required"}
    
    # Check applicable plans
    if coupon.get("applicable_plans") and plan_id not in coupon["applicable_plans"]:
        return {"valid": False, "error": "Coupon not valid for this plan"}
    
    # Calculate discount
    if coupon["discount_type"] == "percentage":
        discount = (amount * coupon["discount_value"]) / 100
    else:
        discount = coupon["discount_value"]
    
    final_amount = max(0, amount - discount)
    
    return {
        "valid": True,
        "discount": discount,
        "final_amount": final_amount,
        "coupon": coupon
    }


# ============== USER NOTES APIs ==============

@api_router.get("/users/{user_id}/notes")
async def get_user_notes(user_id: str, user = Depends(get_current_user)):
    """Get notes for a user"""
    notes = await db.user_notes.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return notes

@api_router.post("/users/{user_id}/notes")
async def add_user_note(user_id: str, data: dict, user = Depends(get_current_user)):
    """Add a note to user"""
    note_data = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "note": data.get("note", ""),
        "added_by": user.get("email", "admin"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_notes.insert_one(note_data)
    return {"message": "Note added", "note": note_data}

@api_router.delete("/users/{user_id}/notes/{note_id}")
async def delete_user_note(user_id: str, note_id: str, user = Depends(get_current_user)):
    """Delete a user note"""
    await db.user_notes.delete_one({"id": note_id, "user_id": user_id})
    return {"message": "Note deleted"}


# ============== USER TAGS APIs ==============

@api_router.get("/tags")
async def get_tags(user = Depends(get_current_user)):
    """Get all tags"""
    tags = await db.user_tags.find({}, {"_id": 0}).to_list(100)
    return tags

@api_router.post("/tags")
async def create_tag(data: dict, user = Depends(get_current_user)):
    """Create a new tag"""
    tag_data = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", ""),
        "color": data.get("color", "blue"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_tags.insert_one(tag_data)
    return {"message": "Tag created", "tag": tag_data}

@api_router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: str, user = Depends(get_current_user)):
    """Delete a tag"""
    await db.user_tags.delete_one({"id": tag_id})
    # Remove tag from all users
    await db.bot_users.update_many({}, {"$pull": {"tags": tag_id}})
    return {"message": "Tag deleted"}

@api_router.post("/users/{user_id}/tags")
async def add_tag_to_user(user_id: str, data: dict, user = Depends(get_current_user)):
    """Add tag to user"""
    tag_id = data.get("tag_id")
    await db.bot_users.update_one(
        {"telegram_user_id": user_id},
        {"$addToSet": {"tags": tag_id}}
    )
    return {"message": "Tag added to user"}

@api_router.delete("/users/{user_id}/tags/{tag_id}")
async def remove_tag_from_user(user_id: str, tag_id: str, user = Depends(get_current_user)):
    """Remove tag from user"""
    await db.bot_users.update_one(
        {"telegram_user_id": user_id},
        {"$pull": {"tags": tag_id}}
    )
    return {"message": "Tag removed from user"}


# ============== BLOCKED USERS APIs ==============

@api_router.get("/blocked-users")
async def get_blocked_users(user = Depends(get_current_user)):
    """Get all blocked users"""
    blocked = await db.blocked_users.find({}, {"_id": 0}).sort("blocked_at", -1).to_list(1000)
    return blocked

@api_router.post("/users/{user_id}/block")
async def block_user(user_id: str, data: dict, user = Depends(get_current_user)):
    """Block a user"""
    # Check if already blocked
    existing = await db.blocked_users.find_one({"telegram_user_id": user_id})
    if existing:
        raise HTTPException(status_code=400, detail="User already blocked")
    
    # Get user info
    bot_user = await db.bot_users.find_one({"telegram_user_id": user_id}, {"_id": 0})
    
    blocked_data = {
        "id": str(uuid.uuid4()),
        "telegram_user_id": user_id,
        "telegram_username": bot_user.get("username", "") if bot_user else "",
        "reason": data.get("reason", ""),
        "blocked_by": user.get("email", "admin"),
        "blocked_at": datetime.now(timezone.utc).isoformat()
    }
    await db.blocked_users.insert_one(blocked_data)
    return {"message": "User blocked", "blocked": blocked_data}

@api_router.delete("/users/{user_id}/block")
async def unblock_user(user_id: str, user = Depends(get_current_user)):
    """Unblock a user"""
    await db.blocked_users.delete_one({"telegram_user_id": user_id})
    return {"message": "User unblocked"}


# ============== REFERRAL APIs ==============

@api_router.get("/referrals")
async def get_referrals(user = Depends(get_current_user)):
    """Get all referrals"""
    referrals = await db.referrals.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return referrals

@api_router.get("/referrals/settings")
async def get_referral_settings(user = Depends(get_current_user)):
    """Get referral program settings"""
    settings = await db.referral_settings.find_one({"id": "referral_settings"}, {"_id": 0})
    if not settings:
        settings = {
            "id": "referral_settings",
            "enabled": True,
            "referrer_reward_type": "discount",
            "referrer_reward_value": 10,
            "referee_reward_type": "discount",
            "referee_reward_value": 10
        }
        await db.referral_settings.insert_one(settings)
    return settings

@api_router.put("/referrals/settings")
async def update_referral_settings(data: dict, user = Depends(get_current_user)):
    """Update referral program settings"""
    await db.referral_settings.update_one(
        {"id": "referral_settings"},
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

@api_router.post("/referrals/validate")
async def validate_referral(data: dict):
    """Validate a referral code (public endpoint for bot)"""
    code = data.get("code", "").upper().strip()
    user_id = data.get("user_id")
    
    referral = await db.referrals.find_one({"referral_code": code, "is_active": True}, {"_id": 0})
    if not referral:
        return {"valid": False, "error": "Invalid referral code"}
    
    # Can't use own referral code
    if referral["referrer_id"] == user_id:
        return {"valid": False, "error": "Can't use your own referral code"}
    
    # Check if user already used a referral
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


# ============== SCHEDULED BROADCAST APIs ==============

@api_router.get("/scheduled-broadcasts")
async def get_scheduled_broadcasts(user = Depends(get_current_user)):
    """Get all scheduled broadcasts"""
    broadcasts = await db.scheduled_broadcasts.find({}, {"_id": 0}).sort("scheduled_at", 1).to_list(1000)
    return broadcasts

@api_router.post("/scheduled-broadcasts")
async def create_scheduled_broadcast(data: dict, user = Depends(get_current_user)):
    """Create a scheduled broadcast"""
    broadcast_data = {
        "id": str(uuid.uuid4()),
        "message": data.get("message", ""),
        "target_segment": data.get("target_segment", "all"),
        "scheduled_at": data.get("scheduled_at"),
        "status": "pending",
        "sent_count": 0,
        "created_by": user.get("email", "admin"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.scheduled_broadcasts.insert_one(broadcast_data)
    return {"message": "Broadcast scheduled", "broadcast": broadcast_data}

@api_router.delete("/scheduled-broadcasts/{broadcast_id}")
async def cancel_scheduled_broadcast(broadcast_id: str, user = Depends(get_current_user)):
    """Cancel a scheduled broadcast"""
    await db.scheduled_broadcasts.update_one(
        {"id": broadcast_id},
        {"$set": {"status": "cancelled"}}
    )
    return {"message": "Broadcast cancelled"}


# ============== FAQ / AUTO-REPLY APIs ==============

@api_router.get("/faqs")
async def get_faqs(user = Depends(get_current_user)):
    """Get all FAQs"""
    faqs = await db.faqs.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return faqs

@api_router.post("/faqs")
async def create_faq(data: dict, user = Depends(get_current_user)):
    """Create a new FAQ"""
    faq_data = {
        "id": str(uuid.uuid4()),
        "keywords": [k.strip().lower() for k in data.get("keywords", "").split(",") if k.strip()],
        "response": data.get("response", ""),
        "is_active": data.get("is_active", True),
        "usage_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.faqs.insert_one(faq_data)
    return {"message": "FAQ created", "faq": faq_data}

@api_router.put("/faqs/{faq_id}")
async def update_faq(faq_id: str, data: dict, user = Depends(get_current_user)):
    """Update a FAQ"""
    await db.faqs.update_one(
        {"id": faq_id},
        {"$set": {
            "keywords": [k.strip().lower() for k in data.get("keywords", "").split(",") if k.strip()],
            "response": data.get("response", ""),
            "is_active": data.get("is_active", True)
        }}
    )
    return {"message": "FAQ updated"}

@api_router.delete("/faqs/{faq_id}")
async def delete_faq(faq_id: str, user = Depends(get_current_user)):
    """Delete a FAQ"""
    await db.faqs.delete_one({"id": faq_id})
    return {"message": "FAQ deleted"}


# ============== VIDEO CALL BOOKINGS APIs ==============

@api_router.get("/video-calls")
async def get_video_call_bookings(user = Depends(get_current_user)):
    """Get all video call bookings"""
    bookings = await db.video_call_bookings.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return bookings

@api_router.put("/video-calls/{booking_id}")
async def update_video_call_booking(booking_id: str, data: dict, user = Depends(get_current_user)):
    """Update a video call booking (confirm, add meeting link, etc.)"""
    update_data = {}
    
    if "status" in data:
        update_data["status"] = data["status"]
    if "meeting_link" in data:
        update_data["meeting_link"] = data["meeting_link"]
    if "notes" in data:
        update_data["notes"] = data["notes"]
    
    if update_data:
        await db.video_call_bookings.update_one(
            {"id": booking_id},
            {"$set": update_data}
        )
        
        # If confirmed, send notification to user
        if data.get("status") == "confirmed":
            booking = await db.video_call_bookings.find_one({"id": booking_id}, {"_id": 0})
            if booking:
                settings = await get_bot_settings()
                bot_token = settings.get("telegram_bot_token", "")
                
                msg = "✅ <b>Video Call Confirmed!</b>\n\n"
                msg += f"📅 Date: <b>{booking.get('scheduled_date')}</b>\n"
                msg += f"🕐 Time: <b>{booking.get('scheduled_time')}</b>\n"
                msg += f"⏱ Duration: <b>{booking.get('duration_minutes', 30)} minutes</b>\n"
                
                if data.get("meeting_link"):
                    msg += f"\n🔗 Meeting Link:\n{data['meeting_link']}"
                
                await send_telegram_message(booking.get("telegram_user_id"), msg, bot_token)
    
    return {"message": "Booking updated"}

@api_router.delete("/video-calls/{booking_id}")
async def delete_video_call_booking(booking_id: str, user = Depends(get_current_user)):
    """Delete a video call booking"""
    await db.video_call_bookings.delete_one({"id": booking_id})
    return {"message": "Booking deleted"}


# ============== ANALYTICS / EXPORT APIs ==============

@api_router.get("/analytics/revenue")
async def get_revenue_analytics(user = Depends(get_current_user)):
    """Get revenue analytics"""
    # Get payments from last 30 days
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    
    payments = await db.payments.find(
        {"status": "verified"},
        {"_id": 0, "amount": 1, "created_at": 1}
    ).to_list(10000)
    
    # Calculate totals
    total_revenue = sum(p.get("amount", 0) for p in payments)
    
    # Group by date for chart
    daily_revenue = {}
    for p in payments:
        date = p.get("created_at", "")[:10]  # Get YYYY-MM-DD
        if date:
            daily_revenue[date] = daily_revenue.get(date, 0) + p.get("amount", 0)
    
    # Last 30 days data
    chart_data = []
    for i in range(30):
        date = (datetime.now(timezone.utc) - timedelta(days=29-i)).strftime("%Y-%m-%d")
        chart_data.append({
            "date": date,
            "revenue": daily_revenue.get(date, 0)
        })
    
    return {
        "total_revenue": total_revenue,
        "total_payments": len(payments),
        "chart_data": chart_data
    }

@api_router.get("/analytics/users")
async def get_user_analytics(user = Depends(get_current_user)):
    """Get user growth analytics"""
    users = await db.bot_users.find({}, {"_id": 0, "created_at": 1}).to_list(100000)
    
    # Group by date
    daily_users = {}
    for u in users:
        date = str(u.get("created_at", ""))[:10]
        if date:
            daily_users[date] = daily_users.get(date, 0) + 1
    
    # Last 30 days data
    chart_data = []
    cumulative = 0
    for i in range(30):
        date = (datetime.now(timezone.utc) - timedelta(days=29-i)).strftime("%Y-%m-%d")
        new_users = daily_users.get(date, 0)
        cumulative += new_users
        chart_data.append({
            "date": date,
            "new_users": new_users,
            "total_users": cumulative
        })
    
    return {
        "total_users": len(users),
        "chart_data": chart_data
    }

@api_router.get("/export/subscribers")
async def export_subscribers(user = Depends(get_current_user)):
    """Export subscribers as CSV data"""
    subscribers = await db.subscribers.find({}, {"_id": 0}).to_list(100000)
    
    # Convert to CSV format
    csv_data = "telegram_user_id,username,plan_name,start_date,end_date,status\n"
    for s in subscribers:
        csv_data += f"{s.get('telegram_user_id','')},{s.get('username','')},{s.get('plan_name','')},{s.get('start_date','')},{s.get('end_date','')},{s.get('status','')}\n"
    
    return {"csv_data": csv_data, "count": len(subscribers)}

@api_router.get("/export/payments")
async def export_payments(user = Depends(get_current_user)):
    """Export payments as CSV data"""
    payments = await db.payments.find({}, {"_id": 0}).to_list(100000)
    
    # Convert to CSV format
    csv_data = "id,telegram_user_id,username,amount,plan_name,status,payment_method,created_at,verified_at\n"
    for p in payments:
        csv_data += f"{p.get('id','')},{p.get('telegram_user_id','')},{p.get('telegram_username','')},{p.get('amount','')},{p.get('plan_name','')},{p.get('status','')},{p.get('payment_method','')},{p.get('created_at','')},{p.get('verified_at','')}\n"
    
    return {"csv_data": csv_data, "count": len(payments)}


# ============== TELEGRAM WEBHOOK ==============

async def send_telegram_message_with_buttons(chat_id: str, message: str, buttons: list = None, bot_token: str = None, retries: int = 3):
    """Send message with inline keyboard buttons with rate limiting"""
    if not bot_token:
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
    
    if not bot_token:
        return False
    
    # Rate limiting per chat
    now = asyncio.get_event_loop().time()
    last = telegram_last_request.get(chat_id, 0)
    if now - last < TELEGRAM_MIN_INTERVAL:
        await asyncio.sleep(TELEGRAM_MIN_INTERVAL - (now - last))
    telegram_last_request[chat_id] = asyncio.get_event_loop().time()
    
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                if buttons:
                    payload["reply_markup"] = {"inline_keyboard": buttons}
                
                response = await http_client.post(url, json=payload)
                logger.info(f"Telegram response: {response.status_code}")
                
                if response.status_code == 200:
                    return True
                elif response.status_code == 429:
                    retry_after = response.json().get("parameters", {}).get("retry_after", 1)
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                else:
                    return False
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(0.5)
    return False

# ============== PAID POSTS ADMIN APIs ==============

@api_router.get("/paid-posts")
async def get_paid_posts(user = Depends(get_current_user)):
    """Get all paid posts for admin dashboard"""
    posts = await db.paid_posts.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return posts

@api_router.get("/paid-posts/{post_id}")
async def get_paid_post(post_id: str, user = Depends(get_current_user)):
    """Get single paid post details"""
    post = await db.paid_posts.find_one({"id": post_id}, {"_id": 0})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Get unlock history
    unlocks = await db.paid_post_unlocks.find({"post_id": post_id}, {"_id": 0}).to_list(100)
    post["unlocks"] = unlocks
    
    return post

@api_router.put("/paid-posts/{post_id}")
async def update_paid_post(post_id: str, data: dict, user = Depends(get_current_user)):
    """Update paid post (price, active status)"""
    await db.paid_posts.update_one(
        {"id": post_id},
        {"$set": {
            "price": data.get("price", 0),
            "is_active": data.get("is_active", True),
            "caption": data.get("caption", "")
        }}
    )
    return {"message": "Post updated"}

@api_router.delete("/paid-posts/{post_id}")
async def delete_paid_post(post_id: str, user = Depends(get_current_user)):
    """Delete/deactivate a paid post"""
    await db.paid_posts.update_one({"id": post_id}, {"$set": {"is_active": False}})
    return {"message": "Post deactivated"}

@api_router.get("/unlock-requests")
async def get_unlock_requests(user = Depends(get_current_user)):
    """Get pending unlock requests for admin approval"""
    requests = await db.unlock_requests.find({"status": "pending_admin"}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return requests

@api_router.post("/unlock-requests/{request_id}/approve")
async def approve_unlock_request(request_id: str, user = Depends(get_current_user)):
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
    
    # Save unlock record
    unlock_record = {
        "id": str(uuid.uuid4()),
        "post_id": post_id,
        "telegram_user_id": chat_id,
        "telegram_username": username,
        "payment_id": "admin_approved",
        "unlocked_at": datetime.now(timezone.utc).isoformat()
    }
    await db.paid_post_unlocks.insert_one(unlock_record)
    
    # Update unlock count
    await db.paid_posts.update_one({"id": post_id}, {"$inc": {"unlock_count": 1}})
    
    # Update request status
    await db.unlock_requests.update_one({"id": request_id}, {"$set": {"status": "approved"}})
    
    # Send content to user
    if bot_token and chat_id:
        success_msg = "✅ <b>Payment Approved!</b>\n\n🔓 Here's your unlocked content:"
        await send_telegram_message(chat_id, success_msg, bot_token)
        
        if paid_post.get("content_type") == "photo" and paid_post.get("original_file_id"):
            caption = f"🔓 <b>Unlocked!</b>\n\n{paid_post.get('caption', '')}"
            await send_telegram_photo(chat_id, paid_post["original_file_id"], caption, bot_token)
        elif paid_post.get("content_type") == "video" and paid_post.get("original_file_id"):
            caption = f"🔓 <b>Unlocked Video!</b>\n\n{paid_post.get('caption', '')}"
            await send_telegram_video(chat_id, paid_post["original_file_id"], caption, bot_token)
    
    return {"message": "Unlock approved and content sent"}

@api_router.post("/unlock-requests/{request_id}/reject")
async def reject_unlock_request(request_id: str, user = Depends(get_current_user)):
    """Reject unlock request"""
    request = await db.unlock_requests.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    await db.unlock_requests.update_one({"id": request_id}, {"$set": {"status": "rejected"}})
    
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    chat_id = request.get("telegram_user_id")
    
    if bot_token and chat_id:
        reject_msg = "❌ <b>Payment Not Verified</b>\n\n"
        reject_msg += "Your screenshot could not be verified.\n"
        reject_msg += "Please try again with a valid payment screenshot."
        await send_telegram_message(chat_id, reject_msg, bot_token)
    
    return {"message": "Unlock request rejected"}

@api_router.post("/telegram/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        
        logger.info(f"Webhook received: {data}")
        
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
        
        # Log bot token status for debugging
        if not bot_token:
            logger.error("BOT TOKEN NOT FOUND! Check database settings or TELEGRAM_BOT_TOKEN env var")
        else:
            logger.info(f"Bot token loaded: {bot_token[:10]}...")
        
        promo_channel_id = settings.get("promo_channel_id", "")  # Public promo channel
        telegram_channel_id = settings.get("telegram_channel_id", "")  # Default channel
        
        # Use promo channel if set, otherwise use telegram channel
        target_channel_id = promo_channel_id if promo_channel_id else telegram_channel_id
        
        # Handle channel posts - Add Subscribe button on channel posts OR process paid posts
        channel_post = data.get("channel_post")
        if channel_post and bot_token:
            post_chat_id = str(channel_post.get("chat", {}).get("id", ""))
            message_id = channel_post.get("message_id")
            caption = channel_post.get("caption", "") or channel_post.get("text", "") or ""
            
            # Skip forwarded messages (they can't be edited)
            is_forwarded = channel_post.get("forward_from_chat") or channel_post.get("forward_origin")
            
            # Check if this is a PAID POST (has /paid command in caption)
            is_paid_post = caption.lower().startswith("/paid") or " /paid" in caption.lower()
            
            if is_paid_post and message_id and not is_forwarded:
                # Process as a PAID POST
                logger.info(f"Processing PAID POST in channel {post_chat_id}")
                
                try:
                    # IMMEDIATELY delete original message to prevent viewing unblurred content
                    await delete_telegram_message(post_chat_id, message_id, bot_token)
                    logger.info(f"Deleted original message {message_id} immediately")
                    
                    # Get content type and file_id
                    photo = channel_post.get("photo")
                    video = channel_post.get("video")
                    content_type = "photo" if photo else ("video" if video else "text")
                    original_file_id = ""
                    
                    if photo:
                        # Get largest photo
                        original_file_id = photo[-1].get("file_id", "")
                    elif video:
                        original_file_id = video.get("file_id", "")
                    
                    # Clean caption (remove /paid command)
                    clean_caption = caption.replace("/paid", "").replace("/Paid", "").replace("/PAID", "").strip()
                    
                    # Extract price if mentioned (e.g., /paid 99 or /paid ₹99 or /paid -99)
                    price_match = re.search(r'^[₹\-]?(\d+)\s*', clean_caption)
                    post_price = float(price_match.group(1)) if price_match else 0
                    
                    # Remove price from caption if found at the beginning
                    if price_match:
                        clean_caption = clean_caption[price_match.end():].strip()
                    
                    # If no price specified, get default from settings or plans
                    if post_price <= 0:
                        settings = await get_bot_settings()
                        post_price = settings.get("default_paid_post_price", 0)
                        if post_price <= 0:
                            plans = await db.plans.find({"is_active": True}, {"_id": 0}).sort("price", 1).to_list(1)
                            if plans:
                                post_price = plans[0].get("price", 99)
                            else:
                                post_price = 99
                    
                    # Create paid post record
                    paid_post_id = str(uuid.uuid4())
                    paid_post = {
                        "id": paid_post_id,
                        "channel_id": post_chat_id,
                        "original_message_id": message_id,
                        "content_type": content_type,
                        "original_file_id": original_file_id,
                        "caption": clean_caption,
                        "price": post_price,
                        "unlock_count": 0,
                        "is_active": True,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    await db.paid_posts.insert_one(paid_post)
                    logger.info(f"Created paid post record: {paid_post_id} with price {post_price}")
                    
                    # If it's a photo, create blurred version
                    blurred_message_id = 0
                    if photo and original_file_id:
                        # Download original photo
                        image_bytes = await download_telegram_photo(original_file_id, bot_token)
                        if image_bytes:
                            # Create blurred version
                            blurred_bytes = create_blurred_image(image_bytes)
                            if blurred_bytes:
                                # Original already deleted above
                                
                                # Send blurred version with Unlock button
                                bot_username = await get_bot_username(bot_token)
                                unlock_button = {
                                    "inline_keyboard": [[{
                                        "text": "🔓 Unlock Post",
                                        "url": f"https://t.me/{bot_username}?start=unlock_{paid_post_id}"
                                    }]]
                                }
                                
                                price_text = f"₹{int(post_price)}" if post_price > 0 else "Premium"
                                blur_caption = f"🔒 <b>Paid Content</b>\n\n"
                                blur_caption += f"💰 Price: <b>{price_text}</b>\n\n"
                                blur_caption += "👆 Tap 'Unlock Post' to view full content!"
                                
                                result = await send_telegram_photo(post_chat_id, blurred_bytes, blur_caption, bot_token, unlock_button)
                                if result and result.get("result"):
                                    blurred_message_id = result["result"].get("message_id", 0)
                                    # Update paid post with blurred message ID
                                    await db.paid_posts.update_one(
                                        {"id": paid_post_id},
                                        {"$set": {"blurred_message_id": blurred_message_id}}
                                    )
                                    logger.info(f"Sent blurred photo with unlock button, message_id: {blurred_message_id}")
                    
                    elif video:
                        # For videos, we can't blur easily - just replace with preview message
                        # Original already deleted above
                        
                        bot_username = await get_bot_username(bot_token)
                        unlock_button = {
                            "inline_keyboard": [[{
                                "text": "🔓 Unlock Video",
                                "url": f"https://t.me/{bot_username}?start=unlock_{paid_post_id}"
                            }]]
                        }
                        
                        price_text = f"₹{int(post_price)}" if post_price > 0 else "Premium"
                        video_msg = f"🎬 <b>Paid Video Content</b>\n\n"
                        video_msg += f"💰 Price: <b>{price_text}</b>\n\n"
                        video_msg += "👆 Tap 'Unlock Video' to view!"
                        
                        await send_telegram_message_with_buttons(post_chat_id, video_msg, unlock_button["inline_keyboard"], bot_token)
                    
                    return {"ok": True, "paid_post": True}
                    
                except Exception as e:
                    logger.error(f"Failed to process paid post: {e}")
            
            # Regular channel post - Add Subscribe button
            elif message_id and not is_forwarded:
                # Add Subscribe button by editing the message (no delay)
                try:
                    bot_username = await get_bot_username(bot_token)
                    if not bot_username:
                        logger.warning("Could not get bot username for subscribe button")
                    
                    subscribe_button = [[{
                        "text": "🔔 Subscribe Now",
                        "url": f"https://t.me/{bot_username}?start=subscribe"
                    }]]
                    
                    async with httpx.AsyncClient(timeout=10.0) as http_client:
                        # Try to edit message with reply markup
                        url = f"https://api.telegram.org/bot{bot_token}/editMessageReplyMarkup"
                        response = await http_client.post(url, json={
                            "chat_id": post_chat_id,
                            "message_id": message_id,
                            "reply_markup": {"inline_keyboard": subscribe_button}
                        })
                        
                        logger.info(f"Subscribe button edit response: {response.status_code} for channel {post_chat_id}")
                        
                        if response.status_code == 200:
                            logger.info(f"Added subscribe button to channel post: SUCCESS")
                        else:
                            # If edit fails, send a reply message with button
                            logger.info(f"Edit failed ({response.status_code}: {response.text}), sending reply with button")
                            reply_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                            reply_response = await http_client.post(reply_url, json={
                                "chat_id": post_chat_id,
                                "text": "👆 <b>Interested?</b>\n\n🔔 Click below to subscribe!",
                                "parse_mode": "HTML",
                                "reply_to_message_id": message_id,
                                "reply_markup": {"inline_keyboard": subscribe_button}
                            })
                            logger.info(f"Reply message response: {reply_response.status_code}")
                            
                except Exception as e:
                    logger.error(f"Failed to add subscribe button: {e}")
            
            return {"ok": True}
        
        # Handle new channel members - Send welcome message
        chat_member_update = data.get("chat_member")
        if chat_member_update and bot_token:
            chat_id = str(chat_member_update.get("chat", {}).get("id", ""))
            new_member = chat_member_update.get("new_chat_member", {})
            old_member = chat_member_update.get("old_chat_member", {})
            user = new_member.get("user", {})
            user_id = str(user.get("id", ""))
            username = user.get("username", "")
            first_name = user.get("first_name", "")
            
            # Check if user joined (status changed to "member" or "administrator")
            old_status = old_member.get("status", "")
            new_status = new_member.get("status", "")
            
            # Only process if user is joining (not leaving)
            if new_status in ["member", "administrator"] and old_status in ["left", "kicked", ""]:
                logger.info(f"New member {user_id} (@{username}) joined channel {chat_id}")
                
                # Send welcome message with plans directly to user's private chat
                if user_id and not user.get("is_bot"):
                    # Get plans and settings
                    plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
                    settings = await get_bot_settings()
                    website_link = settings.get("website_link", "https://miraclecouplee.syke.club")
                    
                    welcome_msg = f"🎉 <b>Welcome {first_name}!</b>\n\n"
                    welcome_msg += "Thanks for joining our channel! 💕\n\n"
                    welcome_msg += f"🌐 <b>Visit:</b> {website_link}\n\n"
                    welcome_msg += "🔥 <b>Get Exclusive Content!</b>\n"
                    welcome_msg += "Subscribe now for premium access!\n\n"
                    welcome_msg += "━━━━━━━━━━━━━━━\n"
                    welcome_msg += "🎯 <b>Choose Your Plan:</b>\n\n"
                    
                    buttons = []
                    for plan in plans:
                        plan_price = int(plan['price'])
                        welcome_msg += f"📦 <b>{plan['name']}</b> - ₹{plan_price}\n"
                        buttons.append([{"text": f"📦 {plan['name']} - ₹{plan_price}", "callback_data": f"buy_{plan['id']}"}])
                    
                    buttons.append([{"text": "🌐 Visit Website", "url": website_link}])
                    buttons.append([{"text": "🎁 Special Discount!", "callback_data": "special_discount"}])
                    
                    try:
                        await send_telegram_message_with_buttons(user_id, welcome_msg, buttons, bot_token)
                        logger.info(f"Sent welcome message with plans to new member {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to send welcome message: {e}")
            
            return {"ok": True}
        
        # Skip old messages (older than 30 seconds) - but allow callback queries
        callback_query = data.get("callback_query")
        message = data.get("message") or (callback_query.get("message") if callback_query else None)
        
        # Only skip old regular messages, not callback queries (button clicks)
        if message and not callback_query:
            msg_date = message.get("date", 0)
            current_time = int(datetime.now(timezone.utc).timestamp())
            if current_time - msg_date > 30:
                logger.info(f"Skipping old message from {current_time - msg_date}s ago")
                return {"ok": True}
        
        # Handle callback queries (button clicks)
        if callback_query:
            callback_data = callback_query.get("data", "")
            chat_id = str(callback_query.get("from", {}).get("id", ""))
            username = callback_query.get("from", {}).get("username", "")
            
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            if callback_data.startswith("buy_"):
                plan_id = callback_data.replace("buy_", "")
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                
                if plan:
                    # Show payment options
                    qr_code_url = settings.get("qr_code_url", "")
                    
                    payment_msg = f"<b>📦 {plan['name']}</b>\n\n"
                    payment_msg += f"💰 Price: <b>₹{plan['price']}</b>\n"
                    payment_msg += f"⏱ Duration: <b>{plan['duration_days']} days</b>\n\n"
                    
                    if plan.get('features'):
                        payment_msg += "<b>Features:</b>\n"
                        for feat in plan['features']:
                            payment_msg += f"✅ {feat}\n"
                        payment_msg += "\n"
                    
                    payment_msg += "━━━━━━━━━━━━━━━\n"
                    payment_msg += "<b>💳 Payment Options:</b>\n\n"
                    payment_msg += "1️⃣ <b>UPI/QR Code:</b>\n"
                    payment_msg += "   Pay via any UPI app\n\n"
                    payment_msg += "2️⃣ After payment, send screenshot to admin\n\n"
                    payment_msg += f"📱 <b>Your User ID:</b> <code>{chat_id}</code>\n"
                    payment_msg += "(Share this with admin after payment)"
                    
                    buttons = []
                    if qr_code_url:
                        buttons.append([{"text": "📱 Show QR Code", "callback_data": f"qr_{plan_id}"}])
                    buttons.append([{"text": "✅ I've Paid - Contact Admin", "callback_data": f"paid_{plan_id}"}])
                    buttons.append([{"text": "◀️ Back to Plans", "callback_data": "back_plans"}])
                    
                    await send_telegram_message_with_buttons(chat_id, payment_msg, buttons, bot_token)
            
            elif callback_data.startswith("qr_"):
                # Send QR code image and wait for screenshot
                plan_id = callback_data.replace("qr_", "")
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                qr_url = settings.get("qr_code_url", "")
                
                # Save that we're waiting for screenshot from this user
                await db.pending_screenshots.update_one(
                    {"telegram_user_id": chat_id},
                    {"$set": {
                        "telegram_user_id": chat_id,
                        "telegram_username": username,
                        "plan_id": plan_id,
                        "plan_name": plan["name"] if plan else "",
                        "amount": plan["price"] if plan else 0,
                        "status": "waiting",
                        "reminder_count": 0,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }},
                    upsert=True
                )
                
                if qr_url:
                    try:
                        async with httpx.AsyncClient() as http_client:
                            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                            await http_client.post(url, json={
                                "chat_id": chat_id,
                                "photo": qr_url,
                                "caption": f"📱 <b>Scan & Pay ₹{plan['price'] if plan else ''}</b>\n\n"
                                          f"📦 Plan: <b>{plan['name'] if plan else ''}</b>\n\n"
                                          f"⚠️ <b>Payment ke baad turant screenshot bhejo!</b>\n\n"
                                          f"⏳ Waiting for your screenshot...",
                                "parse_mode": "HTML"
                            })
                    except Exception as e:
                        logger.error(f"Failed to send QR: {e}")
                        await send_telegram_message(chat_id, f"QR Code: {qr_url}\n\n📸 Screenshot bhejo!", bot_token)
                
                # Send reminder message
                reminder_msg = f"👆 @{username if username else 'User'}\n\n"
                reminder_msg += "⚠️ <b>Screenshot bhejo payment ka!</b>\n\n"
                reminder_msg += "📸 Bina screenshot ke verification nahi hoga.\n"
                reminder_msg += "⏳ <b>Waiting...</b>"
                
                await send_telegram_message(chat_id, reminder_msg, bot_token)
                
                # Schedule reminders using background task
                background_tasks.add_task(send_screenshot_reminders, chat_id, username, bot_token)
            
            elif callback_data.startswith("razorpay_"):
                # Create Razorpay payment link
                plan_id = callback_data.replace("razorpay_", "")
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                
                if plan and razorpay_client:
                    try:
                        # Create Razorpay order
                        order = razorpay_client.order.create({
                            "amount": int(plan["price"] * 100),  # paise
                            "currency": "INR",
                            "payment_capture": 1,
                            "notes": {
                                "telegram_user_id": chat_id,
                                "telegram_username": username,
                                "plan_id": plan_id,
                                "plan_name": plan["name"],
                                "type": "bot_subscription"
                            }
                        })
                        
                        # Store order in database
                        order_obj = {
                            "id": str(uuid.uuid4()),
                            "razorpay_order_id": order["id"],
                            "telegram_user_id": chat_id,
                            "telegram_username": username,
                            "plan_id": plan_id,
                            "plan_name": plan["name"],
                            "amount": plan["price"],
                            "status": "created",
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                        await db.bot_orders.insert_one(order_obj)
                        
                        # Create payment link
                        payment_link = f"https://rzp.io/l/{order['id']}"
                        
                        # Actually we need to use Razorpay payment page
                        # Send user to a web page that handles Razorpay checkout
                        settings = await get_bot_settings()
                        website_url = settings.get("website_link", "https://tgsubsbot.com")
                        checkout_url = f"{website_url}/bot-checkout?order_id={order['id']}&plan_id={plan_id}&user_id={chat_id}"
                        
                        msg = "💳 <b>Pay via Razorpay</b>\n\n"
                        msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                        msg += f"💰 Amount: <b>₹{plan['price']}</b>\n\n"
                        msg += "Click below to complete payment.\n"
                        msg += "<b>Auto-verify hoga payment ke baad!</b>"
                        
                        buttons = [
                            [{"text": "💳 Pay Now", "url": checkout_url}],
                            [{"text": "◀️ Back to Plans", "callback_data": "back_plans"}]
                        ]
                        await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
                        
                    except Exception as e:
                        logger.error(f"Razorpay error: {e}")
                        await send_telegram_message(chat_id, "❌ Payment error. Please try QR code method.", bot_token)
            
            elif callback_data.startswith("paid_"):
                plan_id = callback_data.replace("paid_", "")
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                
                if plan:
                    # Check if already has pending payment for this plan
                    existing = await db.payments.find_one({
                        "telegram_user_id": chat_id,
                        "plan_id": plan_id,
                        "status": "pending"
                    })
                    
                    if not existing:
                        # Create pending payment record
                        payment_obj = {
                            "id": str(uuid.uuid4()),
                            "subscriber_id": None,
                            "telegram_user_id": chat_id,
                            "telegram_username": username or "",
                            "amount": plan["price"],
                            "plan_id": plan_id,
                            "plan_name": plan["name"],
                            "payment_method": "manual",
                            "razorpay_order_id": None,
                            "razorpay_payment_id": None,
                            "status": "pending",
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                        await db.payments.insert_one(payment_obj)
                        logger.info(f"Created pending payment for user {chat_id}, plan {plan['name']}")
                    
                    msg = "✅ <b>Payment Recorded!</b>\n\n"
                    msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                    msg += f"💰 Amount: <b>₹{plan['price']}</b>\n\n"
                    msg += "━━━━━━━━━━━━━━━\n"
                    msg += "📝 <b>Next Steps:</b>\n\n"
                    msg += "1️⃣ Send payment screenshot to admin\n"
                    msg += "2️⃣ Admin will verify your payment\n"
                    msg += "3️⃣ You'll get channel access!\n\n"
                    msg += f"📱 Your ID: <code>{chat_id}</code>\n"
                    if username:
                        msg += f"👤 Username: @{username}\n"
                    msg += "\n⏳ <i>Verification usually takes 5-30 minutes</i>"
                else:
                    msg = "❌ Plan not found. Please try again with /start"
                
                buttons = [[{"text": "◀️ Back to Plans", "callback_data": "back_plans"}]]
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
            
            elif callback_data == "back_plans":
                # Show plans again
                plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
                
                welcome_msg = "🎯 <b>Choose Your Plan</b>\n\n"
                buttons = []
                for plan in plans:
                    plan_price = int(plan['price'])
                    welcome_msg += f"📦 <b>{plan['name']}</b>\n"
                    welcome_msg += f"   💰 ₹{plan_price} • ⏱ {plan['duration_days']} days\n\n"
                    buttons.append([{"text": f"📦 {plan['name']} - ₹{plan_price}", "callback_data": f"buy_{plan['id']}"}])
                
                buttons.append([{"text": "📊 Check My Status", "callback_data": "check_status"}])
                await send_telegram_message_with_buttons(chat_id, welcome_msg, buttons, bot_token)
            
            elif callback_data == "cancel_payment":
                # Cancel pending screenshot/payment
                await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                
                msg = "❌ <b>Cancelled!</b>\n\n"
                msg += "Payment process cancel ho gaya.\n\n"
                msg += "Phir se try karne ke liye /start bhejo!"
                
                buttons = [[{"text": "🔄 Start Again", "callback_data": "back_plans"}]]
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
            
            elif callback_data == "special_discount":
                # Show actual prices (500 less than displayed)
                plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
                
                msg = "🎁 <b>Special Discount Unlocked!</b>\n\n"
                msg += "🔥 <b>Sirf aapke liye special prices:</b>\n\n"
                
                buttons = []
                for plan in plans:
                    plan_price = int(plan['price'])
                    discounted_price = int(plan_price * 0.8)  # 20% discount
                    msg += f"📦 <b>{plan['name']}</b>\n"
                    msg += f"   <s>₹{plan_price}</s> → 💰 <b>₹{discounted_price}</b> 🔥\n\n"
                    buttons.append([{"text": f"🔥 {plan['name']} - ₹{discounted_price}", "callback_data": f"buy_{plan['id']}"}])
                
                msg += "⚡ <i>Limited time offer!</i>"
                
                buttons.append([{"text": "📊 Check My Status", "callback_data": "check_status"}])
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
            
            elif callback_data.startswith("confirm_ss_"):
                # User confirmed it's a payment screenshot - VERIFY
                plan_id = callback_data.replace("confirm_ss_", "")
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                pending = await db.pending_screenshots.find_one({"telegram_user_id": chat_id}, {"_id": 0})
                
                if plan and pending:
                    photo_file_id = pending.get("photo_file_id")
                    final_amount = pending.get("discounted_price") or plan["price"]
                    
                    # Create payment record
                    payment_obj = {
                        "id": str(uuid.uuid4()),
                        "subscriber_id": None,
                        "telegram_user_id": chat_id,
                        "telegram_username": username or pending.get("telegram_username", ""),
                        "amount": final_amount,
                        "plan_id": plan_id,
                        "plan_name": plan["name"],
                        "payment_method": "qr_screenshot",
                        "screenshot_file_id": photo_file_id,
                        "status": "verified",
                        "auto_verified": True,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    await db.payments.insert_one(payment_obj)
                    
                    # Delete pending screenshot record
                    await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                    
                    # Check if this is a Chat plan (5 Min or 30 Min)
                    plan_name_lower = plan['name'].lower()
                    is_chat_plan = "min chat" in plan_name_lower or "minute chat" in plan_name_lower
                    
                    if is_chat_plan:
                        # Handle time-limited chat plan
                        if "5" in plan_name_lower:
                            duration_minutes = 5
                            plan_type = "5min"
                        elif "30" in plan_name_lower:
                            duration_minutes = 30
                            plan_type = "30min"
                        else:
                            duration_minutes = 5
                            plan_type = "5min"
                        
                        # Get available group from pool
                        available_group = await get_available_chat_group()
                        
                        if available_group:
                            result = await assign_chat_group(
                                available_group["group_id"],
                                chat_id,
                                username,
                                plan_type,
                                duration_minutes
                            )
                            
                            if result.get("success"):
                                invite_link = result.get("invite_link")
                                
                                success_msg = "✅ <b>Payment Verified!</b>\n\n"
                                success_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                                success_msg += f"💰 Amount: <b>₹{final_amount}</b>\n"
                                success_msg += f"⏱ Duration: <b>{duration_minutes} minutes</b>\n\n"
                                success_msg += "🔗 <b>Join the chat now:</b>\n"
                                success_msg += f"{invite_link}\n\n"
                                success_msg += f"⚠️ <b>Note:</b> You have {duration_minutes} minutes to chat.\n"
                                success_msg += "After time ends, you'll need to renew!"
                                
                                await send_telegram_message(chat_id, success_msg, bot_token)
                            else:
                                error_msg = "✅ <b>Payment Verified!</b>\n\n"
                                error_msg += "But chat group assignment failed.\n"
                                error_msg += "Admin will contact you shortly!"
                                await send_telegram_message(chat_id, error_msg, bot_token)
                        else:
                            no_group_msg = "✅ <b>Payment Verified!</b>\n\n"
                            no_group_msg += "⚠️ All chat slots are currently busy.\n\n"
                            no_group_msg += "Admin will assign you a chat slot soon!"
                            await send_telegram_message(chat_id, no_group_msg, bot_token)
                    else:
                        # Regular subscription - create subscriber and add to channel
                        grace_days = settings.get("grace_period_days", 2)
                        end_date = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])
                        grace_end = end_date + timedelta(days=grace_days)
                        
                        subscriber_obj = {
                            "id": str(uuid.uuid4()),
                            "telegram_user_id": chat_id,
                            "telegram_username": username or pending.get("telegram_username", ""),
                            "plan_id": plan["id"],
                            "plan_name": plan["name"],
                            "payment_method": "qr_screenshot",
                            "payment_id": payment_obj["id"],
                            "status": "active",
                            "start_date": datetime.now(timezone.utc).isoformat(),
                            "end_date": end_date.isoformat(),
                            "grace_end_date": grace_end.isoformat(),
                            "reminder_sent": False,
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                        await db.subscribers.insert_one(subscriber_obj)
                        
                        success_msg = "✅ <b>Payment Verified!</b>\n\n"
                        success_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                        success_msg += f"💰 Amount: <b>₹{final_amount}</b>\n"
                        success_msg += f"⏱ Valid till: <b>{end_date.strftime('%d %b %Y')}</b>\n\n"
                        success_msg += "🎉 <b>Subscription Activated!</b>\n\n"
                        success_msg += f"🌐 <b>Visit:</b> {settings.get('website_link', 'https://miraclecouplee.syke.club')}\n\n"
                        success_msg += "📢 Channel link aa raha hai..."
                        
                        await send_telegram_message(chat_id, success_msg, bot_token)
                        
                        plan_channel = plan.get("channel_id", "")
                        if plan_channel:
                            await add_to_channel(chat_id, plan_channel, plan["name"])
                    
                    logger.info(f"Payment verified for user {chat_id}, plan {plan['name']}")
                else:
                    await send_telegram_message(chat_id, "❌ Error. /start se dobara try karo.", bot_token)
            
            elif callback_data == "wrong_ss":
                # User sent wrong image - decline and ask for correct one
                await db.pending_screenshots.update_one(
                    {"telegram_user_id": chat_id},
                    {"$set": {"status": "waiting"}}  # Reset to waiting
                )
                
                msg = "❌ <b>Galat Image!</b>\n\n"
                msg += "📸 <b>Sirf payment screenshot bhejo:</b>\n"
                msg += "• GPay ✅\n"
                msg += "• PhonePe ✅\n"
                msg += "• Paytm ✅\n"
                msg += "• UPI ✅\n\n"
                msg += "⏳ <b>Sahi screenshot ka wait kar raha hun...</b>"
                
                buttons = [[{"text": "❌ Cancel", "callback_data": "cancel_payment"}]]
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
            
            elif callback_data.startswith("discount_"):
                # Show discounted price
                plan_id = callback_data.replace("discount_", "")
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                
                if plan:
                    original_price = plan["price"]
                    discounted_price = int(original_price * 0.7)  # 30% discount
                    
                    msg = "🎁 <b>Special Discount!</b>\n\n"
                    msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                    msg += f"💰 Original: <s>₹{original_price}</s>\n"
                    msg += f"🔥 <b>Discounted: ₹{discounted_price}</b> (30% OFF!)\n\n"
                    msg += "📸 Payment karke screenshot bhejo!\n"
                    msg += "✅ Turant verify ho jayega!"
                    
                    # Update pending screenshot with discounted price
                    await db.pending_screenshots.update_one(
                        {"telegram_user_id": chat_id},
                        {"$set": {"discounted_price": discounted_price, "discount_applied": True}}
                    )
                    
                    buttons = [
                        [{"text": "📱 Show QR Code", "callback_data": f"qr_{plan_id}"}],
                        [{"text": "❌ Cancel", "callback_data": "cancel_payment"}]
                    ]
                    await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
                else:
                    await send_telegram_message(chat_id, "❌ Plan not found. /start karke dobara try karo.", bot_token)
            
            elif callback_data.startswith("renew_chat_"):
                # Handle chat session renewal
                session_id = callback_data.replace("renew_chat_", "")
                session = await db.chat_sessions.find_one({"id": session_id}, {"_id": 0})
                
                if session:
                    plan_type = session.get("plan_type", "5min")
                    
                    # Find matching plan
                    if plan_type == "5min":
                        plan = await db.plans.find_one({"name": {"$regex": "5.*min.*chat", "$options": "i"}}, {"_id": 0})
                    else:
                        plan = await db.plans.find_one({"name": {"$regex": "30.*min.*chat", "$options": "i"}}, {"_id": 0})
                    
                    if plan:
                        qr_code_url = settings.get("qr_code_url", "")
                        
                        renew_msg = f"🔄 <b>Renew Chat Session</b>\n\n"
                        renew_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                        renew_msg += f"💰 Price: <b>₹{plan['price']}</b>\n\n"
                        renew_msg += "━━━━━━━━━━━━━━━\n"
                        renew_msg += "<b>💳 Payment:</b>\n\n"
                        renew_msg += "1️⃣ Pay via UPI/QR Code\n"
                        renew_msg += "2️⃣ Send screenshot\n"
                        renew_msg += "3️⃣ Get more chat time!\n\n"
                        renew_msg += f"📱 <b>Your User ID:</b> <code>{chat_id}</code>"
                        
                        buttons = []
                        if qr_code_url:
                            buttons.append([{"text": "📱 Show QR Code", "callback_data": f"qr_{plan['id']}"}])
                        buttons.append([{"text": "✅ I've Paid", "callback_data": f"paid_{plan['id']}"}])
                        
                        await send_telegram_message_with_buttons(chat_id, renew_msg, buttons, bot_token)
                    else:
                        await send_telegram_message(chat_id, "Plan not found. Use /start to see plans.", bot_token)
                else:
                    await send_telegram_message(chat_id, "Session not found. Use /start to buy new plan.", bot_token)
            
            elif callback_data.startswith("exit_chat_"):
                # Handle chat session exit/cancel
                session_id = callback_data.replace("exit_chat_", "")
                session = await db.chat_sessions.find_one({"id": session_id}, {"_id": 0})
                
                if session:
                    group_id = session.get("group_id")
                    user_id = session.get("user_id")
                    
                    # Release the group and kick user
                    if group_id:
                        await release_chat_group(group_id)
                    
                    # Update session status
                    await db.chat_sessions.update_one(
                        {"id": session_id},
                        {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}}
                    )
                    
                    # Send goodbye message
                    exit_msg = "👋 <b>Chat Session Ended</b>\n\n"
                    exit_msg += "Thank you for using our service!\n\n"
                    exit_msg += "💬 Want to chat again?\n"
                    exit_msg += "Use /start to buy a new session."
                    
                    await send_telegram_message(chat_id, exit_msg, bot_token)
                    
                    logger.info(f"User {chat_id} exited chat session {session_id}")
                else:
                    await send_telegram_message(chat_id, "Session not found.", bot_token)
            
            elif callback_data.startswith("renew_"):
                # Handle renewal - go directly to payment for the same plan
                plan_id = callback_data.replace("renew_", "")
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                
                if plan:
                    # Show payment options directly
                    qr_code_url = settings.get("qr_code_url", "")
                    
                    renew_msg = f"🔄 <b>Renew Subscription</b>\n\n"
                    renew_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                    renew_msg += f"💰 Price: <b>₹{plan['price']}</b>\n"
                    renew_msg += f"⏱ Duration: <b>{plan['duration_days']} days</b>\n\n"
                    renew_msg += "━━━━━━━━━━━━━━━\n"
                    renew_msg += "<b>💳 Payment Options:</b>\n\n"
                    renew_msg += "1️⃣ <b>UPI/QR Code:</b> Pay via any UPI app\n"
                    renew_msg += "2️⃣ After payment, click 'I've Paid'\n\n"
                    renew_msg += f"📱 <b>Your User ID:</b> <code>{chat_id}</code>"
                    
                    buttons = []
                    if qr_code_url:
                        buttons.append([{"text": "📱 Show QR Code", "callback_data": f"qr_{plan_id}"}])
                    buttons.append([{"text": "✅ I've Paid", "callback_data": f"paid_{plan_id}"}])
                    buttons.append([{"text": "📦 View Other Plans", "callback_data": "back_plans"}])
                    
                    await send_telegram_message_with_buttons(chat_id, renew_msg, buttons, bot_token)
                else:
                    # Plan not found, show all plans
                    await send_telegram_message(chat_id, "Plan not found. Please choose from available plans:", bot_token)
                    plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
                    buttons = []
                    for p in plans:
                        buttons.append([{"text": f"📦 {p['name']} - ₹{p['price']}", "callback_data": f"buy_{p['id']}"}])
                    await send_telegram_message_with_buttons(chat_id, "🎯 <b>Available Plans:</b>", buttons, bot_token)
            
            # ============ VIDEO CALL BOOKING HANDLERS ============
            elif callback_data == "book_videocall":
                # Show date selection for video call
                today = datetime.now(timezone.utc).date()
                
                msg = "📅 <b>Select Date for Video Call</b>\n\n"
                msg += "Choose a date from below:"
                
                buttons = []
                for i in range(7):  # Next 7 days
                    date = today + timedelta(days=i)
                    date_str = date.strftime("%Y-%m-%d")
                    day_name = date.strftime("%A")
                    display = date.strftime("%d %b") + f" ({day_name})"
                    buttons.append([{"text": f"📆 {display}", "callback_data": f"vc_date_{date_str}"}])
                
                buttons.append([{"text": "❌ Cancel", "callback_data": "cancel_action"}])
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
            
            elif callback_data.startswith("vc_date_"):
                # Date selected, show time slots
                selected_date = callback_data.replace("vc_date_", "")
                
                msg = f"🕐 <b>Select Time Slot</b>\n\n"
                msg += f"📅 Date: <b>{selected_date}</b>\n\n"
                msg += "Choose a time:"
                
                time_slots = ["10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00"]
                buttons = []
                row = []
                for i, time in enumerate(time_slots):
                    row.append({"text": f"🕐 {time}", "callback_data": f"vc_time_{selected_date}_{time}"})
                    if len(row) == 2:
                        buttons.append(row)
                        row = []
                if row:
                    buttons.append(row)
                
                buttons.append([{"text": "◀️ Back to Dates", "callback_data": "book_videocall"}])
                buttons.append([{"text": "❌ Cancel", "callback_data": "cancel_action"}])
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
            
            elif callback_data.startswith("vc_time_"):
                # Time selected, confirm booking
                parts = callback_data.replace("vc_time_", "").split("_")
                selected_date = parts[0]
                selected_time = parts[1]
                
                settings = await get_bot_settings()
                price = settings.get("video_call_price", 500)
                duration = settings.get("video_call_duration", 30)
                
                msg = f"✅ <b>Confirm Video Call Booking</b>\n\n"
                msg += f"📅 Date: <b>{selected_date}</b>\n"
                msg += f"🕐 Time: <b>{selected_time}</b>\n"
                msg += f"⏱ Duration: <b>{duration} minutes</b>\n"
                msg += f"💰 Price: <b>₹{price}</b>\n\n"
                msg += "Click confirm to proceed with payment:"
                
                buttons = [
                    [{"text": "✅ Confirm & Pay", "callback_data": f"vc_confirm_{selected_date}_{selected_time}"}],
                    [{"text": "◀️ Change Time", "callback_data": f"vc_date_{selected_date}"}],
                    [{"text": "❌ Cancel", "callback_data": "cancel_action"}]
                ]
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
            
            elif callback_data.startswith("vc_confirm_"):
                # Create booking and show payment
                parts = callback_data.replace("vc_confirm_", "").split("_")
                selected_date = parts[0]
                selected_time = parts[1]
                
                settings = await get_bot_settings()
                price = settings.get("video_call_price", 500)
                duration = settings.get("video_call_duration", 30)
                qr_code_url = settings.get("qr_code_url", "")
                
                # Create booking record
                booking = {
                    "id": str(uuid.uuid4()),
                    "telegram_user_id": chat_id,
                    "telegram_username": username,
                    "scheduled_date": selected_date,
                    "scheduled_time": selected_time,
                    "duration_minutes": duration,
                    "price": price,
                    "status": "pending_payment",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.video_call_bookings.insert_one(booking)
                
                msg = f"📹 <b>Video Call Booking Created!</b>\n\n"
                msg += f"🆔 Booking ID: <code>{booking['id'][:8]}</code>\n"
                msg += f"📅 Date: <b>{selected_date}</b>\n"
                msg += f"🕐 Time: <b>{selected_time}</b>\n"
                msg += f"💰 Amount: <b>₹{price}</b>\n\n"
                msg += "━━━━━━━━━━━━━━━\n"
                msg += "<b>💳 Payment Instructions:</b>\n\n"
                msg += "1️⃣ Pay ₹{} via UPI\n".format(price)
                msg += "2️⃣ Send payment screenshot here\n"
                msg += "3️⃣ Your booking will be confirmed!\n\n"
                msg += f"📱 <b>Your ID:</b> <code>{chat_id}</code>"
                
                buttons = []
                if qr_code_url:
                    buttons.append([{"text": "📱 Show QR Code", "callback_data": f"vc_qr_{booking['id']}"}])
                buttons.append([{"text": "❌ Cancel Booking", "callback_data": f"vc_cancel_{booking['id']}"}])
                
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
            
            elif callback_data.startswith("vc_qr_"):
                # Show QR code for video call payment
                booking_id = callback_data.replace("vc_qr_", "")
                qr_code_url = settings.get("qr_code_url", "")
                
                if qr_code_url:
                    await send_telegram_photo(chat_id, qr_code_url, "📱 Scan this QR code to pay\n\nAfter payment, send screenshot here.", bot_token)
                else:
                    await send_telegram_message(chat_id, "QR Code not configured. Please contact admin.", bot_token)
            
            elif callback_data.startswith("vc_cancel_"):
                # Cancel video call booking
                booking_id = callback_data.replace("vc_cancel_", "")
                await db.video_call_bookings.update_one(
                    {"id": booking_id},
                    {"$set": {"status": "cancelled"}}
                )
                await send_telegram_message(chat_id, "❌ Video call booking cancelled.\n\nUse /videocall to book again.", bot_token)
            
            elif callback_data == "cancel_action":
                await send_telegram_message(chat_id, "❌ Action cancelled.\n\nUse /start to see plans or /help for commands.", bot_token)
            
            elif callback_data == "check_status":
                subscriber = await db.subscribers.find_one({"telegram_user_id": chat_id}, {"_id": 0})
                if subscriber:
                    end_date = datetime.fromisoformat(subscriber["end_date"]) if isinstance(subscriber["end_date"], str) else subscriber["end_date"]
                    days_left = (end_date - datetime.now(timezone.utc)).days
                    
                    status_emoji = "✅" if subscriber['status'] == 'active' else "⚠️" if subscriber['status'] == 'grace' else "❌"
                    status_msg = f"{status_emoji} <b>Your Subscription</b>\n\n"
                    status_msg += f"📦 Plan: <b>{subscriber['plan_name']}</b>\n"
                    status_msg += f"📊 Status: <b>{subscriber['status'].upper()}</b>\n"
                    status_msg += f"📅 Expires: <b>{end_date.strftime('%d %b %Y')}</b>\n"
                    status_msg += f"⏳ Days Left: <b>{days_left}</b>"
                else:
                    status_msg = "❌ You don't have an active subscription.\n\nUse /start to see available plans!"
                
                buttons = [[{"text": "◀️ Back to Plans", "callback_data": "back_plans"}]]
                await send_telegram_message_with_buttons(chat_id, status_msg, buttons, bot_token)
            
            # ========== PAID POST UNLOCK CALLBACKS ==========
            
            elif callback_data.startswith("unlock_qr_"):
                # Show QR code for paid post unlock
                post_id = callback_data.replace("unlock_qr_", "")
                paid_post = await db.paid_posts.find_one({"id": post_id, "is_active": True}, {"_id": 0})
                
                if paid_post:
                    settings = await get_bot_settings()
                    qr_code_url = settings.get("qr_code_url", "")
                    post_price = paid_post.get("price", 99)
                    
                    if qr_code_url:
                        qr_msg = f"📱 <b>Scan & Pay ₹{int(post_price)}</b>\n\n"
                        qr_msg += "After payment, send screenshot here to unlock content! 📸"
                        await send_telegram_photo(chat_id, qr_code_url, qr_msg, bot_token)
                    else:
                        await send_telegram_message(chat_id, "❌ QR Code not configured. Contact admin.", bot_token)
                else:
                    await send_telegram_message(chat_id, "❌ Post not found or expired.", bot_token)
            
            elif callback_data.startswith("unlock_paid_"):
                # User claims to have paid for unlock
                post_id = callback_data.replace("unlock_paid_", "")
                paid_post = await db.paid_posts.find_one({"id": post_id, "is_active": True}, {"_id": 0})
                
                if paid_post:
                    post_price = paid_post.get("price", 99)
                    
                    # Save pending unlock payment
                    await db.pending_screenshots.update_one(
                        {"telegram_user_id": chat_id},
                        {"$set": {
                            "telegram_user_id": chat_id,
                            "telegram_username": username,
                            "unlock_post_id": post_id,
                            "expected_amount": post_price,
                            "status": "waiting_unlock",
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }},
                        upsert=True
                    )
                    
                    verify_msg = "📸 <b>Send Payment Screenshot!</b>\n\n"
                    verify_msg += f"💰 Amount: ₹{int(post_price)}\n\n"
                    verify_msg += "Send your payment screenshot now and I'll verify it automatically! ✅"
                    
                    buttons = [[{"text": "❌ Cancel", "callback_data": "cancel_action"}]]
                    await send_telegram_message_with_buttons(chat_id, verify_msg, buttons, bot_token)
                else:
                    await send_telegram_message(chat_id, "❌ Post not found or expired.", bot_token)
            
            # Answer callback to remove loading state
            try:
                async with httpx.AsyncClient() as http_client:
                    await http_client.post(
                        f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery",
                        json={"callback_query_id": callback_query.get("id")}
                    )
            except Exception:
                pass
            
            return {"ok": True}
        
        # Handle regular messages
        message = data.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "")
        username = message.get("from", {}).get("username", "")
        photo = message.get("photo")  # Check if message has photo
        caption = message.get("caption", "").lower()  # Get caption if any
        
        if not chat_id:
            return {"ok": True}
        
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
        
        # Handle screenshot/photo for payment verification with OCR
        if photo and bot_token:
            # Check if we're waiting for screenshot from this user (for subscription OR unlock)
            pending = await db.pending_screenshots.find_one({
                "telegram_user_id": chat_id, 
                "status": {"$in": ["waiting", "waiting_unlock"]}
            }, {"_id": 0})
            
            # Handle PAID POST UNLOCK screenshot
            if pending and pending.get("status") == "waiting_unlock":
                post_id = pending.get("unlock_post_id")
                paid_post = await db.paid_posts.find_one({"id": post_id, "is_active": True}, {"_id": 0})
                
                if paid_post:
                    logger.info(f"Processing unlock screenshot for post {post_id} from user {chat_id}")
                    
                    photo_file_id = photo[-1]["file_id"] if photo else None
                    image_bytes = await download_telegram_photo(photo_file_id, bot_token)
                    
                    if image_bytes:
                        # Run OCR + AI analysis
                        ocr_result = detect_payment_screenshot(image_bytes)
                        settings = await get_bot_settings()
                        expected_upi = settings.get("payment_upi_id", "")
                        ai_threshold = settings.get("ai_auto_approve_threshold", 85)
                        
                        ai_result = await analyze_payment_screenshot_with_ai(
                            image_bytes,
                            expected_amount=pending.get("expected_amount", 0),
                            expected_upi_id=expected_upi if expected_upi else None
                        )
                        
                        # Decision logic
                        is_valid = False
                        auto_approve = False
                        
                        if ai_result.get("ai_enabled") and ai_result.get("confidence_score", 0) >= 70:
                            is_valid = ai_result.get("is_valid_payment", False)
                            auto_approve = ai_result.get("auto_approve_recommended", False) and ai_result.get("confidence_score", 0) >= ai_threshold
                        else:
                            is_valid = ocr_result.get("is_valid", False)
                        
                        if is_valid and auto_approve:
                            # AUTO UNLOCK - Valid payment!
                            logger.info(f"Auto-unlocking post {post_id} for user {chat_id}")
                            
                            # Save unlock record
                            unlock_record = {
                                "id": str(uuid.uuid4()),
                                "post_id": post_id,
                                "telegram_user_id": chat_id,
                                "telegram_username": username,
                                "payment_id": "auto_verified",
                                "screenshot_file_id": photo_file_id,
                                "ai_result": ai_result,
                                "unlocked_at": datetime.now(timezone.utc).isoformat()
                            }
                            await db.paid_post_unlocks.insert_one(unlock_record)
                            
                            # Update unlock count
                            await db.paid_posts.update_one({"id": post_id}, {"$inc": {"unlock_count": 1}})
                            
                            # Remove pending status
                            await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                            
                            # Send unlocked content
                            success_msg = "✅ <b>Payment Verified!</b>\n\n🔓 Unlocking your content..."
                            await send_telegram_message(chat_id, success_msg, bot_token)
                            
                            if paid_post.get("content_type") == "photo" and paid_post.get("original_file_id"):
                                caption = f"🔓 <b>Unlocked!</b>\n\n{paid_post.get('caption', '')}"
                                await send_telegram_photo(chat_id, paid_post["original_file_id"], caption, bot_token)
                            elif paid_post.get("content_type") == "video" and paid_post.get("original_file_id"):
                                caption = f"🔓 <b>Unlocked Video!</b>\n\n{paid_post.get('caption', '')}"
                                await send_telegram_video(chat_id, paid_post["original_file_id"], caption, bot_token)
                            
                            return {"ok": True}
                        
                        elif is_valid:
                            # Valid but needs admin review
                            pending_msg = "📸 <b>Screenshot Received!</b>\n\n"
                            pending_msg += "⏳ Admin verification pending...\n"
                            pending_msg += "You'll receive the content once verified! ✅"
                            
                            # Save for admin review
                            unlock_request = {
                                "id": str(uuid.uuid4()),
                                "post_id": post_id,
                                "telegram_user_id": chat_id,
                                "telegram_username": username,
                                "screenshot_file_id": photo_file_id,
                                "expected_amount": pending.get("expected_amount", 0),
                                "status": "pending_admin",
                                "ocr_result": ocr_result,
                                "ai_result": ai_result if ai_result.get("ai_enabled") else None,
                                "created_at": datetime.now(timezone.utc).isoformat()
                            }
                            await db.unlock_requests.insert_one(unlock_request)
                            await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                            
                            await send_telegram_message(chat_id, pending_msg, bot_token)
                            return {"ok": True}
                        
                        else:
                            # Invalid screenshot
                            invalid_msg = "❌ <b>Invalid Screenshot!</b>\n\n"
                            invalid_msg += "Please send a valid payment screenshot showing:\n"
                            invalid_msg += "✅ Payment Success/Completed status\n"
                            invalid_msg += "✅ Amount paid\n\n"
                            invalid_msg += "Try again or contact admin for help."
                            
                            await send_telegram_message(chat_id, invalid_msg, bot_token)
                            return {"ok": True}
                    
                    return {"ok": True}
                else:
                    await send_telegram_message(chat_id, "❌ Post not found or expired.", bot_token)
                    await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                    return {"ok": True}
            
            # Handle REGULAR SUBSCRIPTION screenshot
            if pending and pending.get("status") == "waiting":
                plan_id = pending.get("plan_id")
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                
                if plan:
                    # Get the photo file_id (largest size)
                    photo_file_id = photo[-1]["file_id"] if photo else None
                    
                    # Send "Analyzing" loading message
                    analyzing_msg = "🔍 <b>Analyzing your screenshot...</b>\n\n"
                    analyzing_msg += "⏳ Please wait, verifying your payment..."
                    await send_telegram_message(chat_id, analyzing_msg, bot_token)
                    
                    # Download and analyze photo with OCR
                    image_bytes = await download_telegram_photo(photo_file_id, bot_token)
                    
                    if image_bytes:
                        # Run OCR detection first (fast)
                        ocr_result = detect_payment_screenshot(image_bytes)
                        logger.info(f"OCR Result for user {chat_id}: {ocr_result}")
                        
                        # Get expected UPI ID from settings
                        settings = await get_bot_settings()
                        expected_upi = settings.get("payment_upi_id", "")
                        ai_threshold = settings.get("ai_auto_approve_threshold", 85)
                        
                        # Run AI analysis for better accuracy and fake detection
                        ai_result = await analyze_payment_screenshot_with_ai(
                            image_bytes,
                            expected_amount=plan.get('price'),
                            expected_upi_id=expected_upi if expected_upi else None
                        )
                        logger.info(f"AI Result for user {chat_id}: {ai_result}")
                        
                        # Decision: Use AI if available and confident, otherwise fall back to OCR
                        is_valid = False
                        auto_approve = False
                        verification_method = "ocr"
                        
                        if ai_result.get("ai_enabled") and ai_result.get("confidence_score", 0) >= 70:
                            # AI is confident - use AI decision
                            is_valid = ai_result.get("is_valid_payment", False)
                            # Use threshold from settings (dynamic)
                            auto_approve = ai_result.get("auto_approve_recommended", False) and ai_result.get("confidence_score", 0) >= ai_threshold
                            verification_method = "ai_gpt4o"
                            logger.info(f"Using AI decision: valid={is_valid}, auto_approve={auto_approve}, confidence={ai_result.get('confidence_score')}, threshold={ai_threshold}")
                        else:
                            # Fall back to OCR
                            is_valid = ocr_result.get("is_valid", False)
                            auto_approve = False  # OCR alone should NOT auto-approve - send to admin
                            verification_method = "ocr"
                            logger.info(f"Using OCR decision: valid={is_valid}, auto_approve=False (OCR requires admin review)")
                        
                        if is_valid and auto_approve:
                            # Valid payment screenshot detected - AUTO VERIFY
                            logger.info(f"Valid payment screenshot detected for user {chat_id} via {verification_method}")
                            
                            # Check if user already has active subscription
                            existing_sub = await db.subscribers.find_one({
                                "telegram_user_id": chat_id,
                                "status": "active"
                            }, {"_id": 0})
                            
                            # Get discounted price if available
                            discounted_price = pending.get("discounted_price")
                            final_price = discounted_price if discounted_price else plan['price']
                            
                            if existing_sub:
                                # Extend subscription
                                current_end = datetime.fromisoformat(existing_sub["end_date"]) if isinstance(existing_sub["end_date"], str) else existing_sub["end_date"]
                                new_end = current_end + timedelta(days=plan['duration_days'])
                                
                                await db.subscribers.update_one(
                                    {"telegram_user_id": chat_id},
                                    {"$set": {
                                        "end_date": new_end.isoformat(),
                                        "plan_id": plan_id,
                                        "plan_name": plan['name']
                                    }}
                                )
                            else:
                                # Create new subscriber
                                new_subscriber = {
                                    "id": str(uuid.uuid4()),
                                    "telegram_user_id": chat_id,
                                    "telegram_username": username,
                                    "plan_id": plan_id,
                                    "plan_name": plan['name'],
                                    "status": "active",
                                    "payment_method": "qr_screenshot",
                                    "start_date": datetime.now(timezone.utc).isoformat(),
                                    "end_date": (datetime.now(timezone.utc) + timedelta(days=plan['duration_days'])).isoformat(),
                                    "created_at": datetime.now(timezone.utc).isoformat()
                                }
                                await db.subscribers.insert_one(new_subscriber)
                            
                            # Create payment record
                            payment_record = {
                                "id": str(uuid.uuid4()),
                                "telegram_user_id": chat_id,
                                "telegram_username": username,
                                "amount": final_price,
                                "plan_id": plan_id,
                                "plan_name": plan['name'],
                                "payment_method": "qr_screenshot",
                                "screenshot_file_id": photo_file_id,
                                "status": "verified",
                                "verification_method": verification_method,
                                "ocr_verified": ocr_result.get("is_valid", False),
                                "ocr_keywords": ocr_result.get("found_keywords", []),
                                "ai_verified": ai_result.get("is_valid_payment", False) if ai_result.get("ai_enabled") else None,
                                "ai_confidence": ai_result.get("confidence_score") if ai_result.get("ai_enabled") else None,
                                "ai_extracted_data": ai_result.get("extracted_data") if ai_result.get("ai_enabled") else None,
                                "ai_fake_indicators": ai_result.get("fake_indicators", []) if ai_result.get("ai_enabled") else [],
                                "created_at": datetime.now(timezone.utc).isoformat(),
                                "verified_at": datetime.now(timezone.utc).isoformat()
                            }
                            await db.payments.insert_one(payment_record)
                            
                            # Delete pending screenshot record
                            await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                            
                            # Check if this is a Chat plan (5 Min or 30 Min)
                            plan_name_lower = plan['name'].lower()
                            is_chat_plan = "min chat" in plan_name_lower or "minute chat" in plan_name_lower
                            
                            if is_chat_plan:
                                # Handle time-limited chat plan
                                # Determine duration from plan name
                                if "5" in plan_name_lower:
                                    duration_minutes = 5
                                    plan_type = "5min"
                                elif "30" in plan_name_lower:
                                    duration_minutes = 30
                                    plan_type = "30min"
                                else:
                                    duration_minutes = 5  # default
                                    plan_type = "5min"
                                
                                # Get available group from pool
                                available_group = await get_available_chat_group()
                                
                                if available_group:
                                    # Assign group to user
                                    result = await assign_chat_group(
                                        available_group["group_id"],
                                        chat_id,
                                        username,
                                        plan_type,
                                        duration_minutes
                                    )
                                    
                                    if result.get("success"):
                                        invite_link = result.get("invite_link")
                                        session = result.get("session")
                                        
                                        success_msg = "✅ <b>Payment Verified!</b>\n\n"
                                        success_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                                        success_msg += f"💰 Amount: <b>₹{final_price}</b>\n"
                                        success_msg += f"⏱ Duration: <b>{duration_minutes} minutes</b>\n\n"
                                        success_msg += "🔗 <b>Join the chat now:</b>\n"
                                        success_msg += f"{invite_link}\n\n"
                                        success_msg += f"⚠️ <b>Note:</b> You have {duration_minutes} minutes to chat.\n"
                                        success_msg += "After time ends, you'll need to renew!"
                                        
                                        await send_telegram_message(chat_id, success_msg, bot_token)
                                    else:
                                        # Group assignment failed
                                        error_msg = "✅ <b>Payment Verified!</b>\n\n"
                                        error_msg += "But chat group assignment failed.\n"
                                        error_msg += "Admin will contact you shortly!\n\n"
                                        error_msg += "Your payment is safe."
                                        await send_telegram_message(chat_id, error_msg, bot_token)
                                else:
                                    # No groups available
                                    no_group_msg = "✅ <b>Payment Verified!</b>\n\n"
                                    no_group_msg += "⚠️ All chat slots are currently busy.\n\n"
                                    no_group_msg += "Admin will assign you a chat slot soon!\n"
                                    no_group_msg += "Your payment is recorded."
                                    await send_telegram_message(chat_id, no_group_msg, bot_token)
                                    
                                    # Notify admin (you can customize this)
                                    logger.warning(f"No chat groups available for user {chat_id}")
                            else:
                                # Regular subscription plan
                                success_msg = "✅ <b>Payment Verified Successfully!</b>\n\n"
                                success_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                                success_msg += f"💰 Amount: <b>₹{final_price}</b>\n"
                                success_msg += f"⏱ Duration: <b>{plan['duration_days']} days</b>\n\n"
                                
                                # Check if plan has auto_assign_group enabled
                                if plan.get("auto_assign_group"):
                                    # Auto-assign from groups pool
                                    available_group = await get_available_chat_group()
                                    
                                    if available_group:
                                        # Assign group for plan duration
                                        result = await assign_chat_group(
                                            available_group["group_id"],
                                            chat_id,
                                            username,
                                            f"plan_{plan_id}",
                                            plan['duration_days'] * 24 * 60  # Convert days to minutes
                                        )
                                        
                                        if result.get("success"):
                                            invite_link = result.get("invite_link")
                                            success_msg += f"👥 <b>Group Access:</b>\n{invite_link}\n\n"
                                            logger.info(f"Auto-assigned group {available_group['group_id']} to user {chat_id}")
                                        else:
                                            logger.warning(f"Failed to assign group to user {chat_id}")
                                    else:
                                        logger.warning(f"No groups available for auto-assign, user {chat_id}")
                                elif plan.get("group_id"):
                                    # Manual group ID specified - create invite link
                                    try:
                                        async with httpx.AsyncClient() as http_client:
                                            url = f"https://api.telegram.org/bot{bot_token}/createChatInviteLink"
                                            response = await http_client.post(url, json={
                                                "chat_id": plan["group_id"],
                                                "member_limit": 1,
                                                "expire_date": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp())
                                            })
                                            if response.status_code == 200:
                                                invite_link = response.json().get("result", {}).get("invite_link", "")
                                                if invite_link:
                                                    success_msg += f"👥 <b>Group Access:</b>\n{invite_link}\n\n"
                                    except Exception as e:
                                        logger.error(f"Error creating group invite: {e}")
                                
                                success_msg += "🎉 <b>Your subscription is now active!</b>"
                                
                                await send_telegram_message(chat_id, success_msg, bot_token)
                                
                                # Add user to premium channel
                                plan_channel = plan.get("channel_id", "")
                                await add_to_channel(chat_id, plan_channel, plan['name'])
                            
                        else:
                            # AI/OCR couldn't auto-verify - check if AI explicitly rejected
                            
                            # If AI detected FAKE indicators or invalid payment, REJECT immediately
                            ai_fake_indicators = ai_result.get("fake_indicators", [])
                            ai_is_valid = ai_result.get("is_valid_payment", True)
                            ai_reason = ai_result.get("reason", "")
                            ai_extracted = ai_result.get("extracted_data", {})
                            amount_matches = ai_result.get("amount_matches", True)
                            upi_matches = ai_result.get("upi_matches", True)
                            
                            if ai_result.get("ai_enabled") and (not ai_is_valid or len(ai_fake_indicators) > 0):
                                # AI REJECTED the payment - show specific funny rejection message
                                logger.info(f"AI REJECTED payment for user {chat_id}: {ai_reason}")
                                
                                extracted_amount = ai_extracted.get("amount", "")
                                extracted_upi = ai_extracted.get("upi_id", "")
                                expected_amount = plan.get('price', 0)
                                
                                # Determine rejection reason and give funny message
                                if not amount_matches and not upi_matches:
                                    # Both wrong
                                    reject_msg = "🤦 <b>Bhai ye kya kar diya!</b>\n\n"
                                    reject_msg += f"❌ Amount galat: Tune {extracted_amount} bheja, plan ki price <b>₹{int(expected_amount)}</b> hai\n"
                                    reject_msg += f"❌ UPI bhi galat: Tune <code>{extracted_upi}</code> pe bheja\n"
                                    if expected_upi:
                                        reject_msg += f"✅ Sahi UPI: <code>{expected_upi}</code>\n\n"
                                    reject_msg += "😅 Dobara try kar bhai, is baar dhyan se!"
                                    
                                elif not amount_matches:
                                    # Amount wrong
                                    try:
                                        paid_amount = int(''.join(filter(str.isdigit, str(extracted_amount))))
                                    except:
                                        paid_amount = 0
                                    
                                    if paid_amount > expected_amount:
                                        reject_msg = f"😮 <b>Arre bhai, zyada bhej diya!</b>\n\n"
                                        reject_msg += f"Plan price: <b>₹{int(expected_amount)}</b>\n"
                                        reject_msg += f"Tune bheja: <b>{extracted_amount}</b>\n\n"
                                        reject_msg += "🤑 Extra paisa wapas chahiye to admin se baat kar!"
                                    else:
                                        reject_msg = f"😬 <b>Bhai thoda kam pad gaya!</b>\n\n"
                                        reject_msg += f"Plan price: <b>₹{int(expected_amount)}</b>\n"
                                        reject_msg += f"Tune bheja: <b>{extracted_amount}</b>\n\n"
                                        reject_msg += "💸 Poora amount bhejo phir milega access!"
                                
                                elif not upi_matches:
                                    # UPI wrong
                                    reject_msg = f"😱 <b>Galat account mein bhej diya bhai!</b>\n\n"
                                    reject_msg += f"Tune bheja: <code>{extracted_upi}</code>\n"
                                    if expected_upi:
                                        reject_msg += f"✅ Sahi UPI: <code>{expected_upi}</code>\n\n"
                                    reject_msg += "🙏 Admin se contact kar, shayad refund mil jaye!"
                                
                                elif ai_fake_indicators:
                                    # Fake screenshot detected
                                    reject_msg = "🚨 <b>Bhai ye fake lag raha hai!</b>\n\n"
                                    reject_msg += f"⚠️ Issues: {', '.join(ai_fake_indicators[:3])}\n\n"
                                    reject_msg += "😏 Dekhna hai to dena to hoga bhai!\n"
                                    reject_msg += "Asli payment screenshot bhejo! 💯"
                                
                                else:
                                    # Generic rejection
                                    reject_msg = "❌ <b>Payment verify nahi ho paya!</b>\n\n"
                                    if ai_reason:
                                        reject_msg += f"📋 Reason: {ai_reason}\n\n"
                                    reject_msg += "😅 Valid payment screenshot bhejo bhai!"
                                
                                # Delete pending record
                                await db.pending_screenshots.delete_one({"telegram_user_id": chat_id})
                                
                                await send_telegram_message(chat_id, reject_msg, bot_token)
                            
                            # Check if this is NOT a payment screenshot at all (selfie, car, random photo)
                            elif not ai_result.get("ai_enabled") and len(ocr_result.get("found_keywords", [])) < 2:
                                # OCR found almost nothing - likely not a payment screenshot
                                import random
                                funny_messages = [
                                    "😏 <b>Bhai dekhna hai to dena to hoga!</b>\n\nYe payment screenshot nahi lag raha...",
                                    "🤨 <b>Ye kya bhej diya bhai?</b>\n\nPayment screenshot chahiye, selfie nahi! 📸",
                                    "😅 <b>Are bhai, payment ka screenshot bhejo!</b>\n\nYe to kuch aur hi hai...",
                                    "🙄 <b>Nice try!</b>\n\nBut humein payment proof chahiye, ye nahi! 💸",
                                    "😂 <b>Seedha payment karo na bhai!</b>\n\nYe photo se kaam nahi chalega..."
                                ]
                                funny_msg = random.choice(funny_messages)
                                funny_msg += "\n\n✅ Valid payment screenshot bhejo jisme dikhe:\n"
                                funny_msg += "• Payment SUCCESS status\n"
                                funny_msg += "• Amount\n"
                                funny_msg += "• UPI Transaction ID"
                                
                                await send_telegram_message(chat_id, funny_msg, bot_token)
                            
                            else:
                                # OCR-only or AI couldn't decide - send to admin review
                                logger.info(f"Auto-verification couldn't confirm payment for user {chat_id}, showing manual confirmation")
                                
                                # Save photo file_id and AI analysis for admin review
                                await db.pending_screenshots.update_one(
                                    {"telegram_user_id": chat_id},
                                    {"$set": {
                                        "status": "confirming",
                                        "photo_file_id": photo_file_id,
                                        "ocr_result": ocr_result,
                                        "ai_result": {
                                            "enabled": ai_result.get("ai_enabled", False),
                                            "is_valid": ai_result.get("is_valid_payment"),
                                            "confidence": ai_result.get("confidence_score"),
                                            "extracted_data": ai_result.get("extracted_data"),
                                            "fake_indicators": ai_result.get("fake_indicators", []),
                                            "reason": ai_result.get("reason")
                                        } if ai_result.get("ai_enabled") else None
                                    }}
                                )
                                
                                # NO MANUAL CONFIRMATION BUTTONS - Direct admin review
                                # Security: User can't self-approve anymore
                                pending_msg = "📸 <b>Screenshot Received!</b>\n\n"
                                pending_msg += "⏳ <b>Admin verification pending...</b>\n\n"
                                
                                if ai_result.get("ai_enabled") and ai_result.get("confidence_score"):
                                    pending_msg += f"🤖 AI Confidence: <b>{ai_result.get('confidence_score')}%</b>\n"
                                    if ai_result.get("fake_indicators"):
                                        pending_msg += f"⚠️ Concerns: {', '.join(ai_result.get('fake_indicators', [])[:2])}\n"
                                
                                pending_msg += "\n📋 Your payment screenshot has been submitted for review.\n"
                                pending_msg += "✅ You'll be notified once verified!\n\n"
                                pending_msg += "⏱ Usually takes a few minutes."
                                
                                # Save for admin dashboard review
                                payment_pending = {
                                    "id": str(uuid.uuid4()),
                                    "telegram_user_id": chat_id,
                                    "telegram_username": username,
                                    "amount": plan.get('price'),
                                    "plan_id": plan_id,
                                    "plan_name": plan['name'],
                                    "payment_method": "qr_screenshot",
                                    "screenshot_file_id": photo_file_id,
                                    "status": "pending",
                                    "ocr_result": ocr_result,
                                    "ai_result": ai_result if ai_result.get("ai_enabled") else None,
                                    "created_at": datetime.now(timezone.utc).isoformat()
                                }
                                await db.payments.insert_one(payment_pending)
                                
                                await send_telegram_message(chat_id, pending_msg, bot_token)
                    else:
                        # Could not download image - save for admin review
                        logger.error(f"Could not download image for user {chat_id}")
                        
                        payment_pending = {
                            "id": str(uuid.uuid4()),
                            "telegram_user_id": chat_id,
                            "telegram_username": username,
                            "amount": plan.get('price'),
                            "plan_id": plan_id,
                            "plan_name": plan['name'],
                            "payment_method": "qr_screenshot",
                            "screenshot_file_id": photo_file_id,
                            "status": "pending",
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                        await db.payments.insert_one(payment_pending)
                        
                        fallback_msg = "📸 <b>Screenshot Received!</b>\n\n"
                        fallback_msg += "⏳ <b>Admin verification pending...</b>\n\n"
                        fallback_msg += "📋 Your payment screenshot has been submitted for review.\n"
                        fallback_msg += "✅ You'll be notified once verified!"
                        
                        await send_telegram_message(chat_id, fallback_msg, bot_token)
                    
                    return {"ok": True}
            else:
                # User sent image but we're not waiting for it
                msg = "❌ <b>Screenshot not expected!</b>\n\n"
                msg += "Pehle plan select karo, phir QR code se payment karo, phir screenshot bhejo.\n\n"
                msg += "/start se shuru karo!"
                await send_telegram_message(chat_id, msg, bot_token)
                return {"ok": True}
        
        # Handle /start unlock_{post_id} - Unlock paid post
        if text and text.startswith("/start unlock_"):
            post_id = text.replace("/start unlock_", "").strip()
            logger.info(f"User {chat_id} trying to unlock paid post: {post_id}")
            
            # Find the paid post
            paid_post = await db.paid_posts.find_one({"id": post_id, "is_active": True}, {"_id": 0})
            
            if not paid_post:
                await send_telegram_message(chat_id, "❌ <b>Post not found!</b>\n\nThis paid content may have been removed or expired.", bot_token)
                return {"ok": True}
            
            # Check if user already unlocked this post
            existing_unlock = await db.paid_post_unlocks.find_one({
                "post_id": post_id,
                "telegram_user_id": chat_id
            }, {"_id": 0})
            
            if existing_unlock:
                # User already unlocked - send content again
                logger.info(f"User {chat_id} already unlocked post {post_id}, resending content")
                
                if paid_post.get("content_type") == "photo" and paid_post.get("original_file_id"):
                    caption = f"🔓 <b>Unlocked Content</b>\n\n{paid_post.get('caption', '')}"
                    await send_telegram_photo(chat_id, paid_post["original_file_id"], caption, bot_token)
                elif paid_post.get("content_type") == "video" and paid_post.get("original_file_id"):
                    caption = f"🔓 <b>Unlocked Video</b>\n\n{paid_post.get('caption', '')}"
                    await send_telegram_video(chat_id, paid_post["original_file_id"], caption, bot_token)
                else:
                    await send_telegram_message(chat_id, f"🔓 <b>Unlocked Content</b>\n\n{paid_post.get('caption', 'Content already unlocked!')}", bot_token)
                
                return {"ok": True}
            
            # Everyone must pay for paid posts - no free unlock for subscribers
            # Show payment options
            post_price = paid_post.get("price", 0)
            settings = await get_bot_settings()
            qr_code_url = settings.get("qr_code_url", "")
            
            # If no specific price, use default from plans
            if post_price <= 0:
                plans = await db.plans.find({"is_active": True}, {"_id": 0}).sort("price", 1).to_list(1)
                if plans:
                    post_price = plans[0].get("price", 99)
                else:
                    post_price = 99
            
            unlock_msg = f"🔒 <b>Paid Content</b>\n\n"
            unlock_msg += f"💰 Price: <b>₹{int(post_price)}</b>\n\n"
            unlock_msg += "━━━━━━━━━━━━━━━\n"
            unlock_msg += "<b>💳 Payment Options:</b>\n\n"
            unlock_msg += "1️⃣ Pay via UPI/QR Code\n"
            unlock_msg += "2️⃣ Send payment screenshot here\n"
            unlock_msg += "3️⃣ Get content instantly!\n\n"
            unlock_msg += "OR subscribe for unlimited access! 👇"
            
            buttons = []
            if qr_code_url:
                buttons.append([{"text": "📱 Show QR Code", "callback_data": f"unlock_qr_{post_id}"}])
            buttons.append([{"text": "✅ I've Paid - Verify", "callback_data": f"unlock_paid_{post_id}"}])
            buttons.append([{"text": "📦 Get Full Subscription", "callback_data": "back_plans"}])
            
            await send_telegram_message_with_buttons(chat_id, unlock_msg, buttons, bot_token)
            
            # Save pending unlock request
            await db.pending_screenshots.update_one(
                {"telegram_user_id": chat_id},
                {"$set": {
                    "telegram_user_id": chat_id,
                    "telegram_username": username,
                    "unlock_post_id": post_id,
                    "expected_amount": post_price,
                    "status": "waiting_unlock",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
            
            return {"ok": True}
        
        if text == "/start" or text == "/start subscribe" or text == "/plans":
            # Show plans directly - fetch from database dynamically
            plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
            settings = await get_bot_settings()
            website_link = settings.get("website_link", "https://miraclecouplee.syke.club")
            
            welcome_msg = "🎉 <b>Welcome!</b>\n\n"
            welcome_msg += "🔥 <b>Exclusive Content Awaits!</b>\n\n"
            welcome_msg += f"🌐 <b>Visit:</b> {website_link}\n\n"
            welcome_msg += "━━━━━━━━━━━━━━━\n"
            welcome_msg += "🎯 <b>Choose Your Plan:</b>\n\n"
            
            buttons = []
            for plan in plans:
                # Show actual price from database (no inflation)
                plan_price = plan['price']
                welcome_msg += f"📦 <b>{plan['name']}</b>\n"
                welcome_msg += f"   💰 ₹{int(plan_price)} • ⏱ {plan['duration_days']} days\n\n"
                buttons.append([{"text": f"📦 {plan['name']} - ₹{int(plan_price)}", "callback_data": f"buy_{plan['id']}"}])
            
            if not plans:
                welcome_msg += "No plans available at the moment.\n"
            
            # Add website link button, Special Discount and Status
            buttons.append([{"text": "🌐 Visit Website", "url": website_link}])
            buttons.append([{"text": "🎁 Special Discount For You!", "callback_data": "special_discount"}])
            buttons.append([{"text": "📊 Check My Status", "callback_data": "check_status"}])
            
            await send_telegram_message_with_buttons(chat_id, welcome_msg, buttons)
        
        elif text == "/status":
            subscriber = await db.subscribers.find_one({"telegram_user_id": chat_id}, {"_id": 0})
            if subscriber:
                end_date = datetime.fromisoformat(subscriber["end_date"]) if isinstance(subscriber["end_date"], str) else subscriber["end_date"]
                days_left = (end_date - datetime.now(timezone.utc)).days
                
                status_emoji = "✅" if subscriber['status'] == 'active' else "⚠️" if subscriber['status'] == 'grace' else "❌"
                status_msg = f"{status_emoji} <b>Your Subscription</b>\n\n"
                status_msg += f"📦 Plan: <b>{subscriber['plan_name']}</b>\n"
                status_msg += f"📊 Status: <b>{subscriber['status'].upper()}</b>\n"
                status_msg += f"📅 Expires: <b>{end_date.strftime('%d %b %Y')}</b>\n"
                status_msg += f"⏳ Days Left: <b>{days_left}</b>"
            else:
                status_msg = "❌ You don't have an active subscription.\n\nUse /start to see available plans!"
            
            buttons = [[{"text": "📦 View Plans", "callback_data": "back_plans"}]]
            await send_telegram_message_with_buttons(chat_id, status_msg, buttons)
        
        elif text == "/help":
            help_msg = "🤖 <b>Bot Commands</b>\n\n"
            help_msg += "/start - View subscription plans\n"
            help_msg += "/status - Check your subscription\n"
            help_msg += "/videocall - Book a video call\n"
            help_msg += "/share - Get shareable message\n"
            help_msg += "/help - Show this help message\n\n"
            help_msg += "💬 You can also ask me any questions!"
            await send_telegram_message(chat_id, help_msg)
        
        elif text == "/share":
            # Get bot username
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            bot_username = ""
            
            try:
                async with httpx.AsyncClient() as http_client:
                    me_response = await http_client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
                    if me_response.status_code == 200:
                        bot_username = me_response.json().get("result", {}).get("username", "")
            except Exception:
                pass
            
            plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
            
            share_msg = "🔥 <b>Premium Subscription Service</b> 🔥\n\n"
            share_msg += "━━━━━━━━━━━━━━━━━━━\n"
            share_msg += "📦 <b>Available Plans:</b>\n\n"
            
            for plan in plans:
                share_msg += f"✨ <b>{plan['name']}</b> - ₹{plan['price']}\n"
                share_msg += f"   ⏱ {plan['duration_days']} days\n"
                if plan.get('features'):
                    for feat in plan['features'][:2]:
                        share_msg += f"   ✅ {feat}\n"
                share_msg += "\n"
            
            share_msg += "━━━━━━━━━━━━━━━━━━━\n"
            share_msg += "👇 <b>Click below to subscribe!</b>"
            
            # Create inline button with bot link
            buttons = []
            if bot_username:
                buttons.append([{"text": "🚀 Subscribe Now", "url": f"https://t.me/{bot_username}?start=subscribe"}])
            buttons.append([{"text": "📞 Contact Admin", "url": f"https://t.me/{bot_username}"}])
            
            await send_telegram_message_with_buttons(chat_id, share_msg, buttons)
            
            # Also send instruction
            await send_telegram_message(chat_id, "👆 Forward this message to your groups!\n\nThe buttons will work for everyone.", bot_token)
        
        # Handle /videocall command
        elif text == "/videocall":
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            if not settings.get("video_call_enabled", True):
                await send_telegram_message(chat_id, "❌ Video calls are currently not available.", bot_token)
            else:
                price = settings.get("video_call_price", 500)
                duration = settings.get("video_call_duration", 30)
                instructions = settings.get("video_call_instructions", "📹 Book a 1-on-1 video call with us!")
                
                msg = f"📹 <b>Video Call Booking</b>\n\n"
                msg += f"{instructions}\n\n"
                msg += f"💰 <b>Price:</b> ₹{price}\n"
                msg += f"⏱ <b>Duration:</b> {duration} minutes\n\n"
                msg += "👇 Click below to book your video call:"
                
                buttons = [
                    [{"text": "📅 Book Video Call", "callback_data": "book_videocall"}],
                    [{"text": "❌ Cancel", "callback_data": "cancel_action"}]
                ]
                
                await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
        
        # Handle photo/screenshot uploads
        photo = message.get("photo")
        if photo:
            # Get the largest photo (last in array)
            file_id = photo[-1].get("file_id")
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            if file_id and bot_token:
                # Get file path from Telegram
                try:
                    async with httpx.AsyncClient() as http_client:
                        file_response = await http_client.get(
                            f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
                        )
                        if file_response.status_code == 200:
                            file_data = file_response.json()
                            file_path = file_data.get("result", {}).get("file_path", "")
                            
                            if file_path:
                                # Create the full URL for the screenshot
                                screenshot_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
                                
                                # Find user's pending payment and update with screenshot
                                pending_payment = await db.payments.find_one({
                                    "telegram_user_id": chat_id,
                                    "status": "pending"
                                }, sort=[("created_at", -1)])
                                
                                if pending_payment:
                                    await db.payments.update_one(
                                        {"id": pending_payment["id"]},
                                        {"$set": {"screenshot_url": screenshot_url, "screenshot_file_id": file_id}}
                                    )
                                    
                                    msg = "✅ <b>Screenshot Received!</b>\n\n"
                                    msg += "📸 Your payment screenshot has been saved.\n"
                                    msg += "⏳ Admin will verify it shortly.\n\n"
                                    msg += f"📱 Your ID: <code>{chat_id}</code>"
                                    await send_telegram_message(chat_id, msg, bot_token)
                                    logger.info(f"Screenshot saved for payment {pending_payment['id']}")
                                else:
                                    msg = "⚠️ No pending payment found.\n\n"
                                    msg += "Please first select a plan and click 'I've Paid' button.\n"
                                    msg += "Then send your payment screenshot."
                                    buttons = [[{"text": "📦 View Plans", "callback_data": "back_plans"}]]
                                    await send_telegram_message_with_buttons(chat_id, msg, buttons, bot_token)
                except Exception as e:
                    logger.error(f"Error processing screenshot: {e}")
        
        # ============ AI CHAT - Handle unknown text messages ============
        # If message is text but not a command, try to answer using FAQ or AI
        if text and not text.startswith("/") and not photo:
            settings = await get_bot_settings()
            bot_token = settings.get("telegram_bot_token", "")
            
            # First check FAQs for matching answer
            faqs = await db.faqs.find({"is_active": True}, {"_id": 0}).to_list(100)
            
            faq_answer = None
            text_lower = text.lower()
            
            for faq in faqs:
                keywords = faq.get("keywords", [])
                question = faq.get("question", "").lower()
                
                # Check if any keyword matches
                if any(kw.lower() in text_lower for kw in keywords):
                    faq_answer = faq.get("answer")
                    break
                # Check if question is similar
                elif any(word in text_lower for word in question.split() if len(word) > 3):
                    faq_answer = faq.get("answer")
                    break
            
            if faq_answer:
                # Found FAQ match
                await send_telegram_message(chat_id, faq_answer, bot_token)
            else:
                # No FAQ match - use AI to respond
                try:
                    from emergentintegrations.llm.chat import chat, LlmMessage
                    
                    # Get context about the bot/business
                    plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
                    plan_info = "\n".join([f"- {p['name']}: ₹{p['price']} for {p['duration_days']} days" for p in plans])
                    
                    system_prompt = f"""You are a helpful customer support assistant for a subscription-based Telegram service.

Available Plans:
{plan_info}

Commands users can use:
- /start - View subscription plans
- /status - Check subscription status
- /videocall - Book a video call
- /help - Get help

Keep responses short, friendly, and helpful. If user asks about pricing or plans, tell them to use /start command. 
If they have technical issues, ask them to describe the problem.
Always be polite and use emojis sparingly."""

                    response = await chat(
                        api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
                        messages=[
                            LlmMessage(role="system", content=system_prompt),
                            LlmMessage(role="user", content=text)
                        ],
                        model="gpt-4o-mini"
                    )
                    
                    if response and response.message:
                        await send_telegram_message(chat_id, response.message, bot_token)
                    else:
                        # Fallback response
                        fallback_msg = "🤔 I'm not sure about that.\n\n"
                        fallback_msg += "Try these commands:\n"
                        fallback_msg += "/start - View plans\n"
                        fallback_msg += "/status - Check subscription\n"
                        fallback_msg += "/help - Get help"
                        await send_telegram_message(chat_id, fallback_msg, bot_token)
                        
                except Exception as ai_error:
                    logger.error(f"AI Chat error: {ai_error}")
                    # Fallback response
                    fallback_msg = "🤔 I'm here to help!\n\n"
                    fallback_msg += "Use /start to see our plans or /help for commands."
                    await send_telegram_message(chat_id, fallback_msg, bot_token)
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"ok": False}

# ============== BACKGROUND TASKS ==============

async def check_subscriptions():
    """Check and update subscription statuses"""
    now = datetime.now(timezone.utc)
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    reminder_days = settings.get("reminder_days_before", 3)
    bot_token = settings.get("telegram_bot_token", "")
    
    subscribers = await db.subscribers.find({"status": {"$in": ["active", "grace"]}}, {"_id": 0}).to_list(10000)
    
    for sub in subscribers:
        end_date = datetime.fromisoformat(sub["end_date"]) if isinstance(sub["end_date"], str) else sub["end_date"]
        grace_end = datetime.fromisoformat(sub["grace_end_date"]) if isinstance(sub.get("grace_end_date"), str) else sub.get("grace_end_date")
        
        days_to_expiry = (end_date - now).days
        
        # Send reminder with Renew button
        if days_to_expiry <= reminder_days and days_to_expiry > 0 and not sub.get("reminder_sent"):
            reminder_msg = f"⏰ <b>Subscription Expiring Soon!</b>\n\n"
            reminder_msg += f"📦 Plan: <b>{sub.get('plan_name', 'Premium')}</b>\n"
            reminder_msg += f"📅 Expires in: <b>{days_to_expiry} days</b>\n"
            reminder_msg += f"🗓 End Date: <b>{end_date.strftime('%d %b %Y')}</b>\n\n"
            reminder_msg += "👇 Renew now to continue access!"
            
            buttons = [
                [{"text": "🔄 Renew Now", "callback_data": f"renew_{sub.get('plan_id', '')}"}],
                [{"text": "📦 View All Plans", "callback_data": "back_plans"}]
            ]
            await send_telegram_message_with_buttons(sub["telegram_user_id"], reminder_msg, buttons, bot_token)
            await db.subscribers.update_one({"id": sub["id"]}, {"$set": {"reminder_sent": True}})
        
        # Move to grace period with Renew button
        if now > end_date and sub["status"] == "active":
            await db.subscribers.update_one({"id": sub["id"]}, {"$set": {"status": "grace"}})
            
            grace_msg = "⚠️ <b>Subscription Expired!</b>\n\n"
            grace_msg += f"📦 Plan: <b>{sub.get('plan_name', 'Premium')}</b>\n"
            grace_msg += f"⏳ Grace Period: <b>{settings.get('grace_period_days', 2)} days</b>\n\n"
            grace_msg += "Renew now to keep your access!"
            
            buttons = [
                [{"text": "🔄 Renew Now", "callback_data": f"renew_{sub.get('plan_id', '')}"}],
                [{"text": "📦 View All Plans", "callback_data": "back_plans"}]
            ]
            await send_telegram_message_with_buttons(sub["telegram_user_id"], grace_msg, buttons, bot_token)
        
        # Remove after grace period
        if grace_end and now > grace_end and sub["status"] == "grace":
            await db.subscribers.update_one({"id": sub["id"]}, {"$set": {"status": "expired"}})
            
            # Get plan channel for removal
            plan = await db.plans.find_one({"id": sub.get("plan_id")}, {"_id": 0})
            plan_channel = plan.get("channel_id", "") if plan else ""
            await remove_from_channel(sub["telegram_user_id"], plan_channel)
            
            expired_msg = "❌ <b>Subscription Ended</b>\n\n"
            expired_msg += "Your subscription and grace period have ended.\n"
            expired_msg += "You've been removed from the premium channel.\n\n"
            expired_msg += "👇 Resubscribe anytime!"
            
            buttons = [
                [{"text": "🔄 Resubscribe", "callback_data": "back_plans"}]
            ]
            await send_telegram_message_with_buttons(sub["telegram_user_id"], expired_msg, buttons, bot_token)

async def send_followups():
    """Send follow-up messages twice a week"""
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    
    if not settings.get("followup_enabled"):
        return
    
    followup_msg = settings.get("followup_message", "Check out our premium services!")
    website_link = settings.get("website_link", "")
    
    if website_link:
        followup_msg += f"\n\nVisit: {website_link}"
    
    subscribers = await db.subscribers.find({"status": "active"}, {"_id": 0}).to_list(10000)
    
    for sub in subscribers:
        await send_telegram_message(sub["telegram_user_id"], followup_msg)

async def send_daily_reminders():
    """Send daily reminders to expired subscribers and non-subscribers"""
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    website_link = settings.get("website_link", "https://miraclecouplee.syke.club")
    
    if not bot_token:
        return
    
    logger.info("Starting daily reminders...")
    
    # Get plans for buttons
    plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
    
    buttons = []
    for plan in plans:
        plan_price = int(plan['price'])
        buttons.append([{"text": f"📦 {plan['name']} - ₹{plan_price}", "callback_data": f"buy_{plan['id']}"}])
    buttons.append([{"text": "🌐 Visit Website", "url": website_link}])
    buttons.append([{"text": "🎁 Special Discount!", "callback_data": "special_discount"}])
    
    sent_count = 0
    
    # 1. Expired subscribers
    expired_subs = await db.subscribers.find({
        "status": {"$in": ["expired", "grace"]}
    }, {"_id": 0}).to_list(10000)
    
    for sub in expired_subs:
        try:
            msg = "⚠️ <b>Subscription Expired!</b>\n\n"
            msg += f"Your {sub.get('plan_name', 'subscription')} has expired.\n\n"
            msg += f"🌐 <b>Visit:</b> {website_link}\n\n"
            msg += "🔥 <b>Don't miss out on exclusive content!</b>\n"
            msg += "Renew now to continue access:\n\n"
            
            await send_telegram_message_with_buttons(sub["telegram_user_id"], msg, buttons, bot_token)
            sent_count += 1
            await asyncio.sleep(0.2)  # Rate limiting
        except Exception as e:
            logger.error(f"Failed to send reminder to {sub.get('telegram_user_id')}: {e}")
    
    # 2. Subscribers expiring soon (within 3 days)
    three_days_later = datetime.now(timezone.utc) + timedelta(days=3)
    active_subs = await db.subscribers.find({"status": "active"}, {"_id": 0}).to_list(10000)
    
    for sub in active_subs:
        try:
            end_date = datetime.fromisoformat(sub["end_date"]) if isinstance(sub["end_date"], str) else sub["end_date"]
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            
            if end_date <= three_days_later:
                days_left = (end_date - datetime.now(timezone.utc)).days
                msg = f"⏰ <b>Subscription Expiring Soon!</b>\n\n"
                msg += f"Your {sub.get('plan_name', 'subscription')} expires in <b>{days_left} days</b>.\n\n"
                msg += f"🌐 <b>Visit:</b> {website_link}\n\n"
                msg += "🔄 <b>Renew now to avoid interruption:</b>\n\n"
                
                await send_telegram_message_with_buttons(sub["telegram_user_id"], msg, buttons, bot_token)
                sent_count += 1
                await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Failed to send expiry reminder: {e}")
    
    # 3. Non-subscribers who interacted but never bought
    # Get all user IDs from payments (pending/rejected)
    non_buyers = await db.payments.find({
        "status": {"$in": ["pending", "rejected"]}
    }, {"_id": 0, "telegram_user_id": 1}).to_list(10000)
    
    # Get active subscriber IDs
    active_ids = {s["telegram_user_id"] for s in await db.subscribers.find({"status": "active"}, {"telegram_user_id": 1}).to_list(10000)}
    
    sent_user_ids = set()
    for p in non_buyers:
        user_id = p.get("telegram_user_id")
        if user_id and user_id not in active_ids and user_id not in sent_user_ids:
            try:
                msg = "🔔 <b>You're Missing Out!</b>\n\n"
                msg += "We noticed you haven't subscribed yet.\n\n"
                msg += f"🌐 <b>Visit:</b> {website_link}\n\n"
                msg += "🔥 <b>Get exclusive content today!</b>\n"
                msg += "Limited time offers available:\n\n"
                
                await send_telegram_message_with_buttons(user_id, msg, buttons, bot_token)
                sent_user_ids.add(user_id)
                sent_count += 1
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.error(f"Failed to send non-buyer reminder: {e}")
    
    logger.info(f"Daily reminders completed: {sent_count} messages sent")

# ============== STARTUP/SHUTDOWN ==============

@app.on_event("startup")
async def startup():
    # Schedule tasks
    scheduler.add_job(check_subscriptions, 'interval', hours=6)
    scheduler.add_job(send_followups, 'cron', day_of_week='mon,thu', hour=10)
    scheduler.add_job(check_expired_chat_sessions, 'interval', seconds=30)
    
    # Daily reminders - 3 times a day (morning, afternoon, evening IST)
    scheduler.add_job(send_daily_reminders, 'cron', hour=9, minute=0)   # 9 AM
    scheduler.add_job(send_daily_reminders, 'cron', hour=14, minute=30) # 2:30 PM
    scheduler.add_job(send_daily_reminders, 'cron', hour=20, minute=0)  # 8 PM
    
    scheduler.start()
    logger.info("Scheduler started with daily reminders")

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()
    client.close()

# Include router
app.include_router(api_router)

# Mount static files for uploads
import os as os_module
uploads_dir = os_module.path.join(os_module.path.dirname(__file__), "uploads")
os_module.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
