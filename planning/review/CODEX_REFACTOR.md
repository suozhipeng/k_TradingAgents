# Codex Refactor Review — TradingAgents WebUI

## 目标
检查目录结构、组件重复、数据结构可扩展性、硬编码 / 重复逻辑 / 无用文件，并执行安全重构。

## 已执行的安全重构
### 1) WebUI 主入口重构
- 将原本较平面的单页入口重构为多区块静态仪表盘：
  - Dashboard
  - Module Map
  - Agent Flow
  - Task Center
  - Reports
  - Settings
- 用 section 方式组织内容，降低后续扩展成本

### 2) 新增 markdown 报告组件
- `webui/src/components/MarkdownReport.tsx`
- 目的：将报告展示逻辑从主页面中拆出来，避免 App.tsx 继续膨胀

### 3) 视图组件职责收敛
- `ModuleTree`：只负责搜索 / 筛选 / 树状列表
- `ModuleDetail`：只负责模块详情
- `RiskPanel`：只负责风险与 IO 分组
- `AgentFlow`：只负责流程展示

### 4) 数据结构扩展
- `modules.json` 增加了显式数据源模块：
  - `StockTwits Dataflow`
  - `Reddit Dataflow`
- 并更新了 `Sentiment Analyst` 的输入、输出、依赖、风险与相关文件
- 这样 WebUI 的静态模块视图更接近真实项目的数据入口

### 5) 文档结构整理
- `planning/codebase/MODULE_MAP.md` 重新生成，作为模块映射与主流程说明
- `planning/review/` 下新增分阶段审查输出，便于未来复盘

## 结构合理性判断
**结论：合理。**

当前目录职责分离较清晰：
- `webui/`：静态前端
- `webui-data/`：静态数据源
- `planning/codebase/`：架构 / 模块映射文档
- `planning/review/`：审查与自测报告

## 发现的潜在问题
### 低风险
1. **`modules.json` 与 `webui/src/data/modules.json` 双写**
   - 当前已保持一致，但未来存在漂移风险。

2. **`Task Center` 命名偏静态视图**
   - 当前实现更接近“模块检索中心”，不是任务执行中心。
   - 语义上可接受，但建议后续统一说明。

3. **`MarkdownReport` 是轻量自研解析器**
   - 覆盖了常见标题 / 列表 / 引用 / 行内 code / 粗体，但不是完整 Markdown 引擎。
   - 作为静态报告预览足够，且避免新增依赖。

## 无用文件 / 重复逻辑检查
- 未发现明显无用组件
- 未发现明显死链接
- 未发现重复实现到需要拆分的程度
- 未发现 TODO / FIXME / UNKNOWN 残留

## 构建与可扩展性
- `npm run build` 已通过
- 组件拆分后，后续若要添加：
  - 路由
  - 标签页
  - 搜索高亮
  - 可折叠模块树
  - 运行时 DAG 可视化
  都可以在当前结构上安全扩展

## 结论
**Codex Refactor：通过。**
本轮重构属于低风险、安全重构，没有触碰 `tradingagents/` 核心业务逻辑；WebUI 的结构清晰度与可扩展性均有提升。
