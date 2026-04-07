# CHANGELOG

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
