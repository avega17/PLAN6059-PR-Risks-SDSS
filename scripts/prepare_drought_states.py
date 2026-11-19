"""Prepare Drought States Script Tool adapter."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    import arcpy
    from drought import prepare_drought_states
    try:
        result = prepare_drought_states(arcpy.GetParameterAsText(0),arcpy.GetParameterAsText(1),
            arcpy.GetParameterAsText(2),arcpy.GetParameter(3) is not False)
        arcpy.SetParameterAsText(4,result['workspace'])
    except Exception as error:
        arcpy.AddError(str(error))
        raise


if __name__ == '__main__':
    main()
