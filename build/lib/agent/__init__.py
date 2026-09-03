"""Constrained agents for investment research workflows."""

from .guardrail import GuardrailAgent, run_guarded_audit

__all__ = ["GuardrailAgent", "run_guarded_audit"]
