"""Global App - Creators, Content, Discovery, Subscriptions
Public-facing APIs for the mobile/global consumer app.
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from database import db
from services.auth import get_current_user
from datetime import datetime, timezone
import uuid
import os

router = APIRouter(prefix="/global", tags=["Global App"])


# ============== CREATOR LISTING & DISCOVERY ==============

@router.get("/creators")
async def list_creators(category: str = None, search: str = None, page: int = 1, limit: int = 20):
    """Public: Browse creators listed on the global app."""
    query = {"is_listed": True, "listing_status": "approved"}
    if category:
        query["categories"] = {"$in": [category]}
    if search:
        query["$or"] = [
            {"display_name": {"$regex": search, "$options": "i"}},
            {"bio": {"$regex": search, "$options": "i"}},
        ]
    skip = (page - 1) * limit
    creators = await db.creator_profiles.find(query, {"_id": 0}).sort("followers_count", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.creator_profiles.count_documents(query)
    return {"creators": creators, "total": total}


@router.get("/creators/trending")
async def trending_creators(limit: int = 10):
    """Public: Get trending creators."""
    creators = await db.creator_profiles.find(
        {"is_listed": True, "listing_status": "approved"},
        {"_id": 0}
    ).sort("total_earnings", -1).limit(limit).to_list(limit)
    return creators


@router.get("/creators/categories")
async def get_categories():
    """Public: List all creator categories."""
    categories = await db.creator_categories.find({}, {"_id": 0}).to_list(100)
    if not categories:
        defaults = ["Entertainment", "Education", "Fitness", "Music", "Tech", "Lifestyle", "Gaming", "Finance", "Art", "Other"]
        categories = [{"id": str(uuid.uuid4()), "name": c, "icon": ""} for c in defaults]
        await db.creator_categories.insert_many(categories)
        for c in categories:
            c.pop("_id", None)
    return categories


@router.get("/creators/{creator_id}")
async def get_creator_profile(creator_id: str):
    """Public: Get a single creator's profile."""
    creator = await db.creator_profiles.find_one(
        {"id": creator_id, "is_listed": True, "listing_status": "approved"}, {"_id": 0}
    )
    if not creator:
        raise HTTPException(404, "Creator not found")
    return creator


@router.get("/creators/{creator_id}/content")
async def get_creator_content(creator_id: str, page: int = 1, limit: int = 20, user_id: str = None):
    """Public: Get creator's content feed."""
    skip = (page - 1) * limit
    content = await db.global_content.find(
        {"creator_id": creator_id, "is_published": True},
        {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    # Mark which content user has unlocked
    if user_id:
        unlocked_ids = set()
        unlocks = await db.content_unlocks.find({"user_id": user_id}, {"content_id": 1, "_id": 0}).to_list(1000)
        unlocked_ids = {u["content_id"] for u in unlocks}
        for c in content:
            c["is_unlocked"] = c["id"] in unlocked_ids or not c.get("is_paid", False)

    total = await db.global_content.count_documents({"creator_id": creator_id, "is_published": True})
    return {"content": content, "total": total}


@router.get("/creators/{creator_id}/plans")
async def get_creator_plans(creator_id: str):
    """Public: Get creator's subscription plans."""
    plans = await db.creator_plans.find(
        {"creator_id": creator_id, "is_active": True}, {"_id": 0}
    ).sort("price", 1).to_list(20)
    return plans


@router.get("/creators/{creator_id}/live")
async def get_creator_live(creator_id: str):
    """Public: Get creator's live sessions."""
    sessions = await db.global_live_sessions.find(
        {"creator_id": creator_id, "status": {"$in": ["scheduled", "live"]}}, {"_id": 0}
    ).sort("scheduled_at", 1).to_list(20)
    return sessions


# ============== CREATOR PROFILE MANAGEMENT (Creator's own) ==============

@router.get("/my/creator-profile")
async def get_my_creator_profile(user=Depends(get_current_user)):
    """Creator: Get own profile."""
    profile = await db.creator_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        return {"exists": False}
    return {**profile, "exists": True}


@router.post("/creator/register")
async def register_as_creator(data: dict, user=Depends(get_current_user)):
    """User registers as a creator on the global app (free)."""
    existing = await db.creator_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if existing:
        raise HTTPException(400, "Already registered as creator")

    profile = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "display_name": data.get("display_name", user.get("name", "")),
        "bio": data.get("bio", ""),
        "avatar_url": data.get("avatar_url", ""),
        "cover_url": data.get("cover_url", ""),
        "categories": data.get("categories", []),
        "social_links": data.get("social_links", {}),
        "is_listed": False,
        "listing_status": "pending",
        "followers_count": 0,
        "total_earnings": 0,
        "total_content": 0,
        "is_verified": False,
        "tenant_id": user.get("tenant_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.creator_profiles.insert_one(profile)
    profile.pop("_id", None)
    return {"success": True, "profile": profile}


@router.put("/my/creator-profile")
async def update_creator_profile(data: dict, user=Depends(get_current_user)):
    """Creator: Update own profile."""
    allowed = {"display_name", "bio", "avatar_url", "cover_url", "categories", "social_links"}
    update = {k: v for k, v in data.items() if k in allowed}
    result = await db.creator_profiles.update_one({"user_id": user["id"]}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Creator profile not found")
    return {"success": True}


# ============== LISTING REQUEST (Bot owners request global listing) ==============

@router.post("/listing-request")
async def request_global_listing(data: dict, user=Depends(get_current_user)):
    """Bot owner/Creator requests to be listed on the global app."""
    existing = await db.listing_requests.find_one({"user_id": user["id"], "status": "pending"}, {"_id": 0})
    if existing:
        raise HTTPException(400, "You already have a pending listing request")

    request_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_name": user.get("name", ""),
        "user_email": user.get("email", ""),
        "tenant_id": user.get("tenant_id"),
        "display_name": data.get("display_name", user.get("name", "")),
        "bio": data.get("bio", ""),
        "categories": data.get("categories", []),
        "reason": data.get("reason", ""),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.listing_requests.insert_one(request_doc)
    request_doc.pop("_id", None)
    return {"success": True, "request": request_doc}


@router.get("/my/listing-request")
async def get_my_listing_request(user=Depends(get_current_user)):
    """Get current user's listing request status."""
    req = await db.listing_requests.find_one({"user_id": user["id"]}, {"_id": 0})
    if not req:
        return {"exists": False}
    return {**req, "exists": True}


# ============== ADMIN: Listing Requests ==============

@router.get("/admin/listing-requests")
async def admin_list_requests(user=Depends(get_current_user), status: str = "pending"):
    """Admin: List listing requests."""
    if user.get("role") not in ("super_admin",):
        raise HTTPException(403, "Super admin required")
    query = {} if status == "all" else {"status": status}
    requests = await db.listing_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return requests


@router.post("/admin/listing-requests/{request_id}/approve")
async def admin_approve_listing(request_id: str, user=Depends(get_current_user)):
    """Admin: Approve listing request."""
    if user.get("role") not in ("super_admin",):
        raise HTTPException(403, "Super admin required")

    req = await db.listing_requests.find_one({"id": request_id}, {"_id": 0})
    if not req:
        raise HTTPException(404, "Request not found")

    await db.listing_requests.update_one({"id": request_id}, {"$set": {"status": "approved"}})

    # Create/update creator profile
    existing = await db.creator_profiles.find_one({"user_id": req["user_id"]}, {"_id": 0})
    if existing:
        await db.creator_profiles.update_one(
            {"user_id": req["user_id"]},
            {"$set": {"is_listed": True, "listing_status": "approved"}}
        )
    else:
        profile = {
            "id": str(uuid.uuid4()),
            "user_id": req["user_id"],
            "display_name": req.get("display_name", req.get("user_name", "")),
            "bio": req.get("bio", ""),
            "avatar_url": "",
            "cover_url": "",
            "categories": req.get("categories", []),
            "social_links": {},
            "is_listed": True,
            "listing_status": "approved",
            "followers_count": 0,
            "total_earnings": 0,
            "total_content": 0,
            "is_verified": False,
            "tenant_id": req.get("tenant_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.creator_profiles.insert_one(profile)
    return {"success": True}


@router.post("/admin/listing-requests/{request_id}/reject")
async def admin_reject_listing(request_id: str, data: dict, user=Depends(get_current_user)):
    if user.get("role") not in ("super_admin",):
        raise HTTPException(403, "Super admin required")
    await db.listing_requests.update_one(
        {"id": request_id},
        {"$set": {"status": "rejected", "reject_reason": data.get("reason", "")}}
    )
    return {"success": True}


# ============== CONTENT SYSTEM ==============

@router.post("/content")
async def create_content(data: dict, user=Depends(get_current_user)):
    """Creator: Post content (free or paid)."""
    profile = await db.creator_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(403, "You must be a registered creator")

    content = {
        "id": str(uuid.uuid4()),
        "creator_id": profile["id"],
        "creator_name": profile.get("display_name", ""),
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "content_type": data.get("content_type", "text"),
        "media_url": data.get("media_url", ""),
        "thumbnail_url": data.get("thumbnail_url", ""),
        "preview_url": data.get("preview_url", ""),
        "is_paid": data.get("is_paid", False),
        "coin_price": int(data.get("coin_price", 0)),
        "is_published": True,
        "likes_count": 0,
        "views_count": 0,
        "unlock_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.global_content.insert_one(content)
    content.pop("_id", None)

    await db.creator_profiles.update_one({"id": profile["id"]}, {"$inc": {"total_content": 1}})
    return {"success": True, "content": content}


@router.get("/my/content")
async def get_my_content(user=Depends(get_current_user), page: int = 1, limit: int = 20):
    """Creator: Get own content."""
    profile = await db.creator_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        return {"content": [], "total": 0}
    skip = (page - 1) * limit
    content = await db.global_content.find({"creator_id": profile["id"]}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.global_content.count_documents({"creator_id": profile["id"]})
    return {"content": content, "total": total}


@router.put("/content/{content_id}")
async def update_content(content_id: str, data: dict, user=Depends(get_current_user)):
    """Creator: Update own content."""
    profile = await db.creator_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(403, "Not a creator")
    allowed = {"title", "description", "media_url", "thumbnail_url", "preview_url", "is_paid", "coin_price", "is_published"}
    update = {k: v for k, v in data.items() if k in allowed}
    result = await db.global_content.update_one({"id": content_id, "creator_id": profile["id"]}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Content not found")
    return {"success": True}


@router.delete("/content/{content_id}")
async def delete_content(content_id: str, user=Depends(get_current_user)):
    profile = await db.creator_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(403, "Not a creator")
    result = await db.global_content.delete_one({"id": content_id, "creator_id": profile["id"]})
    if result.deleted_count == 0:
        raise HTTPException(404, "Content not found")
    await db.creator_profiles.update_one({"id": profile["id"]}, {"$inc": {"total_content": -1}})
    return {"success": True}


# ============== CONTENT UNLOCK (Coin-based) ==============

@router.post("/content/unlock")
async def unlock_content(data: dict, user=Depends(get_current_user)):
    """User unlocks paid content using coins."""
    content_id = data.get("content_id")
    content = await db.global_content.find_one({"id": content_id, "is_published": True}, {"_id": 0})
    if not content:
        raise HTTPException(404, "Content not found")
    if not content.get("is_paid", False):
        return {"success": True, "message": "Content is free", "media_url": content.get("media_url", "")}

    # Check if already unlocked
    existing = await db.content_unlocks.find_one({"user_id": user["id"], "content_id": content_id}, {"_id": 0})
    if existing:
        return {"success": True, "message": "Already unlocked", "media_url": content.get("media_url", "")}

    # Spend coins
    from api.customer.global_wallet import spend_coins, credit_creator_revenue
    price = content.get("coin_price", 0)
    if price <= 0:
        raise HTTPException(400, "Invalid price")

    success, msg = await spend_coins(user["id"], price, f"Unlock: {content.get('title', '')}", "content_unlock", content_id)
    if not success:
        raise HTTPException(400, msg)

    # Record unlock
    unlock = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "content_id": content_id,
        "creator_id": content["creator_id"],
        "coins_spent": price,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.content_unlocks.insert_one(unlock)
    await db.global_content.update_one({"id": content_id}, {"$inc": {"unlock_count": 1}})

    # Credit creator with revenue share
    creator_profile = await db.creator_profiles.find_one({"id": content["creator_id"]}, {"_id": 0})
    if creator_profile:
        await credit_creator_revenue(creator_profile["user_id"], price, content.get("title", "Content"), "content_unlock", content_id)
        await db.creator_profiles.update_one({"id": content["creator_id"]}, {"$inc": {"total_earnings": price}})

    return {"success": True, "media_url": content.get("media_url", "")}


@router.get("/content/unlocked")
async def get_unlocked_content(user=Depends(get_current_user), page: int = 1, limit: int = 20):
    """Get all content unlocked by user."""
    skip = (page - 1) * limit
    unlocks = await db.content_unlocks.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    content_ids = [u["content_id"] for u in unlocks]
    content = []
    if content_ids:
        content = await db.global_content.find({"id": {"$in": content_ids}}, {"_id": 0}).to_list(limit)
        for c in content:
            c["is_unlocked"] = True
    return {"content": content, "total": len(content_ids)}


@router.get("/content/{content_id}")
async def get_single_content(content_id: str, user_id: str = None):
    """Public: Get single content. If user_id provided, checks unlock status."""
    content = await db.global_content.find_one({"id": content_id, "is_published": True}, {"_id": 0})
    if not content:
        raise HTTPException(404, "Content not found")

    await db.global_content.update_one({"id": content_id}, {"$inc": {"views_count": 1}})
    content["views_count"] = content.get("views_count", 0) + 1

    if user_id and content.get("is_paid"):
        unlock = await db.content_unlocks.find_one({"user_id": user_id, "content_id": content_id}, {"_id": 0})
        content["is_unlocked"] = unlock is not None
        if not unlock:
            content.pop("media_url", None)
    elif content.get("is_paid"):
        content["is_unlocked"] = False
        content.pop("media_url", None)
    else:
        content["is_unlocked"] = True

    return content


# ============== HOME FEED ==============

@router.get("/home/feed")
async def get_home_feed(user_id: str = None, page: int = 1, limit: int = 20):
    """Public: Get home feed — mix of content from all creators."""
    skip = (page - 1) * limit
    content = await db.global_content.find(
        {"is_published": True},
        {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    if user_id:
        unlocks = await db.content_unlocks.find({"user_id": user_id}, {"content_id": 1, "_id": 0}).to_list(5000)
        unlocked_ids = {u["content_id"] for u in unlocks}
        for c in content:
            if c.get("is_paid"):
                c["is_unlocked"] = c["id"] in unlocked_ids
                if not c["is_unlocked"]:
                    c.pop("media_url", None)
            else:
                c["is_unlocked"] = True

    return {"content": content}


@router.get("/live/ongoing")
async def get_ongoing_live():
    """Public: Get currently live sessions."""
    sessions = await db.global_live_sessions.find(
        {"status": "live"}, {"_id": 0}
    ).sort("started_at", -1).to_list(20)
    return sessions


# ============== CREATOR PLANS & SUBSCRIPTIONS ==============

@router.post("/creator/plans")
async def create_creator_plan(data: dict, user=Depends(get_current_user)):
    """Creator: Create a subscription plan."""
    profile = await db.creator_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(403, "Not a creator")

    plan = {
        "id": str(uuid.uuid4()),
        "creator_id": profile["id"],
        "creator_name": profile.get("display_name", ""),
        "name": data["name"],
        "description": data.get("description", ""),
        "coin_price": int(data["coin_price"]),
        "duration_days": int(data.get("duration_days", 30)),
        "features": data.get("features", []),
        "is_active": True,
        "subscriber_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.creator_plans.insert_one(plan)
    plan.pop("_id", None)
    return {"success": True, "plan": plan}


@router.get("/my/plans")
async def get_my_plans(user=Depends(get_current_user)):
    """Creator: Get own plans."""
    profile = await db.creator_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        return []
    plans = await db.creator_plans.find({"creator_id": profile["id"]}, {"_id": 0}).to_list(50)
    return plans


@router.put("/creator/plans/{plan_id}")
async def update_creator_plan(plan_id: str, data: dict, user=Depends(get_current_user)):
    profile = await db.creator_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(403, "Not a creator")
    allowed = {"name", "description", "coin_price", "duration_days", "features", "is_active"}
    update = {k: v for k, v in data.items() if k in allowed}
    result = await db.creator_plans.update_one({"id": plan_id, "creator_id": profile["id"]}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Plan not found")
    return {"success": True}


@router.delete("/creator/plans/{plan_id}")
async def delete_creator_plan(plan_id: str, user=Depends(get_current_user)):
    profile = await db.creator_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(403, "Not a creator")
    await db.creator_plans.delete_one({"id": plan_id, "creator_id": profile["id"]})
    return {"success": True}


@router.post("/subscriptions/buy")
async def buy_subscription(data: dict, user=Depends(get_current_user)):
    """User: Buy a creator's subscription plan using coins."""
    plan_id = data["plan_id"]
    plan = await db.creator_plans.find_one({"id": plan_id, "is_active": True}, {"_id": 0})
    if not plan:
        raise HTTPException(404, "Plan not found")

    # Check if already subscribed
    existing = await db.global_subscriptions.find_one(
        {"user_id": user["id"], "plan_id": plan_id, "status": "active"}, {"_id": 0}
    )
    if existing:
        raise HTTPException(400, "Already subscribed to this plan")

    # Spend coins
    from api.customer.global_wallet import spend_coins, credit_creator_revenue
    price = plan["coin_price"]
    success, msg = await spend_coins(user["id"], price, f"Subscribe: {plan['name']}", "subscription", plan_id)
    if not success:
        raise HTTPException(400, msg)

    # Create subscription
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    sub = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "creator_id": plan["creator_id"],
        "plan_id": plan_id,
        "plan_name": plan["name"],
        "coins_paid": price,
        "status": "active",
        "start_date": now.isoformat(),
        "end_date": (now + timedelta(days=plan["duration_days"])).isoformat(),
        "created_at": now.isoformat(),
    }
    await db.global_subscriptions.insert_one(sub)
    await db.creator_plans.update_one({"id": plan_id}, {"$inc": {"subscriber_count": 1}})

    # Revenue share
    creator_profile = await db.creator_profiles.find_one({"id": plan["creator_id"]}, {"_id": 0})
    if creator_profile:
        await credit_creator_revenue(creator_profile["user_id"], price, plan["name"], "subscription", plan_id)
        await db.creator_profiles.update_one({"id": plan["creator_id"]}, {"$inc": {"total_earnings": price}})

    sub.pop("_id", None)
    return {"success": True, "subscription": sub}


@router.get("/subscriptions/my")
async def get_my_subscriptions(user=Depends(get_current_user)):
    """User: Get my active subscriptions."""
    subs = await db.global_subscriptions.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return subs


@router.get("/subscriptions/check/{creator_id}")
async def check_subscription(creator_id: str, user=Depends(get_current_user)):
    """Check if user is subscribed to a creator."""
    sub = await db.global_subscriptions.find_one(
        {"user_id": user["id"], "creator_id": creator_id, "status": "active"}, {"_id": 0}
    )
    return {"is_subscribed": sub is not None, "subscription": sub}


# ============== LIVE (Coin-based access) ==============

@router.post("/live/join")
async def join_live(data: dict, user=Depends(get_current_user)):
    """User: Join a live session (may require coins)."""
    session_id = data["session_id"]
    session = await db.global_live_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(404, "Session not found")
    if session["status"] != "live":
        raise HTTPException(400, "Session is not currently live")

    ticket_price = session.get("ticket_price", 0)
    if ticket_price > 0:
        # Check if already has ticket
        existing = await db.global_live_tickets.find_one({"user_id": user["id"], "session_id": session_id}, {"_id": 0})
        if not existing:
            from api.customer.global_wallet import spend_coins, credit_creator_revenue
            success, msg = await spend_coins(user["id"], ticket_price, f"Live: {session.get('title', '')}", "live_ticket", session_id)
            if not success:
                raise HTTPException(400, msg)

            ticket = {
                "id": str(uuid.uuid4()),
                "user_id": user["id"],
                "session_id": session_id,
                "coins_spent": ticket_price,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.global_live_tickets.insert_one(ticket)

            creator_profile = await db.creator_profiles.find_one({"id": session["creator_id"]}, {"_id": 0})
            if creator_profile:
                await credit_creator_revenue(creator_profile["user_id"], ticket_price, session.get("title", "Live"), "live_ticket", session_id)

    await db.global_live_sessions.update_one({"id": session_id}, {"$inc": {"viewer_count": 1}})
    return {"success": True, "session": session}


@router.post("/live/leave")
async def leave_live(data: dict, user=Depends(get_current_user)):
    session_id = data["session_id"]
    await db.global_live_sessions.update_one({"id": session_id}, {"$inc": {"viewer_count": -1}})
    return {"success": True}


# ============== CREATOR LIVE MANAGEMENT ==============

@router.post("/creator/live")
async def creator_start_live(data: dict, user=Depends(get_current_user)):
    """Creator: Create/start a live session."""
    profile = await db.creator_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(403, "Not a creator")

    session = {
        "id": str(uuid.uuid4()),
        "creator_id": profile["id"],
        "creator_name": profile.get("display_name", ""),
        "title": data.get("title", "Live Session"),
        "description": data.get("description", ""),
        "ticket_price": int(data.get("ticket_price", 0)),
        "status": data.get("status", "scheduled"),
        "scheduled_at": data.get("scheduled_at", datetime.now(timezone.utc).isoformat()),
        "viewer_count": 0,
        "max_viewers": int(data.get("max_viewers", 0)),
        "started_at": "",
        "ended_at": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.global_live_sessions.insert_one(session)
    session.pop("_id", None)
    return {"success": True, "session": session}


@router.put("/creator/live/{session_id}")
async def creator_update_live(session_id: str, data: dict, user=Depends(get_current_user)):
    profile = await db.creator_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(403, "Not a creator")
    allowed = {"title", "description", "ticket_price", "status", "scheduled_at", "max_viewers"}
    update = {k: v for k, v in data.items() if k in allowed}
    if data.get("status") == "live":
        update["started_at"] = datetime.now(timezone.utc).isoformat()
    elif data.get("status") == "ended":
        update["ended_at"] = datetime.now(timezone.utc).isoformat()
    await db.global_live_sessions.update_one({"id": session_id, "creator_id": profile["id"]}, {"$set": update})
    return {"success": True}


# ============== FOLLOW SYSTEM ==============

@router.post("/creators/{creator_id}/follow")
async def follow_creator(creator_id: str, user=Depends(get_current_user)):
    existing = await db.global_follows.find_one({"user_id": user["id"], "creator_id": creator_id}, {"_id": 0})
    if existing:
        return {"success": True, "message": "Already following"}
    await db.global_follows.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "creator_id": creator_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.creator_profiles.update_one({"id": creator_id}, {"$inc": {"followers_count": 1}})
    return {"success": True}


@router.delete("/creators/{creator_id}/follow")
async def unfollow_creator(creator_id: str, user=Depends(get_current_user)):
    result = await db.global_follows.delete_one({"user_id": user["id"], "creator_id": creator_id})
    if result.deleted_count:
        await db.creator_profiles.update_one({"id": creator_id}, {"$inc": {"followers_count": -1}})
    return {"success": True}


@router.get("/my/following")
async def get_following(user=Depends(get_current_user)):
    follows = await db.global_follows.find({"user_id": user["id"]}, {"_id": 0}).to_list(1000)
    creator_ids = [f["creator_id"] for f in follows]
    creators = []
    if creator_ids:
        creators = await db.creator_profiles.find({"id": {"$in": creator_ids}}, {"_id": 0}).to_list(1000)
    return creators


# ============== NOTIFICATIONS ==============

@router.get("/notifications")
async def get_notifications(user=Depends(get_current_user), page: int = 1, limit: int = 50):
    skip = (page - 1) * limit
    notifs = await db.global_notifications.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    unread = await db.global_notifications.count_documents({"user_id": user["id"], "is_read": False})
    return {"notifications": notifs, "unread": unread}


@router.post("/notifications/read")
async def mark_notifications_read(data: dict, user=Depends(get_current_user)):
    ids = data.get("notification_ids", [])
    if ids:
        await db.global_notifications.update_many(
            {"user_id": user["id"], "id": {"$in": ids}},
            {"$set": {"is_read": True}}
        )
    else:
        await db.global_notifications.update_many(
            {"user_id": user["id"]},
            {"$set": {"is_read": True}}
        )
    return {"success": True}
