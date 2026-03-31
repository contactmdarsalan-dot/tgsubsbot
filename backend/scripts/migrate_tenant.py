"""Migration script: Add tenant_id='default' to all existing documents.
Run once to prepare the database for multi-tenant SaaS.

Usage: python scripts/migrate_tenant.py
"""
import asyncio
import os
import sys

# Add parent dir to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env')

TENANT_ID = "default"

COLLECTIONS_TO_MIGRATE = [
    "payments",
    "subscribers",
    "plans",
    "bot_users",
    "paid_posts",
    "live_sessions",
    "live_tickets",
    "live_superchats",
    "broadcasts",
    "bot_orders",
    "coupons",
    "referrals",
    "miniapp_users",
    "miniapp_support_chats",
    "support_tickets",
    "pending_screenshots",
    "settings",
    "telegram_admins",
    "creators",
    "channels",
    "chat_groups_pool",
    "chat_sessions",
    "templates",
    "scheduled_broadcasts",
    "faqs",
    "video_call_bookings",
    "user_notes",
    "user_tags",
    "blocked_users",
    "referral_settings",
    "branding",
    "bot_language",
]


async def migrate():
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # Create default tenant
    existing = await db.tenants.find_one({"tenant_id": TENANT_ID})
    if not existing:
        from datetime import datetime, timezone
        await db.tenants.insert_one({
            "id": "default-tenant",
            "tenant_id": TENANT_ID,
            "name": "Default Creator",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        print("[+] Created default tenant")

    total_updated = 0
    for coll_name in COLLECTIONS_TO_MIGRATE:
        coll = db[coll_name]
        # Only update documents that don't have tenant_id yet
        result = await coll.update_many(
            {"tenant_id": {"$exists": False}},
            {"$set": {"tenant_id": TENANT_ID}}
        )
        if result.modified_count > 0:
            print(f"  [{coll_name}] Updated {result.modified_count} documents")
            total_updated += result.modified_count
        else:
            print(f"  [{coll_name}] Already up to date")

    # Create index on tenant_id for key collections
    key_collections = ["payments", "subscribers", "plans", "bot_users", "paid_posts", 
                       "live_sessions", "settings", "telegram_admins"]
    for coll_name in key_collections:
        await db[coll_name].create_index("tenant_id")
        print(f"  [{coll_name}] Index created on tenant_id")

    print(f"\n[DONE] Migration complete. {total_updated} documents updated.")
    client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
