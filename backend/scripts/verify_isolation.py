"""Verify tenant isolation — checks that no collection has documents without tenant_id."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import db


TENANT_SCOPED_COLLECTIONS = [
    "plans", "subscribers", "payments", "bot_users", "paid_posts",
    "live_sessions", "broadcasts", "coupons", "telegram_admins",
    "referrals", "miniapp_users", "channels", "chat_groups_pool",
    "chat_sessions", "templates", "scheduled_broadcasts", "user_notes",
    "user_tags", "blocked_users", "faqs", "video_call_bookings",
]


async def verify_isolation():
    print("=== Tenant Isolation Verification ===\n")
    issues = 0

    for coll_name in TENANT_SCOPED_COLLECTIONS:
        coll = db[coll_name]
        total = await coll.count_documents({})
        missing_tid = await coll.count_documents({"tenant_id": {"$exists": False}})
        empty_tid = await coll.count_documents({"tenant_id": ""})

        status = "OK" if (missing_tid == 0 and empty_tid == 0) else "VIOLATION"
        if status == "VIOLATION":
            issues += 1

        print(f"  [{status}] {coll_name}: total={total}, missing_tenant_id={missing_tid}, empty_tenant_id={empty_tid}")

    print(f"\n{'ALL CLEAR' if issues == 0 else f'{issues} VIOLATIONS FOUND'}")
    return issues == 0


if __name__ == "__main__":
    asyncio.run(verify_isolation())
