# A 股 live_research 环境配置

本文档说明 A 股 `live_research` runtime profile 的可运行环境。它的目标是让 Phase 09 A 股 advisory chain 使用真实 LLM client，而不是 deterministic verification 模式下的 `BridgeLLM`。

## 1. 目标

启用真实 LLM 时必须同时保留以下安全约束：

- `actionable=false`
- `execution_signal=ResearchOnly`
- 缺少任一必要 live client 时 fail-closed，不能静默降级为 `BridgeLLM`

## 2. 必需环境变量

至少需要在 `.env` 或当前 shell 中设置 provider、模型、runtime profile 和对应 API key：

```bash
TRADINGAGENTS_LLM_PROVIDER=deepseek
TRADINGAGENTS_QUICK_THINK_LLM=deepseek-v4-flash
TRADINGAGENTS_DEEP_THINK_LLM=deepseek-v4-pro
TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE=live_research
DEEPSEEK_API_KEY=your_real_key
```

可选配置：

```bash
TRADINGAGENTS_LLM_BACKEND_URL=https://api.deepseek.com
TRADINGAGENTS_OUTPUT_LANGUAGE=Chinese
TRADINGAGENTS_TEMPERATURE=0.0
```

## 3. 推荐本地流程

1. 如有需要，复制环境变量模板：

```bash
cp .env.example .env
```

2. 填入上面的必需变量。

3. 在仓库内校验环境：

```bash
python3 scripts/check_astock_live_research_env.py
```

4. 通过 CLI 运行 A 股分析：

```bash
python3 -m cli.main run-analysis
```

当 ticker 是 A 股，并且 `TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE=live_research` 时，CLI 会为以下角色构建真实 LLM client：

- Bull Researcher：quick-thinking 模型
- Bear Researcher：quick-thinking 模型
- Research Manager：deep-thinking 模型

Streamlit 只读 viewer 在 live runtime mode 下使用同一套配置路径。

## 4. 校验行为

- `deterministic_verification` profile 允许缺少真实 LLM client，并使用 `BridgeLLM`。
- `live_research` profile 如果缺少 provider 配置或 API key，必须在分析开始前失败。
- `live_research` 运行不得回退到 `BridgeLLM`。

## 5. 数据源说明

### mootdx（通达信）

mootdx 0.11.7 已在本地验证通过，可连接通达信行情服务器获取实时 K 线和报价。无需额外配置。支持的 symbol 格式为不带后缀的数字代码，例如 `600519`；`AStockDataRouter` 会自动转换。

### iwencai（问财）

pywencai 0.13.1 已安装，但需要设置 `ASTOCK_IWENCAI_COOKIE` 环境变量才能启用。

获取 iwencai cookie：

1. 用浏览器打开 https://iwencai.com 并登录账号。
2. 打开浏览器开发者工具，进入 Application / Storage。
3. 在 Cookies -> iwencai.com 下找到名为 `v` 或 `other_` 开头的 cookie 值。
4. 复制完整 cookie 字符串。
5. 设置环境变量：

```bash
export ASTOCK_IWENCAI_COOKIE="your_cookie_value_here"
```

也可以写入 `.env`：

```bash
ASTOCK_IWENCAI_COOKIE=your_cookie_value_here
```

配置后可启用语义搜索和机构预期查询能力。

## 6. 当前主机状态

当前仓库已经把 `live_research` 路径接入 config、CLI 和 Streamlit。真实运行仍要求当前 shell 或 app 进程环境中存在匹配 provider 的有效 key。

live provider 的历史验证证据保存在 `docs/verification_provenance/`。这些文件是 provider 可用性溯源，不等同于当前网络环境仍可用；重新验证需要运行 live provider 测试并追加新的 dated provenance。
