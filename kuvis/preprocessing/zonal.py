"""Exact zonal statistics on a raster's native grid.

Instead of resampling every raster onto the 500 m grid (which smears values and invents
precision), we rasterize grid-cell IDs onto each source raster's own pixel grid and aggregate
pixels per cell. A pixel belongs to the cell containing its centre. For sources coarser than the
cell size (e.g. CHIRPS, ~5.5 km) this module is NOT used; those are assigned, not aggregated.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from affine import Affine
from rasterio.features import rasterize


def label_raster(grid: gpd.GeoDataFrame, crs, transform: Affine, shape: tuple[int, int]) -> np.ndarray:
    """Return an int32 array where each pixel holds (cell index + 1), 0 = outside all cells."""
    g = grid.to_crs(crs)
    shapes = ((geom, i + 1) for i, geom in enumerate(g.geometry))
    return rasterize(shapes, out_shape=shape, transform=transform, fill=0, dtype="int32", all_touched=False)


def _flat(labels: np.ndarray, values: np.ndarray, valid: np.ndarray | None):
    lab = labels.ravel()
    val = values.ravel().astype("float64")
    ok = lab > 0
    ok &= np.isfinite(val)
    if valid is not None:
        ok &= valid.ravel()
    return lab[ok] - 1, val[ok], lab


def stats(labels: np.ndarray, values: np.ndarray, n_cells: int, *, valid: np.ndarray | None = None,
          prefix: str, which=("mean", "std", "min", "max", "p90")) -> pd.DataFrame:
    """Per-cell statistics of `values` over valid pixels.

    Always returns `{prefix}_n` (valid pixel count) and `{prefix}_cov` (valid / total pixels in
    the cell) so downstream code can judge evidence quality. Cells without valid pixels get NaN —
    never zero.
    """
    idx, val, lab_all = _flat(labels, values, valid)
    total = np.bincount(lab_all[lab_all > 0] - 1, minlength=n_cells).astype(float)
    cnt = np.bincount(idx, minlength=n_cells).astype(float)
    out = {f"{prefix}_n": cnt, f"{prefix}_cov": np.divide(cnt, total, out=np.full(n_cells, np.nan), where=total > 0)}
    with np.errstate(invalid="ignore", divide="ignore"):
        s = np.bincount(idx, weights=val, minlength=n_cells)
        mean = s / cnt
        if "mean" in which:
            out[f"{prefix}_mean"] = mean
        if "std" in which:
            s2 = np.bincount(idx, weights=val * val, minlength=n_cells)
            out[f"{prefix}_std"] = np.sqrt(np.maximum(s2 / cnt - mean * mean, 0))
    if any(w in which for w in ("min", "max", "p90", "median")):
        df = pd.DataFrame({"i": idx, "v": val})
        grp = df.groupby("i")["v"]
        for w in ("min", "max", "median"):
            if w in which:
                out[f"{prefix}_{w}"] = grp.agg(w).reindex(range(n_cells)).to_numpy()
        if "p90" in which:
            out[f"{prefix}_p90"] = grp.quantile(0.9).reindex(range(n_cells)).to_numpy()
    res = pd.DataFrame(out)
    for col in res.columns:
        if not col.endswith(("_n", "_cov")):
            res.loc[res[f"{prefix}_n"] == 0, col] = np.nan
    return res


def class_fractions(labels: np.ndarray, classes: np.ndarray, n_cells: int, class_names: dict[int, str],
                    *, nodata: int | None = None, prefix: str) -> pd.DataFrame:
    """Fraction of each categorical class among valid pixels of every cell."""
    lab = labels.ravel()
    cls = classes.ravel()
    ok = lab > 0
    if nodata is not None:
        ok &= cls != nodata
    lab, cls = lab[ok] - 1, cls[ok]
    total = np.bincount(lab, minlength=n_cells).astype(float)
    out = {f"{prefix}_npix": total}
    for code, name in class_names.items():
        c = np.bincount(lab[cls == code], minlength=n_cells).astype(float)
        out[f"{prefix}_{name}"] = np.divide(c, total, out=np.full(n_cells, np.nan), where=total > 0)
    return pd.DataFrame(out)


def sums(labels: np.ndarray, values: np.ndarray, n_cells: int, *, prefix: str) -> pd.DataFrame:
    """Per-cell sum (for count data such as population), with coverage of valid pixels."""
    idx, val, lab_all = _flat(labels, values, None)
    total = np.bincount(lab_all[lab_all > 0] - 1, minlength=n_cells).astype(float)
    cnt = np.bincount(idx, minlength=n_cells).astype(float)
    s = np.bincount(idx, weights=val, minlength=n_cells)
    return pd.DataFrame({f"{prefix}_sum": s, f"{prefix}_npix": total, f"{prefix}_nvalid": cnt})
