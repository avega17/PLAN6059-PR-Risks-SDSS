"""Publish the hurricane wind score and the course 1/3/5 ranking."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import arcpy
    from hurricane_winds import classify_wind
    try:
        result = classify_wind(*(arcpy.GetParameterAsText(i) for i in range(3)))
        arcpy.SetParameterAsText(3, result['score'])
        arcpy.SetParameterAsText(4, result['rank'])
    except Exception as error:
        arcpy.AddError(str(error))
        raise


if __name__ == '__main__':
    main()
