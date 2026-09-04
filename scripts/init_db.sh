#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source .venv/bin/activate

psql postgres -tAc "SELECT 1 FROM pg_database WHERE datname='truth_db'" | grep -q 1 || psql postgres -c "CREATE DATABASE truth_db;"
psql postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='truth_user'" | grep -q 1 || psql postgres -c "CREATE USER truth_user WITH PASSWORD 'truth_pass';"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE truth_db TO truth_user;"
psql truth_db -c "GRANT ALL ON SCHEMA public TO truth_user;"

alembic upgrade head
echo "Database ready."
