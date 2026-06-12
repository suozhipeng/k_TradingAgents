# TradingAgents WebUI Self Test Report

> 状态：历史 WebUI 自测记录。当前 A 股二次定制回归和剩余风险见
> `docs/ASTOCK_CURRENT_STATUS.md`。

## 结论
**通过。**

当前 WebUI 已完成自测、复查、补漏与安全重构，满足以下目标：
- `npm run build` 通过
- 核心页面完整
- `modules.json` 覆盖 TradingAgents 主要模块
- 无高风险遗漏
- `planning/review/SELF_TEST_REPORT.md` 已生成

## 已完成的工作
### 1) ECC 只读审查
- 复核了 README、CLI、tradingagents、webui、webui-data、planning/codebase
- 确认模块映射与 Agent Flow 整体一致
- 输出：`planning/review/ECC_REVIEW.md`

### 2) WebUI 修复与增强
- 补齐 Dashboard / Task Center / Reports / Settings
- 增强模块搜索、筛选、详情、风险展示
- 增加 markdown 报告查看
- 增加加载 / 错误 / 空状态
- 输出：`planning/review/OPENCODE_FIX.md`

### 3) 结构与重构优化
- 收敛组件职责
- 生成更完整的模块映射文档
- 扩展 dataflow 覆盖到 StockTwits / Reddit
- 输出：`planning/review/CODEX_REFACTOR.md`

## 功能覆盖检查
- [x] Dashboard 存在
- [x] Module Map 存在
- [x] Agent Flow 存在
- [x] Task Center 存在
- [x] Reports 存在
- [x] Settings 存在

## 模块覆盖检查
- [x] analysts
- [x] researchers
- [x] trader
- [x] risk managers
- [x] portfolio manager
- [x] dataflows
- [x] graph
- [x] cli
- [x] config

## 交互覆盖检查
- [x] 模块搜索
- [x] 模块筛选
- [x] 模块详情
- [x] Agent 流程展示
- [x] 风险展示
- [x] Markdown 报告查看

## 工程覆盖检查
- [x] `npm install` 成功
- [x] `npm run dev` 成功启动
- [x] `npm run build` 通过
- [x] TypeScript 无构建错误
- [x] 未发现未使用组件
- [x] 未发现死链接
- [x] 未发现 TODO / FIXME / UNKNOWN

## 主要修复内容
1. 新增 WebUI 分区导航与仪表盘区块
2. 新增 Markdown 报告查看器
3. 扩展模块搜索范围与空状态提示
4. 补强风险面板与详情面板
5. 更新静态模块映射，补足社媒数据流入口
6. 生成并同步 `MODULE_MAP.md`

## 仍需人工确认的问题
1. 是否将 `webui-data/modules.json` 定义为唯一 canonical 数据源
2. 是否需要将 Agent Flow 升级成运行时 DAG 可视化
3. 后续源码命名变更时的同步流程

## 启动方式
进入 `webui/` 目录后：

```bash
npm install
npm run dev
```

如果本机浏览器对根路径 `/` 访问异常，可直接打开：
- `http://127.0.0.1:5173/index.html`

生产构建：
```bash
npm run build
```

## 结果摘要
- WebUI 已可作为静态只读模块总览页使用
- 主要模块和 Agent 流程已覆盖
- 构建通过
- 未修改 `tradingagents/` 原业务逻辑
