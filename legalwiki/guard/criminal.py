"""Criminal-case guard: law lookup only, never strategy/analysis.

Defense in depth:
- normalize text (NFKC, lowercase, strip spaces/punctuation)
- criminal context detection
- explicit strategy/analysis blocks (not just exact keywords)
- law lookup allowed only when no strategy/analysis
- ambiguous criminal questions refer, never allow
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum


class CriminalMode(str, Enum):
    LAW_ONLY = "law_only"
    REFER = "refer"


CRIMINAL = (
    "刑事", "犯罪", "嫌疑人", "被告人", "罪犯", "罪名", "刑法", "刑诉",
    "拘留", "逮捕", "看守所", "取保", "判刑", "量刑", "辩护", "公诉",
    "自诉", "缓刑", "减刑", "假释", "证人", "口供", "认罪认罚", "被抓",
    "判几年", "罪", "刑事案件", "刑案",
    "criminal", "defense", "defence", "defendant", "suspect", "prosecution", "prison",
)

STRATEGY = (
    "辩护策略", "怎么辩护", "如何辩护", "帮我辩护", "无罪辩护", "罪轻辩护",
    "辩护思路", "辩护方案", "怎么脱罪", "如何脱罪", "脱罪", "逃避",
    "串供", "让证人", "改口", "翻供", "伪证", "作伪证",
    "量刑", "判几年", "能不能缓刑", "争取缓刑", "取保", "不起诉",
    "怎么打", "如何打", "怎么应对", "如何应对", "怎么谈", "认罪认罚",
    "从轻", "减轻", "免予", "无罪", "罪轻", "辩护意见", "辩护词",
    "defense", "defence", "strategy", "sentence", "bail", "acquit", "plea",
)

ANALYSIS = (
    "证据", "证明力", "质证", "庭审", "案卷", "阅卷", "会见", "口供",
    "证人", "笔录", "鉴定", "伤情", "现场", "侦查", "讯问",
    "evidence", "witness", "cross-examination",
)

PROCEDURE = ("程序", "流程", "期限", "上诉", "立案", "管辖", "法律援助", "律师",
             "procedure", "appeal", "legal aid", "lawyer")


@dataclass
class CriminalResult:
    mode: CriminalMode
    allowed: bool
    reason: str
    template: str


def normalize(text: str) -> str:
    s = unicodedata.normalize("NFKC", str(text or "")).lower()
    s = re.sub(r"[\s，。！？、；：\"'“”‘’（）()《》【】\[\]…—\-_/]+", "", s)
    return s


def _article_lookup(s: str) -> bool:
    return bool(re.search(r"第[一二三四五六七八九十百千0-9]+条", s)) or "法条" in s or "司法解释" in s


def contains_strategy(text: str) -> bool:
    return any(k in normalize(text) for k in STRATEGY)


def review_criminal(text: str) -> CriminalResult:
    s = normalize(text)
    if not any(k in s for k in CRIMINAL):
        return CriminalResult(CriminalMode.LAW_ONLY, True, "非刑事语境", "")

    # 1 explicit strategy / sentencing / evidence coaching: always deny
    if any(k in s for k in STRATEGY):
        return CriminalResult(
            CriminalMode.REFER, False,
            "刑事案件不提供策略/量刑/证据分析",
            "刑事案件不建议自行处理，也不建议依赖 AI 判断。"
            "请立即咨询执业律师；符合条件的可申请法律援助。"
            "我可以帮你找相关法条和程序信息，但不提供辩护策略或案件结论。",
        )

    # 2 explicit article/law lookup: allow (even if it mentions evidence)
    if _article_lookup(s):
        return CriminalResult(
            CriminalMode.LAW_ONLY, True, "仅法条信息",
            "以上仅为法条信息，不构成辩护意见；请咨询执业律师。",
        )

    # 3 evidence/analysis: refer, do not analyze
    if any(k in s for k in ANALYSIS):
        return CriminalResult(
            CriminalMode.REFER, False, "刑事案件不分析证据/庭审",
            "刑事案件请咨询执业律师；我可以帮你找法条和程序信息，"
            "但不分析证据或庭审策略。",
        )

    # 4 procedure / legal aid: allow with referral
    if any(k in s for k in PROCEDURE):
        return CriminalResult(
            CriminalMode.LAW_ONLY, True, "仅程序/法援信息",
            "以上仅为程序信息，不构成辩护意见；请咨询执业律师。",
        )

    # 5 ambiguous criminal question: refer, never allow
    return CriminalResult(
        CriminalMode.REFER, False, "刑事问题不明确，保守转介",
        "刑事案件请先咨询执业律师；我可以帮你找法条和程序信息。",
    )


SAFE_REFERRAL = (
    "刑事案件不建议自行处理，也不建议依赖 AI 判断。"
    "请立即咨询执业律师；符合条件的可申请法律援助。"
    "我可以帮你找相关法条和程序信息，但不提供辩护策略或案件结论。"
)


def has_criminal_context(text: str) -> bool:
    s = normalize(text)
    return any(k in s for k in CRIMINAL)


def filter_output(text: str) -> tuple[str, bool]:
    """Return (safe_text, blocked). Blocks strategy/sentencing language only."""
    s = normalize(text)
    blocked = any(k in s for k in STRATEGY)
    return (SAFE_REFERRAL if blocked else text, blocked)


def is_law_lookup(text: str) -> bool:
    return _article_lookup(normalize(text))
