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
    if (status) status.innerHTML = `<span class="status-dot"></span><span>本地账本运行中</span><span class="mono">${audit.verified ? 'AUDIT ✓' : 'AUDIT !'}</span>`;
    const mode = document.querySelector('.mode-note strong');
    if (mode) mode.textContent = health.execution_adapter?.adapter || (health.execution === 'paper-only' ? '本地纸面盘' : health.execution);
    const marketStatus = document.getElementById('marketDataStatus');
    if (marketStatus && health.market_data) {
      const live = health.market_data.providers.some((provider) => provider.is_realtime && provider.configured);
      marketStatus.textContent = live ? '行情源：已配置实时接口' : '行情源：快照降级，非实时';
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
  button.textContent = '同步中…';
  button.disabled = true;
  setTimeout(() => {
    button.textContent = original;
    button.disabled = false;
    showToast('本地示例数据已刷新，未连接外部账户。');
  }, 900);
});

document.querySelectorAll('[data-plan]').forEach((button) => {
  button.addEventListener('click', () => {
    const action = button.dataset.plan;
    if (action === 'approve') { window.executeDemoPaperPlan?.(button); return; }
    if (action === 'snooze') showToast('已延后提醒到下一个交易日。');
    if (action === 'details') showToast('证据面板即将展开：来源、假设和失效条件。');
    if (action === 'rebalance') showView('plans');
  });
});

document.querySelectorAll('#newHypothesisButton, #newPlanButton').forEach((button) => {
  button.addEventListener('click', () => showToast('这是原型中的入口，下一步会接入本地账本和结构化表单。'));
});

document.getElementById('runBacktestButton').addEventListener('click', (event) => {
  window.pioRunDemoBacktest?.(event.currentTarget);
});

document.querySelectorAll('.segment').forEach((segment) => {
  segment.addEventListener('click', () => {
    document.querySelectorAll('.segment').forEach((item) => item.classList.remove('active'));
    segment.classList.add('active');
    showToast(`已切换到“${segment.textContent}”视图。`);
  });
});
