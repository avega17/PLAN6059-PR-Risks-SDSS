"""USDM reference-statistic contracts; preserve rather than repair source errors."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import math

from .usdm_common import as_date

API_BASE = 'https://usdmdataservices.unl.edu/api/'
MUNICIPIOS = {f'72{n:03d}' for n in range(1,154,2)} | {'72054'}
CATEGORIES = ('none','d0','d1','d2','d3','d4')
STAT_FIELDS = ['GEO_TYPE','GEO_ID','MAP_DATE','ROLE','VALID_START','VALID_END',
               'METRIC','STAT_FORMAT','CATEGORY','VALUE','UNIT','SOURCE_HASH']
STAT_SCHEMA = [(key,'DATE' if key in ('MAP_DATE','VALID_START','VALID_END') else
                'DOUBLE' if key=='VALUE' else 'TEXT',
                None if key in ('MAP_DATE','VALID_START','VALID_END','VALUE') else
                64 if key=='SOURCE_HASH' else 32) for key in STAT_FIELDS]
QC_FIELDS = ['SEVERITY','CODE','MAP_DATE','GEO_ID','DETAIL']
QC_SCHEMA = [('SEVERITY','TEXT',12),('CODE','TEXT',64),('MAP_DATE','DATE',None),
             ('GEO_ID','TEXT',12),('DETAIL','TEXT',2000)]


def qc(code, detail, date='', geography='72', severity='WARNING'):
    return dict(zip(QC_FIELDS,(severity,code,date,geography,str(detail))))


def statistic_jobs(plan):
    groups = defaultdict(list)
    for row in plan['weeks']:
        groups[row['MAP_DATE'][:4]].append(row['MAP_DATE'])
    jobs = []
    for year, dates in sorted(groups.items()):
        first,last = as_date(min(dates)),as_date(max(dates))
        params = {'aoi':'72','startdate':f'{first.month}/{first.day}/{first.year}',
                  'enddate':f'{last.month}/{last.day}/{last.year}'}
        for format_id in (1,2):
            jobs.append({'id':year+f'_state_{format_id}','kind':'state','format':format_id,
                'endpoint':API_BASE+'StateStatistics/GetDroughtSeverityStatisticsByAreaPercent',
                'params':dict(params,statisticsType=format_id),'dates':sorted(dates)})
        jobs.append({'id':year+'_dsci','kind':'dsci','format':None,
                'endpoint':API_BASE+'StateStatistics/GetDSCI','params':params,'dates':sorted(dates)})
        if plan['include_municipio_statistics']:
            jobs.append({'id':year+'_municipio','kind':'municipio','format':2,
                'endpoint':API_BASE+'CountyStatistics/GetDroughtSeverityStatisticsByAreaPercent',
                'params':dict(params,aoi='PR',statisticsType=2),'dates':sorted(dates)})
    return jobs


def finite_value(value, maximum):
    if value is None or isinstance(value,bool):
        raise ValueError('Missing or boolean statistic value')
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= maximum:
        raise ValueError('Statistic value is non-finite or out of range')
    return number


def normalize_payload(payload, job, roles, source_hash):
    if not isinstance(payload,list):
        raise ValueError('Statistics payload must be an array')
    expected = set(job['dates'])
    seen, rows, warnings = {}, [], []
    outside, identical = 0,0
    for raw in payload:
        if not isinstance(raw,dict) or 'mapDate' not in raw:
            raise ValueError('Statistics record lacks a map date')
        day = as_date(raw['mapDate']).isoformat()
        if day not in expected:
            outside += 1
            continue
        if as_date(day).weekday()!=1:
            raise ValueError('Statistic map date is not Tuesday')
        if job['kind']=='municipio':
            geo = raw.get('fips')
            if not isinstance(geo,str) or geo not in MUNICIPIOS or raw.get('state')!='PR':
                raise ValueError('Unexpected municipio FIPS or state')
        else:
            geo = '72'
            if ((job['kind']=='dsci' and raw.get('name')!='Puerto Rico') or
                (job['kind']=='state' and raw.get('stateAbbreviation')!='PR')):
                raise ValueError('Statistics response is not Puerto Rico')
        if job['format'] and raw.get('statisticFormatID') != job['format']:
            raise ValueError('Statistics format selector differs from request')
        key = (geo,day)
        if key in seen:
            if seen[key] != raw:
                raise ValueError(f'Conflicting duplicate statistic: {key}')
            identical += 1
            continue
        seen[key] = raw
        base = {'GEO_TYPE':'MUNICIPIO' if job['kind']=='municipio' else 'STATE',
            'GEO_ID':geo,'MAP_DATE':day,'ROLE':roles[day],
            'VALID_START':raw.get('validStart') or '', 'VALID_END':raw.get('validEnd') or '',
            'SOURCE_HASH':source_hash}
        for value in (base['VALID_START'],base['VALID_END']):
            if value:
                datetime.fromisoformat(value)
        if job['kind']=='dsci':
            rows.append(dict(base,METRIC='DSCI',STAT_FORMAT='INDEX',CATEGORY='',
                             VALUE=finite_value(raw.get('dsci'),500),UNIT='INDEX_POINTS'))
        else:
            values = {field:finite_value(raw.get(field),100) for field in CATEGORIES}
            if job['format']==1:
                sequence = [values['d'+str(k)] for k in range(5)]
                if any(a < b for a,b in zip(sequence,sequence[1:])):
                    raise ValueError(f'Non-monotonic cumulative statistics: {day} {geo}')
                error = abs(values['none']+values['d0']-100)
            else:
                error = abs(sum(values.values())-100)
            if error > .035:
                warnings.append(qc('CATEGORY_TOTAL_DISAGREEMENT',f'Total deviation {error:.4f} percentage points; raw values retained.',day,geo))
            for category,value in values.items():
                rows.append(dict(base,METRIC='AREA_PERCENT',
                    STAT_FORMAT='CUMULATIVE' if job['format']==1 else 'CATEGORICAL',
                    CATEGORY=category.upper() if category!='none' else 'NONE',VALUE=value,UNIT='PERCENT_AREA'))
    expected_keys = {(geo,day) for day in expected for geo in (MUNICIPIOS if job['kind']=='municipio' else {'72'})}
    if set(seen)!=expected_keys:
        raise ValueError(f'Incomplete/unexpected geography-date records for {job["id"]}: missing {len(expected_keys-set(seen))}, extra {len(set(seen)-expected_keys)}')
    return rows,warnings,seen,{'excluded_overlap_records':outside,'identical_duplicates_removed':identical}


def compare_state_formats(state):
    warnings = []
    for day,formats in sorted(state.items()):
        cumulative, categorical, dsci = formats.get('1'),formats.get('2'),formats.get('dsci')
        if cumulative is None or categorical is None or dsci is None:
            raise ValueError('A state date lacks one of the three reference products')
        mismatch = max(abs(sum(float(categorical['d'+str(j)]) for j in range(k,5))
                           -float(cumulative['d'+str(k)])) for k in range(5))
        if mismatch > .035:
            warnings.append(qc('CROSS_FORMAT_DISAGREEMENT',f'Max difference {mismatch:.4f} percentage points; do not renormalize.',day))
        for label,total in (('cumulative',sum(float(cumulative['d'+str(k)]) for k in range(5))),
                            ('categorical',sum((k+1)*float(categorical['d'+str(k)]) for k in range(5)))):
            if abs(float(dsci['dsci'])-total) > .55:
                warnings.append(qc('DSCI_DISAGREEMENT',f'{label} calculation differs from returned DSCI by more than 0.55 units.',day))
    return warnings
