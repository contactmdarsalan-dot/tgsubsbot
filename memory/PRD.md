# TgSubsBot - Production SaaS Platform

## Original Problem Statement
Transforming a Telegram Subscription Bot into a scalable, market-ready SaaS product with full Multi-Tenant isolation, distinct RBAC, dynamic subscription plans, analytical Super Admin Dashboard, conversion-focused Landing Page & Mini App, and centralized Wallet System.

## Architecture (DDD)
- **Backend**: FastAPI with Repository Pattern, organized into `core/`, `dependencies/`, `api/`, `schemas/`, `middleware/`, `workers/`
- **Frontend**: React with role-based route guards (SuperAdminRoute, TenantRoute, ProtectedRoute)
- **Database**: MongoDB (shared DB, strict tenant_id isolation via TenantScopedRepository)
- **Auth**: JWT access (2hr) + refresh (30d) tokens with token_version for forced logout
- **Scheduler**: APScheduler with MongoDB distributed locks (embedded + standalone)
- **Wallet**: Centralized payment collection → commission deduction → tenant withdrawal system

## Key Features
- Multi-tenant SaaS with strict row-level isolation (22 repository instances)
- RBAC: Super Admin, Tenant Owner, Tenant Admin, Bot Admin
- Wallet System: All payments → Super Admin Razorpay → tenants request withdrawals
- QR Code Toggle: Super Admin controls QR payment option per-tenant
- Payment Idempotency via MongoDB-based dedup locks
- DDD backend architecture with backward-compatible wrappers
- Auto-QR generation from UPI ID when external URLs are broken
- Discount strikethrough display in bot plan messages

## Wallet System
- **Commission**: Configurable (percentage or fixed per transaction)
- **Withdrawal Rules**: Min amount, max per day, processing days, auto-approve threshold
- **Flow**: Tenant requests → Super Admin approves → Super Admin marks paid

## Key API Endpoints
- Auth: `/api/auth/login`, `/api/auth/register`, `/api/auth/refresh`, `/api/auth/logout`
- Wallet: `/api/wallet/config`, `/api/wallet/platform-revenue`, `/api/wallet/balance`, `/api/wallet/withdraw`
- Admin: `/api/saas/tenants` (GET/POST/PUT with qr_enabled field)
- Webhook: `/api/telegram/webhook`

## 3rd Party Integrations
- Telegram WebApp SDK & Bot API (Token: 8275964628:AAH8...)
- Razorpay Payments (with idempotency locks)
- Resend Email OTPs (MOCKED)
- OpenAI GPT-5.2 Vision (Emergent LLM Key)

## Remaining Backlog
- (P1) Strict Tenant Enforcement — run backfill script, remove "default" fallback
- (P1) Phase out legacy routes/ wrapper files
- (P2) Object Storage migration (S3/R2)
- (P2) Analytics Dashboard (Razorpay vs QR comparison)
- (P3) WhatsApp integration
- (P3) Multi-language bot support

## Known Issues
- Webhook currently pointing to preview URL (needs production deployment)
- Some Telegram channels return 403 (bot can't initiate conversation with users who haven't started the bot)
