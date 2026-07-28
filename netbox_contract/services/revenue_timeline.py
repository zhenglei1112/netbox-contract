from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal


ZERO = Decimal('0')
FILTER_KEYS = frozenset({'all', 'attention', 'overdue', 'next_30_days', 'next_90_days', 'pending_trigger'})


def _amount(value):
    return value if value is not None else ZERO


def _value(item, name, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _identity(item):
    if item is None:
        return None
    return _value(item, 'pk', _value(item, 'id'))


def _add_months(value, months):
    index = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(index, 12)
    month = month_index + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def _month_day(year, month, day):
    return date(year, month, min(max(int(day or 1), 1), monthrange(year, month)[1]))


def _rounded_amount(line, rule, active_start=None, active_end=None, period_start=None, period_end=None):
    amount = Decimal(str(_value(line, 'unit_price', ZERO))) * Decimal(str(_value(line, 'quantity', ZERO)))
    if (
        active_start is not None
        and active_end is not None
        and period_start is not None
        and period_end is not None
        and _value(rule, 'proration_rule', 'none') not in {'none', 'full_month'}
    ):
        amount *= Decimal((active_end - active_start).days + 1) / Decimal((period_end - period_start).days + 1)
    precision = str(_value(rule, 'rounding_precision', '2') or '2')
    quantum = Decimal('1') if precision == '0' else Decimal(f'0.{"0" * (int(precision) - 1)}1')
    return amount.quantize(quantum)


def _version_date(version):
    return getattr(version, 'planned_date', None) if version else None


def _version_amount(version):
    return _amount(getattr(version, 'planned_amount', ZERO)) if version else ZERO


def _event_identity(event):
    event_key = event.get('event_key')
    if event_key:
        return ('event_key', event_key)
    line = event.get('line')
    line_pk = getattr(line, 'pk', None)
    if line_pk is not None:
        return ('line_pk', line_pk)
    return ('object', id(event))


def _charge_item(contract_line, plan=None):
    value = getattr(contract_line, 'charge_item', None)
    if value not in (None, ''):
        return value
    return getattr(plan, 'charge_item', '') if plan else ''


def _track_context(track):
    original_version = track.get('original_version')
    current_version = track.get('current_version')
    return {
        'plan': track.get('plan'),
        'plan_url': track.get('plan_url') or '',
        'original_version': original_version,
        'original_version_url': track.get('original_version_url') or '',
        'original_plan_date': _version_date(original_version),
        'original_plan_amount': _amount(track.get('original_amount', _version_amount(original_version))),
        'current_version': current_version,
        'current_version_url': track.get('current_version_url') or '',
        'current_plan_date': _version_date(current_version),
        'current_plan_amount': _amount(track.get('current_amount', _version_amount(current_version))),
    }


def _formed_node(event, track=None):
    track = track or {}
    context = _track_context(track)
    contract_line = event.get('contract_line') or track.get('contract_line')
    receivable_amount = _amount(event.get('net_amount'))
    invoiced_amount = _amount(event.get('mapped_amount'))
    received_amount = _amount(event.get('receipted_amount'))
    unreceived_amount = _amount(event.get('unreceived_amount', receivable_amount - received_amount))
    actual_receivable_date = event.get('receivable_date')
    due_date = event.get('due_date')
    return {
        'node_key': event.get('event_key') or event.get('event_dom_id') or _event_identity(event),
        'kind': 'formed',
        'kind_label': '已形成应收',
        'date_certainty': 'actual',
        'timeline_date': due_date or actual_receivable_date,
        'contract_line': contract_line,
        'contract_line_url': event.get('contract_line_url') or track.get('contract_line_url') or '',
        'charge_item': _charge_item(contract_line, context['plan']),
        'billing_rule': event.get('billing_rule') or track.get('billing_rule'),
        **context,
        'actual_receivable_date': actual_receivable_date,
        'due_date': due_date,
        'receivable_amount': receivable_amount,
        'invoiced_amount': invoiced_amount,
        'received_amount': received_amount,
        'unreceived_amount': unreceived_amount,
        'status': event.get('collection_status') or 'receivable',
        'status_label': event.get('collection_status_label') or '已形成应收',
        'risk_level': event.get('risk_level') or 'muted',
        'event_key': event.get('event_key') or '',
        'event_dom_id': event.get('event_dom_id') or '',
    }


def _planned_node(track):
    plan = track.get('plan')
    if getattr(plan, 'status', '') in {'closed', 'canceled'}:
        return None
    current_version = track.get('current_version')
    if not current_version:
        return None
    amount = _amount(track.get('current_amount', _version_amount(current_version)))
    if amount <= ZERO:
        return None

    planned_date = _version_date(current_version)
    due_date = track.get('effective_due_date') or planned_date
    trigger_type = getattr(current_version, 'trigger_type', '')
    if due_date is None:
        date_certainty = 'pending_trigger'
    elif trigger_type == 'estimated_date':
        date_certainty = 'estimated'
    else:
        date_certainty = 'fixed'

    context = _track_context(track)
    contract_line = track.get('contract_line')
    return {
        'node_key': f'receivable-plan:{getattr(plan, "pk", getattr(plan, "plan_code", id(plan)))}',
        'kind': 'planned',
        'kind_label': '当前计划',
        'date_certainty': date_certainty,
        'timeline_date': due_date,
        'contract_line': contract_line,
        'contract_line_url': track.get('contract_line_url') or '',
        'charge_item': _charge_item(contract_line, plan),
        'billing_rule': track.get('billing_rule'),
        **context,
        'actual_receivable_date': track.get('actual_receivable_date'),
        'due_date': due_date,
        'receivable_amount': ZERO,
        'invoiced_amount': ZERO,
        'received_amount': ZERO,
        'unreceived_amount': ZERO,
        'status': track.get('status') or 'planned',
        'status_label': track.get('status_label') or '计划中',
        'risk_level': track.get('risk_level') or 'muted',
        'event_key': '',
        'event_dom_id': '',
    }


def _rule_id_from_trigger(record):
    direct_id = _value(record, 'billing_rule_id')
    if direct_id is not None:
        return direct_id
    direct_rule = _value(record, 'billing_rule')
    if direct_rule is not None:
        return _identity(direct_rule)
    plan = _value(record, 'plan')
    return _value(plan, 'billing_rule_id', _identity(_value(plan, 'billing_rule'))) if plan else None


def _rule_projection_node(
    line,
    rule,
    *,
    billing_period,
    timeline_date,
    amount,
    date_certainty='fixed',
    status='planned',
    risk_level='muted',
    trigger_record=None,
    actual_trigger_date=None,
):
    rule_id = _identity(rule)
    line_id = _identity(line)
    status_label = {
        'planned': '待形成',
        'awaiting_trigger': '待业务事件触发',
        'ambiguous_trigger': '触发日期待核对',
        'trigger_outside_validity': '触发日期超出合同项有效期',
        'invalid_trigger_offset': '触发偏移天数无效',
    }.get(status, status)
    return {
        'node_key': f'billing-rule:{rule_id}:{billing_period}',
        'kind': 'planned',
        'kind_label': '规则预测',
        'date_certainty': date_certainty,
        'timeline_date': timeline_date,
        'contract_line': line,
        'contract_line_url': _value(line, 'get_absolute_url', lambda: '')()
        if callable(_value(line, 'get_absolute_url'))
        else '',
        'charge_item': _value(line, 'charge_item', ''),
        'billing_rule': rule,
        'billing_period': billing_period,
        'plan': None,
        'plan_url': '',
        'original_version': None,
        'original_version_url': '',
        'original_plan_date': None,
        'original_plan_amount': ZERO,
        'current_version': None,
        'current_version_url': '',
        'current_plan_date': timeline_date,
        'current_plan_amount': amount,
        'actual_receivable_date': None,
        'actual_trigger_date': actual_trigger_date,
        'trigger_url': (
            _value(trigger_record, 'url', '')
            or (
                _value(trigger_record, 'get_absolute_url', lambda: '')()
                if callable(_value(trigger_record, 'get_absolute_url'))
                else ''
            )
        )
        if trigger_record
        else '',
        'due_date': timeline_date,
        'receivable_amount': ZERO,
        'invoiced_amount': ZERO,
        'received_amount': ZERO,
        'unreceived_amount': ZERO,
        'status': status,
        'status_label': status_label,
        'risk_level': risk_level,
        'event_key': '',
        'event_dom_id': '',
        'trigger_record': trigger_record,
        'contract_line_id': line_id,
    }


def build_rule_projection_nodes(
    contract_lines,
    billing_rules,
    event_rows=(),
    *,
    today=None,
    projection_end=None,
    trigger_records=(),
):
    """Project effective billing rules without requiring receivable plans.

    Confirmed recurring facts suppress the same ``(rule, billing_period)``
    projection.  For stage rules any confirmed fact for the rule wins over a
    projection.  Multiple distinct confirmed trigger dates are deliberately
    represented as one undated warning instead of choosing an arbitrary date.
    A recurring node's timeline date is its configured bill-generation date;
    the active period end remains an amount-calculation boundary, not the node date.
    """
    today = today or date.today()
    projection_end = projection_end or today + timedelta(days=365)
    if projection_end < today:
        return []
    lines_by_id = {_identity(line): line for line in contract_lines}
    confirmed_periods = set()
    formed_stage_rules = set()
    for event in event_rows:
        if not _value(event, 'is_confirmed', False):
            continue
        event_rule = _value(event, 'billing_rule')
        rule_id = _value(event, 'billing_rule_id', _identity(event_rule))
        if rule_id is None:
            continue
        period = _value(event, 'billing_period')
        if period:
            confirmed_periods.add((str(rule_id), str(period)))
        formed_stage_rules.add(str(rule_id))

    nodes = []
    for rule in billing_rules:
        if not _value(rule, 'is_active', True) or _value(rule, 'status', 'effective') != 'effective':
            continue
        rule_id = _identity(rule)
        line = lines_by_id.get(_value(rule, 'contract_line_id')) or _value(rule, 'contract_line')
        if line is None or _value(line, 'status', 'active') != 'active':
            continue
        line_start = _value(line, 'valid_from')
        line_end = _value(line, 'valid_to')
        if not isinstance(line_start, date):
            continue
        rule_type = _value(rule, 'rule_type')
        if rule_type == 'recurring':
            interval = {'month': 1, 'quarter': 3, 'year': 12}.get(_value(rule, 'billing_cycle'), 1)
            period_start = date(line_start.year, line_start.month, 1)
            while period_start <= projection_end and (line_end is None or period_start <= line_end):
                period_end = _add_months(period_start, interval) - timedelta(days=1)
                active_start = max(period_start, line_start)
                active_end = min(period_end, line_end) if line_end else period_end
                billing_period = f'{period_start:%Y-%m}'
                direction_month = period_start if _value(rule, 'billing_direction') == 'prepay' else period_end
                billing_date = _month_day(
                    direction_month.year, direction_month.month, _value(rule, 'bill_generation_day', 1)
                )
                if (
                    active_start <= active_end
                    and today <= billing_date <= projection_end
                    and (str(rule_id), billing_period) not in confirmed_periods
                ):
                    nodes.append(
                        _rule_projection_node(
                            line,
                            rule,
                            billing_period=billing_period,
                            timeline_date=billing_date,
                            amount=_rounded_amount(line, rule, active_start, active_end, period_start, period_end),
                        )
                    )
                period_start = _add_months(period_start, interval)
            continue

        if rule_type not in {'milestone', 'one_time'} or str(rule_id) in formed_stage_rules:
            continue
        matching = [
            record
            for record in trigger_records
            if str(_rule_id_from_trigger(record)) == str(rule_id)
            and _value(record, 'trigger_event') == _value(rule, 'trigger_event')
            and _value(record, 'status', 'confirmed') == 'confirmed'
            and isinstance(_value(record, 'actual_trigger_date'), date)
        ]
        distinct_dates = sorted({_value(record, 'actual_trigger_date') for record in matching})
        amount = _rounded_amount(line, rule)
        pending_period = f'pending-{rule_id}'
        if len(distinct_dates) != 1:
            ambiguous = len(distinct_dates) > 1
            nodes.append(
                _rule_projection_node(
                    line,
                    rule,
                    billing_period=pending_period,
                    timeline_date=None,
                    amount=amount,
                    date_certainty='pending_trigger',
                    status='ambiguous_trigger' if ambiguous else 'awaiting_trigger',
                    risk_level='warning' if ambiguous else 'muted',
                )
            )
            continue
        trigger_date = distinct_dates[0]
        if trigger_date < line_start or (line_end and trigger_date > line_end):
            nodes.append(
                _rule_projection_node(
                    line,
                    rule,
                    billing_period=pending_period,
                    timeline_date=None,
                    amount=amount,
                    date_certainty='pending_trigger',
                    status='trigger_outside_validity',
                    risk_level='warning',
                )
            )
            continue
        offset = _value(rule, 'trigger_offset_days', 0)
        if not isinstance(offset, int) or offset < 0:
            nodes.append(
                _rule_projection_node(
                    line,
                    rule,
                    billing_period=pending_period,
                    timeline_date=None,
                    amount=amount,
                    date_certainty='pending_trigger',
                    status='invalid_trigger_offset',
                    risk_level='warning',
                )
            )
            continue
        receivable_date = trigger_date + timedelta(days=offset)
        if receivable_date <= projection_end:
            record = next(record for record in matching if _value(record, 'actual_trigger_date') == trigger_date)
            nodes.append(
                _rule_projection_node(
                    line,
                    rule,
                    billing_period=f'{receivable_date:%Y-%m}',
                    timeline_date=receivable_date,
                    amount=amount,
                    status='missing_receivable' if receivable_date < today else 'planned',
                    risk_level='danger' if receivable_date < today else 'muted',
                    trigger_record=record,
                    actual_trigger_date=trigger_date,
                )
            )

    nodes.sort(key=_sort_key)
    return nodes


def _matches_filter(node, filter_key, today):
    if filter_key == 'all':
        return True
    if filter_key == 'pending_trigger':
        return node['date_certainty'] == 'pending_trigger'
    if filter_key == 'attention':
        return (
            _matches_filter(node, 'overdue', today)
            or _matches_filter(node, 'pending_trigger', today)
            or _matches_filter(node, 'next_30_days', today)
        )

    timeline_date = node['timeline_date']
    if timeline_date is None:
        return False
    if filter_key == 'overdue':
        due_date = node['due_date']
        return (
            node['kind'] == 'formed' and due_date is not None and due_date < today and node['unreceived_amount'] > ZERO
        )

    days = (timeline_date - today).days
    if filter_key == 'next_30_days':
        return 0 <= days <= 30
    return 0 <= days <= 90


def _sort_key(node):
    kind_order = 0 if node['kind'] == 'formed' else 1
    return (node['timeline_date'] or date.max, kind_order, str(node['node_key']))


def build_revenue_timeline(
    event_rows,
    plan_tracks,
    *,
    today=None,
    filter_key='all',
    contract_lines=(),
    billing_rules=(),
    trigger_records=(),
    projection_end=None,
):
    """Project receivable events and unrealized plans into one chronological view.

    Confirmed events are the source of truth once a receivable has formed. A plan
    that already contains confirmed events is therefore not emitted as a second node. Plans
    without a real date remain undated pending-trigger nodes.
    """
    if filter_key not in FILTER_KEYS:
        raise ValueError(f'Unsupported timeline filter: {filter_key}')
    today = today or date.today()
    event_rows = list(event_rows)
    tracks = list((plan_tracks or {}).get('tracks', ()))

    tracks_by_event = {}
    for track in tracks:
        for event in track.get('events', ()):
            tracks_by_event.setdefault(_event_identity(event), track)

    nodes = []
    for event in event_rows:
        if not event.get('is_confirmed'):
            continue
        nodes.append(_formed_node(event, tracks_by_event.get(_event_identity(event))))

    for track in tracks:
        if any(event.get('is_confirmed') for event in track.get('events', ())):
            continue
        node = _planned_node(track)
        if node:
            nodes.append(node)

    rule_nodes = build_rule_projection_nodes(
        contract_lines,
        billing_rules,
        event_rows,
        today=today,
        projection_end=projection_end,
        trigger_records=trigger_records,
    )
    rule_keys = {(str(_identity(node.get('billing_rule'))), node.get('timeline_date')) for node in rule_nodes}
    nodes = [
        node
        for node in nodes
        if node['kind'] == 'formed'
        or node.get('plan') is None
        or (str(_identity(node.get('billing_rule'))), node.get('timeline_date')) not in rule_keys
    ]
    nodes.extend(rule_nodes)
    nodes.sort(key=_sort_key)
    filtered_nodes = [node for node in nodes if _matches_filter(node, filter_key, today)]
    counts = {key: sum(1 for node in nodes if _matches_filter(node, key, today)) for key in FILTER_KEYS}
    return {
        'nodes': filtered_nodes,
        'all_nodes': nodes,
        'active_filter': filter_key,
        'filter_counts': counts,
        'has_data': bool(nodes),
        'visible_totals': {
            'node_count': len(filtered_nodes),
            'receivable_amount': sum((node['receivable_amount'] for node in filtered_nodes), ZERO),
            'invoiced_amount': sum((node['invoiced_amount'] for node in filtered_nodes), ZERO),
            'received_amount': sum((node['received_amount'] for node in filtered_nodes), ZERO),
            'unreceived_amount': sum((node['unreceived_amount'] for node in filtered_nodes), ZERO),
            'planned_amount': sum(
                (node['current_plan_amount'] for node in filtered_nodes if node['kind'] == 'planned'),
                ZERO,
            ),
        },
        'totals': {
            'node_count': len(nodes),
            'formed_count': sum(1 for node in nodes if node['kind'] == 'formed'),
            'planned_count': sum(1 for node in nodes if node['kind'] == 'planned'),
            'pending_trigger_count': counts['pending_trigger'],
            'risk_count': sum(1 for node in nodes if node['risk_level'] in {'warning', 'danger'}),
            'receivable_amount': sum((node['receivable_amount'] for node in nodes), ZERO),
            'invoiced_amount': sum((node['invoiced_amount'] for node in nodes), ZERO),
            'received_amount': sum((node['received_amount'] for node in nodes), ZERO),
            'unreceived_amount': sum((node['unreceived_amount'] for node in nodes), ZERO),
            'planned_amount': sum(
                (node['current_plan_amount'] for node in nodes if node['kind'] == 'planned'),
                ZERO,
            ),
        },
    }
