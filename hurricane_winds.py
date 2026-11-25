"""Hurricane observations, HURRECON wind fields and hazard maps."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def prepare_hurricane_data(*args, **kwargs):
    from utils.hurricane.ibtracs import prepare_hurricane_data as prepare
    return prepare(*args, **kwargs)


def establish_reference_grid(*args, **kwargs):
    from utils.shared.grid import establish_reference_grid as establish
    return establish(*args, **kwargs)


def validate_prototype(*args, **kwargs):
    from utils.hurricane.validation import validate_prototype as validate
    return validate(*args, **kwargs)


def prepare_wind_inputs(*args, **kwargs):
    from utils.hurricane.wind_workflow import prepare_wind_inputs as prepare
    return prepare(*args, **kwargs)


def estimate_wind_fields(*args, **kwargs):
    from utils.hurricane.wind_workflow import estimate_wind_fields as estimate
    return estimate(*args, **kwargs)


def evaluate_wind_estimates(*args, **kwargs):
    from utils.hurricane.wind_workflow import evaluate_wind_estimates as evaluate
    return evaluate(*args, **kwargs)


def run_wind_benchmark(validated_hurricane_data, grid_spec, output_folder,
                       benchmark_storms=None, size_scenarios=None, reference_observations=None):
    from utils.hurricane.wind import BENCHMARK_STORMS
    return run_wind_history(validated_hurricane_data, grid_spec, output_folder,
                            benchmark_storms or BENCHMARK_STORMS, size_scenarios, reference_observations)


def run_wind_history(validated_hurricane_data, grid_spec, output_folder,
                     benchmark_storms=None, size_scenarios=None, reference_observations=None):
    inputs = prepare_wind_inputs(validated_hurricane_data, grid_spec, output_folder, benchmark_storms)
    fields = estimate_wind_fields(inputs['workspace'], size_scenarios)
    result = evaluate_wind_estimates(fields['catalog'], reference_observations)
    return dict(**inputs, **fields, **result)


def classify_wind(*args, **kwargs):
    from utils.shared.hazard_rank import classify_wind as classify
    return classify(*args, **kwargs)


def combine_ranks(*args, **kwargs):
    from utils.shared.hazard_rank import combine_ranks as combine
    return combine(*args, **kwargs)


def create_layouts(*args, **kwargs):
    from utils.shared.layouts import create_layouts as create
    return create(*args, **kwargs)


def run_prototype(raw_points, output_folder, start_season=1955, end_season=2025,
                  raw_lines=None, spc_reports=None, boundary=None, grid_folder=None, export_csv=False):
    """Run the same three callable stages that are exposed in ModelBuilder."""
    root = Path(output_folder).expanduser().resolve()
    prepared = prepare_hurricane_data(
        raw_points, root / 'data', start_season, end_season, raw_lines, spc_reports, export_csv)
    grid = establish_reference_grid(grid_folder or Path(__file__).resolve().parent / 'output/shared/grid', boundary=boundary)
    validation = validate_prototype(
        prepared['manifest'], grid['grid_spec_path'], root / 'reports')
    return {'prepare_manifest': prepared['manifest'],
            'grid_spec': grid['grid_spec_path'], 'validation': validation}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'run'):
        cmd = sub.add_parser(name, help='Prepare observations' if name == 'prepare'
                             else 'Run preparation, grid creation, and validation')
        cmd.add_argument('--raw-points', required=True)
        cmd.add_argument('--output-folder', default='output/hurricane' if name == 'run' else 'output/hurricane/data')
        cmd.add_argument('--export-csv', action='store_true')
        cmd.add_argument('--start-season', type=int, default=1955)
        cmd.add_argument('--end-season', type=int, default=2025)
        cmd.add_argument('--raw-lines')
        cmd.add_argument('--spc-reports')
        if name == 'run':
            cmd.add_argument('--boundary')
            cmd.add_argument('--grid-folder', default='output/shared/grid')
    grid = sub.add_parser('grid', help='Create the provisional 250 m reference grid')
    grid.add_argument('--output-folder', default='output/shared/grid')
    grid.add_argument('--boundary')
    validation = sub.add_parser('validate', help='Verify actual preparation and grid outputs')
    validation.add_argument('--prepare-manifest', required=True)
    validation.add_argument('--grid-spec', required=True)
    validation.add_argument('--output-folder', default='output/hurricane/reports')
    for name in ('wind-prepare', 'wind-history', 'wind-benchmark'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--validated-hurricane-data', default='output/hurricane/reports/validation_report.json')
        cmd.add_argument('--grid-spec', default='output/shared/grid/grid_spec.json')
        cmd.add_argument('--output-folder', default='output/hurricane/data')
        if name == 'wind-benchmark':
            cmd.add_argument('--benchmark-storms', help='Semicolon-separated SIDs for a diagnostic run')
            cmd.add_argument('--size-scenarios', help='Table with RMW_KM/PROFILE_B, or quoted radius/B pairs')
        if name != 'wind-prepare':
            cmd.add_argument('--reference-observations')
    estimate = sub.add_parser('wind-estimate', help='Estimate historical wind fields')
    estimate.add_argument('--workspace', default='output/hurricane/data/hurricane_winds.gdb')
    estimate.add_argument('--size-scenarios')
    evaluate = sub.add_parser('wind-evaluate', help='Evaluate published benchmark fields')
    evaluate.add_argument('--wind-catalog', default='output/hurricane/data/hurricane_winds.gdb/wind_event_catalog')
    evaluate.add_argument('--reference-observations')
    classify = sub.add_parser('classify', help='Publish hurricane scores and 1/3/5 classes')
    classify.add_argument('--validated-data', default='output/hurricane/reports/validation_report.json')
    classify.add_argument('--grid-spec', default='output/shared/grid/grid_spec.json')
    classify.add_argument('--output-folder', default='output/hurricane/data')
    combine = sub.add_parser('combine', help='Verify and add the two course ranks')
    combine.add_argument('--wind-rank', default='output/hurricane/data/RiskHurricaneWinds_rank250.tif')
    combine.add_argument('--drought-rank', default='output/drought/data/RiskDrought_rank250.tif')
    combine.add_argument('--grid-spec', default='output/shared/grid/grid_spec.json')
    combine.add_argument('--output-folder', default='output/shared/grid')
    layouts = sub.add_parser('layouts', help='Save the three final map layouts in ArcGIS Pro')
    layouts.add_argument('--project', default='output/arcgis/project/SDSS_PR_Hazard_Risks.aprx')
    layouts.add_argument('--wind-rank', default='output/hurricane/data/RiskHurricaneWinds_rank250.tif')
    layouts.add_argument('--drought-rank', default='output/drought/data/RiskDrought_rank250.tif')
    layouts.add_argument('--combined', default='output/shared/grid/Combined_sum250.tif')
    layouts.add_argument('--grid-spec', default='output/shared/grid/grid_spec.json')
    layouts.add_argument('--wind-report')
    layouts.add_argument('--drought-report')
    layouts.add_argument('--pdf', help='Optional three-page map export')
    return parser


def main(argv=None):
    options = vars(build_parser().parse_args(argv))
    command = options.pop('command')
    functions = {'prepare': prepare_hurricane_data, 'grid': establish_reference_grid,
                 'validate': validate_prototype, 'run': run_prototype,
                 'wind-prepare': prepare_wind_inputs, 'wind-estimate': estimate_wind_fields,
                 'wind-evaluate': evaluate_wind_estimates, 'wind-benchmark': run_wind_benchmark,
                 'wind-history': run_wind_history, 'classify': classify_wind, 'combine': combine_ranks,
                 'layouts': create_layouts}
    try:
        result = functions[command](**options)
    except Exception as error:
        print(f'{type(error).__name__}: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
