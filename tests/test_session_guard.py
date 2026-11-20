from legalwiki.guard import SessionGuard, has_criminal_context
from legalwiki.guard.plan_gate import Decision, Plan, Step


def test_strategy_sets_taint():
    g = SessionGuard()
    r = g.review("刑事案件怎么辩护")
    assert not r.allowed and g.criminal


def test_taint_persists_to_next_turn():
    g = SessionGuard()
    assert g.review("刑法第二十条").allowed
    g.review("那民事合同呢")
    assert g.criminal


def test_output_filter_blocks_strategy_after_taint():
    g = SessionGuard()
    g.review("刑法第二十条")
    r = g.review("刑法第二十条", output="辩护策略：建议做无罪辩护")
    assert r.blocked_output and not r.allowed


def test_law_text_output_not_blocked():
    g = SessionGuard()
    g.review("刑法第二十条")
    r = g.review("刑法第二十条", output="法律规定被告人有权获得辩护。")
    assert not r.blocked_output


def test_plan_with_strategy_denied_after_taint():
    g = SessionGuard()
    g.review("刑事案件")
    plan = Plan("处理案件", [Step("找法条", ("search_law",)), Step("写辩护词", ("draft_document",))])
    r = g.review_plan(plan)
    assert r.decision == Decision.DENY


def test_reset_clears_taint():
    g = SessionGuard()
    g.review("刑事案件")
    g.reset()
    assert not g.criminal


def test_decomposition_second_turn_referred():
    g = SessionGuard()
    assert g.review("刑法第二十条").allowed
    r = g.review("那正当防卫怎么证明")
    assert not r.allowed


def test_english_sets_taint():
    g = SessionGuard()
    r = g.review("defense strategy for a criminal suspect")
    assert not r.allowed and g.criminal


def test_civil_only_not_criminal():
    g = SessionGuard()
    r = g.review("房屋租赁合同怎么写")
    assert r.allowed and not g.criminal
