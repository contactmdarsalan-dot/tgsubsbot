from fastapi import FastAPI, APIRouter, HTTPException, Depends, BackgroundTasks, Request, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import random
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

class SubscriptionPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    price: float
    duration_days: int
    features: List[str] = []
    is_active: bool = True
    channel_id: str = ""  # Each plan can have its own channel
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
    reminder_days_before: int = 3
    grace_period_days: int = 2
    followup_enabled: bool = True
    followup_message: str = "Check out our premium services!"

class MessageTemplate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str  # welcome, reminder, followup, expiry
    message: str
    is_active: bool = True

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
    """Get bot settings from database"""
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0})
    return settings or {}

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
    Use OCR to detect if image is a valid payment screenshot.
    Returns dict with is_valid and detected_keywords.
    More lenient detection to avoid false negatives.
    Includes image preprocessing for dark mode screenshots.
    """
    from PIL import ImageOps, ImageEnhance, ImageFilter
    
    # Payment-related keywords to look for (case-insensitive)
    payment_keywords = [
        # UPI Apps
        "gpay", "google pay", "phonepe", "paytm", "bhim", "amazon pay", "whatsapp pay",
        "phone pe", "g pay", "google", "amazon",
        # Transaction indicators
        "upi", "paid", "payment", "successful", "completed", "transaction",
        "transfer", "sent", "credited", "debited", "received", "to",
        # Amount indicators
        "₹", "inr", "rupee", "rs.", "rs ", "rs",
        # Transaction ID patterns
        "utr", "ref", "txn", "transaction id", "reference", "id",
        # Bank names (common)
        "sbi", "hdfc", "icici", "axis", "kotak", "pnb", "bob", "canara", "oksbi", "okaxis", "okicici",
        # Success messages
        "success", "done", "complete", "approved", "confirmed"
    ]
    
    try:
        # Open image from bytes
        image = Image.open(BytesIO(image_bytes))
        
        # Convert to RGB if necessary (for PNG with transparency)
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        
        # Create multiple versions of the image for better OCR
        images_to_try = []
        
        # Version 1: Original
        images_to_try.append(("original", image))
        
        # Version 2: Grayscale
        gray_image = image.convert('L')
        images_to_try.append(("grayscale", gray_image))
        
        # Version 3: Inverted (for dark mode screenshots)
        inverted_image = ImageOps.invert(image.convert('RGB'))
        images_to_try.append(("inverted", inverted_image))
        
        # Version 4: High contrast
        enhancer = ImageEnhance.Contrast(image)
        high_contrast = enhancer.enhance(2.0)
        images_to_try.append(("high_contrast", high_contrast))
        
        # Version 5: Inverted grayscale (best for dark screenshots)
        gray_inverted = ImageOps.invert(gray_image)
        images_to_try.append(("gray_inverted", gray_inverted))
        
        # Version 6: Binarized (threshold)
        threshold = gray_image.point(lambda x: 255 if x > 128 else 0, '1')
        images_to_try.append(("threshold", threshold))
        
        # Version 7: Inverted binarized
        inv_threshold = gray_inverted.point(lambda x: 255 if x > 128 else 0, '1')
        images_to_try.append(("inv_threshold", inv_threshold))
        
        # Try OCR on all versions and collect text
        extracted_text = ""
        
        for name, img in images_to_try:
            try:
                # Default config
                text = pytesseract.image_to_string(img, lang='eng')
                if text.strip():
                    extracted_text += " " + text
                    logger.info(f"OCR {name}: extracted {len(text)} chars")
                
                # PSM 6 config
                text2 = pytesseract.image_to_string(img, lang='eng', config='--psm 6')
                if text2.strip():
                    extracted_text += " " + text2
            except Exception as e:
                logger.debug(f"OCR {name} failed: {e}")
                pass
        
        text_lower = extracted_text.lower()
        
        logger.info(f"OCR extracted text (first 800 chars): {text_lower[:800]}")
        
        # Find matching keywords
        found_keywords = []
        for keyword in payment_keywords:
            if keyword.lower() in text_lower:
                found_keywords.append(keyword)
        
        # Check for amount pattern (₹XXX or Rs. XXX or just numbers with ₹)
        amount_patterns = [
            r'₹\s*\d+',
            r'rs\.?\s*\d+',
            r'\d+\s*₹',
            r'[₹]\d{1,6}',
            r'\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b'
        ]
        amounts = []
        for pattern in amount_patterns:
            found = re.findall(pattern, text_lower)
            amounts.extend(found)
        
        if amounts:
            found_keywords.append(f"amount_detected")
        
        # UPI ID pattern check (more flexible)
        upi_patterns = [
            r'[a-zA-Z0-9._-]+@[a-zA-Z]+',
            r'@ok[a-z]+',
            r'@paytm',
            r'@ybl',
            r'@upi'
        ]
        upi_ids = []
        for pattern in upi_patterns:
            found = re.findall(pattern, text_lower)
            upi_ids.extend(found)
        
        if upi_ids:
            found_keywords.append("upi_id_detected")
        
        # UTR/Transaction ID pattern
        utr_pattern = r'[a-zA-Z]?\d{12,22}'
        utrs = re.findall(utr_pattern, extracted_text)
        if utrs:
            found_keywords.append("utr_detected")
        
        # Determine if valid payment screenshot (MORE LENIENT)
        strong_app_indicators = ["gpay", "google pay", "phonepe", "paytm", "bhim", "amazon pay", "whatsapp pay", "phone pe", "g pay", "google"]
        strong_transaction_indicators = ["paid", "payment", "successful", "completed", "transaction", "transfer", "sent", "credited", "success", "done", "approved", "confirmed"]
        
        has_app = any(k.lower() in text_lower for k in strong_app_indicators)
        has_transaction = any(k.lower() in text_lower for k in strong_transaction_indicators)
        has_amount = bool(amounts)
        has_upi = "upi" in text_lower or bool(upi_ids)
        has_utr = bool(utrs)
        
        # RELAXED VALIDATION LOGIC
        is_valid = False
        
        # Rule 1: App name + any other indicator
        if has_app and (has_transaction or has_amount or has_upi or has_utr):
            is_valid = True
        
        # Rule 2: UPI + any other indicator
        if has_upi and (has_transaction or has_amount or has_app):
            is_valid = True
        
        # Rule 3: UTR number alone is strong indicator
        if has_utr and (has_amount or has_app or has_transaction):
            is_valid = True
        
        # Rule 4: Transaction word + amount
        if has_transaction and has_amount:
            is_valid = True
            
        # Rule 5: Found 2+ keywords (very lenient)
        if len(found_keywords) >= 2:
            is_valid = True
        
        # Rule 6: Contains "successful" or "success" - very strong indicator
        if "successful" in text_lower or "success" in text_lower:
            is_valid = True
        
        logger.info(f"OCR Result - is_valid: {is_valid}, keywords: {found_keywords}, has_app: {has_app}, has_transaction: {has_transaction}, has_amount: {has_amount}, has_upi: {has_upi}, has_utr: {has_utr}")
        
        return {
            "is_valid": is_valid,
            "found_keywords": found_keywords,
            "has_app": has_app,
            "has_transaction": has_transaction,
            "has_amount": has_amount,
            "has_upi": has_upi,
            "has_utr": has_utr,
            "extracted_text_preview": text_lower[:300]
        }
        
    except Exception as e:
        logger.error(f"OCR detection error: {e}")
        # On error, be lenient and allow manual verification
        return {
            "is_valid": False,
            "error": str(e),
            "found_keywords": [],
            "fallback_to_manual": True
        }


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
        
        # Buttons - Cancel always, Discount after 15 reminders
        buttons = []
        if i >= 14:  # After 15 reminders (0-indexed, so 14)
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
            renewal_msg += "Click below to renew your chat session!"
            
            # Send message in group
            try:
                async with httpx.AsyncClient() as http_client:
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    buttons = [[{"text": "🔄 Renew Chat", "callback_data": f"renew_chat_{session['id']}"}]]
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
    for p in payments:
        if isinstance(p.get('created_at'), str):
            p['created_at'] = datetime.fromisoformat(p['created_at'])
    return payments

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
    """Reject a pending payment"""
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Can only reject pending payments")
    
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

@api_router.post("/telegram/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        
        logger.info(f"Webhook received: {data}")
        
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
        promo_channel_id = settings.get("promo_channel_id", "")  # Public promo channel
        
        # Handle channel posts - Add Subscribe button ONLY on promo channel
        channel_post = data.get("channel_post")
        if channel_post and bot_token and promo_channel_id:
            post_chat_id = str(channel_post.get("chat", {}).get("id", ""))
            message_id = channel_post.get("message_id")
            
            # Only process posts from PROMO channel (not subscriber channel)
            if post_chat_id == promo_channel_id and message_id:
                # Wait a bit to ensure message is fully processed
                await asyncio.sleep(0.5)
                
                # Add Subscribe button by editing the message
                try:
                    bot_username = await get_bot_username(bot_token)
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
                        logger.info(f"Added subscribe button to promo channel post: {response.status_code}")
                except Exception as e:
                    logger.error(f"Failed to add subscribe button: {e}")
            
            return {"ok": True}
        
        # Skip old messages (older than 30 seconds)
        message = data.get("message") or data.get("callback_query", {}).get("message")
        if message:
            msg_date = message.get("date", 0)
            current_time = int(datetime.now(timezone.utc).timestamp())
            if current_time - msg_date > 30:
                logger.info(f"Skipping old message from {current_time - msg_date}s ago")
                return {"ok": True}
        
        # Handle callback queries (button clicks)
        callback_query = data.get("callback_query")
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
                    welcome_msg += f"📦 <b>{plan['name']}</b>\n"
                    welcome_msg += f"   💰 ₹{plan['price']} • ⏱ {plan['duration_days']} days\n\n"
                    buttons.append([{"text": f"📦 {plan['name']} - ₹{plan['price']}", "callback_data": f"buy_{plan['id']}"}])
                
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
                    inflated_price = plan['price'] + 500
                    actual_price = plan['price']
                    msg += f"📦 <b>{plan['name']}</b>\n"
                    msg += f"   <s>₹{inflated_price}</s> → 💰 <b>₹{actual_price}</b> 🔥\n\n"
                    buttons.append([{"text": f"🔥 {plan['name']} - ₹{actual_price}", "callback_data": f"buy_{plan['id']}"}])
                
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
            
            # Answer callback to remove loading state
            try:
                async with httpx.AsyncClient() as http_client:
                    await http_client.post(
                        f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery",
                        json={"callback_query_id": callback_query.get("id")}
                    )
            except:
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
            # Check if we're waiting for screenshot from this user
            pending = await db.pending_screenshots.find_one({"telegram_user_id": chat_id, "status": "waiting"}, {"_id": 0})
            
            if pending:
                plan_id = pending.get("plan_id")
                plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
                
                if plan:
                    # Get the photo file_id (largest size)
                    photo_file_id = photo[-1]["file_id"] if photo else None
                    
                    # Send processing message
                    await send_telegram_message(chat_id, "🔍 <b>Analyzing screenshot...</b>\n\nPlease wait while we verify your payment.", bot_token)
                    
                    # Download and analyze photo with OCR
                    image_bytes = await download_telegram_photo(photo_file_id, bot_token)
                    
                    if image_bytes:
                        # Run OCR detection
                        ocr_result = detect_payment_screenshot(image_bytes)
                        logger.info(f"OCR Result for user {chat_id}: {ocr_result}")
                        
                        if ocr_result.get("is_valid"):
                            # Valid payment screenshot detected - AUTO VERIFY
                            logger.info(f"Valid payment screenshot detected for user {chat_id}")
                            
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
                                "ocr_verified": True,
                                "ocr_keywords": ocr_result.get("found_keywords", []),
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
                                # Regular subscription plan - add to channel
                                success_msg = "✅ <b>Payment Verified Successfully!</b>\n\n"
                                success_msg += f"📦 Plan: <b>{plan['name']}</b>\n"
                                success_msg += f"💰 Amount: <b>₹{final_price}</b>\n"
                                success_msg += f"⏱ Duration: <b>{plan['duration_days']} days</b>\n\n"
                                success_msg += "🎉 <b>Your subscription is now active!</b>"
                                
                                await send_telegram_message(chat_id, success_msg, bot_token)
                                
                                # Add user to premium channel
                                plan_channel = plan.get("channel_id", "")
                                await add_to_channel(chat_id, plan_channel, plan['name'])
                            
                        else:
                            # Invalid screenshot - ask to send correct one
                            logger.info(f"Invalid screenshot for user {chat_id}: {ocr_result}")
                            
                            # Save photo file_id for reference
                            await db.pending_screenshots.update_one(
                                {"telegram_user_id": chat_id},
                                {"$set": {
                                    "last_invalid_photo": photo_file_id,
                                    "ocr_result": ocr_result
                                }}
                            )
                            
                            invalid_msg = "❌ <b>Invalid Screenshot!</b>\n\n"
                            invalid_msg += "Yeh payment screenshot nahi lagta.\n\n"
                            invalid_msg += "✅ <b>Valid screenshot mein hona chahiye:</b>\n"
                            invalid_msg += "• GPay / PhonePe / Paytm ka naam\n"
                            invalid_msg += "• 'Paid' ya 'Success' message\n"
                            invalid_msg += "• Transaction amount\n"
                            invalid_msg += "• UPI ID ya Reference number\n\n"
                            invalid_msg += "📸 <b>Sahi payment screenshot bhejo!</b>"
                            
                            buttons = [
                                [{"text": "❌ Cancel Payment", "callback_data": "cancel_payment"}]
                            ]
                            await send_telegram_message_with_buttons(chat_id, invalid_msg, buttons, bot_token)
                    else:
                        # Could not download image - fallback to manual confirmation
                        logger.error(f"Could not download image for user {chat_id}")
                        
                        await db.pending_screenshots.update_one(
                            {"telegram_user_id": chat_id},
                            {"$set": {
                                "status": "confirming",
                                "photo_file_id": photo_file_id
                            }}
                        )
                        
                        fallback_msg = "📸 <b>Image Received!</b>\n\n"
                        fallback_msg += "⚠️ Auto-verification fail hua. Manual confirm karo:\n\n"
                        fallback_msg += "✅ <b>Yes</b> - Agar payment screenshot hai\n"
                        fallback_msg += "❌ <b>No</b> - Agar kuch aur bheja hai"
                        
                        buttons = [
                            [
                                {"text": "✅ Yes, Payment SS", "callback_data": f"confirm_ss_{plan_id}"},
                                {"text": "❌ No", "callback_data": "wrong_ss"}
                            ]
                        ]
                        await send_telegram_message_with_buttons(chat_id, fallback_msg, buttons, bot_token)
                    
                    return {"ok": True}
            else:
                # User sent image but we're not waiting for it
                msg = "❌ <b>Screenshot not expected!</b>\n\n"
                msg += "Pehle plan select karo, phir QR code se payment karo, phir screenshot bhejo.\n\n"
                msg += "/start se shuru karo!"
                await send_telegram_message(chat_id, msg, bot_token)
                return {"ok": True}
        
        if text == "/start":
            plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
            
            welcome_msg = "🎉 <b>Welcome!</b>\n\n"
            welcome_msg += "🎯 <b>Choose Your Plan:</b>\n\n"
            
            buttons = []
            for plan in plans:
                inflated_price = plan['price'] + 500  # Show +500 price
                welcome_msg += f"📦 <b>{plan['name']}</b>\n"
                welcome_msg += f"   💰 ₹{inflated_price} • ⏱ {plan['duration_days']} days\n\n"
                buttons.append([{"text": f"📦 {plan['name']} - ₹{inflated_price}", "callback_data": f"buy_{plan['id']}"}])
            
            if not plans:
                welcome_msg += "No plans available at the moment.\n"
            
            # Add Special Discount button
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
            help_msg += "/share - Get shareable message\n"
            help_msg += "/help - Show this help message"
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
            except:
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

# ============== STARTUP/SHUTDOWN ==============

@app.on_event("startup")
async def startup():
    # Schedule tasks
    scheduler.add_job(check_subscriptions, 'interval', hours=6)
    scheduler.add_job(send_followups, 'cron', day_of_week='mon,thu', hour=10)
    scheduler.add_job(check_expired_chat_sessions, 'interval', seconds=30)  # Check every 30 seconds
    scheduler.start()
    logger.info("Scheduler started")

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
