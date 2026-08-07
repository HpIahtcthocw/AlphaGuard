(() => {
  const button = document.getElementById('runBacktestButton');
  if (!button) return;

  const formatPercent = (value) => `${(Number(value) * 100).toFixed(2)}%`;
  const formatMoney = (value) => `¥${Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`;

  function pathFor(points, min, max, width = 800, height = 260) {
    if (!points?.length) return '';
    const span = max - min || 1;
    return points.map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * width;
      const y = height - ((Number(point.value) - min) / span) * (height - 20) - 10;
      return `${index ? 'L' : 'M'}${x.toFixed(2)} ${y.toFixed(2)}`;
    }).join(' ');
  }

  function render(report) {
    const metrics = report.metrics || {};
    const strategy = document.getElementById('strategyLine');
    const benchmark = document.getElementById('benchmarkLine');
    const points = report.equity || [];
    const benchmarkPoints = report.baselines?.['BASE-BUY-HOLD']?.equity || [];
    const allValues = [...points, ...benchmarkPoints].map((point) => Number(point.value));
    const min = Math.min(...allValues);
    const max = Math.max(...allValues);
    if (strategy) strategy.setAttribute('d', pathFor(points, min, max));
    if (benchmark) benchmark.setAttribute('d', pathFor(benchmarkPoints, min, max));
    document.getElementById('backtestDatasetLabel').textContent = `${report.dataset_kind} · ${report.strategy?.name || 'strategy'}`;
    document.getElementById('backtestPeriod').textContent = `${report.period.start} — ${report.period.end} · ${report.period.sessions} sessions`;
    document.getElementById('backtestScore').textContent = report.production_eligible ? '待审计' : '未认证';
    document.getElementById('backtestScoreNote').textContent = '不是收益承诺';
    document.getElementById('strategyFinalEquity').textContent = formatMoney(metrics.final_equity);
    document.getElementById('benchmarkFinalEquity').textContent = report.baselines?.['BASE-BUY-HOLD'] ? formatMoney(report.baselines['BASE-BUY-HOLD'].metrics.final_equity) : '—';
    document.getElementById('annualizedReturn').textContent = formatPercent(metrics.annualized_return);
    document.getElementById('benchmarkReturn').textContent = `买入持有 ${report.baselines?.['BASE-BUY-HOLD'] ? formatPercent(report.baselines['BASE-BUY-HOLD'].metrics.annualized_return) : '—'}`;
    document.getElementById('maxDrawdown').textContent = formatPercent(metrics.max_drawdown);
    document.getElementById('annualizedVolatility').textContent = formatPercent(metrics.annualized_volatility);
    document.getElementById('sharpeRatio').textContent = `Sharpe ${Number(metrics.sharpe || 0).toFixed(2)}`;
    document.getElementById('costDrag').textContent = formatPercent(metrics.cost_drag);
    document.getElementById('tradeDays').textContent = `交易日 ${metrics.trade_days || 0}`;
    document.getElementById('backtestStartLabel').textContent = report.period.start.slice(0, 4);
    document.getElementById('backtestMidLabel').textContent = report.split.test_start.slice(0, 4);
    document.getElementById('backtestEndLabel').textContent = report.period.end.slice(0, 4);
    const warnings = [...(report.data_quality?.warnings || []), ...(report.warnings || [])];
    document.getElementById('backtestWarnings').textContent = `${report.dataset_kind === 'SYNTHETIC_DEMO' ? '合成演示数据：不代表真实收益。' : '用户数据回测：结果仅对该数据快照负责。'} ${warnings.join(' ') || '数据质量检查通过。'}`;
  }

  async function run(buttonElement) {
    buttonElement.disabled = true;
    const original = buttonElement.textContent;
    buttonElement.textContent = '运行中…';
    try {
      const response = await fetch('/api/research/demo-backtest');
      const report = await response.json();
      if (!response.ok) throw new Error(report.detail || '回测失败');
      render(report);
      window.pioShowToast?.('合成回测完成：请先查看样本外和基线结果。');
    } catch (error) {
      window.pioShowToast?.(error.message || '回测失败');
    } finally {
      buttonElement.disabled = false;
      buttonElement.textContent = original;
    }
  }

  window.pioRunDemoBacktest = run;
  run(button);
})();
