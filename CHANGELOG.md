# 变更记录

## v0.1.0（2026-11-12）

首个开源版本。

### 能力

- 流式 ZIP/CSV 摄入：不解压落盘、编码探测、行级清洗、坏行台账、成员级 checkpoint
- 双写入路径：批量索引（实测 1,161 行/秒）与逐案建图（4.1–9.9 行/秒）
- 存储：SQLite 单文件；`nodes/edges` 邻接图；内容哈希主键幂等
- 检索：FTS5 `trigram`（≥3 字符）+ 标题表 LIKE 降级 + 可插拔向量（fake/qwen/local）+ RRF
- 派生层可重建：FTS / 标题 / 引用（`build-judgment-*` 命令）
- 边界门：计划门三态（ALLOW/REVIEW/DENY）、会话污点、输出过滤
- `build-judgment-fts --full-text`：可选全文索引（体积约 2.6 倍，构建小时级）

### 实测（详见 docs/EXPERIMENTS.md）

- 470 万条语料：31.35 GiB、4,246 秒、1,161 行/秒
- 引用抽取 8,788,964 条（覆盖 94.5% 文档）
- `quick_check` ok；回归 92 passed / 2.2 s

### 已知限制

- 拒绝原因未落 `rejects` 表（仅计数）
- 向量层为原型（低覆盖、无 ANN）
- 单机批处理，无并发服务
