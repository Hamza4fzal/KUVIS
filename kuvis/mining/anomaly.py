"""Contextual anomaly detection: Isolation Forest (primary) and Local Outlier Factor (comparison).

An anomaly is a statistically unusual observation relative to its context — not an emergency.
Contexts are built explicitly (same land-cover class, spatial neighbours, own history) so that a
cell is unusual *for what it is and where it is*, rather than simply hot in absolute terms.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor


def robust_z(x: pd.Series, groups: pd.Series | None = None) -> pd.Series:
    """(x − median) / (1.4826·MAD), optionally within groups."""
    def _z(s):
        med = s.median()
        mad = (s - med).abs().median() * 1.4826
        return (s - med) / (mad if mad > 0 else s.std(ddof=0) or 1.0)
    if groups is None:
        return _z(x)
    return x.groupby(groups, group_keys=False).apply(_z)


def neighbour_residual(x: np.ndarray, y: np.ndarray, values: np.ndarray, radius: float) -> np.ndarray:
    """value − mean of valid neighbours within `radius` (excluding self)."""
    tree = cKDTree(np.c_[x, y])
    out = np.full(len(values), np.nan)
    for i, nb in enumerate(tree.query_ball_point(np.c_[x, y], r=radius)):
        nb = [j for j in nb if j != i and np.isfinite(values[j])]
        if nb and np.isfinite(values[i]):
            out[i] = values[i] - values[nb].mean()
    return out


def isolation_forest(X: np.ndarray, contamination: float, n_estimators: int, random_state: int):
    m = IsolationForest(n_estimators=n_estimators, contamination=contamination, random_state=random_state).fit(X)
    score = -m.score_samples(X)  # higher = more anomalous
    return score, m.predict(X) == -1


def lof(X: np.ndarray, contamination: float, n_neighbors: int = 35):
    m = LocalOutlierFactor(n_neighbors=n_neighbors, contamination=contamination)
    flag = m.fit_predict(X) == -1
    return -m.negative_outlier_factor_, flag


def agreement(a: np.ndarray, b: np.ndarray) -> dict:
    inter, union = int((a & b).sum()), int((a | b).sum())
    return {"n_a": int(a.sum()), "n_b": int(b.sum()), "n_both": inter, "jaccard": inter / union if union else np.nan}
