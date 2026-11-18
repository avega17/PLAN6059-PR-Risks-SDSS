# Hurricane Winds processing plan

The preparation workflow and the three wind-benchmark Script Tools are implemented. The benchmark produced 16 peak-wind rasters for four storms and four size scenarios, with all proposed five-to-2.5-minute convergence checks passing. Individual Script Tool execution, 13 offline regression tests and a relocated-package run have passed. The separate wind ModelBuilder canvas still needs assembly and saved-model execution; follow the [setup guide](hurricane_modelbuilder_setup.md).

This establishes a working computational benchmark. Comparable station validation, a paired CLIMADA comparison, historical coverage accounting and selection of the historical size configuration remain open. Full-period event rates and 1/3/5 classification follow those evaluation decisions.

## IBTrACS preparation contract

This contract defines the Hurricane Winds prototype's observations and provenance. The [wind-estimation section below](#hurricane-wind-spatial-estimation-options-and-validation-gate) distinguishes the implemented benchmark from the remaining scientific decisions.

## Inputs and preservation

The primary source is the local North Atlantic **IBTrACS v04r01 points shapefile** under `Hazard_Variables/Hurricanes`. Optional raw line and SPC wind-report inputs are inventoried for context; neither is substituted for the hurricane observations. SPC severe-wind reports are reports of events, not a hurricane surface or interchangeable hurricane intensity measurements.

The source files remain unchanged. Preparation stages the shapefile and matching sidecars under a safe common basename because the supplied IBTrACS basenames contain multiple dots and may not be accepted as ArcGIS dataset paths. The raw input is consequently exposed as a **File** parameter filtered to `shp`. Required sidecars are checked before use. Staging is temporary and is removed on success or failure. This is a dataset staging operation, not a repair of scientific attributes.

The output geodatabase preserves a raw point copy with the source geometry and attributes. The prepared observation feature class instead rebuilds geometry from valid **USA_LON/USA_LAT in WGS84 (EPSG:4326)**. Never substitute the combined source geometry or LAT/LON when USA coordinates are unusable. This makes the location, USA_WIND, and related agency attributes follow a declared source family. The inventory records input paths, sidecars, sizes/checksums and spatial-reference information; the audit records source geometry/USA-coordinate differences and the field-name mapping.

## Selection and row accounting

The default cohort uses an exact, case-insensitive `main` match after trimming TRACK_TYPE and **1955 <= SEASON <= 2025**, inclusive. Use the stored season, not the observation calendar year or SID prefix, to select the cohort. Retain every selected track observation across its whole lifetime; do not clip points to Puerto Rico or remove offshore/weak stages before interpolation and modeling.

An exact duplicate means identical source attributes and source geometry, with source object ID excluded from the comparison. Remove those duplicates deterministically while recording them. Conflicting rows with the same SID and timestamp are a separate condition: retain their evidence in QC tables and stop preparation rather than silently selecting an intensity or location.

Selected records missing a usable SID, UTC timestamp, or USA coordinate pair are quarantined: preserve them in the raw-point/QC accounting, and exclude them from the prepared spatial observations. Missing wind, pressure, radii, or agency text alone does not remove an otherwise usable observation. Successful spatial preparation does not mean the record is ready for a physical model.

The raw-point feature class and QC table account for every active source row. SOURCE_OID connects the prepared records to the snapshot. Row statuses are INCLUDED, EXCLUDED_TRACK_TYPE, EXCLUDED_SEASON, QUARANTINED, DUPLICATE_EXACT and CONFLICT. Counts must reconcile to the raw-point table; deleted DBF records are reported separately. CSV is an optional export, off by default. Future adapters should consume normalized prepared attributes and preserve QC/coverage.


## Field semantics and project policy

The source authority is NOAA's [v04r01 column guide](https://www.ncei.noaa.gov/sites/default/files/2025-09/IBTrACS_v04r01_column_documentation.pdf). The original CSV names can differ from shapefile field names; the inventory/audit's actual field map is authoritative for a run. Important groups are:

| Fields | Meaning used by this project |
| --- | --- |
| SID, SEASON, ISO_TIME | Storm identity, selected season, and UTC observation time. |
| USA_LAT, USA_LON | Agency-family coordinates for rebuilt WGS84 geometry. |
| USA_WIND | 1-minute sustained maximum wind, knots. |
| USA_PRES, USA_POCI | Central/environmental pressure, mb; preserve missing values. |
| USA_RMW, USA_ROCI | Radius of maximum wind/outer closed isobar, nautical miles. |
| USA_R34/50/64_NE/SE/SW/NW | Quadrant wind-threshold radii, nautical miles. |
| USA_AGENCY, IFLAG | Reporting-source and interpolation provenance. |
| STORM_SPEED/STORM_SPD, STORM_DIR/STORM_DR | IBTrACS merged motion fields; audit provenance separately. |

The [NOAA technical guide](../references/IBTrACS_version4r01_Technical_Details.pdf) discusses averaging/height on printed page 5, uncertainty and reporting differences on pages 7-11, interpolation/spurs on pages 11-12, and combined/USA variables on pages 18-19. The USA family can change supplying agency between timestamps. Preserve those changes; never fill a blank USA_AGENCY from a neighboring row or infer it from the basin.

### Interpolation flags

`USA_IFLAG` is derived from **the first character** of the 15-character IFLAG, not from the entire string. NOAA's flag definitions are: O original; P position and other quantities interpolated/filled; I position supplied but intensity filled; V original position/intensity with some other values filled; underscore means no report. These are provenance labels, not numerical quality scores. See printed page 2 of the column guide.

Retain P records and blank agency text in the selected prepared data and report their counts. This explicitly permits IBTrACS interpolation while making it visible. Do not call the retained dataset an original-only observation sample. A blank/short IFLAG yields an unavailable USA flag and a QC observation, not an invented flag. Subsequent model-specific interpolation/imputation must add its own provenance rather than overwrite the raw IFLAG.

### Missing values and units

Normalize documented numerical missing sentinels to null for analytical use while retaining the source copy. Do not apply one negative-value rule to every field: negative longitude and latitude are legitimate, and USA_SSHS includes valid negative categorical codes. Preserve zero values for review; neither a missing wind nor an absent radius is zero exposure. Report unexpected ranges and unsupported values instead of quietly clamping them.

Keep source units in preparation. Downstream engines must perform explicit conversions: kt to m/s, nautical miles to km or meters, and mb/hPa to Pa where required. Conversion factors and output units belong in their settings or manifests. No averaging-period conversion, gust factor, radius gap-fill, pressure estimate, temporal resampling, or wind-field interpolation occurs in preparation.

`OBS_TIME_UTC` is an ArcGIS date representing UTC; ISO_TIME remains available for unambiguous text exchange. Never interpret it using the workstation's local timezone. Retain existing merged storm-motion fields in preparation. The wind benchmark derives separate motion from the USA positions; it does not overwrite those source fields.

### Storm status is not one interchangeable code system

Retain both NATURE and USA_STATUS. In **NATURE**, TS means tropical and ET means extratropical; in **USA_STATUS**, TS means tropical storm, EX means extratropical, and ET means extrapolated. A wind-speed threshold, NATURE, USA_STATUS, and USA_SSHS answer different questions. Do not infer hurricane status from the combined NATURE code. Preparation preserves complete selected tracks; the wind benchmark explicitly models NATURE TS/SS intervals, including tropical depressions when otherwise usable.

## Outputs and consumer rules

| Product | Use |
| --- | --- |
| `hurricane_prepare.gdb/raw_ibtracs_points` | Preserved raw ArcGIS dataset with source geometry. |
| `hurricane_prepare.gdb/hurricane_observations` | Selected, deduplicated, spatially usable USA-coordinate observations. |
| `hurricane_prepare.gdb/hurricane_storms` | Distinct-storm summary and coverage information. |
| `hurricane_prepare.gdb/hurricane_qc` | Record-level exclusions, provenance and quality evidence. |
| `hurricane_observations.csv` | Optional portable export; off by default. |
| `source_inventory.json` | Source inventory and schema/provenance facts. |
| `prepare_manifest.json` | Machine-readable locations and preparation summary. |

Prepared features retain source attributes with analytical missing values normalized, plus `SOURCE_OID`, `USA_IFLAG`, `OBS_TIME_UTC`, and `QC_FLAGS`. The optional CSV contains all active source rows, including excluded rows, with original DBF text, normalized core columns and row dispositions; its row count differs from the selected feature class. Consumers should read paths from the manifest rather than depend on the current working directory. SOURCE_OID is the zero-based original shapefile record index, a traceability key for this snapshot rather than a global observation identifier.

Keep these meanings distinct downstream: **zero** is an eligible modeled/observed value; **null** is an unavailable attribute; **NoData** is unsupported spatial/temporal coverage. A prepared record's existence does not authorize an engine to turn missing pressure, radius, or wind into a calm field. Any future imputation must be separately justified, flagged, tested, and included in the coverage report.

## Acceptance checks

- Source hashes and source geometry survive preparation unchanged; staged files share a safe basename.
- The selected feature class contains only the requested seasons/main tracks, valid USA-coordinate geometries and unique SID/time observations.
- Quarantined or conflicting records remain traceable, and all row-status counts reconcile to the source.
- P, I, V, missing agency/flag values, status distributions, wind/radius availability and coordinate differences appear in the audit.
- Raw-point/QC tables reconcile with prepared observations; requested CSV exports agree too.
- No surface, probability, 1/3/5 class or hazard ranking is presented as a preparation output.


# Hurricane wind spatial estimation: options and validation gate

The preparation workflow audits IBTrACS observations and establishes the shared grid. The implemented HURRECON benchmark reconstructs wind fields for Betsy, Hugo, Georges and Maria under four size scenarios. Review these results before selecting the configuration for historical event rates and hazard ranking.

## Quantity to estimate

The benchmark target is each storm's maximum **10 m, 1-minute sustained wind speed** over supported tropical/subtropical intervals at each study-land cell. The catalog preserves event identity; the shared study mask supplies spatial coverage and exterior NoData. Separate event/year temporal-coverage products are not yet implemented and must accompany historical aggregation. A hurricane's reported maximum wind is the strongest wind within its circulation; it is not the wind at every location near its track. NOAA discusses measurement height, exposure, averaging periods, and the approximately 0.1-degree source resolution on printed page 5 of the [IBTrACS technical guide](https://www.ncei.noaa.gov/sites/default/files/2025-04/IBTrACS_version4r01_Technical_Details.pdf). The grid's 250 m cell size is an integration convention, not evidence of 250 m meteorological accuracy.

Use **64 kt** as the primary future hurricane-force threshold and **34 kt** as a separately labeled tropical-storm-force sensitivity scenario. The proposed historical statistic is the number of distinct storms reaching or exceeding the threshold in each cell, divided by the **71 seasons from 1955 through 2025**. Its unit is events per year. It is not the probability of at least one exceedance in a year: multiple storms can occur in a year. That probability requires distinct affected-year counts and a declared treatment of incompletely observed years. No such statistic or **1/3/5 reclassification** is implemented here.

## Candidate methods

| Candidate | Appropriate role | Main limitation to resolve |
| --- | --- | --- |
| HURRECON equations | Implemented local benchmark for historical-reconstruction design and sensitivity study | Choose and justify radius/profile parameters and surface treatment; historical configuration remains unselected. |
| CLIMADA | Independent implementation and model-choice comparison | Separate environment; make provider, imputation, distance, cutoff, and wind-model settings explicit. |
| Recorded IBTrACS quadrant radii | Compare modeled 34/50/64 kt footprints where observations exist | Coverage varies through history; missing radii cannot mean zero exposure. |
| Tropycal track proximity | Exploratory storm selection and alternative track-statistics checks | Proximity is not a wind-field reconstruction. |
| `tcwind` | Small experimental Holland-model reference | Scientific normalization, missing-data behavior, and illustrative imputations require review. |

### HURRECON: implemented benchmark, historical parameters pending

The reference HURRECON package accepts track location and maximum wind, plus radius/profile parameters and a land-water representation. Its regional workflow produces peak-wind GeoTIFF products and distinguishes land/water friction; it does not require central pressure. Parameter defaults still express scientific assumptions. See the author's [Python workflow and input definitions](https://github.com/hurrecon-model/HurreconPython).

Our implementation uses the published equations with NumPy rather than invoking that package. It transforms the existing projected cell centers to WGS84, evaluates winds there, and writes the results directly onto the original EPSG:32161 lattice. No geographic wind raster is generated or resampled. An external-engine comparison must preserve those same evaluation locations.

The [Harvard Forest HF446 archive](https://harvardforest1.fas.harvard.edu/exist/apps/datasets/showData.html?id=HF446) provides version 1.1 source released in 2024 and a traceable research history. This supplies a documented comparison basis, but it does not establish that the published parameter choices fit Puerto Rico. Treat alternative radius/profile values as labeled project sensitivity scenarios, not universally valid defaults. Preserve the distinction between sustained wind, gust speed, and modeled damage: these are separate outputs, and only the first matches the proposed target.

### CLIMADA: comparison with explicit controls

CLIMADA's `TropCyclone.from_tracks` models event-maximum 1-minute 10 m wind at centroids in m/s. The documented default is **H08**, with H1980, H10, and ER11 alternatives. Defaults include a **17.5 m/s storage threshold**, **300 km eye-distance cutoff**, and equirectangular distance metric; these must appear in benchmark manifests rather than remain hidden. H10 also exposes a pressure-derived maximum-wind option. See the [CLIMADA tropical-cyclone API](https://climada-python.readthedocs.io/en/stable/api/climada/climada.hazard.trop_cyclone.html).

Do not infer complete input coverage from a successful run. The [windfield source](https://climada-python.readthedocs.io/en/stable/_modules/climada/hazard/trop_cyclone/trop_cyclone_windfields.html) estimates missing RMW during conversion and contains NaN-to-zero handling. An adapter must carry an external validity mask and imputation flags. The [track importer source](https://climada-python.readthedocs.io/en/stable/_modules/climada/hazard/tc_tracks.html) also has provider selection and interpolation policies: choose USA explicitly or construct validated track objects from our canonical data; do not silently replace them with the importer's provider hierarchy.

CLIMADA 6.2.0 is available. The newer development installation documentation lists Python 3.11 as supported and 3.11-3.13 as allowed, while some stable documentation pages still display the older matrix. Pin the release and its environment specification when evaluating compatibility. A separate comparison environment remains the deployment choice for CLIMADA. Its installation guidance includes Mamba, Conda and Pixi options. The current benchmark uses ArcGIS Pro's bundled NumPy and ArcPy. [Releases](https://github.com/CLIMADA-project/climada_python/releases), [installation](https://climada-python.readthedocs.io/en/latest/getting-started/install.html).

### Recorded radii and Tropycal

Where available, the four USA quadrant radii describe the recorded maximum reach of the **34, 50, and 64 kt** wind thresholds in nautical miles. They are a useful footprint comparison and coverage audit, not complete continuous wind fields. No observed radius is invented where absent; avoid interpolating across unsupported time spans or treating blank/zero radii as universal evidence of no wind. Definitions are on printed page 4 of the [IBTrACS column guide](https://www.ncei.noaa.gov/sites/default/files/2025-09/IBTrACS_v04r01_column_documentation.pdf).

Tropycal can find analog tracks near points/shapes and calculate track statistics. Its [TrackDataset API](https://tropycal.github.io/tropycal/api/generated/tropycal.tracks.TrackDataset.html) defaults to online HURDAT2, excludes recent best-track additions unless requested, and has separate IBTrACS provider modes. Pin the data snapshot and provider rather than accepting defaults. Its [data-source discussion](https://tropycal.github.io/tropycal/data.html) explains agency differences. Hourly interpolated point proximity can miss a fast crossing between samples; continuous segment-distance checks are more suitable for selection. Neither approach establishes local hurricane-force wind. Tropycal is not a prototype dependency, and its compatibility with the local Pro environment has not been tested.

### `tcwind`: findings from static source inspection

The inspected revision is [`d3a379ce880297ee36e53be3fd741981501a30e2`](https://github.com/zhang-962464/tcwind/tree/d3a379ce880297ee36e53be3fd741981501a30e2), the initial June 8, 2026 commit. The repository had no tags or releases at inspection. Its [manifest](https://github.com/zhang-962464/tcwind/blob/d3a379ce880297ee36e53be3fd741981501a30e2/pyproject.toml) declares version 0.1.0, Python >=3.9, NumPy >=1.20, and optional netCDF4. This is a dependency description, not a successful ArcGIS compatibility test.

The [ingestion module](https://github.com/zhang-962464/tcwind/blob/d3a379ce880297ee36e53be3fd741981501a30e2/tcwind/data/ibtracs.py) reads CSV using combined `LAT/LON` with USA wind, pressure, and RMW. It does not enforce our USA-coordinate/provenance policy or read the local shapefiles directly. Its interpolation can extend observed RMW to endpoints; its RMW gap-filler explicitly uses illustrative western North Pacific coefficients. Those choices need flags and basin-specific review.

Static deductions from the [physics implementation](https://github.com/zhang-962464/tcwind/blob/d3a379ce880297ee36e53be3fd741981501a30e2/tcwind/physics/holland.py), **not executed or observed failures**:

- Missing pressure or RMW can become zero radial wind through `nan_to_num`; with finite positions and Vmax, an unresolved input can therefore appear calm.
- B derives from input Vmax, and the final field receives a 0.9 surface factor. In the stationary, equatorial, unclipped-B case, 50 m/s input yields a 45 m/s modeled peak. The treatment of an already surface-based USA_WIND needs normalization review.
- The translation correction has zero weight for exactly opposing flow, so its stated opposite-side reduction is not guaranteed by the implementation.
- The optional intensity/latitude B formula is explicitly illustrative, and the engine does not apply land friction or terrain effects.

The [core API](https://github.com/zhang-962464/tcwind/blob/d3a379ce880297ee36e53be3fd741981501a30e2/tcwind/core.py) could evaluate existing cell-center coordinates through `at_points`, avoiding a second grid and large time cubes. Its default environmental pressure is 1013 mb. The four [test modules](https://github.com/zhang-962464/tcwind/tree/d3a379ce880297ee36e53be3fd741981501a30e2/tests) contain useful synthetic checks; they do not establish Puerto Rico observational skill. No tcwind code was executed during this review.

## Evaluation before historical processing

| Evaluation | Current evidence | Remaining work |
|---|---|---|
| Inputs and interpretation | Audited USA tracks, fixed grid, declared TS/SS intervals and explicit units; four benchmark storms pass input checks. | Resolve historical missing winds and unsupported intervals; document completeness before extending the cohort. |
| Numerical behavior | Offline tests cover conversion, geometry, wind-profile behavior, interpolation, missing inputs and exact-bound optimization. A temporary 1,000-case scalar-speed comparison matched the author's implementation to floating-point precision; see [notices](../THIRD_PARTY_NOTICES.md). | Inspect representative point histories and maps. Pressure-deficit tests apply if a pressure-based comparison engine is added. |
| Temporal and spatial support | All 16 default cases pass the proposed five-to-2.5-minute checks at the same grid centers. | Review the tolerance and boundary. Spatial-resolution sensitivity and external-raster resampling comparisons have not been performed; 250 m alignment alone does not validate spatial detail. |
| Model comparison | Four HURRECON size scenarios are calculated for Betsy, Hugo, Georges and Maria. | The paired CLIMADA experiment remains pending; use identical tracks, locations, wind definitions and explicit engine controls. |
| Observational evaluation | Positive IBTrACS quadrant radii support a source-consistency comparison; comparable station comparisons currently number zero. | Reconcile height, exposure, sustained/gust definitions and recording windows. Separate calibration from validation and hold out observations/events where feasible. |
| Historical indicator and classes | The target is distinct storms exceeding 64 kt per cell over 71 seasons; 34 kt is a sensitivity threshold. | Review size and surface assumptions, add historical coverage accounting and agree the class method. Preserve the fixed denominator; do not silently renormalize incomplete coverage or count it as no events. |

Before historical production, review input completeness, numerical behavior, convergence, model/reference differences and the historical configuration together. Unsupported periods must remain visible. The final class method must also match the class-wide project agreement. These scientific decisions do not prevent assembling and testing the benchmark ModelBuilder canvas now.

## Reproducibility and code reuse

Keep external research engines outside the ArcGIS environment. Pin release/commit, Python and dependency versions, model settings, input checksums, grid specification, and validation evidence for every future benchmark. Any external download must retain its URL, retrieval date, version, and license.

HURRECON and CLIMADA carry [GPL-3.0 licenses](https://github.com/hurrecon-model/HurreconPython/blob/master/LICENSE) ([CLIMADA license](https://github.com/CLIMADA-project/climada_python/blob/main/LICENSE)); [Tropycal](https://github.com/tropycal/tropycal/blob/master/LICENSE) and [`tcwind`](https://github.com/zhang-962464/tcwind/blob/main/LICENSE) use MIT. Record these before importing, adapting, or distributing code; preserve notices and license texts and make any copied/adapted code identifiable. The local benchmark implements the published mathematical equations independently and attributes their sources. Source code from those engines is not bundled.

## HURRECON benchmark implementation

The implemented workflow defaults to four storms and four size scenarios before choosing a historical configuration. Its primary field is peak local one-minute sustained wind in m/s. The optional storm parameter accepts subsets of those four named SIDs, and a custom size table can replace the default pairs. Historical-cohort support must be added after the benchmark review. Model tropical and subtropical phases (`NATURE=TS/SS`), retain full USA-coordinate tracks, and derive motion from those positions. The fixed 250 m grid remains a computational convention with a generalized provisional coastline.

### Corrections to the supplied comparison report

The report's performance claim requires a paired model experiment. Our local implementation choice follows deployment needs and the Puerto Rico research precedent. Historical size remains uncertain even when central pressure is unnecessary.

- Boose's Table 1 lists sustained winds of 18-25, 26-35, 36-47 and 48-62 m/s for F0-F3. The suggested Saffir-Simpson crosswalk and recurrence classification cannot be attributed to those table boundaries. The 64 kt hurricane-force threshold converts to 32.924444... m/s and 34 kt to 17.491111... m/s. Use `1852/3600` for knots-to-m/s conversion.
- The four tested size pairs are 20 km/B=1.5, 40/1.4, 60/1.3 and 80/1.2. The report's 30/1.4 combination is a project assumption. Recalculating its stationary 135 kt, 30 km/B=1.4 example gives outer 64 kt radii of 166.85 km over water and 116.25 km over land. Its claimed CLIMADA comparison and plotted radii need correction.
- Actual snapshot checks found 62,400/62,485 usable winds (99.86%), positive pre-1979 central pressure in 6,908/19,907 records (34.70%), and positive pre-2004 RMW in 1,939/39,435 records (4.92%). There are 85 missing winds, all in USA_STATUS=TD/NATURE=TS records, and zero positive pre-2004 R64 quadrant radii. Preserve these limitations when extending the benchmark cohort.
- Van Beusekom's study fits storm parameters, applies terrain sheltering, and computes gale-wind energy. Those features require additional work beyond the friction-only benchmark.
- Correct the report's bibliographic attribution to Cannon et al. (2023), rather than Ibanez, for the North American hurricane-regime paper. Correct Van Beusekom's author list and treat STORM generation and wind-probability papers as separate publications. The population-exposure paper is by Jing et al., rather than Chen.

### Evidence matrix

| Article | Data and spatial support | Indicator/model and thresholds | Evaluation and transfer to this project |
|---|---|---|---|
| Boose, E.R., Serrano, M.I. & Foster, D.R. (2004), *Landscape and regional impacts of hurricanes in Puerto Rico*, Ecological Monographs 74, 335-352. [DOI](https://doi.org/10.1890/02-4057) | HURDAT and historical damage; 43 reconstructed storms, 1851-1997; regional modeling at 3 km and finer damage/exposure analyses | HURRECON sustained wind, gust and Fujita damage; four size/profile combinations | Seven storms informed parameterization; 36 others supported independent damage comparison. Supplies equations and sensitivity cases. Damage recurrence and local wind-force frequency need separate interpretation. |
| Van Beusekom, A.E., Alvarez-Berrios, N.L., Gould, W.A., Quinones, M. & Gonzalez, G. (2018), *Hurricane Maria in the U.S. Caribbean: Disturbance Forces, Variation of Effects, and Implications for Future Storms*, Remote Sensing 10, 1386. [DOI](https://doi.org/10.3390/rs10091386) | Maria/Irma NWS forecasts; MODIS 250 m EVI; 30 m terrain summarized at target cells | Fitted HURRECON profiles, 10-minute winds, terrain sheltering and gale-wind energy above 17 m/s | Vegetation/landslide response models evaluated against observed effects. Supports a process-based 250 m calculation; canopy response also depends on landscape properties. |
| Cannon, J.B., Peterson, C.J., Godfrey, C.M. & Whelan, A.W. (2023), *Hurricane wind regimes for forests of North America*, PNAS 120, e2309076120. [DOI](https://doi.org/10.1073/pnas.2309076120) | Western North Atlantic/eastern North Pacific tracks, 1851-2022; 886 selected hurricanes | HURRECON wind fields, estimated storm size, wind-threshold recurrence and regional regimes | Includes HRRR model comparison and uncertainty in radius prediction. Supports multi-event wind analysis and the need to evaluate size assumptions; an external model comparison has different information support from station measurements. |
| Holland, G.J. (2008), *A revised hurricane pressure-wind model*, Monthly Weather Review 136, 3432-3445. [DOI](https://doi.org/10.1175/2008MWR2395.1) | Hurricane pressure, wind and motion data | Pressure-wind relationship underlying the H08 alternative | Explains physical inputs and historical pressure uncertainty. Useful for evaluating an alternative model; our local field inventory determines actual pressure availability. |
| Aznar-Siguan, G. & Bresch, D.N. (2019), *CLIMADA v1: a global weather and climate risk assessment platform*, GMD 12, 3085-3097. [DOI](https://doi.org/10.5194/gmd-12-3085-2019) | Global hazard/exposure datasets and application examples with varying spatial support | Hazard, exposure, impact and adaptation framework | Supports reproducible alternative hazard modeling. Use current version-specific API documentation for wind-model controls. Loss-function parameters require exposure and vulnerability interpretation. |

### Calculation and retained products

`Prepare Wind Inputs` rechecks the actual preparation/grid, publishes full native tracks and a cell-center table, and records hashes, units and settings in `hurricane_winds.gdb`. Transform EPSG:32161 cell centers to WGS84 with the recorded transformation. Great-circle distances use the author's 6367 km spherical radius and bearings use true north. The model evaluates winds directly at these cell centers.

`Estimate Wind Fields` evaluates all selected size scenarios jointly at maximum intervals of 15, 5 and 2.5 minutes. Each native interval is divided into equal pieces no longer than the requested step, preserving its endpoints; the resulting series need not have a uniform cadence. Latitude, unwrapped longitude and wind are linear between valid native endpoints. Motion is derived from full native USA positions and interpolated from segment midpoints, with circular heading interpolation. Supported intervals require valid wind endpoints, at most six hours separation and TS/SS at both endpoints. Unsupported transitions are excluded from the modeled-phase interval; isolated eligible observations or missing eligible winds stop the benchmark. The wind-track table retains USA_IFLAG, agency, status and SOURCE_OID; the full original IFLAG remains accessible in prepared observations through that source key.

Each radius/B pair is constant throughout each modeled storm. Recorded USA_RMW and pressure are not used to fit those values. Every study-land cell uses F=0.8 and asymmetry S=1, with the published nonnegative speed limit; F=1 is used in water-exposure radius comparisons and optional WATER station calculations. No land-cover friction raster or terrain sheltering is implemented. USA_WIND is treated as an over-water maximum, including around landfall. Applying the additional land factor could reduce an intensity already affected by land; assess this assumption before selecting production parameters.

Streaming maxima avoid retaining a time-by-cell cube. An enclosing-circle upper bound can skip a time sample only when it cannot increase any cell's current maximum; there is no arbitrary 350 km screen or wind-storage cutoff.

The default run retains 16 five-minute peak rasters in the geodatabase, one per storm/size pair; subsets or custom scenario tables change that count. Fifteen- and 2.5-minute arrays serve convergence evaluation and are released after comparison. The event catalog associates SID, storm name, radius, B, nominal time step, raster name and input fingerprint. Exterior cells remain NoData. Geodatabase tables hold timing, convergence, positive quadrant-radius comparisons, optional station comparisons and footprint summaries; full point time series are not retained. Reruns replace the workflow-owned tables and remove obsolete benchmark rasters, keeping one current result.

The existing operational `validation_report.json` receives a `wind_benchmark` section. Top-level `passed` describes preparation only. Wind `status=EVALUATED` means evaluation completed; convergence failure produces a warning and is retained as `temporal_convergence_passed=false`, while unavailable station comparisons remain zero. Read these fields separately from `computational_checks_passed`. The code records `historical_configuration_selected=false`; selecting and implementing a historical configuration remains a subsequent decision.

Running Validate Prototype recreates that report and clears the wind section. After changing preparation inputs or the grid, rerun the complete wind chain from Prepare Wind Inputs to regenerate the assessment; the retained wind geodatabase alone does not establish a current handoff.

`Evaluate Wind Estimates` checks the retained rasters, exact grid, valid land coverage and provenance. The proposed 5-to-2.5-minute tolerances are P99 absolute peak difference <=1 m/s and disagreement at each of 34/64 kt <=1% of study land cells. Failed convergence is retained visibly for review. Computational/data failures raise tool errors. Positive R34/R64 values within 500 km of the enclosing study circle are compared with the modeled maximum water-exposure threshold radius in each quadrant; original and filled source flags are counted. This geographical window limits reference comparisons, not wind-field calculation. These comparisons reuse IBTrACS inputs and describe source consistency.

P99 and footprint disagreement summarize all study-land cells. The maximum absolute difference is also recorded, but is not a pass criterion. Passing these tolerances does not establish a per-cell error bound or guarantee adequate sampling for each smaller island; inspect local differences when reviewing maps.

Optional station comparisons require documented 60-second winds at 10 m within 0.5 m, land/water exposure, complete UTC observation windows and source references. Model each window at intervals no longer than 2.5 minutes, including its exact endpoints; reject windows crossing unsupported phases or extending beyond modeled coverage. Reject lower-bound/incomplete or mismatched observations rather than applying unverified gust/averaging conversions. Comparison rows retain the source, location, exposure, height and window. Empty station comparison tables mean independent station skill remains unmeasured; the report counts station/scenario comparison rows, not unique stations.

In the radii comparison table, ORIGINAL counts USA_IFLAG O/V (original position and intensity); FILLED counts other source flags. V can still include filled radii or other fields, so these are row-provenance groups, not proof that a particular radius was measured independently. Zero, missing and nonpositive radii are excluded from the comparison rather than interpreted as observed zero extent.

The benchmark uses Betsy 1956 (`1956222N13313`), Hugo 1989 (`1989254N13340`), Georges 1998 (`1998259N10335`) and Maria 2017 (`2017260N12310`). Review the scenarios together before selecting the historical configuration. The later indicator is distinct storms with local peak >=64 kt divided by 71 seasons, with 34 kt as a secondary measure and explicit incomplete-coverage handling. Hurricane ranks and the drought/hurricane sum follow that evaluation.

The NHC Maria tropical cyclone report was examined for comparable station observations. Table 4, pages 17-18, includes Puerto Rico winds with varying heights and incomplete records. Its page 23 footnotes specify two-minute sustained winds for land reports unless noted and eight-minute buoy winds unless noted. The one-minute offshore examples are measured at 4-5 m. These values need an additional exposure/averaging method before direct one-minute, 10 m validation. The optional station comparison remains empty until qualifying records are supplied. [NHC Maria report](https://www.nhc.noaa.gov/data/tcr/AL152017_Maria.pdf).

The initial four-storm calculation met the proposed five-to-2.5-minute tolerances across all 16 cases: the largest P99 peak difference was 0.054 m/s and the largest 64 kt footprint disagreement was 0.089% of study land cells (rounded upward). This supports five-minute sampling for these cases, not a selected historical size configuration. Only Maria supplies positive R34/R64 values in the reference window. Its 64 kt radius MAE was about 30 km for 20 km/B=1.5 and 107 km for 40 km/B=1.4; larger scenarios diverged further. These results show consequential size sensitivity and do not establish station skill or a universally appropriate radius.
