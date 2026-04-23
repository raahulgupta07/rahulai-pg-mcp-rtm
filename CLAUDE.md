# MCP Agent — P&G Route-to-Market Outlet Classification

## Stack
- **Frontend**: SvelteKit 5 + Tailwind CSS 4 (brutalist command center UI)
- **Backend**: FastAPI (Python)
- **Database**: SQLite (`data/rtm.db`) — tables: jobs, job_results, job_insights, audit_log
- **AI**: Google Gemini 3.1 Flash Lite via OpenRouter (optional)

## Running

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# Frontend (dev mode)
cd frontend && npm install && npm run dev

# Production (single port)
cd frontend && npm run build
cd ../backend && uvicorn main:app --port 8001
# Open http://localhost:8001

# Docker
docker compose up -d
```

## Default Login
- **admin** / admin123 (configured via .env, full access)
- Other users created by admin via Settings > Users tab

## Project Structure

```
PG-MCP-RTM/
├── backend/
│   ├── main.py              # FastAPI app (API routes + static serving)
│   ├── auth.py              # JWT auth (HS256, JSON user store)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app.css           # Brutalist design system
│   │   ├── lib/
│   │   │   ├── api.ts        # API client
│   │   │   ├── types.ts      # TypeScript interfaces
│   │   │   ├── colors.ts     # Color constants
│   │   │   ├── stores/
│   │   │   │   └── auth.svelte.ts  # Auth store (JWT + localStorage)
│   │   │   └── components/
│   │   │       ├── Header.svelte       # Nav bar with button-style links
│   │   │       ├── Footer.svelte       # Dynamic status bar (auto-refresh 30s)
│   │   │       ├── KpiCard.svelte      # Metric card
│   │   │       ├── DataTable.svelte    # Sortable table
│   │   │       ├── Badge.svelte        # Classification/growth/risk badges
│   │   │       └── ChapterHeading.svelte  # Section header
│   │   └── routes/
│   │       ├── +layout.svelte          # Auth guard + header/footer
│   │       ├── +page.svelte            # Classify (upload + pipeline + results)
│   │       ├── login/+page.svelte      # Login portal
│   │       ├── history/+page.svelte    # Past jobs (click → view results)
│   │       ├── rtm/+page.svelte        # RTM Data explorer (filters + export)
│   │       ├── compare/+page.svelte    # Job comparison + outlet movement
│   │       ├── coverage/+page.svelte   # Coverage gap analysis (township)
│   │       ├── docs/+page.svelte       # Documentation (6 tabs)
│   │       └── users/+page.svelte      # Settings (Users + Config + Audit Log)
│   └── package.json
├── src/                      # Python classification engine
│   ├── rtm_classifier.py     # Pareto 80/15/5 per branch + F4/F2 + workload
│   ├── database.py           # SQLite (jobs, job_results, job_insights, audit_log)
│   ├── job_manager.py        # Job tracking + beautified Excel export
│   ├── ai_service.py         # AI insights (rule-based + Gemini LLM)
│   └── column_mapper.py      # Column name utilities
├── data/                     # SQLite DB + sample data + settings.json + users.json
├── .env                      # API keys + admin credentials
├── .env.example              # Template for env setup
├── Dockerfile                # Multi-stage build (Node + Python)
├── docker-compose.yml        # Single-command deployment
└── outputs/                  # Generated Excel reports
```

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Classify | Upload CSV, run pipeline with live CLI terminal, view results |
| `/history` | History | All past jobs, click to reload full results |
| `/rtm` | RTM Data | Filterable outlet table (branch, class, search) + export |
| `/compare` | Compare | Select 2 jobs, side-by-side stats, outlet movement tracker |
| `/coverage` | Coverage | Township gap analysis (STRONG/MODERATE/WEAK/GAP) |
| `/docs` | Docs | 6-tab reference (Rules, Input, Algorithm, Pipeline, Thresholds, AI) |
| `/users` | Settings | Users tab + Model & Config tab + Audit Log tab |
| `/login` | Login | Brutalist access portal |

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/login` | No | Login → JWT token |
| GET | `/api/auth/me` | Yes | Current user info |
| POST | `/api/classify` | Yes | Upload CSV → validate → run pipeline → return results |
| GET | `/api/jobs` | Yes | List all jobs |
| GET | `/api/jobs/{id}` | Yes | Job details + results + insights |
| GET | `/api/jobs/{id}/export` | Yes | Download beautified Excel report |
| GET | `/api/rtm-data` | Yes | All outlet data (filterable by job_id) |
| GET | `/api/compare` | Yes | Compare 2 jobs (movements, upgrades, downgrades) |
| GET | `/api/coverage` | Yes | Outlet geo data + township breakdown |
| GET | `/api/settings` | Yes | System config (model, thresholds, status) |
| POST | `/api/settings` | Admin | Save threshold defaults |
| GET | `/api/users` | Admin | List users |
| POST | `/api/users` | Admin | Create user |
| DELETE | `/api/users/{id}` | Admin | Delete user |
| GET | `/api/audit` | Admin | Audit log (last 200 actions) |
| GET | `/api/health` | No | System status (jobs, last run, model) |

## Classification Logic

Single CSV → Pareto 80/15/5 per BranchName:
- **Class A (F4)**: Top 80% cumulative revenue — high priority visits
- **Class B (F2)**: Next 15% (80-95%) — standard frequency
- **Class C (F2)**: Bottom 5% (>95%) — standard frequency
- **F4 Wholesaler**: >=3 cartons/brand/month of Local products → override to Class A

## Pipeline Steps
1. **Validate** — columns, dates, branches (with backend validation before start)
2. **Aggregate** — GROUP BY BranchName + Cus.Code
3. **Period Sales** — 2Yr, 12M, 6M, 3M breakdowns by category
4. **Averages** — monthly averages per period
5. **Contributions** — % of branch total
6. **Wholesaler Detection** — Local products, carton threshold
7. **Pareto Classification** — per branch, cumulative %, F4/F2 tiers
8. **Frequency** — purchase days, regularity
9. **Seller Workload** — route outlet counts vs targets (YGN: 25-30, Regional: 30-35)
10. **AI Enrichment** — growth signal, risk level, visit priority, action, LLM insights

## Dashboard Features
- 6 KPI cards (outlets, A/B/C, wholesalers, revenue)
- Branch filter (persists in localStorage)
- Collapsible pipeline log (real CLI terminal output)
- Data Quality Report (warnings for missing fields)
- Classification Summary + Top 10 + Branch Matrix
- Pareto Curve (SVG), Channel Breakdown, Period Comparison
- Trend Comparison (growth % per branch, color-coded)
- Risk Heatmap (branch × risk matrix)
- Seller Workload table (route status: OK/BELOW/ABOVE)
- AI Executive Summary + Class A/B/C Recommendations
- Export: Full Excel (beautified), Full CSV, Filtered CSV

## Excel Export (Beautified)
15 sheets with professional formatting:
- Dark header rows, color-coded Classification/Growth/Risk/Workload
- Alternating row colors, auto-filters, frozen panes, auto-fit columns
- Per-branch sheets, Top 50, AI Action Plan, Seller Workload

## Audit Log
Tracks all user actions: LOGIN, CLASSIFY, EXPORT, CREATE_USER, DELETE_USER, SETTINGS. Viewable in Settings > Audit Log tab (admin only).

## Design System
Brutalist Command Center:
- Font: Space Grotesk (weight 900 for headings)
- Colors: #feffd6 (surface), #383832 (dark), #007518 (green), #00fc40 (CTA), #ff9d00 (warning), #be2d06 (error), #006f7c (teal), #9d4867 (mauve)
- Zero border-radius, ink borders (2px/4px), stamp shadows (4px 4px 0px)
- ALL CAPS labels, monospace data, button-style tabs and nav
- Loading skeletons with pulse animation

## Environment Variables
```
OPENROUTER_API_KEY=sk-or-v1-...     # AI insights (optional)
LLM_MODEL=google/gemini-3.1-flash-lite-preview
LLM_BASE_URL=https://openrouter.ai/api/v1
JWT_SECRET_KEY=your-secret-here
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
ADMIN_DISPLAY_NAME=Administrator
```
