# TgSubsBot - Production SaaS Platform

## Original Problem Statement
Transforming a Telegram Subscription Bot into a scalable, market-ready SaaS product with full Multi-Tenant isolation, distinct RBAC, dynamic subscription plans, analytical Super Admin Dashboard, and conversion-focused Landing Page & Mini App.

## Architecture (DDD — Domain-Driven Design)
```
backend/
├── server.py              # Entry point — app setup, middleware, router inclusion
├── core/                  # Infrastructure layer
│   ├── config.py          # Environment variables, logger, external clients
│   ├── db.py              # MongoDB + Redis connections, indexes
│   ├── rate_limiter.py    # Slowapi rate limiter instance
│   ├── exceptions.py      # Application-wide exception classes
│   └── constants.py       # Role enums, status enums, sentinel values
├── middleware/             # Request processing middleware
│   ├── request_id.py      # Unique request ID injection
│   └── idempotency.py     # MongoDB-based dedup locks for payments
├── dependencies/           # FastAPI dependencies (DI)
│   ├── auth.py            # JWT validation, get_current_user, token creation
│   └── permissions.py     # RBAC enforcement, tenant resolution, tq()
├── api/                   # Routes organized by audience
│   ├── public/            # Unauthenticated (auth, registration)
│   │   └── auth.py
│   ├── tenant_admin/      # Tenant-scoped operations
│   │   ├── dashboard.py, plans.py, subscribers.py, payments.py
│   │   ├── broadcasts.py, engagement.py, live_content.py
│   │   ├── analytics_exports.py, tenant.py, miniapp_admin.py
│   ├── platform_admin/    # Super admin / SaaS management
│   │   └── admin.py
│   ├── customer/          # End-user facing (mini app, wallet)
│   │   ├── miniapp_user.py, miniapp_calls.py, miniapp_chat.py
│   │   └── global_wallet.py, global_app.py
│   └── webhooks/          # External callback handlers
│       ├── telegram.py
│       └── razorpay.py
├── schemas/               # Pydantic request/response models
│   ├── auth.py, tenant.py, plan.py, payment.py, broadcast.py
├── repositories/          # Strict tenant-scoped DB access layer
│   └── base.py            # TenantScopedRepository (22 collection instances)
├── services/              # Business logic services
│   ├── telegram.py, background_tasks.py, chat_pool.py
│   ├── audit.py, payment.py, email_service.py, storage.py
├── workers/               # Background jobs
│   └── scheduler.py       # APScheduler (embedded + standalone modes)
├── webhook_handlers/      # Telegram bot message handlers
│   ├── channel_posts.py, callbacks.py, messages.py, context.py
├── scripts/               # Operational scripts
│   ├── verify_isolation.py, rebuild_indexes.py, backfill_tenant_ids.py
├── routes/                # BACKWARD COMPAT wrappers (re-export from api/)
└── tests/                 # Pytest test files (40+ iterations)
```

## Auth: JWT with access (2hr) + refresh (30d) tokens. token_version for forced logout.
## DB: MongoDB shared DB, strict tenant_id isolation via Repository pattern.
## Scheduler: APScheduler with distributed MongoDB locks (embedded or standalone).

## Key API Endpoints
- POST /api/auth/login, /api/auth/register, /api/auth/refresh, /api/auth/logout
- POST /api/auth/force-logout/{user_id} (Super Admin)
- GET /api/analytics, /api/plans, /api/subscribers, /api/broadcasts
- GET /api/saas/tenants, /api/admin/risk-alerts (Platform Admin)
- POST /api/admin/impersonate (Super Admin)

## 3rd Party Integrations
- Telegram WebApp SDK & Bot API
- Razorpay Payments (with idempotency locks)
- Resend Email OTPs (MOCKED)
- OpenAI GPT-5.2 Vision (Emergent LLM Key)

## Remaining Backlog
- (P2) Move file uploads to Object Storage (S3/R2)
- (P2) Analytics Dashboard (Razorpay vs QR comparison)
- (P3) WhatsApp integration
- (P3) Multi-language bot support
