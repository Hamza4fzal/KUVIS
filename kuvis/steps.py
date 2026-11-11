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


def step_dem():
    from .acquisition import terrain
    terrain.run(_grid(), _study())


def step_worldcover():
    from .acquisition import worldcover
    worldcover.run(_grid(), _study())


def step_sentinel2():
    from .acquisition import satellite
    satellite.run_sentinel2(_grid(), _study())


def step_landsat():
    """Set KUVIS_EPOCHS=2024,2001 to process a subset of epochs (results merge with earlier runs)."""
    import os
    from .acquisition import satellite
    ep = os.environ.get("KUVIS_EPOCHS")
    satellite.run_landsat(_grid(), _study(), epochs=ep.split(",") if ep else None)


def step_chirps():
    from .acquisition import chirps
    chirps.run(_grid(), _study())


def step_worldpop():
    from .acquisition import worldpop
    worldpop.run(_grid(), _study())


def step_osm():
    from .acquisition import osm
    osm.run(_grid(), _study())


def step_jrc_gsw():
    from .acquisition import jrc_gsw
    jrc_gsw.run(_grid(), _study())


def step_lulc():
    from .acquisition import lulc
    lulc.run(_grid(), _study())


def step_features():
    from .features import build
    build.run()


def step_mine_heat():
    from .modules import heat
    heat.run()


def step_mine_flood():
    from .modules import flood
    flood.run()


def step_mine_urban():
    from .modules import urban
    urban.run()


def step_mine_infra():
    from .modules import infra
    infra.run()


def step_vulnerability():
    from .modules import vulnerability
    vulnerability.run()


def step_discoveries():
    from .modules import discoveries
    discoveries.run()


def step_load_db():
    from .db import load
    load.run()
