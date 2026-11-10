"""CHIRPS v3.0 monthly rainfall (0.05°, ≈5.5 km) for Karachi, 1981 onward.

Rainfall is stored at the NATIVE CHIRPS pixel level (`chirps_pixels`, `chirps_monthly`). Grid cells
are linked to the CHIRPS pixel containing their centroid (`cell_pixel_map`). One CHIRPS pixel covers
roughly 100 grid cells, so cells sharing a pixel share one value: rainfall is *assigned*, never
presented as an independent 500 m measurement. CHIRPS blends satellite IR with station data; it is
not a rain-gauge record.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol, xy
from shapely.geometry import box

from .. import provenance
from ..config import cfg, get_logger, path
from . import stac

log = get_logger("kuvis.chirps")


def _read(url: str, bbox):
    for attempt in range(4):
        try:
            return stac.read_window(url, bbox)
        except Exception as exc:  # network hiccup → retry
            log.warning("retry %d %s: %s", attempt + 1, url.rsplit("/", 1)[-1], exc)
    raise RuntimeError(f"CHIRPS read failed: {url}")


def run(grid: gpd.GeoDataFrame, study: gpd.GeoDataFrame) -> pd.DataFrame:
    c = cfg()["chirps"]
    bbox = stac.study_bbox_ll(study, 6000)
    months = [(y, m) for y in range(c["start_year"], c["end_year"] + 1) for m in range(1, 13)]
    urls = {ym: f"/vsicurl/{c['base_url']}/chirps-v3.0.{ym[0]}.{ym[1]:02d}.cog" for ym in months}

    arr0, tr, crs, nod = _read(urls[months[0]], bbox)
    h, w = arr0.shape
    log.info("CHIRPS window %dx%d pixels, transform %s", w, h, tr)

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = dict(zip(months, ex.map(lambda ym: _read(urls[ym], bbox)[0], months)))

    # Pixel table (native geometry)
    pix = []
    for r in range(h):
        for col in range(w):
            x0, y0 = tr * (col, r)
            x1, y1 = tr * (col + 1, r + 1)
            pix.append({"pixel_id": f"CHIRPS_{r:03d}_{col:03d}", "row": r, "col": col,
                        "geometry": box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))})
    pixels = gpd.GeoDataFrame(pix, crs="EPSG:4326")
    cx, cy = xy(tr, pixels["row"], pixels["col"])
    pixels["lon"], pixels["lat"] = np.round(cx, 4), np.round(cy, 4)
    # keep pixels touching the study area
    pixels = pixels[pixels.intersects(study.to_crs("EPSG:4326").geometry.iloc[0])].reset_index(drop=True)

    rows = []
    for (y, m), arr in results.items():
        a = arr.astype("float64")
        a[(a < 0) | ~np.isfinite(a)] = np.nan  # -9999 / negative = missing, NOT zero rainfall
        vals = a[pixels["row"].values, pixels["col"].values]
        rows.append(pd.DataFrame({"pixel_id": pixels["pixel_id"], "year": y, "month": m, "precip_mm": vals}))
    monthly = pd.concat(rows, ignore_index=True)

    # cell → pixel (centroid in pixel)
    r_, c_ = rowcol(tr, grid["lon"].values, grid["lat"].values)
    pid = [f"CHIRPS_{a:03d}_{b:03d}" for a, b in zip(r_, c_)]
    cmap = pd.DataFrame({"grid_id": grid["grid_id"].values, "pixel_id": pid})
    cmap.loc[~cmap["pixel_id"].isin(set(pixels["pixel_id"])), "pixel_id"] = None

    pixels.to_parquet(path("processed", "chirps_pixels.parquet"))
    monthly.to_parquet(path("processed", "chirps_monthly.parquet"))
    cmap.to_parquet(path("processed", "cell_chirps_map.parquet"))
    provenance.record(
        "chirps_v3_monthly",
        status="acquired",
        title="CHIRPS v3.0 monthly precipitation (global COGs)",
        provider="UC Santa Barbara Climate Hazards Center",
        url="https://www.chc.ucsb.edu/data/chirps3",
        method="Windowed HTTP range reads of monthly COGs (no full-file download)",
        files=[path("processed", "chirps_monthly.parquet"), path("processed", "chirps_pixels.parquet")],
        license="CC BY 4.0",
        crs="EPSG:4326",
        spatial_resolution="0.05° (≈5.5 km); stored at native pixels",
        temporal_coverage=f"{c['start_year']}-01 to {c['end_year']}-12 (monthly)",
        variables=["precip_mm (monthly total)"],
        n_pixels=int(len(pixels)),
        limitations="Satellite–gauge blend; one pixel spans ~100 grid cells; not neighbourhood ground truth; "
                    "monthly totals cannot resolve sub-daily cloudburst intensity.",
    )
    log.info("CHIRPS: %d pixels × %d months; missing %.2f%%", len(pixels), len(months),
             100 * monthly["precip_mm"].isna().mean())
    return monthly
