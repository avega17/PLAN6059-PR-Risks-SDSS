"""Auditable Hurricane Winds preparation, shared grid, and validation entry points.

Run with ArcGIS Pro's Python, not a general-purpose Python installation.
No wind surface or hazard ranking is estimated by this prototype.
"""
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
    return parser


def main(argv=None):
    options = vars(build_parser().parse_args(argv))
    command = options.pop('command')
    functions = {'prepare': prepare_hurricane_data, 'grid': establish_reference_grid,
                 'validate': validate_prototype, 'run': run_prototype}
    try:
        result = functions[command](**options)
    except Exception as error:
        print(f'{type(error).__name__}: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
