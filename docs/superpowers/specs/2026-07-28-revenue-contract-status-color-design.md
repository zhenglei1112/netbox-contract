# 收入合同状态颜色修复设计

## 背景

`RevenueContractStatusChoices` 已为收入合同的七种状态配置颜色，其中“生效”对应绿色。但 `RevenueContractListTable` 使用 NetBox 的 `ChoiceFieldColumn` 渲染状态徽标，而 `RevenueContract` 没有提供 `get_status_color()`。NetBox 因此回退到默认 `secondary`，导致“生效”显示为灰色。

## 目标

- 收入合同状态徽标按 `RevenueContractStatusChoices` 中的颜色配置渲染。
- “生效”显示为绿色。
- 保持七种状态及其数据库值不变。
- 不通过模板或表格列硬编码颜色。

## 方案

在 `RevenueContract` 上增加 NetBox 标准颜色接口：

```python
def get_status_color(self):
    return RevenueContractStatusChoices.colors.get(self.status)
```

`ChoiceFieldColumn` 会自动调用该方法，因此列表页以及其他遵循 NetBox 选择字段渲染约定的组件都能获得正确颜色。

状态与颜色保持如下：

| 状态 | 值 | 颜色 |
| --- | --- | --- |
| 草稿 | `draft` | 灰色 |
| 审批中 | `approving` | 黄色 |
| 生效 | `effective` | 绿色 |
| 变更中 | `changing` | 橙色 |
| 暂停 | `suspended` | 橙色 |
| 终止 | `terminated` | 红色 |
| 归档 | `archived` | 灰色 |

## 测试

先增加模型回归测试，断言七种状态均返回选择集配置的颜色，并明确断言 `effective` 返回 `green`。测试应在实现前因缺少 `get_status_color()` 而失败，增加模型方法后通过。

随后运行：

- 本地快速测试；
- 远端收入合同模型测试；
- NetBox 系统检查与迁移检查；
- 页面检查，确认“生效”徽标使用绿色样式。

## 非目标

- 不调整状态名称、数量或流转规则。
- 不修改其他收入模型的状态颜色。
- 不新增数据库迁移。
