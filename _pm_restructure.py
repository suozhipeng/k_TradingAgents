#!/usr/bin/env python3
"""
PM-grade docs restructure for TradingAgents.

Strategy:
  docs/01-arch/    → architecture, API, ADR
  docs/02-guide/   → onboarding, user manual, glossary
  docs/03-ops/     → deployment, live trading, compliance, data sources
  docs/04-dev/     → PRD, test plan, traceability
  docs/05-phases/  → keep active phases only (phase-30+ and phase-web-*)
  docs/hermes/     → unchanged
  docs/verification/ → unchanged
  docs/_archived/  → everything removed

Key merges:
  - BACKLOG → extract CHANGELOG.md + ROADMAP.md, keep slim backlog
  - PRD.md + REQUIREMENTS.md + TECH_REQUIREMENTS.md → PRD.md
  - API_CONTRACTS.md + BACKEND_API_REFERENCE.md → API.md
  - BOUNDARY_AND_UI_REFACTOR_PLAN → archive (completed)
  - review-opencode-docs → archive (dated)
  - Completed phases (phase-00 to phase-28) → archive
"""
import os, re, shutil, json

DOCS = "/Users/szp/Desktop/Code/k-code/ai-lab/TradingAgents/docs"
ARCHIVE = os.path.join(DOCS, "_archived")

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def read(path):
    with open(path) as f:
        return f.read()

def write(path, content):
    ensure_dir(os.path.dirname(path))
    with open(path, "w") as f:
        f.write(content)

def move_to_archive(src):
    """Move file under docs/ to docs/_archived/ preserving relative path."""
    rel = os.path.relpath(src, DOCS)
    dst = os.path.join(ARCHIVE, rel)
    ensure_dir(os.path.dirname(dst))
    # Check if exists
    if os.path.exists(dst):
        base, ext = os.path.splitext(dst)
        dst = f"{base}_{int(os.path.getmtime(src))}{ext}"
    shutil.move(src, dst)
    return dst

actions = []

# ═══════════════════════════════════════════════════════════
# 1. BACKLOG → CHANGELOG + ROADMAP + slim backlog
# ═══════════════════════════════════════════════════════════
backlog = read(os.path.join(DOCS, "ASTOCK_BACKLOG.md"))

# Extract changelog entries (lines with dates like 2026-06-xx)
changelog_lines = ["# Changelog\n", "\n", "自动从 Backlog 提取。完整历史见 `_archived/ASTOCK_BACKLOG.md`。\n", "\n"]
roadmap_lines = ["# Roadmap\n", "\n"]
slim_backlog_parts = []
current_section = ""
in_done_section = False

for line in backlog.split("\n"):
    # Detect date-marked entries for changelog
    if re.match(r'^##?\s*\d{4}-\d{2}-\d{2}', line):
        changelog_lines.append(f"\n### {line.strip('# ')}\n")
        continue
    if re.match(r'^- \*\*.*\d{4}-\d{2}-\d{2}', line):
        changelog_lines.append(f"\n{line}\n")
        continue
    # Detect "已完成" or "Done" sections
    if re.search(r'##\s+.*(已完成|Done|Complete|已实现)', line, re.IGNORECASE):
        in_done_section = True
        slim_backlog_parts.append(line + "\n")
        continue
    if re.search(r'##\s+.*(待办|Todo|Planned|Backlog)', line, re.IGNORECASE):
        in_done_section = False
        slim_backlog_parts.append(line + "\n")
        continue
    if re.search(r'##\s+.*(Roadmap|路线图|规划)', line, re.IGNORECASE):
        roadmap_lines.append(f"\n{line}\n")
        # Include this section in roadmap but not in slim backlog
        continue
    
    if in_done_section:
        # Skip "已完成" content (not needed in active backlog)
        continue
    else:
        slim_backlog_parts.append(line)

# Write CHANGELOG
write(os.path.join(DOCS, "CHANGELOG.md"), "".join(changelog_lines))
actions.append("CREATED: CHANGELOG.md (extracted from BACKLOG)")

# Write ROADMAP
roadmap_content = "# Roadmap\n\n当前季度计划。详细 backlog 见 `BACKLOG.md`。\n\n" + "\n".join(slim_backlog_parts[:200])
write(os.path.join(DOCS, "ROADMAP.md"), roadmap_content[:3000])
actions.append("CREATED: ROADMAP.md")

# Write slim backlog
slim_backlog = "# Backlog\n\n> 待完成任务清单。已完成项已归档至 `_archived/ASTOCK_BACKLOG.md`\n\n" + "\n".join(slim_backlog_parts)
write(os.path.join(DOCS, "BACKLOG.md"), slim_backlog[:5000])
actions.append("CREATED: BACKLOG.md (slimmed)")

# Archive old backlog
move_to_archive(os.path.join(DOCS, "ASTOCK_BACKLOG.md"))
actions.append("ARCHIVED: ASTOCK_BACKLOG.md (3469L → slimmed)")

# ═══════════════════════════════════════════════════════════
# 2. Merge requirements → PRD.md
# ═══════════════════════════════════════════════════════════
prd = read(os.path.join(DOCS, "ASTOCK_PRD.md"))
reqs = read(os.path.join(DOCS, "ASTOCK_REQUIREMENTS.md"))
tech_reqs = read(os.path.join(DOCS, "ASTOCK_TECH_REQUIREMENTS.md"))

merged_prd = "# Product Requirements Document\n\n"
merged_prd += "> 合并自 `ASTOCK_PRD.md` + `ASTOCK_REQUIREMENTS.md` + `ASTOCK_TECH_REQUIREMENTS.md`\n\n"
merged_prd += "---\n\n## 1. 产品概述\n\n" 
# Extract first few sections from PRD
prd_lines = prd.split("\n")
in_skip = True
for line in prd_lines:
    if line.startswith("# "):
        in_skip = False
        continue
    if not in_skip:
        merged_prd += line + "\n"

merged_prd += "\n\n---\n\n## 2. 需求详情\n\n> 以下内容来自 `ASTOCK_REQUIREMENTS.md`\n\n"
# Extract non-header content from REQUIREMENTS
req_lines = reqs.split("\n")
for line in req_lines:
    if not line.startswith("# "):
        merged_prd += line + "\n"

merged_prd += "\n\n---\n\n## 3. 技术需求\n\n> 以下内容来自 `ASTOCK_TECH_REQUIREMENTS.md`\n\n"
tech_lines = tech_reqs.split("\n")
for line in tech_lines:
    if not line.startswith("# "):
        merged_prd += line + "\n"

write(os.path.join(DOCS, "04-dev", "PRD.md"), merged_prd)
actions.append("CREATED: 04-dev/PRD.md (merged 3 req docs)")

# Archive old
move_to_archive(os.path.join(DOCS, "ASTOCK_PRD.md"))
move_to_archive(os.path.join(DOCS, "ASTOCK_REQUIREMENTS.md"))
move_to_archive(os.path.join(DOCS, "ASTOCK_TECH_REQUIREMENTS.md"))
actions.append("ARCHIVED: old PRD + REQUIREMENTS + TECH_REQUIREMENTS")

# ═══════════════════════════════════════════════════════════
# 3. Merge API docs → API.md
# ═══════════════════════════════════════════════════════════
api_contracts = read(os.path.join(DOCS, "ASTOCK_API_CONTRACTS.md"))
api_ref = read(os.path.join(DOCS, "ASTOCK_BACKEND_API_REFERENCE.md"))

merged_api = "# API 参考\n\n> 合并自 `ASTOCK_API_CONTRACTS.md` + `ASTOCK_BACKEND_API_REFERENCE.md`\n\n"
merged_api += "---\n\n## 1. 契约规范\n\n"
for line in api_contracts.split("\n"):
    if not line.startswith("# "):
        merged_api += line + "\n"

merged_api += "\n\n---\n\n## 2. 完整端点参考\n\n"
for line in api_ref.split("\n"):
    if not line.startswith("# "):
        merged_api += line + "\n"

write(os.path.join(DOCS, "01-arch", "API.md"), merged_api)
actions.append("CREATED: 01-arch/API.md (merged API docs)")

# Archive old
move_to_archive(os.path.join(DOCS, "ASTOCK_API_CONTRACTS.md"))
move_to_archive(os.path.join(DOCS, "ASTOCK_BACKEND_API_REFERENCE.md"))
actions.append("ARCHIVED: old API_CONTRACTS + BACKEND_API_REFERENCE")

# ═══════════════════════════════════════════════════════════
# 4. Archive completed phases (phase-00 to phase-28)
# ═══════════════════════════════════════════════════════════
phases_dir = os.path.join(DOCS, "phases")
keep_phases = [
    "phase-30", "phase-31", "phase-32", "phase-33", "phase-34",
    "phase-35", "phase-36", "phase-37", "phase-38", "phase-39",
    "phase-web-", "README.md", "TEMPLATE.md",
]

for f in os.listdir(phases_dir):
    fp = os.path.join(phases_dir, f)
    if not os.path.isfile(fp) or not f.endswith(".md"):
        continue
    should_keep = any(f.startswith(k) for k in keep_phases)
    if not should_keep:
        move_to_archive(fp)
        actions.append(f"ARCHIVED: phases/{f} (completed)")

# ═══════════════════════════════════════════════════════════
# 5. Move remaining root docs to new directories
# ═══════════════════════════════════════════════════════════

# architecture
arch_docs = {
    "ASTOCK_ARCHITECTURE_DECISION_RECORDS.md": "01-arch/ADR.md",
}
# guide
guide_docs = {
    "QUICK_START.md": "02-guide/QUICK_START.md",
    "USER_MANUAL.md": "02-guide/USER_MANUAL.md",
    "GLOSSARY.md": "02-guide/GLOSSARY.md",
    "ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md": "02-guide/strategy-dev.md",
}
# ops
ops_docs = {
    "ASTOCK_DEPLOYMENT_AND_ENVIRONMENT.md": "03-ops/deployment.md",
    "ASTOCK_LIVE_RESEARCH_SETUP.md": "03-ops/live-research.md",
    "ASTOCK_LIVE_TRADING_RUNBOOK.md": "03-ops/live-trading.md",
    "ASTOCK_DATA_SOURCE_LICENSE_AND_USAGE.md": "03-ops/data-sources.md",
    "ASTOCK_RISK_DISCLOSURE_AND_COMPLIANCE.md": "03-ops/compliance.md",
    "ASTOCK_PROJECT_RISK_REGISTER.md": "03-ops/risk-register.md",
    "ASTOCK_PRODUCT_METRICS_AND_OPS_REQUIREMENTS.md": "03-ops/ops-metrics.md",
    "PRIVACY_POLICY.md": "03-ops/privacy.md",
}
# dev
dev_docs = {
    "ASTOCK_TEST_ACCEPTANCE_PLAN.md": "04-dev/test-plan.md",
    "ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md": "04-dev/traceability-matrix.md",
    "ASTOCK_HERMES_EXECUTION_TASK_PACKS.md": "04-dev/hermes-tasks.md",
}

# Other root docs to move
other_docs = {
    "HERMES_CODEX_DEEPSEEK_WORKFLOW.md": "hermes-workflow.md",
    "HERMES_SKILLS_PLAYBOOK.md": "hermes-skills.md",
}

# Archive if already at root level
root_archive = [
    "ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md",
    "ASTOCK_DOCUMENT_SCOPE_REGISTER.md",
    "review-opencode-docs-2026-06-26.md",
]

for name in root_archive:
    fp = os.path.join(DOCS, name)
    if os.path.exists(fp):
        move_to_archive(fp)
        actions.append(f"ARCHIVED: {name}")

# Move files to new locations
for src_name, dst_rel in {**arch_docs, **guide_docs, **ops_docs, **dev_docs}.items():
    src = os.path.join(DOCS, src_name)
    if os.path.exists(src):
        dst = os.path.join(DOCS, dst_rel)
        ensure_dir(os.path.dirname(dst))
        shutil.move(src, dst)
        actions.append(f"MOVED: {src_name} → {dst_rel}")

# Move HERMES workflow/skills to root
for src_name, new_name in other_docs.items():
    src = os.path.join(DOCS, src_name)
    if os.path.exists(src):
        dst = os.path.join(DOCS, new_name)
        shutil.move(src, dst)
        actions.append(f"MOVED: {src_name} → {new_name}")

# ═══════════════════════════════════════════════════════════
# 6. Write new README
# ═══════════════════════════════════════════════════════════
readme = """# TradingAgents — AStock Pro 文档

> 产品经理整理的文档体系。每个主题**只有一个权威文档**。

---

## 📂 文档结构

```
docs/
├── README.md              ← 你在这里
├── CHANGELOG.md           ← 版本日志
├── ROADMAP.md             ← 当前季度规划
├── BACKLOG.md             ← 待完成任务清单
│
├── 01-arch/               ← 架构设计
│   ├── API.md             ← API 端点参考（合并契约+引用）
│   └── ADR.md             ← 架构决策记录
│
├── 02-guide/              ← 上手与使用
│   ├── QUICK_START.md     ← 快速开始
│   ├── USER_MANUAL.md     ← 用户手册
│   ├── GLOSSARY.md        ← 术语表
│   └── strategy-dev.md    ← 策略开发规范
│
├── 03-ops/                ← 运维与合规
│   ├── deployment.md      ← 部署与环境
│   ├── live-trading.md    ← 实盘运行
│   ├── live-research.md   ← 研究环境
│   ├── data-sources.md    ← 数据源授权与字典
│   ├── compliance.md      ← 风险披露与合规
│   ├── risk-register.md   ← 项目风险登记
│   ├── ops-metrics.md     ← 产品指标与运维
│   └── privacy.md         ← 隐私声明
│
├── 04-dev/                ← 需求与开发
│   ├── PRD.md             ← 产品需求（合并PRD+需求+技术需求）
│   ├── test-plan.md       ← 测试验收计划
│   ├── traceability-matrix.md ← 需求追踪矩阵
│   └── hermes-tasks.md    ← Hermes 任务包归档
│
├── 05-phases/             ← 阶段设计文档（活跃中）
│   ├── phase-30*          ← 交易执行
│   ├── phase-31*          ← 数据质量
│   ├── phase-32*          ← 策略实验室
│   ├── phase-33*          ← AI 研究中心
│   ├── phase-34*          ← 市场领导看板
│   ├── phase-35*          ← 交易执行控制
│   ├── phase-36*          ← 组合风控
│   ├── phase-37*          ← 运维审计
│   ├── phase-38*          ← 导航清理
│   ├── phase-39*          ← E2E UAT
│   └── phase-web-*        ← Web 阶段
│
├── hermes/                ← Hermes 协作文档
├── verification/          ← 数据源验证
└── _archived/             ← 历史版本（可查）
```

---

## 🧭 快速导航

| 我想... | 打开... |
|---------|---------|
| 启动服务 | `02-guide/QUICK_START.md` |
| 查看 API | `01-arch/API.md` |
| 了解产品功能 | `04-dev/PRD.md` |
| 查最新变更 | `CHANGELOG.md` |
| 看当前计划 | `ROADMAP.md` |
| 部署上线 | `03-ops/deployment.md` |
| 实盘交易 | `03-ops/live-trading.md` |
| 开发策略 | `02-guide/strategy-dev.md` |

---

> 历史文档已归档至 `_archived/`。如需查阅，直接进入。
"""

write(os.path.join(DOCS, "README.md"), readme)
actions.append("UPDATED: README.md (新导航结构)")

# ═══════════════════════════════════════════════════════════
# Print summary
# ═══════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"完成! 共 {len(actions)} 项操作")
print(f"{'='*60}")
for a in actions:
    print(f"  • {a}")

# Count final state
total = 0
for root, dirs, files in os.walk(DOCS):
    if "_archived" in root:
        continue
    for f in files:
        if f.endswith(".md"):
            total += 1
archived = 0
for root, dirs, files in os.walk(ARCHIVE):
    for f in files:
        if f.endswith(".md"):
            archived += 1

print(f"\n📊 活跃文档: {total}")
print(f"📦 历史归档: {archived}")
