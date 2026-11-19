"""USDM acquisition and continuous drought-hazard processing workflows."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from utils.drought.usdm_catalog import plan_drought_download
from utils.drought.usdm_download import fetch_drought_data
from utils.drought.usdm_validation import validate_drought_download


def prepare_drought_states(*args, **kwargs):
    from utils.drought.usdm_spatial import prepare_drought_states as prepare
    return prepare(*args, **kwargs)


def calculate_drought_metrics(*args, **kwargs):
    from utils.drought.usdm_metrics import calculate_drought_metrics as calculate
    return calculate(*args, **kwargs)


def evaluate_drought_metrics(*args, **kwargs):
    from utils.drought.usdm_validation import evaluate_drought_metrics as evaluate
    return evaluate(*args, **kwargs)


def process_drought(validated_drought_data, grid_spec, output_folder, reuse_completed_cache=True):
    prepared = prepare_drought_states(validated_drought_data,grid_spec,output_folder,reuse_completed_cache)
    metrics = calculate_drought_metrics(prepared['workspace'])
    evaluated = evaluate_drought_metrics(metrics['catalog'])
    return dict(**prepared,**metrics,**evaluated)


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
    for name in ('prepare-states','process'):
        command = sub.add_parser(name)
        command.add_argument('--validated-drought-data',default='output/drought/reports/download_validation.json')
        command.add_argument('--grid-spec',default='output/shared/grid/grid_spec.json')
        command.add_argument('--output-folder',default='output/drought/data')
        command.add_argument('--refresh-spatial',action='store_false',dest='reuse_completed_cache')
    metrics = sub.add_parser('metrics')
    metrics.add_argument('--processing-workspace',default='output/drought/data/drought_processing.gdb')
    evaluate = sub.add_parser('evaluate')
    evaluate.add_argument('--metrics-catalog',default='output/drought/data/drought_processing.gdb/metric_catalog')
    return parser


def main(argv=None):
    options = vars(build_parser().parse_args(argv))
    command = options.pop('command')
    functions = {'plan':plan_drought_download,'fetch':fetch_drought_data,
                 'validate':validate_drought_download,'run':run_acquisition,
                 'prepare-states':prepare_drought_states,'metrics':calculate_drought_metrics,
                 'evaluate':evaluate_drought_metrics,'process':process_drought}
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
