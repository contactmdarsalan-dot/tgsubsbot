"""
Production Data Migration Script
Migrates ALL existing data to 'Anamika' tenant (tenant_85ee971d0285)

Usage:
  python3 migrate_to_anamika.py

This script:
1. Creates the 'Anamika' tenant if not exists
2. Creates the 'Kaloo' (default) tenant if not exists
3. Migrates ALL data from 'default' tenant_id to 'tenant_85ee971d0285'
4. Adds tenant_id to docs that don't have it
5. Sets up admin for Anamika tenant
"""

import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import uuid

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ANAMIKA_TENANT_ID = "tenant_85ee971d0285"
DEFAULT_TENANT_ID = "default"

# Collections that need tenant_id migration
TENANT_COLLECTIONS = [
    "bot_users",
    "subscribers",
    "payments",
    "plans",
    "paid_posts",
    "live_sessions",
    "paid_post_unlocks",
    "pending_screenshots",
    "miniapp_users",
    "miniapp_support_chats",
    "referrals",
    "broadcasts",
    "chat_messages",
    "chat_sessions",
    "bot_activity_logs",
    "bot_orders",
]


async def migrate():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    print(f"Connected to: {MONGO_URL} / {DB_NAME}")
    print("=" * 60)

    # Step 1: Create Anamika tenant if not exists
    existing_anamika = await db.tenants.find_one({"tenant_id": ANAMIKA_TENANT_ID})
    if not existing_anamika:
        anamika_tenant = {
            "id": str(uuid.uuid4()),
            "tenant_id": ANAMIKA_TENANT_ID,
            "name": "Anamika",
            "email": "",
            "owner_telegram_id": "999888777666",
            "bot_token": "8275964628:AAH8U7ECRII7eyAySt7U2pyDQhLcnZunTnY",
            "bot_username": "anamikatgsubs_bot",
            "bot_name": "Anamika Bot",
            "upi_id": "",
            "channel_id": "",
            "razorpay_key_id": "",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.tenants.insert_one(anamika_tenant)
        print("[OK] Created Anamika tenant")
    else:
        # Update name if needed
        await db.tenants.update_one(
            {"tenant_id": ANAMIKA_TENANT_ID},
            {"$set": {"name": "Anamika"}}
        )
        print("[OK] Anamika tenant already exists, updated name")

    # Step 2: Create Kaloo (default) tenant if not exists
    existing_kaloo = await db.tenants.find_one({"tenant_id": DEFAULT_TENANT_ID})
    if not existing_kaloo:
        kaloo_tenant = {
            "id": "default-tenant",
            "tenant_id": DEFAULT_TENANT_ID,
            "name": "Kaloo",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "bot_token": "",
            "bot_username": "KalooBot",
            "owner_telegram_id": "",
        }
        await db.tenants.insert_one(kaloo_tenant)
        print("[OK] Created Kaloo tenant")
    else:
        await db.tenants.update_one(
            {"tenant_id": DEFAULT_TENANT_ID},
            {"$set": {"name": "Kaloo"}}
        )
        print("[OK] Kaloo tenant already exists, updated name")

    # Step 3: Migrate data
    print("\n" + "=" * 60)
    print("MIGRATING DATA TO ANAMIKA TENANT")
    print("=" * 60)

    total_migrated = 0

    for coll_name in TENANT_COLLECTIONS:
        coll = db[coll_name]

        # Count docs with 'default' tenant_id
        default_count = await coll.count_documents({"tenant_id": DEFAULT_TENANT_ID})
        # Count docs without tenant_id
        no_tenant_count = await coll.count_documents({"tenant_id": {"$exists": False}})
        # Count docs with empty tenant_id
        empty_tenant_count = await coll.count_documents({"tenant_id": ""})

        migrated = 0

        if default_count > 0:
            result = await coll.update_many(
                {"tenant_id": DEFAULT_TENANT_ID},
                {"$set": {"tenant_id": ANAMIKA_TENANT_ID}}
            )
            migrated += result.modified_count

        if no_tenant_count > 0:
            result = await coll.update_many(
                {"tenant_id": {"$exists": False}},
                {"$set": {"tenant_id": ANAMIKA_TENANT_ID}}
            )
            migrated += result.modified_count

        if empty_tenant_count > 0:
            result = await coll.update_many(
                {"tenant_id": ""},
                {"$set": {"tenant_id": ANAMIKA_TENANT_ID}}
            )
            migrated += result.modified_count

        if migrated > 0:
            print(f"  {coll_name}: {migrated} docs migrated")
            total_migrated += migrated
        else:
            total_in_coll = await coll.count_documents({})
            if total_in_coll > 0:
                already = await coll.count_documents({"tenant_id": ANAMIKA_TENANT_ID})
                print(f"  {coll_name}: {already} docs already in Anamika (skipped)")
            else:
                print(f"  {coll_name}: empty collection")

    # Step 4: Migrate telegram_admins
    admin_migrated = 0
    default_admins = await db.telegram_admins.count_documents({"tenant_id": DEFAULT_TENANT_ID})
    no_tenant_admins = await db.telegram_admins.count_documents({"tenant_id": {"$exists": False}})

    if default_admins > 0:
        result = await db.telegram_admins.update_many(
            {"tenant_id": DEFAULT_TENANT_ID},
            {"$set": {"tenant_id": ANAMIKA_TENANT_ID}}
        )
        admin_migrated += result.modified_count

    if no_tenant_admins > 0:
        result = await db.telegram_admins.update_many(
            {"tenant_id": {"$exists": False}},
            {"$set": {"tenant_id": ANAMIKA_TENANT_ID}}
        )
        admin_migrated += result.modified_count

    print(f"  telegram_admins: {admin_migrated} docs migrated")
    total_migrated += admin_migrated

    print(f"\n{'=' * 60}")
    print(f"TOTAL MIGRATED: {total_migrated} documents")
    print(f"{'=' * 60}")

    # Step 5: Verification
    print("\nVERIFICATION:")
    for coll_name in ["bot_users", "subscribers", "payments", "plans", "paid_posts", "live_sessions"]:
        coll = db[coll_name]
        anamika_count = await coll.count_documents({"tenant_id": ANAMIKA_TENANT_ID})
        default_count = await coll.count_documents({"tenant_id": DEFAULT_TENANT_ID})
        no_tenant = await coll.count_documents({"tenant_id": {"$exists": False}})
        total = await coll.count_documents({})
        print(f"  {coll_name}: total={total} | anamika={anamika_count} | default={default_count} | no_tenant={no_tenant}")

    # Revenue check
    pipeline = [
        {"$match": {"tenant_id": ANAMIKA_TENANT_ID, "status": {"$in": ["verified", "approved"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    rev = await db.payments.aggregate(pipeline).to_list(1)
    revenue = rev[0]["total"] if rev else 0
    print(f"\n  Anamika Revenue: Rs.{revenue:,.0f}")

    subs = await db.subscribers.count_documents({"tenant_id": ANAMIKA_TENANT_ID, "status": "active"})
    print(f"  Anamika Active Subscribers: {subs}")

    print(f"\n{'=' * 60}")
    print("MIGRATION COMPLETE!")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
