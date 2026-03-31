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
├── Settings.jsx               # Has Mini App config section
├── 20+ other pages
```

## Implementation Log

### Mar 31, 2026 - Bug Fixes (v3)
- [x] **Channel dropdown fix**: Shows `group_name` with `group_id`, filters out "0" values
- [x] **Manual Channel ID input**: Added text input to manually type channel ID alongside dropdown
- [x] **Razorpay OFF**: Completely removed from Mini App, only UPI payment
- [x] **UPI QR Code**: Payment sheet now shows QR code image from website settings + UPI ID + Copy button
- [x] **UPI Details endpoint**: Returns `qr_code_url` from bot settings
- [x] **Testing**: 100% pass (iteration_9: 8/8 backend + all frontend)

### Mar 31, 2026 - Mini App v2 (Phone Login, UI Redesign)
- [x] Phone Login (20% discount), Skip option, Discount popup
- [x] Glassmorphism redesign: pure black bg, glass cards, pink accent
- [x] Testing: 100% pass (iteration_8)

### Mar 31, 2026 - Mini App v1 (Base Features)
- [x] Plans, UPI Payment, Coupon codes, AI Support Chat (GPT-5.2)
- [x] Status, Payment History, Referral, Notifications, Help & FAQ
- [x] Testing: 100% pass (iteration_7)

### Previous Sessions
- Backend refactoring, Docker fix, Admin Approve/Reject
- Branding, PDF Export, Bot Language, GPT-5.2 AI Verification

## Backlog
- (P0) Production Deploy: "Save to Github" → Coolify redeploy
- (P1) RESEND_API_KEY for email OTP (MOCKED)
- (P2) Re-enable Razorpay when user is ready
- (P2) WhatsApp integration

## Credentials
- Super Admin: gamerxboys8958@gmail.com / Sumit@8958
- Bot Token: 8275964628:AAH8U7ECRII7eyAySt7U2pyDQhLcnZunTnY

## Key Mini App Endpoints
- `POST /api/miniapp/phone-login` - Phone register + 20% discount
- `GET /api/miniapp/upi-details` - UPI ID + QR code URL + payment message
- `GET /api/miniapp/plans` - Active plans
- `POST /api/miniapp/apply-coupon` - Validate coupon
- `POST /api/miniapp/support/chat` - AI chatbot (GPT-5.2)
- `GET /api/miniapp/referral/{id}` - Referral code + stats
- `GET /api/miniapp/notifications/{id}` - Notifications
