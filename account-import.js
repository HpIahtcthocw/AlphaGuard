const accountImporter = (() => {
  const modal = document.getElementById('accountImportModal');
  const fileInput = document.getElementById('accountFileInput');
  const dropZone = document.getElementById('accountDropZone');
  const confirmButton = document.getElementById('confirmAccountImport');
  const preview = document.getElementById('accountImportPreview');
  const errorsBox = document.getElementById('importErrors');
  let pendingImport = null;

  const aliases = {
    symbol: ['symbol', 'ticker', 'code', '证券代码', '股票代码', '代码'],
    name: ['name', 'securityname', 'stockname', '证券名称', '股票名称', '名称'],
    market: ['market', 'exchange', '市场', '交易所'],
    currency: ['currency', 'ccy', '币种', '货币'],
    quantity: ['quantity', 'qty', 'position', 'shares', '持仓数量', '数量', '股数'],
    avgCost: ['avgcost', 'averagecost', 'costbasis', '成本价', '平均成本', '持仓成本'],
    lastPrice: ['lastprice', 'marketprice', 'price', '当前价', '市价', '最新价'],
    marketValue: ['marketvalue', 'value', '市值', '市场价值'],
    assetType: ['assettype', 'type', 'securitytype', '资产类型', '品种'],
    date: ['date', 'tradedate', 'datetime', '成交日期', '交易日期', '日期'],
    side: ['side', 'action', 'buyorsell', '买卖方向', '方向'],
    fee: ['fee', 'commission', 'fees', '手续费', '佣金']
  };

  const normalizeHeader = (value) => String(value || '').replace(/^\uFEFF/, '').trim().toLowerCase().replace(/[\s_\-./()]/g, '');
  const aliasLookup = Object.fromEntries(Object.entries(aliases).flatMap(([key, values]) => values.map((value) => [normalizeHeader(value), key])));

  function openModal() { modal.hidden = false; document.body.style.overflow = 'hidden'; }
  function closeModal() { modal.hidden = true; document.body.style.overflow = ''; }

  function parseCSV(text) {
    const rows = []; let row = []; let field = ''; let quoted = false;
    const source = text.replace(/^\uFEFF/, '');
    for (let i = 0; i < source.length; i += 1) {
      const char = source[i];
      if (char === '"' && quoted && source[i + 1] === '"') { field += '"'; i += 1; }
      else if (char === '"') quoted = !quoted;
      else if (char === ',' && !quoted) { row.push(field.trim()); field = ''; }
      else if ((char === '\n' || char === '\r') && !quoted) {
        if (char === '\r' && source[i + 1] === '\n') i += 1;
        row.push(field.trim()); field = '';
        if (row.some((cell) => cell !== '')) rows.push(row);
        row = [];
      } else field += char;
    }
    if (field || row.length) { row.push(field.trim()); if (row.some((cell) => cell !== '')) rows.push(row); }
    return rows;
  }

  function numberValue(value) {
    const cleaned = String(value ?? '').replace(/[,$¥￥\s]/g, '');
    if (cleaned === '') return null;
    const parsed = Number(cleaned);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function inferMarket(symbol, rawMarket) {
    const market = String(rawMarket || '').trim().toUpperCase();
    if (/US|NASDAQ|NYSE|AMEX/.test(market)) return 'US';
    if (/HK|SEHK|港/.test(market)) return 'HK';
    if (/CN|SSE|SZSE|SH|SZ|沪|深|中国/.test(market)) return 'CN';
    if (/^\d{5}(\.HK)?$/i.test(symbol)) return 'HK';
    if (/^\d{6}(\.(SH|SZ))?$/i.test(symbol)) return 'CN';
    return 'US';
  }

  function normalizeSide(value) {
    const side = String(value || '').trim().toUpperCase();
    if (['BUY', 'B', '买', '买入'].includes(side)) return 'BUY';
    if (['SELL', 'S', '卖', '卖出'].includes(side)) return 'SELL';
    return side;
  }

  function processRows(rows, filename) {
    if (rows.length < 2) throw new Error('CSV 至少需要表头和一行数据。');
    const rawHeaders = rows[0];
    const mappedHeaders = rawHeaders.map((header) => aliasLookup[normalizeHeader(header)] || null);
    const schema = mappedHeaders.includes('side') || mappedHeaders.includes('date') ? 'transactions' : 'holdings';
    const errors = [];
    const normalized = rows.slice(1).map((cells, index) => {
      const raw = {};
      mappedHeaders.forEach((key, cellIndex) => { if (key) raw[key] = cells[cellIndex]; });
      const symbol = String(raw.symbol || '').trim().toUpperCase();
      if (!symbol) { errors.push(`第 ${index + 2} 行缺少证券代码`); return null; }
      const market = inferMarket(symbol, raw.market);
      const currency = String(raw.currency || (market === 'US' ? 'USD' : market === 'HK' ? 'HKD' : 'CNY')).toUpperCase();
      if (schema === 'transactions') {
        const quantity = numberValue(raw.quantity); const price = numberValue(raw.lastPrice);
        if (!raw.date || !normalizeSide(raw.side) || quantity === null || price === null) errors.push(`第 ${index + 2} 行交易字段不完整`);
        return { date: raw.date || '', symbol, name: raw.name || symbol, market, currency, side: normalizeSide(raw.side), quantity: quantity || 0, price: price || 0, fee: numberValue(raw.fee) || 0 };
      }
      const quantity = numberValue(raw.quantity); const lastPrice = numberValue(raw.lastPrice); const suppliedValue = numberValue(raw.marketValue);
      if (quantity === null) errors.push(`第 ${index + 2} 行缺少有效持仓数量`);
      if (lastPrice === null && suppliedValue === null) errors.push(`第 ${index + 2} 行缺少当前价或市值`);
      const assetType = String(raw.assetType || (/CASH|现金|货币/.test(`${symbol}${raw.name || ''}`) ? 'CASH' : market === 'CN' && /^5/.test(symbol) ? 'ETF' : 'STOCK')).toUpperCase();
      return { symbol, name: raw.name || symbol, market, currency, quantity: quantity || 0, avgCost: numberValue(raw.avgCost), lastPrice, marketValue: suppliedValue ?? ((quantity || 0) * (lastPrice || 0)), assetType };
    }).filter(Boolean);
    if (!mappedHeaders.includes('symbol')) throw new Error('没有识别到证券代码列。请使用通用模板或包含 symbol/证券代码 字段。');
    return { schema, records: normalized, errors, filename, importedAt: new Date().toISOString() };
  }

  function renderPreview(result) {
    const isHoldings = result.schema === 'holdings';
    document.getElementById('importPreviewTitle').textContent = `${result.records.length} 条${isHoldings ? '持仓' : '交易'}记录已识别`;
    document.getElementById('detectedSchemaTag').textContent = isHoldings ? '持仓快照' : '交易流水';
    document.getElementById('selectedFileName').textContent = result.filename;
    const markets = [...new Set(result.records.map((item) => item.market))].join(' / ');
    const currencies = [...new Set(result.records.map((item) => item.currency))].join(' / ');
    document.getElementById('importPreviewSummary').innerHTML = `<span>市场 ${escapeHTML(markets || '未知')}</span><span>币种 ${escapeHTML(currencies || '未知')}</span><span>异常 ${result.errors.length}</span>`;
    const columns = isHoldings ? ['代码', '名称', '市场', '币种', '数量', '市值'] : ['日期', '代码', '方向', '数量', '价格', '币种'];
    document.getElementById('importPreviewHead').innerHTML = `<tr>${columns.map((item) => `<th>${item}</th>`).join('')}</tr>`;
    document.getElementById('importPreviewBody').innerHTML = result.records.slice(0, 6).map((record) => isHoldings
      ? `<tr><td>${escapeHTML(record.symbol)}</td><td>${escapeHTML(record.name)}</td><td>${record.market}</td><td>${record.currency}</td><td>${formatNumber(record.quantity)}</td><td>${formatMoney(record.marketValue, record.currency)}</td></tr>`
      : `<tr><td>${escapeHTML(record.date)}</td><td>${escapeHTML(record.symbol)}</td><td>${record.side}</td><td>${formatNumber(record.quantity)}</td><td>${formatMoney(record.price, record.currency)}</td><td>${record.currency}</td></tr>`).join('');
    errorsBox.hidden = result.errors.length === 0;
    errorsBox.textContent = result.errors.length ? `需要复核：${result.errors.slice(0, 4).join('；')}` : '';
    preview.hidden = false;
    confirmButton.disabled = result.records.length === 0 || result.errors.length >= result.records.length;
    document.querySelectorAll('.import-steps span').forEach((step, index) => step.classList.toggle('active', index <= 1));
  }

  function renderHoldings(account) {
    if (!account?.records?.length || account.schema !== 'holdings') return;
    const usdCny = Number(account.usdCny) || 7.2;
    const converted = account.records.map((record) => ({ ...record, cnyValue: record.marketValue * (record.currency === 'USD' ? usdCny : 1) }));
    const total = converted.reduce((sum, record) => sum + record.cnyValue, 0);
    const cash = converted.filter((record) => record.assetType === 'CASH').reduce((sum, record) => sum + record.cnyValue, 0);
    const table = document.querySelector('.holdings-table');
    table.innerHTML = '<div class="table-row table-head"><span>标的</span><span>市值</span><span>权重</span><span>日变化</span><span>状态</span></div>' + converted.map((record) => {
      const localValue = formatMoney(record.marketValue, record.currency);
      const valueLabel = record.currency === 'CNY' ? localValue : `${localValue}<small>≈ ¥${formatNumber(record.cnyValue)}</small>`;
      return `<div class="table-row"><strong>${escapeHTML(record.name)}<small>${escapeHTML(record.symbol)} · ${record.market} · ${record.currency}</small></strong><span>${valueLabel}</span><span>${total ? (record.cnyValue / total * 100).toFixed(1) : '0.0'}%</span><span class="neutral">待行情</span><span class="tag teal">已导入</span></div>`;
    }).join('');
    document.querySelector('.holdings-panel .panel-heading h2').textContent = `${converted.length} 个标的 · ¥${formatNumber(total)}`;
    document.querySelector('.holdings-panel .sample-pill').textContent = '本地导入';
    document.getElementById('accountStatusPill').textContent = `本地账户 · ${[...new Set(converted.map((record) => record.currency))].join('/')}`;
    const metricValue = document.querySelector('.primary-metric .metric-value');
    if (metricValue) metricValue.innerHTML = `¥ ${formatNumber(total)}<span class="metric-suffix">.00</span>`;
    const cashMetric = document.querySelector('.metric-grid .metric-card:nth-child(2) .metric-value');
    if (cashMetric) cashMetric.innerHTML = `${total ? (cash / total * 100).toFixed(1) : '0.0'}<span class="metric-suffix">%</span>`;
  }

  async function confirmImport() {
    if (!pendingImport) return;
    confirmButton.disabled = true;
    confirmButton.textContent = '写入中…';
    const usdCny = Number(document.getElementById('usdCnyRate').value) || 7.2;
    const account = { ...pendingImport, usdCny };
    const key = account.schema === 'holdings' ? 'pio.account.holdings' : 'pio.account.transactions';
    localStorage.setItem(key, JSON.stringify(account));
    if (account.schema === 'holdings') renderHoldings(account);
    let coreResult = null;
    if (account.schema === 'holdings') {
      try { coreResult = await syncHoldingsToCore(account); }
      catch (_) { /* local import remains available when the API is offline */ }
    }
    document.querySelectorAll('.import-steps span').forEach((step) => step.classList.add('active'));
    window.pioShowToast?.(account.schema === 'holdings' ? `已导入 ${account.records.length} 条持仓${coreResult ? '，并写入不可变账本快照' : '，当前保存在本地浏览器'}。` : `已保存 ${account.records.length} 条交易流水，等待账本服务核对。`);
    confirmButton.textContent = '确认导入本地账户';
    closeModal();
  }

  async function syncHoldingsToCore(account) {
    const payload = {
      holdings: account.records.map((record) => ({
        symbol: record.symbol, name: record.name, market: record.market, currency: record.currency,
        quantity: record.quantity, avg_cost: record.avgCost, last_price: record.lastPrice,
        market_value: record.marketValue, asset_type: record.assetType
      })),
      fx_rates: { 'USD/CNY': Number(account.usdCny) || 7.2 },
      source_name: account.filename || 'browser-import',
      as_of: new Date().toISOString().slice(0, 10),
      account_id: 'default'
    };
    const response = await fetch('/api/accounts/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!response.ok) throw new Error(`core import failed: ${response.status}`);
    const result = await response.json();
    localStorage.setItem('pio.core.snapshot', result.snapshot_id);
    account.coreManaged = true;
    localStorage.setItem('pio.account.holdings', JSON.stringify(account));
    document.getElementById('accountStatusPill').textContent = '本地账本 · CNY/USD';
    return result;
  }

  function renderCorePortfolio(portfolio) {
    const usdCny = Number(portfolio.fx_rates?.['USD/CNY']) || 7.2;
    const account = {
      schema: 'holdings', usdCny, coreManaged: true,
      records: (portfolio.positions || []).map((record) => ({
        symbol: record.symbol, name: record.name, market: record.market, currency: record.currency,
        quantity: Number(record.quantity), avgCost: record.average_cost === null ? null : Number(record.average_cost),
        lastPrice: record.last_price === null ? null : Number(record.last_price), marketValue: Number(record.market_value),
        assetType: record.asset_type
      }))
    };
    localStorage.setItem('pio.account.holdings', JSON.stringify(account));
    renderHoldings(account);
    document.getElementById('accountStatusPill').textContent = '本地账本 · CNY/USD';
  }

  function handleFile(file) {
    if (!file) return;
    if (!/\.csv$/i.test(file.name)) { window.pioShowToast?.('目前只支持 CSV 文件。'); return; }
    const reader = new FileReader();
    reader.onload = () => {
      try { pendingImport = processRows(parseCSV(String(reader.result)), file.name); renderPreview(pendingImport); }
      catch (error) { pendingImport = null; confirmButton.disabled = true; errorsBox.hidden = false; errorsBox.textContent = error.message; preview.hidden = false; }
    };
    reader.readAsText(file, 'utf-8');
  }

  function downloadTemplate() {
    const csv = '\uFEFFsymbol,name,market,currency,quantity,avg_cost,last_price,asset_type\n510300,沪深300ETF,CN,CNY,1000,3.75,3.91,ETF\nAAPL,Apple Inc.,US,USD,10,212,225.50,STOCK\nCASH_USD,美元现金,US,USD,1800,1,1,CASH';
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = 'pio-account-template.csv'; link.click(); URL.revokeObjectURL(url);
  }

  function escapeHTML(value) { const node = document.createElement('div'); node.textContent = String(value ?? ''); return node.innerHTML; }
  function formatNumber(value) { return Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 }); }
  function formatMoney(value, currency) { return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: currency || 'CNY', maximumFractionDigits: 2 }).format(Number(value || 0)); }

  document.getElementById('importAccountButton').addEventListener('click', openModal);
  document.getElementById('addHoldingButton').addEventListener('click', openModal);
  document.getElementById('closeImportModal').addEventListener('click', closeModal);
  document.getElementById('cancelAccountImport').addEventListener('click', closeModal);
  document.getElementById('chooseAccountFile').addEventListener('click', () => fileInput.click());
  document.getElementById('downloadAccountTemplate').addEventListener('click', downloadTemplate);
  document.getElementById('confirmAccountImport').addEventListener('click', confirmImport);
  fileInput.addEventListener('change', () => handleFile(fileInput.files[0]));
  dropZone.addEventListener('click', (event) => { if (!event.target.closest('button')) fileInput.click(); });
  dropZone.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') fileInput.click(); });
  ['dragenter', 'dragover'].forEach((type) => dropZone.addEventListener(type, (event) => { event.preventDefault(); dropZone.classList.add('dragging'); }));
  ['dragleave', 'drop'].forEach((type) => dropZone.addEventListener(type, (event) => { event.preventDefault(); dropZone.classList.remove('dragging'); }));
  dropZone.addEventListener('drop', (event) => handleFile(event.dataTransfer.files[0]));
  modal.addEventListener('click', (event) => { if (event.target === modal) closeModal(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !modal.hidden) closeModal(); });

  try {
    const stored = JSON.parse(localStorage.getItem('pio.account.holdings'));
    renderHoldings(stored);
    if (stored?.schema === 'holdings' && stored.coreManaged) {
      fetch('/api/portfolio').then((response) => response.ok ? response.json() : Promise.reject()).then(renderCorePortfolio).catch(() => {});
    } else if (stored?.schema === 'holdings') syncHoldingsToCore(stored).catch(() => {});
  } catch (_) { /* keep sample account */ }
  return { processRows, parseCSV, renderHoldings, renderCorePortfolio, syncHoldingsToCore };
})();

window.accountImporter = accountImporter;
