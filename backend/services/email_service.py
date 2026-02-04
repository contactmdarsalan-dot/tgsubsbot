"""Email service using Resend"""
import os
import asyncio
import logging
import resend
from typing import Optional

logger = logging.getLogger(__name__)

# Initialize Resend
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    from_email: Optional[str] = None
) -> dict:
    """Send email using Resend API (non-blocking)"""
    if not RESEND_API_KEY:
        logger.warning("Resend API key not configured. Email not sent.")
        return {"status": "skipped", "message": "Email service not configured"}
    
    params = {
        "from": from_email or SENDER_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html_content
    }
    
    try:
        # Run sync SDK in thread to keep FastAPI non-blocking
        email = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email sent to {to_email}: {email.get('id')}")
        return {
            "status": "success",
            "message": f"Email sent to {to_email}",
            "email_id": email.get("id")
        }
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return {"status": "error", "message": str(e)}

# Email Templates
def get_welcome_email_html(user_name: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h1 style="color: #6366f1;">Welcome to SubsBot! 🎉</h1>
        <p>Hi {user_name},</p>
        <p>Thank you for joining SubsBot. You can now manage your Telegram subscriptions with ease.</p>
        <p style="margin-top: 20px;">
            <a href="#" style="background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px;">
                Go to Dashboard
            </a>
        </p>
        <p style="color: #666; margin-top: 30px;">Best regards,<br>SubsBot Team</p>
    </div>
    """

def get_payment_verified_email_html(user_name: str, plan_name: str, amount: float) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h1 style="color: #22c55e;">Payment Verified! ✅</h1>
        <p>Hi {user_name},</p>
        <p>Your payment has been verified successfully.</p>
        <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p><strong>Plan:</strong> {plan_name}</p>
            <p><strong>Amount:</strong> ₹{amount}</p>
        </div>
        <p>You now have access to the private channel. Enjoy!</p>
        <p style="color: #666; margin-top: 30px;">Best regards,<br>SubsBot Team</p>
    </div>
    """

def get_new_support_ticket_email_html(user_name: str, user_email: str, subject: str, message: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h1 style="color: #f59e0b;">New Support Ticket 🎫</h1>
        <p>A new support ticket has been submitted.</p>
        <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p><strong>From:</strong> {user_name} ({user_email})</p>
            <p><strong>Subject:</strong> {subject}</p>
            <p><strong>Message:</strong></p>
            <p style="background: white; padding: 15px; border-radius: 4px;">{message}</p>
        </div>
        <p>Please respond to this ticket from the admin dashboard.</p>
    </div>
    """

def get_subscription_expiry_email_html(user_name: str, plan_name: str, days_left: int) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h1 style="color: #ef4444;">Subscription Expiring Soon ⏰</h1>
        <p>Hi {user_name},</p>
        <p>Your <strong>{plan_name}</strong> subscription will expire in <strong>{days_left} days</strong>.</p>
        <p>Renew now to continue enjoying uninterrupted access.</p>
        <p style="margin-top: 20px;">
            <a href="#" style="background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px;">
                Renew Now
            </a>
        </p>
        <p style="color: #666; margin-top: 30px;">Best regards,<br>SubsBot Team</p>
    </div>
    """
