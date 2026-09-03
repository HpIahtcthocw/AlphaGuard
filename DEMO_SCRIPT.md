# Firebreak — WebMCP-Compliant Demo Script (≤90s, 单人可录)

> 本版按 WebMCP Challenge 官方验收逐条约束改写：
> - **15 秒内展示项目在运行**（S1→S2 压缩，BLOCKED 结果在 ~12s 落地）
> - **无实时打字**（任务文本提前粘贴好，只点不敲）
> - **≤3 分钟**（全片 75–90s）
> - **人机协作体验**（新增第 4 步"人类保留最终权力"一拍，把"否决=人在回路里"讲成协作而非旁观）
> - **模块化**（每镜头一段短视频，可单独返录、跳剪）
> - **必须有音频**（口播报 VO，绝不止 BGM）

---

## 0. 录制前 5 分钟

1. 浏览器窗口锁到 1280–1440 宽、无滚动条，打开 `/`。
2. **任务文本已粘贴进输入框**（只贴不敲，避免实时打字）：
   `Validate the low-volatility ETF rotation strategy. Anything that passes without REAL market data should be blocked.`
3. 第二标签已打开 `[你的URL]/webmcp.json`；剪贴板放 `/api/goai/audit-demo`。
4. VO 打印放一旁，对着念，念错就返录该镜头。

---

## 1. 镜头总览（15s 钩子结构）

| # | 时长 | 画面 | 口播要点 | 切点 |
|---|---|---|---|---|
| S1 | 0–6s | `/` 首屏 Hero | "不是给你看的UI，是给Agent的真相" | 停 0.5s |
| S2 | 6–14s | **点 Run → 结果即刷出 BLOCKED** | 一次调用、一个否决，12 秒见真章 | BLOCKED 定格 1.5s |
| S3 | 14–28s | **裁决卡 + 6步trace**（slowmo 第5步） | 数字漂亮，闸门照样 BLOCKED；第6步 SKIPPED | 第5步红框停 2s |
| S4 | 28–44s | 回到 trace 末尾 **approval gate** | "人在回路里，最终权力在人"（人机协作） | 高亮审阅框 |
| S5 | 44–60s | 切 `/webmcp.json` policy + agent_safety | 工具契约 / PLAN_ONLY / 绕不过 | 滚到 policy 停下 |
| S6 | 60–75s | 回到 `/` 收尾 | 任何管钱的 Agent 都先过这道闸 | 淡出 |

---

## 2. 逐镜头脚本（照此录，每镜头单独成一段短视频）

### S1 — 首屏反转（0–6s）
**画面**：`/` 完整露出，盾牌 logo、`// agent-safe. no auto-execution. auditable.`。
**VO**：
> "Most AI investing demos are a screen to impress a human. This one deliberately isn't — it's the machine-facing contract an agent calls."

### S2 — 15 秒见真章（6–14s）
**画面**：直接点 primary 按钮 `Run a real audit`（任务已贴好，不敲键盘）→ 转菊花 ≤1s → 结果卡刷出，红色 `BLOCKED` 徽标。
**VO**：
> "A person and their agent ask the same question. The agent answers by calling real tools — one call — and the deterministic gate says no."

**验收点**：这一段落在全片前 15 秒内，满足"15 秒内展示在运行"。

### S3 — 裁决时刻（14–28s）
**画面**：6 步 trace 逐行落下，第 5 步 `apply_risk_gate → BLOCKED` 序号框红色，第 6 步 `create_order_intent → SKIPPED` 琥珀色。指针轻停第 5 步 2s。
**VO**（放慢、加重）：
> "The metrics look great — any sales pitch would win on that number. But step five fires its veto, and the order intent is **SKIPPED**, not approved. Nothing is auto-executed."

### S4 — 人在回路里（28–44s）★人机协作补强
**画面**：滚动/提示 trace 区下方或右侧"Approval"区：显示"final authority holds with the human"、order_intent 旁标 `awaiting human approval`。
**VO**：
> "Here's the collaboration. The agent plans, the gate vetoes, and the *human* keeps final authority. That's the whole design between the two of them — an agent that proposes, a person who disposes."

**叙事落点**：把"否决"包装成**人机共治**，正面回应"human-agent experience"评分项。

### S5 — 切证明：工具契约（44–60s）
**画面**：切 `/webmcp.json`，慢滚到 `policy` + 某工具 `agent_safety`（`PLAN_ONLY` / `deterministic_veto` / `order_creation: NEVER`）。
**VO**：
> "Here's the part a human UI would hide. Every tool carries its safety contract: authority `PLAN_ONLY`, orders `NEVER`. The LLM can plan — it can never override. That's why `BLOCKED` is final."

### S6 — 谁该用它（60–75s）
**画面**：回 `/` 首屏，静止收尾，露出产品名。
**VO**：
> "Any agent that touches money should be forced to call auditable research and risk tools first. Firebreak is that gate — plan freely, execute only with proof. Feed it a beautiful backtest and watch it say no."
> （停）"Firebreak. The refusal is the feature."

**结束卡**：`Firebreak — the refusal is the feature. [repo] · [live]`

---

## 3. 模块化录制清单（每镜头 = 一个短片，便于返录/跳剪）

- [ ] 分别录 S1..S6 六段（每段 8–16s），各自可重录，不必一次念全。
- [ ] S2 单独确认"15 秒内出 BLOCKED"；若加载超 2s，剪掉转菊花（跳剪）。
- [ ] 全程零打字（只有粘贴好的文本 + 点击）。
- [ ] 加底部字幕（口播同步）。
- [ ] 导出 1080p / 30fps，`alpha-guard-demo.mp4`，总长 ≤90s。

---

## 4. 叙事一句话

> **"It's not a pretty screen for a human — it's a truth-server for an agent. The restraint is the design: an agent reading `PLAN_ONLY` feels how little power it has, a human reading `BLOCKED` keeps final authority."**

放进：demo 开场、Devpost "The idea"段首、30 秒 pitch。