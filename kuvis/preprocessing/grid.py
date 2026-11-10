"""Regular analytical grid in the projected CRS.

Cells are square, axis-aligned in UTM 42N, anchored on multiples of the cell size so the grid
is reproducible independent of boundary edits. Each cell stores the fraction of its area that
lies inside the study boundary and the subdivision covering most of it.
"""

from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
from shapely.geometry import box

from ..config import cfg, get_logger, path, projected_crs

log = get_logger("kuvis.grid")


def make_grid(study: gpd.GeoDataFrame, subs: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    g = cfg()["grid"]
    size = float(g["cell_size_m"])
    boundary = study.geometry.iloc[0]
    minx, miny, maxx, maxy = boundary.bounds
    x0, y0 = math.floor(minx / size) * size, math.floor(miny / size) * size
    xs = np.arange(x0, maxx, size)
    ys = np.arange(y0, maxy, size)[::-1]  # north → south so IDs read like raster rows

    cells, rows, cols = [], [], []
    for r, y in enumerate(ys):
        for c_, x in enumerate(xs):
            cells.append(box(x, y, x + size, y + size))
            rows.append(r)
            cols.append(c_)
    grid = gpd.GeoDataFrame({"row": rows, "col": cols}, geometry=cells, crs=projected_crs())
    grid = grid[grid.intersects(boundary)].copy()
    grid["frac_inside"] = grid.geometry.intersection(boundary).area / (size * size)
    grid = grid[grid["frac_inside"] > g["min_fraction_inside"]].reset_index(drop=True)

    grid["grid_id"] = [f"{g['id_prefix']}{i + 1:0{g['id_width']}d}" for i in range(len(grid))]
    grid["area_m2"] = grid.geometry.area
    cent = grid.geometry.centroid
    grid["x_utm"], grid["y_utm"] = cent.x, cent.y
    cent_ll = gpd.GeoSeries(cent, crs=projected_crs()).to_crs("EPSG:4326")
    grid["lon"], grid["lat"] = cent_ll.x.round(6), cent_ll.y.round(6)

    # Administrative attribution: subdivision with the largest overlap.
    ov = gpd.overlay(grid[["grid_id", "geometry"]], subs[["name", "geometry"]], how="intersection", keep_geom_type=True)
    ov["a"] = ov.geometry.area
    best = ov.sort_values("a", ascending=False).drop_duplicates("grid_id").set_index("grid_id")["name"]
    grid["subdivision"] = grid["grid_id"].map(best)

    grid = grid[["grid_id", "row", "col", "x_utm", "y_utm", "lon", "lat", "area_m2", "frac_inside", "subdivision", "geometry"]]
    log.info("grid: %d cells of %.0f m (%d fully inside), %d without subdivision",
             len(grid), size, int((grid.frac_inside > 0.999).sum()), int(grid.subdivision.isna().sum()))
    grid.to_parquet(path("processed", "grid.parquet"))
    return grid
