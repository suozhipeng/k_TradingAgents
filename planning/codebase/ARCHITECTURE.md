# ARCHITECTURE

## 文档定位
- 本文档描述 **当前源码架构基线** 与 **A 股目标态架构** 的关系。
- 当前基线来自现有 `TradingAgents` 仓库。
- 目标态依据来自 `planning/codebase/ASTOCK_RESOURCE_PLAN.md` 与 `planning/a-stock-resource/`。
- 原则：**不把目标态写成已完成事实**。

---

## 1. 当前源码架构基线

### 1.1 总体基线
当前项目本质上是一个基于 **LangGraph 状态图** 的多 Agent 金融研究与决策流水线。

核心对象：`tradingagents.graph.trading_graph.TradingAgentsGraph`

当前主链路为：
1. 分析师阶段（Analyst Team）
2. 多空研究辩论阶段（Research Team）
3. 交易方案阶段（Trader）
4. 风险辩论阶段（Risk Management Team）
5. 最终组合决策阶段（Portfolio Manager）

### 1.2 当前图级顺序
```text
START
  -> [Selected Analysts in sequence]
  -> Bull Researcher
  <-> Bear Researcher   (按轮次往返)
  -> Research Manager
  -> Trader
  -> Aggressive Analyst
  -> Conservative Analyst
  -> Neutral Analyst
  -> ... (风险辩论按轮次循环)
  -> Portfolio Manager
  -> END
```

### 1.3 当前架构特点
- 优点：
  - Agent 职责划分清晰
  - 图编排透明，便于插拔新节点
  - 数据源与模型 provider 已抽象
  - 结构化输出覆盖关键决策节点
  - 支持 checkpoint / resume
- 局限：
  - 决策仍偏 LLM 文本推理主导
  - A 股专用五层数据体系和统一接口已形成基础实现，但 provider 完整度不一致，且 runtime 仍只读
  - A 股 research-only runtime 已扩展为完整 advisory chain（ResearchConclusion → TraderProposal → RiskDecision → PortfolioDecision，Phase 9），但所有 advisory 输出固定为 `actionable=false`
  - A 股默认 BridgeLLM 仅适合确定性验证，输出固定为 research-only
  - 回测引擎与模拟盘引擎已交付（Phase 10），但 QMT 实盘桥接默认 safety mode 且未接入真实券商账户
  - QMT 桥接与受控下单层已交付（Phase 11），管理模式下执行需人工确认

### 1.4 当前 A 股主链路（Phase 0–11 交付后）

```text
AStockDataRouter
  -> AStockInterface
  -> AStockAnalyst
  -> Bull Researcher
  -> Bear Researcher
  -> Research Manager
  -> Phase 9 Advisory Chain
  |    (ResearchConclusion -> TraderProposal -> RiskDecision -> PortfolioDecision)
  -> AStockGraphReport
  -> CLI / Streamlit read-only viewer
  -> { BacktestEngine (Phase 10) | PaperTrader (Phase 10) | QmtExecution (Phase 11, managed) }
```

Phase 9–11 交付后的链路扩展：

- 研究结论后进入 advisory chain，四个合约（ResearchConclusion / TraderProposal / RiskDecision / PortfolioDecision）均采用结构化 schema
- 执行层区分回测 / 模拟盘 / QMT 桥接三种模式
- QMT 桥接默认 safety mode（人工确认），auto mode 需用户显式开启
- 所有执行路径均可用，但实盘路径默认不自动下单

当前契约（advisory chain 阶段）：

- `decision_scope=research_only`
- `actionable=false`
- `execution_signal=ResearchOnly`
- 不写入交易决策记忆
- 不进入通用交易信号解析

Phase 11 执行层额外契约：

- Safety mode：每次执行操作需要人工确认（`confirmed=True`）
- ATR 止损：实时计算止损线，触发时自动拒绝下单
- QMT 降级：桥接不可用时自动走模拟盘路径
- 一切执行输出保持 `actionable=false`，直到 safety mode 下人工确认

---

## 2. A 股目标态的架构主张

根据 `planning/a-stock-resource/`，目标态不是简单给当前图换数据源，而是把系统扩展成：

**A 股投研与交易闭环系统**

其关键特征包括：
- 面向 A 股五层数据能力
- 统一的 Skill / 数据访问封装
- Web UI + 分析引擎 + 回测 + 模拟盘 + 实盘 + 风控的完整系统分层
- akshare + QMT 双数据源
- QMT 桥接与受控执行链路
- 回测验证 → 模拟盘试跑 → 实盘出击的三阶段演进

---

## 3. 目标态分层架构

### 3.1 顶层分层
目标态建议按以下层次理解：

```text
Presentation Layer
  -> Web UI / CLI / API / Notifications

Orchestration Layer
  -> LangGraph Multi-Agent Workflow

Analysis Layer
  -> Five-Layer Analysts + Research Debate + Decision Synthesis

Strategy Layer
  -> 6 Strategies (2 bull / 2 range / 2 bear)

Execution Layer
  -> Backtest Engine / Paper Trading Engine / Live Trading Engine

Data Access Layer
  -> Unified A-Stock Data Skill / Interface

Provider Layer
  -> mootdx / 腾讯财经 / akshare / iwencai / 巨潮 / QMT

Risk & Control Layer
  -> Safety Mode / Manual Confirm / ATR Stop / Trailing TP / Portfolio Risk
```

### 3.2 设计原则
- **展示层** 不直接耦合单个数据源。
- **Agent 编排层** 不直接感知 QMT 细节。
- **策略层** 位于分析结果与执行动作之间。
- **执行层** 必须区分回测、模拟盘、实盘三种模式。
- **风险控制层** 不是附属功能，而是贯穿执行全链路的横切能力。

---

## 4. 五层数据能力架构

目标态的核心变化，是把系统按五层数据能力重构，而不是按“某个 analyst 调某个公网工具”来理解。

### 4.1 五层定义
1. **行情层**
2. **研报层**
3. **新闻层**
4. **基础数据层**
5. **公告层**

### 4.2 五层能力与接口范围

#### 行情层
覆盖：
- K 线
- 五档盘口
- 逐笔成交
- PE / PB
- 市值
- 换手率

#### 研报层
覆盖：
- 研报列表
- PDF 下载
- 机构预期
- NL 语义搜索

#### 新闻层
覆盖：
- 个股新闻
- 财联社快讯
- 全球资讯

#### 基础数据层
覆盖：
- 季报 37 字段
- F10 九大类
- 基本面

#### 公告层
覆盖：
- 公告全文
- 最新摘要

### 4.3 架构含义
这五层不是展示标签，而是后续系统中：
- 分析师输入的一级来源
- API 体系的一级分类
- 页面信息架构的一级分类
- 测试矩阵的一级分类
- 缓存/容错/备源策略的一级分类

---

## 5. 数据源与供应商架构

### 5.1 供应商层
根据图片规划，目标态涉及以下来源：
- `mootdx`
- `腾讯财经`
- `akshare`
- `iwencai`
- `巨潮 cninfo`
- `QMT`

### 5.2 供应商与能力层的关系
建议从架构上把“供应商”与“能力层”解耦：

```text
Five-Layer Capability
  -> Unified A-Stock Data Interface
      -> Provider Router
          -> mootdx
          -> 腾讯财经
          -> akshare
          -> iwencai
          -> 巨潮 cninfo
          -> QMT
```

### 5.3 统一访问层的职责
统一 A 股数据访问层至少负责：
- symbol canonicalization
- 五层能力到供应商的路由
- 主源 / 备源 / 淘汰源策略
- 缓存与去重
- 空结果与错误语义统一
- 时段语义（盘前 / 盘中 / 盘后）

---

## 6. Skill / 接口封装架构

图片规划明确表达了一个重要设计：

```text
mootdx
腾讯财经
akshare
iwencai
巨潮 cninfo
   -> 合并封装 Skill / Unified Interface
   -> a-stock-data
```

### 6.1 这层为什么重要
它的作用不是“换个名字”，而是：
- 屏蔽多源接入差异
- 给 Agent、CLI、Web UI 提供统一调用入口
- 让接口迁移、故障替换、缓存策略集中发生
- 降低上层 prompt / graph / view 层对底层数据源的耦合

### 6.2 架构约束
- 上层 Analyst 不应直接知道具体供应商细节。
- 页面层不应直接拼供应商返回数据。
- 执行层不应直接依赖研报/公告原始格式。

---

## 7. 多 Agent 目标态架构

### 7.1 保留什么
目标态不是推翻现有 LangGraph，而是保留这些骨架能力：
- Analyst Team
- Research Team
- Trader / Decision synthesis
- Risk Management Team
- Portfolio / Final decision layer

### 7.2 需要改造什么
需要把当前通用金融角色，改造成围绕五层能力与 A 股语义的角色体系。

#### Analyst Team（目标态）
建议围绕五层定义输入：
- 行情分析师
- 研报分析师
- 新闻分析师
- 基础数据分析师
- 公告分析师

每类分析师都应：
- 只消费统一 A 股数据访问层
- 产出结构化中间报告
- 不直接越层做执行动作

当前代码证据：A 股分析链已有完整的只读闭环 + Phase 9 advisory chain，包含 `AStockInterface -> tools -> AStockAnalyst -> Bull/Bear/Research Manager -> ResearchConclusion -> TraderProposal -> RiskDecision -> PortfolioDecision`，合约 schema 在 `tradingagents/astock/phase9_schemas.py`，46 项回归测试通过。

#### Research Team（目标态）
- 保留多空辩论作为项目辨识度能力
- 辩论素材从“通用金融报告”切换为“五层 A 股事实报告”
- 输出应服务于后续策略评分和执行模式选择

#### Trader / Decision Layer（目标态）
- 不再只是“买卖评级翻译器”
- 更像“策略执行前的信号综合层”
- 需要明确区分：
  - 只读建议
  - 允许进入回测
  - 允许进入模拟盘
  - 允许进入实盘确认

当前状态：Phase 9 已交付完整 advisory chain（ResearchConclusion → TraderProposal → RiskDecision → PortfolioDecision），合约 schema 在 `tradingagents/astock/phase9_schemas.py`，46 项回归测试通过。
所有 advisory 输出固定为 `actionable=false`，不能进入 signal processing、交易记忆或 QMT 自动下单。
规格见 `docs/phases/phase-09-trader-risk-portfolio.md`。

#### Risk / Portfolio Layer（目标态）
- 需要显式吸收：
  - 安全模式
  - 人工确认
  - ATR 动态止损
  - 跟踪止盈
  - 组合风控
- 这层不只是文本辩论，而是执行权限与交易约束的最后关口

当前状态：Phase 9 advisory chain 已交付 A 股 `RiskDecision` 与
`PortfolioDecision` 结构化 schema。Phase 11 进一步交付了
`risk_gate.py`（ATR 止损、safety mode 人工确认门、组合风控约束）。
通用 Risk Agent 仍输出自由文本且不参与 A 股链路。

---

## 8. 策略层架构

图片规划中出现了明确的“6 策略层”：
- 2 牛市策略
- 2 震荡策略
- 2 熊市策略

### 8.1 策略层位置
策略层应位于：

```text
Five-Layer Analysis Results
  -> Research / Debate Synthesis
  -> Strategy Selection / Scoring
  -> Execution Mode (backtest/paper/live)
```

当前代码证据：仓库中没有 A 股策略层实现，`tradingagents/astock/` 仅覆盖数据、分析、运行和展示，不包含策略选择或评分模块.

### 8.2 策略层职责
- 接收五层分析结果与研究结论
- 输出策略评分与候选动作
- 定义调仓条件
- 定义退出条件
- 为回测 / 模拟 / 实盘提供统一可执行信号

### 8.3 架构价值
这层的加入，使系统不再只是“LLM 报告系统”，而是“分析 → 策略 → 执行”的可验证闭环。

---

## 9. 执行层架构：回测 / 模拟盘 / 实盘

目标态最关键的变化之一，是执行层必须显式分三级，而不是把所有动作混在同一条链路里。

当前代码证据：A 股执行层已交付 Phase 10 回测引擎（`tradingagents/astock/execution/backtest_engine.py`）、模拟盘引擎（`paper_trader.py`），以及 Phase 11 QMT 桥接（`qmt_bridge.py` / `qmt_execution.py`）。风险控制层（`risk_gate.py`）提供 ATR 止损、safety mode 和组合风控。所有执行路径默认保持 `decision_scope=research_only`、`actionable=false`、`execution_signal=ResearchOnly`。见 `docs/ASTOCK_CURRENT_STATUS.md` §2 安全边界。

### 9.1 第一阶段：回测验证
基于图片规划，回测阶段包括：
- `沪深300` 全量回测
- 时间跨度 `2023.01 → 2026.05`
- `6` 策略对比
- 周期调仓
- 完整费率模拟

架构上，回测引擎应承担：
- 历史数据加载
- 策略信号回放
- 调仓周期执行
- 成本/费率建模
- 指标统计与报表输出

### 9.2 第二阶段：模拟盘试跑
基于图片规划，模拟盘阶段包括：
- 完整交易引擎
- 调度器定时自动调仓
- 虚拟券商 + 真实费率
- SSE 流式实时进度

架构上，模拟盘引擎应承担：
- 定时触发
- 信号生成
- 虚拟成交
- 仓位账本
- 风控拦截
- 实时进度推送

### 9.3 第三阶段：实盘出击
基于图片规划，实盘阶段包括：
- `QMT` 桥接已开通
- 安全模式（默认）+ 人工确认
- 自动模式：调度器下单
- 信号生成 → 确认 → 执行
- 完整风控实时止损

架构上，实盘引擎应承担：
- 受控地把信号提交到桥接层
- 在确认点停住等待人工批准
- 记录执行上下文与审计信息
- 支持异常中断和风险熔断

---

## 10. QMT 桥接架构

图片规划给出了一个明确的双系统桥接结构：

```text
Python 3.12 Main System
  -> QmtSource (HTTP client)
  -> HTTP :58609
  -> Python 3.6.8 qmt_bridge.py
      -> xtdata -> Mini QMT (:58610)
      -> xttrader -> Full QMT
          -> 上海 / 深圳证券交易所
```

### 10.1 各层职责
#### 主系统（Python 3.12）
- 承担 Web、Agent、策略、调度、风控主逻辑
- 通过 HTTP 调用桥接层

当前代码证据：QMT 桥接已交付（`tradingagents/astock/execution/qmt_bridge.py` 与 `qmt_execution.py`），包含 xtdata/xttrader 适配、safety/auto 模式切换、ATR 止损和 QMT 降级到模拟盘的自动回退逻辑。对应测试 `tests/test_astock_qmt_bridge.py` / `tests/test_astock_qmt_execution.py`。

#### 桥接层（Python 3.6.8）
- 适配 QMT 运行环境
- 暴露主系统可调用的桥接接口
- 分离数据查询与下单执行能力

#### QMT 侧
- `xtdata`：历史/实时行情访问
- `xttrader`：下单能力
- Mini QMT / 全功能 QMT：运行环境与券商对接

### 10.2 架构约束
- 主系统不能直接耦合 QMT 专属运行时。
- 桥接层必须能单独失败、单独恢复。
- 读操作与写操作应在架构层区分权限边界。
- 默认应优先支持只读 / 查询 / 预览能力。

---

## 11. 风控与控制平面架构

目标态里，风控不是单个 agent，而是一整套控制平面。

当前代码证据：A 股风控控制平面已作为 Phase 11 的一部分交付（`tradingagents/astock/execution/risk_gate.py`），包含 ATR 动态止损、safety mode 人工确认门、组合风控约束和实时止损计算。对应测试 `tests/test_astock_execution_risk_gate.py`。

### 11.1 风控要素
根据图片规划，应至少包含：
- 安全模式
- 人工确认
- ATR 动态止损
- 跟踪止盈
- 组合风控
- 实时止损

### 11.2 风控放置位置
风控层应横切：
- 策略输出之后
- 模拟盘执行之前
- 实盘下单之前
- 持仓运行期间

### 11.3 控制平面职责
- 决定是否允许进入下一执行模式
- 决定是否允许自动下单
- 决定是否强制进入人工确认
- 在异常情况下暂停交易
- 保留审计记录与回退路径

---

## 12. 展示层架构：Web UI / CLI / API / 通知

### 12.1 Web UI
图片规划中明确出现：
- `Flask`
- `9 页面`
- `30+ API`

因此目标态的 Web UI 不是简单的报告查看器，而是应覆盖：
- 数据层可视化
- 分析结果展示
- 回测结果展示
- 模拟盘状态
- 实盘控制入口
- 风控状态显示

当前代码证据：A 股当前通过三种展示表面呈现：
- WebUI（`webui/`）：React/TypeScript 静态仪表盘，产品端入口，展示模块总览、Agent Flow、风险面板
- Streamlit（`tradingagents/ui/`）：运行时 viewer 后端，可生成并渲染实时 A 股研究报告
- CLI（`cli/main.py`）：终端报告渲染
WebUI 与 Streamlit 保持独立代码库，不做全技术合并。

### 12.2 CLI
CLI 仍可保留，用于：
- 单次分析
- 回测触发
- 模拟盘调试
- 桥接层诊断
- 批量任务和自动化脚本

### 12.3 API
API 层应成为展示层和执行层之间的标准边界，按类别组织：
- 数据查询 API
- 分析生成 API
- 回测 API
- 模拟盘 API
- 实盘控制 API
- 风控状态 API

### 12.4 通知层
虽然不是图片主体，但从模拟盘 / 实盘架构看，后续可自然扩展到：
- 实时事件通知
- 风险预警通知
- 调仓 / 执行结果通知

---

## 13. 数据流：从五层数据到受控执行

### 13.1 目标态数据流
```text
Providers
  -> Unified A-Stock Data Interface
  -> Five-Layer Reports
  -> Research / Debate Synthesis
  -> Strategy Scoring
  -> Risk Gate
  -> {Backtest | Paper Trading | Live Trading}
  -> UI / API / Notifications / Audit Log
```

### 13.2 关键中间产物
建议规划中显式保留以下几类中间结果：
- 五层专题报告
- 多空辩论状态
- 策略评分结果
- 执行候选动作
- 风控判定结果
- 回测 / 模拟 / 实盘执行记录

---

## 14. 当前基线到目标态的迁移路径

### 14.1 可以直接复用的部分
- LangGraph 编排骨架
- 多 Agent 拆分思想
- 结构化输出机制
- checkpoint / memory / logging 思路
- CLI 与 Web 的双入口思路

### 14.2 必须重做或新建的部分
- A 股研究结论到交易提案的合同实现（Phase 9 已交付，见 `tradingagents/astock/phase9_schemas.py`；原蓝图契约已在 Phase 9 归档）
- 策略层（尚未实现，仓库无 A 股策略评分模块）
- 回测引擎与回测验收体系（Phase 10 已交付，`tradingagents/astock/execution/backtest_engine.py` + `test_astock_backtest.py`）
- 模拟盘引擎（Phase 10 已交付，`tradingagents/astock/execution/paper_trader.py` + `test_astock_paper_trader.py`）
- QMT 桥接层（Phase 11 已交付，`qmt_bridge.py` / `qmt_execution.py` + 对应测试）
- 实盘控制平面（Phase 11 safety/auto 模式已实现，但仅限 QMT 桥接；完整实盘控制平面依赖真实券商账户接入）
- 风控控制平面（Phase 11 已交付 `risk_gate.py` + `test_astock_execution_risk_gate.py`；包含 ATR 止损、safety mode 人工确认）
- API / 通知体系（尚未实现）

### 14.3 不应混淆的部分
- 当前仓库已有的“研究/交易建议”能力
- 图片目标态中的“回测/模拟盘/实盘闭环”能力

二者相关，但不是同一层次的完成度。

---

## 15. 架构结论

如果只从当前源码看，项目仍然是：
- 一个多 Agent 金融研究与决策框架

如果按 `planning/a-stock-resource/` 的目标去演化，项目应当变成：
- 一个以五层 A 股数据为基础
- 以统一 Skill / 接口封装为中间层
- 以 LangGraph 多 Agent 为分析编排层
- 以策略层连接分析与执行
- 以回测 → 模拟盘 → 实盘为执行主线
- 以 QMT 桥接和风控控制平面约束实盘能力
- 以 Web UI / API / 通知形成产品外壳

这不是简单换数据源，而是一次从“研究框架”走向“交易闭环系统”的架构级演进。
