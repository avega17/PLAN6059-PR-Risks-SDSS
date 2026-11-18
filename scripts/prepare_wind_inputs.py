"""Prepare Wind Inputs adapter; parameter order is documented in the setup guide."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import arcpy
    from hurricane_winds import prepare_wind_inputs
    try:
        result = prepare_wind_inputs(*(arcpy.GetParameterAsText(i) or None for i in range(4)))
        arcpy.SetParameterAsText(4, result['workspace'])
    except Exception as error:
        arcpy.AddError(str(error))
        raise


if __name__ == '__main__':
    main()
