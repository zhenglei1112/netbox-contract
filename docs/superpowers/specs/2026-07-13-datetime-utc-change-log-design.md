# 时间字段变更日志误报修复设计

## 背景与根因

本插件的业务模型均继承 NetBox 的 `NetBoxModel`，因此即使模型没有显式声明时间字段，也包含 `created`、`last_updated` 等 `DateTimeField`。对象时间值可能以当前时区表示，而数据库及审计快照使用 UTC 表示。同一物理时刻因 `+08:00` 与 `+00:00` 的表示差异，可能被 NetBox 变更日志误判为字段发生变化。

NetBox 在模型保存流程的 `pre_save` 阶段采集审计快照。使用插件自己的 `pre_save` 信号无法可靠保证执行顺序，因此转换必须在进入 Django/NetBox 的保存与信号流程之前完成。

## 修复方案

在 `netbox_contract/models.py` 中新增抽象基类 `ContractBaseModel`，继承 `NetBoxModel` 并重写 `save()`：

- 遍历模型的 `_meta.fields`。
- 仅处理 `models.DateTimeField`。
- aware datetime 通过 `astimezone(datetime.timezone.utc)` 转换为 UTC。
- naive datetime、`None` 和非时间字段保持不变。
- 完成规范化后调用 `super().save()`，确保转换早于 NetBox 审计信号。

将本插件全部 23 个直接使用 `NetBoxModel` 的业务模型改为使用 `ContractBaseModel`。具有 `ContactsMixin` 的模型保留 mixin 在前、模型基类在后的现有继承顺序。现有自定义 `save()` 方法继续通过 `super()` 进入统一基类，不改动其业务逻辑。

`ContractBaseModel` 设置 `abstract = True`，不创建数据库表，不需要数据库迁移。

## 非目标

- 不修改 NetBox 核心变更日志实现。
- 不新增或调整信号接收器。
- 不修改日期字段 `DateField`，因为它们没有时区语义。
- 不处理 JSONField 内嵌的时间字符串。
- 不清理既有的历史误报记录。

## 测试与验证

新增针对统一基类的回归测试：

- Asia/Shanghai aware datetime 保存前转换为 UTC，小时数正确偏移且时间戳不变。
- UTC aware datetime 保持等值。
- naive datetime、`None` 与非时间字段不变。
- `ContractBaseModel.save()` 在转换后调用父类保存。
- AST 检查全部 23 个业务模型均继承 `ContractBaseModel`，并确认抽象基类不会生成模型表。
- 现有模型测试与 Python 编译验证通过。
