# Hermes / Codex / DeepSeek 协作流程

本文档定义本仓库中 Hermes、Codex、DeepSeek 协作进行 phase delivery 时的操作契约。

## 1. 目标

使用一个 controller、一个 coder、一个 reviewer：

- `Hermes`：项目经理、任务分派器、phase owner。
- `DeepSeek`：代码实现 worker。
- `Codex`：独立 review、纠偏和验收 gate。

非平凡项目工作必须保持该角色分离。同一个 agent 不能在没有 Codex review 的情况下同时实现并自我验收 phase 结论。

## 2. 角色边界

### Hermes

Hermes 负责：

- phase 选择和排序。
- 任务拆解。
- scope / out-of-scope 边界。
- 分派 repo-local skills。
- 进度跟踪和下一步调度。
- 为 DeepSeek 打包 coding brief。
- 收集修改文件、测试证据和开放风险。
- 在不涉及代码、测试、产品结论变化时，应用狭义事实性文档修正。
- Codex accept 后更新持久化 phase artifacts。

Hermes 不得：

- 对有意义的代码变更跳过 ECC review gate。
- 仅凭聊天信心把 phase 标记为 complete。
- 当前 phase 仍有阻塞 review gap 时开启后续 phase。

### DeepSeek

DeepSeek 负责：

- 在当前 Hermes phase 边界内修改代码。
- 记录本地实现说明。
- 返回精确修改文件。
- 返回已运行命令和原始 pass/fail 结果。
- 主动暴露不确定性，而不是静默扩大 scope。

DeepSeek 不得：

- 重新定义产品边界。
- 没有测试证据就声称 phase 完成。
- 用自测结果绕过 Codex review。

### Codex

Codex 负责：

- 验证 Hermes 任务拆解是否合理。
- 检查 coding plan 是否匹配 active phase。
- 审查修改文件和声称结论。
- 判断测试是否覆盖本次触达面。
- 发现 scope drift、无证据假设和文档不一致。
- 给出 `accept`、`partial` 或 `fail`。
- 当实现证据无法支撑结论时要求返工。

Codex 优先级：

1. 阻塞 bug 或错误结论。
2. scope drift 或产品边界违规。
3. 缺少回归覆盖。
4. 文档漂移。

## 3. 必需执行循环

1. Hermes 选择 phase 并加载相关 skills。跨 phase 的 A 股工作先加载 `tradingagents-core` 和 `astock-rollout-orchestrator`。
2. Hermes 为 DeepSeek 编写 coding brief。brief 必须包含目标、包含范围、排除范围、目标文件或模块、测试命令、验收标准和文档更新项。
3. DeepSeek 只实现 scoped work，并返回修改文件、关键行为变化、测试结果、开放风险和假设。
4. Codex 使用 `ecc-readonly-review` 或 `ecc-self-test` 执行 review gate。
5. 如果 Codex 返回 `partial` 或 `fail`，Hermes 必须生成 correction brief 并交回 DeepSeek。
6. 只有 Codex 返回 `accept` 后，Hermes 才能更新 `docs/phases/`、`docs/phases/README.md`、`docs/ASTOCK_CURRENT_STATUS.md`，提交通过 review 的变更，并记录最终 commit SHA。

## 4. skill 加载规则

默认规则：

- 项目梳理、模块边界、WebUI 重构、策略、回测、风控、数据链路相关任务必须加载 `tradingagents-core`。
- provider 交付使用 `astock-provider-delivery`。
- interface / tools / analyst 接线使用 `astock-analyst-delivery`。
- phase 控制使用 `astock-rollout-orchestrator`。
- 静态 review 使用 `ecc-readonly-review`。
- 回归执行使用 `ecc-self-test`。

涉及策略开发时必须同步参考 `docs/ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md`。

## 5. fallback review gate

Codex 是默认 reviewer。如果当前环境中 Codex 不可用，Hermes 只有在满足以下全部条件时才能自行执行 acceptance review：

- 阻塞原因明确且外部化，例如认证失败、服务不可用、重复超时或用户明确要求继续。
- Hermes 记录 fallback review 被使用，以及 Codex 不可用的原因。
- Hermes 使用与 Codex 相同的 ECC 验收标准：正确性、漂移、回归覆盖、文档一致性。
- Hermes 不伪造 Codex verdict。

fallback 模式下，Hermes 可以输出同形态 verdict：

- `accept`
- `partial`
- `fail`

但必须明确标记为 `Hermes fallback review`，不能写成 `Codex accept`。

### 狭义 Hermes-only 例外

当以下条件全部满足时，Hermes 可以在 Codex accept 前直接应用文档事实修正：

- 不修改 Python source 或测试。
- 不改变产品边界、验收结论或状态 taxonomy。
- 只修正已确认事实，例如 commit SHA、日期、文件名、命令引用、与 `git log` 客观不一致的归档字段。

该例外不允许 Hermes：

- 把 phase 标记为 complete。
- 增加或暗示 Codex `accept` verdict。
- 改变 `docs/phases/README.md` 的状态语义。
- 修改产品决策、scope 或验收标准。

如果文档更新超出事实对齐范围，必须回到正常 `Hermes -> DeepSeek -> Codex` 循环；只有满足 fallback 条件时才允许 `Hermes -> DeepSeek -> Hermes fallback review`。

最终提交辅助命令：

```bash
python3 scripts/hermes_codex_git_gate.py \
  --verdict accept \
  --commit-message "phase message here" \
  path/to/file1 path/to/file2
```

## 6. Codex review gate

以下任一条件成立时必须执行 Codex review：

- Python source 发生变化。
- 测试发生变化。
- docs 声称某个 phase 结果已完成。
- phase archive 被更新。
- runtime 或 schema contract 发生变化。
- provider 或 execution 边界发生变化。

Codex 必须输出紧凑 verdict：

- 检查范围。
- 结论：`accept`、`partial` 或 `fail`。
- 证据。
- 开放风险。
- 下一步。

如果 Codex 不可用并使用 Hermes fallback review，Hermes 必须输出相同结构，并额外写明 fallback reason。

## 7. handoff 格式

### Hermes -> DeepSeek

```text
Phase：
目标：
包含范围：
排除范围：
文件 / 模块：
需要运行的测试：
验收标准：
需要更新的文档：
返回格式：
```

### DeepSeek -> Codex

```text
已修改文件：
行为摘要：
已运行测试：
结果：
开放风险：
假设：
```

### Codex -> Hermes

```text
Review 范围：
结论：accept | partial | fail
证据：
漂移或缺陷：
必须修正项：
```

## 8. Hermes 命令模式

本仓库推荐命令形态：

```bash
hermes chat -q "Phase objective here. Follow AGENTS.md and docs/HERMES_CODEX_DEEPSEEK_WORKFLOW.md. Load tradingagents-core first. Use astock-rollout-orchestrator for phase control, use DeepSeek for coding, and prepare output for Codex review before phase acceptance." \
  --skills tradingagents-core,astock-rollout-orchestrator,ecc-readonly-review
```

实现任务较重且需要回归时：

```bash
hermes chat -q "Implement the scoped phase work only. Follow AGENTS.md and docs/HERMES_CODEX_DEEPSEEK_WORKFLOW.md. Load tradingagents-core first. Return changed files, tests, risks, and unresolved assumptions for Codex review." \
  --skills tradingagents-core,astock-rollout-orchestrator,ecc-self-test
```

## 9. 半自动 phase loop

本仓库推荐低触达 driver：

```bash
scripts/hermes_phase_loop.sh --mode continue
```

适用场景：希望 Hermes 持续推进当前 phase，而不是每次重写 control prompt。脚本以 one-shot project-manager 模式运行 Hermes，并强制输出一个终态：

- `PHASE_ADVANCED`
- `BLOCKED_ON_CODEX`
- `BLOCKED_ON_HUMAN_INPUT`
- `BLOCKED_ON_ENVIRONMENT`

脚本会把持久化状态写入 `.hermes/`：

- `.hermes/phase_loop_latest.txt`：最近一次完整 Hermes 输出。
- `.hermes/phase_loop_status.env`：最近终态和时间戳。
- `.hermes/codex_review_request.md`：阻塞在 review gate 时的 Codex review packet。
- `.hermes/human_input_request.md`：阻塞在人类输入或环境问题时的请求。
- `.hermes/runs/*.txt`：带时间戳的执行历史。

当所有编号 phase 已完成时，phase loop 必须自动进入 backlog / maintenance 模式，而不是因为不存在下一个 phase 就停止。此时 Hermes 应先处理 `docs/ASTOCK_CURRENT_STATUS.md` 中最高优先级 gap，再处理未提交或未推送的 accepted work，最后才请求人类决策。

推荐 cron：

```bash
hermes cron create \
  --name "tradingagents-phase-loop" \
  --workdir /Users/szp/Desktop/Code/k-code/ai-lab/TradingAgents \
  --script /Users/szp/Desktop/Code/k-code/ai-lab/TradingAgents/scripts/hermes_phase_loop.sh \
  "every 30m"
```

终态为 `BLOCKED_ON_CODEX` 时，把 review packet 交给 Codex。终态为 `BLOCKED_ON_HUMAN_INPUT` 或 `BLOCKED_ON_ENVIRONMENT` 时，才需要人类介入。

## 10. 仓库规则

- `docs/phases/` 是 canonical phase archive。
- `docs/HERMES_SKILLS_PLAYBOOK.md` 是顶层 skill dispatch contract。
- `docs/ASTOCK_CURRENT_STATUS.md` 是当前事实基线。
- `docs/ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md` 是策略开发规范。
- `docs/hermes/` 只保存可复用模板，不保存运行态。
- `docs/verification_provenance/` 保存 live provider 验证溯源。
- phase 不能只基于 DeepSeek 输出关闭。
- phase 不能只基于 Hermes narration 关闭。
- Codex review evidence 是默认验收路径的一部分，不是 optional extra。
- 如果 Codex 不可用，Hermes fallback review 必须满足上面的 fallback gate 并明确标注。
- Codex accept 可提交变更后，Hermes 必须在 handoff 前创建 Git commit。
- 原 TradingAgents 底层 AI 分析核心默认保留，不在 A 股功能重构中主动修改。

## 11. 纠偏策略

如果 Codex 拒绝当前结果，Hermes 必须明确说明：

- 哪个结论没有证据支撑。
- 哪些文件或测试不足。
- 问题属于 scope drift、缺少实现还是证据弱。
- DeepSeek 下一步必须做什么修正。

只有纯文档事实对齐属于例外：如果修正不改变代码、测试、产品含义或验收状态，Hermes 可以直接应用，并随后把修正后的记录交回 Codex review。

被拒绝的问题修正前，不要进入下一个 phase，除非 human owner 明确重新定义 scope。
