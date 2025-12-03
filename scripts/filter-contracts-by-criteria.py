class filter_contracts_by_criteria(Script):
    class Meta:
        name = '筛选符合条件的合同并进行分组统计'
        description = '筛选类型为"外购资源"，具有发票模版的合同，并按统计维度分组求和，包含长周期数量和年价款计算'
        commit_default = False

    # 添加年份输入参数
    year = IntegerVar(
        label='统计年份',
        description='请输入要统计的年份（例如：2025）',
        required=True,
        default=date.today().year
    )

    def run(self, data, commit):
        output = []
        
        # 获取用户输入的统计年份
        target_year = data['year']
        output.append(f'=== 统计年份: {target_year} ===')
        output.append('')
        
        # 获取"外购资源"类型
        try:
            purchase_contract_type = ContractType.objects.get(name='外购资源')
        except ContractType.DoesNotExist:
            self.log_error('未找到"外购资源"合同类型，请先创建该类型')
            return '错误：未找到"外购资源"合同类型'

        # 根据输入的年份计算相关日期
        january_first = date(target_year, 1, 1)
        december_31 = date(target_year, 12, 31)

        # 获取所有外购资源类型的合同用于统计
        all_purchase_contracts = Contract.objects.filter(contract_type=purchase_contract_type)

        # 筛选符合条件的合同用于分组统计
        contracts_with_invoice_template = self.filter_eligible_contracts(purchase_contract_type, target_year, january_first, december_31)

        # 输出合同统计信息（在所有外购资源类型合同范围内统计）
        if all_purchase_contracts:
            self.output_contract_statistics(output, all_purchase_contracts, contracts_with_invoice_template, target_year, january_first, december_31)
            
            if contracts_with_invoice_template:
                # 进行分组统计计算
                output.append('=== 分组统计结果 ===')
                stats = self.calculate_group_statistics(contracts_with_invoice_template, target_year)
                output.extend(stats)
            else:
                output.append('未找到符合条件的合同用于分组统计')
        else:
            output.append('未找到外购资源类型的合同')

        return '\n'.join(output)

    def filter_eligible_contracts(self, contract_type, current_year, january_first, december_31):
        """筛选符合条件的合同"""
        contracts_with_invoice_template = []
        
        # 获取所有外购资源类型的合同
        contracts = Contract.objects.filter(contract_type=contract_type)
        
        for contract in contracts:
            # 检查该合同是否有template=True的发票
            has_template_invoice = Invoice.objects.filter(
                contracts=contract,
                template=True
            ).exists()
            
            # 获取合同状态和日期信息
            contract_status = contract.get_status_display()
            contract_start_date = contract.start_date
            contract_end_date = contract.end_date
            
            # 总体参与汇总条件：如果满足以下任一条件，则跳过该合同
            # 1. 开始日期在本年12月31日之后
            # 2. 合同状态为已结束且结束日期在本年1月1日之前
            if (contract_start_date and contract_start_date > december_31) or \
               (contract_status == '已结束' and contract_end_date and contract_end_date < january_first):
                continue
            
            if has_template_invoice:
                contracts_with_invoice_template.append(contract)
        
        return contracts_with_invoice_template

    def output_contract_statistics(self, output, all_contracts, eligible_contracts, current_year, january_first, december_31):
        """输出合同统计信息"""
        total_count = len(all_contracts)
        
        # 初始化统计变量
        short_term_count = 0
        short_term_start_after_dec31 = 0
        short_term_ended_before_jan1 = 0
        short_term_start_in_year = 0
        short_term_ended_in_year = 0
        
        long_term_count = 0
        long_term_start_after_dec31 = 0
        long_term_ended_before_jan1 = 0
        long_term_start_in_year = 0
        long_term_ended_in_year = 0
        
        pending_count = 0
        
        # 统计参与最终统计的合同数量
        eligible_short_term_count = 0
        eligible_long_term_count = 0
        eligible_total_count = len(eligible_contracts)
        
        for contract in all_contracts:
            contract_status = contract.get_status_display()
            contract_start_date = contract.start_date
            contract_end_date = contract.end_date
            payment_frequency = contract.invoice_frequency or 1
            
            # 判断合同类型
            if payment_frequency <= 12:
                # 短周期合同
                short_term_count += 1
                
                # 起始日期在本年12月31日之后
                if contract_start_date and contract_start_date > december_31:
                    short_term_start_after_dec31 += 1
                
                # 状态为已结束且结束日期在本年1月1日前
                if contract_status == '已结束' and contract_end_date and contract_end_date < january_first:
                    short_term_ended_before_jan1 += 1
                
                # 起始日期在本年内
                if contract_start_date and contract_start_date >= january_first and contract_start_date <= december_31:
                    short_term_start_in_year += 1
                
                # 状态为已结束且结束日期在本年内
                if contract_status == '已结束' and contract_end_date and contract_end_date >= january_first and contract_end_date <= december_31:
                    short_term_ended_in_year += 1
            else:
                # 长周期合同
                long_term_count += 1
                
                # 起始日期在本年12月31日之后
                if contract_start_date and contract_start_date > december_31:
                    long_term_start_after_dec31 += 1
                
                # 状态为已结束且结束日期在本年1月1日前
                if contract_status == '已结束' and contract_end_date and contract_end_date < january_first:
                    long_term_ended_before_jan1 += 1
                
                # 起始日期在本年内
                if contract_start_date and contract_start_date >= january_first and contract_start_date <= december_31:
                    long_term_start_in_year += 1
                
                # 状态为已结束且结束日期在本年内
                if contract_status == '已结束' and contract_end_date and contract_end_date >= january_first and contract_end_date <= december_31:
                    long_term_ended_in_year += 1
            
            # 状态为挂起的合同数量
            if contract_status == '挂起':
                pending_count += 1
        
        # 统计参与最终统计的合同数量
        for contract in eligible_contracts:
            payment_frequency = contract.invoice_frequency or 1
            if payment_frequency <= 12:
                eligible_short_term_count += 1
            else:
                eligible_long_term_count += 1
        
        output.append('=== 合同统计信息 ===')
        output.append(f'合同总数: {total_count}')
        output.append('')
        
        # 短周期合同统计
        output.append('短周期合同（周期≤12）:')
        output.append(f'  短周期合同数量: {short_term_count}')
        output.append(f'  起始日期在本年12月31日之后的数量: {short_term_start_after_dec31}')
        output.append(f'  状态为已结束且结束日期在本年1月1日前的数量: {short_term_ended_before_jan1}')
        output.append(f'  起始日期在本年内的数量: {short_term_start_in_year}')
        output.append(f'  状态为已结束且结束日期在本年内的数量: {short_term_ended_in_year}')
        output.append('')
        
        # 长周期合同统计
        output.append('长周期合同（周期>12）:')
        output.append(f'  长周期合同数量: {long_term_count}')
        output.append(f'  起始日期在本年12月31日之后的数量: {long_term_start_after_dec31}')
        output.append(f'  状态为已结束且结束日期在本年1月1日前的数量: {long_term_ended_before_jan1}')
        output.append(f'  起始日期在本年内的数量: {long_term_start_in_year}')
        output.append(f'  状态为已结束且结束日期在本年内的数量: {long_term_ended_in_year}')
        output.append('')
        
        # 挂起合同统计
        output.append(f'状态为挂起的合同数量: {pending_count}')
        output.append('')
        
        # 参与最终统计的合同数量
        output.append('参与最终统计的合同:')
        output.append(f'  参与最终统计的短周期合同数量: {eligible_short_term_count}')
        output.append(f'  参与最终统计的长周期合同数量: {eligible_long_term_count}')
        output.append(f'  参与最终统计的合同总数量: {eligible_total_count}')
        output.append('')

    def calculate_group_statistics(self, contracts, current_year):
        """计算分组统计数据"""
        output = []
        
        # 定义统计维度名称
        dimension_names = ['带宽', '机位', '机房', '机柜', '管道', '纤芯']
        
        # 初始化统计字典
        dimension_stats = self.initialize_dimension_stats()
        
        # 获取当前年份相关日期
        january_first_current = date(current_year, 1, 1)
        december_31 = date(current_year, 12, 31)
        
        # 遍历所有合同进行统计
        for contract in contracts:
            customer_group = self.get_customer_group(contract.custom_field_data.get('Customer', ''))
            
            # 获取该合同的所有发票模板
            template_invoices = Invoice.objects.filter(
                contracts=contract,
                template=True
            )
            
            for invoice in template_invoices:
                for line in invoice.invoicelines.all():
                    self.process_invoice_line(line, contract, customer_group, dimension_stats, 
                                            dimension_names, current_year, january_first_current, december_31)
        
        # 输出统计结果
        return self.output_statistics_results(output, dimension_stats, dimension_names, len(contracts))

    def initialize_dimension_stats(self):
        """初始化统计字典"""
        return defaultdict(lambda: defaultdict(lambda: {
            'total_quantity': 0,
            'total_monthly_subtotal': 0,
            'long_term_quantity': 0,
            'year_0_amount': 0,
            'year_1_amount': 0,
            'year_2_amount': 0,
            'contract_count': 0,
            'invoice_line_count': 0
        }))

    def process_invoice_line(self, line, contract, customer_group, dimension_stats, 
                           dimension_names, current_year, january_first_current, december_31):
        """处理发票明细项"""
        # 获取自定义字段数据
        custom_data = line.custom_field_data
        quantity = custom_data.get('quantity') or 0
        monthly_subtotal = custom_data.get('MonthlySubtotal') or 0
        
        # 计算月度小计累计值
        monthly_subtotal_accumulated = self.calculate_monthly_subtotal_accumulated(
            contract, monthly_subtotal, current_year, january_first_current, december_31
        )
        
        # 计算年价款
        year_0_amount, year_1_amount, year_2_amount = self.calculate_year_amounts(
            contract, monthly_subtotal, current_year
        )
        
        # 处理统计维度
        for dimension in line.accounting_dimensions.all():
            dimension_name = dimension.name
            if dimension_name in dimension_names:
                self.update_dimension_stats(
                    dimension_stats, dimension_name, customer_group,
                    quantity, monthly_subtotal_accumulated, year_0_amount, 
                    year_1_amount, year_2_amount, contract.invoice_frequency or 1
                )

    def calculate_monthly_subtotal_accumulated(self, contract, monthly_subtotal, current_year, january_first_current, december_31):
        """计算月度小计累计值"""
        contract_status = contract.get_status_display()
        contract_start_date = contract.start_date
        contract_end_date = contract.end_date
        
        if contract_status in ['已结束', '挂起']:
            if contract_end_date and contract_end_date < january_first_current:
                return 0
            else:
                if contract_end_date:
                    months_diff = self.calculate_months_diff(contract_end_date, january_first_current)
                    return months_diff * monthly_subtotal
                else:
                    return 12 * monthly_subtotal
        else:
            if contract_start_date and contract_start_date > january_first_current:
                months_diff = self.calculate_months_diff(december_31, contract_start_date)
                return months_diff * monthly_subtotal
            else:
                return 12 * monthly_subtotal

    def calculate_months_diff(self, end_date, start_date):
        """计算两个日期之间的月数（向上取整）"""
        days_diff = (end_date - start_date).days 
        if days_diff > 0:
            months_diff = (days_diff + 29) // 30  # 向上取整
        else:
            months_diff = 0
        return max(0, min(months_diff, 12))

    def calculate_year_amounts(self, contract, monthly_subtotal, current_year):
        """计算年价款"""
        year_0_amount = year_1_amount = year_2_amount = 0
        
        contract_start_date = contract.start_date
        payment_frequency = contract.invoice_frequency or 1
        
        if payment_frequency > 12 and contract_start_date:
            payment_dates = self.calculate_payment_dates(contract_start_date, payment_frequency, current_year)
            
            for payment_date in payment_dates:
                if payment_date.year == current_year:
                    year_0_amount += monthly_subtotal * payment_frequency
                elif payment_date.year == current_year + 1:
                    year_1_amount += monthly_subtotal * payment_frequency
                elif payment_date.year == current_year + 2:
                    year_2_amount += monthly_subtotal * payment_frequency
        
        return year_0_amount, year_1_amount, year_2_amount

    def calculate_payment_dates(self, start_date, payment_frequency, current_year):
        """计算付款日期"""
        payment_dates = []
        current_payment_date = start_date
        
        while current_payment_date.year <= current_year + 2:
            payment_dates.append(current_payment_date)
            try:
                from dateutil.relativedelta import relativedelta
                current_payment_date = current_payment_date + relativedelta(months=payment_frequency)
            except ImportError:
                year = current_payment_date.year
                month = current_payment_date.month + payment_frequency
                while month > 12:
                    year += 1
                    month -= 12
                current_payment_date = date(year, month, start_date.day)
            
            if current_payment_date.year > current_year + 2:
                break
        
        return payment_dates

    def update_dimension_stats(self, dimension_stats, dimension_name, customer_group,
                             quantity, monthly_subtotal_accumulated, year_0_amount, 
                             year_1_amount, year_2_amount, payment_frequency):
        """更新统计维度数据"""
        # 所有合同都参与总数量汇总
        dimension_stats[dimension_name][customer_group]['total_quantity'] += quantity
        
        # 根据付款周期判断其他统计逻辑
        if payment_frequency <= 12:
            dimension_stats[dimension_name][customer_group]['total_monthly_subtotal'] += monthly_subtotal_accumulated
        else:
            dimension_stats[dimension_name][customer_group]['long_term_quantity'] += quantity
        
        # 累加年价款
        dimension_stats[dimension_name][customer_group]['year_0_amount'] += year_0_amount
        dimension_stats[dimension_name][customer_group]['year_1_amount'] += year_1_amount
        dimension_stats[dimension_name][customer_group]['year_2_amount'] += year_2_amount
        
        dimension_stats[dimension_name][customer_group]['contract_count'] += 1
        dimension_stats[dimension_name][customer_group]['invoice_line_count'] += 1

    def output_statistics_results(self, output, dimension_stats, dimension_names, total_contracts):
        """输出统计结果"""
        found_data = False
        global_total_monthly_subtotal = 0
        global_year_0_amount = 0
        global_year_1_amount = 0
        global_year_2_amount = 0
        
        # 先输出CSV格式
        output.append('=== CSV格式输出 ===')
        output.append('')
        
        for dimension_name, customer_groups in dimension_stats.items():
            dimension_found = False
            
            for customer_group, stats in customer_groups.items():
                if stats['invoice_line_count'] > 0:
                    found_data = True
                    dimension_found = True
            
            if dimension_found:
                output.append(f'{dimension_name} 维度统计')
                output.append('')
                
                # 构建CSV格式
                csv_rows = []
                csv_rows.append('分组,合同数量,总数量,长周期数量,年合同价款,+0年价款,+1年价款,+2年价款')
                
                # 计算维度总计
                dimension_total_quantity = sum(stats['total_quantity'] for stats in customer_groups.values())
                dimension_total_monthly_subtotal = sum(stats['total_monthly_subtotal'] for stats in customer_groups.values())
                dimension_long_term_quantity = sum(stats['long_term_quantity'] for stats in customer_groups.values())
                dimension_year_0_amount = sum(stats['year_0_amount'] for stats in customer_groups.values())
                dimension_year_1_amount = sum(stats['year_1_amount'] for stats in customer_groups.values())
                dimension_year_2_amount = sum(stats['year_2_amount'] for stats in customer_groups.values())
                dimension_total_contracts = sum(stats['contract_count'] for stats in customer_groups.values())
                
                # 累加到全局总计
                global_total_monthly_subtotal += dimension_total_monthly_subtotal
                global_year_0_amount += dimension_year_0_amount
                global_year_1_amount += dimension_year_1_amount
                global_year_2_amount += dimension_year_2_amount
                
                # 总计行
                csv_rows.append(f'小计,{dimension_total_contracts},{dimension_total_quantity:.2f},{dimension_long_term_quantity:.2f},{dimension_total_monthly_subtotal:.2f},{dimension_year_0_amount:.2f},{dimension_year_1_amount:.2f},{dimension_year_2_amount:.2f}')
                
                # 按Customer分组输出
                for customer_group in ['公司自用', '客户专用', '混合使用']:
                    if customer_group in customer_groups and customer_groups[customer_group]['invoice_line_count'] > 0:
                        stats = customer_groups[customer_group]
                        csv_rows.append(f'{customer_group},{stats["contract_count"]},{stats["total_quantity"]:.2f},{stats["long_term_quantity"]:.2f},{stats["total_monthly_subtotal"]:.2f},{stats["year_0_amount"]:.2f},{stats["year_1_amount"]:.2f},{stats["year_2_amount"]:.2f}')
                    else:
                        csv_rows.append(f'{customer_group},0,0.00,0.00,0.00,0.00,0.00,0.00')
                
                output.extend(csv_rows)
                output.append('')
        
        # 输出全局总计（CSV格式）
        if found_data:
            output.append('全局总计')
            output.append('')
            output.append('统计项,合同数量,年合同价款,+0年价款,+1年价款,+2年价款')
            output.append(f'总计,{total_contracts},{global_total_monthly_subtotal:.2f},{global_year_0_amount:.2f},{global_year_1_amount:.2f},{global_year_2_amount:.2f}')
            output.append('')
        
        # 再输出Markdown格式
        output.append('=== Markdown表格格式输出 ===')
        output.append('')
        
        for dimension_name, customer_groups in dimension_stats.items():
            dimension_found = False
            
            for customer_group, stats in customer_groups.items():
                if stats['invoice_line_count'] > 0:
                    dimension_found = True
            
            if dimension_found:
                output.append(f'#### {dimension_name} 维度统计')
                output.append('')
                
                # 构建Markdown表格格式
                md_rows = []
                md_rows.append('| 分组 | 合同数量 | 总数量 | 长周期数量 | 年合同价款 | +0年价款 | +1年价款 | +2年价款 |')
                md_rows.append('|------|----------|--------|------------|------------|----------|----------|----------|')
                
                # 计算维度总计
                dimension_total_quantity = sum(stats['total_quantity'] for stats in customer_groups.values())
                dimension_total_monthly_subtotal = sum(stats['total_monthly_subtotal'] for stats in customer_groups.values())
                dimension_long_term_quantity = sum(stats['long_term_quantity'] for stats in customer_groups.values())
                dimension_year_0_amount = sum(stats['year_0_amount'] for stats in customer_groups.values())
                dimension_year_1_amount = sum(stats['year_1_amount'] for stats in customer_groups.values())
                dimension_year_2_amount = sum(stats['year_2_amount'] for stats in customer_groups.values())
                dimension_total_contracts = sum(stats['contract_count'] for stats in customer_groups.values())
                
                # 总计行
                md_rows.append(f'| **小计** | {dimension_total_contracts} | {dimension_total_quantity:.2f} | {dimension_long_term_quantity:.2f} | {dimension_total_monthly_subtotal:.2f} | {dimension_year_0_amount:.2f} | {dimension_year_1_amount:.2f} | {dimension_year_2_amount:.2f} |')
                
                # 按Customer分组输出
                for customer_group in ['公司自用', '客户专用', '混合使用']:
                    if customer_group in customer_groups and customer_groups[customer_group]['invoice_line_count'] > 0:
                        stats = customer_groups[customer_group]
                        md_rows.append(f'| {customer_group} | {stats["contract_count"]} | {stats["total_quantity"]:.2f} | {stats["long_term_quantity"]:.2f} | {stats["total_monthly_subtotal"]:.2f} | {stats["year_0_amount"]:.2f} | {stats["year_1_amount"]:.2f} | {stats["year_2_amount"]:.2f} |')
                    else:
                        md_rows.append(f'| {customer_group} | 0 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |')
                
                output.extend(md_rows)
                output.append('')
        
        # 输出全局总计（Markdown格式）
        if found_data:
            output.append('#### 全局总计')
            output.append('')
            output.append('| 统计项 | 合同数量 | 年合同价款 | +0年价款 | +1年价款 | +2年价款 |')
            output.append('|--------|----------|------------|----------|----------|----------|')
            output.append(f'| **总计** | {total_contracts} | {global_total_monthly_subtotal:.2f} | {global_year_0_amount:.2f} | {global_year_1_amount:.2f} | {global_year_2_amount:.2f} |')
            output.append('')
        
        if not found_data:
            output.append('未找到包含统计维度数据的付款明细项')
            output.append('请检查以下内容：')
            output.append('1. 确保付款明细项关联了统计维度（Accounting Dimensions）')
            output.append('2. 统计维度名称应为: 带宽, 机位, 机房, 机柜, 管道, 纤芯')
            output.append('3. 确保付款明细项设置了 quantity 和 MonthlySubtotal 自定义字段')
            output.append('4. 确保合同设置了 Customer 自定义字段')
        
        return output

    def get_customer_group(self, customer_value):
        """根据Customer字段值确定分组"""
        if not customer_value:
            return '客户专用'
        
        from tenancy.models import TenantGroup
        
        if isinstance(customer_value, list):
            customer_names = []
            for tenantgroup_id in customer_value:
                try:
                    tenantgroup = TenantGroup.objects.get(id=tenantgroup_id)
                    customer_names.append(tenantgroup.name)
                except TenantGroup.DoesNotExist:
                    continue
            
            if not customer_names:
                return '客户专用'
            elif len(customer_names) == 1 and customer_names[0] == '中交信通':
                return '公司自用'
            elif any('中交信通' in name for name in customer_names):
                return '混合使用'
            else:
                return '客户专用'
        else:
            return '客户专用'