# KUVIS — Results

_Generated 2026-11-11 19:44 UTC by `scripts/generate_results.py` from `research/experiments/*.json`. Do not edit by hand._

## Module: heat

### FP-Growth association rules — `heat_association`

*Discover combinations of land-surface conditions that co-occur with high or low relative LST* · n = 11,889 · run 2026-11-11T18:07:00+00:00 · code 0202263
- n rules: **8**

| rule | support | confidence | lift |
|---|---|---|---|
| Bare ground=Low ∧ Elevation=Low ∧ Vegetation=Sparse ⇒ Surface heat=Low | 0.072 | 0.935 | 2.80 |
| Bare ground=Low ∧ Vegetation=Sparse ⇒ Surface heat=Low | 0.092 | 0.915 | 2.74 |
| Elevation=Low ∧ Vegetation=Sparse ⇒ Surface heat=Low | 0.110 | 0.840 | 2.52 |
| Bare ground=Low ∧ Elevation=Low ⇒ Surface heat=Low | 0.164 | 0.770 | 2.31 |
| Elevation=Low ⇒ Surface heat=Low | 0.234 | 0.702 | 2.11 |
| Elevation=High ∧ Vegetation=Sparse ⇒ Surface heat=High | 0.060 | 0.671 | 2.01 |
| Bare ground=Medium ∧ Elevation=High ⇒ Surface heat=High | 0.056 | 0.656 | 1.97 |
| Bare ground=Low ⇒ Surface heat=Low | 0.202 | 0.605 | 1.82 |

_Limitations:_ Association ≠ causation. Tertile cut-points are data-driven, not physical thresholds.

### Spearman correlation + standardized OLS (HC3) — `heat_correlation`

*Quantify associations of LST with vegetation, built-up, population, coast and terrain* · n = 11,889 · run 2026-11-11T18:07:00+00:00 · code 0202263
- ols r2: **0.554**

| feature | Spearman ρ | n |
|---|---|---|
| s2_ndvi_mean | -0.013 | 11889 |
| s2_ndbi_mean | 0.545 | 11889 |
| built_frac | -0.560 | 11889 |
| veg_frac_wc | 0.214 | 11889 |
| bare_frac | 0.447 | 11889 |
| log_pop_density_2025 | -0.493 | 11889 |
| elev_mean | 0.638 | 11889 |

| feature | std. β | 95 % CI |
|---|---|---|
| s2_ndvi_mean | -0.607 | -0.632 – -0.582 |
| built_frac | -0.759 | -0.780 – -0.737 |
| bare_frac | -0.288 | -0.310 – -0.265 |
| log_pop_density_2025 | 0.163 | 0.135 – 0.191 |
| elev_mean | 0.333 | 0.313 – 0.354 |

_Limitations:_ Neighbouring cells are not independent (residual Moran's I reported); naive p-values are overstated. Correlation does not establish causation.

### DBSCAN (feature space) — `heat_dbscan_feature`

*Density-based thermal profiles without fixing K; compare with K-means* · n = 11,889 · run 2026-11-11T18:06:51+00:00 · code 0202263
- n clusters: **3**
- noise share: **0.042**
- ari vs kmeans non noise: **0.134**

_Limitations:_ A single global eps cannot adapt to varying density; most cells may form one large dense cluster with the unusual cells as noise.

### DBSCAN (geographic, hot cells) — `heat_dbscan_geographic`

*Find spatially concentrated groups of the hottest 10 % of land cells* · n = 1,189 · run 2026-11-11T18:06:55+00:00 · code 0202263
- n hotspots: **20**

_Limitations:_ Hot threshold is relative to Karachi land cells; bare desert can be hottest.

### Getis–Ord Gi* + Global Moran's I — `heat_gi_star`

*Statistically significant spatial clustering of surface temperature* · n = 11,889 · run 2026-11-11T18:06:56+00:00 · code 0202263
- n hot: **3604**
- n cold: **2430**
- n hot fdr: **3210**
- Moran's I = **0.922** (pseudo-p 0.002)

_Limitations:_ Hot spots are statistical clustering, not causal evidence. Pseudo p-values from 499 permutations; FDR-adjusted classes also reported.

### Epoch comparison of LST composites — `heat_history`

*Historical thermal comparison of Karachi land cells* · n = 14,701 · run 2026-11-11T18:07:00+00:00 · code 0202263

| epoch | cells | median LST °C | built − (rel.) | bare (rel.) | vegetated (rel.) |
|---|---|---|---|---|---|
| 2001 | 12777 | 44.26 | -3.61 | 0.01 | 0.76 |
| 2010 | 13131 | 50.27 | -4.43 | 0.40 | 0.66 |
| 2015 | 13161 | 48.43 | -4.57 | 0.57 | 0.76 |
| 2020 | 13167 | 47.83 | -4.54 | 0.89 | 0.20 |
| 2024 | 13162 | 50.74 | -4.99 | 1.10 | 0.43 |

_Limitations:_ Absolute LST differs between epochs with weather on acquisition days; compare relative LST. Land-cover classes are from 2021 and applied to all epochs.

### Isolation Forest (+ LOF comparison) — `heat_isolation_forest`

*Find cells whose LST is unusual relative to land-cover peers, neighbours and own history* · n = 11,887 · run 2026-11-11T18:06:59+00:00 · code 0202263
- n flagged: **238**
- n warmer: **74**
- n cooler: **164**
- median persistence flagged: **1.000**
- median persistence unflagged: **0.000**
- Isolation Forest vs LOF Jaccard = 0.249

_Limitations:_ Contamination (2 %) sets how many cells are flagged; anomalies are statistical, not hazards.

### K-means — `heat_kmeans`

*Identify thermal–environmental profiles of land cells* · n = 11,889 · run 2026-11-11T18:06:36+00:00 · code 0202263

- Selected: K=3: highest silhouette (0.531) among K≥3 without clusters <2% of cells; elbow heuristic suggests K=4
- Silhouette 0.531, Davies–Bouldin 0.657, Calinski–Harabasz 11354

| K | inertia | silhouette | Davies–Bouldin |
|---|---|---|---|
| 2 | 36550 | 0.500 | 1.066 |
| 3 | 20425 | 0.531 | 0.657 |
| 4 | 14698 | 0.415 | 0.878 |
| 5 | 11920 | 0.399 | 0.890 |
| 6 | 10492 | 0.360 | 0.967 |
| 7 | 9300 | 0.321 | 0.972 |
| 8 | 8566 | 0.322 | 0.971 |
| 9 | 7937 | 0.314 | 1.027 |
| 10 | 7400 | 0.302 | 1.046 |

| cluster | cells | generated name |
|---|---|---|
| 0 | 413 | low NDBI · high NDVI · low LST |
| 1 | 2746 | high built-up · high population density · low LST |
| 2 | 8730 | near city-wide average |

_Limitations:_ K-means assumes roughly spherical clusters in standardized space. LST composite is daytime (~10:30 local) Apr–Jun.

## Module: flood

### FP-Growth association rules — `flood_association`

*Find combinations of terrain/surface/drainage/rainfall conditions that co-occur with observed intermittent surface water* · n = 13,184 · run 2026-11-11T19:43:27+00:00 · code ab1adb5
- n rules: **28**
- base rate: **0.069**

| rule | support | confidence | lift |
|---|---|---|---|
| Built-up=<20 % ∧ Elevation=≤10 m ∧ Waterway distance=≥1 km ⇒ Intermittent water=Observed | 0.030 | 0.644 | 9.39 |
| Elevation=≤10 m ∧ Monsoon rainfall=Low ∧ Waterway distance=≥1 km ⇒ Intermittent water=Observed | 0.018 | 0.639 | 9.32 |
| Built-up=<20 % ∧ Drain distance=≥1 km ∧ Elevation=≤10 m ⇒ Intermittent water=Observed | 0.038 | 0.635 | 9.26 |
| Built-up=<20 % ∧ Elevation=≤10 m ∧ Slope=Flat (<2°) ⇒ Intermittent water=Observed | 0.028 | 0.630 | 9.19 |
| Elevation=≤10 m ∧ Monsoon rainfall=Low ⇒ Intermittent water=Observed | 0.026 | 0.622 | 9.08 |
| Elevation=≤10 m ∧ Slope=Flat (<2°) ∧ Waterway distance=≥1 km ⇒ Intermittent water=Observed | 0.023 | 0.621 | 9.06 |
| Elevation=≤10 m ∧ Slope=Flat (<2°) ∧ Terrain position=Neutral ⇒ Intermittent water=Observed | 0.019 | 0.619 | 9.02 |
| Built-up=<20 % ∧ Elevation=≤10 m ∧ Terrain position=Neutral ⇒ Intermittent water=Observed | 0.025 | 0.616 | 8.99 |

_Limitations:_ Intermittent water ≠ urban flooding; short urban floods under cloud are rarely captured by Landsat. Association ≠ causation.

### DBSCAN (feature space) — `flood_dbscan_feature`

*Density-based flood-related profiles; compare with K-means* · n = 11,913 · run 2026-11-11T19:43:25+00:00 · code ab1adb5
- n clusters: **4**
- noise share: **0.021**
- ari vs kmeans non noise: **0.003**

### K-means — `flood_kmeans`

*Group land cells by flood-related terrain, surface and rainfall characteristics* · n = 11,913 · run 2026-11-11T19:42:59+00:00 · code ab1adb5

- Selected: K=7: highest silhouette (0.342) among K≥3 without clusters <2% of cells; elbow heuristic suggests K=5
- Silhouette 0.342, Davies–Bouldin 1.078, Calinski–Harabasz 4091

| K | inertia | silhouette | Davies–Bouldin |
|---|---|---|---|
| 2 | 60812 | 0.316 | 1.354 |
| 3 | 49998 | 0.296 | 1.290 |
| 4 | 40917 | 0.309 | 1.147 |
| 5 | 34357 | 0.332 | 1.062 |
| 6 | 29875 | 0.338 | 1.040 |
| 7 | 27238 | 0.342 | 1.078 |
| 8 | 25338 | 0.339 | 1.091 |
| 9 | 23625 | 0.287 | 1.189 |
| 10 | 22181 | 0.289 | 1.163 |

| cluster | cells | generated name |
|---|---|---|
| 0 | 527 | high local depression (TPI) · high elevation · high distance to mapped drain |
| 1 | 424 | high slope · high local depression (TPI) · high elevation |
| 2 | 2654 | high distance to mapped drain · high elevation · low monsoon rainfall |
| 3 | 4668 | near city-wide average |
| 4 | 1202 | high monsoon rainfall · low elevation · low distance to mapped drain |
| 5 | 1846 | high built-up · low elevation · low distance to mapped drain |
| 6 | 592 | high NDVI · low elevation · low slope |

_Limitations:_ Rainfall is assigned from ≈5.5 km CHIRPS pixels and varies little inside the city. 30 m DEM cannot represent drains or micro-topography.

### Decision Tree (spatially blocked CV) — `flood_tree`

*Which terrain/surface characteristics distinguish cells with observed intermittent surface water?* · n = 11,913 · run 2026-11-11T19:43:32+00:00 · code ab1adb5
- balanced accuracy: **0.852**
- roc auc: **0.896**
- precision: **0.264**
- recall: **0.862**
- f1: **0.404**
- best depth: **3**

| label threshold | balanced acc. | ROC-AUC | positive rate |
|---|---|---|---|
| 0.01 | 0.833 | 0.868 | 0.075 |
| 0.02 | 0.852 | 0.896 | 0.062 |
| 0.05 | 0.853 | 0.910 | 0.045 |

_Limitations:_ The target is intermittent surface water, not validated flood occurrence; the model explains this proxy and has no demonstrated predictive validity for urban flood events. Spatial blocks reduce but do not eliminate spatial leakage.

## Module: urban

### Isolation Forest (+ LOF comparison) — `urban_isolation_forest`

*Find cells whose 2001→2024 change is unusual relative to cells with a similar 2001 state* · n = 12,777 · run 2026-11-11T18:38:54+00:00 · code aea7c6e
- n flagged: **256**
- Isolation Forest vs LOF Jaccard = 0.225

_Limitations:_ Unusual change is statistical; it may reflect construction, reservoir level, irrigation, or sensor/compositing differences.

### K-means — `urban_kmeans`

*Group cells by their 2001→2024 development trajectory* · n = 12,777 · run 2026-11-11T18:38:01+00:00 · code aea7c6e

- Selected: K=3: highest silhouette (0.378) among K≥3 without clusters <2% of cells; elbow heuristic suggests K=4
- Silhouette 0.378, Davies–Bouldin 1.132, Calinski–Harabasz 6853

| K | inertia | silhouette | Davies–Bouldin |
|---|---|---|---|
| 2 | 33650 | 0.431 | 1.085 |
| 3 | 24655 | 0.378 | 1.132 |
| 4 | 19985 | 0.370 | 1.082 |
| 5 | 17945 | 0.301 | 1.073 |
| 6 | 16124 | 0.325 | 1.142 |
| 7 | 14571 | 0.322 | 1.081 |
| 8 | 13118 | 0.327 | 1.047 |
| 9 | 11949 | 0.326 | 1.006 |
| 10 | 11194 | 0.304 | 1.060 |

| cluster | cells | generated name |
|---|---|---|
| 0 | 2106 | high built-up (2021) · low relative NDVI change · high population growth |
| 1 | 6544 | low population growth · high relative-heat change · low built-up (2021) |
| 2 | 4127 | high population growth · low relative-heat change · high relative NDVI change |

_Limitations:_ Landsat 5 TM vs 8/9 OLI sensor differences add small offsets to index changes. Population growth 2015–2025 is modelled, and covers a different period than the Landsat change.

### Land-use change detection (transition matrix) — `urban_lulc_change`

*Quantify 2005→2017 land-use transitions from the World Bank EO4SD maps* · n = 9,110 · run 2026-11-11T18:37:54+00:00 · code aea7c6e

_Limitations:_ Polygon boundaries of the two years were mapped independently; slivers inflate small transitions. Covers only the EO4SD mapped extents.

### Theil–Sen trend + Kendall τ (per cell) — `urban_ndvi_trend`

*Long-term vegetation trend across Landsat epochs, absolute and relative to the city median* · n = 13,184 · run 2026-11-11T18:38:53+00:00 · code aea7c6e

_Limitations:_ With ≤ 5 epochs, Kendall's τ has little power: p < 0.05 needs a near-monotonic series. Epoch composites differ in scene count and weather.

## Module: infra

### K-means — `infra_kmeans`

*Profile mapped road-network supply relative to population* · n = 13,187 · run 2026-11-11T19:42:04+00:00 · code ab1adb5

- Selected: K=8: highest silhouette (0.585) among K≥3 without clusters <2% of cells; elbow heuristic suggests K=5
- Silhouette 0.585, Davies–Bouldin 0.807, Calinski–Harabasz 16878

| K | inertia | silhouette | Davies–Bouldin |
|---|---|---|---|
| 2 | 31207 | 0.538 | 0.876 |
| 3 | 20856 | 0.532 | 0.939 |
| 4 | 15555 | 0.550 | 0.830 |
| 5 | 11051 | 0.571 | 0.774 |
| 6 | 8941 | 0.583 | 0.736 |
| 7 | 7526 | 0.580 | 0.747 |
| 8 | 6617 | 0.585 | 0.807 |
| 9 | 5998 | 0.584 | 0.806 |
| 10 | 5442 | 0.588 | 0.811 |

| cluster | cells | generated name |
|---|---|---|
| 0 | 4633 | low log pop density 2025 · low road density |
| 1 | 2820 | low road density |
| 2 | 1855 | near city-wide average |
| 3 | 487 | high major road density |
| 4 | 592 | high log pop density 2025 · high osm building density · high road density |
| 5 | 1266 | high road density · high intersection density · high log pop density 2025 |
| 6 | 657 | high major road density · high osm building density · high road density |
| 7 | 877 | high major road density · high road density · high intersection density |

_Limitations:_ Describes mapped infrastructure supply, not traffic or congestion. OSM completeness varies spatially (see completeness experiment).

### Spearman correlation (completeness check) — `infra_osm_completeness`

*Assess how completely OSM maps buildings where other sources show dense settlement* · n = 13,187 · run 2026-11-11T19:42:04+00:00 · code ab1adb5

| feature | Spearman ρ | n |
|---|---|---|
| pop_density_2025 | 0.522 | 13187 |
| built_frac | 0.556 | 13187 |

_Limitations:_ A low count may also reflect very large buildings; this is a screening indicator.

## Module: vulnerability

### FP-Growth association rules — `vulnerability_association`

*Which stress dimensions tend to co-occur in the same cells?* · n = 13,187 · run 2026-11-11T19:44:19+00:00 · code ab1adb5
- n rules: **11**

| rule | support | confidence | lift |
|---|---|---|---|
| Environmental=High ∧ Heat=Low ∧ Urbanization=Medium ⇒ Flood=High | 0.053 | 0.856 | 2.57 |
| Environmental=High ∧ Heat=Low ∧ Urbanization=High ⇒ Flood=High | 0.075 | 0.852 | 2.56 |
| Environmental=High ∧ Heat=Low ⇒ Flood=High | 0.135 | 0.823 | 2.47 |
| Heat=Low ∧ Urbanization=High ⇒ Flood=High | 0.123 | 0.775 | 2.32 |
| Heat=Low ∧ Urbanization=Medium ⇒ Flood=High | 0.080 | 0.760 | 2.28 |
| Environmental=High ∧ Urbanization=High ⇒ Flood=High | 0.090 | 0.707 | 2.12 |
| Heat=Low ⇒ Flood=High | 0.226 | 0.678 | 2.03 |
| Flood=Low ∧ Urbanization=Medium ⇒ Heat=High | 0.058 | 0.670 | 2.01 |

_Limitations:_ Co-occurrence only. Dimensions share some inputs indirectly (e.g. built-up share and NDVI are negatively related), which raises lift between them.

### DBSCAN (geographic, top-decile UVI) — `vulnerability_dbscan_geographic`

*Locate spatial concentrations of the most stressed cells* · n = 1,319 · run 2026-11-11T19:44:17+00:00 · code ab1adb5
- n hotspots: **37**

### Getis–Ord Gi* + Global Moran's I — `vulnerability_gi_star`

*Statistically significant clustering of the composite index* · n = 13,187 · run 2026-11-11T19:44:18+00:00 · code ab1adb5
- n hot: **3130**
- n cold: **2615**
- n hot fdr: **2630**
- Moran's I = **0.697** (pseudo-p 0.005)

### Composite index (UVI) + weight sensitivity — `vulnerability_index`

*Combine normalized dimension indicators into an explainable composite index* · n = 13,187 · run 2026-11-11T19:44:18+00:00 · code ab1adb5
- n scored: **13187**
- top quintile stable share: **0.218**
- median rank range width: **55.440**

_Limitations:_ Not an official disaster-risk assessment. Percentile normalisation makes the index relative to Karachi; it cannot be compared with other cities. Flood dimension uses susceptibility proxies, not observed flood depth/frequency.

### K-means — `vulnerability_kmeans`

*Identify combinations of overlapping stress across the four dimensions* · n = 13,135 · run 2026-11-11T19:44:14+00:00 · code ab1adb5

- Selected: K=3: highest silhouette (0.334) among K≥3 without clusters <2% of cells; elbow heuristic suggests K=4
- Silhouette 0.334, Davies–Bouldin 1.168, Calinski–Harabasz 7211

| K | inertia | silhouette | Davies–Bouldin |
|---|---|---|---|
| 2 | 2008 | 0.327 | 1.315 |
| 3 | 1459 | 0.334 | 1.168 |
| 4 | 1202 | 0.328 | 1.126 |
| 5 | 1036 | 0.297 | 1.152 |
| 6 | 913 | 0.295 | 1.089 |
| 7 | 801 | 0.312 | 1.052 |
| 8 | 733 | 0.284 | 1.137 |
| 9 | 681 | 0.270 | 1.146 |
| 10 | 639 | 0.269 | 1.139 |

| cluster | cells | generated name |
|---|---|---|
| 0 | 4160 | low environmental |
| 1 | 5691 | low flood · high heat · low urbanization |
| 2 | 3284 | high environmental · low heat · high flood |

## Discovered patterns (53)

**The coolest thermal profile: low NDBI · high NDVI · low LST** — _Thermal profile, K-means, 2023–2025_  
K-means (K=3, silhouette 0.53) isolates 413 cells (3 % of analysed land) with mean LST 37.3 °C, NDVI 0.59, NDBI -0.35, built-up 1 %.

**Built-up=<20 % + Elevation=≤10 m + Waterway distance=≥1 km ⇒ Intermittent water=Observed** — _Environmental association, FP-Growth, current period_  
In 3.0 % of analysed cells these conditions occur together with Intermittent water=Observed. When the conditions hold, Intermittent water=Observed follows 64 % of the time — 9.39× its base rate of 7 %. Co-occurrence, not causation.

**Elevation=≤10 m + Monsoon rainfall=Low + Waterway distance=≥1 km ⇒ Intermittent water=Observed** — _Environmental association, FP-Growth, current period_  
In 1.8 % of analysed cells these conditions occur together with Intermittent water=Observed. When the conditions hold, Intermittent water=Observed follows 64 % of the time — 9.32× its base rate of 7 %. Co-occurrence, not causation.

**Built-up=<20 % + Drain distance=≥1 km + Elevation=≤10 m ⇒ Intermittent water=Observed** — _Environmental association, FP-Growth, current period_  
In 3.8 % of analysed cells these conditions occur together with Intermittent water=Observed. When the conditions hold, Intermittent water=Observed follows 64 % of the time — 9.26× its base rate of 7 %. Co-occurrence, not causation.

**Persistently cool anomaly in GADAP TOWN (4 cells)** — _Unusual heat observation, Isolation Forest, Apr–Jun 2023–2025_  
Isolation Forest flags these cells as cooler than context: their relative LST is -2.5 robust-SD from cells with the same land cover and -4.5 °C from neighbours within 1.5 km; the deviation recurs on 100 % of individual satellite dates. Dominant cover: crop. Statistically unusual, not necessarily hazardous.

**146.7 km² of natural grass shrub became mine dump construction (2005→2017)** — _Urban transformation, Land-use transition matrix, 2005 → 2017_  
Intersecting the World Bank EO4SD peri-urban (HR) land-use maps shows 146.7 km² mapped as natural grass shrub in 2005 and mine dump construction in 2017 — 8 % of all 2005 natural grass shrub in the mapped extent.

**59.6 km² of agriculture became natural grass shrub (2005→2017)** — _Urban transformation, Land-use transition matrix, 2005 → 2017_  
Intersecting the World Bank EO4SD peri-urban (HR) land-use maps shows 59.6 km² mapped as agriculture in 2005 and natural grass shrub in 2017 — 14 % of all 2005 agriculture in the mapped extent.

**Built-up land is consistently cooler than bare land at the surface (every epoch)** — _Historical change, Epoch comparison, 2001–2024_  
In every Landsat epoch (2001, 2010, 2015, 2020, 2024), cells dominated by built-up surface have a median relative LST -3.6, -4.8, -5.1, -5.4, -6.1 °C relative to bare-ground-dominated cells. In arid settings bare desert soil heats strongly by day, so this daytime surface pattern differs from the classic urban heat island measured in air temperature. Land cover classes are from WorldCover 2021.

**48.2 km² of mine dump construction became urban fabric (2005→2017)** — _Urban transformation, Land-use transition matrix, 2005 → 2017_  
Intersecting the World Bank EO4SD peri-urban (HR) land-use maps shows 48.2 km² mapped as mine dump construction in 2005 and urban fabric in 2017 — 30 % of all 2005 mine dump construction in the mapped extent.

**Concentrated vegetation gain: 6.0 km² in Karachi** — _Vegetation change, Change detection + connected components, 2000–02 → 2023–25_  
24 contiguous cells fall in Karachi's most extreme 5 % of NDVI gain relative to the city-wide median between the 2000–02 and 2023–25 Landsat epochs (mean relative change +0.29; NDVI 0.17 → 0.54). Relative surface heat changed by -3.4 °C.

**Persistently cool anomaly in GADAP TOWN (4 cells)** — _Unusual heat observation, Isolation Forest, Apr–Jun 2023–2025_  
Isolation Forest flags these cells as cooler than context: their relative LST is -2.6 robust-SD from cells with the same land cover and -4.0 °C from neighbours within 1.5 km; the deviation recurs on 94 % of individual satellite dates. Dominant cover: crop. Statistically unusual, not necessarily hazardous.

**2022 monsoon rainfall 280 % above the 1991–2020 normal over Karachi** — _Rainfall, Climatological anomaly, Jun–Sep 2022_  
Across the 170 CHIRPS v3 pixels covering Karachi, June–September 2022 rainfall was a median 280 % above the 1991–2020 normal (range 231 % to 340 %). CHIRPS is a satellite–gauge blend at ≈5.5 km; it cannot resolve neighbourhood differences.

**Persistently cool anomaly in KIAMARI TOWN (6 cells)** — _Unusual heat observation, Isolation Forest, Apr–Jun 2023–2025_  
Isolation Forest flags these cells as cooler than context: their relative LST is -3.7 robust-SD from cells with the same land cover and -3.8 °C from neighbours within 1.5 km; the deviation recurs on 97 % of individual satellite dates. Dominant cover: bare. Statistically unusual, not necessarily hazardous.

**Concentrated vegetation gain: 8.0 km² in Karachi** — _Vegetation change, Change detection + connected components, 2000–02 → 2023–25_  
32 contiguous cells fall in Karachi's most extreme 5 % of NDVI gain relative to the city-wide median between the 2000–02 and 2023–25 Landsat epochs (mean relative change +0.26; NDVI 0.16 → 0.51). Relative surface heat changed by -4.0 °C.

**91.5 km² heat concentration around GADAP TOWN** — _Spatial heat concentration, DBSCAN (geographic) + Gi*, Apr–Jun 2023–2025_  
DBSCAN groups 366 of Karachi's hottest-decile cells into one contiguous concentration. Mean pre-monsoon land surface temperature is 57.3 °C, +6.5 °C relative to the city median; mean NDVI 0.16, built-up share 0 %, dominant land cover 'bare'. 100 % of its cells are also Getis–Ord Gi* hot spots. WorldPop estimates 401 residents (2025) in these cells.

**Persistently cool anomaly in GADAP TOWN (4 cells)** — _Unusual heat observation, Isolation Forest, Apr–Jun 2023–2025_  
Isolation Forest flags these cells as cooler than context: their relative LST is -3.3 robust-SD from cells with the same land cover and -3.1 °C from neighbours within 1.5 km; the deviation recurs on 100 % of individual satellite dates. Dominant cover: crop. Statistically unusual, not necessarily hazardous.

**2.8 km² heat concentration around GADAP TOWN** — _Spatial heat concentration, DBSCAN (geographic) + Gi*, Apr–Jun 2023–2025_  
DBSCAN groups 11 of Karachi's hottest-decile cells into one contiguous concentration. Mean pre-monsoon land surface temperature is 56.0 °C, +5.3 °C relative to the city median; mean NDVI 0.16, built-up share 0 %, dominant land cover 'bare'. 100 % of its cells are also Getis–Ord Gi* hot spots. WorldPop estimates 11 residents (2025) in these cells.

**Surface heat rises with elevation (ρ = 0.64)** — _Statistical relationship, Spearman + standardized OLS, 2023–2025_  
Across 11,889 land cells, Spearman ρ between 2023–25 LST and elevation is 0.64. Holding the other variables fixed, the standardized OLS coefficient is +0.33 (95 % CI +0.31 to +0.35; model R² = 0.55). Neighbouring cells are not independent, so significance is overstated; this is association, not causation.

**Overlapping urbanization and flood stress: 3.2 km² in KIAMARI TOWN** — _Overlapping environmental stress, Composite index + DBSCAN, current period_  
13 contiguous cells in the top decile of the composite index (mean UVI 0.67). heat 0.55, flood 0.73, urbanization 0.86, environmental 0.55 (percentile-scale dimension scores). 92 % stay in the top quintile under 95 % of alternative weightings. WorldPop estimates 2,006 residents (2025).

**Persistently warm anomaly in Karachi (13 cells)** — _Unusual heat observation, Isolation Forest, Apr–Jun 2023–2025_  
Isolation Forest flags these cells as warmer than context: their relative LST is -0.5 robust-SD from cells with the same land cover and +2.5 °C from neighbours within 1.5 km; the deviation recurs on 97 % of individual satellite dates. Dominant cover: bare. Statistically unusual, not necessarily hazardous.

**Bare ground=Low + Elevation=Low + Vegetation=Sparse ⇒ Surface heat=Low** — _Environmental association, FP-Growth, current period_  
In 7.2 % of analysed cells these conditions occur together with Surface heat=Low. When the conditions hold, Surface heat=Low follows 93 % of the time — 2.80× its base rate of 33 %. Co-occurrence, not causation.

**Bare ground=Low + Vegetation=Sparse ⇒ Surface heat=Low** — _Environmental association, FP-Growth, current period_  
In 9.2 % of analysed cells these conditions occur together with Surface heat=Low. When the conditions hold, Surface heat=Low follows 91 % of the time — 2.74× its base rate of 33 %. Co-occurrence, not causation.

**113.0 km² heat concentration around GADAP TOWN** — _Spatial heat concentration, DBSCAN (geographic) + Gi*, Apr–Jun 2023–2025_  
DBSCAN groups 452 of Karachi's hottest-decile cells into one contiguous concentration. Mean pre-monsoon land surface temperature is 55.2 °C, +4.5 °C relative to the city median; mean NDVI 0.17, built-up share 1 %, dominant land cover 'bare'. 100 % of its cells are also Getis–Ord Gi* hot spots. WorldPop estimates 10,245 residents (2025) in these cells.

**Surface heat falls with built-up share (ρ = -0.56)** — _Statistical relationship, Spearman + standardized OLS, 2023–2025_  
Across 11,889 land cells, Spearman ρ between 2023–25 LST and built-up share is -0.56. Holding the other variables fixed, the standardized OLS coefficient is -0.76 (95 % CI -0.78 to -0.74; model R² = 0.55). Neighbouring cells are not independent, so significance is overstated; this is association, not causation.

**Surface heat rises with NDBI (ρ = 0.55)** — _Statistical relationship, Spearman + standardized OLS, 2023–2025_  
Across 11,889 land cells, Spearman ρ between 2023–25 LST and NDBI is 0.55. Neighbouring cells are not independent, so significance is overstated; this is association, not causation.

**6.8 km² heat concentration around GADAP TOWN** — _Spatial heat concentration, DBSCAN (geographic) + Gi*, Apr–Jun 2023–2025_  
DBSCAN groups 27 of Karachi's hottest-decile cells into one contiguous concentration. Mean pre-monsoon land surface temperature is 55.1 °C, +4.4 °C relative to the city median; mean NDVI 0.17, built-up share 0 %, dominant land cover 'bare'. 100 % of its cells are also Getis–Ord Gi* hot spots. WorldPop estimates 65 residents (2025) in these cells.

**5.0 km² heat concentration around BIN QASIM TOWN** — _Spatial heat concentration, DBSCAN (geographic) + Gi*, Apr–Jun 2023–2025_  
DBSCAN groups 20 of Karachi's hottest-decile cells into one contiguous concentration. Mean pre-monsoon land surface temperature is 55.1 °C, +4.3 °C relative to the city median; mean NDVI 0.15, built-up share 1 %, dominant land cover 'shrub'. 100 % of its cells are also Getis–Ord Gi* hot spots. WorldPop estimates 860 residents (2025) in these cells.

**5.0 km² heat concentration around GADAP TOWN** — _Spatial heat concentration, DBSCAN (geographic) + Gi*, Apr–Jun 2023–2025_  
DBSCAN groups 20 of Karachi's hottest-decile cells into one contiguous concentration. Mean pre-monsoon land surface temperature is 54.9 °C, +4.2 °C relative to the city median; mean NDVI 0.15, built-up share 0 %, dominant land cover 'bare'. 100 % of its cells are also Getis–Ord Gi* hot spots. WorldPop estimates 9 residents (2025) in these cells.

**Environmental=High + Heat=Low + Urbanization=Medium ⇒ Flood=High** — _Environmental association, FP-Growth, current period_  
In 5.3 % of analysed cells these conditions occur together with Flood=High. When the conditions hold, Flood=High follows 86 % of the time — 2.57× its base rate of 33 %. Co-occurrence, not causation.

**17.5 km² heat concentration around GADAP TOWN** — _Spatial heat concentration, DBSCAN (geographic) + Gi*, Apr–Jun 2023–2025_  
DBSCAN groups 70 of Karachi's hottest-decile cells into one contiguous concentration. Mean pre-monsoon land surface temperature is 54.9 °C, +4.2 °C relative to the city median; mean NDVI 0.16, built-up share 0 %, dominant land cover 'bare'. 100 % of its cells are also Getis–Ord Gi* hot spots. WorldPop estimates 6 residents (2025) in these cells.

**Environmental=High + Heat=Low + Urbanization=High ⇒ Flood=High** — _Environmental association, FP-Growth, current period_  
In 7.5 % of analysed cells these conditions occur together with Flood=High. When the conditions hold, Flood=High follows 85 % of the time — 2.56× its base rate of 33 %. Co-occurrence, not causation.

**3.8 km² heat concentration around GADAP TOWN** — _Spatial heat concentration, DBSCAN (geographic) + Gi*, Apr–Jun 2023–2025_  
DBSCAN groups 15 of Karachi's hottest-decile cells into one contiguous concentration. Mean pre-monsoon land surface temperature is 54.8 °C, +4.1 °C relative to the city median; mean NDVI 0.16, built-up share 0 %, dominant land cover 'bare'. 100 % of its cells are also Getis–Ord Gi* hot spots. WorldPop estimates 1 residents (2025) in these cells.

**Elevation=Low + Vegetation=Sparse ⇒ Surface heat=Low** — _Environmental association, FP-Growth, current period_  
In 11.0 % of analysed cells these conditions occur together with Surface heat=Low. When the conditions hold, Surface heat=Low follows 84 % of the time — 2.52× its base rate of 33 %. Co-occurrence, not causation.

**Profile “high NDVI · low elevation · low slope”: intermittent surface water in 34 % of cells** — _Flood-related profile, K-means + independent JRC label, 1984–2021 water history; current terrain/land cover_  
K-means (K=7) groups 592 cells with mean elevation 31.7 m, slope 1.6°, NDVI 0.55 and built-up share 3 %. JRC Global Surface Water (1984–2021) observed intermittent water in 34 % of them — 5.0× the 6.9 % rate across analysed cells. The water label was not a clustering input. Intermittent water is not the same as urban flooding: Landsat rarely captures short street flooding in dense built-up areas.

**Overlapping urbanization and heat stress: 6.2 km² in BIN QASIM TOWN** — _Overlapping environmental stress, Composite index + DBSCAN, current period_  
25 contiguous cells in the top decile of the composite index (mean UVI 0.69). heat 0.79, flood 0.51, urbanization 0.87, environmental 0.58 (percentile-scale dimension scores). 72 % stay in the top quintile under 95 % of alternative weightings. WorldPop estimates 4,627 residents (2025).

**4.5 km² heat concentration around GADAP TOWN** — _Spatial heat concentration, DBSCAN (geographic) + Gi*, Apr–Jun 2023–2025_  
DBSCAN groups 18 of Karachi's hottest-decile cells into one contiguous concentration. Mean pre-monsoon land surface temperature is 54.7 °C, +4.0 °C relative to the city median; mean NDVI 0.19, built-up share 0 %, dominant land cover 'bare'. 100 % of its cells are also Getis–Ord Gi* hot spots. WorldPop estimates 50 residents (2025) in these cells.

**Surface heat falls with population density (ρ = -0.49)** — _Statistical relationship, Spearman + standardized OLS, 2023–2025_  
Across 11,889 land cells, Spearman ρ between 2023–25 LST and population density is -0.49. Holding the other variables fixed, the standardized OLS coefficient is +0.16 (95 % CI +0.13 to +0.19; model R² = 0.55). Neighbouring cells are not independent, so significance is overstated; this is association, not causation.

**Environmental=High + Heat=Low ⇒ Flood=High** — _Environmental association, FP-Growth, current period_  
In 13.5 % of analysed cells these conditions occur together with Flood=High. When the conditions hold, Flood=High follows 82 % of the time — 2.47× its base rate of 33 %. Co-occurrence, not causation.

**Overlapping urbanization and heat stress: 5.5 km² in GADAP TOWN** — _Overlapping environmental stress, Composite index + DBSCAN, current period_  
22 contiguous cells in the top decile of the composite index (mean UVI 0.66). heat 0.76, flood 0.55, urbanization 0.81, environmental 0.54 (percentile-scale dimension scores). 73 % stay in the top quintile under 95 % of alternative weightings. WorldPop estimates 10,406 residents (2025).

**Overlapping urbanization and environmental stress: 12.5 km² in GADAP TOWN, NEW KARACHI TOWN** — _Overlapping environmental stress, Composite index + DBSCAN, current period_  
50 contiguous cells in the top decile of the composite index (mean UVI 0.67). heat 0.53, flood 0.57, urbanization 0.82, environmental 0.76 (percentile-scale dimension scores). 62 % stay in the top quintile under 95 % of alternative weightings. WorldPop estimates 33,283 residents (2025).

**Overlapping urbanization and environmental stress: 4.2 km² in GADAP TOWN** — _Overlapping environmental stress, Composite index + DBSCAN, current period_  
17 contiguous cells in the top decile of the composite index (mean UVI 0.65). heat 0.63, flood 0.43, urbanization 0.81, environmental 0.73 (percentile-scale dimension scores). 59 % stay in the top quintile under 95 % of alternative weightings. WorldPop estimates 439 residents (2025).

**Overlapping urbanization and environmental stress: 102.0 km² in GADAP TOWN, GULSHAN E IQBAL TOWN** — _Overlapping environmental stress, Composite index + DBSCAN, current period_  
408 contiguous cells in the top decile of the composite index (mean UVI 0.67). heat 0.61, flood 0.58, urbanization 0.79, environmental 0.71 (percentile-scale dimension scores). 55 % stay in the top quintile under 95 % of alternative weightings. WorldPop estimates 786,189 residents (2025).

**Overlapping urbanization and heat stress: 4.0 km² in GADAP TOWN** — _Overlapping environmental stress, Composite index + DBSCAN, current period_  
16 contiguous cells in the top decile of the composite index (mean UVI 0.65). heat 0.64, flood 0.58, urbanization 0.87, environmental 0.53 (percentile-scale dimension scores). 56 % stay in the top quintile under 95 % of alternative weightings. WorldPop estimates 12,687 residents (2025).

**Concentrated vegetation gain: 10.2 km² in BIN QASIM TOWN** — _Vegetation change, Change detection + connected components, 2000–02 → 2023–25_  
41 contiguous cells fall in Karachi's most extreme 5 % of NDVI gain relative to the city-wide median between the 2000–02 and 2023–25 Landsat epochs (mean relative change +0.11; NDVI 0.07 → 0.27). Relative surface heat changed by -4.3 °C.

**Overlapping heat and urbanization stress: 5.8 km² in GADAP TOWN** — _Overlapping environmental stress, Composite index + DBSCAN, current period_  
23 contiguous cells in the top decile of the composite index (mean UVI 0.66). heat 0.91, flood 0.44, urbanization 0.73, environmental 0.55 (percentile-scale dimension scores). 52 % stay in the top quintile under 95 % of alternative weightings. WorldPop estimates 700 residents (2025).

**Concentrated vegetation loss: 67.5 km² in KORANGI TOWN, LANDHI TOWN** — _Vegetation change, Change detection + connected components, 2000–02 → 2023–25_  
270 contiguous cells fall in Karachi's most extreme 5 % of NDVI loss relative to the city-wide median between the 2000–02 and 2023–25 Landsat epochs (mean relative change -0.10; NDVI 0.13 → 0.12). Relative surface heat changed by -0.3 °C.

**15.3 km² of discontinuous urban became continuous urban (2005→2017)** — _Urban transformation, Land-use transition matrix, 2005 → 2017_  
Intersecting the World Bank EO4SD core urban (VHR) land-use maps shows 15.3 km² mapped as discontinuous urban in 2005 and continuous urban in 2017 — 38 % of all 2005 discontinuous urban in the mapped extent.

**Concentrated vegetation loss: 7.0 km² in GADAP TOWN, NEW KARACHI TOWN** — _Vegetation change, Change detection + connected components, 2000–02 → 2023–25_  
28 contiguous cells fall in Karachi's most extreme 5 % of NDVI loss relative to the city-wide median between the 2000–02 and 2023–25 Landsat epochs (mean relative change -0.08; NDVI 0.09 → 0.10). Relative surface heat changed by -0.8 °C.

**Concentrated vegetation loss: 26.5 km² in ORANGI TOWN, SITE TOWN** — _Vegetation change, Change detection + connected components, 2000–02 → 2023–25_  
106 contiguous cells fall in Karachi's most extreme 5 % of NDVI loss relative to the city-wide median between the 2000–02 and 2023–25 Landsat epochs (mean relative change -0.08; NDVI 0.08 → 0.09). Relative surface heat changed by -1.4 °C.

**The warmest thermal profile: near city-wide average** — _Thermal profile, K-means, 2023–2025_  
K-means (K=3, silhouette 0.53) isolates 8730 cells (73 % of analysed land) with mean LST 51.7 °C, NDVI 0.19, NDBI 0.15, built-up 2 %.

**8.5 km² of construction became continuous urban (2005→2017)** — _Urban transformation, Land-use transition matrix, 2005 → 2017_  
Intersecting the World Bank EO4SD core urban (VHR) land-use maps shows 8.5 km² mapped as construction in 2005 and continuous urban in 2017 — 24 % of all 2005 construction in the mapped extent.

**Persistently warm anomaly in GADAP TOWN (6 cells)** — _Unusual heat observation, Isolation Forest, Apr–Jun 2023–2025_  
Isolation Forest flags these cells as warmer than context: their relative LST is +1.6 robust-SD from cells with the same land cover and +0.8 °C from neighbours within 1.5 km; the deviation recurs on 83 % of individual satellite dates. Dominant cover: bare. Statistically unusual, not necessarily hazardous.

**7.4 km² of construction became discontinuous urban (2005→2017)** — _Urban transformation, Land-use transition matrix, 2005 → 2017_  
Intersecting the World Bank EO4SD core urban (VHR) land-use maps shows 7.4 km² mapped as construction in 2005 and discontinuous urban in 2017 — 21 % of all 2005 construction in the mapped extent.
