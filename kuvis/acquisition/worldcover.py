"""ESA WorldCover 10 m land cover (2020 v100, 2021 v200): class fractions per cell.

Fractions are computed on the native 10 m EPSG:4326 pixels (no resampling). The two years were
produced with different algorithm versions; differences between them are NOT treated as land-
cover change anywhere in KUVIS.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.merge import merge

from .. import provenance
from ..config import cfg, get_logger, path
from ..preprocessing import zonal
from . import stac

log = get_logger("kuvis.worldcover")

CLASSES = {10: "tree", 20: "shrub", 30: "grass", 40: "crop", 50: "built", 60: "bare",
           70: "snow", 80: "water", 90: "wetland", 95: "mangrove", 100: "moss"}


def run(grid: gpd.GeoDataFrame, study: gpd.GeoDataFrame) -> pd.DataFrame:
    bbox = stac.study_bbox_ll(study, 1000)
    frames = []
    files = []
    for year in cfg()["worldcover"]["years"]:
        items = stac.search(cfg()["worldcover"]["collection"], bbox, datetime=f"{year}")
        items = [it for it in items if str(year) in it.properties.get("start_datetime", it.id)]
        srcs = [rasterio.open(it.assets["map"].href) for it in items]
        mosaic, tr = merge(srcs, bounds=bbox)
        crs = srcs[0].crs
        for s in srcs:
            s.close()
        arr = mosaic[0]
        tif = path("interim", f"worldcover_{year}.tif")
        with rasterio.open(tif, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                           dtype=arr.dtype, crs=crs, transform=tr, nodata=0, compress="deflate", tiled=True) as d:
            d.write(arr, 1)
        files.append(tif)
        labels = zonal.label_raster(grid, crs, tr, arr.shape)
        fr = zonal.class_fractions(labels, arr, len(grid), CLASSES, nodata=0, prefix=f"wc{year}")
        frames.append(fr)
        log.info("worldcover %d: built mean %.3f, tree mean %.3f", year,
                 np.nanmean(fr[f"wc{year}_built"]), np.nanmean(fr[f"wc{year}_tree"]))
        provenance.record(
            f"esa_worldcover_{year}",
            status="acquired",
            title=f"ESA WorldCover {year} ({'v100' if year == 2020 else 'v200'})",
            provider="European Space Agency, via Microsoft Planetary Computer",
            url="https://esa-worldcover.org/en/data-access",
            method="STAC search + windowed COG read at native 10 m (EPSG:4326)",
            files=[tif],
            license="CC BY 4.0",
            crs="EPSG:4326",
            spatial_resolution="10 m",
            temporal_coverage=str(year),
            variables=list(CLASSES.values()),
            items=[it.id for it in items],
            limitations="2020 (v100) and 2021 (v200) use different algorithms; differences are not change.",
        )
    df = pd.concat(frames, axis=1)
    df.insert(0, "grid_id", grid["grid_id"].values)
    df.to_parquet(path("interim", "features_worldcover.parquet"))
    return df
