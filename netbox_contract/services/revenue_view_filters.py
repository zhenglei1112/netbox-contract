"""Pure filters and projections for contract-specific revenue views.

The builders in :mod:`revenue_views` deliberately remain responsible for
assembling the source dictionaries.  This module only creates shallow copies
of those dictionaries, so callers can safely retain the unfiltered model for
another UI selection without re-querying or mutating it.
"""

from decimal import Decimal


ZERO = Decimal('0')
RISK_LEVELS = frozenset(('warning', 'danger'))
ANOMALY_STATUSES = frozenset(('error', 'missing', 'overdue'))
TIMELINE_FILTERS = (
    ('all', '全部'),
    ('overdue', '已逾期'),
    ('next_30_days', '未来30天'),
    ('next_90_days', '未来90天'),
    ('pending_trigger', '待触发'),
)


def build_timeline_view_profile(contract_type, *, active_filter=None):
    is_recurring = contract_type == 'recurring'
    default_filter = 'attention' if is_recurring else 'all'
    active_filter = active_filter or default_filter
    filters = TIMELINE_FILTERS
    if is_recurring:
        filters = (('attention', '\u9700\u5173\u6ce8'),) + filters
    return {
        'default_filter': default_filter,
        'filters': filters,
        'title': (
            '\u8fd1\u671f\u5e94\u6536\u52a8\u6001'
            if is_recurring
            else '\u7efc\u5408\u5e94\u6536\u65f6\u95f4\u8f74'
        ),
        'description': (
            '\u96c6\u4e2d\u67e5\u770b\u903e\u671f\u3001\u5f85\u89e6\u53d1\u53ca\u672a\u676530\u5929\u5e94\u6536\uff1b\u5b8c\u6574\u5e74\u5ea6\u8ba1\u5212\u8bf7\u67e5\u770b\u5468\u671f\u8d26\u5355\u77e9\u9635\u3002'
            if is_recurring
            else ''
        ),
        'summary_label': '\u5f53\u524d\u7b5b\u9009\u6c47\u603b',
        'empty_filter_message': (
            '\u5f53\u524d\u6ca1\u6709\u903e\u671f\u3001\u5f85\u89e6\u53d1\u6216\u672a\u676530\u5929\u5e94\u6536\uff1b\u53ef\u5207\u6362\u5230\u201c\u5168\u90e8\u201d\u67e5\u770b\u5b8c\u6574\u8ba1\u5212\u3002'
            if is_recurring and active_filter == 'attention'
            else '\u5f53\u524d\u7b5b\u9009\u8303\u56f4\u5185\u6682\u65e0\u5e94\u6536\u8282\u70b9\u3002'
        ),
    }


def _sum(rows, key):
    return sum((row.get(key, ZERO) or ZERO for row in rows), ZERO)


def _is_risk(item):
    return (
        item.get('risk_level') in RISK_LEVELS
        or item.get('status') in ANOMALY_STATUSES
        or (item.get('overdue_total', ZERO) or ZERO) > ZERO
    )


def _option(value, label=None):
    return {'value': str(value), 'label': str(label if label is not None else value)}


def _dedupe_options(options):
    seen = set()
    result = []
    for option in options:
        if option['value'] not in seen:
            result.append(option)
            seen.add(option['value'])
    return result


def _project_identity(project):
    if project is None:
        return '', ''
    if isinstance(project, dict):
        value = project.get('pk', project.get('id', project.get('value', '')))
        label = project.get('name', project.get('label', value))
    else:
        value = getattr(project, 'pk', getattr(project, 'id', ''))
        label = getattr(project, 'name', None) or str(project)
    if value in (None, ''):
        value = label
    return str(value), str(label)


def _cell_totals(cells):
    return {
        'receivable_total': _sum(cells, 'receivable_total'),
        'invoiced_total': _sum(cells, 'invoiced_total'),
        'receipt_total': _sum(cells, 'receipt_total'),
        'adjustment_total': _sum(cells, 'adjustment_total'),
        'overdue_total': _sum(cells, 'overdue_total'),
        'planned_amount': _sum(cells, 'planned_amount'),
        'risk_cells': sum(1 for cell in cells if _is_risk(cell)),
        'missing_cells': sum(1 for cell in cells if cell.get('status') == 'missing'),
    }


def filter_periodic_matrix(matrix, *, anomalies_only=False):
    """Return a periodic matrix, optionally reduced to anomalous cells only."""
    source_rows = list(matrix.get('rows', ()))
    source_months = list(matrix.get('months', ()))
    anomaly_periods = {
        cell.get('billing_period') for row in source_rows for cell in row.get('cells', ()) if _is_risk(cell)
    }
    if anomalies_only:
        months = [m for m in source_months if m.get('billing_period') in anomaly_periods]
        rows = []
        for row in source_rows:
            source_cells = list(row.get('cells', ()))
            if any(_is_risk(cell) for cell in source_cells):
                cells_by_period = {cell.get('billing_period'): cell for cell in source_cells}
                cells = [
                    dict(cells_by_period[month.get('billing_period')])
                    for month in months
                    if month.get('billing_period') in cells_by_period
                ]
                rows.append({**row, 'cells': cells})
    else:
        months = list(source_months)
        rows = [{**row, 'cells': [dict(cell) for cell in row.get('cells', ())]} for row in source_rows]

    cells = [cell for row in rows for cell in row.get('cells', ())]
    return {
        **matrix,
        'months': months,
        'rows': rows,
        'totals': _cell_totals(cells),
        'filter_options': {'anomalies_only': [False, True]},
        'active_filters': {'anomalies_only': bool(anomalies_only)},
        'active_count': len(cells),
    }


def filter_stage_timeline(timeline, *, mode='all'):
    """Filter timeline nodes by ``all``, ``pending`` or ``risk``."""
    if mode not in ('all', 'pending', 'risk'):
        raise ValueError("mode must be 'all', 'pending' or 'risk'")
    source_nodes = list(timeline.get('nodes', ()))
    if mode == 'pending':
        nodes = [node for node in source_nodes if node.get('date_certainty') == 'pending_trigger']
    elif mode == 'risk':
        nodes = [node for node in source_nodes if _is_risk(node) or (node.get('delay_days', 0) or 0) > 0]
    else:
        nodes = source_nodes
    nodes = [dict(node) for node in nodes]
    return {
        **timeline,
        'nodes': nodes,
        'totals': {
            'planned_amount': _sum(nodes, 'planned_amount'),
            'receivable_total': _sum(nodes, 'receivable_total'),
            'invoiced_total': _sum(nodes, 'invoiced_total'),
            'receipt_total': _sum(nodes, 'receipt_total'),
            'unreceived_total': _sum(nodes, 'unreceived_total'),
            'risk_nodes': sum(1 for node in nodes if _is_risk(node)),
            'completed_nodes': sum(1 for node in nodes if node.get('status') == 'completed'),
            'pending_trigger_nodes': sum(1 for node in nodes if node.get('date_certainty') == 'pending_trigger'),
        },
        'filter_options': {
            'modes': [
                _option('all', '全部'),
                _option('pending', '待触发'),
                _option('risk', '风险'),
            ],
        },
        'active_filters': {'mode': mode},
        'active_count': len(nodes),
    }


def _lane_project_options(lanes):
    options = []
    for lane in lanes:
        for project in lane.get('projects', ()):
            value, label = _project_identity(project)
            if value:
                options.append(_option(value, label))
    return _dedupe_options(options)


def _lane_project_values(lane):
    return {_project_identity(project)[0] for project in lane.get('projects', ())}


def _lane_order_status(lane):
    order = lane.get('order')
    if order is not None:
        if isinstance(order, dict):
            value = order.get('status')
        else:
            value = getattr(order, 'status', None)
        if value not in (None, ''):
            return str(value)
    return str(lane.get('status', ''))


def _lane_totals(lanes):
    return {
        'receivable_total': _sum(lanes, 'receivable_total'),
        'invoiced_total': _sum(lanes, 'invoiced_total'),
        'receipt_total': _sum(lanes, 'receipt_total'),
        'unreceived_total': _sum(lanes, 'unreceived_total'),
        'overdue_total': _sum(lanes, 'overdue_total'),
    }


def filter_order_lanes(order_view, *, project=None, order_status=None):
    """Filter order lanes by project identifier and source order status."""
    source_lanes = list(order_view.get('lanes', ()))
    project_value = '' if project in (None, '') else str(project)
    status_value = '' if order_status in (None, '') else str(order_status)
    lanes = [
        dict(lane)
        for lane in source_lanes
        if (not project_value or project_value in _lane_project_values(lane))
        and (not status_value or status_value == _lane_order_status(lane))
    ]
    status_options = _dedupe_options(
        _option(_lane_order_status(lane), lane.get('order_status_label') or lane.get('status_label'))
        for lane in source_lanes
        if _lane_order_status(lane)
    )
    totals = _lane_totals(lanes)
    ordered_amount = _sum(
        (lane for lane in lanes if not lane.get('is_unfiled')),
        'order_amount',
    )
    framework_limit = order_view.get('framework_limit')
    return {
        **order_view,
        'lanes': lanes,
        **totals,
        'ordered_amount': ordered_amount,
        'ordered_baseline_amount': ordered_amount,
        'remaining_limit': framework_limit - ordered_amount if framework_limit is not None else None,
        'order_count': sum(1 for lane in lanes if lane.get('order')),
        'legacy_count': sum(1 for lane in lanes if lane.get('is_legacy')),
        'unfiled_count': sum(1 for lane in lanes if lane.get('is_unfiled')),
        'filter_options': {
            'projects': _lane_project_options(source_lanes),
            'order_statuses': status_options,
        },
        'active_filters': {'project': project_value, 'order_status': status_value},
        'active_count': len(lanes),
    }


def _aggregate_cells(cells, billing_period):
    cells = list(cells)
    totals = _cell_totals(cells)
    risks = [cell for cell in cells if _is_risk(cell)]
    events = [event for cell in cells for event in cell.get('events', ())]
    return {
        'billing_period': billing_period,
        'status': risks[0].get('status', 'risk') if risks else ('generated' if events else 'empty'),
        'status_label': risks[0].get('status_label', '') if risks else '',
        'risk_level': risks[0].get('risk_level', 'muted') if risks else 'muted',
        **{key: value for key, value in totals.items() if key not in ('risk_cells', 'missing_cells')},
        'primary_event_dom_id': next(
            (event.get('event_dom_id') for event in events if event.get('event_dom_id')),
            '',
        ),
        'event_count': sum(cell.get('event_count', 0) or 0 for cell in cells),
        'events': events,
    }


def _aggregate_mixed_group(group_key, lanes, months):
    cells_by_period = {}
    for lane in lanes:
        for cell in lane.get('cells', ()):
            cells_by_period.setdefault(cell.get('billing_period'), []).append(cell)
    cells = [
        _aggregate_cells(cells_by_period.get(month.get('billing_period'), ()), month.get('billing_period'))
        for month in months
    ]
    return {
        'projection_key': str(group_key),
        'label': str(group_key),
        'order_id': str(group_key),
        'source_lanes': list(lanes),
        'source_lane_count': len(lanes),
        'cells': cells,
        'receivable_total': _sum(lanes, 'receivable_total'),
        'invoiced_total': _sum(lanes, 'invoiced_total'),
        'receipt_total': _sum(lanes, 'receipt_total'),
        'adjustment_total': _sum(lanes, 'adjustment_total'),
        'pending_trigger_count': sum(lane.get('pending_trigger_count', 0) or 0 for lane in lanes),
    }


def filter_mixed_lanes(mixed_view, *, view_by='charge_item', selected=None):
    """Project mixed lanes by charge item, order, or billing month.

    ``selected`` is interpreted in the active projection (charge item label,
    order id, or ``YYYY-MM`` billing period).
    """
    if view_by not in ('charge_item', 'order', 'month'):
        raise ValueError("view_by must be 'charge_item', 'order' or 'month'")
    source_lanes = list(mixed_view.get('lanes', ()))
    months = list(mixed_view.get('months', ()))
    selected_value = '' if selected in (None, '') else str(selected)

    charge_options = _dedupe_options(
        _option(str(lane.get('charge_item', ''))) for lane in source_lanes if lane.get('charge_item')
    )
    order_options = _dedupe_options(_option(lane.get('order_id')) for lane in source_lanes if lane.get('order_id'))
    month_options = [_option(m.get('billing_period'), m.get('label')) for m in months]

    if view_by == 'charge_item':
        lanes = [
            dict(lane)
            for lane in source_lanes
            if not selected_value or str(lane.get('charge_item', '')) == selected_value
        ]
        visible_months = months
    elif view_by == 'order':
        groups = {}
        for lane in source_lanes:
            key = str(lane.get('order_id') or '未归档订单')
            groups.setdefault(key, []).append(lane)
        lanes = [
            _aggregate_mixed_group(key, group, months)
            for key, group in groups.items()
            if not selected_value or key == selected_value
        ]
        visible_months = months
    else:
        selected_months = [
            month for month in months if not selected_value or str(month.get('billing_period')) == selected_value
        ]
        lanes = []
        for month in selected_months:
            period = month.get('billing_period')
            source_cells = [
                cell for lane in source_lanes for cell in lane.get('cells', ()) if cell.get('billing_period') == period
            ]
            cell = _aggregate_cells(source_cells, period)
            lanes.append(
                {
                    'projection_key': period,
                    'label': month.get('label', period),
                    'billing_period': period,
                    'cells': [cell],
                    'receivable_total': cell['receivable_total'],
                    'invoiced_total': cell['invoiced_total'],
                    'receipt_total': cell['receipt_total'],
                    'adjustment_total': cell['adjustment_total'],
                    'pending_trigger_count': 0,
                }
            )
        visible_months = [{'month': None, 'label': '应收汇总', 'billing_period': 'summary'}]

    cells = [cell for lane in lanes for cell in lane.get('cells', ())]
    return {
        **mixed_view,
        'months': visible_months,
        'lanes': lanes,
        'projection': view_by,
        'totals': {
            'receivable_total': _sum(lanes, 'receivable_total'),
            'invoiced_total': _sum(lanes, 'invoiced_total'),
            'receipt_total': _sum(lanes, 'receipt_total'),
            'adjustment_total': _sum(lanes, 'adjustment_total'),
            'pending_trigger_count': sum(lane.get('pending_trigger_count', 0) or 0 for lane in lanes),
            'risk_cells': sum(1 for cell in cells if _is_risk(cell)),
        },
        'filter_options': {
            'views': [
                _option('charge_item', '收费项目'),
                _option('order', '订单'),
                _option('month', '应收月份'),
            ],
            'charge_items': charge_options,
            'orders': order_options,
            'months': month_options,
        },
        'active_filters': {'view_by': view_by, 'selected': selected_value},
        'active_count': len(lanes),
    }
