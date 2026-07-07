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
| **模拟交易** | 完整模拟交易周期 + QMT 桥接 |
| **数据质量门禁** | 内置校验规则 + 自定义规则引擎 + 数据隔离区 |
| **Web UI** | 30 个模板文件 / 36+ 条 Web route，Tailwind 暗色主题 |
| **REST API** | 118 条 `/api/v1` route decorators（27 个 API 蓝图，109 个唯一路径）；支持 Bearer Token + TokenBucket，PostgreSQL 写操作默认启用全局认证 gate |
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

## 3. LLM 客户端层

**路径**: `tradingagents/llm_clients/`

### 3.1 架构

工厂模式创建客户端，懒加载避免不必要的 SDK 依赖。

```
factory.py (create_llm_client)
    │
    ├─► OpenAIClient      → openai, xai, deepseek, qwen, glm, minimax, ollama, openrouter
    ├─► AnthropicClient   → anthropic
    ├─► GoogleClient      → google
    └─► AzureOpenAIClient → azure
```

### 3.2 核心文件

| 文件 | 职责 |
|------|------|
| `base_client.py` | 抽象基类，定义统一接口 |
| `openai_client.py` | OpenAI 兼容 API 客户端 |
| `anthropic_client.py` | Anthropic Claude 客户端 |
| `google_client.py` | Google Gemini 客户端 |
| `azure_client.py` | Azure OpenAI 客户端 |
| `factory.py` | 工厂函数 `create_llm_client(provider, model, base_url, **kwargs)` |
| `model_catalog.py` | 模型注册表 |
| `capabilities.py` | LLM 能力检测（结构化输出、图片输入等） |
| `api_key_env.py` | API 密钥环境变量加载 |
| `validators.py` | 输入输出校验器 |

### 3.3 使用示例

```python
from tradingagents.llm_clients.factory import create_llm_client

client = create_llm_client(
    provider="openai",
    model="gpt-4o",
    base_url="https://api.openai.com/v1",
    api_key="sk-xxx"
)
response = client.chat(messages=[...])
```

---

## 4. 数据流管道

**路径**: `tradingagents/dataflows/`

面向全球市场的通用数据管道，与 A 股模块并行。

### 4.1 数据源

| 源 | 文件 | 数据类型 |
|----|------|----------|
| Yahoo Finance | `y_finance.py` | 行情、新闻 |
| Alpha Vantage | `alpha_vantage_*.py` | 股票、新闻、基本面、指标 |
| Reddit | `reddit.py` | 社交情绪 |
| StockTwits | `stocktwits.py` | 社交情绪 |

### 4.2 工具模块

| 文件 | 职责 |
|------|------|
| `interface.py` | 数据源抽象接口 |
| `symbol_utils.py` | 符号规范化 |
| `stockstats_utils.py` | 技术指标计算 |
| `market_data_validator.py` | 数据验证 |
| `utils.py` | 共享工具 |
| `config.py` | 管道配置 |

---

## 5. 多智能体研究系统

**路径**: `tradingagents/agents/`

基于 LangGraph 的多智能体协作研究框架。

### 5.1 智能体团队

```
分析师团队          研究团队          交易团队         风险管理团队        组合管理团队
┌─────────────┐   ┌────────────┐   ┌──────────┐   ┌──────────────┐   ┌─────────────┐
│Fundamentals │   │BullResearch│   │  Trader  │   │Aggressive    │   │PortfolioMgr │
│Sentiment    │──►│BearResearch│──►│          │──►│Neutral       │──►│             │
│News         │   │ResearchMgr  │   │          │   │Conservative  │   │             │
│SocialMedia  │   └────────────┘   └──────────┘   └──────────────┘   └─────────────┘
│Market       │
└─────────────┘
```

### 5.2 核心文件

| 文件 | 职责 |
|------|------|
| `__init__.py` | 统一导出所有智能体工厂函数 |
| `schemas.py` | 智能体状态和数据模型 |
| `analysts/` | 5 类分析师（基本面、情绪、新闻、社交、市场） |
| `researchers/` | 多空研究员（Bull/Bear） |
| `managers/` | 研究经理 + 组合经理 |
| `trader/` | 交易员 |
| `risk_mgmt/` | 三种风险偏好辩论者（激进/中性/保守） |
| `utils/` | 工具集（消息删除、结构化输出、记忆、评级、各类数据工具） |

### 5.3 状态模型

```python
AgentState                    # 通用智能体状态
InvestDebateState             # 投资决策辩论状态
RiskDebateState               # 风险评估辩论状态
```

---

## 6. LangGraph 交易图

**路径**: `tradingagents/graph/`

### 6.1 核心组件

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

### 6.2 执行流程

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

## 7. A 股模块 (astock)

**路径**: `tradingagents/astock/`

这是项目的核心模块，提供完整的 A 股市场数据、策略、交易和研究能力。

### 7.1 统一接口

**文件**: `interface.py`

```python
class AStockInterface:
    """A 股统一接口，封装数据源路由器，返回结构化数据包。"""
    
    def market_snapshot(symbol, ...) -> AStockSectionBundle
    def news_snapshot(symbol, ...) -> AStockSectionBundle
    def fundamentals_snapshot(symbol, ...) -> AStockSectionBundle
    def announcements_snapshot(symbol, ...) -> AStockSectionBundle
    def research_snapshot(symbol, ...) -> AStockSectionBundle
    def collect(symbol, sections=...) -> Dict[str, AStockSectionBundle]
    def to_payload(symbol, ...) -> Dict[str, Any]
    def describe(payload) -> str

class AStockSectionBundle:
    """单个数据区块的结构化响应。"""
    section, symbol, raw_symbol, status, responses, capabilities, summary
    primary_source, missing, notes, meta
```

### 7.2 数据源适配器

**路径**: `data_sources/`

#### 7.2.1 适配器列表

| 适配器 | 类名 | 能力 | 特点 |
|--------|------|------|------|
| **Akshare** | `AkshareAdapter` | K线、估值、新闻、研报、财务、预期、公告、价格限制 | 主免费源；熔断器、日调用限制、反爬延迟 |
| **Tencent** | `TencentFinanceAdapter` | 盘口快照、逐笔、估值 | 解析 `qt.gtimg.cn` 的 `~` 分隔响应 |
| **TDX** | `TdxProvider` | K线、盘口、逐笔、估值、F10、财务、公告、市场总结、板块 | 在线 TDX 服务器 + 本地 VIPDOC + SQLite 缓存 |
| **Mootdx** | `MootdxAdapter` | K线、盘口、逐笔、F10 | MooTDX 协议封装 |
| **EastMoney** | (独立模块) | 龙虎榜、板块、北向资金、概念板块 | 限频数据中心 API |
| **Iwencai** | `IwencaiAdapter` | 研报列表、PDF下载、机构预期、搜索 | 需要 Cookie，封装 pywencai |
| **Cninfo** | `CninfoAdapter` | 公告全文、摘要 | POST cninfo.com.cn，管理 orgId 缓存 |
| **BaoStock** | `BaoStockAdapter` | K线 | 免费免注册，符号转换 `sh.XXXX`/`sz.XXXX` |
| **QMT** | `QMTAdapter` | K线、盘口、逐笔、估值 | 桥接到 QmtBridge HTTP 客户端 |

#### 7.2.2 适配器工厂

```python
DEFAULT_ADAPTER_FACTORIES = {
    "akshare": AkshareAdapter,
    "mootdx": MootdxAdapter,
    "tdx": TdxProvider,
    "tencent": TencentFinanceAdapter,
    "iwencai": IwencaiAdapter,
    "cninfo": CninfoAdapter,
    "qmt": QMTAdapter,
    "baostock": BaoStockAdapter,
}

def build_default_adapters(**configs) -> Mapping[str, AStockAdapterBase]
```

`build_default_adapters()` 返回懒加载映射，路由器按实际命中的 provider 初始化适配器，避免导入数据源时一次性加载所有第三方 SDK。

TDX Provider (`tdx_provider.py`) 为独立 provider，不在 DEFAULT_ADAPTER_FACTORIES 中，通过 `data_sources/` 顶层模块直接导入。

#### 7.2.3 核心模块与工具

核心模块：

| 文件 | 职责 |
|------|------|
| `adapters/` | Adapter 包入口，兼容导出 `AkshareAdapter` 等 provider 类 |
| `adapters/registry.py` | 默认 provider 工厂 + 懒加载映射 `LazyAdapterMapping` |
| `adapters/providers/` | 按供应商拆分的实现：akshare/tencent/mootdx/cninfo/iwencai/qmt/baostock (7 个) |
| `tdx_provider.py` | 在线 TDX + 本地 VIPDOC Provider（独立 provider，不在 adapters/providers/ 下） |
| `router.py` | 统一路由器 `AStockDataRouter` + 便利包装 `AStockDataFacade` |

公共工具文件（10+ 个）：

| 文件 | 职责 |
|------|------|
| `schema.py` | `AStockRequest` / `AStockResponse` 数据模型 |
| `errors.py` | 自定义异常 (`AStockDataError`, `AStockNoDataError`, `AStockSourceUnavailableError`, `AStockSchemaError`) |
| `symbols.py` | 符号规范化 `normalize_astock_symbol()`, `split_astock_symbol()` |
| `calendar.py` | 交易日历 `is_trading_day()`, `next_trading_day()`, `prev_trading_day()` |
| `cache.py` | 缓存策略 `AStockCachePolicy`, `FileAStockCache`, `InMemoryAStockCache` |
| `quality.py` | 质量标签 `DataQualityTag`, `FreshnessInfo`, `DataQualityMetadata` |
| `cleaner.py` | 数据清洗 `clean_records()`, `CleaningReport` |
| `adjustment.py` | 复权因子 `fetch_adjust_factors()`, `adjust_series()`, `adjust_bars()` |
| `suspension/` | 停牌/涨跌停 facade；子模块拆分 suspension / price_limit / common |
| `sina_sectors.py` | 新浪板块数据 |
| `eastmoney.py` | EastMoney 独立数据模块 |
| `tdx_cache.py` | TDX 缓存 |
| `tdx_vipdoc.py` | TDX VIPDOC 本地缓存 |
| `leading_pool.py` | 龙头池管理 |

### 7.3 路由系统

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

### 7.4 数据存储层

**路径**: `store/`

详见[数据库模块白皮书](database_module_whitepaper.md)。

#### 7.4.1 三后端架构

| 后端 | 类 | 用途 | 文件 |
|------|---|------|------|
| DuckDB | `AStockStore` | 本地 OLAP 分析缓存 | `schema.py` |
| PostgreSQL | `PGStore` | 生产主存储 (OLTP) | `pg_store.py` 兼容入口 + `pg_*` mixin |
| ClickHouse | (DDL 定义) | 生产 OLAP 分析副本 | `clickhouse_schema.py` |

#### 7.4.2 核心文件

| 文件 | 职责 |
|------|------|
| `__init__.py` | 统一导出 |
| `schema_defs.py` | **SSOT**: 32 张表统一列定义 / 索引 / DDL 生成（28 个索引定义） |
| `models/` | 32 个 SQLAlchemy ORM 模型（分 reference / market_data / events / governance 子模块） |
| `schema.py` | DuckDB 存储实现 `AStockStore` 类 |
| `pg_store.py` | PostgreSQL public entrypoint，组合各 `pg_*` mixin 并导出 `PGStore` / `init_pg_store` |
| `pg_common.py` | PG 配置、共享导入、ORM 模型集合 |
| `pg_connection.py` | 同步/异步连接、schema 初始化、迁移 |
| `pg_io.py` | DataFrame upsert/query 通用 I/O |
| `pg_market_data.py` | K 线、估值、盘口等市场数据写读 |
| `pg_governance.py` | 数据质量、审计、API key、通知等治理表操作 |
| `pg_admin.py` | 备份、恢复、统计、清理等管理能力 |
| `backend.py` | 运行时后端切换 `BackendManager` + `BackendConfig` |
| `loader.py` | 数据加载器 `KlineLoader`, `ValuationLoader`, `BatchLoader` |
| `jobs.py` | 异步作业管理 `DataJobManager` |
| `clickhouse_schema.py` | ClickHouse 12 张 OLAP 表 DDL + 导出工具 |
| `migrations/runner.py` | 版本化迁移引擎 `MigrationRunner` |
| `migrations/V20260628_001__initial_schema.py` | 初始迁移文件 |

### 7.5 执行引擎

**路径**: `execution/`

#### 7.5.1 策略体系

**单股策略 (13 种)**:

| 策略 | 类型 | 信号逻辑 |
|------|------|----------|
| `MovingAverageTrendStrategy` | 趋势 | 快慢均线交叉 |
| `BullTrendStrategy` | 多头 | MA5>MA20>MA60 + 成交量确认 |
| `ValueAverageStrategy` | 估值 | 价格低于历史分位数买入 |
| `MeanReversionStrategy` | 均值回归 | 价格偏离 MA ± N 标准差 |
| `RSIRangeStrategy` | 均值回归 | RSI 超买/超卖 |
| `DefensiveMomentumStrategy` | 动量 | 正 ROC + 低波动率买入 |
| `PutWriteStrategy` | 期权 | 均线空头排列卖出 |
| `MACDTrendStrategy` | 趋势 | MACD 金叉/死叉 |
| `BollingerBandsReversionStrategy` | 波动率 | 布林带上/下轨反转 |
| `GridTradingStrategy` | 网格 | 固定网格买卖 |

**组合策略 (2 种)**:

| 策略 | 描述 |
|------|------|
| `MomentumRotationStrategy` | 风险调整动量轮动，选择 Top-L 股票 |
| `StockFlow` | 多策略级联（and/or/majority/cascade 模式） |

**策略组合器**:

| 文件 | 描述 |
|------|------|
| `combiners.py` | 策略组合器（and/or/majority/cascade 模式） |
| `portfolio.py` | 组合策略基类 |

#### 7.5.2 回测引擎

**文件**: `backtest_engine.py`

```python
class BacktestEngine:
    def run(self, symbol, start_date, end_date, strategy, ...) -> BacktestResult
    def run_portfolio(self, symbols, start_date, end_date, strategy, ...) -> BacktestResult
```

**关键特性**:
- T+1 结算约束强制执行
- 涨跌停检测（标准 10%，ST 5%）
- 停牌检测（成交量=0 + 外部 akshare/EastMoney 验证）
- 容量约束（默认 25% 成交量）
- 费用计算（佣金、印花税、滑点）
- 偏差检测（幸存者偏差、前瞻偏差）
- 自动市场制度分析集成
- 基准对比（组合模式）

#### 7.5.3 其他执行组件

| 文件 | 职责 |
|------|------|
| `optimizer/` | 参数优化（网格搜索 + 遗传算法 + 滚动窗口） |
| `fee_model.py` | A 股费用配置 `AStockFeeConfig` + 费用计算 |
| `metrics.py` | 绩效指标（夏普比率、最大回撤、胜率） |
| `paper_trader/` | 模拟交易 `PaperTrader` + `PaperTradeState` |
| `risk_gate/` | 交易前风控 `RiskGate` + ATR 止损 + 跟踪止损 |
| `qmt_bridge/` | QMT HTTP 桥接客户端；`client.py` 为主入口，`operations.py` 负责协议发送 |
| `qmt_execution/` | QMT 受控执行层（SAFETY/AUTO 模式） |
| `momentum_rotation.py` | 龙头股动量轮动回测 |
| `kill_switch.py` | 全局紧急停止（单例） |
| `scheduler/` | 周期性模拟交易调度 |
| `event_bus.py` | 进程内发布/订阅环形缓冲区 |
| `strategy_registry.py` | 可发现策略目录 |
| `portfolio_risk/` | 组合风险分析（VaR + Brinson 归因 + 风险敞口） |
| `audit_store/` | 线程安全审计/任务持久化 |
| `leader_pool.py` | 龙头池条目 |
| `batch_backtest/` | 批量回测 Runner + ranking/selection 工具 |
| `strategy_base/` | 策略基类 `StrategyBase` + `PortfolioStrategyBase` + 单股策略实现 |

### 7.6 数据质量

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

### 7.7 预警系统

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

### 7.8 市场分析

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

### 7.9 报告生成

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

### 7.10 Web UI

**路径**: `tradingagents/astock/web/`

30 个模板文件，6 个 blueprint 模块，Tailwind 暗色主题，消费 Flask REST API (`/api/v1/`)。

**Blueprint 模块**:

| 模块 | 文件 | 页面数 |
|------|------|--------|
| dashboard | `dashboard_bp.py` | 3 (dashboard, daily_review, momentum_dashboard) |
| ops | `ops_bp.py` | 3 (settings, ops_audit, data_health) |
| portfolio | `portfolio_bp.py` | 5 (portfolio, trading, paper, risk, qmt) |
| research | `research_bp.py` | 2 (ai_agent, research) |
| strategy | `strategy_bp.py` | 4 (strategies, strategy_hub, strategy_monitor, backtest) |
| watch_center | `watch_center_bp.py` | 13 (watchlist, screener, tv_chart, kc_chart, sectors, dragon_tiger, northbound, market_leaders, momentum_rotation, monitor, base, macros, templates) |

| 路由 | 模板 | 描述 |
|------|------|------|
| `/` | → `/dashboard` | 根重定向 |
| `/dashboard` | `dashboard.html` | 主仪表板 |
| `/trading` | `trading.html` | 交易页面 |
| `/research` | `research.html` | 研究页面 |
| `/strategy_hub` | `strategy_hub.html` | 三合一策略控制台 |
| `/strategies` | `strategies.html` | 策略页面 |
| `/backtest` | `backtest.html` | 回测控制台 |
| `/paper` | `paper.html` | 模拟交易 |
| `/qmt` | `qmt.html` | QMT 集成 |
| `/risk` | `risk.html` | 风险管理 |
| `/reports` | `reports.html` | 报告归档 |
| `/watchlist` | `watchlist.html` | 自选股管理 |
| `/batch-analyze` | `watchlist.html` (batch_mode) | 批量分析 |
| `/settings` | `settings.html` | 设置 |
| `/settings/notifications` | `settings.html` (section=notifications) | 通知设置 |
| `/screener` | `screener.html` | 选股器 |
| `/market_leaders` | `market_leaders.html` | 统一市场龙头 |
| `/dragon_tiger` | `dragon_tiger.html` | 龙虎榜（旧入口→/market_leaders） |
| `/sectors` | `sectors.html` | 板块强弱（旧入口→/market_leaders） |
| `/northbound` | `northbound.html` | 北向资金（旧入口→/market_leaders） |
| `/momentum_rotation` | `momentum_rotation.html` | 动量轮动（旧入口→/market_leaders） |
| `/momentum_dashboard` | `momentum_dashboard.html` | 动量决策看板（旧入口→/market_leaders） |
| `/momentum_standalone` | `momentum_dashboard.html` | 经典 Jinja2 版决策看板 |
| `/portfolio` | `portfolio.html` | 组合工作台 |
| `/ops_audit` | `ops_audit.html` | 运维审计面板 |
| `/ai_agent` | `ai_agent.html` | AI 代理页面 |
| `/tv_chart` | `tv_chart.html` | TradingView 图表 |
| `/kc_chart` | `kc_chart.html` | K 线图表 |
| `/data_health` | `data_health.html` | 数据健康 |
|—|—|—|
| **重定向路由** |||
| `/comparison` | → `/strategy_hub` (301) | 旧策略对比入口 |
| `/compare` | → `/strategy_hub` (301) | 旧策略对比入口 |
| `/performance` | → `/strategy_hub` (301) | 旧绩效分析入口 |

---

## 8. Flask REST API

**路径**: `tradingagents/astock/api/`  
**基础路径**: `/api/v1/`  
**应用工厂**: `create_app()` in `tradingagents/astock/api/__init__.py`

### 8.1 中间件

| 组件 | 文件 | 职责 |
|------|------|------|
| CORS | `__init__.py` | 跨域支持 |
| 认证 | `auth.py` / `__init__.py` | `require_auth` / `optional_auth` + `TokenBucket`；PostgreSQL 模式写操作启用全局 Bearer gate，DuckDB dev 模式默认不强制 |
| 审计 | `audit.py` | `@audit_log` 装饰器，异步审计日志 |
| 后端选择 | `__init__.py` | 根据 `BackendManager` 选择 DuckDB/PostgreSQL |
| 质量门控 | `__init__.py` | `ValidatedStore` 包装原始 Store |

### 8.2 路由蓝图

| 路由文件 | 方法 | 端点 | 描述 |
|---------|------|------|------|
| `routes_data_query.py` | GET/POST | `/kline`, `/valuation`, `/orderbook`, `/news`, `/trade_tape`, `/research`, `/fundamentals`, `/f10`, `/announcements` | 核心数据查询 |
| | POST | `/data/refresh/kline`, `/data/refresh/valuation`, `/data/refresh/all` | 手动数据刷新 |
| `routes_data_jobs.py` | GET/POST | `/data/jobs`, `/data/jobs/refresh`, `/data/jobs/import-database` | 异步数据作业管理 |
| `routes_data_ingest.py` | POST | `/data/manual/<table>` | 手动行插入 |
| `routes_data_cache.py` | GET/POST | `/cache/status`, `/cache/clear` | 缓存管理 |
| `routes_daily.py` | GET | `/daily` | 每日数据 |
| | GET/POST | `/store/stats` | 存储统计 |
| `routes_backtest.py` | POST | `/backtest/run` | 单次回测 |
| | GET/DELETE | `/backtest/results` | 查询/清空回测结果 |
| | GET | `/backtest/compare` | 多策略对比 |
| | POST | `/backtest/walkforward` | 滚动窗口分析 |
| | POST | `/backtest/analyze` | 详细绩效分析 |
| | POST | `/backtest/optimize` | 参数网格搜索 + 遗传算法 |
| `routes_market.py` | GET | `/market/summary`, `/market/strategies`, `/market/regime` | 市场综述/策略列表/制度分析 |
| `routes_market_data.py` | GET | `/market/dragon-tiger`, `/market/sectors`, `/market/northbound`, `/market/blocks`, `/market/momentum`, `/market/overview`, `/market/calendar` | 龙虎榜/板块/北向/股票池/动量/市场概览/日历 |
| | POST | `/market/momentum-rotation` | 动量轮动回测 |
| `routes_data_health.py` | GET | `/data/health` | 数据源健康探测 |
| `routes_paper.py` | POST/GET | `/paper/cycle`, `/paper/state`, `/paper/trades` | 模拟交易周期/状态/成交 |
| `routes_trade.py` | POST/GET | `/trade/order`, `/trade/quote`, `/trade/state` | 下单/实时报价/交易状态 |
| `routes_qmt.py` | GET | `/qmt/health`, `/qmt/positions`, `/qmt/orders` | QMT 健康/持仓/订单 |
| `routes_tv.py` | GET | `/tv/history`, `/tv/symbols`, `/tv/stock-search`, `/tv/stock-info` | TradingView 图表数据 |
| `routes_sse.py` | GET/DELETE | `/sse/paper-progress`, `/sse/events` | SSE 推送/事件轮询 |
| | GET/POST/DELETE | `/sse/scheduler/status`, `/sse/scheduler/start`, `/sse/scheduler/stop`, `/sse/scheduler/pause`, `/sse/scheduler/resume`, `/sse/scheduler/jobs`, `/sse/scheduler/jobs/<job_id>`, `/sse/scheduler/jobs/<job_id>/toggle` | APScheduler 生命周期与用户 cron/interval 任务管理 |
| `routes_scheduler.py` | (included in sse scheduler routes above) | | 调度器路由 |
| `routes_reports.py` | GET/POST/PATCH | `/reports/list`, `/reports/pptx`, `/reports/save`, `/reports/compare`, `/reports/<report_id>/audit` | 报告归档/PPTX 下载/保存/正文对比/AI 审计标注 |
| `routes_dashboard.py` | GET | `/dashboard/overview` | 聚合仪表板数据 |
| `routes_screener.py` | GET | `/market/screener` | 技术选股器 |
| `routes_ai_agent.py` | POST | `/ai/analyze` | AI 代理分析 |
| `routes_portfolio.py` | GET | `/portfolio/risk`, `/portfolio/attribution` | 组合风险/Brinson 归因 |
| `routes_ops.py` | GET/POST | `/ops/audit`, `/ops/tasks`, `/ops/tasks/<task_id>`, `/ops/tasks/<task_id>/cancel`, `/ops/stats`, `/ops/scheduler/status` | 运维审计/任务查询/取消/统计/调度器状态 |
| `routes_watchlist.py` | GET/POST | `/watchlist`, `/watchlist/add`, `/watchlist/remove`, `/watchlist/batch-analyze` | 自选股 CRUD/批量分析 |
| `routes_notifications.py` | POST/GET/PUT/DELETE | `/notifications/test-webhook`, `/notifications/dingtalk`, `/notifications/email`, `/notifications/desktop`, `/notifications/dispatchers`, `/notifications/events`, `/notifications/consumer/start`, `/notifications/consumer/stop` | 通知渠道管理与推送 |
| `routes_alerts.py` | CRUD | `/alerts/rules`, `/alerts`, `/alerts/<id>/ack`, `/alerts/check` | 预警规则/事件管理 |
| `routes_analysis.py` | POST | `/analysis/watchlist` | 自选股技术分析 |
| `routes_admin.py` | GET/POST | `/admin/backend`, `/admin/backend/config`, `/admin/health/sync-ch` | 后端切换/配置/CH 同步触发 |
| `routes_strategy_monitor.py` | (included) | | 策略监控路由 |
| `__init__.py` | GET | `/api/v1/health` | 健康检查 |

---

## 9. CLI 命令行工具

**路径**: `cli/` + `scripts/`

### 9.1 Typer CLI

**文件**: `cli/main.py` (root level)

```bash
# 启动 WebUI
tradingagents webui --port 5001 --open-browser

# 快速回测
tradingagents backtest 000001.SZ --strategy MovingAverageTrend --start 2024-01-01 --end 2025-12-31

# 主分析入口
tradingagents analyze --checkpoint

# 打印 A 股能力蓝图
tradingagents astock-blueprint
```

### 9.2 分析流程

```
1. get_user_selections()  → 8 步交互式向导
   - 股票代码、日期范围、语言
   - 分析师选择、深度
   - LLM 提供商、思维代理、推理配置

2. A 股符号 → AStockGraphRuntime → run_astock_research_bridge → AStockReport

3. 非 A 股符号 → TradingAgentsGraph (多智能体流式)

4. Rich TUI 渲染:
   - 头部: 项目信息
   - 进度: 智能体状态表
   - 消息: 工具调用 + 消息
   - 报告: 实时报告预览
   - 底部: 统计信息
```

### 9.3 运维脚本

| 脚本 | 用途 |
|------|------|
| `scripts/astock_db_tool.py` | AStock 数据库管理 |
| `scripts/astock_pg_tool.py` | PostgreSQL 管理 |
| `scripts/astock_sync_ch.py` | ClickHouse 数据同步 |
| `scripts/run_astock_api.py` | API 服务器启动 |
| `scripts/verify_astock_live_pipeline.py` | 实时管线验证 |
| `scripts/hermes_codex_git_gate.py` | CI 门控自动化 |
| `scripts/hermes_phase_loop.sh` | 阶段循环 Shell 脚本 |
| `scripts/check_astock_live_research_env.py` | 环境检查 |
| `scripts/smoke_structured_output.py` | LLM 结构化输出冒烟测试 |

---

## 10. 部署与运维

### 10.1 Docker Compose

**文件**: `docker-compose.yml`

```yaml
services:
  app:         # Flask API (gunicorn, port 5001)
  postgres:   # PostgreSQL 16 (port 5433)
  clickhouse: # ClickHouse 24.12 (ports 8123/9000)
  pgadmin:    # PGAdmin (port 5050, profile: admin)
```

### 10.2 Dockerfile

多阶段构建：
1. **builder**: 安装依赖 + gunicorn
2. **runtime**: python:3.12-slim + curl + 非 root 用户

### 10.3 初始化脚本

| 文件 | 用途 |
|------|------|
| `deploy/pg_init/01_extensions.sql` | PG 扩展（pg_stat_statements, uuid-ossp）、schema、权限 |
| `deploy/ch_init/01_create_tables.sql` | CH 12 张 MergeTree 表 |

### 10.4 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ASTOCK_DB_BACKEND` | `duckdb` | 当前后端 |
| `ASTOCK_DB_PATH` | `~/.tradingagents/astock/astock.duckdb` | DuckDB 路径 |
| `PG_HOST` | `localhost` | PG 主机 |
| `PG_PORT` | `5432` | PG 端口 |
| `PG_DB` | `astock` | PG 数据库 |
| `PG_USER` | `astock` | PG 用户 |
| `PG_PASSWORD` | `astock_prod_2026` | PG 密码 |
| `PG_POOL_SIZE` | `20` | PG 连接池 |
| `CH_HOST` | `http://localhost:8123` | CH HTTP 地址 |
| `CH_USER` | `astock` | CH 用户 |
| `CH_PASSWORD` | `astock_ch_2026` | CH 密码 |
| `FLASK_ENV` | `production` | Flask 环境 |

### 10.5 配置文件

| 文件 | 用途 |
|------|------|
| `.env.example` | 环境变量模板 |
| `.env.enterprise.example` | 企业配置模板 |
| `pyproject.toml` | 项目元数据 |

---

## 11. 测试覆盖

**路径**: `tests/`

当前全量回归基线：`1074 passed, 15 skipped, 7 warnings, 120 subtests passed`（2026-07-07，`.venv/bin/python -m pytest -q`）。

64 个测试文件，关键测试：

| 测试文件 | 覆盖模块 |
|---------|----------|
| `test_astock_api.py` | Flask API 端点 (52 用例) |
| `test_astock_store.py` | DuckDB/PG 存储层 |
| `test_astock_backtest.py` | 回测引擎 |
| `test_astock_strategies.py` | 策略实现 |
| `test_astock_paper_trader.py` | 模拟交易 |
| `test_astock_qmt_bridge.py` | QMT 桥接 |
| `test_astock_qmt_execution.py` | QMT 执行 |
| `test_astock_scheduler.py` | 交易调度 |
| `test_astock_sse.py` | SSE 推送 |
| `test_astock_blueprint.py` | 蓝图构建 |
| `test_astock_web.py` | Web UI 路由 |
| `test_astock_interface_analyst.py` | 分析师接口 |
| `test_astock_data_sources.py` | 数据源 |
| `test_astock_provider_fixtures.py` | 提供商夹具 |
| `test_astock_live_providers.py` | 实时提供商 (需环境变量) |
| `test_astock_calendar.py` | 交易日历 |
| `test_astock_adjustment.py` | 复权因子 |
| `test_astock_anti_crawl.py` | 反爬机制 |
| `test_astock_execution_risk_gate.py` | 风控门控 |
| `test_astock_graph_runtime.py` | 图运行时 |
| `test_astock_graph_bridge.py` | 图桥接 |
| `test_astock_phases_33_38.py` | 阶段 33-38 |
| `test_astock_phase30.py` | 阶段 30 |
| `test_astock_phase31.py` | 阶段 31 |
| `test_astock_phase9_contracts.py` | 阶段 9 契约 |
| `test_astock_tv_routes.py` | TradingView 路由 |
| `test_astock_market_analyzer.py` | 市场分析器 |
| `test_astock_optimizer.py` | 优化器 |
| `test_astock_batch_backtest.py` | 批量回测 |
| `test_astock_strategies.py` | 策略 |
| `test_astock_ppt.py` | PPT 报告 |
| `test_astock_cli_report.py` | CLI 报告 |
| `test_astock_diagnosis.py` | 诊断 |

---

## 12. 模块依赖关系图

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
    └─► 各提供商 SDK (openai, anthropic, google, azure)

tradingagents/dataflows/
    │
    └─► Yahoo Finance / Alpha Vantage / Reddit / StockTwits

tradingagents/graph/
    │
    └─► langgraph (可选依赖)
```

---

## 附录 A: 关键数字汇总

| 指标 | 数量 |
|------|------|
| 默认 provider 工厂 | 7（Akshare/Tencent/Mootdx/Cninfo/Iwencai/QMT/BaoStock + TDX Provider 独立） |
| 策略数量 | 15 (13 单股 + 2 组合，含 combiners/portfolio) |
| 数据库表 | 32 (DuckDB/PG) + 12 (CH OLAP) |
| 索引 | 28 |
| Flask API route decorators | 118（27 个 API 蓝图，109 个唯一路径） |
| Web UI | 30 个模板文件 |
| 测试文件 | 64 |
| 支持的 LLM 提供商 | 10+ |
| 数据能力 | 22 |

## 附录 B: 版本历史

详细版本历史见 [../CHANGELOG.md](../CHANGELOG.md)。

| 变更 | 说明 |
|------|------|
| 2026-07-07 | 校准全量数字：118 route decorators (27 蓝图/109 唯一路径)、30 模板、15 策略、64 测试文件、回归基线 1074 passed |
| 2026-07-05 | 同步当前代码基线：32 张 DuckDB/PG 表、117 条 `/api/v1` route、29 个 Web 模板、63 个测试文件 |
| 2026-06-28 | 完整功能文档，三后端架构，12 策略，8 适配器，60+ API 端点 |
