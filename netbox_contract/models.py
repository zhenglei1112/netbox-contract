import datetime
from datetime import timedelta
from decimal import Decimal

from dcim.choices import DeviceStatusChoices, SiteStatusChoices
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from netbox.choices import ColorChoices
from netbox.models import NetBoxModel
from netbox.models.features import ContactsMixin
from utilities.choices import ChoiceSet
from utilities.fields import ColorField
from virtualization.choices import VirtualMachineStatusChoices

User = get_user_model()


class StatusChoices(ChoiceSet):
    key = 'Contract.status'

    STATUS_ACTIVE = 'active'
    STATUS_CANCELED = 'canceled'

    CHOICES = [
        (STATUS_ACTIVE, 'Active', 'green'),
        (STATUS_CANCELED, 'Canceled', 'red'),
    ]


class AccountingDimensionStatusChoices(ChoiceSet):
    key = 'AccountingDimension.status'

    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'

    CHOICES = [
        (STATUS_ACTIVE, _('Active1'), 'green'),
        (STATUS_INACTIVE, _('Inactive1'), 'red'),
    ]


class InternalEntityChoices(ChoiceSet):
    key = 'Contract.internal_party'

    ENTITY = 'Default entity'
    GENERAL_AFFAIRS = 'general-affairs'

    CHOICES = [
        (ENTITY, 'Default entity', 'green'),
        (GENERAL_AFFAIRS, '综合部', 'blue'),
    ]


class CurrencyChoices(ChoiceSet):
    key = 'Contract.currency'
    CURRENCY_USD = 'usd'

    CHOICES = [
        (CURRENCY_USD, 'USD'),
        ('eur', 'EUR'),
        ('chf', 'CHF'),
    ]


class InvoiceStatusChoices(ChoiceSet):
    key = 'Invoice.status'

    STATUS_DRAFT = 'draft'
    STATUS_POSTED = 'posted'
    STATUS_CANCELED = 'canceled'

    CHOICES = [
        (STATUS_DRAFT, 'Draft', 'yellow'),
        (STATUS_POSTED, 'Posted', 'green'),
        (STATUS_CANCELED, 'Canceled', 'red'),
    ]


CURRENCY_DEFAULT = CurrencyChoices.CHOICES[0][0]


class ContractBaseModel(NetBoxModel):
    """Normalize aware datetime fields before NetBox captures audit snapshots."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        for field in self._meta.fields:
            if isinstance(field, models.DateTimeField):
                value = getattr(self, field.name)
                if isinstance(value, datetime.datetime) and timezone.is_aware(value):
                    setattr(self, field.name, value.astimezone(datetime.timezone.utc))
        super().save(*args, **kwargs)


class ContractType(ContractBaseModel):
    name = models.CharField(max_length=100, unique=True, verbose_name=_('name'))
    description = models.TextField(blank=True, verbose_name=_('description'))
    color = ColorField(default=ColorChoices.COLOR_GREY, verbose_name=_('color'))

    class Meta:
        ordering = ('name',)
        verbose_name = _('contract type')
        verbose_name_plural = _('contract types')

    def __str__(self):
        return self.name

    def get_color(self):
        return self.color

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:contracttype', args=[self.pk])


class AccountingDimension(ContractBaseModel):
    name = models.CharField(
        max_length=20,
        verbose_name=_('dimension name'),
        help_text=_('Accounting dimension name. Ex: Department, Location, etc.'),
    )
    value = models.CharField(max_length=20, verbose_name=_('value'))
    status = models.CharField(
        max_length=50,
        choices=AccountingDimensionStatusChoices,
        default=StatusChoices.STATUS_ACTIVE,
        verbose_name=_('status'),
    )
    comments = models.TextField(blank=True, verbose_name=_('comments'))

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:accountingdimension', args=[self.pk])

    @property
    def dimension(self):
        return ''.join([self.name, ':', self.value])

    def __str__(self):
        return self.dimension

    def get_status_color(self):
        return AccountingDimensionStatusChoices.colors.get(self.status)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['name', 'value'], name='unique_accounting_dimension')]
        ordering = ('name', 'value')
        verbose_name = _('accounting dimension')
        verbose_name_plural = _('accounting dimensions')


class ServiceProvider(ContactsMixin, ContractBaseModel):
    name = models.CharField(max_length=100, verbose_name=_('name'))
    slug = models.SlugField(max_length=100, unique=True, verbose_name=_('slug'))
    portal_url = models.URLField(blank=True, verbose_name=_('portal URL'))
    comments = models.TextField(blank=True, verbose_name=_('comments'))

    class Meta:
        ordering = ('name',)
        verbose_name = _('service provider')
        verbose_name_plural = _('service providers')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:serviceprovider', args=[self.pk])


class ContractAssignment(ContractBaseModel):
    content_type = models.ForeignKey(to=ContentType, on_delete=models.CASCADE, verbose_name=_('content type'))
    object_id = models.PositiveBigIntegerField(verbose_name=_('object ID'))
    content_object = GenericForeignKey(ct_field='content_type', fk_field='object_id')
    contract = models.ForeignKey(
        to='Contract',
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name=_('contract'),
    )
    clone_fields = ('content_type', 'object_id', 'contract')

    class Meta:
        ordering = ('contract',)
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]
        verbose_name = _('contract assignment')
        verbose_name_plural = _('contract assignments')

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:contractassignment', args=[self.pk])

    def get_contract__status_color(self):
        return StatusChoices.colors.get(self.contract.status)

    def get_content_object__status_color(self):
        STATUS_MAPPING = {
            'virtualmachine': VirtualMachineStatusChoices.colors,
            'device': DeviceStatusChoices.colors,
            'site': SiteStatusChoices.colors,
        }
        status_colors = STATUS_MAPPING.get(self.content_type.model, StatusChoices.colors)
        return status_colors.get(self.content_object.status)


def get_default_external_party_type():
    try:
        from django.contrib.contenttypes.models import ContentType
        return ContentType.objects.get_for_model(ServiceProvider).pk
    except Exception:
        return None


class Contract(ContactsMixin, ContractBaseModel):
    name = models.CharField(max_length=100, verbose_name=_('name'))
    number = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('number'))
    contract_type = models.ForeignKey(
        to='netbox_contract.ContractType',
        on_delete=models.PROTECT,
        related_name='contracts',
        blank=True,
        null=True,
        verbose_name=_('contract type'),
    )
    external_party_object_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        default=get_default_external_party_type,
        verbose_name=_('external party object type'),
    )
    external_party_object_id = models.PositiveBigIntegerField(
        blank=True, null=True, verbose_name=_('external party object ID')
    )
    external_party_object = GenericForeignKey(
        ct_field='external_party_object_type', fk_field='external_party_object_id'
    )
    external_party_object.editable = True
    external_reference = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('external reference'))
    internal_party = models.CharField(max_length=50, choices=InternalEntityChoices, verbose_name=_('internal party'))
    tenant = models.ForeignKey(
        to='tenancy.Tenant',
        on_delete=models.PROTECT,
        related_name='contracts',
        blank=True,
        null=True,
        verbose_name=_('tenant'),
    )
    status = models.CharField(
        max_length=50,
        choices=StatusChoices,
        default=StatusChoices.STATUS_ACTIVE,
        verbose_name=_('status'),
    )
    start_date = models.DateField(blank=True, null=True, verbose_name=_('start date'))
    end_date = models.DateField(blank=True, null=True, verbose_name=_('end date'))
    initial_term = models.IntegerField(
        help_text=_('In month'),
        default=12,
        blank=True,
        null=True,
        verbose_name=_('initial term'),
    )
    renewal_term = models.IntegerField(
        help_text=_('In month'),
        default=12,
        blank=True,
        null=True,
        verbose_name=_('renewal term'),
    )
    notice_period = models.IntegerField(
        help_text=_('Contract notice period. Default to 90 days'),
        default=90,
        verbose_name=_('notice period'),
    )
    currency = models.CharField(
        max_length=3,
        choices=CurrencyChoices,
        default=CURRENCY_DEFAULT,
        verbose_name=_('currency'),
    )
    yrc = models.DecimalField(
        verbose_name=_('yearly recuring cost'),
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_('Use either this field of the monthly recuring cost field'),
    )
    mrc = models.DecimalField(
        verbose_name=_('monthly recuring cost'),
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    nrc = models.DecimalField(verbose_name=_('none recuring cost'), default=0, max_digits=10, decimal_places=2)
    invoice_frequency = models.IntegerField(
        help_text=_('The frequency of invoices in month'),
        default=1,
        verbose_name=_('invoice frequency'),
    )
    documents = models.URLField(
        blank=True,
        verbose_name=_('documents'),
        help_text=_('URL to the contract documents'),
    )
    comments = models.TextField(blank=True, verbose_name=_('comments'))
    compliance_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='compliance_managed_contracts',
        null=True,
        blank=True,
        verbose_name=_('Compliance Manager'),
        help_text=_('compliance manager'),
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='childs',
        null=True,
        blank=True,
        verbose_name=_('parent'),
    )

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:contract', args=[self.pk])

    def get_status_color(self):
        return StatusChoices.colors.get(self.status)

    class Meta:
        ordering = ('-created',)
        indexes = [
            models.Index(fields=['external_party_object_type', 'external_party_object_id']),
        ]
        verbose_name = _('contract')
        verbose_name_plural = _('contracts')

    @property
    def notice_date(self):
        if self.end_date:
            return self.end_date - timedelta(days=self.notice_period)
        return None

    @property
    def current_pay_until(self):
        latest_invoice = self.invoices.filter(period_end__isnull=False).order_by('-period_end').first()
        if latest_invoice:
            return latest_invoice.period_end
        return None

    def __str__(self):
        if self.number:
            return f"{self.name}-{self.number}"
        return self.name


class Invoice(ContractBaseModel):
    number = models.CharField(max_length=100, verbose_name=_('number'))
    template = models.BooleanField(
        blank=True,
        null=True,
        default=False,
        verbose_name=_('template'),
        help_text=_('Wether this invoice is a template or not'),
    )
    status = models.CharField(
        max_length=50,
        choices=InvoiceStatusChoices,
        default=InvoiceStatusChoices.STATUS_POSTED,
        verbose_name=_('status'),
    )
    date = models.DateField(blank=True, null=True, verbose_name=_('date'))
    contracts = models.ManyToManyField(Contract, related_name='invoices', blank=True, verbose_name=_('contracts'))
    period_start = models.DateField(blank=True, null=True, verbose_name=_('period start'))
    period_end = models.DateField(blank=True, null=True, verbose_name=_('period end'))
    currency = models.CharField(
        max_length=3,
        choices=CurrencyChoices,
        default=CURRENCY_DEFAULT,
        verbose_name=_('currency'),
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('amount'))
    documents = models.URLField(
        blank=True,
        verbose_name=_('documents'),
        help_text=_('URL to the contract documents'),
    )
    comments = models.TextField(blank=True, verbose_name=_('comments'))

    class Meta:
        ordering = ('-period_start',)
        verbose_name = _('invoice')
        verbose_name_plural = _('invoices')

    def __str__(self):
        return self.number

    def get_status_color(self):
        return InvoiceStatusChoices.colors.get(self.status)

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:invoice', args=[self.pk])

    @property
    def total_invoicelines_amount(self):
        """
        Calculates the total amount for all related InvoiceLines.
        """
        return sum(invoiceline.amount for invoiceline in self.invoicelines.all())


class InvoiceLine(ContractBaseModel):
    invoice = models.ForeignKey(
        to='Invoice',
        on_delete=models.CASCADE,
        related_name='invoicelines',
        verbose_name=_('invoice'),
    )
    currency = models.CharField(
        max_length=3,
        choices=CurrencyChoices,
        default=CURRENCY_DEFAULT,
        verbose_name=_('currency'),
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('amount'))
    accounting_dimensions = models.ManyToManyField(
        AccountingDimension, blank=True, verbose_name=_('accounting dimensions')
    )
    comments = models.TextField(blank=True, verbose_name=_('comments'))

    class Meta:
        ordering = ('invoice',)
        verbose_name = _('invoice line')
        verbose_name_plural = _('invoice lines')

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:invoiceline', args=[self.pk])

    def clean(self):
        super().clean()
        # Check that the sum of the invoice line amount is not greater the invoice amount
        amount = self.amount
        invoice = self.invoice
        is_new = not bool(self.pk)
        if is_new:
            if amount > (invoice.amount - invoice.total_invoicelines_amount):
                raise ValidationError('Sum of invoice line amount greater than invoice amount')
        else:
            previous_amount = self.__class__.objects.get(pk=self.pk).amount
            if amount > (invoice.amount - invoice.total_invoicelines_amount + previous_amount):
                raise ValidationError('Sum of invoice line amount greater than invoice amount')

class RevenueCustomerTypeChoices(ChoiceSet):
    key = 'RevenueCustomer.customer_type'
    CHOICES = [
        ('operator', _('运营商'), 'blue'),
        ('enterprise', _('政企客户'), 'green'),
        ('integrator', _('集成商'), 'purple'),
        ('internal', _('内部客户'), 'grey'),
    ]


class RevenueProjectTypeChoices(ChoiceSet):
    key = 'RevenueProject.project_type'
    CHOICES = [
        ('fiber', _('光纤'), 'blue'),
        ('circuit', _('电路'), 'cyan'),
        ('idc', _('机房'), 'purple'),
        ('rack', _('机柜'), 'orange'),
        ('pipe', _('管道'), 'brown'),
        ('composite', _('综合项目'), 'grey'),
    ]


class RevenueProjectStatusChoices(ChoiceSet):
    key = 'RevenueProject.status'
    CHOICES = [
        ('draft', _('草稿'), 'grey'),
        ('approved', _('已审批'), 'blue'),
        ('executing', _('执行中'), 'cyan'),
        ('delivered', _('已交付'), 'purple'),
        ('operating', _('运营中'), 'green'),
        ('suspended', _('暂停'), 'orange'),
        ('terminated', _('终止'), 'red'),
        ('archived', _('归档'), 'grey'),
    ]


class RevenueContractTypeChoices(ChoiceSet):
    key = 'RevenueContract.contract_type'
    CHOICES = [
        ('milestone', _('阶段性'), 'blue'),
        ('recurring', _('周期性'), 'green'),
        ('framework', _('框架'), 'purple'),
        ('order', _('订单'), 'cyan'),
        ('hybrid', _('混合'), 'orange'),
    ]


class RevenueContractStatusChoices(ChoiceSet):
    key = 'RevenueContract.status'
    CHOICES = [
        ('draft', _('草稿'), 'grey'),
        ('approving', _('审批中'), 'yellow'),
        ('effective', _('生效'), 'green'),
        ('changing', _('变更中'), 'orange'),
        ('suspended', _('暂停'), 'orange'),
        ('terminated', _('终止'), 'red'),
        ('archived', _('归档'), 'grey'),
    ]


class RevenueOrderStatusChoices(ChoiceSet):
    key = 'RevenueOrder.status'
    CHOICES = [
        ('draft', _('草稿'), 'grey'),
        ('not_started', _('未开始'), 'blue'),
        ('executing', _('执行中'), 'cyan'),
        ('completed', _('已完成'), 'green'),
        ('suspended', _('暂停'), 'orange'),
        ('cancelled', _('已取消'), 'red'),
    ]

class RevenueVersionTypeChoices(ChoiceSet):
    key = 'RevenueContractVersion.change_type'
    CHOICES = [
        ('original', _('原始合同'), 'green'),
        ('supplement', _('补充协议'), 'blue'),
        ('repricing', _('调价'), 'orange'),
        ('extension', _('延期'), 'purple'),
        ('termination', _('终止'), 'red'),
    ]


class RevenueApprovalStatusChoices(ChoiceSet):
    key = 'Revenue.approval_status'
    CHOICES = [
        ('draft', _('草稿'), 'grey'),
        ('pending', _('待处理'), 'yellow'),
        ('effective', _('生效'), 'green'),
        ('approved', _('已审批'), 'green'),
        ('rejected', _('已驳回'), 'red'),
    ]


class RevenueLineStatusChoices(ChoiceSet):
    key = 'RevenueContractLine.status'
    CHOICES = [
        ('draft', _('草稿'), 'grey'),
        ('active', _('有效'), 'green'),
        ('suspended', _('暂停'), 'orange'),
        ('terminated', _('终止'), 'red'),
    ]


class RevenueProductCategoryChoices(ChoiceSet):
    key = 'RevenueContractLine.product_category'
    CHOICES = [
        ('fiber', _('光纤'), 'blue'),
        ('circuit', _('电路'), 'cyan'),
        ('idc_space', _('机房空间'), 'purple'),
        ('rack', _('机柜'), 'orange'),
        ('pipe', _('管道'), 'brown'),
        ('construction', _('工程建设'), 'yellow'),
        ('maintenance', _('运维服务'), 'green'),
        ('other', _('其他'), 'grey'),
    ]


class RevenueBillingRuleTypeChoices(ChoiceSet):
    key = 'RevenueBillingRule.rule_type'
    CHOICES = [
        ('milestone', _('阶段性'), 'blue'),
        ('recurring', _('周期性'), 'green'),
        ('one_time', _('一次性'), 'purple'),
    ]


class RevenueBillingTriggerEventChoices(ChoiceSet):
    key = 'RevenueBillingRule.trigger_event'
    CHOICES = [
        ('activation', _('\u5f00\u901a'), 'blue'),
        ('acceptance', _('\u9a8c\u6536'), 'green'),
        ('delivery', _('\u4ea4\u4ed8'), 'purple'),
    ]


class RevenueBillingCycleChoices(ChoiceSet):
    key = 'RevenueBillingRule.billing_cycle'
    CHOICES = [
        ('month', _('\u6708\u5ea6'), 'blue'),
        ('quarter', _('\u5b63\u5ea6'), 'purple'),
        ('year', _('\u5e74\u5ea6'), 'green'),
    ]


class RevenueBillingDirectionChoices(ChoiceSet):
    key = 'RevenueBillingRule.billing_direction'
    CHOICES = [
        ('postpay', _('\u540e\u4ed8'), 'green'),
        ('prepay', _('\u9884\u4ed8'), 'blue'),
    ]


class RevenueProrationRuleChoices(ChoiceSet):
    key = 'RevenueBillingRule.proration_rule'
    CHOICES = [
        ('actual_days', _('\u6309\u5b9e\u9645\u5929\u6570'), 'blue'),
        ('full_month', _('\u6309\u6574\u6708'), 'green'),
        ('none', _('\u4e0d\u6298\u7b97'), 'grey'),
    ]


class RevenueRoundingPrecisionChoices(ChoiceSet):
    key = 'RevenueBillingRule.rounding_precision'
    CHOICES = [
        ('0', _('\u4fdd\u75590\u4f4d'), 'grey'),
        ('1', _('\u4fdd\u75591\u4f4d'), 'blue'),
        ('2', _('\u4fdd\u75592\u4f4d'), 'green'),
    ]


class RevenuePlanTriggerTypeChoices(ChoiceSet):
    key = 'RevenueReceivablePlanVersion.trigger_type'
    CHOICES = [
        ('fixed_date', _('固定日期'), 'blue'),
        ('trigger_offset', _('条件触发'), 'purple'),
        ('estimated_date', _('预计日期'), 'yellow'),
    ]


class RevenuePlanStatusChoices(ChoiceSet):
    key = 'RevenueReceivablePlan.status'
    CHOICES = [
        ('draft', _('草稿'), 'grey'),
        ('effective', _('生效'), 'green'),
        ('closed', _('已关闭'), 'blue'),
        ('canceled', _('已取消'), 'red'),
    ]


class RevenueTriggerRecordStatusChoices(ChoiceSet):
    key = 'RevenueTriggerRecord.status'
    CHOICES = [
        ('pending', _('待确认'), 'yellow'),
        ('confirmed', _('已确认'), 'green'),
        ('canceled', _('已取消'), 'red'),
    ]


class RevenueAdjustmentTypeChoices(ChoiceSet):
    key = 'RevenueAdjustmentRecord.adjustment_type'
    CHOICES = [
        ('sla_deduction', _('SLA扣款'), 'red'),
        ('delay_compensation', _('延期赔偿'), 'orange'),
        ('discount', _('折扣'), 'yellow'),
        ('refund', _('退款'), 'purple'),
        ('write_off', _('红冲/核销'), 'blue'),
        ('other', _('其他'), 'grey'),
    ]


class RevenueAdjustmentStatusChoices(ChoiceSet):
    key = 'RevenueAdjustmentRecord.status'
    CHOICES = [
        ('draft', _('草稿'), 'grey'),
        ('confirmed', _('已确认'), 'green'),
        ('canceled', _('已取消'), 'red'),
    ]

class RevenueConfirmStatusChoices(ChoiceSet):
    key = 'RevenueReceivableBill.confirm_status'
    CHOICES = [
        ('draft', _('草稿'), 'grey'),
        ('confirmed', _('已确认'), 'green'),
        ('canceled', _('已作废'), 'red'),
    ]


class RevenueInvoiceStatusChoices(ChoiceSet):
    key = 'RevenueReceivableBill.invoice_status'
    CHOICES = [
        ('uninvoiced', _('未开票'), 'grey'),
        ('partially_invoiced', _('部分开票'), 'yellow'),
        ('fully_invoiced', _('已开票'), 'green'),
    ]


class RevenueReceiptStatusChoices(ChoiceSet):
    key = 'RevenueReceivableBill.receipt_status'
    CHOICES = [
        ('unpaid', _('未回款'), 'grey'),
        ('partially_paid', _('部分回款'), 'yellow'),
        ('fully_paid', _('已结清'), 'green'),
    ]


class RevenueAgeingStatusChoices(ChoiceSet):
    key = 'RevenueReceivableBill.ageing_status'
    CHOICES = [
        ('not_due', _('未到期'), 'green'),
        ('overdue', _('已逾期'), 'red'),
    ]


class RevenueRiskStatusChoices(ChoiceSet):
    key = 'RevenueReceivableBill.risk_status'
    CHOICES = [
        ('normal', _('正常'), 'green'),
        ('waived', _('已减免'), 'blue'),
        ('bad_debt', _('坏账'), 'red'),
    ]


class RevenueActiveStatusChoices(ChoiceSet):
    key = 'Revenue.active_status'
    CHOICES = [
        ('active', _('有效'), 'green'),
        ('canceled', _('已作废'), 'red'),
    ]


class RevenueMappingStatusChoices(ChoiceSet):
    key = 'RevenueInvoiceMapping.status'
    CHOICES = [
        ('active', _('有效'), 'green'),
        ('unmapped', _('已解绑'), 'grey'),
    ]


class RevenueReceiptMatchStatusChoices(ChoiceSet):
    key = 'RevenueReceipt.status'
    CHOICES = [
        ('unmatched', _('待匹配'), 'grey'),
        ('partially_allocated', _('部分分配'), 'yellow'),
        ('fully_allocated', _('已分配'), 'green'),
    ]


class RevenueReceiptAllocationTypeChoices(ChoiceSet):
    key = 'RevenueReceiptAllocation.allocation_type'
    CHOICES = [
        ('direct_receipt', _('正常回收'), 'green'),
    ]



class RevenueSourceSystemChoices(ChoiceSet):
    key = 'Revenue.source_system'
    CHOICES = [
        ('SAMPLE_DATA', _('\u6837\u4f8b\u6570\u636e'), 'grey'),
        ('LEGACY_LEDGER', _('合同台账迁移'), 'grey'),
        ('REVENUE_SYS', _('\u6536\u5165\u7cfb\u7edf'), 'green'),
        ('BANK_FLOW', _('\u94f6\u884c\u6d41\u6c34'), 'blue'),
    ]


class RevenueBillingChangeTriggerChoices(ChoiceSet):
    key = 'RevenueBillingSegment.change_trigger'
    CHOICES = [
        ('normal', _('\u6b63\u5e38\u8ba1\u8d39'), 'green'),
        ('contract_change', _('\u5408\u540c\u53d8\u66f4'), 'orange'),
        ('price_change', _('\u4ef7\u683c\u8c03\u6574'), 'blue'),
    ]


class RevenueSyncEntityTypeChoices(ChoiceSet):
    key = 'RevenueSyncLog.entity_type'
    CHOICES = [
        ('RevenueCustomer', _('\u5ba2\u6237'), 'blue'),
        ('RevenueProject', _('\u9879\u76ee'), 'cyan'),
        ('RevenueContract', _('\u6536\u5165\u5408\u540c'), 'green'),
        ('RevenueContractVersion', _('\u5408\u540c\u7248\u672c'), 'purple'),
        ('RevenueContractLine', _('\u5408\u540c\u9879'), 'purple'),
        ('RevenueBillingRule', _('\u8ba1\u8d39\u89c4\u5219'), 'orange'),
        ('RevenueReceivableBill', _('\u5e94\u6536\u8d26\u5355'), 'yellow'),
        ('RevenueReceivableLine', _('\u5e94\u6536\u660e\u7ec6'), 'yellow'),
        ('RevenueInvoice', _('\u53d1\u7968'), 'blue'),
        ('RevenueInvoiceLine', _('\u53d1\u7968\u660e\u7ec6'), 'blue'),
        ('RevenueInvoiceMapping', _('\u53d1\u7968\u6620\u5c04'), 'blue'),
        ('RevenueReceipt', _('\u56de\u6b3e'), 'green'),
        ('RevenueReceiptAllocation', _('\u56de\u6b3e\u5206\u914d'), 'green'),
    ]


class RevenueSyncStatusChoices(ChoiceSet):
    key = 'RevenueSyncLog.sync_status'
    CHOICES = [
        ('pending', _('待处理'), 'yellow'),
        ('synced', _('已同步'), 'green'),
        ('failed', _('失败'), 'red'),
        ('success', _('成功'), 'green'),
    ]


class RevenueCustomer(ContractBaseModel):
    name = models.CharField(max_length=200, unique=True, verbose_name=_('名称'))
    short_name = models.CharField(max_length=100, blank=True, verbose_name=_('简称'))
    usci = models.CharField(max_length=32, unique=True, verbose_name=_('统一社会信用代码'))
    finance_code = models.CharField(max_length=100, blank=True, verbose_name=_('财务系统编码'))
    eip_code = models.CharField(max_length=100, blank=True, verbose_name=_('EIP系统编码'))
    customer_type = models.CharField(max_length=50, choices=RevenueCustomerTypeChoices, verbose_name=_('客户类型'))
    sales_owner = models.CharField(max_length=100, verbose_name=_('销售负责人'))
    business_owner = models.CharField(max_length=100, verbose_name=_('商务负责人'))
    is_risk = models.BooleanField(default=False, verbose_name=_('风险客户'))
    address_phone = models.CharField(max_length=255, blank=True, verbose_name=_('地址与电话'))
    bank_account = models.CharField(max_length=255, blank=True, verbose_name=_('开户行及账号'))

    class Meta:
        ordering = ('name',)
        verbose_name = _('收入客户')
        verbose_name_plural = _('收入客户')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenuecustomer', args=[self.pk])


class RevenueProject(ContractBaseModel):
    name = models.CharField(max_length=200, verbose_name=_('名称'))
    customer = models.ForeignKey(RevenueCustomer, on_delete=models.PROTECT, related_name='revenue_projects')
    project_manager = models.CharField(max_length=100, verbose_name=_('项目经理'))
    sales_owner = models.CharField(max_length=100, verbose_name=_('销售负责人'))
    business_owner = models.CharField(max_length=100, verbose_name=_('商务负责人'))
    project_type = models.CharField(max_length=50, choices=RevenueProjectTypeChoices, verbose_name=_('项目类型'))
    status = models.CharField(max_length=50, choices=RevenueProjectStatusChoices, verbose_name=_('状态'))
    accumulated_receivable = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    accumulated_invoice = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    accumulated_receipt = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ('name',)
        constraints = [models.UniqueConstraint(fields=['customer', 'name'], name='unique_revenue_project_customer_name')]
        verbose_name = _('收入项目')
        verbose_name_plural = _('收入项目')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenueproject', args=[self.pk])


class RevenueContract(ContractBaseModel):
    contract_code = models.CharField(max_length=100, unique=True, verbose_name=_('合同编号'))
    name = models.CharField(max_length=200, verbose_name=_('名称'))
    customer = models.ForeignKey(RevenueCustomer, on_delete=models.PROTECT, related_name='revenue_contracts')
    contract_type = models.CharField(max_length=50, choices=RevenueContractTypeChoices)
    projects = models.ManyToManyField(RevenueProject, through='RevenueContractProject', related_name='revenue_contracts')
    our_party = models.CharField(max_length=200)
    customer_party = models.CharField(max_length=200)
    sign_date = models.DateField()
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    is_framework = models.BooleanField(default=False)
    status = models.CharField(max_length=50, choices=RevenueContractStatusChoices)
    sales_owner = models.CharField(max_length=100)
    business_owner = models.CharField(max_length=100)
    source_system = models.CharField(max_length=50, choices=RevenueSourceSystemChoices)
    external_id = models.CharField(max_length=100, blank=True)
    sync_status = models.CharField(max_length=50, choices=RevenueSyncStatusChoices, default='pending')
    sync_log = models.TextField(blank=True)

    class Meta:
        ordering = ('-created',)
        verbose_name = _('收入合同')
        verbose_name_plural = _('收入合同')

    def __str__(self):
        return f'{self.name}-{self.contract_code}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenuecontract', args=[self.pk])

    def get_status_color(self):
        return RevenueContractStatusChoices.colors.get(self.status)


class RevenueContractProject(ContractBaseModel):
    contract = models.ForeignKey(RevenueContract, on_delete=models.CASCADE, related_name='contract_projects')
    project = models.ForeignKey(RevenueProject, on_delete=models.PROTECT, related_name='project_contracts')

    class Meta:
        ordering = ('contract', 'project')
        constraints = [models.UniqueConstraint(fields=['contract', 'project'], name='unique_revenue_contract_project')]
        verbose_name = _('收入合同项目关联')
        verbose_name_plural = _('收入合同项目关联')

    def __str__(self):
        return f'{self.contract} / {self.project}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenuecontractproject', args=[self.pk])

class RevenueOrder(ContractBaseModel):
    order_code = models.CharField(max_length=100)
    contract = models.ForeignKey(RevenueContract, on_delete=models.CASCADE, related_name='orders')
    project = models.ForeignKey(RevenueProject, on_delete=models.PROTECT, related_name='revenue_orders')
    name = models.CharField(max_length=200, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=RevenueOrderStatusChoices, default='draft')
    source_system = models.CharField(
        max_length=50,
        choices=RevenueSourceSystemChoices,
        default='REVENUE_SYS',
    )
    external_id = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ('contract', 'project', 'order_code')
        constraints = [
            models.UniqueConstraint(
                fields=['contract', 'project', 'order_code'],
                name='unique_revenue_order_contract_project_code',
            )
        ]
        verbose_name = _('收入订单/开工单')
        verbose_name_plural = _('收入订单/开工单')

    def clean(self):
        super().clean()
        if self.project_id and self.contract_id and self.project.customer_id != self.contract.customer_id:
            raise ValidationError(_('订单项目与合同必须属于同一客户。'))
        if self.amount < 0:
            raise ValidationError(_('订单金额不能为负数。'))
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError(_('订单结束日期不能早于开始日期。'))

    def __str__(self):
        return f'{self.order_code} {self.name}'.strip()

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenueorder', args=[self.pk])

class RevenueContractVersion(ContractBaseModel):
    contract = models.ForeignKey(RevenueContract, on_delete=models.CASCADE, related_name='versions')
    version_code = models.CharField(max_length=50)
    change_type = models.CharField(max_length=50, choices=RevenueVersionTypeChoices)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=RevenueApprovalStatusChoices)

    class Meta:
        ordering = ('contract', 'start_date')
        constraints = [
            models.UniqueConstraint(fields=['contract', 'version_code'], name='unique_revenue_contract_version_code'),
            models.UniqueConstraint(fields=['contract'], condition=models.Q(status='effective'), name='unique_effective_revenue_contract_version'),
        ]
        verbose_name = _('收入合同版本')
        verbose_name_plural = _('收入合同版本')

    def __str__(self):
        return f'{self.contract.contract_code} {self.version_code}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenuecontractversion', args=[self.pk])


class RevenueContractLine(ContractBaseModel):
    contract = models.ForeignKey(RevenueContract, on_delete=models.CASCADE, related_name='lines')
    contract_version = models.ForeignKey(RevenueContractVersion, on_delete=models.PROTECT, related_name='lines')
    project = models.ForeignKey(RevenueProject, on_delete=models.PROTECT, related_name='contract_lines')
    revenue_order = models.ForeignKey(
        RevenueOrder,
        on_delete=models.PROTECT,
        related_name='contract_lines',
        blank=True,
        null=True,
    )
    order_id = models.CharField(max_length=100, blank=True)
    product_category = models.CharField(max_length=50, choices=RevenueProductCategoryChoices)
    charge_item = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit = models.CharField(max_length=50)
    valid_from = models.DateField()
    valid_to = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=RevenueLineStatusChoices)

    class Meta:
        ordering = ('contract', 'charge_item')
        verbose_name = _('收入合同项')
        verbose_name_plural = _('收入合同项')

    def clean(self):
        super().clean()
        if self.contract_version_id and self.contract_id and self.contract_version.contract_id != self.contract_id:
            raise ValidationError(_('合同项版本必须属于所选合同。'))
        if self.project_id and self.contract_id and self.project.customer_id != self.contract.customer_id:
            raise ValidationError(_('合同项项目与合同必须属于同一客户。'))
        if self.revenue_order_id:
            if self.revenue_order.contract_id != self.contract_id:
                raise ValidationError(_('合同项订单必须属于所选合同。'))
            if self.revenue_order.project_id != self.project_id:
                raise ValidationError(_('合同项订单必须属于所选项目。'))
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValidationError(_('合同项失效日期不能早于生效日期。'))
    def __str__(self):
        return f'{self.contract.contract_code} {self.charge_item}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenuecontractline', args=[self.pk])


class RevenueBillingRule(ContractBaseModel):
    contract_line = models.ForeignKey(RevenueContractLine, on_delete=models.CASCADE, related_name='billing_rules')
    contract_version = models.ForeignKey(RevenueContractVersion, on_delete=models.PROTECT, related_name='billing_rules')
    rule_type = models.CharField(max_length=50, choices=RevenueBillingRuleTypeChoices)
    trigger_event = models.CharField(max_length=50, choices=RevenueBillingTriggerEventChoices, blank=True)
    trigger_offset_days = models.PositiveIntegerField(
        default=0,
        help_text=_('\u9636\u6bb5\u6216\u4e00\u6b21\u6027\u89c4\u5219\u5728\u4e1a\u52a1\u4e8b\u4ef6\u786e\u8ba4\u540e\uff0c\u5ef6\u540e\u591a\u5c11\u5929\u5f62\u6210\u5e94\u6536\u3002'),
    )
    billing_cycle = models.CharField(max_length=50, choices=RevenueBillingCycleChoices, blank=True)
    billing_direction = models.CharField(max_length=50, choices=RevenueBillingDirectionChoices, blank=True)
    bill_generation_day = models.PositiveSmallIntegerField(blank=True, null=True)
    proration_rule = models.CharField(max_length=50, choices=RevenueProrationRuleChoices)
    rounding_precision = models.CharField(max_length=20, choices=RevenueRoundingPrecisionChoices)
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=50, choices=RevenueApprovalStatusChoices)

    class Meta:
        ordering = ('contract_line', 'rule_type')
        verbose_name = _('收入计费规则')
        verbose_name_plural = _('收入计费规则')

    def clean(self):
        super().clean()
        if self.rule_type == 'recurring':
            if (
                not self.billing_cycle
                or not self.billing_direction
                or self.bill_generation_day is None
                or self.trigger_event
                or self.trigger_offset_days
            ):
                raise ValidationError(_('周期性计费规则必须且只能填写计费周期、计费方向和账单生成日。'))
        elif self.rule_type in ('milestone', 'one_time'):
            if self.billing_cycle or self.billing_direction or self.bill_generation_day is not None or not self.trigger_event:
                raise ValidationError(_('阶段性和一次性计费规则必须且只能填写触发节点。'))

    def __str__(self):
        return f'{self.contract_line} {self.rule_type}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenuebillingrule', args=[self.pk])


class RevenueBillingSegment(ContractBaseModel):
    contract_line = models.ForeignKey(RevenueContractLine, on_delete=models.CASCADE, related_name='billing_segments')
    billing_rule = models.ForeignKey(RevenueBillingRule, on_delete=models.PROTECT, related_name='billing_segments')
    segment_start = models.DateField()
    segment_end = models.DateField()
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    change_trigger = models.CharField(max_length=50, choices=RevenueBillingChangeTriggerChoices)
    billing_rule_snapshot = models.JSONField(default=dict)

    class Meta:
        ordering = ('contract_line', 'segment_start')
        verbose_name = _('收入计费分段')
        verbose_name_plural = _('收入计费分段')

    def __str__(self):
        return f'{self.contract_line} {self.segment_start} - {self.segment_end}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenuebillingsegment', args=[self.pk])


class RevenueReceivablePlan(ContractBaseModel):
    plan_code = models.CharField(max_length=100, unique=True)
    contract = models.ForeignKey(RevenueContract, on_delete=models.CASCADE, related_name='receivable_plans')
    contract_line = models.ForeignKey(RevenueContractLine, on_delete=models.PROTECT, related_name='receivable_plans')
    billing_rule = models.ForeignKey(RevenueBillingRule, on_delete=models.PROTECT, related_name='receivable_plans')
    charge_item = models.CharField(max_length=200)
    order_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50, choices=RevenuePlanStatusChoices, default='draft')

    class Meta:
        ordering = ('contract', 'plan_code')
        verbose_name = _('收入应收计划')
        verbose_name_plural = _('收入应收计划')

    def clean(self):
        super().clean()
        if self.contract_line_id and self.contract_id and self.contract_line.contract_id != self.contract_id:
            raise ValidationError(_('应收计划的合同项必须属于所选合同。'))
        if self.billing_rule_id and self.contract_line_id and self.billing_rule.contract_line_id != self.contract_line_id:
            raise ValidationError(_('应收计划的计费规则必须属于所选合同项。'))

    def __str__(self):
        return f'{self.plan_code} {self.charge_item}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenuereceivableplan', args=[self.pk])


class RevenueReceivablePlanVersion(ContractBaseModel):
    plan = models.ForeignKey(RevenueReceivablePlan, on_delete=models.CASCADE, related_name='versions')
    version_no = models.PositiveIntegerField()
    trigger_type = models.CharField(max_length=50, choices=RevenuePlanTriggerTypeChoices)
    trigger_event = models.CharField(max_length=50, choices=RevenueBillingTriggerEventChoices, blank=True)
    offset_days = models.PositiveIntegerField(blank=True, null=True)
    planned_date = models.DateField(blank=True, null=True)
    planned_amount = models.DecimalField(max_digits=14, decimal_places=2)
    effective_from = models.DateField()
    change_reason = models.TextField(blank=True)
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ('plan', 'version_no')
        constraints = [
            models.UniqueConstraint(fields=['plan', 'version_no'], name='unique_revenue_plan_version_no'),
            models.UniqueConstraint(
                fields=['plan'],
                condition=models.Q(is_current=True),
                name='unique_current_revenue_plan_version',
            ),
        ]
        verbose_name = _('收入应收计划版本')
        verbose_name_plural = _('收入应收计划版本')

    def clean(self):
        super().clean()
        if self.planned_amount < 0:
            raise ValidationError(_('计划金额不能为负数。'))
        if self.trigger_type == 'fixed_date':
            if not self.planned_date or self.trigger_event or self.offset_days is not None:
                raise ValidationError(_('固定日期计划必须且只能填写计划日期。'))
        elif self.trigger_type == 'trigger_offset':
            if not self.trigger_event or self.offset_days is None or self.planned_date:
                raise ValidationError(_('条件触发计划必须填写触发节点和偏移天数，且不能填写虚假日期。'))
        elif self.trigger_type == 'estimated_date':
            if not self.planned_date or self.offset_days is not None:
                raise ValidationError(_('预计日期计划必须填写预计日期，且不能填写偏移天数。'))

    def __str__(self):
        return f'{self.plan.plan_code} V{self.version_no}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenuereceivableplanversion', args=[self.pk])


class RevenueTriggerRecord(ContractBaseModel):
    plan = models.ForeignKey(
        RevenueReceivablePlan,
        on_delete=models.CASCADE,
        related_name='trigger_records',
        blank=True,
        null=True,
    )
    billing_rule = models.ForeignKey(
        RevenueBillingRule,
        on_delete=models.CASCADE,
        related_name='trigger_records',
        blank=True,
        null=True,
    )
    plan_version = models.ForeignKey(
        RevenueReceivablePlanVersion,
        on_delete=models.PROTECT,
        related_name='trigger_records',
        blank=True,
        null=True,
    )
    trigger_event = models.CharField(max_length=50, choices=RevenueBillingTriggerEventChoices)
    actual_trigger_date = models.DateField()
    status = models.CharField(max_length=50, choices=RevenueTriggerRecordStatusChoices, default='confirmed')
    source_system = models.CharField(max_length=50, choices=RevenueSourceSystemChoices)
    external_id = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ('plan', '-actual_trigger_date')
        constraints = [
            models.CheckConstraint(
                condition=models.Q(plan__isnull=False) | models.Q(billing_rule__isnull=False),
                name='revenue_trigger_requires_target',
            ),
        ]
        verbose_name = _('收入应收触发记录')
        verbose_name_plural = _('收入应收触发记录')

    def clean(self):
        super().clean()
        if not self.plan_id and not self.billing_rule_id:
            raise ValidationError(_('触发记录必须关联计费规则；历史数据也可以继续关联应收计划。'))
        if self.plan_version_id and self.plan_version.plan_id != self.plan_id:
            raise ValidationError(_('触发记录的计划版本必须属于所选应收计划。'))
        if self.plan_id and self.billing_rule_id and self.plan.billing_rule_id != self.billing_rule_id:
            raise ValidationError(_('触发记录的应收计划和计费规则必须一致。'))
        if self.billing_rule_id and self.trigger_event != self.billing_rule.trigger_event:
            raise ValidationError(_('触发记录的业务事件必须与计费规则一致。'))

    def __str__(self):
        target = self.plan.plan_code if self.plan_id else str(self.billing_rule)
        return f'{target} {self.get_trigger_event_display()} {self.actual_trigger_date}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenuetriggerrecord', args=[self.pk])


class RevenueAdjustmentRecord(ContractBaseModel):
    plan = models.ForeignKey(
        RevenueReceivablePlan,
        on_delete=models.PROTECT,
        related_name='adjustments',
        blank=True,
        null=True,
    )
    receivable_line = models.ForeignKey(
        'RevenueReceivableLine',
        on_delete=models.PROTECT,
        related_name='adjustment_records',
        blank=True,
        null=True,
    )
    adjustment_type = models.CharField(max_length=50, choices=RevenueAdjustmentTypeChoices)
    adjustment_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.TextField()
    source_system = models.CharField(max_length=50, choices=RevenueSourceSystemChoices)
    external_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50, choices=RevenueAdjustmentStatusChoices, default='draft')

    class Meta:
        ordering = ('-adjustment_date', '-created')
        constraints = [
            models.CheckConstraint(
                condition=models.Q(plan__isnull=False) | models.Q(receivable_line__isnull=False),
                name='revenue_adjustment_has_target',
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0) | models.Q(amount__lt=0),
                name='revenue_adjustment_nonzero',
            ),
        ]
        verbose_name = _('收入应收调整记录')
        verbose_name_plural = _('收入应收调整记录')

    def clean(self):
        super().clean()
        if not self.plan_id and not self.receivable_line_id:
            raise ValidationError(_('调整记录必须关联应收计划或应收明细。'))
        if self.amount == 0:
            raise ValidationError(_('调整金额不能为零。'))
        if self.plan_id and self.receivable_line_id:
            if self.receivable_line.bill.contract_id != self.plan.contract_id:
                raise ValidationError(_('调整记录关联的计划与应收明细必须属于同一合同。'))

    def __str__(self):
        target = self.plan or self.receivable_line
        return f'{target} {self.get_adjustment_type_display()} {self.amount}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenueadjustmentrecord', args=[self.pk])

class RevenueReceivableBill(ContractBaseModel):
    bill_code = models.CharField(max_length=100, unique=True)
    customer = models.ForeignKey(RevenueCustomer, on_delete=models.PROTECT, related_name='receivable_bills')
    contract = models.ForeignKey(RevenueContract, on_delete=models.PROTECT, related_name='receivable_bills')
    project = models.ForeignKey(RevenueProject, on_delete=models.PROTECT, related_name='receivable_bills', blank=True, null=True)
    billing_period = models.CharField(max_length=50)
    receivable_date = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    adjusted_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=14, decimal_places=2)
    invoiced_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    receipted_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    confirm_status = models.CharField(max_length=50, choices=RevenueConfirmStatusChoices)
    invoice_status = models.CharField(max_length=50, choices=RevenueInvoiceStatusChoices)
    receipt_status = models.CharField(max_length=50, choices=RevenueReceiptStatusChoices)
    ageing_status = models.CharField(max_length=50, choices=RevenueAgeingStatusChoices)
    risk_status = models.CharField(max_length=50, choices=RevenueRiskStatusChoices)

    class Meta:
        ordering = ('-receivable_date',)
        verbose_name = _('收入应收账单')
        verbose_name_plural = _('收入应收账单')

    def __str__(self):
        return self.bill_code

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenuereceivablebill', args=[self.pk])


class RevenueReceivableLine(ContractBaseModel):
    bill = models.ForeignKey(RevenueReceivableBill, on_delete=models.CASCADE, related_name='lines')
    contract_line = models.ForeignKey(RevenueContractLine, on_delete=models.PROTECT, related_name='receivable_lines')
    billing_rule = models.ForeignKey(RevenueBillingRule, on_delete=models.PROTECT, related_name='receivable_lines')
    receivable_plan = models.ForeignKey(
        RevenueReceivablePlan,
        on_delete=models.PROTECT,
        related_name='receivable_lines',
        blank=True,
        null=True,
    )
    start_date = models.DateField()
    end_date = models.DateField()
    receivable_date = models.DateField(blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    adjusted_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=14, decimal_places=2)
    risk_status = models.CharField(max_length=50, choices=RevenueRiskStatusChoices)
    idempotent_key = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ('bill', 'start_date')
        verbose_name = _('收入应收明细')
        verbose_name_plural = _('收入应收明细')

    def clean(self):
        super().clean()
        if self.receivable_date and self.due_date and self.due_date < self.receivable_date:
            raise ValidationError(_('应收明细到期日不能早于应收形成日。'))
        if self.net_amount != self.amount + self.adjusted_amount:
            raise ValidationError(_('应收明细净额必须等于原始金额加修正金额。'))
        if self.receivable_plan_id:
            if self.receivable_plan.contract_line_id != self.contract_line_id:
                raise ValidationError(_('应收明细的应收计划必须属于所选合同项。'))
            if self.receivable_plan.billing_rule_id != self.billing_rule_id:
                raise ValidationError(_('应收明细的应收计划必须属于所选计费规则。'))
            if self.receivable_plan.contract_id != self.bill.contract_id:
                raise ValidationError(_('应收明细的应收计划与应收账单必须属于同一合同。'))

    def __str__(self):
        return f'{self.bill.bill_code} {self.start_date} - {self.end_date}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenuereceivableline', args=[self.pk])

class RevenueInvoice(ContractBaseModel):
    invoice_code = models.CharField(max_length=100, unique=True)
    customer = models.ForeignKey(RevenueCustomer, on_delete=models.PROTECT, related_name='revenue_invoices')
    invoice_type = models.CharField(max_length=50, choices=(('paper', _('纸质票据')), ('electronic', _('电子票据')), ('other', _('其他'))))
    invoice_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    source_system = models.CharField(max_length=50, choices=RevenueSourceSystemChoices)
    external_id = models.CharField(max_length=100, blank=True)
    sync_status = models.CharField(max_length=50, choices=RevenueSyncStatusChoices, default='pending')
    sync_log = models.TextField(blank=True)

    class Meta:
        ordering = ('-invoice_date',)
        verbose_name = _('收入发票')
        verbose_name_plural = _('收入发票')

    @property
    def total_line_amount(self):
        return self.lines.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

    def clean(self):
        super().clean()
        if self.pk and self.total_line_amount != self.amount:
            raise ValidationError(_('收入发票金额必须等于发票明细金额合计。'))

    def __str__(self):
        return self.invoice_code

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenueinvoice', args=[self.pk])


class RevenueInvoiceLine(ContractBaseModel):
    invoice = models.ForeignKey(RevenueInvoice, on_delete=models.CASCADE, related_name='lines')
    line_no = models.PositiveIntegerField()
    external_line_id = models.CharField(max_length=100, blank=True)
    item_name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ('invoice', 'line_no')
        constraints = [models.UniqueConstraint(fields=['invoice', 'line_no'], name='unique_revenue_invoice_line_no')]
        verbose_name = _('收入发票明细')
        verbose_name_plural = _('收入发票明细')

    def __str__(self):
        return f'{self.invoice.invoice_code} #{self.line_no}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenueinvoiceline', args=[self.pk])


class RevenueInvoiceMapping(ContractBaseModel):
    receivable_line = models.ForeignKey(RevenueReceivableLine, on_delete=models.PROTECT, related_name='invoice_mappings')
    invoice_line = models.ForeignKey(RevenueInvoiceLine, on_delete=models.PROTECT, related_name='receivable_mappings')
    mapped_amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=50, choices=RevenueMappingStatusChoices, default='active')
    operator = models.CharField(max_length=100)
    approval_batch_no = models.CharField(max_length=100)

    class Meta:
        ordering = ('receivable_line', 'invoice_line')
        constraints = [
            models.UniqueConstraint(
                fields=['receivable_line', 'invoice_line'],
                condition=models.Q(status='active'),
                name='unique_active_revenue_invoice_mapping',
            )
        ]
        verbose_name = _('收入发票映射')
        verbose_name_plural = _('收入发票映射')

    def _active_total_for(self, field_name):
        value = getattr(self, field_name)
        queryset = RevenueInvoiceMapping.objects.filter(status='active', **{field_name: value})
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)
        return queryset.aggregate(total=models.Sum('mapped_amount'))['total'] or Decimal('0')

    def clean(self):
        super().clean()
        if self.status != 'active':
            return
        if self._active_total_for('receivable_line') + self.mapped_amount > self.receivable_line.net_amount:
            raise ValidationError(_('映射金额超过应收明细净额。'))
        if self._active_total_for('invoice_line') + self.mapped_amount > self.invoice_line.amount:
            raise ValidationError(_('映射金额超过发票明细金额。'))

    def __str__(self):
        return f'{self.receivable_line} -> {self.invoice_line}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenueinvoicemapping', args=[self.pk])


class RevenueReceipt(ContractBaseModel):
    customer = models.ForeignKey(RevenueCustomer, on_delete=models.PROTECT, related_name='receipts')
    receipt_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    allocated_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    unallocated_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    bank_flow_no = models.CharField(max_length=100, unique=True)
    payer_name = models.CharField(max_length=200)
    status = models.CharField(max_length=50, choices=RevenueReceiptMatchStatusChoices, default='unmatched')
    source_system = models.CharField(max_length=50, choices=RevenueSourceSystemChoices)
    external_id = models.CharField(max_length=100, blank=True)
    sync_status = models.CharField(max_length=50, choices=RevenueSyncStatusChoices, default='pending')
    sync_log = models.TextField(blank=True)

    class Meta:
        ordering = ('-receipt_date',)
        constraints = [models.CheckConstraint(condition=models.Q(unallocated_amount__gte=0), name='revenue_receipt_unallocated_nonnegative')]
        verbose_name = _('收入回款')
        verbose_name_plural = _('收入回款')

    def update_totals(self):
        allocated_total = self.allocations.filter(status='active').aggregate(
            total=models.Sum('allocated_amount')
        )['total'] or Decimal('0')
        self.allocated_total = allocated_total
        self.unallocated_amount = self.amount - allocated_total
        if allocated_total == 0:
            self.status = 'unmatched'
        elif allocated_total < self.amount:
            self.status = 'partially_allocated'
        else:
            self.status = 'fully_allocated'
        self.save(update_fields=['allocated_total', 'unallocated_amount', 'status'])

    def __str__(self):
        return self.bank_flow_no

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenuereceipt', args=[self.pk])


class RevenueReceiptAllocation(ContractBaseModel):
    receipt = models.ForeignKey(RevenueReceipt, on_delete=models.PROTECT, related_name='allocations')
    receivable_line = models.ForeignKey(RevenueReceivableLine, on_delete=models.PROTECT, related_name='receipt_allocations')
    invoice_mapping = models.ForeignKey(RevenueInvoiceMapping, on_delete=models.PROTECT, related_name='receipt_allocations', blank=True, null=True)
    allocated_amount = models.DecimalField(max_digits=14, decimal_places=2)
    allocation_type = models.CharField(max_length=50, choices=RevenueReceiptAllocationTypeChoices)
    status = models.CharField(max_length=50, choices=RevenueActiveStatusChoices, default='active')
    operator = models.CharField(max_length=100)
    approval_batch_no = models.CharField(max_length=100)

    class Meta:
        ordering = ('receipt',)
        verbose_name = _('收入回款分配')
        verbose_name_plural = _('收入回款分配')

    def _active_total(self, **filters):
        queryset = RevenueReceiptAllocation.objects.filter(status='active', **filters)
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)
        return queryset.aggregate(total=models.Sum('allocated_amount'))['total'] or Decimal('0')

    def _active_total_for_invoice_mapping(self):
        if not self.invoice_mapping:
            return Decimal('0')
        return self._active_total(invoice_mapping=self.invoice_mapping)

    def _active_total_for_receivable_line(self):
        if not self.receivable_line_id:
            return Decimal('0')
        return self._active_total(receivable_line=self.receivable_line)

    def _active_total_for_receipt(self):
        if not self.receipt_id:
            return Decimal('0')
        return self._active_total(receipt=self.receipt)

    def clean(self):
        super().clean()
        if self.allocated_amount is not None and self.allocated_amount <= 0:
            raise ValidationError(_('\u56de\u6b3e\u5206\u914d\u91d1\u989d\u5fc5\u987b\u5927\u4e8e0\u3002'))
        if self.receivable_line_id is None:
            raise ValidationError(_('\u56de\u6b3e\u5206\u914d\u5fc5\u987b\u5173\u8054\u5e94\u6536\u660e\u7ec6\u3002'))
        if self.invoice_mapping and self.invoice_mapping.receivable_line_id != self.receivable_line_id:
            raise ValidationError(_('\u53d1\u7968\u6620\u5c04\u5173\u8054\u7684\u5e94\u6536\u660e\u7ec6\u5fc5\u987b\u4e0e\u5206\u914d\u8bb0\u5f55\u7684\u5e94\u6536\u660e\u7ec6\u4e00\u81f4\u3002'))
        if self.status == 'active':
            if self._active_total_for_receipt() + self.allocated_amount > self.receipt.amount:
                raise ValidationError(_('\u56de\u6b3e\u5206\u914d\u91d1\u989d\u8d85\u8fc7\u56de\u6b3e\u5230\u8d26\u91d1\u989d\u3002'))
            if self._active_total_for_receivable_line() + self.allocated_amount > self.receivable_line.net_amount:
                raise ValidationError(_('\u56de\u6b3e\u5206\u914d\u91d1\u989d\u8d85\u8fc7\u5e94\u6536\u660e\u7ec6\u51c0\u989d\u3002'))
            if self.invoice_mapping:
                if self._active_total_for_invoice_mapping() + self.allocated_amount > self.invoice_mapping.mapped_amount:
                    raise ValidationError(_('\u56de\u6b3e\u5206\u914d\u91d1\u989d\u8d85\u8fc7\u53d1\u7968\u6620\u5c04\u91d1\u989d\u3002'))

    def save(self, *args, **kwargs):
        self.full_clean()
        previous = None
        if self.pk:
            previous = RevenueReceiptAllocation.objects.filter(pk=self.pk).first()
        with transaction.atomic():
            super().save(*args, **kwargs)
            self.receipt.update_totals()
            if previous and previous.receipt_id != self.receipt_id:
                previous.receipt.update_totals()

    def delete(self, *args, **kwargs):
        receipt = self.receipt
        with transaction.atomic():
            result = super().delete(*args, **kwargs)
            receipt.update_totals()
            return result

    def __str__(self):
        return f'{self.receipt} {self.allocated_amount}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenuereceiptallocation', args=[self.pk])

class RevenueSyncLog(ContractBaseModel):
    source_system = models.CharField(max_length=50, choices=RevenueSourceSystemChoices)
    entity_type = models.CharField(max_length=50, choices=RevenueSyncEntityTypeChoices)
    entity_id = models.CharField(max_length=100)
    external_id = models.CharField(max_length=100)
    sync_direction = models.CharField(max_length=20, choices=(('INBOUND', _('入站')), ('OUTBOUND', _('出站'))))
    sync_status = models.CharField(max_length=50, choices=RevenueSyncStatusChoices)
    request_payload = models.JSONField(blank=True, null=True)
    response_payload = models.JSONField(blank=True, null=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ('-created',)
        verbose_name = _('收入同步日志')
        verbose_name_plural = _('收入同步日志')

    def __str__(self):
        return f'{self.source_system} {self.entity_type} {self.sync_status}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_contract:revenuesynclog', args=[self.pk])


def _apply_revenue_verbose_names():
    verbose_names = {
        RevenueCustomer: {
            'name': '名称', 'short_name': '简称', 'usci': '统一社会信用代码', 'finance_code': '财务系统编码',
            'eip_code': 'EIP系统编码', 'customer_type': '客户类型', 'sales_owner': '销售负责人',
            'business_owner': '商务负责人', 'is_risk': '风险客户', 'address_phone': '地址与电话',
            'bank_account': '开户行及账号',
        },
        RevenueProject: {
            'name': '名称', 'customer': '客户', 'project_manager': '项目经理', 'sales_owner': '销售负责人',
            'business_owner': '商务负责人', 'project_type': '项目类型', 'status': '状态',
            'accumulated_receivable': '累计应收金额', 'accumulated_invoice': '累计开票金额',
            'accumulated_receipt': '累计回款金额',
        },
        RevenueContract: {
            'contract_code': '合同编号', 'name': '合同名称', 'customer': '客户', 'contract_type': '合同计费类型',
            'projects': '项目', 'our_party': '我方签约主体', 'customer_party': '对方签约主体',
            'sign_date': '签约日期', 'start_date': '开始日期', 'end_date': '结束日期',
            'total_amount': '合同总金额', 'is_framework': '是否框架合同', 'status': '状态',
            'sales_owner': '销售负责人', 'business_owner': '商务负责人', 'source_system': '来源系统',
            'external_id': '外部系统ID', 'sync_status': '同步状态', 'sync_log': '同步日志',
        },
        RevenueContractProject: {'contract': '合同', 'project': '项目'},
        RevenueOrder: {
            'order_code': '订单/开工单编号', 'contract': '合同', 'project': '项目', 'name': '订单名称',
            'amount': '订单金额', 'start_date': '业务开始日期', 'end_date': '业务结束日期',
            'status': '状态', 'source_system': '来源系统', 'external_id': '外部系统ID',
        },
        RevenueContractVersion: {
            'contract': '合同', 'version_code': '版本号', 'change_type': '变更类型',
            'start_date': '生效日期', 'end_date': '失效日期', 'status': '状态',
        },
        RevenueContractLine: {
            'contract': '合同', 'contract_version': '合同版本', 'project': '项目', 'revenue_order': '订单/开工单', 'order_id': '原订单号',
            'product_category': '产品类别', 'charge_item': '收费项', 'unit_price': '单价',
            'quantity': '数量', 'unit': '单位', 'valid_from': '生效日期', 'valid_to': '失效日期',
            'status': '状态',
        },
        RevenueBillingRule: {
            'contract_line': '合同项', 'contract_version': '合同版本', 'rule_type': '计费方式',
            'trigger_event': '触发节点', 'trigger_offset_days': '触发后天数',
            'billing_cycle': '计费周期', 'billing_direction': '计费方向',
            'bill_generation_day': '账单生成日', 'proration_rule': '折算规则',
            'rounding_precision': '舍入精度', 'is_active': '是否启用', 'status': '状态',
        },
        RevenueBillingSegment: {
            'contract_line': '合同项', 'billing_rule': '计费规则', 'segment_start': '分段开始',
            'segment_end': '分段结束', 'unit_price': '单价', 'quantity': '数量', 'amount': '金额',
            'change_trigger': '触发原因', 'billing_rule_snapshot': '计费规则快照',
        },
        RevenueReceivablePlan: {
            'plan_code': '计划编号', 'contract': '合同', 'contract_line': '合同项',
            'billing_rule': '计费规则', 'charge_item': '收费项', 'order_id': '订单号', 'status': '状态',
        },
        RevenueReceivablePlanVersion: {
            'plan': '应收计划', 'version_no': '版本号', 'trigger_type': '触发方式',
            'trigger_event': '触发节点', 'offset_days': '触发后天数', 'planned_date': '计划日期',
            'planned_amount': '计划金额', 'effective_from': '生效日期', 'change_reason': '变更原因',
            'is_current': '当前版本',
        },
        RevenueTriggerRecord: {
            'plan': '应收计划', 'billing_rule': '计费规则', 'plan_version': '计划版本',
            'trigger_event': '触发节点',
            'actual_trigger_date': '实际触发日期', 'status': '状态', 'source_system': '来源系统',
            'external_id': '外部系统ID', 'notes': '说明',
        },
        RevenueAdjustmentRecord: {
            'plan': '应收计划', 'receivable_line': '应收明细', 'adjustment_type': '调整类型',
            'adjustment_date': '调整日期', 'amount': '调整金额', 'reason': '调整原因',
            'source_system': '来源系统', 'external_id': '外部系统ID', 'status': '状态',
        },
        RevenueReceivableBill: {
            'bill_code': '应收账单编号', 'customer': '客户', 'contract': '合同', 'project': '项目',
            'billing_period': '账期', 'receivable_date': '应收日期', 'due_date': '到期日期',
            'amount': '原始金额', 'adjusted_amount': '修正金额', 'net_amount': '应收净额',
            'invoiced_amount': '已开票金额', 'receipted_amount': '已回款金额',
            'confirm_status': '确认状态', 'invoice_status': '开票状态', 'receipt_status': '回款状态',
            'ageing_status': '账龄状态', 'risk_status': '风险状态',
        },
        RevenueReceivableLine: {
            'bill': '应收账单', 'contract_line': '合同项', 'billing_rule': '计费规则',
            'receivable_plan': '应收计划', 'start_date': '计费开始', 'end_date': '计费结束',
            'receivable_date': '应收日期', 'due_date': '到期日期', 'amount': '原始金额',
            'adjusted_amount': '修正金额', 'net_amount': '应收净额', 'risk_status': '风险状态',
            'idempotent_key': '幂等键',
        },
        RevenueInvoice: {
            'invoice_code': '发票号码', 'customer': '客户', 'invoice_type': '票据形式',
            'invoice_date': '开票日期', 'amount': '发票金额', 'source_system': '来源系统',
            'external_id': '外部系统ID', 'sync_status': '同步状态', 'sync_log': '同步日志',
        },
        RevenueInvoiceLine: {
            'invoice': '发票', 'line_no': '明细行号', 'external_line_id': '外部明细ID',
            'item_name': '项目名称', 'amount': '金额',
        },
        RevenueInvoiceMapping: {
            'receivable_line': '应收明细', 'invoice_line': '发票明细', 'mapped_amount': '映射金额',
            'status': '状态', 'operator': '经办人', 'approval_batch_no': '审批批次号',
        },
        RevenueReceipt: {
            'customer': '客户', 'receipt_date': '到账日期', 'amount': '到账金额',
            'allocated_total': '已分配金额', 'unallocated_amount': '待分配余额',
            'bank_flow_no': '银行流水号', 'payer_name': '付款方名称', 'status': '匹配状态',
            'source_system': '来源系统', 'external_id': '外部系统ID', 'sync_status': '同步状态',
            'sync_log': '同步日志',
        },
        RevenueReceiptAllocation: {
            'receipt': '回款', 'receivable_line': '应收明细', 'invoice_mapping': '发票映射',
            'allocated_amount': '分配金额', 'allocation_type': '分配类型',
            'status': '状态', 'operator': '经办人', 'approval_batch_no': '审批批次号',
        },
        RevenueSyncLog: {
            'source_system': '来源系统', 'entity_type': '实体类型', 'entity_id': '本地实体ID',
            'external_id': '外部系统ID', 'sync_direction': '同步方向', 'sync_status': '同步状态',
            'request_payload': '请求报文', 'response_payload': '响应报文', 'error_message': '错误信息',
        },
    }
    for model, names in verbose_names.items():
        for field_name, label in names.items():
            try:
                model._meta.get_field(field_name).verbose_name = _(label)
            except Exception:
                pass


_apply_revenue_verbose_names()
