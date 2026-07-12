/**
 * Research Page — Stock quote, K-line, F10, news, announcements, AI analysis.
 * Full research/report/watchlist closed loop.
 */

import { useState, useEffect, useCallback } from "react";
import { useApi } from "../hooks/useApi";

/* ── Types ─────────────────────────────────────────────────────── */

interface QuoteData {
  symbol?: string;
  name?: string;
  price?: number;
  change_pct?: number;
  volume?: number;
  turnover?: number;
  source?: string;
  is_mock?: boolean;
  is_stale?: boolean;
  [key: string]: unknown;
}

interface KlineBar {
  bar_time: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
  amount?: number;
  [key: string]: unknown;
}

interface F10Data {
  symbol?: string;
  name?: string;
  industry?: string;
  pe?: number;
  pb?: number;
  market_cap?: number;
  [key: string]: unknown;
}

interface NewsItem {
  title?: string;
  source?: string;
  published_at?: string;
  url?: string;
  [key: string]: unknown;
}

interface Announcement {
  title?: string;
  date?: string;
  url?: string;
  [key: string]: unknown;
}

interface AnalysisResult {
  symbol?: string;
  decisions?: Record<string, unknown>;
  summary?: string;
  scores?: Record<string, unknown>;
  [key: string]: unknown;
}

/* ── Sub-components ────────────────────────────────────────────── */

const QuoteCard: React.FC<{ quote: QuoteData }> = ({ quote }) => {
  const price = quote.price ?? 0;
  const change = quote.change_pct ?? 0;
  const isUp = change >= 0;
  const sourceLabel = quote.source === "live" ? "实时" : quote.source === "cache" ? "缓存" : "模拟";

  return (
    <div className="rounded-lg border border-slate-700/50 bg-slate-800/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-slate-100">
            {quote.symbol} {quote.name ? `(${quote.name})` : ""}
          </h3>
          <span className="text-xs text-slate-500">
            {sourceLabel}
            {quote.is_mock && " · 模拟数据"}
            {quote.is_stale && " · 已过期"}
          </span>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold font-mono text-slate-100">
            {price.toFixed(2)}
          </div>
          <div className={`text-sm font-mono ${isUp ? "text-emerald-400" : "text-rose-400"}`}>
            {isUp ? "+" : ""}{change.toFixed(2)}%
          </div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="rounded bg-slate-900/50 p-2">
          <div className="text-slate-500">成交量</div>
          <div className="font-mono text-slate-200">
            {quote.volume ? `${(quote.volume / 10000).toFixed(0)}万手` : "—"}
          </div>
        </div>
        <div className="rounded bg-slate-900/50 p-2">
          <div className="text-slate-500">成交额</div>
          <div className="font-mono text-slate-200">
            {quote.turnover ? `¥${(quote.turnover / 1e8).toFixed(2)}亿` : "—"}
          </div>
        </div>
        <div className="rounded bg-slate-900/50 p-2">
          <div className="text-slate-500">PE(TTM)</div>
          <div className="font-mono text-slate-200">
            {(quote.pe as number) ? Number(quote.pe).toFixed(2) : "—"}
          </div>
        </div>
      </div>
    </div>
  );
};

const KlineMiniChart: React.FC<{ bars: KlineBar[] }> = ({ bars }) => {
  if (!bars || bars.length < 2) return <p className="text-xs text-slate-500">无K线数据</p>;

  const last100 = bars.slice(-100);
  const closes = last100.map((b) => b.close as number).filter((v) => v > 0);
  if (closes.length < 2) return <p className="text-xs text-slate-500">数据不足</p>;

  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const w = 600;
  const h = 200;
  const pad = 10;
  const points = closes
    .map((v, i) => {
      const x = pad + (i / (closes.length - 1)) * (w - 2 * pad);
      const y = h - pad - ((v - min) / range) * (h - 2 * pad);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
      <defs>
        <linearGradient id="klineGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`${pad},${h} ${points} ${w - pad},${h}`} fill="url(#klineGrad)" />
      <polyline points={points} fill="none" stroke="#3b82f6" strokeWidth="2" />
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
        const y = h - pad - ratio * (h - 2 * pad);
        const val = (min + ratio * range).toFixed(2);
        return (
          <g key={ratio}>
            <line x1={pad} y1={y} x2={w - pad} y2={y} stroke="#1e293b" strokeWidth="1" />
            <text x={w - pad + 2} y={y + 4} fill="#64748b" fontSize="10">{val}</text>
          </g>
        );
      })}
    </svg>
  );
};

const SectionTabs: React.FC<{
  tabs: string[];
  active: string;
  onChange: (tab: string) => void;
}> = ({ tabs, active, onChange }) => (
  <div className="flex gap-1 border-b border-slate-700/50">
    {tabs.map((tab) => (
      <button
        key={tab}
        onClick={() => onChange(tab)}
        className={`px-4 py-2 text-sm font-medium transition-colors ${
          active === tab
            ? "border-b-2 border-blue-500 text-blue-400"
            : "text-slate-400 hover:text-slate-200"
        }`}
      >
        {tab}
      </button>
    ))}
  </div>
);

/* ── Main Component ────────────────────────────────────────────── */

export default function ResearchPage() {
  const api = useApi();
  const [symbol, setSymbol] = useState("600519.SH");
  const [activeTab, setActiveTab] = useState("quote");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* Data state */
  const [quote, setQuote] = useState<QuoteData | null>(null);
  const [klineBars, setKlineBars] = useState<KlineBar[]>([]);
  const [f10, setF10] = useState<F10Data | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);

  const loadQuote = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const q = await api.getMarketQuote(symbol);
      setQuote(q as QuoteData);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [api, symbol]);

  const loadKline = useCallback(async () => {
    try {
      setLoading(true);
      const bars = await api.getKline(symbol, undefined, undefined, "1d", 200);
      setKlineBars((bars as unknown as KlineBar[]) ?? []);
    } catch (e) {
      console.warn("Kline load failed:", e);
    }
  }, [api, symbol]);

  const loadF10 = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getF10(symbol);
      setF10(data as F10Data);
    } catch (e) {
      console.warn("F10 load failed:", e);
    }
  }, [api, symbol]);

  const loadNews = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getNews(symbol);
      setNews((data as { news?: NewsItem[] })?.news ?? []);
    } catch (e) {
      console.warn("News load failed:", e);
    }
  }, [api, symbol]);

  const loadAnnouncements = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getAnnouncements(symbol);
      setAnnouncements((data as { announcements?: Announcement[] })?.announcements ?? []);
    } catch (e) {
      console.warn("Announcements load failed:", e);
    }
  }, [api, symbol]);

  const runAnalysis = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.batchAnalyzeWatchlist([symbol]);
      setAnalysis(data as AnalysisResult);
    } catch (e) {
      console.warn("Analysis failed:", e);
    }
  }, [api, symbol]);

  /* Load all on mount */
  useEffect(() => {
    loadQuote();
    loadKline();
    loadF10();
    loadNews();
    loadAnnouncements();
  }, [loadQuote, loadKline, loadF10, loadNews, loadAnnouncements]);

  const tabs = ["报价", "K线", "F10", "新闻", "公告", "AI分析"];

  return (
    <div className="space-y-4">
      {/* Symbol selector */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          className="w-32 rounded border border-slate-700 bg-slate-800 px-3 py-2 font-mono text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
          placeholder="股票代码"
        />
        <button
          onClick={() => {
            loadQuote();
            loadKline();
            loadF10();
            loadNews();
            loadAnnouncements();
          }}
          className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500"
        >
          刷新
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/[0.05] p-3 text-sm text-rose-300">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          加载中...
        </div>
      )}

      {/* Tabs */}
      <SectionTabs tabs={tabs} active={activeTab} onChange={setActiveTab} />

      {/* Tab content */}
      <div className="min-h-[300px]">
        {activeTab === "quote" && quote && <QuoteCard quote={quote} />}

        {activeTab === "K线" && (
          <div className="rounded-lg border border-slate-700/50 bg-slate-800/50 p-4">
            <KlineMiniChart bars={klineBars} />
            <div className="mt-2 text-xs text-slate-500">
              最近 {klineBars.length} 根日线
            </div>
          </div>
        )}

        {activeTab === "F10" && f10 && (
          <div className="rounded-lg border border-slate-700/50 bg-slate-800/50 p-4">
            <h4 className="mb-3 text-base font-semibold text-slate-200">
              {f10.name} ({f10.symbol})
            </h4>
            <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
              <div className="rounded bg-slate-900/50 p-3">
                <div className="text-slate-500">行业</div>
                <div className="font-medium text-slate-200">{f10.industry ?? "—"}</div>
              </div>
              <div className="rounded bg-slate-900/50 p-3">
                <div className="text-slate-500">PE(TTM)</div>
                <div className="font-mono font-medium text-slate-200">
                  {f10.pe ? f10.pe.toFixed(2) : "—"}
                </div>
              </div>
              <div className="rounded bg-slate-900/50 p-3">
                <div className="text-slate-500">PB</div>
                <div className="font-mono font-medium text-slate-200">
                  {f10.pb ? f10.pb.toFixed(2) : "—"}
                </div>
              </div>
              <div className="rounded bg-slate-900/50 p-3">
                <div className="text-slate-500">总市值</div>
                <div className="font-mono font-medium text-slate-200">
                  {f10.market_cap ? `${(f10.market_cap / 1e8).toFixed(2)}亿` : "—"}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "新闻" && (
          <div className="rounded-lg border border-slate-700/50 bg-slate-800/50 p-4">
            {news.length > 0 ? (
              <div className="space-y-2">
                {news.slice(0, 10).map((n, i) => (
                  <div key={i} className="flex items-start justify-between border-b border-slate-800/50 pb-2">
                    <div className="flex-1">
                      <div className="text-sm text-slate-200">{n.title ?? "—"}</div>
                      <div className="mt-1 flex gap-3 text-xs text-slate-500">
                        <span>{n.source ?? "—"}</span>
                        <span>{n.published_at ? new Date(String(n.published_at)).toLocaleDateString("zh-CN") : "—"}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">暂无新闻</p>
            )}
          </div>
        )}

        {activeTab === "公告" && (
          <div className="rounded-lg border border-slate-700/50 bg-slate-800/50 p-4">
            {announcements.length > 0 ? (
              <div className="space-y-2">
                {announcements.slice(0, 10).map((a, i) => (
                  <div key={i} className="flex items-start justify-between border-b border-slate-800/50 pb-2">
                    <div className="flex-1">
                      <div className="text-sm text-slate-200">{a.title ?? "—"}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        {a.date ? new Date(String(a.date)).toLocaleDateString("zh-CN") : "—"}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">暂无公告</p>
            )}
          </div>
        )}

        {activeTab === "AI分析" && (
          <div className="rounded-lg border border-slate-700/50 bg-slate-800/50 p-4">
            {analysis ? (
              <div>
                <h4 className="mb-3 text-base font-semibold text-slate-200">
                  AI 分析报告 — {analysis.symbol}
                </h4>
                <div className="grid grid-cols-2 gap-3 mb-4">
                  {Object.entries(analysis.decisions ?? {}).map(([key, val]) => (
                    <div key={key} className="rounded bg-slate-900/50 p-3 text-center">
                      <div className="text-xl font-bold text-blue-400">{String(val)}</div>
                      <div className="text-xs text-slate-400">
                        {key === "buy" ? "买入" : key === "hold" ? "持有" : key === "sell" ? "卖出" : key}
                      </div>
                    </div>
                  ))}
                </div>
                {analysis.summary && (
                  <div className="rounded bg-slate-900/50 p-3 text-sm text-slate-300">
                    {analysis.summary}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center">
                <button
                  onClick={runAnalysis}
                  className="rounded bg-blue-600 px-6 py-2 text-sm text-white hover:bg-blue-500"
                >
                  触发AI分析
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
