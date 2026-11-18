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

    def test_radii_and_convergence(self):
        import numpy as np
        from utils.hurricane.wind import quadrant_radius, wind_speed, convergence, KNOT_MPS
        radius = quadrant_radius(135 * KNOT_MPS, 0, 0, 30, 1.4, 64, 'NE')
        self.assertAlmostEqual(radius, 166.8517034139759)
        self.assertAlmostEqual(float(wind_speed(radius, 90, 18, 0, 0,
                                               135 * KNOT_MPS, 30, 1.4, 1)), 64 * KNOT_MPS)
        result = convergence(np.array([0., 40.]), np.array([0., 40.]))
        self.assertTrue(result['passed'])


if __name__ == '__main__':
    unittest.main()
