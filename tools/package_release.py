"""Package portable course tools and documentation without raw data or caches."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def package_data(output=None):
    """Archive the verified saved-model run as a separate review snapshot."""
    source = ROOT / 'output' / 'model_run'
    report = json.loads((source/'validation/validation_report.json').read_text())
    if not report['checks'] or not all(check['passed'] for check in report['checks']):
        raise ValueError('Package data only after all saved-model validation checks pass.')
    destination = Path(output or ROOT/'dist/PRRisks_HurricanePreparedData.zip').resolve()
    files = sorted(path for path in source.rglob('*')
                   if path.is_file() and not path.name.lower().endswith('.lock'))
    manifest = {'created_utc': datetime.now(timezone.utc).isoformat(),
                'scope': 'Verified audit data; no local-wind fields or hazard ranks.',
                'validation_checks': len(report['checks']),
                'paths_in_provenance': 'Retained as executed; regenerate for a different workspace.',
                'files': {path.relative_to(source).as_posix(): file_sha256(path) for path in files}}
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(source))
        archive.writestr('data_manifest.json', json.dumps(manifest, indent=2)+'\n')
        archive.writestr('README.txt',
            'Verified HurricaneAuditPrototype data snapshot.\n'
            'Start with prepare/hurricane_data_audit.md and validation/validation_report.md.\n'
            'Prepared feature classes/tables: prepare/hurricane_prepare.gdb.\n'
            'The CSV accounts for all 128,098 source rows; select ROW_STATUS=INCLUDED\n'
            'for the 62,485 prepared observations. No local-wind surface or ranking is included.\n'
            'Source receipts, staged source copies, grid cache and provenance are retained.\n'
            'Provenance preserves the original execution paths. Extract this snapshot for\n'
            'review; rerun the portable code/tools with your local paths for new analyses.\n')
    temporary.replace(destination)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError('Data archive integrity check failed.')
    return {'archive': str(destination), 'files': len(files),
            'sha256': file_sha256(destination), 'validation_checks': len(report['checks'])}


def package_release(output=None, require_model=True):
    destination = Path(output or ROOT / 'dist' / 'PRRisks_HurricanePrototype.zip').resolve()
    toolbox = ROOT / 'PRRisks.atbx'
    with zipfile.ZipFile(toolbox) as archive:
        model_definitions = []
        for member in archive.namelist():
            if member.endswith('/tool.content'):
                content = json.loads(archive.read(member))
                if content.get('type') == 'ModelTool':
                    folder = member.rsplit('/', 1)[0] + '/'
                    payloads = [name for name in archive.namelist()
                                if name.startswith(folder) and name.endswith('.model')]
                    model_definitions.append({'name': folder.split('.')[0],
                                              'has_model_graph': bool(payloads)})
        if require_model and not any(model['has_model_graph'] for model in model_definitions):
            raise ValueError('The toolbox has no saved ModelBuilder graph; finish/save the model before packaging.')
    files = [ROOT / name for name in ('PRRisks.atbx', 'hurricane_winds.py', 'README.md',
                                     'THIRD_PARTY_NOTICES.md', '.gitignore')]
    for folder in ('scripts', 'utils', 'docs', 'tests', 'tools'):
        files.extend(path for path in (ROOT / folder).rglob('*')
                     if path.is_file() and '__pycache__' not in path.parts
                     and path.suffix.lower() in {'.py', '.md', '.png', '.svg', '.json'})
    files = sorted(set(files))
    manifest = {'created_utc': datetime.now(timezone.utc).isoformat(),
                'scope': 'Hurricane audit prototype; wind estimation and hazard ranking deferred.',
                'raw_datasets_included': False,
                'model_tools': model_definitions,
                'files': {str(path.relative_to(ROOT)).replace('\\', '/'):
                          hashlib.sha256(path.read_bytes()).hexdigest() for path in files}}
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT))
        archive.writestr('release_manifest.json', json.dumps(manifest, indent=2) + '\n')
    temporary.replace(destination)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError('Release archive integrity check failed.')
        for name, expected in manifest['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError(f'Packaged file checksum differs: {name}')
    return {'archive': str(destination), 'files': len(files),
            'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
            'model_tools': model_definitions}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--data-only', action='store_true',
                        help='Package verified output/model_run data separately from code.')
    parser.add_argument('--allow-script-tools-only', action='store_true',
                        help='Explicitly allow an incomplete GUI model; not the complete assignment deliverable.')
    arguments = parser.parse_args()
    result = (package_data(arguments.output) if arguments.data_only else
              package_release(arguments.output, not arguments.allow_script_tools_only))
    print(json.dumps(result, indent=2))
