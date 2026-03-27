# Tgsubsbot - Telegram Subscription Bot PRD

## Original Problem Statement
User requested a Telegram Subscription Bot with:
- Multiple subscription plans
- Analytics dashboard
- Auto-add to private channel on subscription purchase
- 3-4 days before expiry renewal reminder
- 1-2 extra grace days if not renewed
- Auto-remove from channel after grace period
- Auto DM website link on subscription
- Regular follow-up messages 2x per week
- Payment: Razorpay + Manual QR code
- **SaaS Model**: Dashboard itself subscription-based
- **Super Admin Dashboard**: Manage all SaaS subscriptions (SPECIAL PANEL)

## Deployment (VPS - Coolify)
- **Frontend URL**: https://tgsubsbot.com
- **Backend API URL**: https://api.tgsubsbot.com
- **Webhook**: https://api.tgsubsbot.com/api/telegram/webhook
- **Coolify Panel**: http://72.61.244.69:8000
- **Deployment**: Docker Compose via Coolify on Hostinger VPS

## Architecture
- **Backend**: FastAPI (Python) with MongoDB
- **Frontend**: React with Tailwind CSS + Shadcn UI
- **Database**: MongoDB
- **Scheduler**: APScheduler for automated tasks
- **Payments**: Razorpay integration + Manual QR verification
- **Auth**: JWT + Google OAuth (Emergent Auth) + Twilio OTP

## User Personas
1. **Super Admin (gamerxboys8958@gmail.com)**: Full control with SPECIAL DARK PANEL - users, admins, subscriptions, support
2. **Admin**: Limited powers - can view support tickets and respond
3. **Dashboard Users**: Pay for access to manage their Telegram bot
4. **Telegram Subscribers**: Pay for access to private channel

## What's Been Implemented

### Mar 27, 2026 - Subscriber Details Enhancement
- [x] **Subscribers Table Updated** - Added Telegram ID, Channel ID, and Group Name columns
  - Backend `GET /api/subscribers` enriched with plan's channel_id and assigned group info
  - Frontend `Subscribers.jsx` updated with 3 new columns in the data table
  - Group name pulled from `chat_groups_pool` based on user assignment
  - Channel ID pulled from the subscriber's plan configuration

### Mar 24, 2026 - Paid Posts Feature (Current Session)
- [x] **Paid Posts Feature Complete** 🎉
  - Admin posts photo/video with `/paid` in caption → Bot blurs content automatically
  - "Unlock Post" button appears below blurred content
  - Users click unlock → Pay via QR → Send screenshot → Get original content in DM
  - Active subscribers can unlock for FREE
  - Custom pricing: `/paid 99` sets ₹99 unlock price
  - Backend: PaidPost & PaidPostUnlock models, full CRUD APIs
  - Frontend: New "Paid Posts" page with stats, posts list, unlock requests management
  - Admin can approve/reject unlock requests manually
  - AI-powered payment verification for unlock screenshots

### Mar 23-24, 2026 - Previous Session
- [x] **Branding Update** - Changed all "SubsBot" references to "Tgsubsbot"
  - Browser title updated
  - Login page header and footer updated
  - Dashboard sidebar branding updated
  - Deployment zip file recreated

- [x] **AI Payment Screenshot Analysis (GPT-4o Vision)**
  - Integrated OpenAI GPT-4o Vision via Emergent Universal Key
  - Features:
    - Auto-detect payment amount, UPI ID, transaction ID
    - Detect fake/edited screenshots
    - Confidence scoring (0-100%)
    - Auto-approve payments with confidence >= 85%
  - Fallback to OCR if AI unavailable/low confidence
  - AI analysis data stored in payment records

- [x] **Admin Unverify → Kick from Channel**
  - When admin unverifies a payment, user is automatically kicked from:
    - Main premium channel
    - Any assigned chat groups
  - User receives notification about rejection
  - Subscription removed from database

- [x] **Settings Page Enhancements (Batch 1)**
  - AI Auto-Approve Threshold slider (50-100%)
  - Support Username field
  - Welcome Message customization
  - Payment Instructions customization
  - Success Message customization
  - Payment UPI ID for AI matching

- [x] **Plans Page Enhancements**
  - Group ID (Manual) field
  - Auto Groups toggle - auto-assign from pool
  - Sidebar renamed "Chat Groups" → "Groups"

- [x] **Coupons & Discounts (Batch 2)**
  - Create/Edit/Delete coupons
  - Percentage or Flat discount types
  - Min purchase amount
  - Max usage limit
  - Expiry date
  - Coupon validation API for bot

- [x] **Referral Program (Batch 6)**
  - Referral settings (enable/disable)
  - Referrer & Referee reward configuration
  - Reward types: Discount, Cash, Free Days
  - Referral tracking dashboard
  - Referral validation API for bot

- [x] **FAQs & Auto-Reply (Batch 7)**
  - Create/Edit/Delete FAQs
  - Keyword-based auto-responses
  - Usage tracking

- [x] **Analytics & Reports (Batch 3)**
  - Revenue chart (last 14 days)
  - User growth chart (last 14 days)
  - Export Subscribers to CSV
  - Export Payments to CSV

- [x] **User Management APIs (Batch 4)**
  - User Notes API
  - User Tags API
  - Block/Unblock Users API

### VPS Deployment (Previous Session - Completed)
- [x] Full VPS migration from Emergent preview to user's Hostinger VPS
- [x] Docker Compose setup with Coolify panel
- [x] Frontend build fixes (date-fns dependency, npm --force)
- [x] Telegram webhook configured for new domain
- [x] Production database seeded with plans and admin user

### Feb 4, 2026 - Session 2
- [x] **Super Admin SPECIAL PANEL** - Dark purple gradient theme, completely different from normal dashboard
  - User Management tab with all users, roles, plans, actions
  - Support Tickets tab with chat-style messaging
  - Quick stats: Total Users, Active Subs, Lifetime, Admins, Open Tickets, Revenue
- [x] **Chat-Style Support System** - Multiple messages, expand/collapse tickets
- [x] **Payment Reject Button** - Working with confirmation
- [x] **Google Login** - OAuth integration
- [x] **Admin Management** - Make/remove admins
- [x] **Subscription Change** - Change any user's plan

### Feb 4, 2026 - Session 1
- [x] Super Admin Dashboard basic structure
- [x] APIs for admin management

### Earlier
- [x] SaaS subscription model
- [x] Core Telegram bot features
- [x] Payment verification with screenshots
- [x] OCR for payment screenshot detection

## Key APIs
- `POST /api/auth/google/session` - Google OAuth
- `POST /api/support/tickets` - Create ticket
- `POST /api/support/tickets/{id}/message` - Add user message
- `POST /api/admin/support/tickets/{id}/reply` - Admin reply (multiple)
- `PUT /api/admin/make-admin/{id}` - Make user admin
- `PUT /api/admin/remove-admin/{id}` - Remove admin
- `PUT /api/admin/change-subscription/{id}` - Change plan
- `PUT /api/payments/{id}/reject` - Reject payment
- `GET /api/paid-posts` - Get all paid posts
- `PUT /api/paid-posts/{id}` - Update paid post (price, status)
- `DELETE /api/paid-posts/{id}` - Deactivate paid post
- `GET /api/unlock-requests` - Get pending unlock requests
- `POST /api/unlock-requests/{id}/approve` - Approve unlock & send content
- `POST /api/unlock-requests/{id}/reject` - Reject unlock request

## Prioritized Backlog

### P0 (Critical) - DONE ✅
- All core features complete
- Super Admin SPECIAL Panel complete
- Support System (chat-style) complete
- Payment Reject working
- VPS Deployment complete
- Branding update complete (Tgsubsbot)
- AI Payment Analysis (GPT-4o Vision) complete
- Admin Unverify → Kick from Channel complete
- Coupons & Discounts system complete
- Referral Program complete
- FAQs & Auto-Reply complete
- Analytics & Reports with CSV Export complete
- User Notes, Tags, Block APIs complete
- **Paid Posts Feature complete** ✅

### P1 (Important) - Pending
- [ ] Full E2E Testing on VPS deployment (subscription flow, AI verification, payments)
- [ ] Add Chat Groups in production for Time-Limited Chat feature
- [ ] Razorpay Gateway for Bot Subscriptions (Needs user API keys)
- [ ] Integrate coupon system in Telegram bot
- [ ] Integrate referral system in Telegram bot
- [ ] Integrate FAQ auto-reply in Telegram bot

### P2 (Nice to have)
- [ ] Scheduled Broadcasts (date/time picker)
- [ ] User Notes & Tags UI in Subscribers page
- [ ] Block/Unblock Users UI
- [ ] Email notifications (Resend integration)
- [ ] Backend code refactoring (server.py is 5000+ lines now)
- [ ] Show AI analysis details in admin dashboard payment cards

### Batch 8 (Future - Not Started)
- [ ] Multi-language Bot (Hindi/English)
- [ ] WhatsApp Integration
- [ ] Affiliate Program
- [ ] Subscription Pause/Resume

## Test Credentials
- **Super Admin**: gamerxboys8958@gmail.com / Sumit@8958
- **Bot Token**: 8275964628:AAH8U7ECRII7eyAySt7U2pyDQhLcnZunTnY
- **VPS IP**: 72.61.244.69

## Key Files
- `/app/docker-compose.yml` - VPS deployment configuration
- `/app/frontend/public/telegram-bot-deploy.zip` - Deployment archive
- `/app/backend/server.py` - Main backend (needs refactoring, now ~5800 lines)
- `/app/frontend/src/pages/PaidPosts.jsx` - NEW: Paid Posts management page
