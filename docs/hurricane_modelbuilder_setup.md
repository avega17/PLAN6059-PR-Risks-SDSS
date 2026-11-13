# Hurricane Winds ModelBuilder setup

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
