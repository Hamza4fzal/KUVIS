"""Minimal ordered SQL migrations: applies infrastructure/database/migrations/NNN_*.sql once each."""

from __future__ import annotations

from ..config import ROOT, get_logger
from .conn import connect

log = get_logger("kuvis.migrate")
MIG_DIR = ROOT / "infrastructure" / "database" / "migrations"


def run() -> list[str]:
    applied = []
    with connect(autocommit=True) as c:
        c.execute("CREATE SCHEMA IF NOT EXISTS kuvis")
        c.execute("CREATE TABLE IF NOT EXISTS kuvis.schema_migrations (name text PRIMARY KEY, applied_utc timestamptz DEFAULT now())")
        done = {r[0] for r in c.execute("SELECT name FROM kuvis.schema_migrations")}
        for f in sorted(MIG_DIR.glob("*.sql")):
            if f.name in done:
                continue
            with c.transaction():
                c.execute(f.read_text(encoding="utf-8"))
                c.execute("INSERT INTO kuvis.schema_migrations(name) VALUES (%s)", (f.name,))
            log.info("applied migration %s", f.name)
            applied.append(f.name)
    return applied


if __name__ == "__main__":
    print(run())
