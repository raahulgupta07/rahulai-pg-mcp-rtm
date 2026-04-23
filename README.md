# MCP Agent — P&G Route-to-Market Outlet Classification

Intelligent outlet classification system using the **Pareto 80/15/5 Rule**, partitioned by branch. Built for P&G Myanmar market data.

## Features

- **Pareto Classification** — 11,000+ outlets into Class A (80%), B (15%), C (5%) per branch
- **F4/F2 Visit Frequency** — Class A = F4 (high priority), Class B/C = F2 (standard)
- **9-Branch Partitioning** — Each branch is its own Pareto universe
- **AI Enrichment** — Growth signals, risk levels, visit priority, action recommendations
- **LLM Insights** — Executive summary + class recommendations via Gemini
- **Live Pipeline Terminal** — Real-time CLI output during processing
- **Job Comparison** — Side-by-side stats, outlet movement tracker (upgrades/downgrades)
- **Coverage Gap Analysis** — Township breakdown with STRONG/MODERATE/WEAK/GAP status
- **RTM Data Explorer** — Full outlet table with filters + CSV/Excel export
- **Seller Workload** — Route outlet counts vs targets (YGN: 25-30, Regional: 30-35)
- **Beautified Excel** — 15-sheet report with color-coded headers, classifications, risk levels
- **Audit Log** — Tracks all user actions (login, classify, export, user management)
- **File Validation** — Checks required columns before running pipeline
- **Job History** — Every run saved and replayable with full results
- **User Management** — JWT auth, admin/viewer roles, admin creates users via UI
- **Brutalist UI** — Command center design with Space Grotesk, ink borders, stamp shadows

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | SvelteKit 5, Tailwind CSS 4, TypeScript |
| Backend | FastAPI (Python) |
| Database | SQLite |
| AI | Google Gemini 3.1 Flash Lite via OpenRouter |
| Auth | JWT (HS256) |
| Deploy | Docker + docker-compose |

## Quick Start

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# Frontend (new terminal)
cd frontend && npm install && npm run dev
```

**Production (single port):**
```bash
cd frontend && npm run build
cd ../backend && uvicorn main:app --port 8001
# Everything on http://localhost:8001
```

**Docker:**
```bash
docker compose up -d
# http://localhost:8001
```

## Default Credentials

| User | Password | Role |
|------|----------|------|
| admin | admin123 | Admin (configurable via .env) |

All other users created by admin via Settings > Users tab.

## Pages

| Page | Route | Description |
|------|-------|-------------|
| **Classify** | `/` | Upload CSV, run pipeline with live terminal, view results |
| **History** | `/history` | Past jobs, click to reload full results |
| **RTM Data** | `/rtm` | Filter and export outlet data (branch, class, search) |
| **Compare** | `/compare` | Select 2 jobs, see upgrades/downgrades/new/lost outlets |
| **Coverage** | `/coverage` | Township gap analysis with coverage status |
| **Docs** | `/docs` | Classification rules, input format, algorithm (6 tabs) |
| **Settings** | `/users` | Users + Model Config + Audit Log (admin only) |

## Input File

Single CSV with required columns:

| Column | Description |
|--------|-------------|
| `Cus.Code` | Customer/outlet ID |
| `Cus.Name` | Customer name |
| `TotalAmount` | Sales amount per transaction |
| `TotalPcs` | Quantity sold |
| `BranchName` | Branch (partition key) |
| `Item Class` | Nutrition, Food, Non Food |
| `NumInBuy` | Units per carton |

Optional: `DocDate`, `InvoiceNo`, `BrandName`, `Item Type`, `Channel`, `RouteCode`

## Classification Rules

| Class | Rule | Visit Freq | Revenue Share |
|-------|------|-----------|--------------|
| **A** | Cumulative % <= 80% | F4 (high) | ~80% |
| **B** | 80% < Cumulative % <= 95% | F2 (standard) | ~15% |
| **C** | Cumulative % > 95% | F2 (standard) | ~5% |
| **F4** | >= 3 cartons/brand/month (Local) | F4 | Override to A |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/classify` | POST | Upload CSV + run pipeline |
| `/api/jobs` | GET | List all jobs |
| `/api/jobs/{id}` | GET | Job details + results + insights |
| `/api/jobs/{id}/export` | GET | Download beautified Excel |
| `/api/rtm-data` | GET | Outlet data (filterable) |
| `/api/compare` | GET | Compare 2 jobs side-by-side |
| `/api/coverage` | GET | Township coverage analysis |
| `/api/settings` | GET/POST | Config + thresholds |
| `/api/users` | GET/POST/DELETE | User management |
| `/api/audit` | GET | Audit log (admin) |
| `/api/auth/login` | POST | JWT login |
| `/api/health` | GET | System status |

## Environment Variables

```env
OPENROUTER_API_KEY=sk-or-v1-...
LLM_MODEL=google/gemini-3.1-flash-lite-preview
LLM_BASE_URL=https://openrouter.ai/api/v1
JWT_SECRET_KEY=change-in-production
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
ADMIN_DISPLAY_NAME=Administrator
```

## Data Persistence

These files are local-only (never pushed to git):
- `data/rtm.db` — All jobs, results, insights, audit log
- `data/users.json` — User accounts
- `data/settings.json` — Threshold defaults
- `outputs/*.xlsx` — Excel reports
- `.env` — API keys + credentials

Updates via `git pull` won't affect existing data.

## License

City Holdings Myanmar — City AI Team
