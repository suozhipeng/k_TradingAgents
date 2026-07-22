# API Contract Baseline

All routes use the existing `/api/v1` prefix and the project's response envelope helpers.

## Existing endpoints used by the recovery path

- `GET /api/v1/health`
- `GET /api/v1/data/health`
- `GET /api/v1/dashboard/overview`
- `GET /api/v1/market/kline`
- `GET /api/v1/data/jobs/<job_id>`
- `POST /api/v1/data/jobs/refresh`
- `POST /api/v1/backtest/run`
- `GET /api/v1/backtest/results`

## Required V1.5 additions

### Setup

- `GET /api/v1/setup/status`
- `POST /api/v1/setup/bootstrap`
- `GET /api/v1/setup/jobs/<job_id>`

States: `ready`, `empty`, `degraded`, `blocked`, `migrating`, `refreshing`.

### Market review

- `GET /api/v1/market-review/status`
- `POST /api/v1/market-review/generate`
- `GET /api/v1/market-review/latest`
- `GET /api/v1/market-review/<trade_date>`
- Breadth, sentiment, sectors and leaders sub-resources are read-only persisted views.

### Stock analysis

- `POST /api/v1/analysis/stocks`
- `GET /api/v1/analysis/stocks/<symbol>/latest`
- `GET /api/v1/analysis/stocks/<symbol>/history`
- `GET /api/v1/analysis/runs/<run_id>`
- `GET /api/v1/analysis/runs/<run_id>/facts`
- `GET /api/v1/analysis/runs/<run_id>/report`

Responses must expose `data_state`, `data_cutoff`, `source`, `quality`, `interpretation_state`, and fact lineage. Insufficient data must not produce a deterministic buy/sell conclusion.

### Web paths

- `/data_hub?first_run=1`
- `/market_review`
- `/market_review/<trade_date>`
- `/analysis`
- `/analysis/<symbol>`
- Existing `/backtest` remains the final link in the review → analysis → backtest path.
