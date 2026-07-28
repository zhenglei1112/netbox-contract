from calendar import monthrange
from datetime import date
from decimal import Decimal


ZERO = Decimal('0')


def _sum(values):
    return sum(values, ZERO)


def _month_start(value):
    return value.replace(day=1)


def _shift_month(value, offset):
    month_index = value.year * 12 + value.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def _band_key(due_date, today):
    if due_date < today:
        return 'overdue'
    days = (due_date - today).days
    if days <= 7:
        return 'next_7_days'
    if days <= 30:
        return 'days_8_30'
    if days <= 90:
        return 'days_31_90'
    return 'after_90_days'


def _contract_id_from_event(row):
    bill = row.get('bill')
    return getattr(bill, 'contract_id', None)


def _contract_id_from_track(track):
    plan = track.get('plan')
    return getattr(plan, 'contract_id', None)


def _object_url(obj):
    try:
        return obj.get_absolute_url()
    except (AttributeError, TypeError):
        return ''


def _schedule_status(due_date, today):
    if not due_date:
        return '待条件触发'
    days = (due_date - today).days
    if days < 0:
        return f'逾期 {-days} 天'
    if days == 0:
        return '今天到期'
    return f'{days} 天后到期'


def _planned_item(track):
    """Return a future schedule item only when no actual receivable exists."""
    if track.get('events'):
        return None
    plan = track.get('plan')
    if getattr(plan, 'status', '') in {'closed', 'canceled'}:
        return None
    version = track.get('current_version')
    if not version:
        return None
    amount = track.get('current_amount') or ZERO
    if amount <= ZERO:
        return None
    due_date = track.get('effective_due_date') or getattr(version, 'planned_date', None)
    return {
        'amount': amount,
        'due_date': due_date,
        'contract_id': _contract_id_from_track(track),
        'uncertain': getattr(version, 'trigger_type', '') == 'estimated_date',
        'track': track,
    }


def build_revenue_portfolio(event_rows, plan_tracks, *, today=None, month_count=12, detail_limit=200):
    """Aggregate company receivables without double-counting plans already realized.

    Time bands are deliberately non-overlapping. Plans whose trigger has not happened
    stay in a separate bucket instead of being assigned an invented due date.
    """
    today = today or date.today()
    event_rows = [row for row in event_rows if row.get('is_confirmed')]
    tracks = list(plan_tracks.get('tracks', ()))

    band_specs = (
        ('overdue', '已逾期', 'danger'),
        ('next_7_days', '未来7天', 'warning'),
        ('days_8_30', '未来8–30天', 'info'),
        ('days_31_90', '未来31–90天', 'primary'),
        ('after_90_days', '90天以后', 'muted'),
        ('pending_trigger', '待条件触发', 'secondary'),
    )
    bands = {
        key: {
            'key': key,
            'label': label,
            'tone': tone,
            'amount': ZERO,
            'formed_amount': ZERO,
            'planned_amount': ZERO,
            'event_count': 0,
            'contract_ids': set(),
            'details': [],
        }
        for key, label, tone in band_specs
    }

    for row in event_rows:
        due_date = row.get('due_date')
        amount = max(row.get('unreceived_amount') or ZERO, ZERO)
        if not due_date or amount <= ZERO:
            continue
        band = bands[_band_key(due_date, today)]
        band['amount'] += amount
        band['formed_amount'] += amount
        band['event_count'] += 1
        contract_id = _contract_id_from_event(row)
        if contract_id is not None:
            band['contract_ids'].add(contract_id)
        bill = row.get('bill')
        contract = getattr(bill, 'contract', None)
        line = row.get('line')
        band['details'].append(
            {
                'kind': 'formed',
                'kind_label': '已形成应收',
                'contract': contract,
                'contract_url': _object_url(contract),
                'source': line or bill or row.get('event_key', '-'),
                'source_url': row.get('line_url') or row.get('bill_url') or '',
                'due_date': due_date,
                'schedule_status': _schedule_status(due_date, today),
                'amount': amount,
                'status_label': row.get('collection_status_label') or '待收款',
                'uncertain': False,
            }
        )

    planned_items = []
    for track in tracks:
        item = _planned_item(track)
        if not item:
            continue
        planned_items.append(item)
        key = _band_key(item['due_date'], today) if item['due_date'] else 'pending_trigger'
        band = bands[key]
        band['amount'] += item['amount']
        band['planned_amount'] += item['amount']
        band['event_count'] += 1
        if item['contract_id'] is not None:
            band['contract_ids'].add(item['contract_id'])
        track = item['track']
        plan = track.get('plan')
        contract = getattr(plan, 'contract', None)
        band['details'].append(
            {
                'kind': 'planned',
                'kind_label': '当前计划',
                'contract': contract,
                'contract_url': _object_url(contract),
                'source': plan or '-',
                'source_url': track.get('plan_url') or _object_url(plan),
                'due_date': item['due_date'],
                'schedule_status': _schedule_status(item['due_date'], today),
                'amount': item['amount'],
                'status_label': track.get('status_label') or ('日期预计' if item['uncertain'] else '计划中'),
                'uncertain': item['uncertain'],
            }
        )

    band_list = []
    for key, _label, _tone in band_specs:
        band = bands[key]
        band['contract_count'] = len(band.pop('contract_ids'))
        band['details'].sort(key=lambda item: (item['due_date'] or date.max, str(item['source'])))
        band['detail_count'] = len(band['details'])
        band['details_truncated'] = band['detail_count'] > detail_limit
        band['export_details'] = band['details']
        band['details'] = band['details'][:detail_limit]
        band_list.append(band)

    month_count = max(int(month_count), 1)
    first_month = _month_start(today)
    months = []
    months_by_key = {}
    for offset in range(month_count):
        start = _shift_month(first_month, offset)
        month = {
            'key': start.strftime('%Y-%m'),
            'label': start.strftime('%Y年%m月'),
            'start': start,
            'end': date(start.year, start.month, monthrange(start.year, start.month)[1]),
            'received': ZERO,
            'invoiced_unreceived': ZERO,
            'uninvoiced': ZERO,
            'overdue': ZERO,
            'uncertain': ZERO,
            'details': [],
        }
        months.append(month)
        months_by_key[month['key']] = month

    for row in event_rows:
        due_date = row.get('due_date')
        if not due_date:
            continue
        month = months_by_key.get(due_date.strftime('%Y-%m'))
        if not month:
            continue
        net_amount = max(row.get('net_amount') or ZERO, ZERO)
        received = min(max(row.get('receipted_amount') or ZERO, ZERO), net_amount)
        remaining = max(net_amount - received, ZERO)
        bill = row.get('bill')
        contract = getattr(bill, 'contract', None)
        line = row.get('line')
        month['details'].append(
            {
                'kind': 'formed',
                'kind_label': '已形成应收',
                'contract': contract,
                'contract_url': _object_url(contract),
                'source': line or bill or row.get('event_key', '-'),
                'source_url': row.get('line_url') or row.get('bill_url') or '',
                'due_date': due_date,
                'schedule_status': _schedule_status(due_date, today),
                'amount': net_amount,
                'received_amount': received,
                'outstanding_amount': remaining,
                'status_label': row.get('collection_status_label') or '待收款',
                'uncertain': False,
            }
        )
        month['received'] += received
        if due_date < today:
            month['overdue'] += remaining
            continue
        invoiced_unreceived = min(
            max((row.get('mapped_amount') or ZERO) - received, ZERO),
            remaining,
        )
        month['invoiced_unreceived'] += invoiced_unreceived
        month['uninvoiced'] += remaining - invoiced_unreceived

    for item in planned_items:
        due_date = item['due_date']
        if not due_date:
            continue
        month = months_by_key.get(due_date.strftime('%Y-%m'))
        if not month:
            continue
        target = 'uncertain' if item['uncertain'] else 'uninvoiced'
        month[target] += item['amount']
        track = item['track']
        plan = track.get('plan')
        contract = getattr(plan, 'contract', None)
        month['details'].append(
            {
                'kind': 'planned',
                'kind_label': '当前计划',
                'contract': contract,
                'contract_url': _object_url(contract),
                'source': plan or '-',
                'source_url': track.get('plan_url') or _object_url(plan),
                'due_date': due_date,
                'schedule_status': _schedule_status(due_date, today),
                'amount': item['amount'],
                'received_amount': ZERO,
                'outstanding_amount': item['amount'],
                'status_label': track.get('status_label') or ('日期预计' if item['uncertain'] else '计划中'),
                'uncertain': item['uncertain'],
            }
        )

    categories = ('received', 'invoiced_unreceived', 'uninvoiced', 'overdue', 'uncertain')
    for month in months:
        month['total'] = _sum(month[key] for key in categories)
    max_month_total = max((month['total'] for month in months), default=ZERO)
    for month in months:
        denominator = max_month_total or Decimal('1')
        month['width_percent'] = float(month['total'] / denominator * Decimal('100'))
        month['segments'] = [
            {
                'key': key,
                'amount': month[key],
                'percent': float(month[key] / month['total'] * Decimal('100')) if month['total'] else 0,
            }
            for key in categories
            if month[key] > ZERO
        ]
        month['details'].sort(key=lambda item: (item['due_date'] or date.max, str(item['source'])))
        month['detail_count'] = len(month['details'])
        month['details_truncated'] = month['detail_count'] > detail_limit
        month['export_details'] = month['details']
        month['details'] = month['details'][:detail_limit]

    formed_total = _sum(row.get('net_amount') or ZERO for row in event_rows)
    receipt_total = _sum(row.get('receipted_amount') or ZERO for row in event_rows)
    open_total = _sum(max(row.get('unreceived_amount') or ZERO, ZERO) for row in event_rows)
    planned_total = _sum(item['amount'] for item in planned_items if item['due_date'] and item['due_date'] >= today)
    pending_trigger_total = bands['pending_trigger']['amount']
    contract_ids = {
        contract_id
        for contract_id in (
            [_contract_id_from_event(row) for row in event_rows] + [item['contract_id'] for item in planned_items]
        )
        if contract_id is not None
    }

    return {
        'as_of_date': today,
        'bands': band_list,
        'months': months,
        'has_data': bool(event_rows or planned_items),
        'totals': {
            'contract_count': len(contract_ids),
            'formed_receivable': formed_total,
            'receipt_total': receipt_total,
            'open_receivable': open_total,
            'overdue': bands['overdue']['amount'],
            'future_planned': planned_total,
            'pending_trigger': pending_trigger_total,
        },
    }
