"""Scientific data-contract checks that do not require ArcPy."""

import copy
import unittest

from utils.ibtracs import (classify_records, is_hurricane_status, normalize_numeric,
                          normalize_record, parse_utc, usa_iflag,
                          _coordinate_differences, _require_point_geometry)


def sample(**changes):
    attrs = dict(SID="2017260N12310", SEASON=2017, ISO_TIME="2017-09-20 10:15:00",
                 TRACK_TYPE="main", IFLAG="O______________", USA_LAT=18.0,
                 USA_LON=-66.0, USA_WIND=135, USA_AGENCY="hurdat_atl", USA_STATUS="HU")
    attrs.update(changes)
    return dict(attributes=attrs, source_oid=0, geometry_hash="original-geometry")


class NumericContractTests(unittest.TestCase):
    def test_negative_status_codes_and_western_longitude_are_valid(self):
        self.assertEqual(normalize_numeric("USA_SSHS", -5), (-5, None))
        self.assertEqual(normalize_numeric("USA_LON", -66), (-66, None))

    def test_missing_sentinels_are_field_specific_and_zero_radius_is_real(self):
        self.assertEqual(normalize_numeric("USA_WIND", -9999), (None, "sentinel"))
        self.assertEqual(normalize_numeric("NEW_CI", -999.9), (None, "sentinel"))
        self.assertEqual(normalize_numeric("USA_R64_SW", 0), (0, None))
        self.assertEqual(normalize_numeric("USA_WIND", ""), (None, "blank"))

    def test_missing_wind_and_agency_are_flagged_without_dropping_point(self):
        record = sample(USA_WIND=None, USA_AGENCY="", IFLAG="P______________")
        result = classify_records([record])[0]
        self.assertEqual(result["row_status"], "INCLUDED")
        self.assertEqual(result["usa_iflag"], "P")
        self.assertIn("MISSING_USA_WIND", result["qc_flags"])
        self.assertIn("MISSING_USA_AGENCY", result["qc_flags"])


class ProvenanceContractTests(unittest.TestCase):
    def test_track_lines_are_rejected_as_the_primary_point_source(self):
        _require_point_geometry("Point")
        with self.assertRaisesRegex(ValueError, "Raw Points must be a Point"):
            _require_point_geometry("Polyline")

    def test_coordinate_comparison_reports_source_difference_not_accuracy(self):
        records = classify_records([sample()])
        records[0]["raw_geometry_xy"] = (-65.5, 18.2)
        result = _coordinate_differences(records)
        self.assertEqual(result["compared_observations"], 1)
        self.assertEqual(result["observations_exceeding_either_axis_threshold"], 1)
        self.assertAlmostEqual(result["maximum_absolute_axis_difference_degrees"], 0.5)

    def test_usa_flag_uses_first_character_and_validates_length(self):
        self.assertEqual(usa_iflag("V_____________O"), "V")
        with self.assertRaises(ValueError):
            usa_iflag("O")

    def test_special_observation_time_is_preserved_as_utc(self):
        value = parse_utc("2017-09-20 10:15:00")
        self.assertEqual((value.hour, value.minute), (10, 15))
        self.assertEqual(value.utcoffset().total_seconds(), 0)

    def test_malformed_timestamp_is_not_silently_reformatted(self):
        with self.assertRaises(ValueError):
            parse_utc("2017-9-20 10:15:00")
        with self.assertRaises(ValueError):
            parse_utc("2017-02-30 00:00:00")

    def test_nature_and_source_status_are_not_conflated(self):
        self.assertTrue(is_hurricane_status("HU"))
        self.assertFalse(is_hurricane_status("TS"))
        self.assertFalse(is_hurricane_status("ET"))

    def test_only_main_and_complete_selected_seasons_are_included(self):
        rows = [sample(TRACK_TYPE="MAIN"), sample(TRACK_TYPE="US-PROVISIONAL"),
                sample(TRACK_TYPE="spur-merge"), sample(SEASON=2026)]
        self.assertEqual([row["row_status"] for row in classify_records(rows)],
                         ["INCLUDED", "EXCLUDED_TRACK_TYPE", "EXCLUDED_TRACK_TYPE", "EXCLUDED_SEASON"])

    def test_quarantine_does_not_fall_back_to_merged_geometry(self):
        rows = [sample(USA_LAT=None, LAT=18.0), sample(ISO_TIME="bad"), sample(SID="bad")]
        self.assertTrue(all(row["row_status"] == "QUARANTINED" for row in classify_records(rows)))

    def test_exact_duplicates_and_conflicts_are_different(self):
        first = sample()
        duplicate = copy.deepcopy(first)
        duplicate["source_oid"] = 1
        self.assertEqual([row["row_status"] for row in classify_records([first, duplicate])],
                         ["INCLUDED", "DUPLICATE_EXACT"])
        conflict = sample(USA_WIND=140)
        self.assertEqual([row["row_status"] for row in classify_records([first, conflict])],
                         ["CONFLICT", "CONFLICT"])

    def test_same_attributes_but_changed_geometry_are_conflicting(self):
        first = sample()
        other = copy.deepcopy(first)
        other["geometry_hash"] = "different-geometry"
        self.assertEqual(classify_records([first, other])[1]["row_status"], "CONFLICT")

    def test_input_attributes_are_not_mutated(self):
        record = sample(USA_WIND=-9999)
        before = copy.deepcopy(record)
        normalize_record(record["attributes"])
        classify_records([record])
        self.assertEqual(record, before)


if __name__ == "__main__":
    unittest.main()
