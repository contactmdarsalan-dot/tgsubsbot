# TGSubsBot - Complete API Documentation

**Base URL**: `http://YOUR_SERVER:8001/api`

All authenticated endpoints require:
```
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

---

## Table of Contents
1. [Authentication](#1-authentication)
2. [Plans (Bot)](#2-plans-bot)
3. [Subscribers (Bot)](#3-subscribers-bot)
4. [Payments (Bot)](#4-payments-bot)
5. [Dashboard & Settings](#5-dashboard--settings)
6. [Analytics & Exports](#6-analytics--exports)
7. [Broadcasts](#7-broadcasts)
8. [Engagement (Coupons, Referrals, FAQs, Tags)](#8-engagement)
9. [Video Calls (Bot)](#9-video-calls-bot)
10. [Live Content & Creators](#10-live-content--creators)
11. [Telegram Admins & Paid Posts](#11-telegram-admins--paid-posts)
12. [Mini App - User Facing (Public)](#12-mini-app---user-facing)
13. [Mini App - Admin (Telegram)](#13-mini-app---admin-telegram)
14. [Mini App - Dashboard Management](#14-mini-app---dashboard-management)
15. [Mini App - Chat (Private Messaging)](#15-mini-app---chat)
16. [Mini App - Video Calls & Live](#16-mini-app---video-calls--live)
17. [Tenant Management](#17-tenant-management)
18. [SaaS Management (Super Admin)](#18-saas-management-super-admin)
19. [Support Tickets](#19-support-tickets)
20. [WebSocket Endpoints](#20-websocket-endpoints)

---

## 1. Authentication

### POST `/api/auth/register`
Register a new user/tenant admin.
```json
// Request
{
  "email": "user@example.com",
  "password": "Password123",
  "name": "John Doe",
  "phone": "+919876543210"  // optional
}

// Response 200
{
  "message": "Registration successful",
  "token": "eyJhbGciOi...",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "role": "tenant_admin"
  }
}
```

### POST `/api/auth/login`
Login with email/password.
```json
// Request
{ "email": "user@example.com", "password": "Password123" }

// Response 200
{
  "token": "eyJhbGciOi...",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "role": "tenant_admin",
    "tenant_id": "tenant_uuid"
  }
}
```

### GET `/api/auth/me`
Get current logged-in user profile.
```
Headers: Authorization: Bearer <token>
```
```json
// Response 200
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "John Doe",
  "role": "tenant_admin",
  "tenant_id": "tenant_uuid",
  "dashboard_plan": "free",
  "dashboard_subscription_status": "active"
}
```

### POST `/api/auth/otp/send`
Send OTP to phone number.
```json
{ "phone": "+919876543210" }

// Response 200
{ "message": "OTP sent", "otp_id": "uuid" }
```

### POST `/api/auth/otp/verify`
Verify phone OTP.
```json
{ "phone": "+919876543210", "otp": "123456" }

// Response 200
{ "token": "eyJhbGciOi...", "user": {...} }
```

### PUT `/api/auth/profile`
Update user profile.
```json
{ "name": "New Name", "phone": "+919876543210" }
```

### PUT `/api/auth/change-password`
```json
{ "current_password": "oldPass", "new_password": "newPass" }
```

### POST `/api/auth/forgot-password`
```json
{ "email": "user@example.com" }
// Response: { "message": "Reset link sent" }
```

### POST `/api/auth/reset-password`
```json
{ "token": "reset_token", "new_password": "newPass" }
```

---

## 2. Plans (Bot)
*Auth Required. Returns only Bot plans (excludes Mini App plans).*

### GET `/api/plans`
List all bot plans.
```json
// Response 200
[
  {
    "id": "uuid",
    "name": "Premium Monthly",
    "price": 299,
    "duration_days": 30,
    "features": ["Feature 1", "Feature 2"],
    "is_active": true,
    "channel_id": "-100123456",
    "group_id": "",
    "auto_assign_group": false,
    "discount_percentage": 0,
    "created_at": "2025-01-01T00:00:00Z"
  }
]
```

### GET `/api/plans/active`
List only active bot plans.

### POST `/api/plans`
Create a new bot plan.
```json
// Request
{
  "name": "Gold Plan",
  "price": 499,
  "duration_days": 30,
  "features": ["HD Content", "Priority Support"],
  "is_active": true,
  "channel_id": "-100123456",
  "group_id": "",
  "auto_assign_group": false,
  "discount_percentage": 10
}
```

### PUT `/api/plans/{plan_id}`
Update a bot plan.
```json
{ "name": "Platinum Plan", "price": 599 }
```

### DELETE `/api/plans/{plan_id}`
Delete a bot plan.

---

## 3. Subscribers (Bot)
*Auth Required. Returns only Bot subscribers.*

### GET `/api/subscribers`
List subscribers with pagination, search, and filters.
```
Query Params:
  ?page=1&limit=50
  &status=active|expired|cancelled
  &search=username_or_id
```
```json
// Response 200
{
  "subscribers": [
    {
      "id": "uuid",
      "telegram_user_id": "123456789",
      "telegram_username": "john_doe",
      "plan_id": "plan_uuid",
      "plan_name": "Premium Monthly",
      "status": "active",
      "start_date": "2025-01-01T00:00:00Z",
      "end_date": "2025-02-01T00:00:00Z",
      "payment_method": "razorpay"
    }
  ],
  "total": 150,
  "active": 120
}
```

### POST `/api/subscribers`
Manually add a subscriber.
```json
{
  "telegram_user_id": "123456789",
  "telegram_username": "john_doe",
  "plan_id": "plan_uuid",
  "payment_method": "manual"
}
```

### PUT `/api/subscribers/{subscriber_id}/renew`
Renew a subscriber's subscription.
```json
{ "plan_id": "plan_uuid", "payment_method": "manual" }
```

### DELETE `/api/subscribers/{subscriber_id}`
Remove a subscriber.

### POST `/api/subscribers/bulk-add-to-channel`
Bulk add subscribers to Telegram channel.
```json
{ "subscriber_ids": ["id1", "id2", "id3"] }
```

---

## 4. Payments (Bot)
*Auth Required. Returns only Bot payments.*

### GET `/api/payments`
List payments with filters.
```
Query Params:
  ?page=1&limit=50
  &status=pending|verified|rejected
  &search=user_id_or_username
  &method=manual|razorpay
  &date_from=2025-01-01&date_to=2025-12-31
```
```json
// Response 200
{
  "payments": [
    {
      "id": "uuid",
      "telegram_user_id": "123456789",
      "telegram_username": "john_doe",
      "amount": 299,
      "plan_id": "plan_uuid",
      "plan_name": "Premium",
      "payment_method": "manual",
      "status": "pending",
      "screenshot_url": "https://...",
      "created_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 500,
  "verified": 400,
  "revenue": 119600
}
```

### GET `/api/payments/{payment_id}/screenshot`
Get payment screenshot image.

### PUT `/api/payments/{payment_id}/verify-manual`
Manually verify/approve a payment.

### PUT `/api/payments/{payment_id}/reject`
Reject a payment.

### PUT `/api/payments/{payment_id}/unverify`
Revert a verified payment back to pending.

### DELETE `/api/payments/{payment_id}`
Delete a payment.

### POST `/api/payments/create-order`
Create Razorpay order.
```json
{ "plan_id": "plan_uuid", "telegram_user_id": "123456789" }
// Response: { "order_id": "order_xxx", "amount": 29900, "currency": "INR" }
```

### POST `/api/payments/verify`
Verify Razorpay payment.
```json
{
  "razorpay_order_id": "order_xxx",
  "razorpay_payment_id": "pay_xxx",
  "razorpay_signature": "sig_xxx"
}
```

### POST `/api/payments/manual`
Record manual payment.
```json
{
  "telegram_user_id": "123456789",
  "amount": 299,
  "plan_id": "plan_uuid",
  "payment_method": "manual"
}
```

### POST `/api/payments/bulk-verify`
```json
{ "payment_ids": ["id1", "id2", "id3"] }
```

### POST `/api/payments/bulk-reject`
```json
{ "payment_ids": ["id1", "id2", "id3"] }
```

### POST `/api/payments/bulk-delete`
```json
{ "payment_ids": ["id1", "id2", "id3"] }
```

---

## 5. Dashboard & Settings

### GET `/api/settings`
Get bot settings for current tenant.
```json
// Response 200
{
  "telegram_bot_token": "123:ABC...",
  "telegram_channel_id": "-100123456",
  "payment_upi_id": "upi@bank",
  "qr_code_url": "https://...",
  "welcome_message": "Welcome!",
  "payment_instructions": "Scan QR...",
  "success_message": "Payment verified!",
  "reminder_days_before": 3,
  "grace_period_days": 2,
  "ai_auto_approve_threshold": 85,
  "video_call_enabled": true,
  "video_call_price": 500,
  "video_call_duration": 30
}
```

### PUT `/api/settings`
Update bot settings.
```json
{ "payment_upi_id": "new_upi@bank", "welcome_message": "New welcome!" }
```

### POST `/api/upload/qr-code`
Upload QR code image. **Multipart form data.**
```
Content-Type: multipart/form-data
Body: file=<image_file>
```

### POST `/api/upload/image`
Upload generic image. **Multipart form data.**

### GET `/api/analytics`
Get dashboard analytics summary.
```json
// Response 200
{
  "total_subscribers": 150,
  "active_subscribers": 120,
  "total_revenue": 119600,
  "monthly_revenue": 29900,
  "plan_distribution": [{"name": "Premium", "count": 80}],
  "revenue_trend": [{"month": "2025-01", "revenue": 29900}]
}
```

### GET `/api/chat-groups`
List chat group pool.

### POST `/api/chat-groups`
Add a chat group.
```json
{ "group_id": "-100xxx", "group_name": "VIP Chat", "plan_type": "premium" }
```

### DELETE `/api/chat-groups/{group_id}`

### GET `/api/channels`
List connected Telegram channels.

### POST `/api/channels`
Add a channel.
```json
{ "channel_id": "-100xxx", "channel_name": "My Channel" }
```

### DELETE `/api/channels/{channel_id}`

### GET `/api/branding`
Get tenant branding settings.

### PUT `/api/branding`
Update branding.
```json
{ "logo_url": "https://...", "theme_color": "#BFFF00", "brand_name": "MyBrand" }
```

### GET `/api/bot-language`
Get bot language settings.

### PUT `/api/bot-language`
Update bot language/messages.

---

## 6. Analytics & Exports

### GET `/api/analytics/revenue`
Revenue analytics with date range.
```
Query: ?period=7d|30d|90d|12m
```

### GET `/api/analytics/users`
User growth analytics.

### GET `/api/export/subscribers`
Export subscribers as CSV.

### GET `/api/export/payments`
Export payments as CSV.

### GET `/api/export/revenue-report`
Export revenue report as PDF.

### GET `/api/bot-activity`
Bot activity logs.
```
Query: ?page=1&limit=50
```

### GET `/api/bot-activity/stats`
Bot activity summary stats.

### GET `/api/chat-messages`
Chat message logs.

### GET `/api/chat-messages/stats`
Chat message stats.

---

## 7. Broadcasts

### POST `/api/broadcast`
Send broadcast message to subscribers.
```json
{
  "message": "Hello subscribers!",
  "target_segment": "all",  // all|active|expired
  "media_type": "text",     // text|photo|video
  "media_url": ""
}
```

### GET `/api/broadcasts`
List sent broadcasts.

### GET `/api/broadcasts/{broadcast_id}`
Get broadcast details.

### POST `/api/promote-plan`
Send plan promotion broadcast.
```json
{ "plan_id": "plan_uuid", "custom_message": "Special offer!" }
```

### POST `/api/renewal-broadcast`
Send renewal reminder broadcast.
```json
{ "days_before_expiry": 3, "custom_message": "Renew now!" }
```

### GET `/api/templates`
List message templates.

### POST `/api/templates`
Create template.
```json
{ "type": "welcome", "message": "Welcome {{name}}!", "is_active": true }
```

### PUT `/api/templates/{template_id}`
### DELETE `/api/templates/{template_id}`

### GET `/api/scheduled-broadcasts`
### POST `/api/scheduled-broadcasts`
```json
{
  "message": "Scheduled msg",
  "target_segment": "all",
  "scheduled_at": "2025-06-01T10:00:00Z"
}
```
### DELETE `/api/scheduled-broadcasts/{broadcast_id}`

---

## 8. Engagement

### Coupons
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/coupons` | List all coupons |
| POST | `/api/coupons` | Create coupon |
| PUT | `/api/coupons/{coupon_id}` | Update coupon |
| DELETE | `/api/coupons/{coupon_id}` | Delete coupon |
| POST | `/api/coupons/validate` | Validate coupon code |

```json
// POST /api/coupons
{
  "code": "SAVE20",
  "discount_type": "percentage",  // percentage|fixed
  "discount_value": 20,
  "min_purchase": 100,
  "max_uses": 100,
  "valid_from": "2025-01-01",
  "valid_until": "2025-12-31",
  "applicable_plans": ["plan_id1"],
  "is_active": true
}

// POST /api/coupons/validate
{ "code": "SAVE20", "plan_id": "plan_uuid" }
// Response: { "valid": true, "discount_type": "percentage", "discount_value": 20, "final_price": 239 }
```

### Referrals
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/referrals` | List referrals |
| GET | `/api/referrals/settings` | Get referral settings |
| PUT | `/api/referrals/settings` | Update referral settings |
| POST | `/api/referrals/validate` | Validate referral code |

### FAQs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/faqs` | List FAQs |
| POST | `/api/faqs` | Create FAQ |
| PUT | `/api/faqs/{faq_id}` | Update FAQ |
| DELETE | `/api/faqs/{faq_id}` | Delete FAQ |

```json
// POST /api/faqs
{ "keywords": ["price", "cost"], "response": "Our plans start at Rs.99", "is_active": true }
```

### Tags & Notes
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tags` | List tags |
| POST | `/api/tags` | Create tag |
| DELETE | `/api/tags/{tag_id}` | Delete tag |
| GET | `/api/users/{user_id}/notes` | Get user notes |
| POST | `/api/users/{user_id}/notes` | Add note |
| DELETE | `/api/users/{user_id}/notes/{note_id}` | Delete note |
| POST | `/api/users/{user_id}/tags` | Add tag to user |
| DELETE | `/api/users/{user_id}/tags/{tag_id}` | Remove tag |

### Blocked Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/blocked-users` | List blocked users |
| POST | `/api/users/{user_id}/block` | Block a user |
| DELETE | `/api/users/{user_id}/block` | Unblock a user |

---

## 9. Video Calls (Bot)

### GET `/api/video-calls`
List video call bookings.
```json
// Response 200
[
  {
    "id": "uuid",
    "telegram_user_id": "123456789",
    "telegram_username": "john",
    "user_name": "John Doe",
    "plan_id": "plan_uuid",
    "plan_name": "1:1 Call",
    "scheduled_date": "2025-06-15",
    "scheduled_time": "14:00",
    "duration_minutes": 30,
    "price": 500,
    "status": "pending",
    "meeting_link": "",
    "notes": ""
  }
]
```

### PUT `/api/video-calls/{booking_id}`
Update booking (approve/reject/add meeting link).
```json
{ "status": "confirmed", "meeting_link": "https://meet.google.com/xxx" }
```

### DELETE `/api/video-calls/{booking_id}`

### GET `/api/video-calls/queue`
Get call queue stats.

### POST `/api/video-calls/{booking_id}/start`
Start a call session.

### POST `/api/video-calls/{booking_id}/end`
End a call session.

---

## 10. Live Content & Creators

### Creators
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/creators` | List creators |
| POST | `/api/creators` | Add creator |
| PUT | `/api/creators/{creator_id}` | Update creator |
| DELETE | `/api/creators/{creator_id}` | Delete creator |
| POST | `/api/creators/link-telegram` | Link Telegram to creator |

### Live Sessions
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/live/sessions` | List live sessions |
| POST | `/api/live/sessions` | Create live session |
| PUT | `/api/live/sessions/{session_id}` | Update session |
| DELETE | `/api/live/sessions/{session_id}` | Delete session |
| POST | `/api/live/sessions/{session_id}/go-live` | Start live |
| POST | `/api/live/sessions/{session_id}/announce` | Announce to subscribers |
| POST | `/api/live/sessions/{session_id}/start-countdown` | Start countdown |

```json
// POST /api/live/sessions
{
  "title": "Premium Live Session",
  "description": "Exclusive content",
  "ticket_price": 199,
  "scheduled_at": "2025-06-15T20:00:00Z",
  "max_viewers": 100
}
```

### Live Tickets & Super Chats
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/live/tickets` | List tickets |
| POST | `/api/live/tickets/{ticket_id}/approve` | Approve ticket |
| POST | `/api/live/tickets/{ticket_id}/reject` | Reject ticket |
| GET | `/api/live/superchats` | List super chats |
| POST | `/api/live/superchats/{chat_id}/approve` | Approve super chat |
| POST | `/api/live/superchats/{chat_id}/reject` | Reject super chat |

---

## 11. Telegram Admins & Paid Posts

### Telegram Admins
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/telegram-admins` | List TG admins |
| POST | `/api/telegram-admins` | Add TG admin |
| PUT | `/api/telegram-admins/{admin_id}` | Update admin |
| DELETE | `/api/telegram-admins/{admin_id}` | Delete admin |

### Paid Posts
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/paid-posts` | List paid posts |
| GET | `/api/paid-posts/{post_id}` | Get post details |
| PUT | `/api/paid-posts/{post_id}` | Update post |
| DELETE | `/api/paid-posts/{post_id}` | Delete post |
| GET | `/api/unlock-requests` | List unlock requests |
| POST | `/api/unlock-requests/{request_id}/approve` | Approve unlock |
| POST | `/api/unlock-requests/{request_id}/reject` | Reject unlock |
| DELETE | `/api/unlock-requests/{request_id}` | Delete request |

---

## 12. Mini App - User Facing
*These endpoints are used by the Telegram Mini App WebApp. No JWT auth — uses Telegram `initData` validation.*

### POST `/api/miniapp/resolve-tenant-by-init`
Resolve tenant from Telegram `initData`.
```json
// Request
{ "initData": "query_id=xxx&user=...&hash=xxx" }

// Response 200
{
  "tenant_id": "tenant_uuid",
  "bot_name": "MyBot",
  "bot_username": "mybot",
  "settings": { "payment_upi_id": "upi@bank", "qr_code_url": "..." }
}
```

### GET `/api/miniapp/plans?tenant_id={tenant_id}`
Get active plans for a tenant's Mini App.
```json
// Response 200
[
  { "id": "uuid", "name": "Premium", "price": 299, "duration_days": 30 }
]
```

### GET `/api/miniapp/status/{telegram_user_id}?tenant_id={tenant_id}`
Get user subscription status.
```json
// Response 200
{
  "is_subscribed": true,
  "plan_name": "Premium",
  "end_date": "2025-02-01T00:00:00Z",
  "days_remaining": 15
}
```

### POST `/api/miniapp/upload-screenshot`
Upload payment screenshot. **Multipart form data.**
```
Fields: telegram_user_id, plan_id, tenant_id, amount
File: screenshot (image)
```

### POST `/api/miniapp/create-order`
Create Razorpay order from Mini App.
```json
{
  "telegram_user_id": "123456789",
  "plan_id": "plan_uuid",
  "tenant_id": "tenant_uuid"
}
```

### POST `/api/miniapp/verify-payment`
Verify Razorpay payment from Mini App.

### POST `/api/miniapp/apply-coupon`
```json
{ "code": "SAVE20", "plan_id": "plan_uuid", "tenant_id": "tenant_uuid" }
```

### GET `/api/miniapp/payments/{telegram_user_id}?tenant_id={tenant_id}`
User's payment history.

### GET `/api/miniapp/upi-details?tenant_id={tenant_id}`
Get UPI payment details for tenant.

### GET `/api/miniapp/referral/{telegram_user_id}?tenant_id={tenant_id}`
Get referral info.

### POST `/api/miniapp/referral/apply`
Apply referral code.

### GET `/api/miniapp/notifications/{telegram_user_id}?tenant_id={tenant_id}`
Get user notifications.

### GET `/api/miniapp/live-sessions/public?tenant_id={tenant_id}`
List public live sessions.

### POST `/api/miniapp/live-ticket/upload-screenshot`
Upload live ticket screenshot.

### GET `/api/miniapp/live-ticket/status/{telegram_user_id}/{session_id}?tenant_id={tenant_id}`
Check live ticket status.

---

## 13. Mini App - Admin (Telegram)
*Used by Telegram bot admins through the Mini App admin panel.*

### GET `/api/miniapp/admin/check/{telegram_user_id}?tenant_id={tenant_id}`
Check if user is admin.

### GET `/api/miniapp/admin/stats/{telegram_user_id}?tenant_id={tenant_id}`
Get admin dashboard stats.
```json
// Response 200
{
  "total_subscribers": 150,
  "active_subscribers": 120,
  "total_revenue": 119600,
  "pending_payments": 5
}
```

### GET `/api/miniapp/admin/pending-payments/{telegram_user_id}?tenant_id={tenant_id}`
List pending payment approvals.

### POST `/api/miniapp/admin/payment-action`
Approve/reject payment.
```json
{
  "payment_id": "uuid",
  "action": "approve",  // approve|reject
  "admin_telegram_user_id": "123456789",
  "tenant_id": "tenant_uuid"
}
```

### GET `/api/miniapp/admin/subscribers/{telegram_user_id}?tenant_id={tenant_id}`
List all subscribers.

### POST `/api/miniapp/admin/broadcast`
Send broadcast from Mini App.
```json
{
  "message": "Hello!",
  "admin_telegram_user_id": "123456789",
  "target": "all",
  "tenant_id": "tenant_uuid"
}
```

### Live Session Admin
| Method | Endpoint |
|--------|----------|
| GET | `/api/miniapp/admin/live-sessions/{telegram_user_id}?tenant_id=` |
| POST | `/api/miniapp/admin/live-session` |
| POST | `/api/miniapp/admin/announce-live/{session_id}` |
| POST | `/api/miniapp/admin/live-session/{session_id}/go-live` |
| POST | `/api/miniapp/admin/live-session/{session_id}/end` |
| DELETE | `/api/miniapp/admin/live-session/{session_id}` |

### Paid Posts Admin
| Method | Endpoint |
|--------|----------|
| GET | `/api/miniapp/admin/paid-posts/{telegram_user_id}?tenant_id=` |
| POST | `/api/miniapp/admin/paid-post` |
| POST | `/api/miniapp/admin/paid-post-with-media` |
| POST | `/api/miniapp/admin/paid-post/{post_id}/toggle` |
| POST | `/api/miniapp/admin/paid-post/{post_id}/blur` |
| POST | `/api/miniapp/admin/paid-post/{post_id}/broadcast` |

---

## 14. Mini App - Dashboard Management
*Auth Required (JWT). Used by the web dashboard under "Mini App" section.*

### Plans (Mini App)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/miniapp-manage/plans` | List Mini App plans |
| POST | `/api/miniapp-manage/plans` | Create Mini App plan |
| PUT | `/api/miniapp-manage/plans/{plan_id}` | Update plan |
| DELETE | `/api/miniapp-manage/plans/{plan_id}` | Delete plan |

```json
// POST /api/miniapp-manage/plans
{
  "name": "VIP Video Call",
  "description": "30 min 1:1 call",
  "price": 999,
  "duration_days": 30,
  "duration_minutes": 30,
  "plan_type": "video_call",  // subscription|video_call|one_time
  "is_active": true
}
// Note: source="miniapp" is automatically set
```

### Subscribers (Mini App)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/miniapp-manage/subscribers?page=1&limit=50` | List Mini App subscribers |

```json
// Response 200
{ "subscribers": [...], "total": 10, "active": 8 }
```

### Payments (Mini App)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/miniapp-manage/payments?page=1&limit=50&status=pending` | List payments |
| POST | `/api/miniapp-manage/payment-action` | Approve/reject |

```json
// Response 200
{ "payments": [...], "total": 14, "verified": 10, "revenue": 5970 }

// POST payment-action
{ "payment_id": "uuid", "action": "approve" }
```

### Video Bookings (Dashboard)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/miniapp-manage/video-bookings` | List bookings |
| POST | `/api/miniapp-manage/booking-action` | Approve/reject |

### Live Streams (Dashboard)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/miniapp-manage/live-streams` | List streams |
| POST | `/api/miniapp-manage/start-live` | Start stream |
| POST | `/api/miniapp-manage/end-live` | End stream |

### Settings (Mini App)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/miniapp-manage/settings` | Get settings |
| PUT | `/api/miniapp-manage/settings` | Update settings |

---

## 15. Mini App - Chat

### POST `/api/miniapp/chat/send`
User sends message to admin.
```json
{
  "telegram_user_id": "123456789",
  "message": "Hello, need help!",
  "tenant_id": "tenant_uuid"
}
```

### GET `/api/miniapp/chat/history/{telegram_user_id}?tenant_id={tenant_id}`
Get chat history for user.

### GET `/api/miniapp/admin/chats/{telegram_user_id}?tenant_id={tenant_id}`
Admin: list all user chats.

### POST `/api/miniapp/admin/chat/reply`
Admin reply to user.
```json
{
  "admin_telegram_user_id": "admin_id",
  "user_id": "user_telegram_id",
  "message": "Sure, let me help!",
  "tenant_id": "tenant_uuid"
}
```

### GET `/api/miniapp/admin/chat/messages/{user_id}?tenant_id={tenant_id}`
Get messages for specific user.

### Dashboard Chat Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/miniapp-manage/chats` | List all chats |
| GET | `/api/miniapp-manage/chat/{user_id}` | Get user chat |
| POST | `/api/miniapp-manage/chat/reply` | Reply to user |

---

## 16. Mini App - Video Calls & Live

### POST `/api/miniapp/book-video-call`
Book a video call.
```json
{
  "telegram_user_id": "123456789",
  "telegram_username": "john",
  "plan_id": "plan_uuid",
  "scheduled_date": "2025-06-15",
  "scheduled_time": "14:00",
  "tenant_id": "tenant_uuid"
}
```

### GET `/api/miniapp/my-bookings/{telegram_user_id}?tenant_id={tenant_id}`
User's bookings list.

### GET `/api/miniapp/active-live?tenant_id={tenant_id}`
Check if there's an active live stream.
```json
// Response 200
{
  "is_live": true,
  "session": { "id": "uuid", "title": "Live Session", "started_at": "..." }
}
```

---

## 17. Tenant Management

### POST `/api/validate-bot`
Validate a Telegram bot token.
```json
{ "bot_token": "123:ABC..." }
// Response: { "valid": true, "bot_username": "mybot", "bot_name": "My Bot" }
```

### POST `/api/onboard`
Onboard new tenant with bot.
```json
{
  "bot_token": "123:ABC...",
  "channel_id": "-100123456",
  "payment_upi_id": "upi@bank"
}
```

### GET `/api/dashboard/{tenant_id}`
Get tenant dashboard data.

### PUT `/api/settings/{tenant_id}`
Update tenant settings.

### GET `/api/team`
List team members for current tenant.

### POST `/api/team`
Add team member.
```json
{ "email": "member@example.com", "name": "Team Member", "password": "Pass123", "role": "bot_admin" }
```

### DELETE `/api/team/{admin_id}`
Remove team member.

### PUT `/api/team/{admin_id}/reset-password`
Reset team member password.

---

## 18. SaaS Management (Super Admin Only)

### Tenants CRUD
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/saas/tenants` | List all tenants |
| POST | `/api/saas/tenants` | Create tenant |
| PUT | `/api/saas/tenants/{tenant_id}` | Update tenant |
| DELETE | `/api/saas/tenants/{tenant_id}` | Delete tenant |

### Tenant Admins
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/saas/tenant-admins` | List all tenant admins |
| POST | `/api/saas/tenant-admins` | Create tenant admin |
| PUT | `/api/saas/tenant-admins/{admin_id}` | Update admin |
| DELETE | `/api/saas/tenant-admins/{admin_id}` | Delete admin |
| PUT | `/api/saas/tenant-admins/{admin_id}/reset-password` | Reset password |

### SaaS Subscriptions
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/saas/subscriptions` | List subscriptions |
| POST | `/api/saas/assign-subscription` | Assign subscription |
| DELETE | `/api/saas/subscriptions/{sub_id}` | Delete subscription |

### Bot Plans (SaaS Level)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/saas/bot-plans` | List bot plans |
| POST | `/api/saas/bot-plans` | Create bot plan |
| PUT | `/api/saas/bot-plans/{plan_id}` | Update |
| DELETE | `/api/saas/bot-plans/{plan_id}` | Delete |

### Trial Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/trial/config` | Get trial config |
| PUT | `/api/trial/config` | Update trial config |
| GET | `/api/trial/accounts` | List trial accounts |
| POST | `/api/trial/activate` | Activate trial |
| POST | `/api/trial/extend` | Extend trial |
| POST | `/api/trial/cancel` | Cancel trial |
| POST | `/api/trial/convert` | Convert trial to paid |

### Admin Stats
### GET `/api/admin/stats`
Platform-wide statistics.
```json
// Response 200
{
  "total_tenants": 15,
  "active_tenants": 12,
  "total_users": 5000,
  "total_revenue": 1500000,
  "mrr": 125000,
  "growth_rate": 15.5
}
```

---

## 19. Support Tickets

### POST `/api/support/tickets`
Create support ticket.
```json
{ "subject": "Need help with payments", "message": "My payment is stuck..." }
```

### GET `/api/support/tickets`
List user's tickets.

### POST `/api/support/tickets/{ticket_id}/message`
Add message to ticket.
```json
{ "message": "Here's more details..." }
```

### PUT `/api/support/tickets/{ticket_id}/close`
Close ticket.

### PUT `/api/support/tickets/{ticket_id}/reopen`
Reopen ticket.

### DELETE `/api/support/tickets/{ticket_id}`
Delete ticket.

### Admin Support
| Method | Endpoint |
|--------|----------|
| GET | `/api/admin/support/tickets` |
| POST | `/api/admin/support/tickets/{ticket_id}/reply` |
| PUT | `/api/admin/support/tickets/{ticket_id}/status` |

---

## 20. WebSocket Endpoints

### WS `/api/miniapp/ws/call/{room_id}`
WebRTC signaling for 1:1 video calls.
```
Query: ?user_id=telegram_user_id&user_type=user|admin
Messages: JSON { type: "offer"|"answer"|"ice-candidate"|"join", ... }
```

### WS `/api/miniapp/ws/live/{session_id}`
Live stream signaling.
```
Query: ?user_id=telegram_user_id&user_type=viewer|admin
Messages: JSON { type: "offer"|"answer"|"ice-candidate"|"superchat", ... }
```

### WS `/api/miniapp/ws/chat/{user_type}/{user_id}`
Real-time private messaging.
```
user_type: "user" | "admin"
Messages: JSON { type: "message", content: "Hello!", recipient_id: "..." }
```

---

## Data Models Reference

### User
| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Unique ID |
| email | string | Email address |
| name | string | Full name |
| phone | string | Phone number |
| role | string | `super_admin`, `tenant_admin`, `bot_admin` |
| tenant_id | string | Tenant UUID |
| dashboard_plan | string | SaaS plan name |
| dashboard_subscription_status | string | `active`, `inactive`, `trial` |
| trial_end_date | datetime | Trial expiry |

### Subscription Plan
| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Unique ID |
| name | string | Plan name |
| price | float | Price in INR |
| duration_days | int | Subscription duration |
| features | string[] | Feature list |
| is_active | bool | Active status |
| channel_id | string | Telegram channel ID |
| source | string | `"bot"` or `"miniapp"` |

### Subscriber
| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Unique ID |
| telegram_user_id | string | Telegram user ID |
| telegram_username | string | Username |
| plan_id | string | Plan UUID |
| plan_name | string | Plan name |
| status | string | `active`, `expired`, `cancelled` |
| start_date | datetime | Start date |
| end_date | datetime | End date |

### Payment
| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Unique ID |
| telegram_user_id | string | Payer Telegram ID |
| amount | float | Amount in INR |
| plan_id | string | Plan UUID |
| payment_method | string | `manual`, `razorpay` |
| status | string | `pending`, `verified`, `rejected` |
| screenshot_url | string | Screenshot URL (manual) |
| razorpay_order_id | string | Razorpay order ID |
| razorpay_payment_id | string | Razorpay payment ID |

### Video Call Booking
| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Unique ID |
| telegram_user_id | string | Booker Telegram ID |
| plan_id | string | Plan UUID |
| scheduled_date | string | Date (YYYY-MM-DD) |
| scheduled_time | string | Time (HH:MM) |
| duration_minutes | int | Call duration |
| price | float | Price |
| status | string | `pending`, `confirmed`, `completed`, `cancelled` |
| meeting_link | string | Video call URL |

---

## Error Responses

All error responses follow this format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing/invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 500 | Internal Server Error |

---

## Authentication Flow

1. **Register** → `POST /api/auth/register` → Get JWT token
2. **Login** → `POST /api/auth/login` → Get JWT token
3. **Use token** → Add `Authorization: Bearer <token>` header to all requests
4. **Check session** → `GET /api/auth/me` → Verify token is valid

## Mini App Authentication Flow

1. **Telegram sends `initData`** → User opens Mini App
2. **Resolve tenant** → `POST /api/miniapp/resolve-tenant-by-init` with `initData`
3. **Get tenant_id** → Use it in all subsequent Mini App API calls as query param
4. **No JWT needed** → Mini App uses `telegram_user_id` + `tenant_id` for auth
