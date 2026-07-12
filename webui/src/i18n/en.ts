export const en: Record<string, string> = {
  /* ── App header ── */
  "app.title": "TradingAgents Static WebUI",
  "app.subtitle": "Module map, flows, reports, and settings",
  "app.disclaimer":
    "This dashboard reads only a static modules snapshot. It does not run trading, call external APIs, or execute TradingAgents business code.",
  "app.error.title": "Unable to render static modules",
  "app.error.label": "WebUI error",
  "app.error.message":
    "modules.json is empty. The WebUI needs a static snapshot to render.",

  /* ── Nav ── */
  "nav.dashboard": "Dashboard",
  "nav.dataHub": "Data Hub",
  "nav.moduleMap": "Module Map",
  "nav.agentFlow": "Agent Flow",
  "nav.taskCenter": "Task Center",
  "nav.reports": "Reports",
  "nav.settings": "Settings",
  "nav.backtest": "Backtest",
  "nav.marketData": "Market Data",

  /* ── Statistics cards ── */
  "stat.modules": "Modules",
  "stat.visible": "Visible",
  "stat.types": "Types",
  "stat.staticSource": "Static Source",

  /* ── Dashboard section ── */
  "section.dashboard.kicker": "Dashboard",
  "section.dashboard.title": "Market Overview · Data Health · Freshness · Watchlist · Tasks · Reports · Alerts",
  "section.dashboard.desc": "Daily research workspace powered by real APIs — market data, decision summary, paper positions, and alerts.",
  "dashboard.analysts": "Analysts",
  "dashboard.researchers": "Researchers",
  "dashboard.dataflows": "Dataflows",
  "dashboard.configCli": "Config / CLI",
  "dashboard.checklist": "Checklist status",
  "dashboard.check.dashboard": "Dashboard section present",
  "dashboard.check.moduleMap": "Module Map section present",
  "dashboard.check.agentFlow": "Agent Flow section present",
  "dashboard.check.taskCenter": "Task Center section present",
  "dashboard.check.reports": "Reports section present",
  "dashboard.check.settings": "Settings section present",

  /* ── Data Hub section ── */
  "section.dataHub.kicker": "Data Hub",
  "section.dataHub.title": "Real Market Data Download & Incremental Upsert",
  "section.dataHub.desc": "Download K-line, valuation and other market data from providers, upsert into DuckDB, track async refresh job progress, and monitor data source health.",

  /* ── Agent Flow section ── */
  "section.agentFlow.kicker": "Agent Flow",
  "section.agentFlow.title":
    "Data Source → Analysts → Researchers → Trader → Risk Managers → Portfolio Manager",
  "section.agentFlow.desc":
    "A static overview of the repository flow, with counts derived from modules.json only.",

  /* ── Task Center section ── */
  "section.taskCenter.kicker": "Task Center",
  "section.taskCenter.title": "Search, filter, and inspect a module",
  "section.taskCenter.desc":
    "This section acts as the control surface for locating and reviewing static modules.",
  "taskCenter.openModuleMap": "Open Module Map",
  "taskCenter.openReports": "Open Reports",
  "taskCenter.openSettings": "Open Settings",
  "taskCenter.resetFilters": "Reset Filters",
  "taskCenter.search": "Search",
  "taskCenter.filter": "Filter",
  "taskCenter.selected": "Selected",
  "taskCenter.none": "None",
  "taskCenter.whatToDo": "What to do here",
  "taskCenter.hint1":
    "• Search by module name, path, dependency, input, output, or risk.",
  "taskCenter.hint2":
    "• Filter to isolate analysts, researchers, risk teams, dataflows, config, or CLI.",
  "taskCenter.hint3":
    "• Select a module to view its IO, dependency surface, and risk notes.",

  /* ── Module Map filter options ── */
  "filter.all": "All",
  "filter.analyst": "Analyst",
  "filter.researcher": "Researcher",
  "filter.trader": "Trader",
  "filter.risk": "Risk",
  "filter.dataflow": "Dataflow",
  "filter.config": "Config",
  "filter.cli": "CLI",

  /* ── Reports section ── */
  "section.reports.kicker": "Reports",
  "section.reports.title": "A-stock report viewer",
  "section.reports.desc":
    "Paste or upload an AStockGraphReport JSON payload to view a structured report with advisory chain, research sections, provider coverage, and runtime trace.",

  /* ── Report viewer ── */
  "report.header": "AStockGraphReport",
  "report.safetyTag": "Research Only",
  "report.safetyTag.warning": "Not Research-Only",
  "report.safetyTag.actionable": "Actionable",
  "report.safetyDesc":
    "Research-only output. Decision scope: {scope}. No trading execution. Read-only analysis.",
  "report.safetyDesc.actionable":
    "This payload is marked as actionable. Verify before relying on any trade signal.",
  "report.tradeDate": "Trade date: ",
  "report.mode": "Mode: ",
  "report.profile": "Profile: ",
  "report.status": "Status",
  "report.advisoryChain": "Advisory Chain",
  "report.researchConclusion": "Research Conclusion",
  "report.traderProposal": "Trader Proposal",
  "report.riskDecision": "Risk Decision",
  "report.portfolioDecision": "Portfolio Decision",
  "report.field.recommendation": "Recommendation",
  "report.field.confidence": "Confidence",
  "report.field.summary": "Summary",
  "report.field.candidateAction": "Candidate Action",
  "report.field.positionCap": "Position Cap",
  "report.field.rationale": "Rationale",
  "report.field.verdict": "Verdict",
  "report.field.riskLevel": "Risk Level",
  "report.field.constraints": "Constraints",
  "report.field.disposition": "Disposition",
  "report.field.exposureCap": "Exposure Cap",
  "report.field.portfolioNotes": "Notes",
  "report.sections": "Research Sections",
  "report.sections.table.section": "Section",
  "report.sections.table.status": "Status",
  "report.sections.table.source": "Source",
  "report.sections.table.data": "Data",
  "report.sections.table.summary": "Summary",
  "report.coverage": "Provider Coverage",
  "report.coverage.table.section": "Section",
  "report.coverage.table.source": "Source",
  "report.coverage.table.status": "Status",
  "report.coverage.table.available": "Available",
  "report.notes": "Operational Notes",
  "report.notes.missingData": "Missing Data",
  "report.notes.degradation": "Degradation",
  "report.trace": "Runtime Trace",
  "report.trace.steps": "steps",
  "report.debate": "Research Debate",
  "report.debate.bull": "Bull",
  "report.debate.bear": "Bear",
  "report.debate.manager": "Manager",
  "report.clearAndNew": "Clear & New",
  "report.noData":
    "No report loaded. Paste or upload an AStockGraphReport JSON payload above to view the report.",
  "report.pasteHint": "Paste AStockGraphReport JSON here...",
  "report.pasteLabel": "or paste JSON below",
  "report.for": "Report for {symbol}",
  "report.error.notReport":
    "Parsed JSON does not look like an AStockGraphReport (missing symbol/ticker/runtime fields).",
  "report.error.invalidJson": "Invalid JSON",

  /* ── Backtest section ── */
  "section.backtest.kicker": "Backtest",
  "section.backtest.title": "Strategy Backtest",
  "section.backtest.desc": "Run a strategy backtest via the REST API.",
  "backtest.symbol": "Symbol",
  "backtest.strategy": "Strategy",
  "backtest.startDate": "Start Date",
  "backtest.endDate": "End Date",
  "backtest.run": "Run Backtest",
  "backtest.running": "Running...",
  "backtest.noData": 'Click "Run Backtest" to begin.',
  "backtest.error": "Backtest failed: {msg}",

  /* ── Market Data section ── */
  "section.marketData.kicker": "Market Data",
  "section.marketData.title": "Kline Data",
  "section.marketData.desc": "Fetch historical kline data via the REST API.",
  "marketData.symbol": "Symbol",
  "marketData.interval": "Interval",
  "marketData.fetch": "Fetch Data",
  "marketData.fetching": "Fetching...",
  "marketData.noData": 'Click "Fetch Data" to load.',
  "marketData.error": "Data fetch failed: {msg}",

  /* ── Settings section ── */
  "section.settings.kicker": "Settings",
  "section.settings.title": "Static-only configuration",
  "section.settings.desc":
    "These settings are informational and remind users that the WebUI is read-only.",
  "settings.externalApis": "External APIs",
  "settings.externalApis.detail": "Disabled in WebUI",
  "settings.tradingExecution": "Trading Execution",
  "settings.tradingExecution.detail": "Not available",
  "settings.dataSource": "Data Source",
  "settings.editMode": "Edit Mode",
  "settings.editMode.detail": "Read-only snapshot",
  "settings.on": "On",
  "settings.off": "Off",

  /* ── Market ── */
  "market.us": "US Market",
  "market.astock": "A-Share",

  /* ── App loading ── */
  "loading": "Loading...",

  /* ── Static source label ── */
  "staticSource": "Static snapshot: webui/src/data/modules.json",

  /* ── Report markdown ── */
  "report.md.summary": "## Snapshot Summary",
  "report.md.totalModules": "- Total modules: **{count}**",
  "report.md.visibleModules": "- Visible after current filters: **{count}**",
  "report.md.selectedModule": "- Selected module: **{name}**",
  "report.md.none": "None",
  "report.md.typeCoverage": "## Type Coverage",
  "report.md.analysts": "- Analysts: {count}",
  "report.md.researchers": "- Researchers: {count}",
  "report.md.trader": "- Trader: {count}",
  "report.md.risk": "- Risk: {count}",
  "report.md.dataflows": "- Dataflows: {count}",
  "report.md.config": "- Config: {count}",
  "report.md.cli": "- CLI: {count}",
  "report.md.currentSelection": "## Current Selection",
  "report.md.path": "- Path: `{path}`",
  "report.md.type": "- Type: **{type}**",
  "report.md.description": "- Description: {desc}",
  "report.md.noSelection": "No module selected.",
  "report.md.notes": "## Notes",
  "report.md.note1": "- This report is rendered from static WebUI data only.",
  "report.md.note2": "- It is safe to view without running any trading logic.",
  "report.md.note3": "- Search indexing includes names, paths, descriptions, inputs, outputs, dependencies, and risks.",
};
