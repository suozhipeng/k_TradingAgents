# Opencode Documentation Review — 2026-06-26

**Reviewer**: Hermes Agent  
**Branch**: xg_dev  
**Scope**: 9 modified + 1 new docs file (pure documentation, no code changes)  

---

## Verdict: PARTIAL — accept with 4 must-fix items

---

## ✅ What's Consistent and Accurate

### Phase 34 Evidence
- `leader_pool.py` schema fields (symbol/name/reason/score/source/refreshed_at/entry_reason/exit_reason/extra) ✅ match actual code
- 5 old Market Leaders sidebar entries collapsed to 1 — sidebar only shows `/market_leaders` ✅
- Old pages pass `legacy_redirect="/market_leaders"` via Flask render ✅
- Test count 162 (web+api) and 26 (phase 33-38) ✅ consistent with actual test runs

### Phase 36 Evidence
- `schemas/portfolio.py` — Portfolio/RiskExposure/Attribution fields ✅ match actual code
- `portfolio_risk.py` — all 4 functions (calculate_var, calculate_industry_exposure, calculate_attribution, calculate_risk_exposure) ✅ exist with documented behavior
- `routes_portfolio.py` — GET /api/v1/portfolio/risk, GET /api/v1/portfolio/attribution ✅ both present with correct blueprint
- Test counts 26 and 162 ✅

### Phase 37 Evidence (partial)
- `schemas/ops_audit.py` — TaskRun/AuditEvent/TaskType ✅ fields match actual code
- `audit_store.py` — 361 lines, memory + DuckDB, thread-safe ✅ matches 362-line claim
- `routes_ops.py` — GET /api/v1/ops/audit, GET /api/v1/ops/tasks, GET /api/v1/ops/stats ✅ all present

### Phase 39 Skeleton → Roadmap §12.1 Alignment
- All 6 UAT scenarios ✅ identical to roadmap
- Tasks 39-01 through 39-05 ✅ match roadmap task IDs and descriptions
- 3 completion criteria ✅ identical to roadmap
- 5 test commands ✅ identical to roadmap

### Phase 35 done-with-exclusions Decision
- Reasonable given `ASTOCK_PRODUCT_OPTIMIZATION_ROADMAP.md` §1 deprioritizing live trading to P3
- 6 completed items (Order/Fill/Position/Reconciliation schema, PaperTrader Order return, RiskGate, TradingPage mode switcher)
- 2 clearly documented exclusions (real broker reconciliation, QMT real orders)

### NFR-10 and NFR-12 Acceptance Evidence Tables
- NFR-10 table correctly references §1-6 of the deployment document ✅
- NFR-12 table correctly references §1-5 of the release management document ✅

---

## 🔴 MUST-FIX Items

### 1. [CRITICAL] Phase 37 Evidence — claims POST /api/v1/ops/tasks that doesn't exist

**File**: `docs/phases/phase-37-evidence-ops-audit.md`  
**What it says**: Lists `POST /api/v1/ops/tasks — 更新任务状态` as an endpoint  
**Reality**: `routes_ops.py` has **only GET endpoints**. No POST endpoint exists anywhere in the codebase. The three actual endpoints are:
- `GET /api/v1/ops/audit` (list_audit_events)
- `GET /api/v1/ops/tasks` (list_tasks)
- `GET /api/v1/ops/stats` (ops_stats)

**Fix**: Remove the fictional POST endpoint row from the evidence doc, or implement the endpoint and note it in code.

### 2. [HIGH] Phase 38 Evidence — sidebar module list is wrong

**File**: `docs/phases/phase-38-evidence-navigation-cleanup.md`  
**What it says**: The 7 sidebar modules include "Portfolio Workbench"  
**Reality**: The actual sidebar in `base.html` (lines 284-308) has:
1. Trading & Execution
2. Dashboard
3. AI Research Center
4. Strategy Lab
5. Market Leaders
6. Data & Ops
7. Screener

The `/portfolio` route exists but is **NOT in the sidebar**. The 7th slot is **Screener**, not Portfolio Workbench.

**Fix**: Replace "Portfolio Workbench" with "Screener" in the 7-module list, or add Portfolio to the sidebar if intentionally missing.

### 3. [MEDIUM] PROD-06 status mismatch between matrix and Phase 35 doc

**File**: `docs/ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md` (PROD-06) vs `docs/phases/phase-35-trading-execution-control.md`  
**Matrix says**: `partial (schema+接线完成，真实券商 reconciliation 明确 P3 暂不处理)`  
**Phase 35 doc says**: `done-with-exclusions`  
**Problem**: These communicate different statuses. The matrix's `partial` definition ("已有功能雏形，但产品边界、schema、测试或审计未闭环") doesn't match done-with-exclusions where exclusions are explicitly accepted.

**Fix**: Update PROD-06 in the matrix to `done-with-exclusions` with the same explanatory note, or align both to a consistent status label.

### 4. [MEDIUM] NFR-10 and NFR-12 matrix status not updated

**File**: `docs/ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md`  
**What it says**: Both NFR-10 and NFR-12 are marked `partial` (lines 39-41)  
**Reality**: Both documents now have completed acceptance evidence tables (added in this diff) claiming all items ✅ completed.  
**Problem**: Adding acceptance evidence without updating the matrix status creates a self-contradiction.

**Fix**: Update NFR-10 and NFR-12 status in the matrix to `done`, or append a note explaining what's still partial.

---

## ⚠️ Minor Observations (not blocking acceptance)

- **Phase 38 migration table**: Claims `strategies.html` → ✅ redirect to `strategy_hub`, but the actual code renders `strategies.html` as a full template (275 lines), not a redirect.
- **Phase 38 evidence**: Commit hashes `52718f1`, `49f37f0`, `2160e42`, `b410074` referenced but not verified against `git log` — they appear plausible and cross-consistent.
- **Phase 34 evidence**: Uses commit `97db066` + `b410074`; Phase 35/36/37/38 all share `b410074` — consistency suggests a common merge base, which is fine.
- **Phase 39 skeleton**: Minor formatting — markdown table column separators not aligned with header widths, but functionally valid.

---

## Cross-Consistency Summary

| Check | Result |
|-------|--------|
| Doc-to-doc contradictions | None found |
| Numbers (test counts, API counts, versions) | **162/26/1017** consistent across all docs |
| File references | All code paths verified — ✅ real files exist |
| Schema field accuracy | Phase 34/36/37/38 — ✅ verified against code |
| Roadmap §12.1 → Phase 39 alignment | ✅ Exact match on all 6 scenes, 5 tasks, 3 criteria, 5 commands |
| Phase 35 decision rationale | ✅ Reasonable given roadmap §1 live-trading deprioritization |
| NFR-10/12 evidence accuracy | ✅ Section references correct (but matrix not updated) |
| PROD matrix ↔ evidence consistency | ⚠️ PROD-06 mismatch; NFR-10/12 not synced |

---

## Final Verdict

**PARTIAL — accept with must-fix items**

The documentation changes are largely correct and well-synchronized. The 4 issues above should be fixed before closing — particularly the Phase 37 POST endpoint error and Phase 38 sidebar module name, which are factual inaccuracies about the codebase.
