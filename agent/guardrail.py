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
DEFAULT_TASK = "验证低波动 ETF 轮动策略是否已经具备进入模拟交易的证据。"


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
            return self._rule_fallback("未配置 DASHSCOPE_API_KEY；本次未调用 Qwen。")

        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是个人投资研究流程的工具规划器，不提供投资建议。"
                        "只能从 inspect_dataset、run_backtest、audit_backtest、apply_risk_gate、"
                        "create_order_intent 中选择工具。风险门禁拥有最终否决权；"
                        "只有 apply_risk_gate 判定 ELIGIBLE 后才允许 create_order_intent。"
                        "返回 JSON：{\"tools\":[...],\"note\":\"...\"}。"
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
                model=self.model,
                label=f"Qwen 规划器 · {self.model}",
                tools=tools,
                api_key_configured=True,
                note=str(planned.get("note") or "Qwen 已生成受控工具计划。"),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, urllib.error.URLError, TimeoutError):
            return self._rule_fallback("Qwen 规划失败，已降级为确定性规则规划器；审计仍可继续。", configured=True)

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
            label="规则规划器演示（未调用 Qwen）",
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
            "label": "数据来源可用于生产" if not en else "Data source is production-usable",
            "detail": (
                "当前是明确标记的合成演示数据，不能支持交易决策。"
                if dataset_kind != "REAL_MARKET_DATA"
                else "数据来源标记为真实市场数据。"
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
            "label": "数据质量检查" if not en else "Data quality check",
            "detail": (
                f"{len(data_quality.get('errors') or [])} 个错误，{len(data_quality.get('warnings') or [])} 个警告。"
                if not en
                else f"{len(data_quality.get('errors') or [])} errors, {len(data_quality.get('warnings') or [])} warnings."
            ),
        },
        {
            "code": "WALK_FORWARD",
            "status": "PASSED" if len(walk_forward.get("folds") or []) >= 3 else "BLOCKED",
            "label": "Walk-forward 样本外验证" if not en else "Walk-forward out-of-sample validation",
            "detail": (
                f"已运行 {len(walk_forward.get('folds') or [])} 个滚动窗口。"
                if not en
                else f"Ran {len(walk_forward.get('folds') or [])} rolling windows."
            ),
        },
        {
            "code": "PRODUCTION_READINESS",
            "status": "PASSED" if bool(backtest.get("production_eligible")) else "BLOCKED",
            "label": "生产就绪条件" if not en else "Production readiness",
            "detail": (
                "；".join(_translate_reason(reason, lang) for reason in reasons)
                or ("引擎未返回生产准入结论。" if not en else "Engine returned no production eligibility verdict.")
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
            "title": "理解审计任务并约束工具范围" if not en else "Understand the task and constrain the tool scope",
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
            "title": "检查数据来源与指纹" if not en else "Inspect data source and fingerprint",
            "summary": (
                f"识别为 {dataset_kind}，共 {int((backtest.get('period') or {}).get('sessions') or 0)} 个交易日。"
                if not en
                else f"Identified as {dataset_kind}, {int((backtest.get('period') or {}).get('sessions') or 0)} trading sessions."
            ),
            "evidence": {"dataset_kind": dataset_kind, "fingerprint": fingerprint, "data_quality": data_quality},
        },
        {
            "sequence": 3,
            "tool": "run_backtest",
            "status": "COMPLETED",
            "title": "运行策略与三条基线" if not en else "Run the strategy and three baselines",
            "summary": (
                "回测引擎已计算全样本、样本外表现、成本和基准差异。"
                if not en
                else "Backtest engine computed full-sample, out-of-sample, cost and benchmark deltas."
            ),
            "evidence": {"metrics": _metric_excerpt(metrics), "baselines": baseline_summary},
        },
        {
            "sequence": 4,
            "tool": "audit_backtest",
            "status": "COMPLETED",
            "title": "执行样本外与 Walk-forward 审计" if not en else "Run out-of-sample and walk-forward audit",
            "summary": (
                f"样本外年化收益 {_percent(out_of_sample.get('annualized_return'), lang)}，但不据此推断未来收益。"
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
            "title": "确定性风险门禁做最终裁决" if not en else "Deterministic risk gate makes the final call",
            "summary": (
                ("证据不足，拒绝进入模拟交易。" if not en else "Insufficient evidence — refused entry to paper trading.")
                if blocked
                else ("全部硬性条件通过，可进入人工复核。" if not en else "All hard conditions passed; ready for human review.")
            ),
            "evidence": {"checks": checks, "llm_can_override": False},
        },
        {
            "sequence": 6,
            "tool": "create_order_intent",
            "status": "SKIPPED" if blocked else "REQUIRES_HUMAN_APPROVAL",
            "title": (
                ("订单意图未创建" if not en else "Order intent not created")
                if blocked
                else ("等待人工批准后创建订单意图" if not en else "Awaiting human approval to create the order intent")
            ),
            "summary": (
                ("风险门禁已阻断执行路径，数据库未写入订单意图。" if not en else "Risk gate blocked the execution path; no order intent was written.")
                if blocked
                else ("Agent 无权绕过人工批准。" if not en else "The agent has no authority to bypass human approval.")
            ),
            "evidence": {"created": order_intent_created, "reason": decision},
        },
    ]

    return {
        "run_id": run_id,
        "task": task,
        "verdict": decision,
        "headline": (
            "这笔交易，我拒绝执行。" if blocked else "证据通过，等待你的最终判断。"
        )
        if not en
        else ("This trade — I refuse to execute it." if blocked else "Evidence passed; awaiting your final call."),
        "summary": (
            "回测看起来不错，但数据来源和生产验证条件不够可信。"
            if blocked
            else "硬性门禁通过，但系统仍不会自动下单。"
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
            "仅用于研究流程演示，不构成投资建议，不代表真实收益。"
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
        return "n/a" if lang == "en" else "未知"
    return f"{number:.2%}"


def _translate_reason(reason: str, lang: str = "zh") -> str:
    if lang == "en":
        return reason
    translations = {
        "requires independent data-vendor reconciliation": "缺少独立数据源交叉核验",
        "requires walk-forward parameter stability and stress scenarios": "缺少参数稳定性与压力场景验证",
        "requires at least four weeks of paper-trading reconciliation": "缺少至少四周模拟盘对账",
    }
    return translations.get(reason, reason)
