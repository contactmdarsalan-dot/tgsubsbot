"""Plan schemas."""
from pydantic import BaseModel
from typing import List


class PlanCreate(BaseModel):
    name: str
    price: float
    duration_days: int
    features: List[str] = []
    is_active: bool = True
    channel_id: str = ""
    group_id: str = ""
    auto_assign_group: bool = False
    discount_percentage: int = 0
