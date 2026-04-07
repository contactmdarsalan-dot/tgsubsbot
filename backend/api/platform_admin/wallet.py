"""Wallet System — Central payment collection + tenant withdrawal management.

All payments flow to Super Admin's Razorpay account.
Tenants accumulate a virtual balance (minus platform commission).
Tenants request withdrawals → Super Admin approves/rejects → payout.
"""
from fastapi import APIRouter, HTTPException, Depends
from database import db
from services.auth import get_current_user
from services.permissions import ensure_super_admin, get_user_tenant, is_super_admin
from services.audit import log_action
from repositories.base import payments_repo
from config import logger
from datetime import datetime, timezone
import uuid

router = APIRouter()


# ============== WALLET CONFIG (Super Admin) ==============

DEFAULT_WALLET_CONFIG = {
    "id": "wallet_config",
    "commission_type": "percentage",  # "percentage" or "fixed"
    "commission_value": 10.0,         # 10% platform fee
    "min_withdrawal": 500,            # Min ₹500
    "max_withdrawal_per_day": 50000,  # Max ₹50,000/day
    "processing_days": 3,             # 3 business days
    "auto_approve_below": 0,          # 0 = always manual
    "payout_method": "manual",        # "manual" or "razorpay_payout"
    "updated_at": datetime.now(timezone.utc).isoformat(),
}


@router.get("/wallet/config")
async def get_wallet_config(user=Depends(get_current_user)):
    """Get wallet/withdrawal configuration (Super Admin only)."""
    ensure_super_admin(user)
    config = await db.wallet_config.find_one({"id": "wallet_config"}, {"_id": 0})
    return config or DEFAULT_WALLET_CONFIG


@router.put("/wallet/config")
async def update_wallet_config(data: dict, user=Depends(get_current_user)):
    """Update wallet/withdrawal rules (Super Admin only)."""
    ensure_super_admin(user)
    allowed_fields = [
        "commission_type", "commission_value", "min_withdrawal",
        "max_withdrawal_per_day", "processing_days", "auto_approve_below",
        "payout_method",
    ]
    update = {k: v for k, v in data.items() if k in allowed_fields}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.wallet_config.update_one(
        {"id": "wallet_config"},
        {"$set": update},
        upsert=True
    )
    await log_action("platform", user.get("id", ""), user.get("email", ""), "wallet_config_updated", "wallet_config", "wallet_config", metadata=update)
    return {"message": "Wallet config updated"}


# ============== TENANT WALLET BALANCE ==============

async def _get_wallet_config():
    """Internal helper to fetch wallet config."""
    config = await db.wallet_config.find_one({"id": "wallet_config"}, {"_id": 0})
    return config or DEFAULT_WALLET_CONFIG


async def _calculate_tenant_balance(tenant_id: str) -> dict:
    """Calculate a tenant's wallet balance from verified payments minus withdrawals."""
    config = await _get_wallet_config()
    commission_type = config.get("commission_type", "percentage")
    commission_value = float(config.get("commission_value", 10))

    # Sum all verified/approved payments for this tenant
    payment_pipeline = [
        {"$match": {"tenant_id": tenant_id, "status": {"$in": ["verified", "approved", "paid"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}
    ]
    result = await db.payments.aggregate(payment_pipeline).to_list(1)
    total_revenue = result[0]["total"] if result else 0
    payment_count = result[0]["count"] if result else 0

    # Calculate commission
    if commission_type == "percentage":
        commission = total_revenue * (commission_value / 100)
    else:
        commission = commission_value * payment_count

    net_earnings = total_revenue - commission

    # Sum approved withdrawals
    withdrawal_pipeline = [
        {"$match": {"tenant_id": tenant_id, "status": {"$in": ["approved", "processing", "completed"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    withdrawal_result = await db.withdrawal_requests.aggregate(withdrawal_pipeline).to_list(1)
    total_withdrawn = withdrawal_result[0]["total"] if withdrawal_result else 0

    # Pending withdrawals
    pending_pipeline = [
        {"$match": {"tenant_id": tenant_id, "status": "pending"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    pending_result = await db.withdrawal_requests.aggregate(pending_pipeline).to_list(1)
    pending_amount = pending_result[0]["total"] if pending_result else 0

    available_balance = net_earnings - total_withdrawn - pending_amount

    return {
        "total_revenue": round(total_revenue, 2),
        "commission_rate": f"{commission_value}{'%' if commission_type == 'percentage' else ' fixed'}",
        "total_commission": round(commission, 2),
        "net_earnings": round(net_earnings, 2),
        "total_withdrawn": round(total_withdrawn, 2),
        "pending_withdrawals": round(pending_amount, 2),
        "available_balance": round(available_balance, 2),
        "payment_count": payment_count,
    }


@router.get("/wallet/balance")
async def get_wallet_balance(user=Depends(get_current_user)):
    """Get current tenant's wallet balance."""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    balance = await _calculate_tenant_balance(tenant_id)
    return balance


@router.get("/wallet/balance/{tenant_id}")
async def get_tenant_wallet_balance(tenant_id: str, user=Depends(get_current_user)):
    """Get a specific tenant's wallet balance (Super Admin only)."""
    ensure_super_admin(user)
    balance = await _calculate_tenant_balance(tenant_id)
    return balance


# ============== WITHDRAWAL REQUESTS (Tenant) ==============

@router.post("/wallet/withdraw")
async def request_withdrawal(data: dict, user=Depends(get_current_user)):
    """Tenant requests a withdrawal from their available balance."""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")

    amount = float(data.get("amount", 0))
    bank_details = data.get("bank_details", {})
    notes = data.get("notes", "")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid withdrawal amount")

    # Validate against config
    config = await _get_wallet_config()
    min_withdrawal = config.get("min_withdrawal", 500)
    max_per_day = config.get("max_withdrawal_per_day", 50000)

    if amount < min_withdrawal:
        raise HTTPException(status_code=400, detail=f"Minimum withdrawal is ₹{min_withdrawal}")

    # Check daily limit
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_withdrawals = await db.withdrawal_requests.aggregate([
        {"$match": {
            "tenant_id": tenant_id,
            "created_at": {"$gte": today_start.isoformat()},
            "status": {"$in": ["pending", "approved", "processing", "completed"]}
        }},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]).to_list(1)
    today_total = today_withdrawals[0]["total"] if today_withdrawals else 0
    if today_total + amount > max_per_day:
        raise HTTPException(status_code=400, detail=f"Daily withdrawal limit ₹{max_per_day} exceeded")

    # Check available balance
    balance = await _calculate_tenant_balance(tenant_id)
    if amount > balance["available_balance"]:
        raise HTTPException(status_code=400, detail=f"Insufficient balance. Available: ₹{balance['available_balance']}")

    withdrawal = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "amount": amount,
        "bank_details": bank_details,
        "notes": notes,
        "status": "pending",
        "requested_by": user.get("email", ""),
        "requested_by_name": user.get("name", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Auto-approve if below threshold
    auto_approve = config.get("auto_approve_below", 0)
    if auto_approve > 0 and amount <= auto_approve:
        withdrawal["status"] = "approved"
        withdrawal["approved_at"] = datetime.now(timezone.utc).isoformat()
        withdrawal["approved_by"] = "system (auto-approve)"

    await db.withdrawal_requests.insert_one(withdrawal)
    withdrawal.pop("_id", None)

    await log_action(tenant_id, user.get("id", ""), user.get("email", ""), "withdrawal_requested", "withdrawal", withdrawal["id"], metadata={"amount": amount, "status": withdrawal["status"]})
    return {"message": "Withdrawal request submitted", "withdrawal": withdrawal}


@router.get("/wallet/withdrawals")
async def get_my_withdrawals(user=Depends(get_current_user)):
    """Get current tenant's withdrawal history."""
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated")
    withdrawals = await db.withdrawal_requests.find(
        {"tenant_id": tenant_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return withdrawals


# ============== WITHDRAWAL MANAGEMENT (Super Admin) ==============

@router.get("/wallet/all-withdrawals")
async def get_all_withdrawals(status: str = None, user=Depends(get_current_user)):
    """Get all withdrawal requests across all tenants (Super Admin only)."""
    ensure_super_admin(user)
    query = {}
    if status:
        query["status"] = status
    withdrawals = await db.withdrawal_requests.find(
        query, {"_id": 0}
    ).sort("created_at", -1).to_list(500)

    # Enrich with tenant info
    for w in withdrawals:
        tenant = await db.tenants.find_one({"tenant_id": w.get("tenant_id")}, {"_id": 0, "name": 1, "owner_email": 1})
        w["tenant_name"] = tenant.get("name", "Unknown") if tenant else "Unknown"
        w["tenant_email"] = tenant.get("owner_email", "") if tenant else ""

    return withdrawals


@router.put("/wallet/withdrawals/{withdrawal_id}/approve")
async def approve_withdrawal(withdrawal_id: str, data: dict = {}, user=Depends(get_current_user)):
    """Approve a withdrawal request (Super Admin only)."""
    ensure_super_admin(user)
    withdrawal = await db.withdrawal_requests.find_one({"id": withdrawal_id}, {"_id": 0})
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    if withdrawal["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot approve — status is '{withdrawal['status']}'")

    await db.withdrawal_requests.update_one(
        {"id": withdrawal_id},
        {"$set": {
            "status": "approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_by": user.get("email", ""),
            "admin_notes": data.get("notes", ""),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    await log_action("platform", user.get("id", ""), user.get("email", ""), "withdrawal_approved", "withdrawal", withdrawal_id, metadata={"amount": withdrawal["amount"]})
    return {"message": "Withdrawal approved"}


@router.put("/wallet/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(withdrawal_id: str, data: dict = {}, user=Depends(get_current_user)):
    """Reject a withdrawal request (Super Admin only)."""
    ensure_super_admin(user)
    withdrawal = await db.withdrawal_requests.find_one({"id": withdrawal_id}, {"_id": 0})
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    if withdrawal["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot reject — status is '{withdrawal['status']}'")

    await db.withdrawal_requests.update_one(
        {"id": withdrawal_id},
        {"$set": {
            "status": "rejected",
            "rejected_at": datetime.now(timezone.utc).isoformat(),
            "rejected_by": user.get("email", ""),
            "rejection_reason": data.get("reason", ""),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    await log_action("platform", user.get("id", ""), user.get("email", ""), "withdrawal_rejected", "withdrawal", withdrawal_id, metadata={"reason": data.get("reason", "")})
    return {"message": "Withdrawal rejected"}


@router.put("/wallet/withdrawals/{withdrawal_id}/complete")
async def complete_withdrawal(withdrawal_id: str, data: dict = {}, user=Depends(get_current_user)):
    """Mark an approved withdrawal as completed/paid (Super Admin only)."""
    ensure_super_admin(user)
    withdrawal = await db.withdrawal_requests.find_one({"id": withdrawal_id}, {"_id": 0})
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    if withdrawal["status"] != "approved":
        raise HTTPException(status_code=400, detail=f"Cannot complete — status is '{withdrawal['status']}'")

    await db.withdrawal_requests.update_one(
        {"id": withdrawal_id},
        {"$set": {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "transaction_ref": data.get("transaction_ref", ""),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    await log_action("platform", user.get("id", ""), user.get("email", ""), "withdrawal_completed", "withdrawal", withdrawal_id, metadata={"ref": data.get("transaction_ref", "")})
    return {"message": "Withdrawal marked as completed"}


# ============== PLATFORM REVENUE OVERVIEW (Super Admin) ==============

@router.get("/wallet/platform-revenue")
async def get_platform_revenue(user=Depends(get_current_user)):
    """Get overall platform revenue stats (Super Admin only)."""
    ensure_super_admin(user)
    config = await _get_wallet_config()

    # Total revenue across all tenants
    total_pipeline = [
        {"$match": {"status": {"$in": ["verified", "approved", "paid"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}
    ]
    total_result = await db.payments.aggregate(total_pipeline).to_list(1)
    total_revenue = total_result[0]["total"] if total_result else 0
    total_count = total_result[0]["count"] if total_result else 0

    # Revenue per tenant
    tenant_pipeline = [
        {"$match": {"status": {"$in": ["verified", "approved", "paid"]}}},
        {"$group": {"_id": "$tenant_id", "revenue": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        {"$sort": {"revenue": -1}}
    ]
    per_tenant = await db.payments.aggregate(tenant_pipeline).to_list(100)

    # Calculate commissions
    commission_type = config.get("commission_type", "percentage")
    commission_value = float(config.get("commission_value", 10))

    if commission_type == "percentage":
        total_commission = total_revenue * (commission_value / 100)
    else:
        total_commission = commission_value * total_count

    # Total payouts
    payout_pipeline = [
        {"$match": {"status": {"$in": ["approved", "completed"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    payout_result = await db.withdrawal_requests.aggregate(payout_pipeline).to_list(1)
    total_payouts = payout_result[0]["total"] if payout_result else 0

    # Pending payouts
    pending_pipeline = [
        {"$match": {"status": "pending"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}
    ]
    pending_result = await db.withdrawal_requests.aggregate(pending_pipeline).to_list(1)
    pending_payouts = pending_result[0]["total"] if pending_result else 0
    pending_count = pending_result[0]["count"] if pending_result else 0

    # Enrich per-tenant data
    tenant_breakdown = []
    for t in per_tenant:
        tid = t["_id"]
        tenant_info = await db.tenants.find_one({"tenant_id": tid}, {"_id": 0, "name": 1})
        if commission_type == "percentage":
            t_commission = t["revenue"] * (commission_value / 100)
        else:
            t_commission = commission_value * t["count"]
        tenant_breakdown.append({
            "tenant_id": tid,
            "tenant_name": tenant_info.get("name", "Unknown") if tenant_info else "Unknown",
            "revenue": round(t["revenue"], 2),
            "commission": round(t_commission, 2),
            "net_to_tenant": round(t["revenue"] - t_commission, 2),
            "payment_count": t["count"],
        })

    return {
        "total_revenue": round(total_revenue, 2),
        "total_commission": round(total_commission, 2),
        "platform_earnings": round(total_commission, 2),
        "total_payouts": round(total_payouts, 2),
        "pending_payouts": round(pending_payouts, 2),
        "pending_payout_count": pending_count,
        "commission_config": f"{commission_value}{'%' if commission_type == 'percentage' else ' fixed per txn'}",
        "tenant_breakdown": tenant_breakdown,
    }
