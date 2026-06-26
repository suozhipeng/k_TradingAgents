# Phase 31 — K 线 API 字段清单与缺失 Metadata

生成时间：2026-06-25

## Endpoint: GET /api/v1/kline

来源：`tradingagents/astock/api/routes_data.py` `get_kline()`

### 请求参数

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `symbol` | string | 是 | — | A股标的代码 |
| `start` | string | 否 | — | 开始日期（YYYY-MM-DD） |
| `end` | string | 否 | — | 结束日期（YYYY-MM-DD） |
| `interval` | string | 否 | `1d` | K线间隔（1d, 5m, 30m, 60m） |
| `limit` | int | 否 | 0 | 最大条数（0=不限制） |

### 当前响应字段（200 OK）

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | string | 标的代码 |
| `interval` | string | K线间隔 |
| `bars` | array | K线数据数组 |

每条 bar 包含以下字段（经 data_sources/schema.py `_normalize_bar` 归一化）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` / `trade_date` / `datetime` | string | 日期 |
| `open` | float | 开盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `close` | float | 收盘价 |
| `volume` | number | 成交量 |
| `amount` | number | 成交额 |
| `turnover_rate` | number | 换手率 |
| `pe` | number | 市盈率 |
| `pb` | number | 市净率 |
| `market_cap` | number | 总市值 |

### 缺失 Metadata

| 缺失字段 | 问题 | 影响 |
|----------|------|------|
| ❌ `source` | 未标明数据来源（store/mootdx/akshare/cache） | 用户无法判断数据可信度 |
| ❌ `generated_at` | 未标明生成时间 | 无法判断数据新鲜度 |
| ❌ `freshness` | 未标注数据新鲜度等级 | 无法判断是否过期 |
| ❌ `quality` | 未标注数据质量等级 | 无法判断是否完整/降级 |
| ❌ `fallback_path` | 未标明数据降级路径 | 无法追溯是否经过 fallback |
| ❌ `data_snapshot_id` | 未提供数据快照 ID | 无法追溯具体数据版本 |
| ❌ `capability` | 未标注能力等级 | 无法区分 research/paper |
| ❌ `cache_hit` | 未标明是否缓存 | 前端无法决定是否提示用户 |

### 示例：缺失 metadata 的响应

```json
{
  "symbol": "600519.SH",
  "interval": "1d",
  "bars": [...]   // ← 无 metadata
}
```

### 目标：补充 metadata 后的响应

```json
{
  "success": true,
  "data": {
    "symbol": "600519.SH",
    "interval": "1d",
    "bars": [...]
  },
  "meta": {
    "capability": "research",
    "source": "duckdb",
    "freshness": "fresh",
    "quality": "normal",
    "generated_at": "2026-06-25T10:00:00Z",
    "fallback_path": ["duckdb", "mootdx"]
  }
}
```

## Endpoint: GET /api/v1/data/health

来源：`routes_data_health.py` `data_health()`

当前已包含：

| 字段 | 说明 |
|------|------|
| `sources[]` | 每个 adapter 的健康信息 |
| `sources[].name` | 数据源名称 |
| `sources[].available` | 是否可用 |
| `sources[].latency_ms` | 延迟（毫秒） |
| `sources[].error` | 错误信息 |
| `sources[].mock` | 是否 mock |
| `summary.total` | 总数据源数 |
| `summary.available` | 可用数量 |
| `summary.degraded` | 降级数量 |
| `cleaning` | 数据清洗统计 |

### 缺失字段

| 缺失字段 | 问题 |
|----------|------|
| ❌ `freshness` | 数据源最后成功更新时间 |
| ❌ `quality` | 数据源当前质量等级 |
| ❌ `last_checked` | 上次检查时间 |

---
**Commit SHA**: b410074
