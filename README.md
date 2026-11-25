# Puerto Rico hazards — SDSS course project

ArcPy workflows prepare **Hurricane Winds** observations, reconstruct historical wind exposure, and calculate **Drought** occupancy and event duration. The classification tools write a continuous score and a Low/Medium/High raster coded 1/3/5 for each hazard.

| Workflow | Toolbox / saved model | Documentation |
|---|---|---|
| Hurricane Winds | [HurricaneWinds_Model_Toolbox.atbx](HurricaneWinds_Model_Toolbox.atbx) / `HurricaneWinds_Fetch_IBTrACS`, `HurricaneWinds_Estimate_Winds` | [Setup](docs/hurricane_modelbuilder_setup.md), [processing design](docs/hurricane_processing_plan.md), [classification report](docs/hurricane_classification_report.md) |
| Drought | [DroughtRisk_Model_Toolbox.atbx](DroughtRisk_Model_Toolbox.atbx) / `Drought_Fetch_USDM`, `Drought_Process_USDM` | [Setup](docs/drought_modelbuilder_setup.md), [processing design](docs/drought_processing_plan.md), [classification report](docs/drought_classification_report.md) |

The acquisition models retain internal name `Model`; wind processing uses `EstimateWinds` and drought processing uses `ProcessDrought`. The aliases remain `prrisks` and `droughtprobe`. Open the toolbox in ArcGIS Pro Catalog and run its saved model, or edit it in ModelBuilder. See each setup guide for exact dialog values, public parameter order and durable output settings. Interface changes require refreshing saved graphs in the GUI.

## Where things belong

| Location | Purpose |
|---|---|
| `hurricane_winds.py`, `drought.py` | Callable workflows and command-line entrypoints |
| `scripts/` | Linked ArcGIS Script Tool adapters |
| `utils/hurricane/`, `utils/drought/`, `utils/shared/` | Actual processing and runtime validation |
| `Hazard_Variables/` | Original professor inputs; ignored by Git and preserved unchanged |
| `output/hurricane/data`, `output/hurricane/reports` | Prepared observations, historical wind indicators and variants, final GeoTIFFs, and validation JSON |
| `output/drought/plan`, `data`, `reports`, `cache` | Acquisition/processing GDBs, one weekly cube, manifests, one validation JSON and verified downloads |
| `output/shared/grid` | One 250 m reference raster, study mask, projected boundary, specification and Natural Earth cache |
| `output/arcgis/project`, `bridge` | Local ArcGIS project and MCP scratch/log runtime |
| `docs/`, `figures/`, `references/` | Five maintained guides, two requested classification reports, two PNG graphs and supplied course/source documents |
| `tools/` | Toolbox builder, definitions, PNG exporter and combined packager |
| `tests/test_contracts.py` | Offline checks of data rules, wind equations, drought transitions and course class boundaries |
| `dist/PR_Risks_SDSS.zip` | One current portable code distribution; generated data excluded |

Generated data, caches and the ArcGIS project are ignored by Git. Keep your raw inputs and cache when updating code. Source checksums and original download receipts are preserved; mutable cache indexes support relocation. The installed MCP environment lives outside this repository; [bridge configuration](docs/arcgis_mcp_bridge_setup.md) explains its runtime paths.

## Normal execution

Use **ArcGIS Pro’s Python** for all hurricane stages and geodatabase publication. No new modeling dependencies are required. Run from the repository root:

```powershell
& 'C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe' hurricane_winds.py run --raw-points 'path/to/IBTrACS.points.shp'
& 'C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe' drought.py run --arcpy-tables --offline
```

After acquisition and preparation, use ArcGIS Pro Python to process the full records and make the course maps:

```powershell
python hurricane_winds.py wind-history
python hurricane_winds.py classify
python drought.py process
python drought.py classify
python hurricane_winds.py combine
python hurricane_winds.py layouts
```

The wind geodatabase holds reference-year variants and supporting indicators. Drought compares D1+ and D2+ using both recovery rules. The two classification tools use Spatial Analyst to write the final GeoTIFFs. They fit three Natural Breaks (Jenks) classes to each layer independently and preserve the underlying score for comparisons across periods or severity thresholds. The Python sum applies the same arithmetic as the course's **Raster Calculator** branch. Close the project before saving the three layouts with the last command.

Omit drought `--offline` to fetch missing data. Resume reuses only verified cache entries. Standard Python can run `python drought.py run --offline`, using CSV as its primary representation; ArcGIS mode writes typed tables and adds CSV only with `--export-csv`. Hurricane CSV is also opt-in. The saved drought model has no professor-sample/year input; the individual planner and CLI retain optional local-archive reuse.

After drought acquisition, run `python drought.py process` with ArcGIS Pro Python. It prepares the 1,360-map spatial cache and continuous hazard indicators without downloading again. The population-focused course index covers mainland PR, Vieques and Culebra; Mona is outside its scope, with sparse observations retained only for the shared-grid data audit. The processing guide explains both event rules and final classification gates. The second drought model uses Name=`ProcessDrought`, Label=`Drought_Process_USDM`; the setup guide provides its three stages, exact paths and public parameters.

Hurricane selection is main tracks from **1955–2025**. The snapshot has **128,098 source points**, **62,485 prepared observations** and **1,143 storms**. Prepared winds and positions use the USA stream. Drought uses **2000–2025** with **1,357 baseline weeks**, **3 recovery buffers**, **654,160 normalized rows** and **231 retained source warnings**. The validation JSON in each reports folder records the processing and classification results.

The shared provisional grid is EPSG:32161, 250 × 250 m anchored at (0,0), with Natural Earth 5.1.1 Puerto Rico/Vieques/Culebra/Mona coverage. It has 1,140 columns and 267 rows. Its 250 m computational cells do not establish that precision in the observations or generalized coastline.

The classification reports document the exact thresholds, alternative rules, class areas, source comparisons and limitations. If the supplied December 2025 FEMA geodatabase is present under `Hazard_Variables/`, the classification tools write tract-level comparisons to their geodatabases.

## Maintenance

Close ModelBuilder tabs, save the project on its map, then close ArcGIS Pro before rebuilding definitions. This prevents the project from restoring a model while its toolbox is being updated. Use ArcGIS Python for toolbox verification and diagram export:

```text
python tools/build_toolbox.py --overwrite --verify
python tools/export_model_diagram.py
python tools/package_release.py
python -m unittest discover -s tests -p test_contracts.py
```

The builder preserves GUI-authored model archive members; it cannot reconnect a graph after a parameter-contract change. The drought setup guide gives its PNG export command. Package only after both saved graphs and figures match the current contracts. Keep toolboxes beside the scripts/root entrypoints when relocating the distribution; change model input/output values to local folders.

[Hurricane diagram](figures/hurricane_modelbuilder_graph.png) · [Drought diagram](figures/drought_modelbuilder_graph.png) · [Course guidelines](references/SDSS%20Final%20Project%20Fall%202026.pdf) · [Third-party notices](THIRD_PARTY_NOTICES.md)

Development follows [AGENTS.md](AGENTS.md): reuse existing guides/destinations, clean temporary experiments, keep one canonical result and avoid unsolicited evidence files or expanded harnesses. The recovery checkpoint is Git tag `pre-cleanup-2026-11-12` on `main`; the repository simplification has been merged into `main`.

The setup guides include Mermaid overviews and expandable processing algorithms, distinguishing ArcGIS tools from APIs and custom logic. See the [Boose method note](references/boose_2004_method_notes.md) for the damage-scale and recurrence evidence supporting the wind indicators.
