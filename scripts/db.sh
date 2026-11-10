#!/usr/bin/env bash
# Start / stop / status of the portable PostgreSQL cluster used in development.
# PG_HOME defaults to ../_tools/pgsql next to the repository; data dir ../_tools/pgdata.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="${KUVIS_TOOLS:-$ROOT/../_tools}"
PG="$TOOLS/pgsql/bin"
DATA="$TOOLS/pgdata"
PORT="$(grep -E '^KUVIS_DB_PORT=' "$ROOT/.env" 2>/dev/null | cut -d= -f2 || echo 5433)"
case "${1:-status}" in
  start)  "$PG/pg_ctl" -D "$DATA" -l "$TOOLS/pg.log" -o "-p ${PORT:-5433}" start ;;
  stop)   "$PG/pg_ctl" -D "$DATA" stop ;;
  status) "$PG/pg_isready" -p "${PORT:-5433}" ;;
  *) echo "usage: $0 start|stop|status"; exit 2 ;;
esac
