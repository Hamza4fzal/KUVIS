# KUVIS: mining multi-source satellite and open data for urban environmental vulnerability in Karachi

**Final research report** · 5th-semester Data Mining lab project · November 2026

Every number in this report comes from an experiment record in `research/experiments/*.json`. Those records are
rendered in full by `scripts/generate_results.py` into `research/RESULTS.md`. Experiment IDs are given in
`code font` so each claim can be traced. Methods are detailed in `research/RESEARCH_METHODOLOGY.md`, data in
`research/DATA_SOURCES.md`, and references in `research/literature_review/LITERATURE_REVIEW.md`.

---

## Abstract

Karachi faces extreme pre-monsoon heat, recurrent monsoon flooding and rapid, largely informal urban growth. Studies
of these hazards usually examine one at a time and mostly cover the urban core.

KUVIS (Karachi Urban Vulnerability Intelligence System) places eleven open datasets on one 500 m grid covering the
whole Karachi Division (14,701 cells). The datasets are:

- Landsat 5/8/9 surface temperature and reflectance (five epochs, 2000–2025)
- Sentinel-2 L2A
- NASADEM
- ESA WorldCover 2021
- JRC Global Surface Water
- Sentinel-1 radar (RTC), passes after the heaviest 2020 and 2022 rain days
- CHIRPS v3 (monthly and daily)
- WorldPop R2025A
- OpenStreetMap
- World Bank EO4SD land use (2005, 2017)
- geoBoundaries

Five data-mining methods are applied across five thematic modules, each with an explicit evaluation: K-means,
DBSCAN, FP-Growth association rules, Isolation Forest and a Decision Tree. Getis–Ord Gi* and Moran's I add spatial
statistics.

Four findings stand out:

1. **Daytime surface heat is not urban.** Built-up land is consistently cooler at the surface than bare land in every
   epoch from 2001 to 2024, and the gap widens from −3.6 °C to −6.1 °C. The hottest concentrations (up to 57 °C mean
   LST) are bare desert in Gadap. This is the arid "surface cool island" known from other dry cities.
2. **Heat and flood susceptibility are spatially opposed** (Spearman ρ = −0.61). As a result, any single composite
   vulnerability score depends strongly on its weights: only 22 % of top-quintile cells remain in the top quintile
   under 95 % of random weightings. KUVIS therefore reports combined stress *regimes* alongside the index.
3. **Observed intermittent surface water is predictable from terrain alone** under spatially blocked
   cross-validation: balanced accuracy 0.85 and ROC-AUC 0.90. Elevation ≤ 8 m accounts for 80 % of the tree's Gini
   importance. Precision is low (0.26), however, and the satellite proxy does not capture urban street flooding.
   Checked out of sample against Sentinel-1 radar flood water mapped after the 2020 and 2022 storms, the tree still
   ranks flooded cells well (ROC-AUC 0.85), but most of that skill comes from separating low from high ground, and
   radar cannot see water between buildings.
4. **Volunteered map data is too incomplete to stand in for infrastructure.** 66 % of densely built-up cells have
   fewer than 50 mapped buildings per km² in OpenStreetMap.

The system is delivered as a reproducible pipeline, a PostGIS database, a FastAPI service and a React/MapLibre web
application with location reports and PDF export.

---

## 1. Introduction

Karachi is Pakistan's largest city. Its exposure to environmental stress is well documented, but the evidence is
fragmented. Heat studies use Landsat over the urban core (Baqa et al., 2022; Rizvi et al., 2020). Flood knowledge
rests largely on grey literature about the 2020 and 2022 monsoons (UN OCHA, 2020; Urban Resource Centre). Land-use
change is mapped by separate projects such as the World Bank EO4SD maps.

This project asks a data-mining question: **what patterns emerge when these hazards and their drivers are put on a
common spatial unit and mined together, and how reliable are those patterns?**

### 1.1 Objectives

1. Build a reproducible, evidence-typed feature set for every 500 m cell of Karachi Division from real, openly
   licensed data only.
2. Apply clustering, density-based clustering, association-rule mining, anomaly detection and classification to
   heat, flood, urbanization and infrastructure questions, with appropriate evaluation for each.
3. Combine the dimensions into an explainable composite vulnerability index, and test how sensitive it is.
4. Deliver the results through an interactive platform that keeps measured, modelled and derived evidence distinct.

### 1.2 Ground rules

The following rules were held throughout:

- No value is fabricated or imputed as if it were measured.
- Land surface temperature is never described as air temperature.
- Road density is never described as congestion.
- Missing data is never treated as zero.
- The composite index is never presented as an official risk assessment.

---

## 2. Data

| Domain | Source | Resolution / period | Role |
|---|---|---|---|
| Surface temperature, NDVI, NDBI | Landsat C2 L2 (L5 TM; L8/9 OLI-TIRS), Planetary Computer | 30 m (ST 100 m native), read at 60 m; Apr–Jun epochs 2001 · 2010 · 2015 · 2020 · 2024 | Heat, history, change |
| Vegetation/built-up indices | Sentinel-2 L2A | 20 m; Nov 2023–Feb 2024 | Current state |
| Terrain | NASADEM | 30 m | Elevation, slope, TPI |
| Land cover | ESA WorldCover v200 | 10 m; 2021 | Built/bare/vegetation shares |
| Surface water | JRC Global Surface Water v1.4 | 30 m; 1984–2021 | Flood proxy label |
| Event flood water | Sentinel-1 RTC (VV), Planetary Computer | 10 m, read at 40 m; 8 passes ≤ 48 h after 2020/2022 event days | Independent validation label |
| Rainfall | CHIRPS v3 | ≈5.5 km; 1981–2025 monthly; Jun–Sep 2020 and 2022 daily | Monsoon normals, anomalies, event days |
| Population | WorldPop R2025A (constrained) | 100 m; 2015, 2025 | Exposure, growth |
| Infrastructure | OpenStreetMap (Overpass) | vector snapshot | Roads, drains, buildings |
| Land use | World Bank EO4SD Karachi | 2005, 2017 | Transitions |
| Boundaries | geoBoundaries ADM2/ADM3 | — | Division and town names |

Data availability shaped several design decisions:

- **No Landsat 5 for 2005.** Planetary Computer has no usable Landsat 5 coverage of Karachi in 2004–2006, so the
  baseline epoch is 2000–2002.
- **CHIRPS is too coarse for within-city detail.** At 0.05° it cannot resolve neighbourhoods. Each cell receives the
  value of the pixel containing its centroid, and is flagged *assigned*, not measured.
- **No real traffic data.** No open traffic observations exist for Karachi (TomTom requires a commercial licence), so
  Module D describes infrastructure *supply* only.
- **Sentinel-1 only around event days; no IMERG.** Radar was read only for passes within 48 h after the heaviest
  rain days, plus same-orbit dry-season references. IMERG half-hourly rainfall is available on Planetary Computer
  but was not added; CHIRPS daily (whose day-to-day timing is itself disaggregated with IMERG) was used to pick
  event days.

All acquisitions are recorded in a provenance registry. The registry refuses to mark a source "acquired" unless the
files exist on disk.

---

## 3. Methodology

### 3.1 Preprocessing

- **Grid.** The analysis uses a 500 m grid in UTM 42N (EPSG:32642). Zonal statistics are computed by rasterising
  cell IDs on each source's native grid, so no source is resampled before aggregation.
- **Landsat surface temperature.**
  - LST (°C) = DN × 0.00341802 + 149 − 273.15.
  - Pixels are masked with QA_PIXEL (cloud, shadow, cirrus, snow) and with ST_QA ≤ 4 K.
  - Each epoch uses the per-pixel median of the clearest scenes in April–June.
- **Sentinel-2.** The processing-baseline 04.00 reflectance offset (−1000 DN) is corrected, and reprocessed
  duplicate products are removed.
- **Relative indices.** Because the weather on acquisition days differs between epochs, every epoch's LST, NDVI and
  NDBI is expressed *relative to that epoch's median over Karachi land cells*. All change analysis uses these
  relative values. Section 4.3 shows why this matters.

### 3.2 Mining methods and evaluation

| Method | Used for | Evaluation |
|---|---|---|
| K-means | Thermal, flood, trajectory, infrastructure and stress profiles | K swept 2–10; silhouette, Davies–Bouldin, Calinski–Harabasz, elbow; K chosen by highest silhouette with K ≥ 3 and no cluster < 2 % of cells |
| DBSCAN (feature space) | Profiles without fixing K | k-distance knee for ε; noise share; ARI against K-means |
| DBSCAN (geographic) | Contiguous hotspots of top-decile cells | 750 m ε; cross-checked against Gi* |
| Getis–Ord Gi*, Moran's I | Significant spatial clustering | 499 permutations, two-sided, Benjamini–Hochberg FDR; non-negative inputs only |
| FP-Growth | Co-occurring conditions | Support, confidence, lift; confidence threshold relative to base rate; redundant rules pruned |
| Isolation Forest (+ LOF) | Cells unusual for their context | Contextual residuals (land-cover peers, 1.5 km neighbours, own history); persistence across individual satellite dates; Jaccard overlap with LOF |
| Decision Tree | Which terrain/surface variables separate cells with intermittent water | GroupKFold(5) on 5 km spatial blocks; depth search; balanced accuracy, ROC-AUC, precision/recall; label-threshold sensitivity; permutation importance |
| Sentinel-1 change detection + out-of-sample check | Independent event label for the flood models | Leave-one-out false-alarm test on dry-season passes; threshold sensitivity; ROC-AUC of the tree vs single-variable baselines; per-stratum AUC (withheld below 10 positives) |
| Theil–Sen + Kendall τ | Per-cell vegetation trend over five epochs | Absolute and relative trends reported side by side |

### 3.3 Composite index (Module E)

**Dimensions.** The Urban Vulnerability Index (UVI) combines four dimensions:

- **Heat:** LST and relative LST.
- **Flood susceptibility:** low elevation, flatness, depression, distance to waterways, rainfall normal.
- **Urbanization pressure:** population growth 2015–2025, built-up change 2005–2017.
- **Environmental stress:** low NDVI, relative NDVI loss 2001–2024.

A traffic dimension was excluded because no real data exists for it.

**Construction.**

- Indicators are percentile-normalised and averaged within each dimension.
- The UVI is the equal-weight mean of the dimensions.
- A cell is scored only if at least three of the four dimensions have data.

**Sensitivity.** Robustness is measured in two ways:

- 1,000 weight vectors drawn from a flat Dirichlet distribution, recording each cell's rank range.
- Correlation of the equal-weight ranking with two alternative weightings.

---

## 4. Results

### 4.1 Module B — Urban heat

**Spatial structure.**

- Relative LST is very strongly spatially autocorrelated (Moran's I = 0.922, pseudo-p = 0.002).
- Gi* identifies 3,604 hot-spot and 2,430 cold-spot cells, with 3,210 hot-spot cells remaining after FDR correction
  (`heat_gi_star`).
- DBSCAN on the hottest decile finds 20 contiguous concentrations (`heat_dbscan_geographic`).
- The largest concentration covers 113 km² around Gadap at a mean 55.2 °C, +4.5 °C above the city median.
- The hottest concentration covers 91.5 km² at a mean 57.3 °C, +6.5 °C above the median.
- Every cell in both concentrations is also a Gi* hot spot. Both are bare land with near-zero built-up share.

**Drivers** (`heat_correlation`, n = 11,889 land cells; Spearman ρ with LST):

- Distance to the coast: ρ = +0.68
- Elevation: ρ = +0.64
- Built-up share: ρ = −0.56
- NDBI: ρ = +0.55
- Population density: ρ = −0.49

A standardised OLS model with HC3 errors explains R² = 0.67 of the variance, with these coefficients:

- Distance to the coast: β = +0.76 (95 % CI 0.74 to 0.78)
- Built-up share: β = −0.76 (95 % CI −0.78 to −0.74)
- NDVI: β = −0.59
- Bare share: β = −0.36
- Elevation: β = −0.24

Distance to the coast and elevation are strongly collinear (inland Karachi is higher). Once distance to the coast is
in the model, elevation's coefficient turns negative, so the elevation coefficient should not be read on its own. The
built-up coefficient is stable with or without coast distance (−0.76 in both), which is what the cool-island finding
rests on. Residuals remain spatially autocorrelated (Moran's I = 0.65), so the confidence intervals are optimistic.

NDBI correlates *positively* with LST while built-up share correlates *negatively*. This shows that NDBI here
responds to bare soil rather than to buildings, which is why NDBI was later removed from the urbanization dimension.

**Profiles** (`heat_kmeans`, K = 3, silhouette 0.531, Davies–Bouldin 0.657):

| Cluster | Cells | Description |
|---|---|---|
| Vegetated | 413 (3 %) | Mean LST 37.3 °C, NDVI 0.59 |
| Built-up and dense | 2,746 | Cooler than average |
| Remaining land | 8,730 (73 %) | Mean LST 51.7 °C |

DBSCAN in feature space agrees only weakly with K-means (ARI = 0.13). It finds one dominant dense mass and labels
4 % of cells as noise, so the profiles are not sharply separated.

**History** (`heat_history`):

| Epoch | Median land LST | Built-up minus city median | Built-up minus bare |
|---|---|---|---|
| 2001 | 44.3 °C | −3.6 °C | −3.6 °C |
| 2024 | 50.7 °C | −5.0 °C | −6.1 °C |

The built-up versus bare gap widens in every intermediate epoch. Absolute LST differs between epochs mainly because
of weather on the acquisition days, so it is not interpreted as warming.

**Association rules** (`heat_association`, 14 rules): the strongest says low bare-ground share, low elevation and
sparse vegetation together imply low surface heat, with confidence 0.93 and lift 2.80. Proximity to the coast with
sparse vegetation implies low heat (confidence 0.81, lift 2.43); distance from the coast with sparse vegetation
implies high heat (0.74, lift 2.22).

**Anomalies** (`heat_isolation_forest`):

- 238 cells are flagged: 74 warmer and 164 cooler than their context.
- Flagged cells deviate on a median 100 % of individual satellite dates, versus 0 % for unflagged cells, so the
  flags are persistent rather than single-scene artefacts.
- Isolation Forest and LOF agree only partially (Jaccard = 0.25). Only cells flagged by Isolation Forest are
  reported.

### 4.2 Module A — Flood susceptibility

No validated cell-level flood record exists for Karachi. The label used instead is *intermittent surface water*:
the cell's JRC seasonal-water share is at least 2 %. The base rate is 6.9 % of cells.

**Association rules** (`flood_association`, 28 rules): low elevation (≤ 10 m), little built-up land (< 20 %) and
distance from mapped waterways (≥ 1 km) co-occur with intermittent water 64 % of the time, a lift of 9.4. These
describe coastal flats and creek margins, not river overflow.

**Decision tree** (`flood_tree`; 162 spatial blocks, best depth 3):

- Balanced accuracy 0.852, ROC-AUC 0.896, recall 0.86.
- Precision is only 0.26: 638 true positives against 1,778 false positives.
- The result holds across label thresholds: balanced accuracy 0.833–0.853 for thresholds of 1–5 %.
- The first split is elevation ≤ 8.1 m, which carries 80 % of Gini importance. Distance to waterways (12 %) and
  built-up share (4 %) follow.

The tree therefore describes *where Landsat sees water*. It is not an urban flood predictor: short street floods in
dense neighbourhoods, the hazard documented for 2020 and 2022, are rarely captured by 16-day optical imagery under
monsoon cloud.

**Profiles** (`flood_kmeans`, K = 7, silhouette 0.34): one profile, *vegetated, low-lying and flat* (592 cells), has
intermittent water in 34 % of its cells, 5.0 times the base rate. The water label was not a clustering input, so this
is an independent check.

**Independent check against radar flood water** (`flood_sar_validation`). None of the flood models saw this data.

- *Event days* were chosen from CHIRPS daily rainfall, not from news reports: days with a city-mean of at least
  20 mm. This gave 6 days in 2020 (the largest 59 mm on 27 August) and 12 in 2022 (the largest 73 mm on 24 July).
- *Detection.* For each Sentinel-1 pass within 48 h of an event day, a 40 m pixel counts as new water when its VV
  backscatter is below −18 dB and more than 3 dB darker than **every** dry-season (January–May) pass of the same
  orbit. Steep slopes, normally-wet pixels and a 320 m strip along each swath edge are excluded.
- *False alarms.* A first version compared against the dry-season *median*. Run on dry passes against the other dry
  passes (leave-one-out), it "found" up to 43 km² of flooding, almost all on coastal ground below 10 m where tide
  and salt pans change from pass to pass. The minimum reference cut this to a median of 0.2 km² per pass, but two
  of 24 dry passes still show 11 and 21 km². The 21 km² pass (11 January 2022) followed about 10 mm of CHIRPS rain on
  4–6 January, so part of it may be real ponding; the 11 km² pass (6 February 2020) followed a dry month and is a
  genuine false alarm. Detections near the coast therefore carry more doubt than inland ones.
- *What radar saw.* The morning after 27 August 2020 it mapped 40.6 km² of new open water, most of it inland along
  the north-western edge of Gadap. The 2022 passes show 1–12 km² each. In total 159 of the 11,097 evaluated cells
  (1.4 %) are radar-flooded (≥ 2 % of the cell).
- *Does the tree transfer?* Its out-of-fold probabilities rank radar-flooded cells above the rest with ROC-AUC 0.85
  (0.85 for 2020, 0.83 for 2022), clearly better than elevation alone (0.77). It catches 84 % of radar-flooded cells
  but with 5.7 % precision, because radar-flooded cells are rare.
- *But the proxy carries most of it.* The JRC seasonal-water share by itself scores 0.91, higher than the tree: both
  sources see water on open, low ground. Within strata the tree's AUC falls to 0.68 (below 10 m) and 0.72 (above),
  so much of its skill is the low/high split. Inland cells (≥ 2 km from the coast, 96 positives) still reach 0.81,
  so the agreement is not just tide.
- *Rules and profiles.* All 25 top association rules also raise the radar flood rate (median lift 5.2), and the
  K-means profiles rank the same way under both labels (Spearman ρ = 0.96 between cluster shares).
- *The blind spot.* Only 2 of 1,880 mostly built-up cells are radar-flooded. That is not evidence that dense
  neighbourhoods stay dry: C-band radar cannot see water between buildings.

**Rainfall context** (CHIRPS): June–September 2022 rainfall was a median 280 % above the 1991–2020 normal across all
170 pixels. 2022, 1994 and 2020 rank as the wettest monsoons since 1981, consistent with the documented flood
history.

### 4.3 Module C — Urbanization and land change

**Vegetation trend** (`urban_ndvi_trend`):

- In *absolute* NDVI, 58.8 % of cells show a significant greening trend, and the city median NDVI rises steadily
  from 0.066 (2001) to 0.157 (2024).
- In NDVI *relative to each epoch's median*, only 2.2 % of cells show significant greening and 3.8 % show
  significant browning.

The city-wide rise is a sensor and compositing artefact: Landsat 5 TM and Landsat 8/9 OLI differ, and scene
conditions differ between epochs. Treating it as real greening would have produced a false headline finding, which
is why every change analysis in KUVIS uses relative indices.

**Concentrated change** (connected components of the extreme 5 %):

- Vegetation loss covers 67.5 km² in Korangi and Landhi, and 26.5 km² in Orangi and SITE.
- Vegetation gain is concentrated in small clusters of 6–10 km². Relative surface heat in those clusters fell by
  3.4–4.3 °C.

**Land-use transitions, 2005 → 2017** (`urban_lulc_change`, EO4SD):

- 146.7 km² of natural grass and shrub became construction or mine/dump land.
- 48.2 km² of that construction and dump class became urban fabric.
- 15.3 km² of discontinuous urban became continuous urban.
- 1,072 cells gained more than 25 percentage points of built-up share.

**Trajectories** (`urban_kmeans`, K = 3, silhouette 0.38) separate three groups:

| Trajectory | Cells | Description |
|---|---|---|
| Established built-up | 2,106 | Built-up cells with relative vegetation loss |
| Growing periphery | 4,127 | High population growth with relative greening |
| Stable undeveloped land | 6,544 | Low population growth |

### 4.4 Module D — Infrastructure (supply, not traffic)

**Road-network profiles** (`infra_kmeans`, K = 8, silhouette 0.585): road-network metrics form well-separated
profiles, from unmapped periphery (4,633 cells) to dense arterial grids.

**OSM completeness** (`infra_osm_completeness`):

- Mapped building density correlates only moderately with built-up share (ρ = 0.56) and with population
  (ρ = 0.52).
- 1,264 of 1,907 densely built-up cells (66 %) have fewer than 50 mapped buildings per km².

OSM building data is therefore used only as a completeness indicator, never as a measure of building stock.

### 4.5 Module E — Composite vulnerability

**How the dimensions relate** (`vulnerability_index`):

- Heat and flood are strongly opposed: ρ = −0.61. Low-lying coastal and urban land is cooler; elevated inland
  desert is hotter and drier.
- Flood and urbanization move together: ρ = +0.58.

**Sensitivity.** The equal-weight UVI correlates 0.86–0.93 with the alternative weightings, so the overall ranking
holds. Its upper tail, however, is fragile:

- Only 21.8 % of top-quintile cells stay in the top quintile under 95 % of the 1,000 random weightings.
- The median cell's rank moves across 55 percentiles.

Discoveries based on the index are therefore only reported when at least 10 contiguous cells are involved and at
least half of them are stable.

**Stress regimes** (`vulnerability_kmeans`, K = 3) describe the city more honestly than a single score:

| Regime | Cells | Heat | Flood | Urbanization |
|---|---|---|---|---|
| Hot inland | 5,691 (43 %) | High | Low | Low |
| Low-lying urban | 3,284 (25 %) | Low | High | High |
| Low-environmental-stress | 4,160 (32 %) | — | — | — |

The low-lying urban regime also has high environmental stress. In the rest of the table, "—" means the dimension is
not distinctive for that regime. FP-Growth confirms the opposition: *Heat = Low ⇒ Flood = High*, with confidence
0.68 and lift 2.03 (`vulnerability_association`).

**Spatial clustering.** The UVI is spatially clustered (Moran's I = 0.70). The most stable overlapping-stress area is
13 cells in Kiamari, where 92 % stay in the top quintile across weightings. The largest is 102 km² across Gadap and
Gulshan-e-Iqbal, home to an estimated 786,000 people according to WorldPop, where 55 % stay in the top quintile.

**Population exposure.** WorldPop places 14.2 million of Karachi's modelled 18.9 million residents in the two
highest UVI classes. This mostly reflects the fact that the flood and urbanization dimensions are high where people
live. It is not an independent measure of harm.

**Discoveries.** 53 discoveries are generated automatically from these experiments, each with its supporting
statistics and its limitations. They are listed in `research/RESULTS.md` and on the Discoveries page.

---

## 5. Discussion

### 5.1 The arid surface cool island

The most robust result is that Karachi's built-up land is cooler at the surface than its surroundings by day, and
that the gap widens as the city grows. This contradicts the common expectation of an urban heat island but agrees
with the literature on arid and desert cities:

- Imhoff et al. (2010) found desert cities to be the exception to warmer-than-surroundings cities.
- Rasul et al. (2017) documented a daytime surface urban cool island in semi-arid Erbil.
- Peng et al. (2012) showed that daytime surface heat islands are controlled mainly by vegetation contrast.

Earlier Karachi studies emphasised built-up warming (Baqa et al., 2022). The difference is plausibly one of framing:
KUVIS compares cells with the whole Division, including about 1,600 km² of bare Gadap desert, and uses relative LST
per epoch.

The finding is about *daytime surface* temperature only. Night-time LST and air temperature can behave differently,
and KUVIS has data on neither, so no conclusion about heat stress on residents follows from it.

### 5.2 Why one vulnerability number is not enough

Heat and flood susceptibility are anti-correlated because both follow the same terrain gradient in opposite
directions. A weighted sum of opposed dimensions mostly measures the weights. This is a substantive data-mining
result, not a defect, and it is why the platform shows the dimensions, the regimes and the stability of each cell
alongside the composite score.

### 5.3 What the flood model can and cannot say

The spatially blocked Decision Tree shows that terrain explains where open water is observed. But its precision of
0.26 and its proxy label limit it to a screening role. The Sentinel-1 check shows that what it learned transfers to
real storm water on open ground, but adds little beyond the water history it was trained on, and says nothing about
the flooding that matters most to residents: water in dense neighbourhoods with blocked nullahs, which both optical
archives and C-band radar miss. Validating that needs street-level records (municipal complaints, drainage
surveys, or very-high-resolution imagery), not another satellite proxy.

### 5.4 Methodological lessons

These were found by testing during the project and are recorded in `research/RESEARCH_METHODOLOGY.md` §4.1:

- **Gi* sign inversion.** Gi* applied to a zero-centred variable (relative LST) inverted hot and cold spots. KUVIS
  now runs it on absolute values and rejects negative inputs, with a regression test.
- **Absolute index trends are unreliable across sensors.** Absolute NDVI trends across Landsat sensors produced a
  spurious city-wide greening; relative indices removed it.
- **NDBI misreads arid land.** In arid terrain NDBI tracks bare soil, not buildings.
- **Spatial cross-validation is needed.** Random cross-validation would have overstated the flood tree's accuracy
  because neighbouring cells leak information (Roberts et al., 2017).
- **Rule thresholds must follow the base rate.** With fixed confidence thresholds, a 7 % base-rate label produced no
  rules at all.

### 5.5 Limitations

- **Resolution.** At 500 m, cells average over streets, roofs and open plots. The 30 m DEM cannot represent drains.
- **Temporal coverage.** Landsat is cloud-limited in the monsoon and observes at about 10:30 local time only.
- **Fixed land cover.** WorldCover 2021 land-cover classes are applied to every epoch.
- **Modelled population.** WorldPop is a model, not a census. Population growth 2015–2025 covers a different period
  than the Landsat change.
- **Coarse rainfall.** CHIRPS rainfall barely varies inside the city.
- **Uneven OSM coverage.** OSM completeness varies spatially.
- **Spatial dependence.** Naive p-values overstate significance. Permutation, FDR and blocked cross-validation
  reduce this but do not remove it.
- **Boundary mismatch.** The geoBoundaries ADM3 town names (pre-2011 towns) differ from current administrative
  units.

---

## 6. Conclusion

KUVIS shows that mining multiple open datasets on a common grid surfaces structure that single-hazard studies miss:

- a daytime surface cool island in an arid megacity, widening over 23 years;
- a strong spatial opposition between heat and flood susceptibility, which makes simple composite indices fragile;
- terrain-driven, but low-precision, predictability of observed surface water, which transfers to radar-observed
  storm water on open ground but cannot speak for dense neighbourhoods;
- substantial gaps in volunteered infrastructure data.

Every pattern is reported with its evaluation, its evidence type and its limitations, and none is presented as an
official risk assessment.

**Future work:**

- Night-time LST from Landsat or ECOSTRESS.
- IMERG sub-daily rainfall.
- GHSL built-up history.
- Validation against field or municipal drainage records, should these become available.

---

## 7. Reproducibility

```bash
python scripts/run_pipeline.py           # all steps; or name steps, e.g. features mine_heat vulnerability load_db
python scripts/generate_results.py       # research/RESULTS.md from experiment records
python -m pytest tests                   # 27 tests (algorithms + live API)
python scripts/ui_check.py               # browser smoke test of all 12 pages
```

Configuration lives in `config/kuvis.yaml`. Each experiment record stores its parameters, input features, sample
size, run time and code version (git commit).

## References

See `research/literature_review/LITERATURE_REVIEW.md` for full entries and their verification status. Cited here:

- Baqa et al. (2022)
- Funk et al. (2015)
- Imhoff et al. (2010)
- Pekel et al. (2016)
- Peng et al. (2012)
- Rasul, Balzter & Smith (2017)
- Rizvi et al. (2020)
- Roberts et al. (2017)
- Zanaga et al. (2022)
- UN OCHA / ReliefWeb (2020)
- Urban Resource Centre Karachi
- Algorithm references: Agrawal & Srikant (1994); Han, Pei & Yin (2000); Ester et al. (1996); Liu, Ting & Zhou
  (2008); Breunig et al. (2000); Getis & Ord (1992); Ord & Getis (1995); Rousseeuw (1987); Davies & Bouldin (1979)
