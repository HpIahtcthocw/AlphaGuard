# Firebreak Security Benchmarks

Two machine-verifiable suites that turn Firebreak's core promise — *"the
deterministic veto can never be bypassed"* — from a claim into a testable
fact. Any submission for review (demo, agent, PR) is measured against these.

## 1. Deterministic Gate Invariants (property-based)

`tests/test_guardrail_invariants.py` locks the semantics of the veto using
[Hypothesis](https://hypothesis.readthedocs.io/) property tests. For *every*
valid gate input drawn from a wide space, they assert:

| Invariant | Meaning |
|---|---|
| `verdict ∈ {BLOCKED, ELIGIBLE}` | Output is always a clean, single verdict |
| `order_intent_created == False` | Execution is unreachable, always |
| verdict consistent with gate checks | Blocking ⇒ `BLOCKED`; a veto can't be "silently skipped" |
| Non-real data ⇒ `BLOCKED` | Synthetic/unknown provenance always refused |
| Not production-eligible ⇒ `BLOCKED` | No readiness, no green light |
| Trace well-formed | Always 6 steps, sequence 1→6, valid tools |
| Planner never schedules execution | `create_order_intent` is out of the LLM's reach |
| Same input ⇒ same verdict + run_id | Determinism / reproducibility hold |

## 2. Adversarial Risk Scenarios (the published benchmark)

`tests/test_security_benchmark.py` fixes 8 named scenarios of "attempts to get
a bad strategy past the gate". Scenarios `BENCH-01 … BENCH-07` **must** be
vetoed; `BENCH-08` (all-hard-gates-green) must still **not self-execute** and
remain behind human approval. Running the suite:

```bash
pytest tests/test_guardrail_invariants.py tests/test_security_benchmark.py -v
```

## 3. Immutable Decision Ledger

Every `POST /api/goai/audit-demo` decision is appended to a SQLite
append-only, SHA-256 chained-hash ledger (`previous_hash → event_hash`).
`tests/test_audit_integrity.py` proves the chain stays consistent across many
appends and that any tampering flips verification to `false`.

Machine-verifiable endpoints:

- `GET /api/audit/verify` — chain integrity proof + record count
- `GET /api/audit/guardrail` — read-only view of gate decisions
- `GET /api/audit` — full event ledger

## What this buys you

- **For agents / WebMCP**: real, callable, verifiable risk actions — not a UI.
- **For auditors**: an append-only proof that no decision was rewritten.
- **For judges**: three independently testable claims, runnable in one line.