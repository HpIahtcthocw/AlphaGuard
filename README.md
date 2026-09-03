# Personal Investment OS

## AlphaGuard — WebMCP Challenge submission (English)

> **An investment researcher whose job is to stop you from admiring a beautiful backtest.** A person and their AI agent validate a strategy together — but the agent can't bend the rules.

AlphaGuard is the agent-facing surface of the Personal Investment OS. It exposes **real, deterministic, auditable actions** (not a chatbot) that AI agents call directly, declared in [`webmcp.json`](./webmcp.json) and discoverable from [`llms.txt`](./llms.txt). The flagship action is a **guarded audit**: the LLM plans the research sequence, but deterministic data-provenance, data-quality, walk-forward and production gates hold **final veto authority**. Even when the demo backtest looks great (synthetic data is explicitly marked), the gate returns `BLOCKED` and no order intent is ever created. The LLM can plan — it never overrides.

- Tools: `audit_strategy`, `run_demo_backtest`, `validate_dataset`, `market_rules`, `run_experiment`
- Safety: `PLAN_ONLY` authority, deterministic veto, human approval for execution, brokers disabled by default
- Demo entry: `/` (live guarded-audit) · [`webmcp.json`](./webmcp.json) · [`llms.txt`](./llms.txt)
- Submission write-up + video script + Render deploy steps: [`WEBMCP_SUBMISSION.md`](./WEBMCP_SUBMISSION.md)

Reality check: not investment advice, makes no return promises, and represents real returns nowhere.

## GOAI 参赛切口：AlphaGuard

**一句话：一个不负责荐股、专门阻止你被漂亮回测骗到的个人投资研究 Agent。**

默认首屏是 AlphaGuard 的黄金演示：用户要求验证一条低波动 ETF 轮动策略，Agent 调用数据检查、真实回测、样本外审计和风险门禁工具。当前演示使用明确标记的 `SYNTHETIC_DEMO` 数据，因此即使回测结果看起来不错，确定性门禁仍会返回 `BLOCKED`，并且不会创建订单意图。

Qwen 只拥有任务理解和工具规划权，不能改写风险规则。配置 `DASHSCOPE_API_KEY` 后使用 DashScope OpenAI 兼容接口；未配置时界面会明确显示“规则规划器演示（未调用 Qwen）”。完整参赛说明见 [GOAI 提交包](./docs/GOAI_SUBMISSION.md)。

一个本地优先、可审计、面向专业个人投资者和小型投资组织的量化研究、组合账本与受控执行系统。

> 当前版本 `0.7.0`。系统已经具备可运行的行情适配层、版本化因子注册表、多标的市场状态驱动多空突破研究信号、研究组合扫描、研究回测 API、账户账本、纸面交易闭环和可选 Alpaca Paper/Live 适配器，并新增 A 股/美股市场规则、OHLCV 数据集质量契约和可用真实 CSV 重放的个人投资实验；但还没有通过真实资金生产验收，不构成投资建议。

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
- [OHLCV 数据集契约](./docs/DATASET_CONTRACT.md)
- [我们的第一项投资实验](./docs/PERSONAL_INVESTMENT_EXPERIMENT.md)
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
- 17 个版本化 OHLCV/市场状态因子，以及 `S-003` 多空突破研究策略；空头信号与空头可执行性明确分离。
- 多标的横截面扫描、因子排名、研究组合净/毛暴露和空头可执行性筛选。
- Alpaca 官方美股行情和 TuShare A 股实时行情适配器；无凭证时明确降级为非实时持仓快照。
- 本地 CSV 一键导入，支持中美持仓、交易流水与 CNY/USD 折算。
- SQLite 不可变持仓快照、交易意图、硬风控、人工批准、纸面成交和哈希审计链。
- Alpaca Paper/Live 经纪商适配器、外部订单持久化、实时价格偏离检查和两层实盘解锁。
- Alpaca 订单状态查询与持久化同步；明确不把状态回报自动当作成交账本。
- 多空研究回测：负仓位、借券成本、保证金融资、维持保证金、每日亏损保护和强平近似。
- A 股/美股规则适配：交易单位、做空许可、涨跌停近似阻断与规则告警；标准 OHLCV CSV 校验、数据指纹和数据集类型标记。
- PIO-EXP-001 个人投资实验协议：固定参数、基线、样本外与 walk-forward 证据，以及明确的研究/纸面门禁。
- PIO-EXP-001 支持使用经过契约校验的真实/延迟 OHLCV CSV 重放；完整 `adjusted_close` 会优先用于研究，缺失时明确降级为 raw close。
- 42 个自动化测试；CI 覆盖 Python 3.9 与 3.12。

## 当前不具备

- 没有被证明的稳定 Alpha，也没有任何收益承诺。
- 交易流水尚未完整进入现金、分红、税费和公司行动账本。
- 没有中国券商实盘适配器；A 股实时行情需要 TuShare 权限。
- 没有完成真实数据的 walk-forward 参数稳定性、容量、涨跌停、停牌、退市和公司行动验证。
- 市场规则目前是研究与执行前置门禁的保守近似，不等价于交易所或券商生产规则；仍需接入真实停牌、板块、公司行动和券商回报。
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
- `GET /api/research/market-rules`：查看 A 股/美股交易单位、做空和价格限制规则。
- `POST /api/research/datasets/ohlcv/validate`：校验真实/延迟/快照/合成 OHLCV CSV 契约。
- `GET /api/research/experiments/personal`：运行 PIO-EXP-001 的确定性研究实验；不会创建订单意图。
- `POST /api/research/experiments/personal/run`：校验用户 OHLCV CSV 并重放同一实验协议；不会创建订单意图。
- `POST /api/order-intents/{id}/simulate`：本地纸面成交。
- `POST /api/order-intents/{id}/submit`：受控外部券商提交。
- `POST /api/order-intents/{id}/sync`：同步外部券商订单状态；成交回报仍需独立对账。
- `GET /api/audit`：可检测篡改的哈希审计链验证。

## 项目状态

当前准确定位是：**可运行的早期 Alpha 投资操作系统**。研究和执行架构已经成形，但距离真实资金生产系统仍需要真实数据验证、交易流水对账、券商回报同步、监控告警、安全审计和连续纸面运行验收。
