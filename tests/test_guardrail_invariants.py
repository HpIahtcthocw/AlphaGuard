"""Deterministic guardrail invariants, locked with hypothesis property tests.

These are not ordinary regression cases: they assert *for every* valid gate input
that the deterministic veto can never be bypassed and stays reproducible. Any
future change that lets a gate pass when it should block, or that lets the agent
reach execution, breaks one of these properties.

Run alone:  pytest tests/test_guardrail_invariants.py
"""

from typing import Any, Dict, List

import hypothesis.strategies as st
from hypothesis import given, settings

from agent.guardrail import ALLOWED_TOOLS, GuardrailAgent, run_guarded_audit

# Planning must never be able to schedule execution before the gate runs.
REQUIRED_AUDIT_TOOLS = ("inspect_dataset", "run_backtest", "audit_backtest", "apply_risk_gate")

REASONS = [
    "requires independent data-vendor reconciliation",
    "requires walk-forward parameter stability and stress scenarios",
    "requires at least four weeks of paper-trading reconciliation",
]


@st.composite
def backtest_payload(draw) -> Dict[str, Any]:
    """A realistic, well-formed backtest payload drawn from a wide input space."""
    errors = draw(st.lists(st.text(min_size=1, max_size=12), max_size=3))
    warnings = draw(st.lists(st.text(min_size=1, max_size=12), max_size=3))
    reasons = draw(st.lists(st.sampled_from(REASONS), max_size=3))
    return {
        "dataset_kind": draw(st.sampled_from(["SYNTHETIC_DEMO", "REAL_MARKET_DATA", "UNKNOWN", ""])),
        "data_fingerprint": draw(st.text(max_size=24)),
        "data_quality": {"errors": errors, "warnings": warnings},
        "period": {
            "start": draw(st.text(max_size=12)),
            "end": draw(st.text(max_size=12)),
            "sessions": draw(st.integers(min_value=0, max_value=3000)),
        },
        "metrics": {
            "annualized_return": draw(st.floats(min_value=-0.9, max_value=9.0, allow_nan=False, allow_infinity=False)),
            "max_drawdown": draw(st.floats(min_value=-0.9, max_value=0.0, allow_nan=False, allow_infinity=False)),
            "sharpe": draw(st.floats(min_value=-3.0, max_value=6.0, allow_nan=False, allow_infinity=False)),
        },
        "out_of_sample_metrics": {
            "annualized_return": draw(st.floats(min_value=-0.9, max_value=9.0, allow_nan=False, allow_infinity=False)),
        },
        "walk_forward": {
            "folds": draw(st.lists(st.just({}), max_size=5)),
            "metrics": {"annualized_return": draw(st.floats(min_value=-0.5, max_value=5.0, allow_nan=False, allow_infinity=False))},
        },
        "baselines": {},
        "production_eligible": draw(st.booleans()),
        "eligibility_reasons": reasons,
    }


def _audit(backtest: Dict[str, Any]) -> Dict[str, Any]:
    # api_key="" forces the deterministic rule planner; no network, ever.
    return run_guarded_audit(backtest, "verify the low-vol rotation strategy", agent=GuardrailAgent(api_key=""), lang="en")


def _checks(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    return result["evidence"]["risk_gate"]["checks"]


@given(st.data())
@settings(max_examples=20)
def test_verdict_is_binary_and_never_executes(data):
    result = _audit(data.draw(backtest_payload()))
    assert result["verdict"] in {"BLOCKED", "ELIGIBLE"}
    assert result["order_intent_created"] is False
    assert result["evidence"]["risk_gate"]["decision"] == result["verdict"]
    assert result["trace"][-1]["status"] in {"SKIPPED", "REQUIRES_HUMAN_APPROVAL"}


@given(st.data())
@settings(max_examples=20)
def test_verdict_is_consistent_with_gate_checks(data):
    result = _audit(data.draw(backtest_payload()))
    blocked = any(check["status"] == "BLOCKED" for check in _checks(result))
    expected = "BLOCKED" if blocked else "ELIGIBLE"
    assert result["verdict"] == expected, f"gate says {expected}, risk_gate decision said {result['verdict']}"


@given(st.data())
@settings(max_examples=20)
def test_non_real_dataset_is_always_blocked(data):
    result = _audit(data.draw(backtest_payload()))
    provenance = next(c for c in _checks(result) if c["code"] == "DATASET_PROVENANCE")
    if result["evidence"]["dataset"]["kind"] != "REAL_MARKET_DATA":
        assert result["verdict"] == "BLOCKED"
        assert provenance["status"] == "BLOCKED"


@given(st.data())
@settings(max_examples=20)
def test_non_production_eligible_is_always_blocked(data):
    backtest = data.draw(backtest_payload())
    result = _audit(backtest)
    if not backtest["production_eligible"]:
        production = next(c for c in _checks(result) if c["code"] == "PRODUCTION_READINESS")
        assert production["status"] == "BLOCKED"
        assert result["verdict"] == "BLOCKED"


@given(st.data())
@settings(max_examples=20)
def test_walk_forward_gate_matches_fold_count(data):
    backtest = data.draw(backtest_payload())
    result = _audit(backtest)
    folds = len(backtest["walk_forward"]["folds"])
    wf = next(c for c in _checks(result) if c["code"] == "WALK_FORWARD")
    if folds < 3:
        assert wf["status"] == "BLOCKED"


@given(st.data())
@settings(max_examples=20)
def test_trace_is_complete_and_well_formed(data):
    result = _audit(data.draw(backtest_payload()))
    trace = result["trace"]
    assert len(trace) == 6
    assert [step["sequence"] for step in trace] == [1, 2, 3, 4, 5, 6]
    for step in trace:
        assert step["tool"] in {*ALLOWED_TOOLS, "planner"}
    # The execution step never runs: blocked -> skipped, eligible -> still human-gated.
    last = trace[-1]
    assert last["tool"] == "create_order_intent"
    if result["verdict"] == "BLOCKED":
        assert last["status"] == "SKIPPED"
        assert last["evidence"]["created"] is False
    else:
        assert last["status"] == "REQUIRES_HUMAN_APPROVAL"
        assert last["evidence"]["created"] is False


@given(st.data())
@settings(max_examples=20)
def test_planner_can_never_schedule_execution(data):
    result = _audit(data.draw(backtest_payload()))
    planner_tools = result["planner"]["tools"]
    assert "create_order_intent" not in planner_tools
    assert set(REQUIRED_AUDIT_TOOLS) <= set(planner_tools)
    assert set(planner_tools) <= set(ALLOWED_TOOLS)


@given(st.data())
@settings(max_examples=20)
def test_same_input_yields_same_verdict_and_run_id(data):
    backtest = data.draw(backtest_payload())
    first = _audit(backtest)
    second = _audit(backtest)
    assert first["verdict"] == second["verdict"]
    assert first["run_id"] == second["run_id"]
    assert [c["status"] for c in _checks(first)] == [c["status"] for c in _checks(second)]