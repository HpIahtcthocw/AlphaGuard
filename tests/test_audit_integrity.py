"""Immutability of the chained-hash decision ledger."""

import sqlite3

from pio_core import PioStore


def _decision(run_id="AG-TEST", verdict="BLOCKED"):
    return {
        "run_id": run_id,
        "task": "verify strategy",
        "verdict": verdict,
        "order_intent_created": False,
        "planner": {"mode": "RULE_FALLBACK"},
        "evidence": {
            "risk_gate": {
                "checks": [
                    {"code": "DATASET_PROVENANCE", "status": "BLOCKED"},
                    {"code": "PRODUCTION_READINESS", "status": "PASSED"},
                ]
            }
        },
    }


def test_guardrail_decisions_are_chained_and_verifiable(tmp_path):
    store = PioStore(str(tmp_path / "ledger.db"))
    store.record_guardrail_decision(_decision("AG-A", "BLOCKED"))
    store.record_guardrail_decision(_decision("AG-B", "BLOCKED"))

    ledger = store.audit_events(100)
    assert ledger["verified"] is True
    runs = [event for event in ledger["events"] if event["event_type"] == "GUARDRAIL_RUN"]
    assert [event["entity_id"] for event in runs] == ["AG-B", "AG-A"]
    # event hashes must differ (payload differs) and chain via previous_hash.
    assert runs[0]["previous_hash"] == runs[1]["event_hash"]
    assert runs[0]["event_hash"] != runs[1]["event_hash"]


def test_tampering_is_detected(tmp_path):
    store = PioStore(str(tmp_path / "tamper.db"))
    store.record_guardrail_decision(_decision("AG-TAMPER", "BLOCKED"))

    with sqlite3.connect(str(tmp_path / "tamper.db")) as conn:
        conn.execute("UPDATE audit_log SET payload_json=? WHERE event_type='GUARDRAIL_RUN'",
                     ('{"verdict":"ELIGIBLE","run_id":"AG-TAMPER","task":"x"}',))
        conn.commit()

    # The chain hash no longer matches the rewritten payload -> verification fails.
    ledger = store.audit_events(100)
    assert ledger["verified"] is False


def test_chain_stays_consistent_across_many_appends(tmp_path):
    store = PioStore(str(tmp_path / "chain.db"))
    for index in range(5):
        store.record_guardrail_decision(_decision(f"AG-{index}", "BLOCKED"))

    ledger = store.audit_events(100)
    assert ledger["verified"] is True
    runs = [event for event in ledger["events"] if event["event_type"] == "GUARDRAIL_RUN"]
    # newest first; every pair must be linked previous_hash -> prior event_hash
    for current, previous in zip(runs, runs[1:]):
        assert current["previous_hash"] == previous["event_hash"]