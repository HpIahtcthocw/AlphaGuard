window.executeDemoPaperPlan = async function executeDemoPaperPlan(button) {
  const original = button.textContent;
  if (localStorage.getItem('pio.plan.PLAN-018.status') === 'FILLED') {
    button.disabled = true; button.textContent = '已模拟成交';
    window.pioShowToast?.('该计划已经执行过，幂等保护阻止了重复成交。');
    return;
  }
  button.disabled = true;
  button.textContent = '检查风控…';
  try {
    const health = await fetch('/api/health');
    if (!health.ok) throw new Error('本地账本服务未启动');
    let snapshotId = localStorage.getItem('pio.core.snapshot');
    if (!snapshotId) {
      const stored = JSON.parse(localStorage.getItem('pio.account.holdings') || 'null');
      if (!stored) throw new Error('请先导入账户持仓');
      const synced = await window.accountImporter.syncHoldingsToCore(stored);
      snapshotId = synced.snapshot_id;
    }
    const createdResponse = await fetch('/api/order-intents', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: '510300', market: 'CN', currency: 'CNY', side: 'SELL', quantity: 100,
        reference_price: 3.91, reason: '当前权重超过组合预设上限，按计划降低集中度风险',
        idempotency_key: 'PLAN-018-v1', account_id: 'default'
      })
    });
    const created = await createdResponse.json();
    if (!createdResponse.ok) throw new Error(created.detail || '创建交易意图失败');
    if (created.status === 'REJECTED') {
      const failed = created.risk_checks.filter((check) => check.status === 'FAIL').map((check) => check.message).join('；');
      throw new Error(`风控拒绝：${failed}`);
    }
    let order = created;
    if (order.status === 'PENDING_APPROVAL') {
      button.textContent = '记录批准…';
      const response = await fetch(`/api/order-intents/${order.id}/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ approved_by: 'local-owner' }) });
      order = await response.json();
      if (!response.ok) throw new Error(order.detail || '批准失败');
    }
    if (order.status === 'APPROVED') {
      button.textContent = '模拟成交…';
      const response = await fetch(`/api/order-intents/${order.id}/simulate`, { method: 'POST' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || '模拟成交失败');
      window.accountImporter.renderCorePortfolio(result.portfolio);
      localStorage.setItem('pio.core.snapshot', result.portfolio.snapshot_id);
      localStorage.setItem('pio.plan.PLAN-018.status', 'FILLED');
      window.pioUpdateCoreStatus?.();
      button.textContent = '已模拟成交';
      button.closest('.plan-card')?.querySelector('.tag')?.classList.replace('teal', 'green');
      const tag = button.closest('.plan-card')?.querySelector('.tag'); if (tag) tag.textContent = '已成交';
      window.pioShowToast?.(`纸面成交完成：卖出 ${result.fill.quantity} 份 510300，成交价 ¥${result.fill.fill_price}，审计记录已写入。`);
      return;
    }
    if (order.status === 'FILLED') {
      localStorage.setItem('pio.plan.PLAN-018.status', 'FILLED');
      button.textContent = '已模拟成交';
      window.pioShowToast?.('该计划已经执行过，幂等保护阻止了重复成交。');
      return;
    }
    throw new Error(`无法处理订单状态：${order.status}`);
  } catch (error) {
    button.disabled = false;
    button.textContent = original;
    window.pioShowToast?.(error.message);
  }
};
