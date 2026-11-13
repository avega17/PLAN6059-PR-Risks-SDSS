"""Execute a USDM acquisition plan; never infer drought from missing files."""
from __future__ import annotations

from pathlib import Path
import shutil
import uuid
from urllib.parse import urlencode

from .usdm_archive import inspect_zip
from .usdm_catalog import CATALOG_URL, parse_catalog
from .usdm_common import (DroughtAcquisitionError, VERSION, protect_source, normalized_writer,
                          read_json, sha256, utc_now, write_json)
from .usdm_http import HttpCache
from .usdm_statistics import (QC_SCHEMA, STAT_SCHEMA,
                             compare_state_formats, normalize_payload, qc, statistic_jobs)


def json_array(path):
    payload = read_json(path)
    if not isinstance(payload,list):
        raise ValueError('Statistics body is not an array')
    return {'row_count':len(payload)}


def validate_plan(plan):
    from .usdm_catalog import make_calendar
    if plan.get('schema_version')!=1 or plan.get('state_fips')!='72':
        raise ValueError('Unsupported download plan or geography')
    calendar = make_calendar(plan['start_date'],plan['end_date'],plan['recovery_buffer_weeks'],plan['mode'])
    for key in ('weeks','baseline_count','year_count','effective_start','effective_end'):
        if calendar[key]!=plan[key]:
            raise ValueError(f'Download plan cohort has been changed inconsistently: {key}')


def fetch_drought_data(download_plan, cache_folder, output_folder, resume=True,
                       publish_tables=False, progress=None, cancelled=None,
                       http_cache=None, offline=False, export_csv=False):
    plan_path = Path(download_plan).expanduser().resolve()
    plan = read_json(plan_path)
    validate_plan(plan)
    output = Path(output_folder).expanduser().resolve()
    cache = Path(cache_folder).expanduser().resolve()
    for folder in (output,cache):
        protect_source(plan.get('local_archive_folder'),folder)
    output.mkdir(parents=True,exist_ok=True)
    cache.mkdir(parents=True,exist_ok=True)
    client = http_cache or HttpCache(cache,resume=resume,offline=offline)
    if client.folder != cache:
        raise ValueError('HTTP cache root differs from requested Cache Folder')
    manifest_path = output/'download_manifest.json'
    manifest = {'schema_version':1,'created_utc':utc_now(),'software_version':VERSION,
        'scope':'Acquisition only; not a drought raster or hazard rank.',
        'status':'running','acquisition_status':'RUNNING','reference_qc_status':'NOT_CHECKED',
        'download_plan':str(plan_path),'download_plan_sha256':sha256(plan_path),
        'plan_snapshot':plan,'cache_folder':str(cache),'output_folder':str(output),
        'gis':[],'statistics_requests':[],'documents':[],'errors':[],
        'manifest':str(manifest_path)}
    write_json(manifest_path,manifest)
    warnings = []
    canonical = output/'statistics_canonical.csv'
    statistics = str(output/'drought_acquisition.gdb/statistics') if publish_tables else str(canonical)
    qc_table = str(output/'drought_acquisition.gdb/acquisition_qc') if publish_tables else str(output/'acquisition_qc.csv')
    state = {}
    roles = {row['MAP_DATE']:row['ROLE'] for row in plan['weeks']}

    def note(message):
        if progress:
            progress(message)

    def check_cancel():
        if cancelled and cancelled():
            raise DroughtAcquisitionError('Acquisition cancelled; verified cache files retained.')

    try:
        check_cancel()
        catalog = client.get(CATALOG_URL,'html',lambda p:parse_catalog(p.read_text(encoding='utf-8')))
        entries = catalog.pop('audit')
        manifest['catalog'] = catalog
        missing = [day for day in roles if day not in entries]
        if missing:
            raise ValueError(f'Provider directory lacks {len(missing)} required dates, including {missing[:3]}')
        manifest['listed_compressed_bytes'] = sum(entries[day]['listed_bytes'] for day in roles)
        # These receipts make the provider's product/permission caveats reviewable offline.
        for url in ('https://droughtmonitor.unl.edu/DmData/Metadata.aspx',
                    'https://droughtmonitor.unl.edu/About/Permission.aspx'):
            check_cancel()
            receipt = client.get(url,'html',lambda p:{'nonempty':p.stat().st_size>0})
            receipt.pop('audit',None)
            manifest['documents'].append(receipt)
        total = len(plan['weeks'])
        for index,row in enumerate(plan['weeks'],1):
            check_cancel()
            day = row['MAP_DATE']
            entry = dict(entries[day],role=row['ROLE'])
            local = plan['local_candidates'].get(day,[])
            if local:
                candidate = local[0]
                source = Path(candidate['path'])
                if sha256(source)!=candidate['sha256']:
                    raise ValueError(f'Local source changed after planning: {source}')
                audit = inspect_zip(source,day)
                target = cache/'objects'/candidate['sha256'][:2]/(candidate['sha256']+'.zip')
                target.parent.mkdir(parents=True,exist_ok=True)
                repaired_cache_path = None
                if not target.exists() or sha256(target)!=candidate['sha256']:
                    if target.exists():
                        quarantine = cache/'quarantine'/(target.name+'.'+uuid.uuid4().hex)
                        quarantine.parent.mkdir(parents=True,exist_ok=True)
                        target.replace(quarantine)
                        repaired_cache_path = str(quarantine)
                    shutil.copy2(source,target)
                if sha256(target)!=candidate['sha256'] or sha256(source)!=candidate['sha256']:
                    raise ValueError('Local archive copy/source checksum differs')
                entry.update(path=str(target),sha256=candidate['sha256'],bytes=target.stat().st_size,
                    source_kind='LOCAL_COPY',original_path=str(source),original_sha256=candidate['sha256'],
                    acquired_utc=None,source_url=None,provider_content_equivalence_verified=False,audit=audit,
                    repaired_cache_path=repaired_cache_path)
            else:
                receipt = client.get(entry['url'],'zip',lambda p,day=day:inspect_zip(p,day))
                entry.update(receipt,source_kind='HTTP',source_url=entry['url'])
                if entry['bytes']!=entries[day]['listed_bytes']:
                    warnings.append(qc('CATALOG_SIZE_CHANGED','Download differs from frozen catalog size; hash recorded.',day))
            if entry['audit']['duplicate_dm_categories']:
                warnings.append(qc('MULTIPLE_DM_FEATURES','More than one feature for a DM class; topology review still required.',day))
            manifest['gis'].append(entry)
            if index%20==0 or index==total:
                note(f'GIS archives verified: {index}/{total}')
                write_json(manifest_path,manifest)
        normalized_rows = 0
        with normalized_writer(statistics, STAT_SCHEMA, publish_tables) as write_rows:
            for job in statistic_jobs(plan):
                check_cancel()
                url = job['endpoint']+'?'+urlencode(job['params'])
                receipt = client.get(url,'json',json_array,accept='application/json')
                payload = read_json(receipt['path'])
                rows,issues,seen,counts = normalize_payload(payload,job,roles,receipt['sha256'])
                warnings.extend(issues)
                write_rows(rows)
                normalized_rows += len(rows)
                if job['kind']!='municipio':
                    label = 'dsci' if job['kind']=='dsci' else str(job['format'])
                    for (_,day),record in seen.items():
                        state.setdefault(day,{})[label] = record
                receipt.update(job=job,normalization=counts,normalized_rows=len(rows))
                receipt.pop('audit',None)
                manifest['statistics_requests'].append(receipt)
                note(f'Statistics verified: {job["id"]} ({len(seen)} geography/date records)')
                write_json(manifest_path,manifest)
        warnings.extend(compare_state_formats(state))
        with normalized_writer(qc_table, QC_SCHEMA, publish_tables) as write_rows:
            write_rows(warnings)
        canonical_export = qc_export = None
        if publish_tables and export_csv:
            import arcpy
            with arcpy.EnvManager(overwriteOutput=True):
                arcpy.conversion.ExportTable(statistics, str(canonical))
                arcpy.conversion.ExportTable(qc_table, str(output/'acquisition_qc.csv'))
            canonical_export, qc_export = str(canonical), str(output/'acquisition_qc.csv')
        elif not publish_tables:
            canonical_export, qc_export = statistics, qc_table
        manifest.update(status='complete',acquisition_status='COMPLETE',
            reference_qc_status='WARNINGS' if warnings else 'PASS',completed_utc=utc_now(),
            statistics=statistics,qc=qc_table,canonical_csv=canonical_export,qc_csv=qc_export,
            canonical_sha256=sha256(canonical_export) if canonical_export else None,
            qc_sha256=sha256(qc_export) if qc_export else None,
            normalized_rows=normalized_rows,warnings=warnings,
            baseline_gis_count=sum(e['role']=='BASELINE' for e in manifest['gis']),
            buffer_gis_count=sum(e['role']!='BASELINE' for e in manifest['gis']),
            network_requests=client.network_requests,
            limitations=['No historical geometry-topology or assessed-domain validation has been performed.',
                        'NoData/None must be resolved before rasterization or duration metrics.',
                        'Reference statistics disagreements are retained; no values were renormalized.'])
        write_json(manifest_path,manifest)
        note(f'Acquisition complete: {manifest["baseline_gis_count"]} baseline maps, {manifest["buffer_gis_count"]} buffers; {len(warnings)} reference warnings.')
        return manifest
    except Exception as error:
        manifest.update(status='failed',acquisition_status='FAILED',failed_utc=utc_now(),
                        network_requests=client.network_requests)
        manifest['errors'].append(str(error))
        manifest['warnings'] = warnings
        write_json(manifest_path,manifest)
        raise DroughtAcquisitionError(f'{error}. Diagnostic manifest: {manifest_path}') from error
