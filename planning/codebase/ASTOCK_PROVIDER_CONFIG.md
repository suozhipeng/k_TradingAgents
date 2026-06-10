# A 股 Provider 配置与收口验收说明

本文档记录 `tradingagents.astock.data_sources` 只读数据源层的安装、环境变量和 live 验证边界。本文档不包含任何 Cookie、token 或真实凭证。

## 安装

基础安装不强制安装所有 A 股真实 Provider。需要真实 Provider 验证时安装可选依赖：

```bash
python3 -m pip install --user '.[astock-providers]'
```

也可以按需安装：

```bash
python3 -m pip install --user akshare mootdx pywencai
```

当前 provider 层保持只读，不实现 QMT 下单。

## 环境变量

### Akshare

- `ASTOCK_AKSHARE_DISABLE_ENV_PROXY`: 可选。设置为 `1/true/on` 时，调用 Akshare 期间临时屏蔽 `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY` 等环境代理。
- `ASTOCK_AKSHARE_ALLOW_TENCENT_SUPPLEMENT`: 可选。默认 `false`。设置为 `1/true/on` 后，Akshare 估值字段缺失或接口不可用时，允许显式从 Tencent 补充 PE/PB/市值/换手率等字段。

说明：
- Tencent 补充默认关闭。
- 一旦启用并实际补充，响应 `meta.provider` 会标记为 `akshare+tencent`，`meta.field_sources` 会记录每个字段来源，不会伪装成纯 Akshare。

### Tencent Finance

- `ASTOCK_TENCENT_TIMEOUT`: 可选，请求 timeout 秒数。
- `ASTOCK_TENCENT_HEADERS_JSON`: 可选，JSON 格式请求头覆盖。

真实接口：
- `https://qt.gtimg.cn/q=...`
- `https://stock.gtimg.cn/data/index.php?appn=detail&action=data&c=...`

### Cninfo 巨潮资讯

- `ASTOCK_CNINFO_COOKIE`: 可选；如果巨潮增加访问限制，可配置浏览器 Cookie。
- `ASTOCK_CNINFO_CSRF_TOKEN`: 可选。
- `ASTOCK_CNINFO_USER_AGENT`: 可选。
- `ASTOCK_CNINFO_TIMEOUT`: 可选。
- `ASTOCK_CNINFO_HEADERS_JSON`: 可选，JSON 格式请求头覆盖。

真实接口：
- `POST https://www.cninfo.com.cn/new/hisAnnouncement/query`
- `GET https://www.cninfo.com.cn/new/data/szse_stock.json`

### Mootdx

- `ASTOCK_MOOTDX_HOST`: 可选，指定 TDX 行情服务器。
- `ASTOCK_MOOTDX_PORT`: 可选，指定 TDX 行情服务器端口。
- `ASTOCK_MOOTDX_MARKET`: 可选，默认 `std`。
- `ASTOCK_MOOTDX_TIMEOUT`: 可选，默认 `5` 秒。

验证能力：
- K 线：`Quotes.bars(...)`
- 盘口：`Quotes.quotes(...)`
- 逐笔：`Quotes.transactions(...)`
- F10/finance：`Quotes.finance(...)`

连接失败时统一转为 `SOURCE_UNAVAILABLE`，由 router/fallback 处理，不向上层泄露 SDK 异常。

### Iwencai

- `ASTOCK_IWENCAI_COOKIE`: 必需，用于 live 验证和真实请求。
- `ASTOCK_IWENCAI_USER_AGENT`: 可选。
- `ASTOCK_IWENCAI_RETRY`: 可选。
- `ASTOCK_IWENCAI_SLEEP`: 可选。
- `ASTOCK_IWENCAI_TIMEOUT`: 可选。
- `ASTOCK_IWENCAI_PER_PAGE`: 可选。

安全约束：
- Cookie 不得写入代码、fixture、日志或 Git。
- live test 输出只打印状态、条数和字段名，不打印 Cookie。

## 验收命令

离线与 blueprint 回归：

```bash
pytest -q tests/test_astock_data_sources.py tests/test_astock_blueprint.py tests/test_astock_provider_fixtures.py
```

真实 Provider live 验证：

```bash
ASTOCK_RUN_LIVE_TESTS=1 pytest -q tests/test_astock_live_providers.py -m integration
```

如果本机 `pytest` 不在 PATH，可用：

```bash
python3 -m pytest -q tests/test_astock_data_sources.py tests/test_astock_blueprint.py tests/test_astock_provider_fixtures.py
ASTOCK_RUN_LIVE_TESTS=1 python3 -m pytest -q tests/test_astock_live_providers.py -m integration
```

## Live 状态标记规则

- 只有在 `ASTOCK_RUN_LIVE_TESTS=1` 下真实访问通过的能力，才能写入 `blueprint.data_entrypoint.provider_status.*.live_verified`。
- 依赖缺失、凭证缺失或远端不可达导致 skip 的能力，只能保留在 `implemented` / `fixture_verified`，不得标记为 `live_verified`。
- QMT 在本阶段只保留占位，不实现交易执行。