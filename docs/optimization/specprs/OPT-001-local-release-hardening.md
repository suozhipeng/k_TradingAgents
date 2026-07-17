# OPT-001 SpecPR: 本地正式版闭环

## 方案

1. local-release Dashboard 跳过 Ops、告警 fallback 与动量回测请求。
2. local-release 空库市场摘要只报告本地状态，不隐式拉取 provider。
3. 允许唯一的 AI Research 分析端点，保留交易/模拟盘/QMT 禁用边界。
4. 同步 `local-release` 依赖、锁文件、验证脚本和用户入口文档。

## 风险与边界

- 不修改显式数据刷新或非 local-release 行为。
- AI 调用仍要求运行期环境变量密钥；不把密钥写入仓库。
- 不改变交易与执行 API 的拒绝规则。
