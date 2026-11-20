# 国内开源资料包（PACKAGE）

> 用途：Gitee 首发（国内），同提交镜像 GitHub（国际）。
> 来源：`legalwiki-kb` 仓库 `opensource` 分支，剔除内部文件后导出。
> 生成：2026-11-12

## 1. 内容

```text
opensource-package/
├── README.md  LICENSE(MIT)  CONTRIBUTING.md  CHANGELOG.md  SECURITY.md  MIRROR.md
├── pyproject.toml  .gitignore  schema.sql  schema_vector.sql
├── legalwiki/         引擎源码（41 个 .py）
├── tests/             93 项测试（合成数据，约 2–3 秒）
├── ontology/          概念/效力/来源 YAML（4 个）
├── examples/          合成样例 sample_cases.csv
├── results/           2013 标题检索验收（只含查询与命中，无隐私）
├── docs/              论文（md/docx）、EXPERIMENTS、PUBLIC_SCOPE、8 份设计文档
└── scripts/           verify_db / measure_latency / measure_fts_build + README
```

## 2. 统计

| 项 | 值 |
|---|---|
| 文件数 | 74 |
| 体积 | 0.28 MB |
| 源码 | 约 2,500 行 Python |
| 文档 | 14 份 Markdown（论文约 3.4 万字） |
| 测试 | 93 项（2.7 秒） |

## 3. 已剔除（不进公开包）

| 文件 | 原因 |
|---|---|
| `DECISION-20261109.md` | 内部决策（发布门槛/律师复核） |
| `RISK_CONTROLS.md` | 内部风险口径与外部参考整理 |
| `POSITIONING.md` | 产品命名/商标待查、对外口径未定 |
| `results/qwen_review_validity.md` | 模型评审笔记，需人工复核 |
| `scripts-sync-mirrors.ps1` | 含本机路径与令牌用法；由 `MIRROR.md` 说明替代 |
| 全部 `.db` / `.zip` / `*.log` / 密钥 | 数据、PII、凭证 |

## 4. 发布前检查

```text
[x] 无数据库/压缩包/日志/密钥
[x] 无本机绝对路径（盘符路径 / 用户目录）
[x] pytest -q 全绿（93 passed）
[x] LICENSE / README 边界声明 / MIRROR 存在
[ ] 双平台推送后提交哈希一致（待 GitHub 地址 + PAT）
```

## 5. 发布方式（需负责人定）

- **方案 A（推荐）**：Gitee 新建公开仓 `docgraph-kb`，用本包做首次提交（历史干净）
- **方案 B**：现有私有仓转 public —— 缺点：历史提交含已剔除的内部文件，需先清理历史
- 两方案都要求：同一次提交推 GitHub、哈希一致、打 `v0.1.0` tag

## 6. 待决项

| # | 事项 | 需要谁定 |
|---|---|---|
| 1 | 选方案 A（新建公开仓）还是 B（转 public + 清历史） | 负责人 |
| 2 | 内部决策文档是否脱敏后公开 | 负责人 + 律师 |
| 3 | 论文是否投稿期刊（影响"预先公开"判断） | 负责人 |
| 4 | GitHub 仓地址与 PAT | 负责人 |
