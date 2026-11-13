"""Render the saved ModelBuilder nodes and links without modifying the toolbox.

Uses matplotlib bundled with ArcGIS Pro. This is a readable rendering of the
saved diagram XML, not a ModelBuilder authoring or native image-export API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import textwrap
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TITLE = 'Hurricane Winds · saved ModelBuilder graph'
DEFAULT_SUBTITLE = 'HurricaneAuditPrototype · three Script Tools · seasons 1955–2025'
DEFAULT_FOOTER = 'Audit prototype only · provisional boundary · no local-wind estimation or hazard ranking'


def export_diagram(toolbox, destination, *, title=DEFAULT_TITLE,
                   subtitle=DEFAULT_SUBTITLE, footer=DEFAULT_FOOTER):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    from matplotlib.path import Path as PlotPath

    with zipfile.ZipFile(toolbox) as archive:
        model = json.loads(archive.read('Model.tool/tool.model'))
        resources = json.loads(archive.read('Model.tool/tool.content.rc'))['map']
        xml = archive.read('Model.tool/tool.model.diagram.xml')
    diagram = ET.fromstring(xml)
    nodes = [node for node in diagram.find('Nodes')
             if node.get('Class', '').endswith('.MBNode')]
    resolve = lambda value: resources.get(value.removeprefix('$rc:'), value)
    processes = {resolve(process['title']) for process in model['processes']}
    generated_ids = {param['element_id'] for process in model['processes']
                     for param in process['params'].values()
                     if param.get('direction') == 'out'}
    generated = {resolve(variable['title']) for variable in model['variables']
                 if variable['id'] in generated_ids}
    bounds = [tuple(map(float, node.findtext('Bounds').split(','))) for node in nodes]
    by_name = {node.findtext('Text'): box for node, box in zip(nodes, bounds)}
    by_id = {node.get('Id'): box for node, box in zip(nodes, bounds)}
    right = max(x + w for x, y, w, h in bounds)
    bottom = max(y + h for x, y, w, h in bounds)
    fig = plt.figure(figsize=(9.6, 12.3), facecolor='#f7fafc')
    axis = fig.add_axes([.04, .085, .92, .79])
    axis.set_xlim(0, right + 20)
    axis.set_ylim(bottom + 20, 0)
    axis.set_aspect('equal')
    axis.axis('off')
    for link in diagram.find('Links'):
        points = [tuple(map(float, point.text.split(','))) for point in link.find('Points')]
        # Route in the gaps between columns so diagonal connectors do not
        # disappear behind unrelated nodes in the saved automatic layout.
        # Persisted IDs remain stable when the visible variable label changes.
        # OriginName may still contain the earlier name after Pro renames it.
        origin = link.find('Origin')
        destination_node = link.find('Destination')
        source = by_id.get(origin.get('Id')) if origin is not None else None
        target = by_id.get(destination_node.get('Id')) if destination_node is not None else None
        source = source or by_name.get(link.findtext('OriginName'))
        target = target or by_name.get(link.findtext('DestinationName'))
        if source and target and source[0] + source[2] < target[0]:
            sx, sy = source[0] + source[2], source[1] + source[3]/2
            tx, ty = target[0], target[1] + target[3]/2
            middle = (sx + tx)/2
            points = [(sx, sy), (middle, sy), (middle, ty), (tx, ty)]
        if len(points) >= 2:
            axis.add_patch(FancyArrowPatch(path=PlotPath(points), arrowstyle='-|>',
                                          mutation_scale=9, linewidth=.8,
                                          color='#5c7080', zorder=1))
    for node, (x, y, width, height) in zip(nodes, bounds):
        node_title = node.findtext('Text')
        fill = '#ffdf86' if node_title in processes else '#e0f0e4' if node_title in generated else '#e4eff8'
        axis.add_patch(FancyBboxPatch((x, y), width, height,
                       boxstyle='round,pad=0,rounding_size=8',
                       facecolor=fill, edgecolor='#52728b', linewidth=.9, zorder=2))
        # Fit long file basenames to the printed node width in wide diagrams.
        wrap_width = min(17, max(10, int(width / (right + 20) * .92 * 9.6 * 72 / (9.3 * .6))))
        axis.text(x + width/2, y + height/2, textwrap.fill(node_title, wrap_width),
                  ha='center', va='center', fontsize=9.3, linespacing=1.25,
                  fontfamily='DejaVu Sans', color='#17384c', zorder=3)
    fig.text(.055, .958, title,
             fontsize=17, weight='bold', color='#17384c')
    fig.text(.055, .933, subtitle,
             fontsize=10, color='#466477')
    for x, label, color in ((.055, 'Inputs', '#e4eff8'), (.27, 'Script Tools', '#ffdf86'),
                            (.535, 'Typed outputs', '#e0f0e4')):
        fig.text(x, .903, '  ' + label + '  ', fontsize=9.5, color='#17384c',
                 bbox={'boxstyle': 'round,pad=.35', 'fc': color, 'ec': '#52728b', 'lw': .6})
    fig.text(.055, .052,
             'Saved ModelBuilder node positions and connections; connectors rerouted for readability.\n'
             'Colors denote roles. Inputs and outputs are exposed as model parameters.',
             fontsize=8.5, color='#466477', linespacing=1.5)
    fig.text(.055, .018, footer,
             fontsize=8.2, color='#466477')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ('.svg', '.png'):
        fig.savefig(destination.with_suffix(suffix), dpi=170, facecolor=fig.get_facecolor())
    plt.close(fig)
    return {'model': resources['title'], 'nodes': len(nodes),
            'links': len(diagram.find('Links')),
            'saved_diagram_sha256': hashlib.sha256(xml).hexdigest(),
            'svg': str(destination.with_suffix('.svg')),
            'png': str(destination.with_suffix('.png'))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolbox', type=Path, default=ROOT/'HurricaneWinds_Model_Toolbox.atbx')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/hurricane_modelbuilder_graph')
    parser.add_argument('--title', default=DEFAULT_TITLE)
    parser.add_argument('--subtitle', default=DEFAULT_SUBTITLE)
    parser.add_argument('--footer', default=DEFAULT_FOOTER)
    arguments = parser.parse_args()
    print(json.dumps(export_diagram(arguments.toolbox, arguments.output,
        title=arguments.title, subtitle=arguments.subtitle, footer=arguments.footer), indent=2))
