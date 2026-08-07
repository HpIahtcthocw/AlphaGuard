# Personal Investment OS

一个本地优先、可审计、面向专业个人投资者和小型投资组织的量化研究、组合账本与受控执行系统。

> 当前版本 `0.3.0`。系统已经具备可运行的行情适配层、研究回测 API、账户账本、纸面交易闭环和可选 Alpaca Paper/Live 适配器，但还没有通过真实资金生产验收，不构成投资建议。

## 为什么做这个项目

个人投资工具通常在两个极端之间：一端是只展示净值和资产分布的记账工具，另一端是用漂亮回测或 LLM 预测包装的自动交易 Demo。PIO 尝试补上中间缺失的一层：让数据、假设、策略、风险、批准、订单和复盘形成一条可以复现和追责的链路。

核心原则是：**系统首先要阻止用户被自己的回测和叙事骗到。**

## 文档入口

- [产品与技术方案](./docs/PRODUCT_TECHNICAL_PLAN.md)
- [用户痛点与产品边界](./docs/USER_NEEDS_AND_PRODUCT_BOUNDARY.md)
- [策略层与专业化门禁](./docs/STRATEGY_EDGE.md)
- [账户导入与中美市场支持](./docs/ACCOUNT_IMPORT_AND_MULTI_MARKET.md)
- [确定性业务闭环](./docs/CLOSED_LOOP_ARCHITECTURE.md)
- [研究与决策规格](./docs/RESEARCH_AND_DECISION_SPEC.md)
- [风险与合规门禁](./docs/RISK_AND_COMPLIANCE.md)
- [实施路线图](./docs/ROADMAP.md)
- [行情与执行架构](./docs/MARKET_DATA_AND_EXECUTION.md)
- [研究验证协议](./docs/RESEARCH_VALIDATION.md)
- [Build in Public 计划](./docs/BUILD_IN_PUBLIC.md)
- [待确认决策](./docs/OPEN_DECISIONS.md)

## 首版定位

当前面向单一用户或小型团队，支持 A 股/ETF 与美股账户快照、规则型量化研究、本地纸面交易，以及经过人工批准的 Alpaca 模拟盘/实盘提交。实盘适配器默认关闭，必须经过环境杀开关和逐笔确认。

## 设计原则

1. 研究、信号、组合和订单全部可追溯。
2. Agent 只能提出假设、分析和交易计划，不能绕过风险门禁直接下单。
3. 数据、策略和执行适配器可替换，避免锁死在单一供应商。
4. 先做好小而可信的闭环，再扩展资产类别和自动化程度。

## 当前实现

- 可交互的本地投资工作台原型。
- 策略注册表、来源与许可证说明。
- 第一支可审计的 ETF 防守型趋势轮动基线。
- 严格月末调仓、协方差组合波动率目标、强制次日执行和权重漂移的回测核心。
- 买入持有、月度等权、趋势过滤三类基线；样本外指标、数据指纹、数据质量和成本审计。
- Alpaca 官方美股行情和 TuShare A 股实时行情适配器；无凭证时明确降级为非实时持仓快照。
- 本地 CSV 一键导入，支持中美持仓、交易流水与 CNY/USD 折算。
- SQLite 不可变持仓快照、交易意图、硬风控、人工批准、纸面成交和哈希审计链。
- Alpaca Paper/Live 经纪商适配器、外部订单持久化、实时价格偏离检查和两层实盘解锁。
- 20 个自动化测试；CI 覆盖 Python 3.9 与 3.12。

## 当前不具备

- 没有被证明的稳定 Alpha，也没有任何收益承诺。
- 交易流水尚未完整进入现金、分红、税费和公司行动账本。
- 没有中国券商实盘适配器；A 股实时行情需要 TuShare 权限。
- 没有完成真实数据的 walk-forward 参数稳定性、容量、涨跌停、停牌、退市和公司行动验证。
- Agent/LLM 仍是受约束研究层规划，不拥有交易权限，也不会被描述成已运行的多 Agent 系统。

## 本地运行

```powershell
python -m pip install -e ".[dev]"
python -m uvicorn server.app:app --host 127.0.0.1 --port 4173
```

然后访问 `http://127.0.0.1:4173`。默认 `PIO_EXECUTION_ADAPTER=local-paper`，不会向外部券商发单。

## 可选行情与模拟券商

复制 `.env.example` 为 `.env`，按需配置：

```text
ALPACA_API_KEY_ID=...
ALPACA_API_SECRET_KEY=...
ALPACA_MARKET_DATA_FEED=iex
TUSHARE_TOKEN=...
PIO_EXECUTION_ADAPTER=alpaca-paper
```

实时接口未配置或失败时，API 会返回错误并可降级到 `portfolio-snapshot`，同时将 `is_realtime` 标记为 `false`。外部券商提交不会接受这类降级报价。

## 核心 API

- `POST /api/market-data/quotes`：标准化实时/快照报价与来源状态。
- `POST /api/research/backtest`：用户价格矩阵的可复现回测与基线比较。
- `GET /api/research/demo-backtest`：明确标记为合成数据的引擎演示。
- `POST /api/order-intents/{id}/simulate`：本地纸面成交。
- `POST /api/order-intents/{id}/submit`：受控外部券商提交。
- `GET /api/audit`：可检测篡改的哈希审计链验证。

## 项目状态

当前准确定位是：**可运行的早期 Alpha 投资操作系统**。研究和执行架构已经成形，但距离真实资金生产系统仍需要真实数据验证、交易流水对账、券商回报同步、监控告警、安全审计和连续纸面运行验收。
