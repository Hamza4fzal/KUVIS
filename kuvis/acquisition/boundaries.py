"""Study-area and administrative boundaries from geoBoundaries (gbOpen, pinned release).

Karachi Division = PAK ADM2 feature whose shapeName is "Karachi" (boundary year 2019).
Subdivisions = PAK ADM3 features (2017 census, PBS via Pathways Data; ODbL) that fall inside it.
"""

from __future__ import annotations

import geopandas as gpd

from .. import provenance
from ..config import cfg, get_logger, path, projected_crs
from .http import download

log = get_logger("kuvis.boundaries")
BASE = "https://github.com/wmgeolab/geoBoundaries/raw/{commit}/releaseData/gbOpen/PAK/{lvl}/geoBoundaries-PAK-{lvl}.geojson"


def acquire() -> dict[str, gpd.GeoDataFrame]:
    c = cfg()["study_area"]
    out = {}
    for lvl in (c["adm_level"], c["subdivision_level"]):
        url = BASE.format(commit=c["release_commit"], lvl=lvl)
        f = download(url, path("raw", "boundaries", f"geoBoundaries-PAK-{lvl}.geojson"))
        out[lvl] = gpd.read_file(f)
        provenance.record(
            f"geoboundaries_pak_{lvl.lower()}",
            status="acquired",
            title=f"geoBoundaries Pakistan {lvl}",
            provider="William & Mary geoLab — geoBoundaries (gbOpen)",
            url=url,
            method="HTTP download of pinned release commit",
            files=[f],
            license="ADM2: public domain (source: Wikipedia); ADM3: ODbL 1.0 (source: PBS census 2017 via Pathways Data)",
            crs="EPSG:4326",
            spatial_resolution="vector",
            temporal_coverage="ADM2: 2019; ADM3: 2017",
        )
    return out


def build() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Return (study_area, subdivisions) in the projected CRS and write them to processed/."""
    c = cfg()["study_area"]
    layers = acquire()
    adm2 = layers[c["adm_level"]]
    study = adm2[adm2["shapeName"] == c["shape_name"]].copy()
    if len(study) != 1:
        raise RuntimeError(f"expected exactly one {c['shape_name']} feature, found {len(study)}")
    study = study.to_crs(projected_crs())
    study["geometry"] = study.geometry.make_valid()
    study = study[["shapeName", "shapeID", "geometry"]].rename(columns={"shapeName": "name", "shapeID": "source_id"})
    study["area_km2"] = study.geometry.area / 1e6
    log.info("study area: %s, %.1f km²", c["shape_name"], study["area_km2"].iloc[0])

    adm3 = layers[c["subdivision_level"]].to_crs(projected_crs())
    adm3["geometry"] = adm3.geometry.make_valid()
    boundary = study.geometry.iloc[0]
    # Keep subdivisions whose area lies mostly (>50 %) inside Karachi — robust to
    # small sliver mismatches between the two independently produced layers.
    inter = adm3.geometry.intersection(boundary).area
    adm3["frac_inside"] = inter / adm3.geometry.area
    subs = adm3[adm3["frac_inside"] > 0.5].copy()
    subs = subs[["shapeName", "shapeID", "frac_inside", "geometry"]].rename(
        columns={"shapeName": "name", "shapeID": "source_id"}
    )
    subs["area_km2"] = subs.geometry.area / 1e6
    log.info("subdivisions inside study area: %d -> %s", len(subs), sorted(subs["name"]))

    study.to_parquet(path("processed", "study_area.parquet"))
    subs.to_parquet(path("processed", "subdivisions.parquet"))
    return study, subs
