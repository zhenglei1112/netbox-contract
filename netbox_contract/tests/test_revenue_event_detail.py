from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.http import QueryDict
from django.test import SimpleTestCase
from django.urls import resolve, reverse

from netbox_contract import views


class DisplayBill(SimpleNamespace):
    def get_confirm_status_display(self):
        return self.confirm_status


def _row(*, project_id, period, status, risk, amount, order_id=''):
    project = SimpleNamespace(pk=project_id)
    project.__str__ = lambda self: f'Project {project_id}'
    contract_line = SimpleNamespace(
        project=project,
        revenue_order=None,
        order_id=order_id,
    )
    bill = DisplayBill(confirm_status='confirmed')
    amount = Decimal(str(amount))
    return {
        'contract_line': contract_line,
        'bill': bill,
        'billing_period': period,
        'is_confirmed': True,
        'confirm_status': 'confirmed',
        'collection_status': status,
        'collection_status_label': status,
        'risk_level': risk,
        'net_amount': amount,
        'mapped_amount': amount / 2,
        'receipted_amount': Decimal('0'),
        'unreceived_amount': amount,
    }


class RevenueContractEventDetailTests(SimpleTestCase):
    def setUp(self):
        self.rows = [
            _row(
                project_id=1,
                period='2026-01',
                status='overdue',
                risk='danger',
                amount='100',
                order_id='ORD-001',
            ),
            _row(
                project_id=2,
                period='2026-02',
                status='paid',
                risk='success',
                amount='200',
            ),
        ]

    def test_filters_rows_and_recalculates_visible_totals(self):
        params = QueryDict('event_project=1&event_period=2026-01&event_status=overdue&event_risk=danger')

        detail = views._build_revenue_contract_event_detail(self.rows, params)

        self.assertEqual(detail['filtered_count'], 1)
        self.assertEqual(detail['total_count'], 2)
        self.assertEqual(detail['totals']['receivable'], Decimal('100'))
        self.assertEqual(detail['totals']['unreceived'], Decimal('100'))
        self.assertEqual(detail['rows'][0]['detail_order_key'], 'legacy:ORD-001')
        linked = QueryDict(detail['query_string'])
        self.assertEqual(linked['event_project'], '1')
        self.assertEqual(linked['event_status'], 'overdue')

    def test_contract_event_export_has_dedicated_permission_protected_route(self):
        url = reverse(
            'plugins:netbox_contract:revenuecontract_event_export',
            kwargs={'pk': 7},
        )
        match = resolve(url)
        view = views.RevenueContractEventExportView()

        self.assertEqual(
            url,
            '/plugins/contracts/revenue/contracts/7/events/export/',
        )
        self.assertIs(match.func.view_class, views.RevenueContractEventExportView)
        self.assertEqual(
            view.get_required_permission(),
            'netbox_contract.view_revenuecontract',
        )

    def test_template_uses_auto_apply_filters_and_filtered_rows(self):
        template_path = Path(__file__).parents[1] / 'templates' / 'netbox_contract' / 'revenue_contract.html'
        source = template_path.read_text(encoding='utf-8')

        self.assertIn('class="rev-event-filter-bar"', source)
        self.assertIn('{% for row in detail.rows %}', source)
        self.assertIn('{% for row in ws.chain_rows %}', source)
        self.assertIn('revenuecontract_event_export', source)
        self.assertNotIn('应用筛选', source)
        for field in (
            'event_project',
            'event_order',
            'event_period',
            'event_status',
            'event_risk',
        ):
            self.assertIn(f'name="{field}"', source)

    def test_template_renders_unified_timeline_with_direct_filters_and_drilldown(self):
        template_path = Path(__file__).parents[1] / 'templates' / 'netbox_contract' / 'revenue_contract.html'
        source = template_path.read_text(encoding='utf-8')

        self.assertIn('timeline=revenue_timeline', source)
        self.assertIn('id="receivable-timeline"', source)
        self.assertIn('{% for item in timeline.filters %}', source)
        self.assertIn('item.query_string', source)
        self.assertIn('data-bs-target="#{{ node.event_dom_id }}"', source)
        self.assertIn("node.date_certainty == 'pending_trigger'", source)
