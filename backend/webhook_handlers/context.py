"""Shared webhook context — passed to all handler functions."""
from dataclasses import dataclass, field


@dataclass
class WebhookContext:
    """Holds shared state for webhook processing.
    Created once per webhook request and passed to handlers."""
    data: dict = field(default_factory=dict)
    bot_token: str = ""
    bot_tenant_id: str = ""
    settings: dict = field(default_factory=dict)
