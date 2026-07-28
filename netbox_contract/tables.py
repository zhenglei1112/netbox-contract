from datetime import date, datetime
import django_tables2 as tables

from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.db.models import Max
from netbox.tables import NetBoxTable, columns
from tenancy.tables import ContactsColumnMixin

from .models import (
    AccountingDimension,
    Contract,
    ContractAssignment,
    ContractType,
    Invoice,
    InvoiceLine,
    ServiceProvider,
)


class TruncatedNameColumn(tables.Column):
    """
    自定义列类，用于处理长名称的截断和鼠标提示
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs = {
            'td': {
                'title': lambda record: str(record) if record else ''
            }
        }

    def render(self, value, record):
        display_value = str(record)
        if display_value and len(display_value) > 50:
            # 保留前23个字符和后23个字符，中间用...表示
            return format_html(
                '{}...{}',
                display_value[:23],
                display_value[-23:]
            )
        return display_value


class ContractTypeListTable(NetBoxTable):
    name = tables.Column(linkify=True)
    color = columns.ColorColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = ContractType
        fields = ('pk', 'id', 'name', 'description', 'color', 'actions')
        default_columns = ('name', 'description', 'color')


class ContractAssignmentListTable(NetBoxTable):
    id = tables.Column(linkify=True)
    content_type = columns.ContentTypeColumn(verbose_name=_('Object Type'))
    content_object = tables.Column(linkify=True, orderable=False, verbose_name=_('content_Object'))
    contract = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))
    contract__external_party_object = tables.Column(linkify=True, verbose_name=_('external_party_object'))
    tags = columns.TagColumn(url_name='plugins:netbox_contract:contractassignment_list')
    contract__contract_type = columns.ColoredLabelColumn(verbose_name=_('Contract type'))

    class Meta(NetBoxTable.Meta):
        model = ContractAssignment
        fields = (
            'id',
            'content_type',
            'content_object',
            'contract',
            'contract__contract_type',
            'contract__external_party_object',
            'actions',
        )
        default_columns = (
            'id',
            'content_type',
            'content_object',
            'contract',
            'contract__contract_type',
            'contract__external_party_object',
        )


class ContractAssignmentObjectTable(NetBoxTable):
    contract = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))
    contract__external_party_object = tables.Column(
        verbose_name=_('external_party_object'), linkify=True
    )
    contract__status = columns.ChoiceFieldColumn(
        verbose_name=_('Status'),
    )
    contract__contract_type = columns.ColoredLabelColumn(verbose_name=_('Contract type'))
    contract_type = tables.Column(linkify=True, verbose_name=_('Contract type'))

    class Meta(NetBoxTable.Meta):
        model = ContractAssignment
        fields = (
            'pk',
            'contract',
            'contract__external_party_object',
            'contract__status',
            'contract__contract_type',
            'contract__start_date',
            'contract__end_date',
            'contract__mrc',
            'contract__nrc',
            'actions',
        )
        default_columns = (
            'pk',
            'contract',
            'contract__external_party_object',
            'contract__status',
            'contract__contract_type',
            'contract__start_date',
            'contract__end_date',
            'contract__mrc',
            'contract__nrc',
        )


class ContractAssignmentContractTable(NetBoxTable):
    content_type = columns.ContentTypeColumn(verbose_name=_('Object Type'))
    content_object = tables.Column(linkify=True, verbose_name=_('Object'), orderable=False)
    content_object__status = columns.ChoiceFieldColumn(
        verbose_name=_('Status'),
    )
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = ContractAssignment
        fields = (
            'pk',
            'content_type',
            'content_object',
            'content_object__status',
            'actions',
        )
        default_columns = (
            'pk',
            'content_type',
            'content_object',
            'content_object__status',
        )


class ContractListTable(ContactsColumnMixin, NetBoxTable):
    name = TruncatedNameColumn(linkify=True)
    external_party_object = tables.Column(verbose_name=_('External party'), linkify=True)
    parent = tables.Column(linkify=True)
    yrc = tables.Column(verbose_name=_('Yerly recuring costs'))
    status = columns.ChoiceFieldColumn(
        verbose_name=_('Status'),
    )
    current_pay_until = tables.DateColumn(verbose_name=_('当前支付到'), format="Y-m-d")
    tags = columns.TagColumn(url_name='plugins:netbox_contract:contract_list')
    contract_type = columns.ColoredLabelColumn(verbose_name=_('Contract type'))
    compliance_manager = tables.Column(
        verbose_name=_('Compliance Manager'),
        linkify=True
    )

    def order_current_pay_until(self, queryset, is_descending):
        queryset = queryset.annotate(
            _current_pay_until=Max('invoices__period_end')
        ).order_by(('-' if is_descending else '') + '_current_pay_until')
        return (queryset, True)

    class Meta(NetBoxTable.Meta):
        model = Contract
        fields = (
            'pk',
            'id',
            'name',
            'number',
            'contract_type',
            'external_party_object',
            'external_reference',
            'internal_party',
            'tenant',
            'status',
            'start_date',
            'end_date',
            'initial_term',
            'renewal_term',
            'mrc',
            'nrc',
            'invoice_frequency',
            'documents',
            'comments',
            'parent',
            'current_pay_until',
            'actions',
            'compliance_manager',
        )
        default_columns = ('name', 'number', 'status', 'contract_type', 'parent', 'current_pay_until')


class ContractListBottomTable(NetBoxTable):
    name = TruncatedNameColumn(linkify=True)
    external_party_object = tables.Column(linkify=True, verbose_name=_('External party'))
    status = columns.ChoiceFieldColumn(
        verbose_name=_('Status'),
    )
    current_pay_until = tables.DateColumn(verbose_name=_('当前支付到'), format="Y-m-d")

    def order_current_pay_until(self, queryset, is_descending):
        queryset = queryset.annotate(
            _current_pay_until=Max('invoices__period_end')
        ).order_by(('-' if is_descending else '') + '_current_pay_until')
        return (queryset, True)

    class Meta(NetBoxTable.Meta):
        model = Contract
        fields = (
            'pk',
            'id',
            'name',
            'external_party_object',
            'external_reference',
            'internal_party',
            'status',
            'mrc',
            'comments',
            'current_pay_until',
            'actions',
        )
        default_columns = (
            'name',
            'external_party_object',
            'status',
            'current_pay_until',
        )


class InvoiceListTable(NetBoxTable):
    contracts = tables.ManyToManyColumn(linkify=True)
    number = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn(
        verbose_name=_('Status'),
    )
    tags = columns.TagColumn(url_name='plugins:netbox_contract:invoiceline_list')
    actions = columns.ActionsColumn(
        extra_buttons="""
            <form method="post" action="{% url 'plugins:netbox_contract:invoice_generate_seal_reason' %}" style="display: inline;">
                {% csrf_token %}
                <input type="hidden" name="contract_name" value="{{ record.contracts.all.0.name|default:'' }}">
                <input type="hidden" name="period_start" value="{{ record.period_start|date:'Y-m-d'|default:'' }}">
                <input type="hidden" name="period_end" value="{{ record.period_end|date:'Y-m-d'|default:'' }}">
                <input type="hidden" name="amount" value="{{ record.amount|default:0 }}">
                <button type="submit" class="btn btn-sm btn-outline-primary" title="用印事由">
                    <i class="mdi mdi-stamper"></i>
                </button>
            </form>
            <form method="post" action="{% url 'plugins:netbox_contract:invoice_generate_eip_summary' %}" style="display: inline;">
                {% csrf_token %}
                <input type="hidden" name="contract_name" value="{{ record.contracts.all.0.name|default:'' }}">
                <input type="hidden" name="period_start" value="{{ record.period_start|date:'Y-m-d'|default:'' }}">
                <input type="hidden" name="period_end" value="{{ record.period_end|date:'Y-m-d'|default:'' }}">
                <button type="submit" class="btn btn-sm btn-outline-info" title="EIP支付摘要">
                    <i class="mdi mdi-file-document"></i>
                </button>
            </form>
        """
    )

    class Meta(NetBoxTable.Meta):
        model = Invoice
        fields = (
            'pk',
            'id',
            'number',
            'date',
            'status',
            'contracts',
            'period_start',
            'period_end',
            'amount',
            'documents',
            'comments',
            'actions',
        )
        default_columns = (
            'number',
            'date',
            'status',
            'contracts',
            'period_start',
            'period_end',
            'amount',
        )


class ServiceProviderListTable(NetBoxTable):
    name = tables.Column(linkify=True)
    tags = columns.TagColumn(url_name='plugins:netbox_contract:serviceprovider_list')

    class Meta(NetBoxTable.Meta):
        model = ServiceProvider
        fields = ('pk', 'name', 'slug', 'portal_url')
        default_columns = ('name', 'portal_url')


class InvoiceLineListTable(NetBoxTable):
    invoice = tables.Column(linkify=True)
    accounting_dimensions = tables.ManyToManyColumn(linkify_item=True, filter=lambda qs: qs.order_by('name'))
    tags = columns.TagColumn(url_name='plugins:netbox_contract:invoiceline_list')

    class Meta(NetBoxTable.Meta):
        model = InvoiceLine
        fields = (
            'pk',
            'invoice',
            'amount',
            'accounting_dimensions',
            'comments',
        )
        default_columns = (
            'pk',
            'invoice',
            'amount',
            'accounting_dimensions',
            'comments',
        )


class AccountingDimensionListTable(NetBoxTable):
    name = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn(
        verbose_name=_('Status'),
    )
    tags = columns.TagColumn(url_name='plugins:netbox_contract:accountingdimension_list')

    class Meta(NetBoxTable.Meta):
        model = AccountingDimension
        fields = (
            'pk',
            'name',
            'value',
            'comments',
            'status',
        )
        default_columns = (
            'name',
            'value',
            'comments',
            'status',
        )

from .models import (
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
)



REVENUE_DISPLAY_VALUE_MAP = {
    'billing_cycle': {
        'month': '月度',
        'quarter': '季度',
        'year': '年度',
    },
    'billing_direction': {
        'postpay': '后付',
        'prepay': '预付',
    },
    'proration_rule': {
        'actual_days': '按实际天数',
        'full_month': '按整月',
        'none': '不折算',
    },
    'rounding_precision': {
        '0': '保留0位',
        '1': '保留1位',
        '2': '保留2位',
    },
    'trigger_event': {
        'activation': '开通',
        'acceptance': '验收',
        'delivery': '交付',
    },
    'change_trigger': {
        'normal': '正常计费',
        'contract_change': '合同变更',
        'price_change': '价格调整',
    },
    'source_system': {
        'SAMPLE_DATA': '样例数据',
        'REVENUE_SYS': '收入系统',
        'BANK_FLOW': '银行流水',
    },
}

REVENUE_BOOLEAN_FIELDS = {'is_risk', 'is_framework', 'is_active', 'is_current'}


def render_revenue_display_value(value, column_name=None, **kwargs):
    if column_name in REVENUE_BOOLEAN_FIELDS or isinstance(value, bool):
        return '是' if value else '否'
    if column_name in REVENUE_DISPLAY_VALUE_MAP:
        return REVENUE_DISPLAY_VALUE_MAP[column_name].get(value, value)
    return value


def make_revenue_display_renderer(column_name):
    def _render(value, **kwargs):
        return render_revenue_display_value(value, column_name=column_name)
    return _render


def make_revenue_choice_renderer(choice_map):
    def _render(value, **kwargs):
        return choice_map.get(value, value)
    return _render


class RevenueCustomerListTable(NetBoxTable):
    name = tables.Column(linkify=True)
    customer_type = columns.ChoiceFieldColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueCustomer
        fields = ('pk', 'name', 'short_name', 'usci', 'customer_type', 'sales_owner', 'business_owner', 'is_risk', 'actions')
        default_columns = ('name', 'short_name', 'customer_type', 'sales_owner', 'business_owner')


class RevenueProjectListTable(NetBoxTable):
    name = tables.Column(linkify=True)
    customer = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueProject
        fields = ('pk', 'name', 'customer', 'project_type', 'status', 'sales_owner', 'business_owner', 'actions')
        default_columns = ('name', 'customer', 'project_type', 'status')


class RevenueContractListTable(NetBoxTable):
    contract_code = tables.Column(linkify=True)
    customer = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueContract
        fields = ('pk', 'contract_code', 'name', 'customer', 'contract_type', 'status', 'start_date', 'end_date', 'total_amount', 'actions')
        default_columns = ('contract_code', 'name', 'customer', 'contract_type', 'status', 'total_amount')


class RevenueContractProjectListTable(NetBoxTable):
    contract = tables.Column(linkify=True)
    project = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueContractProject
        fields = ('pk', 'contract', 'project', 'actions')
        default_columns = ('contract', 'project')


class RevenueOrderListTable(NetBoxTable):
    order_code = tables.Column(linkify=True)
    contract = tables.Column(linkify=True)
    project = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueOrder
        fields = (
            'pk', 'order_code', 'contract', 'project', 'name', 'amount', 'start_date',
            'end_date', 'status', 'source_system', 'external_id', 'actions',
        )
        default_columns = ('order_code', 'contract', 'project', 'amount', 'start_date', 'end_date', 'status')

class RevenueContractVersionListTable(NetBoxTable):
    contract = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueContractVersion
        fields = ('pk', 'contract', 'version_code', 'change_type', 'start_date', 'end_date', 'status', 'actions')
        default_columns = ('contract', 'version_code', 'change_type', 'start_date', 'status')


class RevenueContractLineListTable(NetBoxTable):
    contract = tables.Column(linkify=True)
    project = tables.Column(linkify=True)
    revenue_order = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueContractLine
        fields = ('pk', 'contract', 'project', 'revenue_order', 'order_id', 'charge_item', 'unit_price', 'quantity', 'unit', 'status', 'actions')
        default_columns = ('contract', 'project', 'revenue_order', 'charge_item', 'unit_price', 'quantity', 'status')


class RevenueBillingRuleListTable(NetBoxTable):
    contract_line = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueBillingRule
        fields = ('pk', 'contract_line', 'rule_type', 'billing_cycle', 'billing_direction', 'bill_generation_day', 'trigger_event', 'trigger_offset_days', 'status', 'actions')
        default_columns = ('contract_line', 'rule_type', 'billing_cycle', 'billing_direction', 'trigger_event', 'trigger_offset_days', 'status')


class RevenueBillingSegmentListTable(NetBoxTable):
    contract_line = tables.Column(linkify=True)
    billing_rule = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueBillingSegment
        fields = ('pk', 'contract_line', 'billing_rule', 'segment_start', 'segment_end', 'amount', 'change_trigger', 'actions')
        default_columns = ('contract_line', 'segment_start', 'segment_end', 'amount')


class RevenueReceivablePlanListTable(NetBoxTable):
    plan_code = tables.Column(linkify=True)
    contract = tables.Column(linkify=True)
    contract_line = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueReceivablePlan
        fields = ('pk', 'plan_code', 'contract', 'contract_line', 'billing_rule', 'charge_item', 'order_id', 'status', 'actions')
        default_columns = ('plan_code', 'contract', 'charge_item', 'order_id', 'status')


class RevenueReceivablePlanVersionListTable(NetBoxTable):
    plan = tables.Column(linkify=True)
    trigger_type = columns.ChoiceFieldColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueReceivablePlanVersion
        fields = ('pk', 'plan', 'version_no', 'trigger_type', 'trigger_event', 'offset_days', 'planned_date', 'planned_amount', 'effective_from', 'is_current', 'actions')
        default_columns = ('plan', 'version_no', 'trigger_type', 'planned_date', 'planned_amount', 'is_current')


class RevenueTriggerRecordListTable(NetBoxTable):
    plan = tables.Column(linkify=True)
    billing_rule = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueTriggerRecord
        fields = ('pk', 'billing_rule', 'plan', 'plan_version', 'trigger_event', 'actual_trigger_date', 'status', 'source_system', 'external_id', 'actions')
        default_columns = ('billing_rule', 'trigger_event', 'actual_trigger_date', 'status', 'source_system')


class RevenueAdjustmentRecordListTable(NetBoxTable):
    plan = tables.Column(linkify=True)
    receivable_line = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueAdjustmentRecord
        fields = ('pk', 'plan', 'receivable_line', 'adjustment_type', 'adjustment_date', 'amount', 'reason', 'source_system', 'status', 'actions')
        default_columns = ('plan', 'receivable_line', 'adjustment_type', 'adjustment_date', 'amount', 'status')

class RevenueReceivableBillListTable(NetBoxTable):
    bill_code = tables.Column(linkify=True)
    customer = tables.Column(linkify=True)
    contract = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueReceivableBill
        fields = ('pk', 'bill_code', 'customer', 'contract', 'billing_period', 'amount', 'net_amount', 'invoiced_amount', 'receipted_amount', 'confirm_status', 'actions')
        default_columns = ('bill_code', 'customer', 'contract', 'billing_period', 'net_amount', 'confirm_status')


class RevenueReceivableLineListTable(NetBoxTable):
    bill = tables.Column(linkify=True)
    contract_line = tables.Column(linkify=True)
    receivable_plan = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueReceivableLine
        fields = ('pk', 'bill', 'contract_line', 'billing_rule', 'receivable_plan', 'start_date', 'end_date', 'receivable_date', 'due_date', 'amount', 'adjusted_amount', 'net_amount', 'risk_status', 'actions')
        default_columns = ('bill', 'contract_line', 'receivable_plan', 'start_date', 'end_date', 'net_amount')


class RevenueInvoiceListTable(NetBoxTable):
    invoice_code = tables.Column(linkify=True)
    customer = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueInvoice
        fields = ('pk', 'invoice_code', 'customer', 'invoice_type', 'invoice_date', 'amount', 'source_system', 'actions')
        default_columns = ('invoice_code', 'customer', 'invoice_type', 'invoice_date', 'amount')


class RevenueInvoiceLineListTable(NetBoxTable):
    invoice = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueInvoiceLine
        fields = ('pk', 'invoice', 'line_no', 'item_name', 'amount', 'actions')
        default_columns = ('invoice', 'line_no', 'item_name', 'amount')


class RevenueInvoiceMappingListTable(NetBoxTable):
    receivable_line = tables.Column(linkify=True)
    invoice_line = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueInvoiceMapping
        fields = ('pk', 'receivable_line', 'invoice_line', 'mapped_amount', 'status', 'approval_batch_no', 'actions')
        default_columns = ('receivable_line', 'invoice_line', 'mapped_amount', 'status')


class RevenueReceiptListTable(NetBoxTable):
    bank_flow_no = tables.Column(linkify=True)
    customer = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueReceipt
        fields = ('pk', 'bank_flow_no', 'customer', 'receipt_date', 'amount', 'allocated_total', 'unallocated_amount', 'status', 'actions')
        default_columns = ('bank_flow_no', 'customer', 'receipt_date', 'amount', 'status')


class RevenueReceiptAllocationListTable(NetBoxTable):
    receipt = tables.Column(linkify=True)
    receivable_line = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = RevenueReceiptAllocation
        fields = ('pk', 'receipt', 'receivable_line', 'invoice_mapping', 'allocated_amount', 'allocation_type', 'status', 'actions')
        default_columns = ('receipt', 'receivable_line', 'allocated_amount', 'allocation_type', 'status')


class RevenueSyncLogListTable(NetBoxTable):
    id = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('delete',))

    class Meta(NetBoxTable.Meta):
        model = RevenueSyncLog
        fields = ('pk', 'id', 'source_system', 'entity_type', 'entity_id', 'sync_direction', 'sync_status', 'created', 'actions')
        default_columns = ('id', 'source_system', 'entity_type', 'sync_direction', 'sync_status', 'created')



def _apply_revenue_table_headers():
    headers = {
        RevenueCustomerListTable: {
            'name': '名称', 'customer_type': '客户类型', 'actions': '操作',
        },
        RevenueProjectListTable: {
            'name': '名称', 'customer': '客户', 'status': '状态', 'actions': '操作',
        },
        RevenueContractListTable: {
            'contract_code': '合同编号', 'customer': '客户', 'status': '状态', 'actions': '操作',
        },
        RevenueContractProjectListTable: {
            'contract': '合同', 'project': '项目', 'actions': '操作',
        },
        RevenueOrderListTable: {
            'order_code': '订单/开工单编号', 'contract': '合同', 'project': '项目', 'status': '状态', 'actions': '操作',
        },
        RevenueContractVersionListTable: {
            'contract': '合同', 'status': '状态', 'actions': '操作',
        },
        RevenueContractLineListTable: {
            'contract': '合同', 'project': '项目', 'status': '状态', 'actions': '操作',
        },
        RevenueBillingRuleListTable: {
            'contract_line': '合同项', 'actions': '操作',
        },
        RevenueBillingSegmentListTable: {
            'contract_line': '合同项', 'billing_rule': '计费规则', 'actions': '操作',
        },
        RevenueReceivablePlanListTable: {
            'plan_code': '计划编号', 'contract': '合同', 'contract_line': '合同项', 'status': '状态', 'actions': '操作',
        },
        RevenueReceivablePlanVersionListTable: {
            'plan': '应收计划', 'trigger_type': '触发方式', 'actions': '操作',
        },
        RevenueTriggerRecordListTable: {
            'plan': '应收计划', 'status': '状态', 'actions': '操作',
        },
        RevenueAdjustmentRecordListTable: {
            'plan': '应收计划', 'receivable_line': '应收明细', 'status': '状态', 'actions': '操作',
        },
        RevenueReceivableBillListTable: {
            'bill_code': '应收账单编号', 'customer': '客户', 'contract': '合同', 'actions': '操作',
        },
        RevenueReceivableLineListTable: {
            'bill': '应收账单', 'contract_line': '合同项', 'actions': '操作',
        },
        RevenueInvoiceListTable: {
            'invoice_code': '发票号码', 'customer': '客户', 'actions': '操作',
        },
        RevenueInvoiceLineListTable: {
            'invoice': '发票', 'actions': '操作',
        },
        RevenueInvoiceMappingListTable: {
            'receivable_line': '应收明细', 'invoice_line': '发票明细', 'actions': '操作',
        },
        RevenueReceiptListTable: {
            'bank_flow_no': '银行流水号', 'customer': '客户', 'actions': '操作',
        },
        RevenueReceiptAllocationListTable: {
            'receipt': '\u56de\u6b3e', 'receivable_line': '\u5e94\u6536\u660e\u7ec6', 'actions': '\u64cd\u4f5c',
        },
        RevenueSyncLogListTable: {
            'id': 'ID', 'actions': '操作',
        },
    }
    for table, names in headers.items():
        for column_name, label in names.items():
            if column_name in table.base_columns:
                table.base_columns[column_name].verbose_name = _(label)



def _format_chinese_date(value):
    if not value:
        return '-'
    return f'{value.year}年{value.month}月{value.day}日'


def _format_chinese_datetime(value):
    if not value:
        return '-'
    if isinstance(value, datetime):
        return f'{value.year}年{value.month}月{value.day}日 {value.hour}时{value.minute}分'
    if isinstance(value, date):
        return _format_chinese_date(value)
    return value

REVENUE_TABLES = (
    RevenueCustomerListTable, RevenueProjectListTable, RevenueContractListTable,
    RevenueContractProjectListTable, RevenueOrderListTable, RevenueContractVersionListTable, RevenueContractLineListTable,
    RevenueBillingRuleListTable, RevenueBillingSegmentListTable, RevenueReceivablePlanListTable,
    RevenueReceivablePlanVersionListTable, RevenueTriggerRecordListTable,
    RevenueAdjustmentRecordListTable, RevenueReceivableBillListTable, RevenueReceivableLineListTable,
    RevenueInvoiceListTable, RevenueInvoiceLineListTable, RevenueInvoiceMappingListTable,
    RevenueReceiptListTable, RevenueReceiptAllocationListTable, RevenueSyncLogListTable,
)


def _apply_revenue_datetime_formats():
    date_fields = {
        'sign_date', 'start_date', 'end_date', 'valid_from', 'valid_to',
        'segment_start', 'segment_end', 'planned_date', 'effective_from',
        'actual_trigger_date', 'adjustment_date', 'receivable_date', 'due_date',
        'invoice_date', 'receipt_date',
    }
    datetime_fields = {'created', 'last_updated'}
    for table in REVENUE_TABLES:
        for column_name, column in table.base_columns.items():
            if column_name in date_fields:
                column.render = _format_chinese_date
            elif column_name in datetime_fields:
                column.render = _format_chinese_datetime


def _apply_revenue_display_renderers():
    display_fields = set(REVENUE_DISPLAY_VALUE_MAP) | REVENUE_BOOLEAN_FIELDS
    for table in REVENUE_TABLES:
        model = table.Meta.model
        for column_name, column in table.base_columns.items():
            if column_name in display_fields:
                column.render = make_revenue_display_renderer(column_name)
                continue
            if isinstance(column, columns.ChoiceFieldColumn):
                continue
            try:
                field = model._meta.get_field(column_name)
            except Exception:
                continue
            choices = getattr(field, 'flatchoices', None) or getattr(field, 'choices', None)
            if choices:
                choice_map = {key: label for key, label in choices}
                column.render = make_revenue_choice_renderer(choice_map)


_apply_revenue_table_headers()
_apply_revenue_datetime_formats()
