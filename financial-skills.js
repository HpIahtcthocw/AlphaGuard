(() => {
  const researchView = document.getElementById('researchView');
  if (!researchView || document.querySelector('.financial-skills-panel')) return;
  const panel = document.createElement('section');
  panel.className = 'panel financial-skills-panel';
  panel.innerHTML = `
    <div class="panel-heading"><div><span class="eyebrow">金融 Skills</span><h2>为中美资产准备的只读研究能力</h2></div><span class="sample-pill">等待数据连接器</span></div>
    <div class="financial-skills-grid">
      <article class="financial-skill-card"><span class="financial-skill-mark">ER</span><div><strong>Equity Research</strong><p>面向美股和个股：一致预期、历史财务、估值、价格表现、催化剂与多空论据。所有数据必须带来源。</p></div><span class="tag skill-status">只读</span></article>
      <article class="financial-skill-card"><span class="financial-skill-mark">MR</span><div><strong>Macro & Rates Monitor</strong><p>面向美元资产：美国增长、通胀、就业、收益率曲线、实际利率和金融条件，不直接生成交易订单。</p></div><span class="tag skill-status">只读</span></article>
    </div>
    <div class="panel-note">当前环境没有这些 Skills 所需的专业数据工具，因此先保留入口和权限边界，不展示伪造的实时研究结论。</div>`;
  researchView.appendChild(panel);
})();
