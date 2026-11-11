"""Assemble analytical tables from the per-source interim feature files.

Outputs (datasets/processed/):
  cell_features.parquet   one row per grid cell: static + latest-period features
  cell_epochs.parquet     one row per (grid cell, Landsat epoch): LST/NDVI/NDBI/MNDWI history
  cell_rainfall.parquet   CHIRPS-derived rainfall summaries per cell (assigned from native pixel)
  feature_dictionary.json definition, unit, source, temporal reference of every feature

Missing values stay missing. Only the OSM count features use 0, because there "0 mapped roads" is
a genuine observation of the map (with completeness caveats), not an imputation.
"""

from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from ..config import cfg, get_logger, path
from .dictionary import FEATURES

log = get_logger("kuvis.features")

SOURCES = ["terrain", "worldcover", "sentinel2", "landsat", "population", "osm", "jrc_gsw", "lulc"]


def _load(name: str) -> pd.DataFrame | None:
    p = path("interim", f"features_{name}.parquet")
    if not p.exists():
        log.warning("feature source missing: %s (step not run or failed) — columns will be absent", name)
        return None
    return pd.read_parquet(p)


def rainfall_features(grid: pd.DataFrame) -> pd.DataFrame | None:
    mp = path("processed", "chirps_monthly.parquet")
    if not mp.exists():
        return None
    m = pd.read_parquet(mp)
    cmap = pd.read_parquet(path("processed", "cell_chirps_map.parquet"))
    normal = m[(m.year >= 1991) & (m.year <= 2020)]  # WMO standard normal period
    annual = normal.groupby(["pixel_id", "year"])["precip_mm"].sum(min_count=12).groupby("pixel_id").mean()
    jjas = normal[normal.month.isin([6, 7, 8, 9])].groupby(["pixel_id", "year"])["precip_mm"].sum(min_count=4)
    jjas_mean = jjas.groupby("pixel_id").mean()
    jjas_cv = jjas.groupby("pixel_id").std() / jjas_mean
    maxm = m.groupby("pixel_id")["precip_mm"].max()
    yr = m.groupby(["pixel_id", "year"])["precip_mm"].sum(min_count=12).reset_index()
    full = yr.dropna()
    # Theil–Sen-free simple OLS trend of annual totals (mm/decade) over all complete years
    def slope(g):
        return np.polyfit(g.year, g.precip_mm, 1)[0] * 10 if len(g) > 10 else np.nan
    trend = full.groupby("pixel_id").apply(slope, include_groups=False)
    m2022 = m[(m.year == 2022) & m.month.isin([6, 7, 8, 9])].groupby("pixel_id")["precip_mm"].sum(min_count=4)
    m2020 = m[(m.year == 2020) & (m.month == 8)].set_index("pixel_id")["precip_mm"]
    p = pd.DataFrame({"rain_annual_normal_mm": annual, "rain_jjas_normal_mm": jjas_mean, "rain_jjas_cv": jjas_cv,
                      "rain_max_month_mm": maxm, "rain_trend_mm_decade": trend,
                      "rain_jjas_2022_mm": m2022, "rain_aug_2020_mm": m2020})
    p["rain_jjas_2022_anom_pct"] = 100 * (p.rain_jjas_2022_mm / p.rain_jjas_normal_mm - 1)
    out = cmap.merge(p, left_on="pixel_id", right_index=True, how="left").rename(columns={"pixel_id": "chirps_pixel_id"})
    return out


def run() -> pd.DataFrame:
    grid = gpd.read_parquet(path("processed", "grid.parquet"))
    df = pd.DataFrame(grid.drop(columns="geometry"))
    for s in SOURCES:
        f = _load(s)
        if f is not None:
            df = df.merge(f, on="grid_id", how="left")

    # ---- derived: terrain position (cell mean elevation minus mean within 2 km)
    if "elev_mean" in df:
        tree = cKDTree(df[["x_utm", "y_utm"]].values)
        ev = df["elev_mean"].values
        nbrs = tree.query_ball_point(df[["x_utm", "y_utm"]].values, r=2000)
        df["tpi_2km_m"] = [ev[i] - np.nanmean(ev[[j for j in nb if j != i]]) if len(nb) > 1 else np.nan
                           for i, nb in enumerate(nbrs)]

    # ---- derived: land-cover aggregates (WorldCover 2021, the newer algorithm)
    if "wc2021_built" in df:
        df["built_frac"] = df["wc2021_built"]
        df["veg_frac_wc"] = df[["wc2021_tree", "wc2021_shrub", "wc2021_grass", "wc2021_crop", "wc2021_mangrove"]].sum(axis=1, min_count=1)
        df["water_frac"] = df[["wc2021_water", "wc2021_wetland"]].sum(axis=1, min_count=1)
        df["bare_frac"] = df["wc2021_bare"]
        cls_cols = [c for c in df.columns if c.startswith("wc2021_") and c != "wc2021_npix"]
        df["dominant_cover"] = df[cls_cols].idxmax(axis=1).str.replace("wc2021_", "", regex=False)
        df.loc[df[cls_cols].isna().all(axis=1), "dominant_cover"] = None

    # ---- derived: relative LST per epoch (cell − median of land cells in that epoch).
    # Absolute LST differs between epochs because of acquisition-day weather; the relative form
    # (surface urban-heat-island style) is what can be compared across years.
    epochs = list(cfg()["landsat"]["epochs"])
    land = (df.get("water_frac", pd.Series(0, index=df.index)).fillna(1) < 0.5) & (df["frac_inside"] >= 0.5)
    df["is_land_cell"] = land
    for e in epochs:
        col = f"lst_mean_{e}"
        if col in df:
            ok = land & (df.get(f"lst_cov_{e}", 1) >= 0.5)
            df[f"lst_rel_{e}"] = np.where(ok, df[col] - df.loc[ok, col].median(), np.nan)
    if {"ls_ndvi_2001", "ls_ndvi_2024"} <= set(df):
        df["ndvi_change_2001_2024"] = df["ls_ndvi_2024"] - df["ls_ndvi_2001"]
        df["ndbi_change_2001_2024"] = df["ls_ndbi_2024"] - df["ls_ndbi_2001"]
    if {"lst_rel_2001", "lst_rel_2024"} <= set(df):
        df["lst_rel_change_2001_2024"] = df["lst_rel_2024"] - df["lst_rel_2001"]
    for y in cfg()["worldpop"]["years"]:
        if f"pop_density_{y}" in df:
            df[f"log_pop_density_{y}"] = np.log1p(df[f"pop_density_{y}"])
    if {"pop_2015", "pop_2025"} <= set(df):
        df["pop_change_2015_2025"] = df["pop_2025"] - df["pop_2015"]

    rf = rainfall_features(df)
    if rf is not None:
        df = df.merge(rf, on="grid_id", how="left")

    # ---- data quality: share of core evidence available for the cell
    core = [c for c in ["elev_mean", "built_frac", "s2_ndvi_mean", "lst_mean_2024", "pop_2025",
                        "rain_jjas_normal_mm", "road_density_km_km2"] if c in df]
    df["data_quality_score"] = df[core].notna().mean(axis=1).round(3)
    df["data_quality_inputs"] = ",".join(core)

    # ---- long epoch table
    rows = []
    for e in epochs:
        cols = {f"lst_mean_{e}": "lst_mean", f"lst_rel_{e}": "lst_rel", f"lst_p90_{e}": "lst_p90", f"lst_cov_{e}": "lst_cov",
                f"lst_nobs_{e}": "lst_nobs", f"ls_ndvi_{e}": "ndvi", f"ls_ndbi_{e}": "ndbi", f"ls_mndwi_{e}": "mndwi"}
        have = {k: v for k, v in cols.items() if k in df}
        if have:
            t = df[["grid_id"] + list(have)].rename(columns=have)
            t.insert(1, "epoch", int(e))
            rows.append(t)
    if rows:
        pd.concat(rows, ignore_index=True).to_parquet(path("processed", "cell_epochs.parquet"))

    df.to_parquet(path("processed", "cell_features.parquet"))
    present = {k: v for k, v in FEATURES.items() if k in df.columns}
    path("processed", "feature_dictionary.json").write_text(json.dumps(present, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("features: %d cells × %d columns; land cells %d; mean data quality %.2f",
             len(df), df.shape[1], int(land.sum()), df["data_quality_score"].mean())
    missing_doc = sorted(c for c in df.columns if c not in FEATURES and not c.startswith(("wc2020_", "wc2021_")))
    if missing_doc:
        log.info("columns without dictionary entry (internal/aux): %s", missing_doc)
    return df
