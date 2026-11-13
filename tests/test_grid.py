"""Grid arithmetic checks; set RUN_ARCPY_INTEGRATION=1 for actual GIS checks."""

import importlib.util
import math
import os
from pathlib import Path
import tempfile
import unittest

from utils.grid import ISLAND_POINTS, aligned_extent, establish_reference_grid


class GridArithmeticTests(unittest.TestCase):
    def test_rounds_outward_on_both_sides_of_zero(self):
        grid = aligned_extent((-1, -251, 251, 1))
        self.assertEqual(grid, {"xmin": -250, "ymin": -500, "xmax": 500, "ymax": 250, "columns": 3, "rows": 3})

    def test_exact_edges_are_not_enlarged(self):
        grid = aligned_extent((250, 500, 1000, 1500))
        self.assertEqual((grid["xmin"], grid["ymin"], grid["xmax"], grid["ymax"]), (250, 500, 1000, 1500))
        self.assertEqual((grid["columns"], grid["rows"]), (3, 4))

    def test_dimensions_and_origin_reconstruct_extent(self):
        grid = aligned_extent((90001.2, 159873.4, 346432.1, 284012.7))
        self.assertEqual(grid["xmax"], grid["xmin"] + 250 * grid["columns"])
        self.assertEqual(grid["ymax"], grid["ymin"] + 250 * grid["rows"])
        for key in ("xmin", "ymin", "xmax", "ymax"):
            self.assertEqual(grid[key] % 250, 0)

    def test_rejects_invalid_extent_or_size(self):
        for bounds in [(0, 0, 0, 1), (1, 0, 0, 1), (0, 1, 1, 0), (0, 0, math.nan, 1), (0, 0, math.inf, 1), (0, 0, 1)]:
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                aligned_extent(bounds)
        for size in [0, -1, math.inf, math.nan]:
            with self.subTest(size=size), self.assertRaises(ValueError):
                aligned_extent((0, 0, 1, 1), size)

    def test_execution_rejects_non_course_cell_size_before_loading_arcpy(self):
        with self.assertRaisesRegex(ValueError, "exactly 250"):
            establish_reference_grid("unused", cell_size=1000)


@unittest.skipUnless(os.environ.get("RUN_ARCPY_INTEGRATION") == "1" and importlib.util.find_spec("arcpy"), "Opt-in ArcPy integration test")
class ArcPyGridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import arcpy
        cls.arcpy = arcpy
        cls.temporary = tempfile.TemporaryDirectory(prefix="plan6059-grid-")
        # A conflicting caller environment must not change the generated grid.
        with arcpy.EnvManager(extent=arcpy.Extent(0, 0, 10, 10), cellSize=1000, outputCoordinateSystem=arcpy.SpatialReference(4326)):
            cls.grid = establish_reference_grid(cls.temporary.name)
            cls.restored_cell_size = arcpy.env.cellSize

    @classmethod
    def tearDownClass(cls):
        cls.arcpy.management.ClearWorkspaceCache()
        target = Path(cls.temporary.name).resolve()
        if target.parent != Path(tempfile.gettempdir()).resolve() or not target.name.startswith("plan6059-grid-"):
            raise RuntimeError("Refusing to clean an unexpected integration-test directory.")
        cls.temporary.cleanup()

    def test_grid_ignores_then_restores_inherited_environments(self):
        self.assertEqual(float(self.restored_cell_size), 1000)
        self.assertEqual(self.grid["wkid"], 32161)
        self.assertEqual(self.grid["cell_size"], 250)
        self.assertEqual(self.grid["alignment_checks"]["reference"], self.grid["alignment_checks"]["mask"])

    def test_default_boundary_covers_all_four_required_islands(self):
        self.assertEqual(set(self.grid["island_checks"]), set(ISLAND_POINTS))
        self.assertTrue(all(check["boundary_contains_point"] and check["mask_value"] == "1" for check in self.grid["island_checks"].values()))
        self.assertEqual(self.grid["boundary_parts"], 4)
        self.assertTrue(self.grid["boundary_source"]["provisional"])

    def test_reference_is_zero_rectangle_and_mask_has_nodata(self):
        import numpy as np
        reference = self.arcpy.RasterToNumPyArray(self.grid["reference_raster"])
        mask = self.arcpy.RasterToNumPyArray(self.grid["mask_raster"], nodata_to_value=255)
        self.assertTrue(np.all(reference == 0))
        self.assertEqual(set(np.unique(mask)), {1, 255})
        self.assertGreater(self.grid["land_cells"], 0)
        self.assertLess(self.grid["land_cells"], self.grid["reference_cells"])
        self.assertTrue(Path(self.grid["manifest"]).is_file())
        self.assertTrue(Path(self.grid["grid_spec_path"]).is_file())

    def test_replacement_boundary_is_preserved(self):
        source = self.grid["projected_boundary"]
        before_fields = [(field.name, field.type) for field in self.arcpy.ListFields(source)]
        with self.arcpy.da.SearchCursor(source, ["SHAPE@WKB"]) as cursor:
            before_geometry = [bytes(row[0]) for row in cursor]
        replacement = establish_reference_grid(Path(self.temporary.name) / "replacement", boundary=source)
        self.assertFalse(replacement["boundary_source"]["provisional"])
        self.assertEqual(replacement["extent"], self.grid["extent"])
        self.assertEqual([(field.name, field.type) for field in self.arcpy.ListFields(source)], before_fields)
        with self.arcpy.da.SearchCursor(source, ["SHAPE@WKB"]) as cursor:
            self.assertEqual([bytes(row[0]) for row in cursor], before_geometry)


if __name__ == "__main__":
    unittest.main()
