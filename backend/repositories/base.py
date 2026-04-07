"""Base repository with mandatory tenant scoping.
All tenant-owned collections MUST go through this layer.
Prevents raw db access from routes bypassing tenant isolation."""
from database import db
from config import logger
from datetime import datetime, timezone


class TenantScopedRepository:
    """Repository that ALWAYS enforces tenant_id on reads and writes.
    Usage: repo = TenantScopedRepository("plans")
           await repo.find_many(tenant_id, {"is_active": True})
    """

    def __init__(self, collection_name: str):
        self.collection = db[collection_name]
        self.collection_name = collection_name

    def _scope(self, tenant_id: str, query: dict = None) -> dict:
        """Add tenant_id to query. Raises if tenant_id is empty."""
        q = dict(query) if query else {}
        if not tenant_id:
            raise ValueError(f"tenant_id is required for {self.collection_name} queries")
        q["tenant_id"] = tenant_id
        return q

    async def find_one(self, tenant_id: str, query: dict, projection: dict = None):
        """Find one document scoped to tenant."""
        proj = projection or {}
        proj["_id"] = 0
        return await self.collection.find_one(self._scope(tenant_id, query), proj)

    async def find_many(self, tenant_id: str, query: dict = None, 
                        projection: dict = None, sort=None, limit: int = 1000):
        """Find many documents scoped to tenant."""
        proj = projection or {}
        proj["_id"] = 0
        cursor = self.collection.find(self._scope(tenant_id, query), proj)
        if sort:
            cursor = cursor.sort(sort)
        return await cursor.to_list(limit)

    async def count(self, tenant_id: str, query: dict = None) -> int:
        """Count documents scoped to tenant."""
        return await self.collection.count_documents(self._scope(tenant_id, query))

    async def insert_one(self, tenant_id: str, doc: dict):
        """Insert one document with tenant_id enforced."""
        doc["tenant_id"] = tenant_id
        if "created_at" not in doc:
            doc["created_at"] = datetime.now(timezone.utc).isoformat()
        result = await self.collection.insert_one(doc)
        return result

    async def update_one(self, tenant_id: str, query: dict, update: dict):
        """Update one document scoped to tenant."""
        if "updated_at" not in update.get("$set", {}):
            update.setdefault("$set", {})["updated_at"] = datetime.now(timezone.utc).isoformat()
        return await self.collection.update_one(self._scope(tenant_id, query), update)

    async def update_many(self, tenant_id: str, query: dict, update: dict):
        """Update many documents scoped to tenant."""
        return await self.collection.update_many(self._scope(tenant_id, query), update)

    async def delete_one(self, tenant_id: str, query: dict):
        """Delete one document scoped to tenant."""
        return await self.collection.delete_one(self._scope(tenant_id, query))

    async def delete_many(self, tenant_id: str, query: dict = None):
        """Delete many documents scoped to tenant."""
        return await self.collection.delete_many(self._scope(tenant_id, query))

    async def find_one_global(self, query: dict, projection: dict = None):
        """Find one document WITHOUT tenant scoping (for super admin / platform ops only).
        MUST be explicitly called — never the default."""
        proj = projection or {}
        proj["_id"] = 0
        return await self.collection.find_one(query, proj)

    async def find_many_global(self, query: dict = None, projection: dict = None, 
                               sort=None, limit: int = 1000):
        """Find many documents WITHOUT tenant scoping (for super admin / platform ops only)."""
        proj = projection or {}
        proj["_id"] = 0
        cursor = self.collection.find(query or {}, proj)
        if sort:
            cursor = cursor.sort(sort)
        return await cursor.to_list(limit)

    async def aggregate(self, tenant_id: str, pipeline: list):
        """Run aggregation pipeline scoped to tenant."""
        scoped_pipeline = [{"$match": {"tenant_id": tenant_id}}] + pipeline
        return await self.collection.aggregate(scoped_pipeline).to_list(1000)

    async def aggregate_global(self, pipeline: list):
        """Run aggregation pipeline without tenant scope (super admin only)."""
        return await self.collection.aggregate(pipeline).to_list(1000)


# Pre-instantiated repositories for all tenant-owned collections
plans_repo = TenantScopedRepository("plans")
subscribers_repo = TenantScopedRepository("subscribers")
payments_repo = TenantScopedRepository("payments")
bot_users_repo = TenantScopedRepository("bot_users")
paid_posts_repo = TenantScopedRepository("paid_posts")
live_sessions_repo = TenantScopedRepository("live_sessions")
broadcasts_repo = TenantScopedRepository("broadcasts")
coupons_repo = TenantScopedRepository("coupons")
telegram_admins_repo = TenantScopedRepository("telegram_admins")
referrals_repo = TenantScopedRepository("referrals")
miniapp_users_repo = TenantScopedRepository("miniapp_users")
