# TgSubsBot - Telegram Subscription Bot SaaS Platform

## Original Problem Statement
Build a market-ready SaaS product for Telegram subscription management with Mini App, Razorpay payments, AI support, and referral system.

## Architecture
```
/app/backend/routes/
├── auth.py, admin.py, core.py, features.py
├── telegram_webhook.py
└── miniapp.py         # Mini App: Plans, Razorpay, Phone Login, AI Support, Referral, Notifications
/app/frontend/src/pages/
├── MiniApp.jsx + MiniApp.css  # Full Telegram Mini App
├── 20+ other pages (Dashboard, Plans, Payments, etc.)
```

## Implementation Log

### Mar 31, 2026 - Mini App v2 (Phone Login, UPI Sheet, UI Redesign)
- [x] **Phone Login Screen**: +91 phone input, "Unlock 20% OFF" button, "Skip for now" option
- [x] **20% Discount System**: Phone login users get 20% off all plans. Discount badge in header. Green discounted prices on all plan cards.
- [x] **Discount Popup**: Glassmorphism popup confirming "20% Discount Unlocked!" with Got it! button
- [x] **UPI Manual Payment Sheet**: Bottom sheet shows UPI ID (anamika.bade@ptyes), amount, plan name, 4-step instructions, Copy button, "I've Paid" confirmation
- [x] **Glassmorphism Redesign**: Pure black (#0e0e0e) background, glass cards with backdrop-filter blur, pink (#e8365d) accent, no brown borders
- [x] **Backend endpoints**: `/api/miniapp/phone-login`, `/api/miniapp/user-discount/{id}`, `/api/miniapp/upi-details`
- [x] **Testing**: 100% pass (iteration_8: 11/11 backend + all frontend)

### Mar 31, 2026 - Mini App v1 (Base Features)
- [x] Plans tab, Razorpay instant payment, Manual UPI, Coupon codes
- [x] AI Support Chat (GPT-5.2), Status tab, Payment History
- [x] Referral Program, Notifications, Help & FAQ, Bottom navigation
- [x] Testing: 100% pass (iteration_7: 19/19 backend + all frontend)

### Previous Sessions
- Backend refactoring (9400→79 lines), Docker fix, Admin Approve/Reject
- Branding, PDF Export, Bot Language, Channel selectors
- GPT-5.2 Payment Verification (relaxed), Blob screenshot fetching

## Backlog
- (P0) Production Deploy: "Save to Github" → Coolify redeploy
- (P1) RESEND_API_KEY for Forgot Password email OTP (MOCKED)
- (P1) Razorpay webhook for server-side verification
- (P2) WhatsApp integration
- (P2) Custom domain per tenant

## Credentials
- Super Admin: gamerxboys8958@gmail.com / Sumit@8958
- Bot Token: 8275964628:AAH8U7ECRII7eyAySt7U2pyDQhLcnZunTnY

## Key Mini App Endpoints
- `POST /api/miniapp/phone-login` - Register phone, get 20% discount
- `GET /api/miniapp/user-discount/{id}` - Check user discount status
- `GET /api/miniapp/upi-details` - UPI payment details for manual pay
- `GET /api/miniapp/plans`, `POST /api/miniapp/create-order`, `POST /api/miniapp/verify-payment`
- `POST /api/miniapp/support/chat`, `GET /api/miniapp/referral/{id}`, `GET /api/miniapp/notifications/{id}`
