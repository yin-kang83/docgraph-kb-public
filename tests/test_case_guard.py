from legalwiki.guard import filter_case_output
from legalwiki.guard.plan_gate import Decision, Plan, Step, review


def test_win_prediction_blocked():
    out, blocked = filter_case_output("我认为被告肯定赢，胜诉率很高。")
    assert blocked and "不能判断" in out


def test_liability_share_blocked():
    out, blocked = filter_case_output("责任几成在对方，七成。")
    assert blocked


def test_law_text_passes():
    text = "民法典第五百七十七条规定，当事人一方不履行合同义务的，应当承担违约责任。"
    out, blocked = filter_case_output(text)
    assert not blocked and out == text


def test_evidence_checklist_passes():
    text = "证据目录：合同、付款凭证、催告函、聊天记录。"
    out, blocked = filter_case_output(text)
    assert not blocked


def test_plan_evaluate_case_denied():
    r = review(Plan("评估这个案子", [Step("判断谁有理", ("evaluate_case",))]))
    assert r.decision == Decision.DENY
    assert "case_evaluation" in r.effects


def test_judgment_commentary_blocked():
    out, blocked = filter_case_output("这个判例判错了，法官偏袒。")
    assert blocked


def test_no_evaluation_of_court():
    out, blocked = filter_case_output("该判决不公，应当改判。")
    assert blocked
