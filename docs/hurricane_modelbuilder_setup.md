# Hurricane Winds ModelBuilder setup

## Wind-field benchmark model

The toolbox now also contains **Prepare Wind Inputs**, **Estimate Wind Fields** and **Evaluate Wind Estimates**. Create a second saved model with internal **Name = EstimateWinds** and **Label = HurricaneWinds_Estimate_Winds**. Keep the existing `Model` / `HurricaneWinds_Fetch_IBTrACS` item. The new model benchmarks Betsy, Hugo, Georges and Maria before selection of the historical size configuration.

Drag the three new Script Tools onto the new canvas. Configure their dialogs as follows. The three optional inputs may stay blank to use the documented defaults.

| Prepare Wind Inputs parameter | Exact value |
|---|---|
| Validated Hurricane Data | `C:\Users\ALEJANDROSVEGANOGALE\Documents\Repos\PLAN6059-PR-Risks-SDSS\output\hurricane\reports\validation_report.json` |
| Grid Specification | `C:\Users\ALEJANDROSVEGANOGALE\Documents\Repos\PLAN6059-PR-Risks-SDSS\output\shared\grid\grid_spec.json` |
| Wind Output Folder | `C:\Users\ALEJANDROSVEGANOGALE\Documents\Repos\PLAN6059-PR-Risks-SDSS\output\hurricane\data` |
| Benchmark Storms | `1956222N13313;1989254N13340;1998259N10335;2017260N12310` |

| Estimate Wind Fields parameter | Value |
|---|---|
| Wind Workspace | Connect the **Wind Workspace model variable** produced by Prepare Wind Inputs |
| Size Scenarios | Blank for the four published pairs, or an input table containing numeric `RMW_KM` and `PROFILE_B` columns |

| Evaluate Wind Estimates parameter | Value |
|---|---|
| Wind Field Catalog | Connect the **Wind Field Catalog model variable** produced by Estimate Wind Fields |
| Reference Wind Observations | Blank unless a qualifying station-observation table is supplied |

Use output-to-input connections for both arrows. Selecting a table/geodatabase directly from disk in place of those model variables would omit the process dependency. Keep all outputs Derived. The workflow writes internal tables and rasters inside the returned workspace; the catalog gives the storm/scenario associations.

Expose inputs in this order: Validated Hurricane Data, Grid Specification, Wind Output Folder, Benchmark Storms (optional), Size Scenarios (optional), Reference Wind Observations (optional). Use Make Variable > From Parameter for the optional inputs if needed. Expose final outputs Wind Field Catalog, Wind Benchmark Summary and Validated Wind Benchmark. Keep the workspace connector internal. Use Model Properties > Parameters to set their order, Auto Layout for native diagram geometry, and the upper Save icon to save the model.

The default scenario table has rows `(20,1.5)`, `(40,1.4)`, `(60,1.3)` and `(80,1.2)`. It is created inside the wind geodatabase. For a custom input, use a separate table so preparation does not replace the supplied scenario values.

The optional station input requires `SID`, `STATION`, `LAT`, `LON`, `WIND_MPS`, `AVG_SECONDS`, `HEIGHT_M`, `COVER`, `START_UTC`, `END_UTC`, `SOURCE`, `LOWER_BOUND`. Use 60-second sustained winds, height 10 m within 0.5 m, COVER `LAND` or `WATER`, complete UTC observation windows, an explicit source, and LOWER_BOUND=0. Invalid/mismatched rows fail with a corrective message. Gusts and incomplete instrument records require a separate evaluation method.

Results use `output/hurricane/data/hurricane_winds.gdb`: 16 default five-minute peak rasters, event catalog, size table, native tracks, geographic cell centers, convergence, timing, reference comparisons and footprint summary tables. Fifteen- and 2.5-minute calculations are compared in memory. The existing `output/hurricane/reports/validation_report.json` receives a `wind_benchmark` section. Read its status, convergence and reference-availability fields when using benchmark results.

Run the three stages from ArcGIS Pro Python through the same root entrypoint:

```powershell
& 'C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe' hurricane_winds.py wind-benchmark
```

For individual stages use `wind-prepare`, `wind-estimate` and `wind-evaluate`. Run `--help` for optional parameters. A successful computational benchmark provides size/convergence evidence for review. Select the historical configuration together before extending to 1955-2025 indicators and 1/3/5 ranking.

After saving the graph, run it from the Geoprocessing pane and check that the catalog, rasters, tables and report survive completion. Test a relocated distribution with local source/output paths. Close ModelBuilder tabs and save the project on its map before updating toolbox files.

After both hurricane models are saved, refresh the existing hurricane PNG with both native graphs:

```powershell
& 'C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe' tools/export_model_diagram.py --all-models --subtitle 'Preparation and wind benchmark' --footer 'Historical aggregation and hazard ranking await benchmark review'
```

This reads saved diagrams and stacks them into the one hurricane PNG. It does not create or connect ModelBuilder graphs.

## Existing preparation model

Open `HurricaneWinds_Model_Toolbox.atbx`; its alias is `prrisks`. The saved model's internal name remains `Model`, with label **HurricaneWinds_Fetch_IBTrACS**. The three Script Tools use the root `hurricane_winds.py` functions and `utils/hurricane` plus the shared grid implementation.

## Stage parameters

Use existing writable folders. Relative paths below are relative to the repository root; in floating dialogs use the full paths shown. Keep inputs as File parameters for shapefiles with sidecars.

| Prepare Hurricane Data parameter | Value |
|---|---|
| Raw Points | Local IBTrACS points `.shp` under `Hazard_Variables/Hurricanes` |
| Preparation Folder | `C:/Users/ALEJANDROSVEGANOGALE/Documents/Repos/PLAN6059-PR-Risks-SDSS/output/hurricane/data` |
| Start Season / End Season | 1955 / 2025 |
| Raw Lines / SPC Reports | Optional source `.shp` files, blank allowed |
| Export CSV | False |

| Establish Reference Grid parameter | Value |
|---|---|
| Grid Folder | `C:/Users/ALEJANDROSVEGANOGALE/Documents/Repos/PLAN6059-PR-Risks-SDSS/output/shared/grid` |
| Boundary | Blank for pinned provisional Natural Earth; optional replacement polygon |

| Validate Prototype parameter | Value |
|---|---|
| Prepare Manifest | Connect Prepare Hurricane Data → Prepare Manifest |
| Grid Specification | Connect Establish Reference Grid → Grid Specification |
| Validation Folder | `C:/Users/ALEJANDROSVEGANOGALE/Documents/Repos/PLAN6059-PR-Risks-SDSS/output/hurricane/reports` |

## Lean saved model

Keep exactly three process boxes. If replacing a pre-cleanup graph, remove its old processes/variables on the canvas and drag in the refreshed three Script Tools. Keep the existing model item/internal name; do not create another model or change aliases. Connect the two JSON outputs to validation as above. Use **Make Variable → From Parameter** for optional inputs that must be public but are not shown automatically.

Expose inputs in this order: Raw Points, Preparation Folder, Raw Lines (optional), SPC Reports (optional), Grid Folder, Validation Folder, Boundary (optional). Expose outputs afterward: Prepared Observations, Reference Raster, Study Mask, Grid Specification, Validated Hurricane Data. Rename variables to these labels. Output parameter values are derived; do not type another destination for them. Do not expose Projected Boundary or Prepare Manifest as public model parameters.

The Script Tool outputs are declared **Derived**. ArcGIS Pro exempts derived outputs from intermediate-data deletion and does not offer the Intermediate toggle for them. Retain that type, keep internal connectors unexposed, and confirm the preparation manifest and projected boundary survive execution from the Geoprocessing pane. Use Validate, Auto Layout and Save; Model Properties → Parameters controls public order. The final validation JSON points to the preparation manifest and grid specification and is the later-processing handoff.

The GDB stores raw points, prepared observations, storms and record QC. The inventory/manifest expose their paths without extra canvas outputs. No duplicate CSV or Markdown audit is written by default. Individual Prepare tools/CLI can request CSV explicitly. Temporary safe-name staging is removed automatically.

## Execution and maintenance

Run the saved model from the Geoprocessing pane after choosing input paths. Source files remain unchanged; inherited extent/mask must not clip selected tracks. Expected snapshot: 128,098 source points, 62,485 prepared points, 1,143 storms. The grid uses EPSG:32161, 250 m, anchor (0,0), 1,140 columns × 267 rows for the provisional default boundary. Grid checks include all four islands and exterior NoData.

`python hurricane_winds.py run --raw-points "path/to/points.shp"` uses the same three stages (ArcGIS Python required). Defaults are `output/hurricane/{data,reports}` and `output/shared/grid`. See [processing design](hurricane_processing_plan.md).

Rebuild Script Tools with `python tools/build_toolbox.py --overwrite --verify` using ArcGIS Python while Pro is closed. This preserves saved model archives but **does not update their graphs** after an interface change; use ModelBuilder for ordinary graph editing. The cleanup repair was explicitly authorized programmatically after repeated desktop-tool aborts, then verified by importing/executing the saved model. Render the final saved graph with `python tools/export_model_diagram.py`. The maintained figure is [here](../figures/hurricane_modelbuilder_graph.png).
