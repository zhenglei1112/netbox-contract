from extras.scripts import Script
from netbox_contract.models import Contract, ContractType, Invoice, InvoiceLine
from django.contrib.auth import get_user_model
from collections import defaultdict
from extras.models import Notification
from django.contrib.contenttypes.models import ContentType
try:
    from core.models import Job
except ImportError:
    from extras.models import Job

# 获取Netbox使用的用户模型
User = get_user_model()

name = '合同数据质量检查脚本'

class check_contract_data_quality(Script):
    class Meta:
        name = '合同数据质量检查'
        description = '检查外购资源类型合同的数据质量问题，包括付款模板、费用字段、明细项字段等'
        commit_default = False

    def run(self, data, commit):
        output = []
        
        # 获取"外购资源"类型
        try:
            purchase_contract_type = ContractType.objects.get(name='外购资源')
        except ContractType.DoesNotExist:
            self.log_error('未找到"外购资源"合同类型，请先创建该类型')
            return '错误：未找到"外购资源"合同类型'

        # 获取所有外购资源类型的合同
        contracts = Contract.objects.filter(contract_type=purchase_contract_type)
        
        output.append(f'=== 合同数据质量检查报告 ===')
        output.append(f'检查范围: 合同类型为"外购资源"的所有合同')
        output.append(f'检查合同总数: {len(contracts)}')
        output.append('')
        
        # 初始化问题统计
        issue_stats = defaultdict(int)
        contracts_with_issues = []
        
        # 按履约主管分组存储有问题的合同
        compliance_manager_groups = defaultdict(list)
        
        # 检查每个合同
        for contract in contracts:
            contract_issues = []
            contract_custom_data = contract.custom_field_data
            
            # 1. 检查合同是否具有付款模板
            has_template_invoice = Invoice.objects.filter(
                contracts=contract,
                template=True
            ).exists()
            
            if not has_template_invoice:
                contract_issues.append('1. 合同不具有付款模板')
                issue_stats['无付款模板'] += 1
            
            # 2. 检查合同未填写月费用字段 (MRC是合同的标准字段)
            mrc_value = contract.mrc
            if mrc_value is None or mrc_value == 0:
                contract_issues.append('2. 合同未填写月费用字段')
                issue_stats['未填月费用'] += 1
            
            # 3. 检查合同填写了年费用字段 (YRC是合同的标准字段)
            yrc_value = contract.yrc
            if yrc_value is not None and yrc_value != 0:
                contract_issues.append('3. 合同填写了年费用字段')
                issue_stats['填写年费用'] += 1
            
            # 如果有付款模板，检查付款模板明细项
            if has_template_invoice:
                template_invoices = Invoice.objects.filter(
                    contracts=contract,
                    template=True
                )
                
                for invoice in template_invoices:
                    invoice_lines = invoice.invoicelines.all()
                    
                    # 收集该发票所有明细的统计维度
                    invoice_dimensions = set()
                    for line in invoice_lines:
                        for d in line.accounting_dimensions.all():
                            invoice_dimensions.add(d.name)

                        line_custom_data = line.custom_field_data
                        
                        # 4. 检查付款模板明细中，自定义字段未全部填写
                        unitprice = line_custom_data.get('Unitprice', None)
                        quantity = line_custom_data.get('quantity', None)
                        monthly_subtotal = line_custom_data.get('MonthlySubtotal', None)
                        
                        missing_fields = []
                        if unitprice is None or unitprice == '':
                            missing_fields.append('月单价')
                        if quantity is None or quantity == '':
                            missing_fields.append('数量')
                        if monthly_subtotal is None or monthly_subtotal == '':
                            missing_fields.append('月小计')
                        
                        if missing_fields:
                            contract_issues.append(f'4. 付款模板明细中，字段未填写: {", ".join(missing_fields)}')
                            issue_stats['明细字段未填'] += 1
                        
                        # 5. 检查Unitprice*quantity不等于MonthlySubtotal
                        if (unitprice is not None and unitprice != '' and 
                            quantity is not None and quantity != '' and 
                            monthly_subtotal is not None and monthly_subtotal != ''):
                            
                            try:
                                unitprice_float = float(unitprice)
                                quantity_float = float(quantity)
                                monthly_subtotal_float = float(monthly_subtotal)
                                
                                calculated_subtotal = unitprice_float * quantity_float
                                
                                # 允许误差为2
                                tolerance = 2
                                if abs(calculated_subtotal - monthly_subtotal_float) > tolerance:
                                    contract_issues.append(f'5. 付款模板明细计算错误: 月单价({unitprice}) * 数量({quantity}) = {calculated_subtotal:.2f} ≠ 月小计({monthly_subtotal}) (允许误差: {tolerance:.4f})')
                                    issue_stats['明细计算错误'] += 1
                                
                            except (ValueError, TypeError):
                                contract_issues.append('5. 付款模板明细字段格式错误，无法计算')
                                issue_stats['字段格式错误'] += 1
                        
                        # 6. 检查付款模板明细中，金额不等于MonthlySubtotal*合同付款周期
                        if monthly_subtotal is not None and monthly_subtotal != '':
                            payment_frequency = contract.invoice_frequency or 1
                            
                            try:
                                monthly_subtotal_float = float(monthly_subtotal)
                                expected_amount = monthly_subtotal_float * payment_frequency
                                
                                # 检查付款模板明细的金额字段
                                line_amount = line.amount
                                if line_amount is not None and line_amount != '':
                                    try:
                                        line_amount_float = float(line_amount)
                                        
                                        # 允许误差为2
                                        tolerance = 2
                                        if abs(line_amount_float - expected_amount) > tolerance:
                                            contract_issues.append(f'6. 付款模板明细金额错误: 月小计({monthly_subtotal}) * 付款周期({payment_frequency}) = {expected_amount:.2f} ≠ 模板明细付款周期小计金额({line_amount}) (允许误差: {tolerance:.4f})')
                                            issue_stats['明细金额错误'] += 1
                                    except (ValueError, TypeError):
                                        contract_issues.append('6. 付款模板明细金额字段格式错误')
                                        issue_stats['明细金额格式错误'] += 1
                                
                            except (ValueError, TypeError):
                                contract_issues.append('6. 月小计字段格式错误，无法计算')
                                issue_stats['月小计格式错误'] += 1

                    # 7. 检查合同采购品目与付款模板明细项不一致 (针对整个发票检查)
                    contract_procurement_item = contract_custom_data.get('ProcurementItem')
                    
                    # 采购品目与统计维度映射关系
                    procurement_mapping = {
                        '管道租赁': '管道',
                        '光纤租赁': '纤芯',
                        '机房租赁': '机房',
                        '机柜租赁': '机柜',
                        '机位租赁': '机位',
                        '电路租赁': '带宽'
                    }
                    
                    # 统一处理为列表
                    items_to_check = []
                    if isinstance(contract_procurement_item, list):
                        items_to_check = contract_procurement_item
                    elif contract_procurement_item:
                        items_to_check = [contract_procurement_item]
                        
                    for item in items_to_check:
                        if item in procurement_mapping:
                            expected_dimension_name = procurement_mapping[item]
                            
                            if expected_dimension_name not in invoice_dimensions:
                                contract_issues.append(f'7. 采购品目不匹配: 合同包含"{item}"，但该合同的付款模板中未包含"{expected_dimension_name}"统计维度的明细项 (当前所有维度: {", ".join(invoice_dimensions) or "无"})')
                                issue_stats['采购品目不匹配'] += 1
            
            # 如果合同有问题，记录到输出
            if contract_issues:
                contracts_with_issues.append(contract)
                
                # 获取履约主管信息
                compliance_manager_id = contract_custom_data.get('ComplianceManager', None)
                compliance_manager_name = '未指定履约主管'
                
                if compliance_manager_id:
                    try:
                        compliance_manager = User.objects.get(id=compliance_manager_id)
                        compliance_manager_name = compliance_manager.username
                    except User.DoesNotExist:
                        compliance_manager_name = f'用户ID不存在: {compliance_manager_id}'
                
                # 按履约主管分组
                compliance_manager_groups[compliance_manager_name].append({
                    'contract': contract,
                    'issues': contract_issues
                })
        
        # 输出统计信息
        output.append('=== 问题统计 ===')
        if issue_stats:
            for issue_type, count in issue_stats.items():
                output.append(f'{issue_type}: {count} 个合同')
        else:
            output.append('未发现数据质量问题')
        
        output.append('')
        output.append(f'发现问题的合同总数: {len(contracts_with_issues)}')
        output.append(f'无问题的合同总数: {len(contracts) - len(contracts_with_issues)}')
        output.append('')
        
        # 按履约主管分组输出
        if compliance_manager_groups:
            output.append('=== 按履约主管分组统计 ===')
            output.append('')
            
            # 按履约主管名称排序
            sorted_managers = sorted(compliance_manager_groups.keys())
            
            for manager_name in sorted_managers:
                contracts_in_group = compliance_manager_groups[manager_name]
                output.append(f'履约主管: {manager_name}')
                output.append(f'问题合同数量: {len(contracts_in_group)}')
                output.append('')
                
                # 输出该履约主管名下的有问题的合同
                for contract_data in contracts_in_group:
                    contract = contract_data['contract']
                    contract_issues = contract_data['issues']
                    
                    output.append(f'--- 合同: {contract.name} (ID: {contract.id}) ---')
                    for issue in contract_issues:
                        output.append(f'  {issue}')
                    output.append('')
                

                output.append('')
        
        return '\n'.join(output)
