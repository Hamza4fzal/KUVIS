"""Discovery engine: turns stored mining outputs into ranked, evidence-carrying findings.

Every discovery is produced by a rule over stored results with an explicit quality threshold; titles and
descriptions are templates filled with computed numbers. Nothing here asserts a finding that the data did
not produce, and a category simply yields no discoveries when its threshold is not met.

strength ∈ [0, 1] is a per-category normalized effect measure (documented in each evidence block) used only
for ranking.
"""

from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy.spatial import cKDTree
from scipy.sparse.csgraph import connected_components
from scipy.sparse import coo_matrix

from ..config import get_logger, path
from ..mining.experiment import EXP_DIR
from .common import features, out

log = get_logger("kuvis.discoveries")


def _exp(eid: str) -> dict | None:
    p = EXP_DIR / f"{eid}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _geom(grid: gpd.GeoDataFrame, ids) -> str | None:
    g = grid[grid.grid_id.isin(list(ids))]
    if g.empty:
        return None
    u = shapely.union_all(g.to_crs(4326).geometry.values)
    return shapely.to_wkb(shapely.set_srid(u, 4326), hex=True, include_srid=True)


def _subs(df: pd.DataFrame, ids) -> str:
    s = df[df.grid_id.isin(list(ids))].subdivision.value_counts()
    return ", ".join(s.index[:2]) if len(s) else "Karachi"


def _components(df: pd.DataFrame, ids, radius=750) -> list[list[str]]:
    sub = df[df.grid_id.isin(list(ids))]
    if sub.empty:
        return []
    xy = sub[["x_utm", "y_utm"]].values
    pairs = cKDTree(xy).query_pairs(radius, output_type="ndarray")
    n = len(sub)
    A = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n)) if len(pairs) else coo_matrix((n, n))
    _, lab = connected_components(A, directed=False)
    return [sub.grid_id.values[lab == c].tolist() for c in np.unique(lab)]


def run() -> list[dict]:
    df = features()
    grid = gpd.read_parquet(path("processed", "grid.parquet"))
    D: list[dict] = []

    def add(**kw):
        ids = kw.pop("grid_ids", [])
        sub = df[df.grid_id.isin(ids)]
        kw.setdefault("lon", float(sub.lon.mean()) if len(sub) else None)
        kw.setdefault("lat", float(sub.lat.mean()) if len(sub) else None)
        kw.setdefault("zoom", 13 if len(ids) < 40 else 12 if len(ids) < 200 else 11)
        kw["grid_ids"] = list(ids)
        kw["geom_ewkb"] = _geom(grid, ids) if ids else None
        kw["discovery_id"] = f"D{len(D) + 1:03d}"
        kw.pop("_rank_col", None)
        if len(sub):  # representative cell = the one nearest the discovery's centroid (used by "Show on map")
            d2 = (sub.x_utm - sub.x_utm.mean()) ** 2 + (sub.y_utm - sub.y_utm.mean()) ** 2
            kw.setdefault("evidence", {})["example_cell"] = sub.grid_id.loc[d2.idxmin()]
        D.append(kw)

    # 1 — heat concentrations (DBSCAN) confirmed by Gi*
    hs_p = out("heat_hotspots.parquet")
    hc_p = out("heat_cells.parquet")
    if hs_p.exists() and hc_p.exists():
        hs, hc = pd.read_parquet(hs_p), pd.read_parquet(hc_p)
        for r in hs.itertuples():
            if r.n_cells >= 10 and r.share_gi_hot >= 0.5:
                ids = hc.grid_id[hc.heat_hotspot == r.hotspot].tolist()
                subs = ", ".join(list(r.subdivisions.keys())[:2]) if isinstance(r.subdivisions, dict) else _subs(df, ids)
                add(category="Spatial heat concentration",
                    title=f"{r.area_km2:.1f} km² heat concentration around {subs}",
                    description=(f"DBSCAN groups {r.n_cells} of Karachi's hottest-decile cells into one contiguous concentration. "
                                 f"Mean pre-monsoon land surface temperature is {r.mean_lst:.1f} °C, {r.mean_lst_rel:+.1f} °C relative to the "
                                 f"city median; mean NDVI {r.mean_ndvi:.2f}, built-up share {r.mean_built * 100:.0f} %, dominant land cover "
                                 f"'{r.dominant_cover}'. {r.share_gi_hot * 100:.0f} % of its cells are also Getis–Ord Gi* hot spots. "
                                 f"WorldPop estimates {r.pop_2025:,.0f} residents (2025) in these cells."),
                    period="Apr–Jun 2023–2025", algorithm="DBSCAN (geographic) + Gi*", experiment_id="heat_dbscan_geographic",
                    variables=["lst_rel_2024", "s2_ndvi_mean", "built_frac"], sources=["Landsat 8/9", "Sentinel-2", "ESA WorldCover", "WorldPop"],
                    evidence={"n_cells": r.n_cells, "mean_lst_rel": r.mean_lst_rel, "share_gi_hot": r.share_gi_hot,
                              "strength_definition": "min(1, mean relative LST / 8 °C)"},
                    strength=float(min(1, r.mean_lst_rel / 8)), grid_ids=ids, _rank_col="grid_id")

    # 2 — thermal profiles: hottest and coolest K-means clusters
    e = _exp("heat_kmeans")
    if e and hc_p.exists():
        hc = pd.read_parquet(hc_p)
        prof = pd.DataFrame(e["results"]["profiles"])
        for which, r in (("warmest", prof.iloc[-1]), ("coolest", prof.iloc[0])):
            ids = hc.grid_id[hc.heat_kmeans == r.cluster].tolist()
            add(category="Thermal profile", title=f"The {which} thermal profile: {r['name']}",
                description=(f"K-means (K={e['parameters']['k']}, silhouette {e['metrics']['chosen']['silhouette']:.2f}) isolates "
                             f"{int(r.n_cells)} cells ({r.share * 100:.0f} % of analysed land) with mean LST {r.mean_lst_mean_2024:.1f} °C, "
                             f"NDVI {r.mean_s2_ndvi_mean:.2f}, NDBI {r.mean_s2_ndbi_mean:.2f}, built-up {r.mean_built_frac * 100:.0f} %."),
                period="2023–2025", algorithm="K-means", experiment_id="heat_kmeans",
                variables=e["input_features"], sources=["Landsat 8/9", "Sentinel-2", "ESA WorldCover", "WorldPop"],
                evidence={"cluster": int(r.cluster), "z_scores": {k: r[k] for k in r.index if str(k).startswith("z_")},
                          "strength_definition": "|z| of mean LST / 2"},
                strength=float(min(1, abs(r.z_lst_mean_2024) / 2)), grid_ids=ids)

    # 3 — statistical relationships (correlation + regression)
    e = _exp("heat_correlation")
    if e:
        names = {"s2_ndvi_mean": "vegetation (NDVI)", "s2_ndbi_mean": "NDBI", "built_frac": "built-up share",
                 "veg_frac_wc": "vegetation share", "bare_frac": "bare-ground share", "log_pop_density_2025": "population density",
                 "dist_coast_m": "distance from the coast", "elev_mean": "elevation"}
        betas = {c["feature"]: c for c in e["metrics"]["ols_std_coefficients"]}
        for s in sorted(e["metrics"]["spearman"], key=lambda s: -abs(s["spearman_rho"]))[:4]:
            if abs(s["spearman_rho"]) < 0.3:
                continue
            bt = betas.get(s["feature"])
            add(category="Statistical relationship",
                title=f"Surface heat {'rises' if s['spearman_rho'] > 0 else 'falls'} with {names.get(s['feature'], s['feature'])} (ρ = {s['spearman_rho']:.2f})",
                description=(f"Across {s['n']:,} land cells, Spearman ρ between 2023–25 LST and {names.get(s['feature'], s['feature'])} is "
                             f"{s['spearman_rho']:.2f}."
                             + (f" Holding the other variables fixed, the standardized OLS coefficient is {bt['std_beta']:+.2f} "
                                f"(95 % CI {bt['ci_low']:+.2f} to {bt['ci_high']:+.2f}; model R² = {e['metrics']['ols_r2']:.2f})." if bt else "")
                             + " Neighbouring cells are not independent, so significance is overstated; this is association, not causation."),
                period="2023–2025", algorithm="Spearman + standardized OLS", experiment_id="heat_correlation",
                variables=["lst_mean_2024", s["feature"]], sources=["Landsat 8/9"],
                evidence={**s, "ols": bt, "residual_moran_I": e["metrics"]["residual_moran_I"]["I"],
                          "strength_definition": "|ρ|"},
                strength=float(abs(s["spearman_rho"])), grid_ids=[], lon=None, lat=None)

    # 4 — association rules (heat, flood, vulnerability)
    for eid, src in (("heat_association", ["Landsat", "Sentinel-2", "WorldCover", "WorldPop", "NASADEM", "OSM"]),
                     ("flood_association", ["NASADEM", "WorldCover", "Sentinel-2", "OSM", "CHIRPS", "JRC GSW"]),
                     ("vulnerability_association", ["KUVIS indicators"])):
        e = _exp(eid)
        rp = out(f"{eid}_rules.parquet")
        if not (e and rp.exists()):
            continue
        rules = pd.read_parquet(rp)
        tp = out(f"{eid}_transactions.parquet")
        tx = pd.read_parquet(tp) if tp.exists() else None
        for r in rules.sort_values("lift", ascending=False).head(3).itertuples():
            if r.lift < 1.5:
                continue
            ids = []
            if tx is not None:
                need = set(r.antecedents) | {r.consequent}
                ids = tx.grid_id[tx["items"].apply(lambda it: need <= set(it))].tolist()
            add(category="Environmental association",
                title=f"{' + '.join(r.antecedents)} ⇒ {r.consequent}",
                description=(f"In {r.support * 100:.1f} % of analysed cells these conditions occur together with {r.consequent}. "
                             f"When the conditions hold, {r.consequent} follows {r.confidence * 100:.0f} % of the time — "
                             f"{r.lift:.2f}× its base rate of {r.consequent_support * 100:.0f} %. Co-occurrence, not causation."),
                period="current period", algorithm="FP-Growth", experiment_id=eid, variables=list(r.antecedents) + [r.consequent],
                sources=src, evidence={"support": r.support, "confidence": r.confidence, "lift": r.lift, "leverage": r.leverage,
                                       "n_matching_cells": len(ids), "strength_definition": "min(1, (lift − 1) / 3)"},
                strength=float(min(1, (r.lift - 1) / 3)), grid_ids=ids)

    # 5 — persistent thermal anomalies (connected groups)
    if hc_p.exists():
        hc = pd.read_parquet(hc_p)
        a = hc[hc.if_flag.astype(bool) & (hc.anom_persistence >= 0.6)]
        comps = sorted(_components(df, a.grid_id), key=len, reverse=True)
        for comp in comps[:6]:
            sub = a[a.grid_id.isin(comp)]
            fd = df[df.grid_id.isin(comp)]
            d = sub.anom_direction.mode().iat[0]
            add(category="Unusual heat observation",
                title=f"{'Persistently warm' if 'warmer' in d else 'Persistently cool'} anomaly in {_subs(df, comp)} ({len(comp)} cell{'s' if len(comp) > 1 else ''})",
                description=(f"Isolation Forest flags these cells as {d}: their relative LST is {sub.anom_z_cover.mean():+.1f} robust-SD from cells "
                             f"with the same land cover and {sub.anom_nb_resid.mean():+.1f} °C from neighbours within 1.5 km; the deviation "
                             f"recurs on {sub.anom_persistence.mean() * 100:.0f} % of individual satellite dates. Dominant cover: "
                             f"{fd.dominant_cover.mode().iat[0] if fd.dominant_cover.notna().any() else 'n/a'}. Statistically unusual, not necessarily hazardous."),
                period="Apr–Jun 2023–2025", algorithm="Isolation Forest", experiment_id="heat_isolation_forest",
                variables=["anom_z_cover", "anom_nb_resid", "anom_hist_resid"], sources=["Landsat 8/9", "ESA WorldCover"],
                evidence={"mean_score": float(sub.if_score.mean()), "persistence": float(sub.anom_persistence.mean()),
                          "lof_agreement": float(sub.lof_flag.mean()), "strength_definition": "persistence × min(1, |nb_resid| / 4)"},
                strength=float(sub.anom_persistence.mean() * min(1, abs(sub.anom_nb_resid.mean()) / 4)), grid_ids=comp)

    # 6 — land-use transitions 2005→2017
    e = _exp("urban_lulc_change")
    if e:
        for prod, label in (("hr", "peri-urban (HR)"), ("vhr", "core urban (VHR)")):
            t = e["results"].get(prod)
            if not t:
                continue
            for tr in t["top_transitions"][:3]:
                if tr["km2"] < 1:
                    continue
                total_from = t["area_2005_km2"].get(tr["from_name"], np.nan)
                add(category="Urban transformation",
                    title=f"{tr['km2']:.1f} km² of {tr['from_name'].replace('_', ' ')} became {tr['to_name'].replace('_', ' ')} (2005→2017)",
                    description=(f"Intersecting the World Bank EO4SD {label} land-use maps shows {tr['km2']:.1f} km² mapped as "
                                 f"{tr['from_name'].replace('_', ' ')} in 2005 and {tr['to_name'].replace('_', ' ')} in 2017 — "
                                 f"{tr['km2'] / total_from * 100:.0f} % of all 2005 {tr['from_name'].replace('_', ' ')} in the mapped extent."),
                    period="2005 → 2017", algorithm="Land-use transition matrix", experiment_id="urban_lulc_change",
                    variables=["EO4SD LULC"], sources=["World Bank EO4SD-Urban"],
                    evidence={**tr, "share_of_source_class": tr["km2"] / total_from, "strength_definition": "min(1, km² / 50)"},
                    strength=float(min(1, tr["km2"] / 50)), grid_ids=[], lon=None, lat=None)

    # 7 — vegetation loss / gain concentrations (Landsat 2005→2024)
    if "ndvi_change_2005_2024" in df:
        land = df[df.is_land_cell & df.ndvi_change_2005_2024.notna()]
        for sign, label in ((-1, "loss"), (1, "gain")):
            thr = land.ndvi_change_2005_2024.quantile(0.05 if sign < 0 else 0.95)
            sel = land[(land.ndvi_change_2005_2024 * sign >= abs(thr)) & (land.ndvi_change_2005_2024 * sign > 0.05)]
            for comp in sorted(_components(df, sel.grid_id), key=len, reverse=True)[:3]:
                if len(comp) < 8:
                    continue
                sub = df[df.grid_id.isin(comp)]
                add(category="Vegetation change",
                    title=f"Concentrated vegetation {label}: {len(comp) * 0.25:.1f} km² in {_subs(df, comp)}",
                    description=(f"{len(comp)} contiguous cells fall in Karachi's most extreme 5 % of NDVI {label} between the 2004–06 and 2023–25 "
                                 f"Landsat epochs (mean change {sub.ndvi_change_2005_2024.mean():+.2f}; NDVI {sub.ls_ndvi_2005.mean():.2f} → "
                                 f"{sub.ls_ndvi_2024.mean():.2f}). Relative surface heat changed by {sub.lst_rel_change_2005_2024.mean():+.1f} °C."),
                    period="2004–06 → 2023–25", algorithm="Change detection + connected components", experiment_id="urban_kmeans",
                    variables=["ndvi_change_2005_2024", "lst_rel_change_2005_2024"], sources=["Landsat 5", "Landsat 8/9"],
                    evidence={"n_cells": len(comp), "mean_ndvi_change": float(sub.ndvi_change_2005_2024.mean()),
                              "threshold": float(thr), "strength_definition": "min(1, |mean change| / 0.3)"},
                    strength=float(min(1, abs(sub.ndvi_change_2005_2024.mean()) / 0.3)), grid_ids=comp)

    # 8 — overlapping stress concentrations
    vh = out("vulnerability_hotspots.parquet")
    vcp = out("vulnerability_cells.parquet")
    if vh.exists() and vcp.exists():
        hs, vc = pd.read_parquet(vh), pd.read_parquet(vcp)
        for r in hs.itertuples():
            if r.n_cells < 10:
                continue
            ids = vc.grid_id[vc.combined_hotspot == r.hotspot].tolist()
            dims = {d: getattr(r, f"mean_dim_{d}") for d in ("heat", "flood", "urbanization", "environmental") if hasattr(r, f"mean_dim_{d}")}
            top = sorted(dims, key=lambda d: -dims[d])[:2]
            add(category="Overlapping environmental stress",
                title=f"Overlapping {top[0]} and {top[1]} stress: {r.area_km2:.1f} km² in {_subs(df, ids)}",
                description=(f"{r.n_cells} contiguous cells in the top decile of the composite index (mean UVI {r.mean_uvi:.2f}). "
                             + ", ".join(f"{d} {v:.2f}" for d, v in dims.items())
                             + f" (percentile-scale dimension scores). {r.share_stable_top * 100:.0f} % stay in the top quintile under 95 % of "
                               f"alternative weightings. WorldPop estimates {r.pop_2025:,.0f} residents (2025)."),
                period="current period", algorithm="Composite index + DBSCAN", experiment_id="vulnerability_dbscan_geographic",
                variables=list(dims), sources=["KUVIS indicators"],
                evidence={**dims, "mean_uvi": r.mean_uvi, "share_stable_top": r.share_stable_top,
                          "strength_definition": "mean UVI × share stable"},
                strength=float(r.mean_uvi * r.share_stable_top), grid_ids=ids)

    # 9 — consistent historical pattern: built vs bare relative heat across epochs
    e = _exp("heat_history")
    if e and len(e["metrics"]["epochs"]) >= 2:
        ep = pd.DataFrame(e["metrics"]["epochs"])
        diff = ep.rel_built_dominant - ep.rel_bare_dominant
        if (np.sign(diff) == np.sign(diff.iloc[0])).all() and diff.abs().min() > 0.5:
            add(category="Historical change",
                title=f"Built-up land is consistently {'cooler' if diff.iloc[0] < 0 else 'warmer'} than bare land at the surface (every epoch)",
                description=("In every Landsat epoch (" + ", ".join(str(x) for x in ep.epoch) + "), cells dominated by built-up surface have a median "
                             "relative LST " + ", ".join(f"{d:+.1f}" for d in diff) + " °C relative to bare-ground-dominated cells. "
                             "In arid settings bare desert soil heats strongly by day, so this daytime surface pattern differs from the "
                             "classic urban heat island measured in air temperature. Land cover classes are from WorldCover 2021."),
                period=f"{ep.epoch.min()}–{ep.epoch.max()}", algorithm="Epoch comparison", experiment_id="heat_history",
                variables=["lst_rel", "built_frac", "bare_frac"], sources=["Landsat 5/8/9", "ESA WorldCover"],
                evidence={"built_minus_bare_by_epoch": dict(zip(ep.epoch.astype(str), diff.round(2))),
                          "strength_definition": "min(1, mean |difference| / 5)"},
                strength=float(min(1, diff.abs().mean() / 5)), grid_ids=[], lon=None, lat=None)

    # 10 — rainfall: 2022 monsoon anomaly (assigned from CHIRPS)
    if "rain_jjas_2022_anom_pct" in df and df.rain_jjas_2022_anom_pct.notna().any():
        an = df.groupby("chirps_pixel_id")["rain_jjas_2022_anom_pct"].first().dropna()
        if an.median() > 50:
            add(category="Rainfall",
                title=f"2022 monsoon rainfall {an.median():.0f} % above the 1991–2020 normal over Karachi",
                description=(f"Across the {len(an)} CHIRPS v3 pixels covering Karachi, June–September 2022 rainfall was a median "
                             f"{an.median():.0f} % above the 1991–2020 normal (range {an.min():.0f} % to {an.max():.0f} %). "
                             "CHIRPS is a satellite–gauge blend at ≈5.5 km; it cannot resolve neighbourhood differences."),
                period="Jun–Sep 2022", algorithm="Climatological anomaly", experiment_id=None,
                variables=["rain_jjas_2022_mm", "rain_jjas_normal_mm"], sources=["CHIRPS v3"],
                evidence={"median_anomaly_pct": float(an.median()), "n_pixels": int(len(an)), "strength_definition": "min(1, anomaly/300 %)"},
                strength=float(min(1, an.median() / 300)), grid_ids=[], lon=None, lat=None)

    for d in D:
        if d.get("experiment_id") and not (EXP_DIR / f"{d['experiment_id']}.json").exists():
            d["experiment_id"] = None
    out("discoveries.json").write_text(json.dumps(D, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)),
                                       encoding="utf-8")
    log.info("discoveries: %d generated (%s)", len(D), pd.Series([d["category"] for d in D]).value_counts().to_dict() if D else {})
    return D
