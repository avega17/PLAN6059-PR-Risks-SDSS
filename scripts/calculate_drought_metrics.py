"""Calculate Drought Metrics Script Tool adapter."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    import arcpy
    from drought import calculate_drought_metrics
    try:
        result = calculate_drought_metrics(arcpy.GetParameterAsText(0))
        arcpy.SetParameterAsText(1,result['catalog'])
    except Exception as error:
        arcpy.AddError(str(error))
        raise


if __name__ == '__main__':
    main()
