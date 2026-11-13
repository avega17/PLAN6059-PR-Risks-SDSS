# Hurricane audit prototype verification

The executable Python stages and their ArcGIS Script Tools have been exercised
against the supplied local IBTrACS snapshot using ArcGIS Pro 3.7 (Advanced),
Python 3.13.13. No additional wind-model packages were installed.

## Verified data products

| Check | Result |
|---|---:|
| Original point records | 128,098 |
| Prepared observations, MAIN seasons 1955–2025 | 62,485 |
| Distinct SID values | 1,143 |
| Retained observations missing USA_WIND | 85 |
| Retained observations with blank USA_AGENCY | 30,252 |
| Canonical CSV/QC record accounting | 128,098 |
| Prepared geometry mismatches against USA coordinates | 0 |
| Grid CRS | EPSG:32161 |
| Cell dimensions | 250 × 250 m |
| Grid columns × rows | 1,140 × 267 |
| Mask land cells | 144,085 |
| Required island controls | Mainland, Vieques, Culebra, Mona: pass |
| Source-sidecar checksums | Unchanged |

The source inventory and preparation audit provide the detailed distributions,
field map, missing-value policy and comparison of merged versus USA positions.
Differences between those position streams are not an independent accuracy test.

## Automated and portability checks

- The final ArcPy-enabled unittest run passed **30 tests** in 19.609 seconds.
  It covers normalization, duplicate conflicts, source preservation, quarantining
  missing USA coordinates, actual raster generation, inherited environments,
  alignment and NoData. Log: `output/provenance/arcpy_integration_tests_final.log`.
- Actual prepared datasets passed **26 validator checks**, including original
  source checksums and canonical CSV/feature-class reconciliation. Reports:
  `output/validation/validation_report.json` and its Markdown companion.
- The `.atbx` parameter contracts were verified using `ImportToolbox` and
  `GetParameterInfo`: 12 preparation, 7 grid, and 5 validation parameters.
- The actual validation Script Tool ran successfully from the toolbox.
- A complete copy of the code/toolbox was run from a fresh directory containing
  spaces, with a separate working directory. Its full 1955–2025 preparation,
  grid, and validation Script Tools passed, matching the source counts and grid.
  Imports resolved to the relocated code, and all 13 source-sidecar checksums
  remained unchanged. Evidence: `output/provenance/portability_report.json`.
- That relocation run preceded a subsequent input-geometry guard and additional
  audit distributions; the final 30-test run includes those changes.

## Interpretation and remaining verification

These checks verify data handling and geoprocessing integration. They do not
validate modeled local winds: spatial estimation, event-exceedance frequency,
1/3/5 ranking, and independent wind validation are deferred. Natural Earth's
generalized land boundary remains provisional, and 250 m is a computational
grid size rather than the accuracy of historical winds or track positions.

## Saved ModelBuilder model

The GUI-authored **HurricaneAuditPrototype** model is saved in `PRRisks.atbx`
(internal name `Model`, alias `prrisks`). It contains the three Script Tools,
with Prepare Manifest and Grid Spec connected to Validate Prototype. Seven
inputs and all 13 derived stage outputs are exposed as model parameters.

The saved model was executed through ArcPy from clean `output/model_run/`
folders. All three stages succeeded in approximately 61 seconds, reproduced
62,485 observations/1,143 storms and the 1,140 × 267 grid, and passed all
26 validator checks. Every published file/dataset remained present after the
model returned. Evidence: `output/provenance/model_execution_report.json`
and `model_execution.log`; generated data: `output/model_run/`.

The first saved-model preflight revealed missing derived-path declarations.
The Script Tool validators now declare deterministic output paths using only
folder/path operations. The successful model execution includes this fix;
validation does not read future datasets or run geoprocessing before execution.

The diagram in `docs/hurricane_modelbuilder_graph.svg` (PNG alongside) renders
the saved ModelBuilder XML. Its node positions and connections are retained;
connectors are rerouted for readability. The exporter does not modify the model.

The complete saved model was then run again from a copied distribution whose
path contains spaces, using fresh output folders. It passed all 26 checks in
approximately 63 seconds, retained all 13 outputs, and loaded `hurricane_winds`
and all three `utils` modules from the relocated distribution. Evidence:
`output/provenance/relocated_model_execution_report.json` and its execution log.

## Distribution artifacts

`dist/PRRisks_HurricanePrototype.zip` contains the toolbox, code, tests and
documentation, with a per-file SHA-256 release manifest. The separate
`dist/PRRisks_HurricanePreparedData.zip` contains the verified saved-model run,
including prepared geodatabase/CSV, grid, audit/provenance and validation.
Its data manifest records file hashes. Execution paths in provenance are
preserved; regenerate outputs with local paths after moving to a new workspace.
