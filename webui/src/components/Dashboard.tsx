/**
 * Dashboard — Real homepage with market overview, data source health,
 * freshness indicators, watchlist, recent tasks, reports, and alerts.
 */

import { useEffect, useState, useCallback } from "react";
import type { ApiResponse } from "../hooks/useApi";
import { useApi } from "../hooks/useApi";

/* ── Types ─────────────────────────────────────────────────────── */

interface DashboardOverview {
  statistics?: {
    symbols_tracked?: number;
    backtests_total?: number;
    paper_positions?: number;
    paper_return_pct?: number;
    paper_total_value?: number;
  };
  recent_backtests?: Array<Record<string, unknown>>;
  latest_equity_curve?: Array<Record<string, unknown>>;
  decision_summary?: Record<string, unknown>;
  paper_positions_detail?: Array<Record<string, unknown>>;
  recent_trades?: Array<Record<string, unknown>>;
  paper_equity_curve?: Array<Record<string, unknown>>;
}

interface MarketSummary {
  indices?: Array<Record<string, unknown>>;
  sector_ranking?: Array<Record<string, unknown>>;
  northbound_flow?: Record<string, unknown>;
  limit_up_down?: Record<string, unknown>;
}

interface DataFreshness {
  kline_latest?: string;
  valuation_latest?: string;
  [key: string]: unknown;
}

interface AlertItem {
  id: string;
  rule_id: string;
  symbol?: string;
  message: string;
  severity?: string;
  created_at: string;
  acknowledged?: boolean;
}

/* ── Helpers ───────────────────────────────────────────────────── */

const fmtNum = (v: unknown, decimals = 2) =>
  typeof v === "number" ? v.toFixed(decimals) : String(v ?? "—");

const fmtDate = (v: unknown) => {
  if (!v) return "—";
  const d = new Date(String(v));
  return isNaN(d.getTime()) ? String(v) : d.toLocaleDateString("zh-CN");
};

const Card: React.FC<{
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  status?: "ok" | "warn" | "error";
}> = ({ title, subtitle, children, status }) => (
  <div
    className={`rounded-lg border p-4 ${
      status === "error"
        ? "border-rose-500/30 bg-rose-500/[0.05]"
        : status === "warn"
          ? "border-amber-500/30 bg-amber-500/[0.05]"
          : "border-slate-700/50 bg-slate-800/50"
    }`}
  >
    <div className="mb-2 flex items-center justify-between">
      <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
      {subtitle && <span className="text-xs text-slate-400">{subtitle}</span>}
    </div>
    {children}
  </div>
);

/* ── Components ────────────────────────────────────────────────── */

/* Mini sparkline from equity curve data */
const SparkLine: React.FC<{ data: Array<Record<string, unknown>> }> = ({
  data,
}) => {
  if (!data || data.length < 2) return <span className="text-xs text-slate-500">数据不足</span>;

  const values = data
    .map((d) => (d.value as number) ?? (d.end_value as number) ?? 0)
    .filter((v) => v > 0);
  if (values.length < 2) return <span className="text-xs text-slate-500">数据不足</span>;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 120;
  const h = 32;
  const points = values
    .map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / range) * h}`)
    .join(" ");

  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={points} fill="none" stroke="#60a5fa" strokeWidth="1.5" />
    </svg>
  );
};

/* Freshness badge */
const FreshnessBadge: React.FC<{ latest?: string; label: string }> = ({
  latest,
  label,
}) => {
  if (!latest)
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-slate-700/50 px-2 py-0.5 text-xs text-slate-400">
        <span className="h-1.5 w-1.5 rounded-full bg-slate-500" />
        {label}: 未知
      </span>
    );

  const d = new Date(latest);
  const ageSec = isNaN(d.getTime()) ? 0 : (Date.now() - d.getTime()) / 1000;
  let color = "bg-emerald-500";
  if (ageSec > 86400) color = "bg-rose-500";
  else if (ageSec > 43200) color = "bg-amber-500";

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-slate-700/50 px-2 py-0.5 text-xs text-slate-300">
      <span className={`h-1.5 w-1.5 rounded-full ${color}`} />
      {label}: {fmtDate(latest)}
    </span>
  );
};

/* Watchlist mini-table */
const WatchlistTable: React.FC<{
  items: Array<Record<string, unknown>>;
  onRemove: (sym: string) => void;
}> = ({ items, onRemove }) => (
  <div className="overflow-x-auto">
    <table className="w-full text-left text-xs">
      <thead>
        <tr className="border-b border-slate-700/50 text-slate-400">
          <th className="pb-1 pr-2">代码</th>
          <th className="pb-1 pr-2">名称</th>
          <th className="pb-1 pr-2 text-right">最新价</th>
          <th className="pb-1 pr-2 text-right">涨跌幅</th>
          <th className="pb-1 text-right">操作</th>
        </tr>
      </thead>
      <tbody>
        {items.slice(0, 5).map((item, i) => (
          <tr key={i} className="border-b border-slate-800/50">
            <td className="py-1 pr-2 font-mono text-slate-200">
              {String(item.symbol ?? "—")}
            </td>
            <td className="py-1 pr-2 text-slate-300">
              {String(item.name ?? "—")}
            </td>
            <td className="py-1 pr-2 text-right font-mono text-slate-200">
              {fmtNum(item.latest_price ?? item.price)}
            </td>
            <td
              className={`py-1 pr-2 text-right font-mono ${
                (item.change_pct as number) >= 0 ? "text-emerald-400" : "text-rose-400"
              }`}
            >
              {fmtNum(item.change_pct, 2)}%
            </td>
            <td className="py-1 text-right">
              <button
                onClick={() => onRemove(String(item.symbol))}
                className="text-rose-400 hover:text-rose-300"
              >
                移除
              </button>
            </td>
          </tr>
        ))}
        {items.length === 0 && (
          <tr>
            <td colSpan={5} className="py-3 text-center text-slate-500">
              暂无自选股，请在右侧添加
            </td>
          </tr>
        )}
      </tbody>
    </table>
  </div>
);

/* ── Main Component ────────────────────────────────────────────── */

export default function Dashboard() {
  const api = useApi();
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [marketSummary, setMarketSummary] = useState<MarketSummary | null>(null);
  const [freshness, setFreshness] = useState<DataFreshness | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /* Watchlist state */
  const [watchlist, setWatchlist] = useState<Array<Record<string, unknown>>>([]);
  const [newSymbol, setNewSymbol] = useState("");

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [ovRes, msRes, frRes, alRes] = await Promise.allSettled([
        api.getDashboardOverview(),
        api.getMarketSummary(),
        api.getDataFreshness(),
        api.listAlerts(),
      ]);

      if (ovRes.status === "fulfilled") setOverview(ovRes.value as DashboardOverview);
      if (msRes.status === "fulfilled") setMarketSummary(msRes.value as MarketSummary);
      if (frRes.status === "fulfilled") setFreshness(frRes.value as DataFreshness);
      if (alRes.status === "fulfilled") {
        const raw = alRes.value as { alerts?: AlertItem[] };
        setAlerts(raw.alerts?.filter((a) => !a.acknowledged) ?? []);
      }

      /* Also fetch watchlist */
      try {
        const wlRes = await api.getWatchlist();
        setWatchlist((wlRes as { items?: Array<Record<string, unknown>> })?.items ?? []);
      } catch {
        /* watchlist may not exist yet */
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    loadData();
    const poll = () => {
      // Do not consume provider/API capacity while this dashboard is hidden.
      if (!document.hidden) loadData();
    };
    const onVisibilityChange = () => {
      if (!document.hidden) loadData();
    };
    const timer = setInterval(poll, 60_000); /* 1 min poll */
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [loadData]);

  /* Watchlist actions */
  const addToWatchlist = async () => {
    const sym = newSymbol.trim().toUpperCase();
    if (!sym) return;
    try {
      await api.addWatchlistSymbol(sym);
      setNewSymbol("");
      loadData();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const removeFromWatchlist = async (sym: string) => {
    try {
      await api.removeWatchlistSymbol(sym);
      loadData();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="animate-spin rounded-full border-2 border-blue-500 border-t-transparent h-8 w-8" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-rose-500/30 bg-rose-500/[0.05] p-6 text-center">
        <p className="text-rose-300">加载失败: {error}</p>
        <button
          onClick={loadData}
          className="mt-3 rounded bg-rose-500/20 px-3 py-1 text-sm text-rose-300 hover:bg-rose-500/30"
        >
          重试
        </button>
      </div>
    );
  }

  const stats = overview?.statistics ?? {};
  const decisions = overview?.decision_summary ?? {};

  return (
    <div className="space-y-4">
      {/* Top row: stats cards + freshness */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card title="跟踪标的" status="ok">
          <p className="text-2xl font-bold text-blue-400">{stats.symbols_tracked ?? "—"}</p>
        </Card>
        <Card title="回测次数" status="ok">
          <p className="text-2xl font-bold text-purple-400">{stats.backtests_total ?? "0"}</p>
        </Card>
        <Card title="模拟持仓" status="ok">
          <p className="text-2xl font-bold text-emerald-400">{stats.paper_positions ?? "0"}</p>
        </Card>
        <Card title="模拟收益" status={stats.paper_return_pct && (stats.paper_return_pct as number) < 0 ? "warn" : "ok"}>
          <p className={`text-2xl font-bold ${(stats.paper_return_pct as number) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {fmtNum(stats.paper_return_pct)}%
          </p>
        </Card>
      </div>

      {/* Freshness badges */}
      <div className="flex flex-wrap gap-2">
        {freshness && (
          <>
            <FreshnessBadge latest={freshness.kline_latest} label="K线" />
            <FreshnessBadge latest={freshness.valuation_latest} label="估值" />
            {Object.entries(freshness).map(([k, v]) =>
              !["kline_latest", "valuation_latest"].includes(k) ? (
                <FreshnessBadge key={k} latest={String(v)} label={k} />
              ) : null
            )}
          </>
        )}
      </div>

      {/* Middle row: market summary + decision summary */}
      <div className="grid gap-3 md:grid-cols-2">
        {/* Market indices */}
        <Card title="主要指数" subtitle={marketSummary ? `${(marketSummary as { timestamp?: string }).timestamp ?? ""}` : ""}>
          {marketSummary?.indices && (marketSummary.indices as Array<Record<string, unknown>>).length > 0 ? (
            <div className="space-y-1">
              {(marketSummary.indices as Array<Record<string, unknown>>).slice(0, 5).map((idx, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="font-medium text-slate-300">{String(idx.name ?? idx.symbol ?? `指数${i + 1}`)}</span>
                  <span className="font-mono text-slate-200">{fmtNum(idx.last)}</span>
                  <span className={`font-mono ${(idx.change_pct as number) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {fmtNum(idx.change_pct, 2)}%
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500">暂无指数数据</p>
          )}
        </Card>

        {/* Decision summary */}
        <Card title="决策摘要">
          {Object.keys(decisions).length > 0 ? (
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(decisions).map(([key, val]) => (
                <div key={key} className="rounded bg-slate-800/50 p-2 text-center">
                  <div className="text-xl font-bold text-blue-400">{String(val ?? "0")}</div>
                  <div className="text-xs text-slate-400">
                    {key === "buy" ? "买入" : key === "hold" ? "持有" : key === "sell" ? "卖出" : key}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500">暂无决策数据</p>
          )}
        </Card>
      </div>

      {/* Bottom row: watchlist + alerts */}
      <div className="grid gap-3 md:grid-cols-2">
        {/* Watchlist */}
        <Card title="自选股">
          <div className="mb-3 flex gap-2">
            <input
              type="text"
              placeholder="输入股票代码"
              value={newSymbol}
              onChange={(e) => setNewSymbol(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addToWatchlist()}
              className="flex-1 rounded border border-slate-700 bg-slate-800 px-2 py-1 text-sm text-slate-200 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
            />
            <button
              onClick={addToWatchlist}
              className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-500"
            >
              添加
            </button>
          </div>
          <WatchlistTable items={watchlist} onRemove={removeFromWatchlist} />
        </Card>

        {/* Alerts */}
        <Card title={`告警 (${alerts.length})`}>
          {alerts.length > 0 ? (
            <div className="space-y-2">
              {alerts.map((a) => (
                <div key={a.id} className="flex items-start justify-between rounded bg-amber-500/10 p-2 text-xs">
                  <div>
                    <span className="font-medium text-amber-300">{a.symbol ?? "—"}</span>
                    <span className="ml-2 text-slate-300">{a.message}</span>
                  </div>
                  <span className="text-slate-500">{fmtDate(a.created_at)}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500">暂无告警</p>
          )}
        </Card>
      </div>

      {/* Recent backtests */}
      {overview?.recent_backtests && (overview.recent_backtests as Array<Record<string, unknown>>).length > 0 && (
        <Card title="最近回测">
          <div className="space-y-2">
            {(overview.recent_backtests as Array<Record<string, unknown>>).slice(0, 3).map((bt, i) => (
              <div key={i} className="flex items-center justify-between rounded bg-slate-800/50 p-2 text-xs">
                <div>
                  <span className="font-medium text-slate-200">{String(bt.strategy ?? bt.name ?? "策略")}</span>
                  <span className="ml-2 text-slate-400">
                    {String(bt.period ?? bt.date_range ?? "")}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <SparkLine data={overview.latest_equity_curve ?? []} />
                  <span className={`font-mono ${(bt.sharpe as number) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    Sharpe: {fmtNum(bt.sharpe)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
