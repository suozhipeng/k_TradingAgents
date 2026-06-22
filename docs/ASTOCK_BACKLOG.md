# TradingAgents-Astock 待开发 Backlog

## 1. 文档目标

本文档整理当前仓库后续最值得推进的需求项，按优先级划分为：

- P0：必须尽快收口
- P1：高价值增强
- P2：后续优化

## 2. P0

### BL-001 统一 QMT 能力边界

现状：

- QMT 在执行层已存在
- QMT 在 blueprint/provider 口径里仍保留 placeholder 语义

目标：

- 统一 QMT 在 provider、execution、API、状态文档中的能力定义

完成标准：

- blueprint / status / phase / code 口径一致
- 不再同时出现“已完成执行”和“provider 仍占位”冲突

### BL-002 修正 `qmt/orders` 的 mock 语义

现状：

- `/api/v1/qmt/orders` 返回的是 mock/read-only 响应

目标：

- 接真实 QMT 订单/委托查询，或明确改名为 mock endpoint

完成标准：

- endpoint 语义与返回内容一致
- 文档不再误导为真实订单模块

### BL-003 修正 trade quote / trade state 的 mock 能力

现状：

- `trade/quote` 使用 synthetic mock quote
- `trade/state` 使用 PaperTrader 状态 + mock price 估值

目标：

- 明确它们是 paper trading API，或接入真实报价与估值

完成标准：

- 用户不会把 mock 报价误认为真实交易报价

### BL-004 为专业交易页建立正式归档

现状：

- `trading.html`、`routes_trade.py`、相关测试已进入代码
- 已建立独立 phase 归档 `docs/phases/phase-29-trading-page.md`

目标：

- ✅ 已达成 — 有 scope、测试、风险说明、commit SHA

完成标准：

- 有 scope — ✅ `phase-29-trading-page.md`
- 有测试 — ✅ WebUI + API 切片 150 passed
- 有风险说明 — ✅ 实时报价依赖/缓存/持久化
- 有 commit SHA — ✅ `268d326`, `87e5b73`, `1960c65` 等

## 3. P1

### BL-101 明确专业交易页的产品定位

候选定位：

- paper trading 控制台
- 受控执行控制台
- 研究辅助交易页

目标：

- 选定一种定位，避免页面和执行语义漂移

### BL-102 完善 QMT fundamentals 替代策略

现状：

- QMT 不提供基本面数据

目标：

- 明确基本面永远走其他 provider，或补标准降级策略

### BL-103 收敛 phase 归档一致性

现状：

- 个别 phase 文档仍有 `pending` 或只留 commit 号

目标：

- phase 文档统一补齐 commit SHA、测试与风险

### BL-104 收紧 mock 与 real 的状态标识

目标：

- 在 API、页面、状态文档里显式标注 mock / paper / real / managed

## 4. P2

### BL-201 补更清晰的模块需求追踪矩阵

目标：

- 建立“需求 -> 模块 -> 测试 -> phase”映射表

### BL-202 继续清理文档漂移

目标：

- 统一 phase 数量、端点数量、页面数量等口径

### BL-203 细化多入口职责

目标：

- 继续明确 CLI、Streamlit、Flask WebUI 各自职责

### BL-204 为真实交易能力补更明确的验收门槛

目标：

- 把真实执行前置条件写成 checklist，而不是散落在 phase 文档中

## 5. 建议执行顺序

1. `BL-001` 统一 QMT 能力边界
2. `BL-002` 修正 `qmt/orders` 语义
3. `BL-003` 修正 trade quote / trade state 能力口径
4. `BL-004` 为交易页建立正式归档
5. `BL-101` 明确交易页定位
6. `BL-103` 收敛 phase 归档一致性

## 6. 关联文档

- `docs/ASTOCK_REQUIREMENTS.md`
- `docs/ASTOCK_PRD.md`
- `docs/ASTOCK_TECH_REQUIREMENTS.md`
- `docs/ASTOCK_CURRENT_STATUS.md`
