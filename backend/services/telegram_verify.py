"""Telegram WebApp init data verification.
Validates that Mini App requests come from real Telegram users, not forged browser requests."""
import hmac
import hashlib
import json
from urllib.parse import parse_qs
from config import logger


def validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """Validate Telegram WebApp initData using HMAC-SHA256.
    
    Returns parsed user dict if valid, None if invalid/tampered.
    """
    if not init_data or not bot_token:
        return None

    try:
        parsed = parse_qs(init_data)
        received_hash = parsed.pop('hash', [None])[0]
        if not received_hash:
            return None

        # Sort and build data check string
        sorted_items = sorted(parsed.items())
        data_check_string = '\n'.join(f"{k}={v[0]}" for k, v in sorted_items)

        # HMAC("WebAppData", bot_token) → secret key
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode('utf-8'),
            hashlib.sha256
        ).digest()

        # HMAC(secret_key, data_check_string) → computed hash
        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            return None

        # Parse user data
        user_data = parsed.get('user', [None])[0]
        if user_data:
            return json.loads(user_data)
        return None

    except Exception as e:
        logger.error(f"Telegram init data validation error: {e}")
        return None


def extract_telegram_user_id(init_data: str, bot_token: str) -> str | None:
    """Extract verified Telegram user ID from init data. Returns None if invalid."""
    user = validate_telegram_init_data(init_data, bot_token)
    if user:
        return str(user.get("id", ""))
    return None
