"""Prepare Wind Inputs adapter; parameter order is documented in the setup guide."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import arcpy
    from hurricane_winds import prepare_wind_inputs
    try:
        # The saved model retains the former optional storm-list slot at index 3.
        # Production always covers the full catalog.
        result = prepare_wind_inputs(*(arcpy.GetParameterAsText(i) for i in range(3)))
        arcpy.SetParameterAsText(4, result['workspace'])
    except Exception as error:
        arcpy.AddError(str(error))
        raise


if __name__ == '__main__':
    main()
