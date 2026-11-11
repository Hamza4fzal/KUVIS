"""Landsat Collection-2 Level-2 (LST, NDVI, NDBI, MNDWI) and Sentinel-2 L2A (NDVI, NDWI, NDBI).

Landsat
-------
* ST band (L8/9 ST_B10 = asset `lwir11`; L5/7 ST_B6 = asset `lwir`): LST[°C] = DN·0.00341802 + 149.0 − 273.15
  (USGS Collection-2 Level-2 scale/offset). This is LAND SURFACE temperature, not 2 m air temperature.
* SR bands: ρ = DN·0.0000275 − 0.2.
* QA_PIXEL mask: drop fill (bit 0), dilated cloud (1), cirrus (2, OLI only), cloud (3), cloud shadow (4).
* ST_QA (asset `qa`, K·0.01): pixels with LST uncertainty > 4 K are dropped.
* Physical-range checks: LST outside [−5, 75] °C and reflectance outside (0, 1] are treated as invalid.

Sentinel-2
----------
* Planetary Computer's `sentinel-2-l2a` is NOT harmonized: for processing baseline ≥ 04.00
  (from 25 Jan 2022) DN carry a +1000 offset, removed here: ρ = (DN − 1000)/10000.
* SCL mask keeps: 4 vegetation, 5 bare, 6 water, 7 unclassified; drops 0–3, 8–11.
* 10 m bands (B03, B04, B08) are read at 20 m (GDAL uses the COG's internal overview, then average
  resampling onto the target grid) — chosen to cut download volume 4× on a slow link; for 500 m cell
  means the difference from full-resolution averaging is negligible. B11 and SCL are native 20 m.
"""

from __future__ import annotations

from collections import defaultdict

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio.warp import Resampling

from .. import provenance
from ..config import cfg, get_logger, path
from ..preprocessing import zonal
from . import stac
from .optical import TargetGrid, composite, nd, read_asset, write_tif

log = get_logger("kuvis.satellite")

ST_SCALE, ST_OFF = 0.00341802, 149.0
# Landsat assets are read from COG overview level 0 (60 m): TIRS thermal is natively 100 m, and 500 m cell
# means of reflectance indices are insensitive to 30 vs 60 m; this quarters download volume on a slow link.
LS_OVR = 0
SR_SCALE, SR_OFF = 0.0000275, -0.2


def _dedupe(items: list, key_fn) -> list:
    """Keep one product per (tile, acquisition date). Planetary Computer lists both original and
    reprocessed Sentinel-2 products for the same acquisition; the id ends with the processing timestamp,
    so the lexicographically largest id is the most recent processing."""
    best = {}
    for it in items:
        k = (key_fn(it), it.datetime.date())
        if k not in best or it.id > best[k].id:
            best[k] = it
    return list(best.values())


def _pick_clearest(items: list, key_fn, per_group: int) -> list:
    groups = defaultdict(list)
    for it in _dedupe(items, key_fn):
        groups[key_fn(it)].append(it)
    out = []
    for g, its in groups.items():
        its.sort(key=lambda i: i.properties.get("eo:cloud_cover", 100))
        out.extend(its[:per_group])
    return sorted(out, key=lambda i: i.datetime)


# ----------------------------------------------------------------------------------------------- Landsat
def landsat_reader(it, tg: TargetGrid):
    a = it.assets
    qa = read_asset(a["qa_pixel"].href, tg, dtype="uint16", overview_level=LS_OVR).astype(np.uint32)
    oli = "lwir11" in a
    bad = (1 << 0) | (1 << 1) | (1 << 3) | (1 << 4) | ((1 << 2) if oli else 0)
    clear = ((qa & bad) == 0) & (qa != 0)
    if clear.mean() < 0.05:
        log.info("landsat %s: <5%% clear pixels on target grid, skipped", it.id)
        return None
    st = read_asset(a["lwir11" if oli else "lwir"].href, tg, overview_level=LS_OVR)
    lst = st * ST_SCALE + ST_OFF - 273.15
    if "qa" in a:
        unc = read_asset(a["qa"].href, tg, overview_level=LS_OVR) * 0.01
        clear &= ~(unc > 4.0)
    lst[~clear | (lst < -5) | (lst > 75)] = np.nan

    def sr(k):
        x = read_asset(a[k].href, tg, overview_level=LS_OVR) * SR_SCALE + SR_OFF
        x[~clear | (x <= 0) | (x > 1)] = np.nan
        return x

    red, nir, swir = sr("red"), sr("nir08"), sr("swir16")
    return {"lst": lst, "ndvi": nd(nir, red), "ndbi": nd(swir, nir)}


def run_landsat(grid: gpd.GeoDataFrame, study: gpd.GeoDataFrame, per_tile: int = 3,
                epochs: list[str] | None = None) -> pd.DataFrame:
    """Process the given epochs (default: all configured). Results merge with previously processed epochs,
    so epochs can be added incrementally on a slow connection."""
    c = cfg()["landsat"]
    tg = TargetGrid.around(study, c["resolution_m"], snap=30)
    bbox = stac.study_bbox_ll(study)
    feats, obs_all = [], []
    prev = provenance.get("landsat_c2_l2") or {}
    used_items = dict(prev.get("items") or {})
    for epoch, spec in c["epochs"].items():
        if epochs and epoch not in epochs:
            continue
        items = []
        for year in range(spec["years"][0], spec["years"][1] + 1):
            m0, m1 = min(c["season_months"]), max(c["season_months"])
            dt = f"{year}-{m0:02d}-01/{year}-{m1:02d}-30"
            items += stac.search(c["collection"], bbox, dt, query={
                "platform": {"in": spec["platforms"]},
                "eo:cloud_cover": {"lt": c["max_scene_cloud"]},
                "landsat:collection_category": {"eq": "T1"},
            })
        items = _pick_clearest(items, lambda i: (i.properties.get("landsat:wrs_path"), i.properties.get("landsat:wrs_row")), per_tile)
        log.info("landsat epoch %s: %d scenes selected", epoch, len(items))
        used_items[epoch] = [i.id for i in items]
        med, obs, labels = composite(items, landsat_reader, tg, grid, ["lst", "ndvi", "ndbi"], f"landsat_{epoch}")
        n = len(grid)
        f = {"grid_id": grid["grid_id"].values}
        lst = zonal.stats(labels, med["lst"], n, prefix="lst", which=("mean", "std", "max", "p90"))
        for col in ["lst_mean", "lst_std", "lst_max", "lst_p90", "lst_cov"]:
            f[f"{col}_{epoch}"] = lst[col].values
        for v in ("ndvi", "ndbi"):
            s = zonal.stats(labels, med[v], n, prefix=v, which=("mean",))
            f[f"ls_{v}_{epoch}"] = s[f"{v}_mean"].values
        cnt = zonal.stats(labels, med["_count"], n, prefix="nobs", which=("mean",))
        f[f"lst_nobs_{epoch}"] = cnt["nobs_mean"].values
        feats.append(pd.DataFrame(f).set_index("grid_id"))
        for v in ("lst", "ndvi"):
            write_tif(med[v], tg, path("interim", f"landsat_{v}_{epoch}.tif"))
        if len(obs):
            obs["epoch"] = epoch
            obs_all.append(obs)
    df = pd.concat(feats, axis=1)
    fp = path("interim", "features_landsat.parquet")
    if fp.exists():  # merge with epochs processed in earlier runs
        old = pd.read_parquet(fp).set_index("grid_id")
        old = old[[c_ for c_ in old.columns if c_ not in df.columns]]
        df = old.join(df, how="outer")
    df = df.reset_index()
    df.to_parquet(fp)
    obs = pd.concat(obs_all, ignore_index=True)
    op = path("processed", "landsat_scene_observations.parquet")
    if op.exists():
        old = pd.read_parquet(op)
        obs = pd.concat([old[~old.epoch.isin(obs.epoch.unique())], obs], ignore_index=True)
    obs.to_parquet(op)
    provenance.record(
        "landsat_c2_l2",
        status="acquired",
        title="Landsat Collection 2 Level-2 Surface Reflectance & Surface Temperature (L5 TM, L8/L9 OLI-TIRS)",
        provider="USGS, via Microsoft Planetary Computer",
        url="https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2",
        method=f"STAC search (Apr–Jun, T1, cloud<30%, clearest {per_tile} per WRS tile) + QA-masked median composite on 60 m UTM 42N grid",
        files=sorted(path("interim").glob("landsat_*.tif")),
        license="Public domain (USGS)",
        crs="EPSG:32642",
        spatial_resolution="60 m processing grid (COG overview 0); thermal native 100 m TIRS / 120 m TM",
        temporal_coverage=", ".join(f"{e}: {s['years'][0]}–{s['years'][1]} Apr–Jun" for e, s in c["epochs"].items()),
        variables=["LST (°C)", "NDVI", "NDBI"],
        items=used_items,
        limitations="LST ≠ air temperature; thermal native resolution coarser than 30 m; cross-sensor (TM vs OLI) "
                    "index offsets not calibrated; acquisition times ~10:30 local only.",
    )
    return df


# -------------------------------------------------------------------------------------------- Sentinel-2
SCL_KEEP = (4, 5, 6, 7)


def s2_reader(it, tg: TargetGrid):
    a = it.assets
    scl = read_asset(a["SCL"].href, tg, dtype="uint8")
    clear = np.isin(scl, SCL_KEEP)
    if clear.mean() < 0.05:
        return None
    baseline = float(it.properties.get("s2:processing_baseline", "0") or 0)
    off = 1000.0 if baseline >= 4.0 else 0.0

    def band(k, rs, ovr=None):
        x = (read_asset(a[k].href, tg, resampling=rs, overview_level=ovr) - off) / 10000.0
        x[~clear | (x <= 0) | (x > 1)] = np.nan
        return x

    g, r, n = (band(k, Resampling.nearest, ovr=0) for k in ("B03", "B04", "B08"))  # 20 m overview, aligned
    s = band("B11", Resampling.nearest)
    return {"ndvi": nd(n, r), "ndwi": nd(g, n), "ndbi": nd(s, n)}


def run_sentinel2(grid: gpd.GeoDataFrame, study: gpd.GeoDataFrame, per_tile: int = 3) -> pd.DataFrame:
    c = cfg()["sentinel2"]
    tg = TargetGrid.around(study, c["resolution_m"], snap=60)
    bbox = stac.study_bbox_ll(study)
    items = stac.search(c["collection"], bbox, f"{c['start']}/{c['end']}",
                        query={"eo:cloud_cover": {"lt": c["max_scene_cloud"]}})
    items = _pick_clearest(items, lambda i: i.properties.get("s2:mgrs_tile"), per_tile)
    med, obs, labels = composite(items, s2_reader, tg, grid, ["ndvi", "ndwi", "ndbi"], "s2")
    n = len(grid)
    f = {"grid_id": grid["grid_id"].values}
    for v in ("ndvi", "ndwi", "ndbi"):
        s = zonal.stats(labels, med[v], n, prefix=v, which=("mean", "std"))
        f[f"s2_{v}_mean"], f[f"s2_{v}_std"] = s[f"{v}_mean"].values, s[f"{v}_std"].values
        f[f"s2_{v}_cov"] = s[f"{v}_cov"].values
        write_tif(med[v], tg, path("interim", f"s2_{v}.tif"))
    # Vegetation fraction: share of valid pixels with NDVI > 0.3 (a common moderate-vegetation threshold).
    veg = np.where(np.isfinite(med["ndvi"]), (med["ndvi"] > 0.3).astype("float32"), np.nan)
    f["s2_veg_frac"] = zonal.stats(labels, veg, n, prefix="veg", which=("mean",))["veg_mean"].values
    df = pd.DataFrame(f)
    df.to_parquet(path("interim", "features_sentinel2.parquet"))
    if len(obs):
        obs.to_parquet(path("processed", "s2_scene_observations.parquet"))
    provenance.record(
        "sentinel2_l2a",
        status="acquired",
        title="Sentinel-2 MSI Level-2A surface reflectance",
        provider="ESA Copernicus, via Microsoft Planetary Computer",
        url="https://planetarycomputer.microsoft.com/dataset/sentinel-2-l2a",
        method=f"STAC search {c['start']}–{c['end']}, cloud<{c['max_scene_cloud']}%, clearest {per_tile} per MGRS tile; "
               "SCL-masked median composite on 20 m UTM 42N grid; baseline-04.00 offset removed",
        files=[path("interim", f"s2_{v}.tif") for v in ("ndvi", "ndwi", "ndbi")],
        license="Copernicus open licence (free, attribution)",
        crs="EPSG:32642",
        spatial_resolution="20 m (10 m bands from 20 m COG overview)",
        temporal_coverage=f"{c['start']} to {c['end']} (dry season)",
        variables=["NDVI", "NDWI (McFeeters)", "NDBI", "vegetation fraction (NDVI>0.3)"],
        items=[i.id for i in items],
        limitations="NDBI is a spectral proxy for built-up/bare surfaces; it confuses bare soil with built-up in arid Karachi.",
    )
    return df
