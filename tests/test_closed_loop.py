from datetime import date
from decimal import Decimal

from pio_core import PioStore
from portfolio.importers import import_account_csv


def build_store(tmp_path):
    store = PioStore(str(tmp_path / "pio-test.db"))
    source = "symbol,name,market,currency,quantity,avg_cost,last_price,asset_type\n510300,沪深300ETF,CN,CNY,1000,3.75,3.91,ETF\nAAPL,Apple,US,USD,10,212,225.5,STOCK\nCASH_CNY,人民币现金,CN,CNY,20000,1,1,CASH\nCASH_USD,美元现金,US,USD,1800,1,1,CASH\n"
    holdings = import_account_csv(source).holdings
    store.import_holdings(holdings, {"USD/CNY": Decimal("7.2")}, "test.csv", date.today().isoformat())
    return store


def test_full_paper_trade_closed_loop(tmp_path):
    store = build_store(tmp_path)
    intent = store.create_order_intent("510300", "CN", "CNY", "SELL", Decimal("100"), Decimal("3.91"), "组合权重超过预设上限，需要降低集中度", "plan-018")
    assert intent["status"] == "PENDING_APPROVAL"
    assert all(check["status"] == "PASS" for check in intent["risk_checks"])
    assert store.approve(intent["id"], "owner")["status"] == "APPROVED"
    result = store.simulate(intent["id"])
    assert result["order"]["status"] == "FILLED"
    position = next(item for item in result["portfolio"]["positions"] if item["symbol"] == "510300")
    assert Decimal(position["quantity"]) == Decimal("900")
    cash = next(item for item in result["portfolio"]["positions"] if item["symbol"] == "CASH_CNY")
    assert Decimal(cash["market_value"]) > Decimal("20000")
    assert store.audit_events()["verified"] is True


def test_risk_rejects_oversized_order(tmp_path):
    store = build_store(tmp_path)
    intent = store.create_order_intent("AAPL", "US", "USD", "BUY", Decimal("100"), Decimal("225.5"), "尝试明显超过现金和组合上限的订单", "too-large")
    assert intent["status"] == "REJECTED"
    assert {check["code"] for check in intent["risk_checks"] if check["status"] == "FAIL"} >= {"ORDER_SIZE", "CASH_AVAILABLE"}


def test_import_is_idempotent(tmp_path):
    store = PioStore(str(tmp_path / "pio-test.db"))
    holdings = import_account_csv("symbol,name,market,currency,quantity,last_price\nAAPL,Apple,US,USD,1,200\n").holdings
    first = store.import_holdings(holdings, {"USD/CNY": Decimal("7.2")}, "same.csv", date.today().isoformat())
    second = store.import_holdings(holdings, {"USD/CNY": Decimal("7.2")}, "same.csv", date.today().isoformat())
    assert first["snapshot_id"] == second["snapshot_id"]
    assert second["idempotent"] is True


def test_order_intent_idempotency_prevents_duplicate_plan(tmp_path):
    store = build_store(tmp_path)
    first = store.create_order_intent("510300", "CN", "CNY", "SELL", Decimal("10"), Decimal("3.91"), "测试同一计划不可重复创建交易意图", "same-plan")
    second = store.create_order_intent("510300", "CN", "CNY", "SELL", Decimal("10"), Decimal("3.91"), "即使理由文字不同也不能重复创建计划", "same-plan")
    assert first["id"] == second["id"]


def test_stale_approved_order_cannot_fork_old_portfolio(tmp_path):
    store = build_store(tmp_path)
    first = store.create_order_intent("510300", "CN", "CNY", "SELL", Decimal("10"), Decimal("3.91"), "第一个减仓计划用于改变账户快照", "first-plan")
    second = store.create_order_intent("510300", "CN", "CNY", "SELL", Decimal("10"), Decimal("3.91"), "第二个计划基于同一个旧账户快照", "second-plan")
    store.approve(first["id"], "owner")
    store.approve(second["id"], "owner")
    store.simulate(first["id"])
    try:
        store.simulate(second["id"])
    except ValueError as exc:
        assert "portfolio changed" in str(exc)
    else:
        raise AssertionError("stale approved order should be rejected")
