# Devpost Submission — copy paste

> Everything below is written in final English you can paste straight into Devpost. Replace the bracketed `[YOUR_URL]` / `[YOUR_REPO]` with the real values.

---

## Title (use the format: name — the hook)

**AlphaGuard — an investment researcher whose job is to stop you from admiring a beautiful backtest**

## Subtitle / tagline

> It's not a pretty screen for a human — it's a truth-server for an agent. Under WebMCP, AlphaGuard hands agents real, deterministic risk-gate tools: the agent calls, the gate vetoes, and a `BLOCKED` verdict is final.

## Short description (first paragraph — start with the hook, not "this is a project")

The WebMCP promise is that a website hands an agent *real, actionable* tools instead of a chat box. AlphaGuard delivers on that promise in the domain where honesty matters most: money. It exposes five typed, callable actions (`llms.txt` → `webmcp.json` → the endpoints) so an agent can actually research an investment-strategy question. But here's the twist — the agent that calls AlphaGuard **can't cheat**. An LLM plans the research, but deterministic data-provenance, data-quality, walk-forward and production gates hold **final veto authority**. Feed it any strategy, and the pretty backtest still comes back `BLOCKED` the moment the data is unproven — no order intent is ever created, and the LLM has no power to override. It's anti-hype hardware for trustworthy human-agent finance.

## Full description

### The problem
Most "AI investing" is either a dashboard of net-worth charts or a demo that sells you on a beautiful backtest. Both are a trap: a backtest that looks great can absolutely be built on data and assumptions that shouldn't touch real money. And when an autonomous agent acts on that, the failure scales.

### The idea
Don't read our sparse design as unfinished — it's load-bearing. The page isn't a dashboard to impress a human; it's a contract the agent reads. AlphaGuard is the agent-facing surface of the **Personal Investment OS**. Instead of letting an agent guess its way through a UI, the site exposes real actions that agents call directly:

| Tool | Endpoint | What it does |
|---|---|---|
| `audit_strategy` | `POST /api/goai/audit-demo` | Full guarded audit: LLM plans → deterministic backtest → provenance/quality/walk-forward/production gates → verdict + auditable tool trace |
| `run_demo_backtest` | `GET /api/research/demo-backtest` | Reproducible backtest on explicitly-marked synthetic data |
| `validate_dataset` | `POST /api/research/datasets/ohlcv/validate` | Validate an OHLCV CSV against a data contract; returns errors/warnings + fingerprint |
| `market_rules` | `GET /api/research/market-rules` | US / CN trading-unit, short-selling and price-limit rules |
| `run_experiment` | `POST /api/research/experiments/personal/run` | Validate a user CSV and replay the fixed research-only protocol |

### The guardrail that makes it a *WebMCP* project
The tools aren't just endpoints — each one carries `agent_safety` metadata in `webmcp.json`: authority `PLAN_ONLY`, `deterministic_veto` and `order_creation: NEVER`. The golden demo is the moment the agent wants to move a low-vol ETF rotation strategy to paper trading: **the metrics look great, and the gate still says `BLOCKED`**, because the data is synthetic and the production checks take priority over the number on the chart. This is the human-agent experience WebMCP is about: the person and the agent can both *understand* why the agent was refused — because the agent had no power to fudge the answer.

### Real evidence, not a mockup
`POST /api/goai/audit-demo` is a real endpoint returning structured JSON — try the live demo on `/`, and the full tool trace (planner → inspect_dataset → run_backtest → audit_backtest → **apply_risk_gate: BLOCKED** → create_order_intent: SKIPPED) is rendered live on the page.

### What it doesn't do (and why that's the point)
No auto-order placement. Paper-only by default; external brokers disabled. Human approval lives outside the agent's reach. It's not investment advice and makes no return promises. The ability to *refuse* is the feature.

## Built With
Python · FastAPI · Uvicorn · pandas · numpy · Qwen (DashScope, OpenAI-compatible) · WebMCP (`webmcp.json` / `llms.txt`) · Render

## Screenshot specs (3) — take on the deployed site, crop 16:9
1. **shot-1-blocked.png** — the `/` live demo showing the red `BLOCKED` verdict badge above the 6-step tool trace (pause until `apply_risk_gate: BLOCKED` and `create_order_intent: SKIPPED` are visible).
2. **shot-2-agent.png** — the English landing's "An agent can't cheat its way past it" transcript card showing the agent calling `/llms.txt` → `/webmcp.json` → `audit_strategy` → `BLOCKED`.
3. **shot-3-manifest.png** — a section of `/webmcp.json` showing the `policy` block and an `audit_strategy` tool entry with its `agent_safety` (`PLAN_ONLY`, `deterministic_veto`, `order_creation: NEVER`).

## Links
- Live app: `[YOUR_DEPLOYED_URL]`
- Source: `[YOUR_REPO_URL]`
- Demo video: `[YOUR_VIDEO_URL]`

## Additional
Follow the 60–90s video script in `WEBMCP_SUBMISSION.md`.