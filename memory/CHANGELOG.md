# CHANGELOG

## 2026-04-07 — Telegram Bot /start Command Fix
- **Root cause**: `settings` collection had placeholder token `123:VALID_BOT_TOKEN`, `get_bot_settings()` never fell through to real token
- **Fix**: `get_bot_settings()` now resolves token from `tenants` collection via `tenant_id` (Priority: tenant token > env var > settings)
- **DB**: Updated `settings.telegram_bot_token` with real token
- **Imports**: Fixed missing `urgency_timer_task`, `send_screenshot_reminders`, `get_bot_username` in `callbacks.py`; Added `LlmChat` import in `messages.py`
- **Webhook**: Set to preview URL for live testing — verified with real user traffic (200 OK)

## 2026-04-07 — Wallet System (Iteration 42)
- **Full Wallet System implemented**: Central payment collection, commission management, tenant withdrawal workflow
- **Backend**: 7 API endpoints — config CRUD, platform revenue overview, tenant balance, withdrawal request/approve/reject/complete
- **Frontend**: WalletPage.jsx with role-aware tabs (Super Admin: 4 tabs, Tenant: 2 tabs), withdrawal form, revenue stats
- **Sidebar**: Wallet link added for both Super Admin (Platform section) and Tenant Admin (Account section)
- **Fixed**: `log_action()` parameter mismatch in audit logging calls

## 2026-04-07 — DDD Architecture Restructuring (Iteration 41)
- Complete backend restructure: `core/`, `dependencies/`, `api/` (public/tenant_admin/platform_admin/customer/webhooks), `schemas/`, `middleware/`, `scripts/`
- 18 route files reorganized with backward-compatible re-export wrappers

## 2026-04-07 — P1 Features Completion (Iteration 40)
- Repository Pattern Migration (22 repos), Payment Idempotency, JWT Refresh Tokens, Scheduler Separation, Frontend Route Guards

## Previous Sessions
- Strict Tenant Isolation, SUPER_ADMIN_EMAILS removal, DEFAULT_TENANT_ID elimination
- Webhook refactoring, Impersonation Mode, Risk & Alerts Dashboard
- Landing Page redesign, Tenant Registration UI, SaaS Management CRUD
