# live provider 验证溯源

`docs/verification_provenance/` 用于保存 A 股 live provider 的历史验证证据。该目录有存在必要，因为 `tradingagents/astock/verification_provenance.py` 会读取这些 JSON 文件，为 provider 能力提供日期、commit、环境、命令和测试结果溯源。

## 1. 保留原因

- 记录 provider 在某个日期、某个 commit、某个 Python/系统环境下通过过验证。
- 为 `AStockDataRouter`、live research、provider fallback 和后续数据质量审计提供证据链。
- 避免把“曾经可用”和“当前一定可用”混为一谈。

## 2. 文件命名

命名格式：

```text
<provider>_<YYYY-MM-DD>.json
```

示例：

```text
mootdx_2026-06-15.json
tencent_2026-06-15.json
cninfo_2026-06-15.json
```

## 3. JSON 字段

每个文件至少应包含：

- `capabilities`：已验证能力列表。
- `evidence_ref`：对应 phase 文档或证据文档。
- `verified_on`：验证日期。
- `verified_at_commit`：验证所在 commit。
- `test_command`：原始验证命令。
- `pass_count` / `fail_count` / `skip_count`：测试结果计数。
- `python_version`：Python 版本。
- `platform`：运行平台。

## 4. 更新规则

- 不要覆盖旧文件；新的验证日期应追加新 JSON。
- 不要手工伪造 pass/fail 结果；只能来自实际运行命令。
- live provider 需要网络、远程服务和可能的登录态，验证结果可能随时间失效。
- 如果 provider 当前不可用，不删除旧证据；应追加新的失败或跳过证据，并在 phase 文档中说明。

## 5. 当前结论

- 本目录保留。
- 现有 2026-06-14 / 2026-06-15 JSON 作为历史 live 验证证据保留。
- 当前没有新的 live provider 验证命令运行，因此不追加新的 dated JSON。
