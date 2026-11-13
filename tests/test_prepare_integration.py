"""Opt-in preparation checks using isolated, synthetic ArcPy shapefiles.

Run with ArcGIS Pro's Python and RUN_ARCPY_INTEGRATION=1.  These tests never
open the professor's datasets or the repository's prepared geodatabases.
"""

import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

from utils.ibtracs import prepare_hurricane_data


def _source_hashes(shapefile):
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for extension in (".shp", ".shx", ".dbf", ".prj", ".cpg")
        if (path := Path(shapefile).with_suffix(extension)).is_file()
    }


@unittest.skipUnless(
    os.environ.get("RUN_ARCPY_INTEGRATION") == "1" and importlib.util.find_spec("arcpy"),
    "Opt-in ArcPy integration test",
)
class PrepareIntegrationTests(unittest.TestCase):
    def setUp(self):
        import arcpy
        self.arcpy = arcpy
        self.temporary = tempfile.TemporaryDirectory(prefix="plan6059-prepare-test-")
        self.root = Path(self.temporary.name).resolve()
        self.fixture_folder = self.root / "fixtures"
        self.fixture_folder.mkdir()

    def tearDown(self):
        self.arcpy.management.ClearWorkspaceCache()
        # Verify the precise recursive-cleanup target remains the temp directory
        # created by this test, rather than any repository or shared output.
        target = Path(self.temporary.name).resolve()
        self.assertEqual(target, self.root)
        self.assertEqual(target.parent, Path(tempfile.gettempdir()).resolve())
        self.assertTrue(target.name.startswith("plan6059-prepare-test-"))
        self.temporary.cleanup()

    def _make_points(self, rows):
        arcpy = self.arcpy
        source = self.fixture_folder / "tracks.shp"
        arcpy.management.CreateFeatureclass(
            str(self.fixture_folder), source.name, "POINT",
            spatial_reference=arcpy.SpatialReference(4326),
        )
        schema = [
            ("SID", "TEXT", 32), ("SEASON", "LONG", None),
            ("ISO_TIME", "TEXT", 32), ("TRACK_TYPE", "TEXT", 20),
            ("IFLAG", "TEXT", 15), ("USA_LAT", "DOUBLE", None),
            ("USA_LON", "DOUBLE", None), ("USA_WIND", "DOUBLE", None),
            ("USA_AGENCY", "TEXT", 20), ("USA_STATUS", "TEXT", 8),
            ("NATURE", "TEXT", 8), ("USA_SSHS", "LONG", None),
            ("LAT", "DOUBLE", None), ("LON", "DOUBLE", None),
            ("NAME", "TEXT", 20),
        ]
        arcpy.management.AddFields(
            str(source), [[name, kind, "", size] for name, kind, size in schema]
        )
        names = [field[0] for field in schema]
        with arcpy.da.InsertCursor(str(source), names + ["SHAPE@XY"]) as cursor:
            for offset, overrides in enumerate(rows):
                values = {
                    "SID": "2017260N12334", "SEASON": 2017,
                    "ISO_TIME": f"2017-09-20 {offset * 3:02d}:00:00",
                    "TRACK_TYPE": "MAIN", "IFLAG": "O" + "_" * 14,
                    "USA_LAT": 18.22, "USA_LON": -66.45,
                    "USA_WIND": 100, "USA_AGENCY": "hurdat_atl",
                    "USA_STATUS": "HU", "NATURE": "TS", "USA_SSHS": 3,
                    "LAT": 45, "LON": 12, "NAME": "SYNTHETIC",
                    "geometry": (12, 45),
                }
                values.update(overrides)
                cursor.insertRow([values[name] for name in names] + [values["geometry"]])
        return source

    def _make_inherited_mask(self):
        arcpy = self.arcpy
        mask = self.fixture_folder / "caller_mask.shp"
        arcpy.management.CreateFeatureclass(
            str(self.fixture_folder), mask.name, "POLYGON",
            spatial_reference=arcpy.SpatialReference(4326),
        )
        ring = arcpy.Array([arcpy.Point(x, y) for x, y in [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]])
        polygon = arcpy.Polygon(ring, arcpy.SpatialReference(4326))
        with arcpy.da.InsertCursor(str(mask), ["SHAPE@"]) as cursor:
            cursor.insertRow([polygon])
        return mask

    def test_rebuilds_usa_geometry_and_restores_caller_environments(self):
        source = self._make_points([
            {},
            {"USA_LAT": 35, "USA_LON": -30, "IFLAG": "P" + "_" * 14},
            {"TRACK_TYPE": "spur"},
        ])
        before = _source_hashes(source)
        caller_mask = self._make_inherited_mask()
        arcpy = self.arcpy
        with arcpy.EnvManager(
            extent=arcpy.Extent(0, 0, 1, 1), mask=str(caller_mask),
            outputCoordinateSystem=arcpy.SpatialReference(3857),
            cellSize=5000, overwriteOutput=False,
        ):
            result = prepare_hurricane_data(str(source), self.root / "prepared")
            self.assertEqual(arcpy.env.outputCoordinateSystem.factoryCode, 3857)
            self.assertEqual(float(arcpy.env.cellSize), 5000)
            self.assertEqual(Path(arcpy.env.mask), caller_mask)
            self.assertEqual((arcpy.env.extent.XMin, arcpy.env.extent.XMax), (0, 1))
            self.assertFalse(arcpy.env.overwriteOutput)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["summary"]["selected_observation_count"], 2)
        self.assertEqual(arcpy.Describe(result["observations"]).spatialReference.factoryCode, 4326)
        with arcpy.da.SearchCursor(result["observations"], ["USA_LON", "USA_LAT", "USA_IFLAG", "SHAPE@XY"]) as cursor:
            rows = list(cursor)
        self.assertEqual(len(rows), 2)
        self.assertEqual({row[2] for row in rows}, {"O", "P"})
        for longitude, latitude, _, xy in rows:
            self.assertAlmostEqual(xy[0], longitude, places=8)
            self.assertAlmostEqual(xy[1], latitude, places=8)
        self.assertTrue(any(abs(row[3][0] + 30) < 1e-8 and abs(row[3][1] - 35) < 1e-8 for row in rows))
        with arcpy.da.SearchCursor(result["raw_points"], ["SHAPE@XY"]) as cursor:
            raw_xy = [row[0] for row in cursor]
        self.assertTrue(all(abs(xy[0] - 12) < 1e-8 and abs(xy[1] - 45) < 1e-8 for xy in raw_xy))
        self.assertEqual(_source_hashes(source), before)

    def test_conflicting_sid_time_publishes_qc_and_failed_manifest_before_raising(self):
        source = self._make_points([
            {"USA_WIND": 70},
            {"ISO_TIME": "2017-09-20 00:00:00", "USA_WIND": 90},
        ])
        before = _source_hashes(source)
        destination = self.root / "conflict"
        with self.assertRaisesRegex(ValueError, "Conflicting SID/timestamp"):
            prepare_hurricane_data(str(source), destination)
        manifest = json.loads((destination / "prepare_manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["status"].startswith("failed"))
        self.assertEqual(manifest["summary"]["row_status_counts"]["CONFLICT"], 2)
        self.assertTrue(self.arcpy.Exists(manifest["qc"]))
        with self.arcpy.da.SearchCursor(manifest["qc"], ["ROW_STATUS", "QC_FLAGS"]) as cursor:
            qc_rows = list(cursor)
        self.assertEqual(len(qc_rows), 2)
        self.assertTrue(all(status == "CONFLICT" and "CONFLICTING_SID_TIME" in flags for status, flags in qc_rows))
        with Path(manifest["canonical_csv"]).open(encoding="utf-8", newline="") as stream:
            csv_rows = list(csv.DictReader(stream))
        self.assertEqual([row["ROW_STATUS"] for row in csv_rows], ["CONFLICT", "CONFLICT"])
        self.assertEqual(_source_hashes(source), before)

    def test_missing_usa_coordinate_is_quarantined_without_merged_fallback(self):
        source = self._make_points([
            {},
            {"USA_LAT": -9999, "USA_LON": -66.45, "LAT": 18.22,
             "LON": -66.45, "geometry": (-66.45, 18.22)},
        ])
        before = _source_hashes(source)
        result = prepare_hurricane_data(str(source), self.root / "quarantine")
        self.assertEqual(result["summary"]["selected_observation_count"], 1)
        self.assertEqual(result["summary"]["row_status_counts"]["QUARANTINED"], 1)
        with self.arcpy.da.SearchCursor(result["observations"], ["SOURCE_OID"]) as cursor:
            self.assertEqual([row[0] for row in cursor], [0])
        with self.arcpy.da.SearchCursor(result["qc"], ["SOURCE_OID", "ROW_STATUS", "QC_FLAGS"]) as cursor:
            qc = {oid: (status, flags) for oid, status, flags in cursor}
        self.assertEqual(qc[1][0], "QUARANTINED")
        self.assertIn("INVALID_USA_COORDINATES", qc[1][1])
        with Path(result["canonical_csv"]).open(encoding="utf-8", newline="") as stream:
            csv_rows = list(csv.DictReader(stream))
        self.assertEqual(csv_rows[1]["ROW_STATUS"], "QUARANTINED")
        self.assertEqual(float(csv_rows[1]["USA_LAT"]), -9999)
        self.assertEqual(csv_rows[1]["NORMALIZED_USA_LAT"], "")
        self.assertEqual(_source_hashes(source), before)


if __name__ == "__main__":
    unittest.main()
