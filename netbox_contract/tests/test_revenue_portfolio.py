from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase

from netbox_contract.services.revenue_portfolio import build_revenue_portfolio


def _event(*, contract_id, due_date, net, mapped, received):
    net = Decimal(str(net))
    mapped = Decimal(str(mapped))
    received = Decimal(str(received))
    return {
        'is_confirmed': True,
        'bill': SimpleNamespace(contract_id=contract_id),
        'due_date': due_date,
        'net_amount': net,
        'mapped_amount': mapped,
        'receipted_amount': received,
        'unreceived_amount': net - received,
    }


def _track(*, contract_id, amount, planned_date=None, trigger_type='fixed_date', events=None, status='effective'):
    version = SimpleNamespace(trigger_type=trigger_type, planned_date=planned_date)
    return {
        'plan': SimpleNamespace(contract_id=contract_id, status=status),
        'current_version': version,
        'current_amount': Decimal(str(amount)),
        'effective_due_date': planned_date,
        'events': list(events or ()),
    }


class RevenuePortfolioTests(TestCase):
    def setUp(self):
        self.today = date(2026, 1, 15)
        self.events = [
            _event(contract_id=1, due_date=date(2026, 1, 10), net=100, mapped=70, received=20),
            _event(contract_id=1, due_date=date(2026, 1, 20), net=100, mapped=75, received=25),
        ]
        self.tracks = {
            'tracks': [
                _track(contract_id=2, amount=200, planned_date=date(2026, 1, 30)),
                _track(contract_id=3, amount=300, trigger_type='trigger_offset'),
                _track(
                    contract_id=4,
                    amount=400,
                    planned_date=date(2026, 2, 5),
                    trigger_type='estimated_date',
                ),
                _track(
                    contract_id=5,
                    amount=500,
                    planned_date=date(2026, 2, 20),
                    events=[{'event_key': 'already-realized'}],
                ),
            ]
        }

    def test_time_bands_are_non_overlapping_and_do_not_repeat_realized_plans(self):
        result = build_revenue_portfolio(self.events, self.tracks, today=self.today)
        bands = {band['key']: band for band in result['bands']}

        self.assertEqual(bands['overdue']['amount'], Decimal('80'))
        self.assertEqual(bands['next_7_days']['amount'], Decimal('75'))
        self.assertEqual(bands['days_8_30']['amount'], Decimal('600'))
        self.assertEqual(bands['pending_trigger']['amount'], Decimal('300'))
        self.assertEqual(result['totals']['future_planned'], Decimal('600'))
        self.assertEqual(result['totals']['contract_count'], 4)

    def test_pending_trigger_is_not_assigned_an_invented_month(self):
        result = build_revenue_portfolio(self.events, self.tracks, today=self.today)

        self.assertEqual(result['totals']['pending_trigger'], Decimal('300'))
        self.assertNotIn(Decimal('300'), [month['total'] for month in result['months']])

    def test_month_segments_reconcile_to_month_total(self):
        result = build_revenue_portfolio(self.events, self.tracks, today=self.today)
        january = result['months'][0]
        february = result['months'][1]

        self.assertEqual(january['received'], Decimal('45'))
        self.assertEqual(january['invoiced_unreceived'], Decimal('50'))
        self.assertEqual(january['uninvoiced'], Decimal('225'))
        self.assertEqual(january['overdue'], Decimal('80'))
        self.assertEqual(january['total'], Decimal('400'))
        self.assertEqual(sum(segment['amount'] for segment in january['segments']), january['total'])
        self.assertEqual(january['detail_count'], 3)
        self.assertEqual(sum(detail['amount'] for detail in january['details']), january['total'])
        self.assertEqual(
            sum(detail['received_amount'] for detail in january['details']),
            january['received'],
        )
        self.assertEqual(february['uncertain'], Decimal('400'))
        self.assertEqual(february['details'][0]['kind'], 'planned')
        self.assertTrue(february['details'][0]['uncertain'])

    def test_closed_or_canceled_plans_are_excluded(self):
        tracks = {
            'tracks': [
                _track(contract_id=1, amount=100, planned_date=date(2026, 1, 20), status='closed'),
                _track(contract_id=2, amount=200, planned_date=date(2026, 1, 20), status='canceled'),
            ]
        }

        result = build_revenue_portfolio([], tracks, today=self.today)

        self.assertFalse(result['has_data'])
        self.assertEqual(result['totals']['future_planned'], Decimal('0'))

    def test_band_details_explain_formed_and_pending_amounts(self):
        result = build_revenue_portfolio(self.events, self.tracks, today=self.today)
        bands = {band['key']: band for band in result['bands']}

        overdue_detail = bands['overdue']['details'][0]
        pending_detail = bands['pending_trigger']['details'][0]
        self.assertEqual(overdue_detail['kind'], 'formed')
        self.assertEqual(overdue_detail['amount'], Decimal('80'))
        self.assertEqual(overdue_detail['schedule_status'], '逾期 5 天')
        self.assertEqual(pending_detail['kind'], 'planned')
        self.assertIsNone(pending_detail['due_date'])
        self.assertEqual(pending_detail['schedule_status'], '待条件触发')

    def test_band_details_are_capped_for_page_safety(self):
        result = build_revenue_portfolio(
            self.events,
            self.tracks,
            today=self.today,
            detail_limit=1,
        )
        band = next(item for item in result['bands'] if item['key'] == 'days_8_30')

        self.assertEqual(band['detail_count'], 2)
        self.assertTrue(band['details_truncated'])
        self.assertEqual(len(band['details']), 1)

        january = result['months'][0]
        self.assertEqual(january['detail_count'], 3)
        self.assertTrue(january['details_truncated'])
        self.assertEqual(len(january['details']), 1)
