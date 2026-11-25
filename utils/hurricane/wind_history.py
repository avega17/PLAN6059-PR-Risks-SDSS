"""Full-catalog hurricane wind exposure on the shared Puerto Rico grid."""
from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path

import numpy as np

from . import wind
from .wind_workflow import (_cells, _check_cells, _digest_tracks, _mark_report, _settings,
                            _table, _track_rows)
from ..shared.grid import _sha256

START, END = 1955, 2025
REFERENCES = tuple(range(1986, 2027, 5))
THRESHOLDS = {'H34': 34 * wind.KNOT_MPS, 'H64': 64 * wind.KNOT_MPS,
              'F0_proxy': 18., 'F1_proxy': 26., 'F2_proxy': 36., 'F3_proxy': 48.}
ELIGIBLE_PHASES = {'TS', 'SS'}


def reference_windows():
    return [(f'{series}_{year}', START if series == 'all' else year-30, year)
            for year in REFERENCES for series in ('all', 'rolling')]


def _new_year(year):
    return datetime(year, 1, 1, tzinfo=timezone.utc).timestamp()


def motion(times, lat, lon):
    distance, heading = wind.range_bearing(lat[:-1], lon[:-1], lat[1:], lon[1:])
    return ((times[:-1] + times[1:])/2, distance*1000/np.diff(times),
            np.unwrap(np.radians(heading)))


def native_arrays(records):
    track = sorted(records, key=lambda record: record['time'])
    times = np.array([r['time'].timestamp() for r in track])
    lat = np.array([r['lat'] for r in track], dtype=float)
    lon = np.degrees(np.unwrap(np.radians([r['lon'] for r in track])))
    maximum = np.array([r['wind'] if r['wind'] is not None else np.nan for r in track])
    if (np.any(np.diff(times) <= 0) or not np.isfinite(lat).all()
            or not np.isfinite(lon).all() or np.any(np.abs(lat) > 90)
            or np.any(maximum[np.isfinite(maximum)] < 0)):
        raise ValueError('Track has invalid coordinates, time sequence or wind.')
    return track, times, lat, lon, maximum


def interval_indices(track):
    eligible = np.array([r['nature'] in ELIGIBLE_PHASES for r in track])
    intervals = np.flatnonzero(eligible[:-1] & eligible[1:])
    isolated = eligible.copy()
    isolated[intervals] = False
    isolated[intervals + 1] = False
    return intervals, np.flatnonzero(isolated)


def radial_bound(distance, profiles, minimum):
    distance = np.atleast_1d(distance)
    combined = []
    for radius, profile in profiles:
        q = (radius / np.maximum(radius, distance)) ** profile
        combined.append(np.sqrt(q * np.exp(1-q)))
    return np.max(np.asarray(combined) / np.broadcast_to(minimum, (len(profiles),))[:, None], axis=0)


def yearly_samples(records, center, land_radius, profiles, minimum, step=5, friction=.8):
    """Bound unsupported intervals separately; split wind samples at UTC year boundaries."""
    track, times, lat, lon, maximum = native_arrays(records)
    intervals, isolated = interval_indices(track)
    if len(times) == 0 or not (len(intervals) or len(isolated)):
        return {}, set(), 0
    if len(times) > 1:
        mid, speed, heading = motion(times, lat, lon)
    else:
        mid, speed, heading = times, [0.], [0.]
    by_year = defaultdict(list)
    unresolved = set()
    bounded = 0
    center_distance = wind.range_bearing(*center, lat, lon)[0]
    # Manhattan angular travel is an upper bound on the length of the
    # interpolated latitude/longitude path, including at the antimeridian.
    travel = wind.EARTH_KM * np.radians(np.abs(np.diff(lat)) + np.abs(np.diff(lon)))
    distance_bound = np.maximum(0., center_distance[:-1] - travel - land_radius)
    radial = radial_bound(distance_bound, profiles, minimum)
    isolated_radial = radial_bound(np.maximum(0, center_distance[isolated]-land_radius), profiles, minimum)
    upper = maximum.copy()
    for index, record in enumerate(track):
        if np.isnan(upper[index]) and record['source']['USA_STATUS'] == 'TD':
            upper[index] = 33 * wind.KNOT_MPS
    for index in intervals:
        start, finish = times[index:index+2]
        first, last = track[index]['time'].year, track[index+1]['time'].year
        peak_bound = friction * np.max(upper[index:index+2]) * radial[index]
        if finish-start <= 21600 and peak_bound + 1e-10 < 1:
            bounded += 1
            continue
        for year in range(max(first, START), min(last, END)+1):
            begin = max(start, _new_year(year))
            end = min(finish, np.nextafter(_new_year(year+1), -np.inf))
            if begin > end:
                continue
            if finish-start > 21600 or not np.isfinite(maximum[index:index+2]).all():
                unresolved.add(year)
                continue
            sample = np.linspace(begin, end, max(1, math.ceil((end-begin)/(60*step)))+1)
            fraction = (sample-start)/(finish-start)
            coords = [v[index] + fraction*(v[index+1]-v[index]) for v in (lat, lon, maximum)]
            by_year[year].append(np.array([sample, *coords]))
    for index, reach in zip(isolated, isolated_radial):
        year = track[index]['time'].year
        if START <= year <= END:
            if friction * upper[index] * reach + 1e-10 < 1:
                bounded += 1
            elif not np.isfinite(maximum[index]) or len(times) == 1:
                unresolved.add(year)
            else:
                by_year[year].append(np.array([[times[index]], [lat[index]], [lon[index]], [maximum[index]]]))
    samples = {}
    for year, pieces in by_year.items():
        values = np.concatenate(pieces, axis=1)
        _, indices = np.unique(values[0], return_index=True)
        timestamp, latitude, longitude, speeds = values[:, indices]
        samples[year] = dict(time=timestamp, lat=latitude, lon=longitude, wind=speeds,
                             speed=np.interp(timestamp, mid, speed),
                             heading=np.degrees(np.interp(timestamp, mid, heading)) % 360)
    return samples, unresolved, bounded


def _profile_errors(tracks, profiles, center, land_radius):
    scores = []
    for sid, records in sorted(tracks.items()):
        track, times, lat, lon, maximum = native_arrays(records)
        if len(track) < 2:
            continue
        mid, speed, heading = motion(times, lat, lon)
        near = wind.range_bearing(*center, lat, lon)[0] <= land_radius + 500
        observed = []
        for i in np.flatnonzero(near & np.isfinite(maximum)):
            source = track[i]['source']
            if track[i]['nature'] not in ELIGIBLE_PHASES or source['USA_IFLAG'] not in {'O', 'V'}:
                continue
            for threshold in (34, 64):
                for quadrant in ('NE', 'SE', 'SW', 'NW'):
                    radius = source[f'R{threshold}_{quadrant}']
                    if radius and radius > 0:
                        observed.append((i, threshold, quadrant, radius*1.852))
        if observed:
            translation = np.interp(times, mid, speed)
            bearing = np.degrees(np.interp(times, mid, heading)) % 360
            errors = [[abs(wind.quadrant_radius(maximum[i], translation[i], bearing[i], *profile,
                                               threshold, quadrant)-radius)
                       for i, threshold, quadrant, radius in observed] for profile in profiles]
            scores.append((sid, len(observed), *map(float, np.mean(errors, axis=1))))
    if len(scores) < 2:
        raise ValueError('Profile selection needs positive original radii from at least two storms.')
    errors = np.array([row[2:] for row in scores])
    choice = int(errors.mean(axis=0).argmin())
    leave_out = np.argmin(errors.sum(axis=0)-errors, axis=1)
    return choice, scores, errors.mean(axis=0).tolist(), int(np.count_nonzero(leave_out != choice))


def _raster_digest(arcpy, workspace, names):
    import hashlib
    digest = hashlib.sha256()
    for name in sorted(names):
        digest.update(name.encode())
        digest.update(arcpy.RasterToNumPyArray(str(Path(workspace)/name),
                                             nodata_to_value=-9999).tobytes())
    return digest.hexdigest()


def _model_storm(task, *, center, land_radius, profiles, choice, latitude, longitude):
    index, (sid, track) = task
    minimum = np.full(len(profiles), THRESHOLDS['H64'])
    minimum[choice] = min(THRESHOLDS.values())
    samples, unresolved, bounded = yearly_samples(track, center, land_radius, profiles, minimum)
    yearly = {year: wind.peak_fields(values, latitude, longitude, profiles, minimum_mps=minimum)[0]
              for year, values in samples.items()}
    # Wind speed is linear in the land factor. Re-check the candidate cutoff
    # for a factor of one, without retaining a second set of peak rasters.
    water, water_unresolved, _ = yearly_samples(track, center, land_radius, (profiles[choice],),
                                                THRESHOLDS['H64'], friction=1)
    water_peaks = [wind.peak_fields(values, latitude, longitude, (profiles[choice],),
                   minimum_mps=THRESHOLDS['H64'], friction=1)[0][0] for values in water.values()]
    water_hit = np.maximum.reduce(water_peaks) >= THRESHOLDS['H64'] if water_peaks else None
    disagreement = None
    if yearly:
        peak = np.maximum.reduce(list(yearly.values()))
        if sid in wind.BENCHMARK_STORMS or (index % 7 == 0 and np.any(peak >= THRESHOLDS['H64'])):
            fine, _, _ = yearly_samples(track, center, land_radius, profiles, minimum, step=2.5)
            fine_peak = np.maximum.reduce([wind.peak_fields(values, latitude, longitude, profiles,
                                           minimum_mps=minimum)[0] for values in fine.values()])
            agreement = [np.mean((peak[choice] >= t) != (fine_peak[choice] >= t)) for t in THRESHOLDS.values()]
            agreement.append(np.mean((peak >= THRESHOLDS['H64']) != (fine_peak >= THRESHOLDS['H64'])))
            disagreement = float(max(agreement))*100
    return sid, len(track), yearly, unresolved, bounded, water_hit, water_unresolved, disagreement


def _storm_results(tracks, cancelled, **parameters):
    """Keep a bounded number of NumPy results in memory; ArcPy stays on the caller thread."""
    from functools import partial
    tasks = list(enumerate(sorted(tracks.items()), 1))
    count = min(4, os.cpu_count() or 1)
    model = partial(_model_storm, **parameters)
    with ThreadPoolExecutor(max_workers=count) as workers:
        for start in range(0, len(tasks), 2*count):
            if cancelled():
                raise RuntimeError('Historical wind estimation cancelled.')
            yield from workers.map(model, tasks[start:start+2*count])


def estimate_history(workspace, size_scenarios=None):
    import arcpy
    from ..shared.hazard_rank import island_domain, write_raster
    workspace = str(Path(workspace).resolve())
    settings = _settings(arcpy, workspace)
    try:
        if size_scenarios:
            raise ValueError('Historical processing compares the four published size profiles. Leave Size Scenarios blank.')
        profiles = wind.SIZE_SCENARIOS
        if _sha256(settings['grid_spec']) != settings['grid_sha256']:
            raise ValueError('Grid changed. Prepare wind inputs again.')
        grid = json.loads(Path(settings['grid_spec']).read_text(encoding='utf-8'))
        row, col, latitude, longitude = _check_cells(arcpy, workspace, grid, settings)
        inside = island_domain(arcpy, grid)[row, col]
        row, col, latitude, longitude = (values[inside] for values in (row, col, latitude, longitude))
        tracks = _track_rows(arcpy, workspace)
        if _digest_tracks(tracks) != settings['track_sha256'] or sorted(tracks) != settings['storm_ids']:
            raise ValueError('Prepared wind tracks changed. Prepare wind inputs again.')
        settings.update(stage='ESTIMATING')
        _settings(arcpy, workspace, settings)
        _mark_report(settings, 'ESTIMATING')
        center = tuple(map(float, (latitude.mean(), longitude.mean())))
        land_radius = float(wind.range_bearing(*center, latitude, longitude)[0].max()) + 1e-6
        choice, scores, errors, switches = _profile_errors(tracks, profiles, center, land_radius)
        arcpy.AddMessage(f'Selected common wind profile {profiles[choice]} from {len(scores)} storms.')
        size = len(row)
        windows = reference_windows()
        counts = np.zeros((len(windows), size), dtype=np.int16)
        totals = {name: np.zeros(size, dtype=np.int16) for name in THRESHOLDS}
        alternate = np.zeros((len(profiles), size), dtype=np.int16)
        no_land_reduction = np.zeros(size, dtype=np.int16)
        annual = np.zeros((END-START+1, size), dtype=bool)
        last = np.zeros(size, dtype=np.int16)
        missing, ledger, convergence = set(), [], []
        results = _storm_results(tracks, lambda: arcpy.env.isCancelled, center=center,
                                 land_radius=land_radius, profiles=profiles, choice=choice,
                                 latitude=latitude, longitude=longitude)
        for index, result in enumerate(results, 1):
            sid, observations, yearly, unresolved, bounded, water_hit, water_unresolved, disagreement = result
            missing.update(unresolved)
            if water_hit is not None:
                no_land_reduction += water_hit
            if disagreement is not None:
                convergence.append((sid, disagreement))
            ledger.append((sid, observations, len(yearly), bounded, ','.join(map(str, sorted(unresolved))),
                           ','.join(map(str, sorted(water_unresolved))),
                           'MODELED' if yearly else 'UNRESOLVED' if unresolved else 'BELOW_OR_OUTSIDE_PHASE'))
            if yearly:
                peak = np.maximum.reduce(list(yearly.values()))
                alternate += peak >= THRESHOLDS['H64']
                for name, threshold in THRESHOLDS.items():
                    totals[name] += peak[choice] >= threshold
                for year, values in yearly.items():
                    affected = values[choice] >= THRESHOLDS['H64']
                    annual[year-START] |= affected
                    np.maximum(last, np.where(affected, year, 0), out=last, casting='unsafe')
                for number, (_, start, end) in enumerate(windows):
                    selected = [values[choice] for year, values in yearly.items() if start <= year < end]
                    if selected:
                        counts[number] += np.maximum.reduce(selected) >= THRESHOLDS['H64']
            if index % 100 == 0:
                arcpy.AddMessage(f'Checked {index:,}/{len(tracks):,} storms.')
        water_missing = {int(year) for record in ledger for year in record[5].split(',') if year}
        products = []

        def publish(name, values, years=(), unknown=missing, integer=True):
            raster = np.full((grid['rows'], grid['columns']), np.nan)
            if not set(years).intersection(unknown):
                raster[row, col] = values
            write_raster(workspace, name, raster, grid, integer=integer)
            products.append(name)

        for i, (name, start, end) in enumerate(windows):
            publish(f'N64_{name}', counts[i], range(start, end))
        for name, values in totals.items():
            if name != 'H64':
                publish(name, values/(END-START+1), range(START, END+1), integer=False)
        for i, values in enumerate(alternate, 1):
            publish(f'N64_profile_{i}', values, range(START, END+1))
        publish('N64_land_factor_1', no_land_reduction, range(START, END+1), unknown=water_missing)
        publish('H64_affected_years', annual.sum(axis=0), range(START, END+1))
        publish('H64_last_year', np.where(last > 0, last, np.nan), range(START, END+1))
        publish('H64_years_since', np.where(last > 0, END+1-last, np.nan), range(START, END+1))
        catalog = _table(arcpy, workspace, 'wind_event_catalog', [('SID','TEXT',30), ('OBS','LONG',None),
                         ('MODELED_YEARS','SHORT',None), ('BOUNDED_PARTS','LONG',None),
                         ('UNRESOLVED','TEXT',400), ('LAND_FACTOR_1_UNRESOLVED','TEXT',400),
                         ('DISPOSITION','TEXT',32)], ledger)
        _table(arcpy, workspace, 'wind_profile_comparison', [('SID','TEXT',30), ('RADII','LONG',None),
               *((f'MAE_{i}_KM','DOUBLE',None) for i in range(1,len(profiles)+1))], scores)
        _table(arcpy, workspace, 'wind_time_step_comparison', [('SID','TEXT',30),
               ('MAX_DISAGREEMENT_PCT','DOUBLE',None)], convergence)
        settings.update(stage='HISTORY_READY', chosen_profile=choice, profiles=profiles, windows=windows,
                        profile_errors_km=errors, profile_storm_count=len(scores), leave_one_out_switches=switches,
                        unresolved_years=sorted(missing), products=products,
                        products_sha256=_raster_digest(arcpy, workspace, products))
        _settings(arcpy, workspace, settings)
        _mark_report(settings, 'HISTORY_READY', unresolved_years=sorted(missing), storm_count=len(ledger))
        return {'catalog': catalog}
    except Exception as error:
        _mark_report(settings, 'FAILED', error=str(error))
        raise


def evaluate_history(catalog, reference_observations=None):
    import arcpy
    from .validation import _raster_info, grid_errors
    from ..shared.hazard_rank import island_domain
    workspace = str(Path(catalog).resolve().parent)
    settings = _settings(arcpy, workspace)
    try:
        if settings['stage'] not in ('HISTORY_READY', 'HISTORY_VALIDATED'):
            raise ValueError('Estimate historical wind fields before evaluating.')
        grid = json.loads(Path(settings['grid_spec']).read_text(encoding='utf-8'))
        if (Path(catalog).resolve() != Path(workspace)/'wind_event_catalog'
                or _sha256(settings['grid_spec']) != settings['grid_sha256']
                or _raster_digest(arcpy, workspace, settings['products']) != settings['products_sha256']):
            raise ValueError('Historical wind inputs or products changed. Rerun estimation.')
        domain = island_domain(arcpy, grid)
        for name in settings['products']:
            path = str(Path(workspace)/name)
            info = _raster_info(arcpy, path)
            errors = grid_errors(info, info, grid['extent'], grid['rows'], grid['columns'])
            if errors or np.any(arcpy.RasterToNumPyArray(path, nodata_to_value=-9999)[~domain] != -9999):
                raise ValueError(f'{name}: mismatched grid or exterior NoData. {errors}')
        with arcpy.da.SearchCursor(str(catalog), ['SID','OBS','MODELED_YEARS']) as cursor:
            records = list(cursor)
        if sorted(sid for sid, _, _ in records) != settings['storm_ids']:
            raise ValueError('The event ledger does not account for the complete prepared catalog.')
        summary = str(Path(workspace)/'wind_time_step_comparison')
        with arcpy.da.SearchCursor(summary, ['MAX_DISAGREEMENT_PCT']) as cursor:
            differences = [value for value, in cursor]
        if not differences or max(differences) > 1:
            raise ValueError('Five-minute sampling disagrees with 2.5 minutes on more than 1% of tested profile/cell combinations.')
        if reference_observations:
            from .wind_workflow import _evaluate_stations
            _evaluate_stations(arcpy, workspace, dict(settings, scenarios=[settings['profiles'][settings['chosen_profile']]]),
                               _track_rows(arcpy, workspace), reference_observations)
        settings['stage'] = 'HISTORY_VALIDATED'
        _settings(arcpy, workspace, settings)
        _mark_report(settings, 'VALIDATED', observation_count=sum(n for _, n, _ in records),
                     storm_count=len(records), modeled_storm_count=sum(n>0 for _, _, n in records),
                     chosen_profile=settings['profiles'][settings['chosen_profile']],
                     profile_mae_km=settings['profile_errors_km'], profile_storm_count=settings['profile_storm_count'],
                     leave_one_out_switches=settings['leave_one_out_switches'],
                     unresolved_years=settings['unresolved_years'], time_step_storm_count=len(differences),
                     max_time_step_disagreement_pct=max(differences), products_sha256=settings['products_sha256'],
                     grid_spec=settings['grid_spec'])
        return {'summary': summary, 'report': settings['validation_report']}
    except Exception as error:
        _mark_report(settings, 'FAILED', error=str(error))
        raise
