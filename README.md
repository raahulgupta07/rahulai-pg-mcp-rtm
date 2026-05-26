# RTM Agent — P&G Route-to-Market Outlet Classification

Intelligent outlet classification using the **Pareto 80/15/5 rule**, partitioned per branch.
Built for P&G Myanmar market data — 11,000+ outlets, 9 branches.

## Features

- **Pareto Classification** — outlets graded Class A / B / C per branch, each branch its own universe
- **Configurable Rule Engine** — every threshold, the wholesaler rule, category overrides,
  AI behaviour — all tuned from the UI (`/rules`), versioned with one-click rollback
- **AI Enrichment** — growth signal, risk level, visit priority, per-outlet actions + LLM insights
- **LLM Cost Tracking** — real OpenRouter token + USD cost captured per job
- **Run Comparison** — every run compared to the previous: class counts, revenue, channels,
  branches, outlet movement — on screen and in Excel
- **Platform Analytics** — 8-tab dashboard: usage, trends, per-user activity, audit explorer,
  jobs, cost, security
- **Roles + Groups + Permissions** — 3 roles, plus admin-defined groups granting extra access
- **LDAP / Active Directory** — up to 5 servers, per-user home server, email auto-merge,
  group-membership sync
- **Job Sharing** — share a specific job with specific users
- **Beautified Excel** — multi-sheet report incl. run-info stamp + comparison sheets
- **Coverage Gap Analysis** — township breakdown
- **Claude.ai-style Design** — flat zero-radius, Inter font, cream `#FAF9F5` / terracotta `#C96442` token system, light/dark/auto, 6 palettes + custom accent (per-user)
- **Audit Log** — every action tracked, incl. failed logins
- **Account management** — password change/reset, disable, LDAP merge

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | SvelteKit 5, Tailwind CSS 4, TypeScript |
| Backend | FastAPI (Python) |
| Database | PostgreSQL 18 + pgvector (psycopg3 pool) |
| AI | Google Gemini 3.1 Flash Lite via OpenRouter (optional) |
| Auth | JWT (HS256) + LDAP / Active Directory |
| Deploy | Docker + docker-compose (app + Postgres) |

## Quick Start

**Docker (recommended — runs Postgres + app):**
```bash
docker compose up -d --build
# → http://localhost:8011
```

**Local dev** (needs a Postgres at `DATABASE_URL`):
```bash
cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8001
cd frontend && npm install && npm run dev
```

## Default Credentials

| User | Password | Role |
|------|----------|------|
| admin | admin123 | super_admin (configurable via `.env`) |

Other users created by super_admin in Settings ▸ Users, or auto-provisioned via LDAP.

## Access Model

| Role | Access |
|------|--------|
| `super_admin` | Everything — Settings, Analytics, LDAP, model config, users, groups |
| `admin` | Classify, data pages, Rules |
| `user` | Classify, view own/shared data |

**Groups** grant extra permissions (`rules`, `analytics`) on top of any role —
effective access = role base ∪ groups. Groups can map to LDAP groups for auto-sync.

## Pages

| Page | Route | Access |
|------|-------|--------|
| Classify | `/` | all |
| History | `/history` | all (own + shared jobs) |
| RTM Data | `/rtm` | all |
| Compare | `/compare` | all |
| Coverage | `/coverage` | all |
| Docs | `/docs` | all |
| Rules | `/rules` | `rules` permission |
| Analytics | `/analytics` | `analytics` permission |
| Settings | `/users` | super_admin |

## Input File

Single CSV. Required columns:

| Column | Description |
|--------|-------------|
| `Cus.Code` | Customer / outlet ID |
| `Cus.Name` | Customer name |
| `TotalAmount` | Sales amount per transaction |
| `TotalPcs` | Quantity sold |
| `BranchName` | Branch (partition key) |
| `Item Type` | Local or Import |
| `Item Class` | Nutrition, Food, Non Food |
| `NumInBuy` | Units per carton |

Optional: `DocDate`, `InvoiceNo`, `BrandName`, `Outlet Channel`, `Channel`, `GroupName`, `RouteCode`

## Classification Rules

Defaults — all configurable on the **Rules** page, version-tracked with rollback:

| Class | Rule | Visit Freq |
|-------|------|-----------|
| **A** | cumulative % ≤ 80% | F4 |
| **B** | 80% < cumulative % ≤ 95% | F2 |
| **C** | cumulative % > 95% | F2 |
| **F4** | ≥ 3 cartons/brand/month (Local) | F4 — override to A |

## Configuration — all from the UI

- **Rules** (`/rules`) — Pareto cutoffs, wholesaler, category override, workload, growth, risk, AI
- **Model & provider** (Settings ▸ Model & Config) — LLM model + base URL, with a Test button
- **LDAP** (Settings ▸ LDAP) — up to 5 directory servers, per-server Test
- **Groups** (Settings ▸ Groups) — define groups, grant permissions, map to LDAP groups
- **Appearance** — theme, palette, density (per-user)

## Design System

**Claude.ai-style, flat** (zero border-radius). CSS variables only — no hardcoded colors.

| Token | Light | Dark |
|-------|-------|------|
| `--bg` | `#FAF9F5` cream | `#1F1E1B` |
| `--accent` | `#C96442` terracotta | `#E89070` |
| `--text` | `#2C2B26` | `#EDEAE0` |
| Font | Inter (system fallback) | same |
| Radius | `0` everywhere | same |

**Components:** `KpiCard`, `DataTable`, `Badge` (A/B/C/F4 solid + soft), `ChapterHeading`, `Appearance` modal (6 palettes + density + accent picker), `ChangePassword` modal.

**Shell:** desktop left sidebar + mobile bottom nav (`+layout.svelte:422`).

## Scalability

PostgreSQL + connection pool; heavy work (classify, Excel) offloaded to a worker-thread
pool so the async event loop never blocks — handles ~100 concurrent users.

## Environment Variables

```env
DATABASE_URL=postgresql://rtm:rtm@postgres:5432/rtm
OPENROUTER_API_KEY=sk-or-v1-...
LLM_MODEL=google/gemini-3.1-flash-lite-preview
LLM_BASE_URL=https://openrouter.ai/api/v1
JWT_SECRET_KEY=change-in-production
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
ADMIN_DISPLAY_NAME=Administrator
```

## Data Persistence

- **PostgreSQL** (`pgdata` volume) — jobs, results, insights, audit log, rule history, job shares
- `data/users.json` — user accounts + group membership
- `data/groups.json` — groups & permissions
- `data/settings.json` — system settings + LLM provider
- `data/rule_config.json` — active classification rules
- `data/ldap_config.json` — LDAP servers
- `outputs/*.xlsx` — Excel reports
- `.env` — keys + credentials

## License

City Holdings Myanmar — City AI Team
