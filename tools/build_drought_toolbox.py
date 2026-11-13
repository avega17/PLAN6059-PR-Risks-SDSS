"""Create the portable Drought Script Tools without editing an open Hurricane toolbox."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.build_toolbox import ROOT, build_toolbox, verify_toolbox
from tools.drought_tool_specs import DROUGHT_TOOLS


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--overwrite',action='store_true')
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    path=build_toolbox(ROOT/'DroughtRisk_Model_Toolbox.atbx',args.overwrite,tools=DROUGHT_TOOLS,alias='droughtprobe',
        title='Puerto Rico SDSS - Drought Acquisition',
        description='Plan, fetch and validate public USDM data. Rasterization, temporal hazard metrics and ranking are later stages.')
    result={'toolbox':str(path),'tools':[tool['name'] for tool in DROUGHT_TOOLS]}
    if args.verify:result['verification']=verify_toolbox(path,DROUGHT_TOOLS)
    print(json.dumps(result,indent=2))
