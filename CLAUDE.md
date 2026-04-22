# MCP Agent — P&G Route-to-Market Outlet Classification

## Stack
- **Frontend**: SvelteKit 5 + Tailwind CSS 4 (brutalist command center UI)
- **Backend**: FastAPI (Python)
- **Database**: SQLite (`data/rtm.db`)
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
```

## Default Login
- **admin** / admin123 (full access + user management)
- **user** / user123 (classify + view only)

## Project Structure

```
PG-MCP-RTM/
├── backend/
│   ├── main.py              # FastAPI app (API routes + static serving)
│   ├── auth.py              # JWT auth (HS256, JSON user store)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app.css           # Brutalist design system (Space Grotesk, ink borders, stamp shadows)
│   │   ├── lib/
│   │   │   ├── api.ts        # API client (classify, jobs, settings, users, rtm-data)
│   │   │   ├── types.ts      # TypeScript interfaces
│   │   │   ├── colors.ts     # Color constants
│   │   │   ├── stores/
│   │   │   │   └── auth.svelte.ts  # Auth store (JWT + localStorage)
│   │   │   └── components/
│   │   │       ├── Header.svelte       # Nav bar with button-style links
│   │   │       ├── Footer.svelte       # Status bar (SYS_OK, PIPELINE, MODEL)
│   │   │       ├── KpiCard.svelte      # Metric card (tag-label + large value)
│   │   │       ├── DataTable.svelte    # Sortable table with dark-bar title
│   │   │       ├── Badge.svelte        # Classification/growth/risk badges
│   │   │       └── ChapterHeading.svelte  # Section header with amber icon
│   │   └── routes/
│   │       ├── +layout.svelte          # Auth guard + header/footer
│   │       ├── +page.svelte            # Classify (upload + pipeline + results dashboard)
│   │       ├── login/+page.svelte      # Brutalist login portal
│   │       ├── history/+page.svelte    # Past jobs table (click → view results)
│   │       ├── rtm/+page.svelte        # RTM Data explorer (filters + export)
│   │       ├── docs/+page.svelte       # Documentation (6 tabbed sections)
│   │       └── users/+page.svelte      # Settings (Users tab + Model & Config tab)
│   └── package.json
├── src/                      # Python classification engine
│   ├── rtm_classifier.py     # Pareto 80/15/5 per branch
│   ├── database.py           # SQLite (jobs, job_results, job_insights)
│   ├── job_manager.py        # Job tracking + multi-sheet Excel export
│   ├── ai_service.py         # AI insights (rule-based + Gemini LLM)
│   └── column_mapper.py      # Column name utilities
├── data/                     # SQLite DB + sample data + settings.json + users.json
├── .env                      # OPENROUTER_API_KEY, LLM_MODEL
└── outputs/                  # Generated Excel reports
```

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Classify | Upload CSV, run pipeline with live CLI terminal, view results |
| `/history` | History | All past jobs, click to reload full results |
| `/rtm` | RTM Data | Filterable outlet table (branch, class, search) + export |
| `/docs` | Docs | 6-tab reference (Rules, Input File, Algorithm, Pipeline, Thresholds, AI Fields) |
| `/users` | Settings | Users tab (CRUD) + Model & Config tab (LLM, thresholds, status) |
| `/login` | Login | Brutalist access portal |

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/login` | No | Login → JWT token |
| GET | `/api/auth/me` | Yes | Current user info |
| POST | `/api/classify` | Yes | Upload CSV → run pipeline → return full results |
| GET | `/api/jobs` | Yes | List all jobs |
| GET | `/api/jobs/{id}` | Yes | Job details + results + insights |
| GET | `/api/jobs/{id}/export` | Yes | Download Excel report |
| GET | `/api/rtm-data` | Yes | All outlet data (filterable by job_id) |
| GET | `/api/settings` | Yes | System config (model, thresholds, status) |
| POST | `/api/settings` | Admin | Save threshold defaults |
| GET | `/api/users` | Admin | List users |
| POST | `/api/users` | Admin | Create user |
| DELETE | `/api/users/{id}` | Admin | Delete user |
| GET | `/api/health` | No | System status |

## Classification Logic

Single CSV → Pareto 80/15/5 per BranchName:
- **Class A**: Top 80% cumulative revenue (per branch)
- **Class B**: Next 15% (80-95%)
- **Class C**: Bottom 5% (>95%)
- **F4**: Wholesalers (>=3 cartons/brand/month of Local products)

## Pipeline Steps
1. Validate (columns, dates, branches)
2. Aggregate (GROUP BY BranchName + Cus.Code)
3. Period Sales (2Yr, 12M, 6M, 3M breakdowns)
4. Averages (monthly averages per period)
5. Contributions (% of branch total)
6. Wholesaler Detection (Local products, carton threshold)
7. Pareto Classification (per branch, cumulative %)
8. Frequency (purchase days, regularity)
9. AI Enrichment (growth signal, risk level, visit priority, action)
10. AI Insights (executive summary, class recs, growth analysis via LLM)

## Dashboard Features
- 6 KPI cards (outlets, A/B/C counts, wholesalers, revenue)
- Branch filter dropdown
- Collapsible pipeline log (CLI terminal with colored output)
- Data Quality Report (warnings for missing fields)
- Classification Summary table
- Top 10 Outlets table
- Branch Matrix (outlets/revenue/class split per branch)
- Pareto Curve (SVG with 80/95% threshold lines)
- Branch Revenue Comparison (horizontal bars)
- Period Comparison (2Yr/12M/6M/3M bars)
- Trend Comparison (growth % per branch, color-coded)
- Channel Breakdown (by GroupName)
- Risk Heatmap (branch × risk level matrix)
- AI Executive Summary (markdown rendered)
- AI Class A/B/C Recommendations
- Export: Full Excel, Full CSV, Filtered CSV

## Design System
Brutalist Command Center:
- Font: Space Grotesk (weight 900 for headings)
- Colors: #feffd6 (surface), #383832 (dark), #007518 (green), #00fc40 (CTA), #ff9d00 (warning), #be2d06 (error), #006f7c (teal), #9d4867 (mauve)
- Zero border-radius, ink borders (2px/4px asymmetric), stamp shadows (4px 4px 0px)
- ALL CAPS labels, monospace data, button-style tabs and nav

## Environment Variables
```
OPENROUTER_API_KEY=sk-or-v1-...    # For AI insights (optional)
LLM_MODEL=google/gemini-3.1-flash-lite-preview
LLM_BASE_URL=https://openrouter.ai/api/v1
JWT_SECRET_KEY=your-secret-here     # For auth (optional, has default)
```
