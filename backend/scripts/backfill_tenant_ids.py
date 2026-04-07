"""Backfill tenant_id on documents missing it — for legacy data migration."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import db
from core.constants import UNRESOLVED_TENANT


TENANT_SCOPED_COLLECTIONS = [
    "plans", "subscribers", "payments", "bot_users", "paid_posts",
    "live_sessions", "broadcasts", "coupons", "telegram_admins",
    "referrals", "miniapp_users", "channels", "chat_groups_pool",
    "chat_sessions", "templates", "scheduled_broadcasts", "user_notes",
    "user_tags", "blocked_users", "faqs", "video_call_bookings",
]


async def backfill(target_tenant_id: str = UNRESOLVED_TENANT):
    """Add tenant_id to any documents that don't have one."""
    print(f"Backfilling tenant_id='{target_tenant_id}' on documents missing it...\n")

    for coll_name in TENANT_SCOPED_COLLECTIONS:
        coll = db[coll_name]
        result = await coll.update_many(
            {"tenant_id": {"$exists": False}},
            {"$set": {"tenant_id": target_tenant_id}}
        )
        if result.modified_count > 0:
            print(f"  {coll_name}: backfilled {result.modified_count} docs")

    print("\nDone!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", default=UNRESOLVED_TENANT)
    args = parser.parse_args()
    asyncio.run(backfill(args.tenant_id))
