# Hermes 持久化协作文档

`docs/hermes/` 用于保存需要进入 Git 的 Hermes 协作模板。它有存在必要，因为这些模板定义了 Hermes、DeepSeek、Codex 在本仓库中的可复用交付格式；它不是运行状态目录。

## 1. 保留范围

本目录只保存：

- DeepSeek 编码 brief 模板。
- Codex review packet 模板。
- 需要随仓库版本化的 Hermes 协作说明。
- 与 `tradingagents-core`、A 股交付 skill、ECC review skill 相关的稳定分派规则。

## 2. 不应放入本目录

以下内容不应放在 `docs/hermes/`：

- 当前运行状态。
- 临时 blocker 文件。
- 带时间戳的运行日志。
- 分支本地执行输出。
- Hermes 当前会话的中间产物。

这些运行态文件应继续放在 `.hermes/`。`.hermes/` 是本地执行状态，不应作为项目长期文档入口。

## 3. 当前模板

- [DeepSeek 编码 Brief 模板](./deepseek_brief_template.md)
- [Codex Review Packet 模板](./codex_review_packet_template.md)

## 4. 当前结论

- `docs/hermes/` 保留。
- 当前文件数量足够，不需要继续拆更多模板。
- 如果 Hermes skill 发生新增或蒸馏，应优先更新 `docs/hermes-skills.md`；只有模板本身发生变化时才更新本目录。
