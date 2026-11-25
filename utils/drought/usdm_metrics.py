"""Weekly drought occupancy and event calculations; ArcPy publication is lazy."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np


def check_states(values):
    values = np.asarray(values)
    if values.dtype != np.uint8 or not np.isin(values, [0, 1, 2, 3, 4, 5, 255]).all():
        raise ValueError('Weekly states must be uint8 None=0, D0..D4=1..5, unknown=255.')
    return values


def occupancy(values, baseline_count, years):
    """Return observed counts; only complete cells receive full-period indicators."""
    values = check_states(values)
    if not 0 < baseline_count <= len(values) or years <= 0:
        raise ValueError('Invalid baseline denominator.')
    base = values[:baseline_count]
    valid = base <= 5
    nvalid = valid.sum(axis=0, dtype=np.int32)
    d1 = ((base >= 2) & valid).sum(axis=0, dtype=np.int32)
    d2 = ((base >= 3) & valid).sum(axis=0, dtype=np.int32)
    eligible = nvalid == baseline_count
    return dict(nvalid=nvalid, d1=d1, d2=d2, eligible=eligible,
                wd1=np.where(eligible, d1 / years, np.nan),
                fd1=np.where(eligible, 100 * d1 / baseline_count, np.nan),
                wd2=np.where(eligible, d2 / years, np.nan),
                burden=np.where(eligible, 100 * np.where(valid, base, 0).sum(axis=0,
                                 dtype=np.int32) / baseline_count, np.nan))


def analyze_events(values, baseline_count, recovery, cell_ids=None, *, minimum_dm=1):
    """Vectorize time transitions across a cell block; retain censored events.

    Event tuples: cell, recovery, first, last qualifying week, confirmation
    (-1 if unknown), baseline span, qualifying weeks, peak, left, right, observed span.
    Counts include events intersecting baseline, never buffer-only events.
    Duration summaries use baseline spans of uncensored, confirmed events.
    """
    values = check_states(values)
    if values.ndim == 1:
        values = values[:, None]
    if values.ndim != 2 or recovery not in (1, 3) or not 0 < baseline_count <= len(values):
        raise ValueError('Events require a time/cell array, baseline and recovery of 1 or 3.')
    if minimum_dm not in (1, 2):
        raise ValueError('Event threshold must be D1 or D2.')
    size = values.shape[1]
    ids = np.arange(size) if cell_ids is None else np.asarray(cell_ids)
    if len(ids) != size:
        raise ValueError('Cell identifiers differ from the input block.')
    active = np.zeros(size, bool)
    first = np.zeros(size, np.int32)
    last = np.zeros(size, np.int32)
    dry = np.zeros(size, np.int32)
    peak = np.zeros(size, np.uint8)
    clear = np.zeros(size, np.int16)
    left = np.zeros(size, bool)
    count = np.zeros(size, np.int32)
    nleft, nright = count.copy(), count.copy()
    durations = [[] for _ in range(size)]
    max_observed = np.full(size, np.nan)
    records = []

    def finish(selected, confirmation, right):
        for c in np.flatnonzero(selected):
            if first[c] < baseline_count:
                span = int(min(last[c], baseline_count - 1) - first[c] + 1)
                records.append((int(ids[c]), recovery, int(first[c]), int(last[c]), confirmation,
                                span, int(dry[c]), int(peak[c]), int(left[c]), int(right),
                                int(last[c] - first[c] + 1)))
                count[c] += 1
                nleft[c] += int(left[c])
                nright[c] += int(right)
                max_observed[c] = span if np.isnan(max_observed[c]) else max(max_observed[c], span)
                if not left[c] and not right:
                    durations[c].append(span)
        active[selected] = False

    for t, row in enumerate(values):
        unknown = row == 255
        finish(active & unknown, -1, True)
        clear[unknown] = 0
        drought = (row > minimum_dm) & (row <= 5)
        new = drought & ~active
        first[new], dry[new], peak[new] = t, 0, 0
        left[new] = clear[new] < recovery
        active[drought] = True
        last[drought] = t
        if t < baseline_count:
            dry[drought] += 1
            peak[drought] = np.maximum(peak[drought], row[drought])
        clear[drought] = 0
        calm = row <= minimum_dm
        clear[calm] = np.minimum(recovery, clear[calm] + 1)
        finish(active & calm & (clear >= recovery), t, False)
    finish(active, -1, True)
    complete = np.array([len(d) for d in durations], dtype=np.int32)
    median = np.array([np.median(d) if d else np.nan for d in durations])
    maximum = np.array([max(d) if d else np.nan for d in durations])
    return records, dict(count=count, complete=complete, left=nleft, right=nright,
                         median=median, maximum=maximum, observed_max=max_observed)


EVENT_SUMMARIES = ('EVENTS','COMPLETE','LEFT_CENS','RIGHT_CENS','MEDIAN_SPAN','MAX_SPAN','OBS_MAX_SPAN')
EVENT_RULES = tuple((dm, recovery, f'{recovery}W' if dm == 1 else f'D2_{recovery}W')
                    for dm in (1, 2) for recovery in (3, 1))


def calculate_drought_metrics(processing_workspace):
    import arcpy
    from .usdm_spatial import load_workspace, table, settings_table, mark_report, publish_raster
    workspace = str(Path(processing_workspace).resolve())
    settings = settings_table(workspace)
    mark_report(settings, 'CHECKING_STATES')
    try:
        workspace, settings, grid, cube, island = load_workspace(workspace)
    except Exception as error:
        mark_report(settings, 'FAILED', error=str(error))
        raise
    settings['stage'] = 'CALCULATING'
    settings_table(workspace, settings)
    mark_report(settings, 'CALCULATING')
    try:
        count, years = settings['baseline_count'], settings['year_count']
        row, col = np.nonzero(island > 0)
        ids = row * grid['columns'] + col
        dates = [datetime.fromisoformat(d) for d in settings['dates']]
        event_schema = [('CELL_ID','LONG',None), ('MIN_DM','SHORT',None),
            ('RECOVERY','SHORT',None), ('FIRST_UTC','DATE',None),
            ('LAST_DRY_UTC','DATE',None), ('CONFIRMED_UTC','DATE',None), ('BASE_SPAN','LONG',None),
            ('BASE_DRY','LONG',None), ('PEAK_CODE','SHORT',None), ('LEFT_CENS','SHORT',None),
            ('RIGHT_CENS','SHORT',None), ('OBS_SPAN','LONG',None)]
        annual_schema = [('CELL_ID','LONG',None), ('YEAR','SHORT',None), ('N_EXPECTED','SHORT',None),
                         ('N_VALID','SHORT',None), ('N_D1','SHORT',None), ('N_D2','SHORT',None)]
        fields = ['N_VALID','N_EXPECTED','COVERAGE_FRACTION','N_D1_OBS','N_D2_OBS','W_D1','F_D1','W_D2','ORDINAL_BURDEN','W_D1_2004']
        for _, _, suffix in EVENT_RULES:
            fields += [f'{name}_{suffix}' for name in EVENT_SUMMARIES]
        cell_schema = [('CELL_ID','LONG',None), ('GRID_ROW','LONG',None), ('GRID_COL','LONG',None)]
        cell_schema += [(n, 'LONG' if n.startswith(('N_', 'EVENTS_', 'COMPLETE_', 'LEFT_', 'RIGHT_'))
                         else 'DOUBLE', None) for n in fields]
        outputs = {n: np.full(island.shape, np.nan) for n in
                   ('N_VALID','N_D1','N_D2','W_D1','W_D2','ORDINAL_BURDEN','W_D1_2004',
                    *(f'{name}_{suffix}' for _, _, suffix in EVENT_RULES
                      for name in ('EVENT_RATE','MEDIAN_SPAN','MAX_SPAN')))}
        post = np.array([d.year >= 2004 for d in dates[:count]])
        if (int(post.sum()), len(set(d.year for d in dates[:count] if d.year >= 2004))) != (1148, 22):
            raise ValueError('The post-2004 sensitivity cohort differs from 1,148 maps / 22 years.')
        # Three primary tables, streamed once rather than duplicate CSV exports.
        from .usdm_common import table_writer, file_gdb_edit
        for name,schema in (('drought_events',event_schema),('annual_cell_metrics',annual_schema),('cell_metrics',cell_schema)):
            table(workspace,name,schema,[])
        with file_gdb_edit(workspace), \
             table_writer(Path(workspace)/'drought_events', event_schema,create=False) as write_events, \
             table_writer(Path(workspace)/'annual_cell_metrics', annual_schema,create=False) as write_annual, \
             table_writer(Path(workspace)/'cell_metrics', cell_schema,create=False) as write_cells:
            for begin in range(0, len(ids), 4096):
                if arcpy.env.isCancelled:
                    raise RuntimeError('Drought metric calculation cancelled.')
                rr, cc, cell_ids = row[begin:begin+4096], col[begin:begin+4096], ids[begin:begin+4096]
                values = cube[:, rr, cc]
                stats = occupancy(values, count, years)
                late = occupancy(values[:count][post], int(post.sum()), 22)
                data = [stats['nvalid'],np.full(len(cell_ids),count),stats['nvalid']/count]
                data += [stats[n] for n in ('d1','d2','wd1','fd1','wd2','burden')] + [late['wd1']]
                for dm, rule, suffix in EVENT_RULES:
                    events, summary = analyze_events(values, count, rule, cell_ids, minimum_dm=dm)
                    write_events(dict(zip([f[0] for f in event_schema],
                        (r[0], dm, r[1], dates[r[2]], dates[r[3]], dates[r[4]] if r[4] >= 0 else None, *r[5:])))
                        for r in events)
                    data += [summary[n] for n in ('count','complete','left','right','median','maximum','observed_max')]
                    outputs[f'EVENT_RATE_{suffix}'][rr,cc] = np.where(stats['eligible'], summary['count']/years, np.nan)
                    outputs[f'MAX_SPAN_{suffix}'][rr,cc] = np.where(stats['eligible'], summary['maximum'], np.nan)
                    outputs[f'MEDIAN_SPAN_{suffix}'][rr,cc] = np.where(stats['eligible'], summary['median'], np.nan)
                for year in range(2000, 2026):
                    selected = np.array([d.year == year for d in dates[:count]])
                    annual = values[:count][selected]
                    valid = annual <= 5
                    counts = valid.sum(axis=0)
                    d1 = ((annual >= 2) & valid).sum(axis=0)
                    d2 = ((annual >= 3) & valid).sum(axis=0)
                    write_annual(dict(zip([f[0] for f in annual_schema],
                                          (int(i), year, int(selected.sum()), int(v), int(a), int(b))))
                                 for i,v,a,b in zip(cell_ids,counts,d1,d2))
                for key, vector in [('N_VALID',stats['nvalid']), ('N_D1',np.where(stats['eligible'],stats['d1'],np.nan)),
                    ('N_D2',np.where(stats['eligible'],stats['d2'],np.nan)),
                    ('W_D1',stats['wd1']), ('W_D2',stats['wd2']), ('ORDINAL_BURDEN',stats['burden']),
                    ('W_D1_2004',late['wd1'])]:
                    outputs[key][rr,cc] = vector
                write_cells(dict(zip([f[0] for f in cell_schema],
                    [int(i),int(r),int(c)] + [None if not np.isfinite(v) else float(v) for v in values_at_cell]))
                    for i,r,c,values_at_cell in zip(cell_ids,rr,cc,zip(*data)))
                arcpy.AddMessage(f'Drought metrics: {min(begin+4096,len(ids)):,}/{len(ids):,} land cells.')
        catalog_rows = []
        for name, array in outputs.items():
            publish_raster(workspace, name, array, grid, integer=name.startswith('N_'))
            units = ('observations' if name.startswith('N_') else 'events/year' if name.startswith('EVENT_RATE')
                     else 'ordinal index points' if name == 'ORDINAL_BURDEN' else 'weeks' if 'SPAN' in name else 'weeks/year')
            catalog_rows.append((name, name, units))
        catalog = table(workspace, 'metric_catalog', [('PRODUCT','TEXT',64), ('DATASET','TEXT',100),
                        ('UNITS','TEXT',100)], catalog_rows)
        from .usdm_spatial import dataset_fingerprint
        from .usdm_common import sha256
        settings.update(stage='METRICS_READY', metrics_sha256=dataset_fingerprint(workspace),
                        metrics_software_sha256=sha256(__file__))
        settings_table(workspace, settings)
        mark_report(settings, 'METRICS_READY', catalog=catalog)
        return {'catalog':catalog}
    except Exception as error:
        mark_report(settings, 'FAILED', error=str(error))
        raise
