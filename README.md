# docgraph-kb

> **论文**：Domain Pack: 面向可验证领域智能体的工程方法论（预印本 v0.1）  
> DOI: [10.5281/zenodo.24341406](https://doi.org/10.5281/zenodo.24341406)
>
> **代码版本**：v0.1.1（脱敏公开版）
>
> **数据边界**：仓库不含真实判例、客户数据或个人信息；示例与测试均为合成数据。

> 单文件 SQLite 文档知识库引擎：**流式摄入 → 文档图 → 检索 → 确定性防护**。
> A single-file SQLite knowledge base engine: streaming ingest, document graph,
> FTS5 + hybrid retrieval, and deterministic guardrails.

## 这是什么

把专业领域的文档组织成**可检索、可溯源、可增量维护**的知识库，通常需要
「搜索引擎 + 图数据库 + 向量库」三套基础设施。本项目把这几层能力压进**一个 SQLite 文件**：

| 层 | 实现 |
|---|---|
| 文档 | 内容哈希主键，`INSERT OR IGNORE` 天然幂等 |
| 图 | 邻接表 `nodes` / `edges`，唯一索引承担去重 |
| 全文 | FTS5 `trigram` 分词（中文子串检索） |
| 向量 | 可插拔 embedder（fake / qwen / local）+ numpy 余弦 + RRF 融合 |
| 质量台账 | 原始行、拒绝、去重、断点（坏行不静默丢） |
| 防护 | 计划门 / 会话污点 / 输出过滤，确定性状态机，可回归 |

## 这不是什么

- ❌ **不附带任何数据集**：仓库不含判例、法条或任何真实文档；测试与示例全部为合成数据
- ❌ 不是法律意见系统，不预测裁判结果，不替代执业律师
- ❌ 不是「图 = 证明」：检索结果是线索，必须回指原文

## 为什么值得看

专业检索不是「找相似段落」，而是要回答：**这份文档引用了什么？在哪个版本有效？
哪些引用之间存在冲突？** 这些关系必须显式存储，否则无法回指、无法判时效、无法发现矛盾。

在单机、离线、8 GB 内存的约束下，本项目的工程取舍是
**单一真相源（SQLite）+ 全部派生层可重建**：31 GB、470 万条文档、879 万条引用，
在无 GPU、无守护进程的笔记本上完成全量摄入与检索（详见 `工程论文-单机大规模文本知识库实现.md`）。

## 特性

- **流式摄入**：ZIP/CSV 不解压落盘；编码探测（UTF-8/GBK）；行级清洗；坏行入 `rejects`；
  成员级 checkpoint 支持续跑；确定性 ID 保证重跑幂等
- **双写入路径**：批量索引路径实测 **1,161 行/秒**，逐案建图路径 **4.1–9.9 行/秒**，
  按「吞吐 × 数据量」选型（见论文 4.4 节）
- **检索降级链**：FTS5 trigram（查询需 ≥3 字符）→ 标题表 LIKE → 全文 LIKE →
  向量 RRF 融合；后端不可用时降级，不伪造结果
- **确定性防护**：计划门三态（ALLOW / REVIEW / DENY）、会话污点传播、输出过滤，
  90 项测试约 2.2 秒回归
- **零外部服务**：无 Elasticsearch / Neo4j / 向量库；单进程批处理即可运行

## 数据策略（重要）

- 本仓库**不分发数据**。语料需自备合法来源，并自行确认授权与合规
  （批量文档可能含个人信息，受《个人信息保护法》约束）
- 示例与测试使用**合成数据**：`examples/sample_cases.csv`
- 数据文件默认被 `.gitignore` 排除（`*.db`、`*.zip`）
- 公开范围与检查清单见 `docs/PUBLIC_SCOPE.md`

## 快速开始

```bash
pip install -e ".[dev]"

# 初始化
python -m legalwiki.cli init --db demo.db

# 摄入：流式 ZIP（--limit 试跑，--dry-run 只统计）
python -m legalwiki.cli index-judgments --db demo.db --zip ./your-data.zip --limit 1000

# 派生表
python -m legalwiki.cli build-judgment-titles    --db demo.db
python -m legalwiki.cli build-judgment-citations --db demo.db

# 检索
python -m legalwiki.cli search --db demo.db --q "示例查询词"

# 回归
pytest -q          # 90 passed in ~2.2s
```

## 目录结构

```text
legalwiki/
  graph/store.py          # 节点/边/分块/证据写入
  graph/queries.py        # 检索、证据链、条文归属
  ingest/markdown.py      # Markdown → Law/Chapter/Article/Chunk
  ingest/judgments_zip.py # ZIP 流式摄入 + 清洗 + 去重 + 质量台账
  ingest/bulk_index.py    # 批量索引路径（文档表 + 后建 FTS）
  ingest/titles.py        # 标题派生表
  ingest/citations.py     # 引用派生表
  retrieval/              # embedder / vector_store / hybrid(RRF)
  guard/                  # plan_gate / criminal / session / case
  validity.py  time.py    # 时效与版本判定
  cli.py                  # 命令行入口
tests/                    # 90 项测试（合成数据）
schema.sql  schema_vector.sql
INGEST_PIPELINE.md  RETRIEVAL.md  GUARD.md  VALIDITY.md  ONTOLOGY.md
```

## 实测数据（案例研究，非本仓库附带数据）

| 指标 | 2013 语料 | 2014 语料 |
|---|---|---|
| 文档条数 | 933,174 | 4,704,775 |
| 全文/标题索引 | 933,174 / 933,174 | 4,704,775 / 4,704,775 |
| 引用条数 | 1,804,379 | 8,788,964 |
| 库体积 | 6.21 GiB | 31.35 GiB（全文 FTS 版约 89 GB） |
| 摄入吞吐 | 未知（无日志） | 1,161 行/秒 |
| 单元测试 | 90 passed / 2.2 s | 同左 |

## 已知限制

- 全文 FTS 与标题 FTS 是显式取舍：全文 trigram 索引体积约为标题版的 2.6 倍
- 批量索引路径的拒绝原因当前只计数、未落 `rejects` 表
- 向量层为原型（覆盖率低、无 ANN），仅用于验证接口
- 8 GB 内存下引用抽取峰值 3.3 GB，会触发换页（优化方向见论文 9.2）

## 边界与免责

- 本项目是**资料检索与证据整理工具**，不提供法律意见，不预测胜负/责任比例，不替代执业律师
- 高风险场景（刑事、人身安全、重大金额、跨境）应由人工处理
- 防护层是**确定性规则**，不是安全证明；公开部署前需人工复核与红队测试

## License

MIT
