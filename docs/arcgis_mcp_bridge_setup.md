# Installed ArcGIS MCP bridge

Installed and tested **2026-11-12**: **arcgis-mcp-bridge 0.6.8** from PyPI.
The [upstream repository](https://github.com/muend/arcgis-mcp-bridge) and
[author's technical article](https://dev.to/muend/building-a-secure-mcp-bridge-for-arcgis-pro-and-arcpy-511g)
were reviewed before installation. This is an independent Apache-2.0 project.

## Local configuration

- Codex server name: **arcgis**; enabled in the user's `~/.codex/config.toml`.
- Transport: **stdio**; no HTTP listener or API credential was configured.
- Server and ArcPy worker use the same dedicated cloned interpreter:
  `C:/Users/ALEJANDROSVEGANOGALE/AppData/Local/ESRI/conda/envs/arcgis-mcp-env/python.exe`.
- Clone source: ArcGIS Pro's `arcgispro-py3`, Python **3.13.13**, Pro **3.7**.
- Allowed filesystem root: this project repository only.
- Scratch geodatabase: `output/arcgis_bridge/scratch.gdb`.
- Worker concurrency: **1**; worker timeout **600 s**, Codex tool timeout **660 s**,
  startup timeout **120 s**.
- Logging: `output/arcgis_bridge/bridge.log`.
- `PYTHONNOUSERSITE=1` and an empty bridge-specific `PYTHONPATH` keep imports in
  the configured environment. Optional vision dependencies were not requested.

Existing Codex configuration was preserved and backed up beside the original
configuration file before the new server block was appended. The registration
was verified using `codex mcp get arcgis --json`. The saved block and installation
receipt are in [the setup evidence folder](../output/arcgis_bridge_setup/).

The configuration follows the [official OpenAI MCP documentation](https://developers.openai.com/codex/mcp/).
Start a **new Codex session**, or restart/reconnect the client, if the current
session's tool list does not yet include `arcgis`. Registration alone does not
prove that a running session has refreshed its tool catalog.

## Tests performed

An actual MCP client initialized the stdio server and discovered **103 tools**:
100 catalog tools plus three core endpoints. Calls were tested through the MCP
transport, not solely through direct Python imports:

1. `health_check` returned the configured worker interpreter.
2. `describe_dataset` read the project's existing projected PR boundary and
   reported **EPSG:32161** and polygon geometry.
3. `get_feature_count` returned **1** for that multipart boundary.
4. `create_feature_class` created an empty **POINT** feature class in the dedicated
   scratch geodatabase with **EPSG:32161**.
5. `get_feature_count` returned **0** for that new test class.
6. An attempted description of `C:/Windows/win.ini` was rejected because it lies
   outside the allowed repository root.

These establish installation, IPC, real ArcPy execution and the tested path
boundary. They are not a validation of every geoprocessing tool in the catalog.

## Environment integrity and limitations

The original ArcGIS environment's `conda-meta` files were hashed before and
after provisioning and remained unchanged. Installation changed only the
dedicated clone. A missing PyArrow dependency in the clone was installed there.

The cloned environment's broad `pip check` still reports the **lifelines 0.30.1 /
pandas 3.0.0** constraint mismatch already present in the source Esri environment.
That unrelated package pair was not changed. ArcPy and the MCP smoke operations
above passed. Do not describe the entire Esri package environment as having a
clean dependency audit solely because these bridge calls pass.

The bridge exposes declared geoprocessing operations. It does **not** provide a
general ArcGIS Pro GUI controller or a supported ModelBuilder-authoring API.
The Drought acquisition scripts remain the reproducible project implementation;
the bridge can assist with dataset inspection and supported later geoprocessing.
