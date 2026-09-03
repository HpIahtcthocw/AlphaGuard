# 我们的第一项投资实验：PIO-EXP-001

## 目的

验证一个具体、可证伪的假设：在混合 A 股/美股代理资产和趋势切换环境中，趋势过滤、逆波动率和组合波动率目标，是否能在样本外降低回撤，并保持可接受的换手和成本。

这不是收益承诺，也不是荐股。实验默认使用确定性合成数据，目的是先验证系统闭环、指标和风控是否工作；因此默认结论永远是 `RESEARCH_ONLY`。

## 固定协议

- 策略：`S-001` 防御型 ETF 趋势轮动。
- 参数：126 日动量、200 日趋势、20 日波动率、最多 2 个持仓、单项上限 35%、组合波动率目标 10%、60 日协方差窗口。
- 执行：收盘生成信号，下一交易日执行；月末调仓。
- 成本：佣金 3 bps、滑点 5 bps。
- 基线：`BASE-BUY-HOLD`、`BASE-EQUAL`、`BASE-TREND`。
- 验证：70/30 留出、504/126 walk-forward、数据指纹和质量报告。

## 门禁

1. 数据必须来自授权、复权、point-in-time 的真实数据，才能从研究阶段进入纸面盘候选。
2. 样本外回撤至少与买入持有基线进行比较，不能只看总收益或 Sharpe。
3. 必须完成连续四周纸面盘，且订单、成交、现金和持仓与券商回报逐日对账。
4. 任何门禁失败都返回 `BLOCKED`/`NOT_READY`，不创建订单意图。

## 运行

```text
GET /api/research/experiments/personal
```

返回实验假设、固定协议、完整回测证据、门禁结果和下一步动作。替换真实 OHLCV 数据时必须保持同一协议，并记录新的数据集指纹。

使用真实或延迟 CSV 重放：

```text
POST /api/research/experiments/personal/run
{
  "dataset_kind": "REAL_MARKET_DATA",
  "benchmark_symbol": "AAPL",
  "csv_text": "date,symbol,open,high,low,close,volume,adjusted_close,currency,market\\n..."
}
```

接口会先执行 [OHLCV 数据集契约](./DATASET_CONTRACT.md)，再将长表转为收盘价矩阵。若 `adjusted_close` 对所有行完整，则使用它；否则使用 `close` 并在报告中留下说明。数据校验失败时不会运行策略。
