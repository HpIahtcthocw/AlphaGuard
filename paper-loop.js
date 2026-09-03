window.executeDemoPaperPlan = async function executeDemoPaperPlan(button) {
  const original = button.textContent;
  if (localStorage.getItem('pio.plan.PLAN-018.status') === 'FILLED') {
    button.disabled = true; button.textContent = 'Simulated fill done';
    window.PIOApplyI18n?.(button);
    window.pioShowToast?.('This plan already executed; idempotency guard blocked a duplicate fill.');
    return;
  }
  button.disabled = true;
  button.textContent = 'Checking risk…';
  try {
    const health = await fetch('/api/health');
    if (!health.ok) throw new Error('Local ledger service not running');
    let snapshotId = localStorage.getItem('pio.core.snapshot');
    if (!snapshotId) {
      const stored = JSON.parse(localStorage.getItem('pio.account.holdings') || 'null');
      if (!stored) throw new Error('Import account holdings first');
      const synced = await window.accountImporter.syncHoldingsToCore(stored);
      snapshotId = synced.snapshot_id;
    }
    const createdResponse = await fetch('/api/order-intents', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: '510300', market: 'CN', currency: 'CNY', side: 'SELL', quantity: 100,
        reference_price: 3.91, reason: 'Weight is above the portfolio preset cap; reduce concentration risk per plan',
        idempotency_key: 'PLAN-018-v1', account_id: 'default'
      })
    });
    const created = await createdResponse.json();
    if (!createdResponse.ok) throw new Error(created.detail || 'Failed to create order intent');
    if (created.status === 'REJECTED') {
      const failed = created.risk_checks.filter((check) => check.status === 'FAIL').map((check) => check.message).join('; ');
      throw new Error(`Risk gate rejected: ${failed}`);
    }
    let order = created;
    if (order.status === 'PENDING_APPROVAL') {
      button.textContent = 'Recording approval…';
      const response = await fetch(`/api/order-intents/${order.id}/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ approved_by: 'local-owner' }) });
      order = await response.json();
      if (!response.ok) throw new Error(order.detail || 'Approval failed');
    }
    if (order.status === 'APPROVED') {
      button.textContent = 'Simulating fill…';
      const response = await fetch(`/api/order-intents/${order.id}/simulate`, { method: 'POST' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Simulation failed');
      window.accountImporter.renderCorePortfolio(result.portfolio);
      localStorage.setItem('pio.core.snapshot', result.portfolio.snapshot_id);
      localStorage.setItem('pio.plan.PLAN-018.status', 'FILLED');
      window.pioUpdateCoreStatus?.();
      button.textContent = 'Simulated fill done';
      button.closest('.plan-card')?.querySelector('.tag')?.classList.replace('teal', 'green');
      const tag = button.closest('.plan-card')?.querySelector('.tag'); if (tag) tag.textContent = 'Filled';
      window.PIOApplyI18n?.(button.closest('.plan-card') || button);
      window.pioShowToast?.(`Paper fill done: sold ${result.fill.quantity} × 510300 at ¥${result.fill.fill_price}; audit record appended to ledger.`);
      return;
    }
    if (order.status === 'FILLED') {
      localStorage.setItem('pio.plan.PLAN-018.status', 'FILLED');
      button.textContent = 'Simulated fill done';
      window.pioShowToast?.('This plan already executed; idempotency guard blocked a duplicate fill.');
      return;
    }
    throw new Error(`Unhandled order status: ${order.status}`);
  } catch (error) {
    button.disabled = false;
    button.textContent = original;
    window.pioShowToast?.(error.message);
  }
};
