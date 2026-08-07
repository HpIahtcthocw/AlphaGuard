"""FastAPI surface for the local-first investment operating system."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from market_data import AlpacaMarketDataProvider, MarketDataService, PortfolioSnapshotProvider, QuoteRequest, TushareRealtimeProvider
from market_data.service import routes_from_env
from execution import ExecutionService
from pio_core import PioStore
from portfolio.importers import Holding
from research import run_research_backtest
from strategies.backtest import BacktestConfig
from strategies.registry import STRATEGY_REGISTRY


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
app = FastAPI(title="Personal Investment OS", version="0.3.0")


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


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "mode": "local-first",
        "execution": "paper-only",
        "version": app.version,
        "market_data": market_data.status(),
        "execution_adapter": execution.status(),
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


app.mount("/", StaticFiles(directory=ROOT, html=True), name="static")
