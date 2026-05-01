"""
Master Admin Integrations — single source of truth for runtime-configurable secrets.

Stores all admin-managed integration credentials under a single MongoDB doc:

    db.system_config.find_one({"key": "integrations_settings"})

Shape (every block is optional — admin can clear what they don't need):

    {
      "key": "integrations_settings",
      "email": {
        "provider": "resend",
        "api_key":  "re_…",
        "from_email": "noreply@evax.io",
        "from_name":  "EVA-X"
      },
      "google_auth": {
        "client_id":     "….apps.googleusercontent.com",
        "client_secret": "…"
      },
      "wayforpay": {
        "merchant_account": "y_store_in_ua",
        "secret_key":       "…",
        "merchant_password":"…",
        "domain":           "evax.io",
        "currency":         "UAH",
        "service_url":      "<backend>/api/payments/wayforpay/callback",
        "return_url":       "<frontend>/client/billing"
      },
      "stripe": {
        "publishable_key":  "pk_test_…",
        "secret_key":       "sk_test_…",
        "restricted_key":   "rk_test_…",
        "webhook_secret":   "whsec_…",
        "currency":         "usd"
      },
      "app": {
        "preview_url":  "https://<emergent-preview>.preview.emergentagent.com",
        "active_payment_provider": "stripe" | "wayforpay" | "mock"
      }
    }

The admin UI calls:
  GET  /api/admin/settings/integrations           — read masked view
  PUT  /api/admin/settings/integrations/{block}   — update one block
  POST /api/admin/settings/integrations/{block}/test  — live-test connection
  GET  /api/config/public                         — UN-AUTH public config
                                                    (Stripe publishable, Google
                                                     client_id, app URL, flags)

`get_setting(block)` is the helper every other module uses to fetch the
*current* config — never cached, so admin saves take effect on the next
request without a restart.
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("admin_integrations")

_db = None  # injected by init_router()

SUPPORTED_BLOCKS = ("email", "google_auth", "wayforpay", "stripe", "app")


# ----------------------------------------------------------------- internals
def _mask(value: Optional[str], head: int = 6, tail: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= head + tail:
        return "*" * len(value)
    return f"{value[:head]}…{value[-tail:]}"


async def _load_doc() -> dict:
    if _db is None:
        return {}
    doc = await _db.system_config.find_one({"key": "integrations_settings"}, {"_id": 0})
    return doc or {}


async def get_setting(block: str) -> dict:
    """Fetch the current settings block. Always async, always live."""
    doc = await _load_doc()
    return doc.get(block) or {}


async def set_setting(block: str, value: dict) -> dict:
    """Replace one block. Caller passes only the fields to update — we merge."""
    if block not in SUPPORTED_BLOCKS:
        raise ValueError(f"unsupported block: {block}")
    current = await get_setting(block)
    merged = {**current, **{k: v for k, v in value.items() if v is not None}}
    # Empty string clears the field (so admin can wipe a key from the UI)
    merged = {k: v for k, v in merged.items() if v != ""}
    await _db.system_config.update_one(
        {"key": "integrations_settings"},
        {"$set": {"key": "integrations_settings", block: merged}},
        upsert=True,
    )
    return merged


# ----------------------------------------------------------------- public view
def _masked_view(doc: dict) -> dict:
    """Build the admin-readable view: secret keys masked, flags surfaced."""
    email = doc.get("email") or {}
    google = doc.get("google_auth") or {}
    wfp = doc.get("wayforpay") or {}
    stripe = doc.get("stripe") or {}
    app = doc.get("app") or {}

    return {
        "email": {
            "provider": email.get("provider") or "resend",
            "from_email": email.get("from_email") or "",
            "from_name": email.get("from_name") or "",
            "api_key_masked": _mask(email.get("api_key")),
            "configured": bool(email.get("api_key")),
            "env_fallback": bool(os.environ.get("RESEND_API_KEY")),
        },
        "google_auth": {
            "client_id": google.get("client_id") or "",
            "client_secret_masked": _mask(google.get("client_secret")),
            "configured": bool(google.get("client_id")),
            "env_fallback": bool(os.environ.get("GOOGLE_CLIENT_ID")),
        },
        "wayforpay": {
            "merchant_account": wfp.get("merchant_account") or "",
            "secret_key_masked": _mask(wfp.get("secret_key")),
            "merchant_password_masked": _mask(wfp.get("merchant_password")),
            "domain": wfp.get("domain") or "",
            "currency": wfp.get("currency") or "UAH",
            "service_url": wfp.get("service_url") or "",
            "return_url": wfp.get("return_url") or "",
            "configured": bool(wfp.get("merchant_account") and wfp.get("secret_key")),
        },
        "stripe": {
            "publishable_key": stripe.get("publishable_key") or "",
            "secret_key_masked": _mask(stripe.get("secret_key")),
            "restricted_key_masked": _mask(stripe.get("restricted_key")),
            "webhook_secret_masked": _mask(stripe.get("webhook_secret")),
            "currency": stripe.get("currency") or "usd",
            "configured": bool(stripe.get("secret_key")),
        },
        "app": {
            "preview_url": app.get("preview_url") or "",
            "active_payment_provider": app.get("active_payment_provider") or "auto",
        },
    }


# ----------------------------------------------------------------- pydantic
class EmailUpdate(BaseModel):
    api_key: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    provider: Optional[str] = None


class GoogleAuthUpdate(BaseModel):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None


class WayForPayUpdate(BaseModel):
    merchant_account: Optional[str] = None
    secret_key: Optional[str] = None
    merchant_password: Optional[str] = None
    domain: Optional[str] = None
    currency: Optional[str] = None
    service_url: Optional[str] = None
    return_url: Optional[str] = None


class StripeUpdate(BaseModel):
    publishable_key: Optional[str] = None
    secret_key: Optional[str] = None
    restricted_key: Optional[str] = None
    webhook_secret: Optional[str] = None
    currency: Optional[str] = None


class AppUpdate(BaseModel):
    preview_url: Optional[str] = None
    active_payment_provider: Optional[str] = None  # 'auto' | 'stripe' | 'wayforpay' | 'mock'


# ----------------------------------------------------------------- seeding
DEFAULT_SEED = {
    # User-provided test keys (May 2026). Admin can rotate these from the UI.
    "wayforpay": {
        "merchant_account": "y_store_in_ua",
        "secret_key": "4f27e43c7052b31c5df78863e0119b51b1e406ef",
        "merchant_password": "a6fcf5fe2a413bdd25bb8b2e7100663a",
        "domain": "evax.io",
        "currency": "UAH",
    },
    "stripe": {
        "publishable_key": "pk_test_51TP0ROBXF2ZAbV1VYJ4kSYk60ImPBed3hZ5S4u3Dc7egaiqxmHU6F2Gn4wVD4eEaCPXneGJmtrJhbzbYA2IB90da00dkoOhmyV",
        "secret_key": "sk_test_51TP0ROBXF2ZAbV1VCkyMZRRpfLZ44sEh8A1Y0SSNohBftnduaQmaXgekWgsR7NwszeUy84K701AZoO9igmlO10HH00jpPTVDHl",
        "restricted_key": "rk_test_51TP0ROBXF2ZAbV1V1e0ziiE2khT8XFL2fflgjrHM7vESaABhHyX6Q6VdnwMQ9DNB0d4lguE18sjIKUERZJ9XCmaH00Jbz6gvI9",
        "currency": "usd",
    },
    "app": {
        "preview_url": os.environ.get("APP_URL") or os.environ.get("BACKEND_URL") or "",
        "active_payment_provider": "auto",
    },
}


async def seed_defaults_if_empty(db) -> None:
    """One-shot seed on first boot. Safe to call repeatedly — only fills empty blocks."""
    doc = await db.system_config.find_one({"key": "integrations_settings"}) or {}
    update: dict = {}
    for block, defaults in DEFAULT_SEED.items():
        if not doc.get(block):
            update[block] = defaults
    if update:
        await db.system_config.update_one(
            {"key": "integrations_settings"},
            {"$set": {"key": "integrations_settings", **update}},
            upsert=True,
        )
        logger.info(
            f"INTEGRATIONS seed: added blocks={list(update.keys())} "
            f"(admin can rotate from /admin/integrations)"
        )


# ----------------------------------------------------------------- router
def init_router(db, admin_dep, public_url_helper=None) -> APIRouter:
    """Mounts /api/admin/settings/integrations and /api/config/public."""
    global _db
    _db = db

    router = APIRouter(tags=["admin-integrations"])

    # ----------- ADMIN: read full masked view --------------------
    @router.get("/api/admin/settings/integrations")
    async def read_all(_admin=Depends(admin_dep)):
        doc = await _load_doc()
        return _masked_view(doc)

    # ----------- ADMIN: per-block updaters -----------------------
    @router.put("/api/admin/settings/integrations/email")
    async def update_email(payload: EmailUpdate, _admin=Depends(admin_dep)):
        await set_setting("email", payload.dict())
        # Hot-apply to the running email_service module
        try:
            import email_service
            email_service.set_runtime_config(await get_setting("email"))
        except Exception as e:
            logger.warning(f"email_service hot-reload skipped: {e}")
        return _masked_view(await _load_doc())

    @router.put("/api/admin/settings/integrations/google_auth")
    async def update_google(payload: GoogleAuthUpdate, _admin=Depends(admin_dep)):
        await set_setting("google_auth", payload.dict())
        return _masked_view(await _load_doc())

    @router.put("/api/admin/settings/integrations/wayforpay")
    async def update_wfp(payload: WayForPayUpdate, _admin=Depends(admin_dep)):
        await set_setting("wayforpay", payload.dict())
        return _masked_view(await _load_doc())

    @router.put("/api/admin/settings/integrations/stripe")
    async def update_stripe(payload: StripeUpdate, _admin=Depends(admin_dep)):
        await set_setting("stripe", payload.dict())
        return _masked_view(await _load_doc())

    @router.put("/api/admin/settings/integrations/app")
    async def update_app(payload: AppUpdate, _admin=Depends(admin_dep)):
        # Validate active_payment_provider
        if payload.active_payment_provider:
            if payload.active_payment_provider not in {"auto", "stripe", "wayforpay", "mock"}:
                raise HTTPException(
                    status_code=400,
                    detail="active_payment_provider must be one of: auto, stripe, wayforpay, mock",
                )
        await set_setting("app", payload.dict())
        return _masked_view(await _load_doc())

    # ----------- ADMIN: live tests -------------------------------
    @router.post("/api/admin/settings/integrations/email/test")
    async def test_email(body: dict, _admin=Depends(admin_dep)):
        """Send a one-off test email to whatever address admin types in."""
        try:
            import email_service
            email_service.set_runtime_config(await get_setting("email"))
            if not email_service.is_configured():
                return {"ok": False, "error": "RESEND_API_KEY not configured (set it above and save first)"}
            to = (body.get("to") or "").strip().lower()
            if not to:
                raise HTTPException(status_code=400, detail="to (email) required")
            msg_id = await email_service.send_otp_email(to, "000000", ttl_minutes=10)
            return {"ok": True, "message_id": msg_id, "to": to}
        except Exception as e:
            return {"ok": False, "error": str(e)[:300]}

    @router.post("/api/admin/settings/integrations/stripe/test")
    async def test_stripe(_admin=Depends(admin_dep)):
        """Verify the secret key by trying to retrieve account info."""
        cfg = await get_setting("stripe")
        secret = (cfg.get("secret_key") or "").strip()
        if not secret:
            return {"ok": False, "error": "Stripe secret_key not configured"}
        try:
            import stripe as stripe_lib
            stripe_lib.api_key = secret
            acct = stripe_lib.Account.retrieve()
            # `acct` is a stripe.Account object — supports both attribute and dict access.
            return {
                "ok": True,
                "account_id": getattr(acct, "id", None) or acct["id"],
                "country": getattr(acct, "country", None),
                "default_currency": getattr(acct, "default_currency", None),
                "charges_enabled": getattr(acct, "charges_enabled", None),
                "details_submitted": getattr(acct, "details_submitted", None),
            }
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}

    @router.post("/api/admin/settings/integrations/wayforpay/test")
    async def test_wfp(_admin=Depends(admin_dep)):
        cfg = await get_setting("wayforpay")
        if not cfg.get("merchant_account") or not cfg.get("secret_key"):
            return {"ok": False, "error": "WayForPay merchant_account/secret_key not configured"}
        # WayForPay has no /me endpoint — best we can do is verify creds shape
        return {
            "ok": True,
            "merchant_account": cfg["merchant_account"],
            "secret_key_length": len(cfg["secret_key"]),
            "domain": cfg.get("domain") or "(missing — set domain to receive payments)",
            "note": "WayForPay does not expose a /me endpoint; live verification happens on first invoice.",
        }

    @router.post("/api/admin/settings/integrations/google_auth/test")
    async def test_google(_admin=Depends(admin_dep)):
        cfg = await get_setting("google_auth")
        if not cfg.get("client_id"):
            return {"ok": False, "error": "Google client_id not configured"}
        # Validate format only (we can't sign-in test from server side)
        cid = cfg["client_id"]
        if not cid.endswith(".apps.googleusercontent.com"):
            return {
                "ok": False,
                "error": "client_id does not look like a valid Google OAuth Client ID (should end with .apps.googleusercontent.com)",
            }
        return {
            "ok": True,
            "client_id": cid,
            "note": "Client ID format valid. Real verification happens on user sign-in.",
        }

    # ----------- PUBLIC: config every frontend needs -------------
    @router.get("/api/config/public")
    async def public_config(request: Request):
        """No auth required. Returns ONLY public-safe config (no secrets).

        Frontends call this on boot to hydrate Stripe.js, Google Sign-In and
        the dynamic preview URL. When the admin saves a new key in the
        admin panel, the next reload of any client picks it up — no
        rebuild, no env change."""
        doc = await _load_doc()
        stripe_cfg = doc.get("stripe") or {}
        google_cfg = doc.get("google_auth") or {}
        app_cfg = doc.get("app") or {}

        # Resolve preview URL: admin override > request origin > env
        preview_url = app_cfg.get("preview_url") or ""
        if not preview_url:
            origin = request.headers.get("origin") or ""
            host = request.headers.get("host") or ""
            scheme = "https" if request.url.scheme == "https" else "http"
            preview_url = origin or (f"{scheme}://{host}" if host else "")

        return {
            "stripe": {
                "enabled": bool(stripe_cfg.get("secret_key")),
                "publishable_key": stripe_cfg.get("publishable_key") or "",
                "currency": stripe_cfg.get("currency") or "usd",
            },
            "google": {
                "enabled": bool(google_cfg.get("client_id")),
                "client_id": google_cfg.get("client_id") or "",
            },
            "wayforpay": {
                "enabled": bool((doc.get("wayforpay") or {}).get("merchant_account")),
            },
            "app": {
                "preview_url": preview_url,
                "active_payment_provider": app_cfg.get("active_payment_provider") or "auto",
            },
        }

    return router
