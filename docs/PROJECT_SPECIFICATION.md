# KUVIS — Project Specification

**Karachi Urban Vulnerability Intelligence System** — a geospatial data-mining platform (5th-semester Data
Mining project) that discovers spatial, temporal and environmental patterns associated with urban vulnerability
across Karachi, Sindh, Pakistan, and exposes them through an interactive map application.

## Background and problem

Karachi faces urban flooding (e.g. the 2020 and 2022 monsoons), extreme surface heat, rapid urbanization and
vegetation loss. These are usually studied separately. KUVIS integrates open satellite, terrain, rainfall,
population, land-use and infrastructure data on one 500 m analytical grid and applies data-mining methods to find
relationships that are not visible in any single dataset.

## Research question

Can geospatial data-mining techniques discover previously hidden spatial, temporal and environmental patterns
associated with urban vulnerability across Karachi?

1. RQ1 Can clustering identify geographically meaningful regions with similar vulnerability characteristics?
2. RQ2 Can association-rule mining find recurring combinations of conditions associated with water observations
   and high surface temperature?
3. RQ3 Can anomaly detection find unusual observations relative to geographic and temporal baselines?
4. RQ4 How have built-up surface and vegetation changed across historical periods?
5. RQ5 Which characteristics best distinguish locations with and without observed water / high vulnerability?
6. RQ6 Can indicators be combined into an interpretable multi-dimensional vulnerability index?
7. RQ7 Where do multiple forms of environmental stress overlap?

## Scope

* Area: Karachi Division (geoBoundaries ADM2 2019), 500 m grid in UTM 42N.
* Time: Landsat epochs 2005, 2010, 2015, 2020, 2024 (Apr–Jun); Sentinel-2 dry season 2023/24; CHIRPS 1981–2025;
  WorldPop 2015/2020/2025; EO4SD LULC 2005/2017.
* Out of scope: real-time monitoring, traffic congestion (no observations available), certified risk assessment.

## Deliverables

Reproducible pipeline (`scripts/run_pipeline.py`), PostGIS database, FastAPI service, React/MapLibre application,
experiment records (`research/experiments/`), documentation (this folder and `research/`), tests (`tests/`).

## Non-negotiable rules

No fabricated observations; synthetic data only in unit tests; missing ≠ zero; resolution and uncertainty always
shown; evidence types (observed / derived / modelled / assigned / cluster / statistic / anomaly / association /
model prediction / composite) kept distinct everywhere; no causal claims from associations; LST ≠ air temperature;
road density ≠ congestion; no hard-coded findings.
