# 判例入库通道设计 v0.1：流式、可清洗、可恢复

> 目标：从年度 ZIP 直接流式读 CSV，清洗后入 SQLite；不落全量解压文件。
> 原则：原始行可追溯；清洗规则显式；坏行不静默丢；可重跑、可恢复。

## 1 通道

```text
年度 ZIP
  → 成员清单（CSV）
  → 流式读取（zipfile，不落盘）
  → 编码识别（utf-8-sig / gbk）
  → 表头校验/字段映射
  → 行级清洗
  → 校验（error/warn）
  → 去重
  → 批量写 SQLite（raw + clean + graph）
  → 质量报告
  → checkpoint
```

## 2 分层

```text
L0 raw_rows      原始行（JSON/原字段），可重放
L1 clean_cases   清洗后的判例
L2 graph         Case/Court/Norm/Chunk/Edge
L3 report        ingest_runs / rejects / dedup
```

L0 保留原始值，避免“清洗后无法回查”。

## 3 阶段与失败

| 阶段 | 输入 | 输出 | 失败处理 |
|---|---|---|---|
| 发现 | ZIP 路径 | 成员列表 | 跳过非 CSV，记录 |
| 解码 | bytes | text | utf-8-sig 失败→gbk→记录错误 |
| 表头 | 首行 | 字段映射 | 缺必需列→整文件 reject |
| 清洗 | row dict | clean dict | 字段级 error/warn |
| 校验 | clean dict | verdict | error 进 rejects，warn 保留 |
| 去重 | clean dict | key/hash | 重复进 dedup 表 |
| 写入 | batch | nodes/edges/chunks | 事务失败→整批回滚 |
| 报告 | 统计 | JSON/MD | 不阻塞 |

## 4 清洗规则

### 4.1 通用

```text
去 BOM
去首尾空白
全角空格→半角
去零宽字符/控制字符
统一换行
HTML 标签剥离（全文）
连续空白压缩（全文，保留段落边界）
```

### 4.2 字段

| 字段 | 规则 | 失败 |
|---|---|---|
| 案号 | 去空白；全角括号保留原样；生成 normalized | 空→warn |
| 案件名称 | 去空白；截断 200 | 空→warn |
| 法院 | 去空白；别名表归一（可选） | 空→warn |
| 所属地区 | 去空白 | 空→warn |
| 案件类型 | 映射表（民事/刑事/行政/执行） | 未知→warn |
| 审理程序 | 映射（一审/二审/再审/执行） | 未知→warn |
| 裁判日期 | 解析 YYYY-MM-DD / YYYY/M/D / 中文日期 | 非法→warn，raw 保留 |
| 公开日期 | 同上 | 非法→warn |
| 当事人 | 去空白；保留原文；PII 标记 | 空→warn |
| 案由 | 去空白；截断 100 | 空→warn |
| 法律依据 | 按 `；;` 切分；解析《法名》第X条 | 空→warn（不是 error） |
| 全文 | 去 HTML/控制符；长度统计 | <50 字→warn；空→error |

### 4.3 严重级别

```text
ERROR：缺案号且缺案件名称；全文空；编码不可解；表头缺列
WARN：日期非法；法院空；法律依据空；全文过短；当事人空
```

WARN 入图但标 `quality_flags`；ERROR 进 rejects，不入图。

## 5 去重

```text
主键：案号 + 法院 + 裁判日期（normalized）
全文 hash：sha256(clean_full_text)
重复策略：保留首条；后续进 dedup 表，reason=case_key/text_hash
跨年重复：同一 key 不重复入图
```

## 6 表

```sql
CREATE TABLE ingest_runs (
  id TEXT PRIMARY KEY, source TEXT, started_at TEXT, finished_at TEXT,
  rows_read INTEGER, rows_ok INTEGER, rows_reject INTEGER,
  duplicates INTEGER, chunks INTEGER, db_bytes INTEGER, status TEXT
);

CREATE TABLE raw_rows (
  id TEXT PRIMARY KEY, run_id TEXT, source_member TEXT, row_no INTEGER,
  raw_json TEXT, created_at TEXT
);

CREATE TABLE rejects (
  id TEXT PRIMARY KEY, run_id TEXT, source_member TEXT, row_no INTEGER,
  reason TEXT, detail TEXT, raw_json TEXT, created_at TEXT
);

CREATE TABLE dedup (
  id TEXT PRIMARY KEY, run_id TEXT, case_key TEXT, text_hash TEXT,
  kept_case_id TEXT, reason TEXT, created_at TEXT
);

CREATE TABLE quality_flags (
  case_id TEXT, flag TEXT, detail TEXT, PRIMARY KEY (case_id, flag)
);

CREATE TABLE checkpoints (
  source TEXT PRIMARY KEY, member TEXT, row_no INTEGER, updated_at TEXT
);
```

## 7 批量与恢复

```text
每 500 行一个事务；
每完成一个 CSV 成员写 checkpoint；
重跑从 checkpoint 之后开始；
ID 确定性：hash(案号|法院|日期|文本)；
重复写用 INSERT OR REPLACE，边去重。
```

## 8 质量报告

```text
runs/<run_id>.json
  source, members, rows_read/ok/reject/dup
  error 分类计数
  warn 分类计数
  chunks, db_bytes, duration
  sample_rejects[10]
```

## 9 隐私

```text
判例含姓名/地址/身份证号；
日志不打印全文；
rejects 保留原文但限制访问；
对外导出默认脱敏；
PII 标记写入 quality_flags。
```

## 10 CLI

```bash
# 单年 ZIP 流式入库
python -m legalwiki.cli ingest-judgments --db legal.db --zip ./data/2013.zip

# 只清洗不入库
python -m legalwiki.cli ingest-judgments --db legal.db --zip ... --dry-run

# 限量试跑
python -m legalwiki.cli ingest-judgments --db legal.db --zip ... --limit 1000
```

## 11 测试

```text
1 BOM/UTF-8
2 GBK 回退
3 缺列 → 文件 reject
4 全文空 → 行 reject
5 日期非法 → warn 保留
6 法律依据空 → warn
7 重复案号 → dedup
8 全文 hash 重复 → dedup
9 重跑幂等
10 HTML/控制符清洗
11 limit/dry-run
12 报告计数
```

## 12 验收

```text
2013 年 ZIP：
  rows_read / ok / reject / dup 有数
  DB 大小可接受
  重跑不重复
  质量报告可读
```

## 13 一句话

```text
先流式读、再分层洗、坏行留证、重复留痕、重跑幂等；
不要先解压 100GB，再人工擦数据。
```
