"""Database connection from environment variables (.env at repo root)."""

from __future__ import annotations

import os

import psycopg

from ..config import ROOT


def _load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def dsn() -> str:
    _load_env()
    e = os.environ
    return (f"host={e.get('KUVIS_DB_HOST', 'localhost')} port={e.get('KUVIS_DB_PORT', '5433')} "
            f"dbname={e.get('KUVIS_DB_NAME', 'kuvis')} user={e.get('KUVIS_DB_USER', 'kuvis')} "
            f"password={e.get('KUVIS_DB_PASSWORD', '')}")


def connect(**kw) -> psycopg.Connection:
    return psycopg.connect(dsn(), **kw)
