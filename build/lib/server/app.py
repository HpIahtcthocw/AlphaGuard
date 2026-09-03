"""FastAPI surface for the local-first investment operating system."""

from __future__ import annotations

import os
import io
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent import run_guarded_audit
from market_data import AlpacaMarketDataProvider, MarketDataService, PortfolioSnapshotProvider, QuoteRequest, TushareRealtimeProvider
from market_data.service import routes_from_env
from execution import ExecutionService
from pio_core import PioStore
from portfolio.importers import Holding
from research import run_research_backtest, run_personal_investment_experiment
from research.factors import list_factors
from research.datasets import load_ohlcv_csv, validate_ohlcv_frame
from research.experiments import ohlcv_to_close_prices
from research.scanner import ScannerConfig, scan_universe
from strategies.backtest import BacktestConfig
from strategies.registry import STRATEGY_REGISTRY
from strategies.regime_breakout import BreakoutConfig, evaluate_breakout_signal
from strategies.long_short_backtest import LongShortBacktestConfig, run_long_short_backtest
from execution.market_rules import get_market_rules, list_market_rules


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = os.getenv("PIO_DB_PATH", str(ROOT / "data" / "pio.db"))
store = PioStore(DB_PATH)
market_data = MarketDataService(
    providers=[AlpacaMarketDataProvider(), TushareRealtimeProvider()],
    routes=routes_from_env(),
    fallback_provider=PortfolioSnapshotProvider(lambda account_id: store.portfolio(account_id)),
    ttl_seconds=float(os.getenv("PIO_QUOTE_CACHE_TTL_SECONDS", "3")),
)
execution = ExecutionService()
app = FastAPI(title="Personal Investment OS", version="0.7.0")

# WebMCP: let AI agents call our real research/risk actions from any origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HoldingInput(BaseModel):
    symbol: str
    name: str
    market: str
    currency: str
    quantity: Decimal
    avg_cost: Optional[Decimal] = None
    last_price: Optional[Decimal] = None
    market_value: Decimal
    asset_type: str = "STOCK"


class HoldingsImportRequest(BaseModel):
    holdings: List[HoldingInput]
    fx_rates: Dict[str, Decimal] = Field(default_factory=lambda: {"USD/CNY": Decimal("7.2")})
    source_name: str = "browser-import"
    as_of: str = Field(default_factory=lambda: date.today().isoformat())
    account_id: str = "default"


class OrderIntentRequest(BaseModel):
    symbol: str
    market: str
    currency: str
    side: str
    quantity: Decimal
    reference_price: Decimal
    reason: str
    idempotency_key: str
    account_id: str = "default"
    expires_at: Optional[str] = None


class ApprovalRequest(BaseModel):
    approved_by: str = "local-user"


class QuoteInstrumentInput(BaseModel):
    symbol: str
    market: str
    currency: str


class QuoteBatchRequest(BaseModel):
    instruments: List[QuoteInstrumentInput]
    allow_snapshot_fallback: bool = True


class ResearchBacktestRequest(BaseModel):
    dates: List[str]
    prices: Dict[str, List[float]]
    strategy_id: str = "S-001"
    parameters: Dict[str, object] = Field(default_factory=dict)
    benchmark_symbol: Optional[str] = None
    split_ratio: float = Field(default=0.70, gt=0.50, lt=0.95)
    initial_cash: float = Field(default=100_000, gt=0)
    commission_bps: float = Field(default=3.0, ge=0)
    slippage_bps: float = Field(default=5.0, ge=0)
    walk_forward_train_window: int = Field(default=252, ge=126)
    walk_forward_test_window: int = Field(default=63, ge=21)


class ExternalSubmissionRequest(BaseModel):
    confirmation_phrase: str
    max_price_deviation: Decimal = Field(default=Decimal("0.05"), gt=0, le=Decimal("0.20"))


class BreakoutSignalRequest(BaseModel):
    symbol: str
    market: str
    dates: List[str]
    close: List[float]
    volume: List[float]
    benchmark_close: Optional[List[float]] = None
    shortable: bool = False
    borrow_cost_bps: Optional[float] = None
    parameters: Dict[str, object] = Field(default_factory=dict)


class UniverseInstrumentInput(BaseModel):
    market: Optional[str] = None
    close: List[float]
    volume: List[float]
    shortable: bool = False
    borrow_cost_bps: Optional[float] = None
    sector: Optional[str] = None
    name: Optional[str] = None


class UniverseScanRequest(BaseModel):
    market: str
    dates: List[str]
    instruments: Dict[str, UniverseInstrumentInput]
    benchmark_close: Optional[List[float]] = None
    breakout_parameters: Dict[str, object] = Field(default_factory=dict)
    scanner_parameters: Dict[str, object] = Field(default_factory=dict)


class LongShortBacktestRequest(BaseModel):
    dates: List[str]
    prices: Dict[str, List[float]]
    target_weights: Dict[str, List[float]]
    benchmark: Optional[List[float]] = None
    shortable: Dict[str, bool] = Field(default_factory=dict)
    borrow_cost_bps: Dict[str, float] = Field(default_factory=dict)
    market: str = "US"
    parameters: Dict[str, object] = Field(default_factory=dict)


class OhlcvValidationRequest(BaseModel):
    csv_text: str = Field(min_length=1, max_length=5_000_000)
    dataset_kind: str = "REAL_MARKET_DATA"


class PersonalExperimentRequest(BaseModel):
    csv_text: str = Field(min_length=1, max_length=5_000_000)
    dataset_kind: str = "REAL_MARKET_DATA"
    benchmark_symbol: Optional[str] = None


class GoaiAuditRequest(BaseModel):
    task: str = Field(
        default="验证低波动 ETF 轮动策略是否已经具备进入模拟交易的证据。",
        min_length=8,
        max_length=500,
    )
    lang: str = Field(default="zh", pattern="^(zh|en)$")
    scenario: str = Field(default="synthetic", pattern="^(synthetic|proven)$")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "mode": "local-first",
        "execution": "paper-only",
        "version": app.version,
        "market_data": market_data.status(),
        "execution_adapter": execution.status(),
        "goai_planner": {
            "provider": "DashScope/Qwen",
            "configured": bool(os.getenv("DASHSCOPE_API_KEY", "").strip()),
            "model": os.getenv("DASHSCOPE_MODEL", "qwen-plus"),
        },
    }


@app.get("/api/market-data/status")
def market_data_status():
    return market_data.status()


@app.post("/api/market-data/quotes")
def market_data_quotes(request: QuoteBatchRequest):
    try:
        instruments = [QuoteRequest(item.symbol, item.market, item.currency) for item in request.instruments]
        return market_data.get_quotes(instruments, request.allow_snapshot_fallback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/research/strategies")
def research_strategies():
    return {
        "strategies": [
            {
                "strategy_id": item.strategy_id,
                "name": item.name,
                "version": item.version,
                "provenance": item.provenance,
                "license_note": item.license_note,
                "risk_level": item.risk_level,
                "rebalance_frequency": item.rebalance_frequency,
                "supports_paper": item.supports_paper,
                "production_eligible": item.production_eligible,
                "mode": item.mode,
            }
            for item in STRATEGY_REGISTRY.values()
        ]
    }


@app.post("/api/research/backtest")
def research_backtest(request: ResearchBacktestRequest):
    try:
        if not request.prices or any(len(values) != len(request.dates) for values in request.prices.values()):
            raise ValueError("every price series must have the same length as dates")
        frame = pd.DataFrame(request.prices, index=pd.to_datetime(request.dates))
        config = BacktestConfig(initial_cash=request.initial_cash, commission_bps=request.commission_bps, slippage_bps=request.slippage_bps)
        return run_research_backtest(
            frame,
            request.strategy_id,
            request.parameters,
            config,
            request.benchmark_symbol,
            request.split_ratio,
            walk_forward_train_window=request.walk_forward_train_window,
            walk_forward_test_window=request.walk_forward_test_window,
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/research/factors")
def research_factors(market: Optional[str] = None):
    return {"factors": list_factors(market)}


@app.get("/api/research/market-rules")
def research_market_rules(market: Optional[str] = None):
    if market:
        try:
            rule = get_market_rules(market)
            return {"rules": [{
                "market": rule.market,
                "currency": rule.currency,
                "timezone": rule.timezone,
                "lot_size": rule.lot_size,
                "supports_short": rule.supports_short,
                "price_tick": rule.price_tick,
                "daily_price_limit_pct": rule.daily_price_limit_pct,
                "session_note": rule.session_note,
            }]}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"rules": list_market_rules()}


@app.post("/api/research/datasets/ohlcv/validate")
def validate_ohlcv_dataset(request: OhlcvValidationRequest):
    try:
        frame = pd.read_csv(io.StringIO(request.csv_text))
        report = validate_ohlcv_frame(frame, request.dataset_kind)
        if not report["errors"]:
            from research.datasets import fingerprint_ohlcv

            report["data_fingerprint"] = fingerprint_ohlcv(frame)
        return report
    except (TypeError, ValueError, pd.errors.ParserError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/research/signals/breakout")
def research_breakout_signal(request: BreakoutSignalRequest):
    try:
        lengths = {len(request.dates), len(request.close), len(request.volume)}
        if request.benchmark_close is not None:
            lengths.add(len(request.benchmark_close))
        if len(lengths) != 1:
            raise ValueError("dates, close, volume and benchmark_close must have equal lengths")
        frame = pd.DataFrame({"close": request.close, "volume": request.volume}, index=pd.to_datetime(request.dates))
        benchmark = pd.Series(request.benchmark_close, index=frame.index, name="benchmark") if request.benchmark_close is not None else None
        config = BreakoutConfig(**request.parameters)
        return evaluate_breakout_signal(frame, benchmark, request.market, request.symbol, request.shortable, request.borrow_cost_bps, config)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/research/signals/breakout/universe")
def research_breakout_universe(request: UniverseScanRequest):
    try:
        if not request.instruments:
            raise ValueError("instruments cannot be empty")
        universe = {}
        metadata = {}
        for symbol, item in request.instruments.items():
            if len(item.close) != len(request.dates) or len(item.volume) != len(request.dates):
                raise ValueError(f"{symbol}: close and volume must match dates")
            universe[symbol] = pd.DataFrame({"close": item.close, "volume": item.volume}, index=pd.to_datetime(request.dates))
            metadata[symbol] = {"shortable": item.shortable, "borrow_cost_bps": item.borrow_cost_bps, "sector": item.sector, "name": item.name}
        benchmark = pd.Series(request.benchmark_close, index=pd.to_datetime(request.dates), name="benchmark") if request.benchmark_close is not None else None
        return scan_universe(universe, benchmark, request.market, metadata, BreakoutConfig(**request.breakout_parameters), ScannerConfig(**request.scanner_parameters))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/research/backtest/long-short")
def research_long_short_backtest(request: LongShortBacktestRequest):
    try:
        if set(request.prices) != set(request.target_weights):
            raise ValueError("prices and target_weights must contain the same symbols")
        if any(len(values) != len(request.dates) for values in [*request.prices.values(), *request.target_weights.values()]):
            raise ValueError("all series must match dates")
        index = pd.to_datetime(request.dates)
        prices = pd.DataFrame(request.prices, index=index)
        weights = pd.DataFrame(request.target_weights, index=index)
        benchmark = pd.Series(request.benchmark, index=index) if request.benchmark is not None else None
        result = run_long_short_backtest(
            prices,
            weights,
            LongShortBacktestConfig(**request.parameters),
            benchmark,
            request.shortable,
            request.borrow_cost_bps,
            market=request.market,
        )
        return {
            "metrics": result.metrics,
            "warnings": result.warnings,
            "forced_liquidations": [date.date().isoformat() for date, value in result.forced_liquidations.items() if value],
            "blocked_trade_days": [date.date().isoformat() for date, value in result.blocked_trade_days.items() if value],
            "rule_warnings": result.rule_warnings,
            "equity": [{"date": date.date().isoformat(), "value": round(float(value), 6)} for date, value in result.equity.items()],
            "positions": [{"date": date.date().isoformat(), **{symbol: round(float(value), 8) for symbol, value in row.items()}} for date, row in result.positions.iterrows()],
            "research_only": True,
            "execution_note": "包含借券、保证金和强平近似模型；不代表任何券商的实际可成交性。",
        }
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/research/demo-backtest")
def research_demo_backtest():
    dates = pd.bdate_range("2021-01-04", periods=1100)
    rng = np.random.default_rng(42)
    market = rng.normal(0.00025, 0.010, len(dates))
    prices = pd.DataFrame(
        {
            "CORE": 100 * np.exp(np.cumsum(market)),
            "DEFENSIVE": 100 * np.exp(np.cumsum(0.55 * market + rng.normal(0.00010, 0.0045, len(dates)))),
            "DIVERSIFIER": 100 * np.exp(np.cumsum(-0.15 * market + rng.normal(0.00008, 0.006, len(dates)))),
        },
        index=dates,
    )
    return run_research_backtest(
        prices,
        benchmark_symbol="CORE",
        dataset_kind="SYNTHETIC_DEMO",
        walk_forward_train_window=504,
        walk_forward_test_window=126,
    )


@app.get("/api/research/experiments/personal")
def personal_investment_experiment():
    """Run the project's deterministic, research-only investment experiment."""
    try:
        return run_personal_investment_experiment()
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/research/experiments/personal/run")
def run_personal_investment_experiment_from_csv(request: PersonalExperimentRequest):
    """Validate a user OHLCV CSV, then replay the fixed experiment protocol."""
    try:
        frame, quality = load_ohlcv_csv(io.StringIO(request.csv_text), request.dataset_kind)
        prices, price_note = ohlcv_to_close_prices(frame)
        benchmark = request.benchmark_symbol.strip().upper() if request.benchmark_symbol else str(prices.columns[0])
        result = run_personal_investment_experiment(
            prices,
            dataset_kind=request.dataset_kind,
            benchmark_symbol=benchmark,
            source_note=price_note,
        )
        result["input_dataset"] = quality
        result["input_dataset"]["data_fingerprint"] = quality.get("data_fingerprint")
        return result
    except (TypeError, ValueError, pd.errors.ParserError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/goai/audit-demo")
def goai_audit_demo(request: GoaiAuditRequest):
    """Run the golden demo without granting the agent execution authority.

    `scenario="synthetic"` audits explicitly unproven demo data -> BLOCKED.
    `scenario="proven"` audits a source-verified, production-eligible dataset
    through the SAME deterministic gates -> ELIGIBLE. Either way every gate
    decision is appended to the immutable, chained-hash audit ledger.
    """
    backtest = research_demo_backtest()
    if request.scenario == "proven":
        backtest["dataset_kind"] = "REAL_MARKET_DATA"
        backtest["production_eligible"] = True
        backtest["eligibility_reasons"] = []
    result = run_guarded_audit(backtest, request.task, lang=request.lang)
    result["scenario"] = request.scenario
    store.record_guardrail_decision(result)
    return result


@app.get("/api/execution/status")
def execution_status():
    return execution.status()


@app.post("/api/order-intents/{intent_id}/submit")
def submit_external_order(intent_id: str, request: ExternalSubmissionRequest):
    try:
        intent = store.prepare_external_execution(intent_id)
        if intent.get("existing_broker_order"):
            return {"idempotent": True, "broker_order": intent["existing_broker_order"]}
        quote_result = market_data.get_quotes(
            [QuoteRequest(str(intent["symbol"]), str(intent["market"]), str(intent["currency"]))],
            allow_snapshot_fallback=False,
        )
        if not quote_result["quotes"]:
            raise ValueError("a real-time quote is required before external broker submission")
        quote = quote_result["quotes"][0]
        if not quote["is_realtime"]:
            raise ValueError("external broker submission refuses non-real-time quotes")
        submitted = execution.submit(intent, request.confirmation_phrase, Decimal(str(quote["price"])), request.max_price_deviation)
        broker_order = store.record_broker_submission(
            intent_id,
            execution.broker.name,
            execution.broker.environment,
            str(submitted["external_order_id"]),
            str(submitted["status"]),
            submitted["raw"],
            str(submitted.get("submitted_at") or "") or None,
        )
        return {"idempotent": False, "quote": quote, "broker_order": broker_order}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/order-intents/{intent_id}/sync")
def sync_external_order(intent_id: str):
    """Refresh broker order state; does not invent fills or update holdings."""
    try:
        intent = store.prepare_external_execution(intent_id)
        broker_order = intent.get("existing_broker_order") or intent.get("broker_order")
        if not broker_order:
            raise ValueError("no submitted broker order to sync")
        status = execution.sync_order(str(broker_order["external_order_id"]))
        saved = store.update_broker_order(intent_id, str(status["status"]), status.get("raw", status))
        return {
            "broker_order": saved,
            "status": status,
            "fills_reconciled": False,
            "note": "订单状态已同步；成交数量、成交均价和现金账本仍需独立成交回报对账。",
        }
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/accounts/import")
def import_holdings(request: HoldingsImportRequest):
    try:
        holdings = [Holding(item.symbol.upper(), item.name, item.market.upper(), item.currency.upper(), item.quantity, item.avg_cost, item.last_price, item.market_value, item.asset_type.upper()) for item in request.holdings]
        return store.import_holdings(holdings, request.fx_rates, request.source_name, request.as_of, request.account_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/portfolio")
def portfolio(account_id: str = "default"):
    return store.portfolio(account_id)


@app.post("/api/order-intents")
def create_order(request: OrderIntentRequest):
    try:
        return store.create_order_intent(request.symbol.upper(), request.market.upper(), request.currency.upper(), request.side.upper(), request.quantity, request.reference_price, request.reason, request.idempotency_key, request.account_id, request.expires_at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/order-intents/{intent_id}/approve")
def approve_order(intent_id: str, request: ApprovalRequest):
    try:
        return store.approve(intent_id, request.approved_by)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/order-intents/{intent_id}/simulate")
def simulate_order(intent_id: str):
    try:
        return store.simulate(intent_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/audit")
def audit(limit: int = 100):
    return store.audit_events(min(max(limit, 1), 500))


@app.get("/api/audit/verify")
def verify_audit_chain():
    """Return a machine-verifiable proof that the decision ledger has not been tampered with."""
    events = store.audit_events(500)
    return {
        "verified": events["verified"],
        "count": len(events["events"]),
        "latest_sequence": events["events"][0]["sequence"] if events["events"] else None,
        "method": "sha256 chained-hash ledger (append-only, start-of-genesis GENESIS)",
        "note": "verified=false indicates a record was rewritten or reordered; a trusted auditor should then reject the ledger.",
    }


@app.get("/api/audit/guardrail")
def audit_guardrail(limit: int = 100):
    """Read-only view of deterministic risk-gate decisions only."""
    ledger = store.audit_events(min(max(limit, 1), 500))
    decisions = [event for event in ledger["events"] if event["event_type"] == "GUARDRAIL_RUN"]
    return {"verified": ledger["verified"], "decisions": decisions}


@app.get("/", include_in_schema=False)
def webmcp_landing():
    landing = ROOT / "landing.html"
    if landing.exists():
        return FileResponse(landing)
    return FileResponse(ROOT / "index.html")


app.mount("/", StaticFiles(directory=ROOT, html=True), name="static")
