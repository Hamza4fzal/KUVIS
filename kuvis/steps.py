"""Thin step wrappers called by scripts/run_pipeline.py. Each loads its inputs from disk."""

from __future__ import annotations

import geopandas as gpd

from .config import path


def _grid() -> gpd.GeoDataFrame:
    return gpd.read_parquet(path("processed", "grid.parquet"))


def _study() -> gpd.GeoDataFrame:
    return gpd.read_parquet(path("processed", "study_area.parquet"))


def step_boundaries():
    from .acquisition import boundaries
    boundaries.build()


def step_grid():
    from .preprocessing.grid import make_grid
    make_grid(_study(), gpd.read_parquet(path("processed", "subdivisions.parquet")))
