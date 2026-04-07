"""Application-wide constants and enums."""


class Roles:
    SUPER_ADMIN = "super_admin"
    TENANT_OWNER = "tenant_owner"
    TENANT_ADMIN = "tenant_admin"
    BOT_ADMIN = "bot_admin"
    ADMIN = "admin"

    PLATFORM_ROLES = {SUPER_ADMIN}
    TENANT_ROLES = {TENANT_OWNER, TENANT_ADMIN, BOT_ADMIN, ADMIN}
    ALL_ADMIN_ROLES = PLATFORM_ROLES | TENANT_ROLES


class SubscriptionStatus:
    ACTIVE = "active"
    EXPIRED = "expired"
    GRACE = "grace"
    CANCELLED = "cancelled"
    TRIAL = "trial"


class PaymentStatus:
    PENDING = "pending"
    VERIFIED = "verified"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


class BroadcastStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Tenant isolation sentinel — replaces old "default" fallback
UNRESOLVED_TENANT = "__unresolved_tenant__"
