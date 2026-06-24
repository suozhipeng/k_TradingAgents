# A 股定制模块常见问题

## 安装与环境

### Q1: 支持哪些 Python 版本？

推荐使用 **Python 3.12**。最低支持 Python 3.10。

### Q2: 安装失败，提示缺少某些依赖？

A 股定制模块有额外的可选依赖。安装时指定：

```bash
pip install ".[astock-providers]"
```

### Q3: conda 环境创建失败？

尝试使用 venv 替代：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[astock-providers]"
```

### Q4: WebUI 启动后页面打不开？

- 确认端口未被占用（默认 8080）
- 尝试更换端口：`PORT=5000 python run_webui.py`
- 确认防火墙未阻止本地端口

## 数据源

### Q5: 数据获取失败怎么办？

1. 进入 **Data & Ops** → 数据健康页查看各 provider 状态
2. 检查 `.env` 中是否有必要的配置
3. 部分 provider（如 iwencai）需要额外配置 cookie
   - 参见 [`docs/ASTOCK_LIVE_RESEARCH_SETUP.md`](ASTOCK_LIVE_RESEARCH_SETUP.md)

### Q6: 数据延迟或过期怎么办？

- 手动刷新数据：`POST /api/v1/data/refresh/all`
- 查看数据新鲜度标签（`ok`/`stale`/`partial`/`fallback`/`mock`）
- 如果数据标记为 `stale`，系统会阻止 live-ready 操作

### Q7: 为什么有些数据显示为 mock？

当主数据源不可用时，系统会 fallback 到备源。如果备源也不可用，会使用 mock 数据。
Mock 数据会在页面上显著标注，不得用于实盘。

### Q8: 如何确认数据源授权？

参见 [`docs/ASTOCK_DATA_SOURCE_LICENSE_AND_USAGE.md`](ASTOCK_DATA_SOURCE_LICENSE_AND_USAGE.md)。
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
参见 [`docs/ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md`](ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md) §7。

### Q14: 回测包含涨跌停和停牌吗？

当前回测引擎对涨跌停和停牌的处理是逐步完善的。
回测结果中的 `data_assumption` 字段会说明是否应用了涨跌停不可成交、停牌不可成交等约束。

## 交易与执行

### Q15: 如何切换到实盘模式？

当前系统**不支持**自动实盘交易。
进入 `live-ready` 模式需要通过 Phase 30 Live Trading Readiness 的准入 checklist。
详见 [`docs/ASTOCK_LIVE_TRADING_RUNBOOK.md`](ASTOCK_LIVE_TRADING_RUNBOOK.md)。

### Q16: QMT 连接失败怎么办？

- 确认 QMT 环境已安装并可运行
- 确认 `.env` 中配置了正确的 QMT 连接参数
- QMT 不可用时系统会自动降级到模拟盘
- 参见 [`docs/ASTOCK_LIVE_RESEARCH_SETUP.md`](ASTOCK_LIVE_RESEARCH_SETUP.md)

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
参见 [`docs/ASTOCK_DEPLOYMENT_AND_ENVIRONMENT.md`](ASTOCK_DEPLOYMENT_AND_ENVIRONMENT.md)。

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

参见 [`docs/ASTOCK_DATA_MIGRATION_AND_UPGRADE.md`](ASTOCK_DATA_MIGRATION_AND_UPGRADE.md)。
Schema 变更会提供迁移脚本和回滚策略。

## 文档相关

### Q23: 从哪里了解完整的文档体系？

参见 [`docs/README.md`](README.md)。

### Q24: 如何了解 Phase 30-38 的进展？

参见 [`docs/phases/README.md`](phases/README.md)。

### Q25: 如何报告文档中的错误？

请在 GitHub 上提交 issue，或在团队内部通过 Hermes 调度修正。
