# Phase 27: 统一数据清洗层（DataCleaner）

## 元数据

- Status: `implemented`
- Implementation: `complete`
- Started: `2026-06-21`
- Completed: `2026-06-22`
- Git branch: `xg_dev`
- Commits: `06930e7`, `44c1b52`

## 目标

全路径 NaN/Inf 清理，防止 JSON 序列化时产生无效 `NaN` token，确保 Flask jsonify 输出合法 JSON。

## 范围

### 包含

1. **`_coerce_float` 修复**（`adapters.py`）：
   - `float('nan')` → `None`
   - 新增 `import math`，`math.isnan()` 判断

2. **`_parse_financials` / `_parse_forecast_profit` 修复**：
   - `_coerce_float(value)` 返回 None 时存储 `None` 而非原值

3. **`_clean_nan()` 模块级助手**（`routes_data.py`）：
   - 递归清洗 dict/list 中的 float NaN → None
   - get_fundamentals 路由使用

4. **Import 优化**：
   - `import math` 移至文件顶部

## 测试结果

A 股切片：全部通过。NaN 不再出现于 JSON 输出。
