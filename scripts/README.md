# 复现脚本

这些脚本用于验证与成本实测，**全部只读源库**，不修改任何数据。

| 脚本 | 作用 | 示例 |
|---|---|---|
| `verify_db.py` | 行数一致性、FTS 行为、抽样完整性、可选 `quick_check` | `python scripts/verify_db.py --db legal.db` |
| `measure_latency.py` | FTS 查询延迟实测 | `python scripts/measure_latency.py --db legal.db --query 合同纠纷` |
| `measure_fts_build.py` | 全文 FTS 构建成本（抽样到临时库，输出外推） | `python scripts/measure_fts_build.py --db legal.db --limit 50000` |

## 口径提醒

- FTS5 `trigram` 查询必须 **≥3 个字符**，2 字词恒返回 0（设计限制，不是 bug）
- `verify_db.py --quick-check` 会全库扫描，几十 GB 的库需要十几分钟
- 实测数字与论文 `docs/工程论文-单机大规模文本知识库实现.md` 的口径一致
