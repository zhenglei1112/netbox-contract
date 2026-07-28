from django.db.models import Case, F, When
from django.db.models.functions import Round
from netbox.api.viewsets import NetBoxModelViewSet

from .. import filtersets, models
from .serializers import (
    AccountingDimensionSerializer,
    ContractAssignmentSerializer,
    ContractSerializer,
    ContractTypeSerializer,
    InvoiceLineSerializer,
    InvoiceSerializer,
    ServiceProviderSerializer,
)


class ContractViewSet(NetBoxModelViewSet):
    queryset = models.Contract.objects.prefetch_related('parent', 'tags').annotate(
        calculated_rc=Round(
            Case(When(yrc__gt=0, then=F('yrc') / 12), default=F('mrc') * 12),
            precision=2,
        )
    )
    serializer_class = ContractSerializer
    filterset_class = filtersets.ContractFilterSet


class InvoiceViewSet(NetBoxModelViewSet):
    queryset = models.Invoice.objects.prefetch_related('contracts', 'tags')
    serializer_class = InvoiceSerializer
    filterset_class = filtersets.InvoiceFilterSet


class ServiceProviderViewSet(NetBoxModelViewSet):
    queryset = models.ServiceProvider.objects.prefetch_related('tags')
    serializer_class = ServiceProviderSerializer
    filterset_class = filtersets.ServiceProviderFilterSet


class ContractAssignmentViewSet(NetBoxModelViewSet):
    queryset = models.ContractAssignment.objects.prefetch_related('contract', 'tags')
    serializer_class = ContractAssignmentSerializer


class InvoiceLineViewSet(NetBoxModelViewSet):
    queryset = models.InvoiceLine.objects.prefetch_related(
        'invoice', 'accounting_dimensions', 'tags'
    )
    serializer_class = InvoiceLineSerializer
    filterset_class = filtersets.InvoiceLineFilterSet


class AccountingDimensionViewSet(NetBoxModelViewSet):
    queryset = models.AccountingDimension.objects.prefetch_related('tags')
    serializer_class = AccountingDimensionSerializer


class ContractTypeViewSet(NetBoxModelViewSet):
    queryset = models.ContractType.objects.prefetch_related('tags')
    serializer_class = ContractTypeSerializer


_REVENUE_VIEWSET_MODELS = [
    models.RevenueCustomer, models.RevenueProject, models.RevenueContract, models.RevenueContractProject,
    models.RevenueOrder, models.RevenueContractVersion, models.RevenueContractLine, models.RevenueBillingRule,
    models.RevenueBillingSegment, models.RevenueReceivablePlan, models.RevenueReceivablePlanVersion,
    models.RevenueTriggerRecord, models.RevenueAdjustmentRecord, models.RevenueReceivableBill,
    models.RevenueReceivableLine,
    models.RevenueInvoice,
    models.RevenueInvoiceLine, models.RevenueInvoiceMapping, models.RevenueReceipt,
    models.RevenueReceiptAllocation,
    models.RevenueSyncLog,
]

for _revenue_model in _REVENUE_VIEWSET_MODELS:
    globals()[f'{_revenue_model.__name__}ViewSet'] = type(
        f'{_revenue_model.__name__}ViewSet',
        (NetBoxModelViewSet,),
        {
            'queryset': _revenue_model.objects.prefetch_related('tags'),
            'serializer_class': getattr(__import__('netbox_contract.api.serializers', fromlist=[f'{_revenue_model.__name__}Serializer']), f'{_revenue_model.__name__}Serializer'),
            'filterset_class': getattr(filtersets, f'{_revenue_model.__name__}FilterSet'),
        },
    )
