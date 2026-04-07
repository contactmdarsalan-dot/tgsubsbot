"""Broadcast schemas."""
from pydantic import BaseModel
from typing import List


class BroadcastRequest(BaseModel):
    message: str
    target_segment: str = "all"
    buttons: list = []
    include_promo: bool = False


class RenewalBroadcastRequest(BaseModel):
    target: str = "all"
    message: str = ""
    discount_percent: int = 0
    video_note_file_id: str = ""
