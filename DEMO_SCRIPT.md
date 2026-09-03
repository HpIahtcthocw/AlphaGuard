# AlphaGuard — Self-Recordable Demo Script (60–90s)

> 这份脚本设计成**你一个人照着就能录完**：一个 1920×1080 浏览器窗口、一台录屏（OBS / QuickTime / Windows 录屏都行）、口播提前放旁边照着念即可。全程只有 5 个镜头，真实操作、无绿幕无剪辑依赖，切点都用"停 1 秒再点"来兜底。

---

## 0. 录制前 5 分钟准备（照做）

1. **固定视口**：浏览器窗口手动拉满到无滚动条的宽度（推荐 1280–1440 宽），刷新 `/`。
2. **预先输入任务文本**：光标停在 task 输入框，但**先不点 Run**。
   - 任务文本（照打）：`Validate the low-volatility ETF rotation strategy. Anything that passes without REAL market data should be blocked.`
3. **准备好第二屏**：开一个浏览器标签已打开 `[你的URL]/webmcp.json`，备用；剪贴板里放 `/api/goai/audit-demo`。
4. **口播**：把下方每镜头 VO 打印出来放旁边。不用背，对着念即可，语速放慢，念错就重录该镜头（镜头之间本来就有切点）。
5. **录制设置**：60fps、音量先测一下、画质 1080p 起。结束一次录完所有镜头再剪，别逐镜头保存。

---

## 1. 镜头总览（先看这页，再往下逐段录）

| # | 时长 | 画面 | 口播要点 | 切点 |
|---|---|---|---|---|
| S1 | 0–8s | `/` 首屏 Hero | "不是给人类看的UI，是给Agent的真相" | Hero 出现后停 1s |
| S2 | 8–20s | 输入框 + 点 Run + 转菊花 | 人和 Agent 一起验证策略 | 结果刷出前切 |
| S3 | 20–38s | **裁决卡 + 6步trace**（slowmo 到第5步） | 数字很漂亮，闸门仍 BLOCKED | "BLOCKED"定格 2s |
| S4 | 38–55s | 切到 `/webmcp.json` policy + agent_safety | 工具契约 / PLAN_ONLY / 绕不过 | 滚动到 policy 段停下 |
| S5 | 55–90s | 回到 `/` 收尾 + 卡片 | 任何管钱的 Agent 都该先过这道闸 | 收尾淡出 |

---

## 2. 逐镜头脚本（照此录）

### S1 — 首屏反转陈述（0–8s）
**画面**：`/` 首屏完整露出，端庄克制的排版、盾牌 logo、`// agent-safe. no auto-execution. auditable.`。
**手感**：无需点击。录 5–6 秒静止，给画面呼吸感。
**VO（英文，5–6 词/秒）**：
> "Most AI investing demos are screens to impress a human eye. This one deliberately isn't."
> （这里停半拍）"AlphaGuard is the *machine-facing* layer — a tool contract an agent calls, not a dashboard to ooh over. It says *less*, on purpose: because the agent needs the truth, not the pretty."

**叙事落点**：把"不炫"说成"不给你看的UI"——第一句就破题。

### S2 — 人与 Agent 一起发问（8–20s）
**画面**：光标进入 task 输入框 → 粘贴任务文本 → 点击 primary 按钮 `Run a real audit` → 出现加载态。
**手感**：粘贴后让文本可见 1 秒再点；点完立即把画面留给转菊花（别动鼠标）。
**VO**：
> "A person and their agent ask the same question: 'Can we move this low-vol rotation strategy to paper trading?' The agent answers by *calling real tools* — not by clicking around a website."

### S3 — 裁决时刻（核心镜头，20–38s）
**画面**：结果卡刷出，红色 `BLOCKED` 徽标 + 徽标旁盾牌叉；下面 6 步 trace 逐行落下。
**关键手法**：**第 5 步 `apply_risk_gate → BLOCKED` 序号框是红色**，比其余步骤扎眼——鼠标指针轻轻停在它上面 1–2 秒，别点。
**VO**（读到这里放慢、加重）：
> "The metrics look great — any human sales pitch would win on this number. But the deterministic gate still returns *BLOCKED*."
> （指着第 5 步，停顿）"Watch step five: `apply_risk_gate` fires its veto. And the next step, `create_order_intent`, is **SKIPPED** — not approved, skipped."

**叙事落点**：把"哪个数字漂亮"和"哪一步被拦"并列，制造反差点。这是全片记忆点。

### S4 — 切证明：工具契约（38–55s）
**画面**：切到 `/webmcp.json`，滚到 `policy` 和某个工具的 `agent_safety` 块（`PLAN_ONLY` / `deterministic_veto` / `order_creation: NEVER`）。
**手感**：从顶部 `"tools": [` 慢慢往下滚，到 `policy` 段速度变缓，指尖停 1s。
**VO**：
> "Here's the part a human UI would hide. Each tool carries its safety contract: authority is `PLAN_ONLY`, orders are `NEVER`. The LLM can *plan* — it can never *override*. That's why `BLOCKED` is final."

### S5 — 谁该用它（55–90s）
**画面**：回到 `/` 首屏，画面整体淡出或在下方露出产品名。
**手感**：静止 4–5 秒收尾，配结束卡。
**VO**：
> "Any agent that touches money should be forced to call auditable research and risk tools *first*. AlphaGuard is that gate — plan freely, execute only with proof. Try it live; feed it a beautiful backtest and watch it say no." →（淡出）"AlphaGuard. The refusal is the feature."

**结束卡文字**：`AlphaGuard — the refusal is the feature. [repo] · [live]`

---

## 3. 一条过录制小抄（不想剪就照这个顺序一口气录）

> 优点：零剪辑复杂度；缺点：VO 得一次念顺。适用于「求快省事」。

准备：任务文本已粘贴未运行 + 浏览器已开两个标签（`/` 与 `/webmcp.json`）。

1. 对着 `/` 首屏念 S1 VO（5–6s）。
2. 点 Run，念 S2 VO，等结果刷出（8–20s 段）。
3. 结果出来后念 S3 VO，一句对一屏，放慢到第 5 步。
4. 念到哪句"这里有个部分人类UI会藏起来"时，切标签到 `/webmcp.json`，补 S4 VO。
5. 记录到结束语，`Alt+Tab` 切回 `/` 对着首屏念 S5 结尾，收。

---

## 4. 剪辑清单（可选，做了更加分）

- [ ] 关键帧：`BLOCKED` 徽标出现那 1–2 帧稍微停留或轻缩放（150–200ms）。
- [ ] S3 第 5 步 BLOCKED + 第 6 步 SKIPPED，各加一个短暂高亮框。
- [ ] 全程去掉鼠标抖动；指针只在需要指的时候动。
- [ ] 字幕加在底部（口播与字幕同步）。
- [ ] 导出 1080p / 30fps，文件名 `alpha-guard-demo.mp4`。

---

## 5. 叙事一句话（任何地方都能复用）

> **"It's not a pretty screen for a human — it's a truth-server for an agent. The design is restraint on purpose: an agent reading `PLAN_ONLY` should *feel* how little power it has, and a human reading `BLOCKED` should trust it."**

把这一句放进：demo 开场、Devpost 描述里"The idea"段首、pitch 的电梯间 30 秒版。