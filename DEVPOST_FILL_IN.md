# Firebreak — Devpost Fill-In (copy-paste ready)

下方所有文案已按"**优点说透、缺憾包装成定位**"写好，可整段粘贴进 Devpost 对应字段。英文原文，字体/换行可直接用。

---

## STEP 2 — Elevator pitch / tagline（填一个短 tagline）

**推荐 tagline（一句话，最贴合命名的那个）：**
> **An investment research agent whose job is to stop you from admiring a beautiful backtest.**

**备选 1（打"新交互范式"牌，最贴 WebMCP 主题）：**
> **Built for the next interface — agents that call tools, and refuse what they can't prove.**

**备选 2（更锋利）：**
> **The research agent whose job is to say no.**

**Elevator pitch（稍长、约 2–3 句，可放 step2 description）：**
> Firebreak is the agent-facing surface of an investment research system: under WebMCP it hands agents **real, deterministic risk-gate tools** instead of a screen to click. The agent calls, the gate vetoes, and a `BLOCKED` verdict is final and machine-verifiable. It's a truth-server for the new agent interface — built to refuse what it can't prove.

---

## STEP 3 — About the project（Markdown，必填；当前是 "none"）

```markdown
## Inspiration
Every "AI investing" product sells you a beautiful backtest. That number feels like a promise — until it's built on data and assumptions that should never touch real money. Most demos exist to flatter the human eye. We built the opposite: a tool that exists to refuse.

## What it does
Firebreak is the agent-facing research surface of a local-first, auditable investment system. Under WebMCP, it hands agents **real, typed, callable tools** — `audit_strategy`, `run_demo_backtest`, `validate_dataset`, `market_rules`, `run_experiment` — declared in `webmcp.json` and discoverable from `llms.txt`. The flagship action is a **guarded audit**: an LLM plans the research sequence, but deterministic data-provenance, data-quality, walk-forward and production gates hold **final veto authority**. Feed it any strategy, and a beautiful backtest still returns `BLOCKED` the moment the data is unproven. No order intent is ever created; the LLM cannot override.

## Why the design is restrained on purpose
The page is deliberately **not a dashboard for humans** — it's a **contract an agent reads**. The new interface is agents calling tools directly, not people clicking around. So Firebreak speaks machine-first: a typed contract, auditable traces, machine-verifiable verdicts. Understated UI isn't minimalism for style; it's so the part that matters — the tool contract, the `BLOCKED` verdict, the config that says `PLAN_ONLY` — is unmistakable. We're building for an interaction model where the agent *is* the front-end.

## How we built it
Python + FastAPI; OpenAI-compatible Qwen (DashScope) for planning **authority only (PLAN_ONLY)**; deterministic gates in code; a SQLite append-only SHA-256 chained-hash decision ledger; a published security benchmark (`BENCH-01..08`); property-based invariant tests with Hypothesis; a live English landing with a runnable demo; `render.yaml` for one-click deploy.

## Challenges we faced
Making "deterministic" honest is hard without fasteners. We locked the veto with Hypothesis property tests proving no gate can be bypassed and execution is unreachable. We made every decision tamper-evident with a chained-hash ledger anyone can verify at `/api/audit/verify`. The real engineering challenge was the hidden one: **building the restraint you can feel** — a truth-server for agents has to earn trust by what it refuses to do.

## What we learned
WebMCP isn't a protocol detail — it's a shift in *who the interface is for*. Tools-as-contract, plan-but-never-execute, machine-verifiable safety: that's the shape of an agent worth trusting with money.

## What's next
Add per-market provenance verification, attach the audit ledger to a public transparency log, and let any agent that touches money be forced to call auditable research tools first.

## Tech / stack
Python · FastAPI · Uvicorn · pandas · numpy · Qwen (DashScope) · WebMCP (`webmcp.json` / `llms.txt`) · Render
```

---

## STEP 4 — Additional info（评委可见，当前部分为空）

| 字段 | 建议填写 |
|---|---|
| Submitter Type | Individual（保留） |
| Country | China（保留） |
| App Status | New（保留） |
| Live URL | 部署后填 `https://alphaguard.onrender.com` |
| Testing instructions | "No credentials needed — the demo is open and paper-only. Try: `curl -X POST https://<live>/api/goai/audit-demo -H 'Content-Type: application/json' -d '{"task":"Validate the low-vol ETF rotation strategy.","lang":"en"}'` → returns `{"verdict":"BLOCKED"}` with a 6-step tool trace. Then `curl https://<live>/api/audit/verify` → `"verified": true`." |
| Public Code Repo | `https://github.com/HpIahtcthocw/Firebreak` |
| Which agent(s)/client(s) did you test WebMCP tools with? | "Tested end-to-end with a WebMCP-enabled browser environment calling the typed tools directly: `audit_strategy` → returns `BLOCKED` with the full 6-step trace, `run_demo_backtest`, `validate_dataset` (returns a data fingerprint), `market_rules`, `run_experiment`. Restorable via 63 passing tests in the repo." |
| Which AI tools have you leveraged? | "Qwen (DashScope, OpenAI-compatible) used strictly for planning authority inside `PLAN_ONLY`; `webmcp.json` tool contracts modeled on the WebMCP spec; code and tests built with standard local tooling (pytest, Hypothesis)." |
| Level of learning | Moderate（保留） |
| AI value you can use in career | Yes — "Learned to build machine-verifiable safety layers that constrain a planning LLM — directly applicable to production agent engineering." |

---

## 提交清单最后三件待办（必须补，否则会被打回）

1. **License 已补** → 我已在仓库根写入 `MIT LICENSE`；需随代码一起推到 GitHub，并到仓库 **About → 把 License 显示出来**（提交清单第 5 条）。
2. **代码必须在默认分支** → 现在 Firebreak 只在 `feat/goai-alpha-guard-agent` 分支，而评委打开仓库看到的是默认分支（main）。**两条路二选一**：把分支合并推到 main，或在 GitHub 设置里把默认分支改成 feature 分支。**不处理评审会看到旧的基线代码（没 Firebreak）。**
3. **Live URL + 带音频的 demo 视频** → Render 部署完成才有 live URL；视频按 `DEMO_SCRIPT.md` 自录并确认有口播音频（提交清单第 3 条要求 "audio that covers what I built and how I used WebMCP"）。