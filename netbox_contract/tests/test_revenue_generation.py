from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from netbox_contract.services.revenue_generation import (
    TriggerFact,
    build_receivable_generation_preview,
)


def line(**overrides):
    values = {
        'pk': 1,
        'valid_from': date(2026, 1, 1),
        'valid_to': None,
        'unit_price': Decimal('100.00'),
        'quantity': Decimal('2.00'),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def rule(rule_type='recurring', **overrides):
    values = {
        'pk': 10,
        'contract_line_id': 1,
        'rule_type': rule_type,
        'trigger_event': '' if rule_type == 'recurring' else 'acceptance',
        'billing_cycle': 'month' if rule_type == 'recurring' else '',
        'proration_rule': 'none',
        'rounding_precision': '2',
        'is_active': True,
        'status': 'effective',
        'trigger_offset_days': 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def preview(billing_rule, *, facts=(), existing=(), billing_period='2026-02'):
    return build_receivable_generation_preview(
        [line()],
        [billing_rule],
        billing_period,
        trigger_facts=facts,
        existing_idempotent_keys=existing,
    )


def test_recurring_rule_is_ready_without_plan():
    result = preview(rule())
    row = result['rows'][0]
    assert row['will_create'] is True
    assert row['active_start'] == date(2026, 2, 1)
    assert row['active_end'] == date(2026, 2, 28)
    assert row['amount'] == Decimal('200.00')
    assert result['create_total'] == Decimal('200.00')


def test_untriggered_milestone_has_no_invented_dates():
    row = preview(rule('milestone'))['rows'][0]
    assert row['will_create'] is False
    assert row['reason_code'] == 'awaiting_trigger'
    assert row['trigger_date'] is None
    assert row['active_start'] is None
    assert row['active_end'] is None
    assert row['idempotent_key'] == ''


def test_confirmed_milestone_fact_generates_on_actual_trigger_date_without_plan():
    fact = TriggerFact(10, 'acceptance', date(2026, 2, 12), source_id='acceptance-42')
    row = preview(rule('milestone'), facts=[fact])['rows'][0]
    assert row['will_create'] is True
    assert row['trigger_fact'] is fact
    assert row['trigger_date'] == date(2026, 2, 12)
    assert row['active_start'] == row['active_end'] == date(2026, 2, 12)
    assert row['amount'] == Decimal('200.00')
    assert row['idempotent_key'] == 'milestone-1-10-acceptance-20260212'


def test_one_time_rule_uses_the_same_confirmed_trigger_contract():
    fact = {
        'billing_rule_id': 10,
        'trigger_event': 'acceptance',
        'actual_trigger_date': date(2026, 2, 3),
        'status': 'confirmed',
    }
    row = preview(rule('one_time'), facts=[fact])['rows'][0]
    assert row['will_create'] is True
    assert row['active_start'] == row['active_end'] == date(2026, 2, 3)


def test_unconfirmed_or_wrong_event_fact_does_not_trigger_stage_rule():
    facts = [
        TriggerFact(10, 'acceptance', date(2026, 2, 3), status='draft'),
        TriggerFact(10, 'delivery', date(2026, 2, 4)),
        TriggerFact(99, 'acceptance', date(2026, 2, 5)),
    ]
    row = preview(rule('milestone'), facts=facts)['rows'][0]
    assert row['reason_code'] == 'awaiting_trigger'
    assert row['active_start'] is None


def test_trigger_fact_is_only_generated_in_its_actual_month():
    fact = TriggerFact(10, 'acceptance', date(2026, 1, 31))
    row = preview(rule('milestone'), facts=[fact], billing_period='2026-02')['rows'][0]
    assert row['reason_code'] == 'receivable_outside_period'
    assert row['trigger_date'] == date(2026, 1, 31)
    assert row['active_start'] is None
    assert row['active_end'] is None


def test_trigger_offset_uses_receivable_month_without_changing_trigger_fact():
    fact = TriggerFact(10, 'acceptance', date(2026, 2, 28))
    billing_rule = rule('milestone', trigger_offset_days=2)

    february = preview(billing_rule, facts=[fact], billing_period='2026-02')['rows'][0]
    march = preview(billing_rule, facts=[fact], billing_period='2026-03')['rows'][0]

    assert february['reason_code'] == 'receivable_outside_period'
    assert february['trigger_date'] == date(2026, 2, 28)
    assert february['receivable_date'] == date(2026, 3, 2)
    assert february['active_start'] is None
    assert march['will_create'] is True
    assert march['trigger_date'] == date(2026, 2, 28)
    assert march['receivable_date'] == date(2026, 3, 2)
    assert march['active_start'] == march['active_end'] == date(2026, 3, 2)


def test_distinct_confirmed_trigger_dates_are_rejected_as_ambiguous():
    facts = [
        TriggerFact(10, 'acceptance', date(2026, 2, 3)),
        TriggerFact(10, 'acceptance', date(2026, 2, 4)),
    ]
    row = preview(rule('milestone'), facts=facts)['rows'][0]
    assert row['reason_code'] == 'ambiguous_trigger'
    assert row['active_start'] is None


def test_duplicate_same_date_trigger_facts_are_safe_and_idempotent():
    facts = [
        TriggerFact(10, 'acceptance', date(2026, 2, 3), source_id='a'),
        TriggerFact(10, 'acceptance', date(2026, 2, 3), source_id='b'),
    ]
    first = preview(rule('milestone'), facts=facts)['rows'][0]
    second = preview(
        rule('milestone'),
        facts=facts,
        existing=[first['idempotent_key']],
    )['rows'][0]
    assert first['will_create'] is True
    assert second['will_create'] is False
    assert second['reason_code'] == 'already_exists'


def test_stage_trigger_outside_contract_line_validity_is_not_generated():
    limited_line = line(valid_to=date(2026, 2, 10))
    fact = TriggerFact(10, 'acceptance', date(2026, 2, 12))
    result = build_receivable_generation_preview(
        [limited_line], [rule('milestone')], '2026-02', trigger_facts=[fact]
    )
    assert result['rows'][0]['reason_code'] == 'trigger_outside_validity'


def test_invalid_billing_period_is_rejected():
    import pytest

    with pytest.raises(ValueError, match='YYYY-MM'):
        preview(rule(), billing_period='2026-13')
