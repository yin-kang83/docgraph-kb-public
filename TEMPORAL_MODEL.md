# 法律时间与承传模型 v0.1

> 原则：不覆盖旧法/旧判例；只追加版本，保留“当时有效”的状态。
> 目标：同一案件能回答“判决时适用哪版法”，同一规范能回答“现在是否有效”。

## 1 四个时间

```text
event_date       事实发生日
filing_date      立案/起诉日
judgment_date    裁判日
norm_effective   规范生效/失效日
```

不能用“今天”去判旧案。

## 2 规范状态

```text
not_yet_effective
in_force
amended
repealed
unknown
```

字段：

```text
effective_from
effective_to
status
version
enacting_body
amendment_of
```

## 3 新旧交接

```text
新法生效前的事实 → 旧法（法不溯及既往）
新法生效后的事实 → 新法
跨法期间 → 分别适用，必要时“从旧兼从轻”等特别规则
旧法被废止 → 旧案不因此无效，只标“适用旧法”
新法替代旧法 → SUPERSEDES，不删除旧法
修正 → AMENDS，保留旧版本
```

## 4 判例承传

```text
Case --CITES--> Norm        (as_of=判决时)
Case --FOLLOWS--> Case      (参照/遵循)
Case --DISTINGUISHES--> Case (区分)
Case --REFERS_TO--> Case    (一般引用)
GuidingCase 标记
```

注意：

```text
中国不是判例法国家；
指导性案例有参照效力，普通判例不是先例；
旧判例仍有解释/事实价值，但不能冒充现行法。
```

## 5 图字段

节点：

```text
effective_from / effective_to / status / version
```

边：

```text
as_of        这条引用/适用发生在哪一天
role         applied / referenced / distinguished
```

## 6 查询

```text
Q1 某案判决时适用哪些规范？
  Case -CITES(as_of=judgment_date)-> Norm
  过滤 norm.effective_from <= as_of < effective_to
Q2 某规范现在还有效吗？
  status=in_force 且 effective_to is null/未来
Q3 新旧法怎么接？
  Norm -SUPERSEDES-> Norm
Q4 旧判例还能用吗？
  标“适用旧法”，不标“现行法”
```

## 7 数据质量

```text
日期缺失 → REVIEW，不默认“今天”
规范版本缺失 → 不判有效/无效
旧案引用新法 → 时间冲突，标 error
新案引用已废止法 → 标 warning
```

## 8 一句话

```text
法律不是“最新版全文”，
是“每个版本在各自时间里有效”；
判例不是“旧答案”，
是“当时法下的答案”。
```
