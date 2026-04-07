# CHANGELOG

## 2026-04-07 — Strict Tenant Enforcement + Legacy Routes Cleanup (Iteration 43)
- **Backfill**: 24 orphan documents cleaned (21 test users deleted, 2 assigned, Super Admin → __platform__)
- **services/tenant.py**: Rewritten to raise AccessDeniedError instead of silent DEFAULT_TENANT_ID fallback
- **DEFAULT_TENANT_ID**: Completely removed from active codebase → replaced with UNRESOLVED_TENANT sentinel
- **Legacy routes/**: 20 wrapper files deleted, entire folder removed. Zero impact on functionality
- **Verified**: 0 orphan documents across all critical collections, 14/14 tests passed

## 2026-04-07 — QR Code Fixes + Super Admin Toggle
- **QR Code**: Fixed broken QR display (placeholder token → real token, expired Discord CDN → auto-generate)
- **QR Toggle**: Super Admin can enable/disable QR per tenant via SaaS Management
- **UPI ID**: Updated to `36757049@hdfcbank`, styled dark-theme QR generated
- **Plans Synced**: 6 active plans matching dashboard, 3 deactivated, discount strikethrough added

## 2026-04-07 — Telegram Bot /start Fix
- **Root cause**: DB settings had placeholder token `123:VALID_BOT_TOKEN`
- **Fix**: `get_bot_settings()` now resolves real token from tenants collection
- **Missing imports**: Fixed `urgency_timer_task`, `send_screenshot_reminders`, `LlmChat`

## 2026-04-07 — Wallet System (Iteration 42)
- Complete Wallet System: commission config, platform revenue, tenant balance, withdrawal workflow
- 7 API endpoints, WalletPage.jsx with role-aware tabs
- Fixed `log_action()` parameter mismatch

## 2026-04-07 — DDD Architecture (Iteration 41)
- Backend restructured: core/, dependencies/, api/, schemas/, middleware/, scripts/
- 18 route files reorganized with backward-compatible wrappers (now removed)

## 2026-04-07 — P1 Features (Iteration 40)
- Repository Pattern (22 repos), Payment Idempotency, JWT Refresh Tokens
- Scheduler Separation, Frontend Route Guards
