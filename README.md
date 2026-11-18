# Puerto Rico hazards — SDSS course project

Two ArcPy workflows prepare **Hurricane Winds** observations and acquire **Drought** maps/reference statistics. The hurricane toolbox includes preparation and HURRECON wind-benchmark Script Tools; the drought toolbox includes three acquisition tools. The wind benchmark compares four size scenarios for Betsy, Hugo, Georges and Maria. Historical wind aggregation, weekly drought rasters and final 1/3/5 ranking follow evaluation of the benchmark results.

| Workflow | Toolbox / saved model | Maintained guides |
|---|---|---|
| Hurricane Winds | [HurricaneWinds_Model_Toolbox.atbx](HurricaneWinds_Model_Toolbox.atbx) / `HurricaneWinds_Fetch_IBTrACS` | [Setup](docs/hurricane_modelbuilder_setup.md), [processing design](docs/hurricane_processing_plan.md) |
| Drought | [DroughtRisk_Model_Toolbox.atbx](DroughtRisk_Model_Toolbox.atbx) / `Drought_Fetch_USDM` | [Setup](docs/drought_modelbuilder_setup.md), [processing design](docs/drought_processing_plan.md) |

Both saved models retain internal name `Model`. The aliases remain `prrisks` and `droughtprobe`. Open the toolbox in ArcGIS Pro Catalog and run its saved model, or edit it in ModelBuilder. See each setup guide for exact dialog values, public parameter order and durable output settings. Interface changes require refreshing saved graphs in the GUI.

## Where things belong

| Location | Purpose |
|---|---|
| `hurricane_winds.py`, `drought.py` | Callable workflows and command-line entrypoints |
| `scripts/` | Nine thin ArcGIS Script Tool adapters |
| `utils/hurricane/`, `utils/drought/`, `utils/shared/` | Actual processing and runtime validation |
| `Hazard_Variables/` | Original professor inputs; ignored by Git and preserved unchanged |
| `output/hurricane/data`, `output/hurricane/reports` | Prepared observations and wind-benchmark GDBs, source inventory/manifest, validation JSON |
| `output/drought/plan`, `data`, `reports`, `cache` | One plan, typed statistics/QC GDB and manifest, validation JSON, verified downloads |
| `output/shared/grid` | One 250 m reference raster, study mask, projected boundary, specification and Natural Earth cache |
| `output/arcgis/project`, `bridge` | Local ArcGIS project and MCP scratch/log runtime |
| `docs/`, `figures/`, `references/` | Five maintained guides, two PNG graphs and supplied course/source documents |
| `tools/` | Toolbox builder, definitions, PNG exporter and combined packager |
| `tests/test_contracts.py` | Thirteen offline checks of data rules and wind equations |
| `dist/PR_Risks_SDSS.zip` | One current portable code distribution; generated data excluded |

Generated data, caches and the ArcGIS project are ignored by Git. Keep your raw inputs and cache when updating code. Source checksums and original download receipts are preserved; mutable cache indexes support relocation. The installed MCP environment lives outside this repository; [bridge configuration](docs/arcgis_mcp_bridge_setup.md) explains its runtime paths.

## Normal execution

Use **ArcGIS Pro’s Python** for all hurricane stages and geodatabase publication. No new modeling dependencies are required. Run from the repository root:

```powershell
& 'C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe' hurricane_winds.py run --raw-points 'path/to/IBTrACS.points.shp'
& 'C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe' drought.py run --arcpy-tables --offline
```

Run the wind benchmark with ArcGIS Pro Python after preparation:

```powershell
& 'C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe' hurricane_winds.py wind-benchmark
```

This creates `output/hurricane/data/hurricane_winds.gdb` with 16 peak-wind rasters and size/convergence/reference comparison tables. The existing hurricane validation JSON receives a `wind_benchmark` section. The separate **HurricaneWinds_Estimate_Winds** canvas still needs assembly in ModelBuilder; the setup guide provides exact values and connections. Its three Script Tools can already run individually or through the command above. Review the benchmark before choosing a historical storm-size configuration.

Omit drought `--offline` to fetch missing data. Resume reuses only verified cache entries. Standard Python can run `python drought.py run --offline`, using CSV as its primary representation; ArcGIS mode writes typed tables and adds CSV only with `--export-csv`. Hurricane CSV is also opt-in. The saved drought model has no professor-sample/year input; the individual planner and CLI retain optional local-archive reuse.

Hurricane selection is main tracks, seasons **1955–2025**: this snapshot has **128,098 source points**, **62,485 prepared observations**, **1,143 storms**. Prepared winds/positions use the USA stream. The separate benchmark estimates local wind fields for the four named storms. Drought uses **2000–2025**: **1,357 baseline weeks**, **3 recovery buffers**, **654,160 normalized rows**, **231 retained source warnings**. Buffers do not enter the historical denominator. The final validation JSON in each reports folder is the handoff to future processing.

The shared provisional grid is EPSG:32161, 250 × 250 m anchored at (0,0), with Natural Earth 5.1.1 Puerto Rico/Vieques/Culebra/Mona coverage. It has 1,140 columns and 267 rows. Its 250 m computational cells do not establish that precision in the observations or generalized coastline.

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
