"""Deterministic plan gate for 法鉴.

No LLM. It reviews a proposed plan BEFORE any step runs:

  goal + steps + capabilities -> terminal effects -> allow/deny/review

Rules:
- if any step has a prohibited effect, deny the whole plan;
- if the terminal step has a prohibited effect, deny even if earlier steps are benign;
- if a step is gray/ambiguous, require review;
- an empty/opaque plan requires review, not allow.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REVIEW = "review"


PROHIBITED_EFFECTS = {
    "evidence_tampering": "伪造/变造/销毁证据",
    "witness_coaching": "教唆作伪证/串供/威胁证人",
    "tax_evasion": "逃税/虚开/骗取退税",
    "money_laundering": "洗钱",
    "sanctions_evasion": "规避制裁/监管申报",
    "privacy_abuse": "侵犯隐私/跟踪/人肉",
    "unauthorized_practice": "无资质执业/代签字/代出庭",
    "violence": "暴力/人身伤害",
    "fraud": "诈骗/虚假陈述",
    "case_evaluation": "对具体案件作胜负/责任/是非评判",
}

GRAY_EFFECTS = {
    "litigation_strategy": "诉讼策略/胜负判断",
    "evidence_selection": "证据取舍/证明力操作",
    "regulatory_planning": "监管套利/交易结构设计",
    "document_drafting": "代写法律文书",
}

# capability -> effects it can produce
BENIGN_CAPABILITIES = {
    "search_law", "search_case", "summarize_public_text",
    "extract_citations", "build_evidence_chain",
}

CAPABILITY_EFFECTS = {
    "search_law": set(),
    "search_case": set(),
    "summarize_public_text": set(),
    "extract_citations": set(),
    "build_evidence_chain": set(),
    "draft_document": {"document_drafting"},
    "advise_strategy": {"litigation_strategy"},
    "evaluate_case": {"case_evaluation"},
    "destroy_records": {"evidence_tampering"},
    "coach_witness": {"witness_coaching"},
    "design_scheme": {"regulatory_planning"},
    "contact_third_party": {"unauthorized_practice"},
}


@dataclass
class Step:
    action: str
    capabilities: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    detail: str = ""


@dataclass
class Plan:
    goal: str
    steps: list[Step] = field(default_factory=list)
    context: str = ""


@dataclass
class Result:
    decision: Decision
    reasons: list[str]
    effects: list[str]
    safe_alternative: str = ""


REFUSAL = (
    "这属于我不能协助的范围。我可以帮你找相关条文/判例、"
    "整理合法证据链、列合规材料清单，或提示需要律师复核的点。"
)


def _text(plan: Plan) -> str:
    return " ".join([plan.goal, plan.context] + [s.action + " " + s.detail for s in plan.steps])


def review(plan: Plan) -> Result:
    reasons: list[str] = []
    effects: set[str] = set()

    if not plan.goal.strip() or not plan.steps:
        return Result(Decision.REVIEW, ["计划为空或目标不清，要求补充/人工复核"], [], REFUSAL)

    text = _text(plan)
    # explicit operational markers: keep this short and conservative
    explicit = {
        "销毁证据": "evidence_tampering",
        "伪造证据": "evidence_tampering",
        "串供": "witness_coaching",
        "作伪证": "witness_coaching",
        "逃税": "tax_evasion",
        "虚开": "tax_evasion",
        "洗钱": "money_laundering",
        "规避监管": "sanctions_evasion",
        "人肉": "privacy_abuse",
        "代签字": "unauthorized_practice",
    }
    for kw, eff in explicit.items():
        if kw in text:
            effects.add(eff)
            reasons.append(f"命中禁止效果：{PROHIBITED_EFFECTS[eff]}")

    for step in plan.steps:
        for cap in step.capabilities:
            for eff in CAPABILITY_EFFECTS.get(cap, set()):
                effects.add(eff)
        effects.update(step.effects)

    prohibited = sorted(e for e in effects if e in PROHIBITED_EFFECTS)
    gray = sorted(e for e in effects if e in GRAY_EFFECTS)

    if prohibited:
        reasons.extend(f"终态/步骤含禁止效果：{PROHIBITED_EFFECTS[e]}" for e in prohibited)
        return Result(Decision.DENY, _dedupe(reasons), prohibited, REFUSAL)

    if gray:
        reasons.extend(f"需要人工复核的效果：{GRAY_EFFECTS[e]}" for e in gray)
        return Result(Decision.REVIEW, _dedupe(reasons), gray, REFUSAL)

    caps = {c for s in plan.steps for c in s.capabilities}
    if caps and caps <= BENIGN_CAPABILITIES and not effects:
        return Result(Decision.ALLOW, ["仅检索/整理公开资料，无可识别禁止效果"], [], "")

    if not effects:
        reasons.append("未识别到明确效果，保守转人工复核")
        return Result(Decision.REVIEW, reasons, [], REFUSAL)

    return Result(Decision.ALLOW, ["仅检索/整理公开资料，无可识别禁止效果"], [], "")


def _dedupe(xs: list[str]) -> list[str]:
    out, seen = [], set()
    for x in xs:
        if x not in seen:
            seen.add(x); out.append(x)
    return out
