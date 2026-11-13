# Puerto Rico drought: literature review and processing design

Research date: **2026-11-12**. This report recommends a method for subsequent implementation. No drought indicator or ranked raster has been produced. The [source inspection](drought_sample_and_api_findings.md) distinguishes tested facts from open questions; the [download plan](drought_download_implementation_plan.md) defines the proposed Script Tools.

## 1. Recommended scope and observation period

Use **weekly USDM polygons for 2000-01-04 through 2025-12-30** as the first drought-hazard series. Live PR statistics and the GIS directory each contain **1,357 matching Tuesday dates**, representing 26 calendar-year cohorts. Use the 2026 professor sample for ingestion tests, rather than mixing a partial year into the historical indicator.

The hurricane preparation covers seasons **1955-2025**. USDM cannot supply those 71 years: a direct API request beginning in 1955 returned no PR observations before January 4, 2000. Preserve different documented periods for the initial hazard layers. Later, evaluate a common-period 2000-2025 hurricane sensitivity product, explicitly distinguishing hurricane seasons from drought map-calendar dates. The course's ordinal sum does not require pretending that the two hazards share an observation denominator.

**If matching 1955-2025 becomes essential**, develop a separate monthly SPI/SPEI branch using a single consistent climate source across that entire period. Do not splice pre-2000 SPEI to post-2000 USDM: they represent different indicators, temporal supports, and decision rules.

## 2. Evidence matrix

The first five entries are peer-reviewed journal articles; the Puerto Rico proceedings paper is additional regional context. This exceeds the course minimum of two research articles for Drought, but the class report still needs evidence for Hurricane Winds. Agency documents supplement research; they do not replace its required article count. Full citations follow the matrix.

| Study | Area, inputs and support | Indicator / threshold | Validation and limitation | Transfer to this project |
|---|---|---|---|---|
| Leeper et al. (2022), [10.1002/joc.7653](https://doi.org/10.1002/joc.7653) | US including PR, 2000-2019; 1,044 weekly USDM maps on a 5 km grid. | D1-or-worse event onset; termination requires three subsequent D0/None weeks. Short recovery gaps can remain within an event. Counts, duration and intensification. | A historical event climatology, not a PR loss model. Comparisons with other drought measures are not independent impact validation. | Strongest direct USDM event-method precedent. Compare its recovery rule with strict consecutive-week runs; retain censor flags. Its 5 km grid does not establish 250 m accuracy. |
| Carrão, Naumann & Barbosa (2016), [10.1016/j.gloenvcha.2016.04.012](https://doi.org/10.1016/j.gloenvcha.2016.04.012) | Global/subnational assessment; historical monthly precipitation deficits at 0.5 degrees; exposure and socioeconomic inputs at other supports. | Separate hazard, exposure and vulnerability; relative risk composite. | Internal robustness/composite comparisons and geographic plausibility; not an absolute loss scale. | Supports naming the USDM product a hazard layer and adding sector-specific exposure/vulnerability only in a later risk study. Do not copy global relative classes to PR. |
| Meza et al. (2020), [10.5194/nhess-20-695-2020](https://nhess.copernicus.org/articles/20/695/2020/) | Global agricultural systems, 1980-2016; hydrologic/crop-model hazards at 0.5 degrees; irrigated and rainfed exposure. | Irrigated frequency/severity uses streamflow/demand departures from calendar-month medians in 1986-2015; rainfed hazard uses a 10% AET/PET reduction relative to its reference mean. | Sensitivity and impact-record comparisons; national vulnerability and incomplete impact records limit validation. | Demonstrates why agricultural risk needs crop/water-system information. Its thresholds and model inputs cannot be inferred from DM polygons. |
| Vicente-Serrano, Beguería & López-Moreno (2010), [10.1175/2009JCLI2909.1](https://doi.org/10.1175/2009JCLI2909.1) | Observatories with different climates; precipitation and temperature/PET inputs; multiple accumulation periods. | SPEI standardizes accumulated precipitation-minus-PET; compares with SPI and sc-PDSI. No universal PR 1/3/5 hazard scale. | Cross-index comparisons and warming experiments; source/PET choice still matters. | Method foundation for an independently computed longer-baseline climate-index branch. Define scale and calibration period before estimating event statistics. |
| Beguería et al. (2014), [10.1002/joc.3887](https://doi.org/10.1002/joc.3887) | Observational and global gridded climate series; method study rather than a PR mapping resolution. | SPEI fitting, ET methods and temporal weighting; recommends unbiased probability-weighted moments for fitting. | Shows sensitivity to ET formulation; not independent validation of a particular PR hazard map. | Requires pinned PET/fitting methods and sensitivity checks; discourages treating every SPEI implementation as interchangeable. |
| Sorí et al. (2021), [10.3390/ecas2021-10335](https://www.mdpi.com/2673-4931/8/1/40), **proceedings paper** | Mainland PR, 1950-2019; Daymet V4 precipitation/temperature, 1 km; SPEI-1. | Spatial drought-category frequencies, including SPEI-1 <= -1; episode duration, severity and peak. | Compared with documented historical episodes; one-month scale and mainland scope constrain transfer. | Regional precedent for a longer climate-index series. Do not assume its results validate other islands or resolve every drought timescale. |

### Puerto Rico planning precedent

The **2020 CDBG-MIT public-comment draft**, printed pp. 53-54, maps average annual drought weeks from USDM 2000-2019 on 0.5-square-mile hexagons. It uses five classes, with boundaries around 1, 3, 5 and 7 weeks/year. Its description does **not clearly identify the minimum DM category counted**. This supports investigating an annual-weeks indicator, but not copying its thresholds as a validated D1-based 1/3/5 rule. It is a planning reference, not another peer-reviewed article. [PR Department of Housing draft, Figure 24](https://recuperacion.pr.gov/wp-content/uploads/2020/09/CDBG_MIT_ACTION_PLAN_FULL_DRAFT_EN_2020_09_20_FOR_PUBLIC_COMMENT-Reviewed-Sept21.pdf)

## 3. What USDM measures and what the sample does not supply

USDM categories blend indicators and expert assessment. **D0 is abnormally dry; D1-D4 are drought categories.** Drought-category maps do not supply all underlying rainfall, soil moisture, streamflow or SPI/SPEI observations, and a DM polygon is not a quantified loss. Keep the optional short/long-term impact information separate; the merged sample's `DM` field does not contain it. The classification table's indicator percentiles describe category interpretation, not the annual probability of a mapped drought at a location. [UNL classification](https://droughtmonitor.unl.edu/About/AbouttheData/DroughtClassification.aspx), [tutorial](https://drought.unl.edu/Education/Tutorials/Usdm.aspx)

For the course, recommend **drought hazard ranking** as the product name. A later agricultural-risk study would need crops, irrigation and water availability; a water-supply study would need service areas, reservoirs, source catchments and demand. Local residence inside a polygon does not fully describe a person's water-supply exposure. UNL population statistics assume an even population distribution within counties/municipios and have demographic and boundary limitations; retain them as contextual exposure estimates, not cell-level damage or independently observed counts. [UNL population methodology](https://droughtmonitor.unl.edu/About/AbouttheData/PopulationStatistics.aspx)

## 4. Prepare a valid weekly series before summarizing

The following are **project design choices** to implement and test.

1. Preserve the weekly ZIPs and metadata; add `MAP_DATE`, source hash, original CRS, retrieval date, and preparation status. Dates in filenames, effective map dates, metadata creation dates and Thursday release dates are distinct.
2. Check each file's fields/geometry. Normalize literal `DM` values 0-4; missing/unknown DM is an error to investigate. Verify that the merged product contains exact, non-overlapping classes. If a different source uses nested threshold polygons, convert it explicitly to exact categories; never sum overlapping class areas.
3. Clip a working copy around PR in the source CRS before projecting large national multipart geometries. Project the subset to EPSG:32161 with a recorded transformation; recompute areas. Preserve repairs and area/geometry change diagnostics.
4. Establish an **assessed-domain ledger by date and island**, independently of the union of drought polygons. Within a verified assessed domain and a successfully acquired week, land outside D0-D4 polygons can be None. A missing ZIP, unsupported island, or unexplained coverage gap is unknown. Neither the hurricane land mask nor the union of places ever in drought proves assessment coverage. Initially keep Mona unknown unless coverage is established; test mainland, Vieques and Culebra for every historical period too.
5. Reuse the shared 250 m grid's CRS, origin, extent, rows, columns and land mask. Rasterize exact classes with **CELL_CENTER** for the first temporal prototype. Compare cell-center and area-fraction assignments on boundary-sensitive weeks before final selection. Do not interpolate DM classes with bilinear/cubic methods.
6. Use a distinct computational encoding: **None=0, D0=1, D1=2, D2=3, D3=4, D4=5; unknown=255/NoData**. Preserve literal raw DM separately. Thus source `DM=0` is D0, not None; D1-or-worse means encoded value at least 2.
7. Build an explicit expected-date calendar. A missing week is not a recovery week, a drought-free week, or a value to forward-fill. Default final-ranking eligibility requires all **1,357 valid map observations** at the cell; retain partial-coverage summaries as diagnostics.

USDM describes broad, transitional conditions. UNL reports that pre-2004 shapefiles were digitized from images, with approximately four-mile horizontal error in preliminary comparisons. Test **2004-2025** as a sensitivity period. The 250 m computational grid cannot remove that historical uncertainty or infer local terrain-driven drought differences. [UNL GIS metadata](https://droughtmonitor.unl.edu/DmData/Metadata.aspx)

## 5. Recommended multi-year indicators

Let `V(c,t)` identify a valid assessment at cell `c`, map date `t`, and `X(c,t)` be the encoding above. Use each map date once, even if its validity interval crosses a year. The initial cohort has **N=1,357 maps** and **Y=26 years**. These formulas are our proposed implementations, informed by the evidence above.

### Primary: average annual weeks in D1 or worse

For a cell with complete coverage:

`N_D1(c) = sum_t 1[V(c,t)=1 and 2 <= X(c,t) <= 5]`

`W_D1(c) = N_D1(c) / 26`  (weekly map observations per year)

Also report `F_D1(c) = 100 * N_D1(c) / 1357`, the percentage of weekly maps in drought. These contain the same information under complete coverage; do not combine both as separate weighted risk factors. `W_D1` is **not an event count/year**, and `F_D1` is **not annual drought probability**. Do not divide by 71 or assume every year contains exactly 52 maps.

A valid cell with no D1 weeks has a real zero indicator; unsupported cells remain NoData. Store `N_VALID`, `N_EXPECTED`, coverage fraction, and per-year counts with every summary. Do not hide gaps by shrinking each cell's denominator and then claiming comparability with the full-period map.

### Supporting indicators

| Indicator | Purpose and interpretation |
|---|---|
| D2-or-worse and D3-or-worse occupancy | Tests whether frequent moderate drought and infrequent intense drought give different patterns. |
| Number of events/year | Requires a declared recovery-gap rule; one persistent drought must not be counted once per week. |
| Median/maximum event duration and peak class | Separates persistence from frequency. Flag events truncated by record boundaries or unknown weeks. |
| Mean ordinal severity | Average encoded 0-5 value over valid weeks; an ordinal burden measure, not equal physical increments of water deficit. |
| Annual/seasonal occupancy | Tests whether agriculture/water supply sees hazards hidden by all-season averaging. |

For event analysis, evaluate the Leeper recovery definition above against strict runs. Retrieve up to three early-2026 recovery weeks **as a separate buffer** when needed to interpret late-2025 events; never add them to the 1,357-map indicator denominator. Events that start before reliable coverage or cannot be shown to terminate are censored.

### DSCI as a comparison measure

For an area and week, UNL defines `DSCI = sum(cumulative D0...D4 percentages)`, equivalently `1*p_D0 + 2*p_D1 + ... + 5*p_D4` using exact-category percentages. It ranges from **0 to 500** and includes abnormally dry conditions. A temporal mean keeps that range; a temporal sum depends on observation count and has a different meaning. UNL labels DSCI experimental and does not provide a universal multiyear risk classification. [UNL DSCI explanation](https://droughtmonitor.unl.edu/About/AbouttheData/DSCI.aspx)

A state DSCI time series cannot create within-island spatial contrasts. Reconstruct area-weighted DSCI from prepared polygons for QA, and compare a cell's **DSCI-style temporal ordinal burden** with `W_D1` as a sensitivity indicator. Label that cell calculation as our adaptation. Do not treat categorical D0-D4 percentages as cumulative, or add cumulative percentages with the 1-5 weights a second time. The [two observed source discrepancies](drought_sample_and_api_findings.md) must remain visible.

## 6. Ranking design and scientific checks

No reviewed source establishes universal Low/Medium/High thresholds for the proposed 2000-2025 `W_D1` surface. USDM instantaneous D1-D4 categories cannot directly classify a multi-year week-count raster.

**Recommended candidate:** fixed relative thirds of `W_D1` over the complete-coverage, shared-grid PR land domain. Calculate the 1/3 and 2/3 quantiles once, record the quantile method (initially NumPy `linear`), domain/grid hash, dates, exact numeric values and units, then freeze them. Do not recompute by municipio or map extent. Suggested boundary convention:

| Eligible indicator | Rank |
|---|---:|
| `0 <= W_D1 <= b1` | 1 |
| `b1 < W_D1 <= b2` | 3 |
| `W_D1 > b2` | 5 |
| Ineligible coverage or unknown indicator | NoData |

The numeric `b1,b2` cannot be supplied honestly before the spatial indicator exists. If ties collapse the two breakpoints, investigate another fixed classification rather than jittering data or forcing three equal cell counts. Relative high means high **within this domain and period**, not a validated damage threshold. A zero value stays eligible; its class follows the declared fixed rule.

Compare this candidate with (a) D2-based occupancy and (b) exploratory fixed `W_D1` breaks at **3 and 7 weeks/year**: Low `<=3`, Medium `(3,7]`, High `>7`. The latter adapts selected boundaries from the PR planning draft's five-bin legend; it is **our unvalidated three-bin adaptation**, and its original minimum category remains unresolved. Retain the continuous indicators whichever ranking is chosen.

Before selecting final classes:

- Recompute state/municipio threshold areas for benchmark weeks; compare with cumulative API statistics, accounting for different coastline masks and area methods. A match checks processing consistency, not independent drought skill.
- Compare the **2015 drought** and later well-documented events with rain/streamflow/reservoir observations and impact records where available. USDM already uses some such inputs; document dependence and avoid calling reused inputs independent validation.
- Compare recovery rules, D1/D2 thresholds, full versus 2004-onward periods, coastal cell assignment and alternate ranking. Publish a class-transition matrix and changed **land area**, plus rank agreement for continuous fields.
- Quantify coverage and boundary uncertainty by island; use year/event block resampling for uncertainty rather than treating adjacent weekly maps as independent trials. With 26 years, avoid unsupported long-return-period estimates.
- Check exact 250 m alignment, final integer values only 1/3/5, distinct NoData, and NoData propagation in the eventual sum with Hurricane Winds. The summed ranks remain an ordinal screening index.

## 7. Longer historical branch: realistic options

| Option | Potential role | Gate before use |
|---|---|---|
| Daymet V4 R1 climate, **1 km**, PR starts **1950** | Preferred finer-support candidate to investigate for computing a consistent SPI/SPEI series spanning 1955-2025. | Confirm the actual 2025 PR files, island masks, units/calendar and version; evaluate station support. Daymet uses a special 365-day calendar, so monthly aggregation needs explicit leap-year handling. Source documentation, not a collection's headline dates, must prove all required PR years. [ORNL dataset](https://doi.org/10.3334/ORNLDAAC/2129) |
| SPEIbase, monthly **0.5 degrees** | Coarse, ready-made long-record comparison; repository describes coverage through 2025. At PR latitude 0.5 degrees is roughly 53 km east-west by 56 km north-south. | **Do not adopt published v2.6-2.12 blindly.** Maintainer documentation reports a PET day-to-month conversion defect; v2.13 code fixes it, but a corrected data release was still described as forthcoming. Verify corrected file/version/checksum and PR cells before evaluation. [Maintainer README](https://github.com/sbegueria/SPEIbase/blob/master/README.md), [issue 19](https://github.com/sbegueria/SPEIbase/issues/19) |
| ERA5-Land monthly climate, **0.1-degree** delivered grid, from **1950** | Alternative consistent climate source for a separately specified index. | Reanalysis is not local observation. Verify island land-mask coverage, accumulation units, PET method, release status and validation. CDS access/account configuration is a separate later task. [Copernicus catalogue](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-monthly-means?tab=overview) |

For a computed branch, choose SPI-3/SPI-6 or SPEI-3/SPEI-6 for comparison, with SPEI-12 as a persistence option; these are candidates, not selected PR impact models. Freeze a defensible calibration period such as 1981-2010, fit calendar-month distributions using only that baseline, and record missing months, accumulation warm-up, PET formula and parameter fitting. Assess against USDM over the overlap without assuming their category boundaries are identical. Computing the index at its native climate support precedes 250 m alignment; resampling must not be advertised as new 250 m climate information.

## References: research articles

1. Leeper, R. D., Bilotta, R., Petersen, B., Stiles, C. J., Heim, R., Fuchs, B., Prat, O. P., Palecki, M., & Ansari, S. (2022). Characterizing U.S. drought over the past 20 years using the U.S. drought monitor. *International Journal of Climatology, 42*(12), 6616-6630. [DOI](https://doi.org/10.1002/joc.7653); [NOAA-hosted article](https://repository.library.noaa.gov/view/noaa/48743/noaa_48743_DS1.pdf).
2. Carrão, H., Naumann, G., & Barbosa, P. (2016). Mapping global patterns of drought risk: An empirical framework based on sub-national estimates of hazard, exposure and vulnerability. *Global Environmental Change, 39*, 108-124. [DOI](https://doi.org/10.1016/j.gloenvcha.2016.04.012); [repository article](https://ri.conicet.gov.ar/server/api/core/bitstreams/3e3cade0-f4b4-44cd-9cb4-aa3ce5221748/content).
3. Meza, I., Siebert, S., Döll, P., Kusche, J., Herbert, C., Eyshi Rezaei, E., Nouri, H., Gerdener, H., Popat, E., Frischen, J., Naumann, G., Vogt, J. V., Walz, Y., Sebesvari, Z., & Hagenlocher, M. (2020). Global-scale drought risk assessment for agricultural systems. *Natural Hazards and Earth System Sciences, 20*, 695-712. [DOI/article](https://doi.org/10.5194/nhess-20-695-2020).
4. Vicente-Serrano, S. M., Beguería, S., & López-Moreno, J. I. (2010). A multiscalar drought index sensitive to global warming: The standardized precipitation evapotranspiration index. *Journal of Climate, 23*(7), 1696-1718. [DOI](https://doi.org/10.1175/2009JCLI2909.1).
5. Beguería, S., Vicente-Serrano, S. M., Reig, F., & Latorre, B. (2014). Standardized precipitation evapotranspiration index (SPEI) revisited: parameter fitting, evapotranspiration models, tools, datasets and drought monitoring. *International Journal of Climatology, 34*(10), 3001-3023. [DOI](https://doi.org/10.1002/joc.3887).
6. Sorí, R., Méndez-Tejeda, R., Stojanovic, M., Fernández-Alvarez, J. C., Pérez-Alarcón, A., Nieto, R., & Gimeno, L. (2021). Spatio-temporal assessment of meteorological drought in Puerto Rico between 1950 and 2019. *Environmental Sciences Proceedings, 8*(1), 40. Proceedings contribution; [DOI](https://doi.org/10.3390/ecas2021-10335).

The [course guidelines](../SDSS%20Final%20Project%20Fall%202026.pdf) govern final grid/ranking and reporting requirements. The [download plan's source register](drought_download_implementation_plan.md#source-register) links every supplied UNL reference.
