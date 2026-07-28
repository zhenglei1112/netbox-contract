from django.conf import settings
from django.utils.translation import gettext_lazy as _
from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem

plugin_settings = settings.PLUGINS_CONFIG['netbox_contract']

contract_buttons = [
    PluginMenuButton(
        link='plugins:netbox_contract:contract_add',
        title=_("新增"),
        icon_class='mdi mdi-plus-thick',
        permissions=['netbox_contract.add_contract'],
    )
]

contracttype_buttons = [
    PluginMenuButton(
        link='plugins:netbox_contract:contracttype_add',
        title=_("新增"),
        icon_class='mdi mdi-plus-thick',
        permissions=['netbox_contract.add_contract'],
    )
]

invoice_buttons = [
    PluginMenuButton(
        link='plugins:netbox_contract:invoice_add',
        title=_("新增"),
        icon_class='mdi mdi-plus-thick',
        permissions=['netbox_contract.add_invoice'],
    )
]

invoiceline_buttons = [
    PluginMenuButton(
        link='plugins:netbox_contract:invoiceline_add',
        title=_("新增"),
        icon_class='mdi mdi-plus-thick',
        permissions=['netbox_contract.add_invoice'],
    )
]

accountingdimension_buttons = [
    PluginMenuButton(
        link='plugins:netbox_contract:accountingdimension_add',
        title=_("新增"),
        icon_class='mdi mdi-plus-thick',
        permissions=['netbox_contract.add_invoice'],
    )
]

serviceprovider_buttons = [
    PluginMenuButton(
        link='plugins:netbox_contract:serviceprovider_add',
        title=_("新增"),
        icon_class='mdi mdi-plus-thick',
        permissions=['netbox_contract.add_serviceprovider'],
    )
]

contract_menu_item = PluginMenuItem(
    link='plugins:netbox_contract:contract_list',
    link_text=_("外购合同"),
    buttons=contract_buttons,
    permissions=['netbox_contract.view_contract'],
)

contracttype_menu_item = PluginMenuItem(
    link='plugins:netbox_contract:contracttype_list',
    link_text=_("合同分类"),
    buttons=contracttype_buttons,
    permissions=['netbox_contract.view_contract'],
)

invoices_menu_item = PluginMenuItem(
    link='plugins:netbox_contract:invoice_list',
    link_text=_("付款"),
    buttons=invoice_buttons,
    permissions=['netbox_contract.view_invoice'],
)

invoicelines_menu_item = PluginMenuItem(
    link='plugins:netbox_contract:invoiceline_list',
    link_text=_("付款明细"),
    buttons=invoiceline_buttons,
    permissions=['netbox_contract.view_invoice'],
)

accounting_dimensions_menu_item = PluginMenuItem(
    link='plugins:netbox_contract:accountingdimension_list',
    link_text=_("统计维度"),
    buttons=accountingdimension_buttons,
    permissions=['netbox_contract.view_invoice'],
)

service_provider_menu_item = PluginMenuItem(
    link='plugins:netbox_contract:serviceprovider_list',
    link_text=_("服务提供商"),
    buttons=serviceprovider_buttons,
    permissions=['netbox_contract.view_serviceprovider'],
)

contract_assignemnt_menu_item = PluginMenuItem(
    link='plugins:netbox_contract:contractassignment_list',
    link_text=_("合同内容"),
    permissions=['netbox_contract.view_contractassignment'],
)

external_contract_items = (
    contract_menu_item,
    contracttype_menu_item,
    invoices_menu_item,
    invoicelines_menu_item,
    accounting_dimensions_menu_item,
    service_provider_menu_item,
    contract_assignemnt_menu_item,
)

_revenue_menu_specs = (
    ('revenuecustomer', _("客户")),
    ('revenueproject', _("项目")),
    ('revenuecontract', _("收入合同")),
    ('revenueorder', _("订单/开工单")),
    ('revenuecontractversion', _("合同版本")),
    ('revenuecontractline', _("合同项")),
    ('revenuebillingrule', _("计费规则")),
    ('revenuetriggerrecord', _("触发记录")),
    ('revenueadjustmentrecord', _("调整记录")),
    ('revenuereceivablebill', _("应收账单")),
    ('revenuereceivableline', _("应收明细")),
    ('revenueinvoice', _("发票")),
    ('revenueinvoiceline', _("发票明细")),
    ('revenueinvoicemapping', _("发票映射")),
    ('revenuereceipt', _("回款")),
    ('revenuereceiptallocation', _("回款分配")),
    ('revenuesynclog', _("同步日志")),
)

revenue_contract_items = tuple(
    PluginMenuItem(
        link=f'plugins:netbox_contract:{_model_name}_list',
        link_text=_label,
        buttons=[
            PluginMenuButton(
                link=f'plugins:netbox_contract:{_model_name}_add',
                title=_("新增"),
                icon_class='mdi mdi-plus-thick',
                permissions=[f'netbox_contract.add_{_model_name}'],
            )
        ],
        permissions=[f'netbox_contract.view_{_model_name}'],
    )
    for _model_name, _label in _revenue_menu_specs
)

revenue_overview_menu_item = PluginMenuItem(
    link='plugins:netbox_contract:revenuereceivable_overview',
    link_text=_("应收总览"),
    permissions=['netbox_contract.view_revenuecontract'],
)

revenue_contract_items = (revenue_overview_menu_item,) + revenue_contract_items
if plugin_settings.get('top_level_menu'):
    menu = PluginMenu(
        label=_("合同管理"),
        groups=(
            (_("外购合同"), external_contract_items),
            (_("收入合同"), revenue_contract_items),
        ),
        icon_class='mdi mdi-file-sign',
    )
else:
    menu_items = external_contract_items + revenue_contract_items
