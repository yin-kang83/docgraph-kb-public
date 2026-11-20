# 法学元知识层设计 v0.1

> 目标：给 legalwiki-kb 补“法学基本知识”，不是补全法条。
> 原则：官方来源、可回指、版本化；不靠 LLM 编定义。

## 1 现在缺什么

```text
已有：法律/判例文档、条款、claim、evidence
缺：
  概念：什么是“善意取得/表见代理/不当得利”
  效力：法律/行政法规/地方性法规/规章谁高
  时间：新法优于旧法、法不溯及既往、失效
  地域：大陆/香港/澳门/台湾；涉外
  推理：大前提-小前提-结论；IRAC
  引用：法条/判决/司法解释的规范格式
```

## 2 四层元知识

```text
L1 法源与效力
  宪法 > 法律 > 行政法规 > 地方性法规 > 规章
  特别法优于一般法
  新法优于旧法
  法不溯及既往（例外）
  上位法优于下位法（冲突时）

L2 概念/关系
  主体/客体/权利/义务/责任
  法律行为/合同/侵权/犯罪构成
  时效/管辖/举证责任/既判力

L3 推理模式
  大前提（规范）→ 小前提（事实）→ 结论
  IRAC：Issue/Rule/Application/Conclusion
  文义/体系/目的/历史解释
  举重以明轻/类推/反面解释（需标注）

L4 引用/证据
  法条引用格式
  判决引用链
  证据能力/证明力
  举证责任分配
```

## 3 最小种子（先做这些）

```text
50 个概念
20 条效力/冲突规则
10 个推理模式
10 个引用/证据规则
```

每个条目：

```yaml
id: concept.good_faith_acquisition
term: 善意取得
definition: ...
source: 《民法典》第311条
jurisdiction: CN
effective_date: 2021-01-01
relations:
  - {type: requires, target: concept.good_faith}
  - {type: part_of, target: concept.property_law}
```

## 4 来源政策

```text
只收官方文本：
  法律/行政法规/司法解释/指导性案例
不收：
  自媒体解读、培训机构讲义、LLM 生成定义
每条必须：
  source / article / jurisdiction / effective_date
无来源 → 不入库
```

## 5 目录

```text
legalwiki-kb/
  ontology/
    sources.yml          # 官方来源清单
    concepts.yml         # 50 概念
    validity_rules.yml   # 20 效力规则
    reasoning_patterns.yml
    citation_rules.yml
  legalwiki/
    ontology/
      loader.py
      validate.py
```

## 6 图中怎么用

```text
Concept 节点
  ← MENTIONS ← Article/Claim
  → REQUIRES/PART_OF → Concept
  → SOURCE → Norm

ValidityRule 节点
  → CONFLICTS_WITH / SUPERSEDES → Norm
```

新增边：

```text
MENTIONS       Clause/Claim → Concept
REQUIRES       Concept → Concept
PART_OF        Concept → Concept
GOVERNS        Norm → Concept
SUPERSEDES     Norm → Norm
INVALID_AFTER  Norm → Date
```

## 7 加载与校验

```text
loader：YAML → nodes/edges
validate：
  必填字段
  来源存在
  关系目标存在
  日期合法
  同一 id 不重复
不合法 → 整条拒绝，不静默
```

## 8 评估

```text
概念覆盖：50 个是否覆盖民刑行商基础
引用准确：每条 source/article 可回指
冲突规则：新旧法/特别法测试
推理模式：能否落到 claim 链
```

## 9 不要做

```text
不要先做全量法律本体
不要用 LLM 自动生成定义
不要把学理解释当规范
不要跨辖区混用
```

## 10 一句话

```text
判例是“事实”，法条是“规范”，
元知识是“怎么找法、怎么冲突、怎么推理”；
没有这一层，知识库只会搜段落，不会讲法。
```
