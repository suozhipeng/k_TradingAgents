#!/usr/bin/env python3
"""Deep docs audit — categorize by audience, purpose, and overlap."""
import os, re, sys

DOCS = "/Users/szp/Desktop/Code/k-code/ai-lab/TradingAgents/docs"
ALL = []

def collect(dir_path):
    for f in sorted(os.listdir(dir_path)):
        fp = os.path.join(dir_path, f)
        if os.path.isdir(fp) and not f.startswith("_"):
            collect(fp)
        elif f.endswith(".md") and not f.startswith("."):
            rel = os.path.relpath(fp, DOCS)
            with open(fp) as fh:
                content = fh.read()
            lines = content.count("\n") + 1
            h1 = ""
            for line in content.split("\n"):
                m = re.match(r'^#\s+(.+)$', line)
                if m:
                    h1 = m.group(1).strip()
                    break
            ALL.append({"path": rel, "size": len(content), "lines": lines, "title": h1, "content": content})

collect(DOCS)

# ── Classification rules ──
CATEGORIES = {
    "architecture": ["ARCHITECTURE_DECISION", "BOUNDARY", "API_CONTRACT", "BACKEND_API"],
    "requirements": ["PRD", "REQUIREMENTS", "TECH_REQUIREMENTS", "TEST_ACCEPTANCE", "TRACEABILITY"],
    "progress": ["BACKLOG", "HERMES_EXECUTION", "DOCUMENT_SCOPE"],
    "onboarding": ["QUICK_START", "USER_MANUAL", "GLOSSARY", "README"],
    "deployment": ["DEPLOYMENT", "LIVE_RESEARCH", "LIVE_TRADING", "RUNBOOK"],
    "compliance": ["PRIVACY", "RISK_DISCLOSURE", "DATA_SOURCE", "PROJECT_RISK"],
    "strategy": ["STRATEGY_DEVELOPMENT", "STRATEGY"],
    "hermes": ["HERMES_CODEX", "HERMES_SKILLS", "hermes/"],
    "phases": ["phases/"],
    "metrics": ["PRODUCT_METRICS", "OPS_REQUIREMENTS"],
    "verification": ["verification_provenance"],
}

def classify(path):
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw.lower() in path.lower():
                return cat
    return "other"

per_category = {}
for d in ALL:
    cat = classify(d["path"])
    per_category.setdefault(cat, []).append(d)

print("=" * 80)
print("DOCS AUDIT — 资深产品经理视角")
print("=" * 80)
print(f"\n总计: {len(ALL)} 文档\n")

# ── Category summary ──
for cat in ["architecture", "requirements", "progress", "onboarding", "deployment",
            "compliance", "strategy", "hermes", "phases", "metrics", "verification", "other"]:
    items = per_category.get(cat, [])
    if not items:
        continue
    print(f"\n{'─'*60}")
    print(f"📁 {cat.upper()} ({len(items)} 个)")
    print(f"{'─'*60}")
    for d in items:
        tag = ""
        # Flag potential issues
        if "BACKLOG" in d["path"] and d["lines"] > 2000:
            tag = " ⚠️ 超巨大(>2000行)"
        if "TODO" in d["content"] or "todo" in d["content"].lower():
            tag += " 📝含TODO"
        if "superseded" in d["content"].lower() or "废弃" in d["content"]:
            tag += " 🗑️标记废弃"
        print(f"  {d['lines']:>5}L {d['path'][:55]:55s}{tag}")
        if d["title"]:
            print(f"       → {d['title'][:70]}")

# ── Content overlap analysis ──
print(f"\n\n{'='*80}")
print("重叠分析：查找跨文档的重复议题")
print(f"{'='*80}")

# Find docs that contain similar patterns (e.g., duplicate "API endpoint" lists)
api_endpoint_count = {}
for d in ALL:
    # Count API endpoint references
    endpoints = re.findall(r'/api/v\d+/[a-z_-]+', d["content"])
    if endpoints:
        api_endpoint_count[d["path"]] = len(set(endpoints))

print("\n📡 API 端点引用最多的文档:")
for path, count in sorted(api_endpoint_count.items(), key=lambda x: -x[1])[:10]:
    print(f"  {count:>3} 个端点 {path}")

# Find docs that list strategies
for d in ALL:
    if "MovingAverageTrend" in d["content"] and "backtest" in d["path"].lower():
        print(f"\n  📊 策略列表: {d['path']} ({d['lines']}L)")

print(f"\n\n{'='*80}")
print("建议")
print(f"{'='*80}")

# Current vs recommended structure
print("""
当前问题:
1. ASTOCK_BACKLOG.md (3468行) — 巨无霸，融合了backlog+进度+roadmap+changelog+web_workbench
   读者无法快速找到所需信息，建议拆分为：
   - CHANGELOG.md (简洁的版本日志，<100行)
   - ROADMAP.md (当前季度计划，<200行)
   - backlog 精简为核心未完成项

2. 根目录 28 个 ASTOCK_* 文档仍然太多
   建议按子目录分组：
   docs/01-arch/         架构/API/ADR
   docs/02-guide/        用户手册/快速开始/术语
   docs/03-ops/          部署/运维/实盘/合规
   docs/04-dev/          需求/PRD/策略开发/测试
   docs/05-phases/       阶段归档
   docs/hermes/          保持不变
   docs/verification/    保持不变

3. ASTOCK_REQUIREMENTS.md (468L) 和 ASTOCK_TECH_REQUIREMENTS.md (345L) 内容高度重叠
   → 合并为一个 PRD.md

4. ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md (467L) — 重构已完成，内容过时
   → 归档，或提炼关键决策到 ADR

5. 阶段文档 (52个 phases) 很大部分是"已完成阶段"的设计文档
   已完成阶段 → 提取 ADR + 归档设计文档
""")
