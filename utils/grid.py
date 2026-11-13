"""Create the common, explicitly aligned Puerto Rico analysis grid.

ArcPy is imported only by the execution entry point so the small grid arithmetic
helpers can also be checked with ordinary Python.  Source features are never
repaired or modified in place.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import urllib.request
import uuid
import zipfile


NATURAL_EARTH_URL = (
    "https://naciscdn.org/naturalearth/10m/cultural/"
    "ne_10m_admin_0_countries.zip"
)
NATURAL_EARTH_VERSION = "5.1.1"
NATURAL_EARTH_SHA256 = (
    "ce1ac7036499a0edd641fbc093cd209a98f96a49d2eca8480aaacad35138a7f6"
)
NATURAL_EARTH_STEM = "ne_10m_admin_0_countries"
ISLAND_POINTS = {
    "mainland": (-66.45, 18.22),
    "Vieques": (-65.433, 18.126),
    "Culebra": (-65.3034, 18.3133),
    "Mona": (-67.90, 18.08),
}


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def aligned_extent(bounds, cell_size=250, anchor=(0, 0)):
    """Round (xmin,ymin,xmax,ymax) outward to a finite square-cell lattice."""
    values = tuple(float(value) for value in bounds)
    if len(values) != 4 or not all(math.isfinite(value) for value in values):
        raise ValueError("Grid bounds must contain four finite coordinates.")
    size = float(cell_size)
    origin = tuple(float(value) for value in anchor)
    if not math.isfinite(size) or size <= 0:
        raise ValueError("Cell size must be positive and finite.")
    if len(origin) != 2 or not all(math.isfinite(value) for value in origin):
        raise ValueError("Grid anchor must contain two finite coordinates.")
    xmin, ymin, xmax, ymax = values
    if xmax <= xmin or ymax <= ymin:
        raise ValueError("Grid bounds must have positive width and height.")
    col0 = math.floor((xmin - origin[0]) / size)
    row0 = math.floor((ymin - origin[1]) / size)
    col1 = math.ceil((xmax - origin[0]) / size)
    row1 = math.ceil((ymax - origin[1]) / size)
    return {
        "xmin": origin[0] + col0 * size,
        "ymin": origin[1] + row0 * size,
        "xmax": origin[0] + col1 * size,
        "ymax": origin[1] + row1 * size,
        "columns": col1 - col0,
        "rows": row1 - row0,
    }


def _write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _natural_earth_source(cache_folder):
    """Fetch and verify the pinned archive; verify extracted files on cache hits."""
    cache_folder = Path(cache_folder)
    cache_folder.mkdir(parents=True, exist_ok=True)
    archive = cache_folder / (NATURAL_EARTH_STEM + ".zip")
    receipt_path = cache_folder / "download.json"
    receipt = {}
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not archive.exists():
        temporary = archive.with_suffix(".zip.part")
        request = urllib.request.Request(NATURAL_EARTH_URL, headers={"User-Agent": "PLAN6059-SDSS/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as stream:
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    stream.write(block)
                receipt = {
                    "downloaded_at_utc": _utc_now(),
                    "last_modified_http": response.headers.get("Last-Modified"),
                    "download_url": NATURAL_EARTH_URL,
                }
            if _sha256(temporary) != NATURAL_EARTH_SHA256:
                raise ValueError("Natural Earth archive SHA256 differs from the pinned 5.1.1 archive.")
            os.replace(temporary, archive)
            _write_json(receipt_path, receipt)
        finally:
            if temporary.exists():
                temporary.unlink()
    digest = _sha256(archive)
    if digest != NATURAL_EARTH_SHA256:
        raise ValueError(f"Cached Natural Earth archive failed SHA256 verification: {archive}")
    with zipfile.ZipFile(archive) as bundle:
        version = bundle.read(NATURAL_EARTH_STEM + ".VERSION.txt").decode("utf-8").strip()
        if version != NATURAL_EARTH_VERSION:
            raise ValueError(f"Expected Natural Earth {NATURAL_EARTH_VERSION}; found {version}.")
        for member in bundle.infolist():
            # The selected archive is flat.  Never extract a path outside the cache.
            if Path(member.filename).name != member.filename or not member.filename.startswith(NATURAL_EARTH_STEM + "."):
                raise ValueError("Unexpected path in the Natural Earth archive.")
            contents = bundle.read(member)
            destination = cache_folder / member.filename
            if not destination.exists() or _sha256(destination) != hashlib.sha256(contents).hexdigest():
                destination.write_bytes(contents)
    return str(cache_folder / (NATURAL_EARTH_STEM + ".shp")), {
        "publisher": "Natural Earth",
        "dataset_title": "Admin 0 - Countries, 1:10 million",
        "version": version,
        "download_url": NATURAL_EARTH_URL,
        "dataset_page": "https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-0-countries/",
        "license": "Public domain",
        "license_url": "https://www.naturalearthdata.com/about/terms-of-use/",
        "archive_path": str(archive.resolve()),
        "sha256": digest,
        "accessed_at_utc": _utc_now(),
        "downloaded_at_utc": receipt.get("downloaded_at_utc"),
        "last_modified_http": receipt.get("last_modified_http"),
        "selection": "ADM0_A3 = 'PRI'",
        "mapping_scale": "1:10,000,000",
        "positional_accuracy_m": None,
        "provisional": True,
        "limitations": "Generalized cartographic boundary; 10m means map scale, not 10-metre resolution. Replace with the class-approved boundary when supplied.",
    }


def _repair_working_copy(arcpy, feature_class, check_table):
    arcpy.management.CheckGeometry(feature_class, check_table, "ESRI")
    count = int(arcpy.management.GetCount(check_table)[0])
    report = {"dataset": str(feature_class), "issues_before": count, "repaired": False}
    if count:
        with arcpy.da.SearchCursor(check_table, ["PROBLEM"]) as cursor:
            report["problems"] = dict(Counter(row[0] for row in cursor))
        before = int(arcpy.management.GetCount(feature_class)[0])
        arcpy.management.RepairGeometry(feature_class, "DELETE_NULL", "ESRI")
        arcpy.management.CheckGeometry(feature_class, check_table, "ESRI")
        if int(arcpy.management.GetCount(check_table)[0]):
            raise ValueError(f"Unresolved geometry errors in working copy: {feature_class}")
        report.update(repaired=True, features_before=before, features_after=int(arcpy.management.GetCount(feature_class)[0]))
    return report


def _transformation(arcpy, source_sr, target_sr, extent):
    source_datum = source_sr.GCS.datumName
    target_datum = target_sr.GCS.datumName
    choices = list(arcpy.ListTransformations(source_sr, target_sr, extent))
    if source_datum == target_datum:
        return "", choices
    if not choices:
        raise ValueError(f"No installed transformation covers the boundary extent: {source_datum} -> {target_datum}.")
    return choices[0], choices


def _check_alignment(arcpy, path, spec):
    raster = arcpy.Raster(str(path))
    actual = {
        "wkid": raster.spatialReference.factoryCode,
        "cell_width": raster.meanCellWidth,
        "cell_height": raster.meanCellHeight,
        "rows": raster.height,
        "columns": raster.width,
        "extent": {key: getattr(raster.extent, attr) for key, attr in [("xmin", "XMin"), ("ymin", "YMin"), ("xmax", "XMax"), ("ymax", "YMax")]},
    }
    if actual["wkid"] != spec["wkid"] or actual["rows"] != spec["rows"] or actual["columns"] != spec["columns"]:
        raise ValueError(f"Raster CRS or dimensions do not match the reference specification: {path}")
    numbers = [(actual["cell_width"], spec["cell_size"]), (actual["cell_height"], spec["cell_size"])]
    numbers.extend((actual["extent"][key], spec["extent"][key]) for key in actual["extent"])
    if any(not math.isclose(a, b, rel_tol=0, abs_tol=1e-6) for a, b in numbers):
        raise ValueError(f"Raster cells or extent do not match the reference specification: {path}")
    return actual


def establish_reference_grid(output_folder, boundary=None, cell_size=250):
    """Build a shared EPSG:32161 grid and land mask and return its JSON manifest.

    ``boundary`` may be a polygon feature layer (including its selection), a
    shapefile, or a geodatabase feature class.  When omitted, the pinned Natural
    Earth country boundary is downloaded automatically.  All four island checks
    must pass.  The course grid is fixed at 250 metres and anchored at (0, 0).
    No Spatial Analyst operations are used.
    """
    if float(cell_size) != 250:
        raise ValueError("The course reference grid requires exactly 250-metre cells.")
    import arcpy
    import numpy as np

    if arcpy.ProductInfo() != "ArcInfo":
        raise RuntimeError(
            "Grid generation requires ArcGIS Pro Advanced for Polygon To Raster. "
            "Basic/Standard require a Spatial Analyst or 3D Analyst extension; "
            "this implementation does not check out either extension."
        )
    output = Path(output_folder).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    geodatabase = output / "grid.gdb"
    working = str(geodatabase / "source_boundary")
    projected = str(geodatabase / "study_boundary32161")
    reference = str(output / "reference250.tif")
    mask = str(output / "study_mask250.tif")
    spec_path = str(output / "grid_spec.json")
    manifest_path = str(output / "grid_manifest.json")
    natural_earth = boundary is None or boundary == ""
    if natural_earth:
        boundary, provenance = _natural_earth_source(output / "_cache" / "naturalearth-5.1.1")
    else:
        provenance = {
            "publisher": "User-supplied / class boundary",
            "input": str(boundary),
            "version": None,
            "mapping_scale": None,
            "positional_accuracy_m": None,
            "provisional": False,
            "accessed_at_utc": _utc_now(),
            "limitations": "Source version, scale, positional accuracy and license must be supplied in the project inventory.",
        }
    description = arcpy.Describe(boundary)
    if getattr(description, "shapeType", None) != "Polygon":
        raise ValueError("Study boundary must be a polygon feature layer or feature class.")
    if description.spatialReference.name == "Unknown":
        raise ValueError("Study boundary needs its true source coordinate system defined before projection.")
    catalog_path = str(description.catalogPath)
    if os.path.normcase(catalog_path) in {os.path.normcase(working), os.path.normcase(projected)}:
        raise ValueError("The input boundary must not be one of this operation's output feature classes.")
    provenance["catalog_path"] = catalog_path
    provenance["source_crs"] = {"name": description.spatialReference.name, "wkid": description.spatialReference.factoryCode}
    if Path(catalog_path).is_file():
        provenance["file_sha256"] = _sha256(catalog_path)
        if Path(catalog_path).suffix.lower() == ".shp":
            provenance["sidecar_sha256"] = {
                str(path.name): _sha256(path)
                for path in sorted(Path(catalog_path).parent.glob(Path(catalog_path).stem + ".*"))
                if path.suffix.lower() in {".shp", ".shx", ".dbf", ".prj", ".cpg"}
            }
    target = arcpy.SpatialReference(32161)
    layer = "grid_source_" + uuid.uuid4().hex
    arcpy.AddMessage("Establishing the 250 m Puerto Rico reference grid in EPSG:32161.")
    # Reset inherited analysis environments so a caller's mask, selection extent,
    # snap grid or output projection cannot alter the reference grid.
    with arcpy.EnvManager(
        outputCoordinateSystem=None, geographicTransformations="", extent=None,
        mask=None, snapRaster=None, cellSize=None, overwriteOutput=True,
        XYTolerance=None, XYResolution=None,
    ):
        if not arcpy.Exists(str(geodatabase)):
            arcpy.management.CreateFileGDB(str(output), geodatabase.name)
        try:
            if natural_earth:
                arcpy.management.MakeFeatureLayer(boundary, layer, "ADM0_A3 = 'PRI'")
                arcpy.management.CopyFeatures(layer, working)
            else:
                arcpy.management.CopyFeatures(boundary, working)
        finally:
            if arcpy.Exists(layer):
                arcpy.management.Delete(layer)
        if not int(arcpy.management.GetCount(working)[0]):
            raise ValueError("Study boundary selection contains no polygons.")
        repairs = [_repair_working_copy(arcpy, working, str(geodatabase / "geometry_check_source"))]
        source_description = arcpy.Describe(working)
        transform, candidates = _transformation(arcpy, source_description.spatialReference, target, source_description.extent)
        arcpy.management.Project(working, projected, target, transform)
        repairs.append(_repair_working_copy(arcpy, projected, str(geodatabase / "geometry_check_projected")))
        if not int(arcpy.management.GetCount(projected)[0]):
            raise ValueError("No boundary polygons remain after geometry validation and projection.")
        geometries = [row[0] for row in arcpy.da.SearchCursor(projected, ["SHAPE@"])]
        island_checks = {}
        point_transform, _ = _transformation(arcpy, arcpy.SpatialReference(4326), target, arcpy.Extent(-68, 17.5, -65, 19))
        for name, (longitude, latitude) in ISLAND_POINTS.items():
            point = arcpy.PointGeometry(arcpy.Point(longitude, latitude), arcpy.SpatialReference(4326)).projectAs(target, point_transform)
            covered = any(geometry.contains(point) for geometry in geometries)
            island_checks[name] = {"longitude": longitude, "latitude": latitude, "boundary_contains_point": covered, "x": point.firstPoint.X, "y": point.firstPoint.Y}
        missing = [name for name, check in island_checks.items() if not check["boundary_contains_point"]]
        if missing:
            raise ValueError("Boundary omits required island check locations: " + ", ".join(missing))
        extent = arcpy.Describe(projected).extent
        lattice = aligned_extent((extent.XMin, extent.YMin, extent.XMax, extent.YMax))
        spec = {
            "schema_version": 1,
            "created_at_utc": _utc_now(),
            "wkid": 32161,
            "coordinate_system": target.name,
            "linear_unit": "metre",
            "cell_size": 250,
            "anchor": {"x": 0, "y": 0},
            "extent": {key: lattice[key] for key in ("xmin", "ymin", "xmax", "ymax")},
            "rows": lattice["rows"],
            "columns": lattice["columns"],
            "projected_boundary": projected,
            "reference_raster": reference,
            "mask_raster": mask,
            "grid_spec_path": spec_path,
            "manifest": manifest_path,
            "boundary_source": provenance,
            "geographic_transformation": transform or None,
            "transformation_candidates": candidates,
            "island_point_transformation": point_transform or None,
            "geometry_checks": repairs,
            "boundary_features": len(geometries),
            "boundary_parts": sum(geometry.partCount for geometry in geometries),
            "island_checks": island_checks,
            "mask_rule": "CELL_CENTER; land = 1; outside boundary = NoData",
            "reference_rule": "Integer constant 0 over the complete aligned rectangle; not a hazard score or coverage mask",
            "arcgis_pro_version": arcpy.GetInstallInfo().get("Version"),
            "license": {"product": arcpy.ProductInfo(), "required_product": "ArcGIS Pro Advanced", "spatial_analyst_used": False, "conversion_tool": "PolygonToRaster"},
        }
        lower_left = arcpy.Point(lattice["xmin"], lattice["ymin"])
        array = np.zeros((lattice["rows"], lattice["columns"]), dtype=np.int16)
        with arcpy.EnvManager(outputCoordinateSystem=target):
            raster = arcpy.NumPyArrayToRaster(array, lower_left, 250, 250)
            raster.save(reference)
            del raster
            arcpy.management.DefineProjection(reference, target)
        fields = {field.name.upper(): field for field in arcpy.ListFields(projected)}
        if "GRID_MASK" in fields and fields["GRID_MASK"].type != "SmallInteger":
            # A caller may have an unrelated field with this name; only the
            # projected working copy is altered, and the mask stays integer.
            arcpy.management.DeleteField(projected, "GRID_MASK")
            del fields["GRID_MASK"]
        if "GRID_MASK" not in fields:
            arcpy.management.AddField(projected, "GRID_MASK", "SHORT")
        arcpy.management.CalculateField(projected, "GRID_MASK", "1", "PYTHON3")
        with arcpy.EnvManager(
            outputCoordinateSystem=target, cellSize=250, snapRaster=reference,
            extent=arcpy.Extent(lattice["xmin"], lattice["ymin"], lattice["xmax"], lattice["ymax"]),
            mask=None,
        ):
            arcpy.conversion.PolygonToRaster(projected, "GRID_MASK", mask, "CELL_CENTER", "NONE", 250)
        spec["alignment_checks"] = {
            "reference": _check_alignment(arcpy, reference, spec),
            "mask": _check_alignment(arcpy, mask, spec),
        }
        for name, check in island_checks.items():
            value = arcpy.management.GetCellValue(mask, f"{check['x']} {check['y']}")[0]
            check["mask_value"] = value
            if value != "1":
                raise ValueError(f"The 250 m land mask omits the {name} check cell.")
        # A sentinel distinct from zero verifies that unclassified background is
        # actually NoData; a raster containing valid zero cells is not a mask.
        mask_array = arcpy.RasterToNumPyArray(mask, nodata_to_value=255)
        if not set(np.unique(mask_array)).issubset({1, 255}) or not np.any(mask_array == 1):
            raise ValueError("Land mask must contain 1 on land and NoData outside land.")
        spec["land_cells"] = int(np.count_nonzero(mask_array == 1))
        spec["reference_cells"] = int(array.size)
        spec["land_area_grid_m2"] = spec["land_cells"] * 250 * 250
        _write_json(spec_path, spec)
        _write_json(manifest_path, spec)
    arcpy.AddMessage(f"Reference grid: {spec['columns']} columns x {spec['rows']} rows; {spec['land_cells']} land cells.")
    return spec
