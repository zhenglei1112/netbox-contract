from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal


ZERO = Decimal('0')


def _sum(values):
    return sum(values, ZERO)


def _period_bounds(year, month):
    start = date(year, month, 1)
    return start, date(year, month, monthrange(year, month)[1])


def _is_line_applicable(contract_line, period_start, period_end):
    return contract_line.valid_from <= period_end and (
        not contract_line.valid_to or contract_line.valid_to >= period_start
    )


def _is_planned_billing_month(rule, contract_line, year, month):
    months_since_start = (year - contract_line.valid_from.year) * 12 + month - contract_line.valid_from.month
    if months_since_start < 0:
        return False
    interval = {
        'month': 1,
        'quarter': 3,
        'year': 12,
    }.get(rule.billing_cycle, 1)
    return months_since_start % interval == 0


def _cell_status(events, *, period_end, today):
    if not events:
        if period_end < today:
            return 'missing', '未生成', 'danger'
        return 'planned', '未来计划', 'muted'

    receivable_total = _sum(event['net_amount'] for event in events)
    invoiced_total = _sum(event['mapped_amount'] for event in events)
    receipt_total = _sum(event['receipted_amount'] for event in events)
    overdue_total = _sum(event['overdue_amount'] for event in events)
    due_dates = [event['due_date'] for event in events if event.get('due_date')]
    nearest_due_date = min(due_dates) if due_dates else None

    if invoiced_total > receivable_total or receipt_total > receivable_total:
        return 'error', '金额异常', 'danger'
    if overdue_total > ZERO:
        return 'overdue', '逾期未收', 'danger'
    if receipt_total >= receivable_total and receivable_total > ZERO:
        return 'paid', '已收款', 'success'
    if receipt_total > ZERO:
        return 'partial_receipt', '部分收款', 'warning'
    if nearest_due_date and today <= nearest_due_date <= today + timedelta(days=7) and receipt_total < receivable_total:
        return 'due_soon', '即将到期', 'warning'
    if invoiced_total >= receivable_total and receivable_total > ZERO:
        return 'invoiced', '已开票', 'info'
    if invoiced_total > ZERO:
        return 'partial_invoice', '部分开票', 'warning'
    return 'generated', '待开票', 'info'


def build_periodic_matrix(contract_lines, billing_rules, event_rows, *, year, today=None):
    """Build a charge-item by month matrix from confirmed receivable events."""
    today = today or date.today()
    recurring_rules_by_line = {}
    for rule in billing_rules:
        if (
            rule.rule_type == 'recurring'
            and getattr(rule, 'is_active', True)
            and getattr(rule, 'status', 'effective') == 'effective'
        ):
            recurring_rules_by_line.setdefault(rule.contract_line_id, []).append(rule)
    recurring_lines = [line for line in contract_lines if line.pk in recurring_rules_by_line]

    events_by_line_period = {}
    for event in event_rows:
        key = (event['contract_line'].pk, event['billing_period'])
        events_by_line_period.setdefault(key, []).append(event)

    months = [
        {
            'month': month,
            'label': f'{month}月',
            'billing_period': f'{year:04d}-{month:02d}',
        }
        for month in range(1, 13)
    ]

    matrix_rows = []
    for contract_line in recurring_lines:
        recurring_rules = recurring_rules_by_line[contract_line.pk]
        cells = []
        for month in months:
            period_start, period_end = _period_bounds(year, month['month'])
            events = events_by_line_period.get(
                (contract_line.pk, month['billing_period']),
                [],
            )
            applicable = _is_line_applicable(contract_line, period_start, period_end)
            is_planned_billing_month = any(
                _is_planned_billing_month(rule, contract_line, year, month['month']) for rule in recurring_rules
            )
            planned_amount = contract_line.unit_price * contract_line.quantity

            if not events and (not applicable or not is_planned_billing_month):
                cells.append(
                    {
                        'billing_period': month['billing_period'],
                        'status': 'not_applicable',
                        'status_label': '不计费',
                        'risk_level': 'muted',
                        'receivable_total': ZERO,
                        'invoiced_total': ZERO,
                        'receipt_total': ZERO,
                        'overdue_total': ZERO,
                        'planned_amount': ZERO,
                        'primary_url': '',
                        'primary_event_dom_id': '',
                        'event_count': 0,
                        'events': [],
                    }
                )
                continue

            status, status_label, risk_level = _cell_status(
                events,
                period_end=period_end,
                today=today,
            )
            cells.append(
                {
                    'billing_period': month['billing_period'],
                    'status': status,
                    'status_label': status_label,
                    'risk_level': risk_level,
                    'receivable_total': _sum(event['net_amount'] for event in events),
                    'invoiced_total': _sum(event['mapped_amount'] for event in events),
                    'receipt_total': _sum(event['receipted_amount'] for event in events),
                    'overdue_total': _sum(event['overdue_amount'] for event in events),
                    'planned_amount': planned_amount if not events else ZERO,
                    'primary_url': events[0]['bill_url'] if events else '',
                    'primary_event_dom_id': events[0]['event_dom_id'] if events else '',
                    'event_count': len(events),
                    'events': events,
                }
            )

        matrix_rows.append(
            {
                'contract_line': contract_line,
                'contract_line_url': contract_line.get_absolute_url(),
                'charge_item': contract_line.charge_item,
                'project': contract_line.project,
                'order_id': (
                    contract_line.revenue_order.order_code
                    if contract_line.revenue_order_id
                    else contract_line.order_id
                ),
                'cells': cells,
            }
        )

    all_cells = [cell for row in matrix_rows for cell in row['cells']]
    return {
        'year': year,
        'months': months,
        'rows': matrix_rows,
        'has_recurring_lines': bool(matrix_rows),
        'totals': {
            'receivable_total': _sum(cell['receivable_total'] for cell in all_cells),
            'receipt_total': _sum(cell['receipt_total'] for cell in all_cells),
            'overdue_total': _sum(cell['overdue_total'] for cell in all_cells),
            'risk_cells': sum(1 for cell in all_cells if cell['risk_level'] in ('warning', 'danger')),
            'missing_cells': sum(1 for cell in all_cells if cell['status'] == 'missing'),
        },
    }


def build_mixed_lanes(contract, contract_lines, billing_rules, event_rows, *, year, today=None):
    """Build a financial Gantt-style view for hybrid contracts."""
    today = today or date.today()
    rules_by_line = {}
    for rule in billing_rules:
        if getattr(rule, 'is_active', True) and getattr(rule, 'status', 'effective') == 'effective':
            rules_by_line.setdefault(rule.contract_line_id, []).append(rule)

    events_by_line = {}
    event_rule_ids_by_line = {}
    for event in event_rows:
        line_id = event['contract_line'].pk
        events_by_line.setdefault(line_id, []).append(event)
        if event.get('billing_rule'):
            event_rule_ids_by_line.setdefault(line_id, set()).add(event['billing_rule'].pk)

    months = [
        {
            'month': month,
            'label': f'{month}月',
            'billing_period': f'{year:04d}-{month:02d}',
        }
        for month in range(1, 13)
    ]

    lanes = []
    for contract_line in contract_lines:
        rules = rules_by_line.get(contract_line.pk, [])
        rule_types = []
        for rule in rules:
            if rule.rule_type not in rule_types:
                rule_types.append(rule.rule_type)
        type_labels = [rule.get_rule_type_display() for rule in rules]
        type_labels = list(dict.fromkeys(type_labels))
        events = events_by_line.get(contract_line.pk, [])
        events_by_period = {}
        for event in events:
            events_by_period.setdefault(event['billing_period'], []).append(event)

        recurring_rules = [rule for rule in rules if rule.rule_type == 'recurring']
        stage_rules = [rule for rule in rules if rule.rule_type in ('milestone', 'one_time')]
        generated_rule_ids = event_rule_ids_by_line.get(contract_line.pk, set())
        pending_trigger_rules = [rule for rule in stage_rules if rule.pk not in generated_rule_ids]
        cells = []
        for month in months:
            period_start, period_end = _period_bounds(year, month['month'])
            period_events = events_by_period.get(month['billing_period'], [])
            recurring_planned = bool(recurring_rules) and _is_line_applicable(
                contract_line,
                period_start,
                period_end,
            ) and any(
                _is_planned_billing_month(rule, contract_line, year, month['month'])
                for rule in recurring_rules
            )
            if period_events:
                status, status_label, risk_level = _cell_status(
                    period_events,
                    period_end=period_end,
                    today=today,
                )
            elif recurring_planned:
                status, status_label, risk_level = 'planned', '周期计划', 'muted'
            else:
                status, status_label, risk_level = 'empty', '—', 'muted'
            cells.append(
                {
                    'billing_period': month['billing_period'],
                    'status': status,
                    'status_label': status_label,
                    'risk_level': risk_level,
                    'receivable_total': _sum(event['net_amount'] for event in period_events),
                    'invoiced_total': _sum(event['mapped_amount'] for event in period_events),
                    'receipt_total': _sum(event['receipted_amount'] for event in period_events),
                    'adjustment_total': _sum(event['line'].adjusted_amount for event in period_events),
                    'overdue_total': _sum(event['overdue_amount'] for event in period_events),
                    'planned_amount': (
                        contract_line.unit_price * contract_line.quantity
                        if recurring_planned and not period_events
                        else ZERO
                    ),
                    'primary_event_dom_id': period_events[0]['event_dom_id'] if period_events else '',
                    'event_count': len(period_events),
                    'events': period_events,
                }
            )

        lanes.append(
            {
                'contract_line': contract_line,
                'contract_line_url': contract_line.get_absolute_url(),
                'charge_item': contract_line.charge_item,
                'project': contract_line.project,
                'order_id': (
                    contract_line.revenue_order.order_code
                    if contract_line.revenue_order_id
                    else contract_line.order_id
                ),
                'rule_types': rule_types,
                'rule_type_labels': type_labels,
                'lane_type': 'mixed' if len(rule_types) > 1 else (rule_types[0] if rule_types else 'unconfigured'),
                'baseline_amount': contract_line.unit_price * contract_line.quantity,
                'pending_trigger_rules': pending_trigger_rules,
                'pending_trigger_count': len(pending_trigger_rules),
                'receivable_total': _sum(event['net_amount'] for event in events),
                'invoiced_total': _sum(event['mapped_amount'] for event in events),
                'receipt_total': _sum(event['receipted_amount'] for event in events),
                'adjustment_total': _sum(event['line'].adjusted_amount for event in events),
                'cells': cells,
            }
        )

    all_cells = [cell for lane in lanes for cell in lane['cells']]
    return {
        'year': year,
        'months': months,
        'lanes': lanes,
        'should_display': contract.contract_type == 'hybrid' and bool(lanes),
        'totals': {
            'receivable_total': _sum(lane['receivable_total'] for lane in lanes),
            'invoiced_total': _sum(lane['invoiced_total'] for lane in lanes),
            'receipt_total': _sum(lane['receipt_total'] for lane in lanes),
            'adjustment_total': _sum(lane['adjustment_total'] for lane in lanes),
            'pending_trigger_count': sum(lane['pending_trigger_count'] for lane in lanes),
            'risk_cells': sum(1 for cell in all_cells if cell['risk_level'] in ('warning', 'danger')),
        },
    }


def _order_lane_status(*, start_date, end_date, receivable_total, receipt_total, overdue_total, today):
    if overdue_total > ZERO:
        return 'overdue', '逾期未收', 'danger'
    if receivable_total > ZERO and receipt_total >= receivable_total:
        return 'completed', '已完成', 'success'
    if start_date and start_date > today:
        return 'not_started', '未开始', 'muted'
    if start_date <= today and (not end_date or end_date >= today):
        return 'executing', '执行中', 'info'
    if receivable_total > receipt_total:
        return 'open', '待回款', 'warning'
    return 'waiting', '待形成应收', 'muted'


def build_order_lanes(
    contract,
    orders,
    contract_lines,
    event_rows,
    *,
    year,
    today=None,
    url_for=None,
):
    """Build order lanes from order facts, with legacy order_id fallback."""
    today = today or date.today()
    url_for = url_for or (lambda _obj: '')
    supported_contract_types = {'framework', 'order', 'hybrid'}
    grouped_lines = {}

    for order in orders:
        key = f'entity:{order.pk}'
        grouped_lines[key] = {
            'order_key': key,
            'order': order,
            'order_url': url_for(order),
            'order_id': order.order_code,
            'label': str(order),
            'is_unfiled': False,
            'is_legacy': order.source_system == 'LEGACY_LEDGER',
            'lines': [],
        }

    for contract_line in contract_lines:
        order = getattr(contract_line, 'revenue_order', None)
        legacy_order_id = (contract_line.order_id or '').strip()
        if order:
            key = f'entity:{order.pk}'
            group = grouped_lines.setdefault(
                key,
                {
                    'order_key': key,
                    'order': order,
                    'order_url': url_for(order),
                    'order_id': order.order_code,
                    'label': str(order),
                    'is_unfiled': False,
                    'is_legacy': order.source_system == 'LEGACY_LEDGER',
                    'lines': [],
                },
            )
        elif legacy_order_id:
            key = f'legacy:{contract_line.project_id}:{legacy_order_id}'
            group = grouped_lines.setdefault(
                key,
                {
                    'order_key': key,
                    'order': None,
                    'order_url': '',
                    'order_id': legacy_order_id,
                    'label': legacy_order_id,
                    'is_unfiled': False,
                    'is_legacy': True,
                    'lines': [],
                },
            )
        else:
            key = f'unfiled:{contract_line.pk}'
            group = {
                'order_key': key,
                'order': None,
                'order_url': '',
                'order_id': '',
                'label': f'未建档订单 · {contract_line.charge_item}',
                'is_unfiled': True,
                'is_legacy': False,
                'lines': [],
            }
            grouped_lines[key] = group
        group['lines'].append(contract_line)

    events_by_line = {}
    for event in event_rows:
        events_by_line.setdefault(event['contract_line'].pk, []).append(event)

    months = [
        {
            'month': month,
            'label': f'{month}月',
            'billing_period': f'{year:04d}-{month:02d}',
        }
        for month in range(1, 13)
    ]

    lanes = []
    for group in grouped_lines.values():
        lines = group['lines']
        line_ids = {line.pk for line in lines}
        events = [event for line_id in line_ids for event in events_by_line.get(line_id, [])]
        events.sort(key=lambda event: (event.get('due_date') or date.max, event['event_key']))
        events_by_period = {}
        for event in events:
            events_by_period.setdefault(event['billing_period'], []).append(event)

        receivable_total = _sum(event['net_amount'] for event in events)
        invoiced_total = _sum(event['mapped_amount'] for event in events)
        receipt_total = _sum(event['receipted_amount'] for event in events)
        overdue_total = _sum(event['overdue_amount'] for event in events)
        baseline_amount = _sum(line.unit_price * line.quantity for line in lines)
        order = group['order']
        order_amount = order.amount if order else baseline_amount
        inferred_start_date = min((line.valid_from for line in lines), default=None)
        inferred_end_date = (
            None
            if lines and any(not line.valid_to for line in lines)
            else max((line.valid_to for line in lines if line.valid_to), default=None)
        )
        start_date = (order.start_date if order else None) or inferred_start_date or contract.start_date
        end_date = (order.end_date if order else None) or inferred_end_date
        status, status_label, risk_level = _order_lane_status(
            start_date=start_date,
            end_date=end_date,
            receivable_total=receivable_total,
            receipt_total=receipt_total,
            overdue_total=overdue_total,
            today=today,
        )

        cells = []
        for month in months:
            period_start, period_end = _period_bounds(year, month['month'])
            period_events = events_by_period.get(month['billing_period'], [])
            if period_events:
                cell_status, cell_status_label, cell_risk_level = _cell_status(
                    period_events,
                    period_end=period_end,
                    today=today,
                )
            else:
                cell_status, cell_status_label, cell_risk_level = 'empty', '—', 'muted'
            cells.append(
                {
                    'billing_period': month['billing_period'],
                    'status': cell_status,
                    'status_label': cell_status_label,
                    'risk_level': cell_risk_level,
                    'receivable_total': _sum(event['net_amount'] for event in period_events),
                    'invoiced_total': _sum(event['mapped_amount'] for event in period_events),
                    'receipt_total': _sum(event['receipted_amount'] for event in period_events),
                    'overdue_total': _sum(event['overdue_amount'] for event in period_events),
                    'primary_url': period_events[0]['bill_url'] if period_events else '',
                    'primary_event_dom_id': period_events[0]['event_dom_id'] if period_events else '',
                    'event_count': len(period_events),
                    'events': period_events,
                }
            )

        projects = [order.project] if order else []
        seen_project_ids = {order.project_id} if order else set()
        for line in lines:
            project_id = getattr(line, 'project_id', None) or getattr(line.project, 'pk', None)
            if project_id not in seen_project_ids:
                projects.append(line.project)
                seen_project_ids.add(project_id)

        lanes.append(
            {
                **group,
                'line_count': len(lines),
                'projects': projects,
                'baseline_amount': baseline_amount,
                'order_amount': order_amount,
                'order_status_label': order.get_status_display() if order else '',
                'start_date': start_date,
                'end_date': end_date,
                'receivable_total': receivable_total,
                'invoiced_total': invoiced_total,
                'receipt_total': receipt_total,
                'unreceived_total': receivable_total - receipt_total,
                'overdue_total': overdue_total,
                'status': status,
                'status_label': status_label,
                'risk_level': risk_level,
                'cells': cells,
                'events': events,
            }
        )

    lanes.sort(key=lambda lane: (lane['is_unfiled'], lane['is_legacy'], lane['label']))
    ordered_amount = _sum(
        lane['order_amount'] for lane in lanes if not lane['is_unfiled']
    )
    framework_limit = contract.total_amount
    remaining_limit = framework_limit - ordered_amount if framework_limit is not None else None

    return {
        'year': year,
        'months': months,
        'lanes': lanes,
        'should_display': contract.contract_type in supported_contract_types and bool(lanes),
        'order_count': sum(1 for lane in lanes if lane['order']),
        'legacy_count': sum(1 for lane in lanes if lane['is_legacy']),
        'unfiled_count': sum(1 for lane in lanes if lane['is_unfiled']),
        'framework_limit': framework_limit,
        'ordered_amount': ordered_amount,
        'ordered_baseline_amount': ordered_amount,
        'remaining_limit': remaining_limit,
        'receivable_total': _sum(lane['receivable_total'] for lane in lanes),
        'receipt_total': _sum(lane['receipt_total'] for lane in lanes),
        'overdue_total': _sum(lane['overdue_total'] for lane in lanes),
    }
