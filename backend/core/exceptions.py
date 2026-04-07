"""Application-wide exception classes for consistent error handling."""
from fastapi import HTTPException


class TenantNotFoundError(HTTPException):
    def __init__(self):
        super().__init__(status_code=400, detail="No tenant associated with this user")


class AccessDeniedError(HTTPException):
    def __init__(self, detail: str = "Access denied"):
        super().__init__(status_code=403, detail=detail)


class ResourceNotFoundError(HTTPException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(status_code=404, detail=f"{resource} not found")


class DuplicateResourceError(HTTPException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(status_code=409, detail=f"{resource} already exists")


class TokenExpiredError(HTTPException):
    def __init__(self):
        super().__init__(status_code=401, detail="Token expired")


class TokenRevokedError(HTTPException):
    def __init__(self):
        super().__init__(status_code=401, detail="Token revoked. Please login again.")


class InvalidTokenError(HTTPException):
    def __init__(self):
        super().__init__(status_code=401, detail="Invalid token")
