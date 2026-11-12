# KUVIS — Data Source Inventory

Status legend: **acquired** (file on disk, registered in `datasets/metadata/registry.json`), **verified** (endpoint
probed and reachable on 2026-11-10, acquisition script written), **not used** (with reason).

All endpoints below were probed from the development machine on **2026-11-10**. Acquisition status is updated from the
machine-readable registry, which the pipeline writes only after a file actually exists on disk
(`kuvis/provenance.py` refuses to mark a dataset "acquired" otherwise).

> **Access route for satellite products.** Google Earth Engine was not configured on the development machine (no
> credentials). Instead of GEE, KUVIS reads the *same* USGS/ESA/NASA/JRC products from **Microsoft Planetary
> Computer** (MPC) STAC as Cloud-Optimized GeoTIFFs. MPC needs no account (URLs are SAS-signed automatically), so
> any marker can re-run the pipeline. Product identity is unchanged (e.g. Landsat Collection 2 Level-2 is the USGS
> product in both catalogs); only the access path differs. This substitution is recorded per dataset.

---

## 1. Study area and administrative units

| Field | Value |
|---|---|
| Dataset | geoBoundaries gbOpen — Pakistan ADM2 and ADM3 |
| Provider | William & Mary geoLab |
| URL | https://www.geoboundaries.org/api/current/gbOpen/PAK/ADM2/ ; …/ADM3/ |
| Method | HTTP download of GeoJSON pinned to release commit `9469f09` |
| Resolution | Vector |
| Temporal | ADM2: boundary year 2019; ADM3: 2017 |
| CRS | EPSG:4326 |
| License | ADM2: Public Domain (source: Wikipedia); ADM3: ODbL 1.0 (source: PBS Census 2017 via Pathways Data) |
| Credentials | None |
| Selected | ADM2 feature `shapeName = "Karachi"` = study area (Karachi Division); ADM3 features >50 % inside it = subdivisions |
| Limitations | ADM2 2019 predates the 2020 creation of Keamari district (split from West); ADM3 2017 census units are sub-district (taluka/town-level) units, not current districts. Boundaries are generalised, not cadastral. |

## 2. Landsat Collection 2 Level-2 (L5 TM, L8 OLI/TIRS, L9 OLI-2/TIRS-2)

| Field | Value |
|---|---|
| Provider | USGS; accessed via MPC collection `landsat-c2-l2` (GEE equivalents: `LANDSAT/LT05/C02/T1_L2`, `LC08`, `LC09`) |
| URL | https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2 |
| Method | STAC search → QA-masked per-scene processing → per-pixel median composite (`kuvis/acquisition/satellite.py`) |
| Resolution | 30 m (thermal: 100 m TIRS / 120 m TM, delivered resampled at 30 m by USGS) |
| Temporal | Epochs 2001 (2000–02, L5 — the USGS archive holds no Landsat-5 scenes over Karachi for 2003–2008), 2010 (2009–11, L5), 2015 (2014–16, L8), 2020 (2019–21, L8), 2024 (2023–25, L8+L9); Apr–Jun each |
| CRS | UTM 42N (EPSG:32642) native |
| License | Public domain |
| Variables | LST °C = ST·0.00341802 + 149.0 − 273.15; SR = DN·0.0000275 − 0.2 → NDVI, NDBI, MNDWI |
| Cleaning | QA_PIXEL fill/dilated cloud/cirrus/cloud/shadow masked; ST_QA uncertainty > 4 K masked; LST outside [−5, 75] °C and reflectance outside (0, 1] treated as invalid; Tier-1 only, scene cloud < 30 %, clearest 8 scenes per WRS path/row per epoch |
| Limitations | LST is *surface* temperature at ~10:30 local time, not air temperature. Landsat 7 deliberately not used (SLC-off gaps since 2003). TM vs OLI index differences include a small sensor effect. Absolute LST varies with weather on acquisition days, so cross-epoch comparison uses *relative* LST. |

## 3. Sentinel-2 MSI Level-2A

| Field | Value |
|---|---|
| Provider | ESA Copernicus; via MPC `sentinel-2-l2a` (GEE: `COPERNICUS/S2_SR_HARMONIZED`) |
| Method | Dry-season (2023-11-01 → 2024-02-29) scenes < 20 % cloud, clearest 8 per MGRS tile; SCL-masked median composite at 20 m |
| Harmonization | MPC data are *not* harmonized: for processing baseline ≥ 04.00 (from 25 Jan 2022) the +1000 DN offset is removed in code — equivalent to GEE's `S2_SR_HARMONIZED` |
| Variables | NDVI (B08,B04), NDWI McFeeters (B03,B08), NDBI (B11,B08), vegetation share (NDVI > 0.3) |
| License | Copernicus free & open licence |
| Limitations | NDBI is a spectral proxy that confuses bare soil with built-up — important in arid Karachi; it is validated against WorldCover built-up share rather than used as a building detector. |

## 4. NASADEM (SRTM reprocessed)

| Field | Value |
|---|---|
| Provider | NASA JPL / LP DAAC; via MPC `nasadem` (GEE: `NASA/NASADEM_HGT/001`; reprocessing of `USGS/SRTMGL1_003`) |
| Resolution / temporal | 1 arc-second (~30 m); February 2000 |
| Processing | Bilinear reprojection to 30 m UTM 42N; Horn slope; per-cell mean/min/max/std elevation, mean & P90 slope; topographic position = cell elevation − mean within 2 km |
| License | Public domain |
| Limitations | Cannot resolve drains, embankments or street-level micro-topography; radar DEM includes some building height in dense areas. |

## 5. ESA WorldCover 2020 (v100) and 2021 (v200)

| Field | Value |
|---|---|
| Provider | ESA; via MPC `esa-worldcover` |
| Resolution | 10 m, EPSG:4326; fractions computed on native pixels |
| License | CC BY 4.0 |
| Limitations | Different algorithm versions in 2020 and 2021 — KUVIS never interprets the difference as change. 2021 is used for current land cover. |

## 6. CHIRPS v3.0 monthly

| Field | Value |
|---|---|
| Provider | UCSB Climate Hazards Center |
| URL | https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/cogs/ (verified: 549 monthly COGs, 1981-01 → 2026-09) |
| Method | HTTP range reads of the Karachi window from each COG |
| Resolution | 0.05° (≈5.5 km); stored at native pixels; cells linked to the pixel containing their centroid |
| License | CC BY 4.0 |
| Limitations | One pixel spans ~100 grid cells; satellite–gauge blend, not a station record; monthly totals cannot capture sub-daily cloudbursts that drive Karachi urban flooding. |

## 7. WorldPop Global2 R2025A constrained 100 m

| Field | Value |
|---|---|
| URL | https://hub.worldpop.org/ — product `G2_CN_POP_R25A_100m`, PAK, years 2015–2030 (verified via REST API) |
| Selected years | 2015, 2020, 2025 |
| Method | Range read of Karachi window; counts summed per cell (aggregation of ~25 native pixels) |
| License | CC BY 4.0 |
| Limitations | Modelled top-down disaggregation of census totals; constrained to detected settlement. Population density is exposure, not social vulnerability. |

## 8. OpenStreetMap (Overpass API)

| Field | Value |
|---|---|
| URL | https://overpass-api.de/api/interpreter |
| Extracted | Roads (highway classes), waterways, coastline, building centroids — snapshot JSON saved to `datasets/raw/osm/` |
| Derived | Road density, major-road density, intersection density (graph nodes with degree ≥ 3), mapped building density, distance to waterways / drains / coast |
| License | ODbL 1.0 |
| Limitations | Spatially uneven completeness; unmapped drains ≠ absent drains; road density ≠ traffic congestion. |

## 9. JRC Global Surface Water v1.4

| Field | Value |
|---|---|
| Provider | EC JRC; via MPC `jrc-gsw` |
| Variables | Occurrence (%), seasonality (months) → mean occurrence, ever-water share, seasonal and permanent water share |
| Temporal | 1984–2021 |
| Limitations | Water occurrence is not urban flooding; used only as context and to exclude permanent water. |

## 10. World Bank — Karachi Land Use/Land Cover (ESA EO4SD-Urban)

| Field | Value |
|---|---|
| URL | https://datacatalog.worldbank.org/search/dataset/0041102 |
| Files (verified, HTTP 200) | `eo4sd_karachi_lulchr_2005.zip` (9.1 MB), `…lulchr_2017.zip` (7.8 MB), `…lulcvhr_2005.zip` (4.1 MB), `…lulcvhr_2017.zip` (4.1 MB), operations report PDF (8.0 MB) from `datacatalogfiles.worldbank.org/ddh-published/0041102/1/…` |
| Format | ESRI Shapefile polygons |
| License | CC BY 4.0 |
| Data-quality note | The `lulcvhr_2017.zip` archive contains files *named* `EO4SD_KARACHI_LULCVHR_2005.*`. Its sizes differ from the 2005 archive; the year is verified from attribute content before use (see DATA_AVAILABILITY.md). |

## 10a. Sentinel-1 RTC and CHIRPS v3 daily (flood-event validation)

| Field | Value |
|---|---|
| Provider | ESA Copernicus Sentinel-1A; radiometric terrain correction by Microsoft Planetary Computer (`sentinel-1-rtc`). Event days from UCSB CHC CHIRPS v3 daily `sat` (`data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/sat/`) |
| Variables | VV γ0 (dB), read from the COG overview at 40 m, 3 × 3 median filtered → per-cell share of newly dark open water (`s1_flood_frac_2020`, `s1_flood_frac_2022`, `s1_flood_frac_max`) |
| Temporal | Passes ≤ 48 h after CHIRPS days with city-mean ≥ 20 mm (2020: 6 days; 2022: 12 days); references from January–May of the same year and orbit |
| License | Copernicus data free and open; RTC product CC BY 4.0; CHIRPS public domain |
| Limitations | Open water only: water between buildings, shallow water on rough surfaces and water drained before the overpass are missed (zero = not detected). Coastal low ground has residual false alarms (leave-one-out QC in `datasets/processed/sentinel1_events.json`). CHIRPS daily timing is disaggregated from pentads, not observed daily. Used only to validate, never to train. |

## 11. Sources investigated but not (yet) used

| Source | Finding | Decision |
|---|---|---|
| Google Earth Engine | No credentials configured; requires a Google Cloud project | Same products read from MPC; GEE optional |
| GPM IMERG | MPC `gpm-imerg-hhr` (half-hourly) | Planned extension for sub-daily rainfall intensity |
| GHSL (BUILT-S, POP, SMOD) | JRC FTP reachable | Planned for built-up history 1975–2030 |
| PMD station data | Requires a formal request to the Climate Data Processing Centre | Not bypassed; not used |
| TomTom Traffic | Requires an API key, commercial terms | Not used; no congestion claims are made |
