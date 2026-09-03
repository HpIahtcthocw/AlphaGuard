"""A constrained research agent with a deterministic production veto."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional


ALLOWED_TOOLS = (
    "inspect_dataset",
    "run_backtest",
    "audit_backtest",
    "apply_risk_gate",
    "create_order_intent",
)
REQUIRED_AUDIT_TOOLS = ALLOWED_TOOLS[:-1]
DEFAULT_TASK = "Verify whether the low-volatility ETF rotation strategy has accumulated sufficient evidence to enter paper trading."


@dataclass(frozen=True)
class PlannerResult:
    mode: str
    model: str
    label: str
    tools: list[str]
    api_key_configured: bool
    note: str


class GuardrailAgent:
    """Use Qwen for planning while keeping execution authority in code."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("DASHSCOPE_API_KEY", "")
        self.model = model or os.getenv("DASHSCOPE_MODEL", "qwen-plus")
        self.endpoint = endpoint or os.getenv(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        )
        self.timeout_seconds = timeout_seconds

    def plan(self, task: str) -> PlannerResult:
        if not self.api_key.strip():
            return self._rule_fallback("No DASHSCOPE_API_KEY configured; Qwen was not called this time.")

        candidates = [self.model] + [m for m in ("qwen-turbo", "qwen-max") if m != self.model]
        for model in candidates:
            planned = self._plan_once(model, task)
            if planned is not None:
                return planned
        return self._rule_fallback(
            "All Qwen models were unavailable; fell back to the deterministic rule planner; the audit may still proceed.",
            configured=True,
        )

    def _plan_once(self, model: str, task: str) -> Optional[PlannerResult]:
        payload = {
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the tool planner for a personal investment research workflow and do not provide investment advice. "
                        "You may only choose tools from inspect_dataset, run_backtest, audit_backtest, apply_risk_gate, "
                        "and create_order_intent. The risk gate has final veto authority; "
                        "create_order_intent is only allowed after apply_risk_gate returns ELIGIBLE. "
                        "Return JSON: {\"tools\":[...],\"note\":\"...\"}."
                    ),
                },
                {"role": "user", "content": task},
            ],
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            planned = json.loads(content)
            tools = self._normalize_tools(planned.get("tools", []))
            return PlannerResult(
                mode="QWEN",
                model=model,
                label=f"Qwen planner · {model}",
                tools=tools,
                api_key_configured=True,
                note=str(planned.get("note") or "Qwen generated a controlled tool plan."),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, urllib.error.URLError, TimeoutError):
            return None

    @staticmethod
    def _normalize_tools(value: object) -> list[str]:
        proposed = [str(item) for item in value] if isinstance(value, list) else []
        tools = [tool for tool in proposed if tool in ALLOWED_TOOLS]
        for required in REQUIRED_AUDIT_TOOLS:
            if required not in tools:
                tools.append(required)
        # Order creation is never scheduled before a successful deterministic gate.
        return [tool for tool in tools if tool != "create_order_intent"]

    def _rule_fallback(self, note: str, configured: bool = False) -> PlannerResult:
        return PlannerResult(
            mode="RULE_FALLBACK",
            model=self.model,
            label="Rule planner demo (Qwen not called)",
            tools=list(REQUIRED_AUDIT_TOOLS),
            api_key_configured=configured,
            note=note,
        )


def run_guarded_audit(
    backtest: Mapping[str, Any],
    task: str = DEFAULT_TASK,
    agent: Optional[GuardrailAgent] = None,
    lang: str = "zh",
) -> dict[str, Any]:
    """Build an auditable tool trace and refuse ineligible order creation."""

    planner = (agent or GuardrailAgent()).plan(task)
    dataset_kind = str(backtest.get("dataset_kind") or "UNKNOWN")
    fingerprint = str(backtest.get("data_fingerprint") or "")
    data_quality = dict(backtest.get("data_quality") or {})
    metrics = dict(backtest.get("metrics") or {})
    out_of_sample = dict(backtest.get("out_of_sample_metrics") or {})
    walk_forward = dict(backtest.get("walk_forward") or {})
    baselines = dict(backtest.get("baselines") or {})
    reasons = [str(reason) for reason in backtest.get("eligibility_reasons") or []]

    en = lang == "en"
    checks = [
        {
            "code": "DATASET_PROVENANCE",
            "status": "BLOCKED" if dataset_kind != "REAL_MARKET_DATA" else "PASSED",
            "label": "Data source is production-usable" if not en else "Data source is production-usable",
            "detail": (
                "Explicitly marked synthetic demo data; cannot support trading decisions."
                if dataset_kind != "REAL_MARKET_DATA"
                else "Data source is marked as real market data."
            )
            if not en
            else (
                "Explicitly marked synthetic demo data; cannot support trading decisions."
                if dataset_kind != "REAL_MARKET_DATA"
                else "Data source is marked as real market data."
            ),
        },
        {
            "code": "DATA_QUALITY",
            "status": "BLOCKED" if data_quality.get("errors") else "PASSED",
            "label": "Data quality check" if not en else "Data quality check",
            "detail": (
                f"{len(data_quality.get('errors') or [])} errors, {len(data_quality.get('warnings') or [])} warnings."
                if not en
                else f"{len(data_quality.get('errors') or [])} errors, {len(data_quality.get('warnings') or [])} warnings."
            ),
        },
        {
            "code": "WALK_FORWARD",
            "status": "PASSED" if len(walk_forward.get("folds") or []) >= 3 else "BLOCKED",
            "label": "Walk-forward out-of-sample validation" if not en else "Walk-forward out-of-sample validation",
            "detail": (
                f"Ran {len(walk_forward.get('folds') or [])} rolling windows."
                if not en
                else f"Ran {len(walk_forward.get('folds') or [])} rolling windows."
            ),
        },
        {
            "code": "PRODUCTION_READINESS",
            "status": "PASSED" if bool(backtest.get("production_eligible")) else "BLOCKED",
            "label": "Production readiness" if not en else "Production readiness",
            "detail": (
                "；".join(_translate_reason(reason, lang) for reason in reasons)
                or ("Engine returned no production eligibility verdict." if not en else "Engine returned no production eligibility verdict.")
            ),
        },
    ]
    blocked = any(check["status"] == "BLOCKED" for check in checks)
    decision = "BLOCKED" if blocked else "ELIGIBLE"
    order_intent_created = False

    baseline_summary = [
        {
            "strategy_id": strategy_id,
            "name": str(item.get("name") or strategy_id),
            "annualized_return": _number((item.get("metrics") or {}).get("annualized_return")),
            "max_drawdown": _number((item.get("metrics") or {}).get("max_drawdown")),
        }
        for strategy_id, item in baselines.items()
    ]
    run_seed = f"{fingerprint}|{task}|{decision}".encode("utf-8")
    run_id = f"AG-{hashlib.sha256(run_seed).hexdigest()[:10].upper()}"

    trace = [
        {
            "sequence": 1,
            "tool": "planner",
            "status": "COMPLETED",
            "title": "Understand the task and constrain the tool scope" if not en else "Understand the task and constrain the tool scope",
            "summary": (
                (
                    "No DASHSCOPE_API_KEY configured — no LLM was called; planning ran in deterministic rule mode."
                    if not planner.api_key_configured
                    else (
                        "Qwen planning failed; fell back to the deterministic rule planner."
                        if planner.mode == "RULE_FALLBACK"
                        else f"Qwen planner ({planner.model}) produced a controlled tool plan under PLAN_ONLY authority."
                    )
                )
                if en
                else planner.note
            ),
            "evidence": {"planned_tools": planner.tools, "authority": "PLAN_ONLY"},
        },
        {
            "sequence": 2,
            "tool": "inspect_dataset",
            "status": "COMPLETED",
            "title": "Inspect data source and fingerprint" if not en else "Inspect data source and fingerprint",
            "summary": (
                f"Identified as {dataset_kind}, {int((backtest.get('period') or {}).get('sessions') or 0)} trading sessions."
                if not en
                else f"Identified as {dataset_kind}, {int((backtest.get('period') or {}).get('sessions') or 0)} trading sessions."
            ),
            "evidence": {"dataset_kind": dataset_kind, "fingerprint": fingerprint, "data_quality": data_quality},
        },
        {
            "sequence": 3,
            "tool": "run_backtest",
            "status": "COMPLETED",
            "title": "Run the strategy and three baselines" if not en else "Run the strategy and three baselines",
            "summary": (
                "Backtest engine computed full-sample, out-of-sample, cost and benchmark deltas."
                if not en
                else "Backtest engine computed full-sample, out-of-sample, cost and benchmark deltas."
            ),
            "evidence": {"metrics": _metric_excerpt(metrics), "baselines": baseline_summary},
        },
        {
            "sequence": 4,
            "tool": "audit_backtest",
            "status": "COMPLETED",
            "title": "Run out-of-sample and walk-forward audit" if not en else "Run out-of-sample and walk-forward audit",
            "summary": (
                f"Out-of-sample annualized return {_percent(out_of_sample.get('annualized_return'), lang)}; not an extrapolation of future returns."
                if not en
                else f"Out-of-sample annualized return {_percent(out_of_sample.get('annualized_return'), lang)}; not an extrapolation of future returns."
            ),
            "evidence": {
                "out_of_sample": _metric_excerpt(out_of_sample),
                "walk_forward_folds": len(walk_forward.get("folds") or []),
                "walk_forward_metrics": _metric_excerpt(walk_forward.get("metrics") or {}),
            },
        },
        {
            "sequence": 5,
            "tool": "apply_risk_gate",
            "status": decision,
            "title": "Deterministic risk gate makes the final call" if not en else "Deterministic risk gate makes the final call",
            "summary": (
                ("Insufficient evidence — refused entry to paper trading." if not en else "Insufficient evidence — refused entry to paper trading.")
                if blocked
                else ("All hard conditions passed; ready for human review." if not en else "All hard conditions passed; ready for human review.")
            ),
            "evidence": {"checks": checks, "llm_can_override": False},
        },
        {
            "sequence": 6,
            "tool": "create_order_intent",
            "status": "SKIPPED" if blocked else "REQUIRES_HUMAN_APPROVAL",
            "title": (
                ("Order intent not created" if not en else "Order intent not created")
                if blocked
                else ("Awaiting human approval to create the order intent" if not en else "Awaiting human approval to create the order intent")
            ),
            "summary": (
                ("Risk gate blocked the execution path; no order intent was written." if not en else "Risk gate blocked the execution path; no order intent was written.")
                if blocked
                else ("The agent has no authority to bypass human approval." if not en else "The agent has no authority to bypass human approval.")
            ),
            "evidence": {"created": order_intent_created, "reason": decision},
        },
    ]

    return {
        "run_id": run_id,
        "task": task,
        "verdict": decision,
        "headline": (
            "This trade — I refuse to execute it." if blocked else "Evidence passed; awaiting your final call."
        )
        if not en
        else ("This trade — I refuse to execute it." if blocked else "Evidence passed; awaiting your final call."),
        "summary": (
            "The backtest looks good, but the data provenance and production validation are not credible enough."
            if blocked
            else "Hard gates passed, but the system still will not auto-place orders."
        )
        if not en
        else (
            "The backtest looks good, but the data provenance and production validation are not credible enough."
            if blocked
            else "Hard gates passed, but the system still will not auto-place orders."
        ),
        "order_intent_created": order_intent_created,
        "planner": asdict(planner),
        "tool_registry": list(ALLOWED_TOOLS),
        "trace": trace,
        "evidence": {
            "dataset": {
                "kind": dataset_kind,
                "fingerprint": fingerprint,
                "period": dict(backtest.get("period") or {}),
                "quality": data_quality,
            },
            "backtest": {
                "metrics": _metric_excerpt(metrics),
                "out_of_sample": _metric_excerpt(out_of_sample),
                "walk_forward_folds": len(walk_forward.get("folds") or []),
                "baselines": baseline_summary,
            },
            "risk_gate": {"decision": decision, "checks": checks, "reasons": reasons},
        },
        "disclaimer": (
            "Research workflow demo only; not investment advice; does not represent real returns."
            if not en
            else "Research workflow demo only; not investment advice; does not represent real returns."
        ),
    }


def _metric_excerpt(metrics: Mapping[str, Any]) -> dict[str, Optional[float]]:
    return {
        key: _number(metrics.get(key))
        for key in ("annualized_return", "max_drawdown", "sharpe", "cost_drag", "final_equity", "excess_return")
    }


def _number(value: object) -> Optional[float]:
    try:
        return round(float(value), 8)
    except (TypeError, ValueError):
        return None


def _percent(value: object, lang: str = "zh") -> str:
    number = _number(value)
    if number is None:
        return "n/a" if lang == "en" else "n/a"
    return f"{number:.2%}"


def _translate_reason(reason: str, lang: str = "zh") -> str:
    if lang == "en":
        return reason
    translations = {
        "requires independent data-vendor reconciliation": "requires independent data-vendor reconciliation",
        "requires walk-forward parameter stability and stress scenarios": "requires walk-forward parameter stability and stress scenarios",
        "requires at least four weeks of paper-trading reconciliation": "requires at least four weeks of paper-trading reconciliation",
    }
    return translations.get(reason, reason)
