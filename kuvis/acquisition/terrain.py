"""NASADEM (reprocessed SRTM, 1 arc-second) elevation and slope per grid cell.

Processing: windowed read of the native EPSG:4326 tiles → mosaic → bilinear reprojection to a
30 m UTM 42N grid (documented resampling) → slope via Horn's method → zonal statistics.
Topographic position (cell elevation minus mean elevation within 2 km) is derived later at the
cell level. A 30 m global DEM cannot resolve urban drains or street-level micro-topography.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.merge import merge
from rasterio.warp import Resampling, calculate_default_transform, reproject

from .. import provenance
from ..config import cfg, get_logger, path, projected_crs
from ..preprocessing import zonal
from . import stac

log = get_logger("kuvis.terrain")


def horn_slope_deg(dem: np.ndarray, res: float) -> np.ndarray:
    z = np.pad(dem, 1, mode="edge")
    a, b, c = z[:-2, :-2], z[:-2, 1:-1], z[:-2, 2:]
    d, f = z[1:-1, :-2], z[1:-1, 2:]
    g, h, i = z[2:, :-2], z[2:, 1:-1], z[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * res)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * res)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))


def run(grid: gpd.GeoDataFrame, study: gpd.GeoDataFrame) -> pd.DataFrame:
    bbox = stac.study_bbox_ll(study, 3000)
    items = stac.search(cfg()["dem"]["collection"], bbox)
    hrefs = [it.assets["elevation"].href for it in items]
    srcs = [rasterio.open(h) for h in hrefs]
    mosaic, mtr = merge(srcs, bounds=bbox)
    src_crs, nodata = srcs[0].crs, srcs[0].nodata
    for s in srcs:
        s.close()
    mosaic = mosaic[0].astype("float32")
    if nodata is not None:
        mosaic[mosaic == nodata] = np.nan

    res = float(cfg()["dem"]["resolution_m"])
    h, w = mosaic.shape
    left, top = mtr.c, mtr.f
    right, bottom = left + w * mtr.a, top + h * mtr.e
    dtr, dw, dh = calculate_default_transform(src_crs, projected_crs(), w, h, left, bottom, right, top, resolution=res)
    dem = np.full((dh, dw), np.nan, dtype="float32")
    reproject(mosaic, dem, src_transform=mtr, src_crs=src_crs, dst_transform=dtr, dst_crs=projected_crs(),
              resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan)

    # Persist the processed DEM (interim) so other steps (e.g. flood) can reuse it.
    out_tif = path("interim", "dem_utm30.tif")
    with rasterio.open(out_tif, "w", driver="GTiff", height=dh, width=dw, count=1, dtype="float32",
                       crs=projected_crs(), transform=dtr, nodata=np.nan, compress="deflate", tiled=True) as dst:
        dst.write(dem, 1)

    slope = horn_slope_deg(dem, res)
    labels = zonal.label_raster(grid, projected_crs(), dtr, dem.shape)
    n = len(grid)
    el = zonal.stats(labels, dem, n, prefix="elev", which=("mean", "std", "min", "max"))
    sl = zonal.stats(labels, slope, n, prefix="slope", which=("mean", "p90"))
    df = pd.concat([el, sl.drop(columns=["slope_n", "slope_cov"])], axis=1)
    df.insert(0, "grid_id", grid["grid_id"].values)
    df.to_parquet(path("interim", "features_terrain.parquet"))
    provenance.record(
        "nasadem",
        status="acquired",
        title="NASADEM Merged DEM Global 1 arc second (SRTM reprocessed)",
        provider="NASA JPL / LP DAAC, via Microsoft Planetary Computer",
        url="https://planetarycomputer.microsoft.com/dataset/nasadem",
        method="STAC search + windowed COG read; bilinear reprojection to 30 m UTM 42N",
        files=[out_tif],
        license="Public domain (NASA)",
        crs="native EPSG:4326 → EPSG:32642",
        spatial_resolution="1 arc-second (~30 m)",
        temporal_coverage="Feb 2000 (SRTM mission)",
        variables=["elevation"],
        items=[it.id for it in items],
    )
    log.info("terrain: elevation range %.1f–%.1f m", np.nanmin(df.elev_mean), np.nanmax(df.elev_mean))
    return df
