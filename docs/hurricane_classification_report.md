# Hurricane Winds: next steps toward three hazard classes

Updated 19 November 2026. **Planning report; no classification adopted.**

## Recommendation and current position

Compare **damage severity and recurrence** as the leading direction for the final index, retaining H64/H34 frequency and percentile classes as benchmarks. This goes beyond spatial percentile thirds without adopting an unvalidated combined score. First complete historical reconstruction and coverage accounting: four benchmark storms cannot establish a 71-season hazard surface.

This is a **hazard ranking for a people-focused study area**, rather than a prediction of deaths, damage or monetary loss. No population weighting or vulnerability model is proposed. Mona is outside the index scope; its presence in the shared grid is an expected audit case.

The [course assignment](../references/SDSS%20Final%20Project%20Fall%202026.pdf), especially pp. 2–5, requires justified Low/Medium/High scores of **1/3/5**, an alternative classification or aggregation rule, affected-land-area statistics, a complete executable ModelBuilder workflow and three final maps. These requirements override the older index example's 1/5/10 scores. This report supplies decisions and next actions, not completed historical results. See the [processing plan](hurricane_processing_plan.md) for preparation/model details and the [setup guide](hurricane_modelbuilder_setup.md) for existing tool parameters.

| Available now | Still needed before classification |
|---|---|
| Audited IBTrACS v04r01 snapshot: 128,098 source points, 62,485 selected observations, 1,143 storms, seasons 1955–2025. | Historical eligibility and coverage assessment, including 85 missing winds and unsupported intervals. |
| USA-family positions and winds, preserved native timestamps, interpolation flags and complete selected tracks. | A reviewed size/profile policy and surface interpretation for historical reconstruction. |
| Betsy 1956, Hugo 1989, Georges 1998 and Maria 2017; four size scenarios each; 16 retained peak rasters. | Full-cohort event counts and a cell/event coverage ledger. |
| Numerical/convergence checks passed; zero comparable station comparisons. | Review against credible references and any genuinely comparable observations available. |
| Acquisition and wind-processing models saved in the hurricane toolbox; benchmark results are available. | The wind-estimation canvas is now saved; verify its execution and extend the four-storm restriction before historical classification. |

These findings come from the existing preparation manifest, `validation_report.json` → `wind_benchmark` and tables in `output/hurricane/data/hurricane_winds.gdb`. The report records `historical_configuration_selected=false`. Its `EVALUATED` status is not approval of a historical configuration.

## 1. Evidence and what it can justify

The following three peer-reviewed papers, together with the two in the [drought report](drought_classification_report.md#1-evidence-and-transfer-to-this-project), meet the assignment's five-article minimum, including at least two per variable. Agency/software references are additional evidence.

| Research article | Study area, inputs and support | Model or thresholds | Evaluation | Transfer to this project |
|---|---|---|---|---|
| H1. Boose, Serrano & Foster (2004), [DOI](https://doi.org/10.1890/02-4057) | Puerto Rico; historical damage and HURDAT; 43 reconstructed storms, 1851–1997; regional modeling at 3 km. | HURRECON; four radius/profile pairs; F0–F3 sustained-wind ranges 18–25, 26–35, 36–47 and 48–62 m/s. | Seven storms informed parameters; 36 other storms supported damage comparison. | Strong regional reconstruction precedent. Damage-return intervals and F-scale boundaries do not establish three classes of local ≥64 kt event frequency. |
| H2. Van Beusekom et al. (2018), [article](https://www.mdpi.com/2072-4292/10/9/1386) | Maria/Irma in the U.S. Caribbean; NWS forecast tracks, 250 m MODIS and 30 m terrain. | Fitted wind profiles, terrain sheltering and accumulated energy above 17 m/s. Fields sampled at 10-minute time steps. | Compared modeled disturbance predictors with vegetation loss and landslide occurrence. | Demonstrates process and terrain effects at the target grid. Energy and forest response differ from our peak-wind/event-count indicator and human impacts. |
| H3. Cannon et al. (2023), [article](https://pmc.ncbi.nlm.nih.gov/articles/PMC10589672/) | North American Atlantic/Pacific basins; 171-/73-year HURDAT2 records; 1 km wind fields, 5 km probability aggregation and additional smoothing. | HURRECON, estimated historical size, multiple wind intensities and four k-means regimes without fixed three-class frequency cuts. | HRRR comparison and radius-model evaluation; size uncertainty remains. | Supports multievent analysis and explicit size estimation. Four ecological regimes and long-record probabilities cannot be copied as our three frequency classes. |

**Full citations**

- **H1:** Boose, E. R., Serrano, M. I., & Foster, D. R. (2004). Landscape and regional impacts of hurricanes in Puerto Rico. *Ecological Monographs, 74*(2), 335–352. [10.1890/02-4057](https://doi.org/10.1890/02-4057). [Full-text research article](https://pdfs.semanticscholar.org/7632/47802f778a053698388872411912bf8f7d27.pdf).
- **H2:** Van Beusekom, A. E., Álvarez-Berríos, N. L., Gould, W. A., Quiñones, M., & González, G. (2018). Hurricane Maria in the U.S. Caribbean: Disturbance forces, variation of effects, and implications for future storms. *Remote Sensing, 10*(9), 1386. [10.3390/rs10091386](https://doi.org/10.3390/rs10091386).
- **H3:** Cannon, J. B., Peterson, C. J., Godfrey, C. M., & Whelan, A. W. (2023). Hurricane wind regimes for forests of North America. *PNAS, 120*(42), e2309076120. [10.1073/pnas.2309076120](https://doi.org/10.1073/pnas.2309076120).

The [NHC wind scale](https://www.nhc.noaa.gov/aboutsshws.php) supports 64 kt as hurricane-force intensity, not a Low/Medium/High recurrence crosswalk. Its five storm-intensity categories are different from the course's three scores. The [Harvard Forest HURRECON documentation](https://harvardforest1.fas.harvard.edu/exist/apps/datasets/showData.html?id=HF446) explains the profile and land/water assumptions; these still need a project-specific assessment.

The reviewed sources do **not** establish transferable numerical Low/Medium/High breakpoints for our particular 1955–2025 event-rate surface. Relative classification is therefore a defensible candidate under the assignment, provided the reference domain and breaks are frozen and their meaning is stated.

## 2. Finish historical reconstruction and the H64 benchmark

For storm `s` and cell `c`, estimate its local peak **10 m, one-minute sustained wind** `P_s(c)` over the declared supported tropical/subtropical phases. Five-minute model sampling describes the time between calculations, not a change to the wind's averaging period. Then calculate:

`N64(c) = number of distinct storms with P_s(c) >= 64 kt`

`H64(c) = N64(c) / 71`, in events/year for seasons 1955–2025.

Use `64 × 1852/3600 = 32.924444… m/s` and, for sensitivity, `34 × 1852/3600 = 17.491111… m/s`. Compare full-precision values, rounding only for display. Count a storm once at a cell, regardless of its duration, number of observations or number of size scenarios. Preserve separate scenario results.

`H64` is an empirical event rate. It is not the proportion of years affected, the probability of at least one event, or a fitted return-period estimate. A supported zero remains eligible; unsupported potential exposure remains NoData. Do not divide by the number of usable years at each cell to hide gaps.

### Required decisions before a production run

1. **Review size and surface assumptions.** Current scenarios are RMW/B = 20 km/1.5, 40/1.4, 60/1.3 and 80/1.2. Retain them as sensitivity cases until a fixed or storm-varying policy is justified. The current land factor is 0.8, with no terrain sheltering; assess whether applying it to USA maximum winds around landfall reduces an already land-affected intensity twice.
2. **Resolve historical support.** Audit missing winds, phases and temporal gaps by storm/season. Keep complete selected tracks for motion and interpolation. Missing winds/radii are not zero. A storm can be excluded as noncontributing only through a documented conservative bound; distance to its track alone is insufficient.
3. **Document coverage explicitly.** For each cell, account for every potentially contributing storm as evaluated, demonstrably below threshold or unresolved. A full-period rate requires resolved contribution status. Record unsupported periods without shrinking the 71-season denominator.
4. **Approve numerical settings for broader conditions.** Five-minute sampling passed the benchmark's comparison with 2.5 minutes: worst P99 peak difference ≈0.054 m/s and worst 64 kt footprint disagreement ≈0.089% of current study-land cells. Recheck representative fast, compact, weak and nearby storms when extending the cohort; the benchmark does not bound every cell's error.

Current Maria comparisons illustrate why size cannot be selected from numerical convergence alone:

| RMW/B | 64 kt radius MAE, km |
|---|---:|
| 20/1.5 | 29.98 |
| 40/1.4 | 107.25 |
| 60/1.3 | 232.31 |
| 80/1.2 | 395.62 |

Each row uses 120 positive quadrant/time comparisons from **one storm**, reusing IBTrACS information. This is source consistency, not 120 independent observations or proof that the smallest radius fits all historical storms. No configuration is selected by this report.

### Keep production outputs manageable

Recommend streaming one storm's peak array at a time into threshold counts and coverage accounting. Retain one event/configuration catalog and the necessary summaries, rather than thousands of permanent event rasters. Keep selected diagnostic peaks where they support review. Preserve source hashes and settings so results can be reproduced. A validated bound may avoid unnecessary calculations; an arbitrary clipping radius must not silently turn distant or unresolved exposure into zero.

Comparable station observations and a paired CLIMADA run would strengthen evaluation. They are optional additional work, not specific assignment requirements. The course permits credible reference data where independent observations are unavailable. Disclose that limitation and avoid calling source reuse independent validation. CLIMADA would require a separate pinned environment; no new modeling dependency is needed for the minimum HURRECON route.

## 3. Classification candidates for review

| Candidate | Definition | Interpretation and disposition |
|---|---|---|
| **Baseline comparison:** frozen relative thirds of `H64` | Calculate 1/3 and 2/3 quantiles once over eligible cells of the three-island index mask, using NumPy `linear`. | Relative local hurricane-force frequency within the chosen period/domain. Exact breaks are unavailable until historical reconstruction is complete. |
| **Required aggregation sensitivity:** `H34 = N34/71` | Repeat with local peaks ≥34 kt and calculate its own frozen thirds on the same eligible comparison domain. | Tests how conclusions change when tropical-storm-force winds count. It measures a different intensity threshold; compare class transitions and continuous patterns. |
| Published damage/recurrence or regime classes | Review H1/H3, preserving their original indicator, support and definitions. | Do not transfer directly: modified damage ratings and four multivariate ecological regimes do not provide this project's three event-rate classes. |

For the relative candidate, the proposed crosswalk is:

| Eligible `H64` | Class | Score |
|---|---|---:|
| `0 <= H64 <= b1` | Low | 1 |
| `b1 < H64 <= b2` | Medium | 3 |
| `H64 > b2` | High | 5 |
| Outside index scope or unresolved historical support | Unknown/outside scope | NoData |

Store breakpoints in both events/year and equivalent storm-count units, with method, reference period, domain/grid identity and boundary convention. Do not split equal storm counts to force equal class sizes or recompute breaks by municipio, zoom level or map extent. If the two quantiles coincide, stop class selection and review a fixed-count alternative with the class; do not invent decimal separation. A valid zero must stay eligible, and an all-zero surface cannot justify three distinct hazard levels.

For the 34/64 comparison, use identical model assumptions and report any change in eligible area separately. Quantify both a score transition matrix and changed clipped land area; relative High under one indicator is not the same physical condition as High under the other. Also compare at least two size assumptions before recommending one production configuration. A 2000–2025 hurricane subset can be an optional period sensitivity alongside drought; it does not replace the declared 71-season primary period.

## 4. Implementation order and future handoffs

| Step | Work to complete | Result needed to proceed |
|---|---|---|
| 1 | Assemble **Prepare Wind Inputs → Estimate Wind Fields → Evaluate Wind Estimates** using the setup guide; execute the actual saved model. | Reproducible benchmark graph and retained outputs. |
| 2 | Review size/friction assumptions, references and historical missingness. | Approved production configuration and explicit coverage policy. |
| 3 | Extend the four-storm restriction to the selected historical cohort, preserving benchmark mode. Stream local maxima into count/coverage products. | Historical indicator, event catalog and current validation assessment. |
| 4 | Compare damage/recurrence and annual-exceedance candidates with H64/H34 and size sensitivities; inspect maps and affected land area. | A documented recommendation and class-wide agreement; no automatic threshold adoption. |
| 5 | Implement a classification branch: check inputs → apply the agreed crosswalk → evaluate ranked output. | `RiskHurricaneWinds_rank250.tif` and a classification section in the existing operational report. |
| 6 | Connect the raw-data/preparation, historical and classification submodels into the complete course model. | Successful execution into a clean workspace, then individual/combined map layouts. |

Keep existing entrypoints, packages, toolbox names and aliases. The future classification branch should take the validated historical handoff, shared grid, agreed classification table and output folder. Its public results should be the ranked raster and existing validation handoff; supporting tables remain discoverable through that report/catalog. A benchmark-only handoff must fail historical classification.

Record the approved crosswalk in a geodatabase table, not just layer symbology. Keep the current one-report-per-hazard approach. Proposed handoffs are design recommendations; no new Script Tool interface or saved graph is introduced by this report.

## 5. Acceptance and course integration

- Use EPSG:32161, 250 × 250 m, origin anchored at (0,0), 1,140 columns × 267 rows and extent (40,750, 209,750)–(325,750, 276,500). Derive the final three-island index mask on this lattice; preserve the shared reference grid.
- Require integer valid ranks **only 1, 3 or 5**, correct threshold equality, valid zeros, preserved NoData and a reproducible frozen reference. The 250 m output grid does not establish 250 m wind accuracy.
- Report class counts and land areas, alternative-rule transitions and coverage exclusions. Use geometric cell/land intersections for clipped areas; do not count ocean portions as land.
- Test a clean end-to-end saved-model run, retained outputs and input relocation. Close ModelBuilder tabs/Pro before any toolbox replacement, following repository rules.
- Feed this rank and `RiskDrought_rank250.tif` into the course's **Raster Calculator** branch. Select the actual model variables to form `"RiskHurricaneWinds_rank250" + "RiskDrought_rank250"`. Preserve NoData and the possible sums **2, 4, 6, 8, 10**; do not classify the sum again.
- ArcGIS Pro 3.7 Advanced and both Spatial Analyst/Image Analyst are available locally. The existing NumPy-based tools do not establish extension entitlement elsewhere. [Raster Calculator requires Spatial Analyst or Image Analyst](https://doc.esri.com/en/arcgis-pro/latest/tool-reference/spatial-analyst/raster-calculator.html) and is an application/ModelBuilder tool, not an `arcpy.sa.RasterCalculator` call.
- Produce two individual rank maps and one sum map at comparable scale, with consistent Low/Medium/High colors, legends, sources, periods, CRS, scale bar, north arrow and methods notes. Show NoData separately and retain the sum's 2–10 scale.

The two hazards have different observation periods and physical units. Their sum is an equal-weight ordinal screening index, not joint probability or expected loss. Tropical-cyclone rainfall can also affect drought recovery, so independence should not be assumed.

**Next review:** choose a defensible historical size/surface policy, verify the damage-scale conversion and assess the richer candidates below before selecting hurricane rank breaks. The drought branch can advance independently while that work is completed.


## Damage, recurrence and a reference-year planning index

### Validated lessons from Boose

The reusable [Boose method note](../references/boose_2004_method_notes.md) records printed-page references, table meanings, calibration changes and the distinction between F and EF damage. The 3 km regional reconstruction, 0.5 km municipality display and 30 m Luquillo EXPOS study are separate products. Their relevance is methodological; none establishes 250 m wind accuracy.

The quoted F0+/F1+/F2+/F3 intervals are cumulative, geographically varying results. A rare F3 event can be more severe than a frequent F0 event; recurrence alone cannot order different severities. The reported 4/6/15?33/50?150 years must not be turned directly into our three class boundaries. F1 can already imply meaningful roof/window damage, so even a proposed Low group must be explained carefully.

### Reference year and temporal quantities

The proposed default is **ReferenceYear=2026**, an as-of planning snapshot using complete seasons **1955?2025**. It is not a forecast of storms during 2026. Changing the label to a later year does not add observations or automatically raise risk; an earlier retrospective reference requires a cutoff before that year and a newly documented denominator.

Future analysis should retain, for each cell:

- Storm-specific peak winds and consistently defined damage proxies.
- Counts of storms exceeding each wind/damage threshold; event rate `lambda=N_events/71` and event-based mean interval `71/N_events` where events were observed.
- Complete-year maximum winds, including supported years with no modeled event, plus the number of years with at least one exceedance. Annual probability estimate `p=N_affected_years/71` differs from storm rate when multiple events occur in one year.
- Temporal percentiles of annual maximum wind, such as P50/P95/P99. These describe a wind distribution at a location; H64's spatial percentiles describe relative event rates across locations.
- Last exceedance year as a descriptive chronology field, without an overdue-storm multiplier.

For an illustrative **30-year horizon (2026?2055)**, `1-(1-p)^30` expresses at-least-one exceedance probability only under declared stationarity and independent-year assumptions. A 1% annual-exceedance level would imply about 26% over 30 years under those assumptions. A 100-year return level is not an event scheduled once per century. Supported zero events remain valid observations, but do not establish zero future probability or an infinite true return interval. Coverage gaps remain NoData and uncertainty must accompany rare-event estimates.

### Richer candidates to compare before choosing a score

| Candidate | What it adds beyond H64 thirds | Evidence needed before use |
|---|---|---|
| Damage-threshold frequency curves | Separate F0+, F1+, F2+ and F3+ storm rates and affected-year probabilities; examine F2+/F3+ at a fixed severity. | Verified original-F conversion or an explicitly labeled proxy; full historical coverage and sensitivity to size/surface assumptions. |
| Damage severity at a common annual-exceedance probability | Compare the potential severity associated with the same rarity at every cell, potentially including a 1% annual-exceedance wind scenario. | A credible PR return-level source or justified statistical model, compatible wind definition and documented uncertainty. |
| Severity/likelihood planning assessment | Consider annual and 30-year damaging-wind likelihood alongside severity, with the same reference year. | A reviewed decision matrix or crosswalk; no arbitrary multiplication or double-counting of overlapping cumulative thresholds. |
| H64/H34 and relative thirds | Keep the existing transparent wind-frequency candidates as comparison baselines. | Historical indicator and frozen domain-wide breaks; relative classes do not become damage probabilities. |

Two three-class damage groupings should be compared as **project adaptations**, not Boose's published risk scale:

| Proposed grouping | Low = 1 | Medium = 3 | High = 5 |
|---|---|---|---|
| More precautionary structural-damage grouping | Supported no damage or F0 | F1 | F2 or higher |
| Greater separation of severe damage | Supported damage below F2 | F2 | F3 or higher |

Unknown remains NoData in both. The second option puts some consequential F1 damage in Low and needs an explicit justification. Neither grouping alone accounts for recurrence; test it at a common scenario probability or within a separately justified severity/likelihood approach. Preserve continuous wind and cumulative probability products for interpretation. No weights, time-decay rule or final crosswalk are adopted here.

A faithful original-F implementation must verify the gust/fastest-quarter-mile conversion and continuous thresholds. Table 1's rounded sustained-wind ranges can support an approximate proxy only if labeled accordingly. Modern HURRECON EF outputs require their own named scale and grouping. Our current peak-wind benchmark produces neither scale.

### What would make a 100-year wind product defensible?

An empirical P99 from 71 annual maxima is an unstable description of the top of a short record; it is not by itself an established 100-year design wind. First assess an authoritative regional source, checking Puerto Rico/Vieques/Culebra coverage, version, return-period definition, wind averaging period, height, exposure, terrain treatment, native support, downloadable data and reuse conditions.

[FEMA's PR/USVI Hazus documentation](https://www.fema.gov/sites/default/files/documents/fema_hazus-hurricane-wind-puerto-rico-u.s.-virgin-islands.pdf), ?5.5, documents Caribbean probabilistic hurricane capability. [Vickery et al.'s hazard-model paper](https://doi.org/10.1061/NHREFO.NHENG-1637) provides a regional stochastic-model lead. This establishes a source to investigate, not a verified ready-to-use 100-year raster or compatibility with our installed Pro workflow. Peak 3-second gusts, tract-level quantities and one-minute sustained winds cannot be merged through an undocumented conversion. NHC [climatological return maps](https://www.nhc.noaa.gov/climo/index.php) concern storm passage within 50 nautical miles, which is also different from local wind exceedance.

If suitable data cannot be obtained and reconciled, leave the 100-year product unavailable. A local extreme-value fit or long stochastic simulation would need a separate method, diagnostics and uncertainty study; it is not an automatic interpolation step or a requirement to complete this documentation round.

### Resolution, future handoff and implementation gates

The common **250 m output grid** can contain resampled coarser estimates. Record the native/model grid, effective information support, resampling method and classification order. Current HURRECON code evaluates the parametric field directly at 250 m centers; it does not currently resample a coarse wind raster. For any future coarse input, harmonize the continuous wind statistic using a justified method before the chosen damage/ranking calculation, and preserve native support. Categorical ranks use nearest-neighbor alignment if needed. Sampling more cells creates no new observations.

The next scientific implementation should proceed in this order: review historical size/surface/coverage policy; verify F or EF conversion; compute per-storm and annual-maxima products; evaluate cumulative damage frequencies and wind percentiles; assess an external return-level candidate if available; compare proposed three-class groupings and changed land areas; obtain agreement on the final crosswalk. Retain separate computational, observational and classification checks.

Future metadata should include `ReferenceYear`, observation start/end, denominator, planning horizon, `DamageScale`, wind statistic, surface/exposure policy, coverage and classification version. These are proposed design fields, not new parameters on the current six-field wind model. Existing entrypoints, toolboxes, reference grid, people-focused three-island scope and final 1/3/5 plus NoData standards remain in place.
