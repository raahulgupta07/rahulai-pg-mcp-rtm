# RTM Agent — P&G Route-to-Market Outlet Classification

## Stack
- **Frontend**: SvelteKit 5 (runes) + Tailwind CSS 4 — token-based flat design, light/dark
- **Backend**: FastAPI (Python) — also serves the built SvelteKit SPA
- **Database**: PostgreSQL 18 (`pgvector/pgvector:pg18`) via psycopg3 connection pool;
  **pgvector** extension enabled (ready for similarity features)
- **AI**: Google Gemini 3.1 Flash Lite via OpenRouter (optional; rule-based fallback)
- **Auth**: JWT (HS256) + JSON user store; optional LDAP / Active Directory + OIDC/OAuth2 SSO (multi-provider)

## Running

```bash
# Docker — runs Postgres + app together (recommended)
docker compose up -d --build      # → http://localhost:8011  (host 8011 → container 8001)
# Host port is configurable: RTM_HOST_PORT=8042 docker compose up -d --build → :8042

# Local dev — needs a Postgres reachable at DATABASE_URL
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8001
cd frontend && npm install && npm run dev
```

## Default Login
- **admin** / admin123 — role **super_admin** (configured via `.env`)
- Other users created by super_admin in Settings ▸ Users, or auto-provisioned via LDAP

## Access Model — roles + groups + permissions
| Role | Base access |
|------|-------------|
| `super_admin` | Everything — Settings, Analytics, LDAP, model config, users, groups |
| `admin` | Classify, data pages, **Rules** |
| `user` | Classify, view own/shared data |

- **Groups** (Settings ▸ Groups) carry permissions from a catalog (`rules`, `analytics`).
  A user's **effective permissions = role base ∪ all their groups** (additive — never reduces).
- Backend gates with `require_perm("rules" | "analytics")`; super_admin always passes.
- The `.env` admin is always migrated to `super_admin`; super_admin can't be disabled/auto-merged.

## Project Structure

```
PG-MCP-RTM/
├── backend/
│   ├── main.py            # FastAPI app — all API routes + SPA serving
│   ├── auth.py            # JWT auth, JSON user store, LDAP, groups & permissions
│   ├── rule_defaults.py   # DEFAULT_RULES — tunable engine parameters
│   ├── docs_seed.py       # Built-in Documentation content
│   └── requirements.txt
├── frontend/src/
│   ├── app.css            # Design system — tokens, dark mode, flat (no radius)
│   ├── lib/
│   │   ├── api.ts  theme.ts  md.ts  types.ts  colors.ts
│   │   ├── stores/auth.svelte.ts        # Auth store (JWT, roles, permissions)
│   │   └── components/   # KpiCard, DataTable, Badge, ChapterHeading,
│   │                     #   Appearance, ChangePassword
│   └── routes/
│       ├── +layout.svelte  # App shell — sidebar + mobile nav + auth guard
│       ├── +page.svelte    # Classify (upload, pipeline, results, Comparison tab)
│       ├── login/ history/ rtm/ compare/ coverage/ docs/
│       ├── rules/          # Classification rule config + versioning
│       ├── cockpit/        # Ops Cockpit — Pulse/Trends/Users/Actions/Audit (analytics perm)
│       │                   #   (analytics/ is a redirect stub → /cockpit)
│       └── users/          # Settings — Users / Model & Config / LDAP / SSO / Groups / Audit
├── src/                    # Python classification engine
│   ├── rtm_classifier.py   # Pareto 80/15/5 per branch — config-driven
│   ├── ai_service.py       # AI enrichment + LLM insights + cost capture
│   ├── database.py         # PostgreSQL layer (psycopg3 pool)
│   ├── job_manager.py      # Job tracking + beautified Excel export
│   └── column_mapper.py
├── data/                   # users.json, settings.json, rule_config.json,
│                           #   ldap_config.json, groups.json, docs_content.json
├── Dockerfile  docker-compose.yml (app + postgres)  .env  .env.example
└── outputs/                # Generated Excel reports
```

> Postgres tables: `jobs`, `job_results`, `job_insights`, `audit_log`,
> `rule_config_history`, `job_shares`.
> `job_results` persists the **full** classifier output incl. AI enrichment
> (`AI_Growth_Signal/Risk_Level/Action/Visit_Priority/Insight`), `Visit_Frequency`,
> and momentum (`Growth_6M_vs_12M`, `Growth_3M_vs_6M`) — so History re-export and the
> RTM Data page keep these fields. Schema additions are idempotent
> `ALTER TABLE … ADD COLUMN IF NOT EXISTS` migrations run on boot in `_init_database`.

## Pages

| Route | Page | Access | Description |
|-------|------|--------|-------------|
| `/` | Classify | all | Upload CSV/Excel, run pipeline (live log), results + Comparison tab |
| `/history` | History | all | Past jobs (own + shared), per-job LLM cost, **Share** |
| `/rtm` | RTM Data | all | Filterable outlet table + export |
| `/compare` | Compare | all | Two-job comparison + outlet movement |
| `/coverage` | Coverage | all | Township gap analysis |
| `/docs` | Docs | all | Read-only reference (6 tabs) |
| `/rules` | Rules | `rules` perm | Tune the engine — versioned, rollback |
| `/cockpit` | Ops Cockpit | `analytics` perm | Live pulse + Trends/Users/Actions/Audit (merged Analytics). `/analytics` redirects here |
| `/users` | Settings | super_admin | Users / Model & Config / LDAP / SSO / Groups / Audit |

## API Endpoints (summary)

| Method | Endpoint | Auth |
|--------|----------|------|
| POST | `/api/auth/login` | No — logs `LOGIN_FAILED` on bad password |
| GET | `/api/auth/me` | Yes — user + prefs + permissions |
| POST | `/api/auth/change-password` | Yes — own password (verifies old) |
| GET/POST | `/api/preferences` | Yes — per-user appearance |
| POST | `/api/upload` · DELETE `/api/upload/{id}` | Yes — stages file to disk first |
| POST | `/api/classify?upload_id=X` | Yes — **sync** (back-compat). Blocks for full run. |
| POST | `/api/classify-async?upload_id=X` | Yes — **async**. Returns `{job_id}` instantly. Reserves job, schedules pipeline as `asyncio.create_task`. LB-timeout safe. |
| GET | `/api/jobs/{id}/status` | Yes — lightweight poller. Returns `{status, step/total, message, log[], ready, error}`. |
| GET | `/api/jobs/{id}/result` | Yes — returns saved full payload when status=completed. |
| GET | `/api/f4-analysis?job_id=X` | Yes — F4 deep-dive: health, top-10, churn-risk, per-branch |
| GET | `/api/jobs` · `/api/jobs/{id}` | Yes — own + shared; admin+ sees all |
| GET | `/api/jobs/{id}/export` · `/comparison` | Yes |
| GET/POST | `/api/jobs/{id}/shares` · `/share` | Yes — owner/admin shares a job |
| GET | `/api/rtm-data` · `/compare` · `/coverage` | Yes |
| GET/POST | `/api/rule-config` (+`/history`, `/rollback/{id}`) | `rules` perm to write |
| GET | `/api/docs-content` | Yes (read-only) |
| GET/POST | `/api/settings` · POST `/api/llm-test` | super_admin |
| GET/POST | `/api/ldap-config` · POST `/api/ldap-test` | super_admin |
| GET/POST | `/api/oidc-config` · POST `/api/oidc-test` | super_admin — SSO providers |
| GET | `/api/auth/oidc/providers` (No) · `/api/auth/oidc/{pid}/login` · `/callback` | OIDC SSO flow |
| GET/POST/DELETE | `/api/users` (+`/{id}`) | super_admin |
| PUT | `/api/users/{id}/password` · `/disabled` · `/ldap-link` · `/groups` | super_admin |
| GET | `/api/users/basic` | Yes — minimal list for share picker |
| GET/POST/PUT/DELETE | `/api/groups` (+`/{id}`) | super_admin |
| GET | `/api/audit` · `/api/analytics` · `/api/cockpit` | `analytics` perm |
| GET/POST | `/api/activity` · `/api/activity/seen` | Yes — notifications feed (derived from jobs + audit) |
| GET | `/api/version` | Yes — app version + changelog (What's new) |
| GET | `/api/health` | No |

> FastAPI auto docs (`/docs`, `/redoc`, `/openapi.json`) are **disabled** — API not browsable.

## Classification Logic
Single CSV/Excel file → Pareto split per `BranchName` (each branch is its own universe):
- **Pure Class A** ≤ Class A cutoff (default 80%) · **Class B** between cutoffs · **Class C** above
- **F4 Distributor** — ≥N cartons/brand/month of a chosen item type → forced Class A Local (F4).
  **Treated as first-class across the app** — own KPI card, own summary row,
  own RTM Data filter, own teal map marker, own Excel row, own deep-dive dashboard
  with health score + churn-risk follow-up list (`GET /api/f4-analysis`).
- **Category override** — outlet dominating a category (≥cutoff%) → Class A {category}
- **Class A (total)** = Pure A + F4 + Category — explicit rollup row

All thresholds are **config-driven** (`/rules`) — no hardcoded values.

## Outlet Lifecycle (cohort)
Every outlet stamped from DocDate: **New** (first buy <3M) · **Active** (bought <3M)
· **Reactivated** (returned after >6M gap) · **Dormant** (3–12M ago) · **Lost** (>12M ago).
Surfaced as 5-card KPI strip on Classify results + column on RTM Data + Excel.

## Upload Flow (2-stage)
Accepts **CSV (.csv) and Excel (.xlsx/.xls)** — both client validation + `accept` allow all three.
1. `POST /api/upload` — streams file (8 MB chunks) to `/app/uploads/{id}_{name}` on disk.
   XHR with `upload.onprogress` → live % bar. Cap 2 GB (frontend).
2. `POST /api/classify?upload_id=X` — reads staged file, runs pipeline, writes DB.
   Parse branches on extension: `.xlsx/.xls` → `pd.read_excel(engine="openpyxl")`,
   else encoding-loop `pd.read_csv` (utf-8/latin-1/cp1252). `finally:` unlinks staged file.

Client preview: CSV → 8 MB slice text parse; Excel → full workbook via **SheetJS `xlsx`**
(lazy `import('xlsx')`, own bundle chunk), first sheet. Both feed a shared `finalizePreview`
→ row/branch/outlet counts, sample table, column-match chips, branch bars.
No upload until "Run Classification" clicked.

## AI Pipeline (parallel + chunked)
`backend/main.py` calls `await asyncio.gather(enrich_task, insights_task)`:
- **3 macro calls** (exec summary, A/B/C recs, growth analysis) fan out via
  `loop.run_in_executor` → `asyncio.gather`
- **Per-outlet enrichment** splits top-N into chunks (default 10), gated by
  `asyncio.Semaphore(max_concurrent)` (default 5). Returns `{cus_code: insight}`
  JSON per chunk → merged on Cus.Code (out-of-order safe).
- Total elapsed ≈ max(layers), not sum. ~3-4x speedup. New `ai.chunk_size` +
  `ai.max_concurrent` keys in `rule_config.json`.

## Rule Engine (`/rules`)
`data/rule_config.json` (defaults `backend/rule_defaults.py`): sections `pareto`,
`wholesaler`, `category_override`, `frequency`, `workload`, `growth`, `risk`, `ai`.
- Each save → a **version** in `rule_config_history` — viewable + **rollback**
- Each job stores the rule snapshot + version it ran with

## Run Comparison
Each job is compared to the previous run — class counts, revenue, by-channel, by-branch,
outlet movement. Shown in the Classify **Comparison** tab + Excel sheets. Excel **Run Info**
sheet records who ran it, rule version, and **LLM tokens + cost**.

## LDAP / Active Directory
- Up to **5 servers** (Settings ▸ LDAP, `data/ldap_config.json`)
- Login: local first, then each enabled server (bind → search → rebind); first hit becomes
  the user's **home server**
- **Email auto-merge** — LDAP login matching a local account's email links into it
- **Group sync** — a group's `ldap_group` matched against the user's `memberOf` on each login

## SSO — OIDC / OAuth2 (`backend/oidc.py`)
Multi-provider OpenID Connect (Keycloak, Google, Microsoft, …). Config in
`data/oidc_config.json` (Settings ▸ **SSO**, super_admin). No new deps — discovery/token via
`requests`, id_token decoded as a trusted back-channel JWT.
- Flow: `GET /api/auth/oidc/{pid}/login` (signed-state cookie → provider authorize) →
  `…/callback` (CSRF state check → code exchange → claims → provision → **RTM JWT** →
  `/login?token=…`; the login page swaps the token for the user via `/api/auth/me`).
- `auth.provision_oidc_user` mirrors LDAP: match username/`oidc_username`, then
  **email auto-merge** (toggle `merge_by_email`; **never into super_admin**), else create
  (`source:"oidc"`). IdP role → admin if in a provider's `admin_roles`; groups synced via the
  same per-group `ldap_group` mapping. Each provider sets `roles_claim`/`groups_claim`
  (nested paths ok, e.g. `realm_access.roles`).
- Public `GET /api/auth/oidc/providers` drives the login-page buttons; `POST /api/oidc-test`
  checks issuer discovery. Redirect URI to register at the IdP: `{base}/api/auth/oidc/{pid}/callback`.

## Job Sharing
`job_shares` table. A job owner or admin shares a job with specific users (History ▸ Share).
Non-admin users see only their own runs + jobs shared with them; admin+ see all.

## LLM Cost Tracking
Every OpenRouter call is sent with `usage:{include:true}` → real token counts + USD cost.
Per job: `jobs.llm_prompt_tokens / llm_completion_tokens / llm_cost / llm_model`. Shown on the
History list, the Cockpit **Pulse** tab (cost/tokens + models + per-user), and the Excel Run Info sheet.

## Ops Cockpit (`/cockpit`) — merged observability
Single super-admin/`analytics`-perm page (Analytics folded in; `/analytics` → redirect).
Tabs: **Pulse** (default) · **Trends** · **Users** · **Actions** · **Audit Log**.
- **Pulse** (`GET /api/cockpit?days=`) — live, 30s auto-refresh + range chips. KPI band
  (jobs/success/tokens/cost/active users/failed logins/avg runtime/outlets), event feed
  (jobs + audit), cost/tokens trend, **models** table, recent jobs (who · model · tokens ·
  cost · duration · status). All **derived** from `jobs` + `audit_log` (no extra tables).
- **Trends/Users/Actions/Audit** (`GET /api/analytics` + `/api/audit`) — 30-day chart,
  per-user + enable/disable, actions-by-type, filterable audit explorer + CSV.

Supporting per-run data: `jobs.llm_model` (stamped each run); `LOGIN_FAILED` logs a
`reason:` (unknown_user/bad_password/disabled) for the security breakdown.

## Notifications + version
- **Activity bell** (top-right) with unread badge → panel: **Activity** feed (filters,
  mark-all-read; `GET/POST /api/activity[/seen]`, unread via `prefs.activity_seen_at`)
  + **What's new** (`GET /api/version` ← `backend/version.py` + `data/changelog.json`).

## Scalability
- **Bundled image**: single container (Postgres + pgvector + FastAPI + SvelteKit
  via supervisord). 4 uvicorn workers, PG tuned (`shared_buffers=512MB`,
  `work_mem=32MB`, `max_connections=200`). ~100 req/s, ~400 concurrent users.
  Override workers via `UVICORN_WORKERS` env. Image ~1.1 GB.
- **Multi-container compose**: separate Postgres + app. Each uvicorn worker
  has own 32-conn psycopg pool (4 workers × 32 = 128 max conns vs PG max 200).
- Heavy work (classify, Excel build) offloaded via `run_in_threadpool` — async
  event loop never blocks. Heavy read endpoints sync `def` (auto-threadpooled).
- AI pipeline = `asyncio.gather` of 3 macro calls + chunked outlet enrichment
  (Semaphore-gated). 3-4× speedup vs serial.

## Deploy Options
| Mode | File | Containers | Users |
|------|------|-----------|-------|
| **Bundled** | `Dockerfile.bundled` + `docker-compose.bundled.yml` | 1 | ~400 |
| **Multi-container** | `docker-compose.yml` | 2 | ~1k |
| **Local dev** | `cd backend && uvicorn ...` + `npm run dev` | — | — |

Bundled internals: `docker/supervisord.conf` runs postgres (via
`docker-entrypoint.sh` with `-c` tuning flags) + uvicorn (with `pg_isready`
wait loop) as managed children. `docker/init-rtm-db.sh` enables pgvector
on first boot via Postgres `/docker-entrypoint-initdb.d/` convention.

## Design System
**Claude.ai-style** with soft rounded corners (radius tokens `--r-sm…xl` = 6/8/12/16px,
`--r-pill` 999px — used app-wide, ~75 refs; flip the tokens to restyle every page).
Inter font; token-only CSS variables (no hardcoded colors). Light/dark/auto via
`[data-theme]` on `<html>`.

**Fonts**: Inter + JetBrains Mono load from Google Fonts CDN (graceful system fallback).
**Material Symbols icons are self-hosted** — `frontend/static/fonts/material-symbols-outlined.ttf`
served at `/fonts/...`, with `@font-face` + the `.material-symbols-outlined` class defined in
`app.css`. Do NOT rely on the CDN for icons: on offline/proxied networks the CDN stylesheet
fails and ligature names (`settings`, `history`…) render as raw text.

| Token | Light | Dark |
|-------|-------|------|
| `--bg` | `#FAF9F5` cream | `#1F1E1B` |
| `--accent` | `#C96442` terracotta | `#E89070` |
| `--text` | `#2C2B26` | `#EDEAE0` |

**Single light theme** — locked via `<html data-theme="light">` in `app.html`; the
Appearance/theme switcher was removed (dark tokens remain in `app.css` but unused).
Desktop left sidebar + a **desktop top bar** (right-aligned bell · change-password · sign-out)
+ mobile bottom nav (`+layout.svelte`). The **activity bell** (badge) opens `ActivityPanel`.
Reusable components: `KpiCard`, `DataTable`, `Badge` (A/B/C/F4), `ChapterHeading`,
`ChangePassword`, `ActivityPanel`.

## Environment Variables
```
DATABASE_URL=postgresql://rtm:rtm@postgres:5432/rtm   # set by docker-compose
OPENROUTER_API_KEY=sk-or-v1-...     # AI insights (optional; rule-based fallback)
LLM_MODEL=google/gemini-3.1-flash-lite-preview
LLM_BASE_URL=https://openrouter.ai/api/v1
JWT_SECRET_KEY=change-in-production
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
ADMIN_DISPLAY_NAME=Administrator
RTM_HOST_PORT=8011                  # host port for docker-compose (maps → container 8001)
```
LLM model/provider and LDAP are also configurable from the UI (Settings).
