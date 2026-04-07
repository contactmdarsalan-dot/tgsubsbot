# CHANGELOG

## 2026-04-07 — P1 Features Completion (Iteration 40)
- **Repository Pattern Complete Migration**: Migrated `dashboard.py`, `broadcasts.py`, `engagement.py` to use `TenantScopedRepository`. All tenant-owned collections (channels, chat_groups, chat_sessions, templates, scheduled_broadcasts, user_notes, user_tags, blocked_users, faqs, video_call_bookings) now use strict tenant scoping.
- **Payment Idempotency**: Added MongoDB-based idempotency locks (`acquire_idempotency_lock`, `mark_idempotency_complete`) to Razorpay webhook callbacks and bot-checkout verify endpoints. Prevents double-crediting on retry/duplicate callbacks.
- **JWT Refresh Token Architecture**: Implemented access tokens (2hr expiry) + refresh tokens (30d expiry) + `token_version` for forced logout. New endpoints: `POST /api/auth/refresh`, `POST /api/auth/logout`, `POST /api/auth/force-logout/{user_id}`.
- **Scheduler Process Separation**: Refactored `workers/scheduler.py` to support both embedded (default) and standalone modes via `SCHEDULER_MODE` env var. Can be run as `python -m workers.scheduler` for horizontal scaling.
- **Frontend Role-based Route Guards**: Enhanced `ProtectedRoute` with client-side JWT expiry check and refresh token flow. `SuperAdminRoute` and `TenantRoute` guards properly isolate routes by role.
- **CRITICAL BUG FIX**: `create_token()` was not including `token_version` in JWT payload — all tokens failed validation after any logout. Fixed by testing agent.

## Previous Sessions
- Strict Row-Level Tenant Isolation enforced
- SUPER_ADMIN_EMAILS bypass eliminated — strict RBAC only
- DEFAULT_TENANT_ID fallback eradicated
- Webhook refactoring (4300 lines → modular handlers)
- APScheduler extraction to workers/scheduler.py
- Impersonation Mode + Risk & Alerts Dashboard
- High-conversion Landing Page redesign
- Complete CRUD for Tenant Admins and Subscriptions
- Security: .env properly ignored in .gitignore
