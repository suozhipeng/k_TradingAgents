export type ModuleType = "analyst" | "researcher" | "trader" | "risk" | "dataflow" | "config" | "cli";

export type ModuleRecord = {
  name: string;
  path: string;
  type: ModuleType;
  description: string;
  inputs: string[];
  outputs: string[];
  dependencies: string[];
  risks: string[];
  related_files: string[];
};

// from AStockGraphReport Python dataclass - tradingagents/astock/runtime.py
export type AStockGraphReport = {
  ticker?: string;
  symbol?: string;
  normalized_symbol?: string;
  trade_date?: string;
  runtime_mode?: string;
  runtime_profile?: string;
  status?: string;
  decision_scope?: string;
  actionable?: boolean;
  analyst_summary?: string;
  bull_view?: string;
  bear_view?: string;
  research_manager_conclusion?: string;
  research_conclusion?: {
    recommendation?: string;
    confidence?: string;
    summary?: string;
  };
  trader_proposal?: {
    candidate_action?: string;
    position_cap_pct?: string;
    rationale?: string;
  };
  risk_decision?: {
    verdict?: string;
    risk_level?: string;
    constraints?: string[];
  };
  portfolio_decision?: {
    disposition?: string;
    exposure_cap_pct?: string;
    portfolio_notes?: string;
  };
  section_results?: Record<
    string,
    {
      status?: string;
      source?: string;
      has_data?: boolean;
      summary?: string;
    }
  >;
  provider_coverage?: Record<
    string,
    {
      source?: string;
      status?: string;
      available?: boolean;
    }
  >;
  missing_data_notes?: string[];
  degradation_notes?: string[];
  runtime_trace?: string[];
};

export const ASTOCK_SECTION_ORDER = [
  "market",
  "news",
  "fundamentals",
  "announcements",
  "research",
] as const;
