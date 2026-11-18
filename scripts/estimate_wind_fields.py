"""Estimate Wind Fields adapter."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import arcpy
    from hurricane_winds import estimate_wind_fields
    try:
        result = estimate_wind_fields(arcpy.GetParameterAsText(0), arcpy.GetParameterAsText(1) or None)
        arcpy.SetParameterAsText(2, result['catalog'])
    except Exception as error:
        arcpy.AddError(str(error))
        raise


if __name__ == '__main__':
    main()
