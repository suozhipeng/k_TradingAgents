# A 股定制模块快速上手

## 前置要求

- Python 3.12（最低 3.10，推荐 3.12）
- pip 或 conda 环境管理器
- 已安装 Git

## 1. 安装

```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents

# 创建虚拟环境
conda create -n astock python=3.12
conda activate astock

# 安装基础包
pip install .

# 安装 A 股可选依赖（数据源）
pip install ".[astock-providers]"
```

## 2. 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入必要的 API key
# 至少需要 DEEPSEEK_API_KEY 用于 AI Research
nano .env
```

最少必需配置：

```bash
DEEPSEEK_API_KEY=your_key_here
TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE=deterministic_verification
```

如需启用真实 LLM 分析：

```bash
TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE=live_research
DEEPSEEK_API_KEY=your_key_here
```

## 3. 启动 WebUI

```bash
PORT=8080 python run_webui.py
```

浏览器访问 http://localhost:8080

## 4. 启动 CLI

```bash
# 通用分析（US / 多市场）
tradingagents analyze
# 或
python -m cli.main

# A 股蓝图打印
tradingagents astock-blueprint
```

## 5. 运行测试

```bash
# A 股主链回归
python3 -m pytest tests/test_astock_graph_runtime.py tests/test_astock_graph_bridge.py -q

# 全仓回归
python3 -m pytest -q
```

## 5b. 启动 Flask REST API

```bash
# 默认端口 5860
python scripts/run_astock_api.py

# 带定时调度
python scripts/run_astock_api.py --scheduler --interval 30

# 自定义端口
python scripts/run_astock_api.py --port 5861
```

## 5c. 启动 DuckDB 数据库工具

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

## 5d. Live Research 验证

```bash
# 检查环境
python scripts/check_astock_live_research_env.py

# 端到端验证
python scripts/verify_astock_live_pipeline.py

# 结构化输出冒烟测试
python scripts/smoke_structured_output.py
```

## 7. 核心工作流

| 工作流 | 入口 | 说明 |
|---|---|---|
| AI 研究 | WebUI → AI Research Center 或 CLI `tradingagents analyze` | 输入 symbol，生成研究报告 |
| 回测 | WebUI → Strategy Hub → 回测 | 选择策略、区间、参数，运行回测 |
| 策略优化 | WebUI → Strategy Hub → 优化 | grid search 最优参数 |
| 模拟盘 | WebUI → Paper Trading / API `POST /paper/cycle` | 虚拟资金试跑 |
| 受控执行 | WebUI → Trading → Managed / QMT | 需要 QMT 环境和人工确认 |
| 批量回测 | API `POST /backtest/batch` | 多策略批量回测 |
| 数据管理 | API `POST /data/refresh/*` + DuckDB CLI | 数据刷新、导入/导出 |
| 龙虎榜/北向 | WebUI 独立页面 | 主力资金追踪、沪深股通资金流 |
| 板块轮动 | WebUI screener + sectors | ECharts treemap 热力图 |
| 动量轮动 | WebUI momentum_dashboard / momentum_rotation | 龙头股动量实时看板 |

## 7. 常见问题

- **Q: 数据源连接失败？**
  A: 检查 `docs/ASTOCK_LIVE_RESEARCH_SETUP.md` 中的 provider 配置说明。

- **Q: AI 分析失败？**
  A: 确认 `.env` 中有有效的 `DEEPSEEK_API_KEY`，且 `TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE` 设置为 `live_research`。

- **Q: WebUI 打不开？**
  A: 确认 8080 端口未被占用，或改用 `PORT=其他端口 python run_webui.py`。

## 8. 常见问题

- **Q: 数据源连接失败？**
  A: 检查 `docs/ASTOCK_LIVE_RESEARCH_SETUP.md` 中的 provider 配置说明。

- **Q: AI 分析失败？**
  A: 确认 `.env` 中有有效的 `DEEPSEEK_API_KEY`，且 `TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE` 设置为 `live_research`。

- **Q: WebUI 打不开？**
  A: 确认 8080 端口未被占用，或改用 `PORT=其他端口 python run_webui.py`。

- **Q: Flask API 启动失败？**
  A: 确认已安装 `pip install '.[astock-providers]'`，且 DuckDB 数据库文件路径可写。

- **Q: React WebUI 实验前端？**
  A: `webui/` 目录为实验性 React/TS 项目，当前渲染静态数据，API 客户端已就绪但未接线。运行 `cd webui && npm install && npm run dev`。

## 9. 下一步

- 完整产品需求：[`docs/ASTOCK_PRD.md`](ASTOCK_PRD.md)
- 当前状态：[`docs/ASTOCK_CURRENT_STATUS.md`](ASTOCK_CURRENT_STATUS.md)
- 文档体系入口：[`docs/README.md`](README.md)
