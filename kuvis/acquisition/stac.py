"""Microsoft Planetary Computer STAC access (no credentials required; URLs are SAS-signed).

Planetary Computer hosts the same Landsat Collection-2 Level-2, Sentinel-2 L2A, NASADEM,
ESA WorldCover and JRC GSW products that the Google Earth Engine catalog exposes, read
directly from Cloud-Optimized GeoTIFFs. Using it keeps the pipeline reproducible without any
personal cloud account.
"""

from __future__ import annotations

import os

import geopandas as gpd
import numpy as np
import planetary_computer
import pystac_client
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds

from ..config import cfg, get_logger

log = get_logger("kuvis.stac")

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.TIF,.tiff,.cog")


def client() -> pystac_client.Client:
    return pystac_client.Client.open(cfg()["stac"]["endpoint"], modifier=planetary_computer.sign_inplace)


def study_bbox_ll(study: gpd.GeoDataFrame, buffer_m: float = 1000) -> tuple[float, float, float, float]:
    g = study.geometry.buffer(buffer_m).to_crs("EPSG:4326")
    return tuple(float(v) for v in g.total_bounds)


def search(collection: str, bbox, datetime: str | None = None, query: dict | None = None) -> list:
    items = list(client().search(collections=[collection], bbox=bbox, datetime=datetime, query=query).items())
    log.info("%s: %d items (%s)", collection, len(items), datetime or "all dates")
    return items


def read_window(href: str, bbox_ll, *, masked_nodata: bool = True):
    """Windowed read of a COG in its NATIVE CRS covering a lon/lat bbox. Returns (array, transform, crs, nodata)."""
    with rasterio.open(href) as src:
        b = transform_bounds("EPSG:4326", src.crs, *bbox_ll, densify_pts=21)
        win = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
        win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
        arr = src.read(1, window=win)
        tr = src.window_transform(win)
        nod = src.nodata
        if masked_nodata and nod is not None and np.issubdtype(arr.dtype, np.floating):
            arr = np.where(arr == nod, np.nan, arr)
        return arr, tr, src.crs, nod
