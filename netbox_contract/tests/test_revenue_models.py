import importlib

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django import forms as django_forms
from django.apps import apps as django_apps
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase, TestCase
from rest_framework.exceptions import ValidationError as DRFValidationError

from netbox_contract import filtersets, forms, views
from netbox_contract.api import serializers as api_serializers

from netbox_contract.models import (
    RevenueBillingRule,
    RevenueBillingSegment,
    RevenueContract,
    RevenueContractStatusChoices,
    RevenueContractLine,
    RevenueContractProject,
    RevenueContractVersion,
    RevenueCustomer,
    RevenueInvoice,
    RevenueInvoiceLine,
    RevenueInvoiceMapping,
    RevenueOrder,
    RevenueProject,
    RevenueReceivablePlan,
    RevenueReceivablePlanVersion,
    RevenueTriggerRecord,
    RevenueAdjustmentRecord,
    RevenueReceivableBill,
    RevenueReceivableLine,
    RevenueReceipt,
    RevenueReceiptAllocation,
    RevenueSyncLog,
)


class RevenueFormLabelLocalizationTestCase(SimpleTestCase):
    expected_business_labels = {
        (RevenueBillingRule, 'trigger_offset_days'): '触发后天数',
        (RevenueTriggerRecord, 'billing_rule'): '计费规则',
        (RevenueReceivableLine, 'receivable_plan'): '应收计划',
        (RevenueReceivableLine, 'receivable_date'): '应收日期',
        (RevenueReceivableLine, 'due_date'): '到期日期',
        (RevenueReceiptAllocation, 'receipt'): '回款',
        (RevenueReceiptAllocation, 'receivable_line'): '应收明细',
    }
    expected_revenue_models = {
        RevenueCustomer,
        RevenueProject,
        RevenueContract,
        RevenueContractProject,
        RevenueOrder,
        RevenueContractVersion,
        RevenueContractLine,
        RevenueBillingRule,
        RevenueBillingSegment,
        RevenueReceivablePlan,
        RevenueReceivablePlanVersion,
        RevenueTriggerRecord,
        RevenueAdjustmentRecord,
        RevenueReceivableBill,
        RevenueReceivableLine,
        RevenueInvoice,
        RevenueInvoiceLine,
        RevenueInvoiceMapping,
        RevenueReceipt,
        RevenueReceiptAllocation,
        RevenueSyncLog,
    }

    def test_revenue_contract_status_colors_follow_choice_set(self):
        contract = RevenueContract()

        for status, label, expected_color in RevenueContractStatusChoices.CHOICES:
            with self.subTest(status=status, label=label):
                contract.status = status
                self.assertEqual(contract.get_status_color(), expected_color)

        contract.status = 'effective'
        self.assertEqual(contract.get_status_color(), 'green')

    def test_business_and_changelog_labels_are_localized(self):
        self.assertSetEqual(
            set(forms._REVENUE_FORM_MODELS),
            self.expected_revenue_models,
        )

        for (model, field_name), expected_label in self.expected_business_labels.items():
            with self.subTest(model=model.__name__, field=field_name):
                self.assertEqual(
                    str(model._meta.get_field(field_name).verbose_name),
                    expected_label,
                )
                form_class = getattr(forms, f'{model.__name__}Form')
                self.assertEqual(
                    str(form_class.base_fields[field_name].label),
                    expected_label,
                )

        for model in forms._REVENUE_FORM_MODELS:
            with self.subTest(model=model.__name__):
                form_class = getattr(forms, f'{model.__name__}Form')
                self.assertTrue(issubclass(form_class, forms.RevenueModelForm))
                field_names = tuple(form_class._meta.fields)
                self.assertEqual(field_names[-1], 'tags')
                self.assertNotIn('custom_field_data', field_names)

        def fake_super_init(form_self, *args, **kwargs):
            form_self.fields = {
                'changelog_message': django_forms.CharField(
                    label='Changelog message'
                )
            }

        with patch.object(forms.NetBoxModelForm, '__init__', fake_super_init):
            form = forms.RevenueModelForm()

        self.assertEqual(
            str(form.fields['changelog_message'].label),
            '变更说明',
        )

        def fake_super_init_without_changelog(form_self, *args, **kwargs):
            form_self.fields = {}

        with patch.object(
            forms.NetBoxModelForm,
            '__init__',
            fake_super_init_without_changelog,
        ):
            forms.RevenueModelForm()

        self.assertFalse(issubclass(forms.ContractForm, forms.RevenueModelForm))


class RevenueModelValidationTestCase(TestCase):
    def setUp(self):
        self.customer = RevenueCustomer.objects.create(
            name='客户A',
            usci='913100000000000001',
            customer_type='enterprise',
            sales_owner='张三',
            business_owner='李四',
        )
        self.project = RevenueProject.objects.create(
            name='项目A',
            customer=self.customer,
            project_manager='王五',
            sales_owner='张三',
            business_owner='李四',
            project_type='fiber',
            status='executing',
        )
        self.contract = RevenueContract.objects.create(
            contract_code='RC-001',
            name='收入合同A',
            customer=self.customer,
            contract_type='recurring',
            our_party='本公司',
            customer_party='客户A',
            sign_date=date(2026, 1, 1),
            start_date=date(2026, 1, 1),
            total_amount=Decimal('1000.00'),
            is_framework=False,
            status='effective',
            sales_owner='张三',
            business_owner='李四',
            source_system='REVENUE_SYS',
        )
        self.version = RevenueContractVersion.objects.create(
            contract=self.contract,
            version_code='V1.0',
            change_type='original',
            start_date=date(2026, 1, 1),
            status='effective',
        )
        self.contract_line = RevenueContractLine.objects.create(
            contract=self.contract,
            contract_version=self.version,
            project=self.project,
            product_category='fiber',
            charge_item='专线月租',
            unit_price=Decimal('100.00'),
            quantity=Decimal('1.00'),
            unit='月',
            valid_from=date(2026, 1, 1),
            status='active',
        )
        self.billing_rule = RevenueBillingRule.objects.create(
            contract_line=self.contract_line,
            contract_version=self.version,
            rule_type='recurring',
            billing_cycle='month',
            billing_direction='postpay',
            bill_generation_day=25,
            proration_rule='actual_days',
            rounding_precision='2',
            status='effective',
        )
        self.segment = RevenueBillingSegment.objects.create(
            contract_line=self.contract_line,
            billing_rule=self.billing_rule,
            segment_start=date(2026, 1, 1),
            segment_end=date(2026, 1, 31),
            unit_price=Decimal('100.00'),
            quantity=Decimal('1.00'),
            amount=Decimal('100.00'),
            change_trigger='normal',
            billing_rule_snapshot={},
        )
        self.bill = RevenueReceivableBill.objects.create(
            bill_code='RB-001',
            customer=self.customer,
            contract=self.contract,
            project=self.project,
            billing_period='2026-01',
            receivable_date=date(2026, 1, 25),
            due_date=date(2026, 2, 25),
            amount=Decimal('100.00'),
            adjusted_amount=Decimal('0.00'),
            net_amount=Decimal('100.00'),
            confirm_status='confirmed',
            invoice_status='uninvoiced',
            receipt_status='unpaid',
            ageing_status='not_due',
            risk_status='normal',
        )
        self.receivable_line = RevenueReceivableLine.objects.create(
            bill=self.bill,
            contract_line=self.contract_line,
            billing_rule=self.billing_rule,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            amount=Decimal('100.00'),
            adjusted_amount=Decimal('0.00'),
            net_amount=Decimal('100.00'),
            risk_status='normal',
            idempotent_key='line-2026-01',
        )
        self.invoice = RevenueInvoice.objects.create(
            invoice_code='INV-001',
            customer=self.customer,
            invoice_type='electronic',
            invoice_date=date(2026, 1, 26),
            amount=Decimal('100.00'),
            source_system='REVENUE_SYS',
        )
        self.invoice_line = RevenueInvoiceLine.objects.create(
            invoice=self.invoice,
            line_no=1,
            item_name='专线月租',
            amount=Decimal('100.00'),
        )

    def test_revenue_categorical_fields_are_model_choices(self):
        expected = {
            RevenueBillingRule: {
                'billing_cycle': {'month', 'quarter', 'year'},
                'billing_direction': {'postpay', 'prepay'},
                'proration_rule': {'actual_days', 'full_month', 'none'},
            },
            RevenueBillingSegment: {
                'change_trigger': {'normal', 'contract_change', 'price_change'},
            },
            RevenueContract: {
                'source_system': {'SAMPLE_DATA', 'REVENUE_SYS', 'BANK_FLOW'},
            },
            RevenueInvoice: {
                'source_system': {'SAMPLE_DATA', 'REVENUE_SYS', 'BANK_FLOW'},
            },
            RevenueReceipt: {
                'source_system': {'SAMPLE_DATA', 'REVENUE_SYS', 'BANK_FLOW'},
            },
            RevenueSyncLog: {
                'source_system': {'SAMPLE_DATA', 'REVENUE_SYS', 'BANK_FLOW'},
                'entity_type': {'RevenueContract', 'RevenueInvoice', 'RevenueReceipt'},
            },
        }
        for model, field_values in expected.items():
            for field_name, values in field_values.items():
                field = model._meta.get_field(field_name)
                actual_values = {value for value, _label in field.choices}
                self.assertTrue(values.issubset(actual_values))

    def test_invoice_requires_line_sum_to_match_header_amount(self):
        RevenueInvoiceLine.objects.create(
            invoice=self.invoice,
            line_no=2,
            item_name='补充行',
            amount=Decimal('1.00'),
        )

        with self.assertRaises(ValidationError):
            self.invoice.full_clean()

    def test_invoice_mapping_rejects_amount_over_receivable_line_limit(self):
        mapping = RevenueInvoiceMapping(
            receivable_line=self.receivable_line,
            invoice_line=self.invoice_line,
            mapped_amount=Decimal('101.00'),
            operator='张三',
            approval_batch_no='BATCH-001',
        )

        with self.assertRaises(ValidationError):
            mapping.full_clean()

    def test_invoice_mapping_rejects_amount_over_invoice_line_limit(self):
        RevenueInvoiceMapping.objects.create(
            receivable_line=self.receivable_line,
            invoice_line=self.invoice_line,
            mapped_amount=Decimal('60.00'),
            operator='张三',
            approval_batch_no='BATCH-001',
        )
        other_bill = RevenueReceivableBill.objects.create(
            bill_code='RB-002',
            customer=self.customer,
            contract=self.contract,
            project=self.project,
            billing_period='2026-02',
            receivable_date=date(2026, 2, 25),
            due_date=date(2026, 3, 25),
            amount=Decimal('100.00'),
            adjusted_amount=Decimal('0.00'),
            net_amount=Decimal('100.00'),
            confirm_status='confirmed',
            invoice_status='uninvoiced',
            receipt_status='unpaid',
            ageing_status='not_due',
            risk_status='normal',
        )
        other_line = RevenueReceivableLine.objects.create(
            bill=other_bill,
            contract_line=self.contract_line,
            billing_rule=self.billing_rule,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
            amount=Decimal('100.00'),
            adjusted_amount=Decimal('0.00'),
            net_amount=Decimal('100.00'),
            risk_status='normal',
            idempotent_key='line-2026-02',
        )
        mapping = RevenueInvoiceMapping(
            receivable_line=other_line,
            invoice_line=self.invoice_line,
            mapped_amount=Decimal('50.00'),
            operator='张三',
            approval_batch_no='BATCH-002',
        )

        with self.assertRaises(ValidationError):
            mapping.full_clean()

    def test_receipt_allocation_rejects_amount_over_invoice_mapping_limit(self):
        mapping = RevenueInvoiceMapping.objects.create(
            receivable_line=self.receivable_line,
            invoice_line=self.invoice_line,
            mapped_amount=Decimal('80.00'),
            operator='张三',
            approval_batch_no='BATCH-001',
        )
        receipt = RevenueReceipt.objects.create(
            customer=self.customer,
            receipt_date=date(2026, 1, 30),
            amount=Decimal('100.00'),
            bank_flow_no='BANK-001',
            payer_name='客户A',
            source_system='BANK_FLOW',
        )
        allocation = RevenueReceiptAllocation(
            receipt=receipt,
            receivable_line=self.receivable_line,
            invoice_mapping=mapping,
            allocated_amount=Decimal('81.00'),
            allocation_type='direct_receipt',
            operator='张三',
            approval_batch_no='BATCH-003',
        )

        with self.assertRaises(ValidationError):
            allocation.full_clean()

    def test_receipt_allocation_requires_receivable_line(self):
        receipt = RevenueReceipt.objects.create(
            customer=self.customer,
            receipt_date=date(2026, 1, 30),
            amount=Decimal('100.00'),
            bank_flow_no='BANK-002',
            payer_name='\u5ba2\u6237A',
            source_system='BANK_FLOW',
        )
        allocation = RevenueReceiptAllocation(
            receipt=receipt,
            allocated_amount=Decimal('20.00'),
            allocation_type='direct_receipt',
            operator='\u5f20\u4e09',
            approval_batch_no='BATCH-004',
        )

        with self.assertRaises(ValidationError):
            allocation.full_clean()

    def test_receipt_allocation_rejects_amount_over_receivable_line_limit(self):
        receipt = RevenueReceipt.objects.create(
            customer=self.customer,
            receipt_date=date(2026, 1, 30),
            amount=Decimal('200.00'),
            bank_flow_no='BANK-004',
            payer_name='payer-a',
            source_system='BANK_FLOW',
        )
        RevenueReceiptAllocation.objects.create(
            receipt=receipt,
            receivable_line=self.receivable_line,
            allocated_amount=Decimal('60.00'),
            allocation_type='direct_receipt',
            operator='operator',
            approval_batch_no='BATCH-005',
        )
        allocation = RevenueReceiptAllocation(
            receipt=receipt,
            receivable_line=self.receivable_line,
            allocated_amount=Decimal('41.00'),
            allocation_type='direct_receipt',
            operator='operator',
            approval_batch_no='BATCH-006',
        )

        with self.assertRaises(ValidationError):
            allocation.full_clean()

    def test_receipt_allocation_rejects_amount_over_receipt_limit(self):
        receipt = RevenueReceipt.objects.create(
            customer=self.customer,
            receipt_date=date(2026, 1, 30),
            amount=Decimal('50.00'),
            bank_flow_no='BANK-005',
            payer_name='payer-a',
            source_system='BANK_FLOW',
        )
        allocation = RevenueReceiptAllocation(
            receipt=receipt,
            receivable_line=self.receivable_line,
            allocated_amount=Decimal('51.00'),
            allocation_type='direct_receipt',
            operator='operator',
            approval_batch_no='BATCH-008',
        )

        with self.assertRaises(ValidationError):
            allocation.full_clean()

    def test_receipt_allocation_rejects_non_positive_amount(self):
        receipt = RevenueReceipt.objects.create(
            customer=self.customer,
            receipt_date=date(2026, 1, 30),
            amount=Decimal('50.00'),
            bank_flow_no='BANK-006',
            payer_name='payer-a',
            source_system='BANK_FLOW',
        )
        allocation = RevenueReceiptAllocation(
            receipt=receipt,
            receivable_line=self.receivable_line,
            allocated_amount=Decimal('-1.00'),
            allocation_type='direct_receipt',
            operator='operator',
            approval_batch_no='BATCH-009',
        )

        with self.assertRaises(ValidationError):
            allocation.full_clean()

    def test_receipt_totals_recalculate_when_allocation_is_saved_and_deleted(self):
        receipt = RevenueReceipt.objects.create(
            customer=self.customer,
            receipt_date=date(2026, 1, 30),
            amount=Decimal('100.00'),
            unallocated_amount=Decimal('100.00'),
            bank_flow_no='BANK-003',
            payer_name='客户A',
            source_system='BANK_FLOW',
        )
        allocation = RevenueReceiptAllocation.objects.create(
            receipt=receipt,
            receivable_line=self.receivable_line,
            allocated_amount=Decimal('40.00'),
            allocation_type='direct_receipt',
            operator='张三',
            approval_batch_no='BATCH-007',
        )

        receipt.refresh_from_db()
        self.assertEqual(receipt.allocated_total, Decimal('40.00'))
        self.assertEqual(receipt.unallocated_amount, Decimal('60.00'))
        self.assertEqual(receipt.status, 'partially_allocated')

        allocation.delete()
        receipt.refresh_from_db()
        self.assertEqual(receipt.allocated_total, Decimal('0.00'))
        self.assertEqual(receipt.unallocated_amount, Decimal('100.00'))
        self.assertEqual(receipt.status, 'unmatched')

    def test_contract_context_builds_structured_workspace(self):
        mapping = RevenueInvoiceMapping.objects.create(
            receivable_line=self.receivable_line,
            invoice_line=self.invoice_line,
            mapped_amount=Decimal('80.00'),
            operator='operator',
            approval_batch_no='BATCH-011',
        )
        receipt = RevenueReceipt.objects.create(
            customer=self.customer,
            receipt_date=date(2026, 1, 30),
            amount=Decimal('80.00'),
            bank_flow_no='BANK-011',
            payer_name='payer',
            source_system='BANK_FLOW',
        )
        RevenueReceiptAllocation.objects.create(
            receipt=receipt,
            receivable_line=self.receivable_line,
            invoice_mapping=mapping,
            allocated_amount=Decimal('80.00'),
            allocation_type='direct_receipt',
            operator='operator',
            approval_batch_no='BATCH-012',
        )

        self.contract.total_amount = Decimal('720000.00')
        self.contract.save(update_fields=['total_amount'])
        self.bill.amount = Decimal('225000.00')
        self.bill.net_amount = Decimal('225000.00')
        self.bill.invoiced_amount = Decimal('225000.00')
        self.bill.receipted_amount = Decimal('200000.00')
        self.bill.save(update_fields=['amount', 'net_amount', 'invoiced_amount', 'receipted_amount'])

        request = RequestFactory().get('/')
        context = views._revenue_contract_context(request, self.contract)

        workspace = context['revenue_contract_workspace']
        self.assertEqual(workspace['overview']['receivable_total'], Decimal('100.00'))
        self.assertEqual(workspace['overview']['invoiced_total'], Decimal('80.00'))
        self.assertEqual(workspace['overview']['receipt_total'], Decimal('80.00'))
        self.assertEqual(workspace['overview']['invoice_rate'], '0.0%')
        self.assertEqual(workspace['overview']['receipt_rate'], '80.0%')
        self.assertEqual(workspace['overview']['overdue_total'], Decimal('20.00'))
        self.assertTrue(workspace['overview']['reconciliation']['has_mismatch'])
        self.assertFalse(workspace['plan_tracks']['has_plans'])
        self.assertEqual(
            workspace['overview']['reconciliation']['cached_receivable_total'],
            Decimal('225000.00'),
        )
        self.assertEqual(
            workspace['overview']['reconciliation']['calculated_receivable_total'],
            Decimal('100.00'),
        )
        self.assertEqual(len(workspace['chain_rows']), 1)
        self.assertEqual(workspace['chain_rows'][0]['receipted_amount'], Decimal('80.00'))
        self.assertEqual(workspace['chain_rows'][0]['event_dom_id'], f'receivable-event-{self.receivable_line.pk}')
        self.assertEqual(workspace['chain_rows'][0]['collection_status'], 'overdue')
        self.assertEqual(len(workspace['contract_line_groups']), 1)
        self.assertEqual(len(workspace['receivable_bill_groups']), 1)
        self.assertEqual(len(workspace['invoice_groups']), 1)
        self.assertEqual(len(workspace['receipt_groups']), 1)

    def test_receivable_plan_tracks_original_current_actual_and_adjustment(self):
        plan = RevenueReceivablePlan.objects.create(
            plan_code='PLAN-001',
            contract=self.contract,
            contract_line=self.contract_line,
            billing_rule=self.billing_rule,
            charge_item='专线月租',
            status='effective',
        )
        self.receivable_line.receivable_plan = plan
        self.receivable_line.save(update_fields=['receivable_plan'])
        original = RevenueReceivablePlanVersion.objects.create(
            plan=plan,
            version_no=1,
            trigger_type='fixed_date',
            planned_date=date(2026, 2, 1),
            planned_amount=Decimal('100.00'),
            effective_from=date(2026, 1, 1),
            is_current=False,
        )
        current = RevenueReceivablePlanVersion.objects.create(
            plan=plan,
            version_no=2,
            trigger_type='trigger_offset',
            trigger_event='acceptance',
            offset_days=30,
            planned_amount=Decimal('120.00'),
            effective_from=date(2026, 1, 10),
            change_reason='验收节点延期',
            is_current=True,
        )
        RevenueTriggerRecord.objects.create(
            plan=plan,
            plan_version=current,
            trigger_event='acceptance',
            actual_trigger_date=date(2026, 1, 20),
            status='confirmed',
            source_system='REVENUE_SYS',
        )
        adjustment = RevenueAdjustmentRecord.objects.create(
            plan=plan,
            receivable_line=self.receivable_line,
            adjustment_type='sla_deduction',
            adjustment_date=date(2026, 2, 1),
            amount=Decimal('-10.00'),
            reason='SLA未达标扣款',
            source_system='REVENUE_SYS',
            status='confirmed',
        )

        context = views._revenue_contract_context(RequestFactory().get('/'), self.contract)
        plan_tracks = context['revenue_contract_workspace']['plan_tracks']
        track = plan_tracks['tracks'][0]

        self.assertTrue(plan_tracks['has_plans'])
        self.assertEqual(track['original_version'], original)
        self.assertEqual(track['current_version'], current)
        self.assertEqual(track['original_amount'], Decimal('100.00'))
        self.assertEqual(track['current_amount'], Decimal('120.00'))
        self.assertEqual(track['actual_trigger_date'], date(2026, 1, 20))
        self.assertEqual(track['calculated_due_date'], date(2026, 2, 19))
        self.assertEqual(track['receivable_total'], Decimal('100.00'))
        self.assertEqual(track['confirmed_adjustment_total'], Decimal('-10.00'))
        self.assertEqual(track['amount_variance'], Decimal('-20.00'))
        self.assertEqual(track['adjustments'], [adjustment])
        self.assertIn('验收节点延期', track['variance_reasons'])
        self.assertIn('SLA未达标扣款', track['variance_reasons'])
        self.assertEqual(context['revenue_contract_workspace']['chain_rows'][0]['adjustment_records'], [adjustment])

        detail_request = RequestFactory().get('/')
        detail_request.user = AnonymousUser()
        plan_context = views._revenue_receivable_plan_context(detail_request, plan)
        self.assertEqual(
            [panel['title'] for panel in plan_context['revenue_related_panels']],
            ['\u8ba1\u5212\u7248\u672c', '\u89e6\u53d1\u8bb0\u5f55', '\u8c03\u6574\u8bb0\u5f55', '\u5173\u8054\u5e94\u6536\u660e\u7ec6'],
        )
        self.assertEqual(plan_context['revenue_summary_cards'][0]['value'], Decimal('120.00'))
        self.assertEqual(plan_context['revenue_summary_cards'][1]['value'], Decimal('100.00'))
        self.assertEqual(plan_context['revenue_summary_cards'][2]['value'], Decimal('-10.00'))
        version_context = views._revenue_receivable_plan_version_context(detail_request, current)
        self.assertEqual(version_context['revenue_related_panels'][0]['count'], 1)
        line_context = views._revenue_receivable_line_context(detail_request, self.receivable_line)
        self.assertIn('\u8c03\u6574\u8bb0\u5f55', [panel['title'] for panel in line_context['revenue_related_panels']])

    def test_plan_tracks_do_not_duplicate_unassigned_events_across_plans(self):
        first_plan = RevenueReceivablePlan.objects.create(
            plan_code='PLAN-FIRST',
            contract=self.contract,
            contract_line=self.contract_line,
            billing_rule=self.billing_rule,
            charge_item='主计划',
            status='effective',
        )
        RevenueReceivablePlan.objects.create(
            plan_code='PLAN-SECOND',
            contract=self.contract,
            contract_line=self.contract_line,
            billing_rule=self.billing_rule,
            charge_item='第二计划',
            status='effective',
        )

        workspace = views._revenue_contract_context(
            RequestFactory().get('/'), self.contract
        )['revenue_contract_workspace']
        tracks = workspace['plan_tracks']
        self.assertEqual([track['receivable_total'] for track in tracks['tracks']], [Decimal('0'), Decimal('0')])
        self.assertEqual(tracks['ambiguous_unassigned_event_count'], 1)

        self.receivable_line.receivable_plan = first_plan
        self.receivable_line.full_clean()
        self.receivable_line.save(update_fields=['receivable_plan'])
        workspace = views._revenue_contract_context(
            RequestFactory().get('/'), self.contract
        )['revenue_contract_workspace']
        tracks_by_code = {
            track['plan'].plan_code: track for track in workspace['plan_tracks']['tracks']
        }
        self.assertEqual(tracks_by_code['PLAN-FIRST']['receivable_total'], Decimal('100.00'))
        self.assertEqual(tracks_by_code['PLAN-SECOND']['receivable_total'], Decimal('0'))
        self.assertEqual(workspace['plan_tracks']['ambiguous_unassigned_event_count'], 0)
    def test_trigger_offset_plan_version_rejects_a_fabricated_date(self):
        plan = RevenueReceivablePlan.objects.create(
            plan_code='PLAN-VALIDATION',
            contract=self.contract,
            contract_line=self.contract_line,
            billing_rule=self.billing_rule,
            charge_item='专线月租',
            status='effective',
        )
        version = RevenueReceivablePlanVersion(
            plan=plan,
            version_no=1,
            trigger_type='trigger_offset',
            trigger_event='acceptance',
            offset_days=30,
            planned_date=date(2026, 2, 1),
            planned_amount=Decimal('100.00'),
            effective_from=date(2026, 1, 1),
            is_current=True,
        )

        with self.assertRaises(ValidationError):
            version.full_clean()
    def test_contract_context_excludes_unconfirmed_receivables_from_execution_totals(self):
        self.bill.confirm_status = 'draft'
        self.bill.save(update_fields=['confirm_status'])

        request = RequestFactory().get('/')
        context = views._revenue_contract_context(request, self.contract)

        overview = context['revenue_contract_workspace']['overview']
        self.assertEqual(overview['receivable_total'], Decimal('0'))
        self.assertEqual(overview['invoiced_total'], Decimal('0'))
        self.assertEqual(overview['receipt_total'], Decimal('0'))
        self.assertEqual(overview['overdue_total'], Decimal('0'))

    def test_calendar_does_not_mix_paid_overdue_and_unpaid_future_bills(self):
        future_bill = RevenueReceivableBill.objects.create(
            bill_code='RB-FUTURE',
            customer=self.customer,
            contract=self.contract,
            project=self.project,
            billing_period='2026-01',
            receivable_date=date(2026, 2, 1),
            due_date=date(2026, 4, 1),
            amount=Decimal('50.00'),
            adjusted_amount=Decimal('0.00'),
            net_amount=Decimal('50.00'),
            confirm_status='confirmed',
            invoice_status='uninvoiced',
            receipt_status='unpaid',
            ageing_status='not_due',
            risk_status='normal',
        )
        RevenueReceivableLine.objects.create(
            bill=future_bill,
            contract_line=self.contract_line,
            billing_rule=self.billing_rule,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
            amount=Decimal('50.00'),
            adjusted_amount=Decimal('0.00'),
            net_amount=Decimal('50.00'),
            risk_status='normal',
            idempotent_key='line-future',
        )
        self.bill.due_date = date(2026, 1, 15)
        self.bill.save(update_fields=['due_date'])

        rows = [
            {
                'billing_period': '2026-01',
                'contract_line': self.contract_line,
                'net_amount': Decimal('100.00'),
                'mapped_amount': Decimal('100.00'),
                'receipted_amount': Decimal('100.00'),
                'unreceived_amount': Decimal('0.00'),
                'overdue_amount': Decimal('0.00'),
                'mappings': [],
                'receipt_allocations': [],
            },
            {
                'billing_period': '2026-01',
                'contract_line': self.contract_line,
                'net_amount': Decimal('50.00'),
                'mapped_amount': Decimal('0.00'),
                'receipted_amount': Decimal('0.00'),
                'unreceived_amount': Decimal('50.00'),
                'overdue_amount': Decimal('0.00'),
                'mappings': [],
                'receipt_allocations': [],
            },
        ]
        calendar = views._build_revenue_contract_calendar(
            self.contract,
            [self.bill, future_bill],
            rows,
            [self.contract_line],
            [self.version],
            today=date(2026, 3, 1),
        )

        january = next(month for month in calendar['months'] if month['billing_period'] == '2026-01')
        self.assertNotEqual(january['status'], 'overdue')
        self.assertEqual(january['overdue_total'], Decimal('0.00'))

    def test_revenue_contract_template_uses_unambiguous_rate_labels(self):
        template_path = Path(__file__).parents[1] / 'templates' / 'netbox_contract' / 'revenue_contract.html'
        template = template_path.read_text(encoding='utf-8')

        self.assertIn('\u5408\u540c\u5f00\u7968\u8fdb\u5ea6', template)
        self.assertIn('\u5e94\u6536\u56de\u6b3e\u7387', template)
        self.assertIn('\u5df2\u5f62\u6210\u5e94\u6536', template)
        self.assertIn('\u903e\u671f\u672a\u6536', template)
        self.assertIn('overview.reconciliation.has_mismatch', template)
        self.assertIn('\u5468\u671f\u8d26\u5355\u77e9\u9635', template)
        self.assertIn('display.periodic_matrix', template)
        self.assertIn('\u8ba2\u5355/\u5f00\u5de5\u5355\u6cf3\u9053', template)
        self.assertIn('display.order_lanes', template)
        self.assertIn('display.order_lanes.ordered_amount', template)
        self.assertIn('display.order_lanes.legacy_count', template)
        self.assertIn('lane.order_url', template)
        self.assertIn('contract_line.revenue_order', template)
        self.assertIn('\u5df2\u4e0b\u5355\u91d1\u989d', template)
        self.assertIn('data-bs-toggle="offcanvas"', template)
        self.assertIn('row.event_dom_id', template)
        self.assertIn('\u7edf\u4e00\u5e94\u6536\u4e8b\u4ef6', template)
        self.assertIn('\u53d1\u7968\u6620\u5c04', template)
        self.assertIn('\u56de\u6b3e\u5206\u914d', template)
        self.assertIn('\u6df7\u5408\u6536\u8d39\u591a\u6cf3\u9053', template)
        self.assertIn('display.mixed_lanes', template)
        self.assertIn('hybrid-order-lanes', template)
        self.assertNotIn('hybrid-month-calendar', template)
        self.assertNotIn('ws.hybrid_month_summary.months', template)
        self.assertNotIn('ws.calendar.months', template)
        self.assertIn("display.periodic_matrix.has_recurring_lines and object.contract_type != 'hybrid'", template)
        self.assertNotIn('\u65b0\u589e\u5e94\u6536\u8ba1\u5212', template)
        self.assertNotIn('\u8ba1\u5212\u2014\u5f53\u524d\u2014\u5b9e\u9645\u4e09\u7ebf', template)
        self.assertNotIn('receivable-plan-tracks', template)
        self.assertIn('\u8c03\u6574\u4e8b\u9879', template)
        self.assertIn('row.adjustment_records', template)
        self.assertIn('revenue_contract_views', template)
        self.assertIn('name="matrix_anomalies"', template)
        self.assertIn('name="stage_mode"', template)
        self.assertIn('name="order_project"', template)
        self.assertIn('name="order_status"', template)
        self.assertIn('name="mixed_view"', template)
        self.assertIn('name="mixed_selected"', template)
        self.assertNotIn('应用筛选', template)
        self.assertNotIn('<div class="label">\u5f00\u7968\u7387</div>', template)
        self.assertNotIn('<div class="label">\u56de\u6b3e\u7387</div>', template)

    def test_all_revenue_forms_use_business_field_whitelists(self):
        self.assertEqual(
            tuple(forms._REVENUE_FORM_FIELDS),
            tuple(forms._REVENUE_FORM_MODELS),
        )
        for model, expected_fields in forms._REVENUE_FORM_FIELDS.items():
            form_class = getattr(forms, f'{model.__name__}Form')
            self.assertEqual(tuple(form_class._meta.fields), expected_fields)
            self.assertNotIn('custom_field_data', expected_fields)
            self.assertNotIn('custom_field_data', form_class().fields)

        self.assertIn('contract', forms.RevenueOrderForm().fields)
        self.assertIn('project', forms.RevenueOrderForm().fields)
        contract_line_fields = forms.RevenueContractLineForm().fields
        self.assertIn('contract', contract_line_fields)
        self.assertIn('contract_version', contract_line_fields)
        self.assertIn('project', contract_line_fields)
        self.assertIn('revenue_order', contract_line_fields)

    def test_revenue_contract_context_has_a_profile_for_every_contract_type(self):
        expected = {
            'milestone': ('\u9636\u6bb5\u6027', 'blue'),
            'recurring': ('\u5468\u671f\u6027', 'green'),
            'framework': ('\u6846\u67b6', 'purple'),
            'order': ('\u8ba2\u5355', 'cyan'),
            'hybrid': ('\u6df7\u5408', 'orange'),
        }
        request = RequestFactory().get('/')

        for contract_type, (label, tone) in expected.items():
            self.contract.contract_type = contract_type
            context = views._revenue_contract_context(request, self.contract)
            profile = context['revenue_contract_type_profile']

            self.assertEqual(profile['label'], label)
            self.assertEqual(profile['tone'], tone)
            self.assertEqual(len(profile['highlights']), 3)

    def test_recurring_contract_defaults_to_attention_timeline(self):
        self.contract.contract_type = 'recurring'
        self.contract.save(update_fields=['contract_type'])

        context = views._revenue_contract_context(
            RequestFactory().get('/'),
            self.contract,
        )
        timeline = context['revenue_timeline']

        self.assertEqual(timeline['active_filter'], 'attention')
        self.assertEqual(timeline['title'], '\u8fd1\u671f\u5e94\u6536\u52a8\u6001')
        self.assertEqual(timeline['summary_label'], '\u5f53\u524d\u7b5b\u9009\u6c47\u603b')
        self.assertEqual(timeline['filters'][0]['key'], 'attention')
        self.assertTrue(timeline['filters'][0]['is_active'])

    def test_non_recurring_contract_keeps_all_timeline_default(self):
        self.contract.contract_type = 'milestone'
        self.contract.save(update_fields=['contract_type'])

        context = views._revenue_contract_context(
            RequestFactory().get('/'),
            self.contract,
        )
        timeline = context['revenue_timeline']

        self.assertEqual(timeline['active_filter'], 'all')
        self.assertEqual(timeline['title'], '\u7efc\u5408\u5e94\u6536\u65f6\u95f4\u8f74')
        self.assertNotIn('attention', [item['key'] for item in timeline['filters']])

    def test_invalid_recurring_timeline_filter_returns_to_attention(self):
        self.contract.contract_type = 'recurring'
        self.contract.save(update_fields=['contract_type'])

        context = views._revenue_contract_context(
            RequestFactory().get('/?timeline_window=invalid'),
            self.contract,
        )

        self.assertEqual(context['revenue_timeline']['active_filter'], 'attention')

    def test_revenue_contract_template_displays_type_adaptive_header(self):
        template_path = Path(__file__).parents[1] / 'templates' / 'netbox_contract' / 'revenue_contract.html'
        template = template_path.read_text(encoding='utf-8')

        self.assertIn('revenue_contract_type_profile', template)
        self.assertIn('\u5408\u540c\u7c7b\u578b', template)
        self.assertNotIn('profile.calendar_title', template)
        self.assertIn('profile.highlights', template)
        self.assertIn(
            '{% badge object.get_status_display bg_color=object.get_status_color %}',
            template,
        )
        self.assertNotIn(
            'class="badge text-bg-secondary">{{ object.get_status_display',
            template,
        )

    def test_revenue_contract_workspace_includes_stage_timeline(self):
        self.contract.contract_type = 'milestone'
        self.contract.save()
        self.billing_rule.rule_type = 'milestone'
        self.billing_rule.trigger_event = 'acceptance'
        self.billing_rule.billing_cycle = ''
        self.billing_rule.billing_direction = ''
        self.billing_rule.bill_generation_day = None
        self.billing_rule.save()

        request = RequestFactory().get('/')
        context = views._revenue_contract_context(request, self.contract)

        timeline = context['revenue_contract_workspace']['timeline']
        self.assertTrue(timeline['is_stage_contract'])
        self.assertEqual(len(timeline['nodes']), 1)
        self.assertEqual(timeline['nodes'][0]['planned_amount'], Decimal('100.0000'))
        self.assertEqual(timeline['nodes'][0]['receivable_total'], Decimal('100.00'))
        self.assertEqual(timeline['nodes'][0]['line_count'], 1)
        self.assertEqual(timeline['nodes'][0]['date_certainty'], 'actual')
        self.assertEqual(timeline['nodes'][0]['actual_receivable_date'], self.bill.receivable_date)

    def test_stage_timeline_does_not_invent_a_date_before_trigger(self):
        RevenueReceivableLine.objects.all().delete()
        RevenueReceivableBill.objects.all().delete()
        self.contract.contract_type = 'milestone'
        self.contract.save(update_fields=['contract_type'])
        self.billing_rule.rule_type = 'milestone'
        self.billing_rule.trigger_event = 'acceptance'
        self.billing_rule.billing_cycle = ''
        self.billing_rule.billing_direction = ''
        self.billing_rule.bill_generation_day = None
        self.billing_rule.save()

        timeline = views._build_revenue_contract_timeline(
            self.contract,
            [self.billing_rule],
            [],
            today=date(2026, 3, 1),
        )
        node = timeline['nodes'][0]

        self.assertEqual(node['date_certainty'], 'pending_trigger')
        self.assertIsNone(node['original_planned_date'])
        self.assertIsNone(node['current_planned_date'])
        self.assertIsNone(node['actual_receivable_date'])
        self.assertIsNone(node['due_date'])
        self.assertIn('\u5f85\u9a8c\u6536\u89e6\u53d1', node['date_summary'])
        self.assertEqual(timeline['totals']['pending_trigger_nodes'], 1)

    def test_revenue_contract_workspace_includes_receivable_calendar(self):
        request = RequestFactory().get('/')
        context = views._revenue_contract_context(request, self.contract)

        calendar = context['revenue_contract_workspace']['calendar']
        january = next(month for month in calendar['months'] if month['billing_period'] == '2026-01')

        self.assertEqual(calendar['year'], 2026)
        self.assertEqual(january['receivable_total'], Decimal('100.00'))
        self.assertEqual(january['line_count'], 1)
        self.assertEqual(january['bill_count'], 1)
        self.assertIn(january['status'], {'generated', 'overdue', 'partial_invoice', 'invoiced', 'partial_receipt', 'paid'})
        self.assertGreaterEqual(calendar['totals']['generated_months'], 1)

    def test_revenue_contract_workspace_includes_periodic_matrix(self):
        request = RequestFactory().get('/')
        context = views._revenue_contract_context(request, self.contract)

        workspace = context['revenue_contract_workspace']
        matrix = workspace['periodic_matrix']
        january = next(
            cell
            for cell in matrix['rows'][0]['cells']
            if cell['billing_period'] == '2026-01'
        )

        self.assertTrue(matrix['has_recurring_lines'])
        self.assertEqual(matrix['year'], 2026)
        self.assertEqual(len(matrix['months']), 12)
        self.assertEqual(len(matrix['rows']), 1)
        self.assertEqual(january['receivable_total'], Decimal('100.00'))
        self.assertEqual(january['event_count'], 1)
        self.assertFalse(workspace['order_lanes']['should_display'])
        self.assertFalse(workspace['mixed_lanes']['should_display'])

    def test_hybrid_contract_workspace_includes_mixed_charge_lanes(self):
        self.contract.contract_type = 'hybrid'
        self.contract.save(update_fields=['contract_type'])
        milestone_line = RevenueContractLine.objects.create(
            contract=self.contract,
            contract_version=self.version,
            project=self.project,
            order_id='ORD-HYBRID-001',
            product_category='fiber',
            charge_item='项目验收款',
            unit_price=Decimal('300.00'),
            quantity=Decimal('1.00'),
            unit='项',
            valid_from=date(2026, 1, 1),
            status='active',
        )
        RevenueBillingRule.objects.create(
            contract_line=milestone_line,
            contract_version=self.version,
            rule_type='milestone',
            trigger_event='acceptance',
            proration_rule='none',
            rounding_precision='2',
            status='effective',
        )

        request = RequestFactory().get('/')
        context = views._revenue_contract_context(request, self.contract)
        mixed_lanes = context['revenue_contract_workspace']['mixed_lanes']
        recurring_lane = next(lane for lane in mixed_lanes['lanes'] if lane['charge_item'] == '专线月租')
        milestone_lane = next(lane for lane in mixed_lanes['lanes'] if lane['charge_item'] == '项目验收款')
        january = next(cell for cell in recurring_lane['cells'] if cell['billing_period'] == '2026-01')

        self.assertTrue(mixed_lanes['should_display'])
        self.assertEqual(len(mixed_lanes['lanes']), 2)
        self.assertEqual(january['receivable_total'], Decimal('100.00'))
        self.assertEqual(january['primary_event_dom_id'], f'receivable-event-{self.receivable_line.pk}')
        self.assertEqual(milestone_lane['lane_type'], 'milestone')
        self.assertEqual(milestone_lane['pending_trigger_count'], 1)
        self.assertEqual(mixed_lanes['totals']['pending_trigger_count'], 1)
        self.assertFalse(
            context['revenue_contract_workspace']['periodic_matrix']['has_recurring_lines']
        )

        month_summary = context['revenue_contract_workspace']['hybrid_month_summary']
        summary_january = next(
            month for month in month_summary['months']
            if month['billing_period'] == '2026-01'
        )
        summary_february = next(
            month for month in month_summary['months']
            if month['billing_period'] == '2026-02'
        )
        self.assertEqual(len(month_summary['months']), 12)
        self.assertEqual(summary_january['receivable_total'], Decimal('100.00'))
        self.assertEqual(summary_january['planned_total'], Decimal('0'))
        self.assertEqual(summary_february['status'], 'planned')
        self.assertEqual(summary_february['planned_total'], Decimal('100.0000'))
        self.assertEqual(month_summary['totals']['planned_months'], 11)

    def test_hybrid_month_summary_excludes_months_without_data_or_plan(self):
        calendar = {
            'year': 2026,
            'months': [
                {
                    'billing_period': '2026-01',
                    'line_count': 0,
                    'bill_count': 0,
                    'risk_level': 'muted',
                },
                {
                    'billing_period': '2026-02',
                    'line_count': 0,
                    'bill_count': 0,
                    'risk_level': 'muted',
                },
            ],
        }
        mixed_lanes = {
            'lanes': [{
                'cells': [
                    {'billing_period': '2026-01', 'planned_amount': Decimal('0')},
                    {'billing_period': '2026-02', 'planned_amount': Decimal('50')},
                ],
            }],
        }

        summary = views._build_hybrid_month_summary(calendar, mixed_lanes)

        self.assertEqual(
            [month['billing_period'] for month in summary['months']],
            ['2026-02'],
        )
        self.assertEqual(summary['months'][0]['status'], 'planned')
        self.assertEqual(summary['totals']['displayed_months'], 1)
        self.assertEqual(summary['totals']['planned_total'], Decimal('50'))

    def test_order_and_contract_line_forms_use_dependent_selectors(self):
        order_form = forms.RevenueOrderForm()
        line_form = forms.RevenueContractLineForm()

        self.assertEqual(order_form.fields['project'].query_params, {'contract_id': '$contract'})
        self.assertEqual(
            line_form.fields['contract_version'].query_params,
            {'contract_id': '$contract'},
        )
        self.assertEqual(line_form.fields['project'].query_params, {'contract_id': '$contract'})
        self.assertEqual(
            line_form.fields['revenue_order'].query_params,
            {'contract_id': '$contract', 'project_id': '$project'},
        )

    def test_revenue_project_filterset_filters_by_contract_usage(self):
        unrelated_project = RevenueProject.objects.create(
            name='未关联合同项目',
            customer=self.customer,
            project_manager='赵六',
            sales_owner='张三',
            business_owner='李四',
            project_type='fiber',
            status='draft',
        )

        queryset = filtersets.RevenueProjectFilterSet(
            {'contract_id': self.contract.pk},
            queryset=RevenueProject.objects.all(),
        ).qs

        self.assertIn(self.project, queryset)
        self.assertNotIn(unrelated_project, queryset)

    def test_contract_line_rejects_an_order_from_another_contract(self):
        other_contract = RevenueContract.objects.create(
            contract_code='RC-OTHER',
            name='其他收入合同',
            customer=self.customer,
            contract_type='order',
            our_party='本公司',
            customer_party='客户A',
            sign_date=date(2026, 1, 1),
            start_date=date(2026, 1, 1),
            total_amount=Decimal('200.00'),
            is_framework=False,
            status='effective',
            sales_owner='张三',
            business_owner='李四',
            source_system='REVENUE_SYS',
        )
        foreign_order = RevenueOrder.objects.create(
            order_code='ORD-FOREIGN',
            contract=other_contract,
            project=self.project,
            amount=Decimal('200.00'),
            status='not_started',
            source_system='REVENUE_SYS',
        )
        self.contract_line.revenue_order = foreign_order

        with self.assertRaises(ValidationError):
            self.contract_line.full_clean()

        serializer = api_serializers.RevenueContractLineSerializer()
        with self.assertRaises(DRFValidationError) as error:
            serializer.validate(
                {
                    'contract': self.contract,
                    'contract_version': self.version,
                    'project': self.project,
                    'revenue_order': foreign_order,
                }
            )
        self.assertIn('revenue_order', getattr(error.exception, 'detail', {}))
    def test_framework_contract_workspace_includes_order_lanes(self):
        self.contract.contract_type = 'framework'
        self.contract.is_framework = True
        self.contract.save(update_fields=['contract_type', 'is_framework'])
        order = RevenueOrder.objects.create(
            order_code='ORD-001',
            contract=self.contract,
            project=self.project,
            name='框架订单001',
            amount=Decimal('240.00'),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status='executing',
            source_system='REVENUE_SYS',
            external_id='ERP-ORD-001',
        )
        self.contract_line.revenue_order = order
        self.contract_line.order_id = 'ORD-001'
        self.contract_line.full_clean()
        self.contract_line.save(update_fields=['revenue_order', 'order_id'])

        request = RequestFactory().get('/')
        context = views._revenue_contract_context(request, self.contract)

        order_lanes = context['revenue_contract_workspace']['order_lanes']
        lane = order_lanes['lanes'][0]

        self.assertTrue(order_lanes['should_display'])
        self.assertEqual(order_lanes['order_count'], 1)
        self.assertEqual(order_lanes['legacy_count'], 0)
        self.assertEqual(order_lanes['unfiled_count'], 0)
        self.assertEqual(order_lanes['ordered_amount'], Decimal('240.00'))
        self.assertEqual(order_lanes['remaining_limit'], Decimal('760.00'))
        self.assertEqual(lane['order'], order)
        self.assertEqual(lane['order_id'], 'ORD-001')
        self.assertEqual(lane['order_amount'], Decimal('240.00'))
        self.assertTrue(lane['order_url'])
        self.assertEqual(lane['receivable_total'], Decimal('100.00'))
        self.assertEqual(len(lane['cells']), 12)

    def test_framework_contract_legacy_order_id_remains_visible_until_mapped(self):
        self.contract.contract_type = 'framework'
        self.contract.is_framework = True
        self.contract.save(update_fields=['contract_type', 'is_framework'])
        self.contract_line.order_id = 'ORD-LEGACY'
        self.contract_line.save(update_fields=['order_id'])

        workspace = views._revenue_contract_context(
            RequestFactory().get('/'), self.contract
        )['revenue_contract_workspace']
        lane = workspace['order_lanes']['lanes'][0]

        self.assertEqual(workspace['order_lanes']['order_count'], 0)
        self.assertEqual(workspace['order_lanes']['legacy_count'], 1)
        self.assertFalse(lane['is_unfiled'])
        self.assertTrue(lane['is_legacy'])
        self.assertEqual(lane['order_amount'], Decimal('100.0000'))

    def test_order_backfill_groups_legacy_contract_lines(self):
        self.contract_line.order_id = 'ORD-MIGRATE'
        self.contract_line.save(update_fields=['order_id'])
        migration = importlib.import_module(
            'netbox_contract.migrations.0055_revenueorder_contractline_revenue_order'
        )

        migration.backfill_revenue_orders(django_apps, None)

        self.contract_line.refresh_from_db()
        order = self.contract_line.revenue_order
        self.assertEqual(order.order_code, 'ORD-MIGRATE')
        self.assertEqual(order.contract, self.contract)
        self.assertEqual(order.project, self.project)
        self.assertEqual(order.amount, Decimal('100.0000'))
        self.assertEqual(order.source_system, 'LEGACY_LEDGER')
    def test_framework_contract_marks_lines_without_order_id_as_unfiled(self):
        self.contract.contract_type = 'framework'
        self.contract.is_framework = True
        self.contract.save(update_fields=['contract_type', 'is_framework'])

        request = RequestFactory().get('/')
        context = views._revenue_contract_context(request, self.contract)

        order_lanes = context['revenue_contract_workspace']['order_lanes']
        self.assertTrue(order_lanes['should_display'])
        self.assertEqual(order_lanes['order_count'], 0)
        self.assertEqual(order_lanes['unfiled_count'], 1)
        self.assertTrue(order_lanes['lanes'][0]['is_unfiled'])

    def test_legacy_contract_views_reuse_the_unified_template(self):
        self.assertEqual(
            views.RevenueContractVisualView.template_name,
            'netbox_contract/revenue_contract.html',
        )
        self.assertEqual(
            views.RevenueContractExecutiveView.template_name,
            'netbox_contract/revenue_contract.html',
        )

    def test_preview_receivables_for_contract_does_not_write(self):
        from netbox_contract.views import preview_receivables_for_contract

        RevenueReceivableLine.objects.all().delete()
        RevenueReceivableBill.objects.all().delete()
        RevenueBillingSegment.objects.all().delete()

        preview = preview_receivables_for_contract(self.contract, '2026-02')

        self.assertEqual(preview['create_count'], 1)
        self.assertEqual(preview['skip_count'], 0)
        self.assertEqual(preview['create_total'], Decimal('100.00'))
        self.assertEqual(preview['rows'][0]['amount'], Decimal('100.00'))
        self.assertTrue(preview['rows'][0]['will_create'])
        self.assertEqual(RevenueReceivableBill.objects.count(), 0)
        self.assertEqual(RevenueReceivableLine.objects.count(), 0)
        self.assertEqual(RevenueBillingSegment.objects.count(), 0)

    def test_stage_generation_uses_direct_confirmed_rule_trigger_without_plan(self):
        RevenueReceivableLine.objects.all().delete()
        RevenueReceivableBill.objects.all().delete()
        RevenueBillingSegment.objects.all().delete()
        self.billing_rule.rule_type = 'milestone'
        self.billing_rule.trigger_event = 'acceptance'
        self.billing_rule.trigger_offset_days = 2
        self.billing_rule.billing_cycle = ''
        self.billing_rule.billing_direction = ''
        self.billing_rule.bill_generation_day = None
        self.billing_rule.save()

        pending = views.preview_receivables_for_contract(self.contract, '2026-02')
        self.assertEqual(pending['rows'][0]['reason_code'], 'awaiting_trigger')

        RevenueTriggerRecord.objects.create(
            billing_rule=self.billing_rule,
            trigger_event='acceptance',
            actual_trigger_date=date(2026, 2, 12),
            status='confirmed',
            source_system='REVENUE_SYS',
        )
        preview = views.preview_receivables_for_contract(self.contract, '2026-02')
        self.assertEqual(preview['create_count'], 1)
        self.assertEqual(preview['rows'][0]['receivable_date'], date(2026, 2, 14))

        result = views.generate_receivables_for_contract(self.contract, '2026-02')
        line = result['bill'].lines.get()
        self.assertEqual(result['created_lines'], 1)
        self.assertIsNone(line.receivable_plan)
        self.assertEqual(line.receivable_date, date(2026, 2, 14))
        self.assertEqual(line.due_date, date(2026, 3, 16))

    def test_direct_trigger_requires_a_rule_or_legacy_plan(self):
        record = RevenueTriggerRecord(
            trigger_event='acceptance',
            actual_trigger_date=date(2026, 2, 12),
            status='confirmed',
            source_system='REVENUE_SYS',
        )
        with self.assertRaises(ValidationError):
            record.full_clean()

    def test_receivable_event_prefers_line_level_dates(self):
        self.receivable_line.receivable_date = date(2026, 1, 20)
        self.receivable_line.due_date = date(2026, 2, 20)
        self.receivable_line.save(update_fields=['receivable_date', 'due_date'])

        workspace = views._build_revenue_contract_workspace(self.contract)
        row = workspace['chain_rows'][0]
        self.assertEqual(row['receivable_date'], date(2026, 1, 20))
        self.assertEqual(row['due_date'], date(2026, 2, 20))

    def test_generate_receivables_for_contract_does_not_create_empty_bill(self):
        from netbox_contract.views import generate_receivables_for_contract

        RevenueReceivableLine.objects.all().delete()
        RevenueReceivableBill.objects.all().delete()
        RevenueBillingSegment.objects.all().delete()
        RevenueBillingRule.objects.all().delete()

        result = generate_receivables_for_contract(self.contract, '2026-02')

        self.assertIsNone(result['bill'])
        self.assertEqual(result['created_lines'], 0)
        self.assertEqual(RevenueReceivableBill.objects.count(), 0)
        self.assertEqual(RevenueReceivableLine.objects.count(), 0)

    def test_generate_receivables_for_contract_is_idempotent(self):
        from netbox_contract.views import generate_receivables_for_contract, preview_receivables_for_contract

        RevenueReceivableLine.objects.all().delete()
        RevenueReceivableBill.objects.all().delete()
        RevenueBillingSegment.objects.all().delete()

        result = generate_receivables_for_contract(self.contract, '2026-02')

        self.assertEqual(result['created_lines'], 1)
        bill = RevenueReceivableBill.objects.get(contract=self.contract, billing_period='2026-02')
        line = RevenueReceivableLine.objects.get(bill=bill)
        self.assertEqual(bill.amount, Decimal('100.00'))
        self.assertEqual(line.net_amount, Decimal('100.00'))
        self.assertEqual(RevenueBillingSegment.objects.count(), 1)

        second_preview = preview_receivables_for_contract(self.contract, '2026-02')
        self.assertEqual(second_preview['create_count'], 0)
        self.assertEqual(second_preview['skip_count'], 1)
        self.assertFalse(second_preview['rows'][0]['will_create'])

        second = generate_receivables_for_contract(self.contract, '2026-02')
        self.assertEqual(second['created_lines'], 0)
        self.assertEqual(second['skipped_lines'], 1)
        self.assertEqual(RevenueReceivableBill.objects.filter(contract=self.contract, billing_period='2026-02').count(), 1)
        self.assertEqual(RevenueReceivableLine.objects.filter(bill=bill).count(), 1)
