"""Small offline checks for data contracts and wind-model numerical behavior."""
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


class WindEquations(unittest.TestCase):
    def test_radial_peak_eye_asymmetry_and_missing(self):
        import numpy as np
        from utils.hurricane.wind import wind_speed, KNOT_MPS
        self.assertAlmostEqual(64 * KNOT_MPS, 32.92444444444445)
        values = wind_speed(np.array([0., 40., 40.]), np.array([90., 90., 270.]),
                            18., 0., 10., 60., 40., 1.4)
        np.testing.assert_allclose(values, [0., 48., 40.])
        self.assertEqual(float(wind_speed(40, 270, 18, 0, 50, 20, 40, 1.4)), 0)
        with self.assertRaises(ValueError):
            wind_speed(40, 90, 18, 0, 10, np.nan, 40, 1.4)

    def test_spherical_geometry_and_heading_wrap(self):
        import numpy as np
        from utils.hurricane.wind import range_bearing
        for lat, lon, expected in [(1, 0, 0), (0, 1, 90), (-1, 0, 180), (0, -1, 270)]:
            distance, bearing = range_bearing(0, 0, lat, lon)
            self.assertAlmostEqual(float(distance), 6367 * np.pi / 180)
            self.assertAlmostEqual(float(bearing), expected)
        self.assertLess(float(range_bearing(0, 179.9, 0, -179.9)[0]), 23)

    def test_native_interpolation_and_gap_policy(self):
        from datetime import datetime, timedelta, timezone
        import numpy as np
        from utils.hurricane.wind import interpolate_track
        start = datetime(2017, 9, 20, tzinfo=timezone.utc)
        records = [dict(time=start + timedelta(minutes=m), lat=18., lon=lon,
                        wind=w, nature='TS') for m, lon, w in [(0, 179.9, 30), (17, -179.9, 40)]]
        samples = interpolate_track(records, 5)
        self.assertTrue(np.all(np.diff(samples['time']) <= 300))
        self.assertEqual(samples['time'][-1], records[-1]['time'].timestamp())
        self.assertEqual(samples['wind'][-1], 40)
        self.assertTrue(np.all(np.abs(samples['lon']) > 179))
        window = (start.timestamp() + 73, start.timestamp() + 697)
        limited = interpolate_track(records, 2.5, window=window)
        self.assertEqual(tuple(limited['time'][[0, -1]]), window)
        with self.assertRaises(ValueError):
            interpolate_track(records, 2.5, window=(start.timestamp() - 1, window[1]))
        phases = [dict(time=start + timedelta(hours=i), lat=18., lon=-66. + i / 10,
                       wind=40., nature=n) for i, n in enumerate(['TS', 'TS', 'ET', 'TS', 'TS'])]
        with self.assertRaises(ValueError):
            interpolate_track(phases, 2.5, window=(start.timestamp() + 7200, start.timestamp() + 12600))
        records[-1]['wind'] = None
        with self.assertRaises(ValueError):
            interpolate_track(records, 5)
        records[-1]['wind'] = 40
        records[-1]['time'] = start + timedelta(hours=7)
        with self.assertRaises(ValueError):
            interpolate_track(records, 5)

    def test_peak_bounds_match_exhaustive_evaluation(self):
        import numpy as np
        from utils.hurricane.wind import peak_fields, range_bearing, wind_speed, SIZE_SCENARIOS
        samples = dict(lat=np.array([18., 18., 30.]), lon=np.array([-66., -65.5, -20.]),
                       wind=np.array([60., 55., 40.]), speed=np.array([5., 5., 10.]),
                       heading=np.array([270., 270., 45.]))
        lat, lon = np.array([18., 18.5, 17.5]), np.array([-65.7, -66., -66.])
        actual, stats = peak_fields(samples, lat, lon)
        expected = np.zeros_like(actual)
        for i in range(3):
            distance, bearing = range_bearing(samples['lat'][i], samples['lon'][i], lat, lon)
            for j, (radius, profile) in enumerate(SIZE_SCENARIOS):
                expected[j] = np.maximum(expected[j], wind_speed(distance, bearing,
                    samples['lat'][i], samples['heading'][i], samples['speed'][i],
                    samples['wind'][i], radius, profile))
        np.testing.assert_allclose(actual, expected, rtol=1e-12)
        self.assertGreater(stats['bounded_skips'], 0)
        cutoffs = np.array([17.5, 32.9, 32.9, 32.9])
        screened, _ = peak_fields(samples, lat, lon, minimum_mps=cutoffs)
        np.testing.assert_array_equal(screened >= cutoffs[:, None], expected >= cutoffs[:, None])

    def test_radii_and_convergence(self):
        import numpy as np
        from utils.hurricane.wind import quadrant_radius, wind_speed, convergence, KNOT_MPS
        radius = quadrant_radius(135 * KNOT_MPS, 0, 0, 30, 1.4, 64, 'NE')
        self.assertAlmostEqual(radius, 166.8517034139759)
        self.assertAlmostEqual(float(wind_speed(radius, 90, 18, 0, 0,
                                               135 * KNOT_MPS, 30, 1.4, 1)), 64 * KNOT_MPS)
        result = convergence(np.array([0., 40.]), np.array([0., 40.]))
        self.assertTrue(result['passed'])


class DroughtProcessing(unittest.TestCase):
    def test_occupancy_encoding_and_buffer_isolation(self):
        import numpy as np
        from utils.drought.usdm_metrics import occupancy
        values = np.array([[0,255],[1,255],[2,2],[5,5],[5,5],[5,5],[5,5]],dtype=np.uint8)
        stats = occupancy(values,4,1)
        np.testing.assert_array_equal(stats['d1'],[2,2])
        self.assertEqual(stats['wd1'][0],2)
        self.assertTrue(np.isnan(stats['wd1'][1]))
        self.assertEqual(stats['burden'][0],200)
        with self.assertRaises(ValueError): occupancy(np.array([[9]],dtype=np.uint8),1,1)
        from utils.drought.usdm_common import spatial_source_signature
        m=dict(plan_snapshot=dict(baseline_count=1,year_count=1),created_utc='old',
               gis=[dict(map_date='2000-01-04',role='BASELINE',sha256='a'*64,path='old')])
        changed=copy.deepcopy(m);changed['created_utc']='new';changed['gis'][0]['path']='relocated'
        self.assertEqual(spatial_source_signature(m),spatial_source_signature(changed))
        changed['gis'][0]['sha256']='b'*64
        self.assertNotEqual(spatial_source_signature(m),spatial_source_signature(changed))

    def test_event_recovery_and_confirmation_dates(self):
        import numpy as np
        from utils.drought.usdm_metrics import analyze_events
        x=np.array([0,0,0,2,2,1,0,3,1,0,0],dtype=np.uint8)
        events,summary=analyze_events(x,8,3)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0][2:10],(3,7,10,5,3,3,0,0))
        self.assertEqual(summary['median'][0],5)
        strict,s=analyze_events(x,8,1)
        self.assertEqual((len(strict),s['maximum'][0]),(2,2))
        d2, summary = analyze_events(x, 8, 3, minimum_dm=2)
        self.assertEqual(d2[0][2:10], (7, 7, 10, 1, 1, 3, 0, 0))
        self.assertEqual(summary['median'][0], 1)

    def test_unknown_censoring_and_buffer_only_events(self):
        import numpy as np
        from utils.drought.usdm_metrics import analyze_events
        x=np.array([0,0,0,2,255,2,0,0,0],dtype=np.uint8)
        events,summary=analyze_events(x,9,3)
        self.assertEqual(len(events),2)
        self.assertEqual((events[0][8],events[0][9],events[1][8],events[1][9]),(0,1,1,0))
        self.assertEqual(summary['complete'][0],0)
        self.assertTrue(np.isnan(summary['maximum'][0]))
        events,summary=analyze_events(np.array([0,0,0,2,2,2],dtype=np.uint8),3,3)
        self.assertEqual(len(events),0)
        self.assertEqual(summary['count'][0],0)

    def test_safe_ring_screen_is_conservative(self):
        import struct
        import numpy as np
        from utils.drought.usdm_archive import has_part_intersection
        def shape(rings):
            xy=np.array([point for ring in rings for point in ring],dtype='<f8')
            starts=np.cumsum([0]+[len(r) for r in rings[:-1]]).astype('<i4')
            low,high=xy.min(axis=0),xy.max(axis=0)
            body=struct.pack('<i4dii',5,low[0],low[1],high[0],high[1],len(rings),len(xy))+starts.tobytes()+xy.tobytes()
            header=bytearray(100);struct.pack_into('>i',header,0,9994)
            return bytes(header)+struct.pack('>ii',1,len(body)//2)+body
        conus=[(-120,30),(-100,30),(-100,40),(-120,40),(-120,30)]
        pr=[(-67,18),(-66,18),(-66,19),(-67,19),(-67,18)]
        envelope=(-68.15,17.8,-65.1,18.6)
        self.assertFalse(has_part_intersection(shape([conus]),envelope))
        self.assertTrue(has_part_intersection(shape([conus,pr]),envelope))
        enclosing=[(-70,16),(-60,16),(-60,20),(-70,20),(-70,16)]
        self.assertTrue(has_part_intersection(shape([enclosing]),envelope))
        with self.assertRaises(ValueError): has_part_intersection(shape([pr])[:-3],envelope)


class HazardClassification(unittest.TestCase):
    def test_relative_breaks_keep_ties_and_require_three_values(self):
        import numpy as np
        from utils.shared.hazard_rank import ranks, relative_breaks
        a = np.array([0, 0, 1, 2, 2, np.nan])
        b = np.array([0, 5, 5, 6, 12, 13, np.nan])
        self.assertEqual(relative_breaks(a), (0, 1))
        self.assertEqual(relative_breaks(b), (0, 6))
        np.testing.assert_array_equal(ranks(a, *relative_breaks(a)), [1, 1, 3, 5, 5, np.nan])
        self.assertIsNone(relative_breaks(np.array([0, 0, 1, np.nan])))

    def test_new_year_windows_and_depression_bound(self):
        from datetime import datetime, timezone
        from utils.hurricane import wind
        from utils.hurricane.wind_history import _new_year, reference_windows, yearly_samples
        def record(y, m, d, h, velocity, status):
            return dict(time=datetime(y, m, d, h, tzinfo=timezone.utc),
                        lat=18., lon=-66., wind=velocity, nature='TS', source={'USA_STATUS':status})
        points = [record(2005, 12, 31, 23, 50., 'HU'), record(2006, 1, 1, 1, 60., 'HU')]
        years, unresolved, _ = yearly_samples(points, (18., -66.), 1., wind.SIZE_SCENARIOS, 17.)
        self.assertFalse(unresolved)
        self.assertLess(years[2005]['time'].max(), _new_year(2006))
        self.assertEqual(years[2006]['time'].min(), _new_year(2006))
        points[0].update(wind=None, source={'USA_STATUS':'TD'})
        points[1].update(wind=20*wind.KNOT_MPS, source={'USA_STATUS':'TD'})
        self.assertEqual(yearly_samples(points, (18., -66.), 1., wind.SIZE_SCENARIOS,
                                        34*wind.KNOT_MPS), ({}, set(), 1))
        self.assertEqual(reference_windows()[-2:], [('all_2026', 1955, 2026), ('rolling_2026', 1996, 2026)])


if __name__ == '__main__':
    unittest.main()
