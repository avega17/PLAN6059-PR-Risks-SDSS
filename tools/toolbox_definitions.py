"""Typed Script Tool interfaces. Saved model graphs are maintained in ArcGIS Pro."""


def parameter(name, label, datatype, description, *, optional=False, output=False,
              extensions=None, polygon=False, default=None, choices=None):
    return dict(name=name, label=label, datatype=datatype, description=description,
                optional=optional, output=output, extensions=extensions,
                polygon=polygon, default=default, choices=choices)


def validator(folder, outputs, date_indexes=None):
    # Declare output paths before execution; never inspect datasets here.
    return f'''import arcpy
import os

class ToolValidator:
    def __init__(self):
        self.params = arcpy.GetParameterInfo()

    def initializeParameters(self):
        return

    def updateParameters(self):
        folder = self.params[{folder}].valueAsText
        for index, relative in {outputs!r}.items():
            self.params[index].value = os.path.normpath(os.path.join(folder, relative)) if folder else None

    def updateMessages(self):
        indexes = {date_indexes!r}
        if indexes:
            first, last = (self.params[i].value for i in indexes)
            if first is not None and last is not None and first > last:
                self.params[indexes[1]].setErrorMessage('End must be on or after Start.')
'''


HURRICANE_TOOLS = [
    dict(name='PrepareHurricaneData', label='Prepare Hurricane Data', script='prepare_hurricane_data.py',
         summary='Stage, preserve, audit and prepare USA-coordinate IBTrACS observations; no wind surface or rank is estimated.',
         validator=validator(1, {7: 'hurricane_prepare.gdb/hurricane_observations', 8: 'prepare_manifest.json'}, (2, 3)),
         params=[
             parameter('RawPoints', 'Raw Points', 'DEFile', 'Local IBTrACS points .shp; matching .shx, .dbf and .prj sidecars must remain beside it.', extensions=['shp']),
             parameter('OutputFolder', 'Preparation Folder', 'DEFolder', 'Existing writable folder for preparation outputs. Use a separate folder from source datasets.'),
             parameter('StartSeason', 'Start Season', 'GPLong', 'First included IBTrACS SEASON, inclusive.', optional=True, default=1955),
             parameter('EndSeason', 'End Season', 'GPLong', 'Last included IBTrACS SEASON, inclusive.', optional=True, default=2025),
             parameter('RawLines', 'Raw Lines', 'DEFile', 'Optional source track lines for inventory only; never substituted for USA-coordinate observations.', optional=True, extensions=['shp']),
             parameter('SPCReports', 'SPC Reports', 'DEFile', 'Optional SPC severe-wind reports for separate contextual inventory.', optional=True, extensions=['shp']),
             parameter('ExportCSV', 'Export CSV', 'GPBoolean', 'Optional duplicate CSV export; off by default when geodatabase tables are published.', optional=True, default='false'),
             parameter('Observations', 'Prepared Observations', 'DEFeatureClass', 'Prepared WGS84 observations rebuilt from USA coordinates.', output=True),
             parameter('PrepareManifest', 'Prepare Manifest', 'DEFile', 'Machine-readable preparation output paths and summary; connect to Validate Prototype.', output=True, extensions=['json']),
         ]),
    dict(name='EstablishReferenceGrid', label='Establish Reference Grid', script='establish_reference_grid.py',
         summary='Create the fixed EPSG:32161 250 m reference and land mask; includes Puerto Rico, Vieques, Culebra and Mona.',
         validator=validator(0, {2: 'reference250.tif', 3: 'study_mask250.tif', 4: 'grid.gdb/study_boundary32161', 5: 'grid_spec.json'}, None),
         params=[
             parameter('OutputFolder', 'Grid Folder', 'DEFolder', 'Existing writable folder for the grid and boundary cache.'),
             parameter('Boundary', 'Boundary', 'GPFeatureLayer', 'Optional approved polygon boundary. If blank, acquire pinned Natural Earth 5.1.1; its 1:10 million boundary is provisional.', optional=True, polygon=True),
             parameter('ReferenceRaster', 'Reference Raster', 'DERasterDataset', 'Constant-zero alignment raster over the complete reference rectangle; not a hazard score.', output=True),
             parameter('StudyMask', 'Study Mask', 'DERasterDataset', 'Land=1 and exterior=NoData, rasterized by cell center.', output=True),
             parameter('ProjectedBoundary', 'Projected Boundary', 'DEFeatureClass', 'Working boundary projected into EPSG:32161; source is preserved.', output=True),
             parameter('GridSpec', 'Grid Specification', 'DEFile', 'Exact grid extent, cell size, anchor, paths and provenance; connect to Validate Prototype.', output=True, extensions=['json']),
         ]),
    dict(name='ValidatePrototype', label='Validate Prototype', script='validate_prototype.py',
         summary='Validate the actual prepared observations and shared grid; this is not scientific wind-model validation.',
         validator=validator(2, {3: 'validation_report.json'}, None),
         params=[
             parameter('PrepareManifest', 'Prepare Manifest', 'DEFile', 'prepare_manifest.json returned by Prepare Hurricane Data.', extensions=['json']),
             parameter('GridSpec', 'Grid Specification', 'DEFile', 'grid_spec.json returned by Establish Reference Grid.', extensions=['json']),
             parameter('OutputFolder', 'Validation Folder', 'DEFolder', 'Existing writable folder for validation reports.'),
             parameter('Report', 'Validated Hurricane Data', 'DEFile', 'Final validation JSON and manifest reference; handoff to later processing. Failures raise a geoprocessing error.', output=True, extensions=['json']),
         ]),
]

HURRICANE_TOOLS.extend([
    dict(name='PrepareWindInputs', label='Prepare Wind Inputs', script='prepare_wind_inputs.py',
         summary='Validate preparation/grid and prepare full USA tracks for four HURRECON benchmark storms.',
         validator=validator(2, {4: 'hurricane_winds.gdb'}), params=[
             parameter('ValidatedHurricaneData', 'Validated Hurricane Data', 'DEFile', 'validation_report.json from Validate Prototype.', extensions=['json']),
             parameter('GridSpec', 'Grid Specification', 'DEFile', 'Validated shared grid_spec.json.', extensions=['json']),
             parameter('OutputFolder', 'Wind Output Folder', 'DEFolder', 'Folder for hurricane_winds.gdb.'),
             parameter('BenchmarkStorms', 'Benchmark Storms', 'GPString', 'Semicolon-separated SIDs for Betsy, Hugo, Georges and Maria.', optional=True,
                       default='1956222N13313;1989254N13340;1998259N10335;2017260N12310'),
             parameter('WindWorkspace', 'Wind Workspace', 'DEWorkspace', 'Prepared wind tracks, cells, settings and size table.', output=True)]),
    dict(name='EstimateWindFields', label='Estimate Wind Fields', script='estimate_wind_fields.py',
         summary='Benchmark four size scenarios at 15, 5 and 2.5 minutes; retain every 5-minute event peak.',
         validator=validator(0, {2: 'wind_event_catalog'}), params=[
             parameter('WindWorkspace', 'Wind Workspace', 'DEWorkspace', 'Geodatabase returned by Prepare Wind Inputs.'),
             parameter('SizeScenarios', 'Size Scenarios', 'DETable', 'Optional table with RMW_KM and PROFILE_B. Blank uses the four published pairs.', optional=True),
             parameter('WindCatalog', 'Wind Field Catalog', 'DETable', 'Storm/scenario catalog with relative raster names.', output=True)]),
    dict(name='EvaluateWindEstimates', label='Evaluate Wind Estimates', script='evaluate_wind_estimates.py',
         summary='Check retained fields, temporal convergence, quadrant radii and optional comparable station winds.',
         validator=validator(0, {}), params=[
             parameter('WindCatalog', 'Wind Field Catalog', 'DETable', 'Catalog returned by Estimate Wind Fields.'),
             parameter('ReferenceObservations', 'Reference Wind Observations', 'DETable', 'Optional 60-second, 10-m station maxima with documented exposure/window/source; see setup guide.', optional=True),
             parameter('Summary', 'Wind Benchmark Summary', 'DETable', 'Geodatabase evaluation results.', output=True),
             parameter('Report', 'Validated Wind Benchmark', 'DEFile', 'Existing validation report with wind_benchmark status and evidence.', output=True, extensions=['json'])]),
])

DROUGHT_TOOLS = [
    dict(name='PlanDroughtDownload', label='Plan Drought Download', script='plan_drought_download.py',
         summary='Freeze the USDM Puerto Rico map-date cohort and inventory local ZIP candidates; no network access.',
         validator=validator(2, {7: 'download_plan.json'}, (0, 1)),
         params=[
             parameter('StartDate', 'Start Date', 'GPDate', 'First requested calendar date. Baseline begins in 2000.', default='1/1/2000'),
             parameter('EndDate', 'End Date', 'GPDate', 'Last requested calendar date; baseline uses complete years.', default='12/31/2025'),
             parameter('OutputFolder', 'Plan Folder', 'DEFolder', 'Existing plan output folder, outside source directories.'),
             parameter('LocalArchiveFolder', 'Local Archive Folder', 'DEFolder', 'Optional professor/archival ZIP input folder; originals are preserved.', optional=True),
             parameter('IncludeMunicipioStatistics', 'Include Municipio Statistics', 'GPBoolean', 'Include all 78 municipio categorical area-percent time series.', optional=True, default='true'),
             parameter('RecoveryBufferWeeks', 'Recovery Buffer Weeks', 'GPLong', 'Separate before/after observations for future event censoring; never included in baseline denominator.', optional=True, default=3),
             parameter('Mode', 'Mode', 'GPString', 'Baseline requires complete years. Pilot permits partial bounded intervals.', optional=True, default='Baseline', choices=['Baseline', 'Pilot']),
             parameter('DownloadPlan', 'Download Plan', 'DEFile', 'Frozen cohort/job specification; connect to Fetch Drought Data.', output=True, extensions=['json']),
         ]),
    dict(name='FetchDroughtData', label='Fetch Drought Data', script='fetch_drought_data.py',
         summary='Retrieve and cache weekly GIS ZIPs and PR reference statistics with checksums and explicit quality warnings.',
         validator=validator(2, {5: 'download_manifest.json'}, None),
         params=[
             parameter('DownloadPlan', 'Download Plan', 'DEFile', 'JSON from Plan Drought Download.', extensions=['json']),
             parameter('CacheFolder', 'Cache Folder', 'DEFolder', 'Existing persistent cache root; keep outside local source inputs.'),
             parameter('OutputFolder', 'Acquisition Folder', 'DEFolder', 'Existing acquisition output folder.'),
             parameter('Resume', 'Resume', 'GPBoolean', 'Reuse only checksum-verified matching cached responses; false refreshes network snapshots.', optional=True, default='true'),
             parameter('ExportCSV', 'Export CSV', 'GPBoolean', 'Optional duplicate CSV export; off by default when geodatabase tables are published.', optional=True, default='false'),
             parameter('DownloadManifest', 'Download Manifest', 'DEFile', 'Receipts, paths, audit results and acquisition status; connect to Validate Drought Download.', output=True, extensions=['json']),
         ]),
    dict(name='ValidateDroughtDownload', label='Validate Drought Download', script='validate_drought_download.py',
         summary='Recheck actual cached bytes, chronology and reference tables offline; this does not establish raster readiness.',
         validator=validator(1, {2: 'download_validation.json'}, None),
         params=[
             parameter('DownloadManifest', 'Download Manifest', 'DEFile', 'JSON from Fetch Drought Data.', extensions=['json']),
             parameter('OutputFolder', 'Validation Folder', 'DEFolder', 'Existing validation output folder.'),
             parameter('Report', 'Validated Drought Data', 'DEFile', 'Final validation JSON and manifest reference; handoff to later processing. Failures raise a geoprocessing error.', output=True, extensions=['json']),
         ]),
]

DROUGHT_TOOLS.extend([
    dict(name='PrepareDroughtStates',label='Prepare Drought States',script='prepare_drought_states.py',
        summary='Prepare the complete cached 2000-2025 weekly spatial series, preserving unknown coverage.',
        validator=validator(2,{4:'drought_processing.gdb'}),params=[
            parameter('ValidatedDroughtData','Validated Drought Data','DEFile','Passing acquisition download_validation.json.',extensions=['json']),
            parameter('GridSpec','Grid Specification','DEFile','Shared EPSG:32161 250 m grid_spec.json.',extensions=['json']),
            parameter('OutputFolder','Processing Folder','DEFolder','Folder for drought_processing.gdb and the weekly cube.'),
            parameter('ReuseCompletedCache','Reuse Completed Cache','GPBoolean','Reuse only fingerprint/checksum-verified completed spatial products.',optional=True,default='true'),
            parameter('ProcessingWorkspace','Processing Workspace','DEWorkspace','Prepared polygons, settings and weekly-state reference.',output=True)]),
    dict(name='CalculateDroughtMetrics',label='Calculate Drought Metrics',script='calculate_drought_metrics.py',
        summary='Calculate continuous occupancy, severity and both event rules; no classification.',
        validator=validator(0,{1:'metric_catalog'}),params=[
            parameter('ProcessingWorkspace','Processing Workspace','DEWorkspace','Workspace from Prepare Drought States.'),
            parameter('MetricsCatalog','Metrics Catalog','DETable','Indicator paths and units; connect to Evaluate Drought Metrics.',output=True)]),
    dict(name='EvaluateDroughtMetrics',label='Evaluate Drought Metrics',script='evaluate_drought_metrics.py',
        summary='Validate indicators, coverage, annual counts and spatial/reference comparisons before classification review.',
        validator=validator(0,{}),params=[
            parameter('MetricsCatalog','Metrics Catalog','DETable','Catalog from Calculate Drought Metrics.'),
            parameter('PrimaryIndicator','D1+ Weeks per Year','DERasterDataset','Average annual D1+ weekly observations; incomplete coverage is NoData.',output=True),
            parameter('ValidWeekCount','Valid Week Count','DERasterDataset','Baseline valid assessments per study-land cell; not a hazard score.',output=True),
            parameter('Report','Validated Drought Metrics','DEFile','Existing report with a separately scoped processing assessment.',output=True,extensions=['json'])]),
])
