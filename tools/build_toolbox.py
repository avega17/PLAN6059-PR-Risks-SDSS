"""Build the linked ArcGIS Pro Script Tools without extra dependencies.

The small ATBX Zip/JSON serialization pattern is adapted from MIT-licensed
autobox, commit 298c57385cdede8b3417cc7b736a066febd874a9:
https://github.com/realiii/autobox
See THIRD_PARTY_NOTICES.md for attribution and the complete license.

This writes Script Tools only. A ModelBuilder diagram must be authored in Pro.
Rebuilding preserves other archive members and manually authored model tools.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ALIAS = 'prrisks'
import sys
sys.path.insert(0, str(ROOT))


from tools.toolbox_definitions import HURRICANE_TOOLS as TOOLS, DROUGHT_TOOLS


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
    if spec.get('choices'):
        content['domain'] = {'type': 'GPCodedValueDomain', 'items': [{'value': v, 'code': v} for v in spec['choices']]}
    if spec['polygon']:
        content['domain'] = {'type': 'GPFeatureClassDomain', 'geometrytype': ['Polygon']}
    if spec['default'] is not None:
        content['value'] = str(spec['default'])
    resources = {key + '.title': spec['label'], key + '.descr': spec['description']}
    return content, resources


def build_toolbox(output=ROOT / 'HurricaneWinds_Model_Toolbox.atbx', overwrite=False, *, tools=None,
                  alias=ALIAS, title=None, description=None):
    """Write deterministic Script Tool definitions with relative source links."""
    tool_specs = TOOLS if tools is None else tools
    output = Path(output).expanduser().resolve()
    if output.suffix.lower() != '.atbx':
        raise ValueError('Output must use the .atbx extension.')
    if output.exists() and not overwrite:
        raise FileExistsError('Toolbox exists; use --overwrite to update Script Tools while preserving saved models.')
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
        'descr': description or 'Hurricane preparation, shared grid, validation and HURRECON wind-field benchmarking.'}}, indent=2)
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
        members[folder + 'tool.script.validate.py'] = tool['validator']
    retained_info = {}
    if output.exists():
        # A model saved in Pro is user-authored state. Preserve its archive
        # members, resource labels and toolset references during regeneration.
        with zipfile.ZipFile(output) as previous:
            old_members = {name: previous.read(name) for name in previous.namelist()}
            old_info = {info.filename: copy.copy(info) for info in previous.infolist()}
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
        retained_info = {name: old_info[name] for name in old_members if name not in members}
        old_members.update({name: text.encode('utf-8') for name, text in members.items()})
        encoded_members = old_members
    else:
        encoded_members = {name: text.encode('utf-8') for name, text in members.items()}
    temporary = output.with_suffix('.atbx.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, contents in encoded_members.items():
                original_info = retained_info.get(name)
                info = (copy.copy(original_info) if original_info is not None else
                        zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)))
                if original_info is None:
                    info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, contents)
                if original_info is not None:
                    # zipfile replaces a zero external_attr during writestr.
                    # Restore it before the central directory is finalized.
                    info.external_attr = original_info.external_attr
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return output


def verify_toolbox(path, tools=None):
    """Import in ArcGIS Pro and validate the public parameter contracts."""
    import arcpy

    with zipfile.ZipFile(path) as archive:
        alias = json.loads(archive.read('toolbox.content'))['alias']
    # Overriding the import alias also changes the saved toolbox alias in Pro.
    # Verify using its declared alias so checks do not alter the deliverable.
    arcpy.ImportToolbox(str(path))
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
                          'GPFeatureLayer': 'Feature Layer', 'DEWorkspace': 'Workspace',
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
                from utils.drought.usdm_common import as_date
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
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--verify', action='store_true')
    options = parser.parse_args()
    for filename, specs, alias, title in (
        ('HurricaneWinds_Model_Toolbox.atbx', TOOLS, 'prrisks', 'Hurricane Winds'),
        ('DroughtRisk_Model_Toolbox.atbx', DROUGHT_TOOLS, 'droughtprobe', 'Drought')):
        path = build_toolbox(ROOT/filename, options.overwrite, tools=specs, alias=alias,
                             title='Puerto Rico SDSS - ' + title,
                             description=('Preparation and HURRECON wind-field benchmarking.' if alias == 'prrisks'
                                          else 'Linked drought acquisition and continuous hazard-processing Script Tools.'))
        report = {'toolbox': str(path)}
        if options.verify:
            report['tools'] = verify_toolbox(path, specs)
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
