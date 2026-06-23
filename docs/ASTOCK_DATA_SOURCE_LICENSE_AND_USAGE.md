# A 股数据源授权与使用边界

| 更新时间：2026-06-23 |

本文记录 TradingAgents-Astock 核心功能使用外部数据源时的来源、用途、标注和使用边界。本文只用于指导数据接入、AI Research、回测和 WebUI 展示，不构成法律意见，也不扩展为完整法务审查文档。

## 1. 数据源分类

| 类别 | 示例 | 用途 | 核心功能检查 |
|---|---|---|---|
| 行情 | mootdx、Tencent、EastMoney、Sina、akshare 聚合接口 | K 线、报价、板块、资金线索 | 授权、频率限制、延迟、缓存边界 |
| 基础资料 | akshare、交易所公开数据、F10 类信息 | 股票基础资料、行业、财务摘要 | 来源条款、再分发限制 |
| 新闻公告 | 公告、新闻、研报摘要 provider | AI Research 上下文 | 版权、摘要范围、引用要求 |
| 券商/QMT | QMT 本地接口 | managed execution、账户/订单联调 | 券商协议、使用场景、账号授权 |
| LLM provider | OpenAI/其他模型服务 | AI 分析与报告生成 | 输出使用条款、数据输入边界 |

## 2. 产品标注要求

所有数据输出应尽量展示：

- `source`：数据来源。
- `provider`：具体 provider 或 fallback provider。
- `freshness`：数据更新时间或延迟状态。
- `quality`：normal / stale / partial / fallback / mock。
- `license_note`：必要时标注“需确认授权”。
- `snapshot_id`：进入回测、AI、交易建议前的数据快照引用。

## 3. 禁止事项

在未确认授权前，不应：

- 对外宣称数据可商用再分发。
- 把第三方行情、新闻、研报全文作为产品卖点。
- 隐藏数据来源和更新时间。
- 把 fallback 数据误标为 primary source。
- 把 mock 或缓存数据误标为实时真实数据。

## 4. 数据使用策略

后续开发应采用以下策略：

- UI 和 API 默认展示来源、更新时间、质量标签。
- AI Research 引用数据时保留 provider 和快照。
- 回测结果展示数据口径、复权方式和数据质量。
- 交易页只把数据作为辅助输入，不把不明来源数据作为自动执行依据。
- 对无法确认授权的数据，标记为 research-only。

## 5. 与其他文档关系

- 字段、质量、血缘见 `docs/ASTOCK_DATA_DICTIONARY_AND_LINEAGE.md`。
- API source/meta 要求见 `docs/ASTOCK_API_CONTRACTS.md`。
- 风险披露见 `docs/ASTOCK_RISK_DISCLOSURE_AND_COMPLIANCE.md`。
- 数据源检查必须进入 `docs/ASTOCK_TEST_ACCEPTANCE_PLAN.md` 的验收证据。

## 6. 验收要求

涉及新增数据源的 phase 必须提供：

- provider 名称和用途。
- 是否 primary / fallback / cache / mock。
- 是否可离线测试。
- 数据更新时间和质量标签。
- 授权状态记录：`unknown`、`research-only`、`commercial-approved`。
- 未确认授权时的产品限制。
