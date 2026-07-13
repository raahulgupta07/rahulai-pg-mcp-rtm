# Install & Upgrade — RTM Agent

Two paths:

- **[Fresh install](#fresh-install)** — no existing deployment
- **[Upgrade](#upgrade-an-existing-deployment)** — an instance is already running; keep its data

Both assume Docker + Docker Compose on the host.

---

## Requirements

| | Minimum | Why |
|---|---|---|
| RAM | **4 GB** | A 113 MB / 743k-row Excel peaks at **1.3 GB** in `pd.read_excel` alone; the full pipeline (classify + AI + export) lands at 2–3 GB. A 2 GB host gets OOM-killed mid-run **with no error in the UI** — the process is simply gone. |
| vCPU | 2 | Excel build is CPU-bound (~11s on 11.6k outlets). |
| Disk | 20 GB + | Uploads and generated workbooks. |
| Replicas | **1** | See [Scaling limits](#scaling-limits). Running 2+ breaks auth and downloads. |

---

## Fresh install

```bash
git clone git@github.com:raahulgupta07/rahulai-pg-mcp-rtm.git
cd rahulai-pg-mcp-rtm
cp .env.example .env
```

### 1. Edit `.env`

```env
OPENROUTER_API_KEY=sk-or-v1-...      # optional — omit and AI falls back to rule-based
ADMIN_PASSWORD=<pick a real password> # ← CHANGE THIS. See note below.
RTM_HOST_PORT=8011                    # host port, if 8011 is taken
```

**Leave `JWT_SECRET_KEY` commented out.** The app generates a strong random key on
first boot and persists it to `data/.jwt_secret` (gitignored, `0600`, survives
restarts, shared by all 4 uvicorn workers). Only set it explicitly if you manage
secrets elsewhere — see [Scaling limits](#scaling-limits).

> **`ADMIN_PASSWORD` is only read on first boot**, when `data/users.json` doesn't
> exist yet. Change it *before* the first `up`, or you'll have to reset the password
> from the UI afterwards. The default in `.env.example` is `admin123` — do not ship that.

### 2. Start

```bash
docker compose up -d --build          # → http://localhost:8011
```

Single-container variant (Postgres bundled in the same image):

```bash
docker compose -f docker-compose.bundled.yml up -d --build
```

### 3. Verify

```bash
curl -s localhost:8011/api/health      # {"status":"ok", ...}
docker compose logs -f mcp-agent | grep -i "jwt\|error"
```

You should see `[auth] generated a new JWT signing key -> /app/data/.jwt_secret`
exactly once. If you don't, `JWT_SECRET_KEY` is set somewhere and is overriding it.

Log in at `http://<host>:8011` with `ADMIN_USERNAME` / `ADMIN_PASSWORD`.

---

## Upgrade an existing deployment

**Data is preserved.** No manual migration is needed:

- New DB tables are created with `CREATE TABLE IF NOT EXISTS` inside `_init_database()`,
  which runs on every boot.
- New rule-config keys are deep-merged over your saved `rule_config.json` by
  `merge_rules()`, so a config predating the `lifecycle` section still works.
- `users.json`, `groups.json`, job history and rule history are untouched.

### 1. Back up first

```bash
# Postgres (jobs, results, audit log, rule history)
docker compose exec -T postgres pg_dump -U rtm rtm | gzip > ~/rtm-backup-$(date +%F).sql.gz

# Config + accounts
tar czf ~/rtm-data-$(date +%F).tar.gz data/
```

### 2. Rotate the JWT key (one-time, important)

If your `.env` predates this release it almost certainly contains:

```
JWT_SECRET_KEY=rtm-command-center-secret-change-in-prod
```

That value is **published in the git history** — anyone who can read the repo can
forge a `super_admin` token. An explicit env var takes precedence over the
auto-generated key, so upgrading does **not** fix this by itself. Comment it out:

```bash
sed -i.bak 's/^JWT_SECRET_KEY=/#JWT_SECRET_KEY=/' .env
rm .env.bak      # the backup contains your API key — don't leave it in the repo dir
```

### 3. Pull and recreate

```bash
git pull origin main
docker compose up -d --build --force-recreate
```

> **`--force-recreate`, not `restart`.** Environment variables are baked into a
> container at *creation*. A restart keeps the old `JWT_SECRET_KEY`; only a recreate
> drops it and lets the app generate a new one.

Rotating the key **invalidates every existing session** — all users, including you,
are logged out once. That is the fix landing, not a failure.

### 4. Verify

```bash
docker compose logs mcp-agent | grep "generated a new JWT signing key"   # should appear once
curl -s localhost:8011/api/health
```

### 5. Re-run one classification

`Lifecycle_Stage` is written into `job_results` **at classify time**. Jobs classified
before this release carry the old, broken cohorts (the "Reactivated" bug labelled
~73% of outlets). Existing jobs are **not** retroactively fixed — re-upload the source
file to get correct cohorts.

---

## Scaling limits

**This release is single-instance.** Run exactly **one** replica.

Everything except job data lives on container-local disk:

```
/app/uploads          staged files
/app/outputs          generated workbooks
data/users.json       accounts + groups
data/.jwt_secret      the signing key
```

With 2+ replicas behind a load balancer:

- **Uploads fail** — the file is staged on pod A; `classify-async` is routed to pod B → `404 upload_id not found`.
- **Exports fail** — the workbook is built on pod A; the download hits pod B → `410`. The progress bar reaches 100%, *then* the download dies.
- **Random 401s** — each pod generates its own `.jwt_secret`, so a token signed by one pod is rejected by the others.
- **Users diverge** — `users.json` is per-pod; an account created on A doesn't exist on B.

If you must scale out, at minimum:

1. Set `JWT_SECRET_KEY` from a secret manager (AWS Secrets Manager / SSM) so every replica shares one key.
2. Move `/app/uploads` and `/app/outputs` to S3 or a shared RWX volume.
3. Move `users.json` / `groups.json` into Postgres.
4. Lower the DB pool: each worker opens up to 32 connections (**4 workers × 32 = 128 per pod**), and Postgres allows 200 — **two pods exhaust it**. Use pgbouncer, or drop `max_size`.
5. Add a job queue. `classify-async` and `export-async` run as `asyncio.create_task` **inside the web process**; if the pod is killed (deploy, autoscale, spot reclaim) the job is lost and its row stays `processing` forever.

---

## Security checklist before exposing this publicly

Not yet fixed in this release — safe on an internal network, **not** on the open internet:

- [ ] Change `ADMIN_PASSWORD` (default is `admin123`)
- [ ] Passwords are hashed with **unsalted SHA-256** — no bcrypt/argon2
- [ ] OIDC `id_token` is decoded but **not signature-verified** (no `iss`/`aud`/`exp` check)
- [ ] `CORS allow_origins=["*"]` is unconditional
- [ ] `users.json` is written without a file lock — 4 workers can race and lose writes
- [ ] The legacy sync `GET /api/jobs/{id}/export` has **no ownership check** — any authenticated user can export any job
- [ ] Put TLS in front (nginx / ALB); the app serves plain HTTP

---

## Troubleshooting

**Classification dies with no error, container restarts**
OOM. Give the host ≥4 GB. Check with `docker stats` during a run.

**Everyone logged out after a deploy**
Expected once, if you rotated the JWT key. If it happens on *every* deploy, `data/`
isn't on a persistent volume, so `.jwt_secret` is regenerated each time.

**`Export file has expired — rebuild it`**
The workbook was built by a different replica than the one serving the download.
You're running more than one replica — don't.

**Excel preview shows "could not read this file"**
Workbooks whose uncompressed sheet XML exceeds ~512 MB can't be parsed in a browser
(V8 string limit). The app falls back to a server-side preview automatically; if that
also fails, the file is likely corrupt.

**Upgrade didn't generate a new JWT key**
`JWT_SECRET_KEY` is still set in `.env` (or in the container env). Comment it out and
`--force-recreate`.
