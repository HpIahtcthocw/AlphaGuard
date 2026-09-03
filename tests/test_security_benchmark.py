"""AlphaGuard Security Benchmark — published, machine-verifiable risk scenarios.

Each scenario describes an *attempt to get a bad strategy past the gate*. The
benchmark asserts the deterministic veto MUST block every one of them. If a
future change lets any scenario through, the benchmark fails — that is the
point. See SECURITY_BENCHMARK.md for the public-facing explanation.

Run alone:  pytest tests/test_security_benchmark.py -v
"""

import pytest

from agent.guardrail import GuardrailAgent, run_guarded_audit


def _payload(**overrides):
    base = {
        "dataset_kind": "SYNTHETIC_DEMO",
        "data_fingerprint": "bench-0000",
        "data_quality": {"errors": [], "warnings": []},
        "period": {"start": "2024-01-01", "end": "2025-01-01", "sessions": 252},
        "metrics": {"annualized_return": 0.25, "max_drawdown": -0.06, "sharpe": 2.4},
        "out_of_sample_metrics": {"annualized_return": 0.19, "max_drawdown": -0.05, "sharpe": 1.9},
        "walk_forward": {"folds": [{}, {}, {}, {}, {}], "metrics": {"annualized_return": 0.11}},
        "baselines": {},
        "production_eligible": True,
        "eligibility_reasons": [],
    }
    base.update(overrides)
    return base


def _run(payload):
    return run_guarded_audit(payload, "can this strategy enter paper trading?", agent=GuardrailAgent(api_key=""), lang="en")


@pytest.mark.parametrize(
    "scenario_id,payload,label",
    [
        (
            "BENCH-01",
            _payload(dataset_kind=""),
            "no dataset provenance at all",
        ),
        (
            "BENCH-02",
            _payload(dataset_kind="SYNTHETIC_DEMO", production_eligible=True),
            "synthetic data wrongly claims production-ready",
        ),
        (
            "BENCH-03",
            _payload(dataset_kind="REAL_MARKET_DATA", production_eligible=False),
            "real data but no production eligibility",
        ),
        (
            "BENCH-04",
            _payload(data_quality={"errors": ["duplicate rows"], "warnings": []}),
            "data quality errors present",
        ),
        (
            "BENCH-05",
            _payload(walk_forward={"folds": [{}, {}]}),
            "insufficient walk-forward out-of-sample evidence",
        ),
        (
            "BENCH-06",
            _payload(walk_forward={"folds": []}),
            "no walk-forward validation at all",
        ),
        (
            "BENCH-07",
            _payload(production_eligible=True, dataset_kind="REAL_MARKET_DATA",
                     data_quality={"errors": ["price <= 0"], "warnings": []}),
            "real + eligible but data fails quality",
        ),
    ],
)
def test_gate_vetoes_every_adversarial_scenario(scenario_id, payload, label):
    result = _run(payload)
    assert result["verdict"] == "BLOCKED", f"{scenario_id} // {label}: gate must BLOCK"
    assert result["order_intent_created"] is False, f"{scenario_id} // {label}: nothing may be executed"
    assert result["trace"][-1]["status"] == "SKIPPED", f"{scenario_id} // {label}: execution must be skipped"


def test_benchmark_proves_no_execution_even_when_gate_is_green_in_fields():
    # Even a payload that holds every hard gate to true is still not auto-executed:
    # human approval is the final, agent-inaccessible step.
    clean = _payload(dataset_kind="REAL_MARKET_DATA", production_eligible=True,
                     data_quality={"errors": [], "warnings": []},
                     walk_forward={"folds": [{}, {}, {}, {}, {}], "metrics": {"annualized_return": 0.11}})
    # clear every remaining blocker so the gate genuinely says ELIGIBLE
    # (REAL + quality-ok + >=3 folds + production_eligible=True, empty reasons)
    result = _run(clean)
    assert result["verdict"] == "ELIGIBLE"
    assert result["order_intent_created"] is False
    order_step = result["trace"][-1]
    assert order_step["tool"] == "create_order_intent"
    assert order_step["status"] == "REQUIRES_HUMAN_APPROVAL"
    assert result["disclaimer"]


BENCHMARK_SCENARIOS = [
    "BENCH-01 no provenance",
    "BENCH-02 synthetic mislabeled ready",
    "BENCH-03 real but not eligible",
    "BENCH-04 quality errors",
    "BENCH-05 insufficient walk-forward",
    "BENCH-06 zero validation",
    "BENCH-07 real+eligible but bad data",
    "BENCH-08 all-green still human-gated",
]


def test_benchmark_defines_public_scenario_manifest():
    assert len(BENCHMARK_SCENARIOS) == 8
    assert all(id_ in " ".join(BENCHMARK_SCENARIOS) for id_ in
               ("BENCH-01", "BENCH-02", "BENCH-03", "BENCH-04",
                "BENCH-05", "BENCH-06", "BENCH-07", "BENCH-08"))