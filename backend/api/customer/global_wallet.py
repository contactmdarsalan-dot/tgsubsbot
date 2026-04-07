"""Global App - Wallet & Coin System
Handles coin packages, wallet balance, transactions, spending, and revenue share.
"""
from fastapi import APIRouter, HTTPException, Depends
from database import db
from services.auth import get_current_user, create_token
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/global", tags=["Global Wallet"])


# ============== COIN PACKAGES (Admin configures) ==============

@router.get("/coin-packages")
async def get_coin_packages():
    """Public: List available coin packages for purchase."""
    packages = await db.coin_packages.find({"is_active": True}, {"_id": 0}).sort("coins", 1).to_list(50)
    return packages


@router.post("/coin-packages")
async def create_coin_package(data: dict, user=Depends(get_current_user)):
    """Admin: Create a coin package."""
    if user.get("role") not in ("super_admin", "tenant_admin"):
        raise HTTPException(403, "Admin access required")
    package = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", ""),
        "coins": int(data["coins"]),
        "price": float(data["price"]),
        "bonus_coins": int(data.get("bonus_coins", 0)),
        "is_active": True,
        "is_popular": data.get("is_popular", False),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.coin_packages.insert_one(package)
    package.pop("_id", None)
    return {"success": True, "package": package}


@router.put("/coin-packages/{package_id}")
async def update_coin_package(package_id: str, data: dict, user=Depends(get_current_user)):
    if user.get("role") not in ("super_admin", "tenant_admin"):
        raise HTTPException(403, "Admin access required")
    update = {k: v for k, v in data.items() if k in ("name", "coins", "price", "bonus_coins", "is_active", "is_popular")}
    result = await db.coin_packages.update_one({"id": package_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Package not found")
    return {"success": True}


@router.delete("/coin-packages/{package_id}")
async def delete_coin_package(package_id: str, user=Depends(get_current_user)):
    if user.get("role") not in ("super_admin", "tenant_admin"):
        raise HTTPException(403, "Admin access required")
    await db.coin_packages.delete_one({"id": package_id})
    return {"success": True}


# ============== WALLET ==============

async def get_or_create_wallet(user_id: str):
    """Get wallet for user, create if not exists."""
    wallet = await db.wallets.find_one({"user_id": user_id}, {"_id": 0})
    if not wallet:
        wallet = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "balance": 0,
            "total_earned": 0,
            "total_spent": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.wallets.insert_one(wallet)
        wallet.pop("_id", None)
    return wallet


@router.get("/wallet")
async def get_wallet(user=Depends(get_current_user)):
    """Get current user's wallet balance."""
    wallet = await get_or_create_wallet(user["id"])
    return wallet


@router.get("/wallet/transactions")
async def get_wallet_transactions(user=Depends(get_current_user), page: int = 1, limit: int = 50):
    """Get user's transaction history."""
    skip = (page - 1) * limit
    txns = await db.wallet_transactions.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.wallet_transactions.count_documents({"user_id": user["id"]})
    return {"transactions": txns, "total": total}


@router.post("/wallet/purchase-coins")
async def purchase_coins(data: dict, user=Depends(get_current_user)):
    """Initiate coin purchase. Creates a pending payment record."""
    package_id = data.get("package_id")
    package = await db.coin_packages.find_one({"id": package_id, "is_active": True}, {"_id": 0})
    if not package:
        raise HTTPException(404, "Package not found")

    payment = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_name": user.get("name", ""),
        "package_id": package_id,
        "package_name": package.get("name", ""),
        "coins": package["coins"] + package.get("bonus_coins", 0),
        "amount": package["price"],
        "status": "pending",
        "payment_method": data.get("payment_method", "manual"),
        "screenshot_url": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.coin_payments.insert_one(payment)
    payment.pop("_id", None)
    return {"success": True, "payment": payment}


@router.post("/wallet/upload-proof/{payment_id}")
async def upload_coin_payment_proof(payment_id: str, data: dict, user=Depends(get_current_user)):
    """Upload payment proof (screenshot URL) for coin purchase."""
    payment = await db.coin_payments.find_one({"id": payment_id, "user_id": user["id"]}, {"_id": 0})
    if not payment:
        raise HTTPException(404, "Payment not found")
    if payment["status"] != "pending":
        raise HTTPException(400, "Payment already processed")

    await db.coin_payments.update_one(
        {"id": payment_id},
        {"$set": {"screenshot_url": data.get("screenshot_url", ""), "status": "proof_submitted"}}
    )
    return {"success": True}


@router.get("/wallet/coin-payments")
async def get_coin_payments(user=Depends(get_current_user), status: str = None, page: int = 1, limit: int = 50):
    """Get user's coin purchase history."""
    query = {"user_id": user["id"]}
    if status:
        query["status"] = status
    skip = (page - 1) * limit
    payments = await db.coin_payments.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.coin_payments.count_documents(query)
    return {"payments": payments, "total": total}


# ============== ADMIN: Coin Payment Approval ==============

@router.get("/admin/coin-payments")
async def admin_list_coin_payments(user=Depends(get_current_user), status: str = "proof_submitted", page: int = 1, limit: int = 50):
    """Admin: List pending coin payments for approval."""
    if user.get("role") not in ("super_admin", "tenant_admin"):
        raise HTTPException(403, "Admin access required")
    query = {}
    if status != "all":
        query["status"] = status
    skip = (page - 1) * limit
    payments = await db.coin_payments.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.coin_payments.count_documents(query)
    return {"payments": payments, "total": total}


@router.post("/admin/coin-payments/{payment_id}/approve")
async def admin_approve_coin_payment(payment_id: str, user=Depends(get_current_user)):
    """Admin: Approve coin purchase and credit wallet."""
    if user.get("role") not in ("super_admin", "tenant_admin"):
        raise HTTPException(403, "Admin access required")

    payment = await db.coin_payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(404, "Payment not found")
    if payment["status"] == "approved":
        raise HTTPException(400, "Already approved")

    # Credit wallet
    wallet = await get_or_create_wallet(payment["user_id"])
    coins = payment["coins"]
    await db.wallets.update_one(
        {"user_id": payment["user_id"]},
        {"$inc": {"balance": coins, "total_earned": coins}}
    )

    # Record transaction
    txn = {
        "id": str(uuid.uuid4()),
        "user_id": payment["user_id"],
        "type": "credit",
        "amount": coins,
        "description": f"Purchased {coins} coins",
        "reference_type": "coin_purchase",
        "reference_id": payment_id,
        "balance_after": wallet["balance"] + coins,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.wallet_transactions.insert_one(txn)

    # Update payment status
    await db.coin_payments.update_one(
        {"id": payment_id},
        {"$set": {"status": "approved", "approved_by": user.get("name", ""), "approved_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"success": True, "coins_credited": coins}


@router.post("/admin/coin-payments/{payment_id}/reject")
async def admin_reject_coin_payment(payment_id: str, data: dict, user=Depends(get_current_user)):
    """Admin: Reject coin purchase."""
    if user.get("role") not in ("super_admin", "tenant_admin"):
        raise HTTPException(403, "Admin access required")
    await db.coin_payments.update_one(
        {"id": payment_id},
        {"$set": {"status": "rejected", "reject_reason": data.get("reason", ""), "rejected_by": user.get("name", "")}}
    )
    return {"success": True}


# ============== SPEND COINS (Internal helper) ==============

async def spend_coins(user_id: str, amount: int, description: str, ref_type: str, ref_id: str):
    """Deduct coins from user's wallet. Returns True if successful."""
    wallet = await get_or_create_wallet(user_id)
    if wallet["balance"] < amount:
        return False, "Insufficient coins"

    await db.wallets.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": -amount, "total_spent": amount}}
    )

    txn = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "debit",
        "amount": amount,
        "description": description,
        "reference_type": ref_type,
        "reference_id": ref_id,
        "balance_after": wallet["balance"] - amount,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.wallet_transactions.insert_one(txn)
    return True, "Success"


async def credit_creator_revenue(creator_id: str, amount: int, description: str, ref_type: str, ref_id: str):
    """Credit a portion of coins to creator's wallet after revenue share."""
    config = await db.global_config.find_one({"id": "revenue_share"}, {"_id": 0})
    platform_share = config.get("platform_percentage", 20) if config else 20
    creator_share_pct = 100 - platform_share
    creator_coins = int(amount * creator_share_pct / 100)
    platform_coins = amount - creator_coins

    # Credit creator
    wallet = await get_or_create_wallet(creator_id)
    await db.wallets.update_one(
        {"user_id": creator_id},
        {"$inc": {"balance": creator_coins, "total_earned": creator_coins}}
    )
    txn = {
        "id": str(uuid.uuid4()),
        "user_id": creator_id,
        "type": "credit",
        "amount": creator_coins,
        "description": f"Revenue: {description} ({creator_share_pct}%)",
        "reference_type": ref_type,
        "reference_id": ref_id,
        "balance_after": wallet["balance"] + creator_coins,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.wallet_transactions.insert_one(txn)

    # Track platform revenue
    await db.platform_revenue.insert_one({
        "id": str(uuid.uuid4()),
        "creator_id": creator_id,
        "total_amount": amount,
        "platform_coins": platform_coins,
        "creator_coins": creator_coins,
        "reference_type": ref_type,
        "reference_id": ref_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return creator_coins, platform_coins


# ============== REVENUE SHARE CONFIG (Super Admin) ==============

@router.get("/admin/revenue-config")
async def get_revenue_config(user=Depends(get_current_user)):
    if user.get("role") != "super_admin":
        raise HTTPException(403, "Super admin required")
    config = await db.global_config.find_one({"id": "revenue_share"}, {"_id": 0})
    if not config:
        config = {"id": "revenue_share", "platform_percentage": 20, "min_withdrawal": 500}
    return config


@router.put("/admin/revenue-config")
async def update_revenue_config(data: dict, user=Depends(get_current_user)):
    if user.get("role") != "super_admin":
        raise HTTPException(403, "Super admin required")
    await db.global_config.update_one(
        {"id": "revenue_share"},
        {"$set": {
            "platform_percentage": data.get("platform_percentage", 20),
            "min_withdrawal": data.get("min_withdrawal", 500),
        }},
        upsert=True
    )
    return {"success": True}


# ============== ADMIN STATS ==============

@router.get("/admin/wallet-stats")
async def admin_wallet_stats(user=Depends(get_current_user)):
    """Admin: Get global wallet statistics."""
    if user.get("role") not in ("super_admin",):
        raise HTTPException(403, "Super admin required")

    total_wallets = await db.wallets.count_documents({})
    pipeline = [{"$group": {"_id": None, "total_balance": {"$sum": "$balance"}, "total_spent": {"$sum": "$total_spent"}, "total_earned": {"$sum": "$total_earned"}}}]
    result = await db.wallets.aggregate(pipeline).to_list(1)
    stats = result[0] if result else {"total_balance": 0, "total_spent": 0, "total_earned": 0}

    pending_payments = await db.coin_payments.count_documents({"status": "proof_submitted"})
    platform_rev = await db.platform_revenue.aggregate([{"$group": {"_id": None, "total": {"$sum": "$platform_coins"}}}]).to_list(1)

    return {
        "total_wallets": total_wallets,
        "total_coins_in_circulation": stats.get("total_balance", 0),
        "total_coins_spent": stats.get("total_spent", 0),
        "total_coins_purchased": stats.get("total_earned", 0),
        "pending_approvals": pending_payments,
        "platform_revenue_coins": platform_rev[0]["total"] if platform_rev else 0,
    }
