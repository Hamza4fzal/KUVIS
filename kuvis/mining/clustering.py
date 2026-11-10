"""K-means and DBSCAN with the evaluation the methodology requires.

K-means: elbow (inertia), silhouette, Davies–Bouldin, Calinski–Harabasz over a K range; cluster
profiles in original units and z-scores; descriptive names generated *from the centroid z-scores*
(so a name like "high LST · low NDVI" is a summary of the numbers, not an assumption).

DBSCAN: parameter grid (eps × min_samples) reporting clusters, noise share, size distribution and
silhouette on non-noise points; k-distance curve to justify eps.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler


def scale(df: pd.DataFrame) -> tuple[np.ndarray, StandardScaler]:
    sc = StandardScaler()
    return sc.fit_transform(df.values), sc


def kmeans_sweep(X: np.ndarray, k_range=(2, 10), random_state=42, sil_sample=6000) -> pd.DataFrame:
    rows = []
    for k in range(k_range[0], k_range[1] + 1):
        km = KMeans(n_clusters=k, n_init=20, random_state=random_state).fit(X)
        lab = km.labels_
        rows.append({
            "k": k,
            "inertia": km.inertia_,
            "silhouette": silhouette_score(X, lab, sample_size=min(sil_sample, len(X)), random_state=random_state),
            "davies_bouldin": davies_bouldin_score(X, lab),
            "calinski_harabasz": calinski_harabasz_score(X, lab),
            "min_cluster_share": np.bincount(lab).min() / len(lab),
        })
    df = pd.DataFrame(rows)
    # Elbow: point of maximum distance from the line joining the first and last inertia values.
    x, y = df["k"].values.astype(float), df["inertia"].values
    xn, yn = (x - x[0]) / (x[-1] - x[0]), (y - y[-1]) / (y[0] - y[-1])
    df["elbow_distance"] = np.abs(yn - (1 - xn)) / np.sqrt(2)
    return df


def choose_k(sweep: pd.DataFrame, min_k: int = 3, min_share: float = 0.02) -> tuple[int, str]:
    """Pick K by best silhouette among K ≥ min_k with no degenerate (<2 %) cluster; report the rule used."""
    cand = sweep[(sweep.k >= min_k) & (sweep.min_cluster_share >= min_share)]
    if cand.empty:
        cand = sweep[sweep.k >= min_k]
    best = cand.sort_values(["silhouette", "davies_bouldin"], ascending=[False, True]).iloc[0]
    elbow = int(sweep.loc[sweep.elbow_distance.idxmax(), "k"])
    rule = (f"K={int(best.k)}: highest silhouette ({best.silhouette:.3f}) among K≥{min_k} without clusters "
            f"<{min_share:.0%} of cells; elbow heuristic suggests K={elbow}")
    return int(best.k), rule


def fit_kmeans(X: np.ndarray, k: int, random_state=42) -> KMeans:
    return KMeans(n_clusters=k, n_init=50, random_state=random_state).fit(X)


def profile(df: pd.DataFrame, labels: np.ndarray, features: list[str], nice: dict[str, str] | None = None,
            z_thresh: float = 0.5) -> pd.DataFrame:
    """Per-cluster size, mean (original units) and z-score vs. all cells; plus an auto-generated name."""
    nice = nice or {}
    mu, sd = df[features].mean(), df[features].std(ddof=0)
    rows = []
    for c in sorted(set(labels)):
        m = labels == c
        means = df.loc[m, features].mean()
        z = (means - mu) / sd
        parts = []
        for f in z.abs().sort_values(ascending=False).index[:3]:
            if abs(z[f]) >= z_thresh:
                parts.append(f"{'high' if z[f] > 0 else 'low'} {nice.get(f, f)}")
        name = " · ".join(parts) if parts else "near city-wide average"
        rows.append({"cluster": int(c), "n_cells": int(m.sum()), "share": float(m.mean()), "name": name,
                     **{f"mean_{f}": float(means[f]) for f in features}, **{f"z_{f}": float(z[f]) for f in features}})
    return pd.DataFrame(rows)


def k_distance(X: np.ndarray, k: int) -> np.ndarray:
    nn = NearestNeighbors(n_neighbors=k + 1).fit(X)
    d, _ = nn.kneighbors(X)
    return np.sort(d[:, -1])


def knee(values: np.ndarray) -> float:
    """Knee of a sorted ascending curve (max distance to the chord)."""
    y = values
    x = np.linspace(0, 1, len(y))
    yn = (y - y[0]) / (y[-1] - y[0] + 1e-12)
    return float(y[np.argmax(x - yn)])


def dbscan_grid(X: np.ndarray, eps_list, min_samples_list, sil_sample=5000, random_state=42) -> pd.DataFrame:
    rows = []
    for eps in eps_list:
        for ms in min_samples_list:
            lab = DBSCAN(eps=eps, min_samples=ms).fit_predict(X)
            core = lab >= 0
            ncl = len(set(lab[core]))
            sizes = np.bincount(lab[core]) if core.any() else np.array([])
            sil = np.nan
            if ncl >= 2 and core.sum() > ncl:
                sil = silhouette_score(X[core], lab[core], sample_size=min(sil_sample, int(core.sum())),
                                       random_state=random_state)
            rows.append({"eps": eps, "min_samples": ms, "n_clusters": ncl, "noise_share": float((~core).mean()),
                         "largest_cluster_share": float(sizes.max() / len(lab)) if len(sizes) else np.nan,
                         "median_cluster_size": float(np.median(sizes)) if len(sizes) else np.nan,
                         "silhouette_non_noise": sil})
    return pd.DataFrame(rows)


def fit_dbscan(X: np.ndarray, eps: float, min_samples: int) -> np.ndarray:
    return DBSCAN(eps=eps, min_samples=min_samples).fit_predict(X)
