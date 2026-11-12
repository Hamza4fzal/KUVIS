# KUVIS — Karachi Urban Vulnerability Intelligence System

A geospatial data-mining platform that integrates open satellite, terrain, rainfall, population, land-use and
infrastructure data for Karachi on a 500 m grid, mines it for clusters, hot spots, anomalies, association rules and
classification rules, combines the results into an explainable vulnerability index, and serves everything through an
interactive map application with per-location intelligence reports.

> Historical satellite and open data — not real-time. Analytical outputs are research results, not an official risk
> assessment. Land surface temperature is not air temperature.

## Documentation

| Document | Content |
|---|---|
| [docs/PROJECT_SPECIFICATION.md](docs/PROJECT_SPECIFICATION.md) | Problem, research questions, scope, rules |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and key decisions |
| [docs/IMPLEMENTATION_ROADMAP.md](docs/IMPLEMENTATION_ROADMAP.md) | Phases and status |
| [research/DATA_SOURCES.md](research/DATA_SOURCES.md) | Dataset inventory (provider, resolution, licence, limitations) |
| [research/DATA_AVAILABILITY.md](research/DATA_AVAILABILITY.md) | Acquisition status of every investigated source |
| [research/RESEARCH_METHODOLOGY.md](research/RESEARCH_METHODOLOGY.md) | Spatial framework, preprocessing, methods, evaluation |
| [research/RESULTS.md](research/RESULTS.md) | Results generated from the experiment records |
| [research/reports/FINAL_REPORT.md](research/reports/FINAL_REPORT.md) | Final research report: findings, discussion, limitations |
| [research/literature_review/LITERATURE_REVIEW.md](research/literature_review/LITERATURE_REVIEW.md) | Literature review with verified references |
| `research/experiments/*.json` | Machine-written experiment records (inputs, parameters, metrics) |

## Quick start (Windows, Git Bash)

```bash
# 1. Python environment (3.12)
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt

# 2. Database: PostgreSQL 17 + PostGIS on port 5433
#    either portable binaries (see docs/ARCHITECTURE.md) started with scripts/db.sh start,
#    or: docker compose -f infrastructure/deployment/docker-compose.yml up -d
cp .env.example .env   # set KUVIS_DB_PASSWORD

# 3. Pipeline (each step can be re-run on its own; downloads are cached)
.venv/Scripts/python scripts/run_pipeline.py --list
.venv/Scripts/python scripts/run_pipeline.py boundaries grid dem worldcover sentinel2 landsat \
    chirps worldpop osm jrc_gsw lulc features mine_heat mine_flood mine_urban mine_infra \
    vulnerability discoveries load_db

# 4. API  (docs at http://localhost:8000/docs)
.venv/Scripts/python -m uvicorn backend.app.main:app --port 8000

# 5. Frontend (http://localhost:5173)
cd frontend && npm install && npm run dev

# Tests
.venv/Scripts/python -m pytest tests -q
.venv/Scripts/python scripts/ui_check.py   # Playwright + installed Edge: 12 pages, location report, PDF export
```

No credentials are needed: satellite data are read from Microsoft Planetary Computer (same USGS/ESA products as
Google Earth Engine), rainfall from CHC, population from WorldPop, land use from the World Bank, vectors from OSM.

## Repository layout

```
config/            kuvis.yaml (all analytical parameters), sources_investigated.yaml
kuvis/             acquisition/ preprocessing/ features/ mining/ modules/ db/  — pipeline & mining engine
scripts/           run_pipeline.py, db.sh, generate_results.py
backend/app/       FastAPI: api/v1.py, services/ (report engine, layer catalogue, store), core/db.py
frontend/src/      React + TypeScript + MapLibre: pages/, maps/, reports/, charts/, components/
infrastructure/    database/migrations/*.sql, deployment/docker-compose.yml
research/          data inventory, methodology, experiments/, results
tests/             algorithms/, data/, backend/
```

## Data licences

Landsat & NASADEM: public domain (USGS/NASA) · Sentinel-2: Copernicus open licence · WorldCover, CHIRPS, WorldPop,
EO4SD LULC: CC BY 4.0 · OpenStreetMap: ODbL · JRC GSW: free with attribution · geoBoundaries ADM3: ODbL.
