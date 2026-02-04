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
- **SaaS Model**: Dashboard itself subscription-based
- **Super Admin Dashboard**: Manage all SaaS subscriptions

## Architecture
- **Backend**: FastAPI (Python) with MongoDB
- **Frontend**: React with Tailwind CSS + Shadcn UI
- **Database**: MongoDB
- **Scheduler**: APScheduler for automated tasks
- **Payments**: Razorpay integration + Manual QR verification
- **Auth**: JWT + Google OAuth (Emergent Auth)

## User Personas
1. **Super Admin (gamerxboys8958@gmail.com)**: Full control over all users, admins, and subscriptions
2. **Admin**: Limited powers - can view support tickets and respond, cannot manage other users
3. **Dashboard Users**: Pay for access to manage their Telegram bot
4. **Telegram Subscribers**: Pay for access to private channel

## Core Requirements (Static)
1. Auth system with JWT + Google OAuth
2. Subscription plans CRUD
3. Subscriber management
4. Payment tracking (Razorpay + Manual) with Verify/Reject
5. Automated reminders and follow-ups
6. Telegram bot integration
7. SaaS subscription model for dashboard
8. Super Admin Dashboard for managing all users
9. Contact Support system
10. Admin management (add/remove admins)

## What's Been Implemented

### Feb 4, 2026 - Session 2 (Latest)
- [x] **Google Login** - OAuth integration with Emergent Auth
- [x] **Payment Reject** - Reject button next to Verify for pending payments
- [x] **Contact Support System** - Users can create tickets, admins can reply on website
- [x] **Admin Management** - Super admin can make/remove admins (limited powers)
- [x] **Subscription Change** - Super admin can change any user's plan (1month, 6month, 12month, lifetime)
- [x] **Role badges** - User/Admin/Super Admin badges in dashboard

### Feb 4, 2026 - Session 1
- [x] Super Admin Dashboard (`/super-admin`) - Only accessible by gamerxboys8958@gmail.com
- [x] API: GET `/api/admin/all-users`, `/api/admin/stats`, etc.
- [x] Frontend: Stats cards, Users table, Search/Filter, Lifetime/Revoke buttons

### Feb 2, 2026 - Core Features
- [x] SaaS subscription model with pricing page
- [x] Renewal flow for expired subscriptions
- [x] Plan-specific Telegram channels
- [x] `/share` command with shareable button message
- [x] Renew button in renewal reminders
- [x] Screenshot viewing in payment verification

### Earlier - Foundation
- [x] User authentication (register/login with JWT)
- [x] Subscription Plans CRUD API
- [x] Subscribers management API
- [x] Payments API (Razorpay + Manual QR)
- [x] Settings API (bot token, channel ID, website link)
- [x] Analytics API
- [x] Telegram webhook handler
- [x] APScheduler for automated tasks

## New APIs Added (Feb 4, 2026)
- `POST /api/auth/google/session` - Process Google OAuth session
- `POST /api/support/tickets` - Create support ticket
- `GET /api/support/tickets` - Get user's own tickets
- `GET /api/admin/support/tickets` - Get all tickets (admin only)
- `PUT /api/admin/support/tickets/{id}/reply` - Reply to ticket
- `PUT /api/admin/make-admin/{user_id}` - Make user admin
- `PUT /api/admin/remove-admin/{user_id}` - Remove admin status
- `PUT /api/admin/change-subscription/{user_id}` - Change user's plan
- `PUT /api/payments/{id}/reject` - Reject pending payment

## Prioritized Backlog

### P0 (Critical) - DONE ✅
- All core features implemented and tested
- Super Admin Dashboard complete
- Google Login
- Support System
- Admin Management

### P1 (Important) - Pending
- [ ] Twilio OTP for phone-based login (User requested, needs Twilio credentials)

### P2 (Nice to have)
- [ ] Email notifications for new support tickets
- [ ] Export subscribers to CSV
- [ ] Promo codes/discounts
- [ ] Code refactoring (server.py modularization)

## Test Credentials
- **Super Admin**: gamerxboys8958@gmail.com / admin123
- **Admin User**: admin@test.com / test123 (is_admin: true)
- **Regular User**: testsuperadmin@test.com / test123
- **Lifetime User**: sumitrawat77011@gmail.com

## Key Files
- `/app/backend/server.py` - All backend APIs
- `/app/frontend/src/pages/SuperAdminDashboard.jsx` - Super Admin UI with admin management
- `/app/frontend/src/pages/SupportPage.jsx` - Support ticket system
- `/app/frontend/src/pages/Payments.jsx` - Payment verification with Reject
- `/app/frontend/src/pages/Login.jsx` - Login with Google OAuth
- `/app/frontend/src/App.js` - Google auth callback handler
