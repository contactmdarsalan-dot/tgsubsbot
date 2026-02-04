"""Pydantic models for the application"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone
import uuid

# ============== USER MODELS ==============

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
    dashboard_plan: str = ""
    dashboard_subscription_end: Optional[datetime] = None
    dashboard_subscription_status: str = "inactive"
    is_admin: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============== PLAN MODELS ==============

class SubscriptionPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    price: float
    duration_days: int
    features: List[str] = []
    is_active: bool = True
    channel_id: str = ""

# ============== SUBSCRIBER MODELS ==============

class Subscriber(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_user_id: str
    telegram_chat_id: str = ""
    plan_id: str
    start_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_date: datetime = None
    status: str = "active"  # active, expired, grace, cancelled
    payment_method: str = "manual"
    payment_id: str = ""

# ============== PAYMENT MODELS ==============

class Payment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_user_id: str
    plan_id: str
    amount: float
    status: str = "pending"  # pending, verified, failed, rejected
    payment_method: str = "manual"  # manual, razorpay
    razorpay_order_id: str = ""
    razorpay_payment_id: str = ""
    screenshot_url: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============== BOT SETTINGS MODELS ==============

class BotSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = "bot_settings"
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""
    website_link: str = ""
    qr_code_url: str = ""
    reminder_days: int = 3
    grace_period_days: int = 2
    followup_enabled: bool = True
    reminder_enabled: bool = True

# ============== MESSAGE TEMPLATE MODELS ==============

class MessageTemplate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str  # welcome, reminder, followup, expiry
    message: str
    is_active: bool = True

# ============== SUPPORT TICKET MODELS ==============

class SupportTicket(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    user_email: str
    user_name: str
    subject: str
    messages: List[dict] = []
    status: str = "open"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============== EMAIL REQUEST MODEL ==============

class EmailRequest(BaseModel):
    recipient_email: str
    subject: str
    html_content: str
