# KUVIS — Data Availability (verified 2026-11-10)

Classification follows the project specification. "Verified" = endpoint probed from the development machine on the
date above. "Acquired" status is authoritative only in `datasets/metadata/registry.json`, which the pipeline writes
after files exist (and the Data Sources page reads).

| Dataset | Classification | Evidence / note |
|---|---|---|
| geoBoundaries PAK ADM2/ADM3 | Successfully acquired | GitHub release `9469f09`, HTTP 200 |
| Landsat C2 L2 (L5, L8, L9) | Alternative source selected → acquired via Planetary Computer | GEE not authenticated; MPC `landsat-c2-l2` serves the same USGS product |
| Landsat 7 | Not used by design | SLC-off striping since 2003; L5 covers 2004–2011, L8 from 2013 |
| Sentinel-2 L2A | Alternative source selected → acquired via Planetary Computer | Harmonization offset applied in code |
| NASADEM (SRTM) | Alternative source selected → acquired via Planetary Computer | NASADEM is the reprocessed SRTM 1″ product |
| ESA WorldCover 2020/2021 | Successfully acquired (via MPC) | |
| CHIRPS v3 monthly | Successfully acquired | 549 COGs (1981-01 → 2026-09) listed; server rate-limits bursts (HTTP 429) → sequential reads with back-off and caching |
| WorldPop R2025A 100 m | Successfully acquired | REST API lists 2015–2030 for PAK |
| OpenStreetMap | Successfully acquired | Overpass API (snapshot saved) |
| JRC GSW v1.4 | Successfully acquired (via MPC) | |
| World Bank EO4SD Karachi LULC 2005/2017 | Successfully acquired | 4 archives + report, HTTP 200; VHR-2017 archive mis-named (`*_2005.*` inside), content verified as 2017 |
| Google Earth Engine | Requires authentication | Needs a Google Cloud project; optional |
| PMD station records (CDPC) | Requires manual request | Not bypassed |
| TomTom Traffic | Requires payment | API key + commercial terms; traffic module limited to infrastructure |
| Sentinel-1 GRD/RTC | Verified available (MPC) — extension not yet run | Urban SAR flood mapping limits documented |
| GPM IMERG | Verified available (MPC `gpm-imerg-hhr`) — extension not yet run | |
| GHSL R2023A | Verified reachable (JRC FTP) — extension not yet run | |

## Practical constraints recorded during Phase 1

* **Bandwidth.** Measured throughput on the development connection was ≈0.2–0.5 MB/s. The pipeline therefore reads
  only the Karachi window from each Cloud-Optimized GeoTIFF (HTTP range requests), limits optical composites to
  the 5 clearest scenes per tile and period, and caches every processed scene so reruns are offline.
* **Database.** Docker Desktop is installed but WSL 2 is not, so the Linux engine cannot start without admin
  rights and a reboot. PostgreSQL 17.7 portable binaries (EDB) + PostGIS 3.6.2 bundle (OSGeo) are used instead;
  `infrastructure/deployment/docker-compose.yml` is provided for machines with Docker.
* **No synthetic data.** Synthetic arrays appear only inside unit tests (`tests/`), never in `datasets/`.
