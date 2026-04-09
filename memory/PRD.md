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
- Dynamic Payment Methods per-tenant (Razorpay, eSewa, Khalti, Mobile Banking)
- Payment Idempotency via MongoDB-based dedup locks
- DDD backend architecture (legacy routes/ deleted)
- Discount strikethrough display in bot plan messages
- Mini App dynamically shows only enabled payment methods per-tenant
- **Paid Post Unlock: Direct Razorpay payment** (no manual screenshot flow)

## Wallet System
- **Commission**: Configurable (percentage or fixed per transaction)
- **Withdrawal Rules**: Min amount, max per day, processing days, auto-approve threshold
- **Flow**: Tenant requests → Super Admin approves → Super Admin marks paid

## Key API Endpoints
- Auth: `/api/auth/login`, `/api/auth/register`, `/api/auth/refresh`, `/api/auth/logout`
- Wallet: `/api/wallet/config`, `/api/wallet/platform-revenue`, `/api/wallet/balance`, `/api/wallet/withdraw`
- Admin: `/api/saas/tenants` (GET/POST/PUT with payment_methods field)
- Mini App: `/api/miniapp/payment-methods` (tenant-aware, returns only enabled methods)
- Webhook: `/api/telegram/webhook`
- Razorpay Callback: `/api/razorpay/callback` (handles subscriptions + paid post unlocks)

## Paid Post Unlock Flow (Razorpay Only)
1. User clicks "Unlock Post" button on channel post
2. Bot creates Razorpay payment link with post price
3. Shows "Pay ₹X - Unlock Post/Video" button (direct Razorpay link)
4. After payment, Razorpay callback → auto-unlock → sends content via bot

## 3rd Party Integrations
- Telegram WebApp SDK & Bot API
- Razorpay Payments (subscriptions + paid post unlocks)
- Resend Email OTPs (MOCKED)
- OpenAI GPT-5.2 Vision (Emergent LLM Key)

## Remaining Backlog
- (P2) SaaSManagement.jsx refactoring (too large >1100 lines)
- (P2) Object Storage migration (S3/R2)
- (P2) Analytics Dashboard (Razorpay vs Custom payments)
- (P2) Clean up subscription renewal/discount flows to use Razorpay links
- (P3) WhatsApp integration
- (P3) Multi-language bot support

## Known Issues
- Webhook currently pointing to preview URL (needs production deployment)
- Some Telegram channels return 403 (bot can't initiate conversation with users who haven't started the bot)

## Recent Changes (April 2026)
- Fixed Plans.jsx: Removed conflicting Select dropdown for Channel ID, replaced with clean manual input field
- Channel ID can now be manually typed without being overridden by dropdown state
- Added QR/UPI payment option alongside Razorpay in Telegram bot for ALL services:
  - Subscription Plans: "Pay via QR/UPI" button next to Razorpay
  - Paid Post Unlock: QR button for content unlock
  - Video Call Booking: QR option for video call payments
  - Live Tickets: QR code shown with Razorpay option
- QR flow: User clicks QR button → Bot sends QR image → User pays and sends screenshot → Auto-verify (OCR+AI) or Admin review
- Fixed: QR upload path bug (dashboard.py was saving to wrong directory)
- Fixed: send_telegram_photo now handles full URLs, local paths, and adds fallback when photo fails
