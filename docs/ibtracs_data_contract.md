# IBTrACS preparation and audit contract

This contract defines the Hurricane Winds prototype's observations and provenance. It describes preparation, not a modeled wind footprint. The [future estimation note](hurricane_wind_estimation_options.md) defines the later scientific decision gate.

## Inputs and preservation

The primary source is the local North Atlantic **IBTrACS v04r01 points shapefile** under `Hazard_Variables/Hurricanes`. Optional raw line and SPC wind-report inputs are inventoried for context; neither is substituted for the hurricane observations. SPC severe-wind reports are reports of events, not a hurricane surface or interchangeable hurricane intensity measurements.

The source files remain unchanged. Preparation stages the shapefile and matching sidecars under a safe common basename because the supplied IBTrACS basenames contain multiple dots and may not be accepted as ArcGIS dataset paths. The raw input is consequently exposed as a **File** parameter filtered to `shp`. Required sidecars are checked before use. This is a dataset staging operation, not a repair of scientific attributes.

The output geodatabase preserves a raw point copy with the source geometry and attributes. The prepared observation feature class instead rebuilds geometry from valid **USA_LON/USA_LAT in WGS84 (EPSG:4326)**. Never substitute the combined source geometry or LAT/LON when USA coordinates are unusable. This makes the location, USA_WIND, and related agency attributes follow a declared source family. The inventory records input paths, sidecars, sizes/checksums and spatial-reference information; the audit records source geometry/USA-coordinate differences and the field-name mapping.

## Selection and row accounting

The default cohort is `TRACK_TYPE == MAIN` and **1955 <= SEASON <= 2025**, inclusive. Use the stored season, not the observation calendar year or SID prefix, to select the cohort. Retain every selected track observation across its whole lifetime; do not clip points to Puerto Rico or remove offshore/weak stages before later interpolation and modeling.

An exact duplicate means identical source attributes and source geometry, with source object ID excluded from the comparison. Remove those duplicates deterministically while recording them. Conflicting rows with the same SID and timestamp are a separate condition: retain their evidence in QC and CSV outputs and stop preparation rather than silently selecting an intensity or location.

Selected records missing a usable SID, UTC timestamp, or USA coordinate pair are quarantined: preserve them in the canonical CSV/QC accounting, and exclude them from the prepared spatial observations. Missing wind, pressure, radii, or agency text alone does not remove an otherwise usable observation. Successful spatial preparation does not mean the record is ready for a physical model.

The canonical CSV accounts for raw records, including excluded, duplicate, and quarantined rows through `ROW_STATUS`. Source object IDs connect records back to the source. A future engine must first filter **`ROW_STATUS == INCLUDED`** and consume `NORMALIZED_*` fields rather than raw DBF text. Statuses are INCLUDED, EXCLUDED_TRACK_TYPE, EXCLUDED_SEASON, QUARANTINED, DUPLICATE_EXACT and CONFLICT. All active-row statuses must sum to the active source-row count; the inventory separately reports deleted DBF records. Distinguish record counts from distinct-storm counts.

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

The [NOAA technical guide](../IBTrACS_version4r01_Technical_Details.pdf) discusses averaging/height on printed page 5, uncertainty and reporting differences on pages 7-11, interpolation/spurs on pages 11-12, and combined/USA variables on pages 18-19. The USA family can change supplying agency between timestamps. Preserve those changes; never fill a blank USA_AGENCY from a neighboring row or infer it from the basin.

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
| `hurricane_observations.csv` | Canonical portable record accounting, normalized values and ROW_STATUS. |
| `source_inventory.json` | Source inventory and schema/provenance facts. |
| `hurricane_data_audit.md` | Human-readable counts and findings. |
| `prepare_manifest.json` | Machine-readable locations and preparation summary. |

Prepared features retain source attributes with analytical missing values normalized, plus `SOURCE_OID`, `USA_IFLAG`, `OBS_TIME_UTC`, and `QC_FLAGS`. The CSV retains original DBF text alongside normalized core columns. Consumers should read paths from the manifest rather than depend on the current working directory. SOURCE_OID is the zero-based original shapefile record index, a traceability key for this snapshot rather than a global observation identifier.

Keep these meanings distinct downstream: **zero** is an eligible modeled/observed value; **null** is an unavailable attribute; **NoData** is unsupported spatial/temporal coverage. A canonical record's existence does not authorize an engine to turn missing pressure, radius, or wind into a calm field. Any future imputation must be separately justified, flagged, tested, and included in the coverage report.

## Acceptance checks

- Source hashes and source geometry survive preparation unchanged; staged files share a safe basename.
- The selected feature class contains only the requested seasons/main tracks, valid USA-coordinate geometries and unique SID/time observations.
- Quarantined or conflicting records remain traceable, and all row-status counts reconcile to the source.
- P, I, V, missing agency/flag values, status distributions, wind/radius availability and coordinate differences appear in the audit.
- The canonical CSV and geodatabase agree for accepted observations after their documented null/date representations.
- No surface, probability, 1/3/5 class or hazard ranking is presented as a preparation output.
