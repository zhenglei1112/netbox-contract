import django_filters
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
    currency = django_filters.MultipleChoiceFilter(
        choices=CurrencyChoices, null_value=None
    )
    external_party_object = django_filters.ModelChoiceFilter(
        queryset=ServiceProvider.objects.all(),
        method='filter_external_party_object',
        label=_('External party')
    )

    class Meta:
        model = Contract
        fields = (
            'id',
            'name',
            'contract_type',
            'external_reference',
            'start_date',
            'end_date',
            'initial_term',
            'parent',
        )

    def search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value)
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
    currency = django_filters.MultipleChoiceFilter(
        choices=CurrencyChoices, null_value=None
    )
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
    currency = django_filters.MultipleChoiceFilter(
        choices=CurrencyChoices, null_value=None
    )

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
