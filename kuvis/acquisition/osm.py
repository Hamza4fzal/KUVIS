"""OpenStreetMap infrastructure via the Overpass API.

Derived per cell: road length density by class, intersection density (road-graph nodes of
degree ≥ 3), building count, and distances from the cell centroid to mapped waterways, mapped
drains/nullahs/canals and the coastline.

Caveats: OSM completeness varies across Karachi (well mapped in the core, sparse in katchi abadis
and peri-urban Malir/Keamari). An unmapped drain is not an absent drain; road density describes
infrastructure supply, not traffic or congestion.
"""

from __future__ import annotations

import json
import time
from collections import Counter

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from .. import provenance
from ..config import cfg, get_logger, path, projected_crs
from . import stac
from .http import UA

log = get_logger("kuvis.osm")

QUERIES = {
    "roads": 'way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"]({bb});out body geom;',
    "waterways": 'way["waterway"]({bb});out body geom;',
    "coastline": 'way["natural"="coastline"]({bb});out body geom;',
    "buildings": 'way["building"]({bb});out center;',
}
DRAIN_TYPES = {"drain", "ditch", "canal"}
MAJOR = {"motorway", "trunk", "primary", "secondary", "motorway_link", "trunk_link", "primary_link", "secondary_link"}


def _overpass(q: str, name: str) -> dict:
    raw = path("raw", "osm", f"{name}.json")
    if raw.exists() and raw.stat().st_size > 100:
        return json.loads(raw.read_text(encoding="utf-8"))
    to = cfg()["osm"]["timeout_s"]
    mirrors = [cfg()["osm"]["overpass_url"], "https://overpass.kumi.systems/api/interpreter",
               "https://overpass.private.coffee/api/interpreter"]
    body = f"[out:json][timeout:{to}];{q}"
    for attempt in range(6):
        url = mirrors[attempt % len(mirrors)]
        try:
            r = requests.post(url, data={"data": body}, headers={"User-Agent": UA}, timeout=to + 60)
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                raw.write_text(r.text, encoding="utf-8")
                log.info("overpass %s: %.1f MB from %s", name, len(r.content) / 1e6, url)
                return r.json()
            status = r.status_code
        except requests.RequestException as exc:
            status = type(exc).__name__
        log.warning("overpass %s via %s failed (%s), retry in %ds", name, url, status, 20 * (attempt + 1))
        time.sleep(20 * (attempt + 1))
    raise RuntimeError(f"Overpass failed for {name}")


def _overpass_tiled(q: str, name: str, bbox, n: int) -> dict:
    """Run a heavy query as n×n bbox tiles (each cached) and merge elements, de-duplicated by OSM id.
    Ways crossing tile edges appear in several tiles with identical full geometry, so de-duplication is exact."""
    merged = path("raw", "osm", f"{name}.json")
    if merged.exists() and merged.stat().st_size > 100:
        return json.loads(merged.read_text(encoding="utf-8"))
    w, s, e, nn = bbox
    xs, ys = np.linspace(w, e, n + 1), np.linspace(s, nn, n + 1)
    seen, elements = set(), []
    for i in range(n):
        for j in range(n):
            bb = f"{ys[j]:.5f},{xs[i]:.5f},{ys[j + 1]:.5f},{xs[i + 1]:.5f}"
            part = _overpass(q.format(bb=bb), f"{name}_t{i}{j}")
            for el in part.get("elements", []):
                if el["id"] not in seen:
                    seen.add(el["id"])
                    elements.append(el)
    data = {"elements": elements, "tiles": n}
    merged.write_text(json.dumps(data), encoding="utf-8")
    return data


def _lines(data: dict) -> gpd.GeoDataFrame:
    recs = []
    for el in data.get("elements", []):
        if el.get("type") == "way" and len(el.get("geometry", [])) >= 2:
            recs.append({"osm_id": el["id"], "nodes": el.get("nodes", []), **{k: v for k, v in el.get("tags", {}).items()
                         if k in ("highway", "waterway", "name", "natural")},
                         "geometry": LineString([(p["lon"], p["lat"]) for p in el["geometry"]])})
    return gpd.GeoDataFrame(recs, geometry="geometry", crs="EPSG:4326")


def run(grid: gpd.GeoDataFrame, study: gpd.GeoDataFrame) -> pd.DataFrame:
    bbox = stac.study_bbox_ll(study, 2000)
    w, s, e, n = bbox
    bb = f"{s},{w},{n},{e}"
    data = {k: (_overpass_tiled(q, k, bbox, 3) if k in ("roads", "buildings") else _overpass(q.format(bb=bb), k))
            for k, q in QUERIES.items()}
    pcrs = projected_crs()
    g = grid.set_index("grid_id")
    cells = gpd.GeoDataFrame({"grid_id": g.index}, geometry=g.geometry.values, crs=pcrs)
    area_km2 = g["area_m2"] / 1e6

    # ---- roads: length per cell by class
    roads = _lines(data["roads"]).to_crs(pcrs)
    roads["major"] = roads["highway"].isin(MAJOR)
    pieces = gpd.overlay(roads[["osm_id", "highway", "major", "geometry"]], cells, how="intersection", keep_geom_type=True)
    pieces["len_km"] = pieces.geometry.length / 1000
    out = pd.DataFrame(index=g.index)
    out["road_km"] = pieces.groupby("grid_id")["len_km"].sum()
    out["road_major_km"] = pieces[pieces.major].groupby("grid_id")["len_km"].sum()
    out[["road_km", "road_major_km"]] = out[["road_km", "road_major_km"]].fillna(0.0)  # mapped-absence: 0 km of mapped road
    out["road_density_km_km2"] = out["road_km"] / area_km2
    out["major_road_density_km_km2"] = out["road_major_km"] / area_km2

    # ---- intersections: node degree in the road graph
    deg = Counter()
    coords = {}
    for el in data["roads"]["elements"]:
        nds, geom = el.get("nodes", []), el.get("geometry", [])
        for i, nd_ in enumerate(nds):
            deg[nd_] += (i > 0) + (i < len(nds) - 1)
            if i < len(geom):
                coords[nd_] = (geom[i]["lon"], geom[i]["lat"])
    inter = [coords[k] for k, d in deg.items() if d >= 3 and k in coords]
    ip = gpd.GeoDataFrame(geometry=[Point(xy) for xy in inter], crs="EPSG:4326").to_crs(pcrs)
    j = gpd.sjoin(ip, cells, predicate="within")
    out["intersections"] = j.groupby("grid_id").size().reindex(g.index).fillna(0)
    out["intersection_density_km2"] = out["intersections"] / area_km2

    # ---- buildings (centroids)
    bpts = [Point(el["center"]["lon"], el["center"]["lat"]) for el in data["buildings"]["elements"] if "center" in el]
    bp = gpd.GeoDataFrame(geometry=bpts, crs="EPSG:4326").to_crs(pcrs)
    jb = gpd.sjoin(bp, cells, predicate="within")
    out["osm_buildings"] = jb.groupby("grid_id").size().reindex(g.index).fillna(0)
    out["osm_building_density_km2"] = out["osm_buildings"] / area_km2

    # ---- distances from centroid
    cent = gpd.GeoSeries([Point(x, y) for x, y in zip(g.x_utm, g.y_utm)], crs=pcrs)

    def nearest_dist(lines: gpd.GeoDataFrame) -> np.ndarray:
        if lines.empty:
            return np.full(len(cent), np.nan)
        tree = STRtree(lines.geometry.values)
        idx = tree.nearest(cent.values)
        return np.array([c.distance(lines.geometry.values[i]) for c, i in zip(cent.values, idx)])

    ww = _lines(data["waterways"]).to_crs(pcrs)
    out["dist_waterway_m"] = nearest_dist(ww)
    out["dist_drain_m"] = nearest_dist(ww[ww["waterway"].isin(DRAIN_TYPES)])
    out["dist_river_stream_m"] = nearest_dist(ww[ww["waterway"].isin({"river", "stream"})])
    coast = _lines(data["coastline"]).to_crs(pcrs)
    out["dist_coast_m"] = nearest_dist(coast)

    out = out.reset_index()
    out.to_parquet(path("interim", "features_osm.parquet"))
    roads[["osm_id", "highway", "major", "geometry"]].to_parquet(path("processed", "osm_roads.parquet"))
    ww[["osm_id", "waterway", "name", "geometry"]].to_parquet(path("processed", "osm_waterways.parquet"))
    provenance.record(
        "osm_overpass",
        status="acquired",
        title="OpenStreetMap roads, waterways, coastline, buildings (Karachi)",
        provider="OpenStreetMap contributors, via Overpass API",
        url="https://overpass-api.de/",
        method="Overpass QL bbox queries (out geom / out center); snapshot saved in datasets/raw/osm",
        files=[path("raw", "osm", f"{k}.json") for k in QUERIES],
        license="ODbL 1.0",
        crs="EPSG:4326 → EPSG:32642",
        spatial_resolution="vector",
        temporal_coverage=f"snapshot {pd.Timestamp.utcnow():%Y-%m-%d}",
        variables=list(out.columns[1:]),
        counts={"roads": len(roads), "waterways": len(ww), "coastline": len(coast), "buildings": len(bp),
                "intersections": len(ip)},
        limitations="Completeness varies spatially; drains under-mapped; road density ≠ traffic congestion.",
    )
    log.info("OSM: %d roads, %d waterways (%d drains), %d buildings, %d intersections",
             len(roads), len(ww), int(ww.waterway.isin(DRAIN_TYPES).sum()), len(bp), len(ip))
    return out
