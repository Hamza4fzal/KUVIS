"""Dataset provenance registry.

Every acquisition step records what it fetched, from where, when, and whether it succeeded.
The registry (datasets/metadata/registry.json) is the machine-readable source for the
Data Sources page and the `data_sources` database table. Nothing is marked acquired unless
the file actually exists on disk.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ROOT, path

REGISTRY = path("metadata", "registry.json")

VALID_STATUS = {
    "acquired",
    "requires_authentication",
    "requires_manual_request",
    "requires_payment",
    "unavailable",
    "alternative_selected",
    "failed",
}


def sha256(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        while b := fh.read(chunk):
            h.update(b)
    return h.hexdigest()


def _load() -> dict[str, Any]:
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {}


def record(
    key: str,
    *,
    status: str,
    title: str,
    provider: str,
    url: str,
    method: str,
    files: list[Path] | None = None,
    **meta: Any,
) -> dict[str, Any]:
    if status not in VALID_STATUS:
        raise ValueError(f"invalid status {status!r}")
    files = files or []
    missing = [str(f) for f in files if not Path(f).exists()]
    if status == "acquired" and (missing or not files):
        raise RuntimeError(f"{key}: refusing to mark acquired; missing files {missing or '(none given)'}")
    entry = {
        "key": key,
        "title": title,
        "provider": provider,
        "url": url,
        "method": method,
        "status": status,
        "accessed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": [
            {
                "path": str(Path(f).resolve().relative_to(ROOT)).replace("\\", "/"),
                "bytes": Path(f).stat().st_size,
                "sha256": sha256(Path(f)) if Path(f).stat().st_size < 2_000_000_000 else None,
            }
            for f in files
            if Path(f).exists()
        ],
        **meta,
    }
    reg = _load()
    reg[key] = entry
    REGISTRY.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")
    return entry


def get(key: str) -> dict[str, Any] | None:
    return _load().get(key)


def all_entries() -> dict[str, Any]:
    return _load()
