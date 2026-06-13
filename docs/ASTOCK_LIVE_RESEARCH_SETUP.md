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

## Current host note

This repo now has the `live_research` code path wired through config, CLI, and
Streamlit. A real run still requires the matching provider key to be present in
the environment of the current shell or app process.
