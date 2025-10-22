from circuits.models import Circuit, VirtualCircuit
from dcim.models import Device, Site
from django.contrib.contenttypes.models import ContentType
from netbox.plugins import PluginTemplateExtension
from tenancy.models import TenantGroup
from virtualization.models import VirtualMachine

from . import tables
from .models import ContractAssignment
from .models import Contract


class TenantContract(PluginTemplateExtension):
    models = ['tenancy.tenant']

    def full_width_page(self):
        current_tenant = self.context['object']
        
        # 获取通过原始租户字段关联的合同
        contracts_by_tenant = Contract.objects.filter(
            tenant=current_tenant        
        )
        
        # 获取通过自定义字段"Project"关联的合同
        # 自定义字段存储在custom_field_data中，多对象类型字段存储为对象ID列表
        # 使用has_key检查字段是否存在，避免KeyError
        contracts_by_Project = Contract.objects.filter(
            custom_field_data__has_key='Project'
        ).filter(
            custom_field_data__Project__contains=[current_tenant.id]
        )
        
        # 合并两个查询集并去重
        all_contracts = (contracts_by_tenant | contracts_by_Project).distinct()
        
        contracts_table = tables.ContractListTable(all_contracts)
        contracts_table.configure(self.context['request'])
 
        return self.render(
            'contract_list_bottom.html',
            extra_context={'contracts_table': contracts_table}
        )



class CircuitContractAssignments(PluginTemplateExtension):
    models = ['circuits.circuit']

    def full_width_page(self):
        circuit = self.context['object']
        circuit_type = ContentType.objects.get_for_model(Circuit)
        contract_assignments = ContractAssignment.objects.filter(
            content_type__pk=circuit_type.id, object_id=circuit.id
        )
        assignments_table = tables.ContractAssignmentObjectTable(contract_assignments)
        assignments_table.configure(self.context['request'])

        return self.render(
            'contract_assignments_bottom.html',
            extra_context={
                'assignments_table': assignments_table,
            },
        )


class DeviceContractAssignments(PluginTemplateExtension):
    models = ['dcim.device']

    def full_width_page(self):
        device = self.context['object']
        device_type = ContentType.objects.get_for_model(Device)
        contract_assignments = ContractAssignment.objects.filter(
            content_type__pk=device_type.id, object_id=device.id
        )
        assignments_table = tables.ContractAssignmentObjectTable(contract_assignments)
        assignments_table.configure(self.context['request'])

        return self.render(
            'contract_assignments_bottom.html',
            extra_context={
                'assignments_table': assignments_table,
            },
        )


class VMContractAssignments(PluginTemplateExtension):
    models = ['virtualization.virtualmachine']

    def full_width_page(self):
        vm = self.context['object']
        vm_type = ContentType.objects.get_for_model(VirtualMachine)
        contract_assignments = ContractAssignment.objects.filter(
            content_type__pk=vm_type.id, object_id=vm.id
        )
        assignments_table = tables.ContractAssignmentObjectTable(contract_assignments)
        assignments_table.configure(self.context['request'])

        return self.render(
            'contract_assignments_bottom.html',
            extra_context={
                'assignments_table': assignments_table,
            },
        )


class SiteContractAssignments(PluginTemplateExtension):
    models = ['dcim.site']

    def full_width_page(self):
        site = self.context['object']
        site_type = ContentType.objects.get_for_model(Site)
        contract_assignments = ContractAssignment.objects.filter(
            content_type__pk=site_type.id, object_id=site.id
        )
        assignments_table = tables.ContractAssignmentObjectTable(contract_assignments)
        assignments_table.configure(self.context['request'])

        return self.render(
            'contract_assignments_bottom.html',
            extra_context={
                'assignments_table': assignments_table,
            },
        )


class VirtualCircuitContractAssignments(PluginTemplateExtension):
    models = ['circuits.virtualcircuit']

    def full_width_page(self):
        virtualcircuit = self.context['object']
        virtualcircuit_type = ContentType.objects.get_for_model(VirtualCircuit)
        contract_assignments = ContractAssignment.objects.filter(
            content_type__pk=virtualcircuit_type.id, object_id=virtualcircuit.id
        )

        assignments_table = tables.ContractAssignmentObjectTable(contract_assignments)
        assignments_table.configure(self.context['request'])

        return self.render(
            'contract_assignments_bottom.html',
            extra_context={
                'assignments_table': assignments_table,
            },
        )


class TenantGroupContract(PluginTemplateExtension):
    models = ['tenancy.tenantgroup']

    def full_width_page(self):
        current_tenantgroup = self.context['object']
        
        # 获取通过自定义字段"Customer"关联的合同
        # 自定义字段存储在custom_field_data中，多对象类型字段存储为对象ID列表
        # 使用has_key检查字段是否存在，避免KeyError
        contracts_by_Customer = Contract.objects.filter(
            custom_field_data__has_key='Customer'
        ).filter(
            custom_field_data__Customer__contains=[current_tenantgroup.id]
        )
        
        contracts_table = tables.ContractListTable(contracts_by_Customer)
        contracts_table.configure(self.context['request'])
 
        return self.render(
            'contract_list_bottom.html',
            extra_context={'contracts_table': contracts_table}
        )


template_extensions = [
    CircuitContractAssignments,
    DeviceContractAssignments,
    VMContractAssignments,
    SiteContractAssignments,
    VirtualCircuitContractAssignments,
    TenantContract,
    TenantGroupContract,
]
