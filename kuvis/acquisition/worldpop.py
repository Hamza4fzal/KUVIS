"""WorldPop Global2 R2025A constrained 100 m population counts (Pakistan) aggregated to cells.

Counts are summed over the ~25 native 100 m pixels whose centres fall in each 500 m cell — a
legitimate aggregation (not a disaggregation). WorldPop counts are modelled estimates
(census-based top-down disaggregation constrained to settled areas), not enumerations.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from .. import provenance
from ..config import cfg, get_logger, path
from ..preprocessing import zonal
from . import stac
from .http import download

log = get_logger("kuvis.worldpop")
URL = ("https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/{y}/PAK/v1/100m/constrained/"
       "pak_pop_{y}_CN_100m_R2025A_v1.tif")


def run(grid: gpd.GeoDataFrame, study: gpd.GeoDataFrame) -> pd.DataFrame:
    bbox = stac.study_bbox_ll(study, 1000)
    out = pd.DataFrame({"grid_id": grid["grid_id"].values})
    files = []
    for y in cfg()["worldpop"]["years"]:
        url = URL.format(y=y)
        try:
            arr, tr, crs, nod = stac.read_window(f"/vsicurl/{url}", bbox)
        except Exception as exc:
            log.warning("range read failed (%s); downloading full file", exc)
            f = download(url, path("raw", "worldpop", url.rsplit("/", 1)[-1]))
            arr, tr, crs, nod = stac.read_window(str(f), bbox)
        arr = arr.astype("float64")
        arr[(arr < 0) | ~np.isfinite(arr)] = np.nan  # outside settled area = nodata in constrained product
        labels = zonal.label_raster(grid, crs, tr, arr.shape)
        s = zonal.sums(labels, np.nan_to_num(arr, nan=0.0), len(grid), prefix="pop")
        out[f"pop_{y}"] = s["pop_sum"].values
        out[f"pop_density_{y}"] = s["pop_sum"].values / (grid["area_m2"].values / 1e6)
        tif = path("interim", f"worldpop_{y}.tif")
        import rasterio
        with rasterio.open(tif, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                           dtype="float32", crs=crs, transform=tr, nodata=np.nan, compress="deflate") as d:
            d.write(arr.astype("float32"), 1)
        files.append(tif)
        log.info("worldpop %d: total in study grid %.2f M", y, out[f"pop_{y}"].sum() / 1e6)
    out.to_parquet(path("interim", "features_population.parquet"))
    provenance.record(
        "worldpop_r2025a",
        status="acquired",
        title="WorldPop Global2 R2025A constrained population counts, Pakistan, 100 m",
        provider="WorldPop, University of Southampton",
        url="https://hub.worldpop.org/project/categories?id=3",
        method="HTTP range read of Karachi window (fallback: full download)",
        files=files,
        license="CC BY 4.0",
        crs="EPSG:4326",
        spatial_resolution="3 arc-seconds (~100 m)",
        temporal_coverage=", ".join(map(str, cfg()["worldpop"]["years"])),
        variables=["population count", "population density (per km²)"],
        limitations="Modelled estimate; constrained to WSF-detected settlement; cells with no detected building have 0 by "
                    "construction (the product's own definition), which KUVIS reports as 'no modelled population'.",
    )
    return out
