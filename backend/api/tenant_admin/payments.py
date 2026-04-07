"""Payments CRUD, verification, Razorpay, bot checkout, bulk operations — Repository pattern"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from database import db
from services.auth import get_current_user
from services.telegram import get_bot_settings, send_telegram_message, add_to_channel, notify_admin_new_payment, kick_user_from_channel
from services.chat_pool import kick_user_from_group, release_chat_group
from services.permissions import get_user_tenant, tq, ensure_admin
from repositories.base import payments_repo
from config import logger, RAZORPAY_KEY_ID, razorpay_client
from models import SubscriberCreate, Subscriber, PaymentCreate, Payment
from datetime import datetime, timezone, timedelta
import uuid
import httpx

router = APIRouter()


@router.get("/payments")
async def get_payments(status=None, page: int = 1, limit: int = 50, search: str = None, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    base_query = tq({"source": {"$ne": "miniapp"}}, tenant_id)
    
    # Build filter query for listing
    list_query = dict(base_query)
    if status:
        list_query["status"] = status
    if search:
        search = search.strip()
        list_query["$or"] = [
            {"telegram_user_id": {"$regex": search, "$options": "i"}},
            {"telegram_username": {"$regex": search, "$options": "i"}},
        ]
    
    # Pagination
    skip = (max(1, page) - 1) * limit
    limit = min(limit, 200)  # Max 200 per page
    
    # Fetch paginated payments
    payments = await db.payments.find(list_query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    for p in payments:
        if isinstance(p.get('created_at'), str):
            p['created_at'] = datetime.fromisoformat(p['created_at'])
        p['has_screenshot'] = bool(p.get('screenshot_file_id') or p.get('screenshot_url'))
    
    # Server-side counts (from ALL data, not just current page)
    total_count = await db.payments.count_documents(list_query)
    
    # Stats from ALL payments (no status/search filter, just tenant)
    all_query = dict(base_query)
    total_all = await db.payments.count_documents(all_query)
    pending_count = await db.payments.count_documents({**base_query, "status": "pending"})
    
    # Revenue from verified payments
    revenue_pipeline = [
        {"$match": {**base_query, "status": {"$in": ["verified", "approved"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    rev_result = await db.payments.aggregate(revenue_pipeline).to_list(1)
    total_collected = rev_result[0]["total"] if rev_result else 0
    
    return {
        "payments": payments,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit if limit > 0 else 1,
        "stats": {
            "total_collected": total_collected,
            "pending_count": pending_count,
            "total_transactions": total_all
        }
    }


@router.get("/payments/{payment_id}/screenshot")
async def get_payment_screenshot(payment_id: str, user=Depends(get_current_user)):
    """Get screenshot URL for a payment"""
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if not payment.get("screenshot_file_id"):
        raise HTTPException(status_code=404, detail="No screenshot available")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot token not configured")

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={payment['screenshot_file_id']}"
            response = await http_client.get(file_info_url)
            if response.status_code == 200:
                file_path = response.json().get("result", {}).get("file_path")
                if file_path:
                    download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
                    return {"screenshot_url": download_url}
    except Exception as e:
        logger.error(f"Error getting screenshot: {e}")

    raise HTTPException(status_code=400, detail="Could not retrieve screenshot")


@router.put("/payments/{payment_id}/unverify")
async def unverify_payment(payment_id: str, user=Depends(get_current_user)):
    """Unverify a payment - changes status back to rejected AND kick user from channel"""
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.get("status") != "verified":
        raise HTTPException(status_code=400, detail="Payment is not verified")

    telegram_user_id = payment.get("telegram_user_id")

    await db.payments.update_one(
        {"id": payment_id},
        {"$set": {
            "status": "rejected",
            "unverified_at": datetime.now(timezone.utc).isoformat(),
            "unverified_by": user.get("email", "admin"),
            "rejection_reason": "Unverified by admin after review"
        }}
    )

    if telegram_user_id:
        await db.subscribers.delete_one({"telegram_user_id": telegram_user_id, "plan_id": payment.get("plan_id")})

    kicked = False
    if telegram_user_id:
        kicked = await kick_user_from_channel(telegram_user_id)
        logger.info(f"Kicked user {telegram_user_id} from channel: {kicked}")

        assigned_group = await db.chat_groups_pool.find_one(
            {"assigned_to_user_id": telegram_user_id},
            {"_id": 0}
        )
        if assigned_group:
            await kick_user_from_group(assigned_group["group_id"], telegram_user_id)
            await release_chat_group(assigned_group["group_id"])

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if bot_token and telegram_user_id:
        msg = "<b>Payment Rejected</b>\n\n"
        msg += f"Your payment for {payment.get('plan_name', 'subscription')} has been rejected after review.\n\n"
        msg += "You have been removed from the channel.\n"
        msg += "Contact support if you believe this is a mistake."
        await send_telegram_message(telegram_user_id, msg, bot_token)

    return {
        "message": "Payment unverified and user kicked from channel",
        "user_kicked": kicked
    }


# ============== BOT CHECKOUT ROUTES ==============

@router.get("/bot-checkout/{order_id}")
async def get_bot_checkout(order_id: str):
    """Get order details for bot checkout page"""
    order = await db.bot_orders.find_one({"razorpay_order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    plan = await db.plans.find_one({"id": order["plan_id"]}, {"_id": 0})

    return {
        "order_id": order_id,
        "plan_id": order["plan_id"],
        "plan_name": order.get("plan_name", plan["name"] if plan else ""),
        "amount": order["amount"],
        "key_id": RAZORPAY_KEY_ID,
        "telegram_user_id": order.get("telegram_user_id", "")
    }


@router.post("/bot-checkout/verify")
async def verify_bot_checkout(data: dict, background_tasks: BackgroundTasks):
    """Verify Razorpay payment and activate subscription — idempotent"""
    if not razorpay_client:
        raise HTTPException(status_code=400, detail="Razorpay not configured")

    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })
    except Exception as e:
        logger.error(f"Payment verification failed: {e}")
        raise HTTPException(status_code=400, detail="Payment verification failed")

    order = await db.bot_orders.find_one({"razorpay_order_id": data['razorpay_order_id']}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Idempotency: if already paid, return success without re-processing
    if order.get("status") == "paid":
        return {"success": True, "message": "Subscription already activated"}

    await db.bot_orders.update_one(
        {"razorpay_order_id": data['razorpay_order_id']},
        {"$set": {"status": "paid", "razorpay_payment_id": data['razorpay_payment_id']}}
    )

    plan = await db.plans.find_one({"id": order["plan_id"]}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    telegram_user_id = data.get("telegram_user_id") or order.get("telegram_user_id")
    telegram_username = order.get("telegram_username", "")

    payment_obj = {
        "id": str(uuid.uuid4()),
        "subscriber_id": None,
        "telegram_user_id": telegram_user_id,
        "telegram_username": telegram_username,
        "amount": order["amount"],
        "plan_id": order["plan_id"],
        "plan_name": plan["name"],
        "payment_method": "razorpay",
        "razorpay_order_id": data['razorpay_order_id'],
        "razorpay_payment_id": data['razorpay_payment_id'],
        "status": "verified",
        "tenant_id": plan.get("tenant_id", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payments.insert_one(payment_obj)

    settings = await db.settings.find_one({"id": "bot_settings"}, {"_id": 0}) or {}
    grace_days = settings.get("grace_period_days", 2)
    bot_token = settings.get("telegram_bot_token", "")

    end_date = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])
    grace_end = end_date + timedelta(days=grace_days)

    subscriber_obj = {
        "id": str(uuid.uuid4()),
        "telegram_user_id": telegram_user_id,
        "telegram_username": telegram_username,
        "plan_id": plan["id"],
        "plan_name": plan["name"],
        "payment_method": "razorpay",
        "payment_id": payment_obj["id"],
        "status": "active",
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": end_date.isoformat(),
        "grace_end_date": grace_end.isoformat(),
        "reminder_sent": False,
        "tenant_id": plan.get("tenant_id", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.subscribers.insert_one(subscriber_obj)

    plan_channel = plan.get("channel_id", "")
    if plan_channel and bot_token:
        background_tasks.add_task(add_to_channel, telegram_user_id, plan_channel, plan["name"])

    if bot_token and telegram_user_id:
        success_msg = "<b>Payment Successful!</b>\n\n"
        success_msg += f"Plan: <b>{plan['name']}</b>\n"
        success_msg += f"Amount: <b>Rs.{order['amount']}</b>\n"
        success_msg += f"Valid till: <b>{end_date.strftime('%d %b %Y')}</b>\n\n"
        success_msg += "Your subscription is now active!\n"
        success_msg += "You will receive channel invite link shortly."
        await send_telegram_message(telegram_user_id, success_msg, bot_token)

    logger.info(f"Bot subscription activated for user {telegram_user_id}, plan {plan['name']}")

    return {"success": True, "message": "Subscription activated"}


@router.post("/payments/create-order")
async def create_razorpay_order(payment: PaymentCreate, user=Depends(get_current_user)):
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
    plan_for_tenant = await db.plans.find_one({"id": payment.plan_id}, {"_id": 0, "tenant_id": 1})
    doc['tenant_id'] = (plan_for_tenant or {}).get("tenant_id") or user.get("tenant_id", "")
    await db.payments.insert_one(doc)

    return {"order_id": order["id"], "payment_id": payment_obj.id, "key_id": RAZORPAY_KEY_ID}


@router.post("/payments/verify")
async def verify_razorpay_payment(data: dict, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    """Verify Razorpay payment — idempotent"""
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

    # Idempotency: already verified
    if payment.get("status") == "verified":
        return {"message": "Payment already verified"}

    await db.payments.update_one(
        {"razorpay_order_id": data['razorpay_order_id']},
        {"$set": {"status": "verified", "razorpay_payment_id": data['razorpay_payment_id']}}
    )

    plan = await db.plans.find_one({"id": payment["plan_id"]}, {"_id": 0})
    if plan:
        subscriber_create = SubscriberCreate(
            telegram_user_id=payment["telegram_user_id"],
            plan_id=payment["plan_id"],
            payment_method="razorpay",
            payment_id=payment["id"]
        )
        from api.tenant_admin.subscribers import create_subscriber
        await create_subscriber(subscriber_create, background_tasks)

    return {"message": "Payment verified"}


@router.post("/payments/manual")
async def create_manual_payment(payment: PaymentCreate, user=Depends(get_current_user)):
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
    plan_for_tenant = await db.plans.find_one({"id": payment.plan_id}, {"_id": 0, "tenant_id": 1})
    doc['tenant_id'] = (plan_for_tenant or {}).get("tenant_id") or user.get("tenant_id", "")
    await db.payments.insert_one(doc)

    return {"payment_id": payment_obj.id, "message": "Manual payment created, waiting for verification"}


@router.put("/payments/{payment_id}/verify-manual")
async def verify_manual_payment(payment_id: str, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.get("status") == "verified":
        raise HTTPException(status_code=400, detail="Payment already verified")

    await db.payments.update_one({"id": payment_id}, {"$set": {"status": "verified", "verified_at": datetime.now(timezone.utc).isoformat()}})

    plan = await db.plans.find_one({"id": payment["plan_id"]}, {"_id": 0})
    if plan:
        existing = await db.subscribers.find_one({
            "telegram_user_id": payment["telegram_user_id"],
            "plan_id": payment["plan_id"],
            "status": "active"
        }, {"_id": 0})

        if not existing:
            from api.tenant_admin.subscribers import create_subscriber_task
            subscriber_create = SubscriberCreate(
                telegram_user_id=payment["telegram_user_id"],
                telegram_username=payment.get("telegram_username"),
                plan_id=payment["plan_id"],
                payment_method="manual",
                payment_id=payment["id"]
            )
            background_tasks.add_task(create_subscriber_task, subscriber_create, plan)
        else:
            settings = await get_bot_settings()
            plan_channel = plan.get("channel_id", "") or settings.get("telegram_channel_id", "")
            if plan_channel:
                background_tasks.add_task(add_to_channel, payment["telegram_user_id"], plan_channel, plan["name"])

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if bot_token and payment.get("telegram_user_id"):
        success_msg = "<b>Payment Verified!</b>\n\n"
        success_msg += f"Plan: <b>{payment.get('plan_name', 'N/A')}</b>\n"
        success_msg += f"Amount: Rs.{payment.get('amount', 0)}\n\n"
        success_msg += "Your subscription is now active!\n"
        success_msg += "You'll receive the channel invite link shortly."
        await send_telegram_message(payment["telegram_user_id"], success_msg, bot_token)

    background_tasks.add_task(
        notify_admin_new_payment,
        payment.get("telegram_user_id", ""),
        payment.get("telegram_username", ""),
        payment.get("plan_name", "N/A"),
        payment.get("amount", 0),
        payment.get("screenshot_file_id", "")
    )

    return {"message": "Payment verified and subscriber created"}


@router.put("/payments/{payment_id}/reject")
async def reject_payment(payment_id: str, data: dict = None, user=Depends(get_current_user)):
    """Reject a payment"""
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.get("status") == "rejected":
        raise HTTPException(status_code=400, detail="Payment is already rejected")

    reason = data.get("reason", "Payment rejected by admin") if data else "Payment rejected by admin"

    await db.payments.update_one(
        {"id": payment_id},
        {"$set": {"status": "rejected", "rejection_reason": reason, "rejected_at": datetime.now(timezone.utc).isoformat()}}
    )

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")
    if bot_token and payment.get("telegram_user_id"):
        msg = f"<b>Payment Rejected</b>\n\n"
        msg += f"Plan: {payment.get('plan_name', 'N/A')}\n"
        msg += f"Amount: Rs.{payment.get('amount', 0)}\n\n"
        msg += f"Reason: {reason}\n\n"
        msg += "Please contact support if you believe this is an error."
        await send_telegram_message(payment["telegram_user_id"], msg, bot_token)

    return {"message": "Payment rejected"}


@router.delete("/payments/{payment_id}")
async def delete_payment(payment_id: str, user=Depends(get_current_user)):
    """Delete a payment record - Admin/Super Admin only"""
    ensure_admin(user)

    tenant_id = get_user_tenant(user)
    payment = await db.payments.find_one(tq({"id": payment_id}, tenant_id), {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    await db.payments.delete_one(tq({"id": payment_id}, tenant_id))
    return {"message": "Payment deleted"}


@router.post("/payments/bulk-verify")
async def bulk_verify_payments(data: dict, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    """Verify multiple payments at once"""
    payment_ids = data.get("payment_ids", [])
    if not payment_ids:
        raise HTTPException(status_code=400, detail="No payment IDs provided")

    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    verified_count = 0
    for payment_id in payment_ids:
        payment = await db.payments.find_one({"id": payment_id, "status": "pending"}, {"_id": 0})
        if payment:
            await db.payments.update_one({"id": payment_id}, {"$set": {"status": "verified", "verified_at": datetime.now(timezone.utc).isoformat()}})

            plan = await db.plans.find_one({"id": payment["plan_id"]}, {"_id": 0})
            if plan:
                existing = await db.subscribers.find_one({
                    "telegram_user_id": payment["telegram_user_id"],
                    "plan_id": payment["plan_id"],
                    "status": "active"
                }, {"_id": 0})

                if not existing:
                    from api.tenant_admin.subscribers import create_subscriber_task
                    subscriber_create = SubscriberCreate(
                        telegram_user_id=payment["telegram_user_id"],
                        telegram_username=payment.get("telegram_username"),
                        plan_id=payment["plan_id"],
                        payment_method=payment.get("payment_method", "manual"),
                        payment_id=payment["id"]
                    )
                    background_tasks.add_task(create_subscriber_task, subscriber_create, plan)
                else:
                    plan_channel = plan.get("channel_id", "") or settings.get("telegram_channel_id", "")
                    if plan_channel:
                        background_tasks.add_task(add_to_channel, payment["telegram_user_id"], plan_channel, plan["name"])

                if bot_token and payment.get("telegram_user_id"):
                    success_msg = "<b>Payment Verified!</b>\n\n"
                    success_msg += f"Plan: <b>{payment.get('plan_name', plan.get('name', 'N/A'))}</b>\n"
                    success_msg += f"Amount: Rs.{payment.get('amount', 0)}\n\n"
                    success_msg += "Your subscription is now active!"
                    await send_telegram_message(payment["telegram_user_id"], success_msg, bot_token)

            verified_count += 1

    return {"message": f"{verified_count} payments verified", "verified_count": verified_count}


@router.post("/payments/bulk-reject")
async def bulk_reject_payments(data: dict, user=Depends(get_current_user)):
    """Reject multiple payments at once"""
    payment_ids = data.get("payment_ids", [])
    reason = data.get("reason", "Payment rejected by admin")
    if not payment_ids:
        raise HTTPException(status_code=400, detail="No payment IDs provided")

    rejected_count = 0
    settings = await get_bot_settings()
    bot_token = settings.get("telegram_bot_token", "")

    for payment_id in payment_ids:
        payment = await db.payments.find_one({"id": payment_id, "status": "pending"}, {"_id": 0})
        if payment:
            await db.payments.update_one(
                {"id": payment_id},
                {"$set": {"status": "rejected", "rejection_reason": reason, "rejected_at": datetime.now(timezone.utc).isoformat()}}
            )

            if bot_token and payment.get("telegram_user_id"):
                msg = f"<b>Payment Rejected</b>\n\n"
                msg += f"Plan: {payment.get('plan_name', 'N/A')}\n"
                msg += f"Amount: Rs.{payment.get('amount', 0)}\n\n"
                msg += f"Reason: {reason}"
                await send_telegram_message(payment["telegram_user_id"], msg, bot_token)
            rejected_count += 1

    return {"message": f"{rejected_count} payments rejected", "rejected_count": rejected_count}


@router.post("/payments/bulk-delete")
async def bulk_delete_payments(data: dict, user=Depends(get_current_user)):
    """Delete multiple payments at once - Admin only"""
    ensure_admin(user)

    payment_ids = data.get("payment_ids", [])
    if not payment_ids:
        raise HTTPException(status_code=400, detail="No payment IDs provided")

    tenant_id = get_user_tenant(user)
    result = await db.payments.delete_many(tq({"id": {"$in": payment_ids}}, tenant_id))
    return {"message": f"{result.deleted_count} payments deleted", "deleted_count": result.deleted_count}
