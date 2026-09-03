/* Lightweight bilingual layer for Personal Investment OS.
 *
 * The public / international build is English by default. Local private use can
 * switch to Chinese. Instead of restringing the hand-built UI into t('key') calls,
 * this applies phrase-level English->Chinese translation over the rendered text
 * nodes, so it also covers content injected at runtime. Switching back to English
 * reloads the page (cheap) to restore the canonical source copy.
 */
(function (window, document) {
  "use strict";

  var LANG_KEY = "pio_lang";

  function readLang() {
    try { return localStorage.getItem(LANG_KEY) || "en"; } catch (_) { return "en"; }
  }
  var lang = readLang();

  /* English phrase -> Chinese. Keys match visible on-screen text (longer phrases
     first so phrase-pairs with substrings resolve to the more specific mapping). */
  var DICT = {
    /* ---- Brand / chrome ---- */
    "Personal Investment OS · Firebreak": "个人投资操作系统 · Firebreak",
    "Personal<br>Investment OS": "个人<br>投资操作系统",
    "Personal Investment OS": "个人投资操作系统",
    "Personal investment workbench": "个人投资工作台",
    "Investment OS": "投资操作系统",
    "Personal": "个人",
    "Workspace": "工作区",
    "My investment account": "我的投资账户",
    "Mode": "模式",
    "Paper trading": "纸面交易",
    "Settings & data sources": "设置与数据源",
    "Local data synced": "本地数据已同步",
    "Data source: checking": "数据源：检测中",
    "Data source: live feed configured": "数据源：已配置实时行情",
    "Data source: snapshot fallback (non-live)": "数据源：快照回退（非实时）",
    "Data source:": "数据源：",
    "Research environment": "研究环境",
    "Sat, Aug 8, 2026": "2026年8月8日 周六",
    "Sample account · CNY": "示例账户 · 人民币",
    "Import account": "导入账户",
    "Refresh data": "刷新数据",
    "Account menu": "账户菜单",

    /* ---- Navigation ---- */
    "Firebreak": "Firebreak",
    "Today": "今日",
    "Portfolio": "持仓",
    "Research": "研究",
    "Backtest": "回测",
    "Plans": "计划",

    /* ---- Landing ---- */
    "Enter the workspace →": "进入工作区 →",
    "Enter the workspace": "进入工作区",
    "Dream-proof investment research": "可防梦的投资研究",
    "A WebMCP action, not a chatbot": "一个 WebMCP 行动，而非聊天机器人",
    "The backtest looks": "回测看上去",
    "beautiful.": "非常漂亮。",
    "The strategy still doesn&rsquo;t trade.": "但策略仍然不会去交易。",
    "The LLM plans the study —": "LLM 只规划研究步骤——",
    "deterministic code gates veto anything that only looks good": "确定性代码门会否决一切“只是看起来不错”的结果",
    ". No order intent is ever written without passing every gate.": "。任何订单意图未经全部门禁通过都不会被写入。",
    "real actions": "个真实可调用行动",
    "automated tests": "项自动化测试",
    "LLM authority": "LLM 权限",
    "toggle evidence → watch the gate": "切换证据 → 观察门禁",
    "RESEARCH TASK": "研究任务",
    "Run guarded audit": "运行受保护审计",
    "Run guarded audit…": "运行受保护审计…",
    "Validate whether the low-volatility ETF rotation strategy has enough evidence to move from research to paper trading.": "验证低波 ETF 轮动策略是否有足够证据从研究阶段进入纸面交易。",
    "PLAN_ONLY authority": "仅计划权限",
    "Plan only, never execute": "只计划，绝不执行",
    "The model proposes the research sequence. It cannot modify risk rules, override a gate, or create an order intent.": "模型仅提出研究序列。它不能修改风控规则、不能绕过门禁、也不能创建订单意图。",
    "VETO > AGENT": "否决权 > 智能体",
    "Deterministic veto": "确定性否决",
    "code decides, not vibes": "代码决定，而非感觉",
    "Same engine, both sides: synthetic data gets blocked, production-eligible data can pass. The verdict is reproducible and property-tested.": "同一引擎、两种情形：合成数据被阻断，可投产数据能通过。结论可复现且经过属性测试。",
    "42 PROPERTY TESTS": "42 项属性测试",
    "Immutable ledger": "不可变账本",
    "chain-hashed receipts": "链式哈希凭证",
    "Every gate decision is appended to a chain-hashed audit log. You can re-read it — you can&rsquo;t quietly rewrite it.": "每一条门禁决策都被追加到链式哈希审计日志。你可以重读它——却无法悄悄改写它。",
    "AUDIT-LEDGER": "审计账本",
    "Research / procedural demo": "研究 / 流程演示",
    "not investment advice, no return promises, and it never places real orders. Deterministic gates hold final authority; no LLM can override them.": "非投资建议、不承诺收益，且绝不产生真实订单。确定性门禁拥有最终权威，任何 LLM 都无法覆盖。",
    "a WebMCP submission": "一个 WebMCP 参赛作品",
    "POST /api/goai/audit-demo": "POST /api/goai/audit-demo",
    "UNPROVEN": "未证明",
    "PROVEN": "已证明",
    "ORDER INTENT WRITTEN": "订单意图已写入",
    "ORDER INTENT — NOT CREATED": "订单意图 — 未创建",
    "No gate records": "无门禁记录",

    /* ---- Firebreak view ---- */
    "checking planner…": "检测规划器中…",
    "A backtest that looks great.": "一个看起来很棒的回测。",
    "Still, it refuses to trade.": "但它仍然拒绝交易。",
    "Firebreak validates evidence before deciding whether a strategy is eligible for paper trading. Agents can plan tools, but they cannot rewrite the risk gates.": "Firebreak 在判定策略是否具备纸面交易资格前，先验证证据。智能体可以规划工具，但不能改写风控门禁。",
    "Execution authority": "执行权限",
    "Deterministic gates hold final authority": "确定性门禁拥有最终权威",
    "Current audit task": "当前审计任务",
    "Low-vol ETF rotation strategy": "低波 ETF 轮动策略",
    "Submit to the research agent": "提交给研究智能体",
    "Tool scope": "工具范围",
    "Start evidence audit": "开始证据审计",
    "Runs real backtest tools · creates no order": "运行真实回测工具 · 不产生订单",
    "LIVE TOOL TRACE": "实时工具追踪",
    "Execution trace": "执行追踪",
    "not run yet": "尚未运行",
    "Understand task": "理解任务",
    "Qwen or rule planner": "Qwen 或规则规划器",
    "Inspect data": "检查数据",
    "source · integrity · fingerprint": "来源 · 完整性 · 指纹",
    "Run backtest": "运行回测",
    "strategy + three baselines": "策略 + 三个基准",
    "Audit stability": "审计稳定性",
    "out-of-sample · walk-forward": "样本外 · 滚动验证",
    "Risk gate": "风控门",
    "deterministic code decision": "确定性代码决策",
    "waiting": "等待中",
    "Waiting": "等待中",
    "Auditing": "审计中",
    "Done": "完成",
    "Blocked": "已阻断",
    "Failed": "失败",
    "Running": "运行中",
    "FINAL VERDICT · RISK GATE": "最终裁定 · 风控门",
    "BLOCKED": "已阻断",
    "PASSED": "已通过",
    "ELIGIBLE": "符合资格",
    "This trade — I refuse to execute it.": "这次交易——我拒绝执行。",
    "The backtest looks fine, but the evidence isn&rsquo;t credible enough.": "回测看起来不错，但证据可信度不足。",
    "ORDER INTENT": "订单意图",
    "NOT CREATED": "未创建",
    "CREATED": "已创建",
    "Agents cannot bypass the gates": "智能体无法绕过门禁",
    "AUDIT EVIDENCE": "审计证据",
    "Not an opinion — a run result": "不是观点——是运行结果",
    "Out-of-sample return": "样本外收益",
    "not future performance": "并非未来表现",
    "Out-of-sample drawdown": "样本外回撤",
    "computed by backtest engine": "由回测引擎计算",
    "Walk-forward": "滚动验证",
    "rolling validation window": "滚动验证窗口",
    "Data fingerprint": "数据指纹",
    "reproducible experiment input": "可复现的实验输入",
    "HARD GATES": "硬性门禁",
    "Why it was blocked": "为何被阻断",
    "THE RECEIPTS": "凭证",
    "Expand the full agent trace": "展开完整智能体追踪",
    "View raw evidence": "查看原始证据",
    "Research / procedural demo only — not investment advice, and does not represent real returns.": "仅作研究 / 流程演示——非投资建议，也不代表真实收益。",
    "Re-run evidence audit": "重新运行证据审计",
    "Running evidence audit…": "正在运行证据审计…",
    "Describe the strategy to audit in one complete sentence.": "请用一句完整的话描述要审计的策略。",
    "Audit complete: risk gate blocked order-intent creation.": "审计完成：风控门阻断了订单意图创建。",
    "Audit incomplete:": "审计未完成：",
    "Audit failed": "审计失败",
    "Clear-marked synthetic data": "明确标注的合成数据",
    "Clearly-marked synthetic data": "明确标注的合成数据",

    /* ---- Today view ---- */
    "Weekend review": "周末回顾",
    "Risk first, opportunity second.": "风险第一，机会第二。",
    "The system puts today&rsquo;s three most important items here. All figures come from local sample data.": "系统把今日最重要的三件事放在这里。所有数字均来自本地示例数据。",
    "Log an idea": "记录想法",
    "Review pending plans": "审阅待处理计划",
    "Portfolio value": "组合市值",
    "year-to-date": "今年以来",
    "Cash ratio": "现金占比",
    "ample liquidity": "流动性充裕",
    "comfort zone": "舒适区",
    "Portfolio drawdown": "组合回撤",
    "near watch line": "接近警戒线",
    "watch line -5%": "警戒线 -5%",
    "current": "当前",
    "Needs your call": "需要你决策",
    "Today&rsquo;s three cards": "今日三张卡片",
    "All plans →": "全部计划 →",
    "CSI 300 ETF needs rebalancing": "沪深300 ETF 需要再平衡",
    "Deviation": "偏离",
    "Current weight is 34.8%, above the 30% cap. If it stays above the cap at next week&rsquo;s open, the system suggests two separate adjustments.": "当前权重 34.8%，高于 30% 上限。若下周开盘仍高于上限，系统建议分两次调整。",
    "Rule: target-weight drift": "规则：目标权重漂移",
    "Impact: medium": "影响：中等",
    "View plan": "查看计划",
    "Backtest results must pass the audit first": "回测结果必须先通过审计",
    "Research flow": "研究流程",
    "The system runs the strategy against buy-and-hold, equal-weight and trend baselines, and surfaces out-of-sample performance, data quality and costs together.": "系统将策略与买入持有、等权和趋势基准对比，并一起呈现样本外表现、数据质量与成本。",
    "Needs: real-data backtest": "需要：真实数据回测",
    "Status: awaiting data": "状态：等待数据",
    "Open report": "打开报告",
    "Portfolio risk stays within bounds": "组合风险处于边界之内",
    "No action": "无需操作",
    "Sector concentration, single-name exposure and the cash ratio all pass the gates. The only thing to watch: tech exposure is up 4.2% vs last month.": "行业集中度、单一标的暴露和现金占比均通过门禁。唯一要注意：科技板块暴露较上月上升 4.2%。",
    "Last check: today 09:30": "上次检查：今日 09:30",
    "Status: passed": "状态：通过",
    "View portfolio": "查看持仓",
    "Quick brief": "快速简报",
    "Portfolio temperature": "组合温度",
    "Stable": "稳定",
    "Steady with upside": "稳中有升",
    "No hard risk gate was triggered. The most important action right now is to confirm the rebalance plan — not to hunt for a new trade.": "没有触发任何硬性风险门。当前最重要的动作是确认再平衡计划——而非寻找新交易。",
    "Stocks / ETFs": "股票 / ETF",
    "Cash": "现金",
    "System note: model opinion never auto-mutates your portfolio.": "系统提示：任何模型观点都不会自动改动你的组合。",
    "Evidence summary": "证据摘要",
    "What the last decision left behind": "上一次决策留下了什么",
    "Fact": "事实",
    "CSI 300 ETF volatility fell over the past 20 days": "过去 20 天沪深300 ETF 波动率回落",
    "Source: local quote snapshot · as of Jul 31": "来源：本地报价快照 · 截至7月31日",
    "Judgment": "判断",
    "Don&rsquo;t chase; wait for weight to return to target.": "不要追高；等待权重回到目标。",
    "Recorded by: me · Confidence: medium": "记录人：我 · 置信度：中等",
    "Unknown": "未知",
    "Next week&rsquo;s open slippage on execution": "下周开盘的执行滑点",
    "Needs to keep being observed in paper trading": "需在纸面交易中持续观察",
    "Open decision log": "打开决策日志",
    "This is an investment journal and research tool — not investment advice. Sample-account figures are for demonstrating the UI and do not represent real returns.": "这是一个投资日志与研究工具——非投资建议。示例账户数字仅用于展示界面，不代表真实收益。",

    /* ---- Portfolio view ---- */
    "Portfolio overview": "持仓概览",
    "Where is your capital now?": "你的资本现在哪里？",
    "Understand exposure before discussing returns. Every holding can be traced back to the transaction log.": "在讨论收益前先了解暴露。每笔持仓都能追溯到交易日志。",
    "+ Add a record": "+ 添加记录",
    "Holdings": "持仓",
    "positions · ¥": "个持仓 · ¥",
    "Sample data": "示例数据",
    "Symbol": "代码",
    "Value": "市值",
    "Weight": "权重",
    "Daily": "日涨跌",
    "Status": "状态",
    "High": "偏高",
    "OK": "正常",
    "Watch": "关注",
    "Risk exposure": "风险暴露",
    "Concentration at a glance": "集中度一览",
    "Risk assets": "风险资产",
    "Broad index": "宽基指数",
    "Thematic": "主题",
    "Overseas": "海外",
    "Concentration: passed. Thematic assets stay under the 20% cap.": "集中度：通过。主题资产保持在 20% 上限以内。",

    /* ---- Research view ---- */
    "Research workbench": "研究工作台",
    "Turn &ldquo;I think&rdquo; into a falsifiable question.": "把“我觉得”转化为可证伪的问题。",
    "You don&rsquo;t need to learn quant first. The system starts from hypothesis, evidence and invalidation conditions.": "你不需要先学会量化。系统从假设、证据和证伪条件出发。",
    "+ New research card": "+ 新建研究卡片",
    "My research": "我的研究",
    "Active & completed": "进行中与已完成",
    "All": "全部",
    "Active": "进行中",
    "Done": "完成",
    "Awaiting audit": "等待审计",
    "Low-vol ETF rotation": "低波 ETF 轮动",
    "When market volatility rises, can low-vol ETF rotation cut portfolio drawdown while keeping most of the upside?": "当市场波动上升时，低波 ETF 轮动能否在保留大部分上涨的同时降低组合回撤？",
    "Progress": "进度",
    "Next: read the backtest audit": "下一步：阅读回测审计",
    "Open research": "打开研究",
    "Is the dividend factor still working?": "红利因子还有效吗？",
    "Over the past 10 years, has a high-dividend, low-volatility mix offered enough risk compensation?": "过去十年，高股息低波组合是否提供了足够的风险补偿？",
    "Next: confirm the data range": "下一步：确认数据范围",
    "Continue editing": "继续编辑",
    "Research guide": "研究指南",
    "Every card answers four questions": "每张卡片回答四个问题",
    "What do you expect to happen?": "你预期发生什么？",
    "Write it as one sentence that data could falsify.": "用一句能被数据证伪的话写下来。",
    "Why might it happen?": "为什么会发生？",
    "Write the economic intuition — not just indicators.": "写出经济直觉——而不只是指标。",
    "When would it be wrong?": "何时会错？",
    "Define the invalidation condition up front.": "事先定义证伪条件。",
    "What&rsquo;s next?": "下一步是什么？",
    "Backtest first, paper-trade next, execute only last.": "先回测，再纸面交易，最后才实盘。",
    "AI can help you organize and challenge, but it never defines risk for you.": "AI 能帮你整理与质询，但永远不会替你定义风险。",

    /* ---- Backtest view ---- */
    "Strategy backtest": "策略回测",
    "See how it fails first.": "先看它如何失败。",
    "Backtest results aren&rsquo;t a promise. We surface drawdown, cost and the invalidation zone up front.": "回测结果不是承诺。我们前置呈现回撤、成本和证伪区间。",
    "Run synthetic audit demo": "运行合成审计演示",
    "Awaiting dataset": "等待数据集",
    "Backtest not run yet": "回测尚未运行",
    "Robustness score": "稳健性评分",
    "No score without a run": "未运行则无评分",
    "Awaiting audit": "等待审计",
    "Not certified": "未认证",
    "Not a return promise": "并非收益承诺",
    "Strategy equity": "策略净值",
    "Benchmark equity": "基准净值",
    "No return figures until a result exists": "产生结果前无收益数字",
    "Annualized return": "年化收益率",
    "Max drawdown": "最大回撤",
    "Computed by the engine": "由引擎计算",
    "Volatility": "波动率",
    "Sharpe": "夏普",
    "Trading cost": "交易成本",
    "sessions": "个交易日",
    "Trade days": "交易天数",
    "Synthetic demo data: not a representation of real returns.": "合成演示数据：不构成真实收益。",
    "User-data backtest: results apply to this data snapshot only.": "用户数据回测：结果仅适用于该数据快照。",
    "Data quality check passed.": "数据质量检查通过。",
    "Import or submit price data; the synthetic demo only validates the engine and does not represent real returns.": "导入或提交价格数据；合成演示仅验证引擎，不代表真实收益。",
    "PIO-EXP-001 done: review out-of-sample, baseline, and gate results first.": "PIO-EXP-001 完成：请先查看样本外、基准和门禁结果。",
    "Running…": "运行中…",

    /* ---- Plans view ---- */
    "Trading plans": "交易计划",
    "Write the risk down before you decide.": "决策前先把风险写下来。",
    "There is no &ldquo;one-click buy&rdquo; here. Every plan passes rule checks plus your confirmation.": "这里没有“一键买入”。每个计划都要通过规则检查并得到你的确认。",
    "+ Create plan": "+ 创建计划",
    "Pending": "待处理",
    "2 plans need your call": "2 个计划需要你决策",
    "Paper": "纸面",
    "Rebalance": "再平衡",
    "valid until": "有效期至",
    "Lower the CSI 300 ETF weight": "降低沪深300 ETF 权重",
    "Current": "当前",
    "Target": "目标",
    "Why now?": "为什么现在？",
    "Current weight exceeds your 30% cap. Two separate adjustments are suggested to avoid one-shot price slippage.": "当前权重超过你 30% 的上限。建议分两次调整以避免一次性价格冲击。",
    "Data fresh": "数据新鲜",
    "Concentration ok": "集中度正常",
    "Needs manual review": "需要人工复核",
    "View evidence": "查看证据",
    "Approve paper plan": "批准纸面计划",
    "Watch": "关注",
    "No adds to STAR 50 ETF": "不再加仓科创50 ETF",
    "Current weight": "当前权重",
    "hold": "持有",
    "The backtest shows win rates drop when adding above 28% volatility; the metric hasn&rsquo;t returned to the comfort zone.": "回测显示：波动率高于 28% 时加仓胜率下降；该指标尚未回到舒适区。",
    "Risk boundary clear": "风险边界清晰",
    "Awaiting new data": "等待新数据",
    "Remind me later": "稍后提醒我",
    "Risk gates": "风控门",
    "Check before acting": "行动前先检查",
    "Data freshness": "数据新鲜度",
    "Latest snapshot: 2026-07-31": "最新快照：2026-07-31",
    "Passed": "通过",
    "Portfolio concentration": "组合集中度",
    "Largest single weight: 34.8%": "最大单一权重：34.8%",
    "Manual confirmation": "人工确认",
    "Paper orders require per-trade confirmation": "纸面订单需要逐笔确认",
    "Live execution": "实盘执行",
    "Disabled in the current environment": "当前环境已禁用",
    "Locked": "已锁定",
    "Risk gates can stop a plan, but they never decide for you.": "风控门可以叫停一个计划，但绝不替你决策。",
    "Filled": "已成交",
    "Simulated fill done": "模拟成交完成",
    "Checking risk…": "正在检查风险…",
    "Recording approval…": "正在记录批准…",
    "Simulating fill…": "正在模拟成交…",
    "Import account holdings first": "请先导入账户持仓",
    "Local ledger service not running": "本地账本服务未运行",
    "Risk gate rejected:": "风控门拒绝：",
    "Failed to create order intent": "订单意图创建失败",
    "Approval failed": "批准失败",
    "Simulation failed": "模拟失败",
    "Backtest failed": "回测失败",
    "Switched to the": "已切换到",
    "view.": "视图。",
    "Reminder moved to the next trading day.": "提醒已移至下一个交易日。",
    "Evidence panel coming up: source, hypothesis and invalidation conditions.": "证据面板即将呈现：来源、假设与证伪条件。",
    "This is a prototype entry; next step wires it to the local ledger and structured forms.": "这是原型入口；下一步将接入本地账本与结构化表单。",
    "Local sample data refreshed; no external account connected.": "本地示例数据已刷新；未连接外部账户。",
    "Syncing…": "同步中…",
    "Paper fill done:": "纸面成交完成：",
    "This plan already executed; idempotency guard blocked a duplicate fill.": "该计划已执行；幂等保护阻止了重复成交。",
    "Question Loupe": "搜索放大镜",
    "query…": "提问…",
    "Value": "市值",
    "value": "价值",
    "Buy & hold": "买入持有",
    "FOLDS": " 次滚动验证",
    " blocked": " 已阻断",
    "$1": "$1"
  };

  var HTML_ENT = { "&rsquo;": "’", "&lsquo;": "‘", "&ldquo;": "“", "&rdquo;": "”", "&amp;": "&", "&nbsp;": " ", "&mdash;": "—", "&ndash;": "–" };
  function decodeHtmlEnt(s) {
    return String(s).replace(/&(rsquo|lsquo|ldquo|rdquo|amp|nbsp|mdash|ndash);/g, function (m, e) { return HTML_ENT["&" + e + ";"] || m; });
  }

  // longest keys first so e.g. "Portfolio value" wins over the nav "Portfolio"
  var DICT_KEYS = Object.keys(DICT).sort(function (a, b) { return b.length - a.length; });

  function tr(s) {
    if (lang !== "zh" || s == null) return s;
    var out = String(s);
    for (var i = 0; i < DICT_KEYS.length; i++) {
      var key = DICT_KEYS[i];
      if (out.indexOf(key) >= 0) { out = out.split(key).join(DICT[key]); continue; }
      // entity forms (e.g. doesn&rsquo;t) won't match decoded text nodes; try the decoded key
      var dk = decodeHtmlEnt(key);
      if (dk !== key && out.indexOf(dk) >= 0) out = out.split(dk).join(DICT[key]);
    }
    return out;
  }

  function applyTranslate(rootNode) {
    var root = rootNode || document.body;
    if (!root) return;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        var parent = node.parentNode;
        // skip script/style/textarea/input text
        if (parent && /SCRIPT|STYLE|TEXTAREA|INPUT|CODE|PRE/.test(parent.tagName || "")) return NodeFilter.FILTER_REJECT;
        return node.nodeValue && node.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    var node;
    while ((node = walker.nextNode())) {
      node.nodeValue = tr(node.nodeValue);
    }
    // placeholders
    var holders = (root === document.body ? document : root).querySelectorAll
      ? (root === document.body ? document : root).querySelectorAll("[placeholder]") : [];
    for (var i = 0; i < holders.length; i++) {
      if (lang === "zh" && !holders[i].getAttribute("data-pio-ph")) holdMark(holders[i]);
      var holder = holders[i];
      var saved = holder.getAttribute("data-pio-ph");
      if (saved != null) holder.setAttribute("placeholder", lang === "zh" ? tr(saved) : saved);
    }
    // textarea default values (only once, before user edits)
    if (root === document.body || root === document) {
      var areas = document.querySelectorAll("textarea[data-pio-va]");
      for (var j = 0; j < areas.length; j++) {
        if (lang === "zh") areas[j].value = tr(areas[j].getAttribute("data-pio-va"));
        else areas[j].value = areas[j].getAttribute("data-pio-va");
      }
    }
    updateToggle();
  }

  function holdMark(el) { if (!el.getAttribute("data-pio-ph")) el.setAttribute("data-pio-ph", el.getAttribute("placeholder")); }

  var toggleBtn;
  function updateToggle() {
    if (!toggleBtn) {
      toggleBtn = document.getElementById("langToggle");
      if (!toggleBtn) return;
      toggleBtn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        setLang(nextLang());
      });
    }
    toggleBtn.textContent = lang === "zh" ? "EN" : "中文";
    toggleBtn.setAttribute("aria-label", lang === "zh" ? "Switch to English" : "切换到中文");
  }

  function nextLang() { return lang === "zh" ? "en" : "zh"; }

  function setLang(next) {
    lang = next;
    try { localStorage.setItem(LANG_KEY, lang); } catch (_) {}
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    if (lang === "zh") {
      // first-time markers for textarea defaults
      var areas0 = document.querySelectorAll("textarea");
      for (var i = 0; i < areas0.length; i++) {
        if (!areas0[i].getAttribute("data-pio-va") && areas0[i].value.trim()) areas0[i].setAttribute("data-pio-va", areas0[i].value);
      }
      applyTranslate();
      window.PIOLang = lang;
      try { window.dispatchEvent(new CustomEvent("pio:lang", { detail: { lang: lang } })); } catch (_) {}
    } else {
      // restore canonical English source
      window.location.reload();
    }
  }

  // public hooks
  window.PIOLang = lang;
  window.PIOtr = tr;
  window.PIOApplyI18n = function (root) { if (lang === "zh") applyTranslate(root); };
  window.PIOSetLang = setLang;

  // always mount the toggle (button is already parsed when i18n.js runs)
  updateToggle();

  // translate once the initial DOM is ready (after all sync scripts have run)
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      if (lang === "zh") applyTranslate();
    });
  } else {
    if (lang === "zh") applyTranslate();
  }
})(window, document);