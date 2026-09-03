# AlphaGuard — WebMCP Challenge Submission

**Project title:** AlphaGuard — an investment researcher whose job is to stop you from admiring a beautiful backtest.

**One-line pitch (use as the Devpost subtitle):**
> A person and their AI agent validate an investment strategy together — but the agent can't bend the rules. AlphaGuard exposes real, deterministic risk-gate actions to agents, and a `BLOCKED` verdict is final.

## What it is

AlphaGuard is the agent-facing surface of the **Personal Investment OS** — a local-first, auditable investment research and paper-trading system. Instead of leaving an AI agent to guess its way through the UI, the web app exposes five structured, real actions (declared in `/webmcp.json` and discoverable from `/llms.txt`). The flagship action is a **guarded audit**: an LLM (Qwen) plans the research sequence, but deterministic data-provenance, data-quality, walk-forward and production gates hold **final veto authority**. Even when the backtest looks great, unproven (synthetic) data makes the gate return `BLOCKED`, and no order intent is ever created. The LLM can plan — it can never override.

## How it fits the WebMCP thesis

WebMCP lets a website hand an agent *real, structured, callable* tools instead of making it click. AlphaGuard is a pure demonstration of that:

- `/llms.txt` — what the site does, for agent discovery.
- `/webmcp.json` — a typed contract listing each tool's method, path, input/output schema and **agent-safety metadata** (`PLAN_ONLY`, `deterministic_veto`, `order_creation: NEVER`).
- Real callable actions an agent can use end-to-end:
  - `audit_strategy` — `POST /api/goai/audit-demo`
  - `run_demo_backtest` — `GET /api/research/demo-backtest`
  - `validate_dataset` — `POST /api/research/datasets/ohlcv/validate`
  - `market_rules` — `GET /api/research/market-rules`
  - `run_experiment` — `POST /api/research/experiments/personal/run`

The **human-agent experience** is the point: a person asks for a strategy validation; the agent calls the tools, gets a structured trace, and both end up with an auditable `BLOCKED`/`ELIGIBLE` verdict they can trust — precisely because the agent had no power to fudge the answer.

## Mapped to the judging criteria

- **Usefulness** — agents that act on financial data are only useful if their claims are auditable. This gives agents a safe, non-executing, evidence-producing path.
- **Originality** — not a chatbot, not a dashboard; a safety-first "anti-hype" research agent with a deterministic veto.
- **Execution** — 42 automated tests, typed contracts, graceful rule-fallback when no LLM key is configured, real structured JSON outputs.
- **Thoughtful use of WebMCP** — tool schema carries `agent_safety`; actions are the product.
- **Human-agent experience** — the live landing demo walks a person + agent through the 6-step audit trace and the moment of refusal.

## What it does NOT do

- Never places real orders; paper-only, human approval required; external brokers default off.
- Is not investment advice and makes no return promises.
- The demo backtest uses explicitly marked `SYNTHETIC_DEMO` data.

---

## Deploy to Render (handoff checklist)

These are the steps to put it live. You need a Render account, a Git remote, and (optionally) a DashScope API key.

1. **Push this repo to a Git remote** (e.g. GitHub).
2. **Create the Web Service on Render**:
   - Render → **New → Blueprint** (Render reads `render.yaml`) — or New → Web Service pointing at the repo.
   - Plan: at least **Starter** (the free/starter tier with enough RAM for pandas).
3. **Build command:** `pip install .`
4. **Start command:** `uvicorn server.app:app --host 0.0.0.0 --port $PORT`
5. **Environment variables:**
   - `PYTHON_VERSION=3.11` (or leave Python version auto; FastAPI needs ≥3.9)
   - `DASHSCOPE_API_KEY=<your DashScope key>` (optional — without it, the audit still works via deterministic rule fallback)
   - Optionally `DASHSCOPE_MODEL=qwen-plus` (default)
6. **Health check path:** `/api/health`
7. **Verify the public URL:**
   - `/` — English landing page with the live demo
   - `/webmcp.json` — tool contract
   - `/llms.txt` — agent discovery
   - `POST /api/goai/audit-demo` with `{"task":"Validate the low-volatility ETF rotation strategy."}` → returns `{"verdict":"BLOCKED", ...}`

> Render injects `$PORT` automatically; the app already reads it via the start command. If you use the free plan, the service may sleep — the private URL / a manual wake keeps it awake during judging windows.

## Demo video script (60–90s)

1. **Hook (0–10s):** "This is AlphaGuard — a research agent that refuses to be impressed by a beautiful backtest."
2. **The ask (10–25s):** Type the strategy-validation task on `/`. Person + agent want to move a low-vol ETF rotation strategy to paper trading.
3. **The agent works (25–45s):** Show the 6-step trace — planner → inspect_dataset → run_backtest → audit_backtest → **apply_risk_gate: BLOCKED** → create_order_intent: SKIPPED. Emphasize the verdict badge.
4. **Why it matters (45–70s):** "The data is synthetic, so the gate says no — no ifs, no LLM override. The agent plans, but only deterministic rules decide." Cut to `/webmcp.json` showing a tool's `agent_safety` block.
5. **Who it's for (70–90s):** "Any agent that handles money should be forced to call auditable research and risk tools first." End card: repo + live URL.

## Devpost write-up checklist

- Title / subtitle (one-liner above).
- Built With: Python, FastAPI, Qwen (DashScope), pandas/numpy, WebMCP, Render.
- Attach: live URL, repo URL, demo video, screenshot of the `BLOCKED` verdict.
- Mention the guardrail design: *the agent can plan, never override the veto*.