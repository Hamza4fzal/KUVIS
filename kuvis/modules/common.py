"""Helpers shared by the analytical modules."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import path


def features() -> pd.DataFrame:
    return pd.read_parquet(path("processed", "cell_features.parquet"))


def out(name: str):
    return path("processed", "mining", name)


def pct_rank(s: pd.Series) -> pd.Series:
    """Percentile rank in [0, 1]; NaN stays NaN."""
    return s.rank(pct=True, method="average")


def relabel_by(labels: np.ndarray, values: pd.Series) -> np.ndarray:
    """Renumber cluster labels so cluster 0 has the lowest mean `values` (stable, readable ordering).
    Negative labels (DBSCAN noise) are kept."""
    labs = pd.Series(labels, index=values.index)
    order = values.groupby(labs[labs >= 0]).mean().sort_values().index.tolist()
    m = {old: new for new, old in enumerate(order)}
    return np.array([m.get(lbl, lbl) for lbl in labels])
