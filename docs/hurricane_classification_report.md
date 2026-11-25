# Hurricane wind hazard classification

The course score is the **number of distinct storms producing local hurricane-force wind (at least 64 kt) divided by years in the observation window**. The 2026 course map uses 1955–2025. The local wind is modeled one-minute sustained wind at 10 m. It describes physical hazard across mainland Puerto Rico, Vieques and Culebra. See the [processing plan](hurricane_processing_plan.md) and [ModelBuilder setup](hurricane_modelbuilder_setup.md).

The classifier fits three **Natural Breaks (Jenks)** groups to the valid cell counts in each window independently. It evaluates every pair of cuts between distinct counts, choosing the pair with the least variation within classes after weighting each count by its number of cells. Equal counts stay in the same class. The fit uses the full study domain for the window and records inclusive upper cutoffs. [Esri classification methods](https://doc.esri.com/en/arcgis-pro/latest/help/mapping/layer-properties/data-classification-methods.html)

| 2026 map class | Distinct qualifying storms in 1955–2025 |
| --- | ---: |
| Low (1) | 0–1 |
| Medium (3) | 2 |
| High (5) | 3–4 |
| Unknown or outside study area | NoData |

The default map assigns 34,310 cells to Low, 58,682 to Medium and 50,333 to High. Their represented land areas are **2,136, 3,666 and 3,137 km²**, respectively.

The 64 kt threshold is the NHC definition of hurricane-force wind. The score divides each cell's count by 71 years for the full record. Several storms can affect a location in one year, so annual storm rate and share of years affected are separate measures. [NHC wind scale](https://www.nhc.noaa.gov/aboutsshws.php)

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

The reviewed sources do **not** establish transferable numerical Low/Medium/High breakpoints for our particular 1955–2025 event-rate surface. The course map uses breaks fitted to the studied distribution and records the calculation and domain.

## Historical reconstruction and time windows

**Estimate Wind Fields** accounts for every storm in the audited 1,143-storm catalog. It uses the same radius/profile choice for every year. The four radius/profile pairs are 20/1.5, 40/1.4, 60/1.3 and 80/1.2 (km and dimensionless B). Choose the lowest average absolute quadrant-radius error among original observations near Puerto Rico, giving each storm equal weight. Check leave-one-storm-out stability and compare the resulting class areas across all four choices. The primary land factor is 0.8. A factor of 1.0 tests sensitivity to applying land reduction to the track intensity.

The model uses complete native tracks for motion, interpolates supported tropical/subtropical intervals with a maximum five-minute step and applies conservative distance and intensity bounds before calculating wind. The 85 missing winds are reported tropical depressions. Their intervals can be ruled out below 34 kt where the opposite endpoint and the interpolation bound support that decision. Records that could affect the score remain unresolved until accounted for.

The full run reconciled 62,485 observations across all 1,143 storms and found no unresolved years. Radius comparisons from 76 storms selected the **20 km / 1.5** common profile. The four per-storm mean absolute radius errors, averaged equally across storms, were 96.51, 101.93, 158.34 and 263.96 km, respectively. The selected profile held when leaving out each storm in turn. The saved model reran in an empty output folder and reproduced the same indicator pixels. It narrowed explicit wind calculations to 63 storms using per-profile thresholds. In that run, the largest threshold disagreement between five- and 2.5-minute sampling was **0.118%**. These checks quantify the fit to reported radii and the effect of time sampling. Comparable independent wind measurements would support an assessment of local predictive accuracy.

Storm size and land-wind reduction affect the modeled counts. The operational report classifies each tested profile using its own breaks and records the land that changes class. Read the raw count ranges to compare the magnitude of the exposure across profiles.

Use January 1 of 1986, 1991, 1996, 2001, 2006, 2011, 2016, 2021 and 2026 as reference dates. The expanding series starts in 1955. The rolling series uses the preceding 30 complete years. The 2026 maps cover 1955–2025 and 1996–2025, respectively. Each storm counts once at a cell per window using only exposures inside that window. Class breaks are fitted separately. Use the class maps to locate relative highs and lows within each period. Use storms/year from the score maps to measure changes in frequency between periods. Overlapping windows and changes in historical observing practices matter when interpreting trends. [NOAA climate and hurricanes assessment](https://www.gfdl.noaa.gov/global-warming-and-hurricanes/)

The 1986 expanding map and 1986 and 1991 rolling maps contain only zero or one qualifying storm per cell. Their event rates are retained. The wind window table records why a three-class rank is unavailable for each. It also holds exact count breaks, years, raster names and land areas for the ranked windows.

The 2026 rolling window also places the breaks after one and two storms, using 30 years for its score denominator. Its High class contains 2,922 cells. The identical count breaks in these two windows are a result of the independent fits.

## Supporting indicators and checks

- Keep the 34 kt threshold alongside 64 kt. Report years affected, last 64 kt exposure and years since it occurred. The recency raster has NoData where no exposure was observed. The frequency raster preserves supported zero.
- Calculate frequencies at ≥18, ≥26, ≥36 and ≥48 m/s as **Boose-inspired wind damage proxies**. The original Fujita damage estimate requires a gust factor and peak quarter-mile wind. The Boose return intervals describe the historical reconstruction at cumulative damage levels. See the [Boose method note](../references/boose_2004_method_notes.md) and [Harvard Forest HURRECON method](https://harvardforest1.fas.harvard.edu/exist/apps/datasets/showData.html?id=HF025).
- Keep the 100-year design wind as a separate question. A 1% annual-exceedance design wind requires a validated extreme-value or stochastic wind model and compatible wind definitions. See [FEMA's Hazus hurricane methodology for PR and the USVI](https://www.fema.gov/sites/default/files/documents/fema_hazus-hurricane-wind-puerto-rico-u.s.-virgin-islands.pdf).
- Compare the Natural Breaks course classes with Quantile, Equal Interval and the former fixed-rate rule. The validation report lists the alternative class counts and transition areas. Equal counts stay together.
- FEMA December 2025 provides `HRCN_AFREQ` for all 939 Puerto Rico census tracts. **937** tracts intersect represented study land and have comparable values. Local land-area-weighted tract means ranged from **0.003 to 0.056** hurricane-force storms/year, compared with FEMA's **0.157 to 0.242**. Pearson's r across the overlapping tracts was **0.10**, and **192** tracts contain more than one local rate. FEMA uses hurricane paths over a longer Atlantic record and a 49 km grid. These results indicate where the layers differ and where the local model shows sub-tract variation. [FEMA NRI technical documentation](https://www.fema.gov/sites/default/files/documents/fema_national-risk-index_technical-documentation.pdf)

The two default wind TIFFs use the **250 m output grid** in EPSG:32161. The shared grid aligns the wind and drought results for a cell-by-cell sum. Track positions, size assumptions and surface representation govern the information support. Read the `historical_wind` and `classification` sections of the operational validation JSON for the current result.
