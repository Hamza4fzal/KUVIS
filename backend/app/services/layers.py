"""Map-layer catalog. A layer is published only if its column exists in kuvis.map_cells and holds data;
legend breaks are computed from the stored values (quantiles), never typed in."""

from __future__ import annotations

from ..core.db import fetch_all, fetch_one

# id → static description. `prop` is the map_cells column; `scale` sequential|diverging|categorical.
CATALOG: list[dict] = [
    {"id": "lst_2024", "prop": "lst_mean_2024", "group": "Heat", "title": "Land surface temperature (2024)",
     "unit": "°C", "scale": "sequential", "palette": "heat", "kind": "observed",
     "source": "Landsat 8/9 C2 L2 ST", "period": "Apr–Jun 2023–2025 median",
     "description": "Daytime (~10:30) land surface temperature — the ground's skin temperature, not air temperature."},
    {"id": "lst_rel_2024", "prop": "lst_rel_2024", "group": "Heat", "title": "Relative surface heat (2024)",
     "unit": "°C vs city median", "scale": "diverging", "palette": "diverging", "kind": "derived",
     "source": "Landsat 8/9 C2 L2 ST", "period": "Apr–Jun 2023–2025",
     "description": "LST minus the median of all Karachi land cells in the same period."},
    {"id": "lst_rel_change", "prop": "lst_rel_change_2001_2024", "group": "Heat", "title": "Relative heat change 2001→2024",
     "unit": "°C", "scale": "diverging", "palette": "diverging", "kind": "derived",
     "source": "Landsat 5 / 8 / 9", "period": "2000–02 vs 2023–25", "description": "Change in relative LST between epochs."},
    {"id": "heat_kmeans", "prop": "heat_kmeans", "group": "Heat", "title": "Thermal profile clusters (K-means)",
     "unit": "cluster", "scale": "categorical", "kind": "cluster", "source": "KUVIS heat_kmeans experiment",
     "period": "2024", "description": "Cells grouped by LST, vegetation, built-up share and population density."},
    {"id": "heat_hotspot", "prop": "heat_hotspot", "group": "Heat", "title": "Heat concentrations (DBSCAN)",
     "unit": "hotspot", "scale": "categorical", "kind": "cluster", "source": "KUVIS heat_dbscan_geographic",
     "period": "2024", "description": "Geographic concentrations of the hottest 10 % of land cells."},
    {"id": "heat_gi", "prop": "gi_class_code", "group": "Heat", "title": "Heat hot/cold spots (Gi*)",
     "unit": "class", "scale": "categorical", "kind": "statistic", "source": "KUVIS heat_gi_star", "period": "2024",
     "description": "Statistically significant spatial clusters of relative LST (p < 0.05, 499 permutations).",
     "categories": {"-1": "Cold spot", "0": "Not significant", "1": "Hot spot"}},
    {"id": "heat_anomaly", "prop": "if_flag_code", "group": "Heat", "title": "Thermal anomalies (Isolation Forest)",
     "unit": "flag", "scale": "categorical", "kind": "anomaly", "source": "KUVIS heat_isolation_forest", "period": "2024",
     "description": "Cells unusually warm or cool relative to land-cover peers, neighbours and their own history.",
     "categories": {"-1": "Cooler than context", "0": "Not anomalous", "1": "Warmer than context"}},
    {"id": "ndvi", "prop": "s2_ndvi_mean", "group": "Environment", "title": "Vegetation index (NDVI)",
     "unit": "index", "scale": "sequential", "palette": "green", "kind": "derived", "source": "Sentinel-2 L2A",
     "period": "Nov 2023–Feb 2024", "description": "Normalized difference vegetation index, dry-season median."},
    {"id": "ndvi_change", "prop": "ndvi_rel_change_2001_2024", "group": "Urbanization", "title": "Relative NDVI change 2001→2024",
     "unit": "Δ index", "scale": "diverging", "palette": "diverging_green", "kind": "derived", "source": "Landsat 5 / 8 / 9",
     "period": "2000–02 vs 2023–25", "description": "Vegetation gain (green) or loss (brown) relative to the city-wide median of each epoch."},
    {"id": "built", "prop": "built_frac", "group": "Urbanization", "title": "Built-up share", "unit": "fraction",
     "scale": "sequential", "palette": "built", "kind": "observed", "source": "ESA WorldCover v200", "period": "2021",
     "description": "Share of 10 m pixels classified as built-up."},
    {"id": "pop_density", "prop": "pop_density_2025", "group": "Population", "title": "Population density",
     "unit": "persons/km²", "scale": "sequential", "palette": "purple", "kind": "modelled", "source": "WorldPop R2025A",
     "period": "2025", "description": "Modelled population per km² (constrained to settled area)."},
    {"id": "elevation", "prop": "elev_mean", "group": "Terrain", "title": "Elevation", "unit": "m",
     "scale": "sequential", "palette": "terrain", "kind": "observed", "source": "NASADEM", "period": "2000",
     "description": "Mean ground elevation (30 m DEM)."},
    {"id": "road_density", "prop": "road_density_km_km2", "group": "Infrastructure", "title": "Road density",
     "unit": "km/km²", "scale": "sequential", "palette": "grey", "kind": "derived", "source": "OpenStreetMap",
     "period": "snapshot", "description": "Mapped road length per km² — infrastructure supply, not congestion."},
    {"id": "rain_jjas", "prop": "rain_jjas_normal_mm", "group": "Flood", "title": "Monsoon rainfall normal",
     "unit": "mm (Jun–Sep)", "scale": "sequential", "palette": "blue", "kind": "assigned", "source": "CHIRPS v3",
     "period": "1991–2020", "description": "Assigned from ≈5.5 km CHIRPS pixels — not a 500 m measurement."},
    {"id": "water_occurrence", "prop": "gsw_occurrence_mean", "group": "Flood", "title": "Surface-water occurrence",
     "unit": "%", "scale": "sequential", "palette": "blue", "kind": "observed", "source": "JRC GSW v1.4",
     "period": "1984–2021", "description": "How often open water was observed; context, not a flood record."},
    {"id": "sar_flood", "prop": "s1_flood_frac_max", "group": "Flood", "title": "Radar-detected flood water (2020/2022)",
     "unit": "fraction", "scale": "sequential", "palette": "blue", "kind": "observed", "source": "Sentinel-1 RTC + CHIRPS daily",
     "period": "≤ 48 h after the heaviest 2020 and 2022 rain days",
     "description": "Share of the cell that turned into open water after a storm (radar change detection). "
                    "Radar misses most flooding between buildings: 0 means not detected, not dry."},
    {"id": "uvi", "prop": "uvi", "group": "Vulnerability", "title": "Composite vulnerability index (UVI)",
     "unit": "0–1", "scale": "sequential", "palette": "uvi", "kind": "composite", "source": "KUVIS vulnerability",
     "period": "current", "description": "Equal-weight composite of normalized dimension indicators; not an official risk rating."},
    {"id": "uvi_quality", "prop": "evidence_quality", "group": "Vulnerability", "title": "Evidence quality",
     "unit": "0–1", "scale": "sequential", "palette": "grey", "kind": "derived", "source": "KUVIS", "period": "current",
     "description": "Share of indicator inputs available for the cell."},
]


for _e in ("2001", "2010", "2015", "2020", "2024"):
    CATALOG.append({"id": f"hist_lst_rel_{_e}", "prop": f"lst_rel_{_e}", "group": "History",
                    "title": f"Relative surface heat {_e}", "unit": "°C vs city median", "scale": "diverging",
                    "palette": "diverging", "kind": "derived", "source": "Landsat C2 L2 ST", "period": f"Apr–Jun epoch {_e}",
                    "description": "LST minus the median of Karachi land cells in the same epoch."})
    CATALOG.append({"id": f"hist_ls_ndvi_{_e}", "prop": f"ls_ndvi_{_e}", "group": "History",
                    "title": f"Landsat NDVI {_e}", "unit": "index", "scale": "sequential", "palette": "green",
                    "kind": "derived", "source": "Landsat C2 L2 SR", "period": f"Apr–Jun epoch {_e}",
                    "description": "Pre-monsoon median NDVI."})


def available_columns() -> set[str]:
    rows = fetch_all("SELECT column_name FROM information_schema.columns WHERE table_schema='kuvis' AND table_name='map_cells'")
    return {r["column_name"] for r in rows}


def catalog() -> list[dict]:
    cols = available_columns()
    out = []
    for lyr in CATALOG:
        if lyr["prop"] not in cols:
            continue
        p = lyr["prop"]
        st = fetch_one(f"""SELECT count({p}) AS n, count(*) AS total,
                 percentile_cont(ARRAY[0.02,0.2,0.4,0.6,0.8,0.98]) WITHIN GROUP (ORDER BY {p}) AS q,
                 min({p}) AS min, max({p}) AS max FROM kuvis.map_cells""")
        if not st or not st["n"]:
            continue
        legend = {"min": st["min"], "max": st["max"], "quantiles": st["q"]}
        if lyr["scale"] == "categorical":
            cats = fetch_all(f"SELECT {p} AS v, count(*) AS n FROM kuvis.map_cells WHERE {p} IS NOT NULL GROUP BY 1 ORDER BY 1")
            legend["categories"] = [{"value": c["v"], "n": c["n"],
                                     "label": lyr.get("categories", {}).get(str(int(c["v"])), None)} for c in cats]
        out.append({**lyr, "legend": legend, "coverage": st["n"] / st["total"]})
    # Epoch layers of the same variable share one legend, so side-by-side historical maps are comparable.
    groups: dict[str, list[dict]] = {}
    for lyr in out:
        if lyr["group"] == "History":
            groups.setdefault(lyr["id"].rsplit("_", 1)[0], []).append(lyr)
    for same in groups.values():
        qs = [lyr["legend"]["quantiles"] for lyr in same]
        common = [min(q[0] for q in qs)] + [sum(q[i] for q in qs) / len(qs) for i in range(1, len(qs[0]) - 1)] \
            + [max(q[-1] for q in qs)]
        for lyr in same:
            lyr["legend"] = {**lyr["legend"], "quantiles": common, "shared_across_epochs": True}
    return out
