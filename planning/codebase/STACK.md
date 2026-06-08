# STACK

## Python 版本
- `pyproject.toml` 指定：`requires-python = ">=3.10"`
- Docker/容器相关默认镜像未在 `docker-compose.yml` 明示 Python 小版本；`terminal.docker_image` 属于 Hermes 配置，不属于本项目，故这里不引用。
- 若生产部署要求固定到 `3.10.x / 3.11.x`，当前仓库内未看到锁定信息，**需人工确认**。

## 依赖来源
- **主依赖来源**：`pyproject.toml`
- **requirements.txt**：仅包含 `.`，表示以当前项目包方式安装，本身不列出真实第三方依赖。

## 主要依赖
### LLM / Agent 编排
- `langchain-core>=0.3.81`
- `langchain-openai>=0.3.23`
- `langchain-anthropic>=0.3.15`
- `langchain-google-genai>=4.0.0`
- `langchain-experimental>=0.3.4`
- `langgraph>=0.4.8`
- `langgraph-checkpoint-sqlite>=2.0.0`

### 金融 / 数据处理
- `yfinance>=1.4.1`
- `stockstats>=0.6.5`
- `pandas>=2.3.0`
- `backtrader>=1.9.78.123`
- `requests>=2.32.4`
- `pytz>=2025.2`
- `parsel>=1.10.0`

### CLI / 交互
- `typer>=0.21.0`
- `questionary>=2.1.0`
- `rich>=14.0.0`
- `tqdm>=4.67.1`

### 其他
- `redis>=6.2.0`（代码中未在本次分析范围内看到核心调用链入口，可能用于扩展/未来功能，**需人工确认**）
- `typing-extensions>=4.14.0`
- `setuptools>=80.9.0`

## LLM 相关组件
### Provider 抽象层
目录：`tradingagents/llm_clients/`
- `factory.py`：统一入口，按 provider 构造客户端
- `openai_client.py`
- `anthropic_client.py`
- `google_client.py`
- `azure_client.py`
- `api_key_env.py`：provider → 环境变量映射
- `model_catalog.py`：CLI 模型选单
- `capabilities.py` / `validators.py`：能力判定与模型校验

### 已支持 Provider（由 `factory.py` 和 `api_key_env.py` 可见）
- OpenAI
- Anthropic
- Google Gemini
- Azure OpenAI
- xAI
- DeepSeek
- Qwen / Qwen-CN
- GLM / GLM-CN
- MiniMax / MiniMax-CN
- OpenRouter
- Ollama

## 数据源相关组件
### 市场与基本面数据
目录：`tradingagents/dataflows/`
- `y_finance.py`：Yahoo Finance 数据
- `yfinance_news.py`：Yahoo Finance 新闻
- `alpha_vantage*.py`：Alpha Vantage 行情/指标/新闻/基本面
- `interface.py`：数据源路由与 fallback
- `market_data_validator.py`：市场数据校验
- `symbol_utils.py`：ticker / symbol 处理

### 舆情与社区数据
- `reddit.py`：Reddit 抓取
- `stocktwits.py`：StockTwits 抓取

### 默认数据供应商策略
`default_config.py` 默认：
- `core_stock_apis`: `yfinance`
- `technical_indicators`: `yfinance`
- `fundamental_data`: `yfinance`
- `news_data`: `yfinance`

并允许：
- 分类级别 `data_vendors`
- 工具级别 `tool_vendors`
- 自动 fallback（`interface.py`）

## CLI 相关组件
目录：`cli/`
- `main.py`：Typer CLI 主入口
- `models.py`：CLI 枚举（分析师类型、资产类型）
- `config.py`：CLI 远端公告配置
- `utils.py`：选择器、辅助函数、保存报告等
- `stats_handler.py`：LLM / 工具调用统计
- `announcements.py`：启动公告获取
- `static/welcome.txt`：欢迎文本资源

### CLI 脚本入口
`pyproject.toml`
- `tradingagents = "cli.main:app"`

## Docker 相关组件
### `docker-compose.yml`
服务：
- `tradingagents`
  - `build: .`
  - 加载 `.env`
  - 挂载持久卷到 `/home/appuser/.tradingagents`
- `ollama`
  - `image: ollama/ollama:latest`
  - profile: `ollama`
- `tradingagents-ollama`
  - `LLM_PROVIDER=ollama`
  - 依赖 `ollama`
  - profile: `ollama`

### Docker 能力结论
- 支持默认容器运行
- 支持通过 `ollama` profile 走本地/自托管模型
- 未看到真实交易网关、券商 API、订单执行容器，当前更像“研究/决策生成框架”，不是完整交易执行系统

## 总结
这是一个：
- **Python 3.10+**
- 以 **LangGraph + LangChain** 为核心
- 通过 **多类 LLM Provider + 多数据源路由** 完成
- 带 **交互式 CLI** 与 **Docker/Ollama 运行方式**
- 输出“分析报告 + 投资建议 + 风险讨论 + 最终评级”的
**多 Agent 金融研究/交易决策框架**。