#!/bin/bash
# Bundled-image entrypoint. Ensures app dirs exist (volumes may be empty on
# first run), fixes permissions, then hands off to supervisord which manages
# postgres + uvicorn together.
set -e

# App dirs — created/owned correctly so volume mounts work on first boot
mkdir -p /app/data /app/uploads /app/outputs
chown -R root:root /app

# Postgres data dir — owned by postgres user (volume may be fresh)
mkdir -p "$PGDATA"
chown -R postgres:postgres "$PGDATA"
chmod 0700 "$PGDATA"

echo "[entrypoint] starting supervisord (postgres + rtm-app)"
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/rtm.conf
