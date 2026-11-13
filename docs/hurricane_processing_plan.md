# Hurricane Winds processing plan

## IBTrACS preparation contract

This contract defines the Hurricane Winds prototype's observations and provenance. It describes preparation, not a modeled wind footprint. The [estimation design below](#hurricane-wind-spatial-estimation-options-and-validation-gate) defines the later scientific decision gate.

## Inputs and preservation

The primary source is the local North Atlantic **IBTrACS v04r01 points shapefile** under `Hazard_Variables/Hurricanes`. Optional raw line and SPC wind-report inputs are inventoried for context; neither is substituted for the hurricane observations. SPC severe-wind reports are reports of events, not a hurricane surface or interchangeable hurricane intensity measurements.

The source files remain unchanged. Preparation stages the shapefile and matching sidecars under a safe common basename because the supplied IBTrACS basenames contain multiple dots and may not be accepted as ArcGIS dataset paths. The raw input is consequently exposed as a **File** parameter filtered to `shp`. Required sidecars are checked before use. Staging is temporary and is removed on success or failure. This is a dataset staging operation, not a repair of scientific attributes.

The output geodatabase preserves a raw point copy with the source geometry and attributes. The prepared observation feature class instead rebuilds geometry from valid **USA_LON/USA_LAT in WGS84 (EPSG:4326)**. Never substitute the combined source geometry or LAT/LON when USA coordinates are unusable. This makes the location, USA_WIND, and related agency attributes follow a declared source family. The inventory records input paths, sidecars, sizes/checksums and spatial-reference information; the audit records source geometry/USA-coordinate differences and the field-name mapping.

## Selection and row accounting

The default cohort is `TRACK_TYPE == MAIN` and **1955 <= SEASON <= 2025**, inclusive. Use the stored season, not the observation calendar year or SID prefix, to select the cohort. Retain every selected track observation across its whole lifetime; do not clip points to Puerto Rico or remove offshore/weak stages before later interpolation and modeling.

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

Keep source units in preparation. Future engines must perform explicit conversions: kt to m/s, nautical miles to km or meters, and mb/hPa to Pa where required. Conversion factors and output units belong in their manifests. No averaging-period conversion, gust factor, radius gap-fill, pressure estimate, temporal resampling, or wind-field interpolation occurs in this stage.

`OBS_TIME_UTC` is an ArcGIS date representing UTC; ISO_TIME remains available for unambiguous text exchange. Never interpret it using the workstation's local timezone. Retain existing merged storm-motion fields without replacing them with recalculated USA-track motion. A future engine must declare whether it derives motion consistently from the rebuilt USA positions.

### Storm status is not one interchangeable code system

Retain both NATURE and USA_STATUS. In **NATURE**, TS means tropical and ET means extratropical; in **USA_STATUS**, TS means tropical storm, EX means extratropical, and ET means extrapolated. A wind-speed threshold, NATURE, USA_STATUS, and USA_SSHS answer different questions. Do not infer hurricane status from the combined NATURE code. The prototype audits these categories and preserves complete selected tracks; the later model specification must choose supported states explicitly.

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

Prepared features retain source attributes with analytical missing values normalized, plus `SOURCE_OID`, `USA_IFLAG`, `OBS_TIME_UTC`, and `QC_FLAGS`. The optional CSV retains original DBF text alongside normalized core columns. Consumers should read paths from the manifest rather than depend on the current working directory. SOURCE_OID is the zero-based original shapefile record index, a traceability key for this snapshot rather than a global observation identifier.

Keep these meanings distinct downstream: **zero** is an eligible modeled/observed value; **null** is an unavailable attribute; **NoData** is unsupported spatial/temporal coverage. A prepared record's existence does not authorize an engine to turn missing pressure, radius, or wind into a calm field. Any future imputation must be separately justified, flagged, tested, and included in the coverage report.

## Acceptance checks

- Source hashes and source geometry survive preparation unchanged; staged files share a safe basename.
- The selected feature class contains only the requested seasons/main tracks, valid USA-coordinate geometries and unique SID/time observations.
- Quarantined or conflicting records remain traceable, and all row-status counts reconcile to the source.
- P, I, V, missing agency/flag values, status distributions, wind/radius availability and coordinate differences appear in the audit.
- Raw-point/QC tables reconcile with prepared observations; requested CSV exports agree too.
- No surface, probability, 1/3/5 class or hazard ranking is presented as a preparation output.


# Hurricane wind spatial estimation: options and validation gate

This is the design note for the **next** implementation round. The current prototype prepares and audits IBTrACS observations, establishes the Puerto Rico/Vieques/Culebra/Mona reference grid, and validates those products. It does not reconstruct wind fields, count exceedances, assign a hazard rank, or calculate a risk index.

## Quantity to estimate

The proposed physical quantity is each storm's maximum **10 m, 1-minute sustained wind speed** at each reference-grid cell. Keep the event identifier and a coverage mask alongside those maxima. A hurricane's reported maximum wind is the strongest wind within its circulation; it is not the wind at every location near its track. NOAA discusses measurement height, exposure, averaging periods, and the approximately 0.1-degree source resolution on printed page 5 of the [IBTrACS technical guide](https://www.ncei.noaa.gov/sites/default/files/2025-04/IBTrACS_version4r01_Technical_Details.pdf). The grid's 250 m cell size is an integration convention, not evidence of 250 m meteorological accuracy.

Use **64 kt** as the primary future hurricane-force exceedance threshold and **34 kt** as a separately labeled tropical-storm-force sensitivity scenario. The proposed historical statistic is the number of distinct storms exceeding the threshold in each cell, divided by the **71 seasons from 1955 through 2025**. Its unit is events per year. It is not the probability of at least one exceedance in a year: multiple storms can occur in a year. That probability requires distinct affected-year counts and a declared treatment of incompletely observed years. No such statistic or **1/3/5 reclassification** is implemented here.

## Candidate methods

| Candidate | Appropriate role | Main limitation to resolve |
| --- | --- | --- |
| HURRECON | First candidate for a transparent historical reconstruction and sensitivity study | Choose and justify radius of maximum wind and profile parameters; reconcile its geographic raster conventions with our projected grid. |
| CLIMADA | Independent implementation and model-choice comparison | Separate environment; make provider, imputation, distance, cutoff, and wind-model settings explicit. |
| Recorded IBTrACS quadrant radii | Compare modeled 34/50/64 kt footprints where observations exist | Coverage varies through history; missing radii cannot mean zero exposure. |
| Tropycal track proximity | Exploratory storm selection and independent track-statistics checks | Proximity is not a wind-field reconstruction. |
| `tcwind` | Small experimental Holland-model reference | Scientific normalization, missing-data behavior, and illustrative imputations require review. |

### HURRECON: first candidate, not a selected final model

HURRECON accepts track location and maximum wind, plus radius/profile parameters and a land-water representation. Its regional workflow produces peak-wind GeoTIFF products and distinguishes land/water friction; it does not require central pressure. Parameter defaults still express scientific assumptions. Its normal regional raster coordinates are latitude/longitude, so a future adapter must retain the reference grid's cell identity and document any reprojection/resampling. See the author's [Python workflow and input definitions](https://github.com/hurrecon-model/HurreconPython).

The [Harvard Forest HF446 archive](https://harvardforest1.fas.harvard.edu/exist/apps/datasets/showData.html?id=HF446) provides version 1.1 source released in 2024 and a traceable research history. This supplies a documented comparison basis, but it does not establish that the published parameter choices fit Puerto Rico. Treat alternative radius/profile values as labeled project sensitivity scenarios, not universally valid defaults. Preserve the distinction between sustained wind, gust speed, and modeled damage: these are separate outputs, and only the first matches the proposed target.

### CLIMADA: comparison with explicit controls

CLIMADA's `TropCyclone.from_tracks` models event-maximum 1-minute 10 m wind at centroids in m/s. The documented default is **H08**, with H1980, H10, and ER11 alternatives. Defaults include a **17.5 m/s storage threshold**, **300 km eye-distance cutoff**, and equirectangular distance metric; these must appear in benchmark manifests rather than remain hidden. H10 also exposes a pressure-derived maximum-wind option. See the [CLIMADA tropical-cyclone API](https://climada-python.readthedocs.io/en/stable/api/climada/climada.hazard.trop_cyclone.html).

Do not infer complete input coverage from a successful run. The [windfield source](https://climada-python.readthedocs.io/en/stable/_modules/climada/hazard/trop_cyclone/trop_cyclone_windfields.html) estimates missing RMW during conversion and contains NaN-to-zero handling. An adapter must carry an external validity mask and imputation flags. The [track importer source](https://climada-python.readthedocs.io/en/stable/_modules/climada/hazard/tc_tracks.html) also has provider selection and interpolation policies: choose USA explicitly or construct validated track objects from our canonical data; do not silently replace them with the importer's provider hierarchy.

The documentation inspected was **CLIMADA 6.1.0**. Its [installation guide](https://climada-python.readthedocs.io/en/stable/getting-started/install.html) supports Python 3.11 and allows 3.10-3.12, with substantial Conda dependencies. The local ArcGIS Pro 3.7 environment uses Python 3.13.13. A future CLIMADA benchmark belongs in a separate pinned Python 3.11 environment, exchanging CSV/JSON and grid coordinates with ArcPy. No compatibility installation or benchmark was performed in this prototype.

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

The [core API](https://github.com/zhang-962464/tcwind/blob/d3a379ce880297ee36e53be3fd741981501a30e2/tcwind/core.py) could evaluate existing cell-center coordinates through `at_points`, avoiding a second grid and large time cubes. Its default environmental pressure is 1013 mb. The four [test modules](https://github.com/zhang-962464/tcwind/tree/d3a379ce880297ee36e53be3fd741981501a30e2/tests) contain useful synthetic checks; they do not establish Puerto Rico observational skill. No remote package code was executed during this review.

## Required benchmark before selecting an engine

1. **Freeze inputs and interpretation.** Reuse the audited USA-coordinate series and fixed 250 m grid. Declare supported storm statuses, time intervals, imputation limits, physical wind definition, boundary and sea/land treatment. Retain complete selected tracks for interpolation; select candidate storms conservatively rather than clipping track points at the island boundary.
2. **Verify numerical invariants.** Test knots/m/s and nautical-mile/km conversion, cardinal directions and hemisphere rotation, calm-eye/profile behavior, preservation of an intended maximum, time ordering, zero/negative pressure deficit, missing critical inputs, and coverage masks. An unresolved input must never become an observed zero.
3. **Compare temporal/spatial convergence.** On representative storms, refine time steps until event maxima and affected area stabilize against a recorded tolerance. Compare use of existing cell centers with any reprojected output. Set and record the final tolerance before accepting a production run.
4. **Benchmark known Puerto Rico events.** Include a modern well-observed crossing event such as Maria (2017), a different track/intensity such as Georges (1998), and an older event with sparse radius/pressure data. Compare HURRECON and CLIMADA with identical data and units. Inspect point time series and footprint maps before computing historical aggregates.
5. **Separate calibration from validation.** Compare available station observations and documented wind analyses with correct height, exposure, sustained/gust definitions, and instrument limitations. NHC/IBTrACS values reused as model inputs are a consistency check, not independent validation. Hold out observations/events where feasible; report bias, absolute error, coverage, and affected-area differences.
6. **Report sensitivity and coverage.** Vary radius/profile assumptions, supported imputation rules, land treatment, time step, and 64/34 kt thresholds. Report valid-event/year denominators by cell. Present uncertainty and unsupported periods beside any final class map.

The engine selection gate requires documented input coverage, numerical tests, converged event maxima, intelligible benchmark differences, and an agreed classification method. Until these pass, no production exceedance raster or class ranking should be generated. The final class method must also match the class-wide project agreement.

## Reproducibility and code reuse

Keep research engines outside the core prototype. Pin release/commit, Python and dependency versions, model settings, input checksums, grid specification, and validation evidence for every future benchmark. Any external download must retain its URL, retrieval date, version, and license.

HURRECON and CLIMADA carry [GPL-3.0 licenses](https://github.com/hurrecon-model/HurreconPython/blob/master/LICENSE) ([CLIMADA license](https://github.com/CLIMADA-project/climada_python/blob/main/LICENSE)); [Tropycal](https://github.com/tropycal/tropycal/blob/master/LICENSE) and [`tcwind`](https://github.com/zhang-962464/tcwind/blob/main/LICENSE) use MIT. Record these before importing, adapting, or distributing code; preserve notices and license texts and make any copied/adapted code identifiable. A literature citation alone does not replace software-license obligations. This prototype vendors none of these engines and makes no claim that their defaults are validated for Puerto Rico.
