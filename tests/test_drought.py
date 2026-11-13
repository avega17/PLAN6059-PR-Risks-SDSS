"""USDM cohort, malformed-source, transport and full cache/validation regressions."""
from datetime import date
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import urllib.error
from urllib.parse import parse_qs,urlparse
import zipfile

from utils.usdm_archive import inspect_zip
from utils.usdm_catalog import CATALOG_URL, make_calendar, parse_catalog, plan_drought_download
from utils.usdm_common import DroughtAcquisitionError, read_json, sha256, write_json
from utils.usdm_download import fetch_drought_data
from utils.usdm_http import HttpCache, validate_url
from utils.usdm_statistics import MUNICIPIOS, compare_state_formats, normalize_payload
from utils.usdm_validation import validate_drought_download


def archive_bytes(stamp='20260106',dm=0,unsafe=False):
    header=bytearray(100)
    struct.pack_into('>i',header,0,9994)
    struct.pack_into('<ii',header,28,1000,5)
    struct.pack_into('<4d',header,36,-67,17,-65,19)
    points=[(-67.,17.),(-65.,17.),(-65.,19.),(-67.,19.),(-67.,17.)]
    content=struct.pack('<i4diii',5,-67,17,-65,19,1,5,0)+b''.join(struct.pack('<dd',*xy) for xy in points)
    shp=bytearray(header)+struct.pack('>ii',1,len(content)//2)+content
    struct.pack_into('>i',shp,24,len(shp)//2)
    shx=bytearray(header)+struct.pack('>ii',50,len(content)//2)
    struct.pack_into('>i',shx,24,len(shx)//2)
    dbf=bytearray(65)
    dbf[0]=3
    struct.pack_into('<IHH',dbf,4,1,65,2)
    dbf[32:34]=b'DM';dbf[43]=ord('N');dbf[48]=1;dbf[64]=13
    dbf+=b' '+str(dm).encode()+b'\x1a'
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        stem='USDM_'+stamp
        for suffix,body in [('.shp',shp),('.shx',shx),('.dbf',dbf),('.prj',b'GEOGCS["GCS_WGS_1984"]'),('.shp.xml',b'<metadata/>')]:
            z.writestr(stem+suffix,body)
        if unsafe: z.writestr('../escape.txt',b'bad')
    return out.getvalue()


def state_record(day='2026-01-06',format_id=2):
    values=[50,30,20,0,0,0] if format_id==2 else [50,50,20,0,0,0]
    return dict(mapDate=day+'T00:00:00',stateAbbreviation='PR',statisticFormatID=format_id,
                **dict(zip(('none','d0','d1','d2','d3','d4'),values)))


class Response(io.BytesIO):
    def __init__(self,body,url):
        super().__init__(body);self.url=url;self.status=200
        self.headers={'Content-Length':str(len(body))}
    def geturl(self): return self.url


class FakeNetwork:
    def __init__(self): self.calls=[]
    def __call__(self,request,timeout):
        self.calls.append(request)
        url=request.full_url
        if url==CATALOG_URL:
            text=''.join(f'{len(archive_bytes(d))} <a href="/Data/shapefiles_m/USDM_{d}_M.zip">file</a>' for d in ('20260106','20260113'))
            return Response(text.encode(),url)
        if url.endswith('.zip'):
            assert request.get_header('Accept')=='*/*'
            return Response(archive_bytes(url.rsplit('_',2)[1]),url)
        if '/api/' in url:
            if 'GetDSCI' in url:
                records=[dict(name='Puerto Rico',mapDate=day+'T00:00:00',dsci=70) for day in ('2026-01-06','2026-01-13')]
            else:
                format_id=int(parse_qs(urlparse(url).query)['statisticsType'][0])
                records=[state_record(day,format_id) for day in ('2026-01-13','2026-01-06','2025-12-30')]
            return Response(json.dumps(records).encode(),url)
        return Response(b'<html>provider documentation</html>',url)


class CalendarTests(unittest.TestCase):
    def test_full_baseline_and_buffers(self):
        result=make_calendar('2000-01-01','2025-12-31',today=date(2026,11,12))
        self.assertEqual(result['baseline_count'],1357)
        self.assertEqual(result['year_count'],26)
        self.assertEqual(len(result['weeks']),1360)
        self.assertEqual(result['weeks'][-1],{'MAP_DATE':'2026-01-20','ROLE':'END_BUFFER'})
        self.assertEqual(len(result['unavailable_start_buffer_dates']),3)

    def test_partial_baseline_and_pre_usdm_rejected(self):
        for start,end in [('1955-01-01','2025-12-31'),('2000-01-02','2025-12-31'),('2026-01-01','2026-12-31')]:
            with self.assertRaises(ValueError):make_calendar(start,end,today=date(2026,11,12))

    def test_pilot_and_buffers_have_distinct_roles(self):
        r=make_calendar('2026-01-06','2026-01-13',1,'Pilot',today=date(2026,11,12))
        self.assertEqual(r['baseline_count'],2)
        self.assertIsNone(r['year_count'])
        self.assertEqual([w['ROLE'] for w in r['weeks']],['START_BUFFER','BASELINE','BASELINE','END_BUFFER'])

    def test_mixed_case_directory_and_conflicts(self):
        entries=parse_catalog('20 <A HREF="/Data/shapefiles_m/usdm_20260106_m.zip">x</A>')
        self.assertEqual(entries['2026-01-06']['listed_bytes'],20)
        with self.assertRaises(ValueError):parse_catalog('not a catalog')
        with self.assertRaises(ValueError):parse_catalog('20 <a href="USDM_20260106_M.zip">a</a>21 <a href="USDM_20260106_M.zip">b</a>')

    def test_output_cannot_be_nested_in_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                plan_drought_download('2026-01-06','2026-01-13',Path(tmp)/'out',tmp,False,0,'Pilot')


class ArchiveTests(unittest.TestCase):
    def test_structural_archive(self):
        result=inspect_zip(io.BytesIO(archive_bytes()),'2026-01-06')
        self.assertEqual(result['dm_values'],[0])
        self.assertFalse(result['assessed_domain_verified'])

    def test_unsafe_members_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unsafe'):
            inspect_zip(io.BytesIO(archive_bytes(unsafe=True)),'2026-01-06')

    def test_mismatched_date_and_unknown_category(self):
        for payload,day in [(archive_bytes(),'2026-01-13'),(archive_bytes(dm=9),'2026-01-06')]:
            with self.assertRaises(ValueError):inspect_zip(io.BytesIO(payload),day)

    def test_bad_index_fails(self):
        data=archive_bytes();out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as source,zipfile.ZipFile(out,'w') as target:
            for name in source.namelist():
                body=source.read(name)
                target.writestr(name,b'bad' if name.endswith('.shx') else body)
        with self.assertRaises(ValueError):inspect_zip(io.BytesIO(out.getvalue()),'2026-01-06')


class StatisticsTests(unittest.TestCase):
    def setUp(self):
        self.job={'id':'test','kind':'state','format':2,'dates':['2026-01-06']}
        self.roles={'2026-01-06':'BASELINE'}

    def test_overlap_filtered_and_identical_duplicate_removed(self):
        row=state_record()
        rows,_,_,counts=normalize_payload([state_record('2025-12-30'),row,row],self.job,self.roles,'a'*64)
        self.assertEqual(len(rows),6)
        self.assertEqual(counts,{'excluded_overlap_records':1,'identical_duplicates_removed':1})
        self.assertEqual(next(r['VALUE'] for r in rows if r['CATEGORY']=='D0'),30)

    def test_conflicting_duplicate_and_empty_array_fail(self):
        row=state_record();other=dict(row,d0=31)
        for data in ([row,other],[]):
            with self.assertRaises(ValueError):normalize_payload(data,self.job,self.roles,'a'*64)

    def test_bad_format_geography_missing_and_nonfinite_values(self):
        for changes in [{'statisticFormatID':1},{'stateAbbreviation':'TX'},{'d0':None},{'d0':float('nan')},{'d0':-1}]:
            with self.assertRaises(ValueError):normalize_payload([dict(state_record(),**changes)],self.job,self.roles,'a'*64)

    def test_source_disagreement_is_preserved(self):
        row=dict(state_record(),d0=30.33)
        rows,issues,_,_=normalize_payload([row],self.job,self.roles,'a'*64)
        self.assertEqual(len(issues),1)
        self.assertEqual(next(r['VALUE'] for r in rows if r['CATEGORY']=='D0'),30.33)

    def test_cumulative_order_not_interpreted_as_categorical(self):
        job=dict(self.job,format=1)
        with self.assertRaises(ValueError):normalize_payload([dict(state_record(format_id=1),d1=60)],job,self.roles,'a'*64)

    def test_complete_municipio_fips_contract(self):
        job=dict(self.job,kind='municipio')
        rows=[]
        for fips in sorted(MUNICIPIOS):
            row=state_record();row.update(fips=fips,state='PR')
            rows.append(row)
        normalized,_,_,_=normalize_payload(rows,job,self.roles,'a'*64)
        self.assertEqual(len(normalized),78*6)
        with self.assertRaises(ValueError):normalize_payload(rows[:-1],job,self.roles,'a'*64)


class HttpTests(unittest.TestCase):
    def test_unapproved_urls_blocked(self):
        for url in ('http://droughtmonitor.unl.edu','https://example.com','https://user@droughtmonitor.unl.edu','https://droughtmonitor.unl.edu:444/'):
            with self.assertRaises(ValueError):validate_url(url)

    def test_retry_after_and_offline_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls=[];sleeps=[]
            def opener(request,timeout):
                calls.append(request)
                if len(calls)==1:raise urllib.error.HTTPError(request.full_url,429,'slow',{'Retry-After':'2'},None)
                return Response(b'[]',request.full_url)
            client=HttpCache(tmp,opener=opener,sleeper=sleeps.append,pause=0)
            url='https://usdmdataservices.unl.edu/api/test'
            result=client.get(url,'json',lambda p:{'valid':True})
            self.assertEqual(result['attempts'],2)
            self.assertIn(2,sleeps)
            cached=HttpCache(tmp,offline=True).get(url,'json',lambda p:{'valid':True})
            self.assertTrue(cached['cache_hit'])

    def test_html_instead_of_json_is_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            client=HttpCache(tmp,pause=0,opener=lambda r,timeout:Response(b'<html>Error</html>',r.full_url))
            with self.assertRaises(ValueError):client.get('https://usdmdataservices.unl.edu/api/test','json',lambda p:{})
            self.assertFalse((Path(tmp)/'request_index').exists())

    def test_corrupt_cached_body_is_refetched(self):
        with tempfile.TemporaryDirectory() as tmp:
            client=HttpCache(tmp,pause=0,opener=lambda r,timeout:Response(b'[]',r.full_url))
            url='https://usdmdataservices.unl.edu/api/test'
            first=client.get(url,'json',lambda p:{})
            Path(first['path']).write_bytes(b'bad')
            second=client.get(url,'json',lambda p:{})
            self.assertFalse(second['cache_hit'])
            self.assertEqual(Path(second['path']).read_bytes(),b'[]')
            self.assertIn('repaired_cache_issue',second)


class PipelineTests(unittest.TestCase):
    def test_corrupt_local_copy_repaired_from_unchanged_source_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.mkdir()
            original=source/'USDM_20260106_M.zip';original.write_bytes(archive_bytes())
            checksum=sha256(original)
            plan=plan_drought_download('2026-01-06','2026-01-13',root/'plan',source,False,0,'Pilot')
            acquired=fetch_drought_data(plan['plan'],root/'cache',root/'acquire',
                http_cache=HttpCache(root/'cache',opener=FakeNetwork(),sleeper=lambda n:None))
            copied=next(e for e in acquired['gis'] if e['source_kind']=='LOCAL_COPY')
            Path(copied['path']).write_bytes(b'corrupt cached copy')
            repaired=fetch_drought_data(plan['plan'],root/'cache',root/'repaired',offline=True)
            self.assertEqual(repaired['network_requests'],0)
            self.assertEqual(sha256(original),checksum)
            self.assertTrue(next(e for e in repaired['gis'] if e['source_kind']=='LOCAL_COPY')['repaired_cache_path'])
            self.assertTrue(validate_drought_download(repaired['manifest'],root/'validate')['passed'])

    def test_cold_then_no_network_warm_run_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='drought test ') as tmp:
            root=Path(tmp);network=FakeNetwork()
            plan=plan_drought_download('2026-01-06','2026-01-13',root/'plan',None,False,0,'Pilot')
            client=HttpCache(root/'cache',opener=network,sleeper=lambda n:None)
            acquired=fetch_drought_data(plan['plan'],root/'cache',root/'acquire',http_cache=client)
            report=validate_drought_download(acquired['manifest'],root/'validate')
            self.assertTrue(report['passed'])
            self.assertFalse(report['ready_for_rasterization'])
            self.assertEqual(report['baseline_maps'],2)
            warmed=fetch_drought_data(plan['plan'],root/'cache',root/'warm',offline=True)
            self.assertEqual(warmed['network_requests'],0)
            self.assertTrue(validate_drought_download(warmed['manifest'],root/'warm_validate')['passed'])

    def test_validation_detects_changed_canonical_values_even_with_updated_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            plan=plan_drought_download('2026-01-06','2026-01-13',root/'plan',None,False,0,'Pilot')
            client=HttpCache(root/'cache',opener=FakeNetwork(),sleeper=lambda n:None)
            acquired=fetch_drought_data(plan['plan'],root/'cache',root/'acquire',http_cache=client)
            path=Path(acquired['canonical_csv'])
            path.write_text(path.read_text().replace(',30.0,',',31.0,'))
            acquired['canonical_sha256']=sha256(path)
            write_json(acquired['manifest'],acquired)
            with self.assertRaises(DroughtAcquisitionError):
                validate_drought_download(acquired['manifest'],root/'validate')
            self.assertFalse(read_json(root/'validate/download_validation.json')['passed'])


if __name__=='__main__':unittest.main()
