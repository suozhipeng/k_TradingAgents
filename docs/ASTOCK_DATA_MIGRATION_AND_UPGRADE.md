# A 股数据迁移与升级手册

| 更新时间：2026-06-23 |

本文定义 DuckDB、cache、schema、报告归档和回测结果等核心数据资产发生变化时的迁移策略。本文只服务核心功能升级，不扩展为企业级备份容灾或 SLA 恢复目标。

## 1. 适用范围

以下变更必须先更新本文，再进入代码实现：

- DuckDB 表、字段、索引、分区或存储路径变化。
- cache key、cache value、TTL、目录结构或清理策略变化。
- 回测结果 schema、策略参数 schema、优化结果 schema 变化。
- AI Research 任务、报告归档、prompt/model audit schema 变化。
- 交易相关 paper/managed 状态、订单、成交、持仓 schema 变化。
- 数据质量标签、provider provenance、snapshot id 结构变化。

## 2. 迁移分类

| 类型 | 示例 | 处理策略 |
|---|---|---|
| additive | 新增字段、新增表、新增 metadata | 向后兼容，旧数据可读 |
| transform | 字段重命名、类型转换、枚举调整 | 提供迁移脚本和回滚说明 |
| rebuild | cache key 变化、衍生表重建 | 可清理重建，但必须标注影响 |
| breaking | 删除字段、改变主键、改变结果 schema | 必须提供兼容层或明确迁移窗口 |
| external | provider 返回结构变化 | 记录来源、fallback、质量标签变化 |

## 3. 迁移前检查

每次数据迁移前必须记录：

- 需求 ID 和 phase 编号。
- 影响的数据对象。
- 当前 schema 版本和目标 schema 版本。
- 是否影响 API response。
- 是否影响 WebUI 展示。
- 是否影响回测可比性。
- 是否影响 AI Research 历史报告复查。
- 是否影响 paper/managed 状态。
- 是否可以无损回滚。

## 4. DuckDB 迁移要求

DuckDB 相关变更必须提供：

- 表名和字段变更说明。
- 默认值和 nullable 规则。
- 历史数据处理策略。
- 迁移脚本或手工 SQL。
- 迁移前备份路径。
- 迁移后校验 SQL。
- 回滚 SQL 或恢复策略。

建议校验项：

```sql
-- 表是否存在
SELECT table_name FROM information_schema.tables;

-- 字段是否存在
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = '<table_name>';

-- 关键记录数
SELECT COUNT(*) FROM <table_name>;
```

## 5. Cache 升级要求

cache 相关变更必须记录：

- cache namespace。
- key 格式。
- value schema。
- TTL。
- 是否允许清理重建。
- 清理命令或 UI 操作路径。
- 清理后如何验证重新生成。

如果 cache 数据影响 WebUI 或回测结果，页面必须显示 stale / rebuilt / missing 状态。

## 6. Schema 版本标记

后续核心数据对象应逐步支持：

- `schema_version`。
- `generated_at`。
- `source`。
- `snapshot_id`。
- `migration_id`。
- `compatibility`：`compatible` / `requires_migration` / `deprecated`。

没有 schema version 的历史数据，迁移时应标记为 `legacy`，不得直接假设为新 schema。

## 7. 回滚策略

迁移文档必须说明：

- 回滚是否会丢失新数据。
- 回滚后 cache 是否需要清理。
- 回滚后 WebUI 是否需要降级显示。
- 回滚后历史回测结果是否仍可比较。
- 回滚后 AI Research 报告是否仍可复查。

无法回滚的迁移必须明确标注 `irreversible`，并在 phase 归档中说明原因。

## 8. 验收要求

涉及数据迁移的 phase 必须提供：

- 迁移前 schema 摘要。
- 迁移后 schema 摘要。
- 迁移命令或脚本。
- 校验命令和结果。
- cache 清理/重建说明。
- API/WebUI 回归结果。
- 回滚或不可回滚说明。
- phase 归档和 commit SHA。
