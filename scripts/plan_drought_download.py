"""Script Tool adapter; parameter contract in docs/drought_modelbuilder_setup.md."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    import arcpy
    from drought import plan_drought_download
    try:
        include = arcpy.GetParameter(4)
        result = plan_drought_download(arcpy.GetParameter(0),arcpy.GetParameter(1),
            arcpy.GetParameterAsText(2),arcpy.GetParameterAsText(3) or None,
            True if include is None else bool(include),
            int(arcpy.GetParameterAsText(5) or 3),arcpy.GetParameterAsText(6) or 'Baseline',True)
        arcpy.SetParameterAsText(7,result['plan'])
        arcpy.SetParameterAsText(8,result['expected_weeks'])
        arcpy.AddMessage(f'Planned {result["baseline_count"]} baseline dates; buffers are separate.')
    except Exception as error:
        arcpy.AddError(str(error))
        raise


if __name__ == '__main__':
    main()
