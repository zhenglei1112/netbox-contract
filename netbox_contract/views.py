from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Case, F, When
from django.db.models.functions import Round
from django.shortcuts import get_object_or_404, render
from netbox.views import generic
from netbox.views.generic.utils import get_prerequisite_model
from utilities.forms import restrict_form_fields
from utilities.querydict import normalize_querydict
from utilities.views import register_model_view

from . import filtersets, forms, tables
from .models import (
    AccountingDimension,
    Contract,
    ContractAssignment,
    ContractType,
    Invoice,
    InvoiceLine,
    ServiceProvider,
)

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
        invoices_table = tables.InvoiceListTable(
            instance.invoices.exclude(template=True)
        )
        invoices_table.columns.hide('contracts')
        invoices_table.configure(request)
        assignments_table = tables.ContractAssignmentContractTable(
            instance.assignments.all()
        )
        invoice_template = instance.invoices.filter(template=True).first()
        if invoice_template:
            invoicelines_table = tables.InvoiceLineListTable(
                invoice_template.invoicelines.all()
            )
            invoicelines_table.columns.hide('invoice')
            invoicelines_table.columns.hide('currency')
            invoicelines_table.configure(request)
        else:
            invoicelines_table = None
        assignments_table.configure(request)
        if instance.childs.all():
            childs_table = tables.ContractListBottomTable(instance.childs.all())
            childs_table.configure(request)
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
            obj.external_party_object_id = data['external_party_object']
            external_party_object_type_id = data['external_party_object_type']
            obj.external_party_object_type = ContentType.objects.get(
                id=external_party_object_type_id
            )
            external_party_object_type = obj.external_party_object_type
            obj.external_party_object = (
                external_party_object_type.get_object_for_this_type(
                    id=obj.external_party_object_id
                )
            )

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
        contracts_table = tables.ContractListTable(instance.contracts.all())
        contracts_table.configure(request)
        invoicelines_table = tables.InvoiceLineListTable(instance.invoicelines.all())
        invoicelines_table.columns.hide('invoice')
        invoicelines_table.configure(request)
        hidden_fields = plugin_settings.get('hidden_invoice_fields')

        return {
            'hidden_fields': hidden_fields,
            'contracts_table': contracts_table,
            'invoicelines_table': invoicelines_table,
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
