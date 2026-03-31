# TgSubsBot - Telegram Subscription Bot SaaS Platform

## Original Problem Statement
Build a market-ready SaaS product for Telegram subscription management with Mini App, payments, AI support, and referral system.

## Architecture
```
/app/backend/routes/
├── auth.py, admin.py, core.py, features.py
├── telegram_webhook.py
└── miniapp.py         # Mini App: Plans, Phone Login, UPI Payment, AI Support, Referral, Notifications
/app/frontend/src/pages/
├── MiniApp.jsx + MiniApp.css  # Telegram Mini App (Glassmorphism dark theme)
├── Plans.jsx                  # Fixed channel dropdown
├── Settings.jsx               # Has Mini App config section (QR + UPI)
├── MiniAppUsers.jsx           # Admin dashboard for phone numbers
├── 20+ other pages
```

## Implementation Log

### Mar 31, 2026 - QR Code + Mini App UI Fixes (v4)
- [x] **QR code fix**: Auto-generates UPI QR from UPI ID using `qrcode` library (was showing person's photo)
- [x] **QR auto-generation**: If QR file is missing/invalid, API auto-generates on demand
- [x] **Inline payment**: Payment section now appears directly below the selected plan card (not at bottom)
- [x] **Scrollable UPI sheet**: Bottom sheet has `max-height: 85vh` + `overflow-y: auto`
- [x] **UPI ID visibility**: `word-break: break-all` prevents truncation
- [x] **Telegram bot QR**: `send_telegram_photo` now reads local files and uploads as multipart
- [x] **Testing**: 100% pass (iteration_10: 11/11 backend + all 12 frontend features)

### Mar 31, 2026 - Bug Fixes (v3)
- [x] Channel dropdown fix: Shows `group_name` with `group_id`, filters out "0" values
- [x] Manual Channel ID input added
- [x] UPI QR Code in payment sheet + UPI ID + Copy button
- [x] Testing: 100% pass (iteration_9: 8/8 backend + all frontend)

### Mar 31, 2026 - Mini App v2 (Phone Login, UI Redesign)
- [x] Phone Login (20% discount), Skip option, Discount popup
- [x] Glassmorphism redesign: pure black bg, glass cards, pink accent
- [x] Testing: 100% pass (iteration_8)

### Mar 31, 2026 - Mini App v1 (Base Features)
- [x] Plans, UPI Payment, Coupon codes, AI Support Chat (GPT-5.2)
- [x] Status, Payment History, Referral, Notifications, Help & FAQ
- [x] Testing: 100% pass (iteration_7)

### Previous Sessions
- Backend refactoring (9400 lines -> 79 lines), Docker fix
- Admin Approve/Reject, Branding, PDF Export
- Bot Language, GPT-5.2 AI Verification

## Backlog
- (P0) Production Deploy: "Save to Github" → Coolify redeploy
- (P1) RESEND_API_KEY for email OTP (MOCKED)
- (P2) Custom Domain mapping per tenant
- (P3) WhatsApp integration
- (P3) Multi-language bot support

## Credentials
- Super Admin: gamerxboys8958@gmail.com / Sumit@8958
- Bot Token: 8275964628:AAH8U7ECRII7eyAySt7U2pyDQhLcnZunTnY

## Key Mini App Endpoints
- `POST /api/miniapp/phone-login` - Phone register + 20% discount
- `GET /api/miniapp/upi-details` - UPI ID + QR code URL (auto-generates QR if missing)
- `GET /api/miniapp/plans` - Active plans
- `POST /api/miniapp/apply-coupon` - Validate coupon
- `POST /api/miniapp/support/chat` - AI chatbot (GPT-5.2)
- `GET /api/miniapp/referral/{id}` - Referral code + stats
- `GET /api/miniapp/notifications/{id}` - Notifications
