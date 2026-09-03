# OHLCV 数据集契约

研究接口接受的最小行级格式是：

`date,symbol,open,high,low,close,volume`

可选字段为 `adjusted_close,currency,market`。`date + symbol` 必须唯一，行应按日期和标的排序；价格必须为正，且 `high >= open/close >= low`，成交量不得为负。

每个数据集必须标记为以下一种：

- `REAL_MARKET_DATA`：授权供应商的历史数据，必须保留供应商和复权口径。
- `DELAYED`：延迟行情，仅用于研究或盘前规划。
- `SNAPSHOT`：账户或本地快照，不得当成实时行情。
- `SYNTHETIC`：合成数据，只能用于引擎测试和演示。

校验接口会返回错误、警告、覆盖区间、标的列表和 SHA-256 指纹。缺少 `adjusted_close` 不会自动拒绝，但会提示拆股、分红和公司行动可能污染回测。超过 30% 的日变动也只产生警告，因为它可能是真实跳空，也可能是未复权数据。

接口：`POST /api/research/datasets/ohlcv/validate`，请求体为 `{ "csv_text": "...", "dataset_kind": "REAL_MARKET_DATA" }`。

这份契约不替代 point-in-time 数据供应商、交易日历、停牌/退市表和公司行动流水；进入纸面盘前仍需逐项对账。
