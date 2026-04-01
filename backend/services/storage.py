"""Emergent Object Storage service for file uploads"""
import os
import uuid
import requests
from config import logger

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "tgsubsbot"

storage_key = None


def init_storage():
    """Initialize storage - call once at startup. Returns reusable storage_key."""
    global storage_key
    if storage_key:
        return storage_key
    if not EMERGENT_KEY:
        logger.error("EMERGENT_LLM_KEY not set - object storage unavailable")
        return None
    try:
        resp = requests.post(
            f"{STORAGE_URL}/init",
            json={"emergent_key": EMERGENT_KEY},
            timeout=30
        )
        resp.raise_for_status()
        storage_key = resp.json()["storage_key"]
        logger.info("Object storage initialized successfully")
        return storage_key
    except Exception as e:
        logger.error(f"Object storage init failed: {e}")
        return None


def put_object(path: str, data: bytes, content_type: str) -> dict:
    """Upload file to object storage. Returns {"path": "...", "size": 123, "etag": "..."}"""
    key = init_storage()
    if not key:
        raise RuntimeError("Object storage not initialized")
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120
    )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str) -> tuple:
    """Download file from object storage. Returns (content_bytes, content_type)."""
    key = init_storage()
    if not key:
        raise RuntimeError("Object storage not initialized")
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=60
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


MIME_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp", "pdf": "application/pdf",
    "mp4": "video/mp4", "mov": "video/quicktime", "avi": "video/x-msvideo",
    "mkv": "video/x-matroska", "webm": "video/webm",
}


def get_content_type(filename: str, fallback: str = "application/octet-stream") -> str:
    """Get MIME type from filename extension"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return MIME_TYPES.get(ext, fallback)


def upload_file(data: bytes, original_filename: str, content_type: str = None, prefix: str = "uploads") -> dict:
    """
    Upload a file to object storage with proper path convention.
    Returns {"storage_path": "tgsubsbot/uploads/uuid.ext", "url": "/api/files/tgsubsbot/uploads/uuid.ext", "size": ...}
    Falls back to local storage if object storage unavailable.
    """
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "bin"
    unique_name = f"{uuid.uuid4().hex[:12]}.{ext}"
    ct = content_type or get_content_type(original_filename)

    # Try object storage first
    try:
        storage_path = f"{APP_NAME}/{prefix}/{unique_name}"
        result = put_object(storage_path, data, ct)
        actual_path = result.get("path", storage_path)
        return {
            "storage_path": actual_path,
            "url": f"/api/files/{actual_path}",
            "original_filename": original_filename,
            "content_type": ct,
            "size": result.get("size", len(data)),
        }
    except Exception as e:
        logger.warning(f"Object storage upload failed, using local fallback: {e}")
        # Fallback to local storage
        uploads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
        os.makedirs(uploads_path, exist_ok=True)
        filepath = os.path.join(uploads_path, unique_name)
        with open(filepath, "wb") as f:
            f.write(data)
        return {
            "storage_path": f"local/{unique_name}",
            "url": f"/api/uploads/{unique_name}",
            "original_filename": original_filename,
            "content_type": ct,
            "size": len(data),
        }
