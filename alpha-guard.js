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
        planner.configured ? `Qwen ready · ${planner.model}` : 'Rule demo · Qwen Key not configured',
        planner.configured,
      );
    } catch (_) {
      setPlannerPill('Offline rule demo', false);
    }
  }

  function resetTrace() {
    clearInterval(progressTimer);
    traceRows.forEach((row) => {
      row.classList.remove('running', 'completed', 'blocked');
      row.querySelector('b').textContent = 'Waiting';
    });
    document.getElementById('alphaRunId').textContent = 'Running';
  }

  function setTraceState(index, state, label) {
    const row = traceRows[index];
    if (!row) return;
    row.classList.remove('running', 'completed', 'blocked');
    row.classList.add(state);
    row.querySelector('b').textContent = label;
    window.PIOApplyI18n?.(row);
  }

  function startTraceProgress() {
    let activeIndex = 0;
    setTraceState(activeIndex, 'running', 'Auditing');
    progressTimer = setInterval(() => {
      if (activeIndex >= traceRows.length - 1) return;
      setTraceState(activeIndex, 'completed', 'Done');
      activeIndex += 1;
      setTraceState(activeIndex, 'running', 'Auditing');
    }, 340);
  }

  async function finishTrace(data) {
    clearInterval(progressTimer);
    for (let index = 0; index < traceRows.length; index += 1) {
      const trace = data.trace[index];
      const blocked = trace?.status === 'BLOCKED';
      setTraceState(index, blocked ? 'blocked' : 'completed', blocked ? 'Blocked' : 'Done');
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
      status.textContent = blocked ? 'Blocked' : 'Passed';
      item.append(mark, copy, status);
      list.append(item);
    });
    const blockedCount = checks.filter((check) => check.status === 'BLOCKED').length;
    document.getElementById('alphaGateCount').textContent = `${blockedCount} / ${checks.length} blocked`;
    window.PIOApplyI18n?.(list);
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
    window.PIOApplyI18n?.(list);
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
    window.PIOApplyI18n?.(resultPanel);
  }

  async function runAudit() {
    const task = taskInput.value.trim();
    if (task.length < 8) {
      errorPanel.textContent = 'Describe the strategy to audit in one complete sentence.';
      window.PIOApplyI18n?.(errorPanel);
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
    runButton.querySelector('strong').textContent = 'Running evidence audit…';

    try {
      const response = await fetch('/api/goai/audit-demo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task }),
      });
      if (!response.ok) {
        const failure = await response.json().catch(() => ({}));
        throw new Error(failure.detail || `Audit API returned ${response.status}`);
      }
      const data = await response.json();
      await finishTrace(data);
      renderResult(data);
      window.pioShowToast?.('Audit complete: risk gate blocked order-intent creation.');
    } catch (error) {
      clearInterval(progressTimer);
      const running = traceRows.findIndex((row) => row.classList.contains('running'));
      if (running >= 0) setTraceState(running, 'blocked', 'Failed');
      errorPanel.textContent = `Audit incomplete: ${error.message}`;
      window.PIOApplyI18n?.(errorPanel);
      errorPanel.hidden = false;
      document.getElementById('alphaRunId').textContent = 'Audit failed';
    } finally {
      runButton.disabled = false;
      runButton.classList.remove('running');
      runButton.querySelector('strong').textContent = 'Re-run evidence audit';
    }
  }

  runButton.addEventListener('click', runAudit);
  loadPlannerStatus();
}());
