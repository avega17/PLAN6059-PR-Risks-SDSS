# Drought ModelBuilder setup

Open `DroughtRisk_Model_Toolbox.atbx`; alias `droughtprobe`. Retain the saved model's internal name **Model** and label **Drought_Fetch_USDM**. Its three stages are Plan Drought Download → Fetch Drought Data → Validate Drought Download.

## Exact dialog values

| Plan Drought Download | Value |
|---|---|
| Start Date | 1/1/2000 |
| End Date | 12/31/2025 |
| Plan Folder | `C:/Users/ALEJANDROSVEGANOGALE/Documents/Repos/PLAN6059-PR-Risks-SDSS/output/drought/plan` |
| Local Archive Folder | **Blank**, optional individual-tool capability only |
| Include Municipio Statistics | True |
| Recovery Buffer Weeks | 3 |
| Mode | Baseline |

| Fetch Drought Data | Value |
|---|---|
| Download Plan | Connect Plan Drought Download → Download Plan |
| Cache Folder | `C:/Users/ALEJANDROSVEGANOGALE/Documents/Repos/PLAN6059-PR-Risks-SDSS/output/drought/cache` |
| Acquisition Folder | `C:/Users/ALEJANDROSVEGANOGALE/Documents/Repos/PLAN6059-PR-Risks-SDSS/output/drought/data` |
| Resume | True |
| Export CSV | False |

| Validate Drought Download | Value |
|---|---|
| Download Manifest | Connect Fetch Drought Data → Download Manifest |
| Validation Folder | `C:/Users/ALEJANDROSVEGANOGALE/Documents/Repos/PLAN6059-PR-Risks-SDSS/output/drought/reports` |

## Lean saved graph

Keep exactly three process boxes. When replacing the old graph, remove old process/variable nodes from the canvas and add the refreshed Script Tools, keeping the existing model item. Make only these public inputs, in order: **Start Date, End Date, Plan Folder, Cache Folder, Acquisition Folder, Validation Folder**. Make the final output **Validated Drought Data** public. No local-archive node, year-specific input, unused `acquire`, duplicate `(2)` labels, Boolean, statistics or QC outputs should remain.

Download Plan and Download Manifest remain internal connectors. All Script Tool outputs are declared **Derived**; ArcGIS Pro exempts derived outputs from intermediate-data deletion and does not offer the Intermediate toggle for them. Retain that type and confirm the files survive a saved-model run. Give folder variables the labels above and control public order under Model Properties → Parameters. Run Validate, Auto Layout, Save. The final validation JSON references the acquisition manifest; future preparation consumes that handoff and discovers tables/raw archives through the manifest.

The plan contains its calendar in JSON. Fetch publishes `drought_acquisition.gdb/statistics` and `acquisition_qc`, plus `download_manifest.json`. Tables are not separate ModelBuilder outputs. CSV export is optional/off by default with ArcGIS; ordinary Python uses CSV as its primary table format. Validation reproduces table values from frozen JSON responses and preserves reference warnings rather than renormalizing them.

## Normal execution

Run the saved model from the Geoprocessing pane. The baseline is **1,357 weeks + 3 end buffers**, **654,160 normalized rows**, and **231 retained reference warnings** for the frozen snapshot. Buffers are separate from the 26-year baseline. A warm-cache run verifies bytes and avoids network requests. The first run without the professor sample fetched the three buffer archives once; historical archives were reused. Keep `output/drought/cache` for subsequent runs.

From ArcGIS Python: `python drought.py run --arcpy-tables --offline`. Remove `--offline` to allow missing downloads. Ordinary Python: `python drought.py run --offline` (primary CSV, no GDB). Optional `--local-archive-folder` is available to individual planning/CLI use, not a public saved-model input. Do not include 2026 in a historical indicator denominator.

The three acquisition stages do not calculate drought hazard. [Processing design](drought_processing_plan.md) explains assessed-domain checks, weekly rasters, frequency/duration and later ranking. Acquisition passing does not certify raster readiness.

Rebuild Script Tools with `python tools/build_toolbox.py --overwrite --verify` in ArcGIS Python with Pro closed. Use the GUI for ordinary graph/interface changes; rebuilding definitions alone does not reconnect a saved graph. Explicitly authorized programmatic repairs must synchronize logical/diagram contracts and pass actual saved-model execution. Render the final graph with `python tools/export_model_diagram.py --toolbox DroughtRisk_Model_Toolbox.atbx --output figures/drought_modelbuilder_graph --title "Drought · saved ModelBuilder graph" --subtitle "Drought_Fetch_USDM · 2000–2025 baseline + recovery buffers" --footer "Acquisition only · weekly states, duration and ranking remain future work"`. See [diagram](../figures/drought_modelbuilder_graph.png).
