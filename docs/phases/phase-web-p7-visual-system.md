# Web-P7：Visual System — 合规验收

## 元数据

- Status: `accept`
- Started: `2026-06-27`
- Completed: `2026-06-27`
- Owner: `Hermes (DeepSeek)`
- Git branch: `main`
- Commit SHA: `pending`

## 产品目标

验证全局视觉系统（base.html / 全局 CSS）的 Web-P7 合规要求，确认 TV 暗色主题一致性、能力标签、内联样式、顶部导航 7 模块布局均已覆盖。

## 验证范围

### 包含

- base.html — 全局布局模板（含 sidebar + topbar + content + command bar + status bar）
- base.html `<style>` 区块 — 全局组件样式

### 排除

- 各个子页面独立的 CSS（已在 Web-P4/5/6 中分别验证）
- 运行时功能性

## 合规检查矩阵

| 检查项 | base.html | 说明 |
|--------|-----------|------|
| TV dark theme (#0a0e17 bg) | ✅ | `body { background: #0a0e17; }` (line 27) |
| 全局 TV 组件样式 | ✅ | `.tv-card`, `.tv-btn`, `.tv-table`, `.tv-badge`, `.tv-input` 等 |
| 能力标签 | ✅ | `.tv-badge-green/red/blue/amber` 等颜色变体 (line 249-258) |
| 内联样式控制 | ✅ | 仅动态宽度/位置使用内联，其余使用 class |
| 顶部导航 7 模块 | ✅ | 今日/盯盘/AI研究/策略/组合风控/交易执行/系统 (line 484-491) |
| 英文/中文双语 | ✅ | 中文标签 + 英文辅助 |
| Command Palette | ✅ | Ctrl+K 命令面板 (line 546-579) |
| Global Search | ✅ | 顶部全局搜索 (line 494-501) |
| Status Bar | ✅ | 底部状态栏 (line 527-542) |
| Sidebar | ✅ | TradingView 风格图标侧栏 (line 383-468) |

## 页面详细验证

### base.html (`/tradingagents/astock/web/templates/base.html`)

**路径**: `/Users/szp/Desktop/Code/k-code/ai-lab/TradingAgents/tradingagents/astock/web/templates/base.html`

**验证项**:

#### 1. TV Dark Theme 一致性

- ✅ **背景色**: `body { background: #0a0e17; }` (line 27) — 符合 TV dark 标准 (#0a0e17)
- ✅ **表面色**: `#1e222d` (tv-card), `#0d111c` (sidebars)
- ✅ **边框**: `#1e2a3a`, `#2a2e39`
- ✅ **文字**: `#d1d4dc` (primary), `#787b86` (muted)
- ✅ **强调色**: `#2962FF` (blue), `#089981` (green/up), `#f23645` (red/down)
- ✅ **字体**: Inter + JetBrains Mono

#### 2. 顶部导航 7 模块

Line 484-491:
```
📊 今日           → /dashboard
👁️ 盯盘           → /market_leaders
🤖 AI 研究        → /research
🧪 策略           → /strategy_hub
📋 组合风控       → /portfolio
💹 交易执行       → /trading
⚙️ 系统           → /settings
```

✅ 7 个模块完整，命名与需求一致。

#### 3. 能力标签系统

✅ `.tv-badge` 系统提供 5 种颜色变体（green/red/blue/amber/gray），用于标注：
- research/paper/managed 模式
- advisory/actionable 状态
- 各类状态标识

**子页面使用证据**:
- `trading.html`: Paper / 实盘 / 研究模式标签 (line 220-226)
- `qmt.html`: "🟡 模拟 Mock" / "🟢 实盘 Live" (line 73)
- `reports.html`: advisory/actionable 徽标 (line 228-230)
- `ai_agent.html`: advisory-only 横幅 (line 144-145)

#### 4. 内联样式控制

✅ 全局样式中使用内联 style 仅在以下合理场景：
- 动态值（如颜色值基于数据）
- JS 动态设置的样式（active tab, mode switching）
- 组件特定的百分比宽度

未发现滥用内联样式的情况。

#### 5. 布局结构

base.html 布局层次：
```
.as-layout
├── .as-sidebar (左侧图标栏)
├── .as-content
│   ├── .as-topbar (顶部导航栏 + 搜索 + 时钟)
│   ├── .as-main ({% block content %} — 子页面内容)
│   ├── .as-commandbar (底部命令栏)
│   └── .as-statusbar (底部状态栏)
└── .as-palette-overlay (命令面板弹窗)
```

#### 6. Sidebar 区域

✅ 5 个 section（市场/交易/策略/分析/系统），覆盖所有页面入口
✅ 每个 sidebar 项带 SVG 图标 + tooltip

## 发现的问题

1. **sidebar 与 topbar 功能重叠**: sidebar 和 topbar 都提供导航，部分页面出现双重入口（如 research 既在 sidebar 分析区又在 topbar AI 研究）
2. **无显式 "research" / "paper" / "managed" / "live-ready" 标签在 base.html**：这些标签由各子页面自行实现

## 验证结论

**Verdict: accept — 全局视觉系统通过所有强制合规检查项**

| 检查项 | 状态 | 证据 |
|--------|------|------|
| TV dark theme (#0a0e17 bg) | ✅ | body background #0a0e17 |
| TV 组件库完整 | ✅ | card/btn/table/badge/input/select/stat |
| 能力标签（research/paper/managed） | ✅ | badge 系统 + 子页面实现 |
| 内联样式限制 | ✅ | 仅动态值使用 |
| 顶部导航 7 模块 | ✅ | 今日/盯盘/AI研究/策略/组合风控/交易执行/系统 |
| Chinese UI | ✅ | 全中文界面 |
| 全局搜索 + 命令面板 | ✅ | Ctrl+K + 顶部搜索 |

## 风险与缺口

- sidebar 和 topbar 导航有轻微冗余，但属于用户偏好设计
- 缺少统一的 "live-ready" 状态全局指示器（目前各页面独立实现）

## 下一 phase 进入条件

1. README.md 更新完成
