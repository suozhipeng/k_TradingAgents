import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import AgentFlow from "./components/AgentFlow";
import MarkdownReport from "./components/MarkdownReport";
import ModuleDetail from "./components/ModuleDetail";
import ModuleTree from "./components/ModuleTree";
import ReportViewerWrapper from "./components/ReportViewer";
import RiskPanel from "./components/RiskPanel";
import rawModules from "./data/modules.json";
import type { ModuleRecord, ModuleType } from "./types";

const modules = rawModules as ModuleRecord[];
const staticSourceLabel = "Static snapshot: webui/src/data/modules.json";

const filterOptions: Array<{ label: string; value: ModuleType | "all" }> = [
  { label: "All", value: "all" },
  { label: "Analyst", value: "analyst" },
  { label: "Researcher", value: "researcher" },
  { label: "Trader", value: "trader" },
  { label: "Risk", value: "risk" },
  { label: "Dataflow", value: "dataflow" },
  { label: "Config", value: "config" },
  { label: "CLI", value: "cli" },
];

const sections = [
  { id: "dashboard", label: "Dashboard" },
  { id: "module-map", label: "Module Map" },
  { id: "agent-flow", label: "Agent Flow" },
  { id: "task-center", label: "Task Center" },
  { id: "reports", label: "Reports" },
  { id: "settings", label: "Settings" },
] as const;

type SectionId = (typeof sections)[number]["id"];

function App() {
  const [hydrated, setHydrated] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<ModuleType | "all">("all");
  const [selectedPath, setSelectedPath] = useState<string>(modules[0]?.path ?? "");
  const [activeSection, setActiveSection] = useState<SectionId>("dashboard");

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
    () => buildReportMarkdown({ modules, filteredModules, selectedModule }),
    [filteredModules, selectedModule],
  );

  if (!hydrated) {
    return <AppLoading />;
  }

  if (!modules.length) {
    return <AppError message="modules.json is empty. The WebUI needs a static snapshot to render." />;
  }

  return (
    <div className="min-h-screen bg-app text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-[1800px] flex-col px-4 py-5 lg:px-6">
        <header className="mb-5 rounded-3xl border border-white/10 bg-white/5 p-5 shadow-2xl shadow-slate-950/30 backdrop-blur">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
            <div className="space-y-3">
              <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/80">TradingAgents Static WebUI</p>
              <div className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-tight text-white">Module map, flows, reports, and settings</h1>
                <p className="max-w-4xl text-sm leading-6 text-slate-300">
                  This dashboard reads only a static modules snapshot. It does not run trading, call external APIs,
                  or execute TradingAgents business code.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="Modules" value={String(modules.length)} />
              <StatCard label="Visible" value={String(filteredModules.length)} />
              <StatCard label="Types" value={String(new Set(modules.map((module) => module.type)).size)} />
              <StatCard label="Static Source" value="1 JSON" />
            </div>
          </div>

          <nav className="mt-5 flex flex-wrap gap-2 border-t border-white/10 pt-4">
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
        </header>

        <section id="dashboard" className="panel p-5">
          <SectionHeader
            kicker="Dashboard"
            title="Static snapshot at a glance"
            description="Quick health overview for the WebUI dataset, module types, and flow coverage."
          />
          <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(280px,0.7fr)]">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <SummaryCard title="Analysts" value={String(modules.filter((m) => m.type === "analyst").length)} />
              <SummaryCard title="Researchers" value={String(modules.filter((m) => m.type === "researcher").length)} />
              <SummaryCard title="Dataflows" value={String(modules.filter((m) => m.type === "dataflow").length)} />
              <SummaryCard title="Config / CLI" value={String(modules.filter((m) => m.type === "config" || m.type === "cli").length)} />
            </div>
            <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
              <h3 className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Checklist status</h3>
              <div className="mt-4 space-y-2 text-sm text-slate-300">
                <CheckItem ok label="Dashboard section present" />
                <CheckItem ok label="Module Map section present" />
                <CheckItem ok label="Agent Flow section present" />
                <CheckItem ok label="Task Center section present" />
                <CheckItem ok label="Reports section present" />
                <CheckItem ok label="Settings section present" />
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
            kicker="Agent Flow"
            title="Data Source → Analysts → Researchers → Trader → Risk Managers → Portfolio Manager"
            description="A static overview of the repository flow, with counts derived from modules.json only."
          />
          <div className="mt-5">
            <AgentFlow modules={modules} selectedModule={selectedModule} />
          </div>
        </section>

        <section id="task-center" className="mt-5 panel p-5">
          <SectionHeader
            kicker="Task Center"
            title="Search, filter, and inspect a module"
            description="This section acts as the control surface for locating and reviewing static modules."
          />
          <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
            <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
              <div className="flex flex-wrap gap-2">
                <QuickActionButton onClick={() => jumpTo("module-map")}>Open Module Map</QuickActionButton>
                <QuickActionButton onClick={() => jumpTo("reports")}>Open Reports</QuickActionButton>
                <QuickActionButton onClick={() => jumpTo("settings")}>Open Settings</QuickActionButton>
                <QuickActionButton onClick={() => {
                  setSearch("");
                  setFilter("all");
                }}>Reset Filters</QuickActionButton>
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-3">
                <SummaryCard title="Search" value={search.trim() || "—"} />
                <SummaryCard title="Filter" value={filter} />
                <SummaryCard title="Selected" value={selectedModule?.name ?? "None"} />
              </div>
            </div>
            <div className="rounded-3xl border border-dashed border-white/10 bg-slate-950/30 p-4 text-sm leading-6 text-slate-300">
              <p className="font-medium text-white">What to do here</p>
              <ul className="mt-3 space-y-2 text-slate-400">
                <li>• Search by module name, path, dependency, input, output, or risk.</li>
                <li>• Filter to isolate analysts, researchers, risk teams, dataflows, config, or CLI.</li>
                <li>• Select a module to view its IO, dependency surface, and risk notes.</li>
              </ul>
            </div>
          </div>
        </section>

        <section id="reports" className="mt-5 panel p-5">
          <SectionHeader
            kicker="Reports"
            title="A-stock report viewer"
            description="Paste or upload an AStockGraphReport JSON payload to view a structured report with advisory chain, research sections, provider coverage, and runtime trace."
          />
          <div className="mt-5">
            <ReportViewerWrapper />
          </div>
        </section>

        <section id="settings" className="mt-5 panel p-5">
          <SectionHeader
            kicker="Settings"
            title="Static-only configuration"
            description="These settings are informational and remind users that the WebUI is read-only."
          />
          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <ToggleCard title="External APIs" enabled={false} detail="Disabled in WebUI" />
            <ToggleCard title="Trading Execution" enabled={false} detail="Not available" />
            <ToggleCard title="Data Source" enabled detail={staticSourceLabel} />
            <ToggleCard title="Edit Mode" enabled={false} detail="Read-only snapshot" />
          </div>
        </section>
      </div>
    </div>
  );
}

function jumpTo(sectionId: SectionId) {
  document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function buildReportMarkdown({
  modules,
  filteredModules,
  selectedModule,
}: {
  modules: ModuleRecord[];
  filteredModules: ModuleRecord[];
  selectedModule?: ModuleRecord;
}) {
  const typeCounts = Object.fromEntries(
    ["analyst", "researcher", "trader", "risk", "dataflow", "config", "cli"].map((type) => [
      type,
      modules.filter((module) => module.type === type).length,
    ]),
  ) as Record<ModuleType, number>;

  return `# TradingAgents WebUI Static Report

> ${staticSourceLabel}

## Snapshot Summary

- Total modules: **${modules.length}**
- Visible after current filters: **${filteredModules.length}**
- Selected module: **${selectedModule?.name ?? "None"}**

## Type Coverage

- Analysts: ${typeCounts.analyst}
- Researchers: ${typeCounts.researcher}
- Trader: ${typeCounts.trader}
- Risk: ${typeCounts.risk}
- Dataflows: ${typeCounts.dataflow}
- Config: ${typeCounts.config}
- CLI: ${typeCounts.cli}

## Current Selection

${selectedModule ? `### ${selectedModule.name}\n\n- Path: \`${selectedModule.path}\`\n- Type: **${selectedModule.type}**\n- Description: ${selectedModule.description}` : "No module selected."}

## Notes

- This report is rendered from static WebUI data only.
- It is safe to view without running any trading logic.
- Search indexing includes names, paths, descriptions, inputs, outputs, dependencies, and risks.
`;
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
  return (
    <div className="min-h-screen bg-app px-4 py-8 text-slate-100">
      <div className="mx-auto max-w-4xl rounded-3xl border border-rose-400/30 bg-rose-500/10 p-8 shadow-2xl shadow-slate-950/30">
        <p className="text-xs uppercase tracking-[0.35em] text-rose-200/80">WebUI error</p>
        <h1 className="mt-3 text-3xl font-semibold text-white">Unable to render static modules</h1>
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
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-medium text-white">{title}</h3>
        <span className={`rounded-full px-2 py-1 text-[11px] uppercase tracking-[0.2em] ${enabled ? "bg-emerald-400/20 text-emerald-100" : "bg-slate-700/60 text-slate-200"}`}>
          {enabled ? "On" : "Off"}
        </span>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-400">{detail}</p>
    </div>
  );
}

export default App;
