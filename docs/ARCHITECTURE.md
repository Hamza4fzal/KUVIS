# KUVIS — Architecture

```
 ┌──────────────────────── data sources ────────────────────────┐
 │ geoBoundaries · Planetary Computer STAC (Landsat C2 L2,       │
 │ Sentinel-2 L2A, NASADEM, WorldCover, JRC GSW) · CHIRPS v3     │
 │ COGs · WorldPop R2025A · Overpass (OSM) · World Bank EO4SD    │
 └───────────────┬──────────────────────────────────────────────┘
                 │  kuvis/acquisition/*   (windowed COG reads, provenance registry)
                 ▼
   datasets/raw  →  datasets/interim (per-source cell features, composites)
                 │  kuvis/preprocessing (grid, exact zonal stats on native pixels)
                 │  kuvis/features      (assembly, derived features, dictionary, quality)
                 ▼
   datasets/processed/*.parquet   ──►  kuvis/modules (heat, flood, urban, infra, vulnerability, discoveries)
                 │                         uses kuvis/mining (K-means, DBSCAN, FP-Growth, Isolation Forest,
                 │                         LOF, Decision Tree w/ spatial CV, Moran's I, Gi*)
                 │                         writes research/experiments/*.json + processed/mining/*.parquet
                 ▼
   kuvis/db/load.py  ──►  PostgreSQL 17 + PostGIS 3.6  (schema `kuvis`, numbered SQL migrations)
                 ▼
   backend/ FastAPI  ── REST /api/v1/*  +  Mapbox Vector Tiles via ST_AsMVT
                 ▼
   frontend/ React + TypeScript + Vite + Tailwind + MapLibre GL + TanStack Query + Zustand + Recharts
```

## Key decisions

| Decision | Reason |
|---|---|
| **Planetary Computer instead of Google Earth Engine** | GEE needs a personal Google Cloud project; MPC serves the identical Landsat C2 L2 / S2 L2A / NASADEM / WorldCover / JRC GSW products as COGs without credentials, so the pipeline is reproducible by anyone. Processing happens locally with rasterio. |
| **UTM 42N (EPSG:32642) as analysis CRS** | Karachi (~67°E) lies in zone 42 (66–72°E); Landsat path 152 and Sentinel-2 tiles over Karachi are natively UTM 42N, so composites need no resampling; metres for grid, distances, areas. |
| **Exact zonal statistics on native grids** | Grid-cell IDs are rasterized onto each source's own pixel grid; no up/down-sampling of the data values. Coarse sources (CHIRPS) are *assigned* from the pixel containing the centroid and stored at native pixels. |
| **One fixed target grid per optical sensor** | All scenes are warped to one aligned grid so per-pixel medians are well-defined; per-scene stacks live in disk-backed arrays to keep memory bounded on a 16 GB laptop. |
| **Vector tiles from PostGIS (`ST_AsMVT`) through FastAPI** | Avoids an extra tile server (Martin/pg_tileserv) while still never shipping the whole grid as GeoJSON. Martin can be pointed at the same tables later without schema changes. |
| **Portable PostgreSQL + PostGIS** | Docker Desktop is installed but WSL 2 is not; the portable EDB binaries + OSGeo PostGIS bundle run without admin rights. `infrastructure/deployment/docker-compose.yml` provides the containerised alternative. |
| **SQL migrations instead of Alembic** | The schema is SQL-first (PostGIS types, GiST indexes); numbered SQL files with a `schema_migrations` ledger are transparent and sufficient. |
| **Experiments as JSON first, database second** | Every algorithm run writes `research/experiments/<id>.json` (inputs, params, metrics computed by code, limitations); the DB loader and the Methodology page read those files, so documentation cannot drift from results. |

## Repository layout

```
KUVIS/
  config/kuvis.yaml          all analytical parameters
  kuvis/                     python package: acquisition, preprocessing, features, mining, modules, db
  scripts/run_pipeline.py    step runner (python scripts/run_pipeline.py --list)
  backend/app/               FastAPI service
  frontend/                  React application
  infrastructure/database/   SQL migrations
  datasets/{raw,interim,processed,metadata}   (data not committed; metadata registry is)
  research/                  data inventory, methodology, experiments, reports
  tests/                     pytest suites (algorithms, data, backend)
```
