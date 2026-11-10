"""Multi-scene optical compositing for Landsat C2 L2 and Sentinel-2 L2A.

Design
------
* Every scene is warped onto ONE fixed target grid in UTM 42N (the native CRS of both Landsat
  path 152 and Sentinel-2 tiles over Karachi), so pixels line up across dates.
* Each scene's per-pixel variables (e.g. LST, NDVI) are written to a disk-backed stack
  (np.memmap) so memory stays bounded; the per-pixel median over valid observations is then
  computed strip by strip.
* For every scene we also store the cell-level mean of each variable together with its valid-
  pixel coverage. These dated observations feed temporal analysis and contextual anomaly
  detection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling

from ..config import get_logger, path, projected_crs
from ..preprocessing import zonal

log = get_logger("kuvis.optical")


@dataclass(frozen=True)
class TargetGrid:
    transform: Affine
    width: int
    height: int
    crs: str

    @classmethod
    def around(cls, study: gpd.GeoDataFrame, res: float, buffer_m: float = 1000, snap: float = 60) -> "TargetGrid":
        minx, miny, maxx, maxy = study.to_crs(projected_crs()).geometry.buffer(buffer_m).total_bounds
        minx, miny = math.floor(minx / snap) * snap, math.floor(miny / snap) * snap
        maxx, maxy = math.ceil(maxx / snap) * snap, math.ceil(maxy / snap) * snap
        w, h = int(round((maxx - minx) / res)), int(round((maxy - miny) / res))
        return cls(Affine(res, 0, minx, 0, -res, maxy), w, h, projected_crs())


def read_asset(href: str, tg: TargetGrid, resampling=Resampling.nearest, dtype="float32") -> np.ndarray:
    """Read a COG asset warped onto the target grid; pixels outside the scene come back as NaN."""
    with rasterio.open(href) as src:
        nod = src.nodata
        with WarpedVRT(src, crs=tg.crs, transform=tg.transform, width=tg.width, height=tg.height,
                       resampling=resampling, src_nodata=nod, nodata=nod) as vrt:
            arr = vrt.read(1, masked=True)
    out = arr.astype(dtype).filled(np.nan) if np.issubdtype(np.dtype(dtype), np.floating) else arr.filled(0).astype(dtype)
    return out


SceneReader = Callable[[object, TargetGrid], dict[str, np.ndarray]]


def composite(items: list, reader: SceneReader, tg: TargetGrid, grid: gpd.GeoDataFrame, variables: list[str],
              tag: str, min_cell_cov: float = 0.5) -> tuple[dict[str, np.ndarray], pd.DataFrame, np.ndarray]:
    """Run `reader` on every item, return (median per variable, per-scene cell observations, labels)."""
    labels = zonal.label_raster(grid, tg.crs, tg.transform, (tg.height, tg.width))
    n_cells = len(grid)
    tmpdir = path("interim", "_stack", tag, "x").parent
    stacks = {v: np.lib.format.open_memmap(tmpdir / f"{v}.npy", mode="w+", dtype="float32",
                                           shape=(len(items), tg.height, tg.width)) for v in variables}
    obs_rows = []
    used = 0
    for it in items:
        try:
            layers = reader(it, tg)
        except Exception as exc:  # a broken scene must not kill the composite; it is logged and skipped
            log.warning("%s: scene %s skipped: %s", tag, it.id, exc)
            continue
        if layers is None:
            continue
        for v in variables:
            stacks[v][used] = layers[v]
            st = zonal.stats(labels, layers[v], n_cells, prefix="v", which=("mean",))
            keep = st["v_cov"] >= min_cell_cov
            if keep.any():
                obs_rows.append(pd.DataFrame({
                    "grid_id": grid["grid_id"].values[keep.values],
                    "scene_id": it.id,
                    "date": pd.Timestamp(it.datetime).tz_localize(None).normalize(),
                    "platform": it.properties.get("platform"),
                    "variable": v,
                    "value": st.loc[keep, "v_mean"].values,
                    "valid_fraction": st.loc[keep, "v_cov"].values,
                }))
        used += 1
        log.info("%s: %d/%d %s clear=%.2f", tag, used, len(items), it.id,
                 float(np.isfinite(layers[variables[0]]).mean()))
    medians, counts = {}, None
    for v in variables:
        med = np.full((tg.height, tg.width), np.nan, dtype="float32")
        cnt = np.zeros((tg.height, tg.width), dtype="int16")
        for r0 in range(0, tg.height, 256):
            block = np.asarray(stacks[v][:used, r0:r0 + 256])
            with np.errstate(all="ignore"):
                med[r0:r0 + 256] = np.nanmedian(block, axis=0) if used else np.nan
            cnt[r0:r0 + 256] = np.isfinite(block).sum(axis=0)
        medians[v] = med
        if counts is None:
            counts = cnt
        del stacks[v]
    medians["_count"] = counts.astype("float32")
    for f in tmpdir.glob("*.npy"):
        try:
            f.unlink()
        except OSError:
            pass
    obs = pd.concat(obs_rows, ignore_index=True) if obs_rows else pd.DataFrame()
    return medians, obs, labels


def write_tif(arr: np.ndarray, tg: TargetGrid, dest: Path) -> Path:
    with rasterio.open(dest, "w", driver="GTiff", height=tg.height, width=tg.width, count=1, dtype="float32",
                       crs=tg.crs, transform=tg.transform, nodata=np.nan, compress="deflate", tiled=True,
                       predictor=3) as d:
        d.write(arr.astype("float32"), 1)
    return dest


def nd(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(all="ignore"):
        out = (a - b) / (a + b)
    out[~np.isfinite(out)] = np.nan
    return np.clip(out, -1, 1)
