# KUVIS — Implementation Roadmap

Status is updated as phases complete. "Done" means executed on real data with outputs on disk; nothing below is
marked done on the basis of code alone.

| Phase | Scope | Status |
|---|---|---|
| 1 Research & data feasibility | Environment audit, source verification, DATA_SOURCES / DATA_AVAILABILITY | Done (2026-11-10) |
| 2 Geospatial preprocessing | Boundary, 500 m grid, terrain, land cover, Sentinel-2, Landsat epochs (2001/2010/2015/2020/2024), CHIRPS, WorldPop, OSM, JRC GSW, EO4SD LULC | Done (2026-11-11) |
| 3 Data-mining experiments | Heat, flood, urbanization, infrastructure: K-means, DBSCAN, Gi*, FP-Growth, Isolation Forest + LOF, Decision Tree, Theil–Sen | Done (2026-11-11), 23 experiment records |
| 4 Vulnerability intelligence | 4-dimension UVI (traffic excluded, no data), coverage rule, 1,000-draw weight sensitivity, stress regimes, 53 discoveries | Done (2026-11-11) |
| 5 Backend & database | PostGIS schema + migrations, loader, FastAPI REST, MVT vector tiles | Done (2026-11-11) |
| 6 Frontend | React/MapLibre app: 12 screens incl. location report, history, compare, discoveries, methodology, sources | Done (2026-11-12) |
| 7 Integration & optimisation | Tile props whitelist, source rebuild per layer set, shared legends, loading/error states | Done (2026-11-12) |
| 8 Validation & presentation | 27 pytest tests; Playwright browser test of 12 pages + report + PDF export; final report (`research/reports/FINAL_REPORT.md`) | Done (2026-11-12) |
| 9 Extension: Sentinel-1 flood validation | CHIRPS daily event days → Sentinel-1 RTC post-event change detection (2020, 2022) with leave-one-out false-alarm QC; out-of-sample check of the flood tree, rules and profiles (`flood_sar_validation`) | Done (2026-11-12) |

### Not done (documented, not acquired)

* IMERG sub-daily rainfall (available on MPC, not added); GHSL built-up history; night-time LST.
* Traffic / congestion: no open observations exist for Karachi, so Module D covers infrastructure supply only.

## Vertical slice (Module B — Urban Heat)

1. Acquire: boundary, grid, WorldCover, Sentinel-2, Landsat 2024 + 2001 baseline epochs (no usable Landsat 5 scenes for 2005), WorldPop, NASADEM
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
