# Phase: Web-P2 — 每日分析、报告归档、推送闭环

**Status:** Completed  
**Date:** 2026-06-27  
**Author:** Hermes Agent

---

## Overview

Implements the Web-P2 parity milestone: watchlist management, report archive with filtering, notification settings, and batch analysis integration. Builds on top of Web-P0/P1 infrastructure.

## Components Implemented

### 1. Watchlist API (`GET/POST /api/v1/watchlist`)

- **File:** `tradingagents/astock/api/routes_watchlist.py`
- **Endpoints:**
  - `GET /api/v1/watchlist` — returns all tracked symbols
  - `POST /api/v1/watchlist/add` — add symbol `{symbol, name?, source?}`
  - `POST /api/v1/watchlist/remove` — remove symbol `{symbol}`
  - `POST /api/v1/watchlist/batch-analyze` — submit batch analysis task
- **Storage:** JSON file at `~/.tradingagents/watchlist.json` (temporary)
- **Fields per entry:** symbol, name, added_at, source
- **Planned migration:** DuckDB store

### 2. Watchlist Page (`/watchlist`)

- **File:** `tradingagents/astock/web/templates/watchlist.html`
- **Route:** `@bp.route("/watchlist")` in `web/__init__.py`
- **Features:**
  - Table view of all tracked symbols with code, name, added_at, source
  - Add symbol via text input
  - Quick-add buttons for common A-stock names (茅台, 平安, 招行, etc.)
  - Remove button per row
  - "批量分析" button that triggers batch analysis
  - All states: loading, empty (暂无自选股), error
- TV dark theme, `.tv-table`, `.tv-btn`, `.tv-badge` classes throughout

### 3. Batch Analysis Route (`/batch-analyze`)

- **Route:** `@bp.route("/batch-analyze")` in `web/__init__.py`
- Renders same watchlist.html with `batch_mode=True` context flag
- Triggers `POST /api/v1/watchlist/batch-analyze` which creates a queued task

### 4. Reports Archive API (`GET /api/v1/reports/list`)

- **File:** `tradingagents/astock/api/routes_reports.py` (enhanced)
- **Endpoints:**
  - `GET /api/v1/reports/list` — filterable archive listing
    - Query params: `type` (market/watchlist/single/all), `source`, `limit`, `offset`
  - `POST /api/v1/reports/save` — save a report to archive
- **Fields per report:** symbol, report_type, source, summary, created_at, advisory_only, actionable, data_snapshot, trade_date
- **Storage:** JSON file at `~/.tradingagents/report_index.json` (temporary)
- **Planned migration:** DuckDB store

### 5. Reports Page Enhanced (`/reports`)

- **File:** `tradingagents/astock/web/templates/reports.html` (rewritten)
- **Improvements:**
  - Report type filter (single/market/watchlist)
  - Source/provider filter (DeepSeek/OpenAI/Claude/API)
  - Mode filter (Advisory vs Actionable)
  - Data snapshot reference display
  - "保存到归档" button on generated reports
  - Auto-save on generation
  - Archive stats (total, today, source coverage)

### 6. Notification Settings (`/settings`)

- **File:** `tradingagents/astock/web/templates/settings.html` (enhanced)
- **Notification channels table:**
  - **Terminal:** verified, togglable
  - **Desktop Notification:** marked "未验证" until user grants permission
  - **Webhook:** URL input + "测试" button + "未验证" badge
  - **Email:** placeholder (grayed out)
  - **WeCom/DingTalk:** placeholder (grayed out)
- **Push rules toggles:** report completion, batch analysis, watchlist alert, trade signal
- **Dedicated URL:** `/settings/notifications` scrolls to notification section

### 7. Notification Test API

- **File:** `tradingagents/astock/api/routes_notifications.py`
- **Endpoint:** `POST /api/v1/notifications/test-webhook`
- Sends test payload to webhook URL, returns success/failure

### 8. Blueprint Registration

- **Files modified:** `tradingagents/astock/api/__init__.py`
- Registered: `routes_watchlist`, `routes_notifications`

## Key Design Decisions

1. **No mock data** — all APIs return real data or empty states (暂无数据)
2. **JSON file fallback** — DuckDB not required for watchlist/archive to work
3. **Chinese UI** — all labels and messages in Chinese
4. **TV dark theme** — consistent `#0a0e17` background, `#1c2538` cards
5. **No duplication** — dashboard already has reports/tasks sections
6. **All states handled** — loading, empty, error, degraded

## File Inventory

| File | Status | Lines |
|------|--------|-------|
| `tradingagents/astock/api/routes_watchlist.py` | NEW | ~160 |
| `tradingagents/astock/api/routes_notifications.py` | NEW | ~55 |
| `tradingagents/astock/api/routes_reports.py` | MODIFIED | +120 |
| `tradingagents/astock/api/__init__.py` | MODIFIED | +4 |
| `tradingagents/astock/web/__init__.py` | MODIFIED | +16 |
| `tradingagents/astock/web/templates/watchlist.html` | NEW | ~200 |
| `tradingagents/astock/web/templates/reports.html` | REWRITTEN | ~350 |
| `tradingagents/astock/web/templates/settings.html` | REWRITTEN | ~350 |
| `docs/phases/phase-web-p2-daily-analysis-report-archive.md` | NEW | This file |

## Future Work

- Migrate watchlist/report archive from JSON to DuckDB
- Add real batch analysis worker (currently queues task only)
- Add email SMTP configuration
- Add WeCom/DingTalk bot channels
- System tray / OS-level notifications
- Scheduled daily summary report generation
