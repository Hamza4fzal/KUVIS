# KUVIS — Literature Review

Every reference below is real. "Verified" means the bibliographic record (authors, venue, DOI) was checked online on
2026-11-11/12 while writing this review; "standard" marks canonical algorithm papers cited in their usual form.
Statements about what a paper found are limited to what its abstract/record states.

## 1. Surface urban heat — and why arid cities differ

The **surface urban heat island (SUHI)** is measured from satellite land surface temperature (LST), which is the
radiometric temperature of the ground, not the air. Across 419 large cities, Peng et al. (2012) found mean daytime
SUHI intensity of 1.5 ± 1.2 °C with daytime SUHI driven mainly by urban–rural differences in vegetation, and no
correlation between daytime and night-time SUHI — i.e. day and night are governed by different mechanisms.

The sign of the daytime effect depends on the biome. Imhoff et al. (2010) analysed 38 US cities with MODIS LST and
impervious surface area and found that cities in **desert** settings show an atypical, U-shaped LST response, with
arid/semi-arid cities the exception to the general finding that urban areas are warmer than their surroundings.
Rasul, Balzter & Smith (2017; thesis Rasul 2016) used Landsat 4–8 (1992–2013) over semi-arid Erbil and found that
densely built-up areas formed a daytime **surface urban cool island (SUCI)** in summer, autumn and winter, with soil
moisture the main control, and that converting bare soil to urban land *lowered* mean LST.

**Relevance to KUVIS.** KUVIS independently finds the same pattern for Karachi from 2001–2024 Landsat composites:
the 20 densest heat concentrations are bare desert land in inland Gadap, while built-up cells are ~4–5 °C cooler than
the median land cell, and the gap widened from −3.6 °C (2001) to −5.0 °C (2024) (`heat_history`, `heat_dbscan_geographic`).
This is consistent with the arid-city literature and is reported strictly as a *daytime surface* phenomenon: the
literature above shows night-time and air-temperature behaviour can differ, and KUVIS has no night-time LST.

Karachi-specific work: Baqa et al. (2022) characterised Karachi's thermal environment 2000–2020 from Landsat and
reported that expanding built-up land raised LST and that large vegetated parks moderated heat. Rizvi et al. (2020)
combined Landsat (day) and MODIS (night) for Karachi. KUVIS differs in two ways that may explain differing emphases:
it compares cells with the *whole Division* (including ~1,600 km² of bare Gadap desert) rather than an urban core
against its immediate fringe, and it uses relative LST per epoch rather than absolute LST.

## 2. Urban flooding in Karachi

Peer-reviewed, cell-level records of Karachi's urban floods are scarce. The best-documented recent events are the
monsoons of **August 2020** and **2022**. A UN-OCHA-hosted rapid needs assessment for 24–27 August 2020 reports six
districts declared calamity-hit, Karachi East and Malir worst affected, and inundation from overflowing nullahs
(reliefweb.int). An IBA Karachi preliminary survey describes August 2020 as the heaviest August rainfall in 89
years. The Urban Resource Centre (Hasan & Ahmed) links flooding to blocked and encroached drains. These grey-literature
sources are used only as event context — KUVIS does not use them as labels.

**Relevance to KUVIS.** CHIRPS v3 independently ranks 2022 (669 mm Jun–Sep), 1994 and 2020 as Karachi's wettest
monsoons since 1981, consistent with this documented history. Because no validated cell-level flood record exists,
KUVIS's supervised flood model predicts *intermittent surface water* from JRC Global Surface Water rather than
"flooding" (see methodology §6).

## 3. Datasets

* **CHIRPS** — Funk et al. (2015): quasi-global 0.05° rainfall blending satellite infrared with station data.
* **JRC Global Surface Water** — Pekel et al. (2016): 30 m water occurrence/seasonality from ~3 million Landsat
  scenes, 1984 onwards.
* **ESA WorldCover 2021 v200** — Zanaga et al. (2022); the producers note that 2020 (v100) and 2021 (v200) used
  different algorithms, so differences between them must not be read as change — a rule KUVIS follows.
* Landsat Collection-2 Level-2, Sentinel-2 L2A, NASADEM, WorldPop R2025A, OpenStreetMap, geoBoundaries and the
  World Bank EO4SD Karachi LULC are cited through their official data records (see `research/DATA_SOURCES.md`).

## 4. Data-mining and spatial-statistics methods

* **Clustering:** K-means with silhouette (Rousseeuw, 1987) and Davies–Bouldin (Davies & Bouldin, 1979) evaluation;
  density-based DBSCAN (Ester et al., 1996).
* **Association rules:** Apriori (Agrawal & Srikant, 1994) and FP-Growth (Han, Pei & Yin, 2000); KUVIS uses FP-Growth
  with support/confidence/lift and redundancy pruning.
* **Anomaly detection:** Isolation Forest (Liu, Ting & Zhou, 2008), compared with Local Outlier Factor
  (Breunig et al., 2000).
* **Spatial statistics:** local Gi/Gi* (Getis & Ord, 1992; Ord & Getis, 1995). G* is defined for non-negative
  variables — KUVIS encountered and fixed a sign inversion caused by applying it to a zero-centred variable.
* **Evaluation under spatial dependence:** Roberts et al. (2017) show that block cross-validation is nearly always
  more appropriate than random CV for structured (e.g. spatial) data, while warning it can force extrapolation; KUVIS
  uses 5 km spatial blocks for its Decision Tree.

## 5. Gap addressed by KUVIS

Existing Karachi studies treat heat, flooding and land-use change separately and mostly focus on the urban core.
KUVIS integrates them on one grid for the whole Division and applies several mining methods with documented
evaluation, which surfaced cross-hazard structure not visible in single-hazard studies — notably that heat and
flood susceptibility are spatially *opposed* (ρ = −0.61), which makes any single composite vulnerability score
strongly weight-dependent.

## References

| Reference | Status |
|---|---|
| Agrawal, R. & Srikant, R. (1994). Fast algorithms for mining association rules. *Proc. 20th VLDB*, 487–499. | standard |
| Baqa, M. F., Lu, L., Chen, F., Nawaz-ul-Huda, S., Pan, L., Tariq, A., Qureshi, S., Li, B. & Li, Q. (2022). Characterizing spatiotemporal variations in the urban thermal environment related to land cover changes in Karachi, Pakistan, from 2000 to 2020. *Remote Sensing*, 14(9), 2164. https://doi.org/10.3390/rs14092164 | verified |
| Breunig, M. M., Kriegel, H.-P., Ng, R. T. & Sander, J. (2000). LOF: identifying density-based local outliers. *Proc. ACM SIGMOD*, 93–104. | standard |
| Davies, D. L. & Bouldin, D. W. (1979). A cluster separation measure. *IEEE TPAMI*, 1(2), 224–227. | standard |
| Ester, M., Kriegel, H.-P., Sander, J. & Xu, X. (1996). A density-based algorithm for discovering clusters in large spatial databases with noise. *Proc. KDD-96*, 226–231. | standard |
| Funk, C. et al. (2015). The climate hazards infrared precipitation with stations — a new environmental record for monitoring extremes. *Scientific Data*, 2, 150066. https://doi.org/10.1038/sdata.2015.66 | verified |
| Getis, A. & Ord, J. K. (1992). The analysis of spatial association by use of distance statistics. *Geographical Analysis*, 24(3), 189–206. | standard |
| Han, J., Pei, J. & Yin, Y. (2000). Mining frequent patterns without candidate generation. *Proc. ACM SIGMOD*, 1–12. | standard |
| Imhoff, M. L., Zhang, P., Wolfe, R. E. & Bounoua, L. (2010). Remote sensing of the urban heat island effect across biomes in the continental USA. *Remote Sensing of Environment*, 114(3), 504–513. https://doi.org/10.1016/j.rse.2009.10.008 | verified |
| Liu, F. T., Ting, K. M. & Zhou, Z.-H. (2008). Isolation Forest. *Proc. 8th IEEE ICDM*, 413–422. https://doi.org/10.1109/ICDM.2008.17 | verified |
| Ord, J. K. & Getis, A. (1995). Local spatial autocorrelation statistics: distributional issues and an application. *Geographical Analysis*, 27(4), 286–306. https://doi.org/10.1111/j.1538-4632.1995.tb00912.x | verified |
| Pekel, J.-F., Cottam, A., Gorelick, N. & Belward, A. S. (2016). High-resolution mapping of global surface water and its long-term changes. *Nature*, 540, 418–422. https://doi.org/10.1038/nature20584 | verified |
| Peng, S. et al. (2012). Surface urban heat island across 419 global big cities. *Environmental Science & Technology*, 46(2), 696–703. | verified |
| Rasul, A., Balzter, H. & Smith, C. (2017). Applying a normalized ratio scale technique to assess influences of urban expansion on land surface temperature of the semi-arid city of Erbil. *International Journal of Remote Sensing*, 38(13), 3960–3980. https://doi.org/10.1080/01431161.2017.1312030 | verified |
| Rizvi, S. H. et al. (2020). Karachi urban heat study combining Landsat (day) and MODIS (night) LST. *Journal of Atmospheric and Solar-Terrestrial Physics*. https://doi.org/10.1016/j.jastp.2020.105374 | verified (DOI and venue; full title to be confirmed from the publisher) |
| Roberts, D. R. et al. (2017). Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure. *Ecography*, 40(8), 913–929. https://doi.org/10.1111/ecog.02881 | verified |
| Rousseeuw, P. J. (1987). Silhouettes: a graphical aid to the interpretation and validation of cluster analysis. *Journal of Computational and Applied Mathematics*, 20, 53–65. | standard |
| Zanaga, D. et al. (2022). ESA WorldCover 10 m 2021 v200. Zenodo. https://doi.org/10.5281/zenodo.7254221 | verified |
| UN OCHA / ReliefWeb (2020). Rapid need assessment report: monsoon rains, Karachi Division, 24th–27th August 2020. reliefweb.int | verified (grey literature) |
| Urban Resource Centre Karachi (Hasan, A. & Ahmed, N.). "Why Karachi floods" and related URC articles. urckarachi.org | verified (grey literature) |
