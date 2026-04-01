TGSubsBot Architecture
Architecture Summary

TGSubsBot is a multi-tenant SaaS platform for Telegram monetization.

It supports:

Platform Owner / Super Admin
Tenant / Creator / Business
Customer / Subscriber / End User

Core capabilities:

SaaS subscription plans for tenants
tenant onboarding
Telegram bot + mini app
customer creation
plan sales
payment verification
live sessions
broadcasts
support
analytics

1. Business Role Architecture
flowchart TB
    A[Super Admin]
    B[Tenant / Creator]
    C[Customer / Subscriber]

    A --> A1[Manage Platform]
    A --> A2[Manage SaaS Plans]
    A --> A3[Manage Tenants]
    A --> A4[View Global Revenue]
    A --> A5[Support and Risk]

    B --> B1[Create Plans]
    B --> B2[Manage Customers]
    B --> B3[View Payments]
    B --> B4[Run Broadcasts]
    B --> B5[Start Live Sessions]
    B --> B6[Manage Branding]

    C --> C1[Open Telegram Bot]
    C --> C2[Use Mini App]
    C --> C3[Buy Plan]
    C --> C4[Join Live]
    C --> C5[Access Paid Content]


