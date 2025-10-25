# 用印事由功能实现说明

## 功能概述

在netbox-contract插件中，为合同详情页的付款列表项添加了"用印事由"功能按钮。该功能实现了以下需求：

1. 在付款列表的每行数据最后添加"用印事由"按钮
2. 点击按钮后生成特定格式的文字内容
3. 自动将生成的文字复制到剪贴板
4. 弹出提示窗口显示生成的内容
5. 窗口显示5秒倒计时，倒计时结束后自动关闭

## 实现细节

### 1. 表格列添加

在 `netbox_contract/tables.py` 中的 `InvoiceListTable` 类添加了新的列：

```python
seal_reason = tables.TemplateColumn(
    template_name='netbox_contract/seal_reason_button.html',
    verbose_name=_('Seal Reason'),
    orderable=False,
    attrs={'td': {'class': 'text-nowrap'}}
)
```

### 2. 按钮模板

创建了 `netbox_contract/templates/netbox_contract/seal_reason_button.html` 模板文件，包含：

- "用印事由"按钮
- 弹窗模态框
- JavaScript功能实现

### 3. 文字生成逻辑

生成的文字格式为：
```
合同名称 + 当前付款开始日期 + '-' + 当前付款的结束日期 + '租金' + 当前付款的金额 + '元'
```

示例：`合同名称2023-01-01-2023-12-31租金1000元`

### 4. 功能特性

- **自动复制**: 使用 `navigator.clipboard.writeText()` API 自动复制到剪贴板
- **弹窗提示**: 显示"以下用印事由已复制到剪切板"的提示信息
- **倒计时**: 5秒倒计时显示，倒计时结束后自动关闭窗口
- **手动关闭**: 用户可随时手动关闭窗口
- **错误处理**: 剪贴板复制失败时的降级处理

### 5. 国际化支持

在 `netbox_contract/locale/zh/LC_MESSAGES/django.po` 中添加了中文翻译：

- "Seal Reason" → "用印事由"
- "用印事由" → "用印事由"
- "以下用印事由已复制到剪切板" → "以下用印事由已复制到剪切板"
- "窗口将在" → "窗口将在"
- "秒后自动关闭" → "秒后自动关闭"
- "关闭" → "关闭"

## 使用方式

1. 进入合同详情页面
2. 在"付款"表格中找到"用印事由"列
3. 点击对应付款行的"用印事由"按钮
4. 系统会自动生成文字并复制到剪贴板
5. 弹出提示窗口显示生成的内容和5秒倒计时
6. 倒计时结束后窗口自动关闭，或可手动点击"关闭"按钮

## 技术实现

- **前端**: Bootstrap 5 模态框 + 原生 JavaScript
- **后端**: Django 模板系统 + django-tables2
- **数据**: 从Invoice模型获取合同名称、付款期间、金额等信息
- **交互**: 异步剪贴板操作 + 定时器控制

## 文件修改

1. `netbox_contract/tables.py` - 添加seal_reason列
2. `netbox_contract/templates/netbox_contract/seal_reason_button.html` - 按钮和弹窗模板
3. `netbox_contract/locale/zh/LC_MESSAGES/django.po` - 中文翻译
4. `netbox_contract/locale/zh/LC_MESSAGES/django.mo` - 编译后的翻译文件

## 兼容性

- 支持现代浏览器（Chrome, Firefox, Safari, Edge）
- 剪贴板API降级处理
- 响应式设计适配不同屏幕尺寸
