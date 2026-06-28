# 数据隐私声明

## 1. 数据收集范围

TradingAgents-Astock 是**本地部署**的分析工具，默认不向任何第三方发送用户数据。

### 1.1 本地存储的数据

以下数据存储在用户本地机器上：

| 数据类型 | 存储位置 | 说明 |
|---|---|---|
| 数据库 | DuckDB 本地文件 | K 线、估值、回测结果、报告等 |
| 缓存 | 本地文件系统 | 数据缓存、模型缓存 |
| 配置文件 | `.env`、`DEFAULT_CONFIG` | API key、模型配置、环境变量 |
| 分析报告 | `~/.tradingagents/reports/` | 生成的研究报告、PPT |
| 决策日志 | `~/.tradingagents/memory/trading_memory.md` | 历史决策和反思 |
| 检查点 | `~/.tradingagents/cache/checkpoints/` | LangGraph 运行状态 |

### 1.2 发送到第三方的数据

以下数据会发送到第三方服务：

| 数据 | 发送目的地 | 说明 |
|---|---|---|
| API Key | 不发送 | API Key 仅存储在本地 `.env`，不上传 |
| LLM 请求 | LLM Provider（如 DeepSeek、OpenAI） | 发送 ticker、日期、上下文数据给 LLM 生成分析 |
| 数据源请求 | 数据 Provider（如 akshare、mootdx、Tencent） | 发送 ticker、日期请求行情数据 |
| 新闻/社交数据 | 新闻源、StockTwits、Reddit | 公开数据抓取 |

## 2. API Key 安全

- API Key 存储在本地 `.env` 文件中
- `.env` 文件已被添加到 `.gitignore`，不会提交到版本控制
- API Key 仅用于配置 LLM Provider 和数据源连接
- 系统不收集、不上传、不记录 API Key

## 3. LLM 数据隐私

- 发送给 LLM Provider 的数据包括：ticker、日期、上下文数据（行情、新闻、财务等）
- LLM Provider 的处理受其各自的隐私政策约束
- 建议在发送敏感数据前确认 LLM Provider 的数据使用政策
- AI 输出默认标注为 `advisory-only`，不直接触发交易

## 4. 数据源隐私

- 数据源请求通过公开 API 进行
- 数据源提供商的隐私政策独立于本项目
- 参见 [`03-ops/data-sources.md`](03-ops/data-sources.md)

## 5. 用户权利

- **访问**：所有本地数据可通过文件系统直接访问
- **删除**：删除本地文件即可清除所有数据
- **导出**：报告可通过 API 导出为 Markdown/JSON/PPT

## 6. 数据安全建议

- 不要将 `.env` 文件提交到公共仓库
- 不要与他人分享 API Key
- 定期备份 DuckDB 数据文件
- 在共享机器上使用时注意文件权限

## 7. 合规说明

本工具为本地部署的研究分析工具，不涉及用户账号体系和个人信息收集。
当前暂不纳入 GDPR/个人信息保护法合规专项文档。
如进入多用户部署或企业交付阶段，需重新评估并补充隐私合规文档。

## 8. 联系我们

如有隐私相关问题，请联系项目维护者。
