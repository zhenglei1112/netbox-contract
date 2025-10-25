# 更新合同名称脚本使用说明

## 脚本功能
此脚本用于检查合同名称是否包含自定义字段ContractNumber的内容，如果不包含，则将ContractNumber的内容添加到合同名称后面，用"-"连接。

## 使用方法

### 1. 在NetBox中运行脚本

1. 登录到NetBox管理界面
2. 导航到 **插件 (Plugins)** → **脚本 (Scripts)**
3. 在脚本列表中找到 **"Contract Name Management"** 分类
4. 点击 **"Update contract names with ContractNumber"** 脚本
5. 点击 **"运行脚本 (Run Script)"** 按钮
6. 脚本将显示执行结果，包括处理的合同数量和更新详情

### 2. 脚本执行逻辑

- 检查每个合同是否有ContractNumber自定义字段
- 如果ContractNumber为空或不存在，跳过该合同
- 检查合同名称是否已包含ContractNumber内容
- 如果名称不包含ContractNumber，将ContractNumber添加到名称后面，用"-"连接
- 显示详细的处理日志和统计信息

### 3. 安全特性

- 默认设置为不自动提交更改（commit_default = False）
- 首次运行时建议使用默认设置进行"干运行"测试
- 确认结果正确后，启用提交选项进行实际更新

## 技术细节

- 脚本文件：`update-contract-names.py`
- 检查的字段：`Contract.name` 和 `Contract.custom_field_data['ContractNumber']`
- 更新格式：`原名称-ContractNumber值`
- 影响范围：所有具有ContractNumber自定义字段且名称不包含该值的合同

## 验证结果

脚本执行后，可以通过以下方式验证结果：
1. 查看脚本执行日志和统计信息
2. 在合同列表中检查更新后的合同名称
3. 使用NetBox的搜索功能过滤查看特定合同

## 示例

假设：
- 合同名称："网络服务合同"
- ContractNumber："CN2024001"

脚本执行后，合同名称将更新为："网络服务合同-CN2024001"
