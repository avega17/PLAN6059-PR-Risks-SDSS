# ArcGIS MCP bridge

The installed independent [arcgis-mcp-bridge](https://github.com/muend/arcgis-mcp-bridge) is version 0.6.8 (Apache-2.0), using stdio. It is a supported-operation bridge, not a ModelBuilder GUI authoring API. See the [author’s explanation](https://dev.to/muend/building-a-secure-mcp-bridge-for-arcgis-pro-and-arcpy-511g).

The user configuration is `~/.codex/config.toml`, server `arcgis`. The server and ArcPy worker use the existing dedicated interpreter:
`C:/Users/ALEJANDROSVEGANOGALE/AppData/Local/ESRI/conda/envs/arcgis-mcp-env/python.exe`.

The allowed root remains this repository only. Runtime paths are `output/arcgis/bridge/scratch.gdb` and `output/arcgis/bridge/bridge.log`. Worker concurrency is 1, worker timeout 600 seconds. `PYTHONNOUSERSITE=1` and empty `PYTHONPATH` isolate imports. Do not reinstall the bridge or alter the original ArcGIS environment to move its scratch/log folder.

Restart/reconnect the Codex MCP client after changing these paths. Check `health_check`, then describe `output/shared/grid/grid.gdb/study_boundary32161` and confirm EPSG:32161. The bridge’s installed package is outside this repository; no source clone or setup receipts are needed here.

The cloned environment inherited an unrelated lifelines/pandas dependency mismatch. Successful ArcPy operations do not certify every installed package. Keep scientific wind-model dependencies in separate future environments.
