"""ArcGIS Script Tool adapter for the provisional Puerto Rico reference grid."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import arcpy
    from hurricane_winds import establish_reference_grid
    try:
        result = establish_reference_grid(arcpy.GetParameterAsText(0),
                                          boundary=arcpy.GetParameterAsText(1) or None)
        for index, key in enumerate(
                ('reference_raster', 'mask_raster', 'projected_boundary',
                 'grid_spec_path', 'manifest'), 2):
            arcpy.SetParameterAsText(index, result[key])
        arcpy.AddMessage('Provisional 250 m grid created; coastline generalization remains documented.')
    except Exception as error:
        arcpy.AddError(str(error))
        raise


if __name__ == '__main__':
    main()
