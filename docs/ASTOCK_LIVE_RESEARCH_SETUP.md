# A-Stock Live Research Setup

This document describes the runnable environment for the A-share
`live_research` runtime profile.

## Goal

Enable the Phase 09 A-share advisory chain to use real LLM clients instead of
`BridgeLLM` while preserving:

- `actionable=false`
- `execution_signal=ResearchOnly`
- fail-closed behavior when any required live client is missing

## Required environment

At minimum, set the provider, models, runtime profile, and matching API key in
`.env` or your shell:

```bash
TRADINGAGENTS_LLM_PROVIDER=deepseek
TRADINGAGENTS_QUICK_THINK_LLM=deepseek-v4-flash
TRADINGAGENTS_DEEP_THINK_LLM=deepseek-v4-pro
TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE=live_research
DEEPSEEK_API_KEY=your_real_key
```

Optional:

```bash
TRADINGAGENTS_LLM_BACKEND_URL=https://api.deepseek.com
TRADINGAGENTS_OUTPUT_LANGUAGE=English
TRADINGAGENTS_TEMPERATURE=0.0
```

## Recommended repo-local flow

1. Copy the example env file if needed:

```bash
cp .env.example .env
```

2. Fill in the required variables above.

3. Validate the environment locally:

```bash
python3 scripts/check_astock_live_research_env.py
```

4. Run the CLI with an A-share ticker:

```bash
python3 -m cli.main run-analysis
```

When the ticker is A-share and `TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE=live_research`,
the CLI will build real LLM clients for:

- Bull Researcher: quick-thinking model
- Bear Researcher: quick-thinking model
- Research Manager: deep-thinking model

The Streamlit read-only viewer follows the same config path when launched in
live runtime mode.

## Validation behavior

- If the runtime profile is `deterministic_verification`, missing LLM clients
  are allowed and `BridgeLLM` is used.
- If the runtime profile is `live_research`, missing provider configuration or
  API keys cause startup failure before the run begins.
- No `live_research` run may fall back to `BridgeLLM`.

## Data source notes

### mootdx（通达信）

mootdx 0.11.7 已安装并在本地验证通过 —— 可直接连接通达信行情服务器获取实时 K 线和报价。无需额外配置。支持的 symbol 格式为不带后缀的数字代码（如 `600519`），`AStockDataRouter` 会自动转换。

### iwencai（问财）

pywencai 0.13.1 已安装，但需要设置 `ASTOCK_IWENCAI_COOKIE` 环境变量才能启用。

**如何获取 iwencai cookie：**
1. 用浏览器打开 https://iwencai.com 并登录你的账号
2. 打开浏览器开发者工具（F12）→ "Application" / "Storage" 标签
3. 在 Cookies → iwencai.com 下找到名为 `v` 或 `other_` 开头的 cookie 值
4. 复制完整 cookie 字符串
5. 设置到环境变量：
   ```bash
   export ASTOCK_IWENCAI_COOKIE="your_cookie_value_here"
   ```
   或者写入 `.env` 文件：
   ```
   ASTOCK_IWENCI_COOKIE=your_cookie_value_here
   ```

配置后即可启用语义搜索和机构预期查询能力。

## Current host note

This repo now has the `live_research` code path wired through config, CLI, and
Streamlit. A real run still requires the matching provider key to be present in
the environment of the current shell or app process.
