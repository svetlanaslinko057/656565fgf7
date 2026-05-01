# ATLAS DevOS — Master Admin Integrations Layer

## Recap (current state)
Cloned from https://github.com/svetlanaslinko057/234dsdw23 → deployed (Expo + React Web + FastAPI + MongoDB).

## Master Admin · Integrations & Keys (NEW)

A single web admin page (`/admin/system` → tab `Integrations`) controls every external integration the
backend talks to. Saves are **hot-reloaded** — no redeploy, no restart.

### What is admin-configurable

| Block | Stored at | Hot-reloaded by | Public field exposed |
|-------|-----------|-----------------|----------------------|
| **Email** (Resend) | `system_config.integrations_settings.email` | `email_service.set_runtime_config()` | — |
| **Google Auth** | `…integrations_settings.google_auth` | `google_auth._resolve_google_client_id()` per-request | `client_id` |
| **WayForPay** | `…integrations_settings.wayforpay` | `payment_providers.get_provider()` per-payment | `enabled` flag |
| **Stripe** | `…integrations_settings.stripe` | `payment_providers.get_provider()` per-payment | `publishable_key`, `currency` |
| **App** (preview URL + active provider) | `…integrations_settings.app` | callbacks pull live each request | `preview_url`, `active_payment_provider` |
| **LLM** (existing) | `system_config.llm_settings` | `admin_llm_settings.get_active_llm_key()` | — |

### Backend wiring

* `/app/backend/admin_integrations.py` — single module with `get_setting()` helper, `set_setting()`, masked view, and the FastAPI router (5 PUT endpoints + 4 test endpoints + 1 public config endpoint).
* `/app/backend/payment_providers/stripe_provider.py` — Stripe wrapper using `emergentintegrations.payments.stripe.checkout.StripeCheckout` (per Emergent Stripe playbook). Conforms to `BasePaymentProvider` — same `create_payment` / `verify_callback` shape as WayForPay/Mock.
* `/app/backend/payment_providers/__init__.py` — `get_provider(db)` is now async, reads admin DB to pick provider (auto / stripe / wayforpay / mock).
* `/app/backend/email_service.py` — added `set_runtime_config()` for hot-reload.
* `/app/backend/google_auth.py` — `_resolve_google_client_id()` lazy-lookup (DB → env → fallback).
* `/app/backend/server.py` — mounts the new router, seeds defaults on startup, adds `/api/webhook/stripe` + `/api/payments/stripe/status/{session_id}`, updates `_provider_create_payment` to use admin URL + async provider.

### Endpoints (admin-only unless noted)

```
GET    /api/admin/settings/integrations                 → masked view of all blocks
PUT    /api/admin/settings/integrations/email           → update Resend config
PUT    /api/admin/settings/integrations/google_auth     → update Google OAuth config
PUT    /api/admin/settings/integrations/wayforpay       → update WFP creds
PUT    /api/admin/settings/integrations/stripe          → update Stripe keys
PUT    /api/admin/settings/integrations/app             → update preview_url + active_payment_provider
POST   /api/admin/settings/integrations/email/test      → send a one-off test email
POST   /api/admin/settings/integrations/stripe/test     → live verify against Stripe API
POST   /api/admin/settings/integrations/wayforpay/test  → cred-shape verify
POST   /api/admin/settings/integrations/google_auth/test → format verify

GET    /api/config/public                  → PUBLIC (no auth) — used by all frontends
                                              { stripe.{enabled, publishable_key, currency},
                                                google.{enabled, client_id},
                                                wayforpay.{enabled},
                                                app.{preview_url, active_payment_provider} }

POST   /api/webhook/stripe                 → Stripe → backend webhook
GET    /api/payments/stripe/status/{sid}   → poll session status (UI fallback for webhook)
```

### Web Admin UI

`/app/web/src/pages/AdminIntegrationsPage.js` — full rewrite. Sections (top → bottom):
1. **App URL & Active Payment Provider** — pin the dynamic Emergent preview URL, force-pick provider
2. **Email · Resend** — API key + from email/name + live "send test email" tool
3. **Google Sign-In** — Client ID (public) + Client Secret + format validator
4. **Stripe** — Publishable / Secret / Restricted / Webhook secret + currency + live `Account.retrieve()` test
5. **WayForPay** — merchant_account / domain / secret_key / merchant_password / currency
6. **LLM** — preserved existing OpenAI / Emergent flow

Every secret field has Show/Hide toggle. Empty input means "keep current". Status pills show
masked fingerprint or "Not configured".

### Seeded test credentials (from user, May 2026)

| Provider | Field | Value |
|----------|-------|-------|
| WayForPay | merchant_account | `y_store_in_ua` |
| WayForPay | secret_key | `4f27e43c…` |
| WayForPay | merchant_password | `a6fcf5fe…` |
| Stripe | publishable_key | `pk_test_51TP0RO…` |
| Stripe | secret_key | `sk_test_51TP0RO…` |
| Stripe | restricted_key | `rk_test_51TP0RO…` |

Stripe live test verified against `acct_1TP0ROBXF2ZAbV1V` (BG, EUR) — `Account.retrieve()` returns 200.

### Pending input from user

* **Google OAuth Client ID + Secret** — user said they will provide
* **Resend API key** + verified `from` address — user has not provided
* **Stripe webhook signing secret** (`whsec_…`) — generated in Stripe dashboard after registering `/api/webhook/stripe` endpoint

### Frontend integration

Web + Expo frontends should boot with a `GET /api/config/public` call to hydrate:
* `Stripe.js` with `stripe.publishable_key`
* `@react-oauth/google` (web) / `expo-auth-session` (mobile) with `google.client_id`
* `app.preview_url` for all redirect-back-from-payment URLs

(Frontend wiring of these dynamic values will be done in the next iteration; the backend layer
that *delivers* them is in place and tested.)
