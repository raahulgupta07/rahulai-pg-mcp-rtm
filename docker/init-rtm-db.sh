#!/bin/bash
# Runs once on first boot of the pgvector image (Postgres entrypoint convention).
# Postgres + the rtm DB/user already exist via POSTGRES_USER/POSTGRES_DB env vars.
# This script only needs to enable pgvector — the app creates its own tables.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "[init-rtm] pgvector extension enabled in $POSTGRES_DB"
