# Drought hazard classification

The **course score** is average weeks per year in D1+ drought across 2000–2025. It counts D1 (Moderate), D2 (Severe), D3 (Extreme) and D4 (Exceptional), including individual qualifying weeks across separate events. The file geodatabase also holds a D2+ comparison and event duration and frequency for both thresholds. The [setup guide](drought_modelbuilder_setup.md) shows how to run the tools.

The full-period drought run assessed all 1,357 baseline weeks at each of 143,325 eligible cell centers. Mean occupancy was 2.57 D1+ weeks/year and 0.55 D2+ weeks/year. Each layer now uses its own three-class breaks, so its High areas indicate relatively frequent drought at that layer's threshold.

Run the [processing model](drought_modelbuilder_setup.md) before classifying, and check the existing operational validation JSON for current coverage, class areas and the land-area transition matrices.

## 1. Evidence and transfer to this project

The drought articles below and the [hurricane evidence matrix](hurricane_classification_report.md#1-evidence-and-what-it-can-justify) cover six distinct peer-reviewed studies.

| Research article | Study area, inputs and support | Indicator/thresholds | Evaluation | Transfer to this project |
|---|---|---|---|---|
| D1. Leeper et al. (2022), [article](https://repository.library.noaa.gov/view/noaa/48743/noaa_48743_DS1.pdf) | U.S. including PR; 1,044 weekly USDM maps, 2000–2019, on a 5 km grid. | D1+ drought events; termination at the last D1+ week followed by at least three D0/None weeks; frequency, duration and intensification. | Event climatology and precipitation/context comparisons, rather than PR loss validation. | Supports D1+ and the three-week recovery comparison. Does not establish 1/3/5 multiyear classes or 250 m information accuracy. We retain valid zero occupancy, rather than copying missing-value choices for event-only figures. |
| D2. Carrão, Naumann & Barbosa (2016), [article](https://www.droughtmanagement.info/literature/EC-JRC_Global%20Mapping%20of%20Drought%20Risk_2016.pdf) | Global/subnational assessment; monthly GPCC precipitation, 1901–2010, at 0.5°, plus exposure and socioeconomic data. | WASP deficit severity relative to the global severe-deficit median; separate hazard, exposure and vulnerability. | Robustness and geographic-pattern comparisons; not a calibrated PR loss scale. | Justifies calling our USDM-only layer hazard. Its global risk classes and exposure inputs cannot be substituted for local drought-week breakpoints. |
| D3. Álvarez-Berríos et al. (2018), [article](https://doi.org/10.1017/S174217051800011X) | Puerto Rico, 887 weekly USDM maps from 2000–2016, summarized at 5 km² hexagon centers. | Counts weeks in D1+ and maps severity, excluding D0 from drought. | Examines geographic overlap with agricultural conservation practices. | Supports counting qualifying weeks at grid centers as a local measure of drought. The course's 250 m grid is for alignment and the three breaks describe the project reference distribution. |

**Full citations**

- **D1:** Leeper, R. D., Bilotta, R., Petersen, B., Stiles, C. J., Heim, R., Fuchs, B., Prat, O. P., Palecki, M., & Ansari, S. (2022). Characterizing U.S. drought over the past 20 years using the U.S. drought monitor. *International Journal of Climatology, 42*(12), 6616–6630. [10.1002/joc.7653](https://doi.org/10.1002/joc.7653).
- **D2:** Carrão, H., Naumann, G., & Barbosa, P. (2016). Mapping global patterns of drought risk: An empirical framework based on sub-national estimates of hazard, exposure and vulnerability. *Global Environmental Change, 39*, 108–124. [10.1016/j.gloenvcha.2016.04.012](https://doi.org/10.1016/j.gloenvcha.2016.04.012).
- **D3.** Álvarez-Berríos, N., Soto-Bayó, S., Holupchinski, E., Fain, S. J., & Gould, W. A. (2018). Correlating drought conservation practices and drought vulnerability in a tropical agricultural system. *Renewable Agriculture and Food Systems, 33*(3), 279–291. [10.1017/S174217051800011X](https://doi.org/10.1017/S174217051800011X).

### Official categories and the local planning precedent

[USDM defines D1–D4 as drought and D0 as abnormally dry](https://droughtmonitor.unl.edu/About/AbouttheData/DroughtClassification.aspx). These are weekly assessment categories. Their indicator percentile ranges do not classify a 26-year average number of drought weeks. Likewise, [DSCI](https://droughtmonitor.unl.edu/About/AbouttheData/DSCI.aspx) is an experimental area-based 0–500 summary, not an authoritative multiyear risk crosswalk.

The [2020 PR CDBG-MIT public-comment draft](https://recuperacion.pr.gov/wp-content/uploads/2020/09/CDBG_MIT_ACTION_PLAN_FULL_DRAFT_EN_2020_09_20_FOR_PUBLIC_COMMENT-Reviewed-Sept21.pdf), Figure 24, printed p. 53, describes 2000–2019 average drought weeks on 0.5-square-mile hexagons, with five bins using cutoffs around 1, 3, 5 and 7 weeks. Its minimum counted DM category remains unresolved. The indexed official figure and earlier processing-plan review support that description; direct full-PDF retrieval returned 403 during this review. Therefore **3/7 weeks is our exploratory three-bin adaptation**, not a verified published D1 hazard standard. This planning document supplements the research articles.

## 2. Score and classification

For each eligible grid cell, count baseline weeks at D1 or worse (encoded states 2–5) or D2 or worse (states 3–5). Divide the count by 26 years to get weeks/year. Eligible cells have 1,357 valid baseline weeks. The three January 2026 buffers confirm event recovery. They do not enter occupancy. Unknown weeks and locations outside the study area stay separate from observed zero drought.

Fit three Natural Breaks (Jenks) classes independently for D1+ and D2+ across all eligible cell centers. The algorithm chooses two distinct count cuts that minimize the sum of squared differences from each class mean, weighted by the frequency of each count. It keeps equal counts together and assigns 1, 3 and 5 in ascending order. Fit the cuts on exact counts, then divide by 26 for the equivalent breaks in weeks/year. [Esri classification methods](https://doc.esri.com/en/arcgis-pro/latest/help/mapping/layer-properties/data-classification-methods.html)

| Class | D1+ qualifying weeks in 2000–2025 | D2+ qualifying weeks in 2000–2025 |
| --- | ---: | ---: |
| Low (1) | 0–52 | 0–10 |
| Medium (3) | 53–120 | 11–34 |
| High (5) | 121 or more | 35 or more |
| Unknown or outside study area | NoData | NoData |

## 3. Comparing the two drought maps

Use the ranks to locate relative concentrations at each threshold. Compare the **weeks/year** scores to see how often moderate and severe drought actually occurred. Severe drought weeks are a subset of moderate-or-worse weeks at every cell. As the two class breaks differ, a location can rank higher on the D2+ map despite recording fewer severe weeks.

| Relative class | D1+ cells | D2+ cells |
| --- | ---: | ---: |
| Low (1) | 62,836 | 73,948 |
| Medium (3) | 61,746 | 50,957 |
| High (5) | 18,743 | 18,420 |

Relative rank changes across **2,241 km²** from D1+ to D2+. This measures how the two definitions distribute their own high and low classes.

Report class and transition areas using clipped land fractions. The total represented land is 8,939.20 km². The validation JSON also records comparisons with D1+ Quantile, Equal Interval and the exploratory fixed 3/7-weeks rule. Six historical comparisons of cell-center and dominant-land-area assignment found 99.960–100% agreement. USDM source layout changes and the generalized coastline still affect the calculation.

## 4. Event recovery and FEMA comparison

An event starts on its first qualifying week. The one-week rule confirms recovery after one consecutive below-threshold week. The three-week rule waits for three, merging short interruptions in the same episode. For D2+, None, D0 and D1 can confirm recovery. For D1+, only None and D0 can do so. Unknown weeks interrupt an observed event and leave its endpoint censored. The three January 2026 observations are available to confirm recovery. The score uses only 2000–2025. The D1+ method follows a Puerto Rico-inclusive USDM study. The D2+ extension is a project choice. [Leeper et al.](https://doi.org/10.1002/joc.7653)

| Weekly threshold | Mean events per cell-year, one-week recovery | Mean events per cell-year, three-week recovery | Mean cell median span, one / three weeks |
| --- | ---: | ---: | ---: |
| D1+ | 0.2773 | 0.2703 | 6.30 / 6.54 weeks |
| D2+ | 0.0507 | 0.0493 | 10.01 / 10.23 weeks |

Mean annual event rates include supported zeros. Duration summaries use completed events and average only over cells that have a completed event at the given threshold. The one- and three-week rules change event counts and durations. The number of qualifying weeks stays the same for both.

The December 2025 FEMA NRI source includes 939 Puerto Rico tracts. All drought risk ratings are labeled “Insufficient Data.” The project reproduced `DRGT_EVNTS` for all 939 tracts by counting distinct D3+ weekly polygons intersecting each tract between January 2000 and March 2025 and multiplying the counts by seven. This checks the tract calculation against an indicator derived from the same USDM maps. The D1+/D2+ course layers describe frequency and persistence at lower intensity thresholds. [FEMA technical documentation](https://www.fema.gov/sites/default/files/documents/fema_national-risk-index_technical-documentation.pdf)

## 5. Final checks and combined map

- Keep EPSG:32161, 250 × 250 m, anchor (0,0), 1,140 × 267 cells and extent (40,750, 209,750)–(325,750, 276,500). Apply the same three-island index mask to both hazards without changing the reference lattice.
- Require integer valid scores **1/3/5**, valid zeros handled by the crosswalk, and NoData outside the domain or where support is insufficient. Check both sides of each recorded break using integer counts. Keep tied values together.
- Fit once per complete D1+ or D2+ layer and save the exact breaks for that layer. Use the full three-island domain rather than an individual municipio or the visible map extent. Preserve continuous indicators and class-area/transition summaries. Use nearest neighbor if categorical ranks ever require alignment; do not bilinearly interpolate scores.
- In the final ModelBuilder **Raster Calculator**, select the actual variables for `"RiskHurricaneWinds_rank250" + "RiskDrought_rank250"`. `Combined_sum250.tif` must preserve NoData and the possible scores **2, 4, 6, 8, 10**. Do not replace unknown cells with zero or automatically turn the sum back into three classes.
- [Raster Calculator](https://doc.esri.com/en/arcgis-pro/latest/tool-reference/spatial-analyst/raster-calculator.html) requires Spatial Analyst or Image Analyst; both are available on this ArcGIS Pro 3.7 Advanced installation. Other computers must have the extension available. Use the GUI/ModelBuilder tool for the course's required branch.
- Produce two rank layouts with the same class colors/labels and one sequential sum layout at comparable scale. Include titles, legends, sources, periods, CRS, scale bar, north arrow, methods, separate NoData and the phrase **250 m output grid**, with coarser information support disclosed.

Hurricane's primary period remains 1955–2025; drought's is 2000–2025. Do not extend USDM backward or imply a shared denominator. The combined output is an equal-weight ordinal screening index, not expected loss or joint probability; tropical-cyclone rainfall and drought recovery can also be related.
