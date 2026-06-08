import type { PropsWithChildren } from "react";
import type { ModuleRecord } from "../types";

function ModuleDetail({ module }: { module?: ModuleRecord }) {
  if (!module) {
    return (
      <section className="panel flex min-h-[640px] items-center justify-center p-8 text-slate-400">
        Select a module to inspect its static metadata.
      </section>
    );
  }

  return (
    <section className="panel min-h-[640px] p-6">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/80">Selected Module</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight text-white">{module.name}</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">{module.description}</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-right">
          <p className="text-[11px] uppercase tracking-[0.24em] text-slate-400">Type</p>
          <p className="mt-2 text-lg font-semibold capitalize text-white">{module.type}</p>
        </div>
      </div>

      <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(280px,0.85fr)]">
        <article className="space-y-5">
          <InfoBlock title="Primary Path">
            <code className="rounded-xl bg-slate-950/70 px-3 py-2 text-sm text-cyan-100">{module.path}</code>
          </InfoBlock>

          <InfoBlock title="Inputs">
            <TagList items={module.inputs} />
          </InfoBlock>

          <InfoBlock title="Outputs">
            <TagList items={module.outputs} />
          </InfoBlock>
        </article>

        <div className="space-y-5">
          <InfoBlock title="Dependencies">
            <TagList items={module.dependencies} />
          </InfoBlock>

          <InfoBlock title="Related Files">
            <TagList items={module.related_files} />
          </InfoBlock>

          <InfoBlock title="System Note">
            <p className="text-sm leading-6 text-slate-300">
              This module is part of a static architecture summary. The WebUI never imports or executes the
              TradingAgents business logic at runtime.
            </p>
          </InfoBlock>
        </div>
      </div>
    </section>
  );
}

function InfoBlock({ title, children }: PropsWithChildren<{ title: string }>) {
  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
      <h3 className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function TagList({ items }: { items: string[] }) {
  if (!items.length) {
    return <p className="text-sm text-slate-500">No entries recorded.</p>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span key={item} className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs text-slate-200">
          {item}
        </span>
      ))}
    </div>
  );
}

export default ModuleDetail;
