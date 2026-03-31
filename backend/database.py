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
