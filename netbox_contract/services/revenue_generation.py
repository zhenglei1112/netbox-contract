"""Pure receivable-generation decisions for revenue billing rules.

This module intentionally performs no ORM queries or writes.  In particular,
stage rules require an explicit confirmed trigger fact; contract dates and
billing periods are never treated as proof that a milestone occurred.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal


ZERO = Decimal('0')
STAGE_RULE_TYPES = frozenset(('milestone', 'one_time'))


@dataclass(frozen=True)
class TriggerFact:
    billing_rule_id: object
    trigger_event: str
    actual_trigger_date: date
    status: str = 'confirmed'
    source_id: str = ''


def _value(item, name, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _identity(item):
    return _value(item, 'pk', _value(item, 'id'))


def _period_bounds(billing_period):
    try:
        year_text, month_text = str(billing_period).split('-', 1)
        year, month = int(year_text), int(month_text)
        return date(year, month, 1), date(year, month, monthrange(year, month)[1])
    except (TypeError, ValueError):
        raise ValueError("billing_period must use YYYY-MM") from None


def _add_months(value, months):
    target_index = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(target_index, 12)
    month = month_index + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def _billing_window(rule, period_start):
    interval = {'month': 1, 'quarter': 3, 'year': 12}.get(_value(rule, 'billing_cycle'), 1)
    return period_start, _add_months(period_start, interval) - timedelta(days=1)


def _round_amount(amount, precision):
    quantum = Decimal('1') if str(precision) == '0' else Decimal(
        f"0.{'0' * (int(precision or 2) - 1)}1"
    )
    return amount.quantize(quantum)


def _recurring_amount(contract_line, rule, active_start, active_end, period_start, period_end):
    amount = _value(contract_line, 'unit_price') * _value(contract_line, 'quantity')
    if _value(rule, 'proration_rule') not in ('none', 'full_month'):
        total_days = Decimal((period_end - period_start).days + 1)
        active_days = Decimal((active_end - active_start).days + 1)
        amount = amount * active_days / total_days
    return _round_amount(amount, _value(rule, 'rounding_precision', '2'))


def _base_row(contract_line, rule, period_start, period_end):
    return {
        'contract_line': contract_line,
        'rule': rule,
        'rule_type': _value(rule, 'rule_type'),
        'period_start': period_start,
        'period_end': period_end,
        'active_start': None,
        'active_end': None,
        'amount': ZERO,
        'idempotent_key': '',
        'will_create': False,
        'reason_code': '',
        'reason': '',
        'trigger_fact': None,
        'trigger_date': None,
        'receivable_date': None,
    }


def _skip(row, code, reason):
    row.update(reason_code=code, reason=reason, status_label='跳过')
    return row


def _ready(row, *, active_start, active_end, amount, idempotent_key, trigger_fact=None):
    row.update(
        active_start=active_start,
        active_end=active_end,
        amount=amount,
        idempotent_key=idempotent_key,
        will_create=True,
        reason_code='ready',
        reason='可生成',
        status_label='待生成',
        trigger_fact=trigger_fact,
        trigger_date=_value(trigger_fact, 'actual_trigger_date') if trigger_fact else None,
        receivable_date=active_start,
    )
    return row


def _matching_trigger_facts(rule, trigger_facts):
    rule_id = _identity(rule)
    trigger_event = _value(rule, 'trigger_event', '')
    matches = [
        fact for fact in trigger_facts
        if str(_value(fact, 'billing_rule_id')) == str(rule_id)
        and _value(fact, 'trigger_event') == trigger_event
        and _value(fact, 'status', 'confirmed') == 'confirmed'
        and isinstance(_value(fact, 'actual_trigger_date'), date)
    ]
    unique_by_date = {}
    for fact in matches:
        unique_by_date.setdefault(_value(fact, 'actual_trigger_date'), fact)
    return list(unique_by_date.values())


def build_receivable_generation_preview(
    contract_lines,
    billing_rules,
    billing_period,
    *,
    trigger_facts=(),
    existing_idempotent_keys=(),
):
    """Build ORM-free generation rows for recurring and stage rules.

    ``trigger_facts`` is deliberately keyed directly to a billing rule and does
    not require a receivable plan.  A milestone or one-time row is eligible only
    when exactly one confirmed trigger date exists for its configured event and
    that date plus the configured offset falls inside the requested billing month.
    """
    period_start, period_end = _period_bounds(billing_period)
    existing_keys = set(existing_idempotent_keys)
    lines_by_id = {_identity(line): line for line in contract_lines}
    rows = []

    for rule in billing_rules:
        line = lines_by_id.get(_value(rule, 'contract_line_id'))
        if line is None:
            continue
        row = _base_row(line, rule, period_start, period_end)
        if not _value(rule, 'is_active', True) or _value(rule, 'status', 'effective') != 'effective':
            rows.append(_skip(row, 'inactive_rule', '计费规则未生效'))
            continue

        rule_type = _value(rule, 'rule_type')
        line_start = _value(line, 'valid_from')
        line_end = _value(line, 'valid_to')
        if rule_type == 'recurring':
            window_start, window_end = _billing_window(rule, period_start)
            row['period_start'], row['period_end'] = window_start, window_end
            active_start = max(window_start, line_start)
            active_end = min(window_end, line_end) if line_end else window_end
            if active_start > active_end:
                rows.append(_skip(row, 'outside_validity', '本账期无有效计费区间'))
                continue
            key = (
                f"{_identity(line)}-{_identity(rule)}-{billing_period}-"
                f"{active_start:%Y%m%d}-{active_end:%Y%m%d}"
            )
            if key in existing_keys:
                row['idempotent_key'] = key
                rows.append(_skip(row, 'already_exists', '已存在，不重复生成'))
                continue
            ready_row = _ready(
                row,
                active_start=active_start,
                active_end=active_end,
                amount=_recurring_amount(line, rule, active_start, active_end, window_start, window_end),
                idempotent_key=key,
            )
            ready_row['receivable_date'] = active_end
            rows.append(ready_row)
            continue

        if rule_type not in STAGE_RULE_TYPES:
            rows.append(_skip(row, 'unsupported_rule_type', '不支持的计费方式'))
            continue

        facts = _matching_trigger_facts(rule, trigger_facts)
        if not facts:
            rows.append(_skip(row, 'awaiting_trigger', '尚无已确认的触发事实'))
            continue
        if len(facts) > 1:
            rows.append(_skip(row, 'ambiguous_trigger', '存在多个不同的已确认触发日期'))
            continue
        fact = facts[0]
        trigger_date = _value(fact, 'actual_trigger_date')
        row['trigger_fact'], row['trigger_date'] = fact, trigger_date
        if trigger_date < line_start or (line_end and trigger_date > line_end):
            rows.append(_skip(row, 'trigger_outside_validity', '触发日期不在合同项有效期内'))
            continue
        offset_days = _value(rule, 'trigger_offset_days', 0)
        if not isinstance(offset_days, int) or offset_days < 0:
            rows.append(_skip(row, 'invalid_trigger_offset', '触发后应收天数必须为非负整数'))
            continue
        receivable_date = trigger_date + timedelta(days=offset_days)
        row['receivable_date'] = receivable_date
        if not period_start <= receivable_date <= period_end:
            rows.append(_skip(row, 'receivable_outside_period', '应收形成日期不在当前账期'))
            continue
        key = (
            f"{rule_type}-{_identity(line)}-{_identity(rule)}-"
            f"{_value(rule, 'trigger_event')}-{trigger_date:%Y%m%d}"
        )
        if key in existing_keys:
            row['idempotent_key'] = key
            rows.append(_skip(row, 'already_exists', '已存在，不重复生成'))
            continue
        amount = _round_amount(
            _value(line, 'unit_price') * _value(line, 'quantity'),
            _value(rule, 'rounding_precision', '2'),
        )
        rows.append(_ready(
            row,
            active_start=receivable_date,
            active_end=receivable_date,
            amount=amount,
            idempotent_key=key,
            trigger_fact=fact,
        ))

    ready_rows = [row for row in rows if row['will_create']]
    return {
        'billing_period': billing_period,
        'period_start': period_start,
        'period_end': period_end,
        'rows': rows,
        'create_count': len(ready_rows),
        'skip_count': len(rows) - len(ready_rows),
        'create_total': sum((row['amount'] for row in ready_rows), ZERO),
    }
