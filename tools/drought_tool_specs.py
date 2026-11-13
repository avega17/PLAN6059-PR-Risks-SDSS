"""Declared public Script Tool interfaces; no expensive pre-run validation."""
from .build_toolbox import parameter


def validator(folder_index, outputs, plan=False):
    return '''import arcpy
import os

class ToolValidator:
    def __init__(self):
        self.params = arcpy.GetParameterInfo()

    def initializeParameters(self):
        if PLAN:
            self.params[6].filter.list = ['Baseline', 'Pilot']

    def updateParameters(self):
        folder = self.params[FOLDER].valueAsText
        for index, relative in OUTPUTS.items():
            self.params[index].value = os.path.normpath(os.path.join(folder, relative)) if folder else None

    def updateMessages(self):
        if PLAN:
            first, last = self.params[0].value, self.params[1].value
            if first is not None and last is not None and first > last:
                self.params[1].setErrorMessage('End Date must be on or after Start Date.')
'''.replace('PLAN',repr(plan)).replace('FOLDER',str(folder_index)).replace('OUTPUTS',repr(outputs))


DROUGHT_TOOLS = [
    dict(name='PlanDroughtDownload',label='Plan Drought Download',script='plan_drought_download.py',
         summary='Freeze the USDM Puerto Rico map-date cohort and inventory local ZIP candidates; no network access.',
         validator=validator(2,{7:'download_plan.json',8:'drought_plan.gdb/expected_weeks'},True),
         params=[
            parameter('StartDate','Start Date','GPDate','First requested calendar date. Baseline begins in 2000.',default='1/1/2000'),
            parameter('EndDate','End Date','GPDate','Last requested calendar date; baseline uses complete years.',default='12/31/2025'),
            parameter('OutputFolder','Output Folder','DEFolder','Existing plan output folder, outside source directories.'),
            parameter('LocalArchiveFolder','Local Archive Folder','DEFolder','Optional professor/archival ZIP input folder; originals are preserved.',optional=True),
            parameter('IncludeMunicipioStatistics','Include Municipio Statistics','GPBoolean','Include all 78 municipio categorical area-percent time series.',optional=True,default='true'),
            parameter('RecoveryBufferWeeks','Recovery Buffer Weeks','GPLong','Separate before/after observations for future event censoring; never included in baseline denominator.',optional=True,default=3),
            parameter('Mode','Mode','GPString','Baseline requires complete years. Pilot permits partial bounded intervals.',optional=True,default='Baseline',choices=['Baseline','Pilot']),
            parameter('DownloadPlan','Download Plan','DEFile','Frozen cohort/job specification; connect to Fetch Drought Data.',output=True,extensions=['json']),
            parameter('ExpectedWeeks','Expected Weeks','DETable','Map dates with BASELINE, START_BUFFER, END_BUFFER roles.',output=True)]),
    dict(name='FetchDroughtData',label='Fetch Drought Data',script='fetch_drought_data.py',
         summary='Retrieve and cache weekly GIS ZIPs and PR reference statistics with checksums and explicit quality warnings.',
         validator=validator(2,{4:'download_manifest.json',5:'drought_acquisition.gdb/statistics',6:'drought_acquisition.gdb/acquisition_qc',7:'statistics_canonical.csv'}),
         params=[
            parameter('DownloadPlan','Download Plan','DEFile','JSON from Plan Drought Download.',extensions=['json']),
            parameter('CacheFolder','Cache Folder','DEFolder','Existing persistent cache root; keep outside local source inputs.'),
            parameter('OutputFolder','Output Folder','DEFolder','Existing acquisition output folder.'),
            parameter('Resume','Resume','GPBoolean','Reuse only checksum-verified matching cached responses; false refreshes network snapshots.',optional=True,default='true'),
            parameter('DownloadManifest','Download Manifest','DEFile','Receipts, paths, audit results and acquisition status; connect to Validate Drought Download.',output=True,extensions=['json']),
            parameter('Statistics','Statistics','DETable','Typed, normalized area-percent and DSCI reference statistics.',output=True),
            parameter('AcquisitionQC','Acquisition QC','DETable','Source disagreements and acquisition warnings; no silent normalization.',output=True),
            parameter('CanonicalStatisticsCSV','Canonical Statistics CSV','DEFile','Portable normalized statistics retaining format, date, geography, role and source hash.',output=True,extensions=['csv'])]),
    dict(name='ValidateDroughtDownload',label='Validate Drought Download',script='validate_drought_download.py',
         summary='Recheck actual cached bytes, chronology and reference tables offline; this does not establish raster readiness.',
         validator=validator(1,{2:'download_validation.json'}),
         params=[
            parameter('DownloadManifest','Download Manifest','DEFile','JSON from Fetch Drought Data.',extensions=['json']),
            parameter('OutputFolder','Output Folder','DEFolder','Existing validation output folder.'),
            parameter('Report','Report','DEFile','JSON check report with a readable Markdown companion.',output=True,extensions=['json']),
            parameter('Passed','Passed','GPBoolean','True only when the acquisition contract passes; unresolved failures raise a tool error.',output=True)])]
