# TgSubsBot - Telegram Subscription Bot SaaS Platform

## Original Problem Statement
Build a market-ready SaaS product for Telegram subscription management with Mini App, payments, AI support, and referral system.

## Architecture
```
/app/backend/routes/
├── auth.py, admin.py, core.py, features.py
├── telegram_webhook.py
└── miniapp.py         # Mini App: Plans, Phone Login, UPI Payment, AI Support, Referral, Notifications, ADMIN PANEL
/app/frontend/src/pages/
├── MiniApp.jsx + MiniApp.css  # Telegram Mini App (Dark glassmorphism theme)
├── MiniAppUsers.jsx           # Admin dashboard for phone numbers
├── Settings.jsx               # Mini App config (QR + UPI)
├── Plans.jsx, Payments.jsx, etc.
```

## Implementation Log

### Mar 31, 2026 - Admin Panel in Mini App (v5)
- [x] **Admin Panel**: Full admin dashboard inside Mini App with permission-based access
- [x] **Stats Dashboard**: Revenue, Active Subs, Total Users, Pending Payments
- [x] **Payment Verification**: Approve/Reject pending payments with screenshots, auto-notifies users via Telegram
- [x] **Broadcast**: Send messages to all bot users from Mini App
- [x] **Live Sessions**: Create, manage, and announce live sessions to subscribers
- [x] **Subscribers List**: View all subscribers with plan details
- [x] **Permission-based**: Each admin only sees actions they have permission for
- [x] **Testing**: 100% pass (iteration_11: 20/20 backend + all frontend)

### Mar 31, 2026 - QR Code + Mini App UI Fixes (v4)
- [x] Auto-generates UPI QR from UPI ID using qrcode library
- [x] Inline payment section below selected plan (not at bottom)
- [x] Scrollable UPI sheet, UPI ID word-break fix
- [x] Telegram bot local file upload for QR
- [x] Testing: 100% pass (iteration_10)

### Previous Sessions
- Mini App v1-v3: Plans, UPI Payment, AI Support Chat (GPT-5.2), Phone Login, Glassmorphism UI
- Backend refactoring (9400 lines -> 79 lines), Docker fix
- Channel management, Layout fixes, Profile page, Forgot Password
- Payment optimization, Tenant/Platform Users, Support CRUD

## Backlog
- (P0) Production Deploy: "Save to Github" -> Coolify redeploy
- (P1) RESEND_API_KEY for email OTP (MOCKED)
- (P2) Custom Domain mapping per tenant
- (P3) WhatsApp integration
- (P3) Multi-language bot support

## Credentials
- Super Admin: gamerxboys8958@gmail.com / Sumit@8958
- Test Admin Telegram ID: 123456789
- Bot Token: 8275964628:AAH8U7ECRII7eyAySt7U2pyDQhLcnZunTnY

## Key Mini App Admin Endpoints
- `GET /api/miniapp/admin/check/{tg_id}` - Check admin status + permissions
- `GET /api/miniapp/admin/stats/{tg_id}` - Dashboard stats
- `GET /api/miniapp/admin/pending-payments/{tg_id}` - Pending payments list
- `POST /api/miniapp/admin/payment-action` - Approve/Reject payment
- `GET /api/miniapp/admin/subscribers/{tg_id}` - Subscribers list
- `POST /api/miniapp/admin/broadcast` - Send broadcast
- `GET /api/miniapp/admin/live-sessions/{tg_id}` - Live sessions list
- `POST /api/miniapp/admin/live-session` - Create live session
- `POST /api/miniapp/admin/announce-live/{session_id}` - Announce live
