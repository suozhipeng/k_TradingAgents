# ECC Review — TradingAgents WebUI（只读审查）

> 状态：历史 WebUI 静态总览验收。该文档不再代表当前全仓 ECC 结论。
> A 股 runtime、provider、CLI 和 Streamlit viewer 的当前基线见
> `docs/ASTOCK_CURRENT_STATUS.md`。

## 结论
当前 WebUI 的静态模块清单与 TradingAgents 代码/README/规划文档整体一致，未发现阻断性问题。`modules.json` 已覆盖 TradingAgents 的核心模块与主流程；WebUI 中的 Dashboard / Module Map / Agent Flow / Task Center / Reports / Settings 六个区块均已存在；`webui/src/data/modules.json` 与 `webui-data/modules.json` 完全一致。TypeScript / 构建层面验证通过，`webui/` 下执行 `npm run build` 成功。

## 1) `modules.json` 覆盖性
**结论：通过。**

- `webui/src/data/modules.json` 与 `webui-data/modules.json` 内容一致。
- 共 **28** 个模块记录，且所有记录字段完整：`name / path / type / description / inputs / outputs / dependencies / risks / related_files`。
- 类型覆盖统计：
  - `analyst`: 4
  - `researcher`: 3
  - `trader`: 1
  - `risk`: 2
  - `dataflow`: 7
  - `config`: 9
  - `cli`: 2
- 已覆盖 README / 源码中的核心链路：
  - 4 个分析师：Market / Technical、Sentiment、News、Fundamentals
  - 研究阶段：Bull Researcher、Bear Researcher、Research Manager
  - 交易阶段：Trader
  - 风险阶段：三类风险 Agent + Portfolio Manager
  - 支撑层：Graph、AgentState、Dataflow interface、LLM clients、Schemas、Memory、Default config、CLI

## 2) Agent Flow 与源码 / README 一致性
**结论：一致，且与规划文档一致。**

- WebUI 的 Agent Flow 标题与顺序为：
  - `Data Source → Analysts → Researchers → Trader → Risk Managers → Portfolio Manager`
- 这与以下内容一致：
  - `README.md` 的框架说明
  - `planning/codebase/MODULE_MAP.md`
  - `tradingagents/graph/setup.py`
  - `tradingagents/graph/conditional_logic.py`
- 需要注意：WebUI 展示的是**静态分层流程**，不是完整运行时 DAG；它不展示每个 analyst 的 tool loop、条件跳转与 `selected_analysts` 执行顺序细节，这是设计上的简化，不是错误。

## 3) 页面 / 功能存在性检查
**结论：通过。**

在 `webui/src/App.tsx` 中确认以下区块均存在：
- `Dashboard`
- `Module Map`
- `Agent Flow`
- `Task Center`
- `Reports`
- `Settings`

同时：
- `ModuleTree` 支持搜索与类型过滤
- `ModuleDetail` 支持模块详情查看
- `RiskPanel` 展示输入 / 输出 / 依赖 / 风险
- `MarkdownReport` 提供静态报告预览

## 4) 缺字段 / 缺模块 / 描述准确性 / TS 与构建风险
**结论：未见高风险缺陷，存在少量中低风险维护项。**

### 高风险
- **未发现高风险问题。**

### 中风险
1. **静态 JSON 与源码之间缺少运行时校验**
   - `App.tsx` 直接将 `rawModules` 断言为 `ModuleRecord[]`，没有运行时 schema 校验。
   - 当前内容是完整的，但如果后续 `modules.json` 字段或类型发生漂移，WebUI 可能在运行时才暴露问题。

2. **Agent Flow 过于抽象**
   - 当前只按模块类型展示，不展示 runtime 的条件分支、tool-node 循环、`selected_analysts` 顺序与实际节点名。
   - 对“流程图”用途足够，但不能替代源码级 DAG 审查。

### 低风险
1. **模块类型是硬编码 union**
   - `ModuleType` 固定为 `analyst/researcher/trader/risk/dataflow/config/cli`。
   - 若后续源码新增模块类别，需要同步更新 TS 类型与 JSON 数据。

2. **部分文案是“静态总览”语义**
   - 例如 `Task Center` 更像模块检索 / 查看面板，不是任务队列或执行中心。
   - 当前实现与文案基本一致，但建议后续保持命名语义稳定，避免误解。

### 描述准确性
- 未发现明显的缺字段、缺模块或明显错误描述。
- `Market / Technical Analyst` 作为 `market_analyst.py` 的静态标签是可接受的，与 README 的 “Technical Analyst” 叙述一致。
- `Risk Management Team` 作为 `aggressive / conservative / neutral` 的聚合标签也与源码 / README 一致。

## 5) 仍需人工确认项
1. **是否将 `webui-data/modules.json` 作为唯一 canonical 数据源**
   - 目前它与 `webui/src/data/modules.json` 完全一致，建议明确后续更新流程，避免双写漂移。

2. **是否需要把 Agent Flow 升级为运行时 DAG 可视化**
   - 当前仅为静态阶段概览；如果后续需要更强的可视化表达，建议补充 `selected_analysts`、tool loop、conditional edge 等信息。

3. **后续源码命名变更的同步策略**
   - 若 `tradingagents/graph/*` 或角色节点名变更，需同步更新 `modules.json` 与 WebUI 文案，否则会产生静态文档漂移。

## 最终判定
**ECC 结论：通过（Accept）**
- 核心模块覆盖完整
- Agent Flow 与源码 / README 一致
- 页面区块齐全
- 构建通过
- 当前仅存在静态快照维护成本与抽象层级带来的中低风险
