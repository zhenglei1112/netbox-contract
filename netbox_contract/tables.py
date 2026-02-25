import django_tables2 as tables

from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
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
            'contract__external_party_object_type',
            'contract__external_party_object',
            'actions',
        )
        default_columns = (
            'id',
            'content_type',
            'content_object',
            'contract',
            'contract__contract_type',
            'contract__external_party_object_type',
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
            'contract__external_party_object_type',
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
    tags = columns.TagColumn(url_name='plugins:netbox_contract:contract_list')
    contract_type = columns.ColoredLabelColumn(verbose_name=_('Contract type'))
    compliance_manager = tables.Column(
        verbose_name=_('Compliance Manager'),
        linkify=True
    )

    class Meta(NetBoxTable.Meta):
        model = Contract
        fields = (
            'pk',
            'id',
            'name',
            'number',
            'contract_type',
            'external_party_object_type',
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
            'actions',
            'compliance_manager',
        )
        default_columns = ('name', 'number', 'status', 'contract_type', 'parent')


class ContractListBottomTable(NetBoxTable):
    name = TruncatedNameColumn(linkify=True)
    external_party_object = tables.Column(linkify=True, verbose_name=_('External party'))
    status = columns.ChoiceFieldColumn(
        verbose_name=_('Status'),
    )

    class Meta(NetBoxTable.Meta):
        model = Contract
        fields = (
            'pk',
            'id',
            'name',
            'external_party_object_type',
            'external_party_object',
            'external_reference',
            'internal_party',
            'status',
            'mrc',
            'comments',
            'actions',
        )
        default_columns = (
            'name',
            'external_party_object_type',
            'external_party_object',
            'status',
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
