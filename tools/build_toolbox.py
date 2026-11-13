"""Build the three linked ArcGIS Pro Script Tools without extra dependencies.

The small ATBX Zip/JSON serialization pattern is adapted from MIT-licensed
autobox, commit 298c57385cdede8b3417cc7b736a066febd874a9:
https://github.com/realiii/autobox
See THIRD_PARTY_NOTICES.md for attribution and the complete license.

This writes Script Tools only. A ModelBuilder diagram must be authored in Pro.
Rebuilding preserves other archive members and manually authored model tools.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ALIAS = 'prrisks'


def parameter(name, label, datatype, description, *, optional=False,
              output=False, extensions=None, polygon=False, default=None, choices=None):
    return dict(name=name, label=label, datatype=datatype,
                description=description, optional=optional, output=output,
                extensions=extensions, polygon=polygon, default=default, choices=choices)


TOOLS = [
    dict(name='PrepareHurricaneData', label='Prepare Hurricane Data',
         script='prepare_hurricane_data.py',
         summary='Stage, preserve, audit and prepare USA-coordinate IBTrACS observations; no wind surface or rank is estimated.',
         params=[
             parameter('RawPoints', 'Raw Points', 'DEFile', 'Local IBTrACS points .shp; matching .shx, .dbf and .prj sidecars must remain beside it.', extensions=['shp']),
             parameter('OutputFolder', 'Output Folder', 'DEFolder', 'Existing writable folder for preparation outputs. Use a separate folder from source datasets.'),
             parameter('StartSeason', 'Start Season', 'GPLong', 'First included IBTrACS SEASON, inclusive.', optional=True, default=1955),
             parameter('EndSeason', 'End Season', 'GPLong', 'Last included IBTrACS SEASON, inclusive.', optional=True, default=2025),
             parameter('RawLines', 'Raw Lines', 'DEFile', 'Optional source track lines for inventory only; never substituted for USA-coordinate observations.', optional=True, extensions=['shp']),
             parameter('SPCReports', 'SPC Reports', 'DEFile', 'Optional SPC severe-wind reports for separate contextual inventory.', optional=True, extensions=['shp']),
             parameter('Observations', 'Observations', 'DEFeatureClass', 'Prepared WGS84 observations rebuilt from USA coordinates.', output=True),
             parameter('Storms', 'Storms', 'DETable', 'Distinct-storm and coverage summary.', output=True),
             parameter('QC', 'QC', 'DETable', 'Record-level quality and row-disposition evidence.', output=True),
             parameter('CanonicalCSV', 'Canonical CSV', 'DEFile', 'Portable source rows, normalized core fields and row accounting.', output=True, extensions=['csv']),
             parameter('Inventory', 'Inventory', 'DEFile', 'Source checksums, schema and provenance inventory.', output=True, extensions=['json']),
             parameter('PrepareManifest', 'Prepare Manifest', 'DEFile', 'Machine-readable preparation output paths and summary; connect to Validate Prototype.', output=True, extensions=['json']),
         ]),
    dict(name='EstablishReferenceGrid', label='Establish Reference Grid',
         script='establish_reference_grid.py',
         summary='Create the fixed EPSG:32161 250 m reference and land mask; includes Puerto Rico, Vieques, Culebra and Mona.',
         params=[
             parameter('OutputFolder', 'Output Folder', 'DEFolder', 'Existing writable folder for the grid and boundary cache.'),
             parameter('Boundary', 'Boundary', 'GPFeatureLayer', 'Optional approved polygon boundary. If blank, acquire pinned Natural Earth 5.1.1; its 1:10 million boundary is provisional.', optional=True, polygon=True),
             parameter('ReferenceRaster', 'Reference Raster', 'DERasterDataset', 'Constant-zero alignment raster over the complete reference rectangle; not a hazard score.', output=True),
             parameter('StudyMask', 'Study Mask', 'DERasterDataset', 'Land=1 and exterior=NoData, rasterized by cell center.', output=True),
             parameter('ProjectedBoundary', 'Projected Boundary', 'DEFeatureClass', 'Working boundary projected into EPSG:32161; source is preserved.', output=True),
             parameter('GridSpec', 'Grid Spec', 'DEFile', 'Exact grid extent, cell size, anchor, paths and provenance; connect to Validate Prototype.', output=True, extensions=['json']),
             parameter('GridManifest', 'Grid Manifest', 'DEFile', 'Machine-readable boundary and grid manifest.', output=True, extensions=['json']),
         ]),
    dict(name='ValidatePrototype', label='Validate Prototype',
         script='validate_prototype.py',
         summary='Validate the actual prepared observations and shared grid; this is not scientific wind-model validation.',
         params=[
             parameter('PrepareManifest', 'Prepare Manifest', 'DEFile', 'prepare_manifest.json returned by Prepare Hurricane Data.', extensions=['json']),
             parameter('GridSpec', 'Grid Spec', 'DEFile', 'grid_spec.json returned by Establish Reference Grid.', extensions=['json']),
             parameter('OutputFolder', 'Output Folder', 'DEFolder', 'Existing writable folder for validation reports.'),
             parameter('Report', 'Report', 'DEFile', 'JSON checks and evidence; a companion Markdown report is also written.', output=True, extensions=['json']),
             parameter('Passed', 'Passed', 'GPBoolean', 'True when all prototype checks pass; failed validation raises a tool error.', output=True),
         ]),
]


VALIDATOR = '''import arcpy
import os

class ToolValidator:
    def __init__(self):
        self.params = arcpy.GetParameterInfo()

    def initializeParameters(self):
        return

    def updateParameters(self):
        # Declare deterministic paths so ModelBuilder can validate downstream
        # required inputs before their files exist. No dataset access or GP.
        if len(self.params) == 12:
            folder_index, first_output = 1, 6
            relative = (
                'hurricane_prepare.gdb/hurricane_observations',
                'hurricane_prepare.gdb/hurricane_storms',
                'hurricane_prepare.gdb/hurricane_qc',
                'hurricane_observations.csv', 'source_inventory.json',
                'prepare_manifest.json')
        elif len(self.params) == 7:
            folder_index, first_output = 0, 2
            relative = ('reference250.tif', 'study_mask250.tif',
                        'grid.gdb/study_boundary32161',
                        'grid_spec.json', 'grid_manifest.json')
        else:
            folder_index, first_output = 2, 3
            relative = ('validation_report.json',)
        folder = self.params[folder_index].valueAsText
        for index, name in enumerate(relative, first_output):
            self.params[index].value = (
                os.path.normpath(os.path.join(folder, name)) if folder else None)

    def updateMessages(self):
        # Only this tool has StartSeason/EndSeason. Do not inspect future
        # ModelBuilder datasets or run geoprocessing during validation.
        if len(self.params) == 12:
            first, last = self.params[2].value, self.params[3].value
            if first is not None and last is not None and int(first) > int(last):
                self.params[3].setErrorMessage('End Season must be on or after Start Season.')
'''


def _parameter_content(spec):
    key = spec['name'].lower()
    content = {'displayname': '$rc:' + key + '.title',
               'datatype': {'type': spec['datatype']},
               'description': '$rc:' + key + '.descr'}
    if spec['output']:
        content.update(type='derived', direction='out')
    elif spec['optional']:
        content['type'] = 'optional'
    if spec['extensions']:
        content['domain'] = {'type': 'GPFileDomain', 'filetypes': spec['extensions']}
    if spec['polygon']:
        content['domain'] = {'type': 'GPFeatureClassDomain', 'geometrytype': ['Polygon']}
    if spec['default'] is not None:
        content['value'] = str(spec['default'])
    resources = {key + '.title': spec['label'], key + '.descr': spec['description']}
    return content, resources


def build_toolbox(output=ROOT / 'PRRisks.atbx', overwrite=False, *, tools=None,
                  alias=ALIAS, title=None, description=None):
    """Write deterministic Script Tool definitions with relative source links."""
    tool_specs = TOOLS if tools is None else tools
    output = Path(output).expanduser().resolve()
    if output.suffix.lower() != '.atbx':
        raise ValueError('Output must use the .atbx extension.')
    if output.exists() and not overwrite:
        raise FileExistsError('Toolbox exists; use --overwrite to update the three Script Tools while preserving other tools.')
    if output.parent != ROOT:
        raise ValueError('Keep the toolbox at the repository root so linked scripts remain portable.')
    for tool in tool_specs:
        if not (ROOT / 'scripts' / tool['script']).is_file():
            raise FileNotFoundError(ROOT / 'scripts' / tool['script'])
    members = {}
    content = {'version': '1.0', 'alias': alias, 'displayname': '$rc:title',
               'description': '$rc:descr',
               'toolsets': {'<root>': {'tools': [tool['name'] for tool in tool_specs]}}}
    members['toolbox.content'] = json.dumps(content, indent=2)
    members['toolbox.content.rc'] = json.dumps({'map': {
        'title': title or 'Puerto Rico SDSS - Hurricane Winds',
        'descr': description or 'Three auditable ArcPy stages for preparation, shared grid establishment and prototype validation. No wind estimation or hazard ranking.'}}, indent=2)
    for tool in tool_specs:
        params, resources = {}, {'title': tool['label'], 'description': tool['summary'], 'summary': tool['summary']}
        for spec in tool['params']:
            definition, labels = _parameter_content(spec)
            params[spec['name']] = definition
            resources.update(labels)
        folder = tool['name'] + '.tool/'
        definition = {'type': 'ScriptTool', 'displayname': '$rc:title',
                      'app_ver': '13.4', 'product': '100',
                      'description': '$rc:description', 'params': params}
        members[folder + 'tool.content'] = json.dumps(definition, indent=2)
        members[folder + 'tool.content.rc'] = json.dumps({'map': resources}, indent=2)
        # ATBX's virtual tool folder is two levels below the external root.
        members[folder + 'tool.script.execute.link'] = '..\\..\\scripts\\' + tool['script']
        members[folder + 'tool.script.validate.py'] = tool.get('validator',VALIDATOR)
    if output.exists():
        # A model saved in Pro is user-authored state. Preserve its archive
        # members, resource labels and toolset references during regeneration.
        with zipfile.ZipFile(output) as previous:
            old_members = {name: previous.read(name) for name in previous.namelist()}
        old_content = json.loads(old_members['toolbox.content'])
        old_resource = json.loads(old_members['toolbox.content.rc'])
        known_names = {tool['name'] for tool in tool_specs}
        toolsets = old_content.get('toolsets', {})
        legacy_root = toolsets.pop('', {})
        toolsets.setdefault('<root>', {}).setdefault('tools', []).extend(
            legacy_root.get('tools', []))
        for toolset in toolsets.values():
            toolset['tools'] = [name for name in toolset.get('tools', [])
                                if name.split(':', 1)[0] not in known_names]
        toolsets.setdefault('<root>', {}).setdefault('tools', []).extend(tool['name'] for tool in tool_specs)
        old_content.update(content)
        old_content['toolsets'] = toolsets
        old_resource.setdefault('map', {}).update(json.loads(members['toolbox.content.rc'])['map'])
        members['toolbox.content'] = json.dumps(old_content, indent=2)
        members['toolbox.content.rc'] = json.dumps(old_resource, indent=2)
        known_folders = {name.casefold() + '.tool' for name in known_names}
        old_members = {name: contents for name, contents in old_members.items()
                       if name.split('/', 1)[0].casefold() not in known_folders}
        old_members.update({name: text.encode('utf-8') for name, text in members.items()})
        encoded_members = old_members
    else:
        encoded_members = {name: text.encode('utf-8') for name, text in members.items()}
    temporary = output.with_suffix('.atbx.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, contents in encoded_members.items():
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, contents)
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return output


def verify_toolbox(path, tools=None):
    """Import in ArcGIS Pro and validate the public parameter contracts."""
    import arcpy

    alias = 'prrisksverify'
    arcpy.ImportToolbox(str(path), alias)
    result = []
    for tool in (TOOLS if tools is None else tools):
        parameters = arcpy.GetParameterInfo(tool['name'] + '_' + alias)
        if len(parameters) != len(tool['params']):
            raise ValueError(f"Unexpected parameter count for {tool['name']}")
        metadata = []
        for actual, expected in zip(parameters, tool['params']):
            expected_direction = 'Output' if expected['output'] else 'Input'
            expected_type = ('Derived' if expected['output'] else
                             'Optional' if expected['optional'] else 'Required')
            if (actual.name != expected['name'] or actual.direction != expected_direction
                    or actual.parameterType != expected_type):
                raise ValueError(f"Unexpected parameter contract for {tool['name']}.{expected['name']}")
            type_names = {'DEFile': 'File', 'DEFolder': 'Folder', 'GPLong': 'Long',
                          'DEFeatureClass': 'Feature Class', 'DETable': 'Table',
                          'GPFeatureLayer': 'Feature Layer',
                          'DERasterDataset': 'Raster Dataset', 'GPBoolean': 'Boolean','GPDate':'Date','GPString':'String'}
            if actual.datatype != type_names[expected['datatype']]:
                raise ValueError(f"Unexpected datatype for {tool['name']}.{expected['name']}")
            actual_filter = list(getattr(actual.filter, 'list', None) or [])
            expected_filter = expected['extensions'] or expected.get('choices') or (['Polygon'] if expected['polygon'] else [])
            if actual_filter != expected_filter:
                raise ValueError(f"Unexpected filter for {tool['name']}.{expected['name']}")
            expected_default = expected['default']
            default_matches = actual.valueAsText == str(expected_default)
            if expected['datatype']=='GPDate' and expected_default is not None:
                from utils.usdm_common import as_date
                default_matches = as_date(actual.valueAsText)==as_date(expected_default)
            if expected_default is not None and not default_matches:
                raise ValueError(f"Unexpected default for {tool['name']}.{expected['name']}")
            metadata.append({'name': actual.name, 'datatype': actual.datatype,
                             'direction': actual.direction, 'type': actual.parameterType,
                             'default': actual.valueAsText,
                             'filter': actual_filter})
        result.append({'name': tool['name'], 'parameters': metadata})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'PRRisks.atbx')
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--verify', action='store_true', help='Verify imports/parameter definitions with installed ArcPy.')
    options = parser.parse_args()
    path = build_toolbox(options.output, options.overwrite)
    report = {'toolbox': str(path), 'tools': [tool['name'] for tool in TOOLS]}
    if options.verify:
        report['verification'] = verify_toolbox(path)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
