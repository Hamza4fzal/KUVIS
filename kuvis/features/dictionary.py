"""Feature dictionary: definition, unit, source and temporal reference of every analytical feature.

`kind` separates evidence types throughout the app:
  observed  – direct (satellite/model product) observation aggregated to the cell
  derived   – computed from observations (indices, distances, changes)
  modelled  – third-party modelled estimate (e.g. WorldPop)
  assigned  – coarse-resolution value assigned to the cell from a larger native pixel
"""

F = {}


def _f(key, label, unit, source, period, kind, definition):
    F[key] = {"label": label, "unit": unit, "source": source, "period": period, "kind": kind, "definition": definition}


# Geography
_f("lat", "Latitude", "°", "Grid", "—", "derived", "Cell centroid latitude (WGS84)")
_f("lon", "Longitude", "°", "Grid", "—", "derived", "Cell centroid longitude (WGS84)")
_f("frac_inside", "Share inside Karachi boundary", "fraction", "geoBoundaries ADM2", "2019", "derived",
   "Area of cell ∩ study boundary / cell area")
_f("subdivision", "Administrative subdivision", "—", "geoBoundaries ADM3 (PBS 2017)", "2017", "derived",
   "Subdivision with the largest overlap")
# Terrain
_f("elev_mean", "Mean elevation", "m", "NASADEM", "2000", "observed", "Mean of 30 m DEM pixels in the cell")
_f("elev_min", "Minimum elevation", "m", "NASADEM", "2000", "observed", "Minimum of 30 m DEM pixels")
_f("elev_max", "Maximum elevation", "m", "NASADEM", "2000", "observed", "Maximum of 30 m DEM pixels")
_f("elev_std", "Elevation variability", "m", "NASADEM", "2000", "derived", "Standard deviation of DEM pixels")
_f("slope_mean", "Mean slope", "°", "NASADEM", "2000", "derived", "Horn-method slope on 30 m UTM DEM, cell mean")
_f("slope_p90", "Slope (90th pct.)", "°", "NASADEM", "2000", "derived", "90th percentile of pixel slopes")
_f("tpi_2km_m", "Topographic position", "m", "NASADEM", "2000", "derived",
   "Cell mean elevation − mean elevation of cells within 2 km (negative = local depression)")
# Land cover
_f("built_frac", "Built-up share", "fraction", "ESA WorldCover v200", "2021", "observed", "Share of 10 m pixels classed built-up")
_f("veg_frac_wc", "Vegetation share", "fraction", "ESA WorldCover v200", "2021", "observed",
   "Share of tree+shrub+grass+crop+mangrove pixels")
_f("water_frac", "Water share", "fraction", "ESA WorldCover v200", "2021", "observed", "Share of water+wetland pixels")
_f("bare_frac", "Bare-ground share", "fraction", "ESA WorldCover v200", "2021", "observed", "Share of bare/sparse pixels")
_f("dominant_cover", "Dominant land cover", "class", "ESA WorldCover v200", "2021", "derived", "Most frequent class")
# Sentinel-2
_f("s2_ndvi_mean", "NDVI (Sentinel-2)", "index", "Sentinel-2 L2A", "Nov 2023–Feb 2024", "derived",
   "(B08−B04)/(B08+B04), median composite, cell mean")
_f("s2_ndwi_mean", "NDWI (Sentinel-2)", "index", "Sentinel-2 L2A", "Nov 2023–Feb 2024", "derived",
   "McFeeters (B03−B08)/(B03+B08), cell mean")
_f("s2_ndbi_mean", "NDBI (Sentinel-2)", "index", "Sentinel-2 L2A", "Nov 2023–Feb 2024", "derived",
   "(B11−B08)/(B11+B08), cell mean; spectral proxy, confuses bare soil with built-up")
_f("s2_veg_frac", "Vegetated share (NDVI>0.3)", "fraction", "Sentinel-2 L2A", "Nov 2023–Feb 2024", "derived",
   "Share of valid 20 m pixels with NDVI > 0.3")
# Landsat
for e in ["2001", "2010", "2015", "2020", "2024"]:
    _f(f"lst_mean_{e}", f"Land surface temperature {e}", "°C", "Landsat C2 L2 ST", f"Apr–Jun, epoch {e}", "observed",
       "Median of clear-sky LST observations per pixel, cell mean (surface, not air, temperature)")
    _f(f"lst_rel_{e}", f"Relative LST {e}", "°C", "Landsat C2 L2 ST", f"Apr–Jun, epoch {e}", "derived",
       "Cell LST − median LST of all valid land cells in the same epoch")
    _f(f"lst_p90_{e}", f"LST 90th pct. {e}", "°C", "Landsat C2 L2 ST", f"epoch {e}", "derived", "90th pct. of pixel LST")
    _f(f"ls_ndvi_{e}", f"NDVI (Landsat) {e}", "index", "Landsat C2 L2 SR", f"Apr–Jun, epoch {e}", "derived", "Median NDVI")
    _f(f"ls_ndbi_{e}", f"NDBI (Landsat) {e}", "index", "Landsat C2 L2 SR", f"Apr–Jun, epoch {e}", "derived", "Median NDBI")
_f("ndvi_change_2001_2024", "NDVI change 2001→2024", "index Δ", "Landsat", "2001 vs 2024", "derived",
   "Landsat NDVI 2024 − 2001 (TM vs OLI sensors; small cross-sensor bias possible)")
_f("ndbi_change_2001_2024", "NDBI change 2001→2024", "index Δ", "Landsat", "2001 vs 2024", "derived", "NDBI 2024 − 2001")
_f("ndvi_rel_change_2001_2024", "Relative NDVI change 2001→2024", "index Δ", "Landsat", "2001 vs 2024", "derived",
   "(NDVI − land-cell median NDVI) 2024 minus the same in 2001; removes epoch-wide sensor/weather shifts")
_f("ndbi_rel_change_2001_2024", "Relative NDBI change 2001→2024", "index Δ", "Landsat", "2001 vs 2024", "derived",
   "(NDBI − land-cell median NDBI) 2024 minus the same in 2001")
_f("lst_rel_change_2001_2024", "Relative LST change 2001→2024", "°C", "Landsat", "2001 vs 2024", "derived",
   "Relative LST 2024 − relative LST 2001")
# Population
for y in ["2015", "2020", "2025"]:
    _f(f"pop_{y}", f"Population {y}", "persons", "WorldPop R2025A", y, "modelled", "Sum of 100 m constrained counts")
    _f(f"pop_density_{y}", f"Population density {y}", "persons/km²", "WorldPop R2025A", y, "modelled", "pop / cell area")
_f("pop_change_2015_2025", "Population change 2015→2025", "persons", "WorldPop R2025A", "2015–2025", "modelled", "pop 2025 − pop 2015")
# OSM
_f("road_density_km_km2", "Road density", "km/km²", "OpenStreetMap", "snapshot", "derived", "Mapped road length / cell area")
_f("major_road_density_km_km2", "Major road density", "km/km²", "OpenStreetMap", "snapshot", "derived",
   "Motorway–secondary road length / area")
_f("intersection_density_km2", "Intersection density", "per km²", "OpenStreetMap", "snapshot", "derived",
   "Road-graph nodes of degree ≥ 3 per km²")
_f("osm_building_density_km2", "Mapped building density", "per km²", "OpenStreetMap", "snapshot", "derived",
   "Mapped building footprints per km² (incomplete mapping)")
_f("dist_waterway_m", "Distance to mapped waterway", "m", "OpenStreetMap", "snapshot", "derived", "Centroid → nearest waterway")
_f("dist_drain_m", "Distance to mapped drain/nullah", "m", "OpenStreetMap", "snapshot", "derived",
   "Centroid → nearest waterway=drain|ditch|canal (unmapped drains not counted)")
_f("dist_coast_m", "Distance to coast", "m", "OpenStreetMap", "snapshot", "derived", "Centroid → OSM coastline")
# Water history
_f("gsw_occurrence_mean", "Surface-water occurrence", "%", "JRC GSW v1.4", "1984–2021", "observed",
   "Mean % of valid observations with water")
_f("gsw_seasonal_frac", "Seasonal-water share", "fraction", "JRC GSW v1.4", "1984–2021", "observed",
   "Share of pixels with 1–11 water months in a typical year")
_f("gsw_permanent_frac", "Permanent-water share", "fraction", "JRC GSW v1.4", "1984–2021", "observed",
   "Share of pixels water 12 months")
# Rainfall (assigned)
_f("rain_annual_normal_mm", "Annual rainfall normal", "mm/yr", "CHIRPS v3", "1991–2020", "assigned",
   "Mean annual total of the ≈5.5 km CHIRPS pixel containing the cell centroid")
_f("rain_jjas_normal_mm", "Monsoon rainfall normal (JJAS)", "mm", "CHIRPS v3", "1991–2020", "assigned", "Mean Jun–Sep total")
_f("rain_jjas_cv", "Monsoon variability (CV)", "ratio", "CHIRPS v3", "1991–2020", "assigned", "Std/mean of JJAS totals")
_f("rain_max_month_mm", "Wettest month on record", "mm", "CHIRPS v3", "1981–2025", "assigned", "Maximum monthly total")
_f("rain_trend_mm_decade", "Annual rainfall trend", "mm/decade", "CHIRPS v3", "1981–2025", "assigned", "OLS slope of annual totals")
_f("rain_jjas_2022_mm", "Monsoon 2022 rainfall", "mm", "CHIRPS v3", "Jun–Sep 2022", "assigned", "JJAS 2022 total")
_f("rain_jjas_2022_anom_pct", "Monsoon 2022 anomaly", "%", "CHIRPS v3", "2022 vs 1991–2020", "assigned", "JJAS 2022 vs normal")
_f("rain_aug_2020_mm", "August 2020 rainfall", "mm", "CHIRPS v3", "Aug 2020", "assigned", "August 2020 monthly total")
# Quality
_f("data_quality_score", "Data quality score", "fraction", "KUVIS", "—", "derived",
   "Share of 7 core evidence features available for the cell")

FEATURES = F
