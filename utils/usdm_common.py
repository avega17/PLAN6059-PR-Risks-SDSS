"""Shared, dependency-free USDM provenance and publication helpers."""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

VERSION = '1.0.0'


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return str(path)


def as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        for pattern in ('%m/%d/%Y', '%m/%d/%Y %I:%M:%S %p'):
            try:
                return datetime.strptime(text, pattern).date()
            except ValueError:
                pass
    raise ValueError(f'Expected a calendar date, received {value!r}')


def protect_source(source, destination):
    """Never write generated products into the declared local input tree."""
    if source and Path(destination).resolve().is_relative_to(Path(source).resolve()):
        raise ValueError('Output/cache folders must be outside the local source folder.')


def write_csv(path, fields, rows):
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def publish_csv_table(csv_path, gdb, name, schema):
    """Publish a typed table only during tool execution; no GIS extension used."""
    import arcpy
    gdb = Path(gdb)
    with arcpy.EnvManager(extent=None, mask=None, overwriteOutput=True):
        if not arcpy.Exists(str(gdb)):
            arcpy.management.CreateFileGDB(str(gdb.parent), gdb.name)
        target = str(gdb/name)
        if arcpy.Exists(target):
            arcpy.management.Delete(target)
        arcpy.management.CreateTable(str(gdb), name)
        for field, kind, length in schema:
            arcpy.management.AddField(target, field, kind, field_length=length)
        with Path(csv_path).open(newline='', encoding='utf-8') as stream:
            with arcpy.da.InsertCursor(target, [s[0] for s in schema]) as cursor:
                for row in csv.DictReader(stream):
                    values = []
                    for field, kind, _ in schema:
                        value = row.get(field)
                        if value in (None, ''):
                            values.append(None)
                        elif kind == 'DATE':
                            values.append(datetime.fromisoformat(value))
                        elif kind in ('LONG', 'SHORT'):
                            values.append(int(value))
                        elif kind == 'DOUBLE':
                            values.append(float(value))
                        else:
                            values.append(value)
                    cursor.insertRow(values)
    return target


class DroughtAcquisitionError(ValueError):
    """Acquisition/validation failed; a diagnostic manifest/report is retained."""

