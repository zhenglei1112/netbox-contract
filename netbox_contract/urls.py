from django.urls import include, path
from netbox.views.generic import ObjectChangeLogView
from utilities.urls import get_model_urls

from . import models, views

urlpatterns = [
    # Service Providers
    path(
        'serviceproviders/',
        views.ServiceProviderListView.as_view(),
        name='serviceprovider_list',
    ),
    path(
        'serviceproviders/add/',
        views.ServiceProviderEditView.as_view(),
        name='serviceprovider_add',
    ),
    path(
        'serviceproviders/import/',
        views.ServiceProviderBulkImportView.as_view(),
        name='serviceprovider_bulk_import',
    ),
    path(
        'serviceproviders/edit/',
        views.ServiceProviderBulkEditView.as_view(),
        name='serviceprovider_bulk_edit',
    ),
    path(
        'serviceproviders/delete/',
        views.ServiceProviderBulkDeleteView.as_view(),
        name='serviceprovider_bulk_delete',
    ),
    path(
        'serviceproviders/<int:pk>/',
        include(get_model_urls('netbox_contract', 'serviceprovider')),
        name='serviceprovider',
    ),
    path(
        'serviceproviders/<int:pk>/edit/',
        views.ServiceProviderEditView.as_view(),
        name='serviceprovider_edit',
    ),
    path(
        'serviceproviders/<int:pk>/delete/',
        views.ServiceProviderDeleteView.as_view(),
        name='serviceprovider_delete',
    ),
    path(
        'serviceproviders/<int:pk>/changelog/',
        ObjectChangeLogView.as_view(),
        name='serviceprovider_changelog',
        kwargs={'model': models.ServiceProvider},
    ),

    # Contracts
    path('contracts/', views.ContractListView.as_view(), name='contract_list'),
    path('contracts/add/', views.ContractEditView.as_view(), name='contract_add'),
    path(
        'contracts/import/',
        views.ContractBulkImportView.as_view(),
        name='contract_bulk_import',
    ),
    path(
        'contracts/edit/',
        views.ContractBulkEditView.as_view(),
        name='contract_bulk_edit',
    ),
    path(
        'contracts/delete/',
        views.ContractBulkDeleteView.as_view(),
        name='contract_bulk_delete',
    ),
    path(
        'contracts/<int:pk>/',
        include(get_model_urls('netbox_contract', 'contract')),
        name='contract',
    ),
    path(
        'contracts/<int:pk>/edit/',
        views.ContractEditView.as_view(),
        name='contract_edit',
    ),
    path(
        'contracts/<int:pk>/delete/',
        views.ContractDeleteView.as_view(),
        name='contract_delete',
    ),
    path(
        'contracts/<int:pk>/changelog/',
        ObjectChangeLogView.as_view(),
        name='contract_changelog',
        kwargs={'model': models.Contract},
    ),
    # Contract invoices
    path('invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/add/', views.InvoiceEditView.as_view(), name='invoice_add'),
    path(
        'invoices/import/', views.InvoiceBulkImportView.as_view(), name='invoice_bulk_import'
    ),
    path(
        'invoices/edit/', views.InvoiceBulkEditView.as_view(), name='invoice_bulk_edit'
    ),
    path(
        'invoices/delete/',
        views.InvoiceBulkDeleteView.as_view(),
        name='invoice_bulk_delete',
    ),
    path(
        'invoices/<int:pk>/',
        include(get_model_urls('netbox_contract', 'invoice')),
        name='invoice',
    ),
    path(
        'invoices/<int:pk>/edit/', views.InvoiceEditView.as_view(), name='invoice_edit'
    ),
    path(
        'invoices/<int:pk>/delete/',
        views.InvoiceDeleteView.as_view(),
        name='invoice_delete',
    ),
    path(
        'invoices/<int:pk>/changelog/',
        ObjectChangeLogView.as_view(),
        name='invoice_changelog',
        kwargs={'model': models.Invoice},
    ),
    # Contract assignments
    path(
        'assignments/',
        views.ContractAssignmentListView.as_view(),
        name='contractassignment_list',
    ),
    path(
        'assignments/add/',
        views.ContractAssignmentEditView.as_view(),
        name='contractassignment_add',
    ),
    path(
        'assignments/import/',
        views.ContractAssignmentBulkImportView.as_view(),
        name='contractassignment_bulk_import',
    ),
    path(
        'assignments/edit/',
        views.ContractAssignmentBulkEditView.as_view(),
        name='contractassignment_bulk_edit',
    ),
    path(
        'assignments/delete/',
        views.ContractAssignmentBulkDeleteView.as_view(),
        name='contractassignment_bulk_delete',
    ),
    path(
        'assignments/<int:pk>/',
        views.ContractAssignmentView.as_view(),
        name='contractassignment',
    ),
    path(
        'assignments/<int:pk>/edit/',
        views.ContractAssignmentEditView.as_view(),
        name='contractassignment_edit',
    ),
    path(
        'assignments/<int:pk>/delete/',
        views.ContractAssignmentDeleteView.as_view(),
        name='contractassignment_delete',
    ),
    path(
        'assignments/<int:pk>/changelog/',
        ObjectChangeLogView.as_view(),
        name='contractassignment_changelog',
        kwargs={'model': models.ContractAssignment},
    ),
    # InvoiceLine
    path(
        'invoiceline/',
        views.InvoiceLineListView.as_view(),
        name='invoiceline_list',
    ),
    path(
        'invoiceline/add/',
        views.InvoiceLineEditView.as_view(),
        name='invoiceline_add',
    ),
    path(
        'invoiceline/import/',
        views.InvoiceLineBulkImportView.as_view(),
        name='invoiceline_bulk_import',
    ),
    path(
        'invoiceline/edit/',
        views.InvoiceLineBulkEditView.as_view(),
        name='invoiceline_bulk_edit',
    ),
    path(
        'invoiceline/delete/',
        views.InvoiceLineBulkDeleteView.as_view(),
        name='invoiceline_bulk_delete',
    ),
    path(
        'invoiceline/<int:pk>/',
        views.InvoiceLineView.as_view(),
        name='invoiceline',
    ),
    path(
        'invoiceline/<int:pk>/edit/',
        views.InvoiceLineEditView.as_view(),
        name='invoiceline_edit',
    ),
    path(
        'invoiceline/<int:pk>/delete/',
        views.InvoiceLineDeleteView.as_view(),
        name='invoiceline_delete',
    ),
    path(
        'invoiceline/<int:pk>/changelog/',
        ObjectChangeLogView.as_view(),
        name='invoiceline_changelog',
        kwargs={'model': models.InvoiceLine},
    ),
    # AccountingDimension
    path(
        'accountingdimension/',
        views.AccountingDimensionListView.as_view(),
        name='accountingdimension_list',
    ),
    path(
        'accountingdimension/add/',
        views.AccountingDimensionEditView.as_view(),
        name='accountingdimension_add',
    ),
    path(
        'accountingdimension/import/',
        views.AccountingDimensionBulkImportView.as_view(),
        name='accountingdimension_bulk_import',
    ),
    path(
        'accountingdimension/edit/',
        views.AccountingDimensionBulkEditView.as_view(),
        name='accountingdimension_bulk_edit',
    ),
    path(
        'accountingdimension/delete/',
        views.AccountingDimensionBulkDeleteView.as_view(),
        name='accountingdimension_bulk_delete',
    ),
    path(
        'accountingdimension/<int:pk>/',
        views.AccountingDimensionView.as_view(),
        name='accountingdimension',
    ),
    path(
        'accountingdimension/<int:pk>/edit/',
        views.AccountingDimensionEditView.as_view(),
        name='accountingdimension_edit',
    ),
    path(
        'accountingdimension/<int:pk>/delete/',
        views.AccountingDimensionDeleteView.as_view(),
        name='accountingdimension_delete',
    ),
    path(
        'accountingdimension/<int:pk>/changelog/',
        ObjectChangeLogView.as_view(),
        name='accountingdimension_changelog',
        kwargs={'model': models.AccountingDimension},
    ),
    path(
        'contracttype/',
        views.ContractTypeListView.as_view(),
        name='contracttype_list',
    ),
    path(
        'contracttype/add/',
        views.ContractTypeEditView.as_view(),
        name='contracttype_add',
    ),
    path(
        'contracttype/<int:pk>/',
        views.ContractTypeView.as_view(),
        name='contracttype',
    ),
    path(
        'contracttype/<int:pk>/edit/',
        views.ContractTypeEditView.as_view(),
        name='contracttype_edit',
    ),
    path(
        'contracttype/edit/',
        views.ContractTypeBulkEditView.as_view(),
        name='contracttype_bulk_edit',
    ),
    path(
        'contracttype/<int:pk>/delete/',
        views.ContractTypeDeleteView.as_view(),
        name='contracttype_delete',
    ),
    path(
        'contracttype/delete/',
        views.ContractTypeBulkDeleteView.as_view(),
        name='contracttype_bulk_delete',
    ),
    path(
        'contracttype/import/',
        views.ContractTypeBulkImportView.as_view(),
        name='contracttype_bulk_import',
    ),
    path(
        'contracttype/<int:pk>/changelog/',
        ObjectChangeLogView.as_view(),
        name='contracttype_changelog',
        kwargs={'model': models.ContractType},
    ),
    # Seal reason generation
    path(
        'invoices/generate-seal-reason/',
        views.InvoiceGenerateSealReasonView.as_view(),
        name='invoice_generate_seal_reason',
    ),
    path(
        'invoices/generate-eip-summary/',
        views.InvoiceGenerateEIPSummaryView.as_view(),
        name='invoice_generate_eip_summary',
    ),
]

urlpatterns += [
    path('revenue/receivables/overview/', views.RevenueReceivableOverviewView.as_view(), name='revenuereceivable_overview'),
    path('revenue/contracts/<int:pk>/generate-receivables/', views.RevenueContractGenerateReceivablesView.as_view(), name='revenuecontract_generate_receivables'),
    path('revenue/contracts/<int:pk>/events/export/', views.RevenueContractEventExportView.as_view(), name='revenuecontract_event_export'),
    path('revenue/contracts/<int:pk>/visual/', views.RevenueContractVisualView.as_view(), name='revenuecontract_visual'),
    path('revenue/contracts/<int:pk>/executive/', views.RevenueContractExecutiveView.as_view(), name='revenuecontract_executive'),
]

_REVENUE_URL_SPECS = [
    ('revenue/customers', 'revenuecustomer', models.RevenueCustomer, views.RevenueCustomerListView, views.RevenueCustomerEditView, views.RevenueCustomerDeleteView),
    ('revenue/projects', 'revenueproject', models.RevenueProject, views.RevenueProjectListView, views.RevenueProjectEditView, views.RevenueProjectDeleteView),
    ('revenue/contracts', 'revenuecontract', models.RevenueContract, views.RevenueContractListView, views.RevenueContractEditView, views.RevenueContractDeleteView),
    ('revenue/contract-projects', 'revenuecontractproject', models.RevenueContractProject, views.RevenueContractProjectListView, views.RevenueContractProjectEditView, views.RevenueContractProjectDeleteView),
    ('revenue/orders', 'revenueorder', models.RevenueOrder, views.RevenueOrderListView, views.RevenueOrderEditView, views.RevenueOrderDeleteView),
    ('revenue/contract-versions', 'revenuecontractversion', models.RevenueContractVersion, views.RevenueContractVersionListView, views.RevenueContractVersionEditView, views.RevenueContractVersionDeleteView),
    ('revenue/contract-lines', 'revenuecontractline', models.RevenueContractLine, views.RevenueContractLineListView, views.RevenueContractLineEditView, views.RevenueContractLineDeleteView),
    ('revenue/billing-rules', 'revenuebillingrule', models.RevenueBillingRule, views.RevenueBillingRuleListView, views.RevenueBillingRuleEditView, views.RevenueBillingRuleDeleteView),
    ('revenue/billing-segments', 'revenuebillingsegment', models.RevenueBillingSegment, views.RevenueBillingSegmentListView, views.RevenueBillingSegmentEditView, views.RevenueBillingSegmentDeleteView),
    ('revenue/receivable-plans', 'revenuereceivableplan', models.RevenueReceivablePlan, views.RevenueReceivablePlanListView, views.RevenueReceivablePlanEditView, views.RevenueReceivablePlanDeleteView),
    ('revenue/receivable-plan-versions', 'revenuereceivableplanversion', models.RevenueReceivablePlanVersion, views.RevenueReceivablePlanVersionListView, views.RevenueReceivablePlanVersionEditView, views.RevenueReceivablePlanVersionDeleteView),
    ('revenue/trigger-records', 'revenuetriggerrecord', models.RevenueTriggerRecord, views.RevenueTriggerRecordListView, views.RevenueTriggerRecordEditView, views.RevenueTriggerRecordDeleteView),
    ('revenue/adjustment-records', 'revenueadjustmentrecord', models.RevenueAdjustmentRecord, views.RevenueAdjustmentRecordListView, views.RevenueAdjustmentRecordEditView, views.RevenueAdjustmentRecordDeleteView),
    ('revenue/receivable-bills', 'revenuereceivablebill', models.RevenueReceivableBill, views.RevenueReceivableBillListView, views.RevenueReceivableBillEditView, views.RevenueReceivableBillDeleteView),
    ('revenue/receivable-lines', 'revenuereceivableline', models.RevenueReceivableLine, views.RevenueReceivableLineListView, views.RevenueReceivableLineEditView, views.RevenueReceivableLineDeleteView),
    ('revenue/invoices', 'revenueinvoice', models.RevenueInvoice, views.RevenueInvoiceListView, views.RevenueInvoiceEditView, views.RevenueInvoiceDeleteView),
    ('revenue/invoice-lines', 'revenueinvoiceline', models.RevenueInvoiceLine, views.RevenueInvoiceLineListView, views.RevenueInvoiceLineEditView, views.RevenueInvoiceLineDeleteView),
    ('revenue/invoice-mappings', 'revenueinvoicemapping', models.RevenueInvoiceMapping, views.RevenueInvoiceMappingListView, views.RevenueInvoiceMappingEditView, views.RevenueInvoiceMappingDeleteView),
    ('revenue/receipts', 'revenuereceipt', models.RevenueReceipt, views.RevenueReceiptListView, views.RevenueReceiptEditView, views.RevenueReceiptDeleteView),
    ('revenue/receipt-allocations', 'revenuereceiptallocation', models.RevenueReceiptAllocation, views.RevenueReceiptAllocationListView, views.RevenueReceiptAllocationEditView, views.RevenueReceiptAllocationDeleteView),
    ('revenue/sync-logs', 'revenuesynclog', models.RevenueSyncLog, views.RevenueSyncLogListView, views.RevenueSyncLogEditView, views.RevenueSyncLogDeleteView),
]

for _prefix, _name, _model, _list_view, _edit_view, _delete_view in _REVENUE_URL_SPECS:
    _detail_view = getattr(views, f'{_model.__name__}View')
    urlpatterns += [
        path(f'{_prefix}/', _list_view.as_view(), name=f'{_name}_list'),
        path(f'{_prefix}/add/', _edit_view.as_view(), name=f'{_name}_add'),
        path(f'{_prefix}/<int:pk>/', _detail_view.as_view(), name=_name),
        path(f'{_prefix}/<int:pk>/edit/', _edit_view.as_view(), name=f'{_name}_edit'),
        path(f'{_prefix}/<int:pk>/delete/', _delete_view.as_view(), name=f'{_name}_delete'),
        path(f'{_prefix}/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name=f'{_name}_changelog', kwargs={'model': _model}),
    ]
