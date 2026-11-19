"""Inspect USDM shapefile archives without changing or extracting the source."""
from __future__ import annotations

import collections
from pathlib import Path, PurePosixPath
import re
import struct
import zipfile

from .usdm_common import as_date

ZIP_DATE = re.compile(r'^usdm_(\d{8})_m\.zip$', re.I)


def archive_date(name):
    match = ZIP_DATE.fullmatch(Path(name).name)
    if not match:
        raise ValueError(f'Not a weekly merged USDM archive name: {name}')
    stamp = match[1]
    value = as_date(f'{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}')
    if value.weekday() != 1:
        raise ValueError(f'Archive map date is not Tuesday: {value}')
    return value.isoformat()


def has_part_intersection(shape, envelope):
    """Conservative WGS84 ring-box screen, never a geometry reconstruction.

    Outer rings enclosing the search area are retained, as are intersecting
    holes. A positive result requires ordinary GIS clipping for actual overlap.
    """
    import numpy as np
    xmin, ymin, xmax, ymax = envelope
    offset = 100
    if len(shape) < 100 or struct.unpack_from('>i', shape, 0)[0] != 9994:
        raise ValueError('Invalid shapefile header for spatial screening.')
    found = False
    while offset < len(shape):
        if offset + 12 > len(shape):
            raise ValueError('Truncated shapefile record.')
        length = struct.unpack_from('>i', shape, offset + 4)[0] * 2
        p = offset + 8
        if length < 4 or p + length > len(shape):
            raise ValueError('Invalid shapefile record size.')
        kind = struct.unpack_from('<i', shape, p)[0]
        if kind not in (0, 5):
            raise ValueError('Spatial screening supports 2D Polygon records only.')
        if kind == 5:
            if length < 44:
                raise ValueError('Truncated polygon header.')
            parts, points = struct.unpack_from('<ii', shape, p + 36)
            if parts <= 0 or points < 4 or 44 + parts * 4 + points * 16 > length:
                raise ValueError('Invalid polygon part/point counts.')
            starts = np.frombuffer(shape, '<i4', parts, p + 44)
            xy = np.frombuffer(shape, '<f8', points * 2, p + 44 + parts * 4).reshape(-1, 2)
            if starts[0] != 0 or np.any(np.diff(starts) <= 0) or starts[-1] >= points or not np.isfinite(xy).all():
                raise ValueError('Invalid polygon offsets or nonfinite coordinates.')
            for i, start in enumerate(starts):
                end = starts[i+1] if i+1 < parts else points
                ring = xy[start:end]
                if len(ring) < 4 or not np.array_equal(ring[0], ring[-1]):
                    raise ValueError('Polygon ring is unclosed or too short.')
                low, high = ring.min(axis=0), ring.max(axis=0)
                found |= high[0] >= xmin and low[0] <= xmax and high[1] >= ymin and low[1] <= ymax
        offset = p + length
    return bool(found)


def read_dbf(data):
    if len(data) < 33:
        raise ValueError('Truncated DBF header')
    count, header_size, record_size = struct.unpack_from('<IHH', data, 4)
    if header_size < 33 or record_size < 1 or header_size + count*record_size > len(data):
        raise ValueError('Invalid DBF dimensions')
    fields = []
    for offset in range(32, header_size-1, 32):
        descriptor = data[offset:offset+32]
        if descriptor[0] == 13:
            break
        fields.append({'name': descriptor[:11].split(b'\0')[0].decode('ascii'),
                       'type': chr(descriptor[11]), 'width': descriptor[16],
                       'decimals': descriptor[17]})
    if 1 + sum(f['width'] for f in fields) != record_size:
        raise ValueError('DBF field widths do not match record size')
    rows = []
    for index in range(count):
        row = data[header_size+index*record_size:header_size+(index+1)*record_size]
        if row[:1] == b'*':
            raise ValueError('Deleted DBF records require explicit source review')
        cursor = 1
        values = {}
        for field in fields:
            values[field['name']] = row[cursor:cursor+field['width']].decode('ascii').strip()
            cursor += field['width']
        rows.append(values)
    return fields, rows


def inspect_zip(path, map_date):
    stamp = as_date(map_date).strftime('%Y%m%d')
    stem = 'usdm_' + stamp
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 64 or sum(m.file_size for m in members) > 512*1024*1024:
            raise ValueError('Archive exceeds the configured extraction-size/member limits')
        names = {}
        for member in members:
            relative = PurePosixPath(member.filename.replace('\\', '/'))
            if (relative.is_absolute() or '..' in relative.parts or ':' in member.filename
                    or (member.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('Unsafe ZIP member path or symbolic link')
            if member.is_dir():
                continue
            key = relative.name.lower()
            if key in names:
                raise ValueError('Duplicate member basename in ZIP')
            names[key] = member.filename
            if not key.startswith(stem + '.'):
                raise ValueError('ZIP member date/basename does not match planned map date')
        required = [stem + suffix for suffix in ('.shp', '.shx', '.dbf', '.prj', '.shp.xml')]
        if any(name not in names for name in required):
            raise ValueError('ZIP lacks a required shapefile sidecar or metadata XML')
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC check failed')
        fields, rows = read_dbf(archive.read(names[stem + '.dbf']))
        if 'DM' not in {f['name'] for f in fields}:
            raise ValueError('DBF has no DM category field')
        levels = []
        for row in rows:
            if row['DM'] not in {'0', '1', '2', '3', '4'}:
                raise ValueError('Missing/unsupported DM value; source review required')
            levels.append(int(row['DM']))
        shape = archive.read(names[stem + '.shp'])
        if len(shape) < 100 or struct.unpack_from('>i', shape, 0)[0] != 9994:
            raise ValueError('Invalid shapefile header')
        if struct.unpack_from('>i', shape, 24)[0]*2 != len(shape):
            raise ValueError('Shapefile length differs from its header')
        shape_type = struct.unpack_from('<i', shape, 32)[0]
        if shape_type not in (5, 15, 25):
            raise ValueError('USDM geometry must be polygon')
        index_file = archive.read(names[stem + '.shx'])
        if (len(index_file)!=100+8*len(rows) or struct.unpack_from('>i',index_file,0)[0]!=9994
                or struct.unpack_from('>i',index_file,24)[0]*2!=len(index_file)
                or struct.unpack_from('<i',index_file,32)[0]!=shape_type):
            raise ValueError('Invalid shapefile index header/dimensions')
        offset, record_count = 100, 0
        while offset < len(shape):
            if offset+8 > len(shape):
                raise ValueError('Truncated shapefile record')
            size = struct.unpack_from('>i', shape, offset+4)[0]*2
            if size < 4 or offset+8+size > len(shape):
                raise ValueError('Invalid shapefile record length')
            if struct.unpack_from('>ii',index_file,100+8*record_count)!=(offset//2,size//2):
                raise ValueError('SHP and SHX record offsets differ')
            if struct.unpack_from('<i', shape, offset+8)[0] not in (0, shape_type):
                raise ValueError('Inconsistent shapefile record type')
            offset += 8+size
            record_count += 1
        if record_count != len(rows):
            raise ValueError('SHP and DBF record counts differ')
        projection = archive.read(names[stem + '.prj']).decode('utf-8-sig').strip()
        if not projection:
            raise ValueError('Missing coordinate-system definition')
        # XML is parsed to establish well-formedness, without trusting old lineage.
        import xml.etree.ElementTree as ET
        metadata = ET.fromstring(archive.read(names[stem + '.shp.xml']))
        return {'map_date': as_date(map_date).isoformat(), 'members': list(names.values()),
                'record_count': record_count, 'fields': fields, 'dm_values': levels,
                'duplicate_dm_categories': [k for k,v in collections.Counter(levels).items() if v>1],
                'shape_type': shape_type, 'extent': list(struct.unpack_from('<4d', shape, 36)),
                'source_crs_wkt': projection, 'zip_crc_pass': True,
                'metadata_creation_date': metadata.findtext('./Esri/CreaDate'),
                'metadata_publication_dates': [e.text for e in metadata.findall('.//pubdate')],
                'geometry_topology_checked': False, 'assessed_domain_verified': False}

