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

class SubscriptionPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    price: float
    duration_days: int
    features: List[str] = []
    is_active: bool = True
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

async def send_telegram_message(chat_id: str, message: str):
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram bot token not configured")
        return False
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            response = await client.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send telegram message: {e}")
        return False

async def add_to_channel(user_id: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        return False
    try:
        # Create invite link for private channel
        async with httpx.AsyncClient() as client:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/createChatInviteLink"
            response = await client.post(url, json={
                "chat_id": TELEGRAM_CHANNEL_ID,
                "member_limit": 1,
                "expire_date": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp())
            })
            if response.status_code == 200:
                data = response.json()
                invite_link = data.get("result", {}).get("invite_link")
                if invite_link:
                    await send_telegram_message(user_id, f"Welcome! Join our premium channel: {invite_link}")
                    return True
        return False
    except Exception as e:
        logger.error(f"Failed to add user to channel: {e}")
        return False

async def remove_from_channel(user_id: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        return False
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/banChatMember"
            response = await client.post(url, json={
                "chat_id": TELEGRAM_CHANNEL_ID,
                "user_id": int(user_id),
                "until_date": int((datetime.now(timezone.utc) + timedelta(seconds=30)).timestamp())
            })
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
    
    # Send welcome message and channel invite
    background_tasks.add_task(add_to_channel, subscriber.telegram_user_id)
    website_link = settings.get("website_link", "")
    if website_link:
        background_tasks.add_task(send_telegram_message, subscriber.telegram_user_id, 
            f"Welcome to our premium subscription! Check out our services: {website_link}")
    
    return sub_obj

@api_router.put("/subscribers/{subscriber_id}/renew")
async def renew_subscriber(subscriber_id: str, plan_id: str, user = Depends(get_current_user)):
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
    
    return {"message": "Subscription renewed"}

@api_router.delete("/subscribers/{subscriber_id}")
async def delete_subscriber(subscriber_id: str, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    subscriber = await db.subscribers.find_one({"id": subscriber_id}, {"_id": 0})
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    await db.subscribers.delete_one({"id": subscriber_id})
    background_tasks.add_task(remove_from_channel, subscriber["telegram_user_id"])
    
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

@api_router.post("/telegram/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        message = data.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "")
        username = message.get("from", {}).get("username", "")
        
        if text == "/start":
            plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(10)
            settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
            
            plan_text = "\n".join([f"• {p['name']} - ₹{p['price']} ({p['duration_days']} days)" for p in plans])
            welcome_msg = f"Welcome! Available subscription plans:\n\n{plan_text}\n\nContact admin to subscribe."
            
            if settings.get("website_link"):
                welcome_msg += f"\n\nVisit: {settings['website_link']}"
            
            await send_telegram_message(chat_id, welcome_msg)
        
        elif text == "/status":
            subscriber = await db.subscribers.find_one({"telegram_user_id": chat_id}, {"_id": 0})
            if subscriber:
                end_date = datetime.fromisoformat(subscriber["end_date"]) if isinstance(subscriber["end_date"], str) else subscriber["end_date"]
                days_left = (end_date - datetime.now(timezone.utc)).days
                status_msg = f"Your subscription:\nPlan: {subscriber['plan_name']}\nStatus: {subscriber['status']}\nExpires: {end_date.strftime('%Y-%m-%d')}\nDays left: {days_left}"
            else:
                status_msg = "You don't have an active subscription."
            await send_telegram_message(chat_id, status_msg)
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"ok": False}

# ============== BACKGROUND TASKS ==============

async def check_subscriptions():
    """Check and update subscription statuses"""
    now = datetime.now(timezone.utc)
    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    reminder_days = settings.get("reminder_days_before", 3)
    
    subscribers = await db.subscribers.find({"status": {"$in": ["active", "grace"]}}, {"_id": 0}).to_list(10000)
    
    for sub in subscribers:
        end_date = datetime.fromisoformat(sub["end_date"]) if isinstance(sub["end_date"], str) else sub["end_date"]
        grace_end = datetime.fromisoformat(sub["grace_end_date"]) if isinstance(sub.get("grace_end_date"), str) else sub.get("grace_end_date")
        
        days_to_expiry = (end_date - now).days
        
        # Send reminder
        if days_to_expiry <= reminder_days and days_to_expiry > 0 and not sub.get("reminder_sent"):
            await send_telegram_message(sub["telegram_user_id"], 
                f"Your subscription expires in {days_to_expiry} days. Renew now to continue access!")
            await db.subscribers.update_one({"id": sub["id"]}, {"$set": {"reminder_sent": True}})
        
        # Move to grace period
        if now > end_date and sub["status"] == "active":
            await db.subscribers.update_one({"id": sub["id"]}, {"$set": {"status": "grace"}})
            await send_telegram_message(sub["telegram_user_id"], 
                "Your subscription has expired. You have a grace period to renew.")
        
        # Remove after grace period
        if grace_end and now > grace_end and sub["status"] == "grace":
            await db.subscribers.update_one({"id": sub["id"]}, {"$set": {"status": "expired"}})
            await remove_from_channel(sub["telegram_user_id"])
            await send_telegram_message(sub["telegram_user_id"], 
                "Your subscription and grace period have ended. Contact us to resubscribe.")

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
