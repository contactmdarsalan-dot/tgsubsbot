# Telegram Subscription Bot - PRD

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

## Architecture
- **Backend**: FastAPI (Python) with MongoDB
- **Frontend**: React with Tailwind CSS + Shadcn UI
- **Database**: MongoDB
- **Scheduler**: APScheduler for automated tasks
- **Payments**: Razorpay integration + Manual QR verification

## User Personas
1. **Admin/Business Owner**: Manages subscriptions, views analytics, configures bot
2. **Telegram Subscribers**: Pay for access to private channel

## Core Requirements (Static)
1. Auth system with JWT
2. Subscription plans CRUD
3. Subscriber management
4. Payment tracking (Razorpay + Manual)
5. Automated reminders and follow-ups
6. Telegram bot integration

## What's Been Implemented (Feb 2, 2026)

### Backend
- [x] User authentication (register/login with JWT)
- [x] Subscription Plans CRUD API
- [x] Subscribers management API (add, renew, delete)
- [x] Payments API (Razorpay + Manual QR)
- [x] Settings API (bot token, channel ID, website link)
- [x] Analytics API (KPIs, revenue, plan stats)
- [x] Message Templates API
- [x] Telegram webhook handler
- [x] APScheduler for automated tasks:
  - Check subscriptions every 6 hours
  - Send follow-ups Mon & Thu at 10 AM
- [x] Auto channel add/remove logic

### Frontend
- [x] Login/Register page (split screen design)
- [x] Dashboard with analytics charts
- [x] Plans page with CRUD and tracing beam effect
- [x] Subscribers page with filters and table
- [x] Payments page with verification flow
- [x] Automation settings (reminders, follow-ups, templates)
- [x] Settings page (bot config, webhook URL, QR code)
- [x] Responsive sidebar navigation

### Design
- Performance Pro theme (Light variant)
- Barlow Condensed + Inter + JetBrains Mono fonts
- Electric Blue primary color
- Bento Grid layout for dashboard

## Prioritized Backlog

### P0 (Critical) - DONE
- All core features implemented and tested

### P1 (Important) - Future
- [ ] Real Telegram bot testing with actual token
- [ ] Razorpay production integration (needs API keys)
- [ ] Email notifications for admins

### P2 (Nice to have)
- [ ] Multi-admin support
- [ ] Subscription tier upgrades/downgrades
- [ ] Referral system
- [ ] Promo codes/discounts
- [ ] Export subscribers to CSV

## Next Tasks
1. Add Telegram Bot Token in Settings
2. Add Channel ID for private channel
3. Configure Razorpay keys (if using online payments)
4. Create subscription plans
5. Set webhook URL in Telegram (@BotFather)
6. Start accepting subscribers!

## Environment Variables Required
```
# Backend (.env)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=-1001234567890
RAZORPAY_KEY_ID=your_key (optional)
RAZORPAY_KEY_SECRET=your_secret (optional)
```
