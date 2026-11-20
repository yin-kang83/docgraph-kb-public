# 判例检索现状（2026-11-12 更新）

## 数据

```text
2013 全量：933,174 条     DB 约 6.2 GiB（标题 FTS）/ 16.1 GiB（全文 FTS）
2014 全量：4,704,775 条   DB 31.4 GiB（标题 FTS）/ 约 89 GiB（全文 FTS，构建中）
字段：案号/标题/法院/地区/类型/程序/日期/案由/法律依据/全文
```

## FTS 两种模式

```text
CLI：python -m legalwiki.cli build-judgment-fts --db <db> [--full-text]

默认（标题-only）
  体积小、建得快；正文检索降级 title/full_text LIKE
  470 万条实测约 7 分钟量级

--full-text（标题+全文）
  正文可直接 trigram 检索
  2014 语料实测：470 万条，约 2–3 小时，库体积 31.4 → 约 89 GiB
  （单条平均 +约 11 KiB，与 2013 全文版的 18.5 KiB/条一致）
```

## 关键工程结论（2026-11-12 实测）

```text
1 trigram 查询必须 ≥3 字符；2 字词恒返回 0（设计限制，不是 bug）
2 早期"93 万条全文建索引 1 小时不落盘"的主因是 SQLite 默认 cache_size=2MB
  导致 b-tree 插入反复换页（实测读放大 ~40 倍）
3 修正后：128–256 MB page cache + temp_store=MEMORY + 每 10 万行 commit
  可稳定落盘
4 4.7M 条实测吞吐约 350–600 行/秒（随索引增长而下降）
```

## 检索降级链

```text
FTS MATCH（≥3 字）
  → 无命中/短查询：judgment_titles 表 LIKE（窄表，约 800 MB）
  → 仍无命中：judgments.full_text LIKE（最后手段）
  → 向量可用：与 FTS 结果 RRF 融合；不可用则纯 FTS，不伪造结果
```

## 向量

```text
judgment_embeddings：judgment_id/model/dim/vector BLOB
只嵌标题 + 前 1000 字；fake 5000 条已跑通；qwen 未真调（需 key/成本审批）
```

## 边界

```text
FTS 是召回层，不是法律结论；
所有结果必须回指原文；
时效/辖区仍靠 validity_rules 和人工复核。
```
