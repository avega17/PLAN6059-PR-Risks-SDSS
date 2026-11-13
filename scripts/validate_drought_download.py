"""Script Tool adapter: failed acquisition validation fails the GP tool."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    import arcpy
    from drought import validate_drought_download
    try:
        result = validate_drought_download(arcpy.GetParameterAsText(0),arcpy.GetParameterAsText(1))
        arcpy.SetParameterAsText(2,result['report'])
        arcpy.AddMessage('Download validation passed; spatial readiness gates remain in the report.')
    except Exception as error:
        arcpy.AddError(str(error))
        raise


if __name__ == '__main__':
    main()
