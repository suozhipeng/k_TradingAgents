import type { ModuleRecord } from "../types";

function RiskPanel({ module }: { module?: ModuleRecord }) {
  if (!module) {
    return (
      <aside className="panel flex min-h-[640px] items-center justify-center p-8 text-slate-400">
        Select a module to inspect inputs, outputs, dependencies, and risks.
      </aside>
    );
  }

  return (
    <aside className="panel min-h-[640px] p-4">
      <p className="px-2 text-xs uppercase tracking-[0.28em] text-cyan-200/80">Operational View</p>
      <div className="mt-4 space-y-4">
        <Section title="Inputs" items={module.inputs} tone="cyan" emptyText="No inputs recorded" />
        <Section title="Outputs" items={module.outputs} tone="emerald" emptyText="No outputs recorded" />
        <Section title="Dependencies" items={module.dependencies} tone="amber" emptyText="No dependencies recorded" />
        <Section title="Risks" items={module.risks} tone="rose" emptyText="No risks recorded" />
      </div>
    </aside>
  );
}

function Section({
  title,
  items,
  tone,
  emptyText,
}: {
  title: string;
  items: string[];
  tone: "cyan" | "emerald" | "amber" | "rose";
  emptyText: string;
}) {
  const toneClasses = {
    cyan: "border-cyan-300/15 bg-cyan-300/[0.06] text-cyan-100",
    emerald: "border-emerald-300/15 bg-emerald-300/[0.06] text-emerald-100",
    amber: "border-amber-300/15 bg-amber-300/[0.06] text-amber-100",
    rose: "border-rose-300/15 bg-rose-300/[0.06] text-rose-100",
  };

  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">{title}</h3>
        <span className="rounded-full bg-white/5 px-2 py-1 text-[11px] text-slate-400">{items.length}</span>
      </div>
      <div className="mt-3 space-y-2">
        {items.length ? (
          items.map((item) => (
            <div key={item} className={`rounded-2xl border px-3 py-2 text-sm leading-6 ${toneClasses[tone]}`}>
              {item}
            </div>
          ))
        ) : (
          <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-400">
            {emptyText}
          </div>
        )}
      </div>
    </section>
  );
}

export default RiskPanel;
