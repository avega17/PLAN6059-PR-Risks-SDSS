"""Add the three matched course map layouts to the ArcGIS Pro project."""
from pathlib import Path
import json
from tempfile import TemporaryDirectory

from .hazard_rank import RELATIVE_METHOD, SUM_COLORS

COURSE_COLORS = {1: (246, 212, 132), 3: (218, 127, 66), 5: (150, 52, 52)}


def rect(arcpy, left, bottom, width, height):
    return arcpy.Polygon(arcpy.Array([arcpy.Point(left+x, bottom+y) for x,y in
        [(0,0), (width,0), (width,height), (0,height), (0,0)]]))


def _rank_legend(rank, report, filename, unit):
    default_report = Path(rank).resolve().parent.parent/'reports'/filename
    result = json.loads(Path(report or default_report).read_text(encoding='utf-8')).get('classification', {})
    if (result.get('status') != 'VALIDATED' or result.get('method') != RELATIVE_METHOD
            or Path(result['rank']).resolve() != Path(rank).resolve()):
        raise ValueError(f'Use the passing relative classification report for {rank}.')
    low, medium = result['upper_count_breaks']
    middle = str(medium) if medium == low+1 else f'{low+1}–{medium}'
    return f'Low: ≤{low} · Medium: {middle} · High: ≥{medium+1} {unit}'


def _set_colors(layer, colors, labels):
    sym = layer.symbology
    sym.updateColorizer('RasterUniqueValueColorizer')
    sym.colorizer.field = 'Value'
    for group in sym.colorizer.groups:
        for value in group.items:
            entry = value.values[0]
            code = int(entry[0] if isinstance(entry, (list, tuple)) else entry)
            value.color = {'RGB':[*colors[code],100]}
            value.label = labels[code]
    layer.symbology = sym


def create_layouts(project, wind_rank, drought_rank, combined, grid_spec,
                   wind_report=None, drought_report=None, pdf=None):
    import arcpy
    import numpy as np
    from .hazard_rank import island_domain
    grid = json.loads(Path(grid_spec).read_text(encoding='utf-8'))
    project = arcpy.mp.ArcGISProject(str(Path(project).resolve()))
    if project.isReadOnly:
        raise ValueError('Close the SDSS ArcGIS Pro project before creating layouts.')
    extent = grid['extent']
    sr = arcpy.SpatialReference(grid['wkid'])
    row, col = np.nonzero(island_domain(arcpy, grid))
    size = grid['cell_size']
    margin = 3000
    map_extent = arcpy.Extent(extent['xmin']+int(col.min())*size-margin,
                              extent['ymax']-(int(row.max())+1)*size-margin,
                              extent['xmin']+(int(col.max())+1)*size+margin,
                              extent['ymax']-int(row.min())*size+margin,
                              spatial_reference=sr)
    class_names = {1:'Low', 3:'Medium', 5:'High'}
    sum_names = {n:str(n) for n in SUM_COLORS}
    wind_breaks = _rank_legend(wind_rank, wind_report, 'validation_report.json', 'storms in 1955–2025')
    drought_breaks = _rank_legend(drought_rank, drought_report, 'download_validation.json',
                                  'qualifying weeks in 2000–2025')
    entries = (
        ('Hurricane wind hazard', wind_rank, COURSE_COLORS, class_names, '1955–2025 · January 2026 reference',
         'Distinct storms with modeled local one-minute sustained winds of at least 64 kt.',
         wind_breaks,
         'NOAA IBTrACS v04r01 · HURRECON · Natural Earth'),
        ('Drought hazard', drought_rank, COURSE_COLORS, class_names, '2000–2025 · January 2026 reference',
         'Average weeks per year in USDM moderate drought (D1) or worse.',
         drought_breaks,
         'U.S. Drought Monitor · Natural Earth'),
        ('Hurricane wind and drought hazard', combined, SUM_COLORS, sum_names,
         'Wind 1955–2025 · Drought 2000–2025 · January 2026 reference',
         'Equal-weight sum of the two hazard classes. Each hazard contributes 1, 3 or 5.',
         'Values 2, 4, 6, 8 and 10 indicate increasing combined class scores.',
         'NOAA IBTrACS v04r01 · HURRECON · U.S. Drought Monitor · Natural Earth'),
    )
    for _, path, *_ in entries:
        if not arcpy.Exists(path):
            raise FileNotFoundError(f'Publish the three course rasters first: {path}')
    # Refresh the combined raster already displayed in a project map as well as the new layout.
    combined_path = Path(combined).resolve()
    for chart in project.listMaps():
        for layer in chart.listLayers():
            if (not layer.isBroken and layer.isRasterLayer and layer.supports('DATASOURCE')
                    and Path(layer.dataSource).resolve() == combined_path):
                _set_colors(layer, SUM_COLORS, sum_names)
    north = project.listStyleItems('ArcGIS 2D', 'NORTH_ARROW', 'ArcGIS North 1')[0]
    scale = project.listStyleItems('ArcGIS 2D', 'SCALE_BAR', 'Alternating Scale Bar 1 Metric')[0]
    titles = []
    for title, path, colors, labels, years, method, breaks, sources in entries:
        name = f'PRRIM · {title}'
        for old in project.listLayouts():
            if old.name == name:
                project.deleteItem(old)
        for old in project.listMaps():
            if old.name == name:
                project.deleteItem(old)
        chart = project.createMap(name)
        for layer in chart.listLayers():
            chart.removeLayer(layer)
        chart.spatialReference = sr
        layer = chart.addDataFromPath(str(Path(path).resolve()))
        _set_colors(layer, colors, labels)
        layout = project.createLayout(11, 7.5, 'INCH', name)
        frame = layout.createMapFrame(rect(arcpy,.6,2.55,9.8,3.3), chart, 'Puerto Rico')
        frame.camera.setExtent(map_extent)
        layout.createMapSurroundElement(arcpy.Point(10,5.45), 'NORTH_ARROW', frame, north)
        layout.createMapSurroundElement(rect(arcpy,.63,2.12,2.4,.22), 'SCALE_BAR', frame, scale)

        def label(x, y, words, size=11, weight='Regular'):
            project.createTextElement(layout, arcpy.Point(x,y), 'POINT', words, size,
                                      'Aptos', weight)

        label(.6, 6.85, title, 25, 'Bold')
        label(.62, 6.42, years, 13)
        label(.62, 6.10, method)
        spacing = 1.48 if len(colors) == 5 else 2.03
        for index, (code, (r,g,b)) in enumerate(colors.items()):
            text = f'{labels[code]} ({code})' if len(colors) == 3 else labels[code]
            label(.62+index*spacing, 1.76, f'<CLR red="{r}" green="{g}" blue="{b}">■</CLR>  {text}')
        label(.62+len(colors)*spacing, 1.76, '□  NoData / outside scope')
        label(.62, 1.36, breaks)
        label(.62, .98, '250 m output grid · NAD83 / Puerto Rico and Virgin Islands (EPSG:32161)', 10)
        label(.62, .68, 'Source observations and models have coarser information support.', 10)
        label(.62, .4, sources, 9)
        titles.append(layout.name)
    project.save()
    result = {'layouts': titles}
    if pdf:
        target = Path(pdf).resolve()
        with TemporaryDirectory(prefix='sdss_layout_pdf_', dir=target.parent) as temporary:
            export = Path(temporary)/'maps.pdf'
            book = arcpy.mp.PDFDocumentCreate(str(export))
            for i, name in enumerate(titles, 1):
                page = str(Path(temporary)/f'page_{i}.pdf')
                project.listLayouts(name)[0].exportToPDF(page, resolution=180)
                book.appendPages(page)
            book.updateDocProperties(pdf_title='Puerto Rico hurricane wind and drought hazard maps')
            book.saveAndClose()
            del book
            export.replace(target)
        result['pdf'] = str(target)
    return result
