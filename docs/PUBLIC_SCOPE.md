# 公开范围（Public Scope）

本文件说明：哪些内容可以进公开仓库，哪些永远不进。

## 公开（public）

```text
源码：legalwiki/、demo_vector.py
测试：tests/（全部使用合成数据）
schema：schema.sql、schema_vector.sql
文档：README、INGEST_PIPELINE、RETRIEVAL、GUARD、VALIDITY、TEMPORAL_MODEL、
      ONTOLOGY、VECTOR、BOUNDARY、POSITIONING
论文：工程论文（技术实现）
样例：examples/（合成数据，不含真实案件）
依赖与工程：pyproject.toml、LICENSE、.gitignore
```

## 不进公开仓库

```text
数据：判例/法条数据库（GB 级）、原始 ZIP、CSV 全量
隐私：raw_rows、rejects（含当事人姓名/地址等个人信息）
密钥：Qwen key、Gitee 令牌、.env / *.key / *.pem
内部：DECISION-*.md、RISK_CONTROLS.md（内部决策与风险口径，律师复核后再定）
运行产物：*.log、临时库、预览图片
```

## 公开前检查清单

```text
1 LICENSE 存在且与 pyproject 一致
2 无 *.db / *.zip / *.csv（真实数据）入库
3 无密钥、无本机绝对路径
4 tests 全绿（pytest -q）
5 git log -p 抽查历史提交无敏感内容
6 README 边界声明存在（不提供法律意见、不替代律师、数据自备）
7 律师书面复核（对外定位与拒答模板）
```
