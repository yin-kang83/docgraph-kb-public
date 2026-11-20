from legalwiki.guard.plan_gate import Decision, Plan, Step, review


def test_search_law_allowed():
    r = review(Plan("查租赁合同条文", [Step("检索民法典", ("search_law",))]))
    assert r.decision == Decision.ALLOW


def test_search_case_allowed():
    r = review(Plan("找类案", [Step("检索判例", ("search_case",))]))
    assert r.decision == Decision.ALLOW


def test_evidence_chain_allowed():
    r = review(Plan("整理合法证据链", [Step("列证据清单", ("build_evidence_chain",))]))
    assert r.decision == Decision.ALLOW


def test_destroy_records_denied():
    r = review(Plan("处理材料", [Step("删除记录", ("destroy_records",))]))
    assert r.decision == Decision.DENY
    assert "evidence_tampering" in r.effects


def test_coach_witness_denied():
    r = review(Plan("准备开庭", [Step("统一说法", ("coach_witness",))]))
    assert r.decision == Decision.DENY


def test_long_chain_terminal_prohibited_denies_whole_plan():
    plan = Plan("研究证据规则", [
        Step("检索条文", ("search_law",)),
        Step("整理材料", ("build_evidence_chain",)),
        Step("让证人改口", ("coach_witness",)),
    ])
    r = review(plan)
    assert r.decision == Decision.DENY


def test_explicit_marker_denied():
    r = review(Plan("写一篇关于销毁证据的责任", [Step("检索", ("search_law",))]))
    assert r.decision == Decision.DENY


def test_drafting_requires_review():
    r = review(Plan("起草文书", [Step("写起诉状", ("draft_document",))]))
    assert r.decision == Decision.REVIEW


def test_strategy_requires_review():
    r = review(Plan("分析案件", [Step("给诉讼策略", ("advise_strategy",))]))
    assert r.decision == Decision.REVIEW


def test_empty_plan_requires_review():
    assert review(Plan("", [])).decision == Decision.REVIEW


def test_opaque_plan_requires_review():
    assert review(Plan("看看这个", [Step("处理")])).decision == Decision.REVIEW


def test_unknown_capability_requires_review():
    assert review(Plan("做点事", [Step("未知操作", ("unknown_cap",))])).decision == Decision.REVIEW


def test_prohibited_effect_not_laundered_by_benign_steps():
    plan = Plan("合规咨询", [
        Step("查找法规", ("search_law",)),
        Step("设计交易结构规避监管", ("design_scheme",)),
    ])
    assert review(plan).decision == Decision.DENY
