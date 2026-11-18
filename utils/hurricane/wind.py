"""HURRECON equations and UTC track interpolation, independent of ArcGIS.

Equations: Boose, Serrano & Foster (2004), doi:10.1890/02-4057.
Conventions checked against the author's HurreconPython scalar functions.
This module implements the published equations; it imports no external engine.
"""
from __future__ import annotations

import math
import numpy as np

KNOT_MPS = 1852 / 3600
EARTH_KM = 6367.0  # Spherical radius used by HurreconPython.
BENCHMARK_STORMS = ('1956222N13313', '1989254N13340', '1998259N10335', '2017260N12310')
SIZE_SCENARIOS = ((20.0, 1.5), (40.0, 1.4), (60.0, 1.3), (80.0, 1.2))
SOURCE = 'https://doi.org/10.1890/02-4057'


def range_bearing(latitude, longitude, target_latitude, target_longitude):
    """Great-circle kilometers and initial bearing clockwise from true north."""
    lat1, lon1, lat2, lon2 = np.broadcast_arrays(*[
        np.radians(np.asarray(v, dtype=float))
        for v in (latitude, longitude, target_latitude, target_longitude)])
    if not all(np.isfinite(a).all() for a in (lat1, lon1, lat2, lon2)):
        raise ValueError('Coordinates must be finite.')
    if np.any(np.abs(lat1) > np.pi / 2) or np.any(np.abs(lat2) > np.pi / 2):
        raise ValueError('Latitude must be between -90 and 90 degrees.')
    delta = (lon2 - lon1 + np.pi) % (2 * np.pi) - np.pi
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(delta / 2) ** 2
    a = np.clip(a, 0, 1)
    distance = 2 * EARTH_KM * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    y = np.sin(delta) * np.cos(lat2)
    x = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(delta)
    bearing = np.degrees(np.arctan2(y, x)) % 360
    return distance, bearing


def wind_speed(distance_km, bearing, latitude, heading, translation_mps,
               maximum_mps, radius_km, profile_b, friction=0.8):
    """One-minute sustained surface wind in m/s; eye-center limit is zero."""
    values = (latitude, heading, translation_mps, maximum_mps, radius_km, profile_b, friction)
    if not all(np.isfinite(v).all() for v in values):
        raise ValueError('HURRECON parameters must be finite; missing values require coverage review.')
    if (np.any(np.asarray(radius_km) <= 0) or np.any(np.asarray(profile_b) <= 0)
            or np.any(np.asarray(translation_mps) < 0) or np.any(np.asarray(maximum_mps) < 0)
            or np.any(np.asarray(friction) <= 0)):
        raise ValueError('Invalid wind, motion, radius, profile or friction parameter.')
    distance = np.asarray(distance_km, dtype=float)
    bearing = np.asarray(bearing, dtype=float)
    if not np.isfinite(distance).all() or not np.isfinite(bearing).all() or np.any(distance < 0):
        raise ValueError('Distances and bearings must be finite; distance must be nonnegative.')
    angle = np.radians(np.where(np.asarray(latitude) >= 0, bearing - heading, heading - bearing))
    peak = np.maximum(0, maximum_mps - translation_mps * (1 - np.sin(angle)) / 2)
    safe_distance = np.where(distance == 0, 1, distance)
    q = (np.asarray(radius_km) / safe_distance) ** np.asarray(profile_b)
    # The logarithmic form avoids the unstable product q * exp(1-q).
    radial = np.exp((np.log(q) + 1 - q) / 2)
    return np.where(distance == 0, 0, friction * peak * radial)


def validate_track(records):
    """Sort full native tracks and reject unresolved eligible intervals."""
    track = sorted(records, key=lambda r: r['time'])
    if len(track) < 2:
        raise ValueError('A storm needs at least two native positions to derive motion.')
    times = np.array([r['time'].timestamp() for r in track])
    if np.any(np.diff(times) <= 0):
        raise ValueError('Storm timestamps must be unique and strictly increasing.')
    for row in track:
        if not (-90 <= row['lat'] <= 90 and -180 <= row['lon'] <= 180):
            raise ValueError('Invalid USA coordinates.')
        if row['nature'] in {'TS', 'SS'}:
            if row['wind'] is None or not math.isfinite(row['wind']) or row['wind'] < 0:
                raise ValueError('Missing/invalid USA_WIND in a tropical or subtropical phase.')
    segments = []
    for i, (left, right) in enumerate(zip(track, track[1:])):
        if left['nature'] in {'TS', 'SS'} and right['nature'] in {'TS', 'SS'}:
            if times[i + 1] - times[i] > 6 * 3600:
                raise ValueError('Eligible native interval exceeds six hours; no gap filling is authorized.')
            segments.append(i)
    if not segments:
        raise ValueError('No supported tropical/subtropical track intervals.')
    supported = {i for segment in segments for i in (segment, segment + 1)}
    if any(r['nature'] in {'TS', 'SS'} and i not in supported for i, r in enumerate(track)):
        raise ValueError('Isolated eligible observation requires an explicit coverage decision.')
    return track, segments


def interpolate_track(records, step_minutes, window=None):
    """Linear native-interval interpolation with midpoint-interpolated motion.

    Keep original timestamps, unwrap longitude/headings, and carry UTC seconds.
    Motion uses full USA positions, including adjacent lifecycle records.
    """
    if not math.isfinite(step_minutes) or step_minutes <= 0:
        raise ValueError('Time step must be positive and finite.')
    track, segments = validate_track(records)
    times = np.array([r['time'].timestamp() for r in track])
    first, last = times[segments[0]], times[segments[-1] + 1]
    if window is not None:
        first, last = map(float, window)
        if not np.isfinite([first, last]).all() or last <= first:
            raise ValueError('Observation window requires finite increasing UTC times.')
        covered_until = first
        for i in segments:
            if times[i] <= covered_until < times[i + 1]:
                covered_until = times[i + 1]
        if covered_until < last:
            raise ValueError('Observation window crosses an unsupported storm phase or extends beyond coverage.')
    lat = np.array([r['lat'] for r in track])
    lon = np.degrees(np.unwrap(np.radians([r['lon'] for r in track])))
    wind = np.array([np.nan if r['wind'] is None else r['wind'] for r in track])
    distances, headings = range_bearing(lat[:-1], lon[:-1], lat[1:], lon[1:])
    speeds = distances * 1000 / np.diff(times)
    midpoints = (times[1:] + times[:-1]) / 2
    sample_times, sample_lat, sample_lon, sample_wind = [], [], [], []
    for i in segments:
        begin, end = max(first, times[i]), min(last, times[i + 1])
        if end < begin:
            continue
        pieces = max(1, math.ceil((end - begin) / (step_minutes * 60)))
        fraction = np.linspace((begin - times[i]) / (times[i + 1] - times[i]),
                               (end - times[i]) / (times[i + 1] - times[i]), pieces + 1)
        sample_times.extend(times[i] + fraction * (times[i + 1] - times[i]))
        sample_lat.extend(lat[i] + fraction * (lat[i + 1] - lat[i]))
        sample_lon.extend(lon[i] + fraction * (lon[i + 1] - lon[i]))
        sample_wind.extend(wind[i] + fraction * (wind[i + 1] - wind[i]))
    seconds, indexes = np.unique(sample_times, return_index=True)
    return dict(time=seconds, lat=np.asarray(sample_lat)[indexes],
                lon=(np.asarray(sample_lon)[indexes] + 180) % 360 - 180,
                wind=np.asarray(sample_wind)[indexes],
                speed=np.interp(seconds, midpoints, speeds),
                heading=np.degrees(np.interp(seconds, midpoints, np.unwrap(np.radians(headings)))) % 360)


def peak_fields(samples, cell_latitude, cell_longitude, scenarios=SIZE_SCENARIOS, progress=None):
    """Stream maxima for every scenario without retaining a time-by-cell cube.

    A spherical enclosing circle gives an upper bound on every cell's wind.
    Skip a sample only when that bound cannot improve any scenario's minimum
    current peak. No arbitrary distance cutoff or wind-storage threshold applies.
    """
    lat = np.asarray(cell_latitude, dtype=float)
    lon = np.asarray(cell_longitude, dtype=float)
    radii = np.array([r for r, b in scenarios])
    profiles = np.array([b for r, b in scenarios])
    center_lat, center_lon = float(np.mean(lat)), float(np.mean(lon))
    enclosing_radius = float(np.max(range_bearing(center_lat, center_lon, lat, lon)[0])) + 1e-6
    center_distance = range_bearing(center_lat, center_lon, samples['lat'], samples['lon'])[0]
    minimum_distance = np.maximum(0, center_distance - enclosing_radius)
    bounds = np.empty((len(scenarios), len(center_distance)))
    for j, (radius, profile) in enumerate(scenarios):
        q = (radius / np.maximum(radius, minimum_distance)) ** profile
        bounds[j] = 0.8 * samples['wind'] * np.sqrt(q * np.exp(1 - q))
    order = np.argsort(-np.max(bounds, axis=0), kind='stable')
    peaks = np.zeros((len(scenarios), len(lat)))
    floor = np.zeros(len(scenarios))
    evaluated = 0
    for number, i in enumerate(order):
        if progress and number % 100 == 0:
            progress(number, len(order))
        if np.all(bounds[:, i] + 1e-10 < floor):
            continue
        distance, bearing = range_bearing(samples['lat'][i], samples['lon'][i], lat, lon)
        values = wind_speed(distance[None, :], bearing[None, :], samples['lat'][i],
                            samples['heading'][i], samples['speed'][i], samples['wind'][i],
                            radii[:, None], profiles[:, None])
        np.maximum(peaks, values, out=peaks)
        floor = np.min(peaks, axis=1)
        evaluated += 1
    return peaks, dict(samples=len(order), evaluated=evaluated, bounded_skips=len(order) - evaluated)


def convergence(coarse, fine):
    """Compare identical land cells, with thresholds converted exactly from kt."""
    delta = np.abs(np.asarray(coarse) - np.asarray(fine))
    if delta.size == 0 or not np.isfinite(delta).all():
        raise ValueError('Convergence requires finite paired peak fields.')
    difference34 = float(np.mean((coarse >= 34 * KNOT_MPS) != (fine >= 34 * KNOT_MPS)) * 100)
    difference64 = float(np.mean((coarse >= 64 * KNOT_MPS) != (fine >= 64 * KNOT_MPS)) * 100)
    p99 = float(np.quantile(delta, .99))
    return dict(p99_mps=p99, max_mps=float(delta.max()), disagreement34_pct=difference34,
                disagreement64_pct=difference64,
                passed=p99 <= 1 and difference34 <= 1 and difference64 <= 1)


def quadrant_radius(maximum_mps, speed_mps, heading, radius_km, profile_b, threshold_kt, quadrant):
    """Maximum outer water-exposure threshold radius in an NE/SE/SW/NW quadrant."""
    start = {'NE': 0, 'SE': 90, 'SW': 180, 'NW': 270}[quadrant]
    bearings = [start, start + 90]
    right_side = (heading + 90) % 360
    if (right_side - start) % 360 <= 90:
        bearings.append(right_side)
    strongest = max(float(wind_speed(radius_km, b, 18, heading, speed_mps,
                                    maximum_mps, radius_km, profile_b, friction=1)) for b in bearings)
    threshold = threshold_kt * KNOT_MPS
    if strongest < threshold:
        return 0.0
    lower, upper = radius_km, radius_km * 2
    def radial(distance):
        q = (radius_km / distance) ** profile_b
        return strongest * math.sqrt(q * math.exp(1 - q))
    while radial(upper) >= threshold:
        upper *= 2
    for _ in range(50):
        middle = (lower + upper) / 2
        if radial(middle) >= threshold:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2
