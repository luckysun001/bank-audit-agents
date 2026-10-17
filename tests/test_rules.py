"""
审计规则引擎测试
"""

import pytest

from bank_audit_agents.tools.rules import (
    DEFAULT_RULES,
    AuditRule,
    RuleCategory,
    RuleEngine,
    RuleSeverity,
    audit_rule_check,
    build_default_engine,
    rule_library_lookup,
)


def _credit_rule(**overrides):
    base = dict(
        rule_id="TEST-001",
        name="测试不良率",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        metric="npl_ratio",
        operator="lte",
        threshold=5.0,
        unit="%",
        recommendation="压降不良",
    )
    base.update(overrides)
    return AuditRule(**base)


# ---------------- 单条规则判定 ----------------


def test_rule_triggered_when_upper_bound_exceeded():
    rule = _credit_rule(operator="lte", threshold=5.0)
    finding = rule.evaluate({"npl_ratio": 6.2})
    assert finding is not None
    assert finding.actual == pytest.approx(6.2)
    assert finding.severity == "high"


def test_rule_passes_when_within_bound():
    rule = _credit_rule(operator="lte", threshold=5.0)
    assert rule.evaluate({"npl_ratio": 4.9}) is None


def test_rule_lower_bound_semantics():
    rule = _credit_rule(metric="lcr", operator="gte", threshold=100.0)
    assert rule.evaluate({"lcr": 80.0}) is not None
    assert rule.evaluate({"lcr": 120.0}) is None


def test_rule_missing_metric_is_skipped_not_reported():
    rule = _credit_rule()
    assert rule.evaluate({}) is None
    assert rule.evaluate({"npl_ratio": None}) is None


def test_rule_ignores_non_numeric_value():
    rule = _credit_rule()
    assert rule.evaluate({"npl_ratio": "无法获取"}) is None


def test_rule_rejects_invalid_operator():
    with pytest.raises(ValueError, match="运算符非法"):
        _credit_rule(operator="approximately")


@pytest.mark.parametrize(
    "operator,actual,expected_violation",
    [
        ("lte", 5.1, True),
        ("lte", 5.0, False),
        ("lt", 5.0, True),
        ("gte", 99.0, True),
        ("gte", 100.0, False),
        ("gt", 100.0, True),
        ("eq", 1.0, False),
        ("eq", 2.0, True),
        ("ne", 2.0, False),
        ("ne", 1.0, True),
    ],
)
def test_operator_semantics(operator, actual, expected_violation):
    rule = _credit_rule(operator=operator, threshold=5.0 if operator.startswith("l") else 100.0)
    if operator in ("eq", "ne"):
        rule = _credit_rule(operator=operator, threshold=1.0)
    result = rule.evaluate({"npl_ratio": actual})
    assert (result is not None) is expected_violation


# ---------------- 引擎 ----------------


def test_engine_evaluates_all_rules_and_reports_violations():
    engine = RuleEngine([_credit_rule()])
    findings = engine.evaluate({"npl_ratio": 8.0})
    assert len(findings) == 1
    assert findings[0].rule_id == "TEST-001"


def test_engine_sorts_by_severity_desc():
    engine = RuleEngine(
        [
            _credit_rule(rule_id="LOW", severity=RuleSeverity.LOW, metric="a", threshold=1.0),
            _credit_rule(rule_id="CRIT", severity=RuleSeverity.CRITICAL, metric="b", threshold=1.0),
        ]
    )
    findings = engine.evaluate({"a": 9.0, "b": 9.0})
    assert [f.severity for f in findings] == ["critical", "low"]


def test_engine_filters_by_category():
    engine = RuleEngine(
        [
            _credit_rule(rule_id="C1", metric="a", threshold=1.0),
            _credit_rule(
                rule_id="L1",
                category=RuleCategory.LIQUIDITY,
                metric="b",
                threshold=1.0,
            ),
        ]
    )
    findings = engine.evaluate({"a": 9.0, "b": 9.0}, categories=[RuleCategory.LIQUIDITY])
    assert [f.rule_id for f in findings] == ["L1"]


def test_engine_filters_by_min_severity():
    engine = RuleEngine(
        [
            _credit_rule(rule_id="LOW", severity=RuleSeverity.LOW, metric="a", threshold=1.0),
            _credit_rule(rule_id="HIGH", severity=RuleSeverity.HIGH, metric="b", threshold=1.0),
        ]
    )
    findings = engine.evaluate({"a": 9.0, "b": 9.0}, min_severity=RuleSeverity.HIGH)
    assert [f.rule_id for f in findings] == ["HIGH"]


def test_engine_missing_metrics_reported():
    engine = RuleEngine([_credit_rule(metric="npl_ratio"), _credit_rule(rule_id="T2", metric="lcr")])
    missing = engine.missing_metrics({"npl_ratio": 3.0})
    assert missing == ["lcr"]


def test_engine_evaluate_report_structure():
    engine = RuleEngine([_credit_rule()])
    report = engine.evaluate_report({"npl_ratio": 7.0})
    assert report["evaluated_rules"] == 1
    assert report["violations"] == 1
    assert report["by_severity"]["high"] == 1
    assert report["by_category"]["credit"] == 1
    assert report["missing_metrics"] == []
    assert report["findings"][0]["rule_id"] == "TEST-001"


def test_engine_override_threshold():
    engine = RuleEngine([_credit_rule(threshold=5.0)])
    assert engine.override_threshold("TEST-001", 8.0) is True
    # 阈值放宽后 6.0 不再违规
    assert engine.evaluate({"npl_ratio": 6.0}) == []
    assert engine.override_threshold("NOT-EXIST", 1.0) is False


def test_engine_from_dicts_and_to_dict_roundtrip():
    engine = build_default_engine()
    rebuilt = RuleEngine.from_dicts(engine.to_dict())
    assert len(rebuilt) == len(engine)
    assert rebuilt.get_rule("CREDIT-001").threshold == engine.get_rule("CREDIT-001").threshold


def test_finding_to_agent_finding_shape():
    finding = _credit_rule().evaluate({"npl_ratio": 9.0})
    payload = finding.to_agent_finding()
    assert payload["severity"] == "high"
    assert payload["evidence"]["threshold"] == 5.0
    assert payload["recommendation"]


# ---------------- 内置规则库 ----------------


def test_default_rules_have_unique_ids():
    ids = [r.rule_id for r in DEFAULT_RULES]
    assert len(ids) == len(set(ids))


def test_default_rules_are_well_formed():
    for rule in DEFAULT_RULES:
        assert rule.operator in ("lte", "lt", "gte", "gt", "eq", "ne")
        assert rule.metric
        assert rule.regulation_ref, f"{rule.rule_id} 缺少监管依据"


def test_default_rules_cover_multiple_categories():
    categories = {r.category for r in DEFAULT_RULES}
    for expected in (
        RuleCategory.CREDIT,
        RuleCategory.CAPITAL,
        RuleCategory.LIQUIDITY,
        RuleCategory.COMPLIANCE,
        RuleCategory.OPERATION,
    ):
        assert expected in categories


def test_builtin_engine_flags_concentration_breach():
    engine = build_default_engine()
    findings = engine.evaluate({"single_customer_concentration": 18.0})
    ids = [f.rule_id for f in findings]
    assert "CREDIT-001" in ids
    assert findings[0].severity == "critical"


def test_builtin_engine_passes_on_healthy_metrics():
    engine = build_default_engine()
    healthy = {
        "single_customer_concentration": 8.0,
        "group_customer_concentration": 12.0,
        "npl_ratio": 1.6,
        "provision_coverage": 220.0,
        "provision_to_loan": 3.0,
        "capital_adequacy_ratio": 14.0,
        "tier1_ratio": 11.0,
        "cet1_ratio": 10.0,
        "leverage_ratio": 6.0,
        "lcr": 130.0,
        "nsfr": 115.0,
        "liquidity_ratio": 55.0,
        "loan_to_deposit": 68.0,
        "kyc_completeness": 100.0,
        "sanction_screening_coverage": 100.0,
        "edd_coverage": 100.0,
        "aml_training_per_year": 2.0,
        "large_transaction_report_days": 5.0,
        "suspicious_report_days": 3.0,
        "customer_data_retention_years": 5.0,
        "transaction_data_retention_years": 5.0,
        "rectification_rate": 98.0,
        "major_case_count": 0.0,
        "dual_control_coverage": 100.0,
        "access_review_per_year": 2.0,
        "cost_income_ratio": 35.0,
        "roa": 0.9,
    }
    assert engine.evaluate(healthy) == []


# ---------------- 工具封装 ----------------


def test_audit_rule_check_tool_reports_violations():
    result = audit_rule_check({"npl_ratio": 9.0, "lcr": 90.0})
    assert result["violations"] == 2
    assert result["by_severity"]["high"] == 1
    assert result["by_severity"]["critical"] == 1


def test_audit_rule_check_tool_filters_category():
    result = audit_rule_check({"npl_ratio": 9.0, "lcr": 90.0}, categories=["liquidity"])
    assert result["violations"] == 1
    assert result["findings"][0]["category"] == "liquidity"


def test_rule_library_lookup_tool():
    all_rules = rule_library_lookup()
    assert len(all_rules) == len(DEFAULT_RULES)
    credit_only = rule_library_lookup("credit")
    assert all(r["category"] == "credit" for r in credit_only)
