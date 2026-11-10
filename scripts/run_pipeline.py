"""KUVIS pipeline runner.

Usage:
    python scripts/run_pipeline.py --list
    python scripts/run_pipeline.py boundaries grid
    python scripts/run_pipeline.py all

Each step is independently executable; steps read their inputs from datasets/ and write outputs
back to datasets/, so a failed step can be re-run without repeating earlier ones.
"""

from __future__ import annotations

import argparse
import importlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kuvis.config import get_logger  # noqa: E402

log = get_logger("kuvis.pipeline")

# step name -> (module, function, description). Order = execution order for "all".
STEPS: dict[str, tuple[str, str, str]] = {
    "boundaries": ("kuvis.steps", "step_boundaries", "Acquire geoBoundaries; build study area + subdivisions"),
    "grid": ("kuvis.steps", "step_grid", "Generate 500 m analytical grid"),
    "dem": ("kuvis.steps", "step_dem", "NASADEM elevation & slope zonal statistics"),
    "worldcover": ("kuvis.steps", "step_worldcover", "ESA WorldCover 2020/2021 class fractions"),
    "sentinel2": ("kuvis.steps", "step_sentinel2", "Sentinel-2 L2A dry-season composite -> NDVI/NDWI/NDBI"),
    "landsat": ("kuvis.steps", "step_landsat", "Landsat C2 L2 LST + NDVI per epoch"),
    "chirps": ("kuvis.steps", "step_chirps", "CHIRPS v3 monthly rainfall at native 0.05° pixels"),
    "worldpop": ("kuvis.steps", "step_worldpop", "WorldPop R2025A population per cell"),
    "osm": ("kuvis.steps", "step_osm", "OpenStreetMap roads, waterways, buildings, coastline"),
    "jrc_gsw": ("kuvis.steps", "step_jrc_gsw", "JRC Global Surface Water occurrence/seasonality"),
    "lulc": ("kuvis.steps", "step_lulc", "World Bank EO4SD Karachi LULC 2005/2017"),
    "features": ("kuvis.steps", "step_features", "Assemble analytical feature tables"),
    "mine_heat": ("kuvis.steps", "step_mine_heat", "Module B — urban heat intelligence"),
    "mine_flood": ("kuvis.steps", "step_mine_flood", "Module A — flood vulnerability intelligence"),
    "mine_urban": ("kuvis.steps", "step_mine_urban", "Module C — urbanization intelligence"),
    "mine_infra": ("kuvis.steps", "step_mine_infra", "Module D — infrastructure intelligence"),
    "vulnerability": ("kuvis.steps", "step_vulnerability", "Module E — composite vulnerability"),
    "discoveries": ("kuvis.steps", "step_discoveries", "Derive discoveries from stored results"),
    "load_db": ("kuvis.steps", "step_load_db", "Load processed outputs into PostGIS"),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("steps", nargs="*")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list or not a.steps:
        for k, (_, _, d) in STEPS.items():
            print(f"  {k:<14} {d}")
        return 0
    names = list(STEPS) if a.steps == ["all"] else a.steps
    for n in names:
        if n not in STEPS:
            log.error("unknown step %s", n)
            return 2
    for n in names:
        mod, fn, desc = STEPS[n]
        log.info("=== %s: %s", n, desc)
        t = time.time()
        getattr(importlib.import_module(mod), fn)()
        log.info("=== %s done in %.1fs", n, time.time() - t)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
