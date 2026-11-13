"""ArcGIS Script Tool adapter. Parameter order: docs/modelbuilder_setup.md."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import arcpy
    from hurricane_winds import prepare_hurricane_data
    try:
        result = prepare_hurricane_data(
            arcpy.GetParameterAsText(0), arcpy.GetParameterAsText(1),
            int(arcpy.GetParameterAsText(2) or 1955),
            int(arcpy.GetParameterAsText(3) or 2025),
            arcpy.GetParameterAsText(4) or None,
            arcpy.GetParameterAsText(5) or None)
        for index, key in enumerate(
                ('observations', 'storms', 'qc', 'canonical_csv', 'inventory', 'manifest'), 6):
            arcpy.SetParameterAsText(index, result[key])
        arcpy.AddMessage('Preparation complete. These are storm observations, not local wind estimates.')
    except Exception as error:
        arcpy.AddError(str(error))
        raise


if __name__ == '__main__':
    main()
