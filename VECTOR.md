# VECTOR —— 判例向量输入 / hybrid 检索原型（task-84）

> 状态：**原型**，先 5000 条；不重建/不碰 2013 全量索引（后台任务在跑）。
> 测试只用 `fake` embedder；不联网、不真调 Qwen。

## 1. 边界

- 只对 **标题 + 前 1000 字** 做向量（`text_for_judgment`），不是全文；
- 默认 `--limit 5000`，不写全量 2013；全量策略、成本、模型选型后议；
- 不在 E: 原库上直接跑迁移/embedding；用 staging 或复制库验证。

## 2. 表结构

```sql
judgment_embeddings(
  judgment_id TEXT NOT NULL,
  model TEXT NOT NULL,
  dim INTEGER NOT NULL,
  vector BLOB NOT NULL,        -- float32 little-endian
  created_at TEXT NOT NULL,
  PRIMARY KEY (judgment_id, model)
);
embedding_runs(
  id TEXT PRIMARY KEY, model TEXT, dim INTEGER, backend TEXT,
  rows_embedded INTEGER, started_at TEXT, finished_at TEXT, status TEXT, detail TEXT
);
```

- `schema.sql` 已追加两表；已有库可执行 `schema_vector.sql`；
- 同一判例可存多个模型向量（(judgment_id, model) 主键）。

## 3. 后端（可插拔）

| backend | 说明 | 测试 |
|---|---|---|
| `fake` | 确定性 blake2b 哈希向量，dim 可配；仅测试/离线 demo | ✅ 使用 |
| `qwen` | DashScope `text-embedding-v3`（OpenAI 兼容 `/embeddings`）；env `QWEN_KEY`，无 key 立即失败 | 接口单测，不真调 |
| `local` | `sentence-transformers` 可选；未安装抛 `EmbedderUnavailable` | 未安装路径 |

```python
from legalwiki.retrieval.embedder import make_embedder
emb = make_embedder("fake", dim=64)
# emb = make_embedder("qwen", model="text-embedding-v3")
```

## 4. Hybrid 检索

- FTS：复用 `judgments_fts`（trigram）；短查询/不支持时降级 `LIKE`；
- 向量：numpy 余弦 top-k（归一化后点积）；
- 融合：`rrf_fuse`（默认 k=60，可配 weights）或 `weighted_fuse`；
- 缺向量/空库自动降级为 FTS，不伪造结果；向量后端异常时 hybrid 降级 FTS。

## 5. CLI

```bash
# 只嵌入 5000 条（幂等：只补缺该 model 向量的判例）
python -m legalwiki.cli embed-judgments --db legal.db --limit 5000 --backend fake --dim 64

# 混合检索
python -m legalwiki.cli search-hybrid --db legal.db --q "房屋租赁合同" --limit 10 --backend fake
```

Qwen 真实运行（不在测试中执行；需 key/费用审批）：

```bash
python -m legalwiki.cli embed-judgments --db <copy.db> --limit 5000 --backend qwen --model text-embedding-v3
```

## 6. Demo

```bash
python demo_vector.py
```

使用临时 SQLite + 5 条合成判例 + fake embedder，输出 embedding stats 与 hybrid hits；
不访问全量库。

## 7. 风险

- Qwen embedding 需要 `QWEN_KEY`；真实调用有 token 费用、限流、维度/模型版本漂移风险；
  5000 条成本/配额需先按当前定价核算，不能沿用本原型的假设；
- 只嵌入标题+前 1000 字，长判决尾部信息会丢失；是否增大窗口需评估召回/成本；
- numpy 全量加载向量；5000×1024 float32 约 20MB，可接受；全量百万级需 ANN/分片；
- FTS trigram 对短中文查询可能降级 LIKE，性能需在全量库另测；
- 向量相似不等于法律相关，hybrid 仍需排序/评估集；
- 本原型未改 2013 索引、未 commit。
