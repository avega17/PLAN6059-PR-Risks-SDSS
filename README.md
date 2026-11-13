# Puerto Rico SDSS: Hurricane Winds and Drought prototypes

ArcPy preparation, audit and integration prototypes for the PLAN 6059 Spatial Decision Support System final project: **Hurricane Winds** using local IBTrACS observations and a **250 m EPSG:32161 reference grid**, plus **Drought** acquisition from the public U.S. Drought Monitor.

The Hurricane prototype preserves sources, prepares USA-coordinate observations for MAIN tracks in seasons **1955-2025**, establishes the shared grid, and validates the products. Drought acquisition preserves and validates **2000-2025** weekly data. Wind reconstruction, drought temporal hazard metrics, **1/3/5 hazard ranking**, and forecast models remain later stages.

## Drought acquisition and research

The [Drought toolbox](Drought.atbx) contains **Plan Drought Download**, **Fetch Drought Data**, and **Validate Drought Download** Script Tools. The [Drought ModelBuilder guide](docs/drought_modelbuilder_setup.md) gives exact parameters and manual model wiring. A saved Drought graph is not supplied; the three tools and equivalent CLI workflow are executable and tested. The [processing-readiness report](docs/drought_processing_readiness.md) records the full 1,357-map acquisition, source warnings, live ArcPy tests, and six diagnostic raster pilots.

The [download design](docs/drought_download_implementation_plan.md), [methods/literature review](docs/drought_hazard_methods_review.md), [initial source inspection](docs/drought_sample_and_api_findings.md), and [evidence manifest](docs/drought_research_evidence.json) preserve the research rationale. Drought spatial metrics and ranked rasters remain later work. The November 6 Hurricane release archives remain unchanged.

```powershell
python drought.py run --output-folder "output/drought_baseline" --local-archive-folder "Hazard_Variables/Drought/2026_USDM_M" --arcpy-tables
```

Use ArcGIS Pro Python for `--arcpy-tables` and Script Tools. Standard Python can publish CSV tables. Full data and receipts are under [output/drought_baseline/](output/drought_baseline/); retain its persistent cache for resume. The portable code/tool distribution is [PRRisks_DroughtAcquisition.zip](dist/PRRisks_DroughtAcquisition.zip). The optionally installed local ArcPy MCP bridge is documented in [bridge setup](docs/arcgis_mcp_bridge_setup.md).

## Run with ArcGIS Pro Python

Use the **Python Command Prompt provided by ArcGIS Pro**, or the Pro environment's Python executable. A normal Python installation does not provide ArcPy. Run from the repository root; keep inputs and generated outputs in separate folders.

The current grid stage requires **ArcGIS Pro Advanced** for Polygon To Raster. It uses no Spatial Analyst extension or new modeling dependencies. Execution was verified with Pro 3.7; classmates should confirm their license and version before running.

```powershell
python hurricane_winds.py run `
  --raw-points "Hazard_Variables/Hurricanes/IBTrACS.NA.list.v04r01.points/IBTrACS.NA.list.v04r01.points.shp" `
  --raw-lines "Hazard_Variables/Hurricanes/IBTrACS.NA.list.v04r01.lines/IBTrACS.NA.list.v04r01.lines.shp" `
  --spc-reports "Hazard_Variables/Hurricanes/1955-2025-wind-aspath/1955-2025-wind-aspath.shp" `
  --output-folder "output/hurricane_prototype"
```

The optional lines and SPC reports are contextual inventory inputs. The primary analytical input is the points dataset. All matching shapefile sidecars must remain beside each `.shp`.

To use an existing approved polygon boundary, add `--boundary "path/to/boundary"`. Without it, grid establishment downloads the pinned Natural Earth 5.1.1 country boundary; an initial download requires internet access. This provisional **1:10 million map-scale** boundary includes the island checks above. The source, archive checksum, transformation and limitations are recorded in the grid manifest. Replace it with the class-approved boundary when available.

Individual stages are also available:

```powershell
python hurricane_winds.py prepare --raw-points "path/to/points.shp" --output-folder "output/prepare"
python hurricane_winds.py grid --output-folder "output/grid"
python hurricane_winds.py validate --prepare-manifest "output/prepare/prepare_manifest.json" --grid-spec "output/grid/grid_spec.json" --output-folder "output/validation"
```

Preparation accepts `--start-season` and `--end-season`, defaulting to 1955 and 2025. Use `python hurricane_winds.py --help` and the subcommand's `--help` for the full interface.

## Outputs and ArcGIS integration

The combined run creates `prepare/`, `grid/` and `validation/` beneath the selected output folder. Start review with `prepare/hurricane_data_audit.md`, `prepare/prepare_manifest.json`, `grid/grid_spec.json`, `grid/grid_manifest.json`, and `validation/validation_report.md` (with detailed JSON alongside). Prepared feature classes/tables are in `prepare/hurricane_prepare.gdb`; the CSV preserves row accounting for excluded/quarantined observations as well as accepted ones. Filter its `ROW_STATUS` to INCLUDED before future estimation.

The supplied **[PRRisks.atbx](PRRisks.atbx)** contains the executable **HurricaneAuditPrototype** ModelBuilder model and three Script Tools linked to thin adapters in `scripts/`. Add the toolbox in Catalog, open the model, select your raw source files and three existing output folders, and run. Leave Boundary blank for Natural Earth. Choose **Edit** to inspect the three-stage graph. The model fixes seasons at 1955–2025 and returns its prepared data, grid products, report and pass flag as typed outputs.

The [ModelBuilder guide and exact parameter tables](docs/modelbuilder_setup.md) cover running, editing and recreating the tools. See the [saved model diagram](docs/hurricane_modelbuilder_graph.svg). Share the entire folder tree so relative script/module paths survive relocation. The [toolbox builder](tools/build_toolbox.py) reproduces the Script Tool definitions with standard Python while preserving the GUI-authored model; `--verify` checks the tools with ArcPy. Third-party format attribution is in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Read the [IBTrACS data contract](docs/ibtracs_data_contract.md) before using prepared fields, especially IFLAG, agency, missing values, and status codes. The [wind estimation options and validation gate](docs/hurricane_wind_estimation_options.md) compares HURRECON, CLIMADA, Tropycal, recorded radii and experimental `tcwind`; none is installed or executed by this prototype. CLIMADA's documented Python versions require a separate research environment from the local Pro Python 3.13 environment.

## Validation

Run the repository's unit checks in the Pro environment:

```powershell
python -m unittest discover -s tests -v
```

The prototype validator checks preparation/grid consistency. The [verification report](docs/verification.md) records the 30 passing automated tests, 26 passing dataset checks, Script Tool relocation run, and successful execution of the GUI-authored model. Scientific wind-model validation remains a later task. A 250 m grid describes output alignment and does not establish 250 m accuracy in the historical track/intensity data.

## Share the prototype

Use `dist/PRRisks_HurricanePrototype.zip` for the portable toolbox, code, tests and documentation. The saved model also passed a complete run from a relocated folder containing spaces. `dist/PRRisks_HurricanePreparedData.zip` is a separate snapshot of the verified `output/model_run/` data and reports; its provenance retains the execution paths. Re-run the model with your local inputs/output folders for new work.

To rebuild the archives after verification, run `python tools/package_release.py` and `python tools/package_release.py --data-only`. The code packager requires a saved ModelBuilder graph and verifies archived file hashes. No raw datasets are needed merely to inspect the toolbox or documentation.
