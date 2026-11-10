"""Connection pool and small query helpers. Credentials come only from environment/.env."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

ROOT = Path(__file__).resolve().parents[3]


def _env() -> None:
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_env()
DSN = (f"host={os.getenv('KUVIS_DB_HOST', 'localhost')} port={os.getenv('KUVIS_DB_PORT', '5433')} "
       f"dbname={os.getenv('KUVIS_DB_NAME', 'kuvis')} user={os.getenv('KUVIS_DB_USER', 'kuvis')} "
       f"password={os.getenv('KUVIS_DB_PASSWORD', '')} options='-c search_path=kuvis,public'")
CORS_ORIGINS = [o.strip() for o in os.getenv("KUVIS_API_CORS_ORIGINS", "http://localhost:5173").split(",")]

pool = ConnectionPool(DSN, min_size=1, max_size=8, kwargs={"row_factory": dict_row}, open=False)


def fetch_all(sql: str, params: Any = None) -> list[dict]:
    with pool.connection() as c:
        return list(c.execute(sql, params))


def fetch_one(sql: str, params: Any = None) -> dict | None:
    with pool.connection() as c:
        return c.execute(sql, params).fetchone()


def fetch_val(sql: str, params: Any = None):
    with pool.connection() as c:
        r = c.execute(sql, params).fetchone()
        return None if r is None else next(iter(r.values()))
