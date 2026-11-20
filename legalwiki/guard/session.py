"""Session-level criminal taint + output filter + plan review.

Once a session touches a criminal question, later turns inherit the taint.
This closes the "ask law first, ask strategy later" decomposition gap.
"""
from __future__ import annotations

from dataclasses import dataclass

from .criminal import (
    CriminalMode,
    SAFE_REFERRAL,
    filter_output,
    has_criminal_context,
    is_law_lookup,
    review_criminal,
)
from .plan_gate import Decision, Plan, review as review_plan


@dataclass
class TurnResult:
    allowed: bool
    mode: CriminalMode
    reason: str
    output: str | None
    blocked_output: bool = False


class SessionGuard:
    def __init__(self) -> None:
        self.criminal = False

    def reset(self) -> None:
        self.criminal = False

    def review(self, text: str, output: str | None = None) -> TurnResult:
        if has_criminal_context(text):
            self.criminal = True
        r = review_criminal(text)
        if r.mode == CriminalMode.REFER:
            self.criminal = True

        # tainted session: only explicit law lookup or procedure may pass;
        # non-criminal questions are treated as continuation of the criminal thread.
        if self.criminal and r.allowed and r.reason == "非刑事语境" and not is_law_lookup(text):
            return TurnResult(False, CriminalMode.REFER,
                              "会话已进入刑案语境，后续问题按刑案处理",
                              SAFE_REFERRAL)

        if output is not None and self.criminal:
            safe, blocked = filter_output(output)
            if blocked:
                return TurnResult(False, CriminalMode.REFER,
                                  "刑案输出含策略/量刑语言，已拦截",
                                  SAFE_REFERRAL, True)
            return TurnResult(r.allowed, r.mode, r.reason, safe)

        return TurnResult(r.allowed, r.mode, r.reason, output)

    def review_plan(self, plan: Plan):
        text = " ".join([plan.goal] + [s.action + " " + s.detail for s in plan.steps])
        if self.criminal or has_criminal_context(text):
            self.criminal = True
            base = review_plan(plan)
            # any strategy marker in a tainted plan -> deny the whole plan
            from .criminal import contains_strategy
            if contains_strategy(text):
                from .plan_gate import Result
                return Result(Decision.DENY, ["刑案会话中出现策略/量刑意图"], [], SAFE_REFERRAL)
            return base
        return review_plan(plan)
