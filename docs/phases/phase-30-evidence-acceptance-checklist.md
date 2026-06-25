# Phase 30 — 交易页页面验收清单

## 页面级验收要求

每个交易相关页面必须通过以下状态验收。需要截图（或替代证据）记录每个状态。

### Trading 页面（`trading.html`）

| 验收点 | 输入条件 | 预期输出 | 状态 |
|--------|----------|----------|------|
| 成功态 | 正常加载 PaperTrader | 显示持仓、现金余额、盈亏 | □ 通过 |
| 空态 | 无持仓、无成交 | 显示"暂无持仓"占位 | □ 通过 |
| 错误态 | PaperTrader 不可用 | 显示错误提示 | □ 通过 |
| 降级态 | 行情源不可用 | 显示 "quotes unavailable" | □ 通过 |
| 能力等级 | 页面应标注 "Paper Trading（模拟交易）" | 而非 "Trading" | □ 通过 |
| kill switch | kill switch 激活后，下单按钮禁用 | 显示 "全局紧急停止已激活" | □ 通过 |

### Paper 页面（`paper.html`）

| 验收点 | 输入条件 | 预期输出 | 状态 |
|--------|----------|----------|------|
| 成功态 | 正常加载 | 显示 paper 状态、持仓、成交 | □ 通过 |
| 空态 | 无交易 | "暂无交易记录" | □ 通过 |
| 能力等级 | 标注 "Paper Trading" | 清晰区分虚拟 | □ 通过 |

### Risk 页面（`risk.html`）

| 验收点 | 输入条件 | 预期输出 | 状态 |
|--------|----------|----------|------|
| 成功态 | 正常加载 | 显示风控规则和状态 | □ 通过 |
| 拦截态 | 检查被拦截的提案 | 显示 reason code 和 blocked_by 列表 | □ 通过 |
| 能力等级 | 标注 ResearchOnly | execution_signal 可见 | □ 通过 |

### QMT 页面（`qmt.html`）

| 验收点 | 输入条件 | 预期输出 | 状态 |
|--------|----------|----------|------|
| 成功态 | Mock QMT 运行 | 显示健康检查、mock 持仓 | □ 通过 |
| mock 标注 | mock_mode 激活 | 所有数据标注 "mock" | □ 通过 |
| 错误态 | QMT 不可用 | 显示健康检查失败 | □ 通过 |

---

## API 级验收要求

### `POST /api/v1/trade/order`

| 验收点 | 输入条件 | 预期输出 | 状态 |
|--------|----------|----------|------|
| 买成功 | symbol, side=买, price, quantity | order.filled=true, cash 减少 | □ 通过 |
| 卖成功 | 先买后卖 | order.filled=true, cash 增加, pnl 计算 | □ 通过 |
| 现金不足 | quantity 超过现金 | 400 error: "Insufficient cash" | □ 通过 |
| 持仓不足 | 卖超过持仓 | 400 error: "Insufficient shares" | □ 通过 |
| 无效参数 | 空的 symbol | 400 error: "symbol is required" | □ 通过 |

### `GET /api/v1/trade/quote`

| 验收点 | 输入条件 | 预期输出 | 状态 |
|--------|----------|----------|------|
| 缓存命中 | 同 symbol 60 秒内二次请求 | source=cache | □ 通过 |
| 实时拉取 | 新 symbol 或缓存过期 | source=live | □ 通过 |
| 降级 | EastMoney 失败 | 自动 fallback 到 Sina | □ 通过 |
| 无数据 | 无效 symbol | 503 + source=none | □ 通过 |

### `GET /api/v1/trade/state`

| 验收点 | 输入条件 | 预期输出 | 状态 |
|--------|----------|----------|------|
| 成功 | 有持仓 | positions avg_cost/current_price/pnl 准确 | □ 通过 |
| 空态 | 无持仓 | positions 空列表 | □ 通过 |

---

## 证据要求

- 截图保存在 `docs/phases/phase-30-evidence-screenshots/`（如有图形界面）
- 如无截图条件，记录 Python 测试输出或 curl 命令结果
- Phase 30 完成时所有验收点应有 "通过/失败/暂不适用" 标记
