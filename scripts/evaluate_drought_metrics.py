"""Evaluate Drought Metrics Script Tool adapter."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    import arcpy
    from drought import evaluate_drought_metrics
    try:
        result = evaluate_drought_metrics(arcpy.GetParameterAsText(0))
        for index,key in enumerate(('primary','valid_count','report'),1):
            arcpy.SetParameterAsText(index,result[key])
    except Exception as error:
        arcpy.AddError(str(error))
        raise


if __name__ == '__main__':
    main()
