
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from netbox_contract.models import (
    RevenueBillingRule,
    RevenueBillingSegment,
    RevenueContract,
    RevenueContractLine,
    RevenueContractProject,
    RevenueContractVersion,
    RevenueCustomer,
    RevenueInvoice,
    RevenueInvoiceLine,
    RevenueInvoiceMapping,
    RevenueOrder,
    RevenueProject,
    RevenueReceivableBill,
    RevenueReceivableLine,
    RevenueReceipt,
    RevenueReceiptAllocation,
    RevenueSyncLog,
)

PREFIX = 'SAMPLE-REV'
SOURCE_SYSTEM = 'SAMPLE_DATA'


def d(value):
    return Decimal(value).quantize(Decimal('0.01'))


class Command(BaseCommand):
    help = 'Create sample data for revenue contract ledger models.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing SAMPLE-REV sample data before creating it again.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            self._delete_existing_sample_data()

        customers = self._create_customers()
        projects = self._create_projects(customers)
        contracts = self._create_contracts(customers, projects)
        self._create_finance_chain(contracts)
        self._create_orders(contracts)

        self.stdout.write(self.style.SUCCESS('Revenue sample data is ready: 7 contracts created or updated.'))

    def _delete_existing_sample_data(self):
        RevenueSyncLog.objects.filter(external_id__startswith=PREFIX).delete()
        RevenueReceiptAllocation.objects.filter(approval_batch_no__startswith=PREFIX).delete()
        RevenueReceipt.objects.filter(bank_flow_no__startswith=PREFIX).delete()
        RevenueInvoiceMapping.objects.filter(approval_batch_no__startswith=PREFIX).delete()
        RevenueInvoiceLine.objects.filter(invoice__invoice_code__startswith=PREFIX).delete()
        RevenueInvoice.objects.filter(invoice_code__startswith=PREFIX).delete()
        RevenueReceivableLine.objects.filter(idempotent_key__startswith=PREFIX).delete()
        RevenueReceivableBill.objects.filter(bill_code__startswith=PREFIX).delete()
        RevenueBillingSegment.objects.filter(contract_line__contract__contract_code__startswith=PREFIX).delete()
        RevenueBillingRule.objects.filter(contract_line__contract__contract_code__startswith=PREFIX).delete()
        RevenueContractLine.objects.filter(contract__contract_code__startswith=PREFIX).delete()
        RevenueOrder.objects.filter(contract__contract_code__startswith=PREFIX).delete()
        RevenueContractVersion.objects.filter(contract__contract_code__startswith=PREFIX).delete()
        RevenueContractProject.objects.filter(contract__contract_code__startswith=PREFIX).delete()
        RevenueContract.objects.filter(contract_code__startswith=PREFIX).delete()
        RevenueProject.objects.filter(customer__usci__startswith='91310000SAMPLE').delete()
        RevenueCustomer.objects.filter(usci__startswith='91310000SAMPLE').delete()

    def _create_customers(self):
        specs = [
            ('001', '\u4e1c\u65b9\u6570\u5b57\u79d1\u6280\u6709\u9650\u516c\u53f8', '\u4e1c\u65b9\u6570\u5b57', 'enterprise', '\u5f20\u78ca', '\u674e\u5a1c'),
            ('002', '\u534e\u5317\u4e91\u7f51\u8fd0\u8425\u6709\u9650\u516c\u53f8', '\u534e\u5317\u4e91\u7f51', 'operator', '\u738b\u5f3a', '\u8d75\u654f'),
            ('003', '\u957f\u6c5f\u667a\u8054\u96c6\u6210\u6709\u9650\u516c\u53f8', '\u957f\u6c5f\u667a\u8054', 'integrator', '\u9648\u660e', '\u5218\u9896'),
        ]
        customers = []
        for suffix, name, short_name, customer_type, sales_owner, business_owner in specs:
            customer, _ = RevenueCustomer.objects.update_or_create(
                usci=f'91310000SAMPLE{suffix}',
                defaults={
                    'name': name,
                    'short_name': short_name,
                    'finance_code': f'FIN-{PREFIX}-{suffix}',
                    'eip_code': f'EIP-{PREFIX}-{suffix}',
                    'customer_type': customer_type,
                    'sales_owner': sales_owner,
                    'business_owner': business_owner,
                    'is_risk': False,
                    'address_phone': '\u4e0a\u6d77\u5e02\u6d66\u4e1c\u65b0\u533a\u6837\u4f8b\u8def88\u53f7 021-60000000',
                    'bank_account': '\u4e2d\u56fd\u5de5\u5546\u94f6\u884c\u4e0a\u6d77\u6837\u4f8b\u652f\u884c 1000000000000000',
                },
            )
            customers.append(customer)
        return customers

    def _create_projects(self, customers):
        specs = [
            (customers[0], '\u91d1\u6865\u4e13\u7ebf\u63a5\u5165\u9879\u76ee', 'fiber'),
            (customers[0], '\u5916\u9ad8\u6865IDC\u6258\u7ba1\u9879\u76ee', 'idc'),
            (customers[1], '\u534e\u5317\u9aa8\u5e72\u7ba1\u9053\u79df\u8d41\u9879\u76ee', 'pipe'),
            (customers[1], '\u4e91\u7f51\u673a\u67dc\u6269\u5bb9\u9879\u76ee', 'rack'),
            (customers[2], '\u667a\u6167\u56ed\u533a\u7efc\u5408\u901a\u4fe1\u9879\u76ee', 'composite'),
        ]
        projects = []
        for idx, (customer, name, project_type) in enumerate(specs, start=1):
            project, _ = RevenueProject.objects.update_or_create(
                customer=customer,
                name=name,
                defaults={
                    'project_manager': ['\u5468\u5b81', '\u90d1\u4f1f', '\u9a6c\u8d85', '\u5b59\u6d69', '\u9ec4\u82b3'][idx - 1],
                    'sales_owner': customer.sales_owner,
                    'business_owner': customer.business_owner,
                    'project_type': project_type,
                    'status': 'operating',
                    'accumulated_receivable': d('0'),
                    'accumulated_invoice': d('0'),
                    'accumulated_receipt': d('0'),
                },
            )
            projects.append(project)
        return projects

    def _create_contracts(self, customers, projects):
        specs = [
            ('001', projects[0], customers[0], '\u91d1\u6865\u4e13\u7ebf\u63a5\u5165\u670d\u52a1\u5408\u540c', 'recurring', '288000.00', date(2026, 1, 1), date(2026, 12, 31)),
            ('002', projects[1], customers[0], '\u5916\u9ad8\u6865IDC\u673a\u67dc\u79df\u8d41\u5408\u540c', 'recurring', '480000.00', date(2026, 1, 1), date(2026, 12, 31)),
            ('003', projects[2], customers[1], '\u534e\u5317\u9aa8\u5e72\u7ba1\u9053\u8d44\u6e90\u79df\u8d41\u5408\u540c', 'recurring', '360000.00', date(2026, 2, 1), date(2027, 1, 31)),
            ('004', projects[3], customers[1], '\u4e91\u7f51\u673a\u67dc\u6269\u5bb9\u8ba2\u5355\u5408\u540c', 'order', '168000.00', date(2026, 3, 1), date(2026, 8, 31)),
            ('005', projects[4], customers[2], '\u667a\u6167\u56ed\u533a\u7efc\u5408\u901a\u4fe1\u6846\u67b6\u5408\u540c', 'framework', '600000.00', date(2026, 1, 15), date(2026, 12, 31)),
            ('006', projects[4], customers[2], '\u667a\u6167\u56ed\u533a\u5206\u9636\u6bb5\u4ea4\u4ed8\u5408\u540c', 'milestone', '300000.00', date(2026, 2, 1), date(2026, 11, 30)),
            ('007', projects[4], customers[2], '\u667a\u6167\u56ed\u533a\u5efa\u8bbe\u8fd0\u7ef4\u6df7\u5408\u5408\u540c', 'hybrid', '720000.00', date(2026, 2, 1), date(2027, 1, 31)),
        ]
        contracts = []
        for suffix, project, customer, name, contract_type, total_amount, start_date, end_date in specs:
            contract, _ = RevenueContract.objects.update_or_create(
                contract_code=f'{PREFIX}-CON-{suffix}',
                defaults={
                    'name': name,
                    'customer': customer,
                    'contract_type': contract_type,
                    'our_party': '\u4e2d\u56fd\u901a\u4fe1\u670d\u52a1\u6837\u4f8b\u516c\u53f8',
                    'customer_party': customer.name,
                    'sign_date': start_date,
                    'start_date': start_date,
                    'end_date': end_date,
                    'total_amount': d(total_amount),
                    'is_framework': contract_type == 'framework',
                    'status': 'effective',
                    'sales_owner': customer.sales_owner,
                    'business_owner': customer.business_owner,
                    'source_system': SOURCE_SYSTEM,
                    'external_id': f'{PREFIX}-EXT-CON-{suffix}',
                    'sync_status': 'synced',
                    'sync_log': '\u6837\u4f8b\u6570\u636e\u521d\u59cb\u5316',
                },
            )
            RevenueContractProject.objects.update_or_create(contract=contract, project=project, defaults={})
            contracts.append((contract, project, suffix))
        return contracts

    def _create_finance_chain(self, contracts):
        for index, (contract, project, suffix) in enumerate(contracts, start=1):
            version, _ = RevenueContractVersion.objects.update_or_create(
                contract=contract,
                version_code='V1.0',
                defaults={
                    'change_type': 'original',
                    'start_date': contract.start_date,
                    'end_date': contract.end_date,
                    'status': 'effective',
                },
            )
            if suffix == '006':
                self._create_milestone_contract_chain(contract, project, version, suffix)
                continue
            if suffix == '007':
                self._create_hybrid_contract_chain(contract, project, version, suffix)
                continue

            monthly_amount = (contract.total_amount / Decimal('12')).quantize(Decimal('0.01'))
            line_specs = [
                ('01', '\u57fa\u7840\u670d\u52a1\u8d39', monthly_amount),
                ('02', '\u8fd0\u7ef4\u4fdd\u969c\u8d39', (monthly_amount * Decimal('0.10')).quantize(Decimal('0.01'))),
            ]
            first_receivable_line = None
            first_mapping = None
            bill_net_total = d('0')
            bill, _ = RevenueReceivableBill.objects.update_or_create(
                bill_code=f'{PREFIX}-BILL-{suffix}-202604',
                defaults={
                    'customer': contract.customer,
                    'contract': contract,
                    'project': project,
                    'billing_period': '2026-04',
                    'receivable_date': date(2026, 4, 25),
                    'due_date': date(2026, 5, 25),
                    'amount': d('0'),
                    'adjusted_amount': d('0'),
                    'net_amount': d('0'),
                    'invoiced_amount': d('0'),
                    'receipted_amount': d('0'),
                    'confirm_status': 'confirmed',
                    'invoice_status': 'fully_invoiced',
                    'receipt_status': 'unpaid',
                    'ageing_status': 'not_due',
                    'risk_status': 'normal',
                },
            )

            invoice_amount = d('0')
            invoice, _ = RevenueInvoice.objects.update_or_create(
                invoice_code=f'{PREFIX}-INV-{suffix}-202604',
                defaults={
                    'customer': contract.customer,
                    'invoice_type': 'electronic',
                    'invoice_date': date(2026, 4, 26),
                    'amount': d('0'),
                    'source_system': SOURCE_SYSTEM,
                    'external_id': f'{PREFIX}-EXT-INV-{suffix}',
                    'sync_status': 'synced',
                    'sync_log': '\u6837\u4f8b\u53d1\u7968',
                },
            )

            for line_index, (line_suffix, charge_item, amount) in enumerate(line_specs, start=1):
                contract_line, _ = RevenueContractLine.objects.update_or_create(
                    contract=contract,
                    order_id=f'{PREFIX}-ORD-{suffix}-{line_suffix}',
                    defaults={
                        'contract_version': version,
                        'project': project,
                        'product_category': 'maintenance' if line_suffix == '02' else 'fiber',
                        'charge_item': charge_item,
                        'unit_price': amount,
                        'quantity': d('1'),
                        'unit': '\u6708',
                        'valid_from': contract.start_date,
                        'valid_to': contract.end_date,
                        'status': 'active',
                    },
                )
                rule, _ = RevenueBillingRule.objects.update_or_create(
                    contract_line=contract_line,
                    defaults={
                        'contract_version': version,
                        'rule_type': 'recurring',
                        'trigger_event': '',
                        'billing_cycle': 'month',
                        'billing_direction': 'postpay',
                        'bill_generation_day': 25,
                        'proration_rule': 'actual_days',
                        'rounding_precision': '2',
                        'is_active': True,
                        'status': 'effective',
                    },
                )
                RevenueBillingSegment.objects.update_or_create(
                    contract_line=contract_line,
                    billing_rule=rule,
                    segment_start=date(2026, 4, 1),
                    defaults={
                        'segment_end': date(2026, 4, 30),
                        'unit_price': amount,
                        'quantity': d('1'),
                        'amount': amount,
                        'change_trigger': 'normal',
                        'billing_rule_snapshot': {'cycle': 'month', 'direction': 'postpay', 'sample': True},
                    },
                )
                receivable_line, _ = RevenueReceivableLine.objects.update_or_create(
                    idempotent_key=f'{PREFIX}-LINE-{suffix}-{line_suffix}-202604',
                    defaults={
                        'bill': bill,
                        'contract_line': contract_line,
                        'billing_rule': rule,
                        'start_date': date(2026, 4, 1),
                        'end_date': date(2026, 4, 30),
                        'amount': amount,
                        'adjusted_amount': d('0'),
                        'net_amount': amount,
                        'risk_status': 'normal',
                    },
                )
                invoice_line, _ = RevenueInvoiceLine.objects.update_or_create(
                    invoice=invoice,
                    line_no=line_index,
                    defaults={
                        'external_line_id': f'{PREFIX}-INVLINE-{suffix}-{line_suffix}',
                        'item_name': charge_item,
                        'amount': amount,
                    },
                )
                mapping, _ = RevenueInvoiceMapping.objects.update_or_create(
                    receivable_line=receivable_line,
                    invoice_line=invoice_line,
                    defaults={
                        'mapped_amount': amount,
                        'status': 'active',
                        'operator': '\u6837\u4f8b\u7ecf\u529e\u4eba',
                        'approval_batch_no': f'{PREFIX}-MAP-{suffix}-{line_suffix}',
                    },
                )
                bill_net_total += amount
                invoice_amount += amount
                if first_receivable_line is None:
                    first_receivable_line = receivable_line
                    first_mapping = mapping

            bill.amount = bill_net_total
            bill.net_amount = bill_net_total
            bill.invoiced_amount = bill_net_total
            bill.save(update_fields=['amount', 'net_amount', 'invoiced_amount'])
            invoice.amount = invoice_amount
            invoice.save(update_fields=['amount'])

            receipt_amount = bill_net_total if index <= 3 else (bill_net_total / Decimal('2')).quantize(Decimal('0.01'))
            receipt, _ = RevenueReceipt.objects.update_or_create(
                bank_flow_no=f'{PREFIX}-BANK-{suffix}-202605',
                defaults={
                    'customer': contract.customer,
                    'receipt_date': date(2026, 5, 10),
                    'amount': receipt_amount,
                    'allocated_total': d('0'),
                    'unallocated_amount': receipt_amount,
                    'payer_name': contract.customer.name,
                    'status': 'unmatched',
                    'source_system': 'BANK_FLOW',
                    'external_id': f'{PREFIX}-EXT-BANK-{suffix}',
                    'sync_status': 'synced',
                    'sync_log': '\u6837\u4f8b\u94f6\u884c\u56de\u6b3e',
                },
            )
            RevenueReceiptAllocation.objects.update_or_create(
                receipt=receipt,
                receivable_line=first_receivable_line,
                defaults={
                    'invoice_mapping': first_mapping,
                    'allocated_amount': min(receipt_amount, first_receivable_line.net_amount),
                    'allocation_type': 'direct_receipt',
                    'status': 'active',
                    'operator': '\u6837\u4f8b\u7ecf\u529e\u4eba',
                    'approval_batch_no': f'{PREFIX}-RCPT-ALLOC-{suffix}',
                },
            )
            receipt.update_totals()
            bill.receipted_amount = receipt.allocated_total
            bill.receipt_status = 'fully_paid' if receipt.allocated_total >= bill.net_amount else 'partially_paid'
            bill.save(update_fields=['receipted_amount', 'receipt_status'])

            RevenueSyncLog.objects.update_or_create(
                external_id=f'{PREFIX}-SYNC-{suffix}',
                defaults={
                    'source_system': SOURCE_SYSTEM,
                    'entity_type': 'RevenueContract',
                    'entity_id': str(contract.pk),
                    'sync_direction': 'INBOUND',
                    'sync_status': 'success',
                    'request_payload': {'contract_code': contract.contract_code, 'sample': True},
                    'response_payload': {'status': 'ok'},
                    'error_message': '',
                },
            )

    def _create_receivable_chain(self, contract, project, contract_line, rule, suffix, chain_suffix, period, receivable_date, amount, receipt_amount):
        bill, _ = RevenueReceivableBill.objects.update_or_create(
            bill_code=f'{PREFIX}-BILL-{suffix}-{chain_suffix}-{period}',
            defaults={
                'customer': contract.customer,
                'contract': contract,
                'project': project,
                'billing_period': period,
                'receivable_date': receivable_date,
                'due_date': receivable_date + timedelta(days=30),
                'amount': amount,
                'adjusted_amount': d('0'),
                'net_amount': amount,
                'invoiced_amount': amount,
                'receipted_amount': d('0'),
                'confirm_status': 'confirmed',
                'invoice_status': 'fully_invoiced',
                'receipt_status': 'unpaid',
                'ageing_status': 'not_due',
                'risk_status': 'normal',
            },
        )
        RevenueBillingSegment.objects.update_or_create(
            contract_line=contract_line,
            billing_rule=rule,
            segment_start=receivable_date,
            defaults={
                'segment_end': receivable_date,
                'unit_price': amount,
                'quantity': d('1'),
                'amount': amount,
                'change_trigger': 'normal',
                'billing_rule_snapshot': {
                    'rule_type': rule.rule_type,
                    'trigger_event': rule.trigger_event,
                    'sample': True,
                },
            },
        )
        receivable_line, _ = RevenueReceivableLine.objects.update_or_create(
            idempotent_key=f'{PREFIX}-LINE-{suffix}-{chain_suffix}-{period}',
            defaults={
                'bill': bill,
                'contract_line': contract_line,
                'billing_rule': rule,
                'start_date': receivable_date,
                'end_date': receivable_date,
                'amount': amount,
                'adjusted_amount': d('0'),
                'net_amount': amount,
                'risk_status': 'normal',
            },
        )
        invoice, _ = RevenueInvoice.objects.update_or_create(
            invoice_code=f'{PREFIX}-INV-{suffix}-{chain_suffix}-{period}',
            defaults={
                'customer': contract.customer,
                'invoice_type': 'electronic',
                'invoice_date': receivable_date + timedelta(days=1),
                'amount': amount,
                'source_system': SOURCE_SYSTEM,
                'external_id': f'{PREFIX}-EXT-INV-{suffix}-{chain_suffix}',
                'sync_status': 'synced',
                'sync_log': '\u6837\u4f8b\u53d1\u7968',
            },
        )
        invoice_line, _ = RevenueInvoiceLine.objects.update_or_create(
            invoice=invoice,
            line_no=1,
            defaults={
                'external_line_id': f'{PREFIX}-INVLINE-{suffix}-{chain_suffix}',
                'item_name': contract_line.charge_item,
                'amount': amount,
            },
        )
        mapping, _ = RevenueInvoiceMapping.objects.update_or_create(
            receivable_line=receivable_line,
            invoice_line=invoice_line,
            defaults={
                'mapped_amount': amount,
                'status': 'active',
                'operator': '\u6837\u4f8b\u7ecf\u529e\u4eba',
                'approval_batch_no': f'{PREFIX}-MAP-{suffix}-{chain_suffix}',
            },
        )
        if receipt_amount > 0:
            receipt, _ = RevenueReceipt.objects.update_or_create(
                bank_flow_no=f'{PREFIX}-BANK-{suffix}-{chain_suffix}',
                defaults={
                    'customer': contract.customer,
                    'receipt_date': receivable_date + timedelta(days=15),
                    'amount': receipt_amount,
                    'allocated_total': d('0'),
                    'unallocated_amount': receipt_amount,
                    'payer_name': contract.customer.name,
                    'status': 'unmatched',
                    'source_system': 'BANK_FLOW',
                    'external_id': f'{PREFIX}-EXT-BANK-{suffix}-{chain_suffix}',
                    'sync_status': 'synced',
                    'sync_log': '\u6837\u4f8b\u94f6\u884c\u56de\u6b3e',
                },
            )
            RevenueReceiptAllocation.objects.update_or_create(
                receipt=receipt,
                receivable_line=receivable_line,
                defaults={
                    'invoice_mapping': mapping,
                    'allocated_amount': min(receipt_amount, amount),
                    'allocation_type': 'direct_receipt',
                    'status': 'active',
                    'operator': '\u6837\u4f8b\u7ecf\u529e\u4eba',
                    'approval_batch_no': f'{PREFIX}-RCPT-ALLOC-{suffix}-{chain_suffix}',
                },
            )
            receipt.update_totals()
            bill.receipted_amount = receipt.allocated_total
            bill.receipt_status = 'fully_paid' if receipt.allocated_total >= bill.net_amount else 'partially_paid'
            bill.save(update_fields=['receipted_amount', 'receipt_status'])
        return receivable_line

    def _create_orders(self, contracts):
        contract_ids = [contract.pk for contract, _project, _suffix in contracts]
        groups = {}
        for line in RevenueContractLine.objects.filter(
            contract_id__in=contract_ids
        ).select_related('contract', 'project'):
            order_code = (line.order_id or '').strip()
            if not order_code:
                continue
            key = (line.contract_id, line.project_id, order_code)
            group = groups.setdefault(key, {'lines': [], 'amount': d('0')})
            group['lines'].append(line)
            group['amount'] += line.unit_price * line.quantity

        for (contract_id, project_id, order_code), group in groups.items():
            start_date = min(line.valid_from for line in group['lines'])
            end_date = (
                None
                if any(line.valid_to is None for line in group['lines'])
                else max(line.valid_to for line in group['lines'])
            )
            order, _ = RevenueOrder.objects.update_or_create(
                contract_id=contract_id,
                project_id=project_id,
                order_code=order_code,
                defaults={
                    'name': f'样例订单 {order_code}',
                    'amount': group['amount'],
                    'start_date': start_date,
                    'end_date': end_date,
                    'status': 'executing',
                    'source_system': SOURCE_SYSTEM,
                    'external_id': order_code,
                },
            )
            RevenueContractLine.objects.filter(
                pk__in=[line.pk for line in group['lines']]
            ).update(revenue_order=order)

    def _create_stage_line_and_rule(self, contract, project, version, suffix, stage_suffix, charge_item, amount, trigger_event, planned_date):
        contract_line, _ = RevenueContractLine.objects.update_or_create(
            contract=contract,
            order_id=f'{PREFIX}-STAGE-{suffix}-{stage_suffix}',
            defaults={
                'contract_version': version,
                'project': project,
                'product_category': 'construction',
                'charge_item': charge_item,
                'unit_price': amount,
                'quantity': d('1'),
                'unit': '\u9879',
                'valid_from': planned_date,
                'valid_to': planned_date,
                'status': 'active',
            },
        )
        rule, _ = RevenueBillingRule.objects.update_or_create(
            contract_line=contract_line,
            defaults={
                'contract_version': version,
                'rule_type': 'milestone',
                'trigger_event': trigger_event,
                'billing_cycle': '',
                'billing_direction': '',
                'bill_generation_day': None,
                'proration_rule': 'none',
                'rounding_precision': '2',
                'is_active': True,
                'status': 'effective',
            },
        )
        return contract_line, rule

    def _create_milestone_contract_chain(self, contract, project, version, suffix):
        stages = [
            ('01', '\u9879\u76ee\u542f\u52a8\u6b3e', d('90000.00'), 'activation', date(2026, 3, 15), '2026-03', d('90000.00')),
            ('02', '\u4ea4\u4ed8\u9a8c\u6536\u6b3e', d('150000.00'), 'acceptance', date(2026, 7, 20), '2026-07', d('60000.00')),
            ('03', '\u8d28\u4fdd\u5c3e\u6b3e', d('60000.00'), 'delivery', date(2026, 11, 20), None, d('0')),
        ]
        for stage_suffix, charge_item, amount, trigger_event, planned_date, period, receipt_amount in stages:
            contract_line, rule = self._create_stage_line_and_rule(
                contract, project, version, suffix, stage_suffix, charge_item, amount, trigger_event, planned_date
            )
            if period:
                self._create_receivable_chain(
                    contract, project, contract_line, rule, suffix, stage_suffix, period, planned_date, amount, receipt_amount
                )
        RevenueSyncLog.objects.update_or_create(
            external_id=f'{PREFIX}-SYNC-{suffix}',
            defaults={
                'source_system': SOURCE_SYSTEM,
                'entity_type': 'RevenueContract',
                'entity_id': str(contract.pk),
                'sync_direction': 'INBOUND',
                'sync_status': 'success',
                'request_payload': {'contract_code': contract.contract_code, 'sample': True, 'scenario': 'milestone'},
                'response_payload': {'status': 'ok'},
                'error_message': '',
            },
        )

    def _create_hybrid_contract_chain(self, contract, project, version, suffix):
        stage_line, stage_rule = self._create_stage_line_and_rule(
            contract,
            project,
            version,
            suffix,
            '01',
            '\u5efa\u8bbe\u5f00\u901a\u4e00\u6b21\u6027\u8d39\u7528',
            d('180000.00'),
            'activation',
            date(2026, 3, 10),
        )
        self._create_receivable_chain(
            contract, project, stage_line, stage_rule, suffix, '01', '2026-03', date(2026, 3, 10), d('180000.00'), d('180000.00')
        )
        recurring_line, _ = RevenueContractLine.objects.update_or_create(
            contract=contract,
            order_id=f'{PREFIX}-RECUR-{suffix}-02',
            defaults={
                'contract_version': version,
                'project': project,
                'product_category': 'maintenance',
                'charge_item': '\u56ed\u533a\u8fd0\u7ef4\u670d\u52a1\u6708\u8d39',
                'unit_price': d('45000.00'),
                'quantity': d('1'),
                'unit': '\u6708',
                'valid_from': date(2026, 4, 1),
                'valid_to': date(2027, 3, 31),
                'status': 'active',
            },
        )
        recurring_rule, _ = RevenueBillingRule.objects.update_or_create(
            contract_line=recurring_line,
            defaults={
                'contract_version': version,
                'rule_type': 'recurring',
                'trigger_event': '',
                'billing_cycle': 'month',
                'billing_direction': 'postpay',
                'bill_generation_day': 25,
                'proration_rule': 'actual_days',
                'rounding_precision': '2',
                'is_active': True,
                'status': 'effective',
            },
        )
        self._create_receivable_chain(
            contract, project, recurring_line, recurring_rule, suffix, '02', '2026-04', date(2026, 4, 25), d('45000.00'), d('20000.00')
        )
        RevenueSyncLog.objects.update_or_create(
            external_id=f'{PREFIX}-SYNC-{suffix}',
            defaults={
                'source_system': SOURCE_SYSTEM,
                'entity_type': 'RevenueContract',
                'entity_id': str(contract.pk),
                'sync_direction': 'INBOUND',
                'sync_status': 'success',
                'request_payload': {'contract_code': contract.contract_code, 'sample': True, 'scenario': 'hybrid'},
                'response_payload': {'status': 'ok'},
                'error_message': '',
            },
        )

