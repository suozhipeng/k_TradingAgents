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

const BASE = "http://localhost:5860/api/v1";

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
  const url = `${BASE}${path}`;
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
        `/kline?${params}`,
      );
    },

    fetchValuation(symbol: string) {
      return request<{ symbol: string; valuations: Array<Record<string, unknown>> }>(
        `/valuation?symbol=${encodeURIComponent(symbol)}`,
      );
    },

    fetchOrderbook(symbol: string) {
      return request<{ symbol: string; snapshots: Array<Record<string, unknown>> }>(
        `/orderbook?symbol=${encodeURIComponent(symbol)}`,
      );
    },

    fetchNews(symbol: string, limit = 20) {
      return request<{ symbol: string; news: Array<Record<string, unknown>> }>(
        `/news?symbol=${encodeURIComponent(symbol)}&limit=${limit}`,
      );
    },

    fetchResearch(symbol: string, limit = 20) {
      return request<{ symbol: string; reports: Array<Record<string, unknown>> }>(
        `/research?symbol=${encodeURIComponent(symbol)}&limit=${limit}`,
      );
    },

    fetchAnnouncements(symbol: string, limit = 20) {
      return request<{ symbol: string; announcements: Array<Record<string, unknown>> }>(
        `/announcements?symbol=${encodeURIComponent(symbol)}&limit=${limit}`,
      );
    },

    fetchStoreStats() {
      return request<{ stats: Record<string, { rows: number; latest_date: string | null }> }>(
        "/store/stats",
      );
    },

    // ---- Backtest endpoints --------------------------------------------

    runBacktest(params: BacktestRunParams) {
      return request<Record<string, unknown>>("/backtest/run", {
        method: "POST",
        body: JSON.stringify(params),
      });
    },

    fetchBacktestResults(strategy?: string) {
      const qs = strategy ? `?strategy=${encodeURIComponent(strategy)}` : "";
      return request<{ results: Array<Record<string, unknown>> }>(`/backtest/results${qs}`);
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
        `/backtest/compare?${params}`,
      );
    },

    // ---- Paper trading endpoints ---------------------------------------

    runPaperCycle(signals: Record<string, number>, prices: Record<string, number>) {
      return request<Record<string, unknown>>("/paper/cycle", {
        method: "POST",
        body: JSON.stringify({ signals, prices }),
      });
    },

    fetchPaperState() {
      return request<Record<string, unknown>>("/paper/state");
    },

    fetchPaperTrades() {
      return request<{ trades: Array<Record<string, unknown>> }>("/paper/trades");
    },

    // ---- Market endpoints ----------------------------------------------

    fetchMarketSummary(symbol: string) {
      return request<Record<string, unknown>>(
        `/market/summary?symbol=${encodeURIComponent(symbol)}`,
      );
    },

    fetchStrategies() {
      return request<{ strategies: Array<{ name: string; description: string }> }>(
        "/market/strategies",
      );
    },

    // ---- QMT endpoints -------------------------------------------------

    fetchQmtHealth() {
      return request<{ healthy: boolean; mock_mode: boolean }>("/qmt/health");
    },

    fetchQmtPositions() {
      return request<{ positions: Array<Record<string, unknown>>; mock_mode: boolean }>(
        "/qmt/positions",
      );
    },

    fetchQmtOrders() {
      return request<{ orders: Array<Record<string, unknown>>; mock_mode: boolean }>(
        "/qmt/orders",
      );
    },

    // ---- Health --------------------------------------------------------

    health() {
      return request<{ status: string; version: string }>("/health");
    },
  };
}
