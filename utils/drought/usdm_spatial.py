"""ArcPy preparation of the frozen Puerto Rico weekly drought series."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import time
import zipfile

import numpy as np

from .usdm_common import (read_json, write_json, sha256, table_writer, normalized_reader,
                          utc_now, spatial_source_signature)
from .usdm_archive import has_part_intersection

ENVELOPE = (-68.15, 17.80, -65.10, 18.60)
BENCHMARK_DATES = ('2000-01-04','2012-10-16','2015-08-04','2015-08-11','2025-12-30','2026-01-06')
POLICY = dict(version=1, assessed=['mainland','Vieques','Culebra'],
    partial=['Mona'], basis='Declared PR product scope plus complete municipio chronology; not inferred from drought intersections.',
    scope_url='https://droughtmonitor.unl.edu/Maps/MapArchive/MapAreas.aspx',
    limitations='Generalized Natural Earth coastline; Mona non-polygon weeks remain unknown.',
    overlap_tolerance_m2=1e-6)


def table(workspace, name, fields, rows):
    path = str(Path(workspace)/name)
    with table_writer(path, fields) as write:
        write(dict(zip([f[0] for f in fields], row)) for row in rows)
    return path


def settings_table(workspace, document=None):
    import arcpy
    if document is not None:
        table(workspace, 'processing_settings', [('SETTING','TEXT',64),('VALUE','TEXT',32767)],
              ((k,json.dumps(v,allow_nan=False)) for k,v in document.items()))
        return document
    with arcpy.da.SearchCursor(str(Path(workspace)/'processing_settings'), ['SETTING','VALUE']) as cursor:
        return {k:json.loads(v) for k,v in cursor}


def mark_report(settings, status, **details):
    path = settings['validation_report']
    document = read_json(path)
    document['processing'] = dict(status=status, updated_utc=utc_now(), workspace=settings['workspace'],
        fingerprint=settings.get('fingerprint'), **details)
    write_json(path, document)


def software_hashes():
    return {name:sha256(Path(__file__).with_name(name)) for name in
            ('usdm_spatial.py','usdm_archive.py')}


def boundary_signature(path):
    import arcpy
    digest = hashlib.sha256()
    with arcpy.da.SearchCursor(str(path),['SHAPE@WKB']) as cursor:
        for wkb, in cursor:
            digest.update(bytes(wkb))
    return digest.hexdigest()


def feature_digest(workspace):
    import arcpy
    digest = hashlib.sha256()
    with arcpy.da.SearchCursor(str(Path(workspace)/'pr_weekly_polygons'),
                              ['MAP_DATE','ROLE','DM','X_CODE','SHAPE@WKB']) as cursor:
        for day,role,dm,code,wkb in cursor:
            digest.update(f'{day.isoformat()}|{role}|{dm}|{code}|'.encode())
            digest.update(bytes(wkb))
    return digest.hexdigest()


def dataset_fingerprint(workspace):
    """Read actual normalized values and raster pixels, excluding mutable locks."""
    import arcpy
    digest = hashlib.sha256()
    for name in ('cell_metrics','annual_cell_metrics','drought_events','metric_catalog'):
        path = str(Path(workspace)/name)
        fields = [f.name for f in arcpy.ListFields(path) if f.type != 'OID']
        digest.update((name+'|'+','.join(fields)).encode())
        with arcpy.da.SearchCursor(path,fields) as cursor:
            for row in cursor:
                digest.update(repr(row).encode())
    with arcpy.da.SearchCursor(str(Path(workspace)/'metric_catalog'), ['DATASET']) as cursor:
        names = [r[0] for r in cursor]
    for name in names:
        digest.update(name.encode())
        digest.update(arcpy.RasterToNumPyArray(str(Path(workspace)/name),nodata_to_value=-9999).tobytes())
    return digest.hexdigest()


def publish_raster(workspace, name, array, grid, integer=False):
    import arcpy
    values = np.where(np.isfinite(array), array, -9999).astype(np.int32 if integer else np.float64)
    with arcpy.EnvManager(overwriteOutput=True, extent=None, mask=None, snapRaster=grid['reference_raster'],
                          outputCoordinateSystem=arcpy.SpatialReference(32161), cellSize=250):
        raster = arcpy.NumPyArrayToRaster(values, arcpy.Point(grid['extent']['xmin'],grid['extent']['ymin']),
                                         250,250,-9999)
        raster.save(str(Path(workspace)/name))
        del raster
        arcpy.management.DefineProjection(str(Path(workspace)/name), arcpy.SpatialReference(32161))


def load_workspace(processing_workspace, require_metrics=False):
    workspace = str(Path(processing_workspace).resolve())
    settings = settings_table(workspace)
    if settings['software'] != software_hashes():
        raise ValueError('Drought software changed; rerun Prepare Drought States.')
    if (sha256(settings['grid_spec']) != settings['grid_sha256']
            or spatial_source_signature(read_json(settings['manifest'])) != settings['source_data_sha256']):
        raise ValueError('Grid or acquisition manifest changed; rerun Prepare Drought States.')
    grid = read_json(settings['grid_spec'])
    if sha256(grid['mask_raster']) != settings['mask_sha256']:
        raise ValueError('Study mask changed; rerun preparation.')
    if boundary_signature(grid['projected_boundary']) != settings.get('boundary_sha256'):
        raise ValueError('Study boundary changed; rerun preparation.')
    cube_path = Path(workspace).parent/'drought_weekly_cube.npz'
    if sha256(cube_path) != settings['cube_sha256'] or feature_digest(workspace) != settings['polygons_sha256']:
        raise ValueError('Prepared cube or polygons changed; rerun preparation.')
    with np.load(cube_path,allow_pickle=False) as archive:
        cube, island = archive['states'], archive['island']
        if str(archive['fingerprint']) != settings['fingerprint']:
            raise ValueError('Weekly cube fingerprint differs from its preparation settings.')
        if archive['dates'].tolist() != settings['dates'] or archive['roles'].tolist() != settings['roles']:
            raise ValueError('Cube dates or baseline/buffer roles changed.')
    from .usdm_metrics import check_states
    check_states(cube)
    if cube.shape != (1360,grid['rows'],grid['columns']) or island.shape != cube.shape[1:]:
        raise ValueError('Cube dimensions differ from the frozen calendar/grid.')
    if require_metrics and settings.get('stage') not in ('METRICS_READY','VALIDATED'):
        raise ValueError('Calculate Drought Metrics must complete first.')
    if require_metrics and sha256(Path(__file__).with_name('usdm_metrics.py')) != settings.get('metrics_software_sha256'):
        raise ValueError('Metric calculation code changed; recalculate metrics before evaluation.')
    settings.update(workspace=workspace, cube=str(cube_path))
    return workspace, settings, grid, cube, island


def _islands(arcpy, grid, scratch):
    from ..shared.grid import ISLAND_POINTS
    target = arcpy.SpatialReference(32161)
    controls = {name:arcpy.PointGeometry(arcpy.Point(*xy),arcpy.SpatialReference(4326)).projectAs(
        target,grid['geographic_transformation']) for name,xy in ISLAND_POINTS.items()}
    geometries = {}
    with arcpy.da.SearchCursor(grid['projected_boundary'],['SHAPE@']) as cursor:
        for geometry, in cursor:
            for part in geometry:
                polygon = arcpy.Polygon(part,target)
                for name,point in controls.items():
                    if polygon.contains(point) or polygon.touches(point):
                        if name in geometries:
                            raise ValueError('Boundary island parts are ambiguous.')
                        geometries[name] = polygon
    if set(geometries) != set(controls):
        raise ValueError('Boundary must have separately identifiable mainland, Vieques, Culebra and Mona parts.')
    fc = str(Path(scratch)/'islands')
    arcpy.management.CreateFeatureclass(scratch,'islands','POLYGON',spatial_reference=target)
    arcpy.management.AddField(fc,'REGION_ID','SHORT')
    with arcpy.da.InsertCursor(fc,['REGION_ID','SHAPE@']) as cursor:
        for index,name in enumerate(ISLAND_POINTS,1):
            cursor.insertRow((index,geometries[name]))
    path = str(Path(scratch)/'island_raster')
    with arcpy.EnvManager(outputCoordinateSystem=target,extent=arcpy.Describe(grid['reference_raster']).extent,
                          snapRaster=grid['reference_raster'],cellSize=250,mask=None):
        arcpy.conversion.PolygonToRaster(fc,'REGION_ID',path,'CELL_CENTER','',250)
    array = arcpy.RasterToNumPyArray(path,nodata_to_value=0).astype(np.uint8)
    mask = arcpy.RasterToNumPyArray(grid['mask_raster'],nodata_to_value=0)
    if not np.array_equal(array>0,mask==1):
        raise ValueError('Island allocation differs from the shared land mask.')
    return array,geometries,controls


def _assessment_evidence(manifest):
    from .usdm_statistics import STAT_SCHEMA, MUNICIPIOS
    expected = {r['map_date'] for r in manifest['gis']}
    observed = {geo:set() for geo in MUNICIPIOS}
    with normalized_reader(manifest['statistics'],STAT_SCHEMA) as rows:
        for row in rows:
            if row['GEO_TYPE']=='MUNICIPIO' and row['CATEGORY']=='NONE':
                observed[row['GEO_ID']].add(row['MAP_DATE'].date().isoformat())
    if any(days != expected for days in observed.values()):
        raise ValueError('Declared assessed islands require the complete municipio/date reference chronology.')
    return dict(POLICY, municipio_chronology='All 78 municipios present for all 1,360 dates; values are not used for spatial fill.',
                island_ids={'mainland':1,'Vieques':2,'Culebra':3,'Mona':4})


def _week(arcpy, entry, grid, scratch, directory):
    """Clip original Esri geometries, preserving original ring topology."""
    source = Path(directory)/'weekly.shp'
    with zipfile.ZipFile(entry['path']) as archive:
        for member in archive.namelist():
            name = Path(member).name
            suffix = name[name.find('.'):]
            (Path(directory)/('weekly'+suffix)).write_bytes(archive.read(member))
    sr = arcpy.Describe(str(source)).spatialReference
    if sr.name == 'Unknown':
        raise ValueError('Source shapefile has no usable coordinate system.')
    for name in ('clipped','projected','land','dissolved','weekly_raster'):
        path = str(Path(scratch)/name)
        if arcpy.Exists(path): arcpy.management.Delete(path)
    # Native bbox clipping precedes projection of national multipart geometry.
    box = arcpy.Polygon(arcpy.Array([arcpy.Point(ENVELOPE[0],ENVELOPE[1]),arcpy.Point(ENVELOPE[2],ENVELOPE[1]),
         arcpy.Point(ENVELOPE[2],ENVELOPE[3]),arcpy.Point(ENVELOPE[0],ENVELOPE[3]),arcpy.Point(ENVELOPE[0],ENVELOPE[1])]),arcpy.SpatialReference(4326))
    if sr.factoryCode != 4326:
        transformations = arcpy.ListTransformations(box.spatialReference,sr,box.extent)
        if box.spatialReference.GCS.datumName != sr.GCS.datumName and not transformations:
            raise ValueError('No installed transformation for source clipping.')
        box = box.projectAs(sr,transformations[0] if transformations else None)
    arcpy.management.AddFields(str(source),[['SRC_ROW','LONG'],['X_CODE','SHORT']])
    with arcpy.da.UpdateCursor(str(source),['OID@','DM','SRC_ROW','X_CODE']) as cursor:
        for oid,dm,_,_ in cursor: cursor.updateRow((oid,dm,oid,int(dm)+1))
    clipped, projected, land, dissolved = [str(Path(scratch)/n) for n in ('clipped','projected','land','dissolved')]
    with arcpy.EnvManager(outputCoordinateSystem=sr,extent=None,mask=None,snapRaster=None):
        arcpy.analysis.PairwiseClip(str(source),box,clipped)
    if not int(arcpy.management.GetCount(clipped)[0]):
        return [],None,0,0,{},sr.exportToString()
    transformations = arcpy.ListTransformations(sr,arcpy.SpatialReference(32161),arcpy.Describe(clipped).extent)
    transform = grid['geographic_transformation'] if sr.factoryCode==4326 else (transformations[0] if transformations else '')
    if sr.GCS.datumName != arcpy.SpatialReference(32161).GCS.datumName and not transform:
        raise ValueError('Source-to-grid datum transformation unavailable.')
    arcpy.management.Project(clipped,projected,arcpy.SpatialReference(32161),transform)
    arcpy.analysis.PairwiseClip(projected,grid['projected_boundary'],land)
    n = int(arcpy.management.GetCount(land)[0])
    if not n: return [],None,0,0,{},sr.exportToString()
    check = str(Path(scratch)/'geometry_check')
    if arcpy.Exists(check): arcpy.management.Delete(check)
    arcpy.management.CheckGeometry(land,check)
    issues = int(arcpy.management.GetCount(check)[0])
    if issues:
        arcpy.management.RepairGeometry(land)
        if int(arcpy.management.GetCount(land)[0]) != n:
            raise ValueError('Geometry repair removed a source feature; review required before None fill.')
        arcpy.management.CheckGeometry(land,check)
        if int(arcpy.management.GetCount(check)[0]): raise ValueError('Unresolved geometry issues.')
    lineage = {}
    with arcpy.da.SearchCursor(land,['DM','SRC_ROW']) as cursor:
        for dm,oid in cursor: lineage.setdefault(int(dm),set()).add(int(oid))
    arcpy.management.Dissolve(land,dissolved,['DM','X_CODE'])
    with arcpy.da.SearchCursor(dissolved,['DM','SHAPE@']) as cursor:
        polygons = sorted([(int(dm),g) for dm,g in cursor],key=lambda r:r[0])
    overlap = sum(a.intersect(b,4).area for i,(_,a) in enumerate(polygons) for _,b in polygons[i+1:])
    if overlap > POLICY['overlap_tolerance_m2']:
        raise ValueError(f'{entry["map_date"]}: cross-category overlap {overlap:g} square metres; review source topology.')
    path = str(Path(scratch)/'weekly_raster')
    with arcpy.EnvManager(outputCoordinateSystem=arcpy.SpatialReference(32161),
                          extent=arcpy.Describe(grid['reference_raster']).extent,
                          snapRaster=grid['reference_raster'],cellSize=250,mask=None):
        arcpy.conversion.PolygonToRaster(dissolved,'X_CODE',path,'CELL_CENTER','X_CODE',250)
    values = arcpy.RasterToNumPyArray(path,nodata_to_value=255).astype(np.uint8)
    return polygons,values,issues,overlap,lineage,sr.exportToString()


def prepare_drought_states(validated_drought_data, grid_spec, output_folder, reuse_completed_cache=True):
    import arcpy
    from .usdm_validation import validate_drought_download
    report_path, grid_path = Path(validated_drought_data).resolve(),Path(grid_spec).resolve()
    report = read_json(report_path)
    if not report.get('passed'): raise ValueError('Acquisition validation must pass first.')
    if arcpy.ProductInfo() != 'ArcInfo': raise RuntimeError('This workflow requires ArcGIS Pro Advanced for Polygon To Raster.')
    grid = read_json(grid_path)
    if grid['wkid'] != 32161 or grid['cell_size'] != 250: raise ValueError('Use the EPSG:32161 250 m shared grid.')
    manifest_path = Path(report['download_manifest'])
    manifest = read_json(manifest_path)
    manifest_hash = sha256(manifest_path)
    if (manifest['plan_snapshot']['baseline_count'],manifest['plan_snapshot']['year_count'],len(manifest['gis'])) != (1357,26,1360):
        raise ValueError('Processing requires the complete 2000-2025 baseline and three end buffers.')
    # Actual bytes and primary reference tables are rechecked before cache reuse.
    validate_drought_download(str(manifest_path),str(report_path.parent))
    if sha256(manifest_path) != manifest_hash:
        raise ValueError('Acquisition changed during preparation checks; wait for fetching to finish and rerun.')
    coverage = _assessment_evidence(manifest)
    dates = [r['map_date'] for r in manifest['gis']]
    roles = [r['role'] for r in manifest['gis']]
    if roles != ['BASELINE']*1357+['END_BUFFER']*3: raise ValueError('Unexpected calendar ordering or buffer roles.')
    output = Path(output_folder).resolve()
    for protected in (Path(manifest['cache_folder']).resolve(),Path('Hazard_Variables').resolve()):
        if output.is_relative_to(protected): raise ValueError('Processing outputs must be outside source/cache folders.')
    output.mkdir(parents=True,exist_ok=True)
    workspace = str(output/'drought_processing.gdb')
    identity = dict(source_data_sha256=spatial_source_signature(manifest),grid_sha256=sha256(grid_path),
                    mask_sha256=sha256(grid['mask_raster']),boundary_sha256=boundary_signature(grid['projected_boundary']),
                    software=software_hashes(),coverage_policy=coverage)
    fingerprint = hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    if reuse_completed_cache and arcpy.Exists(str(Path(workspace)/'processing_settings')):
        try:
            previous = settings_table(workspace)
            if previous.get('fingerprint') == fingerprint:
                _,previous,_,cube,_ = load_workspace(workspace)
                previous.update(validation_report=str(report_path),workspace=workspace,
                                manifest=str(manifest_path),manifest_sha256=manifest_hash)
                settings_table(workspace,previous)
                mark_report(previous,'STATES_READY',reused_complete_cache=True,baseline_maps=1357,buffer_maps=3)
                arcpy.AddMessage('Reusing checksum-verified weekly states and prepared polygons.')
                return {'workspace':workspace}
        except (OSError,ValueError,KeyError) as error:
            arcpy.AddWarning(f'Completed spatial cache cannot be reused: {error}')
    if not arcpy.Exists(workspace): arcpy.management.CreateFileGDB(str(output),'drought_processing.gdb')
    settings = dict(identity,workspace=workspace,validation_report=str(report_path),grid_spec=str(grid_path),
        manifest_sha256=manifest_hash,prepared_input_manifest_sha256=manifest_hash,
        prepared_with_software=identity['software'],cache_identity_version=2,
        manifest=str(manifest_path),fingerprint=fingerprint,dates=dates,roles=roles,baseline_count=1357,
        year_count=26,stage='PREPARING',arcgis=arcpy.GetInstallInfo()['Version'],numpy=np.__version__,created_utc=utc_now())
    settings_table(workspace,settings);mark_report(settings,'PREPARING')
    start = time.perf_counter()
    cube_path = output/'drought_weekly_cube.npz'
    temporary_cube = output/'drought_weekly_cube.tmp.npz'
    try:
        with tempfile.TemporaryDirectory(prefix='sdss_drought_spatial_') as temporary:
            scratch = str(Path(temporary)/'scratch.gdb')
            arcpy.management.CreateFileGDB(temporary,'scratch.gdb')
            try:
                with arcpy.EnvManager(extent=None,mask=None,overwriteOutput=True,outputCoordinateSystem=None):
                    island,geometries,controls = _islands(arcpy,grid,scratch)
                    # Validate that the coarse pruning envelope contains the whole study boundary.
                    geographic = arcpy.Describe(grid['projected_boundary']).extent.polygon.projectAs(
                        arcpy.SpatialReference(4326),grid['geographic_transformation']).extent
                    if not (ENVELOPE[0] <= geographic.XMin and geographic.XMax <= ENVELOPE[2]
                            and ENVELOPE[1] <= geographic.YMin and geographic.YMax <= ENVELOPE[3]):
                        raise ValueError('Study boundary extends outside the documented PR search envelope.')
                    cube = np.full((1360,grid['rows'],grid['columns']),255,np.uint8)
                    fc = str(Path(workspace)/'pr_weekly_polygons')
                    if arcpy.Exists(fc): arcpy.management.Delete(fc)
                    arcpy.management.CreateFeatureclass(workspace,'pr_weekly_polygons','POLYGON',spatial_reference=arcpy.SpatialReference(32161))
                    arcpy.management.AddFields(fc,[['MAP_DATE','DATE'],['ROLE','TEXT','',32],['DM','SHORT'],['X_CODE','SHORT']])
                    ledger, audits, lineage_rows, empty, crs_variants = [],[],[],0,set()
                    with arcpy.da.InsertCursor(fc,['MAP_DATE','ROLE','DM','X_CODE','SHAPE@']) as append:
                        for index,entry in enumerate(manifest['gis']):
                            if arcpy.env.isCancelled: raise RuntimeError('Drought preparation cancelled.')
                            cube[index][(island>=1)&(island<=3)] = 0
                            wkt = entry['audit']['source_crs_wkt']
                            sr = arcpy.SpatialReference();sr.loadFromString(wkt)
                            with zipfile.ZipFile(entry['path']) as archive:
                                raw = archive.read(next(n for n in archive.namelist() if n.lower().endswith('.shp')))
                            active = True if sr.factoryCode != 4326 else has_part_intersection(raw,ENVELOPE)
                            del raw
                            polygons,values,issues,overlap,lineage = [],None,0,0,{}
                            if active:
                                with tempfile.TemporaryDirectory(prefix='week_',dir=temporary) as week_dir:
                                    try:
                                        polygons,values,issues,overlap,lineage,wkt = _week(arcpy,entry,grid,scratch,week_dir)
                                    finally:
                                        arcpy.management.ClearWorkspaceCache(week_dir)
                            else: empty += 1
                            if values is not None:
                                if values.shape != island.shape or not np.isin(values,[1,2,3,4,5,255]).all():
                                    raise ValueError('Weekly category raster differs from its grid/encoding.')
                                selected = (values<=5)&(island>0)
                                cube[index][selected] = values[selected]
                            day = datetime.fromisoformat(entry['map_date'])
                            for dm,g in polygons: append.insertRow((day,entry['role'],dm,dm+1,g))
                            for dm,ids in lineage.items(): lineage_rows.append((day,dm,','.join(map(str,sorted(ids)))))
                            crs_hash = hashlib.sha256(wkt.encode()).hexdigest();crs_variants.add(crs_hash)
                            audits.append((day,entry['role'],entry['sha256'],len(polygons),issues,float(overlap),crs_hash))
                            for region,name in enumerate(('mainland','Vieques','Culebra','Mona'),1):
                                vals = cube[index][island==region]
                                ledger.append((day,name,'DECLARED_ASSESSED' if region<4 else 'POSITIVE_ONLY',
                                    int(np.sum(vals<=5)),int(np.sum(vals==0)),int(np.sum(vals==255))))
                            if (index+1)%25==0 or index==1359:
                                arcpy.AddMessage(f'Weekly states: {index+1}/1360; empty-envelope shortcut {empty}.')
                    table(workspace,'weekly_audit',[('MAP_DATE','DATE',None),('ROLE','TEXT',32),('SOURCE_HASH','TEXT',64),
                        ('DM_FEATURES','LONG',None),('GEOMETRY_ISSUES','LONG',None),('OVERLAP_M2','DOUBLE',None),('CRS_HASH','TEXT',64)],audits)
                    table(workspace,'assessment_ledger',[('MAP_DATE','DATE',None),('ISLAND','TEXT',32),('BASIS','TEXT',32),
                        ('N_VALID','LONG',None),('N_NONE','LONG',None),('N_UNKNOWN','LONG',None)],ledger)
                    table(workspace,'polygon_lineage',[('MAP_DATE','DATE',None),('DM','SHORT',None),('SOURCE_ROWS','TEXT',4000)],lineage_rows)
                    with temporary_cube.open('wb') as stream:
                        np.savez_compressed(stream,states=cube,island=island,dates=np.asarray(dates),roles=np.asarray(roles),fingerprint=np.asarray(fingerprint))
                    temporary_cube.replace(cube_path)
            finally:
                arcpy.management.ClearWorkspaceCache()
        settings.update(stage='STATES_READY',cube=str(cube_path),cube_sha256=sha256(cube_path),
                        polygons_sha256=feature_digest(workspace),empty_envelope_weeks=empty,
                        source_crs_hashes=sorted(crs_variants),preparation_seconds=time.perf_counter()-start)
        settings_table(workspace,settings)
        mark_report(settings,'STATES_READY',baseline_maps=1357,buffer_maps=3,coverage_policy=coverage)
        return {'workspace':workspace}
    except Exception as error:
        mark_report(settings,'FAILED',error=str(error))
        raise
    finally:
        temporary_cube.unlink(missing_ok=True)
