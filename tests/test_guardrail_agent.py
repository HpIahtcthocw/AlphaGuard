from agent.guardrail import GuardrailAgent, run_guarded_audit


def _backtest_result(production_eligible=False):
    return {
        "dataset_kind": "SYNTHETIC_DEMO",
        "data_fingerprint": "abc123",
        "data_quality": {"errors": [], "warnings": [], "instruments": ["CORE"]},
        "period": {"start": "2024-01-01", "end": "2025-01-01", "sessions": 252},
        "metrics": {"annualized_return": 0.12, "max_drawdown": -0.08, "sharpe": 1.1},
        "out_of_sample_metrics": {"annualized_return": 0.08, "max_drawdown": -0.06, "sharpe": 0.8},
        "walk_forward": {"folds": [{}, {}, {}], "metrics": {"annualized_return": 0.05}},
        "baselines": {},
        "production_eligible": production_eligible,
        "eligibility_reasons": ["requires at least four weeks of paper-trading reconciliation"],
    }


def test_rule_fallback_is_transparent(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    planner = GuardrailAgent().plan("验证这个策略是否可以进入模拟交易")

    assert planner.mode == "RULE_FALLBACK"
    assert planner.api_key_configured is False
    assert "未调用 Qwen" in planner.label
    assert "create_order_intent" not in planner.tools


def test_tool_plan_cannot_schedule_order_before_gate():
    tools = GuardrailAgent._normalize_tools(["create_order_intent", "unknown_tool"])

    assert tools == ["inspect_dataset", "run_backtest", "audit_backtest", "apply_risk_gate"]


def test_synthetic_dataset_is_always_blocked(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    result = run_guarded_audit(_backtest_result(production_eligible=True))

    assert result["verdict"] == "BLOCKED"
    assert result["order_intent_created"] is False
    assert result["trace"][-1]["status"] == "SKIPPED"
    provenance = next(check for check in result["evidence"]["risk_gate"]["checks"] if check["code"] == "DATASET_PROVENANCE")
    assert provenance["status"] == "BLOCKED"
