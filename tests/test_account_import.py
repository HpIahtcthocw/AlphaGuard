from decimal import Decimal
from pathlib import Path

from portfolio.importers import import_account_csv


ROOT = Path(__file__).resolve().parents[1]


def test_imports_cn_and_us_holdings_with_explicit_fx():
    result = import_account_csv((ROOT / "samples" / "account-holdings-cn-us.csv").read_text(encoding="utf-8"))
    assert result.schema == "holdings"
    assert len(result.holdings) == 6
    apple = next(item for item in result.holdings if item.symbol == "AAPL")
    assert apple.market == "US"
    assert apple.currency == "USD"
    total = sum((item.base_value({"USD/CNY": Decimal("7.2")}) for item in result.holdings), Decimal("0"))
    assert total == Decimal("69985.20")


def test_imports_multimarket_transactions():
    result = import_account_csv((ROOT / "samples" / "account-transactions-cn-us.csv").read_text(encoding="utf-8"))
    assert result.schema == "transactions"
    assert len(result.transactions) == 3
    assert {item.market for item in result.transactions} == {"CN", "US"}


def test_supports_chinese_headers():
    csv_text = "证券代码,证券名称,市场,币种,持仓数量,平均成本,最新价,资产类型\nAAPL,苹果,US,USD,2,200,220,STOCK\n"
    result = import_account_csv(csv_text)
    assert result.holdings[0].market_value == Decimal("440")
