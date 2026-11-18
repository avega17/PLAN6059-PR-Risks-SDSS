"""Validate actual prototype datasets, rather than only successful tool return codes."""
from __future__ import annotations

from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path


class PrototypeValidationError(ValueError):
    """Validation failed; the report remains available for diagnosis."""


def _load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _output(document, key, parent):
    value = document.get(key) or document.get('outputs', {}).get(key)
    if not value:
        raise ValueError(f'Manifest has no {key!r} output')
    path = Path(value)
    return str(path if path.is_absolute() else Path(parent) / path)


def grid_errors(reference, mask, expected_extent, rows, columns):
    """Compare raster metadata without requiring ArcPy for these checks."""
    errors = []
    for label, info in (('reference', reference), ('mask', mask)):
        if info['wkid'] != 32161:
            errors.append(f'{label}: coordinate system must be EPSG:32161')
        if not all(math.isclose(info[k], 250.0, rel_tol=0, abs_tol=1e-8)
                   for k in ('cell_width', 'cell_height')):
            errors.append(f'{label}: cells must be exactly 250 x 250 m')
        if info['rows'] != rows or info['columns'] != columns:
            errors.append(f'{label}: dimensions differ from the grid specification')
        for key in ('xmin', 'ymin', 'xmax', 'ymax'):
            if not math.isclose(info['extent'][key], expected_extent[key], rel_tol=0, abs_tol=1e-6):
                errors.append(f'{label}: {key} differs from the grid specification')
        for key in ('xmin', 'ymin'):
            quotient = info['extent'][key] / 250.0
            if not math.isclose(quotient, round(quotient), rel_tol=0, abs_tol=1e-8):
                errors.append(f'{label}: {key} is off the anchored 250 m lattice')
    return errors


def _raster_info(arcpy, path):
    raster = arcpy.Raster(path)
    extent = raster.extent
    return {'wkid': raster.spatialReference.factoryCode,
            'cell_width': raster.meanCellWidth, 'cell_height': raster.meanCellHeight,
            'rows': raster.height, 'columns': raster.width,
            'extent': dict(zip(('xmin', 'ymin', 'xmax', 'ymax'),
                               (extent.XMin, extent.YMin, extent.XMax, extent.YMax)))}


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def validate_prototype(prepare_manifest, grid_spec, output_folder):
    import arcpy
    import numpy as np

    destination = Path(output_folder).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / 'validation_report.json'
    checks = []

    def check(label, condition, details=None):
        checks.append({'check': label, 'passed': bool(condition), 'details': details})

    report = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'Preparation and reference-grid audit; wind evaluation is reported separately in wind_benchmark when present.',
              'prepare_manifest': str(Path(prepare_manifest).resolve()),
              'grid_spec': str(Path(grid_spec).resolve()),
              'arcgis': arcpy.GetInstallInfo(), 'checks': checks,
              'limitations': ['Natural Earth mask is generalized and provisional.',
                              '250 m cells are computational resolution, not observed wind accuracy.',
                              'These preparation checks do not evaluate wind estimates or hazard ranking.']}
    try:
        prepared = _load(prepare_manifest)
        spec = _load(grid_spec)
        check('Preparation manifest reports successful completion', prepared.get('status') == 'complete')
        observations = _output(prepared, 'observations', Path(prepare_manifest).parent)
        for key in ('observations', 'storms', 'qc', 'raw_points', 'inventory'):
            path = _output(prepared, key, Path(prepare_manifest).parent)
            check(f'Prepared output exists: {key}', arcpy.Exists(path) or Path(path).is_file(), path)
        inventory = _load(_output(prepared, 'inventory', Path(prepare_manifest).parent))
        checksum_results = []
        for source, components in inventory.get('sources', {}).items():
            for component in components:
                original = Path(component['source'])
                intact = original.is_file() and _sha256(original) == component['sha256']
                checksum_results.append({'source': source, 'path': str(original), 'unchanged': intact})
        check('All original source components remain unchanged',
              bool(checksum_results) and all(item['unchanged'] for item in checksum_results), checksum_results)
        reference = _output(spec, 'reference_raster', Path(grid_spec).parent)
        mask = _output(spec, 'mask_raster', Path(grid_spec).parent)
        check('Prepared points use WGS84', arcpy.Describe(observations).spatialReference.factoryCode == 4326)
        fields = {f.name for f in arcpy.ListFields(observations)}
        required = {'SID', 'SEASON', 'ISO_TIME', 'TRACK_TYPE', 'USA_LAT', 'USA_LON',
                    'USA_WIND', 'USA_AGENCY', 'IFLAG', 'USA_IFLAG', 'OBS_TIME_UTC',
                    'SOURCE_OID', 'QC_FLAGS'}
        check('Required data-contract fields exist', required <= fields, sorted(required - fields))
        if not required <= fields:
            raise ValueError('Prepared observation schema is incomplete')
        seen = set()
        duplicates = bad_geometry = bad_flag = bad_type = bad_time = bad_wind = 0
        count = missing_wind = blank_agency = interpolated = 0
        storms = set()
        seasons = []
        with arcpy.da.SearchCursor(observations, ['SID', 'SEASON', 'ISO_TIME', 'TRACK_TYPE',
                'USA_LAT', 'USA_LON', 'USA_WIND', 'USA_AGENCY', 'IFLAG',
                'USA_IFLAG', 'OBS_TIME_UTC', 'SHAPE@XY']) as cursor:
            for sid, season, iso, track_type, lat, lon, wind, agency, flags, usa_flag, utc, xy in cursor:
                count += 1
                storms.add(sid)
                seasons.append(int(season))
                key = (sid, iso)
                duplicates += key in seen
                seen.add(key)
                bad_type += str(track_type).strip().casefold() != 'main'
                bad_flag += (not flags or len(str(flags)) != 15 or
                             str(usa_flag) != str(flags)[0] or
                             usa_flag not in {'O', 'P', 'I', 'V', '_'})
                bad_time += utc is None
                if lat is None or lon is None or xy is None:
                    bad_geometry += 1
                elif not (math.isclose(xy[0], lon, abs_tol=1e-9) and
                          math.isclose(xy[1], lat, abs_tol=1e-9)):
                    bad_geometry += 1
                missing_wind += wind is None
                bad_wind += wind is not None and (not math.isfinite(wind) or wind < 0)
                blank_agency += not agency or not str(agency).strip()
                interpolated += str(usa_flag) == 'P'
        for label, errors in [('Unique SID/time pairs', duplicates),
                              ('Only main-track records', bad_type),
                              ('USA geometry matches USA coordinates', bad_geometry),
                              ('USA flag derived from complete IFLAG', bad_flag),
                              ('Parsed UTC timestamps present', bad_time),
                              ('Winds contain no unresolved numeric missing sentinels', bad_wind)]:
            check(label, errors == 0, {'violations': errors})
        check('Prepared observations are nonempty', count > 0)
        summary = prepared.get('summary', {})
        check('Observation count agrees with preparation audit',
              count == summary.get('selected_observation_count'), {'actual': count, 'audit': summary.get('selected_observation_count')})
        with arcpy.EnvManager(extent=None):
            storm_table_rows = int(arcpy.management.GetCount(
                _output(prepared, 'storms', Path(prepare_manifest).parent))[0])
        check('Distinct storms agree with audit and event table',
              len(storms) == summary.get('selected_storm_count') == storm_table_rows,
              {'actual': len(storms), 'audit': summary.get('selected_storm_count')})
        check('Missing winds and blank agencies are retained as audited',
              missing_wind == summary.get('missing_usa_wind_included') and
              blank_agency == summary.get('missing_agency_included'),
              {'missing_wind': missing_wind, 'blank_agency': blank_agency})
        qc_rows = qc_included = 0
        qc_ids = set()
        with arcpy.da.SearchCursor(prepared['qc'], ['SID', 'ISO_TIME', 'ROW_STATUS']) as cursor:
            for sid, iso, status in cursor:
                qc_rows += 1
                if status == 'INCLUDED':
                    qc_included += 1
                    qc_ids.add((sid, iso))
        with arcpy.EnvManager(extent=None):
            raw_count = int(arcpy.management.GetCount(prepared['raw_points'])[0])
        check('Raw points and QC account for every source and included observation',
              qc_rows == raw_count == summary.get('source_active_rows') and
              qc_included == count and qc_ids == seen,
              {'raw_points': raw_count, 'qc_rows': qc_rows, 'included': qc_included})
        if prepared.get('canonical_csv'):
            with Path(prepared['canonical_csv']).open(encoding='utf-8', newline='') as stream:
                rows = list(csv.DictReader(stream))
            check('Optional CSV agrees with QC', len(rows) == qc_rows and
                  {(r['SID'], r['ISO_TIME']) for r in rows if r['ROW_STATUS'] == 'INCLUDED'} == seen)
        period = prepared.get('parameters', {})
        start = period.get('start_season', summary.get('start_season', 1955))
        end = period.get('end_season', summary.get('end_season', 2025))
        check('Records fall within requested seasons', bool(seasons) and
              min(seasons) >= start and max(seasons) <= end,
              {'requested': [start, end], 'actual': [min(seasons), max(seasons)] if seasons else None})
        reference_info = _raster_info(arcpy, reference)
        mask_info = _raster_info(arcpy, mask)
        mismatches = grid_errors(reference_info, mask_info, spec['extent'],
                                 spec['rows'], spec['columns'])
        check('Reference and mask match the exact shared grid', not mismatches, mismatches)
        with arcpy.EnvManager(extent=None, mask=None, snapRaster=None):
            values = arcpy.RasterToNumPyArray(mask, nodata_to_value=255)
            ref_values = arcpy.RasterToNumPyArray(reference)
        check('Mask contains land=1 and exterior NoData',
              set(np.unique(values).tolist()) == {1, 255},
              {'land_cells': int(np.count_nonzero(values == 1)),
               'exterior_nodata_cells': int(np.count_nonzero(values == 255))})
        check('Reference is a constant computational grid', bool(np.all(ref_values == 0)))
        boundary = _output(spec, 'projected_boundary', Path(grid_spec).parent)
        check('Projected boundary exists', arcpy.Exists(boundary), boundary)
        from utils.shared.grid import ISLAND_POINTS
        island_results = {}
        geometries = [row[0] for row in arcpy.da.SearchCursor(boundary, ['SHAPE@'])]
        sr_wgs = arcpy.SpatialReference(4326)
        target = arcpy.SpatialReference(32161)
        for name, location in ISLAND_POINTS.items():
            lon, lat = location
            point = arcpy.PointGeometry(arcpy.Point(lon, lat), sr_wgs)
            transformations = arcpy.ListTransformations(sr_wgs, target, point.extent)
            projected = point.projectAs(target, transformations[0] if transformations else None)
            in_boundary = any(g.contains(projected) or g.touches(projected) for g in geometries)
            cell = arcpy.management.GetCellValue(mask, f'{projected.firstPoint.X} {projected.firstPoint.Y}')[0]
            island_results[name] = {'inside_boundary': in_boundary, 'mask_value': cell}
        check('Mainland, Vieques, Culebra, and Mona represented',
              all(r['inside_boundary'] and r['mask_value'] == '1' for r in island_results.values()),
              island_results)
        report['observations'] = {'rows': count, 'unique_storms': len(storms),
                                  'missing_wind': missing_wind, 'blank_agency': blank_agency,
                                  'position_interpolated': interpolated}
        report['rasters'] = {'reference': reference_info, 'mask': mask_info}
    except Exception as error:
        check('Validation execution', False, f'{type(error).__name__}: {error}')
    report['passed'] = bool(checks) and all(item['passed'] for item in checks)
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    if not report['passed']:
        failed = [item['check'] for item in checks if not item['passed']]
        raise PrototypeValidationError(f"Validation failed ({', '.join(failed)}). Report: {report_path}")
    return {'report': str(report_path), 'passed': True}
