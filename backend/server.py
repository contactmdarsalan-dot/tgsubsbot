from fastapi import FastAPI, APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
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

class UserLogin(BaseModel):
    email: str
    password: str

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    telegram_channel_id: str = ""
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

async def get_bot_settings():
    """Get bot settings from database"""
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0})
    return settings or {}

async def send_telegram_message(chat_id: str, message: str, bot_token: str = None):
    """Send message via Telegram Bot API"""
    if not bot_token:
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
    
    if not bot_token:
        logger.warning("Telegram bot token not configured")
        return False
    try:
        async with httpx.AsyncClient() as http_client:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            response = await http_client.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})
            logger.info(f"Telegram sendMessage response: {response.status_code} - {response.text}")
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send telegram message: {e}")
        return False

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


# ============== AUTH ROUTES ==============

@api_router.post("/auth/register")
async def register(user: UserCreate):
    existing = await db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_obj = User(email=user.email, name=user.name)
    doc = user_obj.model_dump()
    doc["password_hash"] = hash_password(user.password)
    doc["created_at"] = doc["created_at"].isoformat()
    
    await db.users.insert_one(doc)
    token = create_token(user_obj.id)
    return {"token": token, "user": {"id": user_obj.id, "email": user_obj.email, "name": user_obj.name}}

@api_router.post("/auth/login")
async def login(user: UserLogin):
    existing = await db.users.find_one({"email": user.email}, {"_id": 0})
    if not existing or not verify_password(user.password, existing.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(existing["id"])
    return {"token": token, "user": {"id": existing["id"], "email": existing["email"], "name": existing["name"]}}

@api_router.get("/auth/me")
async def get_me(user = Depends(get_current_user)):
    return {"id": user["id"], "email": user["email"], "name": user["name"]}

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

# ============== PAYMENTS ROUTES ==============

@api_router.get("/payments")
async def get_payments(status: Optional[str] = None, user = Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    payments = await db.payments.find(query, {"_id": 0}).to_list(1000)
    for p in payments:
        if isinstance(p.get('created_at'), str):
            p['created_at'] = datetime.fromisoformat(p['created_at'])
    return payments

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

async def send_telegram_message_with_buttons(chat_id: str, message: str, buttons: list = None, bot_token: str = None):
    """Send message with inline keyboard buttons"""
    if not bot_token:
        settings = await get_bot_settings()
        bot_token = settings.get("telegram_bot_token", "")
    
    if not bot_token:
        return False
    
    try:
        async with httpx.AsyncClient() as http_client:
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
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        return False

@api_router.post("/telegram/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        logger.info(f"Webhook received: {data}")
        
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
                # Send QR code image
                qr_url = settings.get("qr_code_url", "")
                if qr_url:
                    try:
                        async with httpx.AsyncClient() as http_client:
                            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                            await http_client.post(url, json={
                                "chat_id": chat_id,
                                "photo": qr_url,
                                "caption": "📱 Scan this QR code to pay\n\nAfter payment, click 'I've Paid' button"
                            })
                    except:
                        await send_telegram_message(chat_id, f"QR Code: {qr_url}", bot_token)
            
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
        
        if not chat_id:
            return {"ok": True}
        
        if text == "/start":
            plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
            
            welcome_msg = "🎉 <b>Welcome!</b>\n\n"
            welcome_msg += "🎯 <b>Choose Your Plan:</b>\n\n"
            
            buttons = []
            for plan in plans:
                welcome_msg += f"📦 <b>{plan['name']}</b>\n"
                welcome_msg += f"   💰 ₹{plan['price']} • ⏱ {plan['duration_days']} days\n\n"
                buttons.append([{"text": f"📦 {plan['name']} - ₹{plan['price']}", "callback_data": f"buy_{plan['id']}"}])
            
            if not plans:
                welcome_msg += "No plans available at the moment.\n"
            
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
    scheduler.start()
    logger.info("Scheduler started")

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()
    client.close()

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
