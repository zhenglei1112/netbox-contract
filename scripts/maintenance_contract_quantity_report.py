from decimal import Decimal, InvalidOperation

from django.db.models import Count
from extras.scripts import Script

from netbox_contract.models import (
    AccountingDimension,
    Contract,
    ContractType,
    Invoice,
    InvoiceLine,
)


name = '代维日常合同线路维护数量统计'
TARGET_CONTRACT_STATUS = '执行中'


def parse_quantity(raw):
    """将自定义字段值转换为有限 Decimal；无效值返回 None。"""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return None

    try:
        quantity = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None

    return quantity if quantity.is_finite() else None


def escape_markdown_cell(value):
    """转义 Markdown 表格中的特殊字符。"""
    return (
        str(value)
        .replace('\\', '\\\\')
        .replace('|', '\\|')
        .replace('\r', ' ')
        .replace('\n', ' ')
    )


def format_decimal(value):
    return format(value, 'f')


def append_zero_result_diagnostics(output, contract_type):
    """在零结果时展示每一层筛选计数，帮助定位生产数据口径差异。"""
    contracts = Contract.objects.filter(contract_type=contract_type)
    status_counts = list(
        contracts.values('status')
        .annotate(count=Count('id'))
        .order_by('status')
    )
    eligible_contracts = contracts.filter(status=TARGET_CONTRACT_STATUS)
    template_invoices = Invoice.objects.filter(
        template=True,
        contracts__in=eligible_contracts,
    ).distinct()
    template_lines = InvoiceLine.objects.filter(
        invoice__in=template_invoices,
    ).distinct()
    target_dimensions = AccountingDimension.objects.filter(
        name='线路维护',
        value='线路维护',
    )
    matching_lines = template_lines.filter(
        accounting_dimensions__in=target_dimensions,
    ).distinct()

    status_text = '、'.join(
        f"{item['status']}={item['count']}"
        for item in status_counts
    ) or '无'
    output.extend([
        '',
        '=== 零结果诊断 ===',
        f'“代维-日常”合同总数: {contracts.count()}',
        f'实际状态值及数量: {status_text}',
        f'脚本采用的“执行中”状态值: {TARGET_CONTRACT_STATUS}',
        f'状态匹配的合同数: {eligible_contracts.count()}',
        f'这些合同关联的付款模板数: {template_invoices.count()}',
        f'上述付款模板的明细数: {template_lines.count()}',
        f'“线路维护:线路维护”统计维度定义数: {target_dimensions.count()}',
        f'关联目标统计维度的付款模板明细数: {matching_lines.count()}',
    ])


class MaintenanceContractQuantityReport(Script):
    class Meta:
        name = '代维日常合同线路维护数量统计'
        description = (
            '统计执行中的代维-日常合同里，线路维护:线路维护付款模板明细的数量字段'
        )
        commit_default = False

    def run(self, data, commit):
        try:
            contract_type = ContractType.objects.get(name='代维-日常')
        except ContractType.DoesNotExist:
            message = '错误：未找到合同类型“代维-日常”'
            self.log_error(message)
            return message

        queryset = (
            InvoiceLine.objects.filter(
                invoice__template=True,
                invoice__contracts__contract_type=contract_type,
                invoice__contracts__status=TARGET_CONTRACT_STATUS,
                accounting_dimensions__name='线路维护',
                accounting_dimensions__value='线路维护',
            )
            .values(
                'id',
                'invoice_id',
                'custom_field_data',
                'invoice__contracts__id',
                'invoice__contracts__name',
            )
            .distinct()
        )
        contract_ids = set()
        lines_by_id = {}
        for result in queryset:
            contract_ids.add(result['invoice__contracts__id'])
            line_key = (result['invoice_id'], result['id'])
            custom_data = result['custom_field_data']
            if not isinstance(custom_data, dict):
                custom_data = {}

            line = lines_by_id.setdefault(
                line_key,
                {
                    'contract_names': set(),
                    'invoice_id': result['invoice_id'],
                    'line_id': result['id'],
                    'quantity': custom_data.get('quantity'),
                },
            )
            line['contract_names'].add(result['invoice__contracts__name'])

        rows = []
        for line in lines_by_id.values():
            rows.append({
                **line,
                'contract_name': '、'.join(sorted(line.pop('contract_names'))),
            })
        rows.sort(
            key=lambda row: (
                str(row['contract_name']),
                row['invoice_id'],
                row['line_id'],
            )
        )

        contract_count = len(contract_ids)
        quantity_total = Decimal('0')
        invalid_quantity_count = 0
        for row in rows:
            row['parsed_quantity'] = parse_quantity(row['quantity'])
            if row['parsed_quantity'] is None:
                invalid_quantity_count += 1
            else:
                quantity_total += row['parsed_quantity']

        output = [
            '=== 代维-日常合同线路维护数量统计 ===',
            '',
            f'符合条件的合同数量: {contract_count}',
            f'符合条件的付款模板明细数量: {len(rows)}',
            f'有效数量合计: {format_decimal(quantity_total)}',
            f'数量无效的明细数量: {invalid_quantity_count}',
            '',
        ]

        if not rows:
            output.append('未找到符合条件的付款模板明细。')
            append_zero_result_diagnostics(output, contract_type)
            return '\n'.join(output)

        output.extend([
            '| 序号 | 合同名称 | 数量 |',
            '|---:|---|---:|',
        ])
        for index, row in enumerate(rows, start=1):
            quantity_text = (
                format_decimal(row['parsed_quantity'])
                if row['parsed_quantity'] is not None
                else '无效'
            )
            output.append(
                f"| {index} | {escape_markdown_cell(row['contract_name'])} | {quantity_text} |"
            )

        return '\n'.join(output)
