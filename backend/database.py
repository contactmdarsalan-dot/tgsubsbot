"""
Database module - MongoDB and Redis connections
"""
import os
import json
from motor.motor_asyncio import AsyncIOMotorClient
from config import logger

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Redis Cache (Optional)
redis_client = None
try:
    import redis
    redis_url = os.environ.get('REDIS_URL', '')
    if redis_url:
        redis_client = redis.from_url(redis_url, decode_responses=True)
        logger.info("Redis connected!")
except Exception:
    pass


async def ensure_indexes():
    """Create MongoDB indexes for performance and security.
    Uses compound unique indexes (tenant_id, id) for tenant-owned collections."""
    try:
        # Core indexes — tenant_id on all business collections
        # Compound unique index (tenant_id, id) ensures tenant-scoped uniqueness
        for coll_name in ["subscribers", "payments", "plans", "bot_users", "paid_posts",
                          "live_sessions", "broadcasts", "referrals", "telegram_admins",
                          "coupons", "paid_post_unlocks", "miniapp_users"]:
            coll = db[coll_name]
            await coll.create_index("tenant_id")
            await coll.create_index("id", unique=True, sparse=True)
            # Compound index for performance (tenant-scoped queries)
            try:
                await coll.drop_index("tenant_id_1_id_1")
            except Exception:
                pass
            await coll.create_index([("tenant_id", 1), ("id", 1)])
            await coll.create_index("created_at")

        # Compound indexes for common queries
        await db.subscribers.create_index([("tenant_id", 1), ("status", 1)])
        await db.subscribers.create_index([("tenant_id", 1), ("telegram_user_id", 1)])
        await db.payments.create_index([("tenant_id", 1), ("status", 1)])
        await db.payments.create_index([("tenant_id", 1), ("created_at", -1)])
        await db.plans.create_index([("tenant_id", 1), ("id", 1)])
        await db.plans.create_index([("tenant_id", 1), ("is_active", 1)])
        await db.bot_users.create_index([("tenant_id", 1), ("telegram_user_id", 1)])
        await db.live_sessions.create_index([("tenant_id", 1), ("status", 1)])
        await db.live_sessions.create_index([("tenant_id", 1), ("start_at", 1)])
        await db.broadcasts.create_index([("tenant_id", 1), ("status", 1)])
        await db.broadcasts.create_index([("tenant_id", 1), ("created_at", -1)])
        await db.coupons.create_index([("tenant_id", 1), ("code", 1)], unique=True, sparse=True)
        await db.coupons.create_index([("tenant_id", 1), ("is_active", 1)])
        await db.telegram_admins.create_index([("tenant_id", 1), ("telegram_user_id", 1)])
        await db.telegram_admins.create_index([("tenant_id", 1), ("is_active", 1)])
        await db.paid_post_unlocks.create_index([("tenant_id", 1), ("paid_post_id", 1), ("customer_id", 1)])

        # User indexes
        await db.users.create_index("email", unique=True, sparse=True)
        await db.users.create_index("id", unique=True)
        await db.users.create_index([("tenant_id", 1), ("role", 1)])
        await db.users.create_index([("tenant_id", 1), ("status", 1)])

        # Tenant indexes
        await db.tenants.create_index("tenant_id", unique=True)
        await db.tenants.create_index("status")

        # Settings — unique bot token per tenant
        await db.settings.create_index("tenant_id")
        await db.settings.create_index("telegram_bot_token", sparse=True)

        # Audit log indexes
        await db.audit_logs.create_index([("tenant_id", 1), ("created_at", -1)])
        await db.audit_logs.create_index("action")
        await db.audit_logs.create_index([("actor_user_id", 1), ("created_at", -1)])
        await db.audit_logs.create_index("request_id", sparse=True)

        # Idempotency keys — unique key for dedup
        await db.idempotency_keys.create_index("key", unique=True)
        await db.idempotency_keys.create_index("expires_at")

        # Global App indexes
        for coll_name in ["wallets", "wallet_transactions", "coin_payments", "coin_packages",
                          "creator_profiles", "global_content", "content_unlocks",
                          "creator_plans", "global_subscriptions", "global_live_sessions",
                          "global_follows", "global_notifications", "listing_requests",
                          "platform_revenue"]:
            coll = db[coll_name]
            await coll.create_index("id", unique=True, sparse=True)

        await db.wallets.create_index("user_id", unique=True)
        await db.wallet_transactions.create_index([("user_id", 1), ("created_at", -1)])
        await db.creator_profiles.create_index("user_id")
        await db.creator_profiles.create_index([("is_listed", 1), ("listing_status", 1)])
        await db.global_content.create_index([("creator_id", 1), ("created_at", -1)])
        await db.content_unlocks.create_index([("user_id", 1), ("content_id", 1)])
        await db.global_subscriptions.create_index([("user_id", 1), ("status", 1)])
        await db.global_follows.create_index([("user_id", 1), ("creator_id", 1)])
        await db.global_notifications.create_index([("user_id", 1), ("is_read", 1)])

        logger.info("MongoDB indexes created successfully (with compound tenant-scoped uniqueness)")
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")


async def cache_get(key: str, default=None):
    if not redis_client:
        return default
    try:
        value = redis_client.get(key)
        return json.loads(value) if value else default
    except Exception:
        return default


async def cache_set(key: str, value, ttl: int = 300):
    if not redis_client:
        return
    try:
        redis_client.setex(key, ttl, json.dumps(value))
    except Exception:
        pass


async def cache_delete(key: str):
    if not redis_client:
        return
    try:
        redis_client.delete(key)
    except Exception:
        pass
