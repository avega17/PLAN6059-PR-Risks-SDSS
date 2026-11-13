"""ArcGIS Script Tool adapter for fail-closed prototype validation."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import arcpy
    from hurricane_winds import validate_prototype
    try:
        result = validate_prototype(arcpy.GetParameterAsText(0),
                                    arcpy.GetParameterAsText(1),
                                    arcpy.GetParameterAsText(2))
        arcpy.SetParameterAsText(3, result['report'])
        arcpy.AddMessage('Prototype validation passed. See the report for checks and limitations.')
    except Exception as error:
        arcpy.AddError(str(error))
        raise


if __name__ == '__main__':
    main()
