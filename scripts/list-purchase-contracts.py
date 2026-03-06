from django.contrib.auth import get_user_model
from django.db.models import Q

from extras.scripts import ObjectVar, Script, StringVar

from netbox_contract.models import Contract, ContractType, Invoice

User = get_user_model()

name = '外购合同列表脚本'


class list_purchase_contracts(Script):
    class Meta:
        name = '合同付款截止日期列表'
        description = (
            '列出合同的名称、编号、外购参与方、当前支付截止日期（取最新发票的 period_end），'
            '按截止日期倒序排列。可按合同类型、内部参与方、履约主管筛选，留空则不过滤。'
        )
        commit_default = False

    contract_type = ObjectVar(
        model=ContractType,
        label='合同类型',
        description='按合同类型筛选，留空则列出所有类型的合同',
        required=False,
    )

    internal_party = StringVar(
        label='内部参与方',
        description='按内部参与方筛选（支持模糊匹配），留空则不过滤',
        required=False,
    )

    compliance_manager = StringVar(
        label='履约主管用户名',
        description='按履约主管筛选（输入用户名，支持模糊匹配），留空则不过滤',
        required=False,
    )

    def run(self, data, commit):
        output = []

        # 构建筛选条件
        qs = Contract.objects.select_related('external_party_object_type')

        # 1. 合同类型筛选
        selected_type = data.get('contract_type')
        if selected_type:
            qs = qs.filter(contract_type=selected_type)
            type_label = str(selected_type)
        else:
            type_label = '全部'

        # 2. 内部参与方筛选（模糊匹配）
        internal_party_input = (data.get('internal_party') or '').strip()
        if internal_party_input:
            qs = qs.filter(internal_party__icontains=internal_party_input)
            party_label = internal_party_input
        else:
            party_label = '全部'

        # 3. 履约主管筛选（按用户名模糊匹配）
        manager_username = (data.get('compliance_manager') or '').strip()
        selected_manager_label = None
        if manager_username:
            matched_users = User.objects.filter(username__icontains=manager_username)
            if not matched_users.exists():
                self.log_warning(f'未找到用户名包含 "{manager_username}" 的用户，将不过滤履约主管')
            else:
                qs = qs.filter(compliance_manager__in=matched_users)
                selected_manager_label = ', '.join(str(u) for u in matched_users)
        manager_label = selected_manager_label or '全部'

        contracts = qs

        # 为每个合同找出最新的付款发票的 period_end（即当前支付截止日期）
        contract_data = []
        for contract in contracts:
            # 取 period_end 最大的非模板发票作为当前支付截止日期
            latest_invoice = (
                Invoice.objects.filter(contracts=contract, template=False)
                .exclude(period_end__isnull=True)
                .order_by('-period_end')
                .first()
            )
            payment_end_date = latest_invoice.period_end if latest_invoice else None

            # 获取外购参与方名称
            external_party = contract.external_party_object
            external_party_name = str(external_party) if external_party else '（未设置）'

            contract_data.append({
                'name': contract.name,
                'number': contract.number or '（未填写）',
                'external_party': external_party_name,
                'payment_end_date': payment_end_date,
            })

        # 按当前支付截止日期倒序排列（无付款记录的合同排在最后）
        with_date = sorted(
            [c for c in contract_data if c['payment_end_date'] is not None],
            key=lambda x: x['payment_end_date'],
            reverse=True,
        )
        without_date = [c for c in contract_data if c['payment_end_date'] is None]
        contract_data = with_date + without_date

        # 输出标题（显示当前所有筛选条件）
        output.append(
            f'=== 合同付款截止日期列表 '
            f'[类型: {type_label} | 内部参与方: {party_label} | 履约主管: {manager_label}] '
            f'共 {len(contract_data)} 份合同 ==='
        )
        output.append('')

        if not contract_data:
            output.append('未找到符合筛选条件的合同。')
            return '\n'.join(output)

        # 输出 Markdown 表格
        output.append('| 序号 | 合同名称 | 合同编号 | 外购参与方 | 当前支付截止日期 |')
        output.append('|------|----------|----------|------------|------------------|')

        for idx, item in enumerate(contract_data, start=1):
            date_str = str(item['payment_end_date']) if item['payment_end_date'] else '（无付款记录）'
            output.append(
                f"| {idx} | {item['name']} | {item['number']} | {item['external_party']} | {date_str} |"
            )

        output.append('')

        # CSV 格式
        output.append('=== CSV 格式 ===')
        output.append('')
        output.append('序号,合同名称,合同编号,外购参与方,当前支付截止日期')
        for idx, item in enumerate(contract_data, start=1):
            date_str = str(item['payment_end_date']) if item['payment_end_date'] else ''
            name_escaped = f'"{item["name"]}"' if ',' in item['name'] else item['name']
            party_escaped = f'"{item["external_party"]}"' if ',' in item['external_party'] else item['external_party']
            output.append(
                f"{idx},{name_escaped},{item['number']},{party_escaped},{date_str}"
            )

        return '\n'.join(output)
