"""Build a portable Drought Script Tool distribution without the large raw cache."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def package():
    files=[ROOT/'DroughtRisk_Model_Toolbox.atbx',ROOT/'drought.py',ROOT/'THIRD_PARTY_NOTICES.md',ROOT/'.gitignore',
           ROOT/'tests/test_drought.py']
    files.extend((ROOT/'utils').glob('usdm_*.py'))
    if (ROOT/'utils/__init__.py').exists():files.append(ROOT/'utils/__init__.py')
    files.extend(ROOT/'scripts'/name for name in
                 ('plan_drought_download.py','fetch_drought_data.py','validate_drought_download.py'))
    files.extend(ROOT/'tools'/name for name in ('build_toolbox.py','drought_tool_specs.py',
                 'build_drought_toolbox.py','package_drought_release.py','audit_drought_readiness.py'))
    files.extend((ROOT/'docs').glob('drought_*.md'))
    files.extend((ROOT/'docs').glob('drought_*.json'))
    files.extend(path for path in
                 (ROOT/'docs/drought_modelbuilder_graph.svg',ROOT/'docs/drought_modelbuilder_graph.png')
                 if path.exists())
    files.append(ROOT/'docs/arcgis_mcp_bridge_setup.md')
    files=sorted(set(files))
    with zipfile.ZipFile(ROOT/'DroughtRisk_Model_Toolbox.atbx') as toolbox:
        model_members=[name for name in toolbox.namelist() if name.endswith('.tool/tool.model')]
    manifest={'scope':'Three executable USDM acquisition Script Tools; inspect the setup guide for current ModelBuilder authoring and validation status.',
        'saved_drought_model_graph':bool(model_members),
        'saved_model_members':model_members,
        'model_presence_is_not_execution_validation':True,'raw_cache_included':False,
        'files':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    destination=ROOT/'dist/PRRisks_DroughtAcquisition.zip'
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for p in files:archive.write(p,p.relative_to(ROOT))
        archive.writestr('release_manifest.json',json.dumps(manifest,indent=2)+'\n')
        archive.writestr('README.txt',
            'Puerto Rico SDSS: USDM Drought acquisition\n'
            'Start with docs/drought_modelbuilder_setup.md.\n'
            'DroughtRisk_Model_Toolbox.atbx contains Plan, Fetch, Validate Script Tools.\n'
            'Inspect docs/drought_modelbuilder_setup.md for saved model and validation status.\n'
            'Keep drought.py, scripts and utils beside/below the toolbox.\n'
            'Use licensed ArcGIS Pro Python for Script Tools/geodatabase publication.\n'
            'MCP installation is optional; no new modeling dependencies are required.\n'
            'Raw GIS/statistics cache is not included. Select the supplied/shared cache or fetch it.\n'
            'Download validation is separate from raster/indicator/ranking readiness.\n')
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        for name,digest in manifest['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest()==digest,name
    return {'archive':str(destination),'files':len(files),'bytes':destination.stat().st_size,
            'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()}


if __name__=='__main__':print(json.dumps(package(),indent=2))
