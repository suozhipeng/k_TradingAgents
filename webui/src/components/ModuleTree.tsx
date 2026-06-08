import type { ModuleRecord, ModuleType } from "../types";

type FilterValue = ModuleType | "all";

type ModuleTreeProps = {
  modules: ModuleRecord[];
  selectedPath: string;
  search: string;
  filter: FilterValue;
  filterOptions: Array<{ label: string; value: FilterValue }>;
  onSelect: (path: string) => void;
  onSearchChange: (value: string) => void;
  onFilterChange: (value: FilterValue) => void;
};

const typeOrder: ModuleType[] = ["dataflow", "analyst", "researcher", "trader", "risk", "config", "cli"];

const typeLabels: Record<ModuleType, string> = {
  analyst: "Analysts",
  researcher: "Researchers",
  trader: "Trader",
  risk: "Risk",
  dataflow: "Dataflows",
  config: "Config",
  cli: "CLI",
};

function ModuleTree({
  modules,
  selectedPath,
  search,
  filter,
  filterOptions,
  onSelect,
  onSearchChange,
  onFilterChange,
}: ModuleTreeProps) {
  const groupedModules = typeOrder
    .map((type) => ({
      type,
      items: modules.filter((module) => module.type === type),
    }))
    .filter((group) => group.items.length > 0);

  return (
    <aside className="panel flex min-h-[640px] flex-col overflow-hidden">
      <div className="border-b border-white/10 p-4">
        <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/80">Module Tree</p>
        <div className="mt-3 space-y-3">
          <input
            className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/60"
            placeholder="Search name, path, input, output, dependency, risk..."
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            {filterOptions.map((option) => {
              const active = filter === option.value;
              return (
                <button
                  key={option.value}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                    active
                      ? "bg-cyan-300 text-slate-950"
                      : "border border-white/10 bg-white/5 text-slate-300 hover:border-cyan-200/40 hover:text-white"
                  }`}
                  type="button"
                  onClick={() => onFilterChange(option.value)}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {groupedModules.length ? (
          <div className="space-y-4">
            {groupedModules.map((group) => (
              <section key={group.type}>
                <div className="mb-2 flex items-center justify-between px-2">
                  <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                    {typeLabels[group.type]}
                  </h2>
                  <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-slate-400">
                    {group.items.length}
                  </span>
                </div>
                <div className="space-y-2">
                  {group.items.map((module) => {
                    const active = module.path === selectedPath;
                    return (
                      <button
                        key={`${module.type}-${module.path}`}
                        className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                          active
                            ? "border-cyan-300/50 bg-cyan-300/10 shadow-lg shadow-cyan-950/30"
                            : "border-white/[0.08] bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.05]"
                        }`}
                        type="button"
                        onClick={() => onSelect(module.path)}
                      >
                        <p className="text-sm font-medium text-white">{module.name}</p>
                        <p className="mt-1 line-clamp-2 text-xs text-slate-400">{module.path}</p>
                        <p className="mt-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">{module.type}</p>
                      </button>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <div className="space-y-3 rounded-2xl border border-dashed border-white/10 bg-white/[0.03] p-4 text-sm text-slate-400">
            <p>No modules match the current search and type filter.</p>
            <p>Try clearing search or switching back to <span className="text-white">All</span>.</p>
          </div>
        )}
      </div>
    </aside>
  );
}

export default ModuleTree;
