import { type PropsWithChildren, useState } from "react";
import { useTranslation } from "../hooks/useTranslation";
import type { AStockGraphReport } from "../types";
import { ASTOCK_SECTION_ORDER } from "../types";

type ReportViewerProps = {
  report: AStockGraphReport;
};

type SafetyLevel = "research_only" | "warning" | "actionable";

function getSafetyLevel(report: AStockGraphReport): SafetyLevel {
  if (report.actionable) return "actionable";
  if (report.decision_scope === "research_only") return "research_only";
  return "warning";
}

function ReportViewer({ report }: ReportViewerProps) {
  const safety = getSafetyLevel(report);

  return (
    <div className="space-y-5">
      {/* Header: ticker info */}
      <HeaderSection report={report} safety={safety} />

      {/* Safety tag */}
      <SafetyBanner report={report} safety={safety} />

      {/* Advisory chain */}
      <AdvisoryChain report={report} />

      {/* Research sections */}
      <SectionResults report={report} />

      {/* Provider coverage */}
      <ProviderCoverage report={report} />

      {/* Notes */}
      <NotesSection report={report} />

      {/* Runtime trace */}
      <TraceSection report={report} />
    </div>
  );
}

/* ── Header ── */
function HeaderSection({
  report,
  safety,
}: {
  report: AStockGraphReport;
  safety: SafetyLevel;
}) {
  const { t } = useTranslation();

  const badgeColors = {
    research_only: "bg-cyan-400/20 text-cyan-100 border-cyan-400/30",
    warning: "bg-amber-400/20 text-amber-100 border-amber-400/30",
    actionable: "bg-rose-400/20 text-rose-100 border-rose-400/30",
  };
  const badgeLabels = {
    research_only: t("report.safetyTag"),
    warning: t("report.safetyTag.warning"),
    actionable: t("report.safetyTag.actionable"),
  };

  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/80">{t("report.header")}</p>
          <h2 className="text-2xl font-semibold tracking-tight text-white">
            {report.symbol || report.ticker || "—"}
          </h2>
          <div className="flex flex-wrap gap-2 text-sm text-slate-400">
            {report.normalized_symbol && (
              <span className="rounded-lg bg-white/5 px-2.5 py-1 font-mono text-xs">
                {report.normalized_symbol}
              </span>
            )}
            {report.trade_date && (
              <span>
                {t("report.tradeDate")}<span className="text-slate-200">{report.trade_date}</span>
              </span>
            )}
            {report.runtime_mode && (
              <span>
                {t("report.mode")}<span className="text-slate-200">{report.runtime_mode}</span>
              </span>
            )}
            {report.runtime_profile && (
              <span>
                {t("report.profile")}<span className="text-slate-200">{report.runtime_profile}</span>
              </span>
            )}
          </div>
        </div>
        <span
          className={`rounded-full border px-3 py-1.5 text-xs font-medium uppercase tracking-[0.2em] ${badgeColors[safety]}`}
        >
          {badgeLabels[safety]}
        </span>
      </div>
      {report.status && (
        <div className="mt-3 flex items-center gap-2">
          <span className="rounded-full bg-white/5 px-2.5 py-1 text-xs text-slate-400">{t("report.status")}</span>
          <span className="text-sm text-slate-200">{report.status}</span>
        </div>
      )}
    </div>
  );
}

/* ── Safety Banner ── */
function SafetyBanner({
  report,
  safety,
}: {
  report: AStockGraphReport;
  safety: SafetyLevel;
}) {
  const { t } = useTranslation();

  if (safety === "research_only") {
    return (
      <Banner tone="cyan">
        {t("report.safetyDesc", { scope: report.decision_scope || "research_only" })}
      </Banner>
    );
  }
  return (
    <Banner tone="rose">
      {t("report.safetyDesc.actionable")}
    </Banner>
  );
}

type BannerTone = "cyan" | "amber" | "rose";

function Banner({
  children,
  tone,
}: PropsWithChildren<{ tone: BannerTone }>) {
  const colors = {
    cyan: "border-cyan-400/20 bg-cyan-400/[0.05] text-cyan-100",
    amber: "border-amber-400/20 bg-amber-400/[0.05] text-amber-100",
    rose: "border-rose-400/20 bg-rose-400/[0.05] text-rose-100",
  };
  return (
    <div className={`rounded-3xl border px-4 py-3 text-sm leading-6 ${colors[tone]}`}>
      {children}
    </div>
  );
}

/* ── Advisory Chain ── */
function buildAdvisoryBlocks(t: (key: string) => string): Array<{
  key: string;
  label: string;
  pick: (r: AStockGraphReport) => Record<string, unknown> | undefined;
  fields: Array<{ label: string; key: string }>;
}> {
  return [
    {
      key: "research_conclusion",
      label: t("report.researchConclusion"),
      pick: (r) => r.research_conclusion as Record<string, unknown> | undefined,
      fields: [
        { label: t("report.field.recommendation"), key: "recommendation" },
        { label: t("report.field.confidence"), key: "confidence" },
        { label: t("report.field.summary"), key: "summary" },
      ],
    },
    {
      key: "trader_proposal",
      label: t("report.traderProposal"),
      pick: (r) => r.trader_proposal as Record<string, unknown> | undefined,
      fields: [
        { label: t("report.field.candidateAction"), key: "candidate_action" },
        { label: t("report.field.positionCap"), key: "position_cap_pct" },
        { label: t("report.field.rationale"), key: "rationale" },
      ],
    },
    {
      key: "risk_decision",
      label: t("report.riskDecision"),
      pick: (r) => r.risk_decision as Record<string, unknown> | undefined,
      fields: [
        { label: t("report.field.verdict"), key: "verdict" },
        { label: t("report.field.riskLevel"), key: "risk_level" },
        { label: t("report.field.constraints"), key: "constraints" },
      ],
    },
    {
      key: "portfolio_decision",
      label: t("report.portfolioDecision"),
      pick: (r) => r.portfolio_decision as Record<string, unknown> | undefined,
      fields: [
        { label: t("report.field.disposition"), key: "disposition" },
        { label: t("report.field.exposureCap"), key: "exposure_cap_pct" },
        { label: t("report.field.portfolioNotes"), key: "portfolio_notes" },
      ],
    },
  ];
}

function AdvisoryChain({ report }: ReportViewerProps) {
  const { t } = useTranslation();
  const ADVISORY_BLOCKS = buildAdvisoryBlocks(t);
  const available = ADVISORY_BLOCKS.filter((block) => block.pick(report));

  if (!available.length) return null;

  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
      <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/80">{t("report.advisoryChain")}</p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {available.map((block) => {
          const data = block.pick(report)!;
          return (
            <div
              key={block.key}
              className="rounded-3xl border border-white/10 bg-slate-950/40 p-4"
            >
              <h3 className="text-sm font-semibold text-white">{block.label}</h3>
              <div className="mt-3 space-y-2 text-sm">
                {block.fields.map((field) => {
                  const value = data[field.key];
                  if (value === undefined || value === null || value === "") return null;

                  if (Array.isArray(value)) {
                    if (!value.length) return null;
                    return (
                      <div key={field.key}>
                        <span className="text-xs uppercase tracking-[0.15em] text-slate-400">
                          {field.label}
                        </span>
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          {value.map((v, i) => (
                            <span
                              key={`${field.key}-${i}`}
                              className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-slate-200"
                            >
                              {String(v)}
                            </span>
                          ))}
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div key={field.key}>
                      <span className="text-xs uppercase tracking-[0.15em] text-slate-400">
                        {field.label}
                      </span>
                      <p className="mt-0.5 text-slate-200">{String(value)}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ── Section Results ── */
function SectionResults({ report }: ReportViewerProps) {
  const { t } = useTranslation();
  const sections = ASTOCK_SECTION_ORDER.filter((name) => report.section_results?.[name]);
  if (!sections.length) return null;

  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
      <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/80">{t("report.sections")}</p>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10 text-left text-xs uppercase tracking-[0.2em] text-slate-400">
              <th className="pb-2 pr-4 font-normal">{t("report.sections.table.section")}</th>
              <th className="pb-2 pr-4 font-normal">{t("report.sections.table.status")}</th>
              <th className="pb-2 pr-4 font-normal">{t("report.sections.table.source")}</th>
              <th className="pb-2 pr-4 font-normal">{t("report.sections.table.data")}</th>
              <th className="pb-2 font-normal">{t("report.sections.table.summary")}</th>
            </tr>
          </thead>
          <tbody>
            {sections.map((name) => {
              const row = report.section_results![name]!;
              return (
                <tr key={name} className="border-b border-white/5 text-slate-200">
                  <td className="py-2.5 pr-4 font-medium capitalize">{name}</td>
                  <td className="py-2.5 pr-4">
                    <StatusBadge
                      label={row.status || "—"}
                      ok={row.status === "success" || row.status === "ok"}
                    />
                  </td>
                  <td className="py-2.5 pr-4 text-slate-400">{row.source || "—"}</td>
                  <td className="py-2.5 pr-4">
                    {row.has_data ? (
                      <span className="text-emerald-300">✓</span>
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </td>
                  <td className="py-2.5 text-slate-400 max-w-xs truncate">
                    {row.summary || "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function StatusBadge({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs ${
        ok
          ? "bg-emerald-400/15 text-emerald-200"
          : "bg-amber-400/15 text-amber-200"
      }`}
    >
      {label}
    </span>
  );
}

/* ── Provider Coverage ── */
function ProviderCoverage({ report }: ReportViewerProps) {
  const { t } = useTranslation();
  const sections = ASTOCK_SECTION_ORDER.filter(
    (name) => report.provider_coverage?.[name]
  );
  if (!sections.length) return null;

  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
      <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/80">{t("report.coverage")}</p>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10 text-left text-xs uppercase tracking-[0.2em] text-slate-400">
              <th className="pb-2 pr-4 font-normal">{t("report.coverage.table.section")}</th>
              <th className="pb-2 pr-4 font-normal">{t("report.coverage.table.source")}</th>
              <th className="pb-2 pr-4 font-normal">{t("report.coverage.table.status")}</th>
              <th className="pb-2 font-normal">{t("report.coverage.table.available")}</th>
            </tr>
          </thead>
          <tbody>
            {sections.map((name) => {
              const row = report.provider_coverage![name]!;
              return (
                <tr key={name} className="border-b border-white/5 text-slate-200">
                  <td className="py-2.5 pr-4 font-medium capitalize">{name}</td>
                  <td className="py-2.5 pr-4 text-slate-400">{row.source || "—"}</td>
                  <td className="py-2.5 pr-4">
                    <StatusBadge
                      label={row.status || "—"}
                      ok={row.status === "available" || row.status === "ok"}
                    />
                  </td>
                  <td className="py-2.5">
                    {row.available ? (
                      <span className="text-emerald-300">✓</span>
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/* ── Notes ── */
function NotesSection({ report }: ReportViewerProps) {
  const { t } = useTranslation();
  const missing = report.missing_data_notes ?? [];
  const degraded = report.degradation_notes ?? [];
  if (!missing.length && !degraded.length) return null;

  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
      <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/80">{t("report.notes")}</p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {missing.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-300">
              {t("report.notes.missingData")}
            </h3>
            <ul className="mt-2 space-y-1">
              {missing.map((note, i) => (
                <li key={`missing-${i}`} className="flex items-start gap-2 text-sm text-slate-300">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400/50" />
                  {note}
                </li>
              ))}
            </ul>
          </div>
        )}
        {degraded.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-rose-300">
              {t("report.notes.degradation")}
            </h3>
            <ul className="mt-2 space-y-1">
              {degraded.map((note, i) => (
                <li key={`degraded-${i}`} className="flex items-start gap-2 text-sm text-slate-300">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400/50" />
                  {note}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}

/* ── Runtime Trace (collapsible) ── */
function TraceSection({ report }: ReportViewerProps) {
  const { t } = useTranslation();
  const trace = report.runtime_trace ?? [];
  if (!trace.length) return null;

  const [open, setOpen] = useState(false);

  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between text-left"
      >
        <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/80">
          {t("report.trace")} ({trace.length} {t("report.trace.steps")})
        </p>
        <span className={`text-slate-400 transition ${open ? "rotate-180" : ""}`}>
          ▾
        </span>
      </button>
      {open && (
        <div className="mt-3 space-y-1">
          {trace.map((step, i) => (
            <pre
              key={`trace-${i}`}
              className="overflow-x-auto rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-xs leading-5 text-slate-300"
            >
              <span className="mr-2 text-slate-500">{i + 1}.</span>
              {step}
            </pre>
          ))}
        </div>
      )}
    </section>
  );
}

/* ── Helper: bull / bear / manager blocks (shown if advisory chain missing) ── */
function BullBearBlocks({ report }: ReportViewerProps) {
  const { t } = useTranslation();
  const hasAdvisory = buildAdvisoryBlocks(t).some((b) => b.pick(report));
  if (hasAdvisory) return null;
  if (!report.bull_view && !report.bear_view && !report.research_manager_conclusion) return null;

  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
      <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/80">{t("report.debate")}</p>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        {report.bull_view && (
          <div className="rounded-3xl border border-emerald-400/15 bg-emerald-400/[0.04] p-4">
            <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300">
              {t("report.debate.bull")}
            </h3>
            <p className="mt-2 text-sm leading-6 text-slate-200">{report.bull_view}</p>
          </div>
        )}
        {report.bear_view && (
          <div className="rounded-3xl border border-rose-400/15 bg-rose-400/[0.04] p-4">
            <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-rose-300">
              {t("report.debate.bear")}
            </h3>
            <p className="mt-2 text-sm leading-6 text-slate-200">{report.bear_view}</p>
          </div>
        )}
        {report.research_manager_conclusion && (
          <div className="rounded-3xl border border-amber-400/15 bg-amber-400/[0.04] p-4">
            <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-300">
              {t("report.debate.manager")}
            </h3>
            <p className="mt-2 text-sm leading-6 text-slate-200">
              {report.research_manager_conclusion}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

/* ── Empty state ── */
function EmptyReport() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-[320px] items-center justify-center">
      <div className="max-w-md text-center">
        <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/80">{t("report.noData")}</p>
      </div>
    </div>
  );
}

/* ── JSON Input ── */
function JsonInput({
  onReport,
}: {
  onReport: (report: AStockGraphReport) => void;
}) {
  const { t } = useTranslation();
  const [jsonText, setJsonText] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleTextChange(value: string) {
    setJsonText(value);
    setError(null);
    if (!value.trim()) return;

    try {
      const parsed = JSON.parse(value);
      if (
        !parsed.symbol &&
        !parsed.ticker &&
        !parsed.runtime_mode &&
        !parsed.runtime_profile
      ) {
        setError(t("report.error.notReport"));
        return;
      }
      onReport(parsed as AStockGraphReport);
    } catch (e) {
      setError(e instanceof SyntaxError ? e.message : t("report.error.invalidJson"));
    }
  }

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const text = reader.result as string;
      setJsonText(text);
      handleTextChange(text);
    };
    reader.readAsText(file);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <input
            type="file"
            accept=".json"
            onChange={handleFileUpload}
            className="block w-full cursor-pointer rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-slate-300 file:mr-3 file:rounded-full file:border-0 file:bg-cyan-300 file:px-3 file:py-1 file:text-xs file:font-semibold file:text-slate-950 hover:file:bg-cyan-200"
          />
        </div>
        <span className="text-xs text-slate-500">{t("report.pasteLabel")}</span>
      </div>
      <textarea
        value={jsonText}
        onChange={(e) => handleTextChange(e.target.value)}
        placeholder={t("report.pasteHint")}
        className="min-h-[120px] w-full rounded-2xl border border-white/10 bg-slate-950/60 p-4 font-mono text-xs leading-5 text-slate-200 placeholder-slate-500 focus:border-cyan-300/40 focus:outline-none"
      />
      {error && (
        <p className="text-sm text-rose-300">
          {error}
        </p>
      )}
    </div>
  );
}

/* ── Combined viewer: input + report display ── */
export default function ReportViewerWrapper() {
  const { t } = useTranslation();
  const [report, setReport] = useState<AStockGraphReport | null>(null);
  const [mode, setMode] = useState<"input" | "view">("input");

  return (
    <div className="space-y-5">
      <JsonInput
        onReport={(r) => {
          setReport(r);
          setMode("view");
        }}
      />

      {mode === "view" && report ? (
        <>
          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-500">
              {t("report.for", { symbol: report.symbol || report.ticker || "unknown symbol" })}
            </p>
            <button
              type="button"
              onClick={() => {
                setMode("input");
                setReport(null);
              }}
              className="rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs text-slate-300 transition hover:border-cyan-200/40 hover:text-white"
            >
              {t("report.clearAndNew")}
            </button>
          </div>
          <ReportViewer report={report} />
          <BullBearBlocks report={report} />
        </>
      ) : (
        <EmptyReport />
      )}
    </div>
  );
}

export { ReportViewer, EmptyReport };
