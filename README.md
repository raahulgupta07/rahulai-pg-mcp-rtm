# RTM Agent — P&G Route-to-Market Outlet Classification

Intelligent outlet classification using the **Pareto 80/15/5 rule**, partitioned per branch.
Built for P&G Myanmar market data — 11,000+ outlets, 9 branches.

## Features

- **Pareto Classification** — outlets graded Class A / B / C per branch, each branch its own universe
- **F4 Distributor as first-class** — wholesalers (≥N cartons/brand/month Local) forced-A, broken out across UI: own KPI card, own summary row, own RTM Data filter, own map color, own Excel row, own deep-dive dashboard with health score + churn-risk follow-up list
- **Outlet Lifecycle Cohorts** — every outlet stamped New / Active / Reactivated / Dormant / Lost from DocDate
- **Configurable Rule Engine** — every threshold, the F4 rule, category overrides,
  AI behaviour — all tuned from the UI (`/rules`), versioned with one-click rollback
- **2-Stage Upload** — file lands on app disk first (XHR with live % progress, up to 2 GB), DB write only after classification completes
- **CSV Preview** — client-side parse of first 8 MB on file pick: row/branch/outlet counts, sample table, column-match chips (required/optional), branch distribution bars
- **Parallel AI Pipeline** — 3 macro insight calls + chunked per-outlet enrichment run concurrently (asyncio.gather + Semaphore), ~3-4x faster than serial
- **AI Enrichment** — growth signal, risk level, visit priority, per-outlet actions + LLM insights (chunked, top-N)
- **LLM Cost Tracking** — real OpenRouter token + USD cost captured per job
- **Run Comparison** — every run compared to the previous: class counts, revenue, channels,
  branches, outlet movement — on screen and in Excel
- **Platform Analytics** — 8-tab dashboard: usage, trends, per-user activity, audit explorer,
  jobs, cost, security
- **Roles + Groups + Permissions** — 3 roles, plus admin-defined groups granting extra access
- **LDAP / Active Directory** — up to 5 servers, per-user home server, email auto-merge,
  group-membership sync
- **Job Sharing** — share a specific job with specific users
- **Beautified Excel** — multi-sheet report incl. run-info stamp + comparison sheets + Class A (total) rollup row
- **Coverage Gap Analysis** — township breakdown + Leaflet map with class-coloured outlet markers (F4 own teal color, contact/phone/address in popup)
- **Full-width Layout** — every page uses full content width; sidebar + content shell only
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

### Option 1 — Bundled single image (Open WebUI-style — one container)
Postgres + pgvector + app all in one image. No compose needed.

```bash
docker build -f Dockerfile.bundled -t rahulai/rtm:bundled .
docker run -d --name rtm \
  -p 8011:8001 \
  -v rtmdb:/var/lib/postgresql/data \
  -v rtm-data:/app/data \
  -v rtm-uploads:/app/uploads \
  -v rtm-outputs:/app/outputs \
  -e ADMIN_PASSWORD=changeme \
  -e OPENROUTER_API_KEY=sk-or-v1-... \
  rahulai/rtm:bundled
# → http://localhost:8011
```

Or with compose (same image, just managed volumes):
```bash
docker compose -f docker-compose.bundled.yml up -d --build
```

Image ~1.1 GB. Internally `supervisord` runs Postgres + uvicorn together.
Data persists in named volumes — restart-safe.

### Option 2 — Multi-container (production)
Separate Postgres + app containers. Easier to scale or upgrade independently.

```bash
docker compose up -d --build
# → http://localhost:8011
```

### Option 3 — Local dev
Needs a Postgres reachable at `DATABASE_URL`.
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
| **Pure Class A** | cumulative % ≤ 80% (revenue rank) | F4 |
| **Class A (category)** | ≥ 80% of any Item Class within branch | F4 |
| **F4 Distributor** | ≥ N cartons/brand/month (Local), default N=3 — forced-A | F4 |
| **Class B** | 80% < cumulative % ≤ 95% | F2 |
| **Class C** | cumulative % > 95% | F2 |

> **Class A (total)** = Pure A + F4 Distributor + Class A (category). All three
> sub-types are visible on the dashboard, Excel summary, and RTM Data filter.

### Outlet Lifecycle (cohort stage from DocDate)
| Stage | Definition |
|-------|-----------|
| New | First purchase < 3M ago |
| Active | Bought in last 3M |
| Reactivated | Returned after >6M gap |
| Dormant | Last buy 3–12M ago |
| Lost | Last buy > 12M ago |

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

### Bundled image (default — single container)
- **4 uvicorn workers** (override: `-e UVICORN_WORKERS=8`)
- Postgres tuned: `shared_buffers=512MB`, `work_mem=32MB`, `max_connections=200`
- ~100 req/s throughput · ~400 concurrent users · ~1.6 GB peak RAM
- Recommend 4 GB host RAM, 2+ vCPU

### Multi-container (production)
- Same tuning, independently scaled Postgres + app
- Each uvicorn worker has its own 32-conn psycopg pool (4 workers × 32 = 128 max)
- Heavy work (classify pipeline, Excel build) offloaded via `run_in_threadpool` —
  async event loop never blocks
- AI pipeline parallel + chunked (asyncio.gather + Semaphore) — 3–4x speedup
  vs serial

### Scaling path
Bundled → Multi-container (separate PG) → K8s + managed PG + pgbouncer + HPA.
Volume migrates straight across — same Postgres data dir.

### Trade-off summary

| | Bundled | Multi-container | K8s + managed PG |
|---|---|---|---|
| Users | ~400 | ~1k | unbounded |
| Image | ~1.1 GB | 400 + 350 MB | same |
| Horizontal scale app | ✗ | partial | ✓ HPA |
| HA / PG replica | ✗ | ✗ | ✓ |
| Upgrade PG only | ✗ | ✓ | ✓ |
| One-command deploy | ✓ | ✗ | ✗ |

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
