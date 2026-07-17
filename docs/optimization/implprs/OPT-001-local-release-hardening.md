# OPT-001 ImplPR: 本地正式版闭环

## 实现

- Dashboard 在 local-release 不再请求 Ops API 或自动运行动量回测。
- 市场摘要在 local-release 空库时不访问 live provider。
- `/api/v1/ai/analyze` 作为受支持的本地 AI Research 端点加入 allowlist。
- `local-release` extra 与验证脚本声明 DuckDB；`uv.lock` 已同步。
- 修正文档与项目 Skill 的启动命令和产品范围。

## 验证

- `uv lock --check`
- `tests/test_local_release.py`
- `tests/test_local_release_browser.py`
- `scripts/verify_local_release.sh`

均已通过；DeepSeek live 调用未执行，等待轮换后的密钥通过 `DEEPSEEK_API_KEY` 注入。
