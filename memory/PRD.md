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
- Impersonation Mode + Risk & Alerts Dashboard
- Payment Idempotency via MongoDB-based dedup locks
- DDD backend architecture with backward-compatible wrappers

## Wallet System
- **Commission**: Configurable (percentage or fixed per transaction)
- **Withdrawal Rules**: Min amount, max per day, processing days, auto-approve threshold
- **Flow**: Tenant requests → Super Admin approves → Super Admin marks paid
- **Balance Calculation**: Total revenue - commission - approved withdrawals - pending

## Key API Endpoints
- Auth: `/api/auth/login`, `/api/auth/register`, `/api/auth/refresh`, `/api/auth/logout`
- Wallet: `/api/wallet/config`, `/api/wallet/platform-revenue`, `/api/wallet/balance`, `/api/wallet/withdraw`, `/api/wallet/all-withdrawals`, `/api/wallet/withdrawals/{id}/approve|reject|complete`
- Admin: `/api/admin/impersonate`, `/api/admin/risk-alerts`, `/api/saas/tenants`
- Webhook: `/api/telegram/webhook`

## 3rd Party Integrations
- Telegram WebApp SDK & Bot API
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
- QR Code URL in settings (`https://NEW-QR.com/new.png`) returns invalid content type for Telegram
- Webhook currently pointing to preview URL (needs production deployment)
