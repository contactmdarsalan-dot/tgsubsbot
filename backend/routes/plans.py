"""Plans CRUD routes — using Repository pattern for strict tenant isolation"""
from fastapi import APIRouter, HTTPException, Depends
from database import cache_delete, cache_get, cache_set
from services.auth import get_current_user
from services.permissions import get_user_tenant
from repositories.base import plans_repo
from models import SubscriptionPlanCreate, SubscriptionPlan
from typing import List
from datetime import datetime

router = APIRouter()


def _fix_dates(plan: dict) -> dict:
    """Ensure created_at is a datetime object for Pydantic models."""
    if isinstance(plan.get('created_at'), str):
        plan['created_at'] = datetime.fromisoformat(plan['created_at'])
    return plan


@router.get("/plans", response_model=List[SubscriptionPlan])
async def get_plans(user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        # Super admin — global view
        plans = await plans_repo.find_many_global(
            {"source": {"$ne": "miniapp"}}, sort=[("created_at", -1)]
        )
    else:
        plans = await plans_repo.find_many(
            tenant_id, {"source": {"$ne": "miniapp"}}, sort=[("created_at", -1)]
        )
    return [_fix_dates(p) for p in plans]


@router.get("/plans/active", response_model=List[SubscriptionPlan])
async def get_active_plans():
    """DEPRECATED: Public endpoint listing all active plans. Use tenant-scoped endpoint instead."""
    cached = await cache_get("active_plans")
    if cached:
        return [_fix_dates(p) for p in cached]
    plans = await plans_repo.find_many_global({"is_active": True})
    for p in plans:
        _fix_dates(p)
    plans_for_cache = [{**p, 'created_at': p['created_at'].isoformat() if hasattr(p.get('created_at'), 'isoformat') else p.get('created_at')} for p in plans]
    await cache_set("active_plans", plans_for_cache, ttl=300)
    return plans


@router.post("/plans", response_model=SubscriptionPlan)
async def create_plan(plan: SubscriptionPlanCreate, user=Depends(get_current_user)):
    tenant_id = user.get("tenant_id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated with your account")
    plan_obj = SubscriptionPlan(**plan.model_dump())
    doc = plan_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await plans_repo.insert_one(tenant_id, doc)
    return plan_obj


@router.put("/plans/{plan_id}", response_model=SubscriptionPlan)
async def update_plan(plan_id: str, plan: SubscriptionPlanCreate, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated with your account")
    existing = await plans_repo.find_one(tenant_id, {"id": plan_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")
    await plans_repo.update_one(tenant_id, {"id": plan_id}, {"$set": plan.model_dump()})
    updated = await plans_repo.find_one(tenant_id, {"id": plan_id})
    return _fix_dates(updated)


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str, user=Depends(get_current_user)):
    tenant_id = get_user_tenant(user)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated with your account")
    result = await plans_repo.delete_one(tenant_id, {"id": plan_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"message": "Plan deleted"}
