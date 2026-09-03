const views = [...document.querySelectorAll('.view')];
const navItems = [...document.querySelectorAll('.nav-item')];
const toast = document.getElementById('toast');
let toastTimer;

function showToast(message) {
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2800);
}

window.pioShowToast = showToast;

async function updateCoreStatus() {
  try {
    const [healthResponse, auditResponse] = await Promise.all([fetch('/api/health'), fetch('/api/audit?limit=1')]);
    if (!healthResponse.ok || !auditResponse.ok) return;
    const health = await healthResponse.json();
    const audit = await auditResponse.json();
    const status = document.querySelector('.sync-status');
    if (status) status.innerHTML = `<span class="status-dot"></span><span>Local audit ledger active</span><span class="mono">${audit.verified ? 'AUDIT ✓' : 'AUDIT !'}</span>`;
    const mode = document.querySelector('.mode-note strong');
    if (mode) mode.textContent = health.execution_adapter?.adapter || (health.execution === 'paper-only' ? 'local paper' : health.execution);
    const marketStatus = document.getElementById('marketDataStatus');
    if (marketStatus && health.market_data) {
      const live = health.market_data.providers.some((provider) => provider.is_realtime && provider.configured);
      marketStatus.textContent = live ? 'Data source: live feed configured' : 'Data source: snapshot fallback (non-live)';
    }
  } catch (_) { /* the static prototype remains usable without the API */ }
}

updateCoreStatus();
window.pioUpdateCoreStatus = updateCoreStatus;

function showView(viewName) {
  views.forEach((view) => view.classList.toggle('active-view', view.id === `${viewName}View`));
  navItems.forEach((item) => item.classList.toggle('active', item.dataset.view === viewName));
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.querySelectorAll('[data-view], [data-view-target]').forEach((element) => {
  element.addEventListener('click', () => showView(element.dataset.view || element.dataset.viewTarget));
});

document.getElementById('refreshButton').addEventListener('click', (event) => {
  const button = event.currentTarget;
  const original = button.textContent;
  button.textContent = 'Syncing…';
  button.disabled = true;
  setTimeout(() => {
    button.textContent = original;
    button.disabled = false;
    showToast('Local sample data refreshed; no external account connected.');
  }, 900);
});

document.querySelectorAll('[data-plan]').forEach((button) => {
  button.addEventListener('click', () => {
    const action = button.dataset.plan;
    if (action === 'approve') { window.executeDemoPaperPlan?.(button); return; }
    if (action === 'snooze') showToast('Reminder moved to the next trading day.');
    if (action === 'details') showToast('Evidence panel coming up: source, hypothesis and invalidation conditions.');
    if (action === 'rebalance') showView('plans');
  });
});

document.querySelectorAll('#newHypothesisButton, #newPlanButton').forEach((button) => {
  button.addEventListener('click', () => showToast('This is a prototype entry; next step wires it to the local ledger and structured forms.'));
});

document.getElementById('runBacktestButton').addEventListener('click', (event) => {
  window.pioRunDemoBacktest?.(event.currentTarget);
});

document.querySelectorAll('.segment').forEach((segment) => {
  segment.addEventListener('click', () => {
    document.querySelectorAll('.segment').forEach((item) => item.classList.remove('active'));
    segment.classList.add('active');
    showToast(`Switched to the "${segment.textContent}" view.`);
  });
});
