# ATLAS DevOS — Cloned & Deployed

Cloned from https://github.com/svetlanaslinko057/234dsdw23 (2026-05-01).

## Architecture

The repo ships THREE coordinated codebases sharing one FastAPI backend and one MongoDB:

| Layer | Path | Tech | Served at |
|-------|------|------|-----------|
| **Mobile App** (Expo / React Native) | `/app/frontend/` | Expo SDK 54, React Native 0.81, expo-router 6 | `/` (port 3000 via Metro tunnel) |
| **Web Platform** (React CRA) | `/app/web/` | CRA 5 + craco, Tailwind, Radix UI, React Router 7 | `/api/web-ui/` (FastAPI serves static build) |
| **Backend** (FastAPI) | `/app/backend/` | FastAPI + Socket.IO + Motor (MongoDB) + emergentintegrations | port 8001 (`/api/*` via ingress) |

## Web (React) — User Surfaces

3 distinct UIs inside one bundle (React Router):

- **Client cabinet** (`/client/...`) — order projects, see deliverables, billing, contracts, transparency layer
- **Developer cabinet** (`/developer/...`) — marketplace, accepted modules, time tracking, earnings, leaderboard
- **Admin** (`/admin/...` and `/admin-v2/...`) — Dashboard, Workflow, QA, Finance, Team, System, Profile, Inbox, War Room, Templates, Withdrawals, Earnings Control

90+ pages in `web/src/pages/`. Auth: cookie-based against `/api/auth/*`.

## Mobile (Expo) — Pulse Surface

`/app/frontend/app/` (file-based routing):
- `welcome`, `auth`, `gateway`, `index`, `hub`, `inbox`, `profile`, `settings`, `chat`, `activity`
- Role nests: `admin/`, `client/`, `developer/`, `lead/`, `operator/`, `project/`, `workspace/`

The mobile app is the "remote control" — web is the brain.

## Backend Subsystems (high level)

`assignment_engine`, `acceptance_layer`, `time_tracking_layer`, `event_engine`, `decomposition_engine`, `pricing_engine`, `qa_layer`, `escrow_layer`, `earnings_layer`, `decision_layer`, `intelligence_layer`, `module_motion`, `operator_engine`, `auto_guardian`, `team_balancer`, `reputation_decay`, `system_truth`, `client_workspace`, `developer_brain`, `revenue_brain`, `payment_providers/` (WayForPay + Mock), Socket.IO real-time bus, sentence-transformers semantic matching.

Background loops: GUARDIAN (120s), MODULE MOTION (15s), OPERATOR SCHEDULER (300s), EVENT ENGINE (15min).

## Seeded data (auto on startup)

- Admin user
- Quick-access users: `admin@atlas.dev`, `john@atlas.dev` (developer), `client@atlas.dev`, `multi@atlas.dev` (developer)
- Demo project "Acme Analytics Platform" with 3 modules
- Mock seed: 2 projects, 7 modules, 6 earnings, 6 invoices, 2 deliverables, 3 tickets, 3 notifications
- 4 scope templates, system_config, mock providers, portfolio cases

## Deployment Notes

1. `requirements.txt` pulled in `sentence-transformers` → torch + CUDA libs (>5 GB). Replaced with **CPU-only torch 2.4.0** to fit the 10 GB `/app` quota.
2. Added missing `resend` Python package (used by `email_service.py`; runs in disabled mode unless `RESEND_API_KEY` is set).
3. `web/.env` created with `REACT_APP_BACKEND_URL=` (empty = same-origin, since web is served by FastAPI under `/api/web-ui/`) and `PUBLIC_URL=/api/web-ui` so React Router's `basename` works.
4. Web build: `cd /app/web && yarn build` → `/app/web/build/` → FastAPI auto-serves it.
5. Supervisor managed: `backend`, `expo`, `mongodb`. Web is static — no extra service.

## MOCKED integrations (disabled until keys provided)

- **Email** (Resend) — disabled, OTPs print to backend log instead
- **Cloudinary** — MOCK mode, files saved locally
- **WayForPay** — falls back to mock provider until `WAYFORPAY_*` env keys are set
- **Stripe** — `stripe==15.0.1` installed, used by `payment_providers` if `STRIPE_*` keys are set
- **Google OAuth** — `google_auth.py` exists but inactive without keys
- **HuggingFace** — sentence-transformers downloads `all-MiniLM-L6-v2` on first boot (no auth needed, but `HF_TOKEN` would speed it up)

## Smart Enhancement Opportunity

The system already has a "Pressure View / System Actions Feed / Risk Signals" architecture in place
(`system-actions-feed.tsx`, `system-balance.tsx`, `dev-opportunities-pressure.tsx`,
`hidden_ranking.py`, `auto_guardian.py`). Next iteration: surface these signals on the admin
dashboard as a single "System Visibility Layer" widget (top 3 overloaded devs, last 5 system
adjustments, current risks) — turns the smart engine into a *visible* control panel and improves
operator retention / paid-tier conversion.
