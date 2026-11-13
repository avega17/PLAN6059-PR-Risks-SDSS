import unittest

from utils.validation import grid_errors
from hurricane_winds import build_parser


class GridContractTests(unittest.TestCase):
    def setUp(self):
        self.extent = {'xmin': 1000, 'ymin': 2000, 'xmax': 2000, 'ymax': 2750}
        self.info = {'wkid': 32161, 'cell_width': 250, 'cell_height': 250,
                     'rows': 3, 'columns': 4, 'extent': self.extent.copy()}

    def test_matching_grids(self):
        self.assertEqual(grid_errors(self.info, self.info, self.extent, 3, 4), [])

    def test_shifted_grid_same_size_fails(self):
        shifted = {**self.info, 'extent': {**self.extent, 'xmin': 1125, 'xmax': 2125}}
        self.assertTrue(grid_errors(self.info, shifted, self.extent, 3, 4))

    def test_wrong_units_or_cell_shape_fail(self):
        wrong = {**self.info, 'wkid': 4326, 'cell_height': 249.9}
        self.assertGreaterEqual(len(grid_errors(wrong, self.info, self.extent, 3, 4)), 2)

    def test_prepare_defaults_and_output_folder(self):
        args = build_parser().parse_args(['prepare', '--raw-points', 'input.shp',
                                         '--output-folder', 'with spaces'])
        self.assertEqual((args.start_season, args.end_season), (1955, 2025))
        self.assertEqual(args.output_folder, 'with spaces')


if __name__ == '__main__':
    unittest.main()
