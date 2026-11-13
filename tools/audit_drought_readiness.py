"""Small ArcPy geometry/raster feasibility audit; never fills unverified None land.

The partial category rasters are diagnostics, not complete weekly USDM states
or frequency/duration/hazard-rank products.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from utils.usdm_archive import inspect_zip
from utils.usdm_common import read_json, sha256, utc_now, write_json


def audit(manifest_path, grid_spec, output_folder, sample_folder=None):
    import arcpy
    import numpy as np
    manifest, spec = read_json(manifest_path),read_json(grid_spec)
    output = Path(output_folder).resolve(); output.mkdir(parents=True,exist_ok=True)
    gdb = output/'pilot.gdb'
    if not arcpy.Exists(str(gdb)):
        arcpy.management.CreateFileGDB(str(output),gdb.name)
    target = arcpy.SpatialReference(spec['wkid'])
    boundary = arcpy.Describe(spec['projected_boundary'])
    land_geometries = [row[0] for row in arcpy.da.SearchCursor(spec['projected_boundary'],['SHAPE@'])]
    land_area = sum(g.area for g in land_geometries)
    entries = {e['map_date']:e for e in manifest['gis']}
    chosen = ['2000-01-04','2015-08-04','2015-08-11']
    largest = max(manifest['gis'],key=lambda e:e['audit']['record_count'])['map_date']
    if largest not in chosen:
        chosen.append(largest)
    if sample_folder:
        chosen.extend(['2026-01-06','2026-08-04'])
        for day in chosen[-2:]:
            path=Path(sample_folder)/('USDM_'+day.replace('-','')+'_M.zip')
            entries[day]={'path':str(path),'sha256':sha256(path),'source_kind':'LOCAL_PILOT_ONLY'}
    controls={'mainland':(-66.45,18.22),'Vieques':(-65.433,18.126),
              'Culebra':(-65.3034,18.3133),'Mona':(-67.90,18.08)}
    mask = arcpy.RasterToNumPyArray(spec['mask_raster'],nodata_to_value=255)
    report={'created_utc':utc_now(),'download_manifest':str(manifest_path),
        'arcgis_version':arcpy.GetInstallInfo()['Version'],'license':arcpy.ProductInfo(),
        'download_status_at_audit':manifest['status'],'samples':[],
        'scope':'Feasibility only. Unmapped land remains unknown; no frequency, duration or ranks calculated.'}
    for day in chosen:
        entry=entries[day]; source=Path(entry['path'])
        assert sha256(source)==entry['sha256']
        inspected=inspect_zip(source,day)
        folder=output/day.replace('-',''); folder.mkdir(exist_ok=True)
        with zipfile.ZipFile(source) as archive:
            # inspect_zip rejected traversal, links, duplicate names and excessive size.
            archive.extractall(folder)
        raw=str(next(folder.glob('*.shp')))
        source_sr=arcpy.Describe(raw).spatialReference
        if source_sr.name=='Unknown':raise ValueError('Unknown source CRS')
        native_boundary=str(gdb/('boundary_'+day.replace('-','')))
        native_clip=str(gdb/('clip_'+day.replace('-','')))
        projected=str(gdb/('projected_'+day.replace('-','')))
        transforms=arcpy.ListTransformations(boundary.spatialReference,source_sr,boundary.extent)
        to_source=transforms[0] if transforms else ''
        with arcpy.EnvManager(extent=None,mask=None,snapRaster=None,outputCoordinateSystem=None,overwriteOutput=True):
            arcpy.management.Project(spec['projected_boundary'],native_boundary,source_sr,to_source)
            arcpy.analysis.PairwiseClip(raw,native_boundary,native_clip)
            transforms=arcpy.ListTransformations(source_sr,target,arcpy.Describe(native_boundary).extent)
            to_target=transforms[0] if transforms else ''
            arcpy.management.Project(native_clip,projected,target,to_target)
            check_table=str(gdb/('geometry_'+day.replace('-','')))
            arcpy.management.CheckGeometry(projected,check_table)
            issues=int(arcpy.management.GetCount(check_table)[0])
            geometries=list(arcpy.da.SearchCursor(projected,['DM','SHAPE@']))
            arcpy.management.AddField(projected,'ENCODED','SHORT')
            with arcpy.da.UpdateCursor(projected,['DM','ENCODED']) as cursor:
                for row in cursor:
                    row[1]=int(row[0])+1;cursor.updateRow(row)
        overlap_area=0.
        for i,(level,geometry) in enumerate(geometries):
            for other_level,other in geometries[i+1:]:
                if level!=other_level:
                    overlap_area+=geometry.intersect(other,4).area
        raster_path=str(output/(day.replace('-','')+'_partial_categories250.tif'))
        if geometries:
            temporary_raster=str(folder/'categories_raw.tif')
            with arcpy.EnvManager(outputCoordinateSystem=target,cellSize=250,
                                  snapRaster=spec['reference_raster'],extent=spec['reference_raster'],
                                  mask=None,overwriteOutput=True):
                arcpy.conversion.PolygonToRaster(projected,'ENCODED',temporary_raster,'CELL_CENTER','',250)
            array=arcpy.RasterToNumPyArray(temporary_raster,nodata_to_value=255)
        else:
            array=np.full((spec['rows'],spec['columns']),255,dtype=np.uint8)
        assert array.shape==mask.shape==(spec['rows'],spec['columns'])
        array=np.where(mask==1,array,255).astype(np.uint8)
        raster=arcpy.NumPyArrayToRaster(array,arcpy.Point(spec['extent']['xmin'],spec['extent']['ymin']),250,250,255)
        with arcpy.EnvManager(overwriteOutput=True):raster.save(raster_path)
        arcpy.management.DefineProjection(raster_path,target)
        actual=arcpy.Raster(raster_path)
        assert actual.width==spec['columns'] and actual.height==spec['rows']
        assert actual.meanCellWidth==actual.meanCellHeight==250
        assert np.all(array[mask!=1]==255)
        matches={}
        for name,(x,y) in controls.items():
            point=arcpy.PointGeometry(arcpy.Point(x,y),arcpy.SpatialReference(4326)).projectAs(target,to_target)
            matches[name]=[int(level) for level,geom in geometries if geom.contains(point)]
        areas={str(level):sum(geom.area for lev,geom in geometries if lev==level) for level,_ in geometries}
        report['samples'].append({'map_date':day,'raw_zip_sha256':entry['sha256'],
            'source_crs':source_sr.name,'source_wkid':source_sr.factoryCode,
            'to_source_transformation':to_source,'to_target_transformation':to_target,
            'projected_feature_count':len(geometries),'geometry_issues':issues,
            'cross_category_overlap_square_meters':overlap_area,
            'source_dm_area_square_meters':areas,'provisional_boundary_area_square_meters':land_area,
            'known_dry_category_fraction_of_boundary':sum(areas.values())/land_area,
            'control_raw_dm_matches':matches,'partial_raster':raster_path,
            'raster_values':np.unique(array).tolist(),
            'land_cells_with_source_category':int(np.sum((mask==1)&(array!=255))),
            'land_cells_unresolved_none_or_unassessed':int(np.sum((mask==1)&(array==255))),
            'raster_alignment_passed':True,'source_unchanged':sha256(source)==entry['sha256']})
        print(day,'geometry issues',issues,'overlap m2',overlap_area,flush=True)
    report['geometry_pilot_passed']=all(s['geometry_issues']==0 and s['cross_category_overlap_square_meters']<.1 for s in report['samples'])
    report['ready_for_controlled_raster_pilot']=report['geometry_pilot_passed']
    report['ready_for_full_frequency_duration']=False
    report['ready_for_final_hazard_ranking']=False
    write_json(output/'readiness_audit.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--grid-spec',required=True)
    parser.add_argument('--output-folder',required=True)
    parser.add_argument('--sample-folder')
    args=parser.parse_args()
    audit(args.manifest,args.grid_spec,args.output_folder,args.sample_folder)
