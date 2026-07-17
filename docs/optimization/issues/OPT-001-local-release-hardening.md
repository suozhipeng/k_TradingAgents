# OPT-001 Issue: 本地正式版首屏与交付链路不闭环

## 证据

- Dashboard 自动请求已禁用 Ops API，并自动触发可能访问外部 provider 的动量回测。
- 空本地库的市场摘要会隐式访问 live provider，浏览器门禁可因此超时。
- `uv.lock` 与项目版本漂移；`local-release` extra 未声明 DuckDB。
- 文档建议了启动器不支持的 `--local-release` 参数，且混入已禁用交易范围。

## 目标与验收

本地正式版必须离线可打开、只在用户显式操作时访问 provider、安装/启动文档可执行，并保持研究/回测边界。后端 gate、真实 Chromium smoke gate、锁文件检查均须通过。
