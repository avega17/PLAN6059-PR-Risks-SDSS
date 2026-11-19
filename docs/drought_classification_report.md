# Drought: next steps toward three hazard classes

Prepared 18 November 2026. **Planning report; candidate comparisons only. No classification adopted.**

## Recommendation and current position

Use **average annual D1-or-worse weeks** as the first classification candidate. Evaluate fixed domain-wide thirds against an exploratory 3/7-weeks rule before agreeing final thresholds. The calculations below use existing validated data; they do not create ranked rasters or approve a final crosswalk.

The [course assignment](../references/SDSS%20Final%20Project%20Fall%202026.pdf), pp. 2–5, requires evidence, explicit Low/Medium/High scores of **1/3/5**, an alternative rule, affected-land-area statistics, an executable model and individual/combined maps. The older index example's 1/5/10 scores are not the final standard.

The study domain is mainland PR, Vieques and Culebra. Mona is an expected out-of-scope audit case. This geographical scope does not introduce population weighting: the proposed product is a physical **hazard ranking**, not a model of human losses or water-service vulnerability.

| Available now | Remaining work |
|---|---|
| Saved **Drought_Process_USDM** model executed successfully; computational assessment `VALIDATED`. | Review continuous patterns and reference comparisons before approving classes. |
| 1,357 baseline maps, 2000-01-04–2025-12-30; 26 calendar years. | Compare and select a classification method with the class. |
| Three January 2026 end buffers, kept outside historical denominators. | Freeze approved breaks, reference domain and equality rules. |
| 143,325 complete-coverage study cells; occupancy, severity and both event-rule summaries. | Add a classification/sensitivity/validation branch and final course integration. |
| Existing cell/annual/event tables and 11 indicator rasters. | Export the final rank and prepare individual/combined map layouts. |

Inputs are `output/drought/reports/download_validation.json` → `processing` and `output/drought/data/drought_processing.gdb`. Top-level acquisition `passed` alone is insufficient; the nested processing assessment must be current. The [processing plan](drought_processing_plan.md) covers source semantics and computations; the [setup guide](drought_modelbuilder_setup.md) explains the saved workflow.

## 1. Evidence and transfer to this project

These two peer-reviewed articles plus the three in the [hurricane report](hurricane_classification_report.md#1-evidence-and-what-it-can-justify) meet the course minimum of five distinct articles, with at least two per hazard.

| Research article | Study area, inputs and support | Indicator/thresholds | Evaluation | Transfer to this project |
|---|---|---|---|---|
| D1. Leeper et al. (2022), [article](https://repository.library.noaa.gov/view/noaa/48743/noaa_48743_DS1.pdf) | U.S. including PR; 1,044 weekly USDM maps, 2000–2019, on a 5 km grid. | D1+ drought events; termination at the last D1+ week followed by at least three D0/None weeks; frequency, duration and intensification. | Event climatology and precipitation/context comparisons, rather than PR loss validation. | Supports D1+ and the three-week recovery comparison. Does not establish 1/3/5 multiyear classes or 250 m information accuracy. We retain valid zero occupancy, rather than copying missing-value choices for event-only figures. |
| D2. Carrão, Naumann & Barbosa (2016), [article](https://www.droughtmanagement.info/literature/EC-JRC_Global%20Mapping%20of%20Drought%20Risk_2016.pdf) | Global/subnational assessment; monthly GPCC precipitation, 1901–2010, at 0.5°, plus exposure and socioeconomic data. | WASP deficit severity relative to the global severe-deficit median; separate hazard, exposure and vulnerability. | Robustness and geographic-pattern comparisons; not a calibrated PR loss scale. | Justifies calling our USDM-only layer hazard. Its global risk classes and exposure inputs cannot be substituted for local drought-week breakpoints. |

**Full citations**

- **D1:** Leeper, R. D., Bilotta, R., Petersen, B., Stiles, C. J., Heim, R., Fuchs, B., Prat, O. P., Palecki, M., & Ansari, S. (2022). Characterizing U.S. drought over the past 20 years using the U.S. drought monitor. *International Journal of Climatology, 42*(12), 6616–6630. [10.1002/joc.7653](https://doi.org/10.1002/joc.7653).
- **D2:** Carrão, H., Naumann, G., & Barbosa, P. (2016). Mapping global patterns of drought risk: An empirical framework based on sub-national estimates of hazard, exposure and vulnerability. *Global Environmental Change, 39*, 108–124. [10.1016/j.gloenvcha.2016.04.012](https://doi.org/10.1016/j.gloenvcha.2016.04.012).

### Official categories and the local planning precedent

[USDM defines D1–D4 as drought and D0 as abnormally dry](https://droughtmonitor.unl.edu/About/AbouttheData/DroughtClassification.aspx). These are weekly assessment categories. Their indicator percentile ranges do not classify a 26-year average number of drought weeks. Likewise, [DSCI](https://droughtmonitor.unl.edu/About/AbouttheData/DSCI.aspx) is an experimental area-based 0–500 summary, not an authoritative multiyear risk crosswalk.

The [2020 PR CDBG-MIT public-comment draft](https://recuperacion.pr.gov/wp-content/uploads/2020/09/CDBG_MIT_ACTION_PLAN_FULL_DRAFT_EN_2020_09_20_FOR_PUBLIC_COMMENT-Reviewed-Sept21.pdf), Figure 24, printed p. 53, describes 2000–2019 average drought weeks on 0.5-square-mile hexagons, with five bins using cutoffs around 1, 3, 5 and 7 weeks. Its minimum counted DM category remains unresolved. The indexed official figure and earlier processing-plan review support that description; direct full-PDF retrieval returned 403 during this review. Therefore **3/7 weeks is our exploratory three-bin adaptation**, not a verified published D1 hazard standard. This planning document supplements the research articles.

## 2. Indicator, eligibility and candidate crosswalks

For a cell with all 1,357 baseline observations:

`N_D1 = number of weekly maps with encoded state 2 through 5`

`W_D1 = N_D1 / 26`, in weekly map observations per year.

The encoding is None=0, D0=1, D1=2, …, D4=5; unknown=255. Unknown must never pass a drought predicate. All 143,325 study cells are eligible in this snapshot. A valid zero remains a real zero. Buffers, ocean, out-of-scope cells and unsupported observations cannot be used to inflate denominators or fill missing values with low hazard.

`W_D1` measures time spent in drought, not events/year or annual drought probability. `F_D1 = 100 × N_D1/1357` contains the same information here and should not be added as another weighted factor.

### Candidate A: frozen relative thirds — recommended for review

Calculate unweighted 1/3 and 2/3 quantiles over all eligible three-island cell centers, using NumPy `method='linear'`. Current results are exactly **38 and 78 drought-map observations**, equivalent to **38/26 = 1.4615384615… and 3.0 weeks/year**.

| Class | Exact count rule | Weeks/year interpretation | Score |
|---|---|---|---:|
| Low | `0 <= N_D1 <= 38` | `0 <= W_D1 <= 38/26` | 1 |
| Medium | `38 < N_D1 <= 78` | `38/26 < W_D1 <= 3` | 3 |
| High | `N_D1 > 78` | `W_D1 > 3` | 5 |
| Unknown/outside scope | Ineligible observation coverage or outside index mask | No indicator assigned | NoData |

These are **candidate reference breaks**, not adopted thresholds. Count rules avoid rounding a displayed decimal into a different boundary. Equal counts stay together; class sizes need not be identical. All 2,812 zero-occupancy cells fall in Low under both candidates.

Recommend this candidate for a relative course screening map because its reference and calculation are explicit and the reviewed sources do not establish a portable three-class threshold for this indicator. Approximately balanced area is a descriptive consequence, not proof of validity. High means high relative occupancy within this domain/period, not severe weekly drought or a validated damage level.

### Candidate B: exploratory fixed 3/7-weeks breaks

| Class | Exact count rule | Weeks/year rule | Score |
|---|---|---|---:|
| Low | `0 <= N_D1 <= 78` | `0 <= W_D1 <= 3` | 1 |
| Medium | `78 < N_D1 <= 182` | `3 < W_D1 <= 7` | 3 |
| High | `N_D1 > 182` | `W_D1 > 7` | 5 |
| Unknown/outside scope | Same eligibility as Candidate A | No indicator assigned | NoData |

Fixed numerical units are easy to explain across maps, but the adaptation still needs justification. Its substantially smaller High area is not evidence that it is more accurate or that Candidate A overstates losses.

## 3. Measured comparison on the current data

The analysis read existing rasters and calculated ranks **in memory only**. A temporary 250 m fishnet was intersected with the existing projected Natural Earth boundary for mainland PR, Vieques and Culebra. Category areas sum each cell's intersected land portion using planar square meters in EPSG:32161, converted to km². Ocean is excluded. These are explicit geometric intersections of a generalized boundary, not claims of precise coastal mapping.

The denominator is **8,939.20 km² of land represented by eligible cell centers**. The three-island polygon totals 8,957.71 km²; another 18.51 km² lies in coastal cells whose centers fall outside the mask. Those slivers are excluded by the existing cell-center assignment, not missing weekly data. Do not use `cell count × 0.0625 km²` as the clipped land denominator. Intersection totals reconciled with the polygon within 0.26 m² numerical difference.

| Class | Candidate A cells | A land, km² | A land % | Candidate B cells | B land, km² | B land % |
|---|---:|---:|---:|---:|---:|---:|
| Low / 1 | 48,160 | 2,997.26 | 33.53 | 95,603 | 5,958.94 | 66.66 |
| Medium / 3 | 47,443 | 2,961.68 | 33.13 | 43,213 | 2,698.52 | 30.19 |
| High / 5 | 47,722 | 2,980.26 | 33.34 | 4,509 | 281.74 | 3.15 |
| **Total** | **143,325** | **8,939.20** | **100.00** | **143,325** | **8,939.20** | **100.00** |

### Transition matrix: A → B

Cells are shown below; parentheses give clipped land area in km².

| Candidate A \ Candidate B | Low / 1 | Medium / 3 | High / 5 |
|---|---:|---:|---:|
| Low / 1 | 48,160 (2,997.26) | 0 | 0 |
| Medium / 3 | 47,443 (2,961.68) | 0 | 0 |
| High / 5 | 0 | 43,213 (2,698.52) | 4,509 (281.74) |

**90,656 cells change class: 63.25% of cells, representing 5,660.20 km² or 63.32% of represented land.** All changes are toward a lower score under B because its cutoffs are higher. This is method sensitivity, not an accuracy assessment.

| Island | Represented land, km² | Changed land, km² | Island land changing class |
|---|---:|---:|---:|
| Mainland | 8,764.74 | 5,529.79 | 63.09% |
| Vieques | 148.86 | 119.93 | 80.57% |
| Culebra | 25.60 | 10.48 | 40.95% |

The thresholds were calculated once across the whole reference domain, not independently for each island. Percentages are land-based, not percentages of people, households or water customers.

### Supporting sensitivities

`W_D1` ranges from 0 to 8.96 weeks/year, with a cell mean of 2.57. The existing `W_D2` mean is 0.55 weeks/year; the 2004–2025 `W_D1_2004` mean is 2.96. These cell means describe different thresholds/periods and are not population-weighted.

Next, compare continuous spatial patterns for D1 versus D2 and 2000–2025 versus 2004–2025. For a period-only class sensitivity, keep Candidate A's absolute weeks/year cuts fixed; recomputing period-specific quantiles would also change the reference classification. Compare strict versus three-week-recovery event counts and completed durations as persistence diagnostics, with censored spans kept separate. Do not combine occupancy, equivalent percentage occupancy and persistence into an unreviewed composite.

Existing six-week cell-center/dominant-area comparisons show 99.960–100% assignment agreement. They do not establish independent drought skill or guarantee all-week insensitivity. Acquisition retains 231 source-layout and reference-data warnings; known Culebra discrepancies remain documented rather than corrected by force. Pre-2004 digitization uncertainty, the generalized coastline and dependence between USDM and its underlying weather indicators still matter.

## 4. Implementation order and future handoffs

1. **Review the two candidate maps and evidence.** Temporary previews can support discussion; do not deliver either as the approved result yet. Compare the 2015 event and later documented droughts with credible rainfall, streamflow, reservoir or impact records where available. Record which references also informed USDM; reused inputs are not independent validation.
2. **Agree and freeze the classification.** Record exact count/week cuts, inclusive boundaries, method, 2000–2025 period, eligible mask and grid/boundary identities. If the class-approved boundary changes, recompute affected indicators, areas and candidate breaks before freezing them.
3. **Implement the third drought branch.** Use visible stages for checking classification inputs, applying the agreed ranking and evaluating it. Read the current validated metrics handoff, grid, classification table and output folder. Publish `RiskDrought_rank250.tif` and update the existing operational report's classification assessment; retain supporting tables inside the existing workspace.
4. **Verify the saved model.** Connect model output variables between stages rather than selecting old files manually. Keep derived outputs durable. Run into a clean output workspace and verify exact thresholds, rank values, coverage, paths with spaces and retention after model completion.
5. **Integrate the course model and layouts.** Connect acquisition → processing → classification as a complete branch, combine with the validated hurricane rank, and present the required individual/sum maps.

Proposed handoffs are recommendations for the next implementation. This report adds no Script Tool interface, dependency, permanent analysis script, classification configuration or ranked dataset. Raw archives, receipts, current metrics and validation JSON were left unchanged by the comparison.

## 5. Final checks and combined map

- Keep EPSG:32161, 250 × 250 m, anchor (0,0), 1,140 × 267 cells and extent (40,750, 209,750)–(325,750, 276,500). Apply the same three-island index mask to both hazards without changing the reference lattice.
- Require integer valid scores **1/3/5**, valid zeros handled by the crosswalk, and NoData outside the domain or where support is insufficient. Test values equal to 38, 78 and 182 counts and immediately adjacent counts when checking the candidate rules. Never split ties or classify rounded legend values.
- Freeze the reference once; do not reclassify by municipio or map extent. Preserve continuous indicators and class-area/transition summaries. Use nearest neighbor if categorical ranks ever require alignment; do not bilinearly interpolate scores.
- In the final ModelBuilder **Raster Calculator**, select the actual variables for `"RiskHurricaneWinds_rank250" + "RiskDrought_rank250"`. `Combined_sum250.tif` must preserve NoData and the possible scores **2, 4, 6, 8, 10**. Do not replace unknown cells with zero or automatically turn the sum back into three classes.
- [Raster Calculator](https://doc.esri.com/en/arcgis-pro/latest/tool-reference/spatial-analyst/raster-calculator.html) requires Spatial Analyst or Image Analyst; both are available on this ArcGIS Pro 3.7 Advanced installation. Other computers must have the extension available. Use the GUI/ModelBuilder tool for the course's required branch.
- Produce two rank layouts with the same class colors/labels and one sequential sum layout at comparable scale. Include titles, legends, sources, periods, CRS, scale bar, north arrow, methods, separate NoData and the phrase **250 m output grid**, with coarser information support disclosed.

Hurricane's primary period remains 1955–2025; drought's is 2000–2025. Do not extend USDM backward or imply a shared denominator. The combined output is an equal-weight ordinal screening index, not expected loss or joint probability; tropical-cyclone rainfall and drought recovery can also be related.

**Next review:** compare the two candidate interpretations with the professor/class, inspect their spatial patterns and supporting sensitivities, then agree the crosswalk to implement. The current analysis supports that discussion without preselecting the final classes.
