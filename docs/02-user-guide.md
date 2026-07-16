# 用户指南

> 用户手册、快速入门、术语表和策略开发指南的整合文档。

## 目录

- [1. 用户手册](#1-用户手册)
- [2. 快速入门](#2-快速入门)
- [3. 术语表](#3-术语表)
- [4. 策略开发指南](#4-策略开发指南)

---

## 1. 用户手册

# A 股定制模块用户手册

本文档面向最终用户（投资研究者、量化策略验证者、交易员），提供从首次使用到核心功能操作的完整指南。

### 系统定位

TradingAgents-Astock 是**投研分析 + 策略验证 + 模拟盘 + 受控执行试运行平台**。

**可以做：**
- AI 辅助的 A 股研究报告生成
- 策略回测与参数优化
- 模拟盘试跑
- 查看 QMT managed mock/read-only 边界状态（不接真实券商）

**不能做：**
- 自动实盘交易（默认不触发真实交易）
- 保证盈利的投资建议
- 实时无误的数据服务

### 首次使用

#### 安装

参见 [快速入门](#2-快速入门)。

#### 启动 WebUI

```bash
.venv/bin/python scripts/run_astock_api.py --port 5860
```

浏览器访问 http://127.0.0.1:5860。该模式只提供分析、数据查看、报告和回测；交易、模拟盘、QMT 与组合执行不可用。

首次运行请先安装本地运行所需依赖：`.venv/bin/python -m pip install -e '.[astock-providers,test]'`。启动器只允许绑定 `127.0.0.1`、`::1` 或 `localhost`，避免本地无认证模式暴露到局域网。K 线查询默认只读本地库：首次使用请在 Data Hub 发起刷新，或显式请求 `GET /api/v1/market/kline?symbol=600519.SH&refresh=1`；响应中的 `data_state=not_initialized` 表示本地库尚未初始化，而不是已获得空的真实行情。

#### 启动 CLI

```bash
python3 -m cli.main run-analysis
```

### AI 研究报告

#### 生成研究报告

1. 在 WebUI 的 **AI Research Center** 输入股票代码（如 `600519.SH`）
2. 选择研究模式（`live_research` 或 `deterministic_verification`）
3. 点击运行

系统将生成包含以下内容的报告：
- 五层数据摘要（行情、研报、新闻、基础数据、公告）
- 多空辩论结论
- Advisory 决策结果（ResearchConclusion → TraderProposal → RiskDecision → PortfolioDecision）

#### 查看报告

- **WebUI**：AI Research Center → Reports 标签查看历史报告
- **CLI**：报告保存在 `~/.tradingagents/reports/` 目录
- **PPT**：可通过 API 生成 PPT 格式报告

#### 报告标注

每份报告包含：
- 数据来源（provider）
- 生成时间
- 使用的模型名称
- Advisory-only 标记（仅供参考，不构成投资建议）

### 策略回测

#### 运行单次回测

1. 进入 **Strategy Lab** → 回测
2. 选择策略（MACD 趋势、布林带均值回归、网格交易等 10 种）
3. 设置标的、时间区间、参数
4. 点击运行

#### 查看回测结果

回测结果包含：
- 收益指标（收益率、Sharpe、最大回撤）
- 净值曲线
- 交易明细
- 数据假设（复权方式、成本模型、T+1 约束等）
- 反偏差状态（是否样本外、是否有 look-ahead bias）

#### 参数优化

1. 进入 **Strategy Lab** → 优化
2. 选择策略和参数搜索空间
3. 设置 Top N 和评分方式
4. 运行后查看 Top N 参数组合

优化使用复合评分：`0.35*Sharpe + 0.30*Return - 0.25*Drawdown + 0.10*TradeFrequency`

#### 策略对比

1. 进入 **Strategy Lab** → 对比
2. 选择多个策略和参数组合
3. 查看指标对比和净值曲线叠加

### 模拟盘

#### 启动模拟盘

1. 进入 **Trading & Execution** → Paper
2. 系统显示虚拟资金、虚拟持仓
3. 可发起虚拟订单

#### 查看模拟盘状态

- 虚拟资金余额
- 虚拟持仓
- 虚拟成交记录
- 风控拦截记录

#### 注意事项

- 模拟盘结果不代表真实交易表现
- 所有交易标注为 `paper` 能力等级
- 不涉及真实账户和真实资金

### 受控执行

#### 前置条件

- 当前范围为 `managed` 模拟/只读模式
- 不接入真实券商，不查询真实 QMT 委托，不启用自动实盘交易
- QMT 真实接入统一列为 P3 延后项，需另行完成权限、风控、审计和回滚验收

#### 执行流程

1. 进入 **Trading & Execution** → Managed
2. 系统显示当前模式（managed / mock / read-only）
3. 发起模拟或受控交易请求
4. 风控门检查（ATR 止损、最大单笔、最大持仓等）
5. 人工确认
6. 确认后仅进入当前支持的模拟/只读执行链路

#### 安全机制

- **Kill Switch**：一键阻断所有后续交易
- **风控门**：每笔交易前的自动检查
- **人工确认**：managed 模式下每笔交易必须人工确认
- **券商边界**：QMT 页面只展示 mock/read-only 状态；真实券商接入为 P3 暂缓

### 数据与健康

#### 查看数据状态

进入 **Data & Ops** → 数据健康，查看：
- 各数据源状态（ok/stale/fallback/mock）
- 数据新鲜度
- 最后刷新时间

#### 手动刷新数据

```bash
# 刷新 K 线数据
curl -X POST http://localhost:8080/api/v1/data/refresh/kline \
  -H "Content-Type: application/json" \
  -d '{"symbol": "600519.SH"}'

# 刷新全部数据
curl -X POST http://localhost:8080/api/v1/data/refresh/all
```

#### 缓存管理

- 查看缓存状态：`GET /api/v1/cache/status`
- 清理缓存：`POST /api/v1/cache/clear`

### 龙头与市场分析

#### 龙头决策

进入 **Market Leaders** 查看：
- 动量总览
- 候选池（含入池/出池理由）
- 板块强弱
- 资金线索（龙虎榜、北向资金）

#### K 线图

- 支持 7 种周期：1m/5m/30m/60m/日/周/月
- 27 个技术指标
- 17 种画线工具

### 风险提示

以下页面必须阅读风险提示：

| 页面 | 必须提示 |
|---|---|
| AI Research | AI 结论仅供研究参考 |
| Strategy Lab | 回测不代表未来收益 |
| Market Leaders | 候选池不构成买入建议 |
| Trading | 明确 research/paper/managed/live-ready 模式；当前 managed 不接真实券商 |
| Paper | 虚拟资金、虚拟成交、非真实账户 |
| QMT/Managed | 明确 mock/read-only，真实连接检查和真实委托查询均禁用 |
| Data & Ops | 数据延迟、fallback、provider 状态 |

### 支持与反馈

- 产品文档：[README.md](README.md)
- 原 TradingAgents 社区：[Discord](https://discord.com/invite/hk9PGKShPK) | [GitHub](https://github.com/TauricResearch)


---

## 2. 快速入门

# A 股定制模块快速上手

### ## 前置要求

- Python 3.12（最低 3.10，推荐 3.12）
- pip 或 conda 环境管理器
- 已安装 Git

### 安装

```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents

# 创建虚拟环境
conda create -n astock python=3.12
conda activate astock

# 安装基础包
pip install .

# 安装 A 股可选依赖（数据源）
pip install -e ".[astock-providers,test]"
```

### 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入必要的 API key
# 至少需要 LLM_API_KEY 用于 AI Research
nano .env
```

最少必需配置：

```bash
LLM_API_KEY=your_key_here
TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE=deterministic_verification
```

如需启用真实 LLM 分析：

```bash
TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE=live_research
LLM_API_KEY=your_key_here
```

### 启动 WebUI

```bash
.venv/bin/python scripts/run_astock_api.py --port 5860
```

浏览器访问 http://127.0.0.1:5860；这是本地正式版的唯一 Web 入口。

### 本地 K 线与分钟线增量刷新

所有 Web 查询先读取应用热库，再读取永久本地库 `kline/kline.duckdb`；仅在显式刷新时才访问 provider。首次加载或更新日线：

```bash
curl 'http://127.0.0.1:5860/api/v1/market/kline?symbol=600519.SH&interval=1d&refresh=1'
```

分钟线使用相同接口，例如 5 分钟 K：

```bash
curl 'http://127.0.0.1:5860/api/v1/market/kline?symbol=600519.SH&interval=5m&refresh=1'
```

刷新会从该 `symbol:interval` 的本地水位增量拉取（分钟线保留两根重叠 bar），校验时间与 OHLC 数值后 upsert 至热库和永久库。网络载荷缺少 `bars/items/kline`、缺失 OHLC、日期非法或数值非法时，接口返回 `422 invalid_kline_data`；不会把未验证数据返回页面。批量刷新使用 `POST /api/v1/data/jobs/refresh`，并支持 `1m`、`5m`、`15m`、`30m`、`60m` 等周期。

### 启动 CLI

```bash
# 通用分析（US / 多市场）
tradingagents analyze
# 或
python -m cli.main

# A 股蓝图打印
tradingagents astock-blueprint
```

### 运行测试

```bash
# A 股主链回归
python3 -m pytest tests/test_astock_graph_runtime.py tests/test_astock_graph_bridge.py -q

# 全仓回归
python3 -m pytest -q
```

### ## 5b. 启动 Flask REST API

```bash
# 默认端口 5860
python scripts/run_astock_api.py

# 本地正式版：只开放分析、报告、数据和回测（推荐）
.venv/bin/python scripts/run_astock_api.py --port 5860

# 禁用 WebUI
python scripts/run_astock_api.py --no-web

# 自定义端口
python scripts/run_astock_api.py --port 5002
```

### ## 5c. 启动 DuckDB 数据库工具

```bash
# 列出表
python scripts/astock_db_tool.py list-tables

# 查看统计
python scripts/astock_db_tool.py stats

# 导出数据
python scripts/astock_db_tool.py export --format csv

# 查询
python scripts/astock_db_tool.py query "SELECT * FROM kline_bars LIMIT 10"
```

### ## 5d. Live Research 验证

```bash
# 检查环境
python scripts/check_astock_live_research_env.py

# 端到端验证
python scripts/verify_astock_live_pipeline.py

# 结构化输出冒烟测试
python scripts/smoke_structured_output.py
```

### 核心工作流

| 工作流 | 入口 | 说明 |
|---|---|---|
| AI 研究 | WebUI → AI Research Center 或 CLI `tradingagents analyze` | 输入 symbol，生成研究报告 |
| 回测 | WebUI → Strategy Hub → 回测 | 选择策略、区间、参数，运行回测 |
| 策略优化 | WebUI → Strategy Hub → 优化 | grid search 最优参数 |
| 模拟盘 | WebUI → Paper Trading / API `POST /paper/cycle` | 虚拟资金试跑 |
| 受控执行 | WebUI → Trading → Managed / QMT | 需要 QMT 环境和人工确认 |
| 批量回测 | API `POST /backtest/batch` | 多策略批量回测 |
| 数据管理 | API `POST /data/refresh/*` + DuckDB CLI | 数据刷新、导入/导出 |
| 龙虎榜/北向 | WebUI → Market Leaders 对应 Tab | 主力资金追踪、沪深股通资金流；旧 URL 自动跳转 |
| 板块轮动 | WebUI → Market Leaders → 板块强弱 | ECharts treemap 热力图；`/sectors` 自动跳转 |
| 动量轮动 | WebUI → Market Leaders → 龙头决策 / 动量轮动 | 旧 `momentum_dashboard` / `momentum_rotation` URL 自动跳转 |

### 常见问题

- **Q: 数据源连接失败？**
  A: 检查 `03-operations.md` 中的 provider 配置说明。

- **Q: AI 分析失败？**
  A: 确认 `.env` 中有有效的 API KEY，且 `TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE` 设置为 `live_research`。

- **Q: WebUI 打不开？**
  A: 确认端口未被占用，或改用 `.venv/bin/python scripts/run_astock_api.py --port 其他端口`。

- **Q: Flask API 启动失败？**
  A: 确认已安装 `pip install '.[astock-providers]'`，且 DuckDB 数据库文件路径可写。

- **Q: WebUI 如何启动？**
  A: 唯一入口是 `.venv/bin/python scripts/run_astock_api.py`。默认访问 `http://127.0.0.1:5860/dashboard`；React、Streamlit 和旧动量启动器不属于当前产品面。

### 下一步

- 完整产品需求：[04-development.md](04-development.md)
- 当前状态：[`docs/phase-archive.md`](docs/phase-archive.md)
- 文档体系入口：[`README.md`](README.md)
- 数据库白皮书：[`database_module_whitepaper.md`](database_module_whitepaper.md)
- 全功能文档：[`full_function_documentation.md`](full_function_documentation.md)


---

## 3. 术语表

# A 股定制模块术语表

本文档统一定义 TradingAgents-Astock 中使用的专业术语，供产品、开发和用户参考。

### 核心概念

| 术语 | 英文 | 定义 |
|---|---|---|
| 研究模式 | research | 系统处于只读分析状态，不执行任何交易动作 |
| 模拟盘 | paper | 虚拟资金、虚拟成交的试跑模式，不涉及真实账户 |
| 受控执行 | managed | 需要风控门和人工确认后方可执行的交易模式 |
| 实盘就绪 | live-ready | 已通过实盘准入 checklist 的真实执行能力 |
| 占位数据 | mock | 演示或测试用的模拟数据，不得用于实盘 |
| 降级 | degraded | 部分数据源或功能不可用时的降级运行状态 |

### 数据相关

| 术语 | 英文 | 定义 |
|---|---|---|
| 数据源 | data source | 提供行情、财务、新闻等数据的第三方服务 |
| Provider | provider | 具体数据源实现（如 mootdx、akshare、Tencent） |
| 主源 | primary | 首选数据源，优先使用 |
| 备源 | fallback | 主源失败时自动切换的备用数据源 |
| 数据新鲜度 | freshness | 数据从生成到当前的时间差 |
| 数据质量 | data quality | 数据的完整性、准确性和时效性综合评估 |
| 数据快照 | data snapshot | 某一时刻的数据状态副本，用于可复现分析 |
| 血缘 | lineage | 数据来源、转换和使用的完整追溯链 |
| 复权 | adjustment | 股票除权除息后的价格调整（前复权/后复权/不复权） |
| 停复牌 | suspension/resumption | 股票暂停或恢复交易的状态 |
| 涨跌停 | limit_up/down | A 股单日价格波动上限（±10% 或 ±20%） |
| ST/退市 | ST/delisting | 特别处理和退出市场的证券状态 |

### 研究与分析

| 术语 | 英文 | 定义 |
|---|---|---|
| 五层数据 | five-layer data | 行情层、研报层、新闻层、基础数据层、公告层 |
| 研究链 | research chain | AStockAnalyst → Bull/Bear Researcher → Research Manager 的分析流程 |
| advisory 链 | advisory chain | ResearchConclusion → TraderProposal → RiskDecision → PortfolioDecision 的结构化决策链 |
| advisory-only | advisory-only | AI 输出仅为研究参考，不直接触发真实交易 |
| 多空辩论 | bull/bear debate | Bull Researcher 和 Bear Researcher 的对抗式分析 |
| 研究结论 | ResearchConclusion | 研究链输出的结构化结论 |
| 交易提案 | TraderProposal | 基于研究结论的交易建议 |
| 风控决策 | RiskDecision | 风险评估和风控建议 |
| 组合决策 | PortfolioDecision | 最终的投资组合建议 |
| 幻觉 | hallucination | AI 生成不准确或虚构内容的现象 |
| Prompt | prompt | 发送给 LLM 的指令模板 |

### 回测与策略

| 术语 | 英文 | 定义 |
|---|---|---|
| 回测 | backtest | 使用历史数据验证策略表现 |
| 策略注册表 | strategy registry | 统一管理所有策略元数据的注册中心 |
| 参数优化 | parameter optimization | 通过 grid search 等方法寻找最优策略参数 |
| 复合评分 | composite score | `0.35*Sharpe + 0.30*Return - 0.25*Drawdown + 0.10*TradeFrequency` |
| Survivorship bias | 幸存者偏差 | 只使用当前存在的股票数据进行回测导致的偏差 |
| Look-ahead bias | 前瞻偏差 | 回测中使用了当时不可知的未来信息 |
| 未来函数 | look-ahead function | 在回测中引用了未来数据的代码逻辑 |
| 样本外 | out-of-sample | 未用于参数优化的测试数据区间 |
| Walk-forward | walk-forward | 滚动窗口式的回测验证方法 |
| 成本模型 | cost model | 佣金、印花税、滑点等交易成本的模拟 |
| Benchmark | benchmark | 回测对比的基准（如沪深300） |

### 交易与执行

| 术语 | 英文 | 定义 |
|---|---|---|
| 订单生命周期 | order lifecycle | 订单从创建到最终状态的全过程 |
| 部分成交 | partial fill | 订单只成交了部分数量的情况 |
| 拒单 | rejected | 订单被券商或风控系统拒绝 |
| 撤单 | cancellation | 用户主动撤销未成交订单 |
| Reconciliation | 对账 | 本地订单状态与券商回报的比对 |
| Kill switch | 紧急停机 | 一键阻断所有后续交易的安全机制 |
| 风控门 | risk gate | 下单前执行的风险检查关卡 |
| ATR 止损 | ATR stop-loss | 基于平均真实波幅的动态止损 |
| 人工确认 | manual confirmation | 交易执行前需要用户显式确认的步骤 |
| QMT | QMT | 迅投量化交易平台，用于 A 股券商接口桥接 |

### 系统与运维

| 术语 | 英文 | 定义 |
|---|---|---|
| DuckDB | DuckDB | 本地嵌入式列式数据库，用于数据存储 |
| Cache | 缓存 | 内存或磁盘缓存，加速数据访问 |
| SSE | SSE | Server-Sent Events，服务端推送实时事件 |
| TaskRun | 任务运行 | 数据刷新、回测、AI 研究等任务的执行记录 |
| AuditEvent | 审计事件 | 关键操作的审计追踪记录 |
| Runtime Profile | 运行时配置 | 控制系统运行模式的配置集 |
| Deterministic Verification | 确定性验证 | 使用 BridgeLLM 的离线验证模式 |
| Live Research | 实时研究 | 使用真实 LLM 的研究模式 |
| Capability | 能力等级 | 标注 API/页面能力的标签（research/paper/managed/live-ready） |
| Envelope | 响应信封 | API 响应的标准包装结构（success/data/error/meta） |

### 文档与治理

| 术语 | 英文 | 定义 |
|---|---|---|
| Phase | 阶段 | 一次迭代的交付单元，有明确的 scope 和验收标准 |
| ADR | Architecture Decision Record | 架构决策记录 |
| Traceability Matrix | 需求追踪矩阵 | 需求 ID 到模块/API/测试/Phase 的映射表 |
| Risk Register | 风险登记表 | 项目风险的登记和跟踪表 |
| Scope Register | 范围登记表 | 纳入/暂不纳入范围的登记 |
| ECC | Embedded Continuous Checking | 嵌入式持续检查机制 |
| Hermes | Hermes | 任务调度器和 phase owner |
| DeepSeek | DeepSeek | 代码实现引擎 |
| Codex | Codex | 独立 review gate |


---

## 4. 策略开发指南

# A 股策略开发规范

| 更新时间：2026-07-08 |

本文档承接 Hermes `tradingagents-core` skill 的 Section 12 蒸馏内容，用于约束后续 Strategy Lab、回测、优化器和动量轮动相关开发。代码实现仍以仓库当前状态为准；本文提供新增策略和重构策略模块时的工程边界。

### 策略生命周期

标准单标的策略必须继承 `StrategyBase`，并实现统一入口：

```python
generate_signals(data: pd.DataFrame) -> pd.Series
```

约定：

- 输入必须是按时间升序排列的行情数据，至少包含 `close`，按策略需要补充 `open`、`high`、`low`、`volume` 等列。
- 输出必须是与输入索引对齐的整数信号序列：`1` 表示买入或持有多头，`0` 表示空仓或无动作，`-1` 表示卖出或退出。
- 策略内部必须处理预热期 NaN，不允许把 NaN 信号直接交给回测引擎。
- 策略参数必须通过构造参数或配置字典显式声明，不能依赖页面或 API 的隐式默认值。

### 信号生成模式

新增策略优先复用以下五类模式，避免重复发明不可验证的信号结构：

| 模式 | 典型用途 | 约束 |
|---|---|---|
| Crossover | 均线、MACD、价格突破 | 明确快慢线窗口，处理交叉当天和连续持有规则 |
| Deviation | 布林带、均值回归、估值偏离 | 明确偏离阈值、回归退出条件和极端行情保护 |
| Momentum | 龙头、行业轮动、强弱排序 | 明确 lookback、调仓周期、候选池和等权/加权规则 |
| Threshold | RSI、成交量放大、波动率过滤 | 明确阈值、滞回区间和重复触发去抖 |
| Grid | 网格交易、震荡策略 | 明确网格间距、资金分配、止损和趋势失效条件 |

### 注册点

新增或迁移策略时，至少检查三个注册点：

- `tradingagents/astock/execution/__init__.py`：导出策略类，保证包级导入稳定。
- `tradingagents/astock/api/routes_backtest.py` 的 `_STRATEGY_REGISTRY`：保证 API、WebUI 和回测入口可选择该策略。
- `tradingagents/astock/api/routes_market.py` 的 `AVAILABLE_STRATEGIES`：保证市场分析、推荐策略和页面元数据可见。

如果后续 Phase 30 建立统一 Strategy Registry，上述注册点应收敛到单一 registry，再由 API/WebUI 派生展示配置。

### 优化器评分

参数优化默认使用复合评分，避免只追逐收益或交易次数：

```text
score = 0.35 * Sharpe + 0.30 * Return - 0.25 * Drawdown + 0.10 * TradeFrequency
```

落地要求：

- Sharpe、收益、回撤和交易次数必须先做边界归一化，再进入复合评分。
- 最大回撤必须作为惩罚项，不能被高收益完全掩盖。
- 无交易、极低交易次数或数据不足的参数组合不能排在前列。
- 优化结果必须记录参数、得分、核心指标、数据区间、成本模型和 benchmark。

### 多股票组合策略

多股票策略有两种模式：

| 模式 | 适用场景 | 边界 |
|---|---|---|
| Standalone 组合模式 | 动量轮动、行业轮动、候选池排序 | 可不继承 `StrategyBase`，但必须输出组合净值、持仓、调仓记录和 benchmark |
| StrategyBase 兼容模式 | 单标的策略批量运行、组合回测引擎统一调度 | 每只股票独立生成信号，再由组合层处理仓位和风控 |

动量轮动当前更接近 Standalone 组合模式。Phase 30 重构时应把它纳入 Strategy Lab，但不应强行改成单标的 `StrategyBase`。

### 数据拉取规范

baostock 批量拉取必须使用游标模式：

```python
while rs.next():
    row = rs.get_row_data()
```

工程要求：

- 优先批量获取并本地聚合，避免单股票、单日期、单字段循环请求。
- 对远程 provider 失败要保留 provider、symbol、日期范围和错误原因。
- live provider 结果必须通过 `tradingagents/astock/verification_provenance.py` 或运行日志记录验证环境。
- 回测不能直接依赖实时接口，应优先使用 DuckDB/store 或可复现数据快照。

### 已修复但必须防复发的问题

买入逻辑曾出现 `net_cost > cash` 永远为真的风险。新增回测或模拟盘逻辑时必须保留迭代收敛方案：

- 先按现金估算最大可买数量。
- 计算含佣金、印花税、过户费等费用后的 `net_cost`。
- 若 `net_cost > cash`，按费用重新缩小数量并重复校验。
- 最终仍超出现金时必须放弃交易或返回明确错误，不能产生负现金。

### 常见陷阱

- 参数爆炸：网格搜索必须限制组合数，必要时分层搜索或使用 Top N 初筛。
- NaN 预热：指标窗口期产生的 NaN 必须在策略内转成 `0` 或延后信号生效。
- Mock 无趋势：测试数据如果没有趋势或波动，趋势策略和动量策略会出现假阴性。
- 未来函数：策略只能使用当前 bar 及之前数据，不得读取未来收益、未来最高/最低或回测结果。
- 成交约束：涨跌停、停牌、T+1、成交量容量和滑点必须逐步进入统一回测约束。
- 过拟合：优化结果必须展示样本内/样本外、walk-forward 或至少明确标记“未做样本外验证”。

### Phase 30 接入要求

Strategy Lab 重构前，新增策略必须同时更新：

- 本文档。
- Strategy Lab 目标模块。
- `BACKLOG.md` 中 `BL-100` 的完成标准。
- 对应测试：策略信号、回测结果、优化器排序、API registry。

Phase 30 的目标不是增加更多策略，而是把现有策略、回测、优化、绩效、对比和动量轮动收敛到一个可审计的产品/工程模块。


---

# Appendix: Frequently Asked Questions

# A 股定制模块常见问题

## 安装与环境

### Q1: 支持哪些 Python 版本？

推荐使用 **Python 3.12**。最低支持 Python 3.10。

### Q2: 安装失败，提示缺少某些依赖？

A 股定制模块有额外的可选依赖。安装时指定：

```bash
pip install -e ".[astock-providers,test]"
```

### Q3: conda 环境创建失败？

尝试使用 venv 替代：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[astock-providers,test]"
```

### Q4: WebUI 启动后页面打不开？

- 确认端口未被占用（默认 5860）
- 尝试更换端口：`.venv/bin/python scripts/run_astock_api.py --port 5000`
- 确认防火墙未阻止本地端口

## 数据源

### Q5: 数据获取失败怎么办？

1. 进入 **Data & Ops** → 数据健康页查看各 provider 状态
2. 检查 `.env` 中是否有必要的配置
3. 部分 provider（如 iwencai）需要额外配置 cookie
   - 参见 [`03-operations.md`](03-operations.md)

### Q6: 数据延迟或过期怎么办？

- 手动刷新数据：`POST /api/v1/data/refresh/all`
- 查看数据新鲜度标签（`ok`/`stale`/`partial`/`fallback`/`mock`）
- 如果数据标记为 `stale`，系统会阻止 live-ready 操作

### Q7: 为什么有些数据显示为 mock？

当主数据源不可用时，系统会 fallback 到备源。如果备源也不可用，会使用 mock 数据。
Mock 数据会在页面上显著标注，不得用于实盘。

### Q8: 如何确认数据源授权？

参见 [`03-operations.md`](03-operations.md)。
未确认授权的数据源标记为 `research-only`。

## AI 研究

### Q9: AI 分析失败，提示 LLM 不可用？

- 确认 `.env` 中设置了 `DEEPSEEK_API_KEY`（或其他 LLM provider key）
- 确认 `TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE=live_research`
- 如果 LLM 不可用，系统会降级到 `deterministic_verification` 模式（使用 BridgeLLM）

### Q10: AI 输出的结论可靠吗？

AI 输出标注为 `advisory-only`，仅供参考，不构成投资建议。
AI 可能存在幻觉、引用不完整或对行情理解错误。
每个 AI 输出包含模型名称、prompt 版本、数据快照 ID 和引用来源，可用于复查。

### Q11: 如何查看 AI 的审计信息？

每个 AI 研究任务记录：
- 模型名称和 provider
- Prompt 版本
- 输入数据快照 ID
- 引用来源
- 生成时间
- Advisory-only 标记

## 回测与策略

### Q12: 回测结果和预期不符？

可能的原因：
- 数据质量问题（stale/partial/mock）
- 回测数据假设未正确设置（复权方式、成本模型、T+1 约束）
- 样本内过拟合
- Look-ahead bias 或未来函数

请检查回测结果的 `data_assumption` 字段和反偏差状态。

### Q13: 为什么优化结果中有无交易的参数组合排在前面？

优化器默认使用复合评分，无交易或数据不足的参数组合不应该排在前列。
如果出现问题，可能是策略信号生成有 NaN 泄漏。
参见 [`02-user-guide.md`](02-user-guide.md) §7。

### Q14: 回测包含涨跌停和停牌吗？

当前回测引擎对涨跌停和停牌的处理是逐步完善的。
回测结果中的 `data_assumption` 字段会说明是否应用了涨跌停不可成交、停牌不可成交等约束。

## 交易与执行

### Q15: 如何切换到实盘模式？

当前系统**不支持**自动实盘交易。
进入 `live-ready` 模式需要通过 Phase 30 Live Trading Readiness 的准入 checklist。
详见 [`03-operations.md`](03-operations.md)。

### Q16: QMT 连接失败怎么办？

- 确认 QMT 环境已安装并可运行
- 确认 `.env` 中配置了正确的 QMT 连接参数
- QMT 不可用时系统会自动降级到模拟盘
- 参见 [`03-operations.md`](03-operations.md)

### Q17: 风控门拦截了我的订单怎么办？

风控拦截会返回 `reason_code`，说明拦截原因。
常见原因：
- 超过最大单笔金额
- 超过最大持仓限制
- 超过最大日亏损
- 非交易时段
- ATR 止损触发

### Q18: Kill Switch 怎么使用？

Kill Switch 在交易页面顶部显示，激活后会阻断所有后续交易动作。
这是最重要的安全机制，建议在不确定或异常情况时立即启用。

## 系统运维

### Q19: 如何备份数据？

DuckDB 数据文件位于项目目录下的 DuckDB 存储路径。
建议定期备份整个数据目录。
参见 [`03-operations.md`](03-operations.md)。

### Q20: 如何清理缓存？

```bash
# 通过 API
curl -X POST http://localhost:8080/api/v1/cache/clear

# 或通过 WebUI
# Data & Ops → 缓存管理 → 清理
```

### Q21: 如何查看系统健康状态？

```bash
curl http://localhost:8080/api/v1/health
```

或通过 WebUI → Dashboard → 系统状态。

### Q22: 升级后数据会不会丢失？

参见 [`03-operations.md`](03-operations.md)。
Schema 变更会提供迁移脚本和回滚策略。

## 文档相关

### Q23: 从哪里了解完整的文档体系？

参见 [`docs/README.md`](README.md)。

### Q24: 如何了解 Phase 30-38 的进展？

参见 [`docs/phase-archive.md`](docs/phase-archive.md)。

### Q25: 如何报告文档中的错误？

请在 GitHub 上提交 issue，或在团队内部通过 Hermes 调度修正。
