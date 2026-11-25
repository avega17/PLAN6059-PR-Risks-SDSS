"""Revalidate acquired bytes, statistics and chronology without network access."""
from __future__ import annotations

from pathlib import Path

from .usdm_archive import inspect_zip
from .usdm_common import DroughtAcquisitionError, normalized_reader, typed_value, read_json, sha256, utc_now, write_json
from .usdm_download import validate_plan
from .usdm_statistics import STAT_SCHEMA, QC_SCHEMA, compare_state_formats, normalize_payload, statistic_jobs


def validate_drought_download(download_manifest, output_folder):
    output = Path(output_folder).expanduser().resolve()
    output.mkdir(parents=True,exist_ok=True)
    report_path = output/'download_validation.json'
    checks, state, warnings = [],{},[]
    report = {'schema_version':1,'created_utc':utc_now(),'download_manifest':str(Path(download_manifest).resolve()),
        'checks':checks,'passed':False,'ready_for_rasterization':False,
        'scope':'Acquisition validation; assessed-domain, topology and raster/metric checks remain outstanding.'}

    def check(label, condition, details=None):
        checks.append({'check':label,'passed':bool(condition),'details':details})

    try:
        manifest = read_json(download_manifest)
        plan = manifest['plan_snapshot']
        validate_plan(plan)
        check('Acquisition completed',manifest['status']=='complete' and manifest['acquisition_status']=='COMPLETE')
        check('Original plan checksum unchanged',sha256(manifest['download_plan'])==manifest['download_plan_sha256'])
        expected = {row['MAP_DATE']:row['ROLE'] for row in plan['weeks']}
        actual = {row['map_date']:row['role'] for row in manifest['gis']}
        check('GIS calendar and roles match the planned cohort',actual==expected and len(actual)==len(manifest['gis']))
        check('Baseline and buffer counts are separate',
            sum(e['role']=='BASELINE' for e in manifest['gis'])==plan['baseline_count'])
        zip_errors,source_errors,projections = [],[],set()
        for entry in manifest['gis']:
            try:
                if sha256(entry['path'])!=entry['sha256']:
                    raise ValueError('Archive checksum mismatch')
                audited = inspect_zip(entry['path'],entry['map_date'])
                if audited!=entry['audit']:
                    raise ValueError('Current archive audit differs from acquisition audit')
                projections.add(audited['source_crs_wkt'])
            except Exception as error:
                zip_errors.append({'date':entry['map_date'],'error':str(error)})
            if entry['source_kind']=='LOCAL_COPY':
                try:
                    if sha256(entry['original_path'])!=entry['original_sha256']:
                        source_errors.append(entry['original_path'])
                except OSError:
                    source_errors.append(entry['original_path'])
        check('All GIS ZIP hashes, CRCs, dates, schemas and geometry headers pass',not zip_errors,zip_errors)
        check('Used local source archives remain unchanged',not source_errors,source_errors)
        # The plan also freezes unused professor archives; keep those source checks.
        unused_errors = []
        for candidates in plan['local_candidates'].values():
            for entry in candidates:
                try:
                    if sha256(entry['path'])!=entry['sha256']:
                        unused_errors.append(entry['path'])
                except OSError:
                    unused_errors.append(entry['path'])
        check('Entire inventoried local source snapshot remains unchanged',not unused_errors,unused_errors)
        receipts = [manifest['catalog'],*manifest['documents'],*manifest['statistics_requests']]
        body_errors = [r['path'] for r in receipts if sha256(r['path'])!=r['sha256']]
        check('Catalog, documentation and statistics response hashes match',not body_errors,body_errors)
        check('Statistics request jobs match the declared products and years',
            [r['job'] for r in manifest['statistics_requests']]==statistic_jobs(plan))
        expected_rows, mismatches = 0,0
        with normalized_reader(manifest['statistics'], STAT_SCHEMA) as canonical:
            for receipt in manifest['statistics_requests']:
                rows,issues,seen,counts = normalize_payload(read_json(receipt['path']),receipt['job'],expected,receipt['sha256'])
                warnings.extend(issues)
                check(f'Statistics geography/date contract: {receipt["job"]["id"]}',
                      counts==receipt['normalization'] and len(rows)==receipt['normalized_rows'])
                if receipt['job']['kind']!='municipio':
                    key = 'dsci' if receipt['job']['kind']=='dsci' else str(receipt['job']['format'])
                    for (_,day),raw in seen.items():
                        state.setdefault(day,{})[key] = raw
                for row in rows:
                    recorded = next(canonical,None)
                    if recorded != {key:typed_value(row[key], kind) for key, kind, _ in STAT_SCHEMA}:
                        mismatches += 1
                    expected_rows += 1
            check('Normalized table contains no extra rows',next(canonical,None) is None)
        check('Every normalized value is reproducible from frozen raw statistics',mismatches==0,{'mismatches':mismatches})
        check('Normalized row count reconciles',expected_rows==manifest['normalized_rows'],expected_rows)
        for path_key, hash_key in (('canonical_csv', 'canonical_sha256'), ('qc_csv', 'qc_sha256')):
            if manifest.get(path_key):
                check('Optional/primary CSV hash matches: ' + path_key,
                      sha256(manifest[path_key]) == manifest[hash_key])
        with normalized_reader(manifest['qc'], QC_SCHEMA) as recorded_qc:
            expected_qc = [{key:typed_value(row[key], kind) for key, kind, _ in QC_SCHEMA}
                           for row in manifest['warnings']]
            check('Every retained QC value matches acquisition warnings', list(recorded_qc) == expected_qc)
        cross_warnings = compare_state_formats(state)
        expected_warnings = warnings+cross_warnings
        # Archive warnings are transport/schema observations, not source-statistic repairs.
        recorded_stat_warnings = [w for w in manifest['warnings'] if w['CODE'] not in
                                  ('CATALOG_SIZE_CHANGED','MULTIPLE_DM_FEATURES')]
        check('Reference disagreements are retained and reproducible',expected_warnings==recorded_stat_warnings)
        report.update(baseline_maps=plan['baseline_count'],buffer_maps=len(expected)-plan['baseline_count'],
            mode=plan['mode'],year_count=plan['year_count'],normalized_rows=expected_rows,
            reference_warning_count=len(manifest['warnings']),source_crs_variants=sorted(projections),
            index_scope=['mainland','Vieques','Culebra'],
            scope_exclusions={'Mona':'Outside the people-focused index; sparse observations are an expected edge case.'},
            outstanding=['Verify historical assessed-domain coverage for mainland, Vieques and Culebra.',
                'Check polygon topology and actual ArcPy projection/repair behavior before temporal rasters.',
                'None=0, D0=1,...,D4=5; unknown=255 must be masked out of threshold calculations.',
                'Frequency and event duration are hazard metrics; final ranking follows their evaluation.'])
    except Exception as error:
        check('Validation completed without an unreadable or invalid artifact',False,str(error))
    report['passed'] = bool(checks) and all(c['passed'] for c in checks)
    report['report'] = str(report_path)
    write_json(report_path,report)
    if not report['passed']:
        raise DroughtAcquisitionError(f'Download validation failed. Review {report_path}')
    return report


def evaluate_drought_metrics(metrics_catalog):
    """Check actual states/metrics and compare geometry without selecting ranks."""
    import arcpy
    import numpy as np
    import tempfile
    from .usdm_spatial import (load_workspace, settings_table, mark_report, dataset_fingerprint,
                               table, BENCHMARK_DATES, _islands)
    from .usdm_metrics import occupancy
    from ..hurricane.validation import _raster_info, grid_errors
    workspace = str(Path(metrics_catalog).resolve().parent)
    settings = settings_table(workspace)
    mark_report(settings,'CHECKING_METRICS')
    try:
        workspace, settings, grid, cube, island = load_workspace(workspace,True)
    except Exception as error:
        mark_report(settings,'FAILED',error=str(error))
        raise
    mark_report(settings,'EVALUATING')
    try:
        if Path(metrics_catalog).resolve() != Path(workspace)/'metric_catalog':
            raise ValueError('Use the Metrics Catalog produced by Calculate Drought Metrics.')
        if dataset_fingerprint(workspace) != settings['metrics_sha256']:
            raise ValueError('Metric tables or rasters changed; recalculate metrics.')
        count = settings['baseline_count']
        expected = occupancy(cube,count,26)
        check_arrays = dict(N_VALID=expected['nvalid'],N_D1=np.where(expected['eligible'],expected['d1'],np.nan),
            N_D2=np.where(expected['eligible'],expected['d2'],np.nan),
            W_D1=expected['wd1'],W_D2=expected['wd2'],ORDINAL_BURDEN=expected['burden'])
        with arcpy.da.SearchCursor(str(metrics_catalog),['DATASET']) as cursor:
            names = [r[0] for r in cursor]
        for name in names:
            if Path(name).name != name: raise ValueError('Catalog dataset must be inside its processing geodatabase.')
            path = str(Path(workspace)/name)
            info = _raster_info(arcpy,path)
            errors = grid_errors(info,info,grid['extent'],grid['rows'],grid['columns'])
            if errors: raise ValueError('; '.join(errors))
            values = arcpy.RasterToNumPyArray(path,nodata_to_value=-9999).astype(float)
            if np.any(values[island==0] != -9999): raise ValueError(name+': exterior cells must remain NoData.')
            if name in check_arrays:
                target = np.where(np.isfinite(check_arrays[name]) & (island>0),check_arrays[name],-9999)
                if not np.allclose(values,target,rtol=0,atol=1e-9): raise ValueError(name+': indicator differs from weekly states.')
            if name != 'N_VALID' and name != 'W_D1_2004' and np.any(values[(island>0)&~expected['eligible']] != -9999):
                raise ValueError(name+': incomplete baseline coverage received a full-period indicator.')
        # Annual normalized rows must reproduce the cube, including 52/53-map years.
        years = np.array([int(d[:4]) for d in settings['dates'][:count]])
        year_counts = {y:int(np.sum(years==y)) for y in range(2000,2026)}
        annual_valid = np.array([(cube[:count][years==y] <= 5).sum(axis=0) for y in range(2000,2026)])
        annual_dry = {dm: np.array([np.count_nonzero((cube[:count][years==y] > dm) &
                     (cube[:count][years==y] <= 5), axis=0) for y in range(2000,2026)]) for dm in (1, 2)}
        seen = np.zeros((26,grid['rows'],grid['columns']),bool)
        with arcpy.da.SearchCursor(str(Path(workspace)/'annual_cell_metrics'),
                                  ['CELL_ID','YEAR','N_EXPECTED','N_VALID','N_D1','N_D2']) as cursor:
            for cell,year,n,v,d1,d2 in cursor:
                r,c = divmod(cell,grid['columns']);y=year-2000
                if (not 0<=y<26 or not 0<=r<grid['rows'] or not 0<=c<grid['columns'] or island[r,c]==0
                        or seen[y,r,c] or n!=year_counts[year]
                        or v!=annual_valid[y,r,c] or d1!=annual_dry[1][y,r,c]
                        or d2!=annual_dry[2][y,r,c]):
                    raise ValueError('Annual cell table differs from the calendar/cube.')
                seen[y,r,c]=True
        if not np.all(seen[:,island>0]) or np.any(seen[:,island==0]):
            raise ValueError('Annual table has missing or extra land-cell/year rows.')
        del annual_valid,annual_dry,seen
        _check_cell_metrics(arcpy,workspace,cube,island,grid,settings)
        with tempfile.TemporaryDirectory(prefix='sdss_drought_evaluate_', ignore_cleanup_errors=True) as temporary:
            scratch = str(Path(temporary)/'evaluation.gdb')
            try:
                arcpy.management.CreateFileGDB(temporary,'evaluation.gdb')
                current,geometries,controls = _islands(arcpy,grid,scratch)
                if not np.array_equal(current,island): raise ValueError('Current island geometry differs from prepared state allocation.')
                controls_result = []
                for day in ('2015-08-04','2015-08-11'):
                    point = controls['Culebra'].firstPoint
                    c=int((point.X-grid['extent']['xmin'])/250);r=int((grid['extent']['ymax']-point.Y)/250)
                    code=int(cube[settings['dates'].index(day),r,c])
                    if code != 3: raise ValueError(f'Culebra {day}: expected D2 polygon assignment, got encoded {code}.')
                    controls_result.append(dict(date=day,island='Culebra',code=code))
                zero = cube[settings['dates'].index('2000-01-04')]
                if not np.all(zero[(island>=1)&(island<=3)]==0):
                    raise ValueError('The valid no-drought benchmark must retain assessed land as None=0.')
                _spatial_comparisons(arcpy,workspace,grid,settings,cube,island,geometries,scratch)
            finally:
                arcpy.management.ClearWorkspaceCache(scratch)
                if arcpy.Exists(scratch):
                    try:
                        arcpy.management.Delete(scratch)
                    except arcpy.ExecuteError:
                        if not arcpy.TestSchemaLock(scratch):
                            arcpy.AddWarning('ArcGIS still holds the temporary comparison workspace. '
                                             'Its lock is released when the geoprocessing session closes.')
                        else:
                            raise
        coverage = {name:dict(land_cells=int(np.sum(island==region)),
            complete_cells=int(np.sum((island==region)&expected['eligible'])),
            min_valid=int(expected['nvalid'][island==region].min()),
            max_valid=int(expected['nvalid'][island==region].max()))
            for region,name in enumerate(('mainland','Vieques','Culebra','Mona'),1)}
        if any(coverage[name]['complete_cells'] != coverage[name]['land_cells'] for name in ('mainland','Vieques','Culebra')):
            raise ValueError('Declared assessed primary islands lack complete baseline states.')
        settings.update(stage='VALIDATED',evaluation_software_sha256=sha256(__file__))
        settings_table(workspace,settings)
        primary=str(Path(workspace)/'W_D1');valid=str(Path(workspace)/'N_VALID')
        mark_report(settings,'VALIDATED',computational_checks_passed=True,
            metrics_sha256=settings['metrics_sha256'],evaluation_software_sha256=settings['evaluation_software_sha256'],
            baseline_maps=1357,buffer_maps=3,year_count=26,coverage=coverage,
            index_scope=['mainland','Vieques','Culebra'],
            scope_exclusions={'Mona':'Outside the people-focused index; sparse observations are an expected edge case. Unobserved states remain unknown and full-period indicators remain NoData.'},
            primary_indicator=primary,valid_count=valid,metrics_catalog=str(Path(workspace)/'metric_catalog'),
            source_warning_count=len(read_json(settings['manifest'])['warnings']),culebra_controls=controls_result,
            limitations=['Generalized Natural Earth coastline within the declared study domain.',
                         'Source-consistency checks do not establish independent drought skill.',
                         'Completed duration summaries exclude censored events and use baseline spans.',
                         '250 m output alignment is not 250 m meteorological information support.'])
        arcpy.AddMessage('D1+ and D2+ indicators and event metrics passed the processing checks.')
        arcpy.AddMessage('Mona is outside the people-focused index; sparse observations are an expected edge case, retained as unknown/NoData.')
        return {'primary':primary,'valid_count':valid,'report':settings['validation_report']}
    except Exception as error:
        mark_report(settings,'FAILED',error=str(error))
        raise


def _check_cell_metrics(arcpy,workspace,cube,island,grid,settings):
    """Read the normalized cell table and check basic counts/duration semantics."""
    import numpy as np
    fields=['CELL_ID','N_VALID','N_EXPECTED','COVERAGE_FRACTION','N_D1_OBS','N_D2_OBS','W_D1','F_D1','ORDINAL_BURDEN']
    from .usdm_metrics import EVENT_RULES, EVENT_SUMMARIES
    fields += [f'{n}_{suffix}' for _, _, suffix in EVENT_RULES for n in EVENT_SUMMARIES[:-1]]
    seen=set()
    with arcpy.da.SearchCursor(str(Path(workspace)/'cell_metrics'),fields) as cursor:
        for cell,nvalid,nexpected,fraction,d1,d2,wd1,fd1,burden,*events in cursor:
            r,c=divmod(cell,grid['columns'])
            if (cell in seen or not 0<=r<grid['rows'] or not 0<=c<grid['columns'] or island[r,c]==0
                    or not 0<=d2<=d1<=nvalid<=1357 or nexpected!=1357
                    or abs(fraction-nvalid/1357)>1e-12): raise ValueError('Invalid/duplicate normalized cell counts or coverage.')
            seen.add(cell)
            if nvalid==1357:
                if abs(wd1-d1/26)>1e-9 or abs(fd1-100*d1/1357)>1e-9 or not 0<=burden<=500:
                    raise ValueError('Normalized indicator or denominator is invalid.')
            elif any(v is not None for v in (wd1,fd1,burden)):
                raise ValueError('Incomplete cell has full-period normalized metrics.')
            for offset in range(0, len(events), 6):
                n,complete,left,right,median,maximum=events[offset:offset+6]
                if (not 0<=complete<=n or not 0<=left<=n or not 0<=right<=n
                        or (complete==0 and (median is not None or maximum is not None))
                        or (complete>0 and not 1<=median<=maximum<=1357)):
                    raise ValueError('Event counts, censor flags or completed-duration values are invalid.')
    if len(seen) != int(np.sum(island>0)): raise ValueError('Cell metric table is incomplete.')


def _spatial_comparisons(arcpy,workspace,grid,settings,cube,island,geometries,scratch):
    """Exact land-area assignment comparison, including the None remainder.

    A positive PolygonToRaster priority is not a tie-only area rule. Intersect
    the fishnet explicitly and choose the largest combined category area.
    """
    import numpy as np
    from datetime import datetime
    from .usdm_spatial import table,BENCHMARK_DATES
    primary=geometries['mainland'].union(geometries['Vieques']).union(geometries['Culebra'])
    total_area=primary.getArea('GEODESIC','SQUAREKILOMETERS')
    fish=str(Path(scratch)/'cells')
    e=grid['extent']
    with arcpy.EnvManager(outputCoordinateSystem=arcpy.SpatialReference(32161),extent=None,mask=None):
        arcpy.management.CreateFishnet(fish,f'{e["xmin"]} {e["ymin"]}',f'{e["xmin"]} {e["ymin"]+250}',
                                      250,250,grid['rows'],grid['columns'],'','NO_LABELS','','POLYGON')
    arcpy.management.AddField(fish,'CELL_ID','LONG')
    with arcpy.da.UpdateCursor(fish,['SHAPE@','CELL_ID']) as cursor:
        for geometry,_ in cursor:
            xy=geometry.trueCentroid
            c=int((xy.X-e['xmin'])/250);r=int((e['ymax']-xy.Y)/250)
            cursor.updateRow((geometry,r*grid['columns']+c))
    # Only cells whose centers belong to the declared primary islands.
    row,col=np.nonzero((island>0)&(island<4));primary_ids=row*grid['columns']+col
    references={}
    with normalized_reader(read_json(settings['manifest'])['statistics'],STAT_SCHEMA) as rows:
        for r in rows:
            day=r['MAP_DATE'].date().isoformat()
            if day in BENCHMARK_DATES and r['GEO_TYPE']=='STATE' and r['STAT_FORMAT']=='CUMULATIVE':
                references[(day,r['CATEGORY'])]=r['VALUE']
    comparison,area_rows=[],[]
    for day in BENCHMARK_DATES:
        arcpy.AddMessage('Spatial assignment/reference comparison: '+day)
        with arcpy.da.SearchCursor(str(Path(workspace)/'pr_weekly_polygons'),['MAP_DATE','DM','SHAPE@']) as cursor:
            polygons=[(int(dm),g.intersect(primary,4)) for stamp,dm,g in cursor
                      if stamp.date().isoformat()==day]
        polygons=[(dm,g) for dm,g in polygons if g.area>0]
        union=None
        for _,g in polygons: union=g if union is None else union.union(g)
        none=primary if union is None else primary.difference(union)
        categories=str(Path(scratch)/'categories');intersection=str(Path(scratch)/'category_cells')
        for path in (categories,intersection):
            if arcpy.Exists(path): arcpy.management.Delete(path)
        arcpy.management.CreateFeatureclass(scratch,'categories','POLYGON',spatial_reference=arcpy.SpatialReference(32161))
        arcpy.management.AddField(categories,'X_CODE','SHORT')
        with arcpy.da.InsertCursor(categories,['X_CODE','SHAPE@']) as cursor:
            if none.area: cursor.insertRow((0,none))
            for dm,g in polygons: cursor.insertRow((dm+1,g))
        arcpy.analysis.PairwiseIntersect([fish,categories],intersection)
        areas=np.zeros((6,grid['rows']*grid['columns']))
        with arcpy.da.SearchCursor(intersection,['CELL_ID','X_CODE','SHAPE@AREA']) as cursor:
            for cell,code,area in cursor: areas[code,cell]+=area
        # Reversed argmax resolves exact equal-area ties toward higher category.
        assigned=5-np.argmax(areas[::-1],axis=0)
        if np.any(areas[:,primary_ids].sum(axis=0)<=0): raise ValueError('Area comparison lost a primary-land cell.')
        index=settings['dates'].index(day);current=cube[index,row,col]
        different=assigned[primary_ids]!=current
        land_areas=areas[:,primary_ids].sum(axis=0)
        comparison.append((datetime.fromisoformat(day),len(primary_ids),int(different.sum()),
                           100*float(np.mean(~different)),float(land_areas[different].sum()/1e6)))
        for dm in range(5):
            polygon_percent=100*sum(g.getArea('GEODESIC','SQUAREKILOMETERS') for d,g in polygons if d>=dm)/total_area
            raster_percent=100*float(np.mean((current>=dm+1)&(current<=5)))
            area_rows.append((datetime.fromisoformat(day),dm,polygon_percent,raster_percent,references[(day,'D'+str(dm))]))
    table(workspace,'cell_assignment_comparison',[('MAP_DATE','DATE',None),('LAND_CELLS','LONG',None),
        ('CHANGED_CELLS','LONG',None),('AGREEMENT_PCT','DOUBLE',None),('CHANGED_LAND_KM2','DOUBLE',None)],comparison)
    table(workspace,'area_reference_comparison',[('MAP_DATE','DATE',None),('MIN_DM','SHORT',None),
        ('POLYGON_PERCENT','DOUBLE',None),('GRID_PERCENT','DOUBLE',None),('API_PERCENT','DOUBLE',None)],area_rows)

