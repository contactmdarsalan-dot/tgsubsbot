# TgSubsBot - Telegram Subscription Bot SaaS Platform

## Original Problem Statement
Build a market-ready SaaS product for Telegram subscription management with Mini App, payments, AI support, and referral system.

## Architecture
```
/app/backend/routes/
├── auth.py, admin.py, core.py, features.py
├── telegram_webhook.py
└── miniapp.py         # Mini App: Plans, Phone Login, UPI Payment, Screenshot Upload + AI Verify, Admin Panel
/app/frontend/src/pages/
├── MiniApp.jsx + MiniApp.css  # Telegram Mini App (Dark glassmorphism)
├── MiniAppUsers.jsx, Settings.jsx, Payments.jsx, Plans.jsx, etc.
```

## Implementation Log

### Mar 31, 2026 - Screenshot Upload + Copy Fix (v6)
- [x] **Copy button**: Fixed clipboard API + textarea fallback for Telegram WebApp + showAlert
- [x] **Screenshot upload**: "I've Paid" → upload screen → "Upload & Verify" button
- [x] **AI Verification**: GPT-5.2 Vision analyzes screenshots, auto-approves real payments
- [x] **Payment record**: Creates record with screenshot_url, notifies admins via Telegram
- [x] **Dashboard fix**: Payment modal now uses direct URL (was blob fetch failing)
- [x] **Testing**: 100% pass (iteration_12: 9/9 backend + all frontend)

### Mar 31, 2026 - Admin Panel in Mini App (v5)
- [x] Stats Dashboard, Payment Verification, Broadcast, Live Sessions, Subscribers
- [x] Testing: 100% pass (iteration_11: 20/20 backend + all frontend)

### Mar 31, 2026 - QR Code + UI Fixes (v4)
- [x] Auto-generates UPI QR from UPI ID, inline payment, scrollable sheet
- [x] Testing: 100% pass (iteration_10)

### Previous: Mini App v1-v3, Backend refactoring, Layout fixes, etc.

## Backlog
- (P0) Production Deploy: "Save to Github" → Coolify redeploy
- (P1) RESEND_API_KEY added but domain not verified → verify domain at resend.com/domains
- (P2) Custom Domain mapping per tenant
- (P3) WhatsApp integration
- (P3) Multi-language bot support

## Credentials
- Super Admin: gamerxboys8958@gmail.com / Sumit@8958
- Test Admin Telegram ID: 123456789
- Bot Token: 8275964628:AAH8U7ECRII7eyAySt7U2pyDQhLcnZunTnY

## Key Endpoints
- `POST /api/miniapp/upload-screenshot` - Upload screenshot + AI verify
- `GET /api/miniapp/upi-details` - UPI ID + QR code (auto-generates)
- `GET/POST /api/miniapp/admin/*` - Admin panel endpoints
- `GET /api/miniapp/plans` - Active plans
