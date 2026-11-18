"""ArcPy publication and evaluation for the four-storm HURRECON benchmark."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import time

import numpy as np

from . import wind
from .validation import validate_prototype, _raster_info, grid_errors
from ..shared.grid import _write_json, _sha256

NODATA = -9999.0
TRACK_FIELDS = [('SID', 'TEXT', 30), ('NAME', 'TEXT', 50), ('SEASON', 'LONG', None),
                ('OBS_TIME', 'DATE', None), ('LAT', 'DOUBLE', None), ('LON', 'DOUBLE', None),
                ('WIND_MPS', 'DOUBLE', None), ('NATURE', 'TEXT', 4), ('SOURCE_OID', 'LONG', None),
                ('USA_IFLAG', 'TEXT', 1), ('USA_AGENCY', 'TEXT', 40), ('USA_STATUS', 'TEXT', 8)]
for threshold in (34, 64):
    TRACK_FIELDS.extend((f'R{threshold}_{q}', 'DOUBLE', None) for q in ('NE', 'SE', 'SW', 'NW'))


def _table(arcpy, workspace, name, fields, rows):
    """Replace one workflow-owned table; publish normalized rows once."""
    path = str(Path(workspace) / name)
    if arcpy.Exists(path):
        arcpy.management.Delete(path)
    arcpy.management.CreateTable(str(workspace), name)
    arcpy.management.AddFields(path, [[n, t, '', length] for n, t, length in fields])
    with arcpy.da.InsertCursor(path, [f[0] for f in fields]) as cursor:
        for row in rows:
            cursor.insertRow(row)
    return path


def _settings(arcpy, workspace, document=None):
    path = str(Path(workspace) / 'wind_settings')
    if document is not None:
        _table(arcpy, workspace, 'wind_settings', [('SETTING', 'TEXT', 64), ('VALUE', 'TEXT', 32767)],
               [(key, json.dumps(value, allow_nan=False)) for key, value in document.items()])
        return document
    with arcpy.da.SearchCursor(path, ['SETTING', 'VALUE']) as cursor:
        return {key: json.loads(value) for key, value in cursor}


def _mark_report(settings, status, **details):
    path = Path(settings['validation_report'])
    report = json.loads(path.read_text(encoding='utf-8'))
    report['wind_benchmark'] = dict(status=status, workspace=settings['workspace'],
                                    input_fingerprint=settings['input_fingerprint'],
                                    updated_utc=datetime.now(timezone.utc).isoformat(), **details)
    _write_json(path, report)


def _coordinates(arcpy, workspace, grid):
    mask = arcpy.RasterToNumPyArray(grid['mask_raster'], nodata_to_value=-9999)
    if mask.shape != (grid['rows'], grid['columns']) or not np.isin(mask, [1, -9999]).all():
        raise ValueError('Study mask must contain land=1 and exterior NoData on the specified grid.')
    row, column = np.nonzero(mask == 1)
    points = np.empty(len(row), dtype=[('CELL_ID', '<i4'), ('X', '<f8'), ('Y', '<f8')])
    points['CELL_ID'] = np.arange(len(row))
    points['X'] = grid['extent']['xmin'] + (column + .5) * 250
    points['Y'] = grid['extent']['ymax'] - (row + .5) * 250
    # Project one batch rather than invoke projectAs for every cell/time step.
    with tempfile.TemporaryDirectory(prefix='sdss_wind_centers_') as temporary:
        scratch = str(Path(temporary) / 'coordinates.gdb')
        try:
            arcpy.management.CreateFileGDB(temporary, 'coordinates.gdb')
            source, target = str(Path(scratch) / 'projected'), str(Path(scratch) / 'geographic')
            arcpy.da.NumPyArrayToFeatureClass(points, source, ['X', 'Y'], arcpy.SpatialReference(32161))
            arcpy.management.Project(source, target, arcpy.SpatialReference(4326),
                                     grid['geographic_transformation'])
            coordinates = np.empty((len(row), 2))
            with arcpy.da.SearchCursor(target, ['CELL_ID', 'SHAPE@XY']) as cursor:
                for index, xy in cursor:
                    coordinates[index] = xy
        finally:
            arcpy.management.ClearWorkspaceCache()
    if not np.isfinite(coordinates).all():
        raise ValueError('Grid-center transformation produced invalid coordinates.')
    _table(arcpy, workspace, 'wind_cells', [('CELL_ID', 'LONG', None), ('GRID_ROW', 'LONG', None),
           ('GRID_COL', 'LONG', None), ('LAT', 'DOUBLE', None), ('LON', 'DOUBLE', None)],
           ((i, int(r), int(c), float(lat), float(lon))
            for i, (r, c, (lon, lat)) in enumerate(zip(row, column, coordinates))))
    return len(row)


def _track_rows(arcpy, workspace):
    tracks = {}
    with arcpy.da.SearchCursor(str(Path(workspace) / 'wind_tracks'), [f[0] for f in TRACK_FIELDS]) as cursor:
        for values in cursor:
            row = dict(zip([f[0] for f in TRACK_FIELDS], values))
            record = dict(time=row['OBS_TIME'].replace(tzinfo=timezone.utc), lat=row['LAT'],
                          lon=row['LON'], wind=row['WIND_MPS'], nature=row['NATURE'], source=row)
            tracks.setdefault(row['SID'], []).append(record)
    return tracks


def _digest_tracks(tracks):
    payload = [(sid, [(r['time'].isoformat(), r['lat'], r['lon'], r['wind'], r['nature'], r['source'])
                      for r in sorted(rows, key=lambda r: r['time'])]) for sid, rows in sorted(tracks.items())]
    return hashlib.sha256(json.dumps(payload, default=str, sort_keys=True, allow_nan=False).encode()).hexdigest()


def prepare_wind_inputs(validated_hurricane_data, grid_spec, output_folder,
                        benchmark_storms=None):
    """Revalidate prepared inputs and publish full native benchmark tracks."""
    import arcpy
    report_path = Path(validated_hurricane_data).resolve()
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if not report.get('passed'):
        raise ValueError('The preparation validation must pass before modeling winds.')
    if report_path.name != 'validation_report.json':
        raise ValueError('Use the existing validation_report.json returned by Validate Prototype.')
    grid_path = Path(grid_spec).resolve()
    if grid_path != Path(report['grid_spec']).resolve():
        raise ValueError('Grid Specification differs from the validated preparation handoff.')
    validate_prototype(report['prepare_manifest'], str(grid_path), str(report_path.parent))
    manifest_path = Path(report['prepare_manifest'])
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    inventory = json.loads(Path(manifest['inventory']).read_text(encoding='utf-8'))
    grid = json.loads(grid_path.read_text(encoding='utf-8'))
    if (grid['wkid'], grid['cell_size']) != (32161, 250):
        raise ValueError('Wind modeling requires the validated EPSG:32161 250 m grid.')
    selected = benchmark_storms or wind.BENCHMARK_STORMS
    if isinstance(selected, str):
        selected = [v.strip().strip("'\"") for v in selected.replace(',', ';').split(';') if v.strip()]
    selected = list(dict.fromkeys(selected))
    if not selected or set(selected) - set(wind.BENCHMARK_STORMS):
        raise ValueError('This benchmark supports Betsy 1956, Hugo 1989, Georges 1998 and Maria 2017.')
    output = Path(output_folder).resolve()
    if output.suffix.lower() == '.gdb':
        raise ValueError('Output Folder must be a directory containing hurricane_winds.gdb.')
    output.mkdir(parents=True, exist_ok=True)
    workspace = str(output / 'hurricane_winds.gdb')
    if not arcpy.Exists(workspace):
        arcpy.management.CreateFileGDB(str(output), 'hurricane_winds.gdb')
    settings = dict(workspace=workspace, validation_report=str(report_path), grid_spec=str(grid_path),
                    grid_sha256=_sha256(grid_path), preparation_manifest=manifest['manifest'],
                    preparation_sha256=_sha256(manifest_path), storm_ids=selected,
                    mode='BENCHMARK', statuses=['TS', 'SS'], units='m/s', native_radii_units='nautical miles',
                    friction_land=.8, asymmetry=1., earth_radius_km=wind.EARTH_KM,
                    equation_source=wind.SOURCE, created_utc=datetime.now(timezone.utc).isoformat(),
                    software_sha256={p.name: _sha256(p) for p in (Path(__file__), Path(wind.__file__))},
                    input_fingerprint='pending', stage='PREPARING')
    _settings(arcpy, workspace, settings)
    _mark_report(settings, 'PREPARING')
    names = ['SID', 'NAME', 'SEASON', 'OBS_TIME_UTC', 'USA_LAT', 'USA_LON', 'USA_WIND',
             'NATURE', 'SOURCE_OID', 'USA_IFLAG', 'USA_AGENCY', 'USA_STATUS']
    names += [f'USA_R{threshold}_{q}' for threshold in (34, 64) for q in ('NE', 'SE', 'SW', 'NW')]
    field_map = inventory['prepared_field_map']
    rows = []
    with arcpy.EnvManager(extent=None, mask=None):
        with arcpy.da.SearchCursor(manifest['observations'], [field_map.get(n, n) for n in names]) as cursor:
            for values in cursor:
                if values[0] in selected:
                    row = list(values)
                    row[6] = None if row[6] is None else row[6] * wind.KNOT_MPS
                    rows.append(row)
        _table(arcpy, workspace, 'wind_tracks', TRACK_FIELDS, rows)
        tracks = _track_rows(arcpy, workspace)
        if set(tracks) != set(selected):
            raise ValueError('One or more requested benchmark storms are absent from prepared observations.')
        for sid, records in tracks.items():
            try:
                wind.validate_track(records)
            except ValueError as error:
                raise ValueError(f'{sid}: {error}') from error
        settings['land_cells'] = _coordinates(arcpy, workspace, grid)
    settings['track_sha256'] = _digest_tracks(tracks)
    settings['cells_sha256'] = _digest_cells(_cells(arcpy, workspace))
    settings['input_fingerprint'] = hashlib.sha256(json.dumps({k: settings[k] for k in (
        'grid_sha256', 'preparation_sha256', 'track_sha256', 'cells_sha256', 'software_sha256')}, sort_keys=True).encode()).hexdigest()
    settings['stage'] = 'INPUTS_READY'
    _table(arcpy, workspace, 'wind_size_scenarios', [('RMW_KM', 'DOUBLE', None),
           ('PROFILE_B', 'DOUBLE', None)], wind.SIZE_SCENARIOS)
    _settings(arcpy, workspace, settings)
    _mark_report(settings, 'INPUTS_READY')
    arcpy.AddMessage(f'Prepared {len(tracks)} benchmark storms and {settings["land_cells"]:,} land cells.')
    return {'workspace': workspace}


def _cells(arcpy, workspace):
    with arcpy.da.SearchCursor(str(Path(workspace) / 'wind_cells'),
                              ['CELL_ID', 'GRID_ROW', 'GRID_COL', 'LAT', 'LON']) as cursor:
        cells = np.asarray(sorted(cursor, key=lambda r: r[0]), dtype=float)
    return cells[:, 1].astype(int), cells[:, 2].astype(int), cells[:, 3], cells[:, 4]


def _digest_cells(cells):
    return hashlib.sha256(np.asarray(cells, dtype='<f8').tobytes()).hexdigest()


def _check_cells(arcpy, workspace, grid, settings):
    cells = _cells(arcpy, workspace)
    if _digest_cells(cells) != settings['cells_sha256']:
        raise ValueError('Grid-center table changed; prepare wind inputs again.')
    mask = arcpy.RasterToNumPyArray(grid['mask_raster'], nodata_to_value=-9999)
    expected = np.zeros((grid['rows'], grid['columns']), dtype=bool)
    expected[cells[0], cells[1]] = True
    if (mask.shape != expected.shape or not np.isin(mask, [1, -9999]).all()
            or not np.array_equal(mask == 1, expected)):
        raise ValueError('Study mask changed; prepare wind inputs again.')
    return cells


def _raster(arcpy, values, name, workspace, grid, row, column):
    path = str(Path(workspace) / name)
    array = np.full((grid['rows'], grid['columns']), NODATA, dtype=np.float32)
    array[row, column] = values
    if not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError('A modeled peak is invalid; it cannot be published as zero exposure.')
    with arcpy.EnvManager(overwriteOutput=True, outputCoordinateSystem=arcpy.SpatialReference(32161),
                          extent=None, mask=None, snapRaster=grid['reference_raster'], cellSize=250):
        raster = arcpy.NumPyArrayToRaster(array, arcpy.Point(grid['extent']['xmin'], grid['extent']['ymin']),
                                         250, 250, NODATA)
        raster.save(path)
        del raster
        arcpy.management.DefineProjection(path, arcpy.SpatialReference(32161))
    return path


def estimate_wind_fields(workspace, size_scenarios=None):
    """Run the size/time benchmark; retain only the sixteen 5-minute peak fields."""
    import arcpy
    workspace = str(Path(workspace).resolve())
    settings = _settings(arcpy, workspace)
    if settings['stage'] not in {'INPUTS_READY', 'FIELDS_READY', 'EVALUATED', 'ESTIMATING'}:
        raise ValueError('Run Prepare Wind Inputs successfully first.')
    if _sha256(settings['grid_spec']) != settings['grid_sha256']:
        raise ValueError('The grid specification changed; prepare wind inputs again.')
    if any(_sha256(Path(__file__).with_name(name)) != checksum
           for name, checksum in settings['software_sha256'].items()):
        raise ValueError('Wind software changed; prepare inputs again to record the new version.')
    scenarios = size_scenarios or str(Path(workspace) / 'wind_size_scenarios')
    if isinstance(scenarios, (str, Path)) and arcpy.Exists(str(scenarios)):
        with arcpy.da.SearchCursor(str(scenarios), ['RMW_KM', 'PROFILE_B']) as cursor:
            scenarios = list(cursor)
    if isinstance(scenarios, str):
        scenarios = [tuple(map(float, row.split())) for row in scenarios.replace("'", '').split(';') if row.strip()]
    scenarios = [tuple(map(float, pair)) for pair in scenarios]
    if (len(set(scenarios)) != len(scenarios) or not scenarios
            or any(len(p) != 2 or not all(np.isfinite(p)) or min(p) <= 0 for p in scenarios)):
        raise ValueError('Scenarios require unique positive finite radius-km/profile-B pairs.')
    scenario_names = {pair: f'R{pair[0]:g}_B{pair[1]:g}'.replace('.', 'p') for pair in scenarios}
    if (len(set(scenario_names.values())) != len(scenarios)
            or any(not name.replace('_', '').isalnum() for name in scenario_names.values())):
        raise ValueError('Scenario values require distinct raster names at six significant digits; use ordinary positive decimal values.')
    tracks = _track_rows(arcpy, workspace)
    if _digest_tracks(tracks) != settings['track_sha256']:
        raise ValueError('Prepared wind tracks changed; prepare inputs again.')
    grid = json.loads(Path(settings['grid_spec']).read_text(encoding='utf-8'))
    row, column, lat, lon = _check_cells(arcpy, workspace, grid, settings)
    settings.update(stage='ESTIMATING', scenarios=scenarios)
    _settings(arcpy, workspace, settings)
    _mark_report(settings, 'ESTIMATING')
    # Invalidate a previous catalog before replacing any rasters.
    catalog_fields = [('SID', 'TEXT', 30), ('NAME', 'TEXT', 50), ('RMW_KM', 'DOUBLE', None),
                      ('PROFILE_B', 'DOUBLE', None), ('STEP_MIN', 'DOUBLE', None),
                      ('RASTER_NAME', 'TEXT', 100), ('INPUT_HASH', 'TEXT', 64)]
    _table(arcpy, workspace, 'wind_event_catalog', catalog_fields, [])
    convergence_fields = [('SID', 'TEXT', 30), ('RMW_KM', 'DOUBLE', None), ('PROFILE_B', 'DOUBLE', None),
                          ('COARSE_MIN', 'DOUBLE', None), ('FINE_MIN', 'DOUBLE', None),
                          ('P99_MPS', 'DOUBLE', None), ('MAX_MPS', 'DOUBLE', None),
                          ('DIFF34_PCT', 'DOUBLE', None), ('DIFF64_PCT', 'DOUBLE', None), ('PASSED', 'SHORT', None)]
    catalog, comparisons, timings, keep = [], [], [], set()
    start = time.perf_counter()
    for sid in settings['storm_ids']:
        records = tracks[sid]
        peaks = {}
        for step in (15., 5., 2.5):
            arcpy.AddMessage(f'{sid}: four size scenarios at {step:g}-minute intervals.')
            step_start = time.perf_counter()
            def progress(current, total):
                if arcpy.env.isCancelled:
                    raise RuntimeError('Wind benchmark cancelled; rerun estimation before evaluation.')
            peaks[step], stats = wind.peak_fields(wind.interpolate_track(records, step), lat, lon,
                                                  scenarios, progress)
            timings.append((sid, step, stats['samples'], stats['evaluated'],
                            time.perf_counter() - step_start))
        for j, (radius, profile) in enumerate(scenarios):
            for coarse, fine in ((15., 5.), (5., 2.5)):
                comparison = wind.convergence(peaks[coarse][j], peaks[fine][j])
                comparisons.append((sid, radius, profile, coarse, fine, comparison['p99_mps'],
                                    comparison['max_mps'], comparison['disagreement34_pct'],
                                    comparison['disagreement64_pct'], int(comparison['passed'])))
            name = f'W_{sid}_{scenario_names[(radius, profile)]}'
            _raster(arcpy, peaks[5.][j], name, workspace, grid, row, column)
            keep.add(name)
            catalog.append((sid, records[0]['source']['NAME'], radius, profile, 5., name,
                            settings['input_fingerprint']))
    # Remove only obsolete rasters owned by this benchmark, inside its own GDB.
    with arcpy.EnvManager(workspace=workspace):
        for name in arcpy.ListRasters('W_*') or []:
            if name not in keep:
                arcpy.management.Delete(str(Path(workspace) / name))
    _table(arcpy, workspace, 'wind_convergence', convergence_fields, comparisons)
    _table(arcpy, workspace, 'wind_timing', [('SID', 'TEXT', 30), ('STEP_MIN', 'DOUBLE', None),
           ('SAMPLES', 'LONG', None), ('EVALUATED', 'LONG', None), ('SECONDS', 'DOUBLE', None)], timings)
    catalog_path = _table(arcpy, workspace, 'wind_event_catalog', catalog_fields, catalog)
    settings.update(stage='FIELDS_READY', runtime_seconds=time.perf_counter() - start)
    _settings(arcpy, workspace, settings)
    _mark_report(settings, 'FIELDS_READY', catalog=catalog_path)
    return {'catalog': catalog_path}


def evaluate_wind_estimates(wind_catalog, reference_observations=None):
    """Inspect retained rasters and evaluate temporal/observational evidence."""
    import arcpy
    wind_catalog = str(Path(wind_catalog).resolve())
    workspace = str(Path(wind_catalog).parent)
    settings = _settings(arcpy, workspace)
    if settings['stage'] not in {'FIELDS_READY', 'EVALUATED'}:
        raise ValueError('Wind fields are incomplete. Run Estimate Wind Fields successfully first.')
    if _sha256(settings['grid_spec']) != settings['grid_sha256']:
        raise ValueError('Grid specification changed since estimation.')
    if any(_sha256(Path(__file__).with_name(name)) != checksum
           for name, checksum in settings['software_sha256'].items()):
        raise ValueError('Wind software changed; prepare and estimate again before evaluation.')
    _mark_report(settings, 'EVALUATING')
    grid = json.loads(Path(settings['grid_spec']).read_text(encoding='utf-8'))
    row, column, lat, lon = _check_cells(arcpy, workspace, grid, settings)
    tracks = _track_rows(arcpy, workspace)
    if _digest_tracks(tracks) != settings['track_sha256']:
        raise ValueError('Track data changed since estimation.')
    names = ['SID', 'RMW_KM', 'PROFILE_B', 'STEP_MIN', 'RASTER_NAME', 'INPUT_HASH']
    with arcpy.da.SearchCursor(str(wind_catalog), names) as cursor:
        catalog = list(cursor)
    expected = {(sid, float(r), float(b)) for sid in settings['storm_ids'] for r, b in settings['scenarios']}
    if len(catalog) != len(expected) or {(r[0], r[1], r[2]) for r in catalog} != expected:
        raise ValueError('Wind catalog does not contain exactly the requested storm/scenario combinations.')
    summaries = []
    for sid, radius, profile, step, name, fingerprint in catalog:
        if fingerprint != settings['input_fingerprint'] or step != 5:
            raise ValueError('Wind catalog contains a result from another input set.')
        if Path(name).name != name or not name.startswith('W_'):
            raise ValueError('Wind catalog raster names must refer to datasets inside the wind workspace.')
        path = str(Path(workspace) / name)
        info = _raster_info(arcpy, path)
        errors = grid_errors(info, info, grid['extent'], grid['rows'], grid['columns'])
        if errors:
            raise ValueError('; '.join(errors))
        array = arcpy.RasterToNumPyArray(path, nodata_to_value=NODATA)
        active = np.zeros(array.shape, dtype=bool)
        active[row, column] = True
        if not np.all(array[~active] == NODATA) or np.any(array[active] < 0) or not np.isfinite(array[active]).all():
            raise ValueError(f'{name}: invalid land values or exterior NoData.')
        values = array[row, column]
        summaries.append((sid, radius, profile, float(values.max()),
                          int(np.sum(values >= 34 * wind.KNOT_MPS)), int(np.sum(values >= 64 * wind.KNOT_MPS))))
    summary_path = _table(arcpy, workspace, 'wind_benchmark_summary', [
        ('SID', 'TEXT', 30), ('RMW_KM', 'DOUBLE', None), ('PROFILE_B', 'DOUBLE', None),
        ('MAX_MPS', 'DOUBLE', None), ('CELLS34', 'LONG', None), ('CELLS64', 'LONG', None)], summaries)
    radii_path = _evaluate_radii(arcpy, workspace, settings, tracks, lat, lon)
    station_count = _evaluate_stations(arcpy, workspace, settings, tracks, reference_observations)
    with arcpy.da.SearchCursor(str(Path(workspace) / 'wind_convergence'),
                              ['SID', 'RMW_KM', 'PROFILE_B', 'COARSE_MIN', 'FINE_MIN', 'PASSED']) as cursor:
        convergence_rows = list(cursor)
    expected_pairs = {(*key, coarse, fine) for key in expected for coarse, fine in ((15., 5.), (5., 2.5))}
    if (len(convergence_rows) != len(expected_pairs)
            or {tuple(r[:5]) for r in convergence_rows} != expected_pairs
            or any(r[5] not in (0, 1) for r in convergence_rows)):
        raise ValueError('Convergence table is incomplete or invalid; run Estimate Wind Fields again.')
    converged = all(bool(r[5]) for r in convergence_rows if r[3] == 5)
    settings.update(stage='EVALUATED', temporal_convergence_passed=converged)
    _settings(arcpy, workspace, settings)
    _mark_report(settings, 'EVALUATED', computational_checks_passed=True,
                 temporal_convergence_passed=converged, empirical_station_comparisons=station_count,
                 historical_configuration_selected=False, summary=summary_path,
                 catalog=str(wind_catalog), radii_comparison=radii_path,
                 runtime_seconds=settings['runtime_seconds'], units='m/s', mode='BENCHMARK',
                 limitations=['Constant size scenarios; land friction without terrain sheltering.',
                              'USA maximum wind treated as the HURRECON over-water input.',
                              'IBTrACS radii are a source-consistency comparison.',
                              'Review size scenarios before historical aggregation and ranking.'])
    if not converged:
        arcpy.AddWarning('Some 5-minute fields fail the proposed convergence tolerance; review finer sampling before historical use.')
    if station_count == 0:
        arcpy.AddWarning('Independent comparable station observations were unavailable; station skill remains unmeasured.')
    arcpy.AddMessage(f'Benchmark evaluated: {len(catalog)} peak fields, convergence={converged}. Review scenarios before historical processing.')
    return {'summary': summary_path, 'report': settings['validation_report']}


def _evaluate_radii(arcpy, workspace, settings, tracks, lat, lon):
    rows = []
    center_lat, center_lon = float(np.mean(lat)), float(np.mean(lon))
    land_radius = float(np.max(wind.range_bearing(center_lat, center_lon, lat, lon)[0]))
    for sid, records in tracks.items():
        samples = wind.interpolate_track(records, 5)
        eligible = [r for r in records if r['nature'] in {'TS', 'SS'}]
        for radius, profile in settings['scenarios']:
            for threshold in (34, 64):
                differences, original, filled = [], 0, 0
                for record in eligible:
                    distance = float(wind.range_bearing(center_lat, center_lon, record['lat'], record['lon'])[0])
                    if distance > land_radius + 500:
                        continue
                    seconds = record['time'].timestamp()
                    speed = float(np.interp(seconds, samples['time'], samples['speed']))
                    heading = float(np.degrees(np.interp(seconds, samples['time'],
                                                        np.unwrap(np.radians(samples['heading'])))) % 360)
                    for quadrant in ('NE', 'SE', 'SW', 'NW'):
                        observed = record['source'][f'R{threshold}_{quadrant}']
                        if observed is None or observed <= 0:
                            continue
                        estimate = wind.quadrant_radius(record['wind'], speed, heading,
                                                        radius, profile, threshold, quadrant)
                        differences.append(estimate - observed * 1.852)
                        if record['source']['USA_IFLAG'] in {'O', 'V'}:
                            original += 1
                        else:
                            filled += 1
                rows.append((sid, radius, profile, threshold, len(differences), original, filled,
                             float(np.mean(differences)) if differences else None,
                             float(np.mean(np.abs(differences))) if differences else None))
    return _table(arcpy, workspace, 'wind_radii_comparison', [('SID', 'TEXT', 30),
        ('RMW_KM', 'DOUBLE', None), ('PROFILE_B', 'DOUBLE', None), ('THRESHOLD_KT', 'LONG', None),
        ('N', 'LONG', None), ('ORIGINAL', 'LONG', None), ('FILLED', 'LONG', None),
        ('BIAS_KM', 'DOUBLE', None), ('MAE_KM', 'DOUBLE', None)], rows)


def _evaluate_stations(arcpy, workspace, settings, tracks, reference_observations):
    rows = []
    settings.pop('station_reference', None)
    if reference_observations:
        fields = ['SID', 'STATION', 'LAT', 'LON', 'WIND_MPS', 'AVG_SECONDS', 'HEIGHT_M',
                  'COVER', 'START_UTC', 'END_UTC', 'SOURCE', 'LOWER_BOUND']
        with arcpy.da.SearchCursor(str(reference_observations), fields) as cursor:
            observations = list(cursor)
        for sid, station, lat, lon, observed, average, height, cover, start, end, source, lower in observations:
            measurements = (lat, lon, observed, average, height)
            if (any(v is None for v in measurements) or not np.isfinite(measurements).all()
                    or not (-90 <= lat <= 90 and -180 <= lon <= 180)
                    or sid not in tracks or not station or not source or average != 60
                    or abs(height - 10) > .5 or cover not in {'LAND', 'WATER'} or lower != 0
                    or observed < 0):
                raise ValueError('Reference rows require a benchmark SID, source, 60-second/10-m winds, known cover and complete observations.')
            if isinstance(start, str):
                start = datetime.fromisoformat(start.replace('Z', '+00:00'))
            if isinstance(end, str):
                end = datetime.fromisoformat(end.replace('Z', '+00:00'))
            if not isinstance(start, datetime) or not isinstance(end, datetime):
                raise ValueError('Station observations require valid UTC start/end dates.')
            start = start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start.astimezone(timezone.utc)
            end = end.replace(tzinfo=timezone.utc) if end.tzinfo is None else end.astimezone(timezone.utc)
            if end <= start:
                raise ValueError('Station observation end must be after start.')
            samples = wind.interpolate_track(tracks[sid], 2.5, window=(start.timestamp(), end.timestamp()))
            distance, bearing = wind.range_bearing(samples['lat'], samples['lon'], lat, lon)
            for radius, profile in settings['scenarios']:
                modeled = wind.wind_speed(distance, bearing, samples['lat'],
                    samples['heading'], samples['speed'], samples['wind'],
                    radius, profile, friction=.8 if cover == 'LAND' else 1)
                peak = float(modeled.max())
                rows.append((sid, station, radius, profile, observed, peak, peak - observed,
                             lat, lon, average, height, cover,
                             start.replace(tzinfo=None), end.replace(tzinfo=None), source))
        settings['station_reference'] = str(Path(reference_observations).resolve())
    _table(arcpy, workspace, 'wind_station_comparison', [('SID', 'TEXT', 30), ('STATION', 'TEXT', 100),
        ('RMW_KM', 'DOUBLE', None), ('PROFILE_B', 'DOUBLE', None), ('OBS_MPS', 'DOUBLE', None),
        ('MODEL_MPS', 'DOUBLE', None), ('ERROR_MPS', 'DOUBLE', None),
        ('LAT', 'DOUBLE', None), ('LON', 'DOUBLE', None), ('AVG_SECONDS', 'DOUBLE', None),
        ('HEIGHT_M', 'DOUBLE', None), ('COVER', 'TEXT', 8), ('START_UTC', 'DATE', None),
        ('END_UTC', 'DATE', None), ('SOURCE', 'TEXT', 2000)], rows)
    return len(rows)
