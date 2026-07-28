from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils.translation import gettext_lazy as _
from netbox.forms import (
    NetBoxModelBulkEditForm,
    NetBoxModelFilterSetForm,
    NetBoxModelForm,
    NetBoxModelImportForm,
)
from tenancy.forms import ContactModelFilterForm, TenancyFilterForm
from tenancy.models import Tenant
from utilities.forms import BOOLEAN_WITH_BLANK_CHOICES
from utilities.forms.fields import (
    ColorField,
    CommentField,
    ContentTypeChoiceField,
    CSVChoiceField,
    CSVContentTypeField,
    CSVModelChoiceField,
    CSVModelMultipleChoiceField,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
    SlugField,
    TagFilterField,
)
from utilities.forms.widgets import DatePicker, HTMXSelect

from .constants import ASSIGNEMENT_MODELS, SERVICE_PROVIDER_MODELS


from .models import (
    AccountingDimension,
    AccountingDimensionStatusChoices,
    Contract,
    ContractAssignment,
    ContractType,
    CurrencyChoices,
    InternalEntityChoices,
    Invoice,
    InvoiceLine,
    ServiceProvider,
    StatusChoices,
    InvoiceStatusChoices,
)

plugin_settings = settings.PLUGINS_CONFIG['netbox_contract']
User = get_user_model()


# Contract


class ContractForm(NetBoxModelForm):
    comments = CommentField(label=_('Comments'))

    external_party_object = DynamicModelChoiceField(
        queryset=ServiceProvider.objects.all(),
        selector=True,
        label=_('External party object')
    )
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True, label=_('Tenant'))
    parent = DynamicModelChoiceField(
        queryset=Contract.objects.all(),
        required=False,
        selector=True,
        label=_('Parent'),
    )
    contract_type = DynamicModelChoiceField(
        queryset=ContractType.objects.all(), required=False, selector=True, label=_('Contract type')
    )
    compliance_manager = DynamicModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        selector=True,
        label=_('Compliance Manager'),
        help_text=_('compliance manager'),
    )

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial', None)
        super().__init__(*args, **kwargs)

        # Initialize the external party object
        if self.instance.pk:
            self.fields['external_party_object'].initial = self.instance.external_party_object

        # Initialise fields settings
        mandatory_fields = plugin_settings.get('mandatory_contract_fields')
        for field in mandatory_fields:
            if field in self.fields:
                self.fields[field].required = True
        hidden_fields = plugin_settings.get('hidden_contract_fields')
        for field in hidden_fields:
            if field in self.fields and not self.fields[field].required:
                self.fields[field].widget = forms.HiddenInput()

    class Meta:
        model = Contract
        fields = (
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
            'notice_period',
            'mrc',
            'nrc',
            'invoice_frequency',
            'compliance_manager',
            'parent',
            'documents',
            'comments',
            'tags',
        )

        widgets = {
            'start_date': DatePicker(),
            'end_date': DatePicker(),
        }

    def clean(self):
        super().clean()


class ContractFilterForm(ContactModelFilterForm, TenancyFilterForm, NetBoxModelFilterSetForm):
    model = Contract

    number = forms.CharField(required=False, label=_('Number'))
    contract_type = DynamicModelChoiceField(
        queryset=ContractType.objects.all(),
        required=False,
        selector=True,
        label=_('Contract type'),
    )
    external_reference = forms.CharField(required=False, label=_('External reference'))
    internal_party = forms.ChoiceField(choices=InternalEntityChoices, required=False, label=_('Internal party'))
    status = forms.ChoiceField(choices=StatusChoices, required=False, label=_('Status'))
    external_party_object = DynamicModelChoiceField(
        queryset=ServiceProvider.objects.all(),
        required=False,
        selector=True,
        query_params={
            'q': '$q'
        },
        label=_('External party'),
    )
    parent = DynamicModelChoiceField(
        queryset=Contract.objects.all(),
        required=False,
        selector=True,
        label=_('Parent'),
    )
    compliance_manager = DynamicModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        selector=True,
        label=_('Compliance Manager'),
    )
    tag = TagFilterField(model)



class ContractCSVForm(NetBoxModelImportForm):
    external_party_object_id = forms.CharField(
        help_text='service provider object name', label=_('External party name')
    )
    tenant = CSVModelChoiceField(
        queryset=Tenant.objects.all(),
        to_field_name='name',
        help_text='Tenant name',
        required=False,
        label=_('Tenant'),
    )
    status = CSVChoiceField(choices=StatusChoices, help_text='Contract status', label=_('Status'))
    parent = CSVModelChoiceField(
        queryset=Contract.objects.all(),
        to_field_name='name',
        help_text='Contract name',
        required=False,
        label=_('Parent'),
    )
    contract_type = CSVModelChoiceField(
        queryset=ContractType.objects.all(),
        to_field_name='name',
        help_text='Contract type name',
        required=False,
        label=_('Contract type'),
    )

    class Meta:
        model = Contract
        fields = [
            'name',
            'number',
            'contract_type',
            'external_party_object_id',
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
        ]

    def clean_external_party_object_id(self):
        name = self.cleaned_data.get('external_party_object_id')
        try:
            external_party_object = ServiceProvider.objects.get(name=name)
        except ServiceProvider.DoesNotExist:
            raise ValidationError(f'ServiceProvider {name} not found')

        return external_party_object.id


class ContractBulkEditForm(NetBoxModelBulkEditForm):
    name = forms.CharField(max_length=100, required=False, label=_('Name'))
    number = forms.CharField(max_length=100, required=False, label=_('Number'))
    contract_type = DynamicModelChoiceField(
        queryset=ContractType.objects.all(),
        required=False,
        selector=True,
        label=_('Contract Type')
    )
    external_reference = forms.CharField(max_length=100, required=False, label=_('External reference'))
    internal_party = forms.ChoiceField(choices=InternalEntityChoices, required=False, label=_('Internal party'))
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True, label=_('Tenant'))
    comments = CommentField(required=False, label=_('Comments'))
    parent = DynamicModelChoiceField(
        queryset=Contract.objects.all(),
        required=False,
        selector=True,
        label=_('Parent'),
    )

    nullable_fields = ('comments',)
    model = Contract


# ContractType


class ContractTypeForm(NetBoxModelForm):
    color = ColorField(label=_('Color'))

    class Meta:
        model = ContractType
        fields = (
            'name',
            'description',
            'color',
            'tags',
        )


class ContractTypeCSVForm(NetBoxModelImportForm):
    name = forms.CharField(max_length=100, label=_('Name'))
    description = CommentField(label=_('Description'))
    color = ColorField(label=_('Color'))

    class Meta:
        model = ContractType
        fields = ['name', 'description', 'color']


class ContractTypeBulkEditForm(NetBoxModelBulkEditForm):
    description = CommentField(label=_('Description'))
    nullable_fields = ('comments',)
    color = ColorField(label=_('Color'), required=False,)
    model = ContractType


class ContractTypeFilterForm(NetBoxModelFilterSetForm):
    model = ContractType
    name = forms.CharField(required=False, label=_('Name'))
    description = CommentField(label=_('Description'))

# Invoice


class InvoiceForm(NetBoxModelForm):
    number = forms.CharField(
        max_length=100,
        help_text=_('Invoice template name will be overriden to _invoice_template_contract name'),
        label=_('Number'),
    )
    contracts = DynamicModelMultipleChoiceField(
        queryset=Contract.objects.all(),
        required=False,
        selector=True,
        label=_('Contracts'),
    )

    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label=_('periodic Amount'),
        help_text=_('一个付款周期的总金额'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialise fields settings
        mandatory_fields = plugin_settings.get('mandatory_invoice_fields')
        for field in mandatory_fields:
            if field in self.fields:
                self.fields[field].required = True
        hidden_fields = plugin_settings.get('hidden_invoice_fields')
        for field in hidden_fields:
            if field in self.fields and not self.fields[field].required:
                self.fields[field].widget = forms.HiddenInput()

    def clean(self):
        super().clean()

        # template checks
        if self.cleaned_data['template']:
            # Check that there is only one invoice template per contract
            contracts = self.cleaned_data['contracts']
            for contract in contracts:
                for invoice in contract.invoices.all():
                    if invoice.template and invoice.pk != self.instance.pk:
                        raise ValidationError('Only one invoice template allowed per contract')

            # Prefix the invoice name with _template
            self.cleaned_data['number'] = '_invoice_template_' + contract.name

            # set the periode start and end date to null
            self.cleaned_data['period_start'] = None
            self.cleaned_data['period_end'] = None

    def save(self, *args, **kwargs):
        is_new = not bool(self.instance.pk)

        instance = super().save(*args, **kwargs)

        if is_new and not self.cleaned_data['template']:
            contracts = self.cleaned_data['contracts']

            for contract in contracts:
                try:
                    template_exists = True
                    invoice_template = Invoice.objects.get(template=True, contracts=contract)
                except ObjectDoesNotExist:
                    template_exists = False

                if template_exists:
                    first = True
                    for line in invoice_template.invoicelines.all():
                        dimensions = line.accounting_dimensions.all()
                        line.pk = None
                        line.id = None
                        line._state.adding = True
                        line.invoice = self.instance

                        # adjust the first invoice line amount
                        amount = self.cleaned_data['amount']
                        if first and amount != invoice_template.total_invoicelines_amount:
                            line.amount = line.amount + amount - invoice_template.total_invoicelines_amount

                        line.save()

                        for dimension in dimensions:
                            line.accounting_dimensions.add(dimension)
                        first = False

        return instance

    class Meta:
        model = Invoice
        fields = (
            'number',
            'date',
            'contracts',
            'template',
            'status',
            'period_start',
            'period_end',
            'amount',
            'documents',
            'comments',
            'tags',
        )
        widgets = {
            'date': DatePicker(),
            'period_start': DatePicker(),
            'period_end': DatePicker(),
        }


class InvoiceFilterForm(NetBoxModelFilterSetForm):
    model = Invoice
    number = forms.CharField(
        required=False,
        label=_('Number'),
    )
    template = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
        label=_('Template'),
    )
    status = forms.ChoiceField(choices=InvoiceStatusChoices, required=False, label=_('Status'))
    contracts = DynamicModelMultipleChoiceField(
        queryset=Contract.objects.all(),
        required=False,
        selector=True,
        label=_('Contracts'),
    )
    accounting_dimensions = DynamicModelMultipleChoiceField(
        queryset=AccountingDimension.objects.all(),
        required=False,
        selector=True,
        label=_('Accounting Dimensions'),
    )

    tag = TagFilterField(model)


class InvoiceCSVForm(NetBoxModelImportForm):
    contracts = CSVModelMultipleChoiceField(
        queryset=Contract.objects.all(),
        to_field_name='name',
        help_text='Related Contracts',
        label=_('Contracts'),
    )
    status = CSVChoiceField(choices=InvoiceStatusChoices, help_text='Invoice status', label=_('Status'))

    class Meta:
        model = Invoice
        fields = [
            'number',
            'date',
            'contracts',
            'template',
            'status',
            'period_start',
            'period_end',
            'amount',
            'documents',
            'comments',
            'tags',
        ]


class InvoiceBulkEditForm(NetBoxModelBulkEditForm):
    number = forms.CharField(max_length=100, required=False, label=_('Number'))
    template = forms.BooleanField(
        required=False,
        label=_('Template'),
        help_text=_('Wether this invoice is a template or not'),
    )
    date = forms.DateField(
        required=False,
        label=_('Date'),
    )
    contracts = DynamicModelMultipleChoiceField(
        queryset=Contract.objects.all(),
        required=False,
        selector=True,
    )
    period_start = forms.DateField(
        required=False,
        label=_('Period start'),
    )
    period_end = forms.DateField(
        required=False,
        label=_('Period end'),
    )
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label=_('Amount'),
        help_text=_('付款周期的总金额'),
    )
    documents = forms.URLField(
        required=False,
        label=_('Documents'),
        help_text=_('URL to the contract documents'),
    )
    comments = CommentField(
        label=_('Comments'),
    )
    nullable_fields = ('comments',)

    model = Invoice


# service Provider forms


class ServiceProviderForm(NetBoxModelForm):
    slug = SlugField(label=_('Slug'))
    comments = CommentField(label=_('Comments'))

    class Meta:
        model = ServiceProvider
        fields = ('name', 'slug', 'portal_url', 'comments', 'tags')


class ServiceProviderFilterForm(ContactModelFilterForm, NetBoxModelFilterSetForm):
    model = ServiceProvider
    name = forms.CharField(required=False, label=_('Name'))
    tag = TagFilterField(model)


class ServiceProviderCSVForm(NetBoxModelImportForm):
    slug = SlugField(label=_('Slug'))
    comments = CommentField(label=_('Comments'))

    class Meta:
        model = ServiceProvider
        fields = ['name', 'slug', 'portal_url', 'comments', 'tags']


class ServiceProviderBulkEditForm(NetBoxModelBulkEditForm):
    name = forms.CharField(max_length=100, required=False, label=_('Name'))
    comments = CommentField(label=_('Comments'))
    nullable_fields = ('comments',)
    model = ServiceProvider


# ContractAssignment


class ContractAssignmentForm(NetBoxModelForm):

    content_type = ContentTypeChoiceField(
        queryset=ContentType.objects.all(),
        limit_choices_to=ASSIGNEMENT_MODELS,
        label=_('object type'),
    )

    contract = DynamicModelChoiceField(
        queryset=Contract.objects.all(),
        selector=True,
        label=_('Contract'))

    class Meta:
        model = ContractAssignment
        fields = ['content_type', 'object_id', 'contract', 'tags']
        # widgets = {
        #     'content_type': forms.HiddenInput(),
        #     'object_id': forms.HiddenInput(),
        # }


class ContractAssignmentFilterForm(NetBoxModelFilterSetForm):
    model = ContractAssignment
    contract = DynamicModelChoiceField(
        queryset=Contract.objects.all(),
        required=False,
        selector=True,
        label=_('Contract'),
    )


class ContractAssignmentImportForm(NetBoxModelImportForm):
    content_type = CSVContentTypeField(
        queryset=ContentType.objects.all(),
        limit_choices_to=ASSIGNEMENT_MODELS,
        help_text='Content Type in the form <app>.<model>',
        label=_('Content type'),
    )
    contract = CSVModelChoiceField(
        queryset=Contract.objects.all(),
        help_text='Contract id',
        label=_('Contract'),
    )

    class Meta:
        model = ContractAssignment
        fields = ['content_type', 'object_id', 'contract', 'tags']


class ContractAssignmentBulkEditForm(NetBoxModelBulkEditForm):
    contract = DynamicModelChoiceField(
        queryset=Contract.objects.all(),
        required=False,
        selector=True,
        label=_('Contract'),
    )
    model = ContractAssignment


# InvoiceLine


class InvoiceLineForm(NetBoxModelForm):
    invoice = DynamicModelChoiceField(
        queryset=Invoice.objects.all(),
        selector=True,
        label=_('Invoice'),
    )
    accounting_dimensions = DynamicModelMultipleChoiceField(
        queryset=AccountingDimension.objects.all(),
        required=False,
        selector=True,
        label=_('Accounting dimensions'),
    )

    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label=_('periodic line Amount'),
        help_text=_('此付款明细项在一个付款周期的金额'),
    )

    def clean(self):
        super().clean()

        # check for duplicate dimensions
        accounting_dimensions = self.cleaned_data['accounting_dimensions']
        dimensions_names = []
        for dimension in accounting_dimensions:
            if dimension.name in dimensions_names:
                raise ValidationError('duplicate accounting dimension')
            else:
                dimensions_names.append(dimension.name)

        # Make sure mandatory dimensions are present
        mandatory_dimensions = plugin_settings.get('mandatory_dimensions')
        for dimension in mandatory_dimensions:
            if dimension not in dimensions_names:
                raise ValidationError(f'dimension {dimension} missing')

    class Meta:
        model = InvoiceLine
        fields = [
            'invoice',
            'amount',
            'accounting_dimensions',
            'comments',
            'tags',
        ]


class InvoiceLineFilterForm(NetBoxModelFilterSetForm):
    model = InvoiceLine
    invoice = DynamicModelChoiceField(
        queryset=Invoice.objects.all(),
        required=False,
        selector=True,
        label=_('Invoice'),
    )
    accounting_dimensions = DynamicModelMultipleChoiceField(
        queryset=AccountingDimension.objects.all(),
        required=False,
        selector=True,
        label=_('Accounting dimensions'),
    )
    tag = TagFilterField(model)


class InvoiceLineImportForm(NetBoxModelImportForm):
    invoice = CSVModelChoiceField(
        queryset=Invoice.objects.all(),
        to_field_name='number',
        help_text='Invoice number',
        label=_('Invoice'),
    )
    accounting_dimensions = CSVModelMultipleChoiceField(
        queryset=AccountingDimension.objects.all(),
        to_field_name='id',
        required=False,
        help_text='accounting dimension id',
        label=_('Accounting dimensions'),
    )

    class Meta:
        model = InvoiceLine
        fields = [
            'invoice',
            'amount',
            'accounting_dimensions',
            'comments',
            'tags',
        ]


class InvoiceLineBulkEditForm(NetBoxModelBulkEditForm):
    invoice = DynamicModelChoiceField(queryset=Invoice.objects.all(), required=False)
    accounting_dimensions = DynamicModelMultipleChoiceField(
        queryset=AccountingDimension.objects.all(),
        required=False,
        selector=True,
        label=_('Accounting dimensions'),
    )
    comments = CommentField(label=_('Comments'))
    nullable_fields = ('comments',)
    model = InvoiceLine


# AccountingDimension


class AccountingDimensionForm(NetBoxModelForm):
    class Meta:
        model = AccountingDimension
        fields = [
            'name',
            'value',
            'status',
            'comments',
            'tags',
        ]


class AccountingDimensionFilterForm(NetBoxModelFilterSetForm):
    model = AccountingDimension

    name = forms.CharField(required=False, label=_('Name'))
    value = forms.CharField(required=False, label=_('Value'))
    status = forms.ChoiceField(
        choices=AccountingDimensionStatusChoices,
        required=False,
        label=_('Status'),
    )


class AccountingDimensionImportForm(NetBoxModelImportForm):
    status = CSVChoiceField(choices=StatusChoices, help_text='Contract status')

    class Meta:
        model = AccountingDimension
        fields = [
            'name',
            'value',
            'status',
            'comments',
            'tags',
        ]


class AccountingDimensionBulkEditForm(NetBoxModelBulkEditForm):
    name = forms.CharField(max_length=20, required=False, label=_('Name'))
    value = forms.CharField(max_length=20, required=False, label=_('Value'))
    comments = CommentField(label=_('Comments'))
    nullable_fields = ('comments',)
    model = AccountingDimension



from .models import (
    RevenueCustomer, RevenueProject, RevenueContract, RevenueContractProject, RevenueOrder, RevenueContractVersion,
    RevenueContractLine, RevenueBillingRule, RevenueBillingSegment, RevenueReceivablePlan,
    RevenueReceivablePlanVersion, RevenueTriggerRecord, RevenueAdjustmentRecord,
    RevenueReceivableBill, RevenueReceivableLine, RevenueInvoice,
    RevenueInvoiceLine, RevenueInvoiceMapping, RevenueReceipt, RevenueReceiptAllocation,
    RevenueSyncLog,
)


class RevenueModelForm(NetBoxModelForm):
    """Apply revenue-only presentation conventions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._localize_framework_labels()

    def _localize_framework_labels(self):
        changelog_field = self.fields.get('changelog_message')
        if changelog_field is not None:
            changelog_field.label = _('变更说明')


_REVENUE_FORM_FIELDS = {
    RevenueCustomer: (
        'name', 'short_name', 'usci', 'finance_code', 'eip_code',
        'customer_type', 'sales_owner', 'business_owner', 'is_risk',
        'address_phone', 'bank_account', 'tags',
    ),
    RevenueProject: (
        'name', 'customer', 'project_manager', 'sales_owner',
        'business_owner', 'project_type', 'status',
        'accumulated_receivable', 'accumulated_invoice',
        'accumulated_receipt', 'tags',
    ),
    RevenueContract: (
        'contract_code', 'name', 'customer', 'contract_type', 'projects',
        'our_party', 'customer_party', 'sign_date', 'start_date', 'end_date',
        'total_amount', 'is_framework', 'status', 'sales_owner',
        'business_owner', 'source_system', 'external_id', 'sync_status',
        'sync_log', 'tags',
    ),
    RevenueContractProject: ('contract', 'project', 'tags'),
    RevenueOrder: (
        'order_code', 'contract', 'project', 'name', 'amount', 'start_date',
        'end_date', 'status', 'source_system', 'external_id', 'tags',
    ),
    RevenueContractVersion: (
        'contract', 'version_code', 'change_type', 'start_date', 'end_date',
        'status', 'tags',
    ),
    RevenueContractLine: (
        'contract', 'contract_version', 'project', 'revenue_order',
        'order_id', 'product_category', 'charge_item', 'unit_price',
        'quantity', 'unit', 'valid_from', 'valid_to', 'status', 'tags',
    ),
    RevenueBillingRule: (
        'contract_line', 'contract_version', 'rule_type', 'trigger_event',
        'trigger_offset_days', 'billing_cycle', 'billing_direction',
        'bill_generation_day', 'proration_rule', 'rounding_precision',
        'is_active', 'status', 'tags',
    ),
    RevenueBillingSegment: (
        'contract_line', 'billing_rule', 'segment_start', 'segment_end',
        'unit_price', 'quantity', 'amount', 'change_trigger',
        'billing_rule_snapshot', 'tags',
    ),
    RevenueReceivablePlan: (
        'plan_code', 'contract', 'contract_line', 'billing_rule',
        'charge_item', 'order_id', 'status', 'tags',
    ),
    RevenueReceivablePlanVersion: (
        'plan', 'version_no', 'trigger_type', 'trigger_event', 'offset_days',
        'planned_date', 'planned_amount', 'effective_from', 'change_reason',
        'is_current', 'tags',
    ),
    RevenueTriggerRecord: (
        'plan', 'billing_rule', 'plan_version', 'trigger_event',
        'actual_trigger_date', 'status', 'source_system', 'external_id',
        'notes', 'tags',
    ),
    RevenueAdjustmentRecord: (
        'plan', 'receivable_line', 'adjustment_type', 'adjustment_date',
        'amount', 'reason', 'source_system', 'external_id', 'status', 'tags',
    ),
    RevenueReceivableBill: (
        'bill_code', 'customer', 'contract', 'project', 'billing_period',
        'receivable_date', 'due_date', 'amount', 'adjusted_amount',
        'net_amount', 'invoiced_amount', 'receipted_amount', 'confirm_status',
        'invoice_status', 'receipt_status', 'ageing_status', 'risk_status',
        'tags',
    ),
    RevenueReceivableLine: (
        'bill', 'contract_line', 'billing_rule', 'receivable_plan',
        'start_date', 'end_date', 'receivable_date', 'due_date', 'amount',
        'adjusted_amount', 'net_amount', 'risk_status', 'idempotent_key',
        'tags',
    ),
    RevenueInvoice: (
        'invoice_code', 'customer', 'invoice_type', 'invoice_date', 'amount',
        'source_system', 'external_id', 'sync_status', 'sync_log', 'tags',
    ),
    RevenueInvoiceLine: (
        'invoice', 'line_no', 'external_line_id', 'item_name', 'amount',
        'tags',
    ),
    RevenueInvoiceMapping: (
        'receivable_line', 'invoice_line', 'mapped_amount', 'status',
        'operator', 'approval_batch_no', 'tags',
    ),
    RevenueReceipt: (
        'customer', 'receipt_date', 'amount', 'allocated_total',
        'unallocated_amount', 'bank_flow_no', 'payer_name', 'status',
        'source_system', 'external_id', 'sync_status', 'sync_log', 'tags',
    ),
    RevenueReceiptAllocation: (
        'receipt', 'receivable_line', 'invoice_mapping', 'allocated_amount',
        'allocation_type', 'status', 'operator', 'approval_batch_no', 'tags',
    ),
    RevenueSyncLog: (
        'source_system', 'entity_type', 'entity_id', 'external_id',
        'sync_direction', 'sync_status', 'request_payload',
        'response_payload', 'error_message', 'tags',
    ),
}

_REVENUE_FORM_MODELS = tuple(_REVENUE_FORM_FIELDS)

for _revenue_model in _REVENUE_FORM_MODELS:
    _meta = type(
        'Meta',
        (),
        {
            'model': _revenue_model,
            'fields': _REVENUE_FORM_FIELDS[_revenue_model],
        },
    )
    globals()[f'{_revenue_model.__name__}Form'] = type(
        f'{_revenue_model.__name__}Form',
        (RevenueModelForm,),
        {'Meta': _meta},
    )
    globals()[f'{_revenue_model.__name__}FilterForm'] = type(
        f'{_revenue_model.__name__}FilterForm',
        (NetBoxModelFilterSetForm,),
        {'model': _revenue_model},
    )


class RevenueOrderForm(RevenueModelForm):
    contract = DynamicModelChoiceField(
        queryset=RevenueContract.objects.all(),
        label='合同',
    )
    project = DynamicModelChoiceField(
        queryset=RevenueProject.objects.all(),
        query_params={'contract_id': '$contract'},
        label='项目',
    )

    class Meta:
        model = RevenueOrder
        fields = _REVENUE_FORM_FIELDS[RevenueOrder]


class RevenueContractLineForm(RevenueModelForm):
    contract = DynamicModelChoiceField(
        queryset=RevenueContract.objects.all(),
        label='合同',
    )
    contract_version = DynamicModelChoiceField(
        queryset=RevenueContractVersion.objects.all(),
        query_params={'contract_id': '$contract'},
        label='合同版本',
    )
    project = DynamicModelChoiceField(
        queryset=RevenueProject.objects.all(),
        query_params={'contract_id': '$contract'},
        label='项目',
    )
    revenue_order = DynamicModelChoiceField(
        queryset=RevenueOrder.objects.all(),
        query_params={
            'contract_id': '$contract',
            'project_id': '$project',
        },
        required=False,
        label='订单/开工单',
        help_text='仅显示所选合同及项目下的订单；原订单号字段仅用于历史数据核对。',
    )

    class Meta:
        model = RevenueContractLine
        fields = _REVENUE_FORM_FIELDS[RevenueContractLine]

class RevenueReceivableGenerationForm(forms.Form):
    billing_period = forms.CharField(
        max_length=7,
        label='\u8d26\u671f',
        help_text='\u683c\u5f0f\uff1aYYYY-MM\uff0c\u4f8b\u5982 2026-07\u3002',
    )
    confirm_status = forms.ChoiceField(
        choices=(('draft', '\u8349\u7a3f'), ('confirmed', '\u5df2\u786e\u8ba4')),
        initial='draft',
        label='\u751f\u6210\u72b6\u6001',
    )

    def clean_billing_period(self):
        value = self.cleaned_data['billing_period']
        try:
            year, month = value.split('-')
            year = int(year)
            month = int(month)
            if month < 1 or month > 12:
                raise ValueError
        except ValueError:
            raise ValidationError('\u8d26\u671f\u683c\u5f0f\u5fc5\u987b\u4e3a YYYY-MM\u3002')
        return f'{year:04d}-{month:02d}'
