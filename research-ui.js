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
    document.getElementById('backtestScore').textContent = report.production_eligible ? 'Awaiting audit' : 'Not certified';
    document.getElementById('backtestScoreNote').textContent = 'Not a return promise';
    document.getElementById('strategyFinalEquity').textContent = formatMoney(metrics.final_equity);
    document.getElementById('benchmarkFinalEquity').textContent = report.baselines?.['BASE-BUY-HOLD'] ? formatMoney(report.baselines['BASE-BUY-HOLD'].metrics.final_equity) : '—';
    document.getElementById('annualizedReturn').textContent = formatPercent(metrics.annualized_return);
    document.getElementById('benchmarkReturn').textContent = `Buy & hold ${report.baselines?.['BASE-BUY-HOLD'] ? formatPercent(report.baselines['BASE-BUY-HOLD'].metrics.annualized_return) : '—'}`;
    document.getElementById('maxDrawdown').textContent = formatPercent(metrics.max_drawdown);
    document.getElementById('annualizedVolatility').textContent = formatPercent(metrics.annualized_volatility);
    document.getElementById('sharpeRatio').textContent = `Sharpe ${Number(metrics.sharpe || 0).toFixed(2)}`;
    document.getElementById('costDrag').textContent = formatPercent(metrics.cost_drag);
    document.getElementById('tradeDays').textContent = `Trade days ${metrics.trade_days || 0}`;
    document.getElementById('backtestStartLabel').textContent = report.period.start.slice(0, 4);
    document.getElementById('backtestMidLabel').textContent = report.split.test_start.slice(0, 4);
    document.getElementById('backtestEndLabel').textContent = report.period.end.slice(0, 4);
    const warnings = [...(report.data_quality?.warnings || []), ...(report.warnings || [])];
    document.getElementById('backtestWarnings').textContent = `${report.dataset_kind === 'SYNTHETIC_DEMO' ? 'Synthetic demo data: not a representation of real returns.' : 'User-data backtest: results apply to this data snapshot only.'} ${warnings.join(' ') || 'Data quality check passed.'}`;
  }

  async function run(buttonElement) {
    buttonElement.disabled = true;
    const original = buttonElement.textContent;
    buttonElement.textContent = 'Running…';
    try {
      const response = await fetch('/api/research/experiments/personal');
      const report = await response.json();
      if (!response.ok) throw new Error(report.detail || 'Backtest failed');
      render(report);
      window.pioShowToast?.('PIO-EXP-001 done: review out-of-sample, baseline, and gate results first.');
    } catch (error) {
      window.pioShowToast?.(error.message || 'Backtest failed');
    } finally {
      buttonElement.disabled = false;
      buttonElement.textContent = original;
    }
  }

  window.pioRunDemoBacktest = run;
  run(button);
})();
