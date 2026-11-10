"""Configuration and path resolution. All modules read parameters from config/kuvis.yaml."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "kuvis.yaml"


@lru_cache(maxsize=1)
def cfg() -> dict[str, Any]:
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def path(kind: str, *parts: str) -> Path:
    """Resolve a data path, e.g. path('raw', 'boundaries') -> datasets/raw/boundaries."""
    base = ROOT / cfg()["paths"][kind]
    p = base.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def projected_crs() -> str:
    return cfg()["crs"]["projected"]


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        log_dir = ROOT / "datasets" / "metadata" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        fh = logging.FileHandler(log_dir / "pipeline.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(sh)
        logger.addHandler(fh)
        logger.setLevel(logging.INFO)
    return logger
