"""Build one portable code distribution from an explicit inclusion list."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'AGENTS.md', 'README.md', 'THIRD_PARTY_NOTICES.md', '.gitignore',
    'hurricane_winds.py', 'drought.py',
    'HurricaneWinds_Model_Toolbox.atbx', 'DroughtRisk_Model_Toolbox.atbx',
    'scripts/prepare_hurricane_data.py', 'scripts/establish_reference_grid.py',
    'scripts/validate_prototype.py', 'scripts/plan_drought_download.py',
    'scripts/fetch_drought_data.py', 'scripts/validate_drought_download.py',
    'utils/__init__.py', 'utils/hurricane/__init__.py',
    'utils/hurricane/ibtracs.py', 'utils/hurricane/validation.py',
    'utils/shared/__init__.py', 'utils/shared/grid.py', 'utils/drought/__init__.py',
    'utils/drought/usdm_archive.py', 'utils/drought/usdm_catalog.py',
    'utils/drought/usdm_common.py', 'utils/drought/usdm_download.py',
    'utils/drought/usdm_http.py', 'utils/drought/usdm_statistics.py',
    'utils/drought/usdm_validation.py',
    'docs/hurricane_modelbuilder_setup.md', 'docs/drought_modelbuilder_setup.md',
    'docs/hurricane_processing_plan.md', 'docs/drought_processing_plan.md',
    'docs/arcgis_mcp_bridge_setup.md',
    'figures/hurricane_modelbuilder_graph.png', 'figures/drought_modelbuilder_graph.png',
    'references/SDSS Final Project Fall 2026.pdf',
    'references/IBTrACS_version4r01_Technical_Details.pdf',
    'references/Variable Index Calculation Process Example.txt',
    'tools/build_toolbox.py', 'tools/toolbox_definitions.py',
    'tools/export_model_diagram.py', 'tools/package_release.py',
    'tests/test_contracts.py',
)


def package_release():
    missing = [name for name in FILES if not (ROOT/name).is_file()]
    if missing:
        raise FileNotFoundError('Distribution is missing: ' + ', '.join(missing))
    destination = ROOT/'dist/PR_Risks_SDSS.zip'
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.zip.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in FILES:
                archive.write(ROOT/name, name)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


if __name__ == '__main__':
    print(package_release())
