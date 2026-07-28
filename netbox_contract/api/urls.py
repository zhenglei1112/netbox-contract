from netbox.api.routers import NetBoxRouter

from . import views

app_name = 'netbox_contract'

router = NetBoxRouter()
router.register('contracts', views.ContractViewSet)
router.register('contracttype', views.ContractTypeViewSet)
router.register('invoices', views.InvoiceViewSet)
router.register('serviceproviders', views.ServiceProviderViewSet)
router.register('contractassignment', views.ContractAssignmentViewSet)
router.register('invoiceline', views.InvoiceLineViewSet)
router.register('accountingdimension', views.AccountingDimensionViewSet)

urlpatterns = router.urls

router.register('revenue-customers', views.RevenueCustomerViewSet)
router.register('revenue-projects', views.RevenueProjectViewSet)
router.register('revenue-contracts', views.RevenueContractViewSet)
router.register('revenue-contract-projects', views.RevenueContractProjectViewSet)
router.register('revenue-orders', views.RevenueOrderViewSet)
router.register('revenue-contract-versions', views.RevenueContractVersionViewSet)
router.register('revenue-contract-lines', views.RevenueContractLineViewSet)
router.register('revenue-billing-rules', views.RevenueBillingRuleViewSet)
router.register('revenue-billing-segments', views.RevenueBillingSegmentViewSet)
router.register('revenue-receivable-plans', views.RevenueReceivablePlanViewSet)
router.register('revenue-receivable-plan-versions', views.RevenueReceivablePlanVersionViewSet)
router.register('revenue-trigger-records', views.RevenueTriggerRecordViewSet)
router.register('revenue-adjustment-records', views.RevenueAdjustmentRecordViewSet)
router.register('revenue-receivable-bills', views.RevenueReceivableBillViewSet)
router.register('revenue-receivable-lines', views.RevenueReceivableLineViewSet)
router.register('revenue-invoices', views.RevenueInvoiceViewSet)
router.register('revenue-invoice-lines', views.RevenueInvoiceLineViewSet)
router.register('revenue-invoice-mappings', views.RevenueInvoiceMappingViewSet)
router.register('revenue-receipts', views.RevenueReceiptViewSet)
router.register('revenue-receipt-allocations', views.RevenueReceiptAllocationViewSet)
router.register('revenue-sync-logs', views.RevenueSyncLogViewSet)

urlpatterns = router.urls
