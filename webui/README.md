# webui/ — React/TypeScript 前端实验项目

> ⚠️ **实验性项目 — 不作为产品主入口**

本目录包含一个 React/TypeScript/Vite 前端实验项目，用于探索从前端技术栈角度（独立于 Flask Jinja2）构建 TradingAgents WebUI 的可能性。

## 状态

| 项目 | 状态 |
|------|------|
| 产品用途 | ❌ 不作为 AStock Pro 产品主入口 |
| 开发进度 | 🧪 实验性 — 部分组件原型，非完整页面系统 |
| npm 漏洞 | ✅ 0 个（`npm audit` 已清零） |
| 维护责任 | ⚠️ 无持续维护承诺 |

## 技术栈

- React 18 + TypeScript
- Vite 构建工具
- Tailwind CSS
- 自定义 hooks (useApi, useTranslation)

## 当前实现组件

- AgentFlow — AI 分析链可视化
- BacktestChart — 回测图表
- KlineChart — K 线图
- LangSwitch / MarketSwitch — 语言/市场切换
- MarkdownReport — Markdown 报告渲染
- ModuleDetail / ModuleTree — 模块详情/树
- ReportViewer — 报告查看器
- RiskPanel — 风控面板

## 与 Flask WebUI 的关系

当前产品主入口是 `tradingagents/astock/web/` 下的 Flask Jinja2 模板系统（25 个模板，28 个路由）。
本实验项目与 Flask WebUI 保持独立代码库，不做全技术合并。

## 启动

```bash
cd webui
npm install   # 需要 Node.js 18+
npm run dev   # 开发服务器
```

## 备注

- 当前依赖已升级到 `vite 6.4.3`，`npm audit` 为 0
- 本地默认 Node 14 会导致 Vite 6 构建失败，需切到 Node 18+ 运行
- 无持续性 CI/CD
- 无测试覆盖
- 如果长期不维护，建议归档或移除
