# CHANGELOG — TgSubsBot

## Phase 22: Production Security Hardening (2026-04-07)
- **JWT Enhanced**: Token payload now includes `role`, `tenant_id` alongside `user_id` + `exp`
- **Email-based super admin bypass REMOVED**: `is_super_admin()`, `is_any_admin()` now check `user.role` only
- **SUPER_ADMIN_EMAILS removed from all route files**: admin.py, auth.py, tenant.py cleaned
- **JWT_SECRET production guard**: If `ENVIRONMENT=production` and no `JWT_SECRET`, server crashes on startup
- **Super Admin Bootstrap**: Startup ensures SUPER_ADMIN_EMAILS users have `role='super_admin'` in DB
- **RequestContext Middleware**: Every response includes `X-Request-ID` header for traceability
- **Compound indexes**: Added `(tenant_id, id)` compound indexes on all 12 business collections
- **Repository pattern**: Created `repositories/base.py` with `TenantScopedRepository` class
- **Fixed `is_super_admin` shadowing bug**: auth.py support ticket routes were reassigning the function name to a local variable
- **Fixed duplicate function name**: admin.py had two `update_tenant_admin` functions
- **Audit service enhanced**: Now supports `before_state`, `after_state`, `request_id` fields
- **Missing tenant filters fixed**: subscribers.py `plans.find({})` and `subscribers.find(active)` now use `tq()`
- **Tested**: 16/16 tests passed (iteration_36.json)

## Phase 21: Critical Multi-Tenant Data Isolation Fix (2026-04-05)
- Added `tenant_id` filter to 50+ DB queries in telegram_webhook.py and miniapp_user.py

## Phase 20: Enhanced Tenant Management (2026-04-05)
- Complete CRUD for Tenant Management with Change Owner, Permanent Delete, Reactivate
- Data Isolation Report tab

## Phase 19: Razorpay Bot Payment Integration (2026-04-04)
- Razorpay Payment Links in Telegram Bot flow

## Phase 18: Telegram Bot Command Fix (2026-04-04)
- Fixed `/start` command URL button validation
- All commands now pass bot_token explicitly
