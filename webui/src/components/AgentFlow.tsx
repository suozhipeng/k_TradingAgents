import type { ModuleRecord } from "../types";

type FlowStage = {
  label: string;
  match: (module: ModuleRecord) => boolean;
};

const stages: FlowStage[] = [
  { label: "Data Source", match: (module) => module.type === "dataflow" },
  { label: "Analysts", match: (module) => module.type === "analyst" },
  { label: "Researchers", match: (module) => module.type === "researcher" },
  { label: "Trader", match: (module) => module.type === "trader" && !/portfolio manager/i.test(module.name) },
  { label: "Risk Managers", match: (module) => module.type === "risk" && !/portfolio manager/i.test(module.name) },
  { label: "Portfolio Manager", match: (module) => /portfolio manager/i.test(module.name) },
];

function AgentFlow({
  modules,
  selectedModule,
}: {
  modules: ModuleRecord[];
  selectedModule?: ModuleRecord;
}) {
  return (
    <section className="panel overflow-hidden p-5">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/80">Agent Flow</p>
          <h2 className="mt-2 text-xl font-semibold text-white">Static pipeline overview</h2>
        </div>
        <p className="max-w-xl text-right text-sm text-slate-400">
          The flow uses module metadata only. Counts show how many repository modules support each stage.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
        {stages.map((stage, index) => {
          const stageModules = modules.filter(stage.match);
          const active = selectedModule ? stage.match(selectedModule) : false;

          return (
            <div
              key={stage.label}
              className={`relative rounded-3xl border p-4 transition ${
                active
                  ? "border-cyan-300/50 bg-cyan-300/10 shadow-lg shadow-cyan-950/20"
                  : "border-white/10 bg-white/[0.03]"
              }`}
            >
              {index < stages.length - 1 ? (
                <div className="pointer-events-none absolute -right-3 top-1/2 hidden h-px w-6 -translate-y-1/2 bg-gradient-to-r from-cyan-200/70 to-transparent xl:block" />
              ) : null}
              <p className="text-[11px] uppercase tracking-[0.25em] text-slate-400">Stage {index + 1}</p>
              <h3 className="mt-2 text-lg font-semibold text-white">{stage.label}</h3>
              <p className="mt-3 text-3xl font-semibold text-cyan-100">{stageModules.length}</p>
              <p className="mt-2 text-xs leading-5 text-slate-400">
                {stageModules.slice(0, 2).map((module) => module.name).join(" / ") || "No mapped modules"}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default AgentFlow;
