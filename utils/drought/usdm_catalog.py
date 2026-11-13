"""Offline planning of USDM map-date cohorts and local archive candidates."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse

from .usdm_archive import ZIP_DATE, archive_date
from .usdm_common import VERSION, as_date, protect_source, sha256, utc_now, write_json

FIRST_MAP = date(2000,1,4)
CATALOG_URL = 'https://droughtmonitor.unl.edu/Data/shapefiles_m/'


def make_calendar(start_date, end_date, buffer_weeks=3, mode='Baseline', today=None):
    start, end = as_date(start_date), as_date(end_date)
    today = today or date.today()
    mode = str(mode).casefold()
    if mode not in ('baseline','pilot'):
        raise ValueError('Mode must be Baseline or Pilot')
    if start > end or start < date(2000,1,1):
        raise ValueError('USDM dates must be ordered and start on or after 2000-01-01')
    if end > today:
        raise ValueError('End Date cannot be in the future')
    if mode == 'baseline' and ((start.month,start.day)!=(1,1) or (end.month,end.day)!=(12,31)
                               or end.year >= today.year):
        raise ValueError('Baseline mode requires complete calendar years ending before the current year')
    if not 0 <= int(buffer_weeks) <= 12:
        raise ValueError('Recovery Buffer Weeks must be between 0 and 12')
    current = start + timedelta(days=(1-start.weekday())%7)
    baseline = []
    while current <= end:
        if current >= FIRST_MAP:
            baseline.append(current)
        current += timedelta(days=7)
    if not baseline:
        raise ValueError('The requested interval contains no available Tuesday map date')
    weeks = [{'MAP_DATE':str(day),'ROLE':'BASELINE'} for day in baseline]
    unavailable_start = []
    for n in range(1,int(buffer_weeks)+1):
        prior, following = baseline[0]-timedelta(weeks=n), baseline[-1]+timedelta(weeks=n)
        if prior < FIRST_MAP:
            unavailable_start.append(str(prior))
        else:
            weeks.append({'MAP_DATE':str(prior),'ROLE':'START_BUFFER'})
        if following > today:
            raise ValueError('Requested recovery buffers extend into the future; shorten the pilot or buffer')
        weeks.append({'MAP_DATE':str(following),'ROLE':'END_BUFFER'})
    return {'start_date':str(start),'end_date':str(end),'mode':mode.title(),
            'baseline_count':len(baseline),'year_count':end.year-start.year+1 if mode=='baseline' else None,
            'effective_start':str(baseline[0]),'effective_end':str(baseline[-1]),
            'weeks':sorted(weeks,key=lambda row:row['MAP_DATE']),
            'unavailable_start_buffer_dates':sorted(unavailable_start),
            'left_boundary_censoring_possible':bool(unavailable_start)}


def parse_catalog(html):
    entries = {}
    for size, href in re.findall(r'(\d+)\s+<a\s+href=["\']([^"\']+)["\']',html,re.I):
        url = urljoin(CATALOG_URL,href)
        if urlparse(url).hostname != 'droughtmonitor.unl.edu':
            continue
        name = urlparse(url).path.rsplit('/',1)[-1]
        if ZIP_DATE.fullmatch(name):
            day = archive_date(name)
            candidate = {'map_date':day,'url':url,'listed_bytes':int(size),'filename':name}
            if day in entries and entries[day] != candidate:
                raise ValueError(f'Conflicting directory entries for {day}')
            entries[day] = candidate
    if not entries:
        raise ValueError('No weekly archive links found in provider catalog')
    return entries


def plan_drought_download(start_date, end_date, output_folder, local_archive_folder=None,
                          include_municipio_statistics=True, recovery_buffer_weeks=3,
                          mode='Baseline', publish_tables=False):
    output = Path(output_folder).expanduser().resolve()
    source = Path(local_archive_folder).expanduser().resolve() if local_archive_folder else None
    if source and not source.is_dir():
        raise ValueError('Local Archive Folder does not exist')
    protect_source(source,output)
    cohort = make_calendar(start_date,end_date,recovery_buffer_weeks,mode)
    output.mkdir(parents=True,exist_ok=True)
    candidates = {}
    if source:
        for path in sorted(source.rglob('*.zip')):
            if ZIP_DATE.fullmatch(path.name):
                day = archive_date(path.name)
                candidates.setdefault(day,[]).append({'path':str(path),'sha256':sha256(path),
                    'bytes':path.stat().st_size,'acquired_utc':None,'source_url':None})
    for day, items in candidates.items():
        if len({item['sha256'] for item in items})>1:
            raise ValueError(f'Conflicting local archives for {day}; choose a frozen snapshot explicitly')
    result = {'schema_version':1,'product':'USDM merged weekly drought polygons',
        'created_utc':utc_now(),'software_version':VERSION,'geography':'Puerto Rico','state_fips':'72',
        **cohort,'recovery_buffer_weeks':int(recovery_buffer_weeks),
        'include_municipio_statistics':bool(include_municipio_statistics),
        'local_archive_folder':str(source) if source else None,'local_candidates':candidates,
        'catalog_url':CATALOG_URL,
        'plan':str(output/'download_plan.json'),
        'interpretation':'Map-date cohort, not a reconstruction of daily conditions; buffers excluded from the baseline.',
        'scope':'Acquisition only; assessed-domain verification, rasterization and hazard ranking are later stages.'}
    write_json(result['plan'],result)
    return result
