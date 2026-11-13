"""USDM plan/fetch/validate workflow; no spatial drought indicator is inferred."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from utils.drought.usdm_catalog import plan_drought_download
from utils.drought.usdm_download import fetch_drought_data
from utils.drought.usdm_validation import validate_drought_download


def run_acquisition(start_date, end_date, output_folder, local_archive_folder=None,
                    include_municipio_statistics=True, recovery_buffer_weeks=3,
                    mode='Baseline', publish_tables=False, resume=True, offline=False, export_csv=False):
    root = Path(output_folder).expanduser().resolve()
    plan = plan_drought_download(start_date,end_date,root/'plan',local_archive_folder,
        include_municipio_statistics,recovery_buffer_weeks,mode,publish_tables)
    acquired = fetch_drought_data(plan['plan'],root/'cache',root/'data',resume,
        publish_tables,progress=lambda value:print(value,file=sys.stderr,flush=True),offline=offline,export_csv=export_csv)
    report = validate_drought_download(acquired['manifest'],root/'reports')
    return {'plan':plan['plan'],'download_manifest':acquired['manifest'],
            'report':report['report'],'passed':report['passed']}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    for name in ('plan','run'):
        command = sub.add_parser(name)
        command.add_argument('--start-date',default='2000-01-01')
        command.add_argument('--end-date',default='2025-12-31')
        command.add_argument('--output-folder',default='output/drought' if name=='run' else 'output/drought/plan')
        command.add_argument('--local-archive-folder')
        command.add_argument('--no-municipios',action='store_false',dest='include_municipio_statistics')
        command.add_argument('--recovery-buffer-weeks',type=int,default=3)
        command.add_argument('--mode',choices=('Baseline','Pilot'),default='Baseline')
        command.add_argument('--arcpy-tables',action='store_true',dest='publish_tables')
        if name=='run':
            command.add_argument('--refresh',action='store_false',dest='resume')
            command.add_argument('--offline',action='store_true')
            command.add_argument('--export-csv',action='store_true')
    fetch = sub.add_parser('fetch')
    fetch.add_argument('--download-plan',required=True)
    fetch.add_argument('--cache-folder',default='output/drought/cache')
    fetch.add_argument('--output-folder',default='output/drought/data')
    fetch.add_argument('--refresh',action='store_false',dest='resume')
    fetch.add_argument('--offline',action='store_true')
    fetch.add_argument('--export-csv',action='store_true')
    fetch.add_argument('--arcpy-tables',action='store_true',dest='publish_tables')
    validate = sub.add_parser('validate')
    validate.add_argument('--download-manifest',required=True)
    validate.add_argument('--output-folder',default='output/drought/reports')
    return parser


def main(argv=None):
    options = vars(build_parser().parse_args(argv))
    command = options.pop('command')
    functions = {'plan':plan_drought_download,'fetch':fetch_drought_data,
                 'validate':validate_drought_download,'run':run_acquisition}
    if command=='fetch':
        options['progress'] = lambda value:print(value,file=sys.stderr,flush=True)
    try:
        result = functions[command](**options)
    except Exception as error:
        print(f'{type(error).__name__}: {error}',file=sys.stderr)
        return 1
    print(json.dumps(result,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
