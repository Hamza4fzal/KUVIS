"""Location intelligence report assembled from stored analytical outputs.

The report keeps evidence types apart:
  observed / derived / modelled / assigned  → `profile` sections (values with comparisons)
  cluster / anomaly / statistic / association / model prediction → `mining`
  composite index → `vulnerability`
The explanation sentences are generated from those values; every sentence carries the evidence type it
rests on. Nothing in this module contains a pre-written finding.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np

from ..core.db import fetch_all, fetch_one
from .store import store

SECTIONS = [
    ("Terrain", ["elev_mean", "elev_min", "elev_max", "slope_mean", "tpi_2km_m"]),
    ("Land cover", ["built_frac", "veg_frac_wc", "bare_frac", "water_frac", "dominant_cover"]),
    ("Vegetation & surface indices", ["s2_ndvi_mean", "s2_veg_frac", "s2_ndwi_mean", "s2_ndbi_mean"]),
    ("Surface heat", ["lst_mean_2024", "lst_rel_2024", "lst_p90_2024", "lst_rel_change_2001_2024"]),
    ("Rainfall (assigned from ≈5.5 km CHIRPS pixel)", ["rain_annual_normal_mm", "rain_jjas_normal_mm", "rain_jjas_cv",
                                                       "rain_max_month_mm", "rain_jjas_2022_mm", "rain_jjas_2022_anom_pct",
                                                       "rain_aug_2020_mm", "rain_trend_mm_decade"]),
    ("Water history", ["gsw_occurrence_mean", "gsw_seasonal_frac", "gsw_permanent_frac", "dist_coast_m", "dist_waterway_m",
                       "dist_drain_m"]),
    ("Flood events (Sentinel-1 radar)", ["s1_flood_frac_2020", "s1_flood_frac_2022"]),
    ("Population", ["pop_2025", "pop_density_2025", "pop_change_2015_2025"]),
    ("Infrastructure (OpenStreetMap)", ["road_density_km_km2", "major_road_density_km_km2", "intersection_density_km2",
                                        "osm_building_density_km2"]),
    ("Change 2001 → 2024", ["ndvi_rel_change_2001_2024", "ndvi_change_2001_2024", "ndbi_rel_change_2001_2024"]),
]


def _num(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _value_entry(gid: str, feat: str, nbrs: list[str]) -> dict | None:
    df = store.df
    if feat not in df.columns:
        return None
    meta = store.dictionary.get(feat, {})
    raw = df.at[gid, feat]
    val = _num(raw)
    entry = {"feature": feat, "label": meta.get("label", feat), "unit": meta.get("unit"), "kind": meta.get("kind"),
             "source": meta.get("source"), "period": meta.get("period"), "definition": meta.get("definition"),
             "value": val if val is not None else (raw if isinstance(raw, str) else None)}
    if val is None:
        return entry
    s = store.numeric(feat)
    land = s[store.land()].dropna()
    entry["city_median"] = _num(land.median()) if len(land) else None
    entry["city_percentile"] = store.percentile(feat, val)
    sub = df.at[gid, "subdivision"]
    if sub and isinstance(sub, str):
        ss = s[(df.subdivision == sub) & store.land()].dropna()
        entry["subdivision_mean"] = _num(ss.mean()) if len(ss) else None
        entry["subdivision_n"] = int(len(ss))
    # Neighbour comparison only when the value has cell-level support (not assigned from a coarse pixel)
    if meta.get("kind") != "assigned":
        nb = s.reindex(nbrs).dropna()
        entry["neighbours_mean"] = _num(nb.mean()) if len(nb) else None
        entry["neighbours_n"] = int(len(nb))
    return entry


def _mining(gid: str) -> dict:
    clusters = fetch_all("""SELECT m.experiment_id, e.algorithm, e.module, m.cluster, p.name, p.n_cells, p.share, p.profile
                            FROM kuvis.cluster_memberships m JOIN kuvis.mining_experiments e USING (experiment_id)
                            LEFT JOIN kuvis.cluster_profiles p ON p.experiment_id = m.experiment_id AND p.cluster = m.cluster
                            WHERE m.grid_id = %s ORDER BY e.module, m.experiment_id""", (gid,))
    anomalies = fetch_all("""SELECT a.*, e.algorithm, e.module FROM kuvis.anomaly_observations a
                             JOIN kuvis.mining_experiments e USING (experiment_id) WHERE grid_id = %s""", (gid,))
    hotspots = fetch_all("""SELECT h.*, e.algorithm FROM kuvis.hotspot_statistics h
                            JOIN kuvis.mining_experiments e USING (experiment_id) WHERE grid_id = %s""", (gid,))
    rules = fetch_all("""SELECT r.rule_id, r.experiment_id, r.antecedents, r.consequent, r.support, r.confidence, r.lift
                         FROM kuvis.association_rules r
                         JOIN kuvis.cell_transactions t ON t.experiment_id = r.experiment_id AND t.grid_id = %s
                         WHERE r.antecedents <@ t.items ORDER BY r.lift DESC LIMIT 12""", (gid,))
    items = fetch_all("SELECT experiment_id, items FROM kuvis.cell_transactions WHERE grid_id = %s", (gid,))
    trees = fetch_all("""SELECT d.*, e.algorithm, e.metrics->>'balanced_accuracy' AS cv_balanced_accuracy
                         FROM kuvis.decision_tree_results d JOIN kuvis.mining_experiments e USING (experiment_id)
                         WHERE grid_id = %s""", (gid,))
    for r in rules:
        r["holds_for_cell"] = r["consequent"] in next((i["items"] for i in items if i["experiment_id"] == r["experiment_id"]), [])
    return {"clusters": clusters, "anomalies": anomalies, "hotspots": hotspots, "association_rules": rules,
            "cell_items": items, "decision_tree": trees}


def _history(gid: str) -> dict:
    epochs = fetch_all("SELECT * FROM kuvis.temperature_observations WHERE grid_id = %s ORDER BY epoch", (gid,))
    scenes = fetch_all("""SELECT obs_date, platform, value, valid_fraction FROM kuvis.temperature_scene_observations
                          WHERE grid_id = %s AND variable = 'lst' ORDER BY obs_date""", (gid,))
    return {"epochs": epochs, "lst_scenes": scenes}


def _fmt(v, nd=1):
    return f"{v:.{nd}f}" if v is not None else "n/a"


def explain(gid: str, values: dict[str, dict], mining: dict, vul: dict | None) -> list[dict]:
    out = []

    def say(text, evidence):
        out.append({"text": text, "evidence": evidence})

    lst = values.get("lst_mean_2024")
    if lst and lst.get("value") is not None:
        med, pct, nb = lst.get("city_median"), lst.get("city_percentile"), lst.get("neighbours_mean")
        d = lst["value"] - med if med is not None else None
        t = (f"Its 2023–25 pre-monsoon land surface temperature is {_fmt(lst['value'])} °C, "
             f"{_fmt(abs(d))} °C {'above' if d >= 0 else 'below'} the median of Karachi land cells "
             f"(warmer than {_fmt(pct, 0)} % of them)") if d is not None else f"Its LST is {_fmt(lst['value'])} °C"
        if nb is not None:
            dn = lst["value"] - nb
            t += f", and {_fmt(abs(dn))} °C {'warmer' if dn >= 0 else 'cooler'} than cells within 1.5 km"
        say(t + ". This is surface (skin) temperature, not air temperature.", "observed")
    ndvi, built = values.get("s2_ndvi_mean"), values.get("built_frac")
    if ndvi and ndvi.get("value") is not None and built and built.get("value") is not None:
        say(f"Vegetation is {'sparse' if (ndvi.get('city_percentile') or 0) < 33 else 'moderate' if (ndvi.get('city_percentile') or 0) < 67 else 'relatively dense'} "
            f"(NDVI {_fmt(ndvi['value'], 2)}, {_fmt(ndvi.get('city_percentile'), 0)}th percentile) and "
            f"{_fmt(built['value'] * 100, 0)} % of the surface is classified built-up.", "observed")
    for c in mining["clusters"]:
        if c.get("name"):
            share = f", {_fmt((c.get('share') or 0) * 100, 0)} % of analysed cells" if c.get("share") else ""
            say(f"{c['algorithm']} ({c['experiment_id']}) places it in group {c['cluster']} — “{c['name']}”{share}. "
                "Group names summarise the group's average feature values.", "cluster")
        elif c["cluster"] is not None and c["cluster"] >= 0 and "hotspot" in c["experiment_id"]:
            say(f"It belongs to geographic heat concentration #{c['cluster']} found by DBSCAN among the hottest 10 % of cells.",
                "cluster")
    for h in mining["hotspots"]:
        if h["gi_class"] in ("hot", "cold"):
            say(f"Getis–Ord Gi* marks it as part of a statistically significant {h['gi_class']} spot of {h['variable']} "
                f"(z = {_fmt(h['gi_z'], 2)}, pseudo-p = {_fmt(h['gi_p'], 3)}"
                f"{'' if h['gi_class_fdr'] == h['gi_class'] else '; not significant after FDR correction'}).", "statistic")
    for a in mining["anomalies"]:
        if a["is_anomaly"]:
            p = a.get("persistence")
            say(f"{a['algorithm']} flags it as {a['direction']} (anomaly score {_fmt(a['score'], 3)})"
                + (f"; the deviation recurs on {_fmt(p * 100, 0)} % of individual satellite dates" if p is not None else "")
                + ". An anomaly is statistically unusual, not necessarily hazardous.", "anomaly")
    held = [r for r in mining["association_rules"] if r.get("holds_for_cell")]
    if held:
        r = held[0]
        say(f"Its attributes match the mined rule {{{', '.join(r['antecedents'])}}} ⇒ {r['consequent']} "
            f"(confidence {_fmt(r['confidence'] * 100, 0)} %, lift {_fmt(r['lift'], 2)}), and the consequent holds here. "
            "Rules describe co-occurrence across Karachi, not causation.", "association")
    for t in mining["decision_tree"]:
        say(f"The decision tree ({t['experiment_id']}) predicts class {t['predicted']} "
            f"(probability {_fmt(t['probability'], 2)}; observed {t['observed']}) via: {t['decision_path']}.",
            "model prediction")
    if vul and vul.get("uvi") is not None:
        say(f"Its composite vulnerability index is {_fmt(vul['uvi'], 2)} ({vul.get('uvi_class')}, "
            f"{_fmt(vul.get('uvi_rank_pct'), 0)}th percentile; plausible rank range under alternative weights "
            f"{_fmt(vul.get('rank_p05'), 0)}–{_fmt(vul.get('rank_p95'), 0)}), from {vul.get('dimensions_available')} "
            f"dimensions with evidence quality {_fmt(vul.get('evidence_quality'), 2)}.", "composite")
    return out


def build(gid: str) -> dict | None:
    store.ensure()
    if gid not in store.df.index:
        return None
    r = store.df.loc[gid]
    nbrs = store.neighbours(gid)
    sections = []
    values: dict[str, dict] = {}
    for title, feats in SECTIONS:
        entries = []
        for f in feats:
            e = _value_entry(gid, f, nbrs)
            if e is not None:
                entries.append(e)
                values[f] = e
        if entries:
            sections.append({"title": title, "values": entries})
    mining = _mining(gid)
    vul = fetch_one("SELECT * FROM kuvis.vulnerability_scores WHERE grid_id = %s", (gid,))
    indicators = fetch_all("SELECT dimension, value, n_inputs, n_available FROM kuvis.vulnerability_indicators WHERE grid_id = %s", (gid,))
    srcs = {e.get("source") for s in sections for e in s["values"] if e.get("source")}
    limitations = [
        "Land surface temperature is the radiometric temperature of the ground surface at ~10:30 local time, not air temperature.",
        "Rainfall values are assigned from ≈5.5 km CHIRPS pixels; neighbouring cells share the same value.",
        "OpenStreetMap completeness varies; missing drains or roads may be unmapped rather than absent.",
        "Clusters, anomalies and rules are data-mining outputs that describe patterns, not causes or official risk.",
    ]
    if _num(r.get("frac_inside")) is not None and r["frac_inside"] < 0.5:
        limitations.append(f"Only {r['frac_inside'] * 100:.0f} % of this cell lies inside the study boundary.")
    if _num(r.get("data_quality_score")) is not None and r["data_quality_score"] < 0.75:
        limitations.append("Several core inputs are missing for this cell (see data quality).")
    return {
        "grid_id": gid,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "identity": {"grid_id": gid, "lat": _num(r.lat), "lon": _num(r.lon), "subdivision": r.subdivision,
                     "frac_inside": _num(r.frac_inside), "is_land_cell": bool(r.is_land_cell) if r.is_land_cell is not None else None,
                     "dominant_cover": r.dominant_cover, "data_quality_score": _num(r.data_quality_score),
                     "n_neighbours_1500m": len(nbrs)},
        "profile": sections,
        "mining": mining,
        "history": _history(gid),
        "vulnerability": {"score": vul, "indicators": indicators},
        "explanation": explain(gid, values, mining, vul),
        "sources": fetch_all("SELECT key, title, provider, url, license FROM kuvis.data_sources ORDER BY title"),
        "sources_used": sorted(srcs),
        "limitations": limitations,
    }


def compare(ids: list[str], feats: list[str]) -> dict:
    store.ensure()
    out = []
    for gid in ids:
        if gid not in store.df.index:
            continue
        nbrs = store.neighbours(gid)
        out.append({"grid_id": gid, "subdivision": store.df.at[gid, "subdivision"],
                    "lat": _num(store.df.at[gid, "lat"]), "lon": _num(store.df.at[gid, "lon"]),
                    "values": [e for f in feats if (e := _value_entry(gid, f, nbrs)) is not None]})
    return {"cells": out, "features": feats}


def np_safe(o):
    if isinstance(o, dict):
        return {k: np_safe(v) for k, v in o.items()}
    if isinstance(o, list):
        return [np_safe(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o
