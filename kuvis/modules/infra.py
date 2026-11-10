"""Module D — Infrastructure Intelligence (OpenStreetMap network supply only).

No traffic observations are available (see DATA_AVAILABILITY.md), so this module makes no congestion claims.
D1 K-means infrastructure profiles; D2 mapping-completeness check (OSM building density vs WorldPop / WorldCover).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.preprocessing import StandardScaler

from ..config import cfg, get_logger
from ..mining import clustering, experiment
from .common import features, out, relabel_by

log = get_logger("kuvis.infra")


def run() -> pd.DataFrame:
    mc = cfg()["mining"]
    rs = mc["random_state"]
    df = features()
    b = df[df.is_land_cell & (df.frac_inside >= 0.5)].copy()
    feats = [f for f in ["road_density_km_km2", "major_road_density_km_km2", "intersection_density_km2",
                         "osm_building_density_km2", "log_pop_density_2025"] if f in b]
    kb = b.dropna(subset=feats)
    res = pd.DataFrame({"grid_id": b["grid_id"].values}, index=b.index)
    X = StandardScaler().fit_transform(np.log1p(kb[feats].clip(lower=0)).values)
    sweep = clustering.kmeans_sweep(X, tuple(mc["kmeans"]["k_range"]), rs)
    k, rule = clustering.choose_k(sweep)
    lab = relabel_by(clustering.fit_kmeans(X, k, rs).labels_, kb["road_density_km_km2"])
    res.loc[kb.index, "infra_kmeans"] = lab
    nice = {f: f.replace("_km_km2", "").replace("_km2", "").replace("_", " ") for f in feats}
    prof = clustering.profile(kb, lab, feats, nice)
    prof.to_parquet(out("infra_kmeans_profiles.parquet"))
    experiment.save("infra_kmeans", module="infra", algorithm="K-means",
                    purpose="Profile mapped road-network supply relative to population", inputs=feats, n_samples=len(kb),
                    params={"k": k, "selection": rule, "transform": "log1p then z-score"},
                    metrics={"sweep": sweep.to_dict("records"), "chosen": sweep[sweep.k == k].iloc[0].to_dict()},
                    results={"profiles": prof.to_dict("records")},
                    interpretation_notes=["Cluster 0 = lowest mean road density."],
                    limitations=["Describes mapped infrastructure supply, not traffic or congestion.",
                                 "OSM completeness varies spatially (see completeness experiment)."])
    # Mapping completeness proxy: where WorldPop/WorldCover see dense settlement but OSM has few buildings.
    c = b.dropna(subset=["osm_building_density_km2", "pop_density_2025", "built_frac"])
    r1 = spearmanr(c["osm_building_density_km2"], c["pop_density_2025"])
    r2 = spearmanr(c["osm_building_density_km2"], c["built_frac"])
    dense = c[c["built_frac"] >= 0.5]
    experiment.save("infra_osm_completeness", module="infra", algorithm="Spearman correlation (completeness check)",
                    purpose="Assess how completely OSM maps buildings where other sources show dense settlement",
                    inputs=["osm_building_density_km2", "pop_density_2025", "built_frac"], n_samples=len(c),
                    params={"dense_definition": "WorldCover built-up share ≥ 0.5"},
                    metrics={"spearman": [{"feature": "pop_density_2025", "spearman_rho": r1.statistic, "p_naive": r1.pvalue, "n": len(c)},
                                          {"feature": "built_frac", "spearman_rho": r2.statistic, "p_naive": r2.pvalue, "n": len(c)}],
                             "dense_cells": int(len(dense)),
                             "dense_cells_with_lt_50_mapped_buildings_km2": int((dense["osm_building_density_km2"] < 50).sum()),
                             "share_dense_poorly_mapped": float((dense["osm_building_density_km2"] < 50).mean()) if len(dense) else None},
                    limitations=["A low count may also reflect very large buildings; this is a screening indicator."])
    res.to_parquet(out("infra_cells.parquet"))
    log.info("infra: K=%d", k)
    return res
