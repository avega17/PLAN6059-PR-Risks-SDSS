"""Publish the drought score and the course 1/3/5 ranking."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import arcpy
    from drought import classify_drought
    try:
        result = classify_drought(*(arcpy.GetParameterAsText(i) for i in range(3)))
        arcpy.SetParameterAsText(3, result['score'])
        arcpy.SetParameterAsText(4, result['rank'])
    except Exception as error:
        arcpy.AddError(str(error))
        raise


if __name__ == '__main__':
    main()
