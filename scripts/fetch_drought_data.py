"""Script Tool adapter for resumable public USDM acquisition."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    import arcpy
    from drought import fetch_drought_data
    try:
        resume = arcpy.GetParameter(3)
        result = fetch_drought_data(arcpy.GetParameterAsText(0),arcpy.GetParameterAsText(1),
            arcpy.GetParameterAsText(2),True if resume is None else bool(resume),True,
            progress=arcpy.AddMessage,cancelled=lambda:bool(arcpy.env.isCancelled),export_csv=bool(arcpy.GetParameter(4)))
        for index,key in enumerate(('manifest',),5):
            arcpy.SetParameterAsText(index,result[key])
        arcpy.AddMessage(f'Acquisition complete; reference status: {result["reference_qc_status"]}.')
    except Exception as error:
        arcpy.AddError(str(error))
        raise


if __name__ == '__main__':
    main()
