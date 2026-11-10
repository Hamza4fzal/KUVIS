"""Experiment records: every algorithm run writes its inputs, parameters and metrics to JSON.

These files (research/experiments/*.json) are the single source for experiment documentation, the
`mining_experiments` / `model_evaluation_metrics` tables and the Methodology page. Metrics are
whatever the code computed — nothing is typed in by hand.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from typing import Any

import numpy as np

from ..config import ROOT

EXP_DIR = ROOT / "research" / "experiments"
EXP_DIR.mkdir(parents=True, exist_ok=True)


def _git_rev() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return None


def _clean(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return None if not np.isfinite(f) else round(f, 6)
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def save(exp_id: str, *, module: str, algorithm: str, purpose: str, inputs: list[str], n_samples: int,
         params: dict, metrics: dict, results: dict | None = None, interpretation_notes: list[str] | None = None,
         limitations: list[str] | None = None) -> dict:
    rec = {
        "experiment_id": exp_id,
        "module": module,
        "algorithm": algorithm,
        "purpose": purpose,
        "input_features": inputs,
        "n_samples": n_samples,
        "parameters": params,
        "metrics": metrics,
        "results": results or {},
        "interpretation_notes": interpretation_notes or [],
        "limitations": limitations or [],
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_version": _git_rev(),
    }
    rec = _clean(rec)
    (EXP_DIR / f"{exp_id}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    return rec


def load_all() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(EXP_DIR.glob("*.json"))]
