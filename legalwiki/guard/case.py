"""Block case-merits evaluation in outward answers.

Allowed: law text, procedure, evidence checklist, timeline, risk list.
Blocked: who is right, who wins, liability share, how the judge will rule.
"""
from __future__ import annotations

import re

from .criminal import normalize

CASE_EVAL = (
    "谁有理", "谁对谁错", "谁的责任", "责任几成", "责任比例",
    "能不能赢", "会不会输", "胜诉", "败诉", "胜诉率", "败诉率",
    "法官会", "法院会", "判决会", "应该判", "肯定赢", "肯定输",
    "明显违法", "肯定违法", "必然败诉", "必然胜诉",
    "判错了", "判决不公", "法官偏袒", "枉法裁判", "应当改判",
    "这个判例不对", "裁判错误", "判决有问题",
)

SAFE_CASE = (
    "这属于对具体案件的评判，我不能判断谁有理、能否胜诉或责任比例。"
    "我可以帮你整理法条、程序、证据目录和时间线，供你和律师复核。"
)


def filter_case_output(text: str) -> tuple[str, bool]:
    s = normalize(text)
    blocked = any(k in s for k in CASE_EVAL)
    return (SAFE_CASE if blocked else text, blocked)
