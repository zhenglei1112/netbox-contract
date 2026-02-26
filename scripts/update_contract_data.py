import re

from django.contrib.auth import get_user_model
from extras.scripts import ObjectVar, Script

from netbox_contract.models import Contract

User = get_user_model()

class MigrateContractData(Script):
    class Meta:
        name = "迁移合同历史数据"
        description = "将自定义字段 (ContractNumber, ComplianceManager) 数据迁移至核心基本字段中，并清理合同名称不规范的格式。"

    def run(self, data, commit):
        contracts = Contract.objects.all()
        migrated_count = 0
        cleaned_name_count = 0

        for contract in contracts:
            changed = False
            
            # --- 1) 迁移履约主管 (ComplianceManager) ---
            cf_manager_id = contract.custom_field_data.get('ComplianceManager')
            if cf_manager_id and not contract.compliance_manager_id:
                try:
                    cf_manager_id = int(cf_manager_id)
                    user_exists = User.objects.filter(id=cf_manager_id).exists()
                    if user_exists:
                        contract.compliance_manager_id = cf_manager_id
                        self.log_info(f"合同 ID {contract.pk}: 已将履约主管迁移匹配至用户 ID {cf_manager_id}")
                        changed = True
                    else:
                        self.log_warning(f"合同 ID {contract.pk}: 数据库中未找到 ID 为 {cf_manager_id} 的履约主管用户。")
                except ValueError:
                    self.log_warning(f"合同 ID {contract.pk}: 履约主管的自定义值 '{cf_manager_id}' 不是有效的数字 ID，已跳过。")

            # --- 2) 迁移合同编号 (Contract Number) ---
            cf_number = contract.custom_field_data.get('ContractNumber')
            if cf_number and not contract.number:
                contract.number = str(cf_number).strip()
                self.log_info(f"合同 ID {contract.pk}: 已将原始自定义合同编号迁移为 '{contract.number}'")
                changed = True

            # --- 3) 清洗合同名称 (Contract Name) 中附带的编号与横杠 ---
            if contract.number and contract.name.endswith(contract.number):
                # 截去末尾精确的编号内容
                new_name = contract.name[:-len(contract.number)]
                
                # 去除残余的连字符 (如 '-') 以及空格
                new_name = new_name.rstrip(' -')
                
                if new_name and new_name != contract.name:
                    self.log_info(f"合同 ID {contract.pk}: 名称已清洗 '{contract.name}' -> '{new_name}'")
                    contract.name = new_name
                    changed = True
                    cleaned_name_count += 1

            if changed:
                contract.save()
                migrated_count += 1

        self.log_success(f"执行完毕！共更新了 {migrated_count} 份合同数据，清洗了 {cleaned_name_count} 个不规范的合同名称。")
