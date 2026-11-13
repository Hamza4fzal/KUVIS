"""KUVIS REST API v1. Every response is assembled from database records."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query, Response

from ..core.db import fetch_all, fetch_one, fetch_val, pool
from ..services import layers, report
from ..services.store import store

router = APIRouter(prefix="/api/v1")
GRID_RE = re.compile(r"^KHI_\d{6}$")


def _gid(gid: str) -> str:
    if not GRID_RE.match(gid):
        raise HTTPException(422, "grid id must look like KHI_000123")
    return gid


# ------------------------------------------------------------------ overview
@router.get("/overview")
def overview():
    cells = fetch_one("""SELECT count(*) AS n_cells, count(*) FILTER (WHERE is_land_cell) AS n_land,
                                avg(data_quality_score) AS mean_quality FROM kuvis.spatial_cells""")
    area = fetch_one("SELECT name, area_km2 FROM kuvis.study_areas LIMIT 1")
    exps = fetch_all("SELECT experiment_id, module, algorithm, n_samples, run_utc FROM kuvis.mining_experiments ORDER BY module, experiment_id")
    n_clusters = fetch_val("""SELECT count(*) FROM kuvis.cluster_profiles""")
    n_anom = fetch_val("SELECT count(*) FROM kuvis.anomaly_observations WHERE is_anomaly")
    n_rules = fetch_val("SELECT count(*) FROM kuvis.association_rules")
    epochs = [r["epoch"] for r in fetch_all("SELECT DISTINCT epoch FROM kuvis.temperature_observations ORDER BY 1")]
    sources = fetch_all("SELECT status, count(*) AS n FROM kuvis.data_sources GROUP BY status ORDER BY status")
    fresh = fetch_val("SELECT max(accessed_utc) FROM kuvis.data_sources")
    vul = fetch_one("""SELECT count(*) FILTER (WHERE uvi IS NOT NULL) AS n_scored,
                              count(*) FILTER (WHERE uvi_class = 'Very high') AS n_very_high,
                              avg(evidence_quality) AS mean_evidence FROM kuvis.vulnerability_scores""")
    disc = fetch_all("""SELECT discovery_id, category, title, strength FROM kuvis.discovery_reports
                        ORDER BY strength DESC NULLS LAST LIMIT 6""")
    return {"study_area": area, "cells": cells, "experiments": exps, "n_cluster_groups": n_clusters,
            "n_anomalies": n_anom, "n_rules": n_rules, "landsat_epochs": epochs, "source_status": sources,
            "data_last_accessed": fresh, "vulnerability": vul, "top_discoveries": disc}


# ------------------------------------------------------------------ areas
@router.get("/areas/search")
def search(q: str = Query(..., min_length=1, max_length=80), limit: int = Query(10, le=50)):
    q = q.strip()
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$", q)
    out = []
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        r = fetch_one("""SELECT grid_id, subdivision, lon, lat FROM kuvis.spatial_cells
                         WHERE ST_Contains(geom, ST_SetSRID(ST_Point(%s, %s), 4326))""", (lon, lat))
        if r:
            out.append({"type": "cell", **r, "label": f"{r['grid_id']} ({lat:.4f}, {lon:.4f})"})
    if q.upper().startswith("KHI_"):
        out += [{"type": "cell", **r, "label": r["grid_id"]} for r in fetch_all(
            "SELECT grid_id, subdivision, lon, lat FROM kuvis.spatial_cells WHERE grid_id ILIKE %s ORDER BY grid_id LIMIT %s",
            (q + "%", limit))]
    out += [{"type": "subdivision", "label": r["name"], "name": r["name"], "lon": r["lon"], "lat": r["lat"], "bbox": r["bbox"]}
            for r in fetch_all("""SELECT name, ST_X(ST_PointOnSurface(geom)) AS lon, ST_Y(ST_PointOnSurface(geom)) AS lat,
                                         ARRAY[ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom)] AS bbox
                                  FROM kuvis.administrative_boundaries WHERE name ILIKE %s ORDER BY name LIMIT %s""",
                                 ("%" + q + "%", limit))]
    return out[:limit]


@router.get("/areas/at")
def cell_at(lon: float = Query(..., ge=60, le=75), lat: float = Query(..., ge=20, le=30)):
    r = fetch_one("""SELECT grid_id FROM kuvis.spatial_cells WHERE ST_Contains(geom, ST_SetSRID(ST_Point(%s, %s), 4326))""",
                  (lon, lat))
    if not r:
        raise HTTPException(404, "no analytical cell at this location")
    return r


@router.get("/areas/{grid_id}")
def area(grid_id: str):
    r = fetch_one("""SELECT c.grid_id, c.lon, c.lat, c.subdivision, c.frac_inside, c.is_land_cell, c.dominant_cover,
                            c.data_quality_score, ST_AsGeoJSON(c.geom)::json AS geometry, f.features
                     FROM kuvis.spatial_cells c LEFT JOIN kuvis.cell_features f USING (grid_id) WHERE grid_id = %s""",
                  (_gid(grid_id),))
    if not r:
        raise HTTPException(404, "unknown grid id")
    return r


@router.get("/areas/{grid_id}/report")
def area_report(grid_id: str):
    rep = report.build(_gid(grid_id))
    if rep is None:
        raise HTTPException(404, "unknown grid id")
    return report.np_safe(rep)


@router.get("/areas/{grid_id}/history")
def area_history(grid_id: str):
    return report._history(_gid(grid_id))


@router.get("/areas/{grid_id}/clusters")
def area_clusters(grid_id: str):
    return report._mining(_gid(grid_id))["clusters"]


@router.get("/areas/{grid_id}/anomalies")
def area_anomalies(grid_id: str):
    return report._mining(_gid(grid_id))["anomalies"]


@router.get("/areas/{grid_id}/associations")
def area_associations(grid_id: str):
    return report._mining(_gid(grid_id))["association_rules"]


@router.get("/compare")
def compare(ids: str = Query(..., description="comma-separated grid ids (2–6)"),
            features: str = Query("lst_mean_2024,lst_rel_2024,s2_ndvi_mean,built_frac,pop_density_2025,elev_mean,"
                                  "rain_jjas_normal_mm,road_density_km_km2,ndvi_rel_change_2001_2024")):
    gids = [_gid(g.strip()) for g in ids.split(",") if g.strip()]
    if not 2 <= len(gids) <= 6:
        raise HTTPException(422, "provide 2–6 grid ids")
    return report.np_safe(report.compare(gids, [f.strip() for f in features.split(",") if f.strip()]))


# ------------------------------------------------------------------ map
@router.get("/map/layers")
def map_layers():
    return layers.catalog()


@router.get("/map/boundaries")
def boundaries():
    study = fetch_one("SELECT name, area_km2, ST_AsGeoJSON(geom, 5)::json AS geometry FROM kuvis.study_areas LIMIT 1")
    subs = fetch_all("SELECT name, level, area_km2, ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.0003), 5)::json AS geometry "
                     "FROM kuvis.administrative_boundaries ORDER BY name")
    fc = lambda rows: {"type": "FeatureCollection", "features": [  # noqa: E731
        {"type": "Feature", "geometry": r.pop("geometry"), "properties": r} for r in rows]}
    return {"study_area": fc([study] if study else []), "subdivisions": fc(subs)}


@router.get("/map/metadata")
def map_metadata():
    b = fetch_one("SELECT ST_XMin(geom) x0, ST_YMin(geom) y0, ST_XMax(geom) x1, ST_YMax(geom) y1 FROM kuvis.study_areas LIMIT 1")
    return {"bounds": [b["x0"], b["y0"], b["x1"], b["y1"]] if b else None,
            "cell_size_m": 500, "crs_analysis": "EPSG:32642", "tiles": "/api/v1/tiles/cells/{z}/{x}/{y}.pbf"}


_MAP_COLS: set[str] | None = None


def _map_cols(refresh: bool = False) -> set[str]:
    """Whitelist of map_cells columns (cached; refreshed after a DB reload or when an unknown name is requested,
    since the pipeline can add columns while the API is running)."""
    global _MAP_COLS
    if _MAP_COLS is None or refresh:
        _MAP_COLS = layers.available_columns() - {"grid_id"}
    return _MAP_COLS


@router.get("/tiles/cells/{z}/{x}/{y}.pbf")
def tiles(z: int, x: int, y: int, props: str = ""):
    """Vector tile of grid cells. `props` = comma-separated map_cells columns to include (only those of the
    layers on screen); unknown names are ignored, so the column list is never built from raw user input."""
    if not (0 <= z <= 18 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        raise HTTPException(422, "bad tile")
    requested = [p for p in props.split(",") if p]
    if any(p not in _map_cols() for p in requested):
        _map_cols(refresh=True)
    wanted = [p for p in requested if p in _map_cols()]
    cols = "".join(f", m.{p}" for p in sorted(set(wanted)))
    with pool.connection() as c:
        row = c.execute(f"""
            WITH b AS (SELECT ST_TileEnvelope(%s, %s, %s) AS g),
            t AS (
              SELECT ST_AsMVTGeom(s.geom_3857, b.g, 4096, 16, true) AS geom, s.grid_id{cols}
              FROM kuvis.spatial_cells s JOIN kuvis.map_cells m USING (grid_id), b
              WHERE s.geom_3857 && b.g)
            SELECT ST_AsMVT(t, 'cells', 4096, 'geom') AS mvt FROM t""", (z, x, y)).fetchone()
    data = bytes(row["mvt"]) if row and row["mvt"] else b""
    return Response(data, media_type="application/vnd.mapbox-vector-tile",
                    headers={"Cache-Control": "public, max-age=3600"})


@router.get("/map/hotspots")
def hotspot_points():
    """Centroids of discovered concentrations for map labels (from discovery records)."""
    return fetch_all("SELECT discovery_id, category, title, lon, lat, zoom FROM kuvis.discovery_reports WHERE lon IS NOT NULL")


# ------------------------------------------------------------------ discoveries / research
@router.get("/discoveries")
def discoveries(category: str | None = None, limit: int = Query(100, le=500), offset: int = 0):
    rows = fetch_all("""SELECT discovery_id, category, title, description, period, algorithm, experiment_id, variables,
                               evidence, sources, lon, lat, zoom, strength, cardinality(grid_ids) AS n_cells,
                               ST_AsGeoJSON(geom, 5)::json AS geometry
                        FROM kuvis.discovery_reports WHERE (%(c)s::text IS NULL OR category = %(c)s)
                        ORDER BY strength DESC NULLS LAST LIMIT %(l)s OFFSET %(o)s""",
                     {"c": category, "l": limit, "o": offset})
    total = fetch_val("SELECT count(*) FROM kuvis.discovery_reports WHERE (%(c)s::text IS NULL OR category = %(c)s)", {"c": category})
    return {"total": total, "items": rows}


@router.get("/discoveries/{discovery_id}")
def discovery(discovery_id: str):
    r = fetch_one("SELECT *, ST_AsGeoJSON(geom, 5)::json AS geometry FROM kuvis.discovery_reports WHERE discovery_id = %s",
                  (discovery_id,))
    if not r:
        raise HTTPException(404, "unknown discovery")
    r.pop("geom", None)
    return r


@router.get("/methodology")
def methodology():
    return fetch_all("""SELECT experiment_id, module, algorithm, purpose, input_features, n_samples, parameters, metrics,
                               interpretation_notes, limitations, run_utc, code_version
                        FROM kuvis.mining_experiments ORDER BY module, experiment_id""")


@router.get("/experiments/{experiment_id}")
def experiment(experiment_id: str):
    r = fetch_one("SELECT * FROM kuvis.mining_experiments WHERE experiment_id = %s", (experiment_id,))
    if not r:
        raise HTTPException(404, "unknown experiment")
    r["cluster_profiles"] = fetch_all("SELECT * FROM kuvis.cluster_profiles WHERE experiment_id = %s ORDER BY cluster", (experiment_id,))
    r["rules"] = fetch_all("""SELECT rule_id, antecedents, consequent, support, confidence, lift, leverage, conviction
                              FROM kuvis.association_rules WHERE experiment_id = %s ORDER BY lift DESC LIMIT 200""", (experiment_id,))
    return r


@router.get("/history/epochs")
def history_epochs():
    """City-wide statistics per Landsat epoch (land cells)."""
    return fetch_all("""SELECT t.epoch, count(t.lst_mean) AS n_cells,
                               percentile_cont(0.5) WITHIN GROUP (ORDER BY t.lst_mean) AS lst_median,
                               percentile_cont(0.5) WITHIN GROUP (ORDER BY t.ndvi) AS ndvi_median,
                               percentile_cont(0.5) WITHIN GROUP (ORDER BY t.ndbi) AS ndbi_median,
                               avg(t.ndvi) AS ndvi_mean
                        FROM kuvis.temperature_observations t JOIN kuvis.spatial_cells c USING (grid_id)
                        WHERE c.is_land_cell AND t.lst_cov >= 0.5 GROUP BY t.epoch ORDER BY t.epoch""")


@router.get("/history/rainfall")
def history_rainfall(pixel_id: str | None = None):
    """Annual and monsoon rainfall from CHIRPS (mean over Karachi pixels, or one native pixel)."""
    return fetch_all("""SELECT year, avg(annual) AS annual_mm, avg(jjas) AS jjas_mm FROM (
                          SELECT pixel_id, year, sum(precip_mm) AS annual,
                                 sum(precip_mm) FILTER (WHERE month BETWEEN 6 AND 9) AS jjas, count(precip_mm) AS n
                          FROM kuvis.rainfall_observations WHERE (%(p)s::text IS NULL OR pixel_id = %(p)s)
                          GROUP BY pixel_id, year) s WHERE n = 12 GROUP BY year ORDER BY year""", {"p": pixel_id})


@router.get("/subdivisions")
def subdivisions():
    return fetch_all("""SELECT c.subdivision AS name, count(*) AS n_cells,
                               avg((f.features->>'lst_mean_2024')::float) AS lst_mean_2024,
                               avg((f.features->>'s2_ndvi_mean')::float) AS ndvi,
                               avg((f.features->>'built_frac')::float) AS built_frac,
                               sum((f.features->>'pop_2025')::float) AS pop_2025,
                               avg(v.uvi) AS uvi
                        FROM kuvis.spatial_cells c LEFT JOIN kuvis.cell_features f USING (grid_id)
                        LEFT JOIN kuvis.vulnerability_scores v USING (grid_id)
                        WHERE c.subdivision IS NOT NULL AND c.is_land_cell GROUP BY 1 ORDER BY 1""")


# ------------------------------------------------------------------ data catalogue
@router.get("/data/sources")
def data_sources(q: str | None = None):
    return fetch_all("""SELECT key, title, provider, url, method, status, accessed_utc, license, crs, spatial_resolution,
                               temporal_coverage, variables, limitations, files, extra
                        FROM kuvis.data_sources
                        WHERE (%(q)s::text IS NULL OR title ILIKE '%%' || %(q)s || '%%' OR provider ILIKE '%%' || %(q)s || '%%')
                        ORDER BY title""", {"q": q})


@router.get("/data/status")
def data_status():
    return {"sources": fetch_all("SELECT key, title, status, accessed_utc FROM kuvis.data_sources ORDER BY title"),
            "migrations": fetch_all("SELECT name, applied_utc FROM kuvis.schema_migrations ORDER BY name"),
            "processing_logs": fetch_all("SELECT step, finished_utc, status FROM kuvis.processing_logs ORDER BY id DESC LIMIT 30"),
            "feature_dictionary": fetch_all("SELECT * FROM kuvis.feature_dictionary ORDER BY feature")}


@router.post("/admin/reload-cache", include_in_schema=False)
def reload_cache():
    store.reload()
    _map_cols(refresh=True)
    return {"ok": True}
