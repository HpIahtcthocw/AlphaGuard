# 确定性业务闭环

本项目借鉴优秀系统的核心，不直接复制其实现：Ghostfolio 的账户与交易导入、Wealthfolio 的本地优先和数据所有权、Lean 的事件驱动与测试纪律、NautilusTrader 的研究/执行一致语义，以及 Qlib 的完整研究生产链。

## 当前闭环

`行情/持仓导入 -> 因子计算 -> 单标的/横截面信号 -> 研究组合 -> 基线/回测/审计 -> 交易意图 -> 硬风控 -> 人工批准 -> 本地纸面成交或外部经纪商提交 -> 成交回写 -> 派生新快照 -> 哈希审计链`

### 不可变快照

导入和成交不直接覆盖旧持仓，每次生成新快照并保留父快照。相同来源数据通过内容哈希保证幂等，避免重复导入。

### 交易意图

策略或用户只能创建 `OrderIntent`。它包含标的、市场、币种、方向、数量、参考价、理由、来源快照和幂等键。没有交易意图不能生成成交。

### 硬风控

当前门禁包括订单字段、允许市场、数据新鲜度、订单占组合比例、币种现金、单项仓位上限和可卖持仓。风控是普通 Python 确定性代码，不允许 Agent 覆盖。

### 人工批准

只有 `PENDING_APPROVAL` 状态可以批准；被拒绝、已成交或过期的计划不能重复批准。

### 纸面成交

模拟执行使用同一个交易意图，明确计算滑点和佣金。成交后更新对应证券和同币种现金，生成新的不可变组合快照。

### 哈希审计链

账户初始化、导入、交易意图、批准和成交都写入追加式审计日志。每条记录包含上一条哈希，篡改后验证会失败。

## API

- `GET /api/health`
- `POST /api/accounts/import`
- `GET /api/portfolio`
- `POST /api/order-intents`
- `POST /api/order-intents/{id}/approve`
- `POST /api/order-intents/{id}/simulate`
- `GET /api/audit`
- `GET /api/market-data/status`
- `POST /api/market-data/quotes`
- `GET /api/research/strategies`
- `POST /api/research/backtest`
- `GET /api/execution/status`
- `POST /api/order-intents/{id}/submit`

默认配置只能作用于本地纸面账户。Alpaca Paper/Live 适配器已经存在，但外部提交需要凭证、实时报价、人工批准和逐笔确认；Live 还需要独立环境杀开关。经纪商成交回报同步尚未完成，因此当前不应视为生产就绪。
