import django_filters
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from netbox.filtersets import NetBoxModelFilterSet
from tenancy.filtersets import ContactModelFilterSet, TenancyFilterSet

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


class ContractFilterSet(ContactModelFilterSet, NetBoxModelFilterSet, TenancyFilterSet):
    status = django_filters.MultipleChoiceFilter(choices=StatusChoices, null_value=None)
    internal_party = django_filters.MultipleChoiceFilter(
        choices=InternalEntityChoices, null_value=None
    )
    external_party_object = django_filters.ModelChoiceFilter(
        queryset=ServiceProvider.objects.all(),
        method='filter_external_party_object',
        label=_('External party')
    )
    compliance_manager = django_filters.ModelChoiceFilter(
        queryset=get_user_model().objects.all(),
        label=_('Compliance Manager')
    )

    class Meta:
        model = Contract
        fields = (
            'id',
            'name',
            'number',
            'contract_type',
            'external_reference',
            'start_date',
            'end_date',
            'initial_term',
            'parent',
            'compliance_manager',
        )

    def search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value)
            | Q(number__icontains=value)
            | Q(external_reference__icontains=value)
            | Q(comments__icontains=value),
#            Q(status__iexact='Active'),
        )

    def filter_external_party_object(self, queryset, name, value):
        """
        根据外部参与方筛选合同
        """
        if not value:
            return queryset
        
        # 获取外部参与方的ContentType
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(value)
        
        # 筛选匹配的合同
        return queryset.filter(
            external_party_object_type=content_type,
            external_party_object_id=value.id
        )



class InvoiceFilterSet(NetBoxModelFilterSet):
    status = django_filters.MultipleChoiceFilter(choices=InvoiceStatusChoices, null_value=None)
    accounting_dimensions = django_filters.ModelChoiceFilter(
        field_name='invoicelines__accounting_dimensions',
        queryset=AccountingDimension.objects.all(),
        label='Accounting Dimension'
    )

    class Meta:
        model = Invoice
        fields = (
            'id',
            'number',
            'template',
            'date',
            'contracts',
            'period_start',
            'period_end',
            'amount',
        )

    def search(self, queryset, name, value):
        return queryset.filter(
            Q(number__icontains=value) | Q(contracts__name__icontains=value)
        )


class ServiceProviderFilterSet(ContactModelFilterSet, NetBoxModelFilterSet):
    class Meta:
        model = ServiceProvider
        fields = ('id', 'name')

    def search(self, queryset, name, value):
        return queryset.filter(name__icontains=value)


class ContractTypeFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = ContractType
        fields = ('name', 'description', 'color')

    def search(self, queryset, name, value):
        return queryset.filter(name__icontains=value)


class ContractAssignmentFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = ContractAssignment
        fields = ('id', 'contract')

    def search(self, queryset, name, value):
        return queryset.filter(Q(contract__name__icontains=value))


class InvoiceLineFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = InvoiceLine
        fields = ('id', 'invoice', 'accounting_dimensions')

    def search(self, queryset, name, value):
        return queryset.filter(
            Q(comments__icontains=value) | Q(invoice__number__icontains=value)
        )


class AccountingDimensionFilterSet(NetBoxModelFilterSet):
    status = django_filters.MultipleChoiceFilter(
        choices=AccountingDimensionStatusChoices, null_value=None
    )

    class Meta:
        model = AccountingDimension
        fields = ('name', 'value')

    def search(self, queryset, name, value):
        return queryset.filter(Q(comments__icontains=value) | Q(name__icontains=value))

from .models import (
    RevenueCustomer, RevenueProject, RevenueContract, RevenueContractProject, RevenueOrder, RevenueContractVersion,
    RevenueContractLine, RevenueBillingRule, RevenueBillingSegment, RevenueReceivablePlan,
    RevenueReceivablePlanVersion, RevenueTriggerRecord, RevenueAdjustmentRecord,
    RevenueReceivableBill, RevenueReceivableLine, RevenueInvoice,
    RevenueInvoiceLine, RevenueInvoiceMapping, RevenueReceipt, RevenueReceiptAllocation,
    RevenueSyncLog,
)


class RevenueCustomerFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = RevenueCustomer
        fields = ('id', 'name', 'short_name', 'usci', 'customer_type', 'sales_owner', 'business_owner', 'is_risk')

    def search(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(short_name__icontains=value) | Q(usci__icontains=value))


class RevenueProjectFilterSet(NetBoxModelFilterSet):
    contract_id = django_filters.NumberFilter(method='filter_contract_id')
    class Meta:
        model = RevenueProject
        fields = ('id', 'name', 'customer', 'project_type', 'status', 'sales_owner', 'business_owner')

    def filter_contract_id(self, queryset, name, value):
        return queryset.filter(
            Q(project_contracts__contract_id=value) | Q(contract_lines__contract_id=value)
        ).distinct()

    def search(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(customer__name__icontains=value))


class RevenueContractFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = RevenueContract
        fields = ('id', 'contract_code', 'name', 'customer', 'contract_type', 'status', 'start_date', 'end_date')

    def search(self, queryset, name, value):
        return queryset.filter(Q(contract_code__icontains=value) | Q(name__icontains=value) | Q(customer__name__icontains=value))


_REVENUE_FILTER_MODELS = [
    RevenueContractProject, RevenueOrder, RevenueContractVersion, RevenueContractLine, RevenueBillingRule,
    RevenueBillingSegment, RevenueReceivablePlan, RevenueReceivablePlanVersion, RevenueTriggerRecord,
    RevenueAdjustmentRecord, RevenueReceivableBill, RevenueReceivableLine, RevenueInvoice,
    RevenueInvoiceLine, RevenueInvoiceMapping,
    RevenueReceipt, RevenueReceiptAllocation, RevenueSyncLog,
]

for _revenue_model in _REVENUE_FILTER_MODELS:
    _meta = type('Meta', (), {'model': _revenue_model, 'fields': ('id',)})
    globals()[f'{_revenue_model.__name__}FilterSet'] = type(
        f'{_revenue_model.__name__}FilterSet',
        (NetBoxModelFilterSet,),
        {'Meta': _meta},
    )

class RevenueOrderFilterSet(NetBoxModelFilterSet):
    contract_id = django_filters.NumberFilter(field_name='contract_id')
    project_id = django_filters.NumberFilter(field_name='project_id')

    class Meta:
        model = RevenueOrder
        fields = ('id', 'order_code', 'contract', 'project', 'status', 'source_system')

    def search(self, queryset, name, value):
        return queryset.filter(Q(order_code__icontains=value) | Q(name__icontains=value))


class RevenueContractVersionFilterSet(NetBoxModelFilterSet):
    contract_id = django_filters.NumberFilter(field_name='contract_id')

    class Meta:
        model = RevenueContractVersion
        fields = ('id', 'contract', 'version_code', 'status')


class RevenueContractLineFilterSet(NetBoxModelFilterSet):
    contract_id = django_filters.NumberFilter(field_name='contract_id')
    project_id = django_filters.NumberFilter(field_name='project_id')
    revenue_order_id = django_filters.NumberFilter(field_name='revenue_order_id')

    class Meta:
        model = RevenueContractLine
        fields = ('id', 'contract', 'project', 'revenue_order', 'status')
