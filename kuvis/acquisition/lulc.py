"""World Bank / ESA EO4SD-Urban Karachi Land Use / Land Cover, 2005 and 2017.

Two products, identical CORINE-style nomenclature in both years (so transitions are valid):
  HR  (peri-urban extent)  — classes to level 2 (C_L2), 7 classes in Karachi
  VHR (core urban extent)  — classes to level 4 (C_L4), incl. soil-sealing bands
Both are polygons in WGS 84 / UTM 42N (our analysis CRS — no reprojection).

Per cell we compute exact polygon-area class fractions (of the product-covered part of the cell) and the
share of the cell the product covers. Transition matrices are computed by intersecting the 2005 and 2017
polygons (exact areas). Imperviousness is estimated from the VHR sealing bands using band mid-points —
a derived estimate, labelled as such.

Data-quality note: the published `eo4sd_karachi_lulcvhr_2017.zip` contains files named
`EO4SD_KARACHI_LULCVHR_2005.*`. Their attribute content differs from the 2005 archive (e.g. 674 vs 1,543
construction-site polygons; 12,251 vs 9,955 continuous-urban polygons), so the archive is treated as the 2017
map with a file-naming error, as recorded in provenance.
"""

from __future__ import annotations

import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd

from .. import provenance
from ..config import get_logger, path, projected_crs
from .http import download

log = get_logger("kuvis.lulc")
BASE = "https://datacatalogfiles.worldbank.org/ddh-published/0041102/1/"
FILES = {
    ("hr", 2005): "DR0051283/eo4sd_karachi_lulchr_2005.zip",
    ("hr", 2017): "DR0051284/eo4sd_karachi_lulchr_2017.zip",
    ("vhr", 2005): "DR0051285/eo4sd_karachi_lulcvhr_2005.zip",
    ("vhr", 2017): "DR0051286/eo4sd_karachi_lulcvhr_2017.zip",
}
HR_CLASSES = {11000: "urban_fabric", 12000: "industrial_commercial_transport", 13000: "mine_dump_construction",
              14000: "urban_green", 20000: "agriculture", 32000: "natural_grass_shrub", 51000: "water"}
VHR_L3 = {11100: "continuous_urban", 11200: "discontinuous_urban", 12100: "industrial_commercial", 12200: "roads_rail",
          12300: "port", 12400: "airport", 13300: "construction", 13400: "vacant_land", 14100: "urban_green",
          20000: "agriculture", 31000: "forest", 32000: "natural_grass", 33000: "bare_land", 51000: "water"}
# Mid-point of the published sealing band (fraction of sealed surface). Non-urban classes: documented assumptions.
SEALING_L4 = {11100: 0.90, 11210: 0.65, 11220: 0.30, 11221: 0.40, 12110: 0.80, 12120: 0.80, 12210: 0.90, 12300: 0.80,
              12400: 0.60, 13300: 0.30, 13400: 0.05, 14100: 0.05, 20000: 0.0, 31000: 0.0, 32000: 0.0, 33000: 0.0, 51000: 0.0}
ARTIFICIAL_L1 = 10000


def _read(prod: str, year: int) -> gpd.GeoDataFrame:
    rel = FILES[(prod, year)]
    z = download(BASE + rel, path("raw", "worldbank_lulc", rel.split("/")[1]))
    with zipfile.ZipFile(z) as zf:
        shp = [n for n in zf.namelist() if n.lower().endswith(".shp")][0]
    g = gpd.read_file(f"zip://{z}!{shp}")
    if g.crs is None or g.crs.to_epsg() != 32642:
        g = g.to_crs(projected_crs())
    g["geometry"] = g.geometry.make_valid()
    return g


def _fractions(g: gpd.GeoDataFrame, cells: gpd.GeoDataFrame, code_col: str, classes: dict, prefix: str) -> pd.DataFrame:
    ov = gpd.overlay(cells[["grid_id", "geometry"]], g[[code_col, "geometry"]], how="intersection", keep_geom_type=True)
    ov["a"] = ov.geometry.area
    cov = ov.groupby("grid_id")["a"].sum()
    out = pd.DataFrame(index=cells.grid_id)
    out[f"{prefix}_cover_frac"] = (cov / cells.set_index("grid_id").geometry.area).reindex(out.index)
    piv = ov.groupby(["grid_id", code_col])["a"].sum().unstack(fill_value=0.0)
    for code, name in classes.items():
        col = piv[code] if code in piv.columns else 0.0
        out[f"{prefix}_{name}"] = (col / cov).reindex(out.index)
    return out, ov


def _transitions(g0: gpd.GeoDataFrame, g1: gpd.GeoDataFrame, col: str, classes: dict) -> pd.DataFrame:
    a = g0[[col, "geometry"]].rename(columns={col: "from"})
    b = g1[[col, "geometry"]].rename(columns={col: "to"})
    ov = gpd.overlay(a, b, how="intersection", keep_geom_type=True)
    ov["km2"] = ov.geometry.area / 1e6
    t = ov.groupby(["from", "to"])["km2"].sum().reset_index()
    t["from_name"] = t["from"].map(classes)
    t["to_name"] = t["to"].map(classes)
    return t


def run(grid: gpd.GeoDataFrame, study: gpd.GeoDataFrame) -> pd.DataFrame:
    cells = grid[["grid_id", "geometry"]].copy()
    layers = {(p, y): _read(p, y) for p, y in FILES}
    frames = []
    for y in (2005, 2017):
        hr = layers[("hr", y)]
        fr, _ = _fractions(hr, cells, "C_L2", HR_CLASSES, f"lulc_hr{y}")
        hr["art"] = (hr["C_L1"] == ARTIFICIAL_L1).astype(int)
        b, _ = _fractions(hr, cells, "art", {1: "artificial"}, f"lulc_hr{y}x")
        fr[f"lulc_built_{y}"] = b[f"lulc_hr{y}x_artificial"]
        frames.append(fr)
        vhr = layers[("vhr", y)]
        vhr["C_L3"] = vhr["C_L3"].astype(int)
        fv, ov = _fractions(vhr, cells, "C_L3", VHR_L3, f"lulc_vhr{y}")
        ov2 = gpd.overlay(cells, vhr[["C_L4", "geometry"]], how="intersection", keep_geom_type=True)
        ov2["a"] = ov2.geometry.area
        ov2["seal"] = ov2["C_L4"].astype(int).map(SEALING_L4)
        s = ov2.groupby("grid_id").apply(lambda d: np.average(d.seal, weights=d.a) if d.seal.notna().all() else np.nan,
                                        include_groups=False)
        fv[f"lulc_imperv_{y}"] = s.reindex(fv.index)
        frames.append(fv)
        log.info("LULC %d: HR covers %d cells, VHR covers %d cells", y,
                 int((fr[f"lulc_hr{y}_cover_frac"] > 0.5).sum()), int((fv[f"lulc_vhr{y}_cover_frac"] > 0.5).sum()))
    df = pd.concat(frames, axis=1)
    # Change is only defined where both years cover ≥ 50 % of the cell.
    ok = (df["lulc_hr2005_cover_frac"] >= 0.5) & (df["lulc_hr2017_cover_frac"] >= 0.5)
    df["lulc_built_change_2005_2017"] = np.where(ok, df["lulc_built_2017"] - df["lulc_built_2005"], np.nan)
    okv = (df["lulc_vhr2005_cover_frac"] >= 0.5) & (df["lulc_vhr2017_cover_frac"] >= 0.5)
    df["lulc_imperv_change_2005_2017"] = np.where(okv, df["lulc_imperv_2017"] - df["lulc_imperv_2005"], np.nan)
    df = df.reset_index().rename(columns={"index": "grid_id"})
    df.to_parquet(path("interim", "features_lulc.parquet"))

    th = _transitions(layers[("hr", 2005)], layers[("hr", 2017)], "C_L2", HR_CLASSES)
    th.to_parquet(path("processed", "mining", "lulc_transitions_hr.parquet"))
    lv0, lv1 = layers[("vhr", 2005)], layers[("vhr", 2017)]
    tv = _transitions(lv0, lv1, "C_L3", VHR_L3)
    tv.to_parquet(path("processed", "mining", "lulc_transitions_vhr.parquet"))
    files = [path("raw", "worldbank_lulc", r.split("/")[1]) for r in FILES.values()]
    provenance.record(
        "worldbank_eo4sd_lulc",
        status="acquired",
        title="Karachi Land Use/Land Cover 2005 & 2017 (ESA EO4SD-Urban), core (VHR) and peri-urban (HR)",
        provider="World Bank / ESA EO4SD-Urban",
        url="https://datacatalog.worldbank.org/search/dataset/0041102",
        method="HTTP download of shapefile archives; exact polygon–cell area overlay in UTM 42N",
        files=files,
        license="CC BY 4.0",
        crs="EPSG:32642 (native)",
        spatial_resolution="vector polygons (HR ≈ 10 m-class mapping; VHR ≈ sub-metre-class mapping)",
        temporal_coverage="2005, 2017",
        variables=["class fractions (HR L2, VHR L3)", "artificial-surface share", "imperviousness estimate (VHR L4 sealing mid-points)"],
        limitations="Archive `lulcvhr_2017.zip` contains files named *_2005 but 2017 content (verified from attributes). "
                    "Imperviousness uses band mid-points (estimate). Coverage limited to the EO4SD mapped extents.",
        transitions_hr_km2=float(th.km2.sum()), transitions_vhr_km2=float(tv.km2.sum()),
    )
    return df
