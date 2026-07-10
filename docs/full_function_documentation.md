# TradingAgents 全功能文档

> 版本以 [../CHANGELOG.md](../CHANGELOG.md) 最新条目为准。

---

## 目录

1. [项目概览](#1-项目概览)
2. [架构总览](#2-架构总览)
3. [LLM 客户端层](#3-llm-客户端层)
4. [数据流管道](#4-数据流管道)
5. [多智能体研究系统](#5-多智能体研究系统)
6. [LangGraph 交易图](#6-langgraph-交易图)
7. [A 股模块 (astock)](#7-a-股模块-astock)
   - 7.1 [统一接口](#71-统一接口)
   - 7.2 [数据源适配器](#72-数据源适配器)
   - 7.3 [路由系统](#73-路由系统)
   - 7.4 [数据存储层](#74-数据存储层)
   - 7.5 [执行引擎](#75-执行引擎)
   - 7.6 [数据质量](#76-数据质量)
   - 7.7 [预警系统](#77-预警系统)
   - 7.8 [市场分析](#78-市场分析)
   - 7.9 [报告生成](#79-报告生成)
   - 7.10 [Web UI](#710-web-ui)
8. [Flask REST API](#8-flask-rest-api)
9. [CLI 命令行工具](#9-cli-命令行工具)
10. [部署与运维](#10-部署与运维)
11. [测试覆盖](#11-测试覆盖)
12. [模块依赖关系图](#12-模块依赖关系图)

---

## 1. 项目概览

TradingAgents 是一个面向 A 股市场的 AI 驱动量化研究与交易系统。核心能力：

| 能力域 | 描述 |
|--------|------|
| **多 LLM 支持** | OpenAI / Anthropic / Google / Azure / DeepSeek / Qwen 等 10+ 提供商 |
| **多智能体研究** | 基本面、情绪、新闻、社交、市场分析师 + 多空研究员辩论 + 交易员 + 风险管理 + 组合经理 |
| **A 股数据接入** | 8 个默认 provider 工厂（7 个 Adapter + TDX Provider），另有 EastMoney 独立数据模块；自动降级路由覆盖 K 线、估值、新闻、研报、公告等 22 数据能力 |
| **三后端存储** | DuckDB (本地) / PostgreSQL (生产 OLTP) / ClickHouse (生产 OLAP) |
| **策略回测** | 12 种策略 + 遗传算法优化 + 滚动窗口分析 + T+1 结算约束 |
| **模拟交易** | 完整模拟交易周期 + QMT managed mock/read-only 边界 |
| **数据质量门禁** | 内置校验规则 + 自定义规则引擎 + 数据隔离区 |
| **Web UI** | 30 个模板文件 / 36+ 条 Web route，Tailwind 暗色主题 |
| **REST API** | 118 条 `/api/v1` route decorators（27 个 API 蓝图，109 个唯一路径）；支持 Bearer Token + TokenBucket，默认保护所有状态变更请求，DuckDB 与 PostgreSQL 行为一致 |
| **CLI** | Typer + Rich TUI 交互式终端 |

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI / Web UI / API                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
  ┌──────▼──────┐  ┌───────▼───────┐  ┌─────▼───────┐
  │ Trading     │  │ AStock        │  │ General     │
  │ Agents Graph│  │ Module        │  │ DataFlows   │
  │ (Multi-Agent│  │ (A-Share      │  │ (Yahoo/AV   │
  │  + LangGraph│  │  Data + Strat)│  │  /Reddit)   │
  └──────┬──────┘  └──────┬────────┘  └─────────────┘
         │                │
  ┌──────▼────────────────▼────────────────┐
  │         LLM Client Layer               │
  │  OpenAI / Anthropic / Google / Azure   │
  └────────────────┬───────────────────────┘
                   │
         ┌─────────┼──────────┐
         │         │          │
  ┌──────▼──┐ ┌────▼────┐ ┌──▼────────┐
  │DuckDB   │ │PostgreSQL│ │ClickHouse │
  │(Local)  │ │(Primary) │ │(OLAP)     │
  └─────────┘ └─────────┘ └───────────┘
```

---


**路径**: `tradingagents/dataflows/`

面向全球市场的通用数据管道，与 A 股模块并行。

### 3.1 数据源

| 源 | 文件 | 数据类型 |
|----|------|----------|
| Yahoo Finance | `y_finance.py` | 行情、新闻 |
| Alpha Vantage | `alpha_vantage_*.py` | 股票、新闻、基本面、指标 |
| Reddit | `reddit.py` | 社交情绪 |
| StockTwits | `stocktwits.py` | 社交情绪 |

### 3.2 工具模块

| 文件 | 职责 |
|------|------|
| `interface.py` | 数据源抽象接口 |
| `symbol_utils.py` | 符号规范化 |
| `stockstats_utils.py` | 技术指标计算 |
| `market_data_validator.py` | 数据验证 |
| `utils.py` | 共享工具 |
| `config.py` | 管道配置 |

---

## 3. LangGraph 交易图

**路径**: `tradingagents/graph/`

### 4.1 核心组件

| 文件 | 职责 |
|------|------|
| `trading_graph.py` | 主图定义 `TradingAgentsGraph` |
| `setup.py` | 图设置 |
| `analyst_execution.py` | 分析师节点执行 |
| `signal_processing.py` | 信号处理 |
| `propagation.py` | 状态传播 |
| `conditional_logic.py` | 条件路由 `ConditionalLogic` |
| `reflection.py` | 反思循环 `Reflector` |
| `checkpointer.py` | 状态检查点 |

### 4.2 执行流程

```
Start → Analysts → Signal Processing → Propagation → Conditional Routing
                                              ↓
                              ┌───────────────┴───────────────┐
                              │                               │
                        Bull/Bear Debate              Risk Management Debate
                              │                               │
                              └───────────────┬───────────────┘
                                              ↓
                                        Trader Decision
                                              ↓
                                    Portfolio Manager
                                              ↓
                                        End (Reflection)
```

---

### 4.3 路由系统

**文件**: `data_sources/router.py`

#### 7.3.1 路由策略

每个数据能力都有预定义的供应商降级链：

```python
DEFAULT_ROUTE_POLICY = {
    "kline": ("baostock", "mootdx", "tencent", "akshare", "qmt", "tdx"),
    "valuation": ("akshare", "tencent"),
    "order_book": ("akshare", "tencent", "mootdx"),
    "trade_tape": ("akshare", "mootdx"),
    "news": ("akshare",),
    "announcements": ("akshare", "cninfo"),
    "research": ("akshare", "iwencai"),
    # ... 25+ 能力映射
}
```

#### 7.3.2 查询流程

```
1. 规范化股票代码
2. 构建 AStockRequest
3. 查找缓存（历史/快照/摘要三类）
4. 从 route_policy 获取候选供应商列表
5. 依次调用各供应商适配器
   - 成功 → 返回 AStockResponse（标记 NORMAL 或 FALLBACK）
   - 失败 → 尝试下一供应商
6. 全部失败 → 返回空响应或错误响应（含降级元数据）
```

### 4.4 数据质量

**路径**: `quality/`

#### 7.6.1 质量执行器

**文件**: `executor.py`

```python
class QualityExecutor:
    MIN_PRICE = 0.01
    MAX_PRICE = 10000.0
    
    def validate_kline(self, symbol, df, interval) -> ValidationResult
    def validate_and_import_kline(self, symbol, df, interval, source) -> int
    def validate_valuations(self, symbol, df) -> ValidationResult
    def validate_and_import_valuations(self, symbol, df, source) -> int
    def resolve_quarantine(self, quarantine_id, resolved_by) -> bool
```

**内置校验规则**:
- 非负价格检查
- 高低价完整性（high≥low, high≥close, low≤close）
- 关键字段无 NaN
- 价格范围（0.01 ~ 10000）
- 成交量完整性

**自定义规则**: 从 `data_quality_rules` 表读取，通过 DuckDB SQL 或 Python eval 执行。

**严重级别**:
- `error` → 隔离数据 + 抛出 `BlockedImportError`
- `warn` → 允许导入 + 记录警告

#### 7.6.2 验证存储

**文件**: `validated_store.py`

```python
class ValidatedStore:
    """包装原始 Store，在写入前执行质量门控。"""
```

### 4.5 预警系统

**路径**: `tradingagents/astock/alert/`

**文件**: `tradingagents/astock/alert/alert_store.py`

```python
class AlertStore:
    # 规则 CRUD
    def create_rule(self, rule) -> AlertRule
    def get_rule(self, rule_id) -> AlertRule | None
    def list_rules(self, enabled_only=False) -> list[AlertRule]
    def update_rule(self, rule_id, updates) -> AlertRule | None
    def delete_rule(self, rule_id) -> bool
    
    # 事件
    def create_event(self, event) -> AlertEvent
    def get_open_alerts(self, limit=20) -> list[AlertEvent]
    def list_events(self, limit=50) -> list[AlertEvent]
    def acknowledge(self, alert_id) -> AlertEvent | None
    def resolve(self, alert_id) -> AlertEvent | None
```

**触发类型**: `PRICE`, `PCT`, `VOLUME`, `STRATEGY`, `RISK`  
**方向**: `ABOVE`, `BELOW`  
**严重程度**: `INFO`, `WARN`, `CRITICAL`  
**状态**: `OPEN`, `ACKNOWLEDGED`, `RESOLVED`

### 4.6 市场分析

**路径**: `tradingagents/astock/analysis/`

**文件**: `tradingagents/astock/analysis/market_analyzer.py`

```python
class MarketAnalyzer:
    """四维度加权市场制度评估。"""
    def analyze(self, symbol, trade_date) -> dict
    def market_regime(self, symbol, lookback=60) -> str  # "bull" | "oscillate" | "bear" | "unknown"

def analyze_regime_from_df(df: pd.DataFrame) -> dict
```

**四维度评分**:

| 维度 | 权重 | 指标 |
|------|------|------|
| 趋势 | 30% | MA5 vs MA20 vs MA60 排列 |
| 动量 | 30% | ROC(20), RSI(14) |
| 波动率 | 20% | ATR(14) / 价格 |
| 成交量 | 20% | 当前成交量 vs MA5 |

**综合评分映射**:

| 分数范围 | 判定 | 推荐策略 |
|---------|------|----------|
| [-1.0, -0.5) | 看跌 | PutWrite, DefensiveMomentum |
| [-0.5, -0.15) | 谨慎看跌 | - |
| [-0.15, 0.15] | 中性 | MeanReversion, RSIRange |
| (0.15, 0.5] | 谨慎看涨 | BullTrend, ValueAverage |
| (0.5, 1.0] | 看涨 | BullTrend, ValueAverage |

### 4.7 报告生成

**路径**: `tradingagents/astock/reporting/`

**文件**: `tradingagents/astock/reporting/ppt.py`

```python
class ReportGenerator:
    """生成 5 页暗色主题 PPTX 报告。"""
    def to_pptx(self, report: dict, output_path: str) -> str
```

**幻灯片布局**:
1. **封面**: 代码、交易日、运行时配置、状态
2. **研究结论**: 建议、置信度、摘要、投资计划
3. **顾问链**: 交易提议、风险决策、组合决策
4. **供应商覆盖**: 供应商状态/来源/记录数表格
5. **运行时追踪**: 执行步骤时间线

## 4. 模块依赖关系图

```
cli/main.py
    │
    ├─► AStockGraphRuntime ──► AStockInterface ──► AStockDataFacade
    │                            │                    │
    │                            │                    └─► AStockDataRouter
    │                            │                         │
    │                            │                         ├─► AkshareAdapter
    │                            │                         ├─► TencentAdapter
    │                            │                         ├─► TdxProvider
    │                            │                         ├─► MootdxAdapter
    │                            │                         ├─► IwencaiAdapter
    │                            │                         ├─► CninfoAdapter
    │                            │                         ├─► BaoStockAdapter
    │                            │                         └─► QMTAdapter
    │                            │
    │                            ├─► AStockStore / PGStore ──► DuckDB / PostgreSQL
    │                            │
    │                            ├─► BacktestEngine ──► StrategyBase (12 strategies)
    │                            │                  ──► MarketAnalyzer
    │                            │                  ──► QualityExecutor
    │                            │                  ──► RiskGate
    │                            │                  ──► PaperTrader
    │                            │
    │                            └─► ReportGenerator ──► python-pptx
    │
    ├─► TradingAgentsGraph ──► Agents (analysts/researchers/trader/risk/portfolio)
    │                         ──► LLM Clients (OpenAI/Anthropic/Google/Azure)
    │
    └─► Flask Blueprint ──► 20+ route blueprints ──► /api/v1/*

tradingagents/llm_clients/
    │
    └─► 各提供商 SDK (openai, anthropic, azure; Gemini 当前已暂时屏蔽)

tradingagents/dataflows/
    │
    └─► Yahoo Finance / Alpha Vantage / Reddit / StockTwits

tradingagents/graph/
    │
    └─► langgraph (可选依赖)
```

---
