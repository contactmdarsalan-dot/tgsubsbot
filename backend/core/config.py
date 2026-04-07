"""
Configuration module - Environment variables, constants, and client initialization
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent  # /app/backend/
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("server")

# Environment mode
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development')

# JWT Secret — MUST be set in production
JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    if ENVIRONMENT == 'production':
        raise RuntimeError("FATAL: JWT_SECRET not set in production. Server cannot start without it.")
    JWT_SECRET = 'dev-only-unsafe-secret-do-not-use-in-prod'
    logger.warning("JWT_SECRET not set! Using unsafe dev default. Set JWT_SECRET in .env for production.")

# Telegram
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHANNEL_ID = os.environ.get('TELEGRAM_CHANNEL_ID', '')

# Emergent LLM Key
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Super Admin Emails (comma-separated in .env)
SUPER_ADMIN_EMAILS = [e.strip() for e in os.environ.get('SUPER_ADMIN_EMAILS', 'gamerxboys8958@gmail.com').split(',') if e.strip()]

# Razorpay
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')

# Twilio
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')

# Dashboard SaaS Plans
DASHBOARD_PLANS = {
    "1month": {"name": "1 Month", "price": 4999, "days": 30},
    "6month": {"name": "6 Months", "price": 24999, "days": 180},
    "12month": {"name": "12 Months", "price": 44999, "days": 365},
    "lifetime": {"name": "Lifetime", "price": 0, "days": 36500}
}

# Initialize optional clients
razorpay_client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    import razorpay
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    from twilio.rest import Client as TwilioClient
    twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
