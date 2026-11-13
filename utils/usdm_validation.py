"""Revalidate acquired bytes, statistics and chronology without network access."""
from __future__ import annotations

import csv
from pathlib import Path

from .usdm_archive import inspect_zip
from .usdm_common import DroughtAcquisitionError, read_json, sha256, utc_now, write_json
from .usdm_download import validate_plan
from .usdm_statistics import STAT_FIELDS, compare_state_formats, normalize_payload, statistic_jobs


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
        with Path(manifest['canonical_csv']).open(newline='',encoding='utf-8') as stream:
            canonical = csv.DictReader(stream)
            check('Canonical table schema matches the contract',canonical.fieldnames==STAT_FIELDS)
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
                    if recorded != {key:str(row[key]) for key in STAT_FIELDS}:
                        mismatches += 1
                    expected_rows += 1
            check('Canonical table contains no extra rows',next(canonical,None) is None)
        check('Every canonical value is reproducible from frozen raw statistics',mismatches==0,{'mismatches':mismatches})
        check('Normalized row count reconciles',expected_rows==manifest['normalized_rows'],expected_rows)
        check('Canonical and QC file hashes match',sha256(manifest['canonical_csv'])==manifest['canonical_sha256']
              and sha256(manifest['qc_csv'])==manifest['qc_sha256'])
        cross_warnings = compare_state_formats(state)
        expected_warnings = warnings+cross_warnings
        # Archive warnings are transport/schema observations, not source-statistic repairs.
        recorded_stat_warnings = [w for w in manifest['warnings'] if w['CODE'] not in
                                  ('CATALOG_SIZE_CHANGED','MULTIPLE_DM_FEATURES')]
        check('Reference disagreements are retained and reproducible',expected_warnings==recorded_stat_warnings)
        if manifest['statistics'].endswith('.gdb/statistics') or '.gdb\\' in manifest['statistics']:
            import arcpy
            with arcpy.EnvManager(extent=None,mask=None):
                check('Published Statistics table row count matches canonical CSV',
                    int(arcpy.management.GetCount(manifest['statistics'])[0])==expected_rows)
                check('Published QC table row count matches recorded warnings',
                    int(arcpy.management.GetCount(manifest['qc'])[0])==len(manifest['warnings']))
        report.update(baseline_maps=plan['baseline_count'],buffer_maps=len(expected)-plan['baseline_count'],
            mode=plan['mode'],year_count=plan['year_count'],normalized_rows=expected_rows,
            reference_warning_count=len(manifest['warnings']),source_crs_variants=sorted(projections),
            outstanding=['Verify historical assessed-domain/island coverage, especially Mona.',
                'Check polygon topology and actual ArcPy projection/repair behavior before temporal rasters.',
                'None=0, D0=1,...,D4=5; unknown=255 must be masked out of threshold calculations.',
                'Frequency and event duration are hazard metrics; final ranking follows their evaluation.'])
    except Exception as error:
        check('Validation completed without an unreadable or invalid artifact',False,str(error))
    report['passed'] = bool(checks) and all(c['passed'] for c in checks)
    report['report'] = str(report_path)
    write_json(report_path,report)
    lines = ['# Drought download validation','',f'Passed: **{report["passed"]}**','',
             'This checks acquisition, not scientific drought skill or raster readiness.','']
    lines.extend(f'- {"PASS" if c["passed"] else "FAIL"}: {c["check"]}' for c in checks)
    lines.extend(['','## Outstanding processing gates','']+[f'- {x}' for x in report.get('outstanding',[])])
    (output/'download_validation.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if not report['passed']:
        raise DroughtAcquisitionError(f'Download validation failed. Review {report_path}')
    return report

