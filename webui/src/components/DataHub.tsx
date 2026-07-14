/**
 * Data Hub — Real market data download, incremental upsert, job tracking,
 * and provider health monitoring.
 */

import { useEffect, useState } from "react";
import { useApi } from "../hooks/useApi";

/* ── Types ─────────────────────────────────────────────────────── */

interface JobInfo {
  id: string;
  type: string;
  status: string;
  message: string;
  total: number;
  completed: number;
  result?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

interface RefreshOption {
  symbols: string[];
  intervals: string[];
  default_interval: string;
  modes: string[];
  include_valuation: boolean;
}

interface DataHealthSource {
  name: string;
  available: boolean;
  latency_ms?: number;
  error?: string;
  mock?: boolean;
  rate_limit_interval?: number;
  tables?: number;
}

interface DataHealthResult {
  sources: DataHealthSource[];
  summary: { total: number; available: number; degraded: number };
  quality_overall: string;
  cleaning?: Record<string, unknown>;
}

interface StoreStats {
  stats: Record<string, { rows: number; latest_date: string | null }>;
}

/* ── Sub-components ────────────────────────────────────────────── */

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "completed" ? "bg-emerald-400/20 text-emerald-200"
    : status === "running" ? "bg-blue-400/20 text-blue-200 animate-pulse"
    : status === "failed" ? "bg-rose-400/20 text-rose-200"
    : status === "pending" ? "bg-yellow-400/20 text-yellow-200"
    : "bg-slate-400/20 text-slate-200";
  return <span className={`rounded-full px-2 py-0.5 text-[11px] uppercase tracking-wider ${color}`}>{status}</span>;
}

function ProgressBar({ completed, total }: { completed: number; total: number }) {
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
  return (
    <div className="w-full rounded-full bg-slate-700/50">
      <div
        className="h-2 rounded-full bg-cyan-400 transition-all duration-300"
        style={{ width: `${pct}%` }}
      />
      <p className="mt-1 text-right text-xs text-slate-400">{completed}/{total} ({pct}%)</p>
    </div>
  );
}

function HealthSourceRow({ source }: { source: DataHealthSource }) {
  const icon = source.available
    ? source.mock ? "🟡" : "🟢"
    : "🔴";
  return (
    <div className="flex items-center justify-between rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2">
      <div className="flex items-center gap-2">
        <span>{icon}</span>
        <span className="text-sm text-slate-200">{source.name}</span>
      </div>
      <div className="flex items-center gap-3 text-xs text-slate-400">
        {source.latency_ms !== undefined && <span>{source.latency_ms}ms</span>}
        {source.tables !== undefined && <span>{source.tables} tables</span>}
        {source.error && <span className="text-rose-300">{source.error}</span>}
      </div>
    </div>
  );
}

/* ── Main Page ─────────────────────────────────────────────────── */

export default function DataHub() {
  const api = useApi();
  const [tab, setTab] = useState<"refresh" | "jobs" | "health" | "stats">("refresh");

  /* Refresh form state */
  const [symbols, setSymbols] = useState("");
  const [refreshOptions, setRefreshOptions] = useState<RefreshOption | null>(null);
  const [optionsError, setOptionsError] = useState("");
  const [interval, setIntervalVal] = useState("");
  const [mode, setMode] = useState<"incremental" | "range">("incremental");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [includeValuation, setIncludeValuation] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshResult, setRefreshResult] = useState<JobInfo | null>(null);
  const [refreshError, setRefreshError] = useState("");

  /* Jobs list */
  const [jobs, setJobs] = useState<JobInfo[]>([]);
  const [selectedJob, setSelectedJob] = useState<JobInfo | null>(null);
  const [jobsLoading, setJobsLoading] = useState(false);

  /* Health */
  const [health, setHealth] = useState<DataHealthResult | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);

  /* Store stats */
  const [storeStats, setStoreStats] = useState<StoreStats | null>(null);
  const [storeLoading, setStoreLoading] = useState(false);

  /* The server owns the valid refresh form values. */
  useEffect(() => {
    let cancelled = false;
    api.getRefreshOptions().then((options) => {
      if (cancelled) return;
      setRefreshOptions(options);
      setIntervalVal(options.default_interval);
      setMode(options.modes.includes("incremental") ? "incremental" : "range");
    }).catch((error: unknown) => {
      if (!cancelled) setOptionsError(error instanceof Error ? error.message : String(error));
    });
    return () => { cancelled = true; };
  }, [api]);

  /* Poll jobs list periodically */
  useEffect(() => {
    if (tab !== "jobs") return;
    let cancelled = false;
    setJobsLoading(true);
    api.listJobs({ limit: 50 }).then((res) => {
      if (!cancelled) {
        setJobs((res as unknown as { jobs: JobInfo[] }).jobs ?? []);
        setJobsLoading(false);
      }
    }).catch(() => {
      if (!cancelled) setJobsLoading(false);
    });
    return () => { cancelled = true; };
  }, [tab, api]);

  /* Poll selected job for progress */
  useEffect(() => {
    if (!selectedJob || selectedJob.status !== "running") return;
    const poll = () => {
      if (document.hidden) return;
      api.getJob(selectedJob.id).then((res) => {
        const job = (res as unknown as { job: JobInfo }).job;
        if (job) setSelectedJob(job);
      }).catch(() => {});
    };
    const id = setInterval(poll, 2000);
    const onVisibilityChange = () => { if (!document.hidden) poll(); };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [selectedJob, api]);

  /* Refresh handler */
  const handleRefresh = async () => {
    if (!refreshOptions || !interval || !refreshOptions.modes.includes(mode)) return;
    setRefreshing(true);
    setRefreshError("");
    setRefreshResult(null);
    try {
      const body: Record<string, unknown> = {
        symbols: symbols.trim() ? symbols.split(/[,;\s]+/).filter(Boolean) : ["all"],
        interval,
        mode,
        include_valuation: includeValuation,
      };
      if (mode === "range") {
        if (startDate) body.start = startDate;
        if (endDate) body.end = endDate;
      }
      const res = await api.createRefreshJob(body as Parameters<typeof api.createRefreshJob>[0]);
      const job = (res as unknown as { job: JobInfo }).job as JobInfo;
      setRefreshResult(job);
      setSelectedJob(job);
      setTab("jobs");
    } catch (e: unknown) {
      setRefreshError(e instanceof Error ? e.message : String(e));
    } finally {
      setRefreshing(false);
    }
  };

  /* Stats handler */
  const handleFetchStats = async () => {
    setStoreLoading(true);
    try {
      const res = await api.fetchStoreStats();
      setStoreStats(res as unknown as StoreStats);
    } catch {
      /* ignore */
    } finally {
      setStoreLoading(false);
    }
  };

  /* Health handler */
  const handleFetchHealth = async () => {
    setHealthLoading(true);
    try {
      const res = await api.request("/api/v1/data/health");
      setHealth(res as unknown as DataHealthResult);
    } catch {
      /* ignore */
    } finally {
      setHealthLoading(false);
    }
  };

  const tabs = [
    { id: "refresh" as const, label: "数据刷新" },
    { id: "jobs" as const, label: "任务列表" },
    { id: "health" as const, label: "数据源健康" },
    { id: "stats" as const, label: "数据库统计" },
  ];

  return (
    <div className="space-y-5">
      {/* Tab bar */}
      <div className="flex gap-2 border-b border-white/10 pb-3">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`rounded-full px-4 py-1.5 text-sm transition ${
              tab === t.id
                ? "bg-cyan-300 text-slate-950"
                : "border border-white/10 bg-white/5 text-slate-300 hover:border-cyan-200/40 hover:text-white"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Refresh Tab ── */}
      {tab === "refresh" && (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="tv-label">标的 (逗号/空格分隔)</label>
              <input className="tv-input" value={symbols} onChange={e => setSymbols(e.target.value)} placeholder="600519.SH, 000858.SZ" />
            </div>
            <div>
              <label className="tv-label">周期</label>
              <select className="tv-input" value={interval} onChange={e => setIntervalVal(e.target.value)} disabled={!refreshOptions}>
                {!refreshOptions && <option value="">加载服务端选项中...</option>}
                {refreshOptions?.intervals.map(value => <option key={value} value={value}>{value}</option>)}
              </select>
            </div>
            <div>
              <label className="tv-label">模式</label>
              <select className="tv-input" value={mode} onChange={e => setMode(e.target.value as "incremental" | "range")} disabled={!refreshOptions}>
                {refreshOptions?.modes.map(value => <option key={value} value={value}>{value === "incremental" ? "增量更新" : "指定区间"}</option>)}
              </select>
            </div>
            <div>
              <label className="tv-label">包含估值</label>
              <select className="tv-input" value={includeValuation ? "yes" : "no"} onChange={e => setIncludeValuation(e.target.value === "yes")} disabled={!refreshOptions?.include_valuation}>
                <option value="no">否</option>
                <option value="yes">是</option>
              </select>
            </div>
          </div>

          {optionsError && <p className="text-sm text-rose-300">无法获取服务端刷新选项：{optionsError}</p>}

          {mode === "range" && (
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="tv-label">起始日期</label>
                <input className="tv-input" type="date" value={startDate} onChange={e => setStartDate(e.target.value)} />
              </div>
              <div>
                <label className="tv-label">结束日期</label>
                <input className="tv-input" type="date" value={endDate} onChange={e => setEndDate(e.target.value)} />
              </div>
            </div>
          )}

          <button
              className="tv-btn tv-btn-primary"
              disabled={refreshing || !refreshOptions || !interval}
            onClick={handleRefresh}
          >
            {refreshing ? "刷新中..." : "发起刷新"}
          </button>

          {refreshError && <p className="text-sm text-rose-300">{refreshError}</p>}

          {refreshResult && (
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <h3 className="text-sm font-medium text-white">刷新任务已创建</h3>
              <p className="mt-1 text-xs text-slate-400">Job ID: {refreshResult.id}</p>
              <StatusBadge status={refreshResult.status} />
              <p className="mt-2 text-xs text-slate-300">{refreshResult.message}</p>
              <button
                className="mt-2 text-xs text-cyan-300 underline"
                onClick={() => { setTab("jobs"); setSelectedJob(refreshResult); }}
              >
                查看任务详情 →
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Jobs Tab ── */}
      {tab === "jobs" && (
        <div className="space-y-3">
          {!jobsLoading && jobs.length === 0 && (
            <p className="text-sm text-slate-400">暂无任务</p>
          )}
          {jobs.map((j) => (
            <div
              key={j.id}
              className={`rounded-xl border px-4 py-3 transition ${
                selectedJob?.id === j.id
                  ? "border-cyan-300/40 bg-cyan-300/5"
                  : "border-white/5 bg-white/[0.02] hover:border-white/10"
              }`}
              onClick={() => setSelectedJob(j)}
            >
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium text-white capitalize">{j.type}</span>
                  <span className="ml-2 text-xs text-slate-400">{j.id.slice(0, 8)}</span>
                </div>
                <StatusBadge status={j.status} />
              </div>
              <p className="mt-1 text-xs text-slate-400">{j.message}</p>
              {(j.status === "running" || j.completed > 0) && (
                <div className="mt-2">
                  <ProgressBar completed={j.completed} total={j.total} />
                </div>
              )}
              {j.status === "completed" && j.result && (
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-300">
                  {Object.entries(j.result as Record<string, unknown>).slice(0, 4).map(([k, v]) => (
                    <div key={k} className="rounded bg-white/[0.03] px-2 py-1">
                      <span className="text-slate-400">{k}:</span>{" "}
                      {typeof v === "number" ? v : JSON.stringify(v).slice(0, 50)}
                    </div>
                  ))}
                </div>
              )}
              {j.status === "failed" && (
                <p className="mt-1 text-xs text-rose-300">
                  {((j.result as Record<string, unknown>)?.error as string | null) ?? "未知错误"}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── Health Tab ── */}
      {tab === "health" && (
        <div className="space-y-4">
          <button className="tv-btn tv-btn-secondary" onClick={handleFetchHealth} disabled={healthLoading}>
            {healthLoading ? "检测中..." : "检测数据源健康"}
          </button>
          {health && (
            <>
              <div className="flex gap-4 text-sm">
                <span className="text-emerald-300">正常: {health.summary.available}</span>
                <span className="text-rose-300">降级: {health.summary.degraded}</span>
                <span className="text-slate-400">总体质量: {health.quality_overall}</span>
              </div>
              <div className="space-y-2">
                {health.sources.map((s, i) => (
                  <HealthSourceRow key={i} source={s} />
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Stats Tab ── */}
      {tab === "stats" && (
        <div className="space-y-4">
          <button className="tv-btn tv-btn-secondary" onClick={handleFetchStats} disabled={storeLoading}>
            {storeLoading ? "加载中..." : "刷新数据库统计"}
          </button>
          {storeStats && (
            <div className="grid gap-3 md:grid-cols-2">
              {Object.entries(storeStats.stats).map(([table, info]) => {
                const i = info as { rows: number; latest_date: string | null };
                return (
                  <div key={table} className="rounded-xl border border-white/5 bg-white/[0.02] p-3">
                    <p className="text-sm font-medium text-white">{table}</p>
                    <p className="mt-1 text-xs text-slate-400">
                      记录数: {i.rows.toLocaleString()}
                    </p>
                    <p className="text-xs text-slate-400">
                      最新日期: {i.latest_date ?? "—"}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
