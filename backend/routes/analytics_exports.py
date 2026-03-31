"""Analytics, Revenue, Chat Tracking, Bot Activity, Export routes"""
from fastapi import APIRouter, Depends
from database import db
from services.auth import get_current_user
from services.permissions import get_user_tenant, tq
from config import logger
from datetime import datetime, timezone, timedelta
import uuid

router = APIRouter()


# ============== ANALYTICS / REVENUE APIs ==============

@router.get("/analytics/revenue")
async def get_revenue_analytics(user=Depends(get_current_user)):
    """Advanced revenue analytics with daily/weekly/monthly breakdowns"""
    now = datetime.now(timezone.utc)
    tenant_id = get_user_tenant(user)

    payments = await db.payments.find(
        tq({"status": "verified"}, tenant_id),
        {"_id": 0, "amount": 1, "created_at": 1, "plan_id": 1, "plan_name": 1}
    ).to_list(50000)

    subscribers = await db.subscribers.find(tq({}, tenant_id), {"_id": 0}).to_list(50000)
    plans = await db.plans.find(tq({}, tenant_id), {"_id": 0}).to_list(100)

    # Total metrics
    total_revenue = sum(p.get("amount", 0) for p in payments)
    total_payments = len(payments)

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    monthly_payments = [p for p in payments if str(p.get("created_at", "")) >= month_start]
    monthly_revenue = sum(p.get("amount", 0) for p in monthly_payments)

    last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
    last_month_end = now.replace(day=1).isoformat()
    last_month_payments = [p for p in payments if last_month_start <= str(p.get("created_at", "")) < last_month_end]
    last_month_revenue = sum(p.get("amount", 0) for p in last_month_payments)

    revenue_growth = 0
    if last_month_revenue > 0:
        revenue_growth = round(((monthly_revenue - last_month_revenue) / last_month_revenue) * 100, 1)

    # Daily chart (Last 30 days)
    daily_revenue = {}
    for p in payments:
        date = str(p.get("created_at", ""))[:10]
        if date:
            daily_revenue[date] = daily_revenue.get(date, 0) + p.get("amount", 0)

    daily_chart = []
    for i in range(30):
        date = (now - timedelta(days=29-i)).strftime("%Y-%m-%d")
        daily_chart.append({"date": date, "revenue": daily_revenue.get(date, 0)})

    # Weekly chart (Last 12 weeks)
    weekly_chart = []
    for w in range(12):
        week_end = now - timedelta(weeks=11-w)
        week_start = week_end - timedelta(days=6)
        week_rev = sum(
            p.get("amount", 0) for p in payments
            if week_start.strftime("%Y-%m-%d") <= str(p.get("created_at", ""))[:10] <= week_end.strftime("%Y-%m-%d")
        )
        weekly_chart.append({
            "week": f"W{12-11+w}",
            "label": f"{week_start.strftime('%d %b')} - {week_end.strftime('%d %b')}",
            "revenue": week_rev
        })

    # Monthly chart (Last 6 months)
    monthly_chart = []
    for m in range(6):
        month_date = now - timedelta(days=30 * (5 - m))
        m_start = month_date.replace(day=1).strftime("%Y-%m-%d")
        if m < 5:
            next_month = (month_date.replace(day=1) + timedelta(days=32)).replace(day=1)
            m_end = next_month.strftime("%Y-%m-%d")
        else:
            m_end = (now + timedelta(days=1)).strftime("%Y-%m-%d")

        m_rev = sum(
            p.get("amount", 0) for p in payments
            if m_start <= str(p.get("created_at", ""))[:10] < m_end
        )
        monthly_chart.append({
            "month": month_date.strftime("%b %Y"),
            "revenue": m_rev
        })

    # Plan performance
    plan_revenue = {}
    plan_count = {}
    for p in payments:
        pname = p.get("plan_name", p.get("plan_id", "Unknown"))
        plan_revenue[pname] = plan_revenue.get(pname, 0) + p.get("amount", 0)
        plan_count[pname] = plan_count.get(pname, 0) + 1

    plan_performance = [
        {"name": name, "revenue": rev, "sales": plan_count.get(name, 0)}
        for name, rev in sorted(plan_revenue.items(), key=lambda x: x[1], reverse=True)
    ]

    # Subscriber metrics
    active_subs = len([s for s in subscribers if s.get("status") == "active"])
    grace_subs = len([s for s in subscribers if s.get("status") == "grace"])
    expired_subs = len([s for s in subscribers if s.get("status") == "expired"])

    churn_rate = round((expired_subs / max(len(subscribers), 1)) * 100, 1)
    arpu = round(total_revenue / max(len(subscribers), 1), 0)

    avg_duration = 0
    for s in subscribers:
        try:
            start = s.get("start_date", "")
            end = s.get("end_date", "")
            if start and end:
                s_date = datetime.fromisoformat(str(start)) if isinstance(start, str) else start
                e_date = datetime.fromisoformat(str(end)) if isinstance(end, str) else end
                avg_duration += (e_date - s_date).days
        except Exception:
            pass
    avg_duration = avg_duration / max(len(subscribers), 1) / 30
    ltv = round(arpu * max(avg_duration, 1), 0)

    # Today's stats
    today = now.strftime("%Y-%m-%d")
    today_revenue = daily_revenue.get(today, 0)
    today_payments = len([p for p in payments if str(p.get("created_at", ""))[:10] == today])

    # Conversion funnel
    total_bot_users = await db.bot_users.count_documents({})
    total_pending = await db.payments.count_documents({"status": "pending"})

    funnel = [
        {"stage": "Bot Users", "count": total_bot_users},
        {"stage": "Payment Started", "count": total_pending + total_payments},
        {"stage": "Payment Verified", "count": total_payments},
        {"stage": "Active Subscribers", "count": active_subs},
    ]

    return {
        "total_revenue": total_revenue,
        "total_payments": total_payments,
        "monthly_revenue": monthly_revenue,
        "last_month_revenue": last_month_revenue,
        "revenue_growth": revenue_growth,
        "today_revenue": today_revenue,
        "today_payments": today_payments,
        "active_subscribers": active_subs,
        "grace_subscribers": grace_subs,
        "expired_subscribers": expired_subs,
        "churn_rate": churn_rate,
        "arpu": arpu,
        "ltv": ltv,
        "daily_chart": daily_chart,
        "weekly_chart": weekly_chart,
        "monthly_chart": monthly_chart,
        "plan_performance": plan_performance,
        "funnel": funnel
    }

@router.get("/analytics/users")
async def get_user_analytics(user=Depends(get_current_user)):
    """Get user growth analytics"""
    tenant_id = get_user_tenant(user)
    users = await db.bot_users.find(tq({}, tenant_id), {"_id": 0, "created_at": 1}).to_list(50000)

    daily_users = {}
    for u in users:
        date = str(u.get("created_at", ""))[:10]
        if date:
            daily_users[date] = daily_users.get(date, 0) + 1

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


# ============== EXPORT APIs ==============

@router.get("/export/subscribers")
async def export_subscribers(user=Depends(get_current_user)):
    """Export subscribers as CSV data"""
    tenant_id = get_user_tenant(user)
    subscribers = await db.subscribers.find(tq({}, tenant_id), {"_id": 0}).to_list(50000)

    csv_data = "telegram_user_id,username,plan_name,start_date,end_date,status\n"
    for s in subscribers:
        csv_data += f"{s.get('telegram_user_id','')},{s.get('username','')},{s.get('plan_name','')},{s.get('start_date','')},{s.get('end_date','')},{s.get('status','')}\n"

    return {"csv_data": csv_data, "count": len(subscribers)}

@router.get("/export/payments")
async def export_payments(user=Depends(get_current_user)):
    """Export payments as CSV data"""
    tenant_id = get_user_tenant(user)
    payments = await db.payments.find(tq({}, tenant_id), {"_id": 0}).to_list(50000)

    csv_data = "id,telegram_user_id,username,amount,plan_name,status,payment_method,created_at,verified_at\n"
    for p in payments:
        csv_data += f"{p.get('id','')},{p.get('telegram_user_id','')},{p.get('telegram_username','')},{p.get('amount','')},{p.get('plan_name','')},{p.get('status','')},{p.get('payment_method','')},{p.get('created_at','')},{p.get('verified_at','')}\n"

    return {"csv_data": csv_data, "count": len(payments)}

@router.get("/export/revenue-report")
async def export_revenue_report(user=Depends(get_current_user)):
    """Export full revenue report as CSV"""
    payments = await db.payments.find({"status": "verified"}, {"_id": 0}).to_list(50000)
    subscribers = await db.subscribers.find({}, {"_id": 0}).to_list(50000)

    revenue_csv = "Date,User ID,Username,Plan,Amount,Payment Method,Status\n"
    for p in sorted(payments, key=lambda x: x.get("created_at", ""), reverse=True):
        revenue_csv += f"{str(p.get('created_at',''))[:10]},{p.get('telegram_user_id','')},{p.get('telegram_username','')},{p.get('plan_name','')},{p.get('amount',0)},{p.get('payment_method','')},{p.get('status','')}\n"

    total_revenue = sum(p.get("amount", 0) for p in payments)
    active_count = len([s for s in subscribers if s.get("status") == "active"])

    summary = {
        "total_revenue": total_revenue,
        "total_payments": len(payments),
        "active_subscribers": active_count,
        "total_subscribers": len(subscribers),
        "generated_at": datetime.now(timezone.utc).isoformat()
    }

    return {"csv_data": revenue_csv, "summary": summary}


# ============== CHAT TRACKING API ==============

@router.get("/chat-messages")
async def get_chat_messages(user=Depends(get_current_user), limit: int = 100, chat_type: str = None):
    """Get chat messages from users"""
    query = {}
    if chat_type:
        query["chat_type"] = chat_type

    messages = await db.chat_messages.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return messages

@router.get("/chat-messages/stats")
async def get_chat_stats(user=Depends(get_current_user)):
    """Get chat statistics"""
    private_count = await db.chat_messages.count_documents({"chat_type": "private"})
    group_count = await db.chat_messages.count_documents({"chat_type": {"$in": ["group", "supergroup"]}})

    unique_users = await db.chat_messages.distinct("telegram_user_id")

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    recent_messages = await db.chat_messages.find(
        {"created_at": {"$gte": yesterday}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)

    return {
        "total_messages": private_count + group_count,
        "private_messages": private_count,
        "group_messages": group_count,
        "unique_users": len(unique_users),
        "recent_messages": recent_messages
    }

@router.get("/chat-messages/user/{user_id}")
async def get_user_chat_history(user_id: str, user=Depends(get_current_user)):
    """Get chat history for a specific user"""
    messages = await db.chat_messages.find(
        {"telegram_user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(100).to_list(100)
    return messages


# ============== BOT ACTIVITY LOGS ==============

@router.get("/bot-activity")
async def get_bot_activity(user=Depends(get_current_user), limit: int = 100, event_type: str = None):
    """Get bot activity logs"""
    query = {}
    if event_type:
        query["event_type"] = event_type

    logs = await db.bot_activity_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return logs

@router.get("/bot-activity/stats")
async def get_bot_activity_stats(user=Depends(get_current_user)):
    """Get bot activity stats for last 24 hours"""
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    total_24h = await db.bot_activity_logs.count_documents({"created_at": {"$gte": yesterday}})

    event_types = ["command", "payment_screenshot", "callback", "message", "payment_verified", "new_subscriber"]
    type_counts = {}
    for et in event_types:
        type_counts[et] = await db.bot_activity_logs.count_documents({
            "event_type": et,
            "created_at": {"$gte": yesterday}
        })

    active_users_24h = len(await db.bot_activity_logs.distinct("telegram_user_id", {"created_at": {"$gte": yesterday}}))
    total_all = await db.bot_activity_logs.count_documents({})

    return {
        "total_24h": total_24h,
        "total_all": total_all,
        "active_users_24h": active_users_24h,
        "by_type": type_counts
    }
