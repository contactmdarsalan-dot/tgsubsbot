"""CSV Export utilities"""
import csv
import io
from typing import List, Dict, Any
from datetime import datetime

def generate_subscribers_csv(subscribers: List[Dict[Any, Any]], plans: List[Dict[Any, Any]]) -> str:
    """Generate CSV for subscribers data"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Telegram ID',
        'Plan Name',
        'Status',
        'Start Date',
        'End Date',
        'Payment Method',
        'Created At'
    ])
    
    # Create plan lookup
    plan_lookup = {p['id']: p['name'] for p in plans}
    
    # Data rows
    for sub in subscribers:
        writer.writerow([
            sub.get('telegram_user_id', ''),
            plan_lookup.get(sub.get('plan_id', ''), sub.get('plan_id', '')),
            sub.get('status', ''),
            format_date(sub.get('start_date')),
            format_date(sub.get('end_date')),
            sub.get('payment_method', ''),
            format_date(sub.get('created_at'))
        ])
    
    return output.getvalue()

def generate_payments_csv(payments: List[Dict[Any, Any]], plans: List[Dict[Any, Any]]) -> str:
    """Generate CSV for payments data"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Payment ID',
        'Telegram ID',
        'Plan Name',
        'Amount (₹)',
        'Status',
        'Payment Method',
        'Razorpay Order ID',
        'Created At'
    ])
    
    # Create plan lookup
    plan_lookup = {p['id']: p['name'] for p in plans}
    
    # Data rows
    for payment in payments:
        writer.writerow([
            payment.get('id', ''),
            payment.get('telegram_user_id', ''),
            plan_lookup.get(payment.get('plan_id', ''), payment.get('plan_id', '')),
            payment.get('amount', 0),
            payment.get('status', ''),
            payment.get('payment_method', ''),
            payment.get('razorpay_order_id', ''),
            format_date(payment.get('created_at'))
        ])
    
    return output.getvalue()

def generate_users_csv(users: List[Dict[Any, Any]]) -> str:
    """Generate CSV for dashboard users data"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'User ID',
        'Name',
        'Email',
        'Phone',
        'Dashboard Plan',
        'Subscription Status',
        'Subscription End',
        'Is Admin',
        'Created At'
    ])
    
    # Data rows
    for user in users:
        writer.writerow([
            user.get('id', ''),
            user.get('name', ''),
            user.get('email', ''),
            user.get('phone', ''),
            user.get('dashboard_plan', ''),
            user.get('dashboard_subscription_status', ''),
            format_date(user.get('dashboard_subscription_end')),
            'Yes' if user.get('is_admin') else 'No',
            format_date(user.get('created_at'))
        ])
    
    return output.getvalue()

def generate_support_tickets_csv(tickets: List[Dict[Any, Any]]) -> str:
    """Generate CSV for support tickets data"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Ticket ID',
        'User Name',
        'User Email',
        'Subject',
        'Status',
        'Messages Count',
        'Created At'
    ])
    
    # Data rows
    for ticket in tickets:
        writer.writerow([
            ticket.get('id', ''),
            ticket.get('user_name', ''),
            ticket.get('user_email', ''),
            ticket.get('subject', ''),
            ticket.get('status', ''),
            len(ticket.get('messages', [])),
            format_date(ticket.get('created_at'))
        ])
    
    return output.getvalue()

def format_date(date_val) -> str:
    """Format date for CSV"""
    if not date_val:
        return ''
    if isinstance(date_val, str):
        try:
            date_val = datetime.fromisoformat(date_val.replace('Z', '+00:00'))
        except:
            return date_val
    if isinstance(date_val, datetime):
        return date_val.strftime('%Y-%m-%d %H:%M:%S')
    return str(date_val)
