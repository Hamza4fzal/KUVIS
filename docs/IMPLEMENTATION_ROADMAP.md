# KUVIS — Implementation Roadmap

Status is updated as phases complete. "Done" means executed on real data with outputs on disk; nothing below is
marked done on the basis of code alone.

| Phase | Scope | Status |
|---|---|---|
| 1 Research & data feasibility | Environment audit, source verification, DATA_SOURCES / DATA_AVAILABILITY | Done (2026-11-10) |
| 2 Geospatial preprocessing | Boundary, 500 m grid, terrain, land cover, Sentinel-2, Landsat epochs, CHIRPS, WorldPop, OSM, JRC GSW, EO4SD LULC | In progress |
| 3 Data-mining experiments | Heat (vertical slice) → flood → urbanization → infrastructure | In progress (heat first) |
| 4 Vulnerability intelligence | Indicators, composite index, missing-data policy, sensitivity analysis, combined clusters | Planned |
| 5 Backend & database | PostGIS schema + migrations, loader, FastAPI REST, vector tiles | In progress |
| 6 Frontend | React/MapLibre app: overview, explore map, module pages, report, history, compare, discoveries, methodology, sources | Planned |
| 7 Integration & optimisation | Tiles, caching, loading/error states | Planned |
| 8 Validation & presentation | Re-verify findings, tests, final report, PDF export | Planned |

## Vertical slice (Module B — Urban Heat)

1. Acquire: boundary, grid, WorldCover, Sentinel-2, Landsat 2024 + 2005 epochs, WorldPop, NASADEM
2. Preprocess → cell features
3. Mine: K-means sweep, DBSCAN (feature & geographic), Gi*, Isolation Forest + LOF, correlation
4. Store in PostGIS
5. Serve via FastAPI; render on MapLibre; click a cell → intelligence report

## Extensions after the slice

* Module A (flood): Sentinel-1 change detection for the Aug-2020 / 2022 monsoon events as an independent
  inundation label; association rules (FP-Growth) and spatially-blocked Decision Tree.
* Module C (urbanization): EO4SD 2005→2017 transition matrix; Landsat NDVI/NDBI change; GHSL built-up history.
* Module D (infrastructure): OSM network metrics only — no congestion claims without traffic observations.
* Module E: composite UVI with explicit coverage rule and Monte-Carlo weight sensitivity.
* IMERG sub-daily rainfall for event intensity.

## Known constraints

* Network throughput on the development machine is ~0.2–0.5 MB/s, so satellite acquisition uses the clearest
  5 scenes per tile per period and reads only the Karachi window from each COG; every scene is cached locally after
  first download.
* No Google Earth Engine credentials → Planetary Computer STAC (same products).
* No WSL 2 → portable PostgreSQL 17.7 + PostGIS 3.6.2 instead of Docker.
