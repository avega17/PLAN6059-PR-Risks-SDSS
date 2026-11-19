"""Shared, dependency-free USDM provenance and publication helpers."""
from __future__ import annotations

import csv
from contextlib import contextmanager
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


def spatial_source_signature(manifest):
    """Hash scientific GIS inputs, independent of mutable acquisition receipts.

    Re-running a warm-cache fetch changes its manifest timestamp and paths,
    not necessarily its maps. Byte hashes, dates and roles define this series.
    """
    cohort = manifest['plan_snapshot']
    payload = dict(baseline_count=cohort['baseline_count'],year_count=cohort['year_count'],
        maps=[(r['map_date'],r['role'],r['sha256']) for r in manifest['gis']])
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()


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


def typed_value(value, kind):
    if value in (None, ''):
        return None
    if kind == 'DATE':
        return datetime.fromisoformat(str(value))
    if kind in ('LONG', 'SHORT'):
        return int(value)
    return float(value) if kind == 'DOUBLE' else value


@contextmanager
def table_writer(path, schema, create=True):
    """Stream normalized rows directly into the primary typed geodatabase table."""
    import arcpy
    path = Path(path)
    with arcpy.EnvManager(extent=None, mask=None, overwriteOutput=True):
        if not arcpy.Exists(str(path.parent)):
            arcpy.management.CreateFileGDB(str(path.parent.parent), path.parent.name)
        if create:
            if arcpy.Exists(str(path)):
                arcpy.management.Delete(str(path))
            arcpy.management.CreateTable(str(path.parent), path.name)
            arcpy.management.AddFields(str(path), [[field, kind, '', length] for field, kind, length in schema])
        with arcpy.da.InsertCursor(str(path), [f[0] for f in schema]) as cursor:
            def write(rows):
                for row in rows:
                    cursor.insertRow([typed_value(row.get(field), kind) for field, kind, _ in schema])
            yield write


@contextmanager
def file_gdb_edit(workspace):
    """Commit related cursor writes together; create schemas before entering."""
    import arcpy
    editor = arcpy.da.Editor(str(workspace))
    editor.startEditing(False, False)
    editor.startOperation()
    try:
        yield
    except BaseException:
        editor.abortOperation()
        editor.stopEditing(False)
        raise
    else:
        editor.stopOperation()
        editor.stopEditing(True)


@contextmanager
def normalized_writer(path, schema, publish_tables):
    if publish_tables:
        with table_writer(path, schema) as write:
            yield write
    else:
        with Path(path).open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, [s[0] for s in schema])
            writer.writeheader()
            yield writer.writerows


@contextmanager
def normalized_reader(path, schema):
    """Return typed rows for either representation, in insertion order."""
    if str(path).lower().endswith('.csv'):
        with Path(path).open(newline='', encoding='utf-8') as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != [s[0] for s in schema]:
                raise ValueError('Normalized CSV schema differs from contract')
            yield ({field: typed_value(row[field], kind) for field, kind, _ in schema} for row in reader)
    else:
        import arcpy
        fields = {f.name: f.type for f in arcpy.ListFields(str(path))}
        types = {'TEXT':'String','DATE':'Date','DOUBLE':'Double','LONG':'Integer','SHORT':'SmallInteger'}
        if any(fields.get(f) != types[k] for f,k,_ in schema):
            raise ValueError('Normalized geodatabase schema differs from contract')
        oid = arcpy.Describe(str(path)).OIDFieldName
        with arcpy.da.SearchCursor(str(path), [s[0] for s in schema],
                                   sql_clause=(None, 'ORDER BY ' + oid)) as cursor:
            yield (dict(zip((s[0] for s in schema), row)) for row in cursor)




class DroughtAcquisitionError(ValueError):
    """Acquisition/validation failed; a diagnostic manifest/report is retained."""
