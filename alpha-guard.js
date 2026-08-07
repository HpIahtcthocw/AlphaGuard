(function () {
  const runButton = document.getElementById('runAlphaGuardButton');
  const taskInput = document.getElementById('alphaTaskInput');
  const resultPanel = document.getElementById('alphaResult');
  const errorPanel = document.getElementById('alphaError');
  const plannerPill = document.getElementById('alphaPlannerPill');
  const traceRows = [...document.querySelectorAll('[data-alpha-step]')];
  let progressTimer;

  if (!runButton || !taskInput || !resultPanel) return;

  const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
  const percent = (value) => value == null ? '—' : `${(Number(value) * 100).toFixed(2)}%`;

  function setPlannerPill(label, isQwen) {
    plannerPill.textContent = label;
    plannerPill.classList.toggle('qwen', Boolean(isQwen));
  }

  async function loadPlannerStatus() {
    try {
      const response = await fetch('/api/health');
      if (!response.ok) return;
      const health = await response.json();
      const planner = health.goai_planner;
      if (!planner) return;
      setPlannerPill(
        planner.configured ? `Qwen 就绪 · ${planner.model}` : '规则演示 · Qwen Key 未配置',
        planner.configured,
      );
    } catch (_) {
      setPlannerPill('离线规则演示', false);
    }
  }

  function resetTrace() {
    clearInterval(progressTimer);
    traceRows.forEach((row) => {
      row.classList.remove('running', 'completed', 'blocked');
      row.querySelector('b').textContent = '等待';
    });
    document.getElementById('alphaRunId').textContent = '运行中';
  }

  function setTraceState(index, state, label) {
    const row = traceRows[index];
    if (!row) return;
    row.classList.remove('running', 'completed', 'blocked');
    row.classList.add(state);
    row.querySelector('b').textContent = label;
  }

  function startTraceProgress() {
    let activeIndex = 0;
    setTraceState(activeIndex, 'running', '执行中');
    progressTimer = setInterval(() => {
      if (activeIndex >= traceRows.length - 1) return;
      setTraceState(activeIndex, 'completed', '完成');
      activeIndex += 1;
      setTraceState(activeIndex, 'running', '执行中');
    }, 340);
  }

  async function finishTrace(data) {
    clearInterval(progressTimer);
    for (let index = 0; index < traceRows.length; index += 1) {
      const trace = data.trace[index];
      const blocked = trace?.status === 'BLOCKED';
      setTraceState(index, blocked ? 'blocked' : 'completed', blocked ? '阻断' : '完成');
      await sleep(70);
    }
  }

  function renderGates(checks) {
    const list = document.getElementById('alphaGateList');
    list.replaceChildren();
    checks.forEach((check) => {
      const blocked = check.status === 'BLOCKED';
      const item = document.createElement('div');
      item.className = `alpha-gate-item${blocked ? ' blocked' : ''}`;

      const mark = document.createElement('span');
      mark.className = 'alpha-gate-mark';
      mark.textContent = blocked ? '×' : '✓';

      const copy = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = check.label;
      const detail = document.createElement('small');
      detail.textContent = check.detail;
      copy.append(title, detail);

      const status = document.createElement('b');
      status.textContent = blocked ? '阻断' : '通过';
      item.append(mark, copy, status);
      list.append(item);
    });
    const blockedCount = checks.filter((check) => check.status === 'BLOCKED').length;
    document.getElementById('alphaGateCount').textContent = `${blockedCount} / ${checks.length} 阻断`;
  }

  function renderReceipts(trace) {
    const list = document.getElementById('alphaReceiptList');
    list.replaceChildren();
    trace.forEach((step) => {
      const item = document.createElement('div');
      item.className = 'alpha-receipt-item';

      const index = document.createElement('span');
      index.textContent = String(step.sequence).padStart(2, '0');
      const copy = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = step.title;
      const summary = document.createElement('p');
      summary.textContent = step.summary;
      copy.append(title, summary);
      const evidence = document.createElement('code');
      evidence.textContent = JSON.stringify(step.evidence, null, 2);
      item.append(index, copy, evidence);
      list.append(item);
    });
  }

  function renderResult(data) {
    const outOfSample = data.evidence.backtest.out_of_sample;
    const dataset = data.evidence.dataset;
    const checks = data.evidence.risk_gate.checks;

    document.getElementById('alphaRunId').textContent = data.run_id;
    document.getElementById('alphaVerdict').textContent = data.verdict;
    document.getElementById('alphaHeadline').textContent = data.headline;
    document.getElementById('alphaSummary').textContent = data.summary;
    document.getElementById('alphaOrderStatus').textContent = data.order_intent_created ? 'CREATED' : 'NOT CREATED';
    document.getElementById('alphaOosReturn').textContent = percent(outOfSample.annualized_return);
    document.getElementById('alphaOosDrawdown').textContent = percent(outOfSample.max_drawdown);
    document.getElementById('alphaFoldCount').textContent = `${data.evidence.backtest.walk_forward_folds} FOLDS`;
    document.getElementById('alphaFingerprint').textContent = dataset.fingerprint;
    document.getElementById('alphaDisclaimer').textContent = data.disclaimer;
    setPlannerPill(data.planner.label, data.planner.mode === 'QWEN');
    renderGates(checks);
    renderReceipts(data.trace);
    resultPanel.hidden = false;
  }

  async function runAudit() {
    const task = taskInput.value.trim();
    if (task.length < 8) {
      errorPanel.textContent = '请用一句完整的话描述要审计的策略任务。';
      errorPanel.hidden = false;
      taskInput.focus();
      return;
    }

    errorPanel.hidden = true;
    resultPanel.hidden = true;
    resetTrace();
    startTraceProgress();
    runButton.disabled = true;
    runButton.classList.add('running');
    runButton.querySelector('strong').textContent = '正在运行证据审计';

    try {
      const response = await fetch('/api/goai/audit-demo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task }),
      });
      if (!response.ok) {
        const failure = await response.json().catch(() => ({}));
        throw new Error(failure.detail || `审计接口返回 ${response.status}`);
      }
      const data = await response.json();
      await finishTrace(data);
      renderResult(data);
      window.pioShowToast?.('审计完成：风险门禁拒绝创建订单意图。');
    } catch (error) {
      clearInterval(progressTimer);
      const running = traceRows.findIndex((row) => row.classList.contains('running'));
      if (running >= 0) setTraceState(running, 'blocked', '失败');
      errorPanel.textContent = `审计未完成：${error.message}`;
      errorPanel.hidden = false;
      document.getElementById('alphaRunId').textContent = '运行失败';
    } finally {
      runButton.disabled = false;
      runButton.classList.remove('running');
      runButton.querySelector('strong').textContent = '再次运行证据审计';
    }
  }

  runButton.addEventListener('click', runAudit);
  loadPlannerStatus();
}());
