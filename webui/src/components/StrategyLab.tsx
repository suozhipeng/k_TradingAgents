/**
 * Strategy Lab — Backtest runner, results viewer, MC Leaders dashboard.
 */

import { useState, useEffect, useCallback } from "react";
import { useApi } from "../hooks/useApi";

/* ── Types ─────────────────────────────────────────────────────── */

interface BacktestResult {
  run_id: string;
  strategy: string;
  symbol: string;
  start_date: string;
  end_date: string;
  sharpe?: number;
  max_drawdown?: number;
  total_return?: number;
  equity_curve?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

interface LeaderStock {
  symbol: string;
  name?: string;
  sector?: string;
  score?: number;
  momentum?: number;
  [key: string]: unknown;
}

/* ── Sub-components ────────────────────────────────────────────── */

const EquityCurveChart: React.FC<{ data: Array<Record<string, unknown>> }> = ({
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
  const w = 600;
  const h = 180;
  const pad = 10;
  const points = values
    .map((v, i) => {
      const x = pad + (i / (values.length - 1)) * (w - 2 * pad);
      const y = h - pad - ((v - min) / range) * (h - 2 * pad);
      return `${x},${y}`;
    })
    .join(" ");

  const isProfit = values[values.length - 1] >= values[0];
  const color = isProfit ? "#10b981" : "#f43f5e";

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
      <defs>
        <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`${pad},${h} ${points} ${w - pad},${h}`} fill="url(#eqGrad)" />
      <polyline points={points} fill="none" stroke={color} strokeWidth="2" />
    </svg>
  );
};

/* ── Backtest Runner ────────────────────────────────────────────── */

const BacktestRunner: React.FC = () => {
  const api = useApi();
  const [symbol, setSymbol] = useState("600519.SH");
  const [strategy, setStrategy] = useState("ma_cross");
  const [startDate, setStartDate] = useState("2024-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const strategies = ["ma_cross", "rsi_reversal", "bollinger_breakout", "momentum_rotation"];

  const run = async () => {
    try {
      setRunning(true);
      setError(null);
      const res = await api.runBacktest({
        symbol,
        strategy,
        start: startDate,
        end: endDate,
      });
      setResult(res as BacktestResult);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="rounded-lg border border-slate-700/50 bg-slate-800/50 p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-200">回测运行</h3>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label className="mb-1 block text-xs text-slate-400">股票代码</label>
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            className="w-full rounded border border-slate-700 bg-slate-900/50 px-2 py-1.5 text-sm font-mono text-slate-200 focus:border-blue-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">策略</label>
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            className="w-full rounded border border-slate-700 bg-slate-900/50 px-2 py-1.5 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
          >
            {strategies.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">开始日期</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="w-full rounded border border-slate-700 bg-slate-900/50 px-2 py-1.5 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">结束日期</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="w-full rounded border border-slate-700 bg-slate-900/50 px-2 py-1.5 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
          />
        </div>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <button
          onClick={run}
          disabled={running}
          className="rounded bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-500 disabled:opacity-50"
        >
          {running ? "运行中..." : "运行回测"}
        </button>
        {error && <span className="text-sm text-rose-400">{error}</span>}
      </div>
      {result && (
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-4 gap-2 text-xs">
            <div className="rounded bg-slate-900/50 p-2 text-center">
              <div className="text-slate-500">Sharpe</div>
              <div className="font-mono font-bold text-blue-400">
                {result.sharpe != null ? result.sharpe.toFixed(2) : "—"}
              </div>
            </div>
            <div className="rounded bg-slate-900/50 p-2 text-center">
              <div className="text-slate-500">最大回撤</div>
              <div className="font-mono font-bold text-rose-400">
                {result.max_drawdown != null ? `${(result.max_drawdown * 100).toFixed(2)}%` : "—"}
              </div>
            </div>
            <div className="rounded bg-slate-900/50 p-2 text-center">
              <div className="text-slate-500">总收益</div>
              <div className="font-mono font-bold text-emerald-400">
                {result.total_return != null ? `${(result.total_return * 100).toFixed(2)}%` : "—"}
              </div>
            </div>
            <div className="rounded bg-slate-900/50 p-2 text-center">
              <div className="text-slate-500">期间</div>
              <div className="font-mono text-slate-200">{result.start_date} ~ {result.end_date}</div>
            </div>
          </div>
          {result.equity_curve && (
            <div>
              <div className="mb-1 text-xs text-slate-400">权益曲线</div>
              <EquityCurveChart data={result.equity_curve as Array<Record<string, unknown>>} />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

/* ── MC Leaders Table ──────────────────────────────────────────── */

const McLeadersTable: React.FC = () => {
  const api = useApi();
  const [leaders, setLeaders] = useState<LeaderStock[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getMarketOverview().then((res) => {
      const data = res as { leaders?: LeaderStock[] };
      setLeaders(data.leaders ?? []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [api]);

  if (loading) return <div className="flex h-32 items-center justify-center"><div className="animate-spin rounded-full border-2 border-blue-500 border-t-transparent h-6 w-6" /></div>;

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-700/50 bg-slate-800/50">
      <table className="w-full text-left text-xs">
        <thead className="bg-slate-900/50 text-slate-400">
          <tr>
            <th className="px-3 py-2">排名</th>
            <th className="px-3 py-2">代码</th>
            <th className="px-3 py-2">名称</th>
            <th className="px-3 py-2">板块</th>
            <th className="px-3 py-2 text-right">得分</th>
            <th className="px-3 py-2 text-right">动量</th>
          </tr>
        </thead>
        <tbody>
          {leaders.slice(0, 10).map((l, i) => (
            <tr key={l.symbol} className="border-b border-slate-800/50">
              <td className="px-3 py-2 font-mono text-slate-300">{i + 1}</td>
              <td className="px-3 py-2 font-mono text-blue-400">{l.symbol}</td>
              <td className="px-3 py-2 text-slate-200">{l.name ?? "—"}</td>
              <td className="px-3 py-2 text-slate-300">{l.sector ?? "—"}</td>
              <td className="px-3 py-2 text-right font-mono text-emerald-400">
                {l.score != null ? Number(l.score).toFixed(2) : "—"}
              </td>
              <td className="px-3 py-2 text-right font-mono text-slate-300">
                {l.momentum != null ? Number(l.momentum).toFixed(2) : "—"}
              </td>
            </tr>
          ))}
          {leaders.length === 0 && (
            <tr><td colSpan={6} className="py-6 text-center text-slate-500">暂无龙头数据</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

/* ── Backtest History ──────────────────────────────────────────── */

const BacktestHistory: React.FC = () => {
  const api = useApi();
  const [results, setResults] = useState<BacktestResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getBacktestResults().then((res) => {
      const data = res as { results?: BacktestResult[] };
      setResults(data.results ?? []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [api]);

  if (loading) return <div className="flex h-32 items-center justify-center"><div className="animate-spin rounded-full border-2 border-blue-500 border-t-transparent h-6 w-6" /></div>;

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-700/50 bg-slate-800/50">
      <table className="w-full text-left text-xs">
        <thead className="bg-slate-900/50 text-slate-400">
          <tr>
            <th className="px-3 py-2">ID</th>
            <th className="px-3 py-2">策略</th>
            <th className="px-3 py-2">标的</th>
            <th className="px-3 py-2">期间</th>
            <th className="px-3 py-2 text-right">Sharpe</th>
            <th className="px-3 py-2 text-right">回撤</th>
          </tr>
        </thead>
        <tbody>
          {results.slice(0, 10).map((r) => (
            <tr key={r.run_id} className="border-b border-slate-800/50">
              <td className="px-3 py-2 font-mono text-slate-300">{r.run_id.slice(0, 8)}</td>
              <td className="px-3 py-2 text-slate-200">{r.strategy}</td>
              <td className="px-3 py-2 font-mono text-blue-400">{r.symbol}</td>
              <td className="px-3 py-2 text-slate-300">{r.start_date}~{r.end_date}</td>
              <td className="px-3 py-2 text-right font-mono text-blue-400">
                {r.sharpe != null ? r.sharpe.toFixed(2) : "—"}
              </td>
              <td className="px-3 py-2 text-right font-mono text-rose-400">
                {r.max_drawdown != null ? `${(r.max_drawdown * 100).toFixed(1)}%` : "—"}
              </td>
            </tr>
          ))}
          {results.length === 0 && (
            <tr><td colSpan={6} className="py-6 text-center text-slate-500">无回测记录</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

/* ── Main Component ────────────────────────────────────────────── */

export default function StrategyLab() {
  const [activeTab, setActiveTab] = useState("backtest");
  const tabs = ["回测运行", "历史结果", "MC 龙头"];

  return (
    <div className="space-y-4">
      <div className="flex gap-1 border-b border-slate-700/50">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab
                ? "border-b-2 border-blue-500 text-blue-400"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="min-h-[300px]">
        {activeTab === "回测运行" && <BacktestRunner />}
        {activeTab === "历史结果" && <BacktestHistory />}
        {activeTab === "MC 龙头" && <McLeadersTable />}
      </div>
    </div>
  );
}
