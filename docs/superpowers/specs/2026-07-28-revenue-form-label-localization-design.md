# 收入模型编辑页标签中文化设计

## 背景

全量检查 21 个收入模型表单后，发现大部分业务字段已经通过
`_apply_revenue_verbose_names()` 显示为中文，但仍有 7 个业务字段沿用
Django 自动生成的英文名称。NetBox 注入的 `changelog_message` 字段也在
所有收入编辑页显示为 `Changelog message`。

## 目标

将收入模型编辑页中发现的英文标签统一改为中文，同时保持现有字段顺序、
数据结构、校验、保存和权限行为不变。

## 中文名称

| 模型 | 字段 | 当前标签 | 中文标签 |
| --- | --- | --- | --- |
| RevenueBillingRule | `trigger_offset_days` | Trigger offset days | 触发后天数 |
| RevenueTriggerRecord | `billing_rule` | Billing rule | 计费规则 |
| RevenueReceivableLine | `receivable_plan` | Receivable plan | 应收计划 |
| RevenueReceivableLine | `receivable_date` | Receivable date | 应收日期 |
| RevenueReceivableLine | `due_date` | Due date | 到期日期 |
| RevenueReceiptAllocation | `receipt` | Receipt | 回款 |
| RevenueReceiptAllocation | `receivable_line` | Receivable line | 应收明细 |
| 全部收入模型表单 | `changelog_message` | Changelog message | 变更说明 |

`EIP`、`ID` 等业务缩写保持不变，不属于本次英文标签修正范围。

## 设计

### 业务字段

在 `netbox_contract/models.py` 的 `_apply_revenue_verbose_names()` 中补充
缺失的 7 个字段映射。继续沿用当前项目的运行时中文标签模式，避免仅为
显示名称产生数据库迁移。

### NetBox 框架字段

在 `netbox_contract/forms.py` 增加收入模型专用公共表单基类，继承
`NetBoxModelForm`。公共基类调用 NetBox 初始化逻辑后，若表单包含
`changelog_message`，仅将该字段对象的 `label` 设置为“变更说明”。

动态生成的收入模型表单、`RevenueOrderForm` 和
`RevenueContractLineForm` 统一继承该公共基类。非收入模型表单继续
直接继承原有基类，不受本次调整影响。

公共基类不移动字段，因此页面顺序仍为：

`业务字段 → 标签 → 变更说明`

## 数据与错误处理

本改动只调整运行时展示标签，不改变字段名称、提交参数或数据库结构。
若未来某个收入表单不包含 `changelog_message`，公共逻辑直接跳过，
不抛出异常。

## 测试与验收

自动化测试应验证：

- 7 个业务字段的运行时 `verbose_name` 等于设计中的中文名称。
- 全部收入模型表单中的 `changelog_message` 标签均为“变更说明”。
- 动态表单、订单表单和合同项表单均使用公共收入表单基类。
- `tags` 仍位于 `changelog_message` 之前。
- 非收入模型表单不继承公共收入表单基类。
- `makemigrations --check --dry-run` 不产生迁移。

远端页面检查应覆盖全部 21 个收入模型。对于有数据的模型检查编辑页；
对于无数据的模型检查新增页。每个页面应正常渲染，原始
`Custom field data` 保持隐藏，表格列出的英文标签不再出现。
