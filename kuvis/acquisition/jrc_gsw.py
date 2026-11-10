"""JRC Global Surface Water (1984–2021): water occurrence and seasonality per cell.

Contextual evidence only: occurrence describes how often open water was observed by Landsat. It is
NOT a flood record — permanent sea, reservoirs and salt-pans dominate it, and short urban flooding
under cloud is rarely captured.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from .. import provenance
from ..config import get_logger, path
from ..preprocessing import zonal
from . import stac

log = get_logger("kuvis.jrc")


def run(grid: gpd.GeoDataFrame, study: gpd.GeoDataFrame) -> pd.DataFrame:
    bbox = stac.study_bbox_ll(study, 1000)
    items = stac.search("jrc-gsw", bbox)
    out = pd.DataFrame({"grid_id": grid["grid_id"].values})
    import rasterio
    from rasterio.merge import merge

    def mosaic(asset):
        srcs = [rasterio.open(it.assets[asset].href) for it in items]
        arr, tr = merge(srcs, bounds=bbox)
        crs = srcs[0].crs
        for s in srcs:
            s.close()
        return arr[0], tr, crs

    occ, tr, crs = mosaic("occurrence")
    seas, _, _ = mosaic("seasonality")
    labels = zonal.label_raster(grid, crs, tr, occ.shape)
    occf = occ.astype("float32")
    occf[occf > 100] = np.nan  # 255 = no data
    n = len(grid)
    o = zonal.stats(labels, occf, n, prefix="gsw_occ", which=("mean", "max"))
    out["gsw_occurrence_mean"] = o["gsw_occ_mean"].values
    out["gsw_occurrence_max"] = o["gsw_occ_max"].values
    ever = np.where(np.isfinite(occf), (occf > 0).astype("float32"), np.nan)
    out["gsw_ever_water_frac"] = zonal.stats(labels, ever, n, prefix="e", which=("mean",))["e_mean"].values
    perm = np.where(seas <= 12, (seas == 12).astype("float32"), np.nan)
    out["gsw_permanent_frac"] = zonal.stats(labels, perm, n, prefix="p", which=("mean",))["p_mean"].values
    seasonal = np.where(seas <= 12, ((seas > 0) & (seas < 12)).astype("float32"), np.nan)
    out["gsw_seasonal_frac"] = zonal.stats(labels, seasonal, n, prefix="s", which=("mean",))["s_mean"].values
    out.to_parquet(path("interim", "features_jrc_gsw.parquet"))
    tif = path("interim", "jrc_occurrence.tif")
    with rasterio.open(tif, "w", driver="GTiff", height=occ.shape[0], width=occ.shape[1], count=1, dtype="uint8",
                       crs=crs, transform=tr, nodata=255, compress="deflate") as d:
        d.write(occ.astype("uint8"), 1)
    provenance.record(
        "jrc_gsw",
        status="acquired",
        title="JRC Global Surface Water v1.4 (occurrence, seasonality)",
        provider="European Commission Joint Research Centre, via Microsoft Planetary Computer",
        url="https://global-surface-water.appspot.com/",
        method="STAC search + windowed COG read at native 30 m (EPSG:4326)",
        files=[tif],
        license="Free use with attribution (Pekel et al., 2016, Nature)",
        crs="EPSG:4326",
        spatial_resolution="1 arc-second (~30 m)",
        temporal_coverage="1984-03 to 2021-12",
        variables=["occurrence (%)", "seasonality (months)"],
        limitations="Permanent water occurrence is not urban flooding.",
    )
    log.info("JRC GSW: cells with any water history %d", int((out.gsw_ever_water_frac > 0).sum()))
    return out
