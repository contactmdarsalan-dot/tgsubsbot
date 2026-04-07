"""Tenant schemas."""
from pydantic import BaseModel
from typing import Optional


class TenantCreate(BaseModel):
    name: str
    owner_email: str
    plan: str = "free"


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    plan: Optional[str] = None
