"""Spatial statistics: Global Moran's I, Local Getis–Ord Gi* (permutation inference), spatial blocks."""

from __future__ import annotations

import numpy as np
import pandas as pd
from esda.getisord import G_Local
from esda.moran import Moran
from libpysal.weights import DistanceBand


def weights(x: np.ndarray, y: np.ndarray, threshold: float, star: bool = False) -> DistanceBand:
    w = DistanceBand(np.c_[x, y], threshold=threshold, binary=True, silence_warnings=True)
    w.transform = "r"
    return w


def moran(values: np.ndarray, w, permutations: int = 999, seed: int = 42) -> dict:
    np.random.seed(seed)
    m = Moran(values, w, permutations=permutations)
    return {"I": m.I, "expected_I": m.EI, "z_norm": m.z_norm, "p_norm": m.p_norm, "p_sim": m.p_sim}


def gi_star(values: np.ndarray, x: np.ndarray, y: np.ndarray, threshold: float, permutations: int = 999,
            seed: int = 42, alpha: float = 0.05) -> pd.DataFrame:
    w = DistanceBand(np.c_[x, y], threshold=threshold, binary=True, silence_warnings=True)
    g = G_Local(values, w, star=True, permutations=permutations, seed=seed, transform="B",
                alternative="two-sided", keep_simulations=False, n_jobs=1)
    cls = np.where(g.p_sim < alpha, np.where(g.Zs > 0, "hot", "cold"), "not significant")
    # Bonferroni-free but report FDR-adjusted significance too (Benjamini–Hochberg on pseudo p-values)
    p = g.p_sim
    order = np.argsort(p)
    ranks = np.empty_like(order)
    ranks[order] = np.arange(1, len(p) + 1)
    q = np.minimum.accumulate((p[order] * len(p) / np.arange(1, len(p) + 1))[::-1])[::-1]
    q_full = np.empty_like(p, dtype=float)
    q_full[order] = np.minimum(q, 1.0)
    cls_fdr = np.where(q_full < alpha, np.where(g.Zs > 0, "hot", "cold"), "not significant")
    return pd.DataFrame({"gi_z": g.Zs, "gi_p": g.p_sim, "gi_q_fdr": q_full, "gi_class": cls, "gi_class_fdr": cls_fdr})


def spatial_blocks(x: np.ndarray, y: np.ndarray, block_m: float) -> np.ndarray:
    """Integer block id for spatially blocked cross-validation (square blocks of side block_m)."""
    bx = np.floor((x - x.min()) / block_m).astype(int)
    by = np.floor((y - y.min()) / block_m).astype(int)
    return bx * 10_000 + by
