"""Prepare auditable IBTrACS observations without changing source data.

Pure normalization helpers have no ArcGIS dependency. ArcPy is imported only by
``prepare_hurricane_data``; run that function with ArcGIS Pro's Python runtime.
"""

from __future__ import annotations

import collections
import csv
import datetime as dt
import hashlib
import json
import math
import pathlib
import re
import shutil
import struct
import tempfile


UTC = dt.timezone.utc
TECHNICAL_DETAILS = "https://www.ncei.noaa.gov/sites/default/files/2025-04/IBTrACS_version4r01_Technical_Details.pdf"
COLUMN_DETAILS = "https://www.ncei.noaa.gov/sites/default/files/2025-09/IBTrACS_v04r01_column_documentation.pdf"
SPC_DETAILS = "https://www.spc.noaa.gov/gis/svrgis/"
RADII = tuple(f"USA_R{speed}_{quadrant}" for speed in (34, 50, 64)
              for quadrant in ("NE", "SE", "SW", "NW"))
NORMALIZED_COLUMNS = ("USA_LAT", "USA_LON", "USA_WIND", "WMO_WIND", "USA_PRES", "USA_RMW",
                      "USA_ROCI", "USA_POCI", "USA_EYE", "STORM_SPD", "STORM_DR") + RADII
IFLAG_DESCRIPTIONS = {
    "O": "Original agency report",
    "P": "Position and other variables interpolated or filled",
    "I": "Original position; intensity interpolated or filled",
    "V": "Original position and intensity; other variables interpolated or filled",
    "_": "No agency information",
}


def usa_iflag(value):
    """Return the USA character; do not invent a native USA_IFLAG source field."""
    value = str(value or "").strip()
    if len(value) != 15 or value[0] not in IFLAG_DESCRIPTIONS:
        raise ValueError("IFLAG must contain 15 characters and a recognized USA flag")
    return value[0]


def parse_utc(value):
    """Parse the source UTC timestamp, including special observation times."""
    value = str(value).strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", value):
        raise ValueError("ISO_TIME must use YYYY-MM-DD HH:mm:ss in UTC")
    return dt.datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)


def is_hurricane_status(status):
    """NATURE=TS is tropical; USA_STATUS=ET is extrapolated."""
    return str(status or "").strip().upper() in {"HU", "HR", "TY", "ST"}


def normalize_numeric(field, value):
    """Normalize documented missing values without destroying valid negatives/zero.

    Returns ``(number_or_none, reason_or_none)``. Sentinel families are matched to
    physical fields, not applied to classifications such as negative USA_SSHS.
    Units stay native: knots for wind/motion and nautical miles for USA radii.
    """
    if value is None or str(value).strip() in {"", "*"}:
        return None, "blank"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, "invalid_numeric"
    if not math.isfinite(number):
        return None, "nonfinite"
    field = field.upper()
    coordinate = field in {"LAT", "LON"} or field.endswith(("_LAT", "_LON"))
    physical = coordinate or field.endswith(("_WIND", "_PRES", "_GUST", "_GUSTP", "_RMW", "_ROCI", "_POCI", "_EYE"))
    physical = physical or bool(re.search(r"_R\d+_(NE|SE|SW|NW|L|S|DR)$", field))
    physical = physical or field in {"DIST2LAND", "LANDFALL", "STORM_SPD", "STORM_DR"}
    dvorak = field.endswith(("_CI", "_TNUM", "_DP"))
    sentinels = {-9999.0, -999.0} if physical else set()
    if coordinate or dvorak:
        sentinels |= {-9999.0, -999.0, -999.9}
    if any(math.isclose(number, missing, rel_tol=0, abs_tol=1e-6) for missing in sentinels):
        return None, "sentinel"
    return number, None


def normalize_record(attributes):
    """Return normalized attributes and QC flags; keep weak observations visible."""
    values = dict(attributes)
    flags = []
    reasons = {}
    for field, value in attributes.items():
        if isinstance(value, (int, float)) or field in NORMALIZED_COLUMNS:
            number, reason = normalize_numeric(field, value)
            if reason:
                values[field] = None
                reasons[field] = reason
                if reason != "blank":
                    flags.append(f"{reason.upper()}:{field}")
            else:
                values[field] = int(number) if isinstance(value, int) else number
    try:
        flag = usa_iflag(attributes.get("IFLAG"))
    except ValueError:
        flag = "?"
        flags.append("INVALID_IFLAG")
    if flag in {"P", "I", "V"}:
        flags.append(f"USA_FLAG_{flag}")
    if not str(attributes.get("USA_AGENCY") or "").strip():
        flags.append("MISSING_USA_AGENCY")
    if values.get("USA_WIND") is None:
        flags.append("MISSING_USA_WIND")
    elif values["USA_WIND"] < 0 or values["USA_WIND"] > 300:
        flags.append("OUT_OF_RANGE_USA_WIND")
    for speed in (34, 50, 64):
        fields = [f"USA_R{speed}_{quadrant}" for quadrant in ("NE", "SE", "SW", "NW")]
        if any(values.get(field) is None for field in fields):
            flags.append(f"INCOMPLETE_R{speed}")
        if any(values.get(field) is not None and values[field] < 0 for field in fields):
            flags.append(f"NEGATIVE_R{speed}")
    return values, flag, flags, reasons


def classify_records(records, start_season=1955, end_season=2025):
    """Apply filters, quarantine malformed records, and distinguish duplicates.

    Each input has ``attributes``, ``source_oid``, and ``geometry_hash``. Results
    preserve the input dictionaries and add normalized values, status and flags.
    Conflicts are returned so the caller can publish QC before raising an error.
    """
    if int(start_season) > int(end_season):
        raise ValueError("start_season must not exceed end_season")
    results, seen = [], {}
    for record in records:
        result = dict(record)
        attrs = record["attributes"]
        values, flag, flags, reasons = normalize_record(attrs)
        result.update(values=values, usa_iflag=flag, qc_flags=flags,
                      normalization_reasons=reasons, observation_time=None)
        result["row_status"] = "INCLUDED"
        if str(attrs.get("TRACK_TYPE") or "").strip().lower() != "main":
            result["row_status"] = "EXCLUDED_TRACK_TYPE"
        try:
            season = int(attrs.get("SEASON"))
        except (TypeError, ValueError, OverflowError):
            season = None
        if season is None:
            flags.append("INVALID_SEASON")
            result["row_status"] = "QUARANTINED"
        elif result["row_status"] == "INCLUDED" and not int(start_season) <= season <= int(end_season):
            result["row_status"] = "EXCLUDED_SEASON"
        sid = str(attrs.get("SID") or "").strip()
        if not re.fullmatch(r"\d{7}[NS]\d{5}", sid):
            flags.append("INVALID_SID")
            if result["row_status"] == "INCLUDED":
                result["row_status"] = "QUARANTINED"
        try:
            result["observation_time"] = parse_utc(attrs.get("ISO_TIME"))
        except (TypeError, ValueError):
            flags.append("INVALID_ISO_TIME")
            if result["row_status"] == "INCLUDED":
                result["row_status"] = "QUARANTINED"
        lat, lon = values.get("USA_LAT"), values.get("USA_LON")
        coordinates_valid = lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180
        if not coordinates_valid or (lat == 0 and lon == 0):
            flags.append("INVALID_USA_COORDINATES")
            if result["row_status"] == "INCLUDED":
                result["row_status"] = "QUARANTINED"
        if result["row_status"] == "INCLUDED":
            key = (sid, result["observation_time"])
            fingerprint = (tuple(sorted(attrs.items())), record.get("geometry_hash"))
            if key in seen:
                prior, original_fingerprint = seen[key]
                if fingerprint == original_fingerprint:
                    result["row_status"] = "DUPLICATE_EXACT"
                    flags.append("DUPLICATE_EXACT")
                else:
                    result["row_status"] = "CONFLICT"
                    flags.append("CONFLICTING_SID_TIME")
                    prior["row_status"] = "CONFLICT"
                    if "CONFLICTING_SID_TIME" not in prior["qc_flags"]:
                        prior["qc_flags"].append("CONFLICTING_SID_TIME")
            else:
                seen[key] = (result, fingerprint)
        results.append(result)
    return results


def _read_dbf(path):
    """Read DBF attributes directly so blank numeric cells are not silently zeroed."""
    with path.open("rb") as stream:
        header = stream.read(32)
        count = struct.unpack("<I", header[4:8])[0]
        header_length, row_length = struct.unpack("<HH", header[8:12])
        fields, offset = [], 1
        while stream.tell() < header_length - 1:
            descriptor = stream.read(32)
            if descriptor[0] == 13:
                break
            name = descriptor[:11].split(b"\0")[0].decode("ascii")
            fields.append({"name": name, "dbf_type": chr(descriptor[11]),
                           "length": descriptor[16], "decimals": descriptor[17], "offset": offset})
            offset += descriptor[16]
        stream.seek(header_length)
        rows = []
        for oid in range(count):
            raw = stream.read(row_length)
            if len(raw) != row_length:
                raise ValueError(f"Truncated DBF record {oid}: {path}")
            if raw[0:1] == b"*":
                continue
            attrs, raw_attrs = {}, {}
            for field in fields:
                value = raw[field["offset"]:field["offset"] + field["length"]].decode("utf-8", errors="replace").strip()
                raw_attrs[field["name"]] = value
                if field["dbf_type"] in {"N", "F"}:
                    if not value or set(value) == {"*"}:
                        parsed = None
                    else:
                        try:
                            parsed = float(value) if field["decimals"] else int(value)
                        except ValueError:
                            parsed = value
                    attrs[field["name"]] = parsed
                else:
                    attrs[field["name"]] = value
            rows.append({"source_oid": oid, "attributes": attrs, "raw_attributes": raw_attrs})
    return fields, rows, count


def _geometry_records(path):
    """Read exact geometry hashes and point XY for the provenance comparison."""
    records = []
    with path.open("rb") as stream:
        stream.seek(100)
        while True:
            header = stream.read(8)
            if not header:
                break
            if len(header) != 8:
                raise ValueError("Truncated shapefile record header")
            _, length = struct.unpack(">ii", header)
            content = stream.read(length * 2)
            if len(content) != length * 2:
                raise ValueError("Truncated shapefile geometry")
            shape_type = struct.unpack("<i", content[:4])[0]
            xy = struct.unpack("<2d", content[4:20]) if shape_type in {1, 11, 21} else None
            records.append({"hash": hashlib.sha256(content).hexdigest(), "xy": xy})
    return records


def _require_point_geometry(geometry_type):
    if str(geometry_type).casefold() != "point":
        raise ValueError("Raw Points must be a Point shapefile; track lines are an optional inventory input")


def _coordinate_differences(records, threshold=0.01):
    """Compare raw WGS84 geometry with USA positions, not positional accuracy."""
    compared = different = missing = 0
    largest = 0.0
    for record in records:
        xy = record.get("raw_geometry_xy")
        lon, lat = record["values"].get("USA_LON"), record["values"].get("USA_LAT")
        if xy is None or lon is None or lat is None:
            missing += 1
            continue
        difference = max(abs(xy[0] - lon), abs(xy[1] - lat))
        compared += 1
        different += difference > threshold + 1e-6
        largest = max(largest, difference)
    return {"compared_observations": compared, "unavailable_comparisons": missing,
            "difference_threshold_degrees": threshold,
            "observations_exceeding_either_axis_threshold": different,
            "maximum_absolute_axis_difference_degrees": largest if compared else None,
            "interpretation": "Difference between source merged geometry and USA positions; not an accuracy or uncertainty estimate"}


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stage(source, output, name):
    source = pathlib.Path(source).resolve()
    if source.suffix.lower() != ".shp" or not source.is_file():
        raise ValueError(f"Expected an existing .shp file: {source}")
    for suffix in (".shp", ".shx", ".dbf", ".prj"):
        if not source.with_suffix(suffix).is_file():
            raise ValueError(f"Required shapefile sidecar is missing: {source.with_suffix(suffix)}")
    folder = output / "staged_inputs" / name
    folder.mkdir(parents=True, exist_ok=True)
    inventory = []
    for component in sorted(source.parent.glob(source.stem + ".*")):
        if not component.is_file():
            continue
        tail = component.name[len(source.stem):]
        target = folder / (name + tail)
        source_hash = _hash(component)
        shutil.copy2(component, target)
        staged_hash = _hash(target)
        if source_hash != staged_hash:
            raise RuntimeError(f"Staging checksum mismatch: {component}")
        inventory.append({"source": str(component), "safe_basename": target.name,
                          "size_bytes": component.stat().st_size, "sha256": source_hash})
    return folder / (name + ".shp"), inventory


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def _add_fields(arcpy, table, definitions):
    arcpy.management.AddFields(str(table), [[name, kind, "", length if kind == "TEXT" else None]
                                          for name, kind, length in definitions])


def _source_metadata(arcpy, path, kind):
    """Describe staged sources and scan only date/season cells, not full records."""
    description = arcpy.Describe(str(path))
    extent = description.extent
    coverage = {"first_observation": None, "last_observation": None,
                "first_season": None, "last_season": None}
    with path.with_suffix(".dbf").open("rb") as stream:
        header = stream.read(32)
        count = struct.unpack("<I", header[4:8])[0]
        header_length, row_length = struct.unpack("<HH", header[8:12])
        columns, offset = {}, 1
        while stream.tell() < header_length - 1:
            descriptor = stream.read(32)
            if descriptor[0] == 13:
                break
            name = descriptor[:11].split(b"\0")[0].decode("ascii")
            columns[name] = (offset, descriptor[16])
            offset += descriptor[16]
        time_name, season_name = ("date", "yr") if kind == "spc_reports" else ("ISO_TIME", "SEASON")
        stream.seek(header_length)
        for _ in range(count):
            row = stream.read(row_length)
            if len(row) != row_length:
                raise ValueError("Truncated source DBF during inventory")
            if row[:1] == b"*":
                continue
            for name, first, last in ((time_name, "first_observation", "last_observation"),
                                      (season_name, "first_season", "last_season")):
                if name not in columns:
                    continue
                start, length = columns[name]
                value = row[start:start + length].decode("ascii", errors="replace").strip()
                if not value:
                    continue
                if first.endswith("season"):
                    try:
                        value = int(value)
                    except ValueError:
                        continue
                if coverage[first] is None or value < coverage[first]:
                    coverage[first] = value
                if coverage[last] is None or value > coverage[last]:
                    coverage[last] = value
    spc = kind == "spc_reports"
    return {"publisher": "NOAA National Weather Service Storm Prediction Center" if spc else "NOAA National Centers for Environmental Information (NCEI)",
            "dataset_title": "SPC United States severe thunderstorm wind reports, paths" if spc else "International Best Track Archive for Climate Stewardship (IBTrACS), North Atlantic " + kind,
            "version": None if spc else "v04r01", "authoritative_product_url": SPC_DETAILS if spc else "https://www.ncei.noaa.gov/products/international-best-track-archive",
            "original_download_url": None, "original_acquired_date": None,
            "license_or_use_restrictions": "Not verified; consult publisher product documentation",
            "geometry_type": description.shapeType, "row_count": count,
            "coordinate_reference_system": {"name": description.spatialReference.name,
                                              "wkid": description.spatialReference.factoryCode,
                                              "wkt": description.spatialReference.exportToString()},
            "extent": [extent.XMin, extent.YMin, extent.XMax, extent.YMax],
            "observation_coverage": coverage,
            "role": "Auxiliary severe thunderstorm inventory only; excluded from hurricane observations" if spc else "Primary observation source" if kind == "points" else "Auxiliary merged-position track lines; not used for prepared USA geometry"}


def _publish_qc(arcpy, path, records):
    if arcpy.Exists(str(path)):
        arcpy.management.Delete(str(path))
    arcpy.management.CreateTable(str(path.parent), path.name)
    _add_fields(arcpy, path, [("SOURCE_OID", "LONG", None), ("SID", "TEXT", 32),
                             ("ISO_TIME", "TEXT", 32), ("ROW_STATUS", "TEXT", 32), ("QC_FLAGS", "TEXT", 4000)])
    with arcpy.da.InsertCursor(str(path), ["SOURCE_OID", "SID", "ISO_TIME", "ROW_STATUS", "QC_FLAGS"]) as cursor:
        for record in records:
            attrs = record["attributes"]
            cursor.insertRow((record["source_oid"], attrs.get("SID"), attrs.get("ISO_TIME"),
                              record["row_status"], ";".join(record["qc_flags"])))


def prepare_hurricane_data(raw_points, output_folder, start_season=1955,
                           end_season=2025, raw_lines=None, spc_reports=None, export_csv=False):
    """Temporarily stage sources; publish observations, event/QC tables and provenance.

    The optional CSV contains every raw point row, original DBF cells and disposition;
    the prepared FC contains selected, non-quarantined observations only. Exact
    duplicates are removed from that FC; conflicting SID/time duplicates publish
    QC and a failed manifest, then raise ValueError. No AOI clipping is performed.
    """
    import arcpy  # Deliberately lazy: pure tests run without ArcGIS installed.

    output = pathlib.Path(output_folder).resolve()
    sources = {"points": pathlib.Path(raw_points).resolve()}
    if raw_lines:
        sources["lines"] = pathlib.Path(raw_lines).resolve()
    if spc_reports:
        sources["spc_reports"] = pathlib.Path(spc_reports).resolve()
    for source in sources.values():
        if output == source.parent or source.parent in output.parents:
            raise ValueError("Output folder must not be inside any raw source directory")
    if int(start_season) > int(end_season):
        raise ValueError("start_season must not exceed end_season")
    for source in sources.values():
        if not source.is_file():
            raise ValueError(f"Source does not exist: {source}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sdss_hurricane_") as staging_root:
        try:
            inventory_sources, staged = {}, {}
            for kind, source in sources.items():
                staged[kind], inventory_sources[kind] = _stage(source, pathlib.Path(staging_root), "ibtracs_" + kind if kind != "spc_reports" else kind)
            dataset_metadata = {kind: _source_metadata(arcpy, path, kind) for kind, path in staged.items()}
            _require_point_geometry(dataset_metadata["points"]["geometry_type"])
            fields, records, source_count = _read_dbf(staged["points"].with_suffix(".dbf"))
            geometries = _geometry_records(staged["points"])
            if len(geometries) != source_count:
                raise ValueError("Shapefile and DBF record counts differ")
            required = {"SID", "SEASON", "ISO_TIME", "TRACK_TYPE", "IFLAG", "USA_LAT", "USA_LON", "USA_WIND"}
            missing = required - {field["name"] for field in fields}
            if missing:
                raise ValueError("Missing required source fields: " + ", ".join(sorted(missing)))
            for record in records:
                geometry = geometries[record["source_oid"]]
                record["geometry_hash"] = geometry["hash"]
                record["raw_geometry_xy"] = geometry["xy"]
            records = classify_records(records, start_season, end_season)
            included = [record for record in records if record["row_status"] == "INCLUDED"]
            statuses = collections.Counter(record["row_status"] for record in records)
            sentinel_counts = collections.Counter(field for record in records for field, reason in record["normalization_reasons"].items() if reason == "sentinel")
            selected = [record for record in records if record["row_status"] in {"INCLUDED", "QUARANTINED", "DUPLICATE_EXACT", "CONFLICT"}]
            summary = {"source_record_count": source_count, "source_active_rows": len(records),
                       "source_deleted_rows": source_count - len(records), "row_status_counts": dict(statuses),
                       "selected_observation_count": len(included), "selected_storm_count": len({r["attributes"]["SID"] for r in included}),
                       "start_season": int(start_season), "end_season": int(end_season),
                       "source_track_types": dict(collections.Counter(str(r["attributes"].get("TRACK_TYPE")) for r in records)),
                       "source_usa_iflag": dict(collections.Counter(r["usa_iflag"] for r in records)),
                       "source_agencies_included": dict(collections.Counter(str(r["attributes"].get("USA_AGENCY") or "") for r in included)),
                       "usa_iflag_included": dict(collections.Counter(r["usa_iflag"] for r in included)),
                       "usa_status_included": dict(collections.Counter(str(r["attributes"].get("USA_STATUS") or "") for r in included)),
                       "nature_included": dict(collections.Counter(str(r["attributes"].get("NATURE") or "") for r in included)),
                       "unavailable_usa_iflag_included": sum(r["usa_iflag"] == "?" for r in included),
                       "missing_usa_wind_included": sum(r["values"].get("USA_WIND") is None for r in included),
                       "missing_agency_included": sum(not r["attributes"].get("USA_AGENCY") for r in included),
                       "sentinel_counts_all_raw_rows": dict(sentinel_counts),
                       "incomplete_radii_included": {str(speed): sum(f"INCOMPLETE_R{speed}" in r["qc_flags"] for r in included) for speed in (34, 50, 64)},
                       "selected_rows_before_qc": len(selected)}
            if dataset_metadata["points"]["coordinate_reference_system"]["wkid"] == 4326:
                summary["raw_geometry_vs_usa_positions_included"] = _coordinate_differences(included)
            else:
                summary["raw_geometry_vs_usa_positions_included"] = {"compared_observations": 0,
                    "reason": "Raw geometry is not WGS84; no untransformed coordinate comparison was made"}
            gdb = output / "hurricane_prepare.gdb"
            paths = {"geodatabase": str(gdb), "raw_points": str(gdb / "raw_ibtracs_points"),
                     "observations": str(gdb / "hurricane_observations"), "storms": str(gdb / "hurricane_storms"),
                     "qc": str(gdb / "hurricane_qc"),
                     "canonical_csv": str(output / "hurricane_observations.csv") if export_csv else None,
                     "inventory": str(output / "source_inventory.json"),
                     "manifest": str(output / "prepare_manifest.json")}
            inventory = {"created_utc": dt.datetime.now(UTC).isoformat(), "sources": inventory_sources,
                         "datasets": dataset_metadata,
                         "staging_policy": "Temporary safe-name sidecars, verified before ArcPy import and removed on exit; original checksums retained",
                         "source_fields": fields, "geometry_policy": "Raw geometry is merged LAT/LON; prepared geometry is rebuilt from USA_LON/USA_LAT in EPSG:4326; full tracks retained.",
                         "native_units": {"wind_and_translation_speed": "knots", "USA_radii_RMW_ROCI_EYE": "nautical miles", "pressure": "millibars", "DIST2LAND_LANDFALL": "kilometers", "time": "UTC", "coordinates": "degrees"},
                         "derived_fields": {"USA_IFLAG": "First character of IFLAG; not a source column", "OBS_TIME_UTC": "ISO_TIME parsed as UTC, stored in ArcGIS DATE without timezone", "SOURCE_OID": "Zero-based original shapefile record index", "QC_FLAGS": "Semicolon-delimited quality indicators"},
                         "usa_iflag_values": IFLAG_DESCRIPTIONS, "summary": summary,
                         "sources_documentation": [TECHNICAL_DETAILS, COLUMN_DETAILS, SPC_DETAILS],
                         "limitations": ["Best tracks are uncertain estimates; native positional reporting approximately 0.1 degree (~10 km).", "Prepared winds are storm maximum sustained 1-minute wind, not local exposure or gusts.", "Blank agency values are retained, including interpolated observations; no agency attribution is invented.", "SPC severe thunderstorm reports are inventoried separately and never merged into hurricane observations.", "Missing numeric cells and field-specific sentinels become NULL; valid negative status codes and zero radii are retained."]}
            raw_names = [field["name"] for field in fields]
            csv_names = raw_names + ["SOURCE_OID", "USA_IFLAG", "OBS_TIME_UTC", "ROW_STATUS", "QC_FLAGS"] + ["NORMALIZED_" + field for field in NORMALIZED_COLUMNS]
            if export_csv:
                with pathlib.Path(paths["canonical_csv"]).open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=csv_names)
                    writer.writeheader()
                    for record in records:
                        row = dict(record["raw_attributes"])
                        row.update(SOURCE_OID=record["source_oid"], USA_IFLAG=record["usa_iflag"],
                                   OBS_TIME_UTC=record["observation_time"].isoformat() if record["observation_time"] else "",
                                   ROW_STATUS=record["row_status"], QC_FLAGS=";".join(record["qc_flags"]))
                        row.update({"NORMALIZED_" + field: record["values"].get(field) for field in NORMALIZED_COLUMNS})
                        writer.writerow(row)
            with arcpy.EnvManager(extent=None, mask=None, outputCoordinateSystem=arcpy.SpatialReference(4326), overwriteOutput=True):
                if not arcpy.Exists(str(gdb)):
                    arcpy.management.CreateFileGDB(str(output), gdb.name)
                arcpy.management.CopyFeatures(str(staged["points"]), paths["raw_points"])
                _publish_qc(arcpy, pathlib.Path(paths["qc"]), records)
                if statuses.get("CONFLICT"):
                    for key in ("observations", "storms"):
                        if arcpy.Exists(paths[key]):
                            arcpy.management.Delete(paths[key])
                    inventory["status"] = "failed_conflicting_duplicates"
                    _write_json(pathlib.Path(paths["inventory"]), inventory)
                    _write_json(pathlib.Path(paths["manifest"]), dict(paths, summary=summary, status=inventory["status"]))
                    raise ValueError(f"Conflicting SID/timestamp observations; review {paths['qc']}")
                observations = pathlib.Path(paths["observations"])
                if arcpy.Exists(str(observations)):
                    arcpy.management.Delete(str(observations))
                arcpy.management.CreateFeatureclass(str(gdb), observations.name, "POINT", spatial_reference=arcpy.SpatialReference(4326))
                definitions = []
                field_map = {}
                for field in fields:
                    name = field["name"]
                    safe_name = arcpy.ValidateFieldName(name, str(gdb))
                    field_map[name] = safe_name
                    if field["dbf_type"] in {"N", "F"}:
                        kind = "LONG" if field["decimals"] == 0 and field["length"] <= 9 else "DOUBLE"
                        definitions.append((safe_name, kind, None))
                    else:
                        definitions.append((safe_name, "TEXT", max(1, field["length"])))
                definitions += [("SOURCE_OID", "LONG", None), ("USA_IFLAG", "TEXT", 1), ("OBS_TIME_UTC", "DATE", None), ("QC_FLAGS", "TEXT", 4000)]
                _add_fields(arcpy, observations, definitions)
                insert_fields = [field_map[name] for name in raw_names] + ["SOURCE_OID", "USA_IFLAG", "OBS_TIME_UTC", "QC_FLAGS", "SHAPE@XY"]
                with arcpy.da.InsertCursor(str(observations), insert_fields) as cursor:
                    for record in included:
                        values = record["values"]
                        attrs = [values[name] for name in raw_names]
                        cursor.insertRow(attrs + [record["source_oid"], record["usa_iflag"], record["observation_time"].replace(tzinfo=None),
                                                  ";".join(record["qc_flags"]), (values["USA_LON"], values["USA_LAT"])])
                storms_path = pathlib.Path(paths["storms"])
                if arcpy.Exists(str(storms_path)):
                    arcpy.management.Delete(str(storms_path))
                arcpy.management.CreateTable(str(gdb), storms_path.name)
                storm_definitions = [("SID", "TEXT", 32), ("SEASON", "LONG", None), ("NAME", "TEXT", 80),
                                     ("OBS_COUNT", "LONG", None), ("FIRST_UTC", "DATE", None), ("LAST_UTC", "DATE", None),
                                     ("MAX_USA_WIND_KT", "DOUBLE", None), ("MISSING_WIND_N", "LONG", None),
                                     ("R34_COMPLETE_N", "LONG", None), ("R64_COMPLETE_N", "LONG", None),
                                     ("USA_POS_INTERP_N", "LONG", None)]
                _add_fields(arcpy, storms_path, storm_definitions)
                groups = collections.defaultdict(list)
                for record in included:
                    groups[record["attributes"]["SID"]].append(record)
                with arcpy.da.InsertCursor(str(storms_path), [field[0] for field in storm_definitions]) as cursor:
                    for sid, rows in sorted(groups.items()):
                        first = min(rows, key=lambda row: row["observation_time"])
                        times = [row["observation_time"].replace(tzinfo=None) for row in rows]
                        winds = [row["values"]["USA_WIND"] for row in rows if row["values"].get("USA_WIND") is not None]
                        cursor.insertRow((sid, first["attributes"]["SEASON"], first["attributes"].get("NAME"), len(rows), min(times), max(times),
                                          max(winds) if winds else None, len(rows) - len(winds),
                                          sum("INCOMPLETE_R34" not in row["qc_flags"] for row in rows),
                                          sum("INCOMPLETE_R64" not in row["qc_flags"] for row in rows),
                                          sum(row["usa_iflag"] == "P" for row in rows)))
            # Verify source checksums after all processing; staging must never edit raw data.
            for components in inventory_sources.values():
                for component in components:
                    if _hash(pathlib.Path(component["source"])) != component["sha256"]:
                        raise RuntimeError("Raw source changed during processing: " + component["source"])
            inventory["prepared_field_map"] = field_map
            inventory["status"] = "complete"
            inventory["arcgis_installation"] = arcpy.GetInstallInfo()
            _write_json(pathlib.Path(paths["inventory"]), inventory)
            result = dict(paths, summary=summary, status="complete")
            _write_json(pathlib.Path(paths["manifest"]), result)
            arcpy.AddMessage(f"Prepared {len(included):,} observations across {len(groups):,} storms. Manifest: {paths['manifest']}")
            return result
        finally:
            # Script Tool execution can retain a schema lock on staged shapefiles.
            # Release it before TemporaryDirectory removes them, even on errors.
            arcpy.management.ClearWorkspaceCache()
