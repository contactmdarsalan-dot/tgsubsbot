"""All Pydantic models for the application"""
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== PLAN MODELS ==============
class SubscriptionPlanCreate(BaseModel):
    name: str
    price: float
    duration_days: int
    features: List[str] = []
    is_active: bool = True
    channel_id: str = ""
    group_id: str = ""
    auto_assign_group: bool = False
    discount_percentage: int = 0

class SubscriptionPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    price: float
    duration_days: int
    features: List[str] = []
    is_active: bool = True
    channel_id: str = ""
    group_id: str = ""
    auto_assign_group: bool = False
    discount_percentage: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== SUBSCRIBER MODELS ==============
class SubscriberCreate(BaseModel):
    telegram_user_id: str
    telegram_username: Optional[str] = None
    plan_id: str
    payment_method: str = "manual"
    payment_id: Optional[str] = None

class Subscriber(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_user_id: str
    telegram_username: Optional[str] = None
    plan_id: str
    plan_name: str = ""
    status: str = "active"
    payment_method: str = "manual"
    payment_id: Optional[str] = None
    start_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    grace_end_date: Optional[datetime] = None
    reminder_sent: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== PAYMENT MODELS ==============
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
    status: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== BOT SETTINGS ==============
class BotSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = "bot_settings"
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""
    promo_channel_id: str = ""
    website_link: str = ""
    qr_code_url: str = ""
    payment_upi_id: str = ""
    reminder_days_before: int = 3
    grace_period_days: int = 2
    followup_enabled: bool = True
    followup_message: str = "Check out our premium services!"
    ai_auto_approve_threshold: int = 85
    support_username: str = ""
    welcome_message: str = "Welcome to our subscription bot! Use /plans to see available plans."
    payment_instructions: str = "Scan the QR code above and send payment screenshot here."
    success_message: str = "Payment verified! Your subscription is now active."
    video_call_enabled: bool = True
    video_call_price: float = 500
    video_call_duration: int = 30
    video_call_instructions: str = "Book a 1-on-1 video call with us! Choose a date and time."


class MessageTemplate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    message: str
    is_active: bool = True


# ============== COUPON ==============
class Coupon(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    code: str
    discount_type: str = "percentage"
    discount_value: float
    min_purchase: float = 0
    max_uses: int = 0
    used_count: int = 0
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    applicable_plans: List[str] = []
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== USER NOTES & TAGS ==============
class UserNote(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    note: str
    added_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserTag(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    color: str = "blue"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== CREATOR ==============
class Creator(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    telegram_user_id: str = ""
    telegram_username: str = ""
    email: str = ""
    role: str = "creator"
    permissions: List[str] = ["live_manage", "superchat_view"]
    revenue_share: float = 0
    total_earnings: float = 0
    is_active: bool = True
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== REFERRAL ==============
class Referral(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    referrer_id: str
    referrer_username: str
    referral_code: str
    referred_users: List[str] = []
    reward_type: str = "discount"
    reward_value: float = 10
    total_earnings: float = 0
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== SCHEDULED BROADCAST ==============
class ScheduledBroadcast(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    message: str
    target_segment: str = "all"
    scheduled_at: str
    status: str = "pending"
    sent_count: int = 0
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== FAQ ==============
class FAQ(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    keywords: List[str]
    response: str
    is_active: bool = True
    usage_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== BLOCKED USERS ==============
class BlockedUser(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_user_id: str
    telegram_username: str = ""
    reason: str = ""
    blocked_by: str
    blocked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== VIDEO CALL ==============
class VideoCallBooking(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_user_id: str
    telegram_username: str = ""
    user_name: str = ""
    plan_id: str = ""
    plan_name: str = ""
    call_type: str = "video"
    scheduled_date: str = ""
    scheduled_time: str = ""
    duration_minutes: int = 30
    price: float = 0
    status: str = "pending"
    meeting_link: str = ""
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== SUPPORT TICKET ==============
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


# ============== CHAT GROUP POOL ==============
class ChatGroupPool(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_id: str
    group_name: str = ""
    group_invite_link: str = ""
    status: str = "available"
    assigned_to_user_id: str = ""
    assigned_to_username: str = ""
    plan_type: str = ""
    session_start: Optional[datetime] = None
    session_end: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ActiveChatSession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    username: str = ""
    group_id: str
    plan_type: str
    duration_minutes: int
    start_time: datetime
    end_time: datetime
    status: str = "active"
    renewal_message_sent: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== PAID POST ==============
class PaidPost(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str
    original_message_id: int
    blurred_message_id: int = 0
    content_type: str = "photo"
    original_file_id: str = ""
    blurred_file_id: str = ""
    caption: str = ""
    price: float = 0
    unlock_count: int = 0
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PaidPostUnlock(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    post_id: str
    telegram_user_id: str
    telegram_username: str = ""
    payment_id: str = ""
    unlocked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== CHAT MESSAGE TRACKING ==============
class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_user_id: str
    telegram_username: str = ""
    user_first_name: str = ""
    chat_type: str = "private"
    group_id: str = ""
    group_name: str = ""
    message_text: str = ""
    message_type: str = "text"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
