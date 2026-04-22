# MCP Agent — P&G Route-to-Market Outlet Classification

Intelligent outlet classification system using the **Pareto 80/15/5 Rule**, partitioned by branch. Built for P&G Myanmar market data.

## Features

- **Pareto Classification** — Classifies 11,000+ outlets into Class A (80%), B (15%), C (5%) per branch
- **9-Branch Partitioning** — Each branch is its own universe with independent Pareto ranking
- **AI Enrichment** — Growth signals, risk levels, visit priority, action recommendations per outlet
- **LLM Insights** — Executive summary, class recommendations, growth analysis via Gemini
- **Live Pipeline Terminal** — Real-time CLI-style output showing each processing step
- **Rich Analytics** — Pareto curve, branch comparison, trend analysis, risk heatmap, channel breakdown
- **RTM Data Explorer** — Full outlet table with filters (branch, class, search) and CSV/Excel export
- **Job History** — Every classification run saved and replayable
- **User Management** — JWT auth with admin/viewer roles
- **Brutalist UI** — Command center design with Space Grotesk, ink borders, stamp shadows

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | SvelteKit 5, Tailwind CSS 4, TypeScript |
| Backend | FastAPI (Python) |
| Database | SQLite |
| AI | Google Gemini 3.1 Flash Lite via OpenRouter |
| Auth | JWT (HS256) |

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

**Production (single port):**
```bash
cd frontend && npm run build
cd ../backend && uvicorn main:app --port 8001
# Everything on http://localhost:8001
```

## Default Credentials

| User | Password | Role |
|------|----------|------|
| admin | admin123 | Admin |
| user | user123 | Viewer |

## Pages

| Page | Description |
|------|-------------|
| **Classify** | Upload CSV, run pipeline with live terminal, view results |
| **History** | Past jobs, click to reload full results |
| **RTM Data** | Filter and export outlet data |
| **Docs** | Classification rules, input format, algorithm |
| **Settings** | User management + model config + thresholds |

## Input File

Single CSV with required columns: `Cus.Code`, `Cus.Name`, `TotalAmount`, `TotalPcs`, `BranchName`, `Item Class`, `NumInBuy`

## Classification Rules

| Class | Rule | Revenue Share |
|-------|------|--------------|
| **A** | Cumulative % <= 80% | ~80% |
| **B** | 80% < Cumulative % <= 95% | ~15% |
| **C** | Cumulative % > 95% | ~5% |
| **F4** | >= 3 cartons/brand/month (Local) | Override to A |

## Environment Variables

```env
OPENROUTER_API_KEY=sk-or-v1-...
LLM_MODEL=google/gemini-3.1-flash-lite-preview
```

## License

City Holdings Myanmar — City AI Team
