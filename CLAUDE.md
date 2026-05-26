# RTM Agent — P&G Route-to-Market Outlet Classification

## Stack
- **Frontend**: SvelteKit 5 (runes) + Tailwind CSS 4 — token-based flat design, light/dark
- **Backend**: FastAPI (Python) — also serves the built SvelteKit SPA
- **Database**: PostgreSQL 18 (`pgvector/pgvector:pg18`) via psycopg3 connection pool;
  **pgvector** extension enabled (ready for similarity features)
- **AI**: Google Gemini 3.1 Flash Lite via OpenRouter (optional; rule-based fallback)
- **Auth**: JWT (HS256) + JSON user store; optional LDAP / Active Directory

## Running

```bash
# Docker — runs Postgres + app together (recommended)
docker compose up -d --build      # → http://localhost:8011  (host 8011 → container 8001)

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
│       ├── analytics/      # Platform analytics — 8 tabs (super_admin)
│       └── users/          # Settings — Users / Model & Config / LDAP / Groups / Audit
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

## Pages

| Route | Page | Access | Description |
|-------|------|--------|-------------|
| `/` | Classify | all | Upload CSV, run pipeline (live log), results + Comparison tab |
| `/history` | History | all | Past jobs (own + shared), per-job LLM cost, **Share** |
| `/rtm` | RTM Data | all | Filterable outlet table + export |
| `/compare` | Compare | all | Two-job comparison + outlet movement |
| `/coverage` | Coverage | all | Township gap analysis |
| `/docs` | Docs | all | Read-only reference (6 tabs) |
| `/rules` | Rules | `rules` perm | Tune the engine — versioned, rollback |
| `/analytics` | Analytics | `analytics` perm | Platform analytics — 8 tabs |
| `/users` | Settings | super_admin | Users / Model & Config / LDAP / Groups / Audit |

## API Endpoints (summary)

| Method | Endpoint | Auth |
|--------|----------|------|
| POST | `/api/auth/login` | No — logs `LOGIN_FAILED` on bad password |
| GET | `/api/auth/me` | Yes — user + prefs + permissions |
| POST | `/api/auth/change-password` | Yes — own password (verifies old) |
| GET/POST | `/api/preferences` | Yes — per-user appearance |
| POST | `/api/upload` · DELETE `/api/upload/{id}` | Yes — stages file to disk first |
| POST | `/api/classify?upload_id=X` | Yes — reads staged file, runs pipeline |
| GET | `/api/f4-analysis?job_id=X` | Yes — F4 deep-dive: health, top-10, churn-risk, per-branch |
| GET | `/api/jobs` · `/api/jobs/{id}` | Yes — own + shared; admin+ sees all |
| GET | `/api/jobs/{id}/export` · `/comparison` | Yes |
| GET/POST | `/api/jobs/{id}/shares` · `/share` | Yes — owner/admin shares a job |
| GET | `/api/rtm-data` · `/compare` · `/coverage` | Yes |
| GET/POST | `/api/rule-config` (+`/history`, `/rollback/{id}`) | `rules` perm to write |
| GET | `/api/docs-content` | Yes (read-only) |
| GET/POST | `/api/settings` · POST `/api/llm-test` | super_admin |
| GET/POST | `/api/ldap-config` · POST `/api/ldap-test` | super_admin |
| GET/POST/DELETE | `/api/users` (+`/{id}`) | super_admin |
| PUT | `/api/users/{id}/password` · `/disabled` · `/ldap-link` · `/groups` | super_admin |
| GET | `/api/users/basic` | Yes — minimal list for share picker |
| GET/POST/PUT/DELETE | `/api/groups` (+`/{id}`) | super_admin |
| GET | `/api/audit` · `/api/analytics` | `analytics` perm |
| GET | `/api/health` | No |

> FastAPI auto docs (`/docs`, `/redoc`, `/openapi.json`) are **disabled** — API not browsable.

## Classification Logic
Single CSV → Pareto split per `BranchName` (each branch is its own universe):
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
1. `POST /api/upload` — streams file (8 MB chunks) to `/app/uploads/{id}_{name}` on disk.
   XHR with `upload.onprogress` → live % bar. Cap 2 GB (frontend).
2. `POST /api/classify?upload_id=X` — reads staged file, runs pipeline, writes DB.
   `finally:` unlinks staged file.

CSV preview (8 MB slice, client-side parse): row/branch/outlet counts, sample table,
column-match chips, branch bars. No upload until "Run Classification" clicked.

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

## Job Sharing
`job_shares` table. A job owner or admin shares a job with specific users (History ▸ Share).
Non-admin users see only their own runs + jobs shared with them; admin+ see all.

## LLM Cost Tracking
Every OpenRouter call is sent with `usage:{include:true}` → real token counts + USD cost.
Per job: `jobs.llm_prompt_tokens / llm_completion_tokens / llm_cost`. Shown on the History
list, the Analytics **Cost** tab (totals + per-user), and the Excel Run Info sheet.

## Analytics (`/analytics`) — 8 tabs
Overview · Activity (30-day trend) · Users (analytics + enable/disable) · Actions ·
Audit Log (filterable + CSV) · Jobs · Cost · Auth & Security (local vs LDAP, failed logins).

## Scalability
- PostgreSQL + psycopg pool (max 32)
- Heavy work (classify pipeline, Excel build) offloaded via `run_in_threadpool` — the async
  event loop never blocks; heavy read endpoints are sync `def` (auto-threadpooled)
- Worker-thread pool raised to 64 — handles ~100 concurrent users

## Design System
**Claude.ai-style, flat** (zero border-radius). Inter font; token-only CSS variables
(no hardcoded colors). Light/dark/auto via `[data-theme]` on `<html>`.

| Token | Light | Dark |
|-------|-------|------|
| `--bg` | `#FAF9F5` cream | `#1F1E1B` |
| `--accent` | `#C96442` terracotta | `#E89070` |
| `--text` | `#2C2B26` | `#EDEAE0` |

**Appearance** modal — 6 palettes + custom accent + density (per-user, persisted in
`/api/preferences`). Desktop left sidebar + mobile bottom nav (`+layout.svelte`).
Reusable components: `KpiCard`, `DataTable`, `Badge` (A/B/C/F4), `ChapterHeading`,
`Appearance`, `ChangePassword`. **No cyber/terminal theme — fully migrated 2026-05-26.**

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
```
LLM model/provider and LDAP are also configurable from the UI (Settings).
