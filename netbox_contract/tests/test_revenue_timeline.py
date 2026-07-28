from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase

from netbox_contract.services.revenue_timeline import (
    build_revenue_timeline,
    build_rule_projection_nodes,
)


def _version(*, trigger_type, planned_date, amount):
    return SimpleNamespace(
        trigger_type=trigger_type,
        planned_date=planned_date,
        planned_amount=Decimal(str(amount)),
    )


def _event(
    key,
    *,
    receivable_date,
    due_date,
    net=100,
    mapped=50,
    received=20,
    confirmed=True,
    status='partial_invoice',
    risk='warning',
):
    contract_line = SimpleNamespace(pk=f'line-{key}', charge_item=f'charge-{key}')
    return {
        'event_key': key,
        'event_dom_id': f'dom-{key}',
        'is_confirmed': confirmed,
        'contract_line': contract_line,
        'contract_line_url': f'/lines/{key}/',
        'billing_rule': SimpleNamespace(pk=f'rule-{key}'),
        'receivable_date': receivable_date,
        'due_date': due_date,
        'net_amount': Decimal(str(net)),
        'mapped_amount': Decimal(str(mapped)),
        'receipted_amount': Decimal(str(received)),
        'unreceived_amount': Decimal(str(net - received)),
        'collection_status': status,
        'collection_status_label': status,
        'risk_level': risk,
    }


def _track(
    code,
    *,
    trigger_type='fixed_date',
    planned_date=None,
    effective_due_date=None,
    amount=100,
    events=(),
    original_date=None,
    status='planned',
    risk='muted',
    plan_status='effective',
):
    current = _version(
        trigger_type=trigger_type,
        planned_date=planned_date,
        amount=amount,
    )
    original = _version(
        trigger_type=trigger_type,
        planned_date=original_date,
        amount=Decimal(str(amount)) - Decimal('10'),
    )
    contract_line = SimpleNamespace(pk=f'line-{code}', charge_item=f'charge-{code}')
    plan = SimpleNamespace(
        pk=code,
        plan_code=code,
        charge_item=f'plan-charge-{code}',
        status=plan_status,
    )
    return {
        'plan': plan,
        'plan_url': f'/plans/{code}/',
        'contract_line': contract_line,
        'contract_line_url': f'/lines/{code}/',
        'billing_rule': SimpleNamespace(pk=f'rule-{code}'),
        'original_version': original,
        'original_version_url': f'/versions/{code}/original/',
        'current_version': current,
        'current_version_url': f'/versions/{code}/current/',
        'original_amount': original.planned_amount,
        'current_amount': current.planned_amount,
        'actual_receivable_date': None,
        'effective_due_date': effective_due_date,
        'events': list(events),
        'status': status,
        'status_label': status,
        'risk_level': risk,
    }


class RevenueTimelineTests(TestCase):
    def setUp(self):
        self.today = date(2026, 7, 15)

    def test_projects_formed_event_with_plan_context_and_financial_chain(self):
        event = _event(
            'formed',
            receivable_date=date(2026, 7, 1),
            due_date=date(2026, 7, 10),
            net=120,
            mapped=80,
            received=30,
        )
        track = _track(
            'P1',
            planned_date=date(2026, 7, 5),
            effective_due_date=date(2026, 7, 10),
            amount=120,
            original_date=date(2026, 6, 30),
            events=[event],
        )

        result = build_revenue_timeline([event], {'tracks': [track]}, today=self.today)

        self.assertEqual(len(result['nodes']), 1)
        node = result['nodes'][0]
        self.assertEqual(node['kind'], 'formed')
        self.assertEqual(node['date_certainty'], 'actual')
        self.assertEqual(node['original_plan_date'], date(2026, 6, 30))
        self.assertEqual(node['current_plan_date'], date(2026, 7, 5))
        self.assertEqual(node['actual_receivable_date'], date(2026, 7, 1))
        self.assertEqual(node['receivable_amount'], Decimal('120'))
        self.assertEqual(node['invoiced_amount'], Decimal('80'))
        self.assertEqual(node['received_amount'], Decimal('30'))
        self.assertEqual(node['unreceived_amount'], Decimal('90'))
        self.assertEqual(node['event_dom_id'], 'dom-formed')
        self.assertEqual(node['plan_url'], '/plans/P1/')
        self.assertEqual(node['charge_item'], 'charge-formed')

    def test_does_not_repeat_plan_that_already_has_a_formed_event(self):
        event = _event(
            'formed',
            receivable_date=date(2026, 7, 1),
            due_date=date(2026, 7, 20),
        )
        track = _track(
            'P1',
            planned_date=date(2026, 7, 20),
            effective_due_date=date(2026, 7, 20),
            events=[event],
        )

        result = build_revenue_timeline([event], {'tracks': [track]}, today=self.today)

        self.assertEqual([node['kind'] for node in result['all_nodes']], ['formed'])

    def test_projects_fixed_estimated_and_pending_trigger_plans_without_inventing_date(self):
        tracks = [
            _track(
                'fixed',
                planned_date=date(2026, 7, 25),
                effective_due_date=date(2026, 7, 25),
            ),
            _track(
                'estimated',
                trigger_type='estimated_date',
                planned_date=date(2026, 8, 20),
                effective_due_date=date(2026, 8, 20),
            ),
            _track('pending', trigger_type='trigger_offset'),
        ]

        result = build_revenue_timeline([], {'tracks': tracks}, today=self.today)
        nodes = {node['plan'].plan_code: node for node in result['nodes']}

        self.assertEqual(nodes['fixed']['date_certainty'], 'fixed')
        self.assertEqual(nodes['fixed']['timeline_date'], date(2026, 7, 25))
        self.assertEqual(nodes['estimated']['date_certainty'], 'estimated')
        self.assertEqual(nodes['estimated']['timeline_date'], date(2026, 8, 20))
        self.assertEqual(nodes['pending']['date_certainty'], 'pending_trigger')
        self.assertIsNone(nodes['pending']['timeline_date'])
        self.assertIsNone(nodes['pending']['due_date'])
        self.assertEqual(nodes['pending']['plan_url'], '/plans/pending/')

    def test_filters_are_inclusive_and_overdue_requires_an_open_balance(self):
        events = [
            _event(
                'overdue-open',
                receivable_date=date(2026, 7, 1),
                due_date=date(2026, 7, 14),
                received=20,
            ),
            _event(
                'overdue-paid',
                receivable_date=date(2026, 7, 1),
                due_date=date(2026, 7, 14),
                received=100,
                status='paid',
                risk='success',
            ),
            _event(
                'today',
                receivable_date=date(2026, 7, 1),
                due_date=self.today,
            ),
        ]
        tracks = [
            _track('day30', planned_date=date(2026, 8, 14), effective_due_date=date(2026, 8, 14)),
            _track('day90', planned_date=date(2026, 10, 13), effective_due_date=date(2026, 10, 13)),
            _track('day91', planned_date=date(2026, 10, 14), effective_due_date=date(2026, 10, 14)),
            _track('pending', trigger_type='trigger_offset'),
        ]

        overdue = build_revenue_timeline(events, {'tracks': tracks}, today=self.today, filter_key='overdue')
        next_30 = build_revenue_timeline(events, {'tracks': tracks}, today=self.today, filter_key='next_30_days')
        next_90 = build_revenue_timeline(events, {'tracks': tracks}, today=self.today, filter_key='next_90_days')
        pending = build_revenue_timeline(events, {'tracks': tracks}, today=self.today, filter_key='pending_trigger')

        self.assertEqual([node['event_key'] for node in overdue['nodes']], ['overdue-open'])
        self.assertEqual(
            {node.get('event_key') or node['plan'].plan_code for node in next_30['nodes']},
            {'today', 'day30'},
        )
        self.assertEqual(
            {node.get('event_key') or node['plan'].plan_code for node in next_90['nodes']},
            {'today', 'day30', 'day90'},
        )
        self.assertEqual([node['plan'].plan_code for node in pending['nodes']], ['pending'])

    def test_attention_filter_combines_overdue_pending_and_next_30_days(self):
        events = [
            _event(
                'overdue-open',
                receivable_date=date(2026, 7, 1),
                due_date=date(2026, 7, 14),
                net=100,
                received=20,
            ),
            _event(
                'overdue-paid',
                receivable_date=date(2026, 7, 1),
                due_date=date(2026, 7, 14),
                net=100,
                received=100,
                status='paid',
                risk='success',
            ),
            _event(
                'today',
                receivable_date=self.today,
                due_date=self.today,
                net=40,
                received=10,
            ),
        ]
        tracks = [
            _track(
                'day30',
                planned_date=date(2026, 8, 14),
                effective_due_date=date(2026, 8, 14),
                amount=30,
            ),
            _track(
                'day31',
                planned_date=date(2026, 8, 15),
                effective_due_date=date(2026, 8, 15),
                amount=31,
            ),
            _track('pending', trigger_type='trigger_offset', amount=50),
        ]

        result = build_revenue_timeline(
            events,
            {'tracks': tracks},
            today=self.today,
            filter_key='attention',
        )

        identities = {
            node.get('event_key') or node['plan'].plan_code
            for node in result['nodes']
        }
        self.assertEqual(identities, {'overdue-open', 'today', 'day30', 'pending'})
        self.assertEqual(result['filter_counts']['attention'], 4)
        self.assertEqual(result['visible_totals']['receivable_amount'], Decimal('140'))
        self.assertEqual(result['visible_totals']['unreceived_amount'], Decimal('110'))
        self.assertEqual(result['visible_totals']['planned_amount'], Decimal('80'))

    def test_excludes_unconfirmed_events_and_closed_or_canceled_plans(self):
        draft = _event(
            'draft',
            receivable_date=date(2026, 7, 1),
            due_date=date(2026, 7, 20),
            confirmed=False,
        )
        tracks = [
            _track('closed', planned_date=date(2026, 7, 20), plan_status='closed'),
            _track('canceled', planned_date=date(2026, 7, 20), plan_status='canceled'),
        ]

        result = build_revenue_timeline([draft], {'tracks': tracks}, today=self.today)

        self.assertFalse(result['has_data'])
        self.assertEqual(result['nodes'], [])

    def test_unconfirmed_event_does_not_hide_its_still_effective_plan(self):
        draft = _event(
            'draft',
            receivable_date=date(2026, 7, 1),
            due_date=date(2026, 7, 20),
            confirmed=False,
        )
        track = _track(
            'planned',
            planned_date=date(2026, 7, 20),
            effective_due_date=date(2026, 7, 20),
            events=[draft],
        )

        result = build_revenue_timeline([draft], {'tracks': [track]}, today=self.today)

        self.assertEqual([node['kind'] for node in result['nodes']], ['planned'])

    def test_event_without_due_date_is_not_inferred_overdue_from_receivable_date(self):
        event = _event(
            'no-due-date',
            receivable_date=date(2026, 6, 1),
            due_date=None,
            received=0,
        )

        result = build_revenue_timeline(
            [event],
            {'tracks': []},
            today=self.today,
            filter_key='overdue',
        )

        self.assertEqual(result['nodes'], [])

    def test_visible_totals_follow_the_active_window(self):
        tracks = [
            _track('day30', planned_date=date(2026, 8, 14), effective_due_date=date(2026, 8, 14), amount=30),
            _track('day90', planned_date=date(2026, 10, 13), effective_due_date=date(2026, 10, 13), amount=90),
        ]

        result = build_revenue_timeline(
            [],
            {'tracks': tracks},
            today=self.today,
            filter_key='next_30_days',
        )

        self.assertEqual(result['visible_totals']['node_count'], 1)
        self.assertEqual(result['visible_totals']['planned_amount'], Decimal('30'))
        self.assertEqual(result['totals']['planned_amount'], Decimal('120'))

    def test_rejects_unknown_filter(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported timeline filter'):
            build_revenue_timeline([], {'tracks': []}, today=self.today, filter_key='invalid')


def _rule_line(**overrides):
    values = {
        'pk': 501,
        'valid_from': date(2026, 7, 1),
        'valid_to': None,
        'unit_price': Decimal('100'),
        'quantity': Decimal('1'),
        'charge_item': '规则收费项',
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _billing_rule(rule_type='recurring', **overrides):
    values = {
        'pk': 601,
        'contract_line_id': 501,
        'rule_type': rule_type,
        'billing_cycle': 'month' if rule_type == 'recurring' else '',
        'billing_direction': 'prepay' if rule_type == 'recurring' else '',
        'bill_generation_day': 20 if rule_type == 'recurring' else None,
        'proration_rule': 'none',
        'rounding_precision': '2',
        'trigger_event': '' if rule_type == 'recurring' else 'acceptance',
        'trigger_offset_days': 0,
        'is_active': True,
        'status': 'effective',
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class RevenueRuleProjectionTests(TestCase):
    def test_recurring_projection_obeys_validity_proration_precision_and_generation_day(self):
        line = _rule_line(valid_from=date(2026, 7, 15), valid_to=date(2026, 8, 14))
        rule = _billing_rule(proration_rule='actual_days')

        nodes = build_rule_projection_nodes([line], [rule], today=date(2026, 7, 1), projection_end=date(2026, 8, 31))

        self.assertEqual([node['billing_period'] for node in nodes], ['2026-07', '2026-08'])
        self.assertEqual([node['timeline_date'] for node in nodes], [date(2026, 7, 20), date(2026, 8, 20)])
        self.assertEqual([node['current_plan_amount'] for node in nodes], [Decimal('54.84'), Decimal('45.16')])

    def test_quarterly_postpay_projects_on_clamped_last_month_generation_day(self):
        line = _rule_line(valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31))
        rule = _billing_rule(billing_cycle='quarter', billing_direction='postpay', bill_generation_day=31)

        nodes = build_rule_projection_nodes([line], [rule], today=date(2026, 1, 1), projection_end=date(2026, 6, 30))

        self.assertEqual([node['billing_period'] for node in nodes], ['2026-01', '2026-04'])
        self.assertEqual([node['timeline_date'] for node in nodes], [date(2026, 3, 31), date(2026, 6, 30)])

    def test_confirmed_recurring_fact_suppresses_only_same_rule_and_period(self):
        line = _rule_line()
        rule = _billing_rule()
        event = {
            'is_confirmed': True,
            'billing_rule': rule,
            'billing_period': '2026-07',
        }

        nodes = build_rule_projection_nodes(
            [line], [rule], [event], today=date(2026, 7, 1), projection_end=date(2026, 8, 31)
        )

        self.assertEqual([node['billing_period'] for node in nodes], ['2026-08'])

    def test_stage_rule_waits_undated_then_uses_unique_confirmed_trigger_plus_offset(self):
        line = _rule_line()
        rule = _billing_rule('milestone', trigger_offset_days=3)
        pending = build_rule_projection_nodes([line], [rule], today=date(2026, 7, 1), projection_end=date(2026, 8, 31))
        records = [
            {
                'billing_rule_id': 601,
                'trigger_event': 'acceptance',
                'actual_trigger_date': date(2026, 7, 10),
                'status': 'confirmed',
            },
            {
                'billing_rule_id': 601,
                'trigger_event': 'acceptance',
                'actual_trigger_date': date(2026, 7, 10),
                'status': 'confirmed',
            },
        ]
        triggered = build_rule_projection_nodes(
            [line], [rule], today=date(2026, 7, 1), projection_end=date(2026, 8, 31), trigger_records=records
        )

        self.assertEqual(pending[0]['date_certainty'], 'pending_trigger')
        self.assertIsNone(pending[0]['timeline_date'])
        self.assertEqual(len(triggered), 1)
        self.assertEqual(triggered[0]['timeline_date'], date(2026, 7, 13))
        self.assertEqual(triggered[0]['current_plan_amount'], Decimal('100.00'))

    def test_distinct_stage_trigger_dates_are_ambiguous_and_outside_validity_is_not_used(self):
        line = _rule_line(valid_to=date(2026, 7, 31))
        rule = _billing_rule('one_time')
        ambiguous = [
            {
                'billing_rule_id': 601,
                'trigger_event': 'acceptance',
                'actual_trigger_date': date(2026, 7, 10),
                'status': 'confirmed',
            },
            {
                'billing_rule_id': 601,
                'trigger_event': 'acceptance',
                'actual_trigger_date': date(2026, 7, 11),
                'status': 'confirmed',
            },
        ]
        outside = [
            {
                'billing_rule_id': 601,
                'trigger_event': 'acceptance',
                'actual_trigger_date': date(2026, 8, 1),
                'status': 'confirmed',
            },
        ]

        ambiguous_node = build_rule_projection_nodes(
            [line], [rule], today=date(2026, 7, 1), projection_end=date(2026, 8, 31), trigger_records=ambiguous
        )[0]
        outside_node = build_rule_projection_nodes(
            [line], [rule], today=date(2026, 7, 1), projection_end=date(2026, 8, 31), trigger_records=outside
        )[0]

        self.assertEqual(ambiguous_node['status'], 'ambiguous_trigger')
        self.assertEqual(ambiguous_node['risk_level'], 'warning')
        self.assertIsNone(ambiguous_node['timeline_date'])
        self.assertEqual(outside_node['status'], 'trigger_outside_validity')
        self.assertIsNone(outside_node['timeline_date'])

    def test_formed_stage_fact_wins_and_timeline_merges_rule_projection_without_plan(self):
        line = _rule_line()
        rule = _billing_rule('milestone')
        event = _event('stage-formed', receivable_date=date(2026, 7, 10), due_date=date(2026, 7, 20))
        event['billing_rule'] = rule
        event['billing_period'] = '2026-07'

        result = build_revenue_timeline(
            [event],
            {'tracks': []},
            today=date(2026, 7, 1),
            contract_lines=[line],
            billing_rules=[rule],
            trigger_records=[
                {
                    'billing_rule_id': 601,
                    'trigger_event': 'acceptance',
                    'actual_trigger_date': date(2026, 7, 10),
                    'status': 'confirmed',
                }
            ],
            projection_end=date(2026, 8, 31),
        )

        self.assertEqual([node['kind'] for node in result['all_nodes']], ['formed'])


class RevenueRuleProjectionIntegrationTests(TestCase):
    def test_inactive_contract_line_is_not_projected(self):
        line = _rule_line(status='closed')
        nodes = build_rule_projection_nodes(
            [line], [_billing_rule()], today=date(2026, 7, 1), projection_end=date(2026, 8, 31)
        )
        self.assertEqual(nodes, [])

    def test_triggered_stage_node_exposes_trigger_fact_date_and_url(self):
        line = _rule_line()
        rule = _billing_rule('milestone', trigger_offset_days=2)
        record = SimpleNamespace(
            billing_rule_id=601,
            trigger_event='acceptance',
            actual_trigger_date=date(2026, 7, 10),
            status='confirmed',
            get_absolute_url=lambda: '/triggers/1/',
        )
        node = build_rule_projection_nodes(
            [line], [rule], today=date(2026, 7, 1), projection_end=date(2026, 8, 31), trigger_records=[record]
        )[0]
        self.assertEqual(node['timeline_date'], date(2026, 7, 12))
        self.assertEqual(node['actual_trigger_date'], date(2026, 7, 10))
        self.assertEqual(node['trigger_url'], '/triggers/1/')

    def test_rule_projection_supersedes_same_rule_and_date_plan_track(self):
        line = _rule_line()
        rule = _billing_rule()
        track = _track('duplicate', planned_date=date(2026, 7, 20), effective_due_date=date(2026, 7, 20), amount=100)
        track['billing_rule'] = rule
        result = build_revenue_timeline(
            [],
            {'tracks': [track]},
            today=date(2026, 7, 1),
            contract_lines=[line],
            billing_rules=[rule],
            projection_end=date(2026, 7, 31),
        )
        self.assertEqual(len(result['all_nodes']), 1)
        self.assertIsNone(result['all_nodes'][0]['plan'])
        self.assertEqual(result['all_nodes'][0]['node_key'], 'billing-rule:601:2026-07')


class RevenueRuleProjectionHorizonTests(TestCase):
    def test_default_horizon_projects_across_calendar_year_boundary(self):
        line = _rule_line(valid_from=date(2026, 12, 1))
        rule = _billing_rule(bill_generation_day=20)

        nodes = build_rule_projection_nodes([line], [rule], today=date(2026, 12, 15))

        self.assertIn('2027-01', [node['billing_period'] for node in nodes])
        january = next(node for node in nodes if node['billing_period'] == '2027-01')
        self.assertEqual(january['timeline_date'], date(2027, 1, 20))
