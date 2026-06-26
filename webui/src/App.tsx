import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import AgentFlow from "./components/AgentFlow";
import BacktestChart from "./components/BacktestChart";
import KlineChart from "./components/KlineChart";
import type { EquityCurve } from "./components/BacktestChart";
import type { OHLCV } from "./components/KlineChart";
import LangSwitch from "./components/LangSwitch";
import MarkdownReport from "./components/MarkdownReport";
import MarketSwitch from "./components/MarketSwitch";
import ModuleDetail from "./components/ModuleDetail";
import ModuleTree from "./components/ModuleTree";
import ReportViewerWrapper from "./components/ReportViewer";
import RiskPanel from "./components/RiskPanel";
import { LocaleProvider, useTranslation } from "./hooks/useTranslation";
import { useApi } from "./hooks/useApi";
import { MarketProvider } from "./components/MarketSwitch";
import rawModules from "./data/modules.json";
import type { ModuleRecord, ModuleType } from "./types";

const modules = rawModules as ModuleRecord[];

function AppContent() {
  const { t } = useTranslation();
  const staticSourceLabel = t("staticSource");

  const filterOptions: Array<{ label: string; value: ModuleType | "all" }> = [
    { label: t("filter.all"), value: "all" },
    { label: t("filter.analyst"), value: "analyst" },
    { label: t("filter.researcher"), value: "researcher" },
    { label: t("filter.trader"), value: "trader" },
    { label: t("filter.risk"), value: "risk" },
    { label: t("filter.dataflow"), value: "dataflow" },
    { label: t("filter.config"), value: "config" },
    { label: t("filter.cli"), value: "cli" },
  ];

  const sections = [
    { id: "dashboard", label: t("nav.dashboard") },
    { id: "module-map", label: t("nav.moduleMap") },
    { id: "agent-flow", label: t("nav.agentFlow") },
    { id: "task-center", label: t("nav.taskCenter") },
    { id: "reports", label: t("nav.reports") },
    { id: "backtest", label: t("nav.backtest") },
    { id: "market-data", label: t("nav.marketData") },
    { id: "settings", label: t("nav.settings") },
  ] as const;

  type SectionId = (typeof sections)[number]["id"];

  const [hydrated, setHydrated] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<ModuleType | "all">("all");
  const [selectedPath, setSelectedPath] = useState<string>(modules[0]?.path ?? "");
  const [activeSection, setActiveSection] = useState<SectionId>("dashboard");

  // ── Backtest state ──
  const api = useApi();
  const [btSymbol, setBtSymbol] = useState("600519.SH");
  const [btStrategy, setBtStrategy] = useState("macd_trend");
  const [btStart, setBtStart] = useState("2024-01-01");
  const [btEnd, setBtEnd] = useState("2024-06-30");
  const [btCurves, setBtCurves] = useState<EquityCurve[]>([]);
  const [btLoading, setBtLoading] = useState(false);
  const [btError, setBtError] = useState("");

  // ── Kline state ──
  const [klSymbol, setKlSymbol] = useState("600519.SH");
  const [klInterval, setKlInterval] = useState("1d");
  const [klData, setKlData] = useState<OHLCV[]>([]);
  const [klLoading, setKlLoading] = useState(false);
  const [klError, setKlError] = useState("");

  useEffect(() => {
    setHydrated(true);
  }, []);

  const filteredModules = useMemo(() => {
    const query = search.trim().toLowerCase();

    return modules.filter((module) => {
      const typeMatch = filter === "all" || module.type === filter;
      const haystack = [
        module.name,
        module.path,
        module.type,
        module.description,
        ...module.inputs,
        ...module.outputs,
        ...module.dependencies,
        ...module.risks,
        ...module.related_files,
      ]
        .join(" ")
        .toLowerCase();

      return typeMatch && (!query || haystack.includes(query));
    });
  }, [filter, search]);

  const selectedModule = useMemo(() => {
    if (!filteredModules.length) return undefined;
    return filteredModules.find((module) => module.path === selectedPath) ?? filteredModules[0];
  }, [filteredModules, selectedPath]);

  useEffect(() => {
    if (!filteredModules.length) return;
    if (!filteredModules.some((module) => module.path === selectedPath)) {
      setSelectedPath(filteredModules[0].path);
    }
  }, [filteredModules, selectedPath]);

  const reportMarkdown = useMemo(
    () => buildReportMarkdown({ modules, filteredModules, selectedModule, t }),
    [filteredModules, selectedModule, t],
  );

  if (!hydrated) {
    return <AppLoading />;
  }

  if (!modules.length) {
    return <AppError message={t("app.error.message")} />;
  }

  return (
    <div className="min-h-screen bg-app text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-[1800px] flex-col px-4 py-5 lg:px-6">
        <header className="mb-5 rounded-3xl border border-white/10 bg-white/5 p-5 shadow-2xl shadow-slate-950/30 backdrop-blur">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
            <div className="space-y-3">
              <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/80">{t("app.title")}</p>
              <div className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-tight text-white">{t("app.subtitle")}</h1>
                <p className="max-w-4xl text-sm leading-6 text-slate-300">
                  {t("app.disclaimer")}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label={t("stat.modules")} value={String(modules.length)} />
              <StatCard label={t("stat.visible")} value={String(filteredModules.length)} />
              <StatCard label={t("stat.types")} value={String(new Set(modules.map((module) => module.type)).size)} />
              <StatCard label={t("stat.staticSource")} value="1 JSON" />
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4">
            <nav className="flex flex-wrap gap-2">
              {sections.map((section) => (
                <a
                  key={section.id}
                  href={`#${section.id}`}
                  className={`rounded-full px-4 py-2 text-sm transition ${
                    activeSection === section.id
                      ? "bg-cyan-300 text-slate-950"
                      : "border border-white/10 bg-white/5 text-slate-300 hover:border-cyan-200/40 hover:text-white"
                  }`}
                  onClick={() => setActiveSection(section.id)}
                >
                  {section.label}
                </a>
              ))}
            </nav>
            <div className="flex items-center gap-2">
              <MarketSwitch />
              <LangSwitch />
            </div>
          </div>
        </header>

        <section id="dashboard" className="panel p-5">
          <SectionHeader
            kicker={t("section.dashboard.kicker")}
            title={t("section.dashboard.title")}
            description={t("section.dashboard.desc")}
          />
          <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(280px,0.7fr)]">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <SummaryCard title={t("dashboard.analysts")} value={String(modules.filter((m) => m.type === "analyst").length)} />
              <SummaryCard title={t("dashboard.researchers")} value={String(modules.filter((m) => m.type === "researcher").length)} />
              <SummaryCard title={t("dashboard.dataflows")} value={String(modules.filter((m) => m.type === "dataflow").length)} />
              <SummaryCard title={t("dashboard.configCli")} value={String(modules.filter((m) => m.type === "config" || m.type === "cli").length)} />
            </div>
            <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
              <h3 className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">{t("dashboard.checklist")}</h3>
              <div className="mt-4 space-y-2 text-sm text-slate-300">
                <CheckItem ok label={t("dashboard.check.dashboard")} />
                <CheckItem ok label={t("dashboard.check.moduleMap")} />
                <CheckItem ok label={t("dashboard.check.agentFlow")} />
                <CheckItem ok label={t("dashboard.check.taskCenter")} />
                <CheckItem ok label={t("dashboard.check.reports")} />
                <CheckItem ok label={t("dashboard.check.settings")} />
              </div>
            </div>
          </div>
        </section>

        <section id="module-map" className="mt-5 grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
          <ModuleTree
            filter={filter}
            filterOptions={filterOptions}
            modules={filteredModules}
            search={search}
            selectedPath={selectedModule?.path ?? ""}
            onFilterChange={setFilter}
            onSearchChange={setSearch}
            onSelect={setSelectedPath}
          />
          <ModuleDetail module={selectedModule} />
          <RiskPanel module={selectedModule} />
        </section>

        <section id="agent-flow" className="mt-5 panel p-5">
          <SectionHeader
            kicker={t("section.agentFlow.kicker")}
            title={t("section.agentFlow.title")}
            description={t("section.agentFlow.desc")}
          />
          <div className="mt-5">
            <AgentFlow modules={modules} selectedModule={selectedModule} />
          </div>
        </section>

        <section id="task-center" className="mt-5 panel p-5">
          <SectionHeader
            kicker={t("section.taskCenter.kicker")}
            title={t("section.taskCenter.title")}
            description={t("section.taskCenter.desc")}
          />
          <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
            <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
              <div className="flex flex-wrap gap-2">
                <QuickActionButton onClick={() => jumpTo("module-map")}>{t("taskCenter.openModuleMap")}</QuickActionButton>
                <QuickActionButton onClick={() => jumpTo("reports")}>{t("taskCenter.openReports")}</QuickActionButton>
                <QuickActionButton onClick={() => jumpTo("settings")}>{t("taskCenter.openSettings")}</QuickActionButton>
                <QuickActionButton onClick={() => {
                  setSearch("");
                  setFilter("all");
                }}>{t("taskCenter.resetFilters")}</QuickActionButton>
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-3">
                <SummaryCard title={t("taskCenter.search")} value={search.trim() || "—"} />
                <SummaryCard title={t("taskCenter.filter")} value={filter} />
                <SummaryCard title={t("taskCenter.selected")} value={selectedModule?.name ?? t("taskCenter.none")} />
              </div>
            </div>
            <div className="rounded-3xl border border-dashed border-white/10 bg-slate-950/30 p-4 text-sm leading-6 text-slate-300">
              <p className="font-medium text-white">{t("taskCenter.whatToDo")}</p>
              <ul className="mt-3 space-y-2 text-slate-400">
                <li>{t("taskCenter.hint1")}</li>
                <li>{t("taskCenter.hint2")}</li>
                <li>{t("taskCenter.hint3")}</li>
              </ul>
            </div>
          </div>
        </section>

        <section id="reports" className="mt-5 panel p-5">
          <SectionHeader
            kicker={t("section.reports.kicker")}
            title={t("section.reports.title")}
            description={t("section.reports.desc")}
          />
          <div className="mt-5">
            <ReportViewerWrapper />
          </div>
        </section>

        {/* ── Backtest section ── */}
        <section id="backtest" className="mt-5 panel p-5">
          <SectionHeader
            kicker={t("section.backtest.kicker")}
            title={t("section.backtest.title")}
            description={t("section.backtest.desc")}
          />
          <div className="mt-5 flex flex-wrap items-end gap-3">
            <div>
              <label className="tv-label">{t("backtest.symbol")}</label>
              <input className="tv-input" value={btSymbol} onChange={e => setBtSymbol(e.target.value)} placeholder="600519.SH" />
            </div>
            <div>
              <label className="tv-label">{t("backtest.strategy")}</label>
              <select className="tv-input" value={btStrategy} onChange={e => setBtStrategy(e.target.value)}>
                <option value="macd_trend">MACD Trend</option>
                <option value="bollinger_mean_reversion">Bollinger Mean Reversion</option>
                <option value="grid_trading">Grid Trading</option>
                <option value="sma_cross">SMA Cross</option>
              </select>
            </div>
            <div>
              <label className="tv-label">{t("backtest.startDate")}</label>
              <input className="tv-input" type="date" value={btStart} onChange={e => setBtStart(e.target.value)} />
            </div>
            <div>
              <label className="tv-label">{t("backtest.endDate")}</label>
              <input className="tv-input" type="date" value={btEnd} onChange={e => setBtEnd(e.target.value)} />
            </div>
            <button
              className="tv-btn tv-btn-primary"
              disabled={btLoading}
              onClick={async () => {
                setBtLoading(true);
                setBtError("");
                try {
                  await api.runBacktest({ symbol: btSymbol, strategy: btStrategy, start: btStart, end: btEnd });
                  const res = await api.fetchBacktestResults(btStrategy);
                  const results = res.results ?? [];
                  const curves: EquityCurve[] = results.map((r: Record<string, unknown>) => ({
                    strategy_name: (r.strategy_name as string) ?? btStrategy,
                    dates: (r.equity_curve_dates as string[]) ?? [],
                    values: (r.equity_curve_values as number[]) ?? [],
                  }));
                  setBtCurves(curves.length ? curves : []);
                } catch (e: unknown) {
                  setBtError(t("backtest.error", { msg: e instanceof Error ? e.message : String(e) }));
                } finally {
                  setBtLoading(false);
                }
              }}
            >
              {btLoading ? t("backtest.running") : t("backtest.run")}
            </button>
          </div>
          {btError && <p className="mt-3 text-sm text-rose-300">{btError}</p>}
          <div className="mt-4">
            {btCurves.length > 0 ? (
              <BacktestChart curves={btCurves} />
            ) : (
              !btLoading && <p className="text-sm text-slate-400">{t("backtest.noData")}</p>
            )}
          </div>
        </section>

        {/* ── Market Data section ── */}
        <section id="market-data" className="mt-5 panel p-5">
          <SectionHeader
            kicker={t("section.marketData.kicker")}
            title={t("section.marketData.title")}
            description={t("section.marketData.desc")}
          />
          <div className="mt-5 flex flex-wrap items-end gap-3">
            <div>
              <label className="tv-label">{t("marketData.symbol")}</label>
              <input className="tv-input" value={klSymbol} onChange={e => setKlSymbol(e.target.value)} placeholder="600519.SH" />
            </div>
            <div>
              <label className="tv-label">{t("marketData.interval")}</label>
              <select className="tv-input" value={klInterval} onChange={e => setKlInterval(e.target.value)}>
                <option value="1d">Daily</option>
                <option value="1w">Weekly</option>
                <option value="1m">Monthly</option>
                <option value="60m">60 min</option>
                <option value="30m">30 min</option>
              </select>
            </div>
            <button
              className="tv-btn tv-btn-primary"
              disabled={klLoading}
              onClick={async () => {
                setKlLoading(true);
                setKlError("");
                try {
                  const res = await api.fetchKline(klSymbol, undefined, undefined, klInterval);
                  const bars = (res.bars ?? []) as Record<string, unknown>[];
                  const ohlcv: OHLCV[] = bars.map(b => ({
                    trade_date: (b.trade_date ?? b.date ?? "") as string,
                    open: Number(b.open ?? 0),
                    high: Number(b.high ?? 0),
                    low: Number(b.low ?? 0),
                    close: Number(b.close ?? 0),
                    volume: Number(b.volume ?? 0),
                  }));
                  setKlData(ohlcv);
                } catch (e: unknown) {
                  setKlError(t("marketData.error", { msg: e instanceof Error ? e.message : String(e) }));
                } finally {
                  setKlLoading(false);
                }
              }}
            >
              {klLoading ? t("marketData.fetching") : t("marketData.fetch")}
            </button>
          </div>
          {klError && <p className="mt-3 text-sm text-rose-300">{klError}</p>}
          <div className="mt-4">
            {klData.length > 0 ? (
              <KlineChart data={klData} symbol={klSymbol} />
            ) : (
              !klLoading && <p className="text-sm text-slate-400">{t("marketData.noData")}</p>
            )}
          </div>
        </section>

        <section id="settings" className="mt-5 panel p-5">
          <SectionHeader
            kicker={t("section.settings.kicker")}
            title={t("section.settings.title")}
            description={t("section.settings.desc")}
          />
          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <ToggleCard title={t("settings.externalApis")} enabled={false} detail={t("settings.externalApis.detail")} />
            <ToggleCard title={t("settings.tradingExecution")} enabled={false} detail={t("settings.tradingExecution.detail")} />
            <ToggleCard title={t("settings.dataSource")} enabled detail={staticSourceLabel} />
            <ToggleCard title={t("settings.editMode")} enabled={false} detail={t("settings.editMode.detail")} />
          </div>
        </section>
      </div>
    </div>
  );
}

function jumpTo(sectionId: string) {
  document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function buildReportMarkdown({
  modules,
  filteredModules,
  selectedModule,
  t,
}: {
  modules: ModuleRecord[];
  filteredModules: ModuleRecord[];
  selectedModule?: ModuleRecord;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const typeCounts = Object.fromEntries(
    ["analyst", "researcher", "trader", "risk", "dataflow", "config", "cli"].map((type) => [
      type,
      modules.filter((module) => module.type === type).length,
    ]),
  ) as Record<ModuleType, number>;

  const noneLabel = t("report.md.none");
  const selectedName = selectedModule?.name ?? noneLabel;

  return (
    `# ${t("app.title")}` +
    "\n\n> " + t("staticSource") +
    "\n\n" + t("report.md.summary") +
    "\n\n" + t("report.md.totalModules", { count: String(modules.length) }) +
    "\n" + t("report.md.visibleModules", { count: String(filteredModules.length) }) +
    "\n" + t("report.md.selectedModule", { name: selectedName }) +
    "\n\n" + t("report.md.typeCoverage") +
    "\n\n" + t("report.md.analysts", { count: String(typeCounts.analyst) }) +
    "\n" + t("report.md.researchers", { count: String(typeCounts.researcher) }) +
    "\n" + t("report.md.trader", { count: String(typeCounts.trader) }) +
    "\n" + t("report.md.risk", { count: String(typeCounts.risk) }) +
    "\n" + t("report.md.dataflows", { count: String(typeCounts.dataflow) }) +
    "\n" + t("report.md.config", { count: String(typeCounts.config) }) +
    "\n" + t("report.md.cli", { count: String(typeCounts.cli) }) +
    "\n\n" + t("report.md.currentSelection") +
    "\n\n" + (selectedModule
      ? "### " + selectedModule.name +
        "\n\n" + t("report.md.path", { path: selectedModule.path }) +
        "\n" + t("report.md.type", { type: selectedModule.type }) +
        "\n" + t("report.md.description", { desc: selectedModule.description })
      : t("report.md.noSelection")) +
    "\n\n" + t("report.md.notes") +
    "\n\n" + t("report.md.note1") +
    "\n" + t("report.md.note2") +
    "\n" + t("report.md.note3") + "\n"
  );
}

function App() {
  return (
    <LocaleProvider>
      <MarketProvider>
        <AppContent />
      </MarketProvider>
    </LocaleProvider>
  );
}

function AppLoading() {
  return (
    <div className="min-h-screen bg-app px-4 py-8 text-slate-100">
      <div className="mx-auto max-w-4xl rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl shadow-slate-950/30">
        <div className="animate-pulse space-y-4">
          <div className="h-4 w-44 rounded bg-white/10" />
          <div className="h-10 w-3/4 rounded bg-white/10" />
          <div className="h-4 w-full rounded bg-white/10" />
          <div className="h-4 w-5/6 rounded bg-white/10" />
        </div>
      </div>
    </div>
  );
}

function AppError({ message }: { message: string }) {
  const { t } = useTranslation();
  return (
    <div className="min-h-screen bg-app px-4 py-8 text-slate-100">
      <div className="mx-auto max-w-4xl rounded-3xl border border-rose-400/30 bg-rose-500/10 p-8 shadow-2xl shadow-slate-950/30">
        <p className="text-xs uppercase tracking-[0.35em] text-rose-200/80">{t("app.error.label")}</p>
        <h1 className="mt-3 text-3xl font-semibold text-white">{t("app.error.title")}</h1>
        <p className="mt-3 text-sm leading-6 text-rose-100/90">{message}</p>
      </div>
    </div>
  );
}

function SectionHeader({
  kicker,
  title,
  description,
}: {
  kicker: string;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/80">{kicker}</p>
      <h2 className="text-2xl font-semibold tracking-tight text-white">{title}</h2>
      <p className="max-w-4xl text-sm leading-6 text-slate-400">{description}</p>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.25em] text-slate-400">{label}</p>
      <p className="mt-2 text-lg font-semibold text-white">{value}</p>
    </div>
  );
}

function SummaryCard({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.03] px-4 py-3">
      <p className="text-xs uppercase tracking-[0.24em] text-slate-400">{title}</p>
      <p className="mt-2 text-lg font-semibold text-white break-words">{value}</p>
    </div>
  );
}

function CheckItem({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-950/30 px-3 py-2">
      <span className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-xs ${ok ? "bg-emerald-400/20 text-emerald-200" : "bg-rose-400/20 text-rose-200"}`}>
        {ok ? "✓" : "!"}
      </span>
      <span>{label}</span>
    </div>
  );
}

function QuickActionButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 transition hover:border-cyan-200/40 hover:bg-cyan-300/10 hover:text-white"
    >
      {children}
    </button>
  );
}

function ToggleCard({ title, enabled, detail }: { title: string; enabled: boolean; detail: string }) {
  const { t } = useTranslation();
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-medium text-white">{title}</h3>
        <span className={`rounded-full px-2 py-1 text-[11px] uppercase tracking-[0.2em] ${enabled ? "bg-emerald-400/20 text-emerald-100" : "bg-slate-700/60 text-slate-200"}`}>
          {enabled ? t("settings.on") : t("settings.off")}
        </span>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-400">{detail}</p>
    </div>
  );
}

export default App;
