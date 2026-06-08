// painel_diversas.js — Painel (Dashboard) das Apostas Diversas (não-NBA)
// Espelha painel.js, mas lê de /api/bets-diversas e adiciona filtro/quebra por Esporte.
// DEPENDE de painel.js carregado ANTES: reaproveita ensurePlugins(), calcStats(),
// fmtMoney(), _escP(), getDistinctTipos() e as constantes _TT/_GRID/_TICK/_MONO.
// Todos os ids de canvas, vars de chart e funções têm prefixo "dv" para isolar da aba Painel.

let _dvChartLucro = null;
let _dvChartTipo  = null;

let _dvPanelFilter   = 'all'; // 'week' | 'month' | 'year' | 'all'
let _dvTipoFilter    = 'all'; // 'all' | mercado específico
let _dvEsporteFilter = 'all'; // 'all' | esporte específico
let _dvAllBetsCache  = null;
let _dvFilteredCache = null;

// ── Filtros ───────────────────────────────────────────────────────────────
function _dvApplyPanelFilter(bets) {
  const now = new Date();
  if (_dvPanelFilter === 'week') {
    const day = now.getDay();
    const monday = new Date(now);
    monday.setDate(now.getDate() - (day === 0 ? 6 : day - 1));
    return bets.filter(b => b.data >= monday.toISOString().slice(0, 10));
  }
  if (_dvPanelFilter === 'month') {
    const de = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`;
    return bets.filter(b => b.data >= de);
  }
  if (_dvPanelFilter === 'year') {
    return bets.filter(b => b.data >= `${now.getFullYear()}-01-01`);
  }
  return bets;
}

function dvSetPanelFilter(f)   { _dvPanelFilter = f;   if (_dvAllBetsCache) renderPainelDiversas(); }
function dvSetTipoFilter(t)    { _dvTipoFilter = t;    if (_dvAllBetsCache) renderPainelDiversas(); }
function dvSetEsporteFilter(e) { _dvEsporteFilter = e; if (_dvAllBetsCache) renderPainelDiversas(); }

function _dvGetDistinctEsportes(bets) {
  const set = new Set();
  bets.forEach(b => { if (b.esporte) set.add(b.esporte); });
  return [...set].sort();
}

function _dvApplyTipoFilter(bets) {
  if (_dvTipoFilter === 'all') return bets;
  return bets.filter(b => (b.tipo_aposta || 'Outro') === _dvTipoFilter);
}

function _dvApplyEsporteFilter(bets) {
  if (_dvEsporteFilter === 'all') return bets;
  return bets.filter(b => (b.esporte || 'Outro') === _dvEsporteFilter);
}

// ── Load & render ─────────────────────────────────────────────────────────
async function loadPainelDiversas() {
  const container = document.getElementById('tab-painel-diversas');
  container.innerHTML = '<div style="padding:60px;text-align:center;color:var(--muted);font-family:var(--font-mono);font-size:12px;letter-spacing:0.08em">Carregando...</div>';

  try {
    const res = await authFetch('/api/bets-diversas');
    if (!res.ok) throw new Error('Erro ao carregar apostas');
    _dvAllBetsCache = await res.json();
    renderPainelDiversas();
  } catch (e) {
    container.innerHTML = `<div style="padding:60px;text-align:center;color:var(--red);font-family:var(--font-mono);font-size:12px">${e.message}</div>`;
  }
}

function renderPainelDiversas() {
  ensurePlugins();
  const bets = _dvAllBetsCache || [];
  const container = document.getElementById('tab-painel-diversas');

  if (bets.length === 0) {
    container.innerHTML = `
      <div style="text-align:center;padding:80px 24px">
        <div style="font-size:44px;margin-bottom:16px;opacity:0.35">◧</div>
        <p style="font-family:var(--font-mono);font-size:11px;color:var(--muted);letter-spacing:0.08em;line-height:1.9">
          SEM DADOS AINDA<br>Importe ou adicione apostas diversas para ver seu desempenho.
        </p>
      </div>`;
    return;
  }

  const filtered = _dvApplyEsporteFilter(_dvApplyTipoFilter(_dvApplyPanelFilter(bets)));
  _dvFilteredCache = filtered;

  const s = calcStats(filtered);

  // Comparação: últimos 30 dias vs 30 dias anteriores (sobre o conjunto bruto)
  const now = new Date();
  const fmtD = d => d.toISOString().slice(0, 10);
  const d30 = new Date(now); d30.setDate(d30.getDate() - 30);
  const d60 = new Date(now); d60.setDate(d60.getDate() - 60);
  const sLast30 = calcStats(bets.filter(b => b.data >= fmtD(d30)));
  const sPrev30 = calcStats(bets.filter(b => b.data >= fmtD(d60) && b.data < fmtD(d30)));

  const plChange     = sLast30.totalLP - sPrev30.totalLP;
  const plChangePct  = sPrev30.totalLP !== 0
    ? (plChange / Math.abs(sPrev30.totalLP) * 100) : null;
  const wrChange  = (sLast30.winRate !== null && sPrev30.winRate !== null)
    ? sLast30.winRate - sPrev30.winRate : null;
  const roiChange = (sLast30.roi !== null && sPrev30.roi !== null)
    ? sLast30.roi - sPrev30.roi : null;

  const winFill = s.winRate !== null && s.winRate >= 55 ? 'kpf-lime'
                : s.winRate !== null && s.winRate >= 40 ? 'kpf-gold' : 'kpf-red';

  const pf = f => _dvPanelFilter === f ? 'active' : '';
  const tf = f => _dvTipoFilter === f ? 'active' : '';
  const ef = f => _dvEsporteFilter === f ? 'active' : '';

  const allEsportes = _dvGetDistinctEsportes(bets);
  const esporteChips = allEsportes.map(e =>
    `<button class="dch-range-btn dtipo-btn ${ef(e)}" onclick="dvSetEsporteFilter('${_escP(e)}')">${_escP(e)}</button>`
  ).join('');

  const allTipos = getDistinctTipos(bets);
  const tipoChips = allTipos.map(t =>
    `<button class="dch-range-btn dtipo-btn ${tf(t)}" onclick="dvSetTipoFilter('${_escP(t)}')">${_escP(t)}</button>`
  ).join('');

  container.innerHTML = `
    <div class="pg-wrap">

      <!-- Header -->
      <div class="pg-hdr">
        <div>
          <h1 class="section-title">PAINEL DIVERSAS</h1>
          <div class="section-sub">Performance das apostas fora da NBA</div>
        </div>
        <div class="dch-range-btns">
          <button class="dch-range-btn ${pf('week')}"  onclick="dvSetPanelFilter('week')">SEMANA</button>
          <button class="dch-range-btn ${pf('month')}" onclick="dvSetPanelFilter('month')">MÊS</button>
          <button class="dch-range-btn ${pf('year')}"  onclick="dvSetPanelFilter('year')">ANO</button>
          <button class="dch-range-btn ${pf('all')}"   onclick="dvSetPanelFilter('all')">TUDO</button>
        </div>
      </div>

      <!-- Esporte filter -->
      ${allEsportes.length >= 1 ? `
      <div class="dtipo-filter-row">
        <span class="dtipo-label">ESPORTE</span>
        <div class="dch-range-btns dtipo-btns">
          <button class="dch-range-btn dtipo-btn ${ef('all')}" onclick="dvSetEsporteFilter('all')">TODOS</button>
          ${esporteChips}
        </div>
      </div>` : ''}

      <!-- Mercado filter -->
      ${allTipos.length >= 1 ? `
      <div class="dtipo-filter-row">
        <span class="dtipo-label">MERCADO</span>
        <div class="dch-range-btns dtipo-btns">
          <button class="dch-range-btn dtipo-btn ${tf('all')}" onclick="dvSetTipoFilter('all')">TODOS</button>
          ${tipoChips}
        </div>
      </div>` : ''}

      <!-- ── 4 KPI Cards ── -->
      <div class="dash-kpi-row">

        <div class="dash-kpi">
          <div class="dkpi-label">Lucro Total</div>
          <div class="dkpi-main">
            <span class="dkpi-val ${s.totalLP >= 0 ? 'dkpi-pos' : 'dkpi-neg'}">${fmtMoney(s.totalLP)}</span>
            ${plChangePct !== null ? `<span class="dkpi-badge ${plChange >= 0 ? 'dbadge-pos' : 'dbadge-neg'}">${plChange >= 0 ? '+' : ''}${plChangePct.toFixed(1)}%</span>` : ''}
          </div>
          ${s.winRate !== null ? `<div class="dkpi-prog-wrap"><div class="dkpi-prog ${winFill}" style="width:${Math.min(s.winRate,100).toFixed(1)}%"></div></div>` : ''}
          <div class="dkpi-sub">vs últimos 30 dias</div>
        </div>

        <div class="dash-kpi">
          <div class="dkpi-label">Taxa de Acerto</div>
          <div class="dkpi-main">
            <span class="dkpi-val">${s.winRate !== null ? s.winRate.toFixed(1) + '%' : '—'}</span>
            ${wrChange !== null ? `<span class="dkpi-badge ${wrChange >= 0 ? 'dbadge-pos' : 'dbadge-neg'}">${wrChange >= 0 ? '+' : ''}${wrChange.toFixed(1)}%</span>` : ''}
          </div>
          ${s.winRate !== null ? `<div class="dkpi-prog-wrap"><div class="dkpi-prog kpf-lime" style="width:${Math.min(s.winRate,100).toFixed(1)}%"></div></div>` : ''}
          <div class="dkpi-sub">Performance acumulada</div>
        </div>

        <div class="dash-kpi">
          <div class="dkpi-label">Retorno sobre Investimento</div>
          <div class="dkpi-main">
            <span class="dkpi-val">${s.roi !== null ? (s.roi >= 0 ? '+' : '') + s.roi.toFixed(1) + '%' : '—'}</span>
            ${roiChange !== null ? `<span class="dkpi-badge ${roiChange >= 0 ? 'dbadge-pos' : 'dbadge-neg'}">${roiChange >= 0 ? '+' : ''}${roiChange.toFixed(1)}%</span>` : ''}
          </div>
          <div class="dkpi-sub">Performance vitalícia</div>
        </div>

        <div class="dash-kpi">
          <div class="dkpi-label">Odds Médias</div>
          <div class="dkpi-main">
            <span class="dkpi-val" style="color:var(--gold)">${s.avgOdds !== null ? s.avgOdds.toFixed(2) : '—'}</span>
          </div>
          <div class="dkpi-sub">${s.wonCount + s.lostCount} apostas finalizadas</div>
        </div>

      </div>

      <!-- ── Row 2: Advanced KPIs ── -->
      ${s.wonCount + s.lostCount > 0 ? `
      <div class="dash-kpi-row">
        <div class="dash-kpi">
          <div class="dkpi-label">Max Drawdown</div>
          <div class="dkpi-main">
            <span class="dkpi-val dkpi-neg">R$ ${s.maxDrawdown.toFixed(2)}</span>
          </div>
          <div class="dkpi-sub">Maior queda pico-a-vale</div>
        </div>

        <div class="dash-kpi">
          <div class="dkpi-label">Maior Sequência W</div>
          <div class="dkpi-main">
            <span class="dkpi-val dkpi-pos">${s.longestWin} apostas</span>
          </div>
          <div class="dkpi-sub">Vitórias consecutivas</div>
        </div>

        <div class="dash-kpi">
          <div class="dkpi-label">Maior Sequência L</div>
          <div class="dkpi-main">
            <span class="dkpi-val dkpi-neg">${s.longestLoss} apostas</span>
          </div>
          <div class="dkpi-sub">Derrotas consecutivas</div>
        </div>

        <div class="dash-kpi">
          <div class="dkpi-label">Profit Factor</div>
          <div class="dkpi-main">
            <span class="dkpi-val ${s.profitFactor !== null && s.profitFactor >= 1 ? 'dkpi-pos' : 'dkpi-neg'}">${s.profitFactor !== null ? s.profitFactor.toFixed(2) : '—'}</span>
          </div>
          <div class="dkpi-sub">Ganhos brutos / Perdas brutas</div>
        </div>
      </div>
      ` : `<div class="muted" style="text-align:center;padding:2rem;">Registre suas primeiras apostas para ver as estatísticas</div>`}

      <!-- ── P&L Line Chart (full width) ── -->
      <div class="dash-chart-card">
        <div class="dash-chart-hdr">
          <div>
            <div class="dch-title">Acumulado P&amp;L</div>
            <div class="dch-sub">Evolução diária de lucro e prejuízo</div>
          </div>
        </div>
        <canvas id="dvChartLucro" style="max-height:240px"></canvas>
      </div>

      <!-- ── Bottom row: Esporte x Mercado ── -->
      <div class="dash-bottom">
        <div class="dash-chart-card">
          <div class="dch-title" style="margin-bottom:22px">Resultados por Esporte</div>
          <div id="dvEsportesList"></div>
        </div>
        <div class="dash-chart-card">
          <div class="dch-title" style="margin-bottom:22px">Resultados por Mercado</div>
          <div id="dvTypesList"></div>
        </div>
      </div>

      <!-- Total de Apostas (full width) -->
      <div class="dash-chart-card">
        <div class="dash-chart-hdr" style="margin-bottom:20px">
          <div class="dch-title">Total de Apostas</div>
          <span class="dch-total-badge">${s.total} total</span>
        </div>
        <canvas id="dvChartTipo"></canvas>
      </div>

      ${s.wonCount + s.lostCount >= 7 ? `
      <!-- ── Pattern Analysis ── -->
      <div class="dash-charts-row" style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;">
        <div class="dash-chart-card">
          <div class="dch-title">Performance por Dia da Semana</div>
          <canvas id="dvChartDayOfWeek" height="250"></canvas>
        </div>
        <div class="dash-chart-card">
          <div class="dch-title">Performance por Faixa de Odds</div>
          <canvas id="dvChartOddsRange" height="250"></canvas>
        </div>
      </div>
      ` : `<div class="muted" style="text-align:center;padding:2rem;">Aposte mais para ver padrões por dia da semana</div>`}

      <div class="dash-chart-card">
        <div class="dch-title">Hot/Cold Streaks (últimas 50 apostas)</div>
        <div id="dvStreaksTimeline" style="padding:1rem 0;"></div>
      </div>

      <div class="dash-charts-row" style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;">
        <div class="dash-chart-card">
          <div class="dch-title">Distribuição de Odds</div>
          <canvas id="dvChartOddsHist" height="250"></canvas>
        </div>
        <div class="dash-chart-card">
          <div class="dch-title">Odds vs Resultado</div>
          <canvas id="dvChartOddsScatter" height="250"></canvas>
        </div>
      </div>

      <div class="dash-chart-card">
        <div class="dch-title">Evolução do ROI</div>
        <canvas id="dvChartROI" height="200"></canvas>
      </div>

    </div>`;

  [_dvChartLucro, _dvChartTipo].forEach(c => c?.destroy());
  _dvChartLucro = _dvChartTipo = null;
  dvDrawCharts(filtered, s);
  dvRenderEsportesList(filtered);
  dvRenderTypesList(filtered);
}

// ── Render "Resultados por X" HTML lists ──────────────────────────────────
function _dvRenderBreakdown(elId, keyFn, bets) {
  const el = document.getElementById(elId);
  if (!el) return;

  const groups = {};
  bets.filter(b => b.resultado !== 'pendente').forEach(b => {
    const k = keyFn(b) || 'Outro';
    groups[k] = (groups[k] ?? 0) + (b.lucro_prejuizo ?? 0);
  });

  const entries = Object.entries(groups)
    .map(([k, v]) => [k, parseFloat(v.toFixed(2))])
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));

  if (entries.length === 0) {
    el.innerHTML = '<div style="color:var(--muted);font-family:var(--font-mono);font-size:11px">Sem dados resolvidos</div>';
    return;
  }

  const maxAbs = Math.max(...entries.map(([, v]) => Math.abs(v)), 1);
  const dotColors = ['#f59e0b', '#06b6d4', '#22c55e', '#a78bfa', '#f472b6', '#fb923c'];

  el.innerHTML = entries.map(([name, val], i) => {
    const pct   = (Math.abs(val) / maxAbs * 100).toFixed(1);
    const isPos = val >= 0;
    const dot   = dotColors[i % dotColors.length];
    return `
      <div class="dtype-row">
        <div class="dtype-info">
          <span class="dtype-name">
            <span class="dtype-dot" style="background:${dot}"></span>
            ${_escP(name)}
          </span>
          <span class="dtype-val ${isPos ? 'dkpi-pos' : 'dkpi-neg'}">${fmtMoney(val)}</span>
        </div>
        <div class="dtype-bar-wrap">
          <div class="dtype-bar ${isPos ? 'dtype-bar-pos' : 'dtype-bar-neg'}" style="width:${pct}%;background:${dot}88"></div>
        </div>
      </div>`;
  }).join('');
}

function dvRenderEsportesList(bets) {
  _dvRenderBreakdown('dvEsportesList', b => b.esporte, bets);
}

function dvRenderTypesList(bets) {
  _dvRenderBreakdown('dvTypesList', b => b.tipo_aposta, bets);
}

// ── Charts (espelham painel.js, com ids/vars "dv") ────────────────────────
function dvDrawCharts(bets, stats) {
  dvDrawLineChart(bets);
  dvDrawBetsBarChart(bets, stats);
  dvDrawDayOfWeekChart(bets);
  dvDrawOddsRangeChart(bets);
  dvDrawStreaksTimeline(bets);
  dvDrawOddsHistogram(bets);
  dvDrawOddsScatter(bets);
  dvDrawROIEvolution(bets);
}

function dvDrawLineChart(bets) {
  const ranged = bets
    .filter(b => b.resultado !== 'pendente')
    .sort((a, b) => a.data.localeCompare(b.data));

  let cum = 0;
  const labels = [];
  const data   = [];
  ranged.forEach(b => {
    cum += b.lucro_prejuizo ?? 0;
    labels.push(b.data);
    data.push(parseFloat(cum.toFixed(2)));
  });

  const ds = {
    label: 'P&L Acumulado',
    data,
    borderColor: '#22c55e',
    backgroundColor: 'transparent',
    fill: true,
    tension: 0.4,
    pointRadius: 0,
    pointHoverRadius: 5,
    pointHoverBackgroundColor: ctx => ctx.parsed.y >= 0 ? '#22c55e' : '#ef4444',
    pointHoverBorderColor: '#ffffff',
    pointHoverBorderWidth: 2,
    borderWidth: 2.5,
  };

  _dvChartLucro = new Chart(document.getElementById('dvChartLucro'), {
    type: 'line',
    data: { labels, datasets: [ds] },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          ..._TT,
          callbacks: {
            title: items => items[0]?.label || '',
            label: item => {
              const v = item.raw;
              return ` ${v >= 0 ? '+' : ''}R$ ${Math.abs(v).toFixed(2)}`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: _TICK, maxTicksLimit: 8, font: _MONO },
          grid:  { color: _GRID },
          border: { color: 'rgba(228,228,231,0.06)' },
        },
        y: {
          ticks: {
            color: _TICK, font: _MONO,
            callback: v => (v >= 0 ? '+' : '') + 'R$' + v.toFixed(0),
          },
          grid:  { color: _GRID },
          border: { color: 'rgba(228,228,231,0.06)' },
        },
      },
    },
  });
}

function dvDrawBetsBarChart(bets, stats) {
  const byDate = {};
  bets.forEach(b => {
    const d = b.data || 'N/A';
    byDate[d] = (byDate[d] ?? 0) + 1;
  });

  let labels = Object.keys(byDate).sort();
  let data   = labels.map(k => byDate[k]);

  if (labels.length > 20) {
    const byMonth = {};
    labels.forEach(d => {
      const m = d.slice(0, 7);
      byMonth[m] = (byMonth[m] ?? 0) + byDate[d];
    });
    labels = Object.keys(byMonth).sort();
    data   = labels.map(k => byMonth[k]);
  }

  const maxVal = Math.max(...data, 1);
  const maxIdx = data.indexOf(maxVal);
  const bgColors = data.map((v, i) => {
    if (i === maxIdx) return 'rgba(245,158,11,0.85)';
    const t = v / maxVal;
    return `rgba(245,158,11,${0.15 + t * 0.55})`;
  });

  _dvChartTipo = new Chart(document.getElementById('dvChartTipo'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Apostas',
        data,
        backgroundColor: bgColors,
        borderRadius: 4,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          ..._TT,
          callbacks: {
            label: item => ` ${item.raw} aposta${item.raw !== 1 ? 's' : ''}`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: _TICK, font: _MONO, maxTicksLimit: 8 },
          grid:  { display: false },
          border: { color: 'rgba(228,228,231,0.06)' },
        },
        y: {
          ticks: { color: _TICK, font: _MONO, stepSize: 1 },
          grid:  { color: _GRID },
          border: { color: 'rgba(228,228,231,0.06)' },
        },
      },
    },
  });
}

function dvDrawDayOfWeekChart(bets) {
  const days = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];
  const dayData = days.map(() => ({ pl: 0, staked: 0, count: 0, won: 0 }));
  bets.forEach(b => {
    if (b.resultado === 'pendente' || b.resultado === 'void') return;
    const d = new Date(b.data + 'T12:00:00').getDay();
    dayData[d].pl += b.lucro_prejuizo || 0;
    dayData[d].staked += b.stake || 0;
    dayData[d].count++;
    if (b.resultado === 'ganhou') dayData[d].won++;
  });
  const ctx = document.getElementById('dvChartDayOfWeek');
  if (!ctx) return;
  if (window._dvChartDayOfWeek) window._dvChartDayOfWeek.destroy();
  window._dvChartDayOfWeek = new Chart(ctx, {
    type: 'bar',
    data: { labels: days, datasets: [{ data: dayData.map(d => d.pl), backgroundColor: dayData.map(d => d.pl >= 0 ? '#22c55e' : '#ef4444'), borderRadius: 6 }] },
    options: {
      responsive: true,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => { const i = ctx.dataIndex; const d = dayData[i]; const wr = d.count > 0 ? ((d.won/d.count)*100).toFixed(0) : '0'; return [`P&L: R$ ${d.pl.toFixed(2)}`, `Apostado: R$ ${d.staked.toFixed(2)}`, `${d.count} apostas — ${wr}% win rate`]; } } } },
      scales: { y: { ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.05)' } }, x: { ticks: { color: '#888' }, grid: { display: false } } },
    },
  });
}

function dvDrawOddsRangeChart(bets) {
  const ranges = [
    { label: '1.00-1.50', min: 1.00, max: 1.50 },
    { label: '1.51-1.80', min: 1.51, max: 1.80 },
    { label: '1.81-2.20', min: 1.81, max: 2.20 },
    { label: '2.21-3.00', min: 2.21, max: 3.00 },
    { label: '3.01+', min: 3.01, max: Infinity },
  ];
  const rangeData = ranges.map(() => ({ pl: 0, count: 0, won: 0 }));
  bets.forEach(b => {
    if (b.resultado === 'pendente' || b.resultado === 'void' || !b.odds) return;
    const idx = ranges.findIndex(r => b.odds >= r.min && b.odds <= r.max);
    if (idx < 0) return;
    rangeData[idx].pl += b.lucro_prejuizo || 0;
    rangeData[idx].count++;
    if (b.resultado === 'ganhou') rangeData[idx].won++;
  });
  const ctx = document.getElementById('dvChartOddsRange');
  if (!ctx) return;
  if (window._dvChartOddsRange) window._dvChartOddsRange.destroy();
  window._dvChartOddsRange = new Chart(ctx, {
    type: 'bar',
    data: { labels: ranges.map(r => r.label), datasets: [{ label: 'P&L', data: rangeData.map(d => d.pl), backgroundColor: rangeData.map(d => d.pl >= 0 ? '#22c55e' : '#ef4444'), borderRadius: 6 }] },
    options: {
      responsive: true,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => { const i = ctx.dataIndex; const d = rangeData[i]; const wr = d.count > 0 ? ((d.won/d.count)*100).toFixed(0) : '0'; return [`P&L: R$ ${d.pl.toFixed(2)}`, `${d.count} apostas — ${wr}% win rate`]; } } } },
      scales: { y: { ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.05)' } }, x: { ticks: { color: '#888' }, grid: { display: false } } },
    },
  });
}

function dvDrawStreaksTimeline(bets) {
  const resolved = bets
    .filter(b => b.resultado === 'ganhou' || b.resultado === 'perdeu' || b.resultado === 'void')
    .sort((a, b) => a.data.localeCompare(b.data) || (a.criado_em || '').localeCompare(b.criado_em || ''))
    .slice(-50);
  if (resolved.length === 0) return;
  const container = document.getElementById('dvStreaksTimeline');
  if (!container) return;
  const items = resolved.map(b => {
    const color = b.resultado === 'ganhou' ? '#22c55e' : b.resultado === 'perdeu' ? '#ef4444' : '#666';
    return { color, resultado: b.resultado, data: b.data, desc: b.descricao || b.partida || '' };
  });
  let html = '<div style="display:flex;gap:4px;flex-wrap:wrap;align-items:center;">';
  let streakStart = 0;
  for (let i = 0; i <= items.length; i++) {
    if (i < items.length && items[i].resultado !== 'void' && items[i].resultado === items[streakStart].resultado) continue;
    const len = i - streakStart;
    const isStreak = len >= 3 && items[streakStart].resultado !== 'void';
    for (let j = streakStart; j < i; j++) {
      const it = items[j];
      const bg = isStreak ? (it.resultado === 'ganhou' ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)') : 'transparent';
      html += `<div title="${it.data} — ${it.desc}" style="width:12px;height:12px;border-radius:50%;background:${it.color};box-shadow:0 0 4px ${it.color};outline:2px solid ${bg};cursor:pointer;"></div>`;
    }
    streakStart = i;
  }
  html += '</div>';
  container.innerHTML = html;
}

function dvDrawOddsHistogram(bets) {
  const ranges = [
    { label: '1.00-1.50', min: 1.00, max: 1.50 },
    { label: '1.51-1.80', min: 1.51, max: 1.80 },
    { label: '1.81-2.20', min: 1.81, max: 2.20 },
    { label: '2.21-3.00', min: 2.21, max: 3.00 },
    { label: '3.01+', min: 3.01, max: Infinity },
  ];
  const counts = ranges.map(() => 0);
  bets.forEach(b => {
    if (!b.odds) return;
    const idx = ranges.findIndex(r => b.odds >= r.min && b.odds <= r.max);
    if (idx >= 0) counts[idx]++;
  });
  const ctx = document.getElementById('dvChartOddsHist');
  if (!ctx) return;
  if (window._dvChartOddsHist) window._dvChartOddsHist.destroy();
  window._dvChartOddsHist = new Chart(ctx, {
    type: 'bar',
    data: { labels: ranges.map(r => r.label), datasets: [{ data: counts, backgroundColor: '#f59e0b', borderRadius: 6 }] },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { title: { display: true, text: 'Qtd apostas', color: '#888' }, ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { ticks: { color: '#888' }, grid: { display: false } },
      },
    },
  });
}

function dvDrawOddsScatter(bets) {
  const won = [], lost = [];
  bets.forEach(b => {
    if (!b.odds || b.resultado === 'pendente' || b.resultado === 'void') return;
    const pt = { x: b.odds, y: b.lucro_prejuizo || 0 };
    (b.resultado === 'ganhou' ? won : lost).push(pt);
  });
  const ctx = document.getElementById('dvChartOddsScatter');
  if (!ctx) return;
  if (window._dvChartOddsScatter) window._dvChartOddsScatter.destroy();
  window._dvChartOddsScatter = new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: [
        { label: 'Ganhou', data: won, backgroundColor: '#22c55e', pointRadius: 5 },
        { label: 'Perdeu', data: lost, backgroundColor: '#ef4444', pointRadius: 5 },
      ],
    },
    plugins: [{
      afterDraw: (chart) => {
        const y = chart.scales.y.getPixelForValue(0);
        const c = chart.ctx;
        c.save(); c.setLineDash([5, 5]); c.strokeStyle = 'rgba(255,255,255,0.3)';
        c.beginPath(); c.moveTo(chart.chartArea.left, y); c.lineTo(chart.chartArea.right, y); c.stroke(); c.restore();
      },
    }],
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#ccc' } } },
      scales: {
        x: { title: { display: true, text: 'Odds', color: '#888' }, ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        y: { title: { display: true, text: 'P&L (R$)', color: '#888' }, ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.05)' } },
      },
    },
  });
}

function dvDrawROIEvolution(bets) {
  const resolved = bets.filter(b => b.resultado !== 'pendente' && b.resultado !== 'void').sort((a, b) => a.data.localeCompare(b.data));
  if (resolved.length < 2) return;
  const stakes = resolved.map(b => b.stake || 0).sort((a, b) => a - b);
  const medianStake = stakes[Math.floor(stakes.length / 2)];
  let cumStake = 0, cumPL = 0, flatStake = 0, flatPL = 0;
  const labels = [], roiActual = [], roiFlat = [];
  resolved.forEach(b => {
    cumStake += b.stake || 0;
    cumPL += b.lucro_prejuizo || 0;
    roiActual.push(cumStake > 0 ? (cumPL / cumStake) * 100 : 0);
    flatStake += medianStake;
    const flatResult = b.resultado === 'ganhou' ? medianStake * ((b.odds || 1) - 1) : -medianStake;
    flatPL += flatResult;
    roiFlat.push(flatStake > 0 ? (flatPL / flatStake) * 100 : 0);
    labels.push(b.data);
  });
  const ctx = document.getElementById('dvChartROI');
  if (!ctx) return;
  if (window._dvChartROI) window._dvChartROI.destroy();
  window._dvChartROI = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'ROI Real', data: roiActual, borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.1)', fill: true, tension: 0.3, pointRadius: 0 },
        { label: 'ROI Flat Betting', data: roiFlat, borderColor: 'rgba(255,255,255,0.3)', borderDash: [5, 5], fill: false, tension: 0.3, pointRadius: 0 },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#ccc' } } },
      scales: {
        y: { title: { display: true, text: 'ROI (%)', color: '#888' }, ticks: { color: '#888', callback: v => v.toFixed(0) + '%' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { ticks: { color: '#888', maxTicksLimit: 10 }, grid: { display: false } },
      },
    },
  });
}
