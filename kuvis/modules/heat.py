"""Module B — Urban Heat Intelligence.

B1  K-means thermal–environmental profiles (LST, NDVI, NDBI, built-up share, population density).
B2  DBSCAN: (a) feature-space clusters; (b) geographic concentrations of hot cells; compared with
    Getis–Ord Gi* hot spots and with K-means.
B3  Contextual Isolation Forest on LST residuals vs land-cover peers, spatial neighbours and the
    cell's own history; Local Outlier Factor for comparison; persistence check across single dates.
B4  Correlation / standardized regression of LST on vegetation, built-up, population, coast, terrain.
B5  Historical thermal comparison across Landsat epochs.

All statements use land surface temperature (LST), which is not air temperature.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import spearmanr
from sklearn.metrics import adjusted_rand_score
from sklearn.preprocessing import StandardScaler

from ..config import cfg, get_logger, path
from ..mining import anomaly, clustering, experiment, spatial
from .common import features, out, relabel_by

log = get_logger("kuvis.heat")

EPOCH = "2024"
KM_FEATS = ["lst_mean_2024", "s2_ndvi_mean", "s2_ndbi_mean", "built_frac", "log_pop_density_2025"]
NICE = {"lst_mean_2024": "LST", "s2_ndvi_mean": "NDVI", "s2_ndbi_mean": "NDBI", "built_frac": "built-up",
        "log_pop_density_2025": "population density"}


def _base(df: pd.DataFrame) -> pd.DataFrame:
    m = df["is_land_cell"] & (df[f"lst_cov_{EPOCH}"] >= 0.5)
    for f in KM_FEATS:
        m &= df[f].notna()
    return df[m].copy()


def _subdiv(df) -> dict:
    """Top subdivisions of a cell group as JSON text + the leading name (Parquet would unify dict keys across rows)."""
    import json as _json
    vc = df.subdivision.dropna().astype(object).value_counts().head(3)
    return {"subdivisions_json": _json.dumps({str(k): int(v) for k, v in vc.items()}),
            "top_subdivision": str(vc.index[0]) if len(vc) else None}


def run() -> pd.DataFrame:
    mc = cfg()["mining"]
    rs = mc["random_state"]
    df = features()
    b = _base(df)
    log.info("heat: %d analysable land cells (of %d)", len(b), len(df))
    res = pd.DataFrame({"grid_id": b["grid_id"].values}, index=b.index)

    # ---------------------------------------------------------------- B1 K-means
    X = StandardScaler().fit_transform(b[KM_FEATS].values)
    sweep = clustering.kmeans_sweep(X, tuple(mc["kmeans"]["k_range"]), rs)
    k, rule = clustering.choose_k(sweep)
    km = clustering.fit_kmeans(X, k, rs)
    lab = relabel_by(km.labels_, b["lst_mean_2024"])
    res["heat_kmeans"] = lab
    prof = clustering.profile(b, lab, KM_FEATS, NICE)
    prof.to_parquet(out("heat_kmeans_profiles.parquet"))
    sweep.to_parquet(out("heat_kmeans_sweep.parquet"))
    experiment.save("heat_kmeans", module="heat", algorithm="K-means",
                    purpose="Identify thermal–environmental profiles of land cells",
                    inputs=KM_FEATS, n_samples=len(b), params={"k": k, "selection": rule, "n_init": 50, "scaling": "z-score"},
                    metrics={"sweep": sweep.to_dict("records"),
                             "chosen": sweep[sweep.k == k].iloc[0].to_dict()},
                    results={"profiles": prof.to_dict("records")},
                    interpretation_notes=["Cluster names are generated from centroid z-scores (|z| ≥ 0.5), "
                                          "ordered so cluster 0 has the lowest mean LST."],
                    limitations=["K-means assumes roughly spherical clusters in standardized space.",
                                 "LST composite is daytime (~10:30 local) Apr–Jun."])
    log.info("heat k-means: %s", rule)

    # ---------------------------------------------------------------- B2a DBSCAN in feature space
    ms = 10
    kd = clustering.k_distance(X, ms)
    eps_knee = clustering.knee(kd)
    eps_list = sorted({round(eps_knee * f, 3) for f in (0.6, 0.8, 1.0, 1.25, 1.5)})
    grid_feat = clustering.dbscan_grid(X, eps_list, mc["dbscan"]["min_samples_grid"], random_state=rs)
    lab_f = clustering.fit_dbscan(X, eps_knee, ms)
    res["heat_dbscan_feature"] = lab_f
    nonnoise = lab_f >= 0
    ari = adjusted_rand_score(lab[nonnoise], lab_f[nonnoise]) if nonnoise.sum() > 10 else np.nan
    experiment.save("heat_dbscan_feature", module="heat", algorithm="DBSCAN (feature space)",
                    purpose="Density-based thermal profiles without fixing K; compare with K-means",
                    inputs=KM_FEATS, n_samples=len(b),
                    params={"eps": eps_knee, "min_samples": ms, "metric": "euclidean on z-scores",
                            "eps_rule": f"knee of sorted {ms}-NN distance curve"},
                    metrics={"n_clusters": int(len(set(lab_f[nonnoise]))), "noise_share": float((~nonnoise).mean()),
                             "ari_vs_kmeans_non_noise": ari, "parameter_grid": grid_feat.to_dict("records")},
                    limitations=["A single global eps cannot adapt to varying density; most cells may form one "
                                 "large dense cluster with the unusual cells as noise."])

    # ---------------------------------------------------------------- Gi* + Moran
    xy = b[["x_utm", "y_utm"]].values
    lst_rel = b[f"lst_rel_{EPOCH}"].values
    w = spatial.weights(xy[:, 0], xy[:, 1], threshold=1000)
    mor = spatial.moran(lst_rel, w, permutations=499)
    # Getis–Ord G* requires non-negative values; relative LST is centred on 0, so G* is run on absolute LST (°C).
    # Relative LST is a constant shift of it, so hot/cold spots are the same places by construction.
    gi = spatial.gi_star(b[f"lst_mean_{EPOCH}"].values, xy[:, 0], xy[:, 1], threshold=1000, permutations=499)
    for c in gi.columns:
        res[c] = gi[c].values

    # ---------------------------------------------------------------- B2b DBSCAN on hot cells (geographic)
    q = np.nanquantile(lst_rel, 0.9)
    hot = lst_rel >= q
    hx = xy[hot]
    geo_grid = clustering.dbscan_grid(hx, [600, 750, 1000, 1500], [3, 5, 8], random_state=rs)
    lab_g = np.full(len(b), -2)  # -2 = not a hot cell
    lab_g[hot] = clustering.fit_dbscan(hx, 750, 5)
    sizes = pd.Series(lab_g[lab_g >= 0]).value_counts()
    big = sizes[sizes >= 5].index
    # order hotspot ids by size (0 = largest)
    remap = {old: new for new, old in enumerate(sizes.loc[big].sort_values(ascending=False).index)}
    lab_g = np.array([remap.get(v, -1 if v >= -1 else v) for v in lab_g])
    res["heat_hotspot"] = lab_g
    hot_gi = gi["gi_class"].to_numpy(dtype=object) == "hot"
    overlap = anomaly.agreement(lab_g >= 0, hot_gi)
    hs = []
    for hid in sorted(set(lab_g[lab_g >= 0])):
        m = lab_g == hid
        sub = b[m]
        hs.append({"hotspot": int(hid), "n_cells": int(m.sum()), "area_km2": float(m.sum() * 0.25),
                   "mean_lst": float(sub.lst_mean_2024.mean()), "mean_lst_rel": float(sub[f"lst_rel_{EPOCH}"].mean()),
                   "mean_ndvi": float(sub.s2_ndvi_mean.mean()), "mean_built": float(sub.built_frac.mean()),
                   "dominant_cover": sub.dominant_cover.mode().iat[0] if sub.dominant_cover.notna().any() else None,
                   **_subdiv(sub),
                   "pop_2025": float(sub.pop_2025.sum()), "lat": float(sub.lat.mean()), "lon": float(sub.lon.mean()),
                   "share_gi_hot": float(hot_gi[m].mean())})
    hs = pd.DataFrame(hs)
    hs.to_parquet(out("heat_hotspots.parquet"))
    experiment.save("heat_dbscan_geographic", module="heat", algorithm="DBSCAN (geographic, hot cells)",
                    purpose="Find spatially concentrated groups of the hottest 10 % of land cells",
                    inputs=["x_utm", "y_utm"], n_samples=int(hot.sum()),
                    params={"hot_threshold": f"relative LST ≥ 90th percentile ({q:.2f} °C)", "eps_m": 750,
                            "min_samples": 5, "eps_rule": "750 m > diagonal neighbour distance (707 m) on a 500 m grid",
                            "min_hotspot_cells": 5, "crs": cfg()["crs"]["projected"]},
                    metrics={"n_hotspots": int(len(hs)), "parameter_grid": geo_grid.to_dict("records"),
                             "agreement_with_gi_star_hot": overlap,
                             "moran_I_lst_rel": mor},
                    results={"hotspots": hs.to_dict("records")},
                    limitations=["Hot threshold is relative to Karachi land cells; bare desert can be hottest."])
    experiment.save("heat_gi_star", module="heat", algorithm="Getis–Ord Gi* + Global Moran's I",
                    purpose="Statistically significant spatial clustering of surface temperature",
                    inputs=[f"lst_mean_{EPOCH} (Gi*)", f"lst_rel_{EPOCH} (Moran's I)"], n_samples=len(b),
                    params={"weights": "binary distance band 1000 m", "permutations": 499, "alpha": 0.05,
                            "alternative": "two-sided",
                            "note": "G* is defined for non-negative values, so it is computed on absolute LST (°C)"},
                    metrics={"moran": mor, "n_hot": int((gi.gi_class == "hot").sum()),
                             "n_cold": int((gi.gi_class == "cold").sum()),
                             "n_hot_fdr": int((gi.gi_class_fdr == "hot").sum()),
                             "n_cold_fdr": int((gi.gi_class_fdr == "cold").sum())},
                    limitations=["Hot spots are statistical clustering, not causal evidence.",
                                 "Pseudo p-values from 499 permutations; FDR-adjusted classes also reported."])

    # ---------------------------------------------------------------- B3 contextual Isolation Forest
    ctx = pd.DataFrame(index=b.index)
    ctx["z_cover"] = anomaly.robust_z(b[f"lst_rel_{EPOCH}"], b["dominant_cover"].fillna("unknown"))
    ctx["nb_resid"] = anomaly.neighbour_residual(xy[:, 0], xy[:, 1], lst_rel, radius=1500)
    hist_cols = [f"lst_rel_{e}" for e in cfg()["landsat"]["epochs"] if e != EPOCH and f"lst_rel_{e}" in b]
    hist = b[hist_cols]
    need = min(2, len(hist_cols))  # use every earlier epoch available; require ≥2 when ≥2 exist
    ctx["hist_resid"] = np.where((hist.notna().sum(axis=1) >= need) & (need > 0),
                                 b[f"lst_rel_{EPOCH}"] - hist.mean(axis=1), np.nan)
    ok = ctx.notna().all(axis=1)
    Xa = StandardScaler().fit_transform(ctx[ok].values)
    ic = mc["isolation_forest"]
    score, flag = anomaly.isolation_forest(Xa, ic["contamination"], ic["n_estimators"], rs)
    lscore, lflag = anomaly.lof(Xa, ic["contamination"])
    direction = np.where(ctx[ok].mean(axis=1) > 0, "warmer than context", "cooler than context")
    for c in ctx:
        res.loc[ctx.index, f"anom_{c}"] = ctx[c]
    res["if_score"], res["if_flag"], res["lof_flag"], res["anom_direction"] = np.nan, False, False, None
    res.loc[ok[ok].index, "if_score"] = score
    res.loc[ok[ok].index, "if_flag"] = flag
    res.loc[ok[ok].index, "lof_flag"] = lflag
    res.loc[ok[ok].index, "anom_direction"] = direction

    persist = _persistence(b, res)
    res["anom_persistence"] = persist
    flagged = res[res.if_flag.astype(bool)]
    experiment.save("heat_isolation_forest", module="heat", algorithm="Isolation Forest (+ LOF comparison)",
                    purpose="Find cells whose LST is unusual relative to land-cover peers, neighbours and own history",
                    inputs=list(ctx.columns), n_samples=int(ok.sum()),
                    params={**ic, "context_features": {
                        "z_cover": "robust z of relative LST within the cell's dominant WorldCover class",
                        "nb_resid": "relative LST − mean of land cells within 1.5 km",
                        "hist_resid": f"relative LST {EPOCH} − mean relative LST of earlier epochs (≥2 required)"},
                        "lof_n_neighbors": 35},
                    metrics={"n_flagged": int(flag.sum()),
                             "n_warmer": int((flagged.anom_direction == "warmer than context").sum()),
                             "n_cooler": int((flagged.anom_direction == "cooler than context").sum()),
                             "if_vs_lof": anomaly.agreement(flag, lflag),
                             "median_persistence_flagged": float(np.nanmedian(flagged.anom_persistence)),
                             "median_persistence_unflagged": float(np.nanmedian(res.loc[~res.if_flag.astype(bool), "anom_persistence"]))},
                    interpretation_notes=["Persistence = share of individual Landsat dates (2023–2025) on which the "
                                          "cell's scene-level LST deviates from its neighbours in the same direction "
                                          "as the anomaly; high persistence means the anomaly is not a compositing artefact."],
                    limitations=["Contamination (2 %) sets how many cells are flagged; anomalies are statistical, "
                                 "not hazards."])

    # ---------------------------------------------------------------- B4 correlation / regression
    corr_feats = ["s2_ndvi_mean", "s2_ndbi_mean", "built_frac", "veg_frac_wc", "bare_frac", "log_pop_density_2025",
                  "dist_coast_m", "elev_mean"]
    corr = []
    for f in corr_feats:
        if f in b:
            d = b[["lst_mean_2024", f]].dropna()
            r, p = spearmanr(d.iloc[:, 0], d.iloc[:, 1])
            corr.append({"feature": f, "spearman_rho": r, "p_naive": p, "n": len(d)})
    reg_feats = [f for f in ["s2_ndvi_mean", "built_frac", "bare_frac", "log_pop_density_2025", "dist_coast_m", "elev_mean"] if f in b]
    d = b[["lst_mean_2024"] + reg_feats].dropna()
    Xr = sm.add_constant(StandardScaler().fit_transform(d[reg_feats]))
    yr = (d["lst_mean_2024"] - d["lst_mean_2024"].mean()) / d["lst_mean_2024"].std()
    ols = sm.OLS(yr.values, Xr).fit(cov_type="HC3")
    coefs = [{"feature": f, "std_beta": float(ols.params[i + 1]), "ci_low": float(ols.conf_int()[i + 1][0]),
              "ci_high": float(ols.conf_int()[i + 1][1])} for i, f in enumerate(reg_feats)]
    resid_moran = spatial.moran(ols.resid, spatial.weights(b.loc[d.index, "x_utm"].values, b.loc[d.index, "y_utm"].values, 1000), permutations=199)
    experiment.save("heat_correlation", module="heat", algorithm="Spearman correlation + standardized OLS (HC3)",
                    purpose="Quantify associations of LST with vegetation, built-up, population, coast and terrain",
                    inputs=corr_feats, n_samples=len(d), params={"target": "lst_mean_2024"},
                    metrics={"spearman": corr, "ols_r2": float(ols.rsquared), "ols_std_coefficients": coefs,
                             "residual_moran_I": resid_moran},
                    limitations=["Neighbouring cells are not independent (residual Moran's I reported); naive p-values "
                                 "are overstated.", "Correlation does not establish causation."])

    # ---------------------------------------------------------------- B5 history
    hist_rows = []
    for e in cfg()["landsat"]["epochs"]:
        c = f"lst_mean_{e}"
        if c in df:
            v = df.loc[df.is_land_cell & (df[f"lst_cov_{e}"] >= 0.5), c]
            built_hot = df.loc[df.is_land_cell & (df.built_frac >= 0.5), f"lst_rel_{e}"].median()
            bare = df.loc[df.is_land_cell & (df.bare_frac >= 0.5), f"lst_rel_{e}"].median()
            veg = df.loc[df.is_land_cell & (df.veg_frac_wc >= 0.5), f"lst_rel_{e}"].median()
            hist_rows.append({"epoch": int(e), "n_cells": int(v.notna().sum()), "lst_median": float(v.median()),
                              "lst_p10": float(v.quantile(.1)), "lst_p90": float(v.quantile(.9)),
                              "rel_built_dominant": float(built_hot), "rel_bare_dominant": float(bare),
                              "rel_veg_dominant": float(veg),
                              "n_scenes": int(len(experiment_items(e)))})
    hist_df = pd.DataFrame(hist_rows)
    hist_df.to_parquet(out("heat_history.parquet"))
    experiment.save("heat_history", module="heat", algorithm="Epoch comparison of LST composites",
                    purpose="Historical thermal comparison of Karachi land cells", inputs=["lst_mean_<epoch>"],
                    n_samples=int(len(df)), params={"season": "Apr–Jun", "land_cover_reference": "WorldCover 2021"},
                    metrics={"epochs": hist_df.to_dict("records")},
                    limitations=["Absolute LST differs between epochs with weather on acquisition days; compare "
                                 "relative LST.", "Land-cover classes are from 2021 and applied to all epochs."])

    # ---------------------------------------------------------------- B6 association rules (heat)
    _heat_rules(b, mc)

    res.to_parquet(out("heat_cells.parquet"))
    log.info("heat done: K=%d, %d hotspots, %d IF anomalies, Moran I=%.3f", k, len(hs), int(flag.sum()), mor["I"])
    return res


def _heat_rules(b: pd.DataFrame, mc: dict) -> None:
    """Which combinations of land-surface conditions co-occur with high relative LST? Antecedent items exclude
    every thermal variable, so a rule cannot restate its own consequent."""
    from ..mining import association
    T = pd.DataFrame(index=b.index)
    T["Surface heat"] = association.qbin(b[f"lst_rel_{EPOCH}"])
    T["Built-up"] = association.qbin(b["built_frac"])
    T["Vegetation"] = association.qbin(b["s2_ndvi_mean"], labels=("Sparse", "Moderate", "Dense"))
    T["Bare ground"] = association.qbin(b["bare_frac"])
    T["Population density"] = association.qbin(b["log_pop_density_2025"])
    if "dist_coast_m" in b:
        T["Distance to coast"] = association.qbin(b["dist_coast_m"], labels=("Near", "Mid", "Far"))
    T["Elevation"] = association.qbin(b["elev_mean"])
    oh = association.transactions(T)
    a = mc["apriori"]
    cons = ["Surface heat=High", "Surface heat=Low"]
    rules = association.mine(oh, cons, a["min_support"], a["min_confidence"], a["min_lift"])
    rules.to_parquet(out("heat_association_rules.parquet"))
    items = pd.DataFrame({"grid_id": b["grid_id"].values,
                          "items": [sorted(oh.columns[row].tolist()) for row in oh.values]})
    items.to_parquet(out("heat_association_transactions.parquet"))
    experiment.save("heat_association", module="heat", algorithm="FP-Growth association rules",
                    purpose="Discover combinations of land-surface conditions that co-occur with high or low relative LST",
                    inputs=list(T.columns), n_samples=len(T),
                    params={**a, "discretisation": "tertiles of land cells (labels Low/Medium/High etc.)",
                            "consequents": cons, "redundancy_pruning": "drop rule if a more general rule has ≥ 98 % of its lift"},
                    metrics={"n_rules": int(len(rules)), "n_transactions": int(len(oh)), "n_items": int(oh.shape[1]),
                             "base_rate_high_heat": float(oh.get("Surface heat=High", pd.Series(False)).mean())},
                    results={"top_rules": rules.head(25).to_dict("records")},
                    interpretation_notes=["Lift > 1 means the conditions make high (or low) heat more frequent than its "
                                          "base rate of one third; a frequent rule is not necessarily an interesting one."],
                    limitations=["Association ≠ causation.", "Tertile cut-points are data-driven, not physical thresholds."])


def experiment_items(epoch: str) -> list:
    from .. import provenance
    e = provenance.get("landsat_c2_l2") or {}
    return (e.get("items") or {}).get(epoch, [])


def _persistence(b: pd.DataFrame, res: pd.DataFrame) -> np.ndarray:
    """Share of single scenes (current epoch) on which the cell is *unusually* far from its 1.5 km neighbours in
    the anomaly's direction: (cell LST − neighbour mean) / SD of that quantity across all cells on the same date
    > 1. Computed for every cell so flagged and unflagged cells can be compared. A sign-only test is not used:
    LST patterns are so spatially stable that nearly every cell keeps its sign on every date."""
    p = path("processed", "landsat_scene_observations.parquet")
    if not p.exists():
        return np.full(len(b), np.nan)
    obs = pd.read_parquet(p)
    obs = obs[(obs.variable == "lst") & (obs.epoch.astype(str) == EPOCH) & obs.grid_id.isin(b.grid_id)]
    xy = b.set_index("grid_id")[["x_utm", "y_utm"]]
    zs = []
    for sid, g in obs.groupby("scene_id"):
        g = g.set_index("grid_id").join(xy)
        rr = anomaly.neighbour_residual(g.x_utm.values, g.y_utm.values, g.value.values, 1500)
        sd = np.nanstd(rr)
        if np.isfinite(sd) and sd > 0:
            zs.append(pd.Series(rr / sd, index=g.index, name=sid))
    if not zs:
        return np.full(len(b), np.nan)
    Z = pd.concat(zs, axis=1).reindex(b.grid_id).values
    sign = np.where(res["anom_direction"].to_numpy(dtype=object) == "cooler than context", -1.0, 1.0)
    hit = (Z * sign[:, None]) > 1.0
    n = np.isfinite(Z).sum(axis=1)
    return np.where(n >= 3, hit.sum(axis=1) / np.maximum(n, 1), np.nan)
