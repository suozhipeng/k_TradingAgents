# STRUCTURE

## 顶层目录结构
```text
TradingAgents/
├── main.py
├── pyproject.toml
├── requirements.txt
├── docker-compose.yml
├── cli/
├── tradingagents/
├── tests/
├── scripts/
├── assets/
└── planning/codebase/
```

> 本次重点分析范围按要求聚焦：`main.py`、`cli/`、`tradingagents/`、`pyproject.toml`、`requirements.txt`、`docker-compose.yml`。

## 核心目录职责

### 1. `main.py`
职责：
- 最小化脚本入口
- 直接构造 `TradingAgentsGraph`
- 用固定示例 `NVDA` 和 `2024-05-10` 调用 `propagate()`
- 打印最终决策

特点：
- 更像 demo / smoke entry，不是主交互入口
- 使用 `DEFAULT_CONFIG.copy()`，环境变量可覆盖默认配置

### 2. `cli/`
职责：用户交互层 / 可视化终端层

主要文件：
- `cli/main.py`
  - Typer 应用入口
  - 用户问答式选择 ticker、分析日期、分析师、LLM provider、模型、语言、研究深度
  - 驱动 `TradingAgentsGraph`
  - 实时展示进度、消息、工具调用、报告分段
  - 保存结果到磁盘
- `cli/models.py`
  - 定义 `AnalystType`、`AssetType`
- `cli/config.py`
  - CLI 公告服务配置
- `cli/utils.py`
  - 各类选择器、provider 配置、报告保存等辅助逻辑
- `cli/stats_handler.py`
  - 统计 token / tool / LLM 使用情况
- `cli/announcements.py`
  - 拉取公告并显示

结论：
- `cli/` 是**真正的主产品入口**
- `main.py` 是轻量脚本入口

### 3. `tradingagents/`
职责：核心业务实现

子目录职责：

#### `tradingagents/graph/`
- 多 Agent 工作流编排核心
- 定义图结构、节点连接、条件跳转、状态传播、checkpoint、结果处理

关键文件：
- `trading_graph.py`：总控类 `TradingAgentsGraph`
- `setup.py`：构建 LangGraph 工作流
- `conditional_logic.py`：控制 analyst / debate / risk debate 的跳转
- `propagation.py`：初始化图状态、配置 stream 参数
- `signal_processing.py`：从最终 Portfolio Manager 输出中提取评级
- `reflection.py`：事后反思逻辑
- `checkpointer.py`：断点恢复
- `analyst_execution.py`：分析师执行计划与耗时追踪

#### `tradingagents/agents/`
- 各类角色 agent 定义

子模块：
- `analysts/`
  - Market Analyst
  - Sentiment Analyst
  - News Analyst
  - Fundamentals Analyst
- `researchers/`
  - Bull Researcher
  - Bear Researcher
- `risk_mgmt/`
  - Aggressive Analyst
  - Conservative Analyst
  - Neutral Analyst
- `managers/`
  - Research Manager
  - Portfolio Manager
- `trader/`
  - Trader
- `utils/`
  - agent state、工具封装、语言指令、memory、结构化输出适配
- `schemas.py`
  - Pydantic 输出 schema

#### `tradingagents/dataflows/`
- 数据获取与供应商路由层
- 屏蔽 yfinance / Alpha Vantage / Reddit / StockTwits 差异

#### `tradingagents/llm_clients/`
- LLM provider 抽象层
- 屏蔽 OpenAI / Anthropic / Gemini / OpenRouter / Ollama 等差异

#### `tradingagents/default_config.py`
- 默认配置单点来源
- 环境变量覆盖入口
- 数据目录、缓存目录、模型、供应商、语言、轮次、vendor 默认值定义

## 入口文件说明

### 入口 1：CLI 入口（主入口）
来源：`pyproject.toml`
- `tradingagents = "cli.main:app"`

实际行为：
- 用户执行 `tradingagents analyze`
- 进入 `cli/main.py`
- 最终走 `run_analysis()`
- 构造 `TradingAgentsGraph`
- 调用 `graph.graph.stream(...)`

### 入口 2：脚本入口（示例/调试）
文件：`main.py`
- 直接实例化 `TradingAgentsGraph`
- 调用 `propagate("NVDA", "2024-05-10")`

适用场景：
- 快速验证
- 开发调试
- 非交互式调用样例

## 输出结构
运行过程中会写入：
- `results_dir/<ticker>/<date>/reports/*.md`
- `results_dir/<ticker>/<date>/message_tool.log`
- `results_dir/<ticker>/TradingAgentsStrategy_logs/full_states_log_<date>.json`
- memory log（默认 `~/.tradingagents/memory/trading_memory.md`）
- checkpoint sqlite / cache（启用时）

## 结构总结
项目结构可以概括为四层：
1. **CLI 层**：收集输入、展示过程、保存报告
2. **Graph 编排层**：定义节点顺序与状态流转
3. **Agent 层**：各角色完成分析/辩论/决策
4. **Data + LLM 适配层**：接入外部模型与外部市场数据

这种结构清晰，适合做“研究型多 Agent 决策系统”的二次开发。