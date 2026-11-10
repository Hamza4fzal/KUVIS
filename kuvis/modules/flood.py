"""Module A — Flood Vulnerability Intelligence.

Label policy
------------
No validated, openly available cell-level record of historical urban flooding exists for Karachi. The only
independent, spatially complete observation of water appearing where it is not permanent is JRC Global
Surface Water seasonality (Landsat, 1984–2021). KUVIS therefore defines

    intermittent_water = share of the cell's 30 m pixels with 1–11 water months in a typical year ≥ 2 %

and calls it exactly that — "intermittent surface water observed", NOT "flooded". It captures ponding,
seasonal channels, river beds, tidal flats and some flood extents. Predictors never include water-derived
variables (JRC, WorldCover water, NDWI/MNDWI), so the label is not reconstructed from its own inputs.
Permanent-water cells are excluded. The label threshold is varied (1 %, 2 %, 5 %) as a sensitivity check.

A1 K-means flood-related terrain/surface profiles · A2 DBSCAN · A3 FP-Growth rules with the intermittent-
water item as consequent · A4 Decision Tree with spatially blocked CV.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score
from sklearn.preprocessing import StandardScaler

from ..config import cfg, get_logger
from ..mining import association, classification, clustering, experiment, spatial
from .common import features, out, relabel_by

log = get_logger("kuvis.flood")

KM_FEATS = ["elev_mean", "slope_mean", "tpi_2km_m", "built_frac", "s2_ndvi_mean", "log_dist_drain", "rain_jjas_normal_mm"]
NICE = {"elev_mean": "elevation", "slope_mean": "slope", "tpi_2km_m": "local depression (TPI)", "built_frac": "built-up",
        "s2_ndvi_mean": "NDVI", "log_dist_drain": "distance to mapped drain", "rain_jjas_normal_mm": "monsoon rainfall"}
TREE_FEATS = ["elev_mean", "elev_std", "slope_mean", "tpi_2km_m", "built_frac", "bare_frac", "s2_ndvi_mean",
              "log_dist_drain", "log_dist_waterway", "log_dist_coast", "rain_jjas_normal_mm"]
LABEL_T = 0.02


def _prep() -> pd.DataFrame:
    df = features()
    df["log_dist_drain"] = np.log10(df["dist_drain_m"] + 50)
    df["log_dist_waterway"] = np.log10(df["dist_waterway_m"] + 50)
    df["log_dist_coast"] = np.log10(df["dist_coast_m"] + 50)
    perm = (df["gsw_permanent_frac"].fillna(0) > 0.5) | (df["water_frac"].fillna(0) > 0.5)
    base = df[df["is_land_cell"] & ~perm & (df["frac_inside"] >= 0.5)].copy()
    base["intermittent_water"] = np.where(base["gsw_seasonal_frac"].notna(),
                                          (base["gsw_seasonal_frac"] >= LABEL_T).astype(float), np.nan)
    return base


def run() -> pd.DataFrame:
    mc = cfg()["mining"]
    rs = mc["random_state"]
    b = _prep()
    res = pd.DataFrame({"grid_id": b["grid_id"].values}, index=b.index)

    # ------------------------------------------------ A1 K-means
    km_b = b.dropna(subset=KM_FEATS)
    X = StandardScaler().fit_transform(km_b[KM_FEATS].values)
    sweep = clustering.kmeans_sweep(X, tuple(mc["kmeans"]["k_range"]), rs)
    k, rule = clustering.choose_k(sweep)
    lab = relabel_by(clustering.fit_kmeans(X, k, rs).labels_, -km_b["elev_mean"])  # 0 = highest ground
    res.loc[km_b.index, "flood_kmeans"] = lab
    prof = clustering.profile(km_b, lab, KM_FEATS, NICE)
    # attach observed intermittent-water share per cluster (evidence, not an input)
    prof["share_intermittent_water"] = [float(km_b.loc[lab == c, "intermittent_water"].mean()) for c in prof.cluster]
    prof["mean_gsw_occurrence"] = [float(km_b.loc[lab == c, "gsw_occurrence_mean"].mean()) for c in prof.cluster]
    prof.to_parquet(out("flood_kmeans_profiles.parquet"))
    experiment.save("flood_kmeans", module="flood", algorithm="K-means",
                    purpose="Group land cells by flood-related terrain, surface and rainfall characteristics",
                    inputs=KM_FEATS, n_samples=len(km_b), params={"k": k, "selection": rule, "scaling": "z-score",
                                                                  "excluded": "permanent water cells"},
                    metrics={"sweep": sweep.to_dict("records"), "chosen": sweep[sweep.k == k].iloc[0].to_dict()},
                    results={"profiles": prof.to_dict("records")},
                    interpretation_notes=["Clusters are NOT labelled flood-prone a priori; the share of cells with observed "
                                          "intermittent surface water (JRC) is attached afterwards as independent evidence.",
                                          "Cluster 0 = highest mean elevation."],
                    limitations=["Rainfall is assigned from ≈5.5 km CHIRPS pixels and varies little inside the city.",
                                 "30 m DEM cannot represent drains or micro-topography."])

    # ------------------------------------------------ A2 DBSCAN (feature space) + compare
    ms = 10
    eps = clustering.knee(clustering.k_distance(X, ms))
    grid_f = clustering.dbscan_grid(X, sorted({round(eps * f, 3) for f in (0.6, 0.8, 1.0, 1.25, 1.5)}), mc["dbscan"]["min_samples_grid"], random_state=rs)
    lab_d = clustering.fit_dbscan(X, eps, ms)
    res.loc[km_b.index, "flood_dbscan_feature"] = lab_d
    nn = lab_d >= 0
    experiment.save("flood_dbscan_feature", module="flood", algorithm="DBSCAN (feature space)",
                    purpose="Density-based flood-related profiles; compare with K-means", inputs=KM_FEATS, n_samples=len(km_b),
                    params={"eps": eps, "min_samples": ms, "eps_rule": "knee of sorted k-distance curve"},
                    metrics={"n_clusters": int(len(set(lab_d[nn]))), "noise_share": float((~nn).mean()),
                             "ari_vs_kmeans_non_noise": adjusted_rand_score(lab[nn], lab_d[nn]) if nn.sum() > 10 else None,
                             "noise_intermittent_water_share": float(km_b.loc[~nn, "intermittent_water"].mean()) if (~nn).any() else None,
                             "core_intermittent_water_share": float(km_b.loc[nn, "intermittent_water"].mean()),
                             "parameter_grid": grid_f.to_dict("records")})

    # ------------------------------------------------ A3 association rules
    T = pd.DataFrame(index=b.index)
    T["Elevation"] = association.qbin(b["elev_mean"])
    T["Terrain position"] = association.qbin(b["tpi_2km_m"], labels=("Depression", "Neutral", "Raised"))
    T["Slope"] = association.qbin(b["slope_mean"], labels=("Flat", "Moderate", "Steep"))
    T["Built-up"] = association.qbin(b["built_frac"])
    T["Vegetation"] = association.qbin(b["s2_ndvi_mean"], labels=("Sparse", "Moderate", "Dense"))
    T["Drain distance"] = association.qbin(b["dist_drain_m"], labels=("Near", "Mid", "Far"))
    T["Monsoon rainfall"] = association.qbin(b["rain_jjas_normal_mm"])
    T["Intermittent water"] = np.where(b["intermittent_water"].isna(), None,
                                       np.where(b["intermittent_water"] == 1, "Observed", "Not observed"))
    oh = association.transactions(T)
    a = mc["apriori"]
    base_rate = float(oh.get("Intermittent water=Observed", pd.Series(False)).mean())
    # the consequent is rare, so support is set relative to its base rate (documented)
    min_sup = min(a["min_support"], max(0.01, base_rate * 0.25))
    rules = association.mine(oh, ["Intermittent water=Observed"], min_sup, min(0.3, a["min_confidence"]), 1.5)
    rules.to_parquet(out("flood_association_rules.parquet"))
    pd.DataFrame({"grid_id": b["grid_id"].values, "items": [sorted(oh.columns[r].tolist()) for r in oh.values]}).to_parquet(
        out("flood_association_transactions.parquet"))
    experiment.save("flood_association", module="flood", algorithm="FP-Growth association rules",
                    purpose="Find combinations of terrain/surface/drainage/rainfall conditions that co-occur with observed "
                            "intermittent surface water",
                    inputs=list(T.columns), n_samples=len(T),
                    params={"min_support": min_sup, "min_confidence": min(0.3, a["min_confidence"]), "min_lift": 1.5,
                            "support_rule": "min(config support, max(1 %, ¼ × base rate of consequent))",
                            "consequent": "Intermittent water=Observed", "label_threshold": LABEL_T},
                    metrics={"n_rules": int(len(rules)), "base_rate": base_rate, "n_transactions": int(len(oh))},
                    results={"top_rules": rules.head(25).to_dict("records")},
                    interpretation_notes=["Because only a minority of cells show intermittent water, confidence values are "
                                          "modest; lift measures how much the conditions raise the rate above its base rate."],
                    limitations=["Intermittent water ≠ urban flooding; short urban floods under cloud are rarely captured "
                                 "by Landsat.", "Association ≠ causation."])

    # ------------------------------------------------ A4 Decision tree, spatial block CV
    tb = b.dropna(subset=TREE_FEATS + ["intermittent_water"])
    groups = spatial.spatial_blocks(tb["x_utm"].values, tb["y_utm"].values, 5000)
    sens = {}
    for t in (0.01, LABEL_T, 0.05):
        y = (tb["gsw_seasonal_frac"] >= t).astype(int).values
        r = classification.blocked_cv(tb[TREE_FEATS], y, groups, random_state=rs)
        sens[str(t)] = {k_: r["metrics"][k_] for k_ in ("balanced_accuracy", "roc_auc", "positive_rate", "best_depth")}
        if t == LABEL_T:
            main = r
    y = (tb["gsw_seasonal_frac"] >= LABEL_T).astype(int).values
    model = main["model"]
    paths = classification.decision_paths(model, tb[TREE_FEATS])
    tr = pd.DataFrame({"grid_id": tb["grid_id"].values, "observed": y, "predicted": (main["oof_proba"] >= 0.5).astype(int),
                       "probability": main["oof_proba"], "decision_path": paths})
    tr.to_parquet(out("flood_tree_results.parquet"))
    res.loc[tb.index, "flood_tree_proba"] = main["oof_proba"]
    experiment.save("flood_tree", module="flood", algorithm="Decision Tree (spatially blocked CV)",
                    purpose="Which terrain/surface characteristics distinguish cells with observed intermittent surface water?",
                    inputs=TREE_FEATS, n_samples=len(tb),
                    params={"target": f"JRC GSW seasonal-water share ≥ {LABEL_T}", "class_weight": "balanced",
                            "cv": "GroupKFold(5) on 5 km × 5 km blocks", "min_samples_leaf": "1 % of cells"},
                    metrics={**{k_: v for k_, v in main["metrics"].items() if k_ != "depth_search"},
                             "depth_search": main["metrics"]["depth_search"], "label_threshold_sensitivity": sens},
                    results={"importance": main["importance"].to_dict("records"), "rules_text": main["rules_text"]},
                    interpretation_notes=["Probabilities are out-of-fold: each cell is scored by a tree that never saw its "
                                          "5 km block. Decision paths are from the final tree fitted on all cells."],
                    limitations=["The target is intermittent surface water, not validated flood occurrence; the model "
                                 "explains this proxy and has no demonstrated predictive validity for urban flood events.",
                                 "Spatial blocks reduce but do not eliminate spatial leakage."])
    res.to_parquet(out("flood_cells.parquet"))
    log.info("flood: K=%d, %d rules, tree balanced acc %.3f AUC %.3f", k, len(rules),
             main["metrics"]["balanced_accuracy"], main["metrics"]["roc_auc"])
    return res
