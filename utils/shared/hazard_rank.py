"""Publish the two course hazard scores and their integer map classes."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from .grid import _sha256, _write_json

NODATA = -9999
RANK_CODES = (1, 3, 5)
RELATIVE_METHOD = 'Natural Breaks (Jenks)'
SUM_COLORS = {2: (245, 218, 109), 4: (124, 195, 118), 6: (47, 153, 180),
              8: (99, 82, 167), 10: (104, 28, 56)}


def island_domain(arcpy, grid):
    from ..drought.usdm_spatial import _islands
    with TemporaryDirectory(prefix='sdss_index_', ignore_cleanup_errors=True) as temporary:
        scratch = str(Path(temporary)/'grid.gdb')
        arcpy.management.CreateFileGDB(temporary, 'grid.gdb')
        try:
            island, _, _ = _islands(arcpy, grid, scratch)
        finally:
            arcpy.management.ClearWorkspaceCache(scratch)
            try:
                arcpy.management.Delete(scratch)
            except arcpy.ExecuteError:
                arcpy.AddWarning('ArcGIS retained a lock on the temporary island grid.')
    return (island > 0) & (island < 4)


def write_raster(workspace, name, values, grid, *, integer=False):
    from ..drought.usdm_spatial import publish_raster
    publish_raster(workspace, name, values, grid, integer)
    return str(Path(workspace)/name)


def ranks(count, low, medium):
    return np.where(np.isfinite(count), np.where(count <= low, 1, np.where(count <= medium, 3, 5)), np.nan)


def read_raster(arcpy, path):
    raw = arcpy.RasterToNumPyArray(str(path), nodata_to_value=NODATA).astype(float)
    raw[raw == NODATA] = np.nan
    return raw


def rank_raster(arcpy, source, target, count, low, medium, grid):
    expected = ranks(count, low, medium)
    codes = np.unique(count[np.isfinite(count)]).astype(int)
    if set(np.unique(expected[np.isfinite(expected)])) != set(RANK_CODES):
        raise ValueError(f'{source} must support three nonempty classes with equal counts kept together.')
    remap = arcpy.sa.RemapValue([[int(n), 1 if n <= low else 3 if n <= medium else 5] for n in codes])
    with arcpy.EnvManager(overwriteOutput=True, extent=grid['reference_raster'],
                          outputCoordinateSystem=arcpy.SpatialReference(32161),
                          mask=None, snapRaster=grid['reference_raster'], cellSize=250):
        result = arcpy.sa.Reclassify(str(source), 'VALUE', remap, 'NODATA')
        result.save(str(target))
        del result
    if not np.array_equal(read_raster(arcpy, target), expected, equal_nan=True):
        raise ValueError(f'Reclassified pixels differ from the course rule: {target}')
    from ..hurricane.validation import grid_errors, _raster_info
    info = _raster_info(arcpy, str(target))
    if (errors := grid_errors(info, info, grid['extent'], grid['rows'], grid['columns'])):
        raise ValueError('; '.join(errors))
    return expected


def _jenks(values):
    """Exact three-group Jenks objective over unique values with cell frequencies."""
    distinct, frequency = np.unique(values, return_counts=True)
    if len(distinct) < 3:
        return None
    counts, sums, squares = (np.r_[0, np.cumsum(term)] for term in
                              (frequency, frequency*distinct, frequency*distinct**2))
    best = (float('inf'), 0, 0)
    for first in range(1, len(distinct)-1):
        second = np.arange(first+1, len(distinct))
        within = squares[-1] - (sums[first]**2/counts[first]
                 + (sums[second]-sums[first])**2/(counts[second]-counts[first])
                 + (sums[-1]-sums[second])**2/(counts[-1]-counts[second]))
        i = int(np.argmin(within))
        best = min(best, (float(within[i]), first, int(second[i])))
    return [float(distinct[best[1]-1]), float(distinct[best[2]-1])]


def relative_breaks(count):
    """Fit three classes on one layer's valid cells. Keep ties in one class."""
    breaks = _jenks(count[np.isfinite(count)])
    return tuple(map(int, breaks)) if breaks is not None else None


def comparison_breaks(count):
    values = count[np.isfinite(count)]
    lo, hi = float(values.min()), float(values.max())
    return {'Quantile': np.quantile(values, [1/3, 2/3], method='linear').tolist(),
            'Natural Breaks': _jenks(values), 'Equal Interval': [lo+(hi-lo)/3, lo+2*(hi-lo)/3]}


def _clipped_area(arcpy, grid, domain, values, fema):
    """Intersect course-grid cells with land, including clipped coastal cells."""
    from ..drought.usdm_spatial import _islands
    e = grid['extent']
    area = np.zeros(domain.shape)
    context = None
    with TemporaryDirectory(prefix='sdss_class_area_', ignore_cleanup_errors=True) as temporary:
        scratch = str(Path(temporary)/'area.gdb')
        arcpy.management.CreateFileGDB(temporary, 'area.gdb')
        try:
            _, shapes, _ = _islands(arcpy, grid, scratch)
            primary = shapes['mainland'].union(shapes['Vieques']).union(shapes['Culebra'])
            land, cells, intersections = (str(Path(scratch)/n) for n in ('land','cells','land_cells'))
            with arcpy.EnvManager(outputCoordinateSystem=arcpy.SpatialReference(32161),
                                  extent=None, mask=None, parallelProcessingFactor='0'):
                arcpy.management.CopyFeatures([primary], land)
                arcpy.management.CreateFishnet(cells, f'{e["xmin"]} {e["ymin"]}',
                    f'{e["xmin"]} {e["ymin"]+250}', 250, 250, grid['rows'], grid['columns'],
                    '', 'NO_LABELS', '', 'POLYGON')
                arcpy.management.AddField(cells, 'CELL_ID', 'LONG')
                with arcpy.da.UpdateCursor(cells, ['SHAPE@', 'CELL_ID']) as cursor:
                    for shape, _ in cursor:
                        xy = shape.trueCentroid
                        col = int((xy.X-e['xmin'])/250)
                        row = int((e['ymax']-xy.Y)/250)
                        if domain[row, col]:
                            cursor.updateRow((shape, row*grid['columns']+col))
                        else:
                            cursor.deleteRow()
                arcpy.analysis.PairwiseIntersect([cells, land], intersections)
                with arcpy.da.SearchCursor(intersections, ['CELL_ID','SHAPE@AREA']) as cursor:
                    for cell, value in cursor:
                        area.ravel()[cell] += value
                if fema:
                    context = _compare_wind_tracts(arcpy, fema, intersections, scratch, grid, values)
        finally:
            arcpy.management.ClearWorkspaceCache(scratch)
            try:
                arcpy.management.Delete(scratch)
            except arcpy.ExecuteError:
                arcpy.AddWarning('ArcGIS retained a lock on the temporary class-area workspace.')
    if np.any(area[domain] <= 0):
        raise ValueError('Class area calculation lost a study cell.')
    return area / 1e6, context


def _compare_wind_tracts(arcpy, fema, land_cells, scratch, grid, score):
    from collections import defaultdict
    projected = str(Path(scratch)/'fema_tracts')
    pieces = str(Path(scratch)/'tract_cells')
    target = arcpy.SpatialReference(32161)
    source = arcpy.Describe(fema).spatialReference
    transforms = arcpy.ListTransformations(source, target)
    wgs84_to_nad83 = grid['geographic_transformation']
    transform = wgs84_to_nad83 if wgs84_to_nad83 in transforms else (transforms[0] if transforms else '')
    arcpy.management.Project(fema, projected, target, transform)
    arcpy.analysis.PairwiseIntersect([land_cells, projected], pieces)
    stats = defaultdict(lambda: [0., 0., float('inf'), float('-inf'), 0.])
    with arcpy.da.SearchCursor(pieces, ['TRACTFIPS','CELL_ID','SHAPE@AREA','HRCN_AFREQ']) as cursor:
        for tract, cell, area, frequency in cursor:
            value = score.ravel()[cell]
            if not np.isfinite(value) or frequency is None or area <= 0:
                continue
            row = stats[tract]
            row[0] += area
            row[1] += area * value
            row[2] = min(row[2], value)
            row[3] = max(row[3], value)
            row[4] = frequency
    return [(tract, row[0]/1e6, row[1]/row[0], row[2], row[3], row[4])
            for tract, row in sorted(stats.items())], transform


def _fema_drought(arcpy, workspace, fema):
    from collections import defaultdict
    with TemporaryDirectory(prefix='sdss_fema_', ignore_cleanup_errors=True) as temporary:
        scratch = str(Path(temporary)/'fema.gdb')
        arcpy.management.CreateFileGDB(temporary, 'fema.gdb')
        dates = defaultdict(set)
        try:
            dry, projected, joined = (str(Path(scratch)/name) for name in ('dry','tracts','joined'))
            with arcpy.EnvManager(extent=None, mask=None, outputCoordinateSystem=None):
                arcpy.analysis.Select(str(Path(workspace)/'pr_weekly_polygons'), dry,
                    "DM IN (3,4) AND MAP_DATE >= timestamp '2000-01-01 00:00:00' "
                    "AND MAP_DATE < timestamp '2025-04-01 00:00:00'")
                target = arcpy.Describe(dry).spatialReference
                transformations = arcpy.ListTransformations(arcpy.Describe(fema).spatialReference, target)
                arcpy.management.Project(fema, projected, target, transformations[0] if transformations else '')
                arcpy.analysis.SpatialJoin(projected, dry, joined, 'JOIN_ONE_TO_MANY', 'KEEP_COMMON',
                                           match_option='INTERSECT')
                with arcpy.da.SearchCursor(joined, ['TRACTFIPS','MAP_DATE']) as cursor:
                    for tract, when in cursor:
                        dates[tract].add(when)
        finally:
            arcpy.management.ClearWorkspaceCache(scratch)
            try:
                arcpy.management.Delete(scratch)
            except arcpy.ExecuteError:
                arcpy.AddWarning('ArcGIS retained a lock on the temporary FEMA comparison workspace.')
    with arcpy.da.SearchCursor(fema, ['TRACTFIPS','DRGT_EVNTS','DRGT_AFREQ']) as cursor:
        return [(tract, 7*len(dates[tract]), observed, frequency) for tract, observed, frequency in cursor]


def _fema_table(arcpy, workspace, fema, wind, wind_comparison):
    from ..hurricane.wind_workflow import _table
    if not fema:
        return None
    if wind:
        rows, transformation = wind_comparison
        fields = ['LAND_KM2','LOCAL_H64','LOCAL_MIN','LOCAL_MAX','FEMA_HRCN_AFREQ']
        details = {'tract_count': len(rows), 'transformation': transformation}
        if rows:
            values = np.array([row[1:] for row in rows])
            details.update(land_km2=float(values[:, 0].sum()),
                           local_rate_range=[float(values[:, 1].min()), float(values[:, 1].max())],
                           fema_rate_range=[float(values[:, 4].min()), float(values[:, 4].max())],
                           tracts_within_tract_variation=int(np.count_nonzero(values[:, 2] != values[:, 3])))
            if values[:, 1].std() and values[:, 4].std():
                details['tract_pearson_r'] = float(np.corrcoef(values[:, 1], values[:, 4])[0, 1])
    else:
        rows = _fema_drought(arcpy, workspace, fema)
        fields = ['LOCAL_D3_EVENT_DAYS','FEMA_DRGT_EVNTS','FEMA_DRGT_AFREQ']
        details = {'tract_count': len(rows), 'matching_event_days': sum(ours == theirs for _, ours, theirs, _ in rows)}
    table = _table(arcpy, workspace, 'fema_tract_comparison', [('TRACTFIPS','TEXT',11),
                   *((name,'DOUBLE',None) for name in fields)], rows)
    return dict(details, source=fema, table=table)


def _compare(primary, alternative, area):
    valid = np.isfinite(primary) & np.isfinite(alternative)
    return {'common_land_km2': float(area[valid].sum()),
            'changed_land_km2': float(area[valid & (primary != alternative)].sum()),
            'transition_land_km2': [[float(area[valid & (primary == a) & (alternative == b)].sum())
                                     for b in (1, 3, 5)] for a in (1, 3, 5)]}


def _relative_summary(classes, area, breaks):
    return dict(upper_count_breaks=list(breaks),
                class_cells={n:int(np.count_nonzero(classes == n)) for n in RANK_CODES},
                class_land_km2={n:float(area[classes == n].sum()) for n in RANK_CODES})


def _classify_wind_windows(arcpy, workspace, settings, grid, score, rank, primary, primary_breaks, area):
    from ..hurricane.wind_workflow import _table
    windows = []
    for label, start, end in settings['windows']:
        years = end-start
        name = f'N64_{label}'
        if label == 'all_2026':
            window_score, window_rank = score, str(rank)
            breaks, classes = primary_breaks, primary
        else:
            values = read_raster(arcpy, workspace/name)
            window_score = f'H64_score_{label}'
            window_rank = f'H64_rank_{label}'
            write_raster(workspace, window_score, values/years, grid)
            breaks = relative_breaks(values)
            if breaks is not None:
                classes = rank_raster(arcpy, workspace/name, workspace/window_rank, values, *breaks, grid)
            else:
                previous = str(workspace/window_rank)
                if arcpy.Exists(previous):
                    arcpy.management.Delete(previous)
                arcpy.AddWarning(f'{label}: retained the score. Three classes require three distinct counts.')
                window_rank = None
                classes = None
        areas = [float(area[classes == code].sum()) for code in RANK_CODES] if classes is not None else [None]*3
        windows.append((label, start, end-1, years, *(breaks or (None, None)), window_score, window_rank,
                        *areas, 'RANKED' if breaks else 'INSUFFICIENT_DISTINCT_COUNTS'))
    table = _table(arcpy, workspace, 'wind_reference_windows',
                   [('WINDOW','TEXT',30), ('FIRST_YEAR','SHORT',None), ('LAST_YEAR','SHORT',None),
                    ('YEARS','SHORT',None), ('LOW_MAX_COUNT','SHORT',None), ('MED_MAX_COUNT','SHORT',None),
                    ('SCORE_RASTER','TEXT',512), ('CLASS_RASTER','TEXT',512),
                    ('LOW_KM2','DOUBLE',None), ('MEDIUM_KM2','DOUBLE',None), ('HIGH_KM2','DOUBLE',None),
                    ('CLASS_STATUS','TEXT',40)], windows)
    return table, [record[0] for record in windows if record[-1] != 'RANKED']


def _classification(hazard, report_path, grid_spec, output_folder):
    import arcpy
    from ..hurricane.wind_workflow import _settings
    from ..hurricane.wind_history import _raster_digest
    from ..drought.usdm_spatial import settings_table, dataset_fingerprint
    report_path = str(Path(report_path).resolve())
    report = json.loads(Path(report_path).read_text(encoding='utf-8'))
    report.pop('classification', None)
    _write_json(Path(report_path), report)
    section = report.get('historical_wind' if hazard == 'wind' else 'processing', {})
    try:
        if section.get('status') != 'VALIDATED':
            raise ValueError('Run and validate the full processing model before classification.')
        workspace = Path(section['workspace']).resolve()
        wind = hazard == 'wind'
        settings = _settings(arcpy, workspace) if wind else settings_table(workspace)
        if (Path(grid_spec).resolve() != Path(settings['grid_spec']).resolve()
                or _sha256(grid_spec) != settings['grid_sha256']):
            raise ValueError('Use the same grid specification as the validated processing model.')
        if wind:
            if _raster_digest(arcpy, workspace, settings['products']) != section['products_sha256']:
                raise ValueError('Wind indicator rasters changed after validation.')
            if section['unresolved_years']:
                raise ValueError('Some storms have unresolved historical exposure. Review the wind event ledger before ranking.')
        elif dataset_fingerprint(workspace) != section['metrics_sha256']:
            raise ValueError('Drought indicators changed after validation.')
        grid = json.loads(Path(grid_spec).read_text(encoding='utf-8'))
        domain = island_domain(arcpy, grid)
        source, output, years = (('N64_all_2026', 'RiskHurricaneWinds', 71)
                                 if wind else ('N_D1', 'RiskDrought', 26))
        published = Path(output_folder).resolve()
        published.mkdir(parents=True, exist_ok=True)
        score = str(published/f'{output}_score250.tif')
        rank = published/f'{output}_rank250.tif'
        count = np.where(domain, read_raster(arcpy, workspace/source), np.nan)
        if np.any(np.isfinite(count) & ((count < 0) | (count != np.floor(count)))):
            raise ValueError('Historical counts must be nonnegative integers.')
        breaks = relative_breaks(count)
        if breaks is None:
            raise ValueError(f'{source} needs three distinct observed counts to publish three classes.')
        lo, hi = breaks
        fema = str(Path(__file__).resolve().parents[2]/'Hazard_Variables'/'NRI_FEMA_PR.gdb'/'NRI_CensusTracts_PR')
        if not arcpy.Exists(fema):
            fema = None
        area, wind_context = _clipped_area(arcpy, grid, domain, count/years, fema if wind else None)
        write_raster(published, Path(score).name, count/years, grid)
        spatial_license = arcpy.CheckOutExtension('Spatial')
        if spatial_license != 'CheckedOut':
            raise RuntimeError('Classification requires an available Spatial Analyst license.')
        try:
            masked = write_raster(workspace, 'course_count', count, grid, integer=True)
            primary = rank_raster(arcpy, masked, rank, count, lo, hi, grid)
            arcpy.management.Delete(masked)
            alternatives = {}
            for method, cuts in comparison_breaks(count).items():
                if method == 'Natural Breaks' or cuts is None:
                    continue
                alternate = ranks(count, *cuts)
                alternatives[method] = dict(breaks_count=cuts,
                    classes_present=np.unique(alternate[np.isfinite(alternate)]).astype(int).tolist(),
                    **_compare(primary, alternate, area))
            extra = {}
            if wind:
                table, score_only = _classify_wind_windows(
                    arcpy, workspace, settings, grid, score, rank, primary, breaks, area)
                extra.update(window_table=table, score_only_windows=score_only)
                for name in [f'N64_profile_{i}' for i in range(1, len(settings['profiles'])+1)] + ['N64_land_factor_1']:
                    values = read_raster(arcpy, workspace/name)
                    cuts = relative_breaks(values)
                    if cuts is not None:
                        alternate = ranks(values, *cuts)
                        alternatives[name] = dict(**_relative_summary(alternate, area, cuts),
                                                   **_compare(primary, alternate, area))
                alternatives['Former 0.02/0.05 storms per year'] = _compare(
                    primary, ranks(count, 2*years//100, 5*years//100), area)
            else:
                d2 = np.where(domain, read_raster(arcpy, workspace/'N_D2'), np.nan)
                d2_breaks = relative_breaks(d2)
                if d2_breaks is None:
                    raise ValueError('D2+ needs three distinct observed counts to publish three classes.')
                source_d2 = write_raster(workspace, 'course_d2_count', d2, grid, integer=True)
                d2_score = write_raster(workspace, 'D2_score_250', d2/years, grid)
                d2_rank = str(workspace/'D2_rank_250')
                comparison = rank_raster(arcpy, source_d2, d2_rank, d2, *d2_breaks, grid)
                arcpy.management.Delete(source_d2)
                alternatives['D2+'] = dict(score=d2_score, rank=d2_rank,
                    upper_rate_breaks=[n/years for n in d2_breaks],
                    **_relative_summary(comparison, area, d2_breaks), **_compare(primary, comparison, area))
                alternatives['3/7 weeks per year'] = _compare(primary, ranks(count, 78, 182), area)
        finally:
            arcpy.CheckInExtension('Spatial')
        fema_context = _fema_table(arcpy, workspace, fema, wind, wind_context)
        report['classification'] = dict(status='VALIDATED', score=score, rank=str(rank), years=years,
            reference_year=2026, method=RELATIVE_METHOD, upper_rate_breaks=[lo/years,hi/years],
            **_relative_summary(primary, area, breaks), **extra,
            unknown_land_km2=float(area[domain & ~np.isfinite(primary)].sum()), alternatives=alternatives,
            fema_comparison=fema_context)
        _write_json(Path(report_path), report)
        return {'score':score, 'rank':str(rank), 'report':report_path}
    except Exception as error:
        report['classification'] = dict(status='FAILED', error=str(error))
        _write_json(Path(report_path), report)
        raise


def classify_wind(validated_data, grid_spec, output_folder):
    return _classification('wind', validated_data, grid_spec, output_folder)


def classify_drought(validated_data, grid_spec, output_folder):
    return _classification('drought', validated_data, grid_spec, output_folder)


def combine_ranks(wind_rank, drought_rank, grid_spec, output_folder):
    """Reproduce and check the course Raster Calculator sum from Python."""
    import arcpy
    from ..hurricane.validation import _raster_info, grid_errors
    grid = json.loads(Path(grid_spec).read_text(encoding='utf-8'))
    wind_info, drought_info = (_raster_info(arcpy, path) for path in (wind_rank, drought_rank))
    errors = grid_errors(wind_info, drought_info, grid['extent'], grid['rows'], grid['columns'])
    if errors:
        raise ValueError('; '.join(errors))
    domain = island_domain(arcpy, grid)
    wind, drought = (read_raster(arcpy, path) for path in (wind_rank, drought_rank))
    if any(np.any(np.isfinite(values) & (~domain | ~np.isin(values, [1, 3, 5])))
           for values in (wind, drought)):
        raise ValueError('Both rasters must have only 1/3/5 classes inside the common study area.')
    if arcpy.CheckOutExtension('Spatial') != 'CheckedOut':
        raise RuntimeError('The course sum requires an available Spatial Analyst license.')
    target = Path(output_folder).resolve() / 'Combined_sum250.tif'
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with arcpy.EnvManager(overwriteOutput=True, extent=grid['reference_raster'], mask=None,
                              snapRaster=grid['reference_raster'], cellSize=250,
                              outputCoordinateSystem=arcpy.SpatialReference(32161)):
            result = arcpy.sa.Plus(wind_rank, drought_rank)
            result.save(str(target))
            del result
    finally:
        arcpy.CheckInExtension('Spatial')
    actual = read_raster(arcpy, target)
    if not np.array_equal(actual, wind+drought, equal_nan=True):
        raise ValueError('Combined raster failed integer sum or NoData validation.')
    return {'combined': str(target), 'classes_present': np.unique(actual[np.isfinite(actual)]).astype(int).tolist()}
