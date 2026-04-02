"""Plans CRUD routes"""
from fastapi import APIRouter, HTTPException, Depends
from database import db, cache_delete, cache_get, cache_set
from services.auth import get_current_user
from services.tenant import DEFAULT_TENANT_ID
from services.permissions import get_user_tenant, tq
from models import SubscriptionPlanCreate, SubscriptionPlan
from typing import List
from datetime import datetime

router = APIRouter()


@router.get("/plans", response_model=List[SubscriptionPlan])
async def get_plans(user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    plans = await db.plans.find(tq({"source": {"$ne": "miniapp"}}, tenant_id), {"_id": 0}).to_list(100)
    for plan in plans:
        if isinstance(plan.get('created_at'), str):
            plan['created_at'] = datetime.fromisoformat(plan['created_at'])
    return plans


@router.get("/plans/active", response_model=List[SubscriptionPlan])
async def get_active_plans():
    cached = await cache_get("active_plans")
    if cached:
        for plan in cached:
            if isinstance(plan.get('created_at'), str):
                plan['created_at'] = datetime.fromisoformat(plan['created_at'])
        return cached

    plans = await db.plans.find({"is_active": True}, {"_id": 0}).to_list(100)
    for plan in plans:
        if isinstance(plan.get('created_at'), str):
            plan['created_at'] = datetime.fromisoformat(plan['created_at'])

    plans_for_cache = [{**p, 'created_at': p['created_at'].isoformat() if hasattr(p.get('created_at'), 'isoformat') else p.get('created_at')} for p in plans]
    await cache_set("active_plans", plans_for_cache, ttl=300)

    return plans


@router.post("/plans", response_model=SubscriptionPlan)
async def create_plan(plan: SubscriptionPlanCreate, user=Depends(get_current_user)):
    plan_obj = SubscriptionPlan(**plan.model_dump())
    doc = plan_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['tenant_id'] = user.get("tenant_id") or DEFAULT_TENANT_ID
    await db.plans.insert_one(doc)
    return plan_obj


@router.put("/plans/{plan_id}", response_model=SubscriptionPlan)
async def update_plan(plan_id: str, plan: SubscriptionPlanCreate, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    existing = await db.plans.find_one(tq({"id": plan_id}, tenant_id), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")

    await db.plans.update_one(tq({"id": plan_id}, tenant_id), {"$set": plan.model_dump()})
    updated = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return updated


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    result = await db.plans.delete_one(tq({"id": plan_id}, tenant_id))
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"message": "Plan deleted"}
