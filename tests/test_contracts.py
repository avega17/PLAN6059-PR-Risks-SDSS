"""Eight small offline checks for scientific rules and reusable cache integrity."""
import copy
from datetime import date
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from utils.hurricane.ibtracs import classify_records, normalize_numeric, usa_iflag
from utils.shared.grid import aligned_extent
from utils.drought.usdm_catalog import make_calendar
from utils.drought.usdm_http import HttpCache
from utils.drought.usdm_statistics import compare_state_formats, normalize_payload


def observation(**changes):
    attributes = dict(SID='2017260N12310', SEASON=2017, ISO_TIME='2017-09-20 10:15:00',
                      TRACK_TYPE='main', IFLAG='O______________', USA_LAT=18., USA_LON=-66.,
                      USA_WIND=135, USA_AGENCY='hurdat_atl', USA_STATUS='HU', NATURE='TS')
    attributes.update(changes)
    return dict(attributes=attributes, source_oid=0, geometry_hash='original')


class Contracts(unittest.TestCase):
    def test_selection_and_usa_position(self):
        rows = [observation(TRACK_TYPE='MAIN'), observation(TRACK_TYPE='spur'),
                observation(SEASON=2026), observation(USA_LAT=None, LAT=18.)]
        self.assertEqual([r['row_status'] for r in classify_records(rows)],
                         ['INCLUDED', 'EXCLUDED_TRACK_TYPE', 'EXCLUDED_SEASON', 'QUARANTINED'])

    def test_missing_values_are_field_specific(self):
        for field, value, expected in [('USA_WIND', -9999, None), ('USA_LON', -66, -66),
                                       ('USA_SSHS', -5, -5), ('USA_R64_SW', 0, 0)]:
            self.assertEqual(normalize_numeric(field, value)[0], expected)

    def test_duplicate_conflicts(self):
        first = observation()
        duplicate = copy.deepcopy(first)
        duplicate['source_oid'] = 1
        self.assertEqual(classify_records([first, duplicate])[1]['row_status'], 'DUPLICATE_EXACT')
        self.assertEqual([r['row_status'] for r in classify_records([first, observation(USA_WIND=140)])],
                         ['CONFLICT', 'CONFLICT'])

    def test_flags_blank_agency_and_status(self):
        row = classify_records([observation(IFLAG='P______________', USA_AGENCY='', USA_WIND=None)])[0]
        self.assertEqual(row['row_status'], 'INCLUDED')
        self.assertEqual(row['usa_iflag'], 'P')
        self.assertEqual(row['values']['USA_AGENCY'], '')
        self.assertEqual((row['values']['NATURE'], row['values']['USA_STATUS']), ('TS', 'HU'))
        self.assertEqual(usa_iflag('V_____________O'), 'V')
        with self.assertRaises(ValueError):
            usa_iflag('O')

    def test_baseline_and_buffers(self):
        cohort = make_calendar('2000-01-01', '2025-12-31', today=date(2026, 11, 12))
        self.assertEqual((cohort['baseline_count'], cohort['year_count'], len(cohort['weeks'])), (1357, 26, 1360))
        self.assertEqual(cohort['weeks'][-1], {'MAP_DATE':'2026-01-20', 'ROLE':'END_BUFFER'})
        with self.assertRaises(ValueError):
            make_calendar('1955-01-01', '2025-12-31')

    def test_statistics_interpretation(self):
        day = '2015-08-04'
        raw = dict(mapDate=day+'T00:00:00', validStart=day+'T00:00:00',
                   validEnd='2015-08-10T23:59:59', stateAbbreviation='PR', statisticFormatID=2,
                   none=50, d0=30, d1=20, d2=0, d3=0, d4=0)
        job = dict(kind='state', format=2, dates=[day], id='example')
        rows, issues, _, _ = normalize_payload([raw], job, {day:'BASELINE'}, 'a'*64)
        self.assertFalse(issues)
        self.assertEqual({r['CATEGORY']:r['VALUE'] for r in rows},
                         {'NONE':50, 'D0':30, 'D1':20, 'D2':0, 'D3':0, 'D4':0})
        cumulative = dict(raw, none=50, d0=50, d1=20)
        self.assertEqual(compare_state_formats({day:{'1':cumulative, '2':raw, 'dsci':{'dsci':70}}}), [])

    def test_grid_alignment(self):
        self.assertEqual(aligned_extent((-1, -251, 251, 1)),
                         dict(xmin=-250, ymin=-500, xmax=500, ymax=250, columns=3, rows=3))

    def test_cache_relocation_and_integrity(self):
        with tempfile.TemporaryDirectory(prefix='cache with spaces ') as temporary:
            root = Path(temporary).resolve()
            url = 'https://droughtmonitor.unl.edu/example.json'
            checksum = hashlib.sha256(b'[]').hexdigest()
            key = hashlib.sha256((url+'\napplication/json\njson').encode()).hexdigest()
            body = root/'objects'/checksum[:2]/(checksum+'.json')
            receipt = root/'receipts'/key/'original.json'
            pointer = root/'request_index'/(key+'.json')
            for p in (body, receipt, pointer):
                p.parent.mkdir(parents=True, exist_ok=True)
            body.write_bytes(b'[]')
            original = dict(url=url, kind='json', accept='application/json', bytes=2, sha256=checksum,
                            path=str(root.parent/'old location'/'objects'/checksum[:2]/(checksum+'.json')),
                            receipt_path=str(root.parent/'old location'/'receipts'/key/'original.json'), retrieved_utc='unknown')
            receipt.write_text(json.dumps(original))
            frozen = receipt.read_bytes()
            pointer.write_text(json.dumps(original))
            client = HttpCache(root, offline=True)
            result = client.get(url, 'json', lambda p:json.loads(p.read_text()))
            self.assertEqual(result['path'], str(body))
            self.assertEqual(client.network_requests, 0)
            self.assertFalse(Path(json.loads(pointer.read_text())['path']).is_absolute())
            self.assertEqual(receipt.read_bytes(), frozen)
            body.write_bytes(b'{}')
            with self.assertRaises(ConnectionError):
                client.get(url, 'json', lambda p:json.loads(p.read_text()))


if __name__ == '__main__':
    unittest.main()
