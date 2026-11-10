# KUVIS — Research Methodology

## 1. Research question

*Can geospatial data-mining techniques discover previously hidden spatial, temporal and environmental patterns
associated with urban vulnerability across Karachi?* Supporting questions RQ1–RQ7 are listed in
`docs/PROJECT_SPECIFICATION.md`; the table in §8 maps each to the experiments that address it.

## 2. Spatial framework

* **Study area:** Karachi Division = geoBoundaries gbOpen PAK ADM2 `Karachi` (2019 boundary).
* **Administrative attribution:** geoBoundaries ADM3 (PBS 2017 census subdivisions) with > 50 % of their area
  inside the study area; each cell takes the subdivision it overlaps most.
* **Analysis CRS:** WGS 84 / UTM zone 42N (EPSG:32642). Interchange: EPSG:4326. Tiles: EPSG:3857.
* **Unit of analysis:** 500 m × 500 m square cells anchored on multiples of 500 m (reproducible), kept when they
  intersect the boundary; `frac_inside` is stored. Analyses use land cells (`frac_inside ≥ 0.5`, WorldCover
  water+wetland share < 0.5).
* **Spatial support is preserved.** Each raster is summarised on its own native pixel grid by rasterising cell IDs
  (pixel → cell by pixel centre). Sources coarser than a cell (CHIRPS ≈ 5.5 km) are *assigned* from the pixel
  containing the centroid, stored at native pixels, flagged `kind = assigned`, and never compared between
  neighbouring cells.

## 3. Data preprocessing

| Source | Processing | Cleaning / quality |
|---|---|---|
| Landsat C2 L2 | per epoch (2004–06, 2009–11, 2014–16, 2019–21, 2023–25; Apr–Jun) select clearest 5 Tier-1 scenes per WRS tile; warp to one 30 m UTM grid; per-pixel median | QA_PIXEL fill/dilated cloud/cirrus/cloud/shadow; ST_QA > 4 K; LST ∉ [−5, 75] °C; SR ∉ (0, 1] |
| Sentinel-2 L2A | Nov 2023–Feb 2024, clearest 5 per MGRS tile, 20 m median | SCL ∈ {4,5,6,7}; baseline-04.00 offset removed |
| NASADEM | mosaic, bilinear to 30 m UTM, Horn slope | nodata masked |
| WorldCover | native 10 m class fractions | class 0 = nodata excluded |
| WorldPop | sum of 100 m counts per cell | negative / nodata excluded |
| CHIRPS v3 | monthly windows 1981–2025 at native pixels | −9999 / negatives → missing (never 0 mm) |
| OSM | Overpass snapshot; lengths via exact overlay in UTM | invalid lines skipped |
| JRC GSW | native 30 m occurrence/seasonality fractions | 255 = nodata excluded |
| EO4SD LULC | exact polygon–cell overlay (native UTM 42N) | change only where both years cover ≥ 50 % of cell |

**Missing data.** Values stay missing (NaN) unless a zero is a genuine observation (e.g. "0 km of mapped road").
Every satellite-derived feature carries a valid-pixel coverage; heat analysis requires LST coverage ≥ 0.5.
`data_quality_score` = share of 7 core evidence features available.

## 4. Feature engineering

All features are defined in `kuvis/features/dictionary.py` (label, unit, source, period, kind, definition) and
published as the `feature_dictionary` table. Key derived features: relative LST per epoch (cell − land-cell median of
that epoch, making epochs comparable despite weather), NDVI/NDBI/relative-LST change 2005→2024, topographic position
(cell elevation − mean within 2 km), log distances to drains/waterways/coast, rainfall climatology (1991–2020 WMO
normal), monsoon variability and 2022 anomaly.

## 5. Data-mining methods

| Method | Where | Evaluation |
|---|---|---|
| K-means | heat, flood, urban, infra, vulnerability | K = 2–10 sweep: inertia/elbow, silhouette (sampled), Davies–Bouldin, Calinski–Harabasz; K chosen by silhouette among K ≥ 3 without < 2 % clusters; profiles in original units + z-scores |
| DBSCAN | feature space (eps = knee of k-distance) and geographic space (UTM metres, eps = 750 m on hottest/most-stressed decile) | n clusters, noise share, size distribution, silhouette (non-noise), parameter grid; ARI vs K-means; Jaccard vs Gi* |
| Getis–Ord Gi*, Moran's I | heat, vulnerability | 1 km distance band, 499 permutations, BH-FDR classes |
| FP-Growth | heat, flood, vulnerability | support / confidence / lift / leverage / conviction; redundancy pruning |
| Isolation Forest (+ LOF) | heat (contextual LST), urban (contextual change) | IF–LOF Jaccard; persistence over single dates |
| Decision Tree | flood (intermittent water) | spatially blocked GroupKFold (5 km blocks); depth tuned in CV; balanced accuracy, precision, recall, F1, ROC-AUC, confusion matrix, Gini & permutation importance; label-threshold sensitivity |
| Theil–Sen + Kendall τ | urban NDVI trend | per-cell, ≥ 4 epochs |
| Composite index | vulnerability | coverage rule, 1,000 Dirichlet weight draws, alternative-weight rank correlations |

## 6. Label policy for supervised learning

No openly available, validated cell-level urban-flood record exists for Karachi. The only independent, spatially
complete water observation is JRC GSW seasonality (Landsat 1984–2021). The flood Decision Tree therefore predicts
**"intermittent surface water observed"** (≥ 2 % of the cell's 30 m pixels with 1–11 water months), never "flooding",
and its predictors exclude all water-derived variables. Permanent water is excluded. The threshold is varied
(1 %, 2 %, 5 %) and results reported for each.

## 7. Composite vulnerability (UVI)

Four dimensions (heat, flood susceptibility, urbanization pressure, environmental deficit) are each the mean of
percentile-ranked inputs (signs documented in `kuvis/modules/vulnerability.py`). Traffic stress is excluded because
no traffic observations exist. UVI = Σ wᵢDᵢ / Σ wᵢ over available dimensions, equal weights, computed only when ≥ 75 %
of the weight is available; evidence quality is reported separately from the score. Population is exposure, not
vulnerability, and is summarised separately.

## 8. Research questions → experiments

| RQ | Experiments |
|---|---|
| RQ1 clusters of similar vulnerability | heat_kmeans, flood_kmeans, urban_kmeans, vulnerability_kmeans, *_dbscan_* |
| RQ2 associations with flood observations / high LST | flood_association, heat_association |
| RQ3 anomalies vs geographic/seasonal baselines | heat_isolation_forest, urban_isolation_forest |
| RQ4 built-up & vegetation change | urban_lulc_change, urban_ndvi_trend, urban_kmeans |
| RQ5 most informative characteristics | flood_tree (importance), heat_correlation (standardized β) |
| RQ6 interpretable multi-dimensional index | vulnerability_index |
| RQ7 overlapping stress | vulnerability_dbscan_geographic, vulnerability_gi_star, vulnerability_association |

## 9. Limitations (summary)

LST ≠ air temperature; daytime overpass only. CHIRPS cannot resolve neighbourhoods or sub-daily intensity. OSM is
incomplete and not traffic. The flood label is a proxy. Percentile-based indices are relative to Karachi. Spatial
autocorrelation inflates naive significance (residual Moran's I reported). Cross-sensor Landsat effects.
