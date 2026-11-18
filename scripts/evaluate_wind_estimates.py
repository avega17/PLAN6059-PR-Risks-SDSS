"""Evaluate Wind Estimates adapter."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import arcpy
    from hurricane_winds import evaluate_wind_estimates
    try:
        result = evaluate_wind_estimates(arcpy.GetParameterAsText(0), arcpy.GetParameterAsText(1) or None)
        arcpy.SetParameterAsText(2, result['summary'])
        arcpy.SetParameterAsText(3, result['report'])
    except Exception as error:
        arcpy.AddError(str(error))
        raise


if __name__ == '__main__':
    main()
