from django.contrib.auth import get_user_model
from django.contrib.auth.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from drf_yasg.utils import swagger_serializer_method
from netbox.api.fields import ContentTypeField, SerializedPKRelatedField
from netbox.api.serializers import NetBoxModelSerializer, WritableNestedSerializer
from rest_framework import serializers
from tenancy.api.serializers_.tenants import TenantSerializer
from utilities.api import get_serializer_for_model

from ..models import (
    AccountingDimension,
    Contract,
    ContractAssignment,
    ContractType,
    Invoice,
    InvoiceLine,
    ServiceProvider,
)

User = get_user_model()


class NestedContractSerializer(WritableNestedSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_contract-api:contract-detail'
    )
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)
    external_party_object_type = ContentTypeField(queryset=ContentType.objects.all(), required=False, allow_null=True)
    external_party_object = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Contract
        fields = fields = (
            'id',
            'url',
            'display',
            'name',
            'number',
            'contract_type',
            'external_party_object_type',
            'external_party_object_id',
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
            'comments',
        )

    @swagger_serializer_method(serializer_or_field=serializers.JSONField)
    def get_external_party_object(self, instance):
        serializer = get_serializer_for_model(
            instance.external_party_object_type.model_class()
        )
        context = {'request': self.context['request']}
        return serializer(
            instance.external_party_object, nested=True, context=context
        ).data


class NestedInvoiceSerializer(WritableNestedSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_contract-api:invoice-detail'
    )

    class Meta:
        model = Invoice
        fields = ('id', 'url', 'display', 'number')
        brief_fields = ('id', 'url', 'display', 'number')


class NestedAccountingDimensionSerializer(WritableNestedSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_contract-api:accountingdimension-detail'
    )

    class Meta:
        model = AccountingDimension
        fields = ('id', 'url', 'display', 'name', 'value')
        brief_fields = ('id', 'url', 'display', 'name', 'value')


class ContractTypeSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='plugins-api:netbox_contract-api:contracttype-detail')

    class Meta:
        model = ContractType
        fields = (
            'id',
            'url',
            'display',
            'name',
            'description',
            'tags',
            'custom_fields',
            'created',
            'last_updated',
        )
        brief_fields = ('id', 'name', 'description', 'url', 'display')


class ContractSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_contract-api:contract-detail'
    )
    contract_type = ContractTypeSerializer(nested=True, required=False, allow_null=True)
    parent = NestedContractSerializer(many=False, required=False)
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)
    external_party_object_type = ContentTypeField(queryset=ContentType.objects.all(), required=False, allow_null=True)
    external_party_object = serializers.SerializerMethodField(read_only=True)
    compliance_manager = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )
    current_pay_until = serializers.DateField(read_only=True)

    class Meta:
        model = Contract
        fields = (
            'id',
            'url',
            'display',
            'name',
            'number',
            'contract_type',
            'external_party_object_type',
            'external_party_object_id',
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
            'comments',
            'compliance_manager',
            'parent',
            'current_pay_until',
            'tags',
            'custom_fields',
            'created',
            'last_updated',
        )
        brief_fields = (
            'id',
            'url',
            'display',
            'name',
            'number',
            'contract_type',
            'external_party_object_type',
            'external_party_object_id',
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
            'comments',
            'compliance_manager',
            'parent',
            'current_pay_until',
        )

    @swagger_serializer_method(serializer_or_field=serializers.JSONField)
    def get_external_party_object(self, instance):
        serializer = get_serializer_for_model(
            instance.external_party_object_type.model_class()
        )
        context = {'request': self.context['request']}
        return serializer(
            instance.external_party_object, nested=True, context=context
        ).data


class InvoiceSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_contract-api:invoice-detail'
    )
    contracts = SerializedPKRelatedField(
        queryset=Contract.objects.all(),
        serializer=ContractSerializer,
        required=False,
        many=True,
    )

    class Meta:
        model = Invoice
        fields = (
            'id',
            'url',
            'display',
            'number',
            'date',
            'template',
            'contracts',
            'period_start',
            'period_end',
            'amount',
            'comments',
            'tags',
            'custom_fields',
            'created',
            'last_updated',
        )
        brief_fields = (
            'id',
            'url',
            'display',
            'number',
            'date',
            'template',
            'contracts',
            'period_start',
            'period_end',
            'amount',
            'comments',
        )

    def validate(self, data):
        data = super().validate(data)

        # template checks
        if data['template']:
            # Check that there is only one invoice template per contract
            contracts = data['contracts']
            for contract in contracts:
                for invoice in contract.invoices.all():
                    if invoice.template and invoice != self.instance:
                        raise serializers.ValidationError(
                            'Only one invoice template allowed per contract'
                        )

            # Prefix the invoice name with _template
            data['number'] = '_invoice_template_' + contract.name

            # set the periode start and end date to null
            data['period_start'] = None
            data['period_end'] = None
        return data

    def create(self, validated_data):
        instance = super().create(validated_data)

        if not instance.template:
            contracts = instance.contracts.all()

            for contract in contracts:
                try:
                    template_exists = True
                    invoice_template = Invoice.objects.get(
                        template=True, contracts=contract
                    )
                except ObjectDoesNotExist:
                    template_exists = False

                if template_exists:
                    first = True
                    for line in invoice_template.invoicelines.all():
                        dimensions = line.accounting_dimensions.all()
                        line.pk = None
                        line.id = None
                        line._state.adding = True
                        line.invoice = instance

                        # adjust the first invoice line amount
                        amount = validated_data['amount']
                        if (
                            first
                            and amount != invoice_template.total_invoicelines_amount
                        ):
                            line.amount = (
                                line.amount
                                + amount
                                - invoice_template.total_invoicelines_amount
                            )

                        line.save()

                        for dimension in dimensions:
                            line.accounting_dimensions.add(dimension)
                        first = False

        return instance


class ServiceProviderSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_contract-api:serviceprovider-detail'
    )

    class Meta:
        model = ServiceProvider
        fields = (
            'id',
            'url',
            'display',
            'name',
            'portal_url',
            'tags',
            'custom_fields',
            'created',
            'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'name')


class ContractAssignmentSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_contract-api:contractassignment-detail'
    )
    content_type = ContentTypeField(queryset=ContentType.objects.all())
    content_object = serializers.SerializerMethodField(read_only=True)
    contract = NestedContractSerializer()

    class Meta:
        model = ContractAssignment
        fields = (
            'id',
            'url',
            'display',
            'content_type',
            'object_id',
            'content_object',
            'contract',
            'created',
            'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'content_object', 'contract')

    @swagger_serializer_method(serializer_or_field=serializers.JSONField)
    def get_content_object(self, instance):
        serializer = get_serializer_for_model(instance.content_type.model_class())
        context = {'request': self.context['request']}
        return serializer(instance.content_object, nested=True, context=context).data


class InvoiceLineSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_contract-api:invoiceline-detail'
    )
    invoice = NestedInvoiceSerializer(many=False, required=False)
    accounting_dimensions = SerializedPKRelatedField(
        queryset=AccountingDimension.objects.all(),
        serializer=NestedAccountingDimensionSerializer,
        required=False,
        many=True,
    )

    class Meta:
        model = InvoiceLine
        fields = (
            'id',
            'url',
            'display',
            'invoice',
            'amount',
            'accounting_dimensions',
            'comments',
            'tags',
            'custom_fields',
            'created',
            'last_updated',
        )
        brief_fields = (
            'invoice',
            'accounting_dimensions',
            'amount',
            'url',
            'display',
            'name',
        )

    def validate(self, data):
        super().validate(data)
        # check for duplicate dimensions
        accounting_dimensions = data['accounting_dimensions']
        dimensions_names = []
        for dimension in accounting_dimensions:
            if dimension.name in dimensions_names:
                raise serializers.ValidationError('duplicate accounting dimension')
            else:
                dimensions_names.append(dimension.name)
        return data


class AccountingDimensionSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_contract-api:accountingdimension-detail'
    )

    class Meta:
        model = AccountingDimension
        fields = (
            'id',
            'url',
            'display',
            'name',
            'value',
            'comments',
            'tags',
            'custom_fields',
            'created',
            'last_updated',
        )
        brief_fields = ('id', 'name', 'value', 'url', 'display')


from ..models import (
    RevenueCustomer, RevenueProject, RevenueContract, RevenueContractProject, RevenueOrder, RevenueContractVersion,
    RevenueContractLine, RevenueBillingRule, RevenueBillingSegment, RevenueReceivablePlan,
    RevenueReceivablePlanVersion, RevenueTriggerRecord, RevenueAdjustmentRecord,
    RevenueReceivableBill, RevenueReceivableLine, RevenueInvoice,
    RevenueInvoiceLine, RevenueInvoiceMapping, RevenueReceipt, RevenueReceiptAllocation,
    RevenueSyncLog,
)


_REVENUE_SERIALIZER_MODELS = [
    RevenueCustomer, RevenueProject, RevenueContract, RevenueContractProject, RevenueOrder, RevenueContractVersion,
    RevenueContractLine, RevenueBillingRule, RevenueBillingSegment, RevenueReceivablePlan,
    RevenueReceivablePlanVersion, RevenueTriggerRecord, RevenueAdjustmentRecord,
    RevenueReceivableBill, RevenueReceivableLine, RevenueInvoice,
    RevenueInvoiceLine, RevenueInvoiceMapping, RevenueReceipt, RevenueReceiptAllocation,
    RevenueSyncLog,
]

for _revenue_model in _REVENUE_SERIALIZER_MODELS:
    _meta = type('Meta', (), {
        'model': _revenue_model,
        'fields': '__all__',
        'brief_fields': ('id', 'display'),
    })
    globals()[f'{_revenue_model.__name__}Serializer'] = type(
        f'{_revenue_model.__name__}Serializer',
        (NetBoxModelSerializer,),
        {'Meta': _meta},
    )
_RevenueOrderSerializerBase = globals()['RevenueOrderSerializer']


class RevenueOrderSerializer(_RevenueOrderSerializerBase):
    def validate(self, data):
        contract = data.get('contract', getattr(self.instance, 'contract', None))
        project = data.get('project', getattr(self.instance, 'project', None))
        amount = data.get('amount', getattr(self.instance, 'amount', None))
        start_date = data.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = data.get('end_date', getattr(self.instance, 'end_date', None))
        errors = {}
        if contract and project and project.customer_id != contract.customer_id:
            errors['project'] = '订单项目与合同必须属于同一客户。'
        if amount is not None and amount < 0:
            errors['amount'] = '订单金额不能为负数。'
        if start_date and end_date and end_date < start_date:
            errors['end_date'] = '订单结束日期不能早于开始日期。'
        if errors:
            raise serializers.ValidationError(errors)
        return super().validate(data)


_RevenueContractLineSerializerBase = globals()['RevenueContractLineSerializer']


class RevenueContractLineSerializer(_RevenueContractLineSerializerBase):
    def validate(self, data):
        contract = data.get('contract', getattr(self.instance, 'contract', None))
        project = data.get('project', getattr(self.instance, 'project', None))
        contract_version = data.get(
            'contract_version', getattr(self.instance, 'contract_version', None)
        )
        revenue_order = data.get(
            'revenue_order', getattr(self.instance, 'revenue_order', None)
        )
        errors = {}
        if contract and contract_version and contract_version.contract_id != contract.pk:
            errors['contract_version'] = '合同版本必须属于所选合同。'
        if contract and project and project.customer_id != contract.customer_id:
            errors['project'] = '合同项项目与合同必须属于同一客户。'
        if contract and revenue_order and revenue_order.contract_id != contract.pk:
            errors['revenue_order'] = '订单必须属于所选合同。'
        elif project and revenue_order and revenue_order.project_id != project.pk:
            errors['revenue_order'] = '订单必须属于所选项目。'
        if errors:
            raise serializers.ValidationError(errors)
        return super().validate(data)
