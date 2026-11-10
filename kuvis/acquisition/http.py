"""Small, polite HTTP download helper with resume-safe atomic writes."""

from __future__ import annotations

import time
from pathlib import Path

import requests

from ..config import get_logger

log = get_logger("kuvis.http")
UA = "KUVIS-research-pipeline/0.1 (academic data-mining project)"


def download(url: str, dest: Path, *, overwrite: bool = False, retries: int = 4, timeout: int = 300) -> Path:
    """Download `url` to `dest`. Original files are never overwritten unless asked."""
    if dest.exists() and dest.stat().st_size > 0 and not overwrite:
        log.info("exists, skipping: %s", dest.name)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": UA}) as r:
                r.raise_for_status()
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
            tmp.replace(dest)
            log.info("downloaded %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
            return dest
        except requests.RequestException as exc:
            log.warning("attempt %d/%d failed for %s: %s", attempt, retries, url, exc)
            time.sleep(5 * attempt)
    raise RuntimeError(f"download failed after {retries} attempts: {url}")
