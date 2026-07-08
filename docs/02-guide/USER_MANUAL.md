# A 股定制模块用户手册

本文档面向最终用户（投资研究者、量化策略验证者、交易员），提供从首次使用到核心功能操作的完整指南。

## 1. 系统定位

TradingAgents-Astock 是**投研分析 + 策略验证 + 模拟盘 + 受控执行试运行平台**。

**可以做：**
- AI 辅助的 A 股研究报告生成
- 策略回测与参数优化
- 模拟盘试跑
- 在 QMT 环境下受控执行（需人工确认）

**不能做：**
- 自动实盘交易（默认不触发真实交易）
- 保证盈利的投资建议
- 实时无误的数据服务

## 2. 首次使用

### 2.1 安装

参见 [`QUICK_START.md`](QUICK_START.md)。

### 2.2 启动 WebUI

```bash
PORT=8080 python run_webui.py
```

浏览器访问 http://localhost:8080。

### 2.3 启动 CLI

```bash
python3 -m cli.main run-analysis
```

## 3. AI 研究报告

### 3.1 生成研究报告

1. 在 WebUI 的 **AI Research Center** 输入股票代码（如 `600519.SH`）
2. 选择研究模式（`live_research` 或 `deterministic_verification`）
3. 点击运行

系统将生成包含以下内容的报告：
- 五层数据摘要（行情、研报、新闻、基础数据、公告）
- 多空辩论结论
- Advisory 决策结果（ResearchConclusion → TraderProposal → RiskDecision → PortfolioDecision）

### 3.2 查看报告

- **WebUI**：AI Research Center → Reports 标签查看历史报告
- **CLI**：报告保存在 `~/.tradingagents/reports/` 目录
- **PPT**：可通过 API 生成 PPT 格式报告

### 3.3 报告标注

每份报告包含：
- 数据来源（provider）
- 生成时间
- 使用的模型名称
- Advisory-only 标记（仅供参考，不构成投资建议）

## 4. 策略回测

### 4.1 运行单次回测

1. 进入 **Strategy Lab** → 回测
2. 选择策略（MACD 趋势、布林带均值回归、网格交易等 10 种）
3. 设置标的、时间区间、参数
4. 点击运行

### 4.2 查看回测结果

回测结果包含：
- 收益指标（收益率、Sharpe、最大回撤）
- 净值曲线
- 交易明细
- 数据假设（复权方式、成本模型、T+1 约束等）
- 反偏差状态（是否样本外、是否有 look-ahead bias）

### 4.3 参数优化

1. 进入 **Strategy Lab** → 优化
2. 选择策略和参数搜索空间
3. 设置 Top N 和评分方式
4. 运行后查看 Top N 参数组合

优化使用复合评分：`0.35*Sharpe + 0.30*Return - 0.25*Drawdown + 0.10*TradeFrequency`

### 4.4 策略对比

1. 进入 **Strategy Lab** → 对比
2. 选择多个策略和参数组合
3. 查看指标对比和净值曲线叠加

## 5. 模拟盘

### 5.1 启动模拟盘

1. 进入 **Trading & Execution** → Paper
2. 系统显示虚拟资金、虚拟持仓
3. 可发起虚拟订单

### 5.2 查看模拟盘状态

- 虚拟资金余额
- 虚拟持仓
- 虚拟成交记录
- 风控拦截记录

### 5.3 注意事项

- 模拟盘结果不代表真实交易表现
- 所有交易标注为 `paper` 能力等级
- 不涉及真实账户和真实资金

## 6. 受控执行

### 6.1 前置条件

- 当前范围为 `managed` 模拟/只读模式
- 不接入真实券商，不查询真实 QMT 委托，不启用自动实盘交易
- QMT 真实接入统一列为 P3 延后项，需另行完成权限、风控、审计和回滚验收

### 6.2 执行流程

1. 进入 **Trading & Execution** → Managed
2. 系统显示当前模式（managed / mock / read-only）
3. 发起模拟或受控交易请求
4. 风控门检查（ATR 止损、最大单笔、最大持仓等）
5. 人工确认
6. 确认后仅进入当前支持的模拟/只读执行链路

### 6.3 安全机制

- **Kill Switch**：一键阻断所有后续交易
- **风控门**：每笔交易前的自动检查
- **人工确认**：managed 模式下每笔交易必须人工确认
- **券商边界**：QMT 页面只展示 mock/read-only 状态；真实券商接入为 P3 暂缓

## 7. 数据与健康

### 7.1 查看数据状态

进入 **Data & Ops** → 数据健康，查看：
- 各数据源状态（ok/stale/fallback/mock）
- 数据新鲜度
- 最后刷新时间

### 7.2 手动刷新数据

```bash
# 刷新 K 线数据
curl -X POST http://localhost:8080/api/v1/data/refresh/kline \
  -H "Content-Type: application/json" \
  -d '{"symbol": "600519.SH"}'

# 刷新全部数据
curl -X POST http://localhost:8080/api/v1/data/refresh/all
```

### 7.3 缓存管理

- 查看缓存状态：`GET /api/v1/cache/status`
- 清理缓存：`POST /api/v1/cache/clear`

## 8. 龙头与市场分析

### 8.1 龙头决策

进入 **Market Leaders** 查看：
- 动量总览
- 候选池（含入池/出池理由）
- 板块强弱
- 资金线索（龙虎榜、北向资金）

### 8.2 K 线图

- 支持 7 种周期：1m/5m/30m/60m/日/周/月
- 27 个技术指标
- 17 种画线工具

## 9. 风险提示

以下页面必须阅读风险提示：

| 页面 | 必须提示 |
|---|---|
| AI Research | AI 结论仅供研究参考 |
| Strategy Lab | 回测不代表未来收益 |
| Market Leaders | 候选池不构成买入建议 |
| Trading | 明确 research/paper/managed/live-ready 模式 |
| Paper | 虚拟资金、虚拟成交、非真实账户 |
| QMT/Managed | 需要人工确认和风控门 |
| Data & Ops | 数据延迟、fallback、provider 状态 |

## 10. 支持与反馈

- 产品文档：[`README.md`](../README.md)
- 原 TradingAgents 社区：[Discord](https://discord.com/invite/hk9PGKShPK) | [GitHub](https://github.com/TauricResearch)
