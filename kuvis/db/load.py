"""Load processed outputs into PostGIS (full, idempotent reload inside one transaction).

Sources: datasets/processed/*.parquet, datasets/processed/mining/*, research/experiments/*.json,
datasets/metadata/registry.json, config/sources_investigated.yaml.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import yaml

from .. import provenance
from ..config import ROOT, get_logger, path
from ..mining.experiment import load_all as load_experiments
from . import migrate
from .conn import connect

log = get_logger("kuvis.load")
P = lambda n: path("processed", n)  # noqa: E731
M = lambda n: path("processed", "mining", n)  # noqa: E731

TABLES = ["discovery_reports", "vulnerability_scores", "vulnerability_indicators", "vulnerability_weights",
          "cell_transactions", "decision_tree_results", "association_rules", "hotspot_statistics", "anomaly_observations",
          "cluster_memberships", "cluster_profiles", "model_evaluation_metrics", "mining_experiments",
          "rainfall_observations", "rainfall_pixels", "temperature_scene_observations", "temperature_observations",
          "feature_dictionary", "cell_features", "waterways", "roads", "spatial_cells", "administrative_boundaries",
          "study_areas", "data_sources", "dataset_versions"]

# Cell-level mining outputs → membership / anomaly / hotspot tables. Extended as modules are added.
MEMBERSHIPS = [  # (experiment_id, cells parquet, column)
    ("heat_kmeans", "heat_cells.parquet", "heat_kmeans"),
    ("heat_dbscan_feature", "heat_cells.parquet", "heat_dbscan_feature"),
    ("heat_dbscan_geographic", "heat_cells.parquet", "heat_hotspot"),
    ("flood_kmeans", "flood_cells.parquet", "flood_kmeans"),
    ("flood_dbscan_feature", "flood_cells.parquet", "flood_dbscan_feature"),
    ("urban_kmeans", "urban_cells.parquet", "urban_kmeans"),
    ("infra_kmeans", "infra_cells.parquet", "infra_kmeans"),
    ("vulnerability_kmeans", "vulnerability_cells.parquet", "combined_kmeans"),
    ("vulnerability_dbscan_geographic", "vulnerability_cells.parquet", "combined_hotspot"),
]
PROFILES = [  # (experiment_id, profile parquet, id column)
    ("heat_kmeans", "heat_kmeans_profiles.parquet", "cluster"),
    ("heat_dbscan_geographic", "heat_hotspots.parquet", "hotspot"),
    ("flood_kmeans", "flood_kmeans_profiles.parquet", "cluster"),
    ("urban_kmeans", "urban_kmeans_profiles.parquet", "cluster"),
    ("infra_kmeans", "infra_kmeans_profiles.parquet", "cluster"),
    ("vulnerability_kmeans", "vulnerability_kmeans_profiles.parquet", "cluster"),
    ("vulnerability_dbscan_geographic", "vulnerability_hotspots.parquet", "hotspot"),
]
ANOMALIES = [  # (experiment_id, parquet, prefix map)
    ("heat_isolation_forest", "heat_cells.parquet",
     {"score": "if_score", "flag": "if_flag", "lof": "lof_flag", "dir": "anom_direction", "persist": "anom_persistence",
      "ctx": ["anom_z_cover", "anom_nb_resid", "anom_hist_resid"]}),
    ("urban_isolation_forest", "urban_cells.parquet",
     {"score": "chg_if_score", "flag": "chg_if_flag", "lof": "chg_lof_flag", "dir": "chg_direction", "persist": None,
      "ctx": ["chg_ndvi", "chg_ndbi", "chg_lst_rel"]}),
]
HOTSPOTS = [("heat_gi_star", "heat_cells.parquet", "lst_mean_2024", "gi_"),
            ("vulnerability_gi_star", "vulnerability_cells.parquet", "uvi", "uvi_gi_")]
MAP_EXTRA = [  # (parquet, column, map column)
    ("heat_cells.parquet", "heat_kmeans", "heat_kmeans"),
    ("heat_cells.parquet", "heat_hotspot", "heat_hotspot"),
    ("flood_cells.parquet", "flood_kmeans", "flood_kmeans"),
    ("urban_cells.parquet", "urban_kmeans", "urban_kmeans"),
    ("infra_cells.parquet", "infra_kmeans", "infra_kmeans"),
    ("vulnerability_cells.parquet", "combined_kmeans", "combined_kmeans"),
]
MAP_FEATURES = ["lst_mean_2024", "lst_rel_2024", "lst_rel_change_2001_2024", "lst_mean_2001", "lst_rel_2001",
                "s2_ndvi_mean", "s2_ndbi_mean", "ndvi_change_2001_2024", "ndvi_rel_change_2001_2024", "built_frac", "veg_frac_wc", "pop_density_2025",
                "elev_mean", "slope_mean", "road_density_km_km2", "intersection_density_km2", "rain_jjas_normal_mm",
                "gsw_occurrence_mean", "data_quality_score", "lulc_built_change_2005_2017"] + \
               [f"{p}_{e}" for e in ("2001", "2010", "2015", "2020", "2024") for p in ("lst_rel", "ls_ndvi")]
MAP_FEATURES = list(dict.fromkeys(MAP_FEATURES))


def _ewkb(geoms, srid: int) -> list[str]:
    return [shapely.to_wkb(shapely.set_srid(g, srid), hex=True, include_srid=True) for g in geoms]


def _clean(v):
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        return None if not math.isfinite(float(v)) else float(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, (list, tuple, np.ndarray)):
        return [_clean(x) for x in v]
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if pd.isna(v) if not isinstance(v, (str, bytes)) else False:
        return None
    return v


def _copy(cur, table: str, cols: list[str], rows) -> int:
    n = 0
    with cur.copy(f"COPY kuvis.{table} ({', '.join(cols)}) FROM STDIN") as cp:
        for r in rows:
            cp.write_row([_clean(x) if not isinstance(x, str) else x for x in r])
            n += 1
    log.info("  %-32s %8d rows", table, n)
    return n


def _jsonb(o) -> str:
    return json.dumps(_clean(o), ensure_ascii=False, default=str)


def run() -> None:
    migrate.run()
    grid = gpd.read_parquet(P("grid.parquet"))
    feats = pd.read_parquet(P("cell_features.parquet"))
    study = gpd.read_parquet(P("study_area.parquet")).to_crs(4326)
    subs = gpd.read_parquet(P("subdivisions.parquet")).to_crs(4326)

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET search_path = kuvis, public")
        cur.execute("TRUNCATE " + ", ".join(f"kuvis.{t}" for t in TABLES) + " RESTART IDENTITY CASCADE")
        cur.execute("DROP TABLE IF EXISTS kuvis.map_cells")

        # -------- geography
        _copy(cur, "study_areas", ["name", "source_id", "area_km2", "geom"],
              zip(study.name, study.source_id, study.area_km2, _ewkb(study.geometry.apply(lambda g: shapely.MultiPolygon([g]) if g.geom_type == "Polygon" else g), 4326)))
        _copy(cur, "administrative_boundaries", ["name", "level", "source_id", "area_km2", "geom"],
              zip(subs.name, ["ADM3"] * len(subs), subs.source_id, subs.area_km2,
                  _ewkb(subs.geometry.apply(lambda g: shapely.MultiPolygon([g]) if g.geom_type == "Polygon" else g), 4326)))
        g4326 = grid.to_crs(4326)
        g3857 = grid.to_crs(3857)
        f_idx = feats.set_index("grid_id")
        _copy(cur, "spatial_cells", ["grid_id", "row_idx", "col_idx", "lon", "lat", "x_utm", "y_utm", "area_m2", "frac_inside",
                                     "subdivision", "is_land_cell", "dominant_cover", "data_quality_score", "geom", "geom_3857"],
              zip(grid.grid_id, grid.row, grid.col, grid.lon, grid.lat, grid.x_utm, grid.y_utm, grid.area_m2, grid.frac_inside,
                  grid.subdivision, f_idx.reindex(grid.grid_id)["is_land_cell"].values,
                  f_idx.reindex(grid.grid_id).get("dominant_cover", pd.Series([None] * len(grid))).values,
                  f_idx.reindex(grid.grid_id)["data_quality_score"].values,
                  _ewkb(g4326.geometry, 4326), _ewkb(g3857.geometry, 3857)))
        skip = {"geometry", "row", "col", "x_utm", "y_utm", "area_m2", "data_quality_inputs"}
        fcols = [c for c in feats.columns if c not in skip and c != "grid_id"]
        _copy(cur, "cell_features", ["grid_id", "features"],
              ((r.grid_id, _jsonb({c: getattr(r, c) for c in fcols})) for r in feats.itertuples(index=False)))
        fd = json.loads(P("feature_dictionary.json").read_text(encoding="utf-8"))
        _copy(cur, "feature_dictionary", ["feature", "label", "unit", "source", "period", "kind", "definition"],
              ((k, v["label"], v["unit"], v["source"], v["period"], v["kind"], v["definition"]) for k, v in fd.items()))
        for name, table, cols in [("osm_roads.parquet", "roads", ["osm_id", "highway", "major"]),
                                  ("osm_waterways.parquet", "waterways", ["osm_id", "waterway", "name"])]:
            if P(name).exists():
                g = gpd.read_parquet(P(name)).to_crs(4326)
                g = g[g.geometry.geom_type == "LineString"]
                _copy(cur, table, cols + ["geom"], zip(*[g[c] for c in cols], _ewkb(g.geometry, 4326)))

        # -------- observations
        if P("cell_epochs.parquet").exists():
            ep = pd.read_parquet(P("cell_epochs.parquet"))
            cols = [c for c in ["lst_mean", "lst_rel", "lst_p90", "lst_cov", "lst_nobs", "ndvi", "ndbi", "mndwi"] if c in ep]
            ep = ep.dropna(subset=cols, how="all")
            _copy(cur, "temperature_observations", ["grid_id", "epoch"] + cols, ep[["grid_id", "epoch"] + cols].itertuples(index=False))
        if P("landsat_scene_observations.parquet").exists():
            so = pd.read_parquet(P("landsat_scene_observations.parquet"))
            so = so[so.variable.isin(["lst", "ndvi"])]
            _copy(cur, "temperature_scene_observations", ["grid_id", "scene_id", "obs_date", "platform", "variable", "value", "valid_fraction"],
                  zip(so.grid_id, so.scene_id, so.date.dt.date, so.platform, so.variable, so.value, so.valid_fraction))
        if P("chirps_pixels.parquet").exists():
            px = gpd.read_parquet(P("chirps_pixels.parquet"))
            _copy(cur, "rainfall_pixels", ["pixel_id", "lon", "lat", "geom"], zip(px.pixel_id, px.lon, px.lat, _ewkb(px.geometry, 4326)))
            mo = pd.read_parquet(P("chirps_monthly.parquet"))
            _copy(cur, "rainfall_observations", ["pixel_id", "year", "month", "precip_mm"], mo.itertuples(index=False))

        # -------- experiments
        exps = {e["experiment_id"]: e for e in load_experiments()}
        _copy(cur, "mining_experiments", ["experiment_id", "module", "algorithm", "purpose", "input_features", "n_samples", "parameters",
                                          "metrics", "results", "interpretation_notes", "limitations", "run_utc", "code_version"],
              ((e["experiment_id"], e["module"], e["algorithm"], e["purpose"], _jsonb(e["input_features"]), e["n_samples"],
                _jsonb(e["parameters"]), _jsonb(e["metrics"]), _jsonb(e["results"]), _jsonb(e["interpretation_notes"]),
                _jsonb(e["limitations"]), e["run_utc"], e["code_version"]) for e in exps.values()))
        metric_rows = []
        for e in exps.values():
            def walk(prefix, o):
                if isinstance(o, dict):
                    for k, v in o.items():
                        walk(f"{prefix}.{k}" if prefix else k, v)
                elif isinstance(o, (int, float)) and not isinstance(o, bool) and o is not None:
                    metric_rows.append((e["experiment_id"], prefix, float(o)))
            walk("", {k: v for k, v in e["metrics"].items() if not isinstance(v, list)})
        _copy(cur, "model_evaluation_metrics", ["experiment_id", "metric", "value"], metric_rows)

        cache: dict[str, pd.DataFrame] = {}

        def cells(name):
            if name not in cache:
                cache[name] = pd.read_parquet(M(name)) if M(name).exists() else None
            return cache[name]

        for exp, prof_file, idcol in PROFILES:
            if exp in exps and M(prof_file).exists():
                p = pd.read_parquet(M(prof_file))
                _copy(cur, "cluster_profiles", ["experiment_id", "cluster", "name", "n_cells", "share", "profile"],
                      ((exp, int(r[idcol]), r.get("name") or _hotspot_name(r), int(r["n_cells"]), r.get("share"),
                        _jsonb({k: v for k, v in r.items() if k not in (idcol, "name", "n_cells", "share")}))
                       for r in p.to_dict("records")))
        mem = []
        for exp, f, col in MEMBERSHIPS:
            c = cells(f)
            if exp in exps and c is not None and col in c:
                d = c[c[col].notna() & (c[col] >= -1)]
                mem += [(g, exp, int(v)) for g, v in zip(d.grid_id, d[col])]
        _copy(cur, "cluster_memberships", ["grid_id", "experiment_id", "cluster"], mem)
        an = []
        for exp, f, m in ANOMALIES:
            c = cells(f)
            if exp in exps and c is not None and m["score"] in c:
                d = c[c[m["score"]].notna()]
                for r in d.to_dict("records"):
                    an.append((r["grid_id"], exp, r[m["score"]], bool(r[m["flag"]]), bool(r.get(m["lof"]) or False),
                               r.get(m["dir"]), r.get(m["persist"]) if m["persist"] else None,
                               _jsonb({k: r.get(k) for k in m["ctx"]})))
        _copy(cur, "anomaly_observations", ["grid_id", "experiment_id", "score", "is_anomaly", "lof_flag", "direction",
                                            "persistence", "context"], an)
        hs = []
        for exp, f, var, pre in HOTSPOTS:
            c = cells(f)
            if exp in exps and c is not None and f"{pre}z" in c:
                d = c[c[f"{pre}z"].notna()]
                hs += list(zip(d.grid_id, [exp] * len(d), [var] * len(d), d[f"{pre}z"], d[f"{pre}p"], d[f"{pre}q_fdr"],
                               d[f"{pre}class"], d[f"{pre}class_fdr"]))
        _copy(cur, "hotspot_statistics", ["grid_id", "experiment_id", "variable", "gi_z", "gi_p", "gi_q_fdr", "gi_class", "gi_class_fdr"], hs)

        # association rules + transactions (any *_rules.parquet / *_transactions.parquet)
        for rf in sorted(M("x").parent.glob("*_rules.parquet")):
            exp = rf.stem.replace("_rules", "")
            if exp not in exps:
                continue
            r = pd.read_parquet(rf)
            _copy(cur, "association_rules", ["experiment_id", "antecedents", "consequent", "support", "confidence", "lift",
                                             "leverage", "conviction", "n_items"],
                  zip([exp] * len(r), r.antecedents.apply(list), r.consequent, r.support, r.confidence, r.lift, r.leverage,
                      r.conviction.replace([np.inf], np.nan), r.n_items))
            tf = M(f"{exp}_transactions.parquet")
            if tf.exists():
                t = pd.read_parquet(tf)
                _copy(cur, "cell_transactions", ["grid_id", "experiment_id", "items"],
                      zip(t.grid_id, [exp] * len(t), t["items"].apply(list)))
        for tf in sorted(M("x").parent.glob("*_tree_results.parquet")):
            exp = tf.stem.replace("_results", "")
            if exp in exps:
                t = pd.read_parquet(tf)
                _copy(cur, "decision_tree_results", ["grid_id", "experiment_id", "observed", "predicted", "probability", "decision_path"],
                      zip(t.grid_id, [exp] * len(t), t.observed, t.predicted, t.probability, t.decision_path))

        # -------- vulnerability
        if M("vulnerability_cells.parquet").exists():
            v = pd.read_parquet(M("vulnerability_cells.parquet"))
            w = json.loads(M("vulnerability_weights.json").read_text(encoding="utf-8"))
            _copy(cur, "vulnerability_weights", ["scheme", "dimension", "weight"],
                  ((s, d, wt) for s, dims in w.items() for d, wt in dims.items()))
            ind = pd.read_parquet(M("vulnerability_indicators.parquet"))
            _copy(cur, "vulnerability_indicators", ["grid_id", "dimension", "value", "n_inputs", "n_available"], ind.itertuples(index=False))
            _copy(cur, "vulnerability_scores", ["grid_id", "uvi", "uvi_rank_pct", "uvi_class", "evidence_quality", "dimensions_available",
                                                "rank_p05", "rank_p95", "combined_kmeans", "explanation", "factors"],
                  ((r["grid_id"], r.get("uvi"), r.get("uvi_rank_pct"), r.get("uvi_class"), r.get("evidence_quality"),
                    r.get("dimensions_available"), r.get("rank_p05"), r.get("rank_p95"),
                    None if pd.isna(r.get("combined_kmeans")) else int(r["combined_kmeans"]), r.get("explanation"),
                    _jsonb(r.get("factors_json") and json.loads(r["factors_json"]))) for r in v.to_dict("records")))

        # -------- discoveries
        if M("discoveries.json").exists():
            ds = json.loads(M("discoveries.json").read_text(encoding="utf-8"))
            _copy(cur, "discovery_reports", ["discovery_id", "category", "title", "description", "period", "algorithm", "experiment_id",
                                             "variables", "evidence", "sources", "grid_ids", "lon", "lat", "zoom", "strength", "geom"],
                  ((d["discovery_id"], d["category"], d["title"], d["description"], d["period"], d["algorithm"], d["experiment_id"],
                    _jsonb(d["variables"]), _jsonb(d["evidence"]), _jsonb(d["sources"]), d["grid_ids"], d.get("lon"), d.get("lat"),
                    d.get("zoom"), d.get("strength"), d.get("geom_ewkb")) for d in ds))

        # -------- map_cells (wide numeric table for vector tiles)
        mc = feats[["grid_id"] + [c for c in MAP_FEATURES if c in feats]].copy()
        for f, col, out_col in MAP_EXTRA:
            c = cells(f)
            if c is not None and col in c:
                mc = mc.merge(c[["grid_id", col]].rename(columns={col: out_col}), on="grid_id", how="left")
        hc = cells("heat_cells.parquet")
        if hc is not None:
            hc = hc.assign(gi_class_code=hc.gi_class.map({"hot": 1, "cold": -1, "not significant": 0}),
                           if_flag_code=np.where(hc.if_flag.astype(bool),
                                                 np.where(hc.anom_direction == "warmer than context", 1, -1), 0))
            mc = mc.merge(hc[["grid_id", "gi_class_code", "if_flag_code"]], on="grid_id", how="left")
        if M("vulnerability_cells.parquet").exists():
            vv = pd.read_parquet(M("vulnerability_cells.parquet"))
            keep = [c for c in ["uvi", "evidence_quality", "uvi_rank_pct", "dim_flood", "dim_heat", "dim_urbanization",
                                "dim_environmental", "dim_infrastructure"] if c in vv]
            mc = mc.merge(vv[["grid_id"] + keep], on="grid_id", how="left")
        num = [c for c in mc.columns if c != "grid_id"]
        cur.execute("CREATE TABLE kuvis.map_cells (grid_id text PRIMARY KEY REFERENCES kuvis.spatial_cells(grid_id) ON DELETE CASCADE, "
                    + ", ".join(f"{c} real" for c in num) + ")")
        _copy(cur, "map_cells", ["grid_id"] + num, mc[["grid_id"] + num].itertuples(index=False))

        # -------- data sources (acquired registry + investigated alternatives)
        reg = provenance.all_entries()
        known = {"key", "title", "provider", "url", "method", "status", "accessed_utc", "license", "crs", "spatial_resolution",
                 "temporal_coverage", "variables", "limitations", "files"}
        rows = [(k, e["title"], e["provider"], e["url"], e["method"], e["status"], e["accessed_utc"], e.get("license"), e.get("crs"),
                 e.get("spatial_resolution"), e.get("temporal_coverage"), _jsonb(e.get("variables")), e.get("limitations"),
                 _jsonb(e.get("files")), _jsonb({x: y for x, y in e.items() if x not in known}))
                for k, e in reg.items()]
        inv = yaml.safe_load((ROOT / "config" / "sources_investigated.yaml").read_text(encoding="utf-8"))
        rows += [(s["key"], s["title"], s["provider"], s["url"], None, s["status"], "2026-11-10T00:00:00+00:00", None, None,
                  None, None, None, s["limitations"], None, None) for s in inv if s["key"] not in reg]
        _copy(cur, "data_sources", ["key", "title", "provider", "url", "method", "status", "accessed_utc", "license", "crs",
                                    "spatial_resolution", "temporal_coverage", "variables", "limitations", "files", "extra"], rows)
        _copy(cur, "dataset_versions", ["key", "version", "sha256"],
              ((k, e["accessed_utc"], (e.get("files") or [{}])[0].get("sha256")) for k, e in reg.items()))
        cur.execute("INSERT INTO kuvis.processing_logs(step, started_utc, finished_utc, status, message) "
                    "VALUES ('load_db', now(), now(), 'success', %s)", (f"{len(grid)} cells, {len(exps)} experiments",))
        cur.execute("ANALYZE")
    log.info("database load complete")


def _hotspot_name(r: dict) -> str:
    top = r.get("top_subdivision")
    return f"Concentration #{int(r.get('hotspot', 0))}" + (f" — {top}" if top else "")
