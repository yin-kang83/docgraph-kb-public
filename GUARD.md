# 边界门（plan gate）

`legalwiki/guard/plan_gate.py` 是确定性规则门，不调 LLM。

## 规则

```text
1 计划为空/目标不清 → REVIEW
2 任一步骤含禁止效果 → DENY 整条计划
3 终态禁止 → 前面的合法步骤也不放行
4 灰区（文书/策略/证据取舍）→ REVIEW
5 纯检索/引用链 → ALLOW
6 无法识别效果 → REVIEW，不默认放行
```

## 用法

```python
from legalwiki.guard import Plan, Step, review

r = review(Plan("查租赁合同条文", [Step("检索", ("search_law",))]))
print(r.decision)  # allow
```

## 边界

```text
这不是完整 agent 安全层；
它只做“执行前计划审查”。
还需要：
  taint 传播
  会话累计风险
  人工复核队列
  输出过滤
```

## 测试

```text
tests/test_plan_gate.py  13 tests
全仓 49 passed
```


## 刑案绕过防护（criminal.py）

```text
1 normalize：NFKC、小写、去空格/标点
2 刑事语境：刑事/犯罪/拘留/逮捕/被告人/证人/量刑/英文 criminal 等
3 策略/量刑/证据：一律 REFER，不输出
4 法条例外：第…条/法条/司法解释 → 允许，仅给条文
5 模糊刑案：保守转介，不默认允许
6 输出模板：必须建议执业律师/法援
```

已覆盖绕过样例：

```text
假设朋友被抓
写小说角色脱罪
英文 defense strategy
整理案卷证据
法条+想脱罪
取保/认罪认罚/辩护词/量刑情节
```

边界：

```text
关键词门不是证明；
同义改写/多轮/工具链仍可能绕过；
公开前仍需 LLM 意图门 + 计划门 + 人审。
```


## 会话级防线（session.py）

```text
1 一旦出现刑案语境，session 标记 taint
2 后续非刑事问题也按刑案处理（防“先问法条，再问策略”）
3 只有显式法条/程序查询可过
4 输出生成后再过滤策略/量刑语言
5 计划门：刑案会话中出现“辩护词/策略” → 整条拒绝
```

测试：

```text
tests/test_session_guard.py
83 passed
```
