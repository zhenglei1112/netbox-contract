from datetime import date
from decimal import Decimal

from django.http import QueryDict
from django.template.loader import get_template
from django.test import SimpleTestCase
from django.urls import resolve, reverse

from netbox_contract import navigation, views


class RevenueReceivableOverviewViewTests(SimpleTestCase):
    def test_overview_has_dedicated_route_and_template(self):
        url = reverse('plugins:netbox_contract:revenuereceivable_overview')
        match = resolve(url)

        self.assertEqual(url, '/plugins/contracts/revenue/receivables/overview/')
        self.assertIs(match.func.view_class, views.RevenueReceivableOverviewView)
        self.assertEqual(
            views.RevenueReceivableOverviewView.template_name,
            'netbox_contract/revenue_receivable_overview.html',
        )
        get_template(views.RevenueReceivableOverviewView.template_name)

    def test_contract_list_uses_standard_list_template(self):
        self.assertEqual(views.RevenueContractListView.template_name, 'generic/object_list.html')

    def test_overview_menu_item_is_first_revenue_item(self):
        first_item = navigation.revenue_contract_items[0]

        self.assertEqual(first_item.link, 'plugins:netbox_contract:revenuereceivable_overview')
        self.assertEqual(str(first_item.link_text), '应收总览')
        self.assertEqual(first_item.permissions, ['netbox_contract.view_revenuecontract'])

    def test_overview_requires_revenue_contract_view_permission(self):
        view = views.RevenueReceivableOverviewView()

        self.assertEqual(view.get_required_permission(), 'netbox_contract.view_revenuecontract')
    def test_band_selection_defaults_to_overdue_and_marks_one_active(self):
        portfolio = {
            'bands': [
                {'key': 'overdue'},
                {'key': 'next_7_days'},
            ]
        }

        views._select_revenue_portfolio_band(portfolio, 'not-a-window')

        self.assertEqual(portfolio['selected_band']['key'], 'overdue')
        self.assertEqual([band['is_active'] for band in portfolio['bands']], [True, False])
    def test_band_links_preserve_active_filters(self):
        portfolio = {
            'bands': [
                {'key': 'overdue'},
                {'key': 'next_7_days'},
            ]
        }
        params = QueryDict('customer=7&business_owner=Alice&window=overdue')

        views._select_revenue_portfolio_band(portfolio, 'overdue', params)

        next_band = portfolio['bands'][1]
        linked_params = QueryDict(next_band['query_string'])
        self.assertEqual(linked_params['customer'], '7')
        self.assertEqual(linked_params['business_owner'], 'Alice')
        self.assertEqual(linked_params['window'], 'next_7_days')
        export_params = QueryDict(next_band['export_query_string'])
        self.assertEqual(export_params['export'], 'band')
    def test_month_selection_preserves_filters_and_marks_only_requested_month(self):
        portfolio = {
            'months': [
                {'key': '2026-01'},
                {'key': '2026-02'},
            ]
        }
        params = QueryDict('customer=7&window=overdue&month=2026-01')

        views._select_revenue_portfolio_month(portfolio, '2026-02', params)

        self.assertEqual(portfolio['selected_month']['key'], '2026-02')
        self.assertEqual([month['is_active'] for month in portfolio['months']], [False, True])
        linked_params = QueryDict(portfolio['months'][1]['query_string'])
        self.assertEqual(linked_params['customer'], '7')
        self.assertEqual(linked_params['window'], 'overdue')
        self.assertEqual(linked_params['month'], '2026-02')
        export_params = QueryDict(portfolio['months'][1]['export_query_string'])
        self.assertEqual(export_params['export'], 'month')

    def test_invalid_month_selection_does_not_open_month_details(self):
        portfolio = {'months': [{'key': '2026-01'}]}

        views._select_revenue_portfolio_month(portfolio, 'not-a-month')

        self.assertIsNone(portfolio['selected_month'])
        self.assertFalse(portfolio['months'][0]['is_active'])

    def test_csv_export_uses_uncapped_details_and_escapes_spreadsheet_formulas(self):
        detail = {
            'contract': '=Customer',
            'source': '=SUM(A1:A2)',
            'kind_label': '已形成应收',
            'due_date': date(2026, 1, 20),
            'schedule_status': '未来 5 天',
            'status_label': '待收款',
            'amount': Decimal('100.00'),
        }
        second = dict(detail, source='正常来源', amount=Decimal('200.00'))
        portfolio = {
            'selected_band': {
                'key': 'next_7_days',
                'details': [detail],
                'export_details': [detail, second],
            },
            'selected_month': None,
        }

        response = views._export_revenue_portfolio_csv(portfolio, 'band')
        content = response.content.decode('utf-8-sig')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(content.splitlines()), 3)
        self.assertIn("'=Customer", content)
        self.assertIn("'=SUM(A1:A2)", content)
        self.assertIn('正常来源', content)
        self.assertIn('receivables-band-next_7_days-', response['Content-Disposition'])

    def test_filter_controls_are_in_header_and_auto_submit(self):
        template = get_template(views.RevenueReceivableOverviewView.template_name)
        source = template.template.source

        self.assertIn('{% block controls %}', source)
        self.assertEqual(source.count('onchange="this.form.submit()"'), 5)
        self.assertNotIn('应用筛选', source)
        self.assertNotIn('筛选范围', source)
        self.assertIn('#monthly-details', source)
        self.assertIn('portfolio.selected_month.details', source)
        self.assertIn('portfolio.selected_band.export_query_string', source)
        self.assertIn('portfolio.selected_month.export_query_string', source)
