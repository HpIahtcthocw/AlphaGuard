(() => {
  const researchView = document.getElementById('researchView');
  if (!researchView || document.querySelector('.financial-skills-panel')) return;
  const panel = document.createElement('section');
  panel.className = 'panel financial-skills-panel';
  panel.innerHTML = `
    <div class="panel-heading"><div><span class="eyebrow">Financial Skills</span><h2>Read-only research for CN and US assets</h2></div><span class="sample-pill">Awaiting data connector</span></div>
    <div class="financial-skills-grid">
      <article class="financial-skill-card"><span class="financial-skill-mark">ER</span><div><strong>Equity Research</strong><p>For US and single names: consensus, history, valuation, price action, catalysts and bull/bear arguments. Every data point must carry a source.</p></div><span class="tag skill-status">Read-only</span></article>
      <article class="financial-skill-card"><span class="financial-skill-mark">MR</span><div><strong>Macro & Rates Monitor</strong><p>For USD assets: US growth, inflation, labor, yield curve, real rates and financial conditions. It never generates an order directly.</p></div><span class="tag skill-status">Read-only</span></article>
    </div>
    <div class="panel-note">This environment lacks the dedicated data tools these skills need, so we keep the entry points and permission boundaries — and never display fabricated research.</div>`;
  researchView.appendChild(panel);
})();
