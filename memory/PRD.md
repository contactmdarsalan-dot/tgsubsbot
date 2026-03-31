# TgSubsBot - Telegram Subscription Bot SaaS Platform

## Original Problem Statement
Build a market-ready SaaS product for Telegram subscription management. Features include automated payment verification, live stream management, super chat, channel/group management, and a modern admin dashboard. Transform the bot into a full SaaS with Mini App, Razorpay payments, AI support, and referral system.

## Architecture
```
/app/backend/
├── server.py              # App setup, middleware (82 lines)
├── config.py              # Env vars, logging
├── database.py            # MongoDB + Redis
├── routes/
│   ├── auth.py            # Auth, Forgot Password (email), Support
│   ├── admin.py           # Dashboard, User Management
│   ├── core.py            # Plans, Payments, PDF Export, Branding, Bot Language
│   ├── features.py        # Templates, Broadcast, Live, Telegram file proxy
│   ├── telegram_webhook.py # Webhook + admin approve/reject
│   └── miniapp.py         # NEW: Mini App endpoints (Plans, Razorpay, AI Support, Referral, Notifications)
├── services/
│   ├── auth.py, telegram.py, payment.py, chat_pool.py
│   ├── bot_activity.py, background_tasks.py, email_service.py
│   └── csv_export.py
└── models/__init__.py

/app/frontend/src/
├── components/Layout.jsx  # Dynamic branding, role-based sidebar
├── pages/ (20+ pages including MiniApp, Branding, BotLanguage)
├── App.js
└── index.css
```

## Implementation Log

### Mar 31, 2026 - Telegram Mini App (Complete)
- [x] **Mini App Plans Tab**: Shows all active plans with price, duration, features. Click to select.
- [x] **Razorpay Instant Payment**: Create order → Razorpay JS checkout → Verify signature → Auto-activate subscription
- [x] **Manual UPI Payment**: Select plan → Send data to bot → User sends UPI screenshot → Admin verification
- [x] **Coupon Code System**: Apply coupon in payment section, validates server-side, shows discount
- [x] **AI Support Chat**: GPT-5.2 powered chatbot answers plan/payment/subscription queries. Auto-escalates complex issues to admin as support tickets.
- [x] **Subscription Status Tab**: Shows active plan, expiry, days remaining, progress bar. Renew button.
- [x] **Payment History**: Lists all past payments with status, amount, date, method
- [x] **Referral Program**: Auto-generates referral code, share with friends, both get discount. Apply referral code input.
- [x] **Notifications**: Expiry warnings (3 days), pending payment alerts, new plan promos
- [x] **Help & FAQ**: "How It Works" 4-step guide + 5 FAQ accordion items
- [x] **Backend**: New `/app/backend/routes/miniapp.py` with 12+ endpoints
- [x] **Testing**: 100% pass rate (19/19 backend + all frontend elements verified)

### Mar 31, 2026 - Previous Session Features
- [x] Plan channel mapping, Payment screenshot thumbnails, Live Stream screenshots
- [x] Branding (super admin only), Functional branding CSS variables
- [x] Telegram Admin Approve/Reject buttons, User Management fix
- [x] Email integration (Resend - MOCKED), PDF Export, Bot Language page
- [x] Backend refactoring (9400→79 lines), Docker fix
- [x] GPT-5.2 Payment Verification AI (relaxed logic)

## Backlog
### P0 - Deploy
- [ ] User: "Save to Github" → Coolify redeploy
- [ ] User: Set channel_id per plan in production

### P1
- [ ] Add RESEND_API_KEY for email OTP (MOCKED currently)
- [ ] Razorpay payment flow improvements (webhook verification)

### P2+
- [ ] WhatsApp integration
- [ ] Custom domain mapping per tenant
- [ ] Mobile app

## Credentials
- Super Admin: gamerxboys8958@gmail.com / Sumit@8958
- Bot Token: 8275964628:AAH8U7ECRII7eyAySt7U2pyDQhLcnZunTnY

## Key API Endpoints (Mini App)
- `GET /api/miniapp/plans` - Active plans (public)
- `GET /api/miniapp/status/{user_id}` - Subscription status
- `POST /api/miniapp/apply-coupon` - Validate coupon
- `POST /api/miniapp/create-order` - Create Razorpay order
- `POST /api/miniapp/verify-payment` - Verify & activate subscription
- `POST /api/miniapp/support/chat` - AI support chat (GPT-5.2)
- `GET /api/miniapp/referral/{user_id}` - Get/create referral code
- `POST /api/miniapp/referral/apply` - Apply referral code
- `GET /api/miniapp/payments/{user_id}` - Payment history
- `GET /api/miniapp/notifications/{user_id}` - Notifications
