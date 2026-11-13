# Drought acquisition ModelBuilder verification

Verified locally on November 12, 2026 in ArcGIS Pro 3.7.

## Saved model and execution

The [Drought toolbox](../DroughtRisk_Model_Toolbox.atbx) contains a saved ModelBuilder model with three Script Tools: Plan Drought Download â†’ Fetch Drought Data â†’ Validate Drought Download. The display label is **Drought_Fetch_USDM**, internal name is `Model`, and alias is `droughtprobe`. The final label was confirmed in ArcGIS Pro and the saved toolbox; stage settings and the parameter contract remain identical to the executed model. GUI assembly established the graph, and the user supplied the floating-dialog values. The saved model itself was imported and executed through ArcPy; this was not a substitute run of the core CLI pipeline.

The full **2000â€“2025** model run succeeded in **81.37 seconds**, publishing all eight declared outputs. It used the verified historical cache with Resume=True and made **zero network requests**. It planned and verified **1,357 baseline weeks plus 3 recovery-buffer weeks**, with **654,160 normalized statistics rows**. **Passed=True**. The **231 reference-statistics warnings** remain recorded, without correcting or renormalizing source data.

See the machine-readable [verification summary](drought_modelbuilder_verification.json), [execution receipt](../output/drought_modelbuilder_setup/saved_model_execution.json), [geoprocessing messages](../output/drought_modelbuilder_setup/saved_model_messages.log), and [download validation report](../output/drought_model_baseline/validate/download_validation.json).

The saved interface exposes seven inputs (the two dates and five folders) and eight derived outputs. Baseline/Pilot mode, municipio statistics, recovery buffer and resume remain configured inside their Script Tools; this model uses Baseline, True, 3 and True. See [setup and exact parameter order](drought_modelbuilder_setup.md). The unconnected `acquire` folder variable is excluded from the public interface; the connected acquisition output folder is `acquire (2)`.

## Relocation and paths with spaces

A copied distribution containing the toolbox, adapters, core and utilities imported from a different directory whose path contains spaces. The copied Plan Script Tool executed successfully and published its JSON plan plus a typed expected-weeks table with **1,360 rows**. The copied model retained all 15 parameters. See [relocation evidence](../output/drought_modelbuilder_setup/relocation_check.json).

The full model was executed at the original location; a full acquisition/validation rerun of the relocated copy was not performed. This distinction limits the portability claim to model import and the planning adapter/core execution. Classmates must retain the complete code folder structure and select their own existing folders/cache/source paths.

## Scientific limits

The acquisition report explicitly returns **ready_for_rasterization=False**. Outstanding gates include historical assessed-domain and island coverage (especially Mona), polygon topology and projection behavior, and distinguishing assessed None from unknown coverage. Only after these gates are resolved should the weekly polygons be rasterized on the shared 250 m grid and used for frequency/duration/event metrics. Hazard-indicator evaluation and final course ranking/index calculations follow those metrics.
