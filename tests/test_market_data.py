from decimal import Decimal

from market_data import AlpacaMarketDataProvider, MarketDataService, PortfolioSnapshotProvider, QuoteRequest, TushareRealtimeProvider


def test_alpaca_normalizes_snapshot_payload():
    def transport(method, url, headers, body, timeout):
        assert method == "GET"
        assert "symbols=AAPL" in url
        assert headers["APCA-API-KEY-ID"] == "key"
        return {
            "snapshots": {
                "AAPL": {
                    "latestTrade": {"p": 225.5, "t": "2026-08-01T15:59:59Z"},
                    "latestQuote": {"bp": 225.49, "ap": 225.51},
                    "prevDailyBar": {"c": 223.0},
                }
            }
        }

    provider = AlpacaMarketDataProvider("key", "secret", transport=transport)
    quote = provider.fetch_quotes([QuoteRequest("aapl", "us", "usd")])[0]
    assert quote.price == Decimal("225.5")
    assert quote.bid == Decimal("225.49")
    assert quote.source == "alpaca:iex"
    assert quote.is_realtime is True


def test_tushare_normalizes_rt_k_payload():
    def transport(method, url, headers, body, timeout):
        assert method == "POST"
        assert body["params"]["ts_code"] == "510300.SH"
        return {
            "code": 0,
            "data": {
                "fields": ["ts_code", "price", "pre_close", "bid1", "ask1", "trade_date", "trade_time"],
                "items": [["510300.SH", 3.91, 3.88, 3.909, 3.911, "20260802", "10:01:02"]],
            },
        }

    provider = TushareRealtimeProvider("token", transport=transport)
    quote = provider.fetch_quotes([QuoteRequest("510300", "CN", "CNY")])[0]
    assert quote.price == Decimal("3.91")
    assert quote.previous_close == Decimal("3.88")
    assert quote.source == "tushare:rt_k"


def test_service_explicitly_falls_back_to_non_realtime_snapshot():
    portfolio = {
        "as_of": "2026-08-02",
        "positions": [{"symbol": "AAPL", "market": "US", "currency": "USD", "last_price": "225.5"}],
    }
    fallback = PortfolioSnapshotProvider(lambda account_id: portfolio)
    provider = AlpacaMarketDataProvider("", "")
    service = MarketDataService([provider], {"US": "alpaca"}, fallback)
    result = service.get_quotes([QuoteRequest("AAPL", "US", "USD")])
    assert result["returned"] == 1
    assert result["quotes"][0]["price"] == "225.5"
    assert result["quotes"][0]["is_realtime"] is False
    assert result["quotes"][0]["source"] == "portfolio-snapshot"
    assert result["errors"][0]["error"] == "provider is not configured"
