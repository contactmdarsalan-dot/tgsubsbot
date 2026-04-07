"""Authentication service - password hashing, JWT tokens, user verification"""
from database import db
from config import JWT_SECRET, logger
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
import secrets

security = HTTPBearer()

# Token durations
ACCESS_TOKEN_EXPIRY = timedelta(hours=2)
REFRESH_TOKEN_EXPIRY = timedelta(days=30)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: str, role: str = "", tenant_id: str = "", token_version: int = 0) -> str:
    """Create short-lived access JWT. Includes role, tenant_id, and token_version for faster auth."""
    payload = {
        "user_id": user_id,
        "role": role,
        "tenant_id": tenant_id,
        "type": "access",
        "token_version": token_version,
        "exp": datetime.now(timezone.utc) + ACCESS_TOKEN_EXPIRY
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def create_refresh_token(user_id: str) -> str:
    """Create long-lived refresh JWT tied to user's token_version."""
    payload = {
        "user_id": user_id,
        "type": "refresh",
        "jti": secrets.token_hex(16),
        "exp": datetime.now(timezone.utc) + REFRESH_TOKEN_EXPIRY
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        # Reject refresh tokens used as access tokens
        if payload.get("type") == "refresh":
            raise HTTPException(status_code=401, detail="Refresh token cannot be used for API access")
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        # Check token_version — if user has been force-logged-out, reject
        user_token_version = user.get("token_version", 0)
        token_version = payload.get("token_version", 0)
        if token_version < user_token_version:
            raise HTTPException(status_code=401, detail="Token revoked. Please login again.")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
