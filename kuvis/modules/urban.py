"""Module C — Urbanization and Land-use Intelligence.

C1 Land-use change: EO4SD 2005→2017 transition matrices (exact polygon areas) and cell-level built-up change.
C2 K-means development trajectories on Landsat 2001→2024 change vectors and population growth.
C3 Temporal analysis: per-cell Theil–Sen NDVI trend across all available epochs with Kendall's τ.
C4 Contextual Isolation Forest: changes that are unusual relative to cells that started in a similar state.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, theilslopes
from sklearn.preprocessing import StandardScaler

from ..config import cfg, get_logger, path
from ..mining import anomaly, clustering, experiment
from .common import features, out, relabel_by

log = get_logger("kuvis.urban")
KM_FEATS = ["ndvi_change_2001_2024", "ndbi_change_2001_2024", "lst_rel_change_2001_2024", "pop_growth_log", "built_frac"]
NICE = {"ndvi_change_2001_2024": "NDVI change", "ndbi_change_2001_2024": "NDBI change",
        "lst_rel_change_2001_2024": "relative-heat change", "pop_growth_log": "population growth", "built_frac": "built-up (2021)"}


def run() -> pd.DataFrame:
    mc = cfg()["mining"]
    rs = mc["random_state"]
    df = features()
    df["pop_growth_log"] = np.log1p(df["pop_2025"].clip(lower=0)) - np.log1p(df["pop_2015"].clip(lower=0))
    b = df[df.is_land_cell & (df.frac_inside >= 0.5)].copy()
    res = pd.DataFrame({"grid_id": b["grid_id"].values}, index=b.index)

    # ---------------- C1 transitions
    trans = {}
    for prod in ("hr", "vhr"):
        p = path("processed", "mining", f"lulc_transitions_{prod}.parquet")
        if p.exists():
            t = pd.read_parquet(p)
            tot0 = t.groupby("from_name")["km2"].sum()
            tot1 = t.groupby("to_name")["km2"].sum()
            changed = t[t["from"] != t["to"]].sort_values("km2", ascending=False)
            trans[prod] = {"matrix": t.to_dict("records"), "area_2005_km2": tot0.to_dict(), "area_2017_km2": tot1.to_dict(),
                           "net_change_km2": (tot1.reindex(tot0.index.union(tot1.index), fill_value=0)
                                              - tot0.reindex(tot0.index.union(tot1.index), fill_value=0)).to_dict(),
                           "top_transitions": changed.head(10).to_dict("records"),
                           "unchanged_share": float(t.loc[t["from"] == t["to"], "km2"].sum() / t["km2"].sum())}
    if trans:
        cc = b["lulc_built_change_2005_2017"] if "lulc_built_change_2005_2017" in b else pd.Series(dtype=float)
        experiment.save("urban_lulc_change", module="urban", algorithm="Land-use change detection (transition matrix)",
                        purpose="Quantify 2005→2017 land-use transitions from the World Bank EO4SD maps",
                        inputs=["EO4SD HR C_L2", "EO4SD VHR C_L3"], n_samples=int(cc.notna().sum()),
                        params={"method": "intersection of 2005 and 2017 polygons, exact area in UTM 42N",
                                "cell_change_rule": "only where both years cover ≥ 50 % of the cell"},
                        metrics={"cells_with_change_estimate": int(cc.notna().sum()),
                                 "mean_cell_built_change": float(cc.mean()) if cc.notna().any() else None,
                                 "cells_built_gain_gt_25pct": int((cc > 0.25).sum())},
                        results=trans,
                        limitations=["Polygon boundaries of the two years were mapped independently; slivers inflate "
                                     "small transitions.", "Covers only the EO4SD mapped extents."])

    # ---------------- C2 K-means trajectories
    kb = b.dropna(subset=KM_FEATS)
    if len(kb) > 100:
        X = StandardScaler().fit_transform(kb[KM_FEATS].values)
        sweep = clustering.kmeans_sweep(X, tuple(mc["kmeans"]["k_range"]), rs)
        k, rule = clustering.choose_k(sweep)
        lab = relabel_by(clustering.fit_kmeans(X, k, rs).labels_, kb["ndvi_change_2001_2024"])
        res.loc[kb.index, "urban_kmeans"] = lab
        prof = clustering.profile(kb, lab, KM_FEATS, NICE)
        prof.to_parquet(out("urban_kmeans_profiles.parquet"))
        experiment.save("urban_kmeans", module="urban", algorithm="K-means",
                        purpose="Group cells by their 2001→2024 development trajectory", inputs=KM_FEATS, n_samples=len(kb),
                        params={"k": k, "selection": rule, "pop_growth_log": "ln(1+pop2025) − ln(1+pop2015) (WorldPop)"},
                        metrics={"sweep": sweep.to_dict("records"), "chosen": sweep[sweep.k == k].iloc[0].to_dict()},
                        results={"profiles": prof.to_dict("records")},
                        interpretation_notes=["Cluster 0 = strongest mean vegetation loss."],
                        limitations=["Landsat 5 TM vs 8/9 OLI sensor differences add small offsets to index changes.",
                                     "Population growth 2015–2025 is modelled, and covers a different period than the "
                                     "Landsat change."])

    # ---------------- C3 temporal NDVI trend
    epochs = [int(e) for e in cfg()["landsat"]["epochs"]]
    cols = [f"ls_ndvi_{e}" for e in epochs if f"ls_ndvi_{e}" in b]
    yrs = np.array([int(c[-4:]) for c in cols])
    if len(cols) >= 4:
        V = b[cols].values
        slope, tau_p = np.full(len(b), np.nan), np.full(len(b), np.nan)
        for i in range(len(b)):
            ok = np.isfinite(V[i])
            if ok.sum() >= 4:
                slope[i] = theilslopes(V[i, ok], yrs[ok])[0] * 10
                tau_p[i] = kendalltau(yrs[ok], V[i, ok]).pvalue
        res["ndvi_trend_decade"], res["ndvi_trend_p"] = slope, tau_p
        city = b[cols].median()
        experiment.save("urban_ndvi_trend", module="urban", algorithm="Theil–Sen trend + Kendall τ (per cell)",
                        purpose="Long-term vegetation trend across Landsat epochs", inputs=cols, n_samples=int(np.isfinite(slope).sum()),
                        params={"epochs": yrs.tolist(), "min_epochs": 4},
                        metrics={"city_median_ndvi_by_epoch": dict(zip(map(str, yrs), city.values)),
                                 "share_decreasing_p05": float(np.mean((slope < 0) & (tau_p < 0.05))),
                                 "share_increasing_p05": float(np.mean((slope > 0) & (tau_p < 0.05))),
                                 "median_trend_per_decade": float(np.nanmedian(slope))},
                        limitations=["With ≤ 5 epochs, Kendall's τ has little power: p < 0.05 needs a near-monotonic "
                                     "series.", "Epoch composites differ in scene count and weather."])
    else:
        log.info("NDVI trend skipped: only %d Landsat epochs available", len(cols))

    # ---------------- C4 contextual anomaly of change
    ab = b.dropna(subset=["ndvi_change_2001_2024", "ndbi_change_2001_2024", "lst_rel_change_2001_2024", "ls_ndvi_2001"])
    if len(ab) > 200:
        start = pd.qcut(ab["ls_ndvi_2001"], 10, labels=False, duplicates="drop").astype(str) + "_" + \
                pd.cut(ab["built_frac"].fillna(0), [-0.01, 0.2, 0.5, 1.01], labels=["low", "mid", "high"]).astype(str)
        ctx = pd.DataFrame({"chg_ndvi": anomaly.robust_z(ab["ndvi_change_2001_2024"], start),
                            "chg_ndbi": anomaly.robust_z(ab["ndbi_change_2001_2024"], start),
                            "chg_lst_rel": anomaly.robust_z(ab["lst_rel_change_2001_2024"], start)}, index=ab.index)
        Xa = StandardScaler().fit_transform(ctx.values)
        ic = mc["isolation_forest"]
        score, flag = anomaly.isolation_forest(Xa, ic["contamination"], ic["n_estimators"], rs)
        lscore, lflag = anomaly.lof(Xa, ic["contamination"])
        direction = np.where(ctx["chg_ndvi"] < 0, "unusual vegetation loss", "unusual vegetation gain")
        for c in ctx:
            res.loc[ab.index, c] = ctx[c]
        res["chg_if_score"], res["chg_if_flag"], res["chg_lof_flag"], res["chg_direction"] = np.nan, False, False, None
        res.loc[ab.index, "chg_if_score"] = score
        res.loc[ab.index, "chg_if_flag"] = flag
        res.loc[ab.index, "chg_lof_flag"] = lflag
        res.loc[ab.index, "chg_direction"] = direction
        experiment.save("urban_isolation_forest", module="urban", algorithm="Isolation Forest (+ LOF comparison)",
                        purpose="Find cells whose 2001→2024 change is unusual relative to cells with a similar 2001 state",
                        inputs=list(ctx.columns), n_samples=len(ab),
                        params={**ic, "context": "robust z within groups of 2001-NDVI decile × 2021 built-up band"},
                        metrics={"n_flagged": int(flag.sum()), "n_down": int(((direction == "unusual vegetation loss") & flag).sum()),
                                 "n_up": int(((direction == "unusual vegetation gain") & flag).sum()),
                                 "if_vs_lof": anomaly.agreement(flag, lflag)},
                        limitations=["Unusual change is statistical; it may reflect construction, reservoir level, "
                                     "irrigation, or sensor/compositing differences."])
    res.to_parquet(out("urban_cells.parquet"))
    log.info("urban module done")
    return res
