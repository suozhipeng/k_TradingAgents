/**
 * API client hook — thin fetch wrapper around the Flask REST API.
 *
 * All methods return the raw JSON response body.  Errors are thrown
 * as ``ApiError`` instances.
 *
 * @example
 * ```ts
 * const api = useApi();
 * const kline = await api.fetchKline("600519.SH", "2024-01-01", "2024-06-01");
 * ```
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function request<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  // When VITE_API_BASE_URL is set, use it directly (production/proxy)
  // When empty, fetch goes to same origin (Vite dev proxy rewrites /api)
  const url = API_BASE ? `${API_BASE}${path}` : path;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    ...options,
  });

  const body = await res.json().catch(() => null);

  if (!res.ok) {
    throw new ApiError(
      body?.error ?? `HTTP ${res.status}`,
      res.status,
      body,
    );
  }

  return body as T;
}

export interface BacktestRunParams {
  symbol: string;
  strategy: string;
  start: string;
  end: string;
  rebalance_freq?: string;
}

export function useApi() {
  return {
    // ---- Data endpoints ------------------------------------------------

    fetchKline(
      symbol: string,
      start?: string,
      end?: string,
      interval = "1d",
    ) {
      const params = new URLSearchParams({ symbol, interval });
      if (start) params.set("start", start);
      if (end) params.set("end", end);
      return request<{ symbol: string; interval: string; bars: Array<Record<string, unknown>> }>(
        `/api/v1/kline?${params}`,
      );
    },

    fetchValuation(symbol: string) {
      return request<{ symbol: string; valuations: Array<Record<string, unknown>> }>(
        `/api/v1/valuation?symbol=${encodeURIComponent(symbol)}`,
      );
    },

    fetchOrderbook(symbol: string) {
      return request<{ symbol: string; snapshots: Array<Record<string, unknown>> }>(
        `/api/v1/orderbook?symbol=${encodeURIComponent(symbol)}`,
      );
    },

    fetchNews(symbol: string, limit = 20) {
      return request<{ symbol: string; news: Array<Record<string, unknown>> }>(
        `/api/v1/news?symbol=${encodeURIComponent(symbol)}&limit=${limit}`,
      );
    },

    fetchResearch(symbol: string, limit = 20) {
      return request<{ symbol: string; reports: Array<Record<string, unknown>> }>(
        `/api/v1/research?symbol=${encodeURIComponent(symbol)}&limit=${limit}`,
      );
    },

    fetchAnnouncements(symbol: string, limit = 20) {
      return request<{ symbol: string; announcements: Array<Record<string, unknown>> }>(
        `/api/v1/announcements?symbol=${encodeURIComponent(symbol)}&limit=${limit}`,
      );
    },

    fetchStoreStats() {
      return request<{ stats: Record<string, { rows: number; latest_date: string | null }> }>(
        "/api/v1/store/stats",
      );
    },

    // ---- Data refresh / jobs -------------------------------------------

    refreshKline(params: {
      symbols: string[];
      markets?: string[];
      intervals?: string[];
      start?: string;
      end?: string;
      force_refresh?: boolean;
    }) {
      return request<{ job_id: string; message: string }>(
        "/api/v1/data/refresh/kline",
        {
          method: "POST",
          body: JSON.stringify(params),
        },
      );
    },

    refreshValuation(params: {
      symbols: string[];
      start?: string;
      end?: string;
      force_refresh?: boolean;
    }) {
      return request<{ job_id: string; message: string }>(
        "/api/v1/data/refresh/valuation",
        {
          method: "POST",
          body: JSON.stringify(params),
        },
      );
    },

    refreshAll(params: {
      symbols?: string[];
      force_refresh?: boolean;
    }) {
      return request<{ job_id: string; message: string }>(
        "/api/v1/data/refresh/all",
        {
          method: "POST",
          body: JSON.stringify(params),
        },
      );
    },

    createRefreshJob(params: {
      job_type: string;
      symbols?: string[];
      markets?: string[];
      intervals?: string[];
      start?: string;
      end?: string;
      force_refresh?: boolean;
    }) {
      return request<{ job_id: string; message: string }>(
        "/api/v1/data/jobs/refresh",
        {
          method: "POST",
          body: JSON.stringify(params),
        },
      );
    },

    listJobs(params?: {
      status?: string;
      limit?: number;
      offset?: number;
    }) {
      const qs = new URLSearchParams();
      if (params?.status) qs.set("status", params.status);
      if (params?.limit) qs.set("limit", String(params.limit));
      if (params?.offset) qs.set("offset", String(params.offset));
      const query = qs.toString() ? `?${qs}` : "";
      return request<{ jobs: Array<Record<string, unknown>>; total: number }>(
        `/api/v1/data/jobs${query}`,
      );
    },

    getJob(jobId: string): Promise<{ job: Record<string, unknown> }> {
      return request<{ job: Record<string, unknown> }>(
        `/api/v1/data/jobs/${jobId}`,
      );
    },

    // ---- Cache / Store -------------------------------------------------

    cacheStatus() {
      return request<{ status: Record<string, unknown> }>(
        "/api/v1/cache/status",
      );
    },

    // ---- Backtest endpoints --------------------------------------------

    runBacktest(params: BacktestRunParams) {
      return request<Record<string, unknown>>("/api/v1/backtest/run", {
        method: "POST",
        body: JSON.stringify(params),
      });
    },

    fetchBacktestResults(strategy?: string) {
      const qs = strategy ? `?strategy=${encodeURIComponent(strategy)}` : "";
      return request<{ results: Array<Record<string, unknown>> }>(
        `/api/v1/backtest/results${qs}`,
      );
    },

    compareBacktests(
      strategies: string[],
      symbol: string,
      start: string,
      end: string,
    ) {
      const params = new URLSearchParams({
        strategies: strategies.join(","),
        symbol,
        start,
        end,
      });
      return request<{ comparison: Array<Record<string, unknown>> }>(
        `/api/v1/backtest/compare?${params}`,
      );
    },

    // ---- Paper trading endpoints ---------------------------------------

    runPaperCycle(signals: Record<string, number>, prices: Record<string, number>) {
      return request<Record<string, unknown>>("/api/v1/paper/cycle", {
        method: "POST",
        body: JSON.stringify({ signals, prices }),
      });
    },

    fetchPaperState() {
      return request<Record<string, unknown>>("/api/v1/paper/state");
    },

    fetchPaperTrades() {
      return request<{ trades: Array<Record<string, unknown>> }>("/api/v1/paper/trades");
    },

    // ---- Market endpoints ----------------------------------------------

    fetchMarketSummary(symbol: string) {
      return request<Record<string, unknown>>(
        `/api/v1/market/summary?symbol=${encodeURIComponent(symbol)}`,
      );
    },

    fetchStrategies() {
      return request<{ strategies: Array<{ name: string; description: string }> }>(
        "/api/v1/market/strategies",
      );
    },

    // ---- QMT endpoints -------------------------------------------------

    fetchQmtHealth() {
      return request<{ healthy: boolean; mock_mode: boolean }>("/api/v1/qmt/health");
    },

    fetchQmtPositions() {
      return request<{ positions: Array<Record<string, unknown>>; mock_mode: boolean }>(
        "/api/v1/qmt/positions",
      );
    },

    fetchQmtOrders() {
      return request<{ orders: Array<Record<string, unknown>>; mock_mode: boolean }>(
        "/api/v1/qmt/orders",
      );
    },

    // ---- Generic -----------------------------------------------------

    request(path: string, options: RequestInit = {}) {
      return request(path, options);
    },

    // ---- Health --------------------------------------------------------

    health() {
      return request<{ status: string; version: string }>("/api/v1/health");
    },
  };
}
