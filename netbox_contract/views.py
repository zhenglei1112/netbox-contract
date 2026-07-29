import csv
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Case, F, Q, Sum, When
from django.db.models.functions import Round
from django.shortcuts import get_object_or_404, redirect, render
from netbox.views import generic
from netbox.views.generic.utils import get_prerequisite_model
from utilities.forms import restrict_form_fields
from utilities.paginator import get_paginate_count
from utilities.querydict import normalize_querydict
from utilities.views import ObjectPermissionRequiredMixin, register_model_view

from . import filtersets, forms, models as plugin_models, tables
from .services.revenue_events import build_revenue_event_rows, summarize_revenue_events
from .services.revenue_generation import build_receivable_generation_preview
from .services.revenue_plans import build_receivable_plan_tracks
from .services.revenue_timeline import build_revenue_timeline
from .services.revenue_view_filters import (
    build_timeline_view_profile,
    filter_mixed_lanes,
    filter_order_lanes,
    filter_periodic_matrix,
    filter_stage_timeline,
)
from .services.revenue_portfolio import build_revenue_portfolio
from .services.revenue_views import build_mixed_lanes, build_order_lanes, build_periodic_matrix
from .models import (
    AccountingDimension,
    Contract,
    ContractAssignment,
    ContractType,
    Invoice,
    InvoiceLine,
    ServiceProvider,
)

DETAIL_PAGE_PARAMS = (
    'invoice_lines_page',
    'assignments_page',
    'children_page',
    'invoices_page',
    'contracts_page',
)


def _detail_query(params, page_key, per_page):
    query = params.copy()
    query.pop(page_key, None)
    query['per_page'] = per_page
    return query.urlencode()


def _detail_per_page_query(params):
    query = params.copy()
    query.pop('per_page', None)
    for page_key in DETAIL_PAGE_PARAMS:
        query.pop(page_key, None)
    return query.urlencode()


def _configure_detail_table(table, request, page_param):
    table.prefix = page_param.removesuffix('page')
    table.configure(request)


plugin_settings = settings.PLUGINS_CONFIG['netbox_contract']


# ContractType views


class ContractTypeView(generic.ObjectView):
    queryset = ContractType.objects.all()


class ContractTypeListView(generic.ObjectListView):
    queryset = ContractType.objects.all()
    table = tables.ContractTypeListTable
    filterset = filtersets.ContractTypeFilterSet
    filterset_form = forms.ContractTypeFilterForm


class ContractTypeEditView(generic.ObjectEditView):
    queryset = ContractType.objects.all()
    form = forms.ContractTypeForm


class ContractTypeBulkImportView(generic.BulkImportView):
    queryset = ContractType.objects.all()
    model_form = forms.ContractTypeCSVForm
    table = tables.ContractTypeListTable


class ContractTypeBulkEditView(generic.BulkEditView):
    queryset = ContractType.objects.annotate()
    filterset = filtersets.ContractTypeFilterSet
    table = tables.ContractTypeListTable
    form = forms.ContractTypeBulkEditForm


class ContractTypeDeleteView(generic.ObjectDeleteView):
    queryset = ContractType.objects.all()


class ContractTypeBulkDeleteView(generic.BulkDeleteView):
    queryset = ContractType.objects.annotate()
    filterset = filtersets.ContractTypeFilterSet
    table = tables.ContractTypeListTable


# ServiceProvider views

@register_model_view(ServiceProvider)
class ServiceProviderView(generic.ObjectView):
    queryset = ServiceProvider.objects.all()

    def get_extra_context(self, request, instance):
        # Get contracts where this service provider is the external party
        from django.contrib.contenttypes.models import ContentType
        service_provider_content_type = ContentType.objects.get_for_model(ServiceProvider)
        contracts = Contract.objects.filter(
            external_party_object_type=service_provider_content_type,
            external_party_object_id=instance.pk
        )
        contracts_table = tables.ContractListTable(contracts)
        contracts_table.configure(request)
        
        return {
            'contracts_table': contracts_table,
        }


class ServiceProviderListView(generic.ObjectListView):
    queryset = ServiceProvider.objects.all()
    table = tables.ServiceProviderListTable
    filterset = filtersets.ServiceProviderFilterSet
    filterset_form = forms.ServiceProviderFilterForm


class ServiceProviderEditView(generic.ObjectEditView):
    queryset = ServiceProvider.objects.all()
    form = forms.ServiceProviderForm


class ServiceProviderDeleteView(generic.ObjectDeleteView):
    queryset = ServiceProvider.objects.all()


class ServiceProviderBulkImportView(generic.BulkImportView):
    queryset = ServiceProvider.objects.all()
    model_form = forms.ServiceProviderCSVForm
    table = tables.ServiceProviderListTable


class ServiceProviderBulkEditView(generic.BulkEditView):
    queryset = ServiceProvider.objects.annotate()
    filterset = filtersets.ServiceProviderFilterSet
    table = tables.ServiceProviderListTable
    form = forms.ServiceProviderBulkEditForm


class ServiceProviderBulkDeleteView(generic.BulkDeleteView):
    queryset = ServiceProvider.objects.annotate()
    filterset = filtersets.ServiceProviderFilterSet
    table = tables.ServiceProviderListTable


# Contract assignment view


class ContractAssignmentView(generic.ObjectView):
    queryset = ContractAssignment.objects.all()


class ContractAssignmentListView(generic.ObjectListView):
    queryset = ContractAssignment.objects.all()
    table = tables.ContractAssignmentListTable
    filterset = filtersets.ContractAssignmentFilterSet
    filterset_form = forms.ContractAssignmentFilterForm


class ContractAssignmentEditView(generic.ObjectEditView):
    queryset = ContractAssignment.objects.all()
    form = forms.ContractAssignmentForm

    def alter_object(self, instance, request, args, kwargs):
        if not instance.pk and kwargs:
            # Assign the object based on URL kwargs
            content_type = get_object_or_404(
                ContentType, pk=request.GET.get('content_type')
            )
            instance.object = get_object_or_404(
                content_type.model_class(), pk=request.GET.get('object_id')
            )
        return instance

    def get_extra_addanother_params(self, request):
        return {
            'content_type': request.GET.get('content_type'),
            'object_id': request.GET.get('object_id'),
        }


class ContractAssignmentDeleteView(generic.ObjectDeleteView):
    queryset = ContractAssignment.objects.all()


class ContractAssignmentBulkImportView(generic.BulkImportView):
    queryset = ContractAssignment.objects.all()
    model_form = forms.ContractAssignmentImportForm
    table = tables.ContractAssignmentListTable


class ContractAssignmentBulkEditView(generic.BulkEditView):
    queryset = ContractAssignment.objects.annotate()
    filterset = filtersets.ContractAssignmentFilterSet
    table = tables.ContractAssignmentListTable
    form = forms.ContractAssignmentBulkEditForm


class ContractAssignmentBulkDeleteView(generic.BulkDeleteView):
    queryset = ContractAssignment.objects.annotate()
    filterset = filtersets.ContractAssignmentFilterSet
    table = tables.ContractAssignmentListTable

# Contract views


@register_model_view(Contract)
class ContractView(generic.ObjectView):
    queryset = Contract.objects.annotate(
        calculated_rc=Round(
            Case(When(yrc__gt=0, then=F('yrc') / 12), default=F('mrc') * 12),
            precision=2,
        )
    )

    def get_extra_context(self, request, instance):
        per_page = get_paginate_count(request)
        invoices_table = tables.InvoiceListTable(
            instance.invoices.exclude(template=True).prefetch_related('tags')
        )
        invoices_table.columns.hide('contracts')
        _configure_detail_table(invoices_table, request, 'invoices_page')
        invoices_table.columns.show('tags')
        assignments_table = tables.ContractAssignmentContractTable(
            instance.assignments.all()
        )
        invoice_template = instance.invoices.filter(template=True).first()
        if invoice_template:
            invoicelines_table = tables.InvoiceLineListTable(
                invoice_template.invoicelines.all()
            )
            invoicelines_table.columns.hide('invoice')
            _configure_detail_table(invoicelines_table, request, 'invoice_lines_page')
        else:
            invoicelines_table = None
        _configure_detail_table(assignments_table, request, 'assignments_page')
        if instance.childs.all():
            childs_table = tables.ContractListBottomTable(instance.childs.all())
            _configure_detail_table(childs_table, request, 'children_page')
        else:
            childs_table = None

        hidden_fields = plugin_settings.get('hidden_contract_fields')

        return {
            'hidden_fields': hidden_fields,
            'invoices_table': invoices_table,
            'invoice_template': invoice_template,
            'invoicelines_table': invoicelines_table,
            'assignments_table': assignments_table,
            'childs_table': childs_table,
            'detail_per_page_query': _detail_per_page_query(request.GET),
            'invoice_lines_query': _detail_query(request.GET, 'invoice_lines_page', per_page),
            'assignments_query': _detail_query(request.GET, 'assignments_page', per_page),
            'children_query': _detail_query(request.GET, 'children_page', per_page),
            'invoices_query': _detail_query(request.GET, 'invoices_page', per_page),
        }


class ContractListView(generic.ObjectListView):
    queryset = Contract.objects.annotate(
        calculated_rc=Round(
            Case(When(yrc__gt=0, then=F('yrc') / 12), default=F('mrc') * 12),
            precision=2,
        )
    )
    table = tables.ContractListTable
    filterset = filtersets.ContractFilterSet
    filterset_form = forms.ContractFilterForm


class ContractEditView(generic.ObjectEditView):
    queryset = Contract.objects.all()
    form = forms.ContractForm

    def alter_object(self, obj, request, url_args, url_kwargs):
        """
        When this method is called after a Post,
        it is used here to set the external party object id for exiting objects,
        In any case, this happens before the form is instanciated.

        Args:
            obj: The object being edited
            request: The current request
            url_args: URL path args
            url_kwargs: URL path kwargs
        """

        if request.method == 'POST':
            data = normalize_querydict(request.POST)
            if data.get('external_party_object'):
                obj.external_party_object_id = data.get('external_party_object')
                obj.external_party_object_type = ContentType.objects.get_for_model(ServiceProvider)
                try:
                    obj.external_party_object = ServiceProvider.objects.get(id=obj.external_party_object_id)
                except ServiceProvider.DoesNotExist:
                    pass

        return obj


class ContractDeleteView(generic.ObjectDeleteView):
    queryset = Contract.objects.all()


class ContractBulkImportView(generic.BulkImportView):
    queryset = Contract.objects.all()
    model_form = forms.ContractCSVForm
    table = tables.ContractListTable


class ContractBulkEditView(generic.BulkEditView):
    queryset = Contract.objects.all()
    filterset = filtersets.ContractFilterSet
    table = tables.ContractListTable
    form = forms.ContractBulkEditForm


class ContractBulkDeleteView(generic.BulkDeleteView):
    queryset = Contract.objects.all()
    filterset = filtersets.ContractFilterSet
    table = tables.ContractListTable


# Invoice views


@register_model_view(Invoice)
class InvoiceView(generic.ObjectView):
    queryset = Invoice.objects.all()

    def get_extra_context(self, request, instance):
        per_page = get_paginate_count(request)
        contracts_table = tables.ContractListTable(instance.contracts.all())
        _configure_detail_table(contracts_table, request, 'contracts_page')
        invoicelines_table = tables.InvoiceLineListTable(instance.invoicelines.all())
        invoicelines_table.columns.hide('invoice')
        _configure_detail_table(invoicelines_table, request, 'invoice_lines_page')
        hidden_fields = plugin_settings.get('hidden_invoice_fields')

        return {
            'hidden_fields': hidden_fields,
            'contracts_table': contracts_table,
            'invoicelines_table': invoicelines_table,
            'detail_per_page_query': _detail_per_page_query(request.GET),
            'invoice_lines_query': _detail_query(request.GET, 'invoice_lines_page', per_page),
            'contracts_query': _detail_query(request.GET, 'contracts_page', per_page),
        }


class InvoiceListView(generic.ObjectListView):
    queryset = Invoice.objects.all()
    table = tables.InvoiceListTable
    filterset = filtersets.InvoiceFilterSet
    filterset_form = forms.InvoiceFilterForm


class InvoiceEditView(generic.ObjectEditView):
    queryset = Invoice.objects.all()
    form = forms.InvoiceForm

    def get(self, request, *args, **kwargs):
        """
        GET request handler
            Overrides the ObjectEditView function to include form initialization
            with data from the parent contract object

        Args:
            request: The current request
        """
        obj = self.get_object(**kwargs)
        obj = self.alter_object(obj, request, args, kwargs)
        model = self.queryset.model

        initial_data = normalize_querydict(request.GET)
        initial_data['date'] = date.today()
        if 'contracts' in initial_data.keys():
            contract = Contract.objects.get(pk=initial_data['contracts'])

            try:
                last_invoice = contract.invoices.exclude(template=True).latest(
                    'period_end'
                )
                if last_invoice.period_end:
                    new_period_start = last_invoice.period_end + timedelta(days=1)
                else:
                    new_period_start = None
            except ObjectDoesNotExist:
                if contract.start_date:
                    new_period_start = contract.start_date
                else:
                    new_period_start = None

            if new_period_start:
                initial_data['period_start'] = new_period_start
                delta = relativedelta(months=contract.invoice_frequency)
                new_period_end = new_period_start + delta - timedelta(days=1)
                initial_data['period_end'] = new_period_end
            else:
                # If new_period_start is None, set default values
                initial_data['period_start'] = date.today()
                delta = relativedelta(months=contract.invoice_frequency)
                new_period_end = date.today() + delta - timedelta(days=1)
                initial_data['period_end'] = new_period_end

            if contract.mrc:
                initial_data['amount'] = contract.mrc * contract.invoice_frequency
            else:
                initial_data['amount'] = 0

        form = self.form(instance=obj, initial=initial_data)
        restrict_form_fields(form, request.user)

        return render(
            request,
            self.template_name,
            {
                'model': model,
                'object': obj,
                'form': form,
                'return_url': self.get_return_url(request, obj),
                'prerequisite_model': get_prerequisite_model(self.queryset),
                **self.get_extra_context(request, obj),
            },
        )


class InvoiceDeleteView(generic.ObjectDeleteView):
    queryset = Invoice.objects.all()


class InvoiceBulkImportView(generic.BulkImportView):
    queryset = Invoice.objects.all()
    model_form = forms.InvoiceCSVForm
    table = tables.InvoiceListTable


class InvoiceBulkEditView(generic.BulkEditView):
    queryset = Invoice.objects.all()
    filterset = filtersets.InvoiceFilterSet
    table = tables.InvoiceListTable
    form = forms.InvoiceBulkEditForm


class InvoiceBulkDeleteView(generic.BulkDeleteView):
    queryset = Invoice.objects.all()
    filterset = filtersets.InvoiceFilterSet
    table = tables.InvoiceListTable


# InvoiceLine


class InvoiceLineView(generic.ObjectView):
    queryset = InvoiceLine.objects.all()


class InvoiceLineListView(generic.ObjectListView):
    queryset = InvoiceLine.objects.all()
    table = tables.InvoiceLineListTable
    filterset = filtersets.InvoiceLineFilterSet
    filterset_form = forms.InvoiceLineFilterForm


class InvoiceLineEditView(generic.ObjectEditView):
    queryset = InvoiceLine.objects.all()
    form = forms.InvoiceLineForm

    def get(self, request, *args, **kwargs):
        """
        GET request handler
            Overrides the ObjectEditView function to include form initialization
            with data from the parent invoice object

        Args:
            request: The current request
        """
        obj = self.get_object(**kwargs)
        obj = self.alter_object(obj, request, args, kwargs)
        model = self.queryset.model

        initial_data = normalize_querydict(request.GET)
        if 'invoice' in initial_data.keys():
            invoice = Invoice.objects.get(pk=initial_data['invoice'])
            initial_data['amount'] = invoice.amount - invoice.total_invoicelines_amount

        form = self.form(instance=obj, initial=initial_data)
        restrict_form_fields(form, request.user)

        return render(
            request,
            self.template_name,
            {
                'model': model,
                'object': obj,
                'form': form,
                'return_url': self.get_return_url(request, obj),
                'prerequisite_model': get_prerequisite_model(self.queryset),
                **self.get_extra_context(request, obj),
            },
        )


class InvoiceLineDeleteView(generic.ObjectDeleteView):
    queryset = InvoiceLine.objects.all()


class InvoiceLineBulkImportView(generic.BulkImportView):
    queryset = InvoiceLine.objects.all()
    model_form = forms.InvoiceLineImportForm
    table = tables.InvoiceLineListTable


class InvoiceLineBulkEditView(generic.BulkEditView):
    queryset = InvoiceLine.objects.annotate()
    filterset = filtersets.InvoiceLineFilterSet
    table = tables.InvoiceLineListTable
    form = forms.InvoiceLineBulkEditForm


class InvoiceLineBulkDeleteView(generic.BulkDeleteView):
    queryset = InvoiceLine.objects.annotate()
    filterset = filtersets.InvoiceLineFilterSet
    table = tables.InvoiceLineListTable


# Accounting dimension


class AccountingDimensionView(generic.ObjectView):
    queryset = AccountingDimension.objects.all()


class AccountingDimensionListView(generic.ObjectListView):
    queryset = AccountingDimension.objects.all()
    table = tables.AccountingDimensionListTable
    filterset = filtersets.AccountingDimensionFilterSet
    filterset_form = forms.AccountingDimensionFilterForm


class AccountingDimensionEditView(generic.ObjectEditView):
    queryset = AccountingDimension.objects.all()
    form = forms.AccountingDimensionForm


class AccountingDimensionDeleteView(generic.ObjectDeleteView):
    queryset = AccountingDimension.objects.all()


class AccountingDimensionBulkImportView(generic.BulkImportView):
    queryset = AccountingDimension.objects.all()
    model_form = forms.AccountingDimensionImportForm
    table = tables.AccountingDimensionListTable


class AccountingDimensionBulkEditView(generic.BulkEditView):
    queryset = AccountingDimension.objects.annotate()
    filterset = filtersets.AccountingDimensionFilterSet
    table = tables.AccountingDimensionListTable
    form = forms.AccountingDimensionBulkEditForm


class AccountingDimensionBulkDeleteView(generic.BulkDeleteView):
    queryset = AccountingDimension.objects.annotate()
    filterset = filtersets.AccountingDimensionFilterSet
    table = tables.AccountingDimensionListTable


# Seal reason generation view
from django.views import View
from django.http import HttpResponse

class InvoiceGenerateSealReasonView(View):
    """View to generate seal reason text and copy to clipboard"""
    
    def post(self, request):
        # Get data from form
        contract_name = request.POST.get('contract_name', '')
        period_start = request.POST.get('period_start', '')
        period_end = request.POST.get('period_end', '')
        amount = request.POST.get('amount', '0')
        
        # Generate seal reason text
        seal_reason = f"{contract_name}，{period_start}-{period_end}租金{amount}元"
        
        # Return a response with Bootstrap modal
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>用印事由已生成</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .modal-backdrop {{
            background-color: rgba(0, 0, 0, 0.5);
        }}
        .seal-reason-text {{
            font-family: monospace;
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            border: 1px solid #dee2e6;
            white-space: pre-wrap;
            word-break: break-all;
        }}
        .countdown-btn {{
            width: 120px;
        }}
    </style>
</head>
<body>
    <!-- Bootstrap Modal -->
    <div class="modal fade show" id="sealReasonModal" tabindex="-1" aria-labelledby="sealReasonModalLabel" aria-hidden="true" style="display: block;">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="sealReasonModalLabel">用印事由已生成</h5>
                </div>
                <div class="modal-body">
                    <p id="copyStatus">请点击下方按钮复制用印事由：</p>
                    <div class="seal-reason-text" id="sealReasonText">{seal_reason}</div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-primary" id="copyBtn" onclick="copyToClipboard()">
                        复制到剪贴板
                    </button>
                    <button type="button" class="btn btn-secondary countdown-btn" id="closeBtn" onclick="closeModal()">
                        关闭 (5)
                    </button>
                </div>
            </div>
        </div>
    </div>
    <div class="modal-backdrop fade show"></div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let countdown = 5;
        const closeBtn = document.getElementById('closeBtn');
        const countdownInterval = setInterval(updateCountdown, 1000);
        
        function updateCountdown() {{
            countdown--;
            if (countdown <= 0) {{
                clearInterval(countdownInterval);
                closeModal();
            }} else {{
                closeBtn.textContent = '关闭 (' + countdown + ')';
            }}
        }}
        
        function closeModal() {{
            clearInterval(countdownInterval);
            window.history.back();
        }}
        
        // Copy to clipboard function - requires user interaction
        function copyToClipboard() {{
            const text = '{seal_reason}';
            
            if (navigator.clipboard && window.isSecureContext) {{
                navigator.clipboard.writeText(text).then(function() {{
                    document.getElementById('copyStatus').textContent = '以下用印事由已复制到剪切板：';
                    document.getElementById('copyBtn').textContent = '已复制';
                    document.getElementById('copyBtn').classList.remove('btn-primary');
                    document.getElementById('copyBtn').classList.add('btn-success');
                    document.getElementById('copyBtn').disabled = true;
                }}).catch(function(err) {{
                    console.error('Failed to copy text: ', err);
                    fallbackCopyToClipboard(text);
                }});
            }} else {{
                // Use fallback for older browsers or insecure contexts
                fallbackCopyToClipboard(text);
            }}
        }}
        
        function fallbackCopyToClipboard(text) {{
            var textArea = document.createElement("textarea");
            textArea.value = text;
            textArea.style.position = "fixed";
            textArea.style.left = "-999999px";
            textArea.style.top = "-999999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {{
                var successful = document.execCommand('copy');
                if (successful) {{
                    document.getElementById('copyStatus').textContent = '以下用印事由已复制到剪切板：';
                    document.getElementById('copyBtn').textContent = '已复制';
                    document.getElementById('copyBtn').classList.remove('btn-primary');
                    document.getElementById('copyBtn').classList.add('btn-success');
                    document.getElementById('copyBtn').disabled = true;
                }} else {{
                    document.getElementById('copyStatus').textContent = '生成的用印事由：';
                }}
            }} catch (err) {{
                console.error('Fallback copy failed: ', err);
                document.getElementById('copyStatus').textContent = '生成的用印事由：';
            }}
            document.body.removeChild(textArea);
        }}
    </script>
</body>
</html>
"""
        return HttpResponse(html_content)


class InvoiceGenerateEIPSummaryView(View):
    """View to generate EIP payment summary text and copy to clipboard"""
    
    def post(self, request):
        # Get data from form
        contract_name = request.POST.get('contract_name', '')
        period_start = request.POST.get('period_start', '')
        period_end = request.POST.get('period_end', '')
        
        # Generate EIP summary text
        eip_summary = f"支付{contract_name}，{period_start}-{period_end}"
        
        # Return a response with Bootstrap modal
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EIP支付摘要已生成</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .modal-backdrop {{
            background-color: rgba(0, 0, 0, 0.5);
        }}
        .seal-reason-text {{
            font-family: monospace;
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            border: 1px solid #dee2e6;
            white-space: pre-wrap;
            word-break: break-all;
        }}
        .countdown-btn {{
            width: 120px;
        }}
    </style>
</head>
<body>
    <!-- Bootstrap Modal -->
    <div class="modal fade show" id="sealReasonModal" tabindex="-1" aria-labelledby="sealReasonModalLabel" aria-hidden="true" style="display: block;">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="sealReasonModalLabel">EIP支付摘要已生成</h5>
                </div>
                <div class="modal-body">
                    <p id="copyStatus">请点击下方按钮复制EIP支付摘要：</p>
                    <div class="seal-reason-text" id="sealReasonText">{eip_summary}</div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-primary" id="copyBtn" onclick="copyToClipboard()">
                        复制到剪贴板
                    </button>
                    <button type="button" class="btn btn-secondary countdown-btn" id="closeBtn" onclick="closeModal()">
                        关闭 (5)
                    </button>
                </div>
            </div>
        </div>
    </div>
    <div class="modal-backdrop fade show"></div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let countdown = 5;
        const closeBtn = document.getElementById('closeBtn');
        const countdownInterval = setInterval(updateCountdown, 1000);
        
        function updateCountdown() {{
            countdown--;
            if (countdown <= 0) {{
                clearInterval(countdownInterval);
                closeModal();
            }} else {{
                closeBtn.textContent = '关闭 (' + countdown + ')';
            }}
        }}
        
        function closeModal() {{
            clearInterval(countdownInterval);
            window.history.back();
        }}
        
        // Copy to clipboard function - requires user interaction
        function copyToClipboard() {{
            const text = '{eip_summary}';
            
            if (navigator.clipboard && window.isSecureContext) {{
                navigator.clipboard.writeText(text).then(function() {{
                    document.getElementById('copyStatus').textContent = '以下EIP支付摘要已复制到剪切板：';
                    document.getElementById('copyBtn').textContent = '已复制';
                    document.getElementById('copyBtn').classList.remove('btn-primary');
                    document.getElementById('copyBtn').classList.add('btn-success');
                    document.getElementById('copyBtn').disabled = true;
                }}).catch(function(err) {{
                    console.error('Failed to copy text: ', err);
                    fallbackCopyToClipboard(text);
                }});
            }} else {{
                // Use fallback for older browsers or insecure contexts
                fallbackCopyToClipboard(text);
            }}
        }}
        
        function fallbackCopyToClipboard(text) {{
            var textArea = document.createElement("textarea");
            textArea.value = text;
            textArea.style.position = "fixed";
            textArea.style.left = "-999999px";
            textArea.style.top = "-999999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {{
                var successful = document.execCommand('copy');
                if (successful) {{
                    document.getElementById('copyStatus').textContent = '以下EIP支付摘要已复制到剪切板：';
                    document.getElementById('copyBtn').textContent = '已复制';
                    document.getElementById('copyBtn').classList.remove('btn-primary');
                    document.getElementById('copyBtn').classList.add('btn-success');
                    document.getElementById('copyBtn').disabled = true;
                }} else {{
                    document.getElementById('copyStatus').textContent = '生成的EIP支付摘要：';
                }}
            }} catch (err) {{
                console.error('Fallback copy failed: ', err);
                document.getElementById('copyStatus').textContent = '生成的EIP支付摘要：';
            }}
            document.body.removeChild(textArea);
        }}
    </script>
</body>
</html>
"""
        return HttpResponse(html_content)





def _sum_amount(queryset, field_name):
    return queryset.aggregate(total=Sum(field_name))['total'] or 0


def _format_chinese_datetime(value):
    if isinstance(value, datetime):
        return f'{value.year}\u5e74{value.month}\u6708{value.day}\u65e5 {value.hour}\u65f6{value.minute}\u5206'
    if isinstance(value, date):
        return f'{value.year}\u5e74{value.month}\u6708{value.day}\u65e5'
    return value



def _format_chinese_date_range(start, end):
    if not start or not end:
        return '-'
    return f'{start.year}\u5e74{start.month}\u6708{start.day}\u65e5 - {end.year}\u5e74{end.month}\u6708{end.day}\u65e5'

def _format_revenue_display_value(field_name, value):
    if isinstance(value, bool):
        return '\u662f' if value else '\u5426'
    if field_name in tables.REVENUE_DISPLAY_VALUE_MAP:
        return tables.REVENUE_DISPLAY_VALUE_MAP[field_name].get(value, value)
    return _format_chinese_datetime(value)

def _make_revenue_panel(request, title, table_class, queryset, hide_columns=()):
    table = table_class(queryset)
    for column in hide_columns:
        try:
            table.columns.hide(column)
        except Exception:
            pass
    table.configure(request)
    return {
        'title': title,
        'table': table,
        'count': queryset.count(),
    }




def _period_bounds(billing_period):
    year, month = (int(part) for part in billing_period.split('-'))
    start = date(year, month, 1)
    end = start + relativedelta(months=1) - timedelta(days=1)
    return start, end


def _billing_window_for_rule(rule, billing_period):
    period_start, period_end = _period_bounds(billing_period)
    if rule.billing_cycle == 'quarter':
        period_end = period_start + relativedelta(months=3) - timedelta(days=1)
    elif rule.billing_cycle == 'year':
        period_end = period_start + relativedelta(years=1) - timedelta(days=1)
    return period_start, period_end


def _calculate_segment_amount(contract_line, rule, segment_start, segment_end, period_start, period_end):
    base_amount = contract_line.unit_price * contract_line.quantity
    if rule.proration_rule == 'none':
        amount = base_amount
    elif rule.proration_rule == 'full_month':
        amount = base_amount
    else:
        total_days = Decimal((period_end - period_start).days + 1)
        active_days = Decimal((segment_end - segment_start).days + 1)
        amount = base_amount * active_days / total_days
    precision = Decimal('1') if rule.rounding_precision == '0' else Decimal(f"0.{'0' * (int(rule.rounding_precision) - 1)}1")
    return amount.quantize(precision)


def preview_receivables_for_contract(contract, billing_period):
    contract_lines = list(
        contract.lines.filter(status='active').select_related('project')
    )
    billing_rules = list(
        plugin_models.RevenueBillingRule.objects.filter(
            contract_line__in=contract_lines,
            status='effective',
        ).select_related('contract_line')
    )
    trigger_records = list(
        plugin_models.RevenueTriggerRecord.objects.filter(
            Q(billing_rule__contract_line__contract=contract) | Q(plan__contract=contract),
        )
        .select_related('billing_rule', 'plan__billing_rule')
        .distinct()
    )
    trigger_facts = [
        {
            'billing_rule_id': record.billing_rule_id
            or getattr(record.plan, 'billing_rule_id', None),
            'trigger_event': record.trigger_event,
            'actual_trigger_date': record.actual_trigger_date,
            'status': record.status,
            'source_id': record.external_id or str(record.pk),
        }
        for record in trigger_records
    ]
    existing_keys = plugin_models.RevenueReceivableLine.objects.filter(
        bill__contract=contract,
    ).values_list('idempotent_key', flat=True)
    preview = build_receivable_generation_preview(
        contract_lines,
        billing_rules,
        billing_period,
        trigger_facts=trigger_facts,
        existing_idempotent_keys=existing_keys,
    )
    for row in preview['rows']:
        row['period_label'] = _format_chinese_date_range(
            row['period_start'],
            row['period_end'],
        )
        row['active_label'] = _format_chinese_date_range(
            row['active_start'],
            row['active_end'],
        )
    return preview

def generate_receivables_for_contract(contract, billing_period, confirm_status='draft'):
    preview = preview_receivables_for_contract(contract, billing_period)
    _period_start, default_period_end = _period_bounds(billing_period)
    ready_dates = [
        row['receivable_date']
        for row in preview['rows']
        if row['will_create'] and row.get('receivable_date')
    ]
    bill_receivable_date = min(ready_dates) if ready_dates else default_period_end
    if preview['create_count'] == 0:
        existing_bill = plugin_models.RevenueReceivableBill.objects.filter(
            contract=contract,
            billing_period=billing_period,
        ).first()
        return {
            'bill': existing_bill,
            'created_lines': 0,
            'skipped_lines': len(preview['rows']),
            'preview': preview,
        }

    with transaction.atomic():
        bill, _created = plugin_models.RevenueReceivableBill.objects.get_or_create(
            bill_code=f'{contract.contract_code}-{billing_period}',
            defaults={
                'customer': contract.customer,
                'contract': contract,
                'project': contract.projects.first(),
                'billing_period': billing_period,
                'receivable_date': bill_receivable_date,
                'due_date': bill_receivable_date + timedelta(days=30),
                'amount': Decimal('0'),
                'adjusted_amount': Decimal('0'),
                'net_amount': Decimal('0'),
                'confirm_status': confirm_status,
                'invoice_status': 'uninvoiced',
                'receipt_status': 'unpaid',
                'ageing_status': 'not_due',
                'risk_status': 'normal',
            },
        )

        created_lines = 0
        for row in preview['rows']:
            if not row['will_create']:
                continue
            segment = plugin_models.RevenueBillingSegment.objects.create(
                contract_line=row['contract_line'],
                billing_rule=row['rule'],
                segment_start=row['active_start'],
                segment_end=row['active_end'],
                unit_price=row['contract_line'].unit_price,
                quantity=row['contract_line'].quantity,
                amount=row['amount'],
                change_trigger='normal',
                billing_rule_snapshot={
                    'rule_type': row['rule'].rule_type,
                    'billing_cycle': row['rule'].billing_cycle,
                    'billing_direction': row['rule'].billing_direction,
                    'proration_rule': row['rule'].proration_rule,
                    'rounding_precision': row['rule'].rounding_precision,
                    'trigger_event': row['rule'].trigger_event,
                    'trigger_offset_days': row['rule'].trigger_offset_days,
                },
            )
            plugin_models.RevenueReceivableLine.objects.create(
                bill=bill,
                contract_line=row['contract_line'],
                billing_rule=row['rule'],
                start_date=segment.segment_start,
                end_date=segment.segment_end,
                receivable_date=row['receivable_date'],
                due_date=row['receivable_date'] + timedelta(days=30),
                amount=row['amount'],
                adjusted_amount=Decimal('0'),
                net_amount=row['amount'],
                risk_status='normal',
                idempotent_key=row['idempotent_key'],
            )
            created_lines += 1

        lines = bill.lines.all()
        bill.amount = sum((line.amount for line in lines), Decimal('0'))
        bill.adjusted_amount = sum((line.adjusted_amount for line in lines), Decimal('0'))
        bill.net_amount = sum((line.net_amount for line in lines), Decimal('0'))
        line_receivable_dates = [line.receivable_date for line in lines if line.receivable_date]
        line_due_dates = [line.due_date for line in lines if line.due_date]
        if line_receivable_dates:
            bill.receivable_date = min(line_receivable_dates)
        if line_due_dates:
            bill.due_date = min(line_due_dates)
        bill.confirm_status = confirm_status
        bill.save(update_fields=[
            'amount', 'adjusted_amount', 'net_amount', 'receivable_date', 'due_date',
            'confirm_status',
        ])

    return {
        'bill': bill,
        'created_lines': created_lines,
        'skipped_lines': len(preview['rows']) - created_lines,
        'preview': preview,
    }


class RevenueContractGenerateReceivablesView(View):
    template_name = 'netbox_contract/revenue_generate_receivables.html'

    def get(self, request, pk):
        contract = get_object_or_404(plugin_models.RevenueContract, pk=pk)
        form = forms.RevenueReceivableGenerationForm()
        return render(request, self.template_name, {'object': contract, 'form': form})

    def post(self, request, pk):
        contract = get_object_or_404(plugin_models.RevenueContract, pk=pk)
        form = forms.RevenueReceivableGenerationForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'object': contract, 'form': form})

        billing_period = form.cleaned_data['billing_period']
        confirm_status = form.cleaned_data['confirm_status']
        if request.POST.get('confirm') == '1':
            result = generate_receivables_for_contract(contract, billing_period, confirm_status)
            messages.success(request, f"\u5df2\u751f\u6210\u5e94\u6536\u660e\u7ec6 {result['created_lines']} \u6761\uff0c\u8df3\u8fc7 {result['skipped_lines']} \u6761\u3002")
            return redirect(contract.get_absolute_url())

        preview = preview_receivables_for_contract(contract, billing_period)
        return render(
            request,
            self.template_name,
            {
                'object': contract,
                'form': form,
                'preview': preview,
                'billing_period': billing_period,
                'confirm_status': confirm_status,
            },
        )

def _money_percent(numerator, denominator):
    if not denominator:
        return '0%'
    percentage = (numerator / denominator * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    return f'{percentage}%'


def _url_for(obj):
    try:
        return obj.get_absolute_url()
    except Exception:
        return ''



def _month_period(year, month):
    return f'{year:04d}-{month:02d}'


def _safe_rate_value(numerator, denominator):
    if not denominator:
        return 0
    value = numerator / denominator * 100
    if value < 0:
        return 0
    if value > 100:
        return 100
    return int(value.quantize(Decimal('1')))


def _build_revenue_contract_calendar(instance, receivable_bills, chain_rows, contract_lines, versions, today=None):
    today = today or date.today()
    years = set()
    for bill in receivable_bills:
        try:
            years.add(int(str(bill.billing_period)[:4]))
        except (TypeError, ValueError):
            pass
    for contract_line in contract_lines:
        if contract_line.valid_from:
            years.add(contract_line.valid_from.year)
        if contract_line.valid_to:
            years.add(contract_line.valid_to.year)
    for version in versions:
        if version.start_date:
            years.add(version.start_date.year)
        if version.end_date:
            years.add(version.end_date.year)
    if not years:
        years.add(today.year)

    selected_year = today.year if today.year in years else max(years)
    bills_by_period = {}
    for bill in receivable_bills:
        bills_by_period.setdefault(bill.billing_period, []).append(bill)

    rows_by_period = {}
    for row in chain_rows:
        rows_by_period.setdefault(row['billing_period'], []).append(row)

    months = []
    for month in range(1, 13):
        period = _month_period(selected_year, month)
        bills = bills_by_period.get(period, [])
        rows = rows_by_period.get(period, [])
        receivable_total = sum((row.get('net_amount', Decimal('0')) for row in rows), Decimal('0'))
        invoiced_total = sum((row['mapped_amount'] for row in rows), Decimal('0'))
        receipt_total = sum((row['receipted_amount'] for row in rows), Decimal('0'))
        uninvoiced_total = receivable_total - invoiced_total
        unreceived_total = receivable_total - receipt_total
        overdue_total = sum((row.get('overdue_amount', Decimal('0')) for row in rows), Decimal('0'))
        invoice_count = sum(
            1 for row in rows for mapping in row['mappings'] if mapping['mapping'].status == 'active'
        )
        receipt_count = sum(
            1 for row in rows for allocation in row['receipt_allocations'] if allocation.status == 'active'
        )
        contract_line_count = len({row['contract_line'].pk for row in rows if row.get('contract_line')})
        has_amount_error = invoiced_total > receivable_total or receipt_total > receivable_total
        overdue = overdue_total > 0

        if has_amount_error:
            status = 'error'
            status_label = '\u91d1\u989d\u5f02\u5e38'
            risk_level = 'danger'
            risk_label = '\u91d1\u989d\u4e0d\u95ed\u5408'
        elif not bills:
            status = 'not_generated'
            status_label = '\u672a\u751f\u6210'
            risk_level = 'muted'
            risk_label = '\u672a\u751f\u6210\u5e94\u6536'
        elif overdue:
            status = 'overdue'
            status_label = '\u903e\u671f\u672a\u56de\u6b3e'
            risk_level = 'danger'
            risk_label = '\u9700\u5173\u6ce8\u56de\u6b3e'
        elif receipt_total >= receivable_total and receivable_total > 0:
            status = 'paid'
            status_label = '\u5df2\u56de\u6b3e'
            risk_level = 'success'
            risk_label = '\u6b63\u5e38'
        elif receipt_total > 0:
            status = 'partial_receipt'
            status_label = '\u90e8\u5206\u56de\u6b3e'
            risk_level = 'warning'
            risk_label = '\u5c1a\u6709\u672a\u56de\u6b3e'
        elif invoiced_total >= receivable_total and receivable_total > 0:
            status = 'invoiced'
            status_label = '\u5df2\u5f00\u7968'
            risk_level = 'info'
            risk_label = '\u5f85\u56de\u6b3e'
        elif invoiced_total > 0:
            status = 'partial_invoice'
            status_label = '\u90e8\u5206\u5f00\u7968'
            risk_level = 'warning'
            risk_label = '\u5c1a\u6709\u672a\u5f00\u7968'
        else:
            status = 'generated'
            status_label = '\u5df2\u751f\u6210'
            risk_level = 'info'
            risk_label = '\u5f85\u5f00\u7968'

        months.append({
            'month': month,
            'month_label': f'{selected_year}\u5e74{month}\u6708',
            'billing_period': period,
            'status': status,
            'status_label': status_label,
            'risk_level': risk_level,
            'risk_label': risk_label,
            'receivable_total': receivable_total,
            'invoiced_total': invoiced_total,
            'receipt_total': receipt_total,
            'uninvoiced_total': uninvoiced_total,
            'unreceived_total': unreceived_total,
            'overdue_total': overdue_total,
            'invoice_rate': _money_percent(invoiced_total, receivable_total),
            'receipt_rate': _money_percent(receipt_total, receivable_total),
            'invoice_rate_value': _safe_rate_value(invoiced_total, receivable_total),
            'receipt_rate_value': _safe_rate_value(receipt_total, receivable_total),
            'bill_count': len(bills),
            'line_count': len(rows),
            'invoice_count': invoice_count,
            'receipt_count': receipt_count,
            'contract_line_count': contract_line_count,
            'chain_rows': rows,
        })

    return {
        'year': selected_year,
        'years': sorted(years),
        'months': months,
        'totals': {
            'receivable_total': sum((month['receivable_total'] for month in months), Decimal('0')),
            'invoiced_total': sum((month['invoiced_total'] for month in months), Decimal('0')),
            'receipt_total': sum((month['receipt_total'] for month in months), Decimal('0')),
            'generated_months': sum(1 for month in months if month['bill_count']),
            'risk_months': sum(1 for month in months if month['risk_level'] in ('warning', 'danger')),
            'not_generated_months': sum(1 for month in months if month['status'] == 'not_generated'),
        },
    }


def _build_hybrid_month_summary(calendar, mixed_lanes):
    planned_by_period = {}
    for lane in mixed_lanes.get('lanes', ()):
        for cell in lane.get('cells', ()):
            planned_by_period[cell['billing_period']] = (
                planned_by_period.get(cell['billing_period'], Decimal('0'))
                + cell.get('planned_amount', Decimal('0'))
            )

    months = []
    for calendar_month in calendar.get('months', ()):
        planned_total = planned_by_period.get(calendar_month['billing_period'], Decimal('0'))
        if not calendar_month['line_count'] and planned_total <= 0:
            continue
        month = dict(calendar_month)
        month['planned_total'] = planned_total
        if not month['line_count'] and planned_total > 0:
            month.update({
                'status': 'planned',
                'status_label': '周期计划',
                'risk_level': 'muted',
                'risk_label': '尚未形成应收',
            })
        months.append(month)

    return {
        'year': calendar.get('year'),
        'months': months,
        'totals': {
            'displayed_months': len(months),
            'generated_months': sum(1 for month in months if month['bill_count']),
            'planned_months': sum(1 for month in months if month['planned_total'] > 0),
            'risk_months': sum(
                1 for month in months if month['risk_level'] in ('warning', 'danger')
            ),
            'planned_total': sum(
                (month['planned_total'] for month in months),
                Decimal('0'),
            ),
        },
    }


def _choice_label(obj, field_name):
    display = getattr(obj, f'get_{field_name}_display', None)
    if callable(display):
        return display()
    return getattr(obj, field_name, '') or '-'


def _stage_status_for_amounts(planned_amount, receivable_total, invoiced_total, receipt_total, due_date, *, today=None):
    today = today or date.today()
    if receipt_total >= planned_amount and planned_amount > 0:
        return 'completed', '\u5df2\u5b8c\u6210', 'success', '\u9636\u6bb5\u5df2\u56de\u6b3e\u5b8c\u6210'
    if due_date and due_date < today and receipt_total < planned_amount:
        return 'overdue', '\u903e\u671f\u672a\u56de\u6b3e', 'danger', '\u9636\u6bb5\u56de\u6b3e\u6ede\u540e'
    if receipt_total > 0:
        return 'partial_receipt', '\u90e8\u5206\u56de\u6b3e', 'warning', '\u5c1a\u6709\u672a\u56de\u6b3e'
    if invoiced_total >= planned_amount and planned_amount > 0:
        return 'invoiced', '\u5df2\u5f00\u7968', 'info', '\u5f85\u56de\u6b3e'
    if invoiced_total > 0:
        return 'partial_invoice', '\u90e8\u5206\u5f00\u7968', 'warning', '\u5c1a\u6709\u672a\u5f00\u7968'
    if receivable_total > 0:
        return 'receivable', '\u5df2\u5f62\u6210\u5e94\u6536', 'info', '\u5f85\u5f00\u7968'
    return 'planned', '\u672a\u751f\u6210\u5e94\u6536', 'muted', '\u7b49\u5f85\u9636\u6bb5\u89e6\u53d1'


def _build_revenue_contract_timeline(
    instance, billing_rules, chain_rows, *, trigger_records=(), today=None,
):
    today = today or date.today()
    stage_contract_types = {'milestone', 'hybrid'}
    stage_rules = [rule for rule in billing_rules if rule.rule_type in ('milestone', 'one_time')]
    is_stage_contract = instance.contract_type in stage_contract_types or bool(stage_rules)
    rows_by_rule = {}
    rows_by_contract_line = {}
    triggers_by_rule = {}
    for record in trigger_records:
        rule_id = record.billing_rule_id or getattr(record.plan, 'billing_rule_id', None)
        if rule_id and record.status == 'confirmed':
            triggers_by_rule.setdefault(rule_id, []).append(record)
    for row in chain_rows:
        if row['line'].billing_rule_id:
            rows_by_rule.setdefault(row['line'].billing_rule_id, []).append(row)
        rows_by_contract_line.setdefault(row['contract_line'].pk, []).append(row)

    nodes = []
    for index, rule in enumerate(stage_rules, start=1):
        contract_line = rule.contract_line
        rows = rows_by_rule.get(rule.pk, rows_by_contract_line.get(contract_line.pk, []))
        planned_amount = contract_line.unit_price * contract_line.quantity
        receivable_total = sum((row['net_amount'] for row in rows), Decimal('0'))
        invoiced_total = sum((row['mapped_amount'] for row in rows), Decimal('0'))
        receipt_total = sum((row['receipted_amount'] for row in rows), Decimal('0'))
        unreceived_total = receivable_total - receipt_total if receivable_total else planned_amount - receipt_total
        receivable_dates = [row['receivable_date'] for row in rows if row.get('receivable_date')]
        due_dates = [row['due_date'] for row in rows if row.get('due_date')]
        actual_receivable_date = min(receivable_dates) if receivable_dates else None
        due_date = min(due_dates) if due_dates else None
        trigger_label = _choice_label(rule, 'trigger_event')
        expected_receivable_date = None
        trigger_dates = []
        if actual_receivable_date:
            date_certainty = 'actual'
            date_summary = f'已形成应收 {_format_chinese_datetime(actual_receivable_date)}'
            if due_date:
                date_summary += f' · 到期 {_format_chinese_datetime(due_date)}'
        else:
            confirmed_triggers = triggers_by_rule.get(rule.pk, [])
            trigger_dates = sorted({record.actual_trigger_date for record in confirmed_triggers})
            if len(trigger_dates) == 1:
                expected_receivable_date = trigger_dates[0] + timedelta(days=rule.trigger_offset_days)
                date_certainty = 'fixed'
                date_summary = (
                    f'{trigger_label}已于 {_format_chinese_datetime(trigger_dates[0])} 确认'
                    f' · 预计 {_format_chinese_datetime(expected_receivable_date)} 形成应收'
                )
            elif len(trigger_dates) > 1:
                expected_receivable_date = None
                date_certainty = 'pending_trigger'
                date_summary = f'{trigger_label}存在多个确认日期 · 请先核对触发记录'
            else:
                expected_receivable_date = None
                date_certainty = 'pending_trigger'
                date_summary = f'待{trigger_label}触发 · 应收形成日待确定'
        status, status_label, risk_level, risk_label = _stage_status_for_amounts(
            planned_amount,
            receivable_total,
            invoiced_total,
            receipt_total,
            due_date,
            today=today,
        )
        if len(trigger_dates) > 1:
            status, status_label = 'ambiguous_trigger', '触发日期待核对'
            risk_level, risk_label = 'warning', '存在多个确认触发日期'
        nodes.append({
            'index': index,
            'rule': rule,
            'rule_url': _url_for(rule),
            'contract_line': contract_line,
            'contract_line_url': _url_for(contract_line),
            'project': contract_line.project,
            'stage_name': contract_line.charge_item,
            'trigger_label': trigger_label,
            'rule_type_label': _choice_label(rule, 'rule_type'),
            'original_planned_date': None,
            'current_planned_date': None,
            'expected_receivable_date': expected_receivable_date if not actual_receivable_date else None,
            'actual_receivable_date': actual_receivable_date,
            'actual_receivable_date_label': _format_chinese_datetime(actual_receivable_date) if actual_receivable_date else '',
            'due_date': due_date,
            'due_date_label': _format_chinese_datetime(due_date) if due_date else '',
            'date_certainty': date_certainty,
            'date_summary': date_summary,
            'timeline_sort_date': due_date or actual_receivable_date or expected_receivable_date,
            'delay_days': max((today - due_date).days, 0) if due_date and receipt_total < planned_amount else 0,
            'planned_amount': planned_amount,
            'receivable_total': receivable_total,
            'invoiced_total': invoiced_total,
            'receipt_total': receipt_total,
            'unreceived_total': unreceived_total,
            'receivable_rate': _money_percent(receivable_total, planned_amount),
            'invoice_rate': _money_percent(invoiced_total, planned_amount),
            'receipt_rate': _money_percent(receipt_total, planned_amount),
            'receivable_rate_value': _safe_rate_value(receivable_total, planned_amount),
            'invoice_rate_value': _safe_rate_value(invoiced_total, planned_amount),
            'receipt_rate_value': _safe_rate_value(receipt_total, planned_amount),
            'status': status,
            'status_label': status_label,
            'risk_level': risk_level,
            'risk_label': risk_label,
            'chain_rows': rows,
            'line_count': len(rows),
        })

    nodes.sort(key=lambda node: (node['timeline_sort_date'] or date.max, node['index']))
    for index, node in enumerate(nodes, start=1):
        node['index'] = index

    return {
        'is_stage_contract': is_stage_contract,
        'nodes': nodes,
        'totals': {
            'planned_amount': sum((node['planned_amount'] for node in nodes), Decimal('0')),
            'receivable_total': sum((node['receivable_total'] for node in nodes), Decimal('0')),
            'invoiced_total': sum((node['invoiced_total'] for node in nodes), Decimal('0')),
            'receipt_total': sum((node['receipt_total'] for node in nodes), Decimal('0')),
            'risk_nodes': sum(1 for node in nodes if node['risk_level'] in ('warning', 'danger')),
            'completed_nodes': sum(1 for node in nodes if node['status'] == 'completed'),
            'pending_trigger_nodes': sum(1 for node in nodes if node['date_certainty'] == 'pending_trigger'),
        },
    }


def _build_revenue_contract_workspace(instance):
    receivable_bills = list(plugin_models.RevenueReceivableBill.objects.filter(contract=instance).select_related('customer', 'project'))
    receivable_lines = list(
        plugin_models.RevenueReceivableLine.objects.filter(bill__contract=instance)
        .select_related('bill', 'contract_line', 'contract_line__revenue_order', 'billing_rule')
        .order_by('bill__billing_period', 'start_date')
    )
    invoice_mappings = list(
        plugin_models.RevenueInvoiceMapping.objects.filter(receivable_line__bill__contract=instance)
        .select_related('receivable_line', 'invoice_line', 'invoice_line__invoice')
    )
    receipt_allocations = list(
        plugin_models.RevenueReceiptAllocation.objects.filter(receivable_line__bill__contract=instance)
        .select_related('receipt', 'receivable_line', 'invoice_mapping')
    )
    invoices = list(
        plugin_models.RevenueInvoice.objects.filter(lines__receivable_mappings__receivable_line__bill__contract=instance)
        .distinct()
        .order_by('-invoice_date', 'invoice_code')
    )
    receipts = list(
        plugin_models.RevenueReceipt.objects.filter(allocations__receivable_line__bill__contract=instance)
        .distinct()
        .order_by('-receipt_date', 'bank_flow_no')
    )
    contract_lines = list(instance.lines.select_related('project', 'contract_version', 'revenue_order').order_by('project__name', 'charge_item'))
    billing_rules = list(plugin_models.RevenueBillingRule.objects.filter(contract_line__contract=instance).select_related('contract_line', 'contract_version'))
    billing_segments = list(plugin_models.RevenueBillingSegment.objects.filter(contract_line__contract=instance).select_related('contract_line', 'billing_rule'))
    versions = list(instance.versions.all().order_by('-start_date', 'version_code'))
    projects = list(instance.contract_projects.select_related('project'))
    revenue_orders = list(instance.orders.select_related('project').order_by('project__name', 'order_code'))
    receivable_plans = list(
        instance.receivable_plans.select_related('contract_line', 'billing_rule').order_by('plan_code')
    )
    plan_versions = list(
        plugin_models.RevenueReceivablePlanVersion.objects.filter(plan__contract=instance)
        .select_related('plan')
        .order_by('plan', 'version_no')
    )
    trigger_records = list(
        plugin_models.RevenueTriggerRecord.objects.filter(
            Q(billing_rule__contract_line__contract=instance) | Q(plan__contract=instance),
        )
        .select_related('billing_rule', 'billing_rule__contract_line', 'plan', 'plan_version')
        .distinct()
        .order_by('actual_trigger_date', 'pk')
    )
    adjustment_records = list(
        plugin_models.RevenueAdjustmentRecord.objects.filter(
            Q(plan__contract=instance) | Q(receivable_line__bill__contract=instance)
        )
        .select_related('plan', 'receivable_line', 'receivable_line__bill')
        .distinct()
        .order_by('adjustment_date', 'pk')
    )

    rules_by_contract_line = {}
    for rule in billing_rules:
        rules_by_contract_line.setdefault(rule.contract_line_id, []).append(rule)

    segments_by_contract_line = {}
    for segment in billing_segments:
        segments_by_contract_line.setdefault(segment.contract_line_id, []).append(segment)

    receivable_lines_by_bill = {}
    for line in receivable_lines:
        receivable_lines_by_bill.setdefault(line.bill_id, []).append(line)

    invoice_lines_by_invoice = {}
    for invoice_line in plugin_models.RevenueInvoiceLine.objects.filter(invoice__in=invoices).select_related('invoice').order_by('invoice', 'line_no'):
        invoice_lines_by_invoice.setdefault(invoice_line.invoice_id, []).append(invoice_line)

    mappings_by_invoice_line = {}
    for mapping in invoice_mappings:
        mappings_by_invoice_line.setdefault(mapping.invoice_line_id, []).append(mapping)

    allocations_by_receipt = {}
    for allocation in receipt_allocations:
        allocations_by_receipt.setdefault(allocation.receipt_id, []).append(allocation)

    chain_rows = build_revenue_event_rows(
        receivable_lines,
        invoice_mappings,
        receipt_allocations,
        url_for=_url_for,
    )
    event_summary = summarize_revenue_events(chain_rows, receivable_bills)
    adjustments_by_line = {}
    for adjustment in adjustment_records:
        if adjustment.receivable_line_id:
            adjustments_by_line.setdefault(adjustment.receivable_line_id, []).append(adjustment)
    for row in chain_rows:
        row['adjustment_records'] = adjustments_by_line.get(row['line'].pk, [])
    plan_tracks = build_receivable_plan_tracks(
        receivable_plans,
        plan_versions,
        trigger_records,
        adjustment_records,
        event_summary['confirmed_rows'],
        url_for=_url_for,
    )
    receivable_total = event_summary['receivable_total']
    invoiced_total = event_summary['invoiced_total']
    receipt_total = event_summary['receipt_total']
    contract_amount = instance.total_amount or Decimal('0')

    contract_line_groups = []
    for contract_line in contract_lines:
        related_rows = [
            row
            for row in event_summary['confirmed_rows']
            if row['contract_line'].pk == contract_line.pk
        ]
        contract_line_groups.append({
            'contract_line': contract_line,
            'url': _url_for(contract_line),
            'project': contract_line.project,
            'version': contract_line.contract_version,
            'rules': rules_by_contract_line.get(contract_line.pk, []),
            'segments': segments_by_contract_line.get(contract_line.pk, []),
            'receivable_count': len(related_rows),
            'receivable_total': sum((row['net_amount'] for row in related_rows), Decimal('0')),
        })

    event_rows_by_bill = {}
    for row in chain_rows:
        event_rows_by_bill.setdefault(row['bill'].pk, []).append(row)

    receivable_bill_groups = []
    for bill in receivable_bills:
        lines = receivable_lines_by_bill.get(bill.pk, [])
        bill_rows = event_rows_by_bill.get(bill.pk, [])
        calculated_net_amount = sum((row['net_amount'] for row in bill_rows), Decimal('0'))
        calculated_invoiced_amount = sum((row['mapped_amount'] for row in bill_rows), Decimal('0'))
        calculated_receipted_amount = sum((row['receipted_amount'] for row in bill_rows), Decimal('0'))
        receivable_bill_groups.append({
            'bill': bill,
            'url': _url_for(bill),
            'lines': lines,
            'line_count': len(lines),
            'net_amount': calculated_net_amount,
            'invoiced_amount': calculated_invoiced_amount,
            'receipted_amount': calculated_receipted_amount,
            'unbilled_amount': calculated_net_amount - calculated_invoiced_amount,
            'unreceived_amount': calculated_net_amount - calculated_receipted_amount,
        })

    invoice_groups = []
    for invoice in invoices:
        invoice_lines = invoice_lines_by_invoice.get(invoice.pk, [])
        invoice_groups.append({
            'invoice': invoice,
            'url': _url_for(invoice),
            'lines': [
                {
                    'invoice_line': invoice_line,
                    'url': _url_for(invoice_line),
                    'mappings': mappings_by_invoice_line.get(invoice_line.pk, []),
                    'mapped_amount': sum((m.mapped_amount for m in mappings_by_invoice_line.get(invoice_line.pk, []) if m.status == 'active'), Decimal('0')),
                }
                for invoice_line in invoice_lines
            ],
        })

    receipt_groups = []
    for receipt in receipts:
        allocations = allocations_by_receipt.get(receipt.pk, [])
        active_allocations = [allocation for allocation in allocations if allocation.status == 'active']
        contract_allocated_amount = sum(
            (allocation.allocated_amount for allocation in active_allocations),
            Decimal('0'),
        )
        receipt_groups.append({
            'receipt': receipt,
            'url': _url_for(receipt),
            'allocations': allocations,
            'allocation_count': len(active_allocations),
            'allocated_amount': contract_allocated_amount,
            'allocation_rate': _money_percent(contract_allocated_amount, receipt.amount),
        })

    calendar = _build_revenue_contract_calendar(
        instance,
        event_summary['confirmed_bills'],
        event_summary['confirmed_rows'],
        contract_lines,
        versions,
    )
    has_stage_rules = any(
        rule.rule_type in ('milestone', 'one_time')
        for rule in billing_rules
    )
    if instance.contract_type in ('milestone', 'hybrid') or has_stage_rules:
        timeline = _build_revenue_contract_timeline(
            instance,
            billing_rules,
            event_summary['confirmed_rows'],
            trigger_records=trigger_records,
        )
    else:
        timeline = {
            'is_stage_contract': False,
            'nodes': [],
            'totals': {
                'receivable_total': Decimal('0'),
                'invoiced_total': Decimal('0'),
                'receipt_total': Decimal('0'),
                'risk_nodes': 0,
                'completed_nodes': 0,
                'pending_trigger_nodes': 0,
            },
        }

    if instance.contract_type == 'recurring':
        periodic_matrix = build_periodic_matrix(
            contract_lines,
            billing_rules,
            event_summary['confirmed_rows'],
            year=calendar['year'],
        )
    else:
        periodic_matrix = {
            'year': calendar['year'],
            'months': [],
            'rows': [],
            'has_recurring_lines': False,
            'totals': {},
        }

    if instance.contract_type in ('framework', 'order', 'hybrid'):
        order_lanes = build_order_lanes(
            instance,
            revenue_orders,
            contract_lines,
            event_summary['confirmed_rows'],
            year=calendar['year'],
            url_for=_url_for,
        )
    else:
        order_lanes = {
            'year': calendar['year'],
            'lanes': [],
            'should_display': False,
            'order_count': 0,
            'legacy_count': 0,
            'unfiled_count': 0,
        }

    if instance.contract_type == 'hybrid':
        mixed_lanes = build_mixed_lanes(
            instance,
            contract_lines,
            billing_rules,
            event_summary['confirmed_rows'],
            year=calendar['year'],
        )
    else:
        mixed_lanes = {
            'year': calendar['year'],
            'months': [],
            'lanes': [],
            'should_display': False,
            'totals': {},
        }
    hybrid_month_summary = (
        _build_hybrid_month_summary(calendar, mixed_lanes)
        if instance.contract_type == 'hybrid'
        else {'year': calendar['year'], 'months': [], 'totals': {}}
    )

    return {
        'overview': {
            'contract_amount': contract_amount,
            'receivable_total': receivable_total,
            'invoiced_total': invoiced_total,
            'receipt_total': receipt_total,
            'contract_gap': contract_amount - receivable_total,
            'uninvoiced_total': event_summary['uninvoiced_total'],
            'unreceived_total': event_summary['unreceived_total'],
            'overdue_total': event_summary['overdue_total'],
            'reconciliation': event_summary['reconciliation'],
            'invoice_rate': _money_percent(invoiced_total, contract_amount),
            'receipt_rate': _money_percent(receipt_total, receivable_total),
            'receivable_rate': _money_percent(receivable_total, contract_amount),
            'project_count': len(projects),
            'version_count': len(versions),
            'contract_line_count': len(contract_lines),
            'bill_count': len(receivable_bills),
            'invoice_count': len(invoices),
            'receipt_count': len(receipts),
            'open_item_count': event_summary['open_item_count'],
            'plan_count': len(receivable_plans),
            'plan_variance_count': plan_tracks['totals']['variance_count'],
        },
        'projects': projects,
        'orders': revenue_orders,
        'versions': versions,
        'chain_rows': chain_rows,
        'contract_line_groups': contract_line_groups,
        'receivable_bill_groups': receivable_bill_groups,
        'invoice_groups': invoice_groups,
        'receipt_groups': receipt_groups,
        'calendar': calendar,
        'timeline': timeline,
        'periodic_matrix': periodic_matrix,
        'order_lanes': order_lanes,
        'mixed_lanes': mixed_lanes,
        'hybrid_month_summary': hybrid_month_summary,
        'plan_tracks': plan_tracks,
        'contract_lines': contract_lines,
        'billing_rules': billing_rules,
        'trigger_records': trigger_records,
        'adjustment_records': adjustment_records,
    }

_REVENUE_EVENT_FILTER_KEYS = (
    'event_project',
    'event_order',
    'event_period',
    'event_status',
    'event_risk',
)


def _revenue_event_order(row):
    contract_line = row.get('contract_line')
    order = getattr(contract_line, 'revenue_order', None)
    if order:
        return f'order:{order.pk}', str(order)
    legacy_order_id = getattr(contract_line, 'order_id', '') or ''
    if legacy_order_id:
        return f'legacy:{legacy_order_id}', legacy_order_id
    return 'unfiled', '未归属订单'


def _build_revenue_contract_event_detail(chain_rows, params):
    rows = list(chain_rows)
    project_options = {}
    order_options = {}
    period_options = set()
    status_options = {}
    risk_labels = {
        'danger': '高风险',
        'warning': '需关注',
        'info': '进行中',
        'success': '已完成',
        'muted': '普通',
    }

    for row in rows:
        project = getattr(row.get('contract_line'), 'project', None)
        if project:
            project_options[str(project.pk)] = str(project)
        order_key, order_label = _revenue_event_order(row)
        order_options[order_key] = order_label
        row['detail_order_key'] = order_key
        row['detail_order_label'] = order_label
        period_options.add(row.get('billing_period') or '')
        if row.get('is_confirmed'):
            status_key = row.get('collection_status') or 'unknown'
            status_label = row.get('collection_status_label') or '未知状态'
        else:
            status_key = f"confirm:{row.get('confirm_status') or 'unknown'}"
            bill = row.get('bill')
            display = getattr(bill, 'get_confirm_status_display', None)
            status_label = f"确认状态：{display() if callable(display) else row.get('confirm_status') or '未知'}"
        row['detail_status_key'] = status_key
        row['detail_badge_class'] = {
            'danger': 'text-bg-danger',
            'warning': 'text-bg-warning',
            'info': 'text-bg-info',
            'success': 'text-bg-success',
            'muted': 'text-bg-secondary',
        }.get(row.get('risk_level'), 'text-bg-secondary')
        row['detail_status_label'] = status_label
        status_options[status_key] = status_label

    values = {
        key: (params.get(key) or '').strip()
        for key in _REVENUE_EVENT_FILTER_KEYS
    }
    filtered_rows = []
    for row in rows:
        project = getattr(row.get('contract_line'), 'project', None)
        if values['event_project'] and str(getattr(project, 'pk', '')) != values['event_project']:
            continue
        if values['event_order'] and row['detail_order_key'] != values['event_order']:
            continue
        if values['event_period'] and row.get('billing_period') != values['event_period']:
            continue
        if values['event_status'] and row['detail_status_key'] != values['event_status']:
            continue
        if values['event_risk'] and row.get('risk_level') != values['event_risk']:
            continue
        filtered_rows.append(row)

    active_values = {key: value for key, value in values.items() if value}
    return {
        'rows': filtered_rows,
        'values': values,
        'active_count': len(active_values),
        'query_string': urlencode(active_values),
        'total_count': len(rows),
        'filtered_count': len(filtered_rows),
        'totals': {
            'receivable': sum((row['net_amount'] for row in filtered_rows), Decimal('0')),
            'invoiced': sum((row['mapped_amount'] for row in filtered_rows), Decimal('0')),
            'received': sum((row['receipted_amount'] for row in filtered_rows), Decimal('0')),
            'unreceived': sum((row['unreceived_amount'] for row in filtered_rows), Decimal('0')),
        },
        'projects': sorted(project_options.items(), key=lambda item: item[1]),
        'orders': sorted(order_options.items(), key=lambda item: item[1]),
        'periods': sorted((period for period in period_options if period), reverse=True),
        'statuses': sorted(status_options.items(), key=lambda item: item[1]),
        'risks': [
            (key, risk_labels[key])
            for key in ('danger', 'warning', 'info', 'success', 'muted')
            if any(row.get('risk_level') == key for row in rows)
        ],
    }


def _revenue_contract_context(request, instance):
    workspace = _build_revenue_contract_workspace(instance)
    overview = workspace['overview']
    event_detail = _build_revenue_contract_event_detail(workspace['chain_rows'], request.GET)
    def preserved_params(excluded):
        return [
            {'name': key, 'value': value}
            for key in request.GET
            if key not in excluded
            for value in request.GET.getlist(key)
        ]

    periodic_matrix_view = filter_periodic_matrix(
        workspace['periodic_matrix'],
        anomalies_only=request.GET.get('matrix_anomalies') == '1',
    )
    periodic_matrix_view['hidden_params'] = preserved_params({'matrix_anomalies'})

    stage_mode = request.GET.get('stage_mode') or 'all'
    try:
        stage_timeline_view = filter_stage_timeline(
            workspace['timeline'],
            mode=stage_mode,
        )
    except ValueError:
        stage_mode = 'all'
        stage_timeline_view = filter_stage_timeline(workspace['timeline'], mode=stage_mode)
    stage_timeline_view['hidden_params'] = preserved_params({'stage_mode'})

    order_lanes_view = filter_order_lanes(
        workspace['order_lanes'],
        project=request.GET.get('order_project'),
        order_status=request.GET.get('order_status'),
    )
    order_lanes_view['hidden_params'] = preserved_params(
        {'order_project', 'order_status'}
    )

    mixed_projection = request.GET.get('mixed_view') or 'charge_item'
    try:
        mixed_lanes_view = filter_mixed_lanes(
            workspace['mixed_lanes'],
            view_by=mixed_projection,
            selected=request.GET.get('mixed_selected'),
        )
    except ValueError:
        mixed_projection = 'charge_item'
        mixed_lanes_view = filter_mixed_lanes(
            workspace['mixed_lanes'],
            view_by=mixed_projection,
        )
    mixed_lanes_view['hidden_params'] = preserved_params(
        {'mixed_view', 'mixed_selected'}
    )
    contract_views = {
        'periodic_matrix': periodic_matrix_view,
        'stage_timeline': stage_timeline_view,
        'order_lanes': order_lanes_view,
        'mixed_lanes': mixed_lanes_view,
    }

    timeline_profile = build_timeline_view_profile(instance.contract_type)
    default_timeline_filter = timeline_profile['default_filter']
    timeline_filter = request.GET.get('timeline_window') or default_timeline_filter
    try:
        unified_timeline = build_revenue_timeline(
            workspace['chain_rows'],
            {},
            filter_key=timeline_filter,
            contract_lines=workspace['contract_lines'],
            billing_rules=workspace['billing_rules'],
            trigger_records=workspace['trigger_records'],
        )
    except ValueError:
        timeline_filter = default_timeline_filter
        unified_timeline = build_revenue_timeline(
            workspace['chain_rows'],
            {},
            filter_key=timeline_filter,
            contract_lines=workspace['contract_lines'],
            billing_rules=workspace['billing_rules'],
            trigger_records=workspace['trigger_records'],
        )
    timeline_profile = build_timeline_view_profile(
        instance.contract_type,
        active_filter=timeline_filter,
    )
    timeline_filters = timeline_profile['filters']
    unified_timeline.update(timeline_profile)
    unified_timeline['filters'] = []
    for key, label in timeline_filters:
        query = request.GET.copy()
        query['timeline_window'] = key
        unified_timeline['filters'].append({
            'key': key,
            'label': label,
            'count': unified_timeline['filter_counts'][key],
            'is_active': key == timeline_filter,
            'query_string': query.urlencode(),
        })
    contract_type_profile = {
        'milestone': {
            'label': '\u9636\u6bb5\u6027', 'tone': 'blue', 'title': '\u6309\u91cc\u7a0b\u7891\u8ddf\u8e2a\u6536\u5165',
            'description': '\u4ee5\u9a8c\u6536\u3001\u4ea4\u4ed8\u7b49\u5173\u952e\u8282\u70b9\u4e3a\u4e3b\u7ebf\uff0c\u805a\u7126\u5404\u9636\u6bb5\u5e94\u6536\u3001\u5f00\u7968\u548c\u56de\u6b3e\u5b8c\u6210\u60c5\u51b5\u3002',
            'calendar_title': '\u9636\u6bb5\u5e94\u6536\u8d26\u671f', 'focus_title': '\u9636\u6bb5\u6267\u884c\u6982\u89c8',
            'highlights': (('\u91cc\u7a0b\u7891', len(workspace['timeline']['nodes'])), ('\u5df2\u5b8c\u6210', workspace['timeline']['totals']['completed_nodes']), ('\u98ce\u9669\u8282\u70b9', workspace['timeline']['totals']['risk_nodes'])),
        },
        'recurring': {
            'label': '\u5468\u671f\u6027', 'tone': 'green', 'title': '\u6309\u8d26\u671f\u7ba1\u7406\u6301\u7eed\u6536\u5165',
            'description': '\u4ee5\u6708\u3001\u5b63\u6216\u5e74\u5ea6\u8d26\u671f\u4e3a\u4e3b\u7ebf\uff0c\u4f18\u5148\u5173\u6ce8\u5e94\u6536\u751f\u6210\u8fde\u7eed\u6027\u548c\u5404\u671f\u56de\u6b3e\u60c5\u51b5\u3002',
            'calendar_title': '\u5468\u671f\u5e94\u6536\u65e5\u5386', 'focus_title': '\u5468\u671f\u6267\u884c\u6982\u89c8',
            'highlights': (('\u5df2\u751f\u6210\u8d26\u671f', workspace['calendar']['totals']['generated_months']), ('\u98ce\u9669\u8d26\u671f', workspace['calendar']['totals']['risk_months']), ('\u5e94\u6536\u56de\u6b3e\u7387', overview['receipt_rate'])),
        },
        'framework': {
            'label': '\u6846\u67b6', 'tone': 'purple', 'title': '\u4ece\u6846\u67b6\u989d\u5ea6\u5230\u9879\u76ee\u627f\u63a5',
            'description': '\u4ee5\u5408\u540c\u603b\u989d\u548c\u9879\u76ee\u627f\u63a5\u4e3a\u4e3b\u7ebf\uff0c\u5173\u6ce8\u989d\u5ea6\u8f6c\u5316\u3001\u5408\u540c\u9879\u843d\u5730\u53ca\u5e94\u6536\u8986\u76d6\u3002',
            'calendar_title': '\u6846\u67b6\u5408\u540c\u8c03\u7528\u8d26\u671f', 'focus_title': '\u989d\u5ea6\u4e0e\u627f\u63a5\u6982\u89c8',
            'highlights': (('\u6846\u67b6\u989d\u5ea6', overview['contract_amount']), ('\u8ba2\u5355/\u5f00\u5de5\u5355', workspace['order_lanes']['order_count']), ('\u5e94\u6536\u8f6c\u5316', overview['receivable_rate'])),
        },
        'order': {
            'label': '\u8ba2\u5355', 'tone': 'cyan', 'title': '\u6309\u8ba2\u5355\u5c65\u7ea6\u8ddf\u8e2a\u6536\u5165',
            'description': '\u4ee5\u5408\u540c\u9879\u548c\u5e94\u6536\u94fe\u8def\u4e3a\u4e3b\u7ebf\uff0c\u5feb\u901f\u6838\u5bf9\u8ba2\u5355\u5e94\u6536\u3001\u5f00\u7968\u4e0e\u56de\u6b3e\u3002',
            'calendar_title': '\u8ba2\u5355\u5c65\u7ea6\u8d26\u671f', 'focus_title': '\u8ba2\u5355\u5c65\u7ea6\u6982\u89c8',
            'highlights': (('\u8ba2\u5355/\u5f00\u5de5\u5355', workspace['order_lanes']['order_count']), ('\u5e94\u6536\u5408\u8ba1', overview['receivable_total']), ('\u56de\u6b3e\u5b8c\u6210', overview['receipt_rate'])),
        },
        'hybrid': {
            'label': '\u6df7\u5408', 'tone': 'orange', 'title': '\u534f\u540c\u7ba1\u7406\u9636\u6bb5\u4e0e\u5468\u671f\u6536\u5165',
            'description': '\u540c\u65f6\u5448\u73b0\u91cc\u7a0b\u7891\u548c\u5468\u671f\u8d26\u671f\uff0c\u7edf\u4e00\u8ddf\u8e2a\u591a\u79cd\u8ba1\u8d39\u6a21\u5f0f\u4e0b\u7684\u5c65\u7ea6\u4e0e\u56de\u6b3e\u3002',
            'calendar_title': '\u6df7\u5408\u8ba1\u8d39\u8d26\u671f', 'focus_title': '\u6df7\u5408\u8ba1\u8d39\u6982\u89c8',
            'highlights': (('\u91cc\u7a0b\u7891', len(workspace['timeline']['nodes'])), ('\u5df2\u751f\u6210\u8d26\u671f', workspace['calendar']['totals']['generated_months']), ('\u5f85\u5904\u7406\u660e\u7ec6', overview['open_item_count'])),
        },
    }.get(instance.contract_type, {
        'label': instance.get_contract_type_display() or instance.contract_type or '\u672a\u5206\u7c7b', 'tone': 'slate', 'title': '\u6536\u5165\u5408\u540c\u6267\u884c\u6982\u89c8',
        'description': '\u7edf\u4e00\u8ddf\u8e2a\u5408\u540c\u3001\u5e94\u6536\u3001\u5f00\u7968\u548c\u56de\u6b3e\u60c5\u51b5\u3002', 'calendar_title': '\u5e94\u6536\u8d26\u671f\u65e5\u5386', 'focus_title': '\u5408\u540c\u6267\u884c\u6982\u89c8',
        'highlights': (('\u5408\u540c\u9879', overview['contract_line_count']), ('\u5e94\u6536\u5408\u8ba1', overview['receivable_total']), ('\u5e94\u6536\u56de\u6b3e\u7387', overview['receipt_rate'])),
    })
    return {
        'revenue_summary_cards': [
            {'label': '\u5408\u540c\u603b\u91d1\u989d', 'value': overview['contract_amount']},
            {'label': '\u5df2\u5f62\u6210\u5e94\u6536', 'value': overview['receivable_total']},
            {'label': '\u5df2\u5f00\u7968\u5408\u8ba1', 'value': overview['invoiced_total']},
            {'label': '\u5df2\u6536\u6b3e\u5408\u8ba1', 'value': overview['receipt_total']},
            {'label': '\u903e\u671f\u672a\u6536', 'value': overview['overdue_total']},
            {'label': '\u672a\u6536\u6b3e', 'value': overview['unreceived_total']},
        ],
        'revenue_related_panels': [],
        'revenue_contract_workspace': workspace,
        'revenue_contract_type_profile': contract_type_profile,
        'revenue_event_detail': event_detail,
        'revenue_timeline': unified_timeline,
        'revenue_contract_views': contract_views,
    }



class RevenueContractEventExportView(ObjectPermissionRequiredMixin, View):
    queryset = plugin_models.RevenueContract.objects.all()

    def get_required_permission(self):
        return 'netbox_contract.view_revenuecontract'

    def get(self, request, pk):
        instance = get_object_or_404(
            self.queryset.restrict(request.user, 'view'),
            pk=pk,
        )
        workspace = _build_revenue_contract_workspace(instance)
        detail = _build_revenue_contract_event_detail(
            workspace['chain_rows'],
            request.GET,
        )

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="contract-{instance.pk}-receivables-{date.today():%Y%m%d}.csv"'
        )
        response.write('﻿')
        writer = csv.writer(response)
        writer.writerow([
            '账期', '项目', '订单/开工单', '合同项', '应收账单', '确认/收款状态',
            '风险', '应收金额', '开票金额', '回款金额', '未回款金额', '到期日期',
        ])
        for row in detail['rows']:
            project = getattr(row.get('contract_line'), 'project', None)
            writer.writerow([
                row.get('billing_period', ''),
                _revenue_csv_value(project),
                _revenue_csv_value(row.get('detail_order_label')),
                _revenue_csv_value(row.get('contract_line')),
                _revenue_csv_value(row.get('bill')),
                row.get('detail_status_label', ''),
                row.get('risk_level', ''),
                row.get('net_amount', Decimal('0')),
                row.get('mapped_amount', Decimal('0')),
                row.get('receipted_amount', Decimal('0')),
                row.get('unreceived_amount', Decimal('0')),
                row['due_date'].isoformat() if row.get('due_date') else '',
            ])
        return response


def _revenue_receivable_bill_context(request, instance):
    lines = instance.lines.all()
    mappings = plugin_models.RevenueInvoiceMapping.objects.filter(receivable_line__bill=instance)
    receipt_allocations = plugin_models.RevenueReceiptAllocation.objects.filter(receivable_line__bill=instance)
    invoices = plugin_models.RevenueInvoice.objects.filter(lines__receivable_mappings__receivable_line__bill=instance).distinct()
    receipts = plugin_models.RevenueReceipt.objects.filter(allocations__receivable_line__bill=instance).distinct()
    return {
        'revenue_summary_cards': [
            {'label': '\u5e94\u6536\u51c0\u989d', 'value': instance.net_amount},
            {'label': '\u5df2\u5f00\u7968\u91d1\u989d', 'value': instance.invoiced_amount},
            {'label': '\u672a\u5f00\u7968\u91d1\u989d', 'value': instance.net_amount - instance.invoiced_amount},
            {'label': '\u5df2\u56de\u6b3e\u91d1\u989d', 'value': instance.receipted_amount},
            {'label': '\u672a\u56de\u6b3e\u91d1\u989d', 'value': instance.net_amount - instance.receipted_amount},
        ],
        'revenue_related_panels': [
            _make_revenue_panel(request, '\u5e94\u6536\u660e\u7ec6', tables.RevenueReceivableLineListTable, lines, ('bill',)),
            _make_revenue_panel(request, '\u53d1\u7968\u6620\u5c04', tables.RevenueInvoiceMappingListTable, mappings, ()),
            _make_revenue_panel(request, '\u53d1\u7968', tables.RevenueInvoiceListTable, invoices, ()),
            _make_revenue_panel(request, '\u56de\u6b3e', tables.RevenueReceiptListTable, receipts, ()),
            _make_revenue_panel(request, '\u56de\u6b3e\u5206\u914d', tables.RevenueReceiptAllocationListTable, receipt_allocations, ()),
        ],
    }


def _revenue_receivable_line_context(request, instance):
    mappings = instance.invoice_mappings.all()
    receipt_allocations = instance.receipt_allocations.all()
    receipt_total = _sum_amount(receipt_allocations.filter(status='active'), 'allocated_amount')
    return {
        'revenue_summary_cards': [
            {'label': '\u5e94\u6536\u51c0\u989d', 'value': instance.net_amount},
            {'label': '\u5df2\u6620\u5c04\u53d1\u7968', 'value': _sum_amount(mappings.filter(status='active'), 'mapped_amount')},
            {'label': '\u5df2\u6838\u9500\u91d1\u989d', 'value': receipt_total},
            {'label': '\u672a\u6838\u9500\u91d1\u989d', 'value': instance.net_amount - receipt_total},
        ],
        'revenue_related_panels': [
            _make_revenue_panel(request, '\u53d1\u7968\u6620\u5c04', tables.RevenueInvoiceMappingListTable, mappings, ('receivable_line',)),
            _make_revenue_panel(request, '\u56de\u6b3e\u5206\u914d', tables.RevenueReceiptAllocationListTable, receipt_allocations, ('receivable_line',)),
            _make_revenue_panel(request, '\u8c03\u6574\u8bb0\u5f55', tables.RevenueAdjustmentRecordListTable, instance.adjustment_records.all(), ('receivable_line',)),
        ],
    }


def _revenue_invoice_context(request, instance):
    lines = instance.lines.all()
    mappings = plugin_models.RevenueInvoiceMapping.objects.filter(invoice_line__invoice=instance)
    receipt_allocations = plugin_models.RevenueReceiptAllocation.objects.filter(invoice_mapping__invoice_line__invoice=instance)
    bills = plugin_models.RevenueReceivableBill.objects.filter(lines__invoice_mappings__invoice_line__invoice=instance).distinct()
    contracts = plugin_models.RevenueContract.objects.filter(receivable_bills__lines__invoice_mappings__invoice_line__invoice=instance).distinct()
    mapped_total = _sum_amount(mappings.filter(status='active'), 'mapped_amount')
    receipt_total = _sum_amount(receipt_allocations.filter(status='active'), 'allocated_amount')
    return {
        'revenue_summary_cards': [
            {'label': '\u53d1\u7968\u91d1\u989d', 'value': instance.amount},
            {'label': '\u660e\u7ec6\u5408\u8ba1', 'value': _sum_amount(lines, 'amount')},
            {'label': '\u5df2\u6620\u5c04\u5e94\u6536', 'value': mapped_total},
            {'label': '\u5df2\u6838\u9500\u91d1\u989d', 'value': receipt_total},
            {'label': '\u672a\u6838\u9500\u91d1\u989d', 'value': mapped_total - receipt_total},
        ],
        'revenue_related_panels': [
            _make_revenue_panel(request, '\u53d1\u7968\u660e\u7ec6', tables.RevenueInvoiceLineListTable, lines, ('invoice',)),
            _make_revenue_panel(request, '\u53d1\u7968\u6620\u5c04', tables.RevenueInvoiceMappingListTable, mappings, ()),
            _make_revenue_panel(request, '\u5bf9\u5e94\u5408\u540c', tables.RevenueContractListTable, contracts, ()),
            _make_revenue_panel(request, '\u5bf9\u5e94\u5e94\u6536\u8d26\u5355', tables.RevenueReceivableBillListTable, bills, ()),
            _make_revenue_panel(request, '\u56de\u6b3e\u5206\u914d', tables.RevenueReceiptAllocationListTable, receipt_allocations, ()),
        ],
    }


def _revenue_receipt_context(request, instance):
    allocations = instance.allocations.all()
    receivable_lines = plugin_models.RevenueReceivableLine.objects.filter(receipt_allocations__receipt=instance).distinct()
    bills = plugin_models.RevenueReceivableBill.objects.filter(lines__receipt_allocations__receipt=instance).distinct()
    invoices = plugin_models.RevenueInvoice.objects.filter(lines__receivable_mappings__receipt_allocations__receipt=instance).distinct()
    direct_total = _sum_amount(allocations.filter(status='active'), 'allocated_amount')
    return {
        'revenue_summary_cards': [
            {'label': '\u5230\u8d26\u91d1\u989d', 'value': instance.amount},
            {'label': '\u5df2\u5206\u914d\u91d1\u989d', 'value': instance.allocated_total},
            {'label': '\u672a\u5206\u914d\u91d1\u989d', 'value': instance.unallocated_amount},
            {'label': '\u76f4\u63a5\u6838\u9500', 'value': direct_total},
        ],
        'revenue_related_panels': [
            _make_revenue_panel(request, '\u56de\u6b3e\u5206\u914d', tables.RevenueReceiptAllocationListTable, allocations, ('receipt',)),
            _make_revenue_panel(request, '\u6d89\u53ca\u5e94\u6536\u660e\u7ec6', tables.RevenueReceivableLineListTable, receivable_lines, ()),
            _make_revenue_panel(request, '\u6d89\u53ca\u5e94\u6536\u8d26\u5355', tables.RevenueReceivableBillListTable, bills, ()),
            _make_revenue_panel(request, '\u6d89\u53ca\u53d1\u7968', tables.RevenueInvoiceListTable, invoices, ()),
        ],
    }



def _revenue_customer_context(request, instance):
    return {
        'revenue_related_panels': [
            _make_revenue_panel(request, '\u9879\u76ee', tables.RevenueProjectListTable, instance.revenue_projects.all(), ('customer',)),
            _make_revenue_panel(request, '\u6536\u5165\u5408\u540c', tables.RevenueContractListTable, instance.revenue_contracts.all(), ('customer',)),
            _make_revenue_panel(request, '\u5e94\u6536\u8d26\u5355', tables.RevenueReceivableBillListTable, instance.receivable_bills.all(), ('customer',)),
            _make_revenue_panel(request, '\u53d1\u7968', tables.RevenueInvoiceListTable, instance.revenue_invoices.all(), ('customer',)),
            _make_revenue_panel(request, '\u56de\u6b3e', tables.RevenueReceiptListTable, instance.receipts.all(), ('customer',)),
        ],
    }


def _revenue_project_context(request, instance):
    receivable_lines = plugin_models.RevenueReceivableLine.objects.filter(contract_line__project=instance)
    return {
        'revenue_summary_cards': [
            {'label': '\u7d2f\u8ba1\u5e94\u6536', 'value': instance.accumulated_receivable},
            {'label': '\u7d2f\u8ba1\u5f00\u7968', 'value': instance.accumulated_invoice},
            {'label': '\u7d2f\u8ba1\u56de\u6b3e', 'value': instance.accumulated_receipt},
        ],
        'revenue_related_panels': [
            _make_revenue_panel(request, '\u5173\u8054\u5408\u540c', tables.RevenueContractProjectListTable, instance.project_contracts.all(), ('project',)),
            _make_revenue_panel(request, '\u5408\u540c\u9879', tables.RevenueContractLineListTable, instance.contract_lines.all(), ('project',)),
            _make_revenue_panel(request, '\u5e94\u6536\u8d26\u5355', tables.RevenueReceivableBillListTable, instance.receivable_bills.all(), ('project',)),
            _make_revenue_panel(request, '\u5e94\u6536\u660e\u7ec6', tables.RevenueReceivableLineListTable, receivable_lines, ()),
        ],
    }


def _revenue_order_context(request, instance):
    contract_lines = instance.contract_lines.all()
    receivable_plans = plugin_models.RevenueReceivablePlan.objects.filter(
        contract_line__revenue_order=instance
    )
    receivable_lines = plugin_models.RevenueReceivableLine.objects.filter(
        contract_line__revenue_order=instance
    )
    receipt_allocations = plugin_models.RevenueReceiptAllocation.objects.filter(
        receivable_line__contract_line__revenue_order=instance,
        status='active',
    )
    baseline_amount = sum(
        (line.unit_price * line.quantity for line in contract_lines),
        Decimal('0'),
    )
    return {
        'revenue_summary_cards': [
            {'label': '订单金额', 'value': instance.amount},
            {'label': '合同项基准金额', 'value': baseline_amount},
            {'label': '已形成应收', 'value': _sum_amount(receivable_lines, 'net_amount')},
            {'label': '已收款', 'value': _sum_amount(receipt_allocations, 'allocated_amount')},
        ],
        'revenue_related_panels': [
            _make_revenue_panel(request, '合同项', tables.RevenueContractLineListTable, contract_lines, ('revenue_order',)),
            _make_revenue_panel(request, '应收计划', tables.RevenueReceivablePlanListTable, receivable_plans, ()),
            _make_revenue_panel(request, '应收明细', tables.RevenueReceivableLineListTable, receivable_lines, ()),
        ],
    }

def _revenue_contract_version_context(request, instance):
    lines = instance.lines.all()
    rules = instance.billing_rules.all()
    segments = plugin_models.RevenueBillingSegment.objects.filter(billing_rule__contract_version=instance)
    return {
        'revenue_related_panels': [
            _make_revenue_panel(request, '\u5408\u540c\u9879', tables.RevenueContractLineListTable, lines, ('contract_version',)),
            _make_revenue_panel(request, '\u8ba1\u8d39\u89c4\u5219', tables.RevenueBillingRuleListTable, rules, ('contract_version',)),
            _make_revenue_panel(request, '\u8ba1\u8d39\u5206\u6bb5', tables.RevenueBillingSegmentListTable, segments, ()),
        ],
    }


def _revenue_contract_line_context(request, instance):
    receivable_lines = instance.receivable_lines.all()
    mappings = plugin_models.RevenueInvoiceMapping.objects.filter(receivable_line__contract_line=instance)
    return {
        'revenue_related_panels': [
            _make_revenue_panel(request, '\u8ba1\u8d39\u89c4\u5219', tables.RevenueBillingRuleListTable, instance.billing_rules.all(), ('contract_line',)),
            _make_revenue_panel(request, '\u8ba1\u8d39\u5206\u6bb5', tables.RevenueBillingSegmentListTable, instance.billing_segments.all(), ('contract_line',)),
            _make_revenue_panel(request, '\u5e94\u6536\u8ba1\u5212', tables.RevenueReceivablePlanListTable, instance.receivable_plans.all(), ('contract_line',)),
            _make_revenue_panel(request, '\u5e94\u6536\u660e\u7ec6', tables.RevenueReceivableLineListTable, receivable_lines, ('contract_line',)),
            _make_revenue_panel(request, '\u53d1\u7968\u6620\u5c04', tables.RevenueInvoiceMappingListTable, mappings, ()),
            _make_revenue_panel(request, '\u56de\u6b3e\u5206\u914d', tables.RevenueReceiptAllocationListTable, plugin_models.RevenueReceiptAllocation.objects.filter(receivable_line__contract_line=instance), ()),
        ],
    }


def _revenue_billing_rule_context(request, instance):
    return {
        'revenue_related_panels': [
            _make_revenue_panel(request, '\u8ba1\u8d39\u5206\u6bb5', tables.RevenueBillingSegmentListTable, instance.billing_segments.all(), ('billing_rule',)),
            _make_revenue_panel(request, '\u5e94\u6536\u8ba1\u5212', tables.RevenueReceivablePlanListTable, instance.receivable_plans.all(), ('billing_rule',)),
            _make_revenue_panel(request, '\u5e94\u6536\u660e\u7ec6', tables.RevenueReceivableLineListTable, instance.receivable_lines.all(), ('billing_rule',)),
        ],
    }


def _revenue_receivable_plan_context(request, instance):
    versions = instance.versions.all()
    triggers = instance.trigger_records.all()
    adjustments = instance.adjustments.all()
    if instance.billing_rule.receivable_plans.count() == 1:
        receivable_lines = instance.billing_rule.receivable_lines.filter(
            Q(receivable_plan=instance) | Q(receivable_plan__isnull=True)
        )
    else:
        receivable_lines = instance.receivable_lines.all()
    current_version = versions.filter(is_current=True).first()
    confirmed_adjustment_total = _sum_amount(adjustments.filter(status='confirmed'), 'amount')
    return {
        'revenue_summary_cards': [
            {'label': '\u5f53\u524d\u8ba1\u5212\u91d1\u989d', 'value': current_version.planned_amount if current_version else 0},
            {'label': '\u5b9e\u9645\u5e94\u6536\u91d1\u989d', 'value': _sum_amount(receivable_lines, 'net_amount')},
            {'label': '\u5df2\u786e\u8ba4\u8c03\u6574', 'value': confirmed_adjustment_total},
            {'label': '\u89e6\u53d1\u8bb0\u5f55', 'value': triggers.count()},
        ],
        'revenue_related_panels': [
            _make_revenue_panel(request, '\u8ba1\u5212\u7248\u672c', tables.RevenueReceivablePlanVersionListTable, versions, ('plan',)),
            _make_revenue_panel(request, '\u89e6\u53d1\u8bb0\u5f55', tables.RevenueTriggerRecordListTable, triggers, ('plan',)),
            _make_revenue_panel(request, '\u8c03\u6574\u8bb0\u5f55', tables.RevenueAdjustmentRecordListTable, adjustments, ('plan',)),
            _make_revenue_panel(request, '\u5173\u8054\u5e94\u6536\u660e\u7ec6', tables.RevenueReceivableLineListTable, receivable_lines, ('receivable_plan',)),
        ],
    }


def _revenue_receivable_plan_version_context(request, instance):
    return {
        'revenue_related_panels': [
            _make_revenue_panel(request, '\u89e6\u53d1\u8bb0\u5f55', tables.RevenueTriggerRecordListTable, instance.trigger_records.all(), ('plan_version',)),
        ],
    }

def _revenue_invoice_line_context(request, instance):
    mappings = instance.receivable_mappings.all()
    receivable_lines = plugin_models.RevenueReceivableLine.objects.filter(invoice_mappings__invoice_line=instance).distinct()
    bills = plugin_models.RevenueReceivableBill.objects.filter(lines__invoice_mappings__invoice_line=instance).distinct()
    contracts = plugin_models.RevenueContract.objects.filter(receivable_bills__lines__invoice_mappings__invoice_line=instance).distinct()
    return {
        'revenue_related_panels': [
            _make_revenue_panel(request, '\u53d1\u7968\u6620\u5c04', tables.RevenueInvoiceMappingListTable, mappings, ('invoice_line',)),
            _make_revenue_panel(request, '\u5bf9\u5e94\u5e94\u6536\u660e\u7ec6', tables.RevenueReceivableLineListTable, receivable_lines, ()),
            _make_revenue_panel(request, '\u5bf9\u5e94\u5e94\u6536\u8d26\u5355', tables.RevenueReceivableBillListTable, bills, ()),
            _make_revenue_panel(request, '\u5bf9\u5e94\u5408\u540c', tables.RevenueContractListTable, contracts, ()),
        ],
    }


def _revenue_invoice_mapping_context(request, instance):
    receipt_allocations = instance.receipt_allocations.all()
    receipt_total = _sum_amount(receipt_allocations.filter(status='active'), 'allocated_amount')
    return {
        'revenue_summary_cards': [
            {'label': '\u6620\u5c04\u91d1\u989d', 'value': instance.mapped_amount},
            {'label': '\u56de\u6b3e\u6838\u9500', 'value': receipt_total},
            {'label': '\u672a\u6838\u9500', 'value': instance.mapped_amount - receipt_total},
        ],
        'revenue_related_panels': [
            _make_revenue_panel(request, '\u56de\u6b3e\u5206\u914d', tables.RevenueReceiptAllocationListTable, receipt_allocations, ('invoice_mapping',)),
        ],
    }


def _revenue_receipt_allocation_context(request, instance):
    panels = []
    if instance.receivable_line_id:
        panels.append(_make_revenue_panel(request, '\u540c\u5e94\u6536\u660e\u7ec6\u7684\u56de\u6b3e\u5206\u914d', tables.RevenueReceiptAllocationListTable, plugin_models.RevenueReceiptAllocation.objects.filter(receivable_line=instance.receivable_line), ('receivable_line',)))
    return {'revenue_related_panels': panels}


_REVENUE_CONTEXT_BUILDERS = {
    'RevenueCustomer': _revenue_customer_context,
    'RevenueProject': _revenue_project_context,
    'RevenueContract': _revenue_contract_context,
    'RevenueOrder': _revenue_order_context,
    'RevenueContractVersion': _revenue_contract_version_context,
    'RevenueContractLine': _revenue_contract_line_context,
    'RevenueBillingRule': _revenue_billing_rule_context,
    'RevenueReceivablePlan': _revenue_receivable_plan_context,
    'RevenueReceivablePlanVersion': _revenue_receivable_plan_version_context,
    'RevenueReceivableBill': _revenue_receivable_bill_context,
    'RevenueReceivableLine': _revenue_receivable_line_context,
    'RevenueInvoice': _revenue_invoice_context,
    'RevenueInvoiceLine': _revenue_invoice_line_context,
    'RevenueInvoiceMapping': _revenue_invoice_mapping_context,
    'RevenueReceipt': _revenue_receipt_context,
    'RevenueReceiptAllocation': _revenue_receipt_allocation_context,
}


def _revenue_object_extra_context(self, request, instance):
    object_fields = []
    for field in instance._meta.fields:
        if field.name in ('id', 'custom_field_data'):
            continue
        raw_value = None
        value = None
        link = None
        try:
            raw_value = getattr(instance, field.name)
            display_method = getattr(instance, f'get_{field.name}_display', None)
            value = display_method() if callable(display_method) else _format_revenue_display_value(field.name, raw_value)
            if raw_value is not None and hasattr(raw_value, 'get_absolute_url'):
                link = raw_value.get_absolute_url()
        except Exception:
            value = None
        object_fields.append({
            'label': field.verbose_name,
            'value': value,
            'link': link,
        })
    context = {
        'revenue_object_fields': object_fields,
        'revenue_summary_cards': [],
        'revenue_related_panels': [],
    }
    builder = _REVENUE_CONTEXT_BUILDERS.get(instance.__class__.__name__)
    if builder:
        context.update(builder(request, instance))
    return context


def _build_revenue_portfolio_filter_context(contract_queryset, params):
    contract_type_choices = list(
        plugin_models.RevenueContract._meta.get_field('contract_type').flatchoices
    )
    status_choices = list(
        plugin_models.RevenueContract._meta.get_field('status').flatchoices
    )
    customer_value = params.get('customer', '').strip()
    project_value = params.get('project', '').strip()
    contract_type_value = params.get('contract_type', '').strip()
    status_value = params.get('status', '').strip()
    owner_value = params.get('business_owner', '').strip()

    customers = plugin_models.RevenueCustomer.objects.filter(
        revenue_contracts__in=contract_queryset
    ).distinct().order_by('name')
    projects = plugin_models.RevenueProject.objects.filter(
        revenue_contracts__in=contract_queryset
    ).distinct().order_by('name')
    owners = list(
        contract_queryset.exclude(business_owner='')
        .order_by('business_owner')
        .values_list('business_owner', flat=True)
        .distinct()
    )

    filtered_queryset = contract_queryset
    if customer_value.isdigit():
        filtered_queryset = filtered_queryset.filter(customer_id=int(customer_value))
    else:
        customer_value = ''
    if project_value.isdigit():
        filtered_queryset = filtered_queryset.filter(projects__id=int(project_value))
    else:
        project_value = ''
    if contract_type_value in {value for value, _label in contract_type_choices}:
        filtered_queryset = filtered_queryset.filter(contract_type=contract_type_value)
    else:
        contract_type_value = ''
    if status_value in {value for value, _label in status_choices}:
        filtered_queryset = filtered_queryset.filter(status=status_value)
    else:
        status_value = ''
    if owner_value in owners:
        filtered_queryset = filtered_queryset.filter(business_owner=owner_value)
    else:
        owner_value = ''

    filtered_queryset = filtered_queryset.distinct()
    values = {
        'customer': customer_value,
        'project': project_value,
        'contract_type': contract_type_value,
        'status': status_value,
        'business_owner': owner_value,
    }
    return filtered_queryset, {
        'values': values,
        'customers': customers,
        'projects': projects,
        'contract_types': contract_type_choices,
        'statuses': status_choices,
        'owners': owners,
        'active_count': sum(bool(value) for value in values.values()),
        'contract_count': filtered_queryset.count(),
    }

def _build_revenue_portfolio_context(contract_queryset):
    receivable_lines = list(
        plugin_models.RevenueReceivableLine.objects.filter(
            bill__contract__in=contract_queryset,
            bill__confirm_status='confirmed',
        ).select_related(
            'bill',
            'bill__contract',
            'contract_line',
            'billing_rule',
            'receivable_plan',
        )
    )
    invoice_mappings = list(
        plugin_models.RevenueInvoiceMapping.objects.filter(
            receivable_line__bill__contract__in=contract_queryset,
            receivable_line__bill__confirm_status='confirmed',
            status='active',
        ).select_related(
            'receivable_line',
            'invoice_line',
            'invoice_line__invoice',
        )
    )
    receipt_allocations = list(
        plugin_models.RevenueReceiptAllocation.objects.filter(
            receivable_line__bill__contract__in=contract_queryset,
            receivable_line__bill__confirm_status='confirmed',
            status='active',
        ).select_related(
            'receipt',
            'receivable_line',
            'invoice_mapping',
        )
    )
    event_rows = build_revenue_event_rows(
        receivable_lines,
        invoice_mappings,
        receipt_allocations,
        url_for=_url_for,
    )

    receivable_plans = list(
        plugin_models.RevenueReceivablePlan.objects.filter(
            contract__in=contract_queryset,
            status__in=('draft', 'effective'),
        ).select_related(
            'contract',
            'contract_line',
            'billing_rule',
        )
    )
    plan_versions = list(
        plugin_models.RevenueReceivablePlanVersion.objects.filter(
            plan__contract__in=contract_queryset,
            plan__status__in=('draft', 'effective'),
        ).select_related('plan').order_by('plan', 'version_no')
    )
    trigger_records = list(
        plugin_models.RevenueTriggerRecord.objects.filter(
            plan__contract__in=contract_queryset,
            plan__status__in=('draft', 'effective'),
            status='confirmed',
        ).select_related('plan', 'plan_version')
    )
    plan_tracks = build_receivable_plan_tracks(
        receivable_plans,
        plan_versions,
        trigger_records,
        [],
        event_rows,
        url_for=_url_for,
    )
    return {
        'revenue_portfolio': build_revenue_portfolio(
            event_rows,
            plan_tracks,
        ),
    }


def _select_revenue_portfolio_band(portfolio, requested_key, query_params=None):
    bands_by_key = {band['key']: band for band in portfolio['bands']}
    selected_key = requested_key if requested_key in bands_by_key else 'overdue'
    selected_band = bands_by_key[selected_key]
    for band in portfolio['bands']:
        band['is_active'] = band['key'] == selected_key
        if query_params is not None:
            query = query_params.copy()
            query.pop('export', None)
            query['window'] = band['key']
            band['query_string'] = query.urlencode()
            export_query = query.copy()
            export_query['export'] = 'band'
            band['export_query_string'] = export_query.urlencode()
    portfolio['selected_band'] = selected_band
    return portfolio


def _select_revenue_portfolio_month(portfolio, requested_key, query_params=None):
    months_by_key = {month['key']: month for month in portfolio['months']}
    selected_month = months_by_key.get(requested_key)
    for month in portfolio['months']:
        month['is_active'] = month is selected_month
        if query_params is not None:
            query = query_params.copy()
            query.pop('export', None)
            query['month'] = month['key']
            month['query_string'] = query.urlencode()
            export_query = query.copy()
            export_query['export'] = 'month'
            month['export_query_string'] = export_query.urlencode()
    portfolio['selected_month'] = selected_month
    return portfolio


def _revenue_csv_value(value):
    if value is None:
        return ''
    text = str(value)
    if text.startswith(('=', '+', '-', '@')):
        return "'" + text
    return text


def _export_revenue_portfolio_csv(portfolio, scope):
    target = portfolio.get('selected_month') if scope == 'month' else portfolio.get('selected_band')
    if not target:
        return None

    key = target['key']
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="receivables-{scope}-{key}-{date.today():%Y%m%d}.csv"'
    )
    response.write('﻿')
    writer = csv.writer(response)
    if scope == 'month':
        writer.writerow([
            '合同', '应收来源', '类型', '到期时间', '计划状态', '业务状态',
            '应收/计划金额', '已收金额', '未收金额',
        ])
    else:
        writer.writerow([
            '合同', '应收来源', '类型', '到期时间', '计划状态', '业务状态',
            '未收/计划金额',
        ])

    for detail in target.get('export_details', target.get('details', ())):
        common = [
            _revenue_csv_value(detail.get('contract')),
            _revenue_csv_value(detail.get('source')),
            detail.get('kind_label', ''),
            detail['due_date'].isoformat() if detail.get('due_date') else '待触发',
            detail.get('schedule_status', ''),
            detail.get('status_label', ''),
        ]
        if scope == 'month':
            writer.writerow(common + [
                detail.get('amount', Decimal('0')),
                detail.get('received_amount', Decimal('0')),
                detail.get('outstanding_amount', Decimal('0')),
            ])
        else:
            writer.writerow(common + [detail.get('amount', Decimal('0'))])
    return response


class RevenueReceivableOverviewView(ObjectPermissionRequiredMixin, View):
    queryset = plugin_models.RevenueContract.objects.all()
    template_name = 'netbox_contract/revenue_receivable_overview.html'

    def get_required_permission(self):
        return 'netbox_contract.view_revenuecontract'

    def get(self, request):
        filtered_queryset, filter_context = _build_revenue_portfolio_filter_context(
            self.queryset,
            request.GET,
        )
        context = _build_revenue_portfolio_context(filtered_queryset)
        context['portfolio_filters'] = filter_context
        _select_revenue_portfolio_band(
            context['revenue_portfolio'],
            request.GET.get('window'),
            request.GET,
        )
        _select_revenue_portfolio_month(
            context['revenue_portfolio'],
            request.GET.get('month'),
            request.GET,
        )
        export_scope = request.GET.get('export')
        if export_scope in {'band', 'month'}:
            response = _export_revenue_portfolio_csv(
                context['revenue_portfolio'],
                export_scope,
            )
            if response is not None:
                return response
        return render(request, self.template_name, context)


class RevenueContractVisualView(generic.ObjectView):
    queryset = plugin_models.RevenueContract.objects.all()
    template_name = 'netbox_contract/revenue_contract.html'
    get_extra_context = _revenue_object_extra_context


class RevenueContractExecutiveView(generic.ObjectView):
    queryset = plugin_models.RevenueContract.objects.all()
    template_name = 'netbox_contract/revenue_contract.html'
    get_extra_context = _revenue_object_extra_context


_REVENUE_VIEW_SPECS = [
    ('RevenueCustomer', 'RevenueCustomerListTable', 'RevenueCustomerFilterSet', 'RevenueCustomerForm'),
    ('RevenueProject', 'RevenueProjectListTable', 'RevenueProjectFilterSet', 'RevenueProjectForm'),
    ('RevenueContract', 'RevenueContractListTable', 'RevenueContractFilterSet', 'RevenueContractForm'),
    ('RevenueContractProject', 'RevenueContractProjectListTable', 'RevenueContractProjectFilterSet', 'RevenueContractProjectForm'),
    ('RevenueOrder', 'RevenueOrderListTable', 'RevenueOrderFilterSet', 'RevenueOrderForm'),
    ('RevenueContractVersion', 'RevenueContractVersionListTable', 'RevenueContractVersionFilterSet', 'RevenueContractVersionForm'),
    ('RevenueContractLine', 'RevenueContractLineListTable', 'RevenueContractLineFilterSet', 'RevenueContractLineForm'),
    ('RevenueBillingRule', 'RevenueBillingRuleListTable', 'RevenueBillingRuleFilterSet', 'RevenueBillingRuleForm'),
    ('RevenueBillingSegment', 'RevenueBillingSegmentListTable', 'RevenueBillingSegmentFilterSet', 'RevenueBillingSegmentForm'),
    ('RevenueReceivablePlan', 'RevenueReceivablePlanListTable', 'RevenueReceivablePlanFilterSet', 'RevenueReceivablePlanForm'),
    ('RevenueReceivablePlanVersion', 'RevenueReceivablePlanVersionListTable', 'RevenueReceivablePlanVersionFilterSet', 'RevenueReceivablePlanVersionForm'),
    ('RevenueTriggerRecord', 'RevenueTriggerRecordListTable', 'RevenueTriggerRecordFilterSet', 'RevenueTriggerRecordForm'),
    ('RevenueAdjustmentRecord', 'RevenueAdjustmentRecordListTable', 'RevenueAdjustmentRecordFilterSet', 'RevenueAdjustmentRecordForm'),
    ('RevenueReceivableBill', 'RevenueReceivableBillListTable', 'RevenueReceivableBillFilterSet', 'RevenueReceivableBillForm'),
    ('RevenueReceivableLine', 'RevenueReceivableLineListTable', 'RevenueReceivableLineFilterSet', 'RevenueReceivableLineForm'),
    ('RevenueInvoice', 'RevenueInvoiceListTable', 'RevenueInvoiceFilterSet', 'RevenueInvoiceForm'),
    ('RevenueInvoiceLine', 'RevenueInvoiceLineListTable', 'RevenueInvoiceLineFilterSet', 'RevenueInvoiceLineForm'),
    ('RevenueInvoiceMapping', 'RevenueInvoiceMappingListTable', 'RevenueInvoiceMappingFilterSet', 'RevenueInvoiceMappingForm'),
    ('RevenueReceipt', 'RevenueReceiptListTable', 'RevenueReceiptFilterSet', 'RevenueReceiptForm'),
    ('RevenueReceiptAllocation', 'RevenueReceiptAllocationListTable', 'RevenueReceiptAllocationFilterSet', 'RevenueReceiptAllocationForm'),
    ('RevenueSyncLog', 'RevenueSyncLogListTable', 'RevenueSyncLogFilterSet', 'RevenueSyncLogForm'),
]

for _model_name, _table_name, _filterset_name, _form_name in _REVENUE_VIEW_SPECS:
    _model = getattr(__import__('netbox_contract.models', fromlist=[_model_name]), _model_name)
    globals()[f'{_model_name}View'] = type(
        f'{_model_name}View',
        (generic.ObjectView,),
        {
            'queryset': _model.objects.all(),
            'template_name': 'netbox_contract/revenue_contract.html' if _model_name == 'RevenueContract' else 'netbox_contract/revenue_object.html',
            'get_extra_context': _revenue_object_extra_context,
        },
    )
    globals()[f'{_model_name}ListView'] = type(
        f'{_model_name}ListView',
        (generic.ObjectListView,),
        {
            'queryset': _model.objects.all(),
            'table': getattr(tables, _table_name),
            'filterset': getattr(filtersets, _filterset_name),
            'filterset_form': getattr(forms, f'{_model_name}FilterForm'),
        },
    )
    globals()[f'{_model_name}EditView'] = type(
        f'{_model_name}EditView',
        (generic.ObjectEditView,),
        {'queryset': _model.objects.all(), 'form': getattr(forms, _form_name)},
    )
    globals()[f'{_model_name}DeleteView'] = type(
        f'{_model_name}DeleteView',
        (generic.ObjectDeleteView,),
        {'queryset': _model.objects.all()},
    )
