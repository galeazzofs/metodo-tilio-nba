// painel.js — Aba Painel (Dashboard)

let _chartLucro     = null;
let _chartResultado = null;
let _chartTipo      = null;
let _pluginsRegistered = false;

let _panelFilter   = 'all'; // 'week' | 'month' | 'year' | 'all'
let _allBetsCache  = null;
let _filteredCache = null;

// ── Chart.js custom plugins (registered once) ────────────────────────────
function ensurePlugins() {
  if (_pluginsRegistered) return;
  _pluginsRegistered = true;

  // Gradient line + fill: green above R$0, red below R$0
  Chart.register({
    id: 'lineGradientFill',
    afterLayout(chart) {
      if (chart.config.type !== 'line') return;
      const { ctx, chartArea, scales } = chart;
      if (!chartArea || !scales.y) return;
      const ds = chart.data.datasets[0];

      const GREEN = '#22c55e';
      const RED   = '#ef4444';

      const zeroY = scales.y.getPixelForValue(0);
      const { top, bottom } = chartArea;
      // ratio of where y=0 falls within the chart area (0=top, 1=bottom)
      const pct = Math.max(0, Math.min(1, (zeroY - top) / (bottom - top)));

      // Line gradient (borderColor)
      const lineGrad = ctx.createLinearGradient(0, top, 0, bottom);
      lineGrad.addColorStop(0,   GREEN);
      lineGrad.addColorStop(pct, GREEN);
      lineGrad.addColorStop(pct, RED);
      lineGrad.addColorStop(1,   RED);
      ds.borderColor = lineGrad;

      // Fill gradient (backgroundColor)
      const fillGrad = ctx.createLinearGradient(0, top, 0, bottom);
      fillGrad.addColorStop(0,   'rgba(34,197,94,0.2)');
      fillGrad.addColorStop(pct, 'rgba(34,197,94,0.03)');
      fillGrad.addColorStop(pct, 'rgba(239,68,68,0.03)');
      fillGrad.addColorStop(1,   'rgba(239,68,68,0.18)');
      ds.backgroundColor = fillGrad;
    },
  });
}

// ── Panel date filter ─────────────────────────────────────────────────────
function applyPanelFilter(bets) {
  const now = new Date();
  if (_panelFilter === 'week') {
    const day = now.getDay(); // 0=Sun, 1=Mon...
    const monday = new Date(now);
    monday.setDate(now.getDate() - (day === 0 ? 6 : day - 1));
    return bets.filter(b => b.data >= monday.toISOString().slice(0, 10));
  }
  if (_panelFilter === 'month') {
    const de = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`;
    return bets.filter(b => b.data >= de);
  }
  if (_panelFilter === 'year') {
    return bets.filter(b => b.data >= `${now.getFullYear()}-01-01`);
  }
  return bets; // 'all'
}

function setPanelFilter(f) {
  _panelFilter = f;
  if (_allBetsCache) renderPainel();
}

// ── Load & render ─────────────────────────────────────────────────────────
async function loadPainel() {
  const container = document.getElementById('tab-painel');
  container.innerHTML = '<div style="padding:60px;text-align:center;color:var(--muted);font-family:var(--font-mono);font-size:12px;letter-spacing:0.08em">Carregando...</div>';

  try {
    const res = await authFetch('/api/bets');
    if (!res.ok) throw new Error('Erro ao carregar apostas');
    _allBetsCache = await res.json();
    renderPainel();
  } catch (e) {
    container.innerHTML = `<div style="padding:60px;text-align:center;color:var(--red);font-family:var(--font-mono);font-size:12px">${e.message}</div>`;
  }
}

function renderPainel() {
  ensurePlugins();
  const bets = _allBetsCache || [];
  const container = document.getElementById('tab-painel');

  if (bets.length === 0) {
    container.innerHTML = `
      <div style="text-align:center;padding:80px 24px">
        <div style="font-size:44px;margin-bottom:16px;opacity:0.35">◧</div>
        <p style="font-family:var(--font-mono);font-size:11px;color:var(--muted);letter-spacing:0.08em;line-height:1.9">
          SEM DADOS AINDA<br>Importe ou adicione apostas para ver seu desempenho.
        </p>
      </div>`;
    return;
  }

  const filtered = applyPanelFilter(bets);
  _filteredCache = filtered;

  const s = calcStats(filtered);

  // Comparison: last 30 days vs previous 30 days (always on raw bets)
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

  const pf = f => _panelFilter === f ? 'active' : '';

  container.innerHTML = `
    <div class="pg-wrap">

      <!-- Header -->
      <div class="pg-hdr">
        <div>
          <h1 class="section-title">PAINEL</h1>
          <div class="section-sub">Performance &amp; Analytics</div>
        </div>
        <div class="dch-range-btns">
          <button class="dch-range-btn ${pf('week')}"  onclick="setPanelFilter('week')">SEMANA</button>
          <button class="dch-range-btn ${pf('month')}" onclick="setPanelFilter('month')">MÊS</button>
          <button class="dch-range-btn ${pf('year')}"  onclick="setPanelFilter('year')">ANO</button>
          <button class="dch-range-btn ${pf('all')}"   onclick="setPanelFilter('all')">TUDO</button>
        </div>
      </div>

      <!-- ── 3 KPI Cards ── -->
      <div class="dash-kpi-row">

        <!-- Total Profit -->
        <div class="dash-kpi">
          <div class="dkpi-label">Lucro Total</div>
          <div class="dkpi-main">
            <span class="dkpi-val ${s.totalLP >= 0 ? 'dkpi-pos' : 'dkpi-neg'}">${fmtMoney(s.totalLP)}</span>
            ${plChangePct !== null ? `<span class="dkpi-badge ${plChange >= 0 ? 'dbadge-pos' : 'dbadge-neg'}">${plChange >= 0 ? '+' : ''}${plChangePct.toFixed(1)}%</span>` : ''}
          </div>
          ${s.winRate !== null ? `<div class="dkpi-prog-wrap"><div class="dkpi-prog ${winFill}" style="width:${Math.min(s.winRate,100).toFixed(1)}%"></div></div>` : ''}
          <div class="dkpi-sub">vs últimos 30 dias</div>
        </div>

        <!-- Win Rate -->
        <div class="dash-kpi">
          <div class="dkpi-label">Taxa de Acerto</div>
          <div class="dkpi-main">
            <span class="dkpi-val">${s.winRate !== null ? s.winRate.toFixed(1) + '%' : '—'}</span>
            ${wrChange !== null ? `<span class="dkpi-badge ${wrChange >= 0 ? 'dbadge-pos' : 'dbadge-neg'}">${wrChange >= 0 ? '+' : ''}${wrChange.toFixed(1)}%</span>` : ''}
          </div>
          ${s.winRate !== null ? `<div class="dkpi-prog-wrap"><div class="dkpi-prog kpf-lime" style="width:${Math.min(s.winRate,100).toFixed(1)}%"></div></div>` : ''}
          <div class="dkpi-sub">Performance acumulada</div>
        </div>

        <!-- ROI -->
        <div class="dash-kpi">
          <div class="dkpi-label">Retorno sobre Investimento</div>
          <div class="dkpi-main">
            <span class="dkpi-val">${s.roi !== null ? (s.roi >= 0 ? '+' : '') + s.roi.toFixed(1) + '%' : '—'}</span>
            ${roiChange !== null ? `<span class="dkpi-badge ${roiChange >= 0 ? 'dbadge-pos' : 'dbadge-neg'}">${roiChange >= 0 ? '+' : ''}${roiChange.toFixed(1)}%</span>` : ''}
          </div>
          <div class="dkpi-sub">Performance vitalícia</div>
        </div>

        <!-- Avg Odds -->
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
        <canvas id="chartLucro" style="max-height:240px"></canvas>
      </div>

      <!-- ── Bottom row ── -->
      <div class="dash-bottom">

        <!-- Results by Type (HTML bars) -->
        <div class="dash-chart-card">
          <div class="dch-title" style="margin-bottom:22px">Resultados por Tipo</div>
          <div id="typesList"></div>
        </div>

        <!-- Total Bets bar chart -->
        <div class="dash-chart-card">
          <div class="dash-chart-hdr" style="margin-bottom:20px">
            <div class="dch-title">Total de Apostas</div>
            <span class="dch-total-badge">${s.total} total</span>
          </div>
          <canvas id="chartTipo"></canvas>
        </div>

      </div>
    </div>`;

  [_chartLucro, _chartResultado, _chartTipo].forEach(c => c?.destroy());
  _chartLucro = _chartResultado = _chartTipo = null;
  drawCharts(filtered, s);
  renderTypesList(filtered);
}

// ── Render "Results by Type" HTML list ────────────────────────────────────
function renderTypesList(bets) {
  const el = document.getElementById('typesList');
  if (!el) return;

  const byTipo = {};
  bets.filter(b => b.resultado !== 'pendente').forEach(b => {
    const t = b.tipo_aposta || 'Outro';
    byTipo[t] = (byTipo[t] ?? 0) + (b.lucro_prejuizo ?? 0);
  });

  const entries = Object.entries(byTipo)
    .map(([t, v]) => [t, parseFloat(v.toFixed(2))])
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));

  if (entries.length === 0) {
    el.innerHTML = '<div style="color:var(--muted);font-family:var(--font-mono);font-size:11px">Sem dados resolvidos</div>';
    return;
  }

  const maxAbs = Math.max(...entries.map(([, v]) => Math.abs(v)), 1);
  const dotColors = ['#f59e0b', '#06b6d4', '#22c55e', '#a78bfa', '#f472b6', '#fb923c'];

  el.innerHTML = entries.map(([tipo, val], i) => {
    const pct   = (Math.abs(val) / maxAbs * 100).toFixed(1);
    const isPos = val >= 0;
    const dot   = dotColors[i % dotColors.length];
    return `
      <div class="dtype-row">
        <div class="dtype-info">
          <span class="dtype-name">
            <span class="dtype-dot" style="background:${dot}"></span>
            ${_escP(tipo)}
          </span>
          <span class="dtype-val ${isPos ? 'dkpi-pos' : 'dkpi-neg'}">${fmtMoney(val)}</span>
        </div>
        <div class="dtype-bar-wrap">
          <div class="dtype-bar ${isPos ? 'dtype-bar-pos' : 'dtype-bar-neg'}" style="width:${pct}%;background:${dot}88"></div>
        </div>
      </div>`;
  }).join('');
}

function _escP(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Stats calculation ─────────────────────────────────────────────────────
function calcStats(bets) {
  const resolved     = bets.filter(b => b.resultado === 'ganhou' || b.resultado === 'perdeu');
  const wonCount     = bets.filter(b => b.resultado === 'ganhou').length;
  const lostCount    = bets.filter(b => b.resultado === 'perdeu').length;
  const pendingCount = bets.filter(b => b.resultado === 'pendente').length;

  const totalLP = bets
    .filter(b => ['ganhou','perdeu','void'].includes(b.resultado))
    .reduce((s, b) => s + (b.lucro_prejuizo ?? 0), 0);

  const totalStake = bets.reduce((s, b) => s + (b.stake ?? 0), 0);
  const winRate    = resolved.length > 0 ? (wonCount / resolved.length) * 100 : null;

  const roiStake = resolved.reduce((s, b) => s + (b.stake ?? 0), 0);
  const roiLP    = resolved.reduce((s, b) => s + (b.lucro_prejuizo ?? 0), 0);
  const roi      = roiStake > 0 ? (roiLP / roiStake) * 100 : null;

  const avgOdds = resolved.length > 0
    ? resolved.reduce((s, b) => s + (b.odds ?? 0), 0) / resolved.length : null;

  // Max Drawdown
  let peak = 0, maxDD = 0, cumPL = 0;
  resolved.forEach(b => {
    cumPL += b.lucro_prejuizo || 0;
    if (cumPL > peak) peak = cumPL;
    const dd = peak - cumPL;
    if (dd > maxDD) maxDD = dd;
  });

  // Streaks
  let curWin = 0, curLoss = 0, bestWin = 0, bestLoss = 0;
  resolved.forEach(b => {
    if (b.resultado === 'ganhou') { curWin++; curLoss = 0; if (curWin > bestWin) bestWin = curWin; }
    else if (b.resultado === 'perdeu') { curLoss++; curWin = 0; if (curLoss > bestLoss) bestLoss = curLoss; }
  });

  // Profit Factor
  const grossWin = resolved.reduce((s, b) => s + (b.lucro_prejuizo > 0 ? b.lucro_prejuizo : 0), 0);
  const grossLoss = resolved.reduce((s, b) => s + (b.lucro_prejuizo < 0 ? Math.abs(b.lucro_prejuizo) : 0), 0);
  const profitFactor = grossLoss > 0 ? grossWin / grossLoss : null;

  return {
    totalLP: parseFloat(totalLP.toFixed(2)),
    totalStake: parseFloat(totalStake.toFixed(2)),
    wonCount, lostCount, pendingCount,
    winRate, roi, avgOdds,
    maxDrawdown: maxDD, longestWin: bestWin, longestLoss: bestLoss, profitFactor,
    total: bets.length,
  };
}

// ── Charts ────────────────────────────────────────────────────────────────
const _GRID  = 'rgba(228,228,231,0.05)';
const _TICK  = 'rgba(228,228,231,0.35)';
const _MONO  = { family: '"JetBrains Mono"', size: 10 };
const _TT    = {
  backgroundColor: '#1a1a26',
  borderColor: 'rgba(245,158,11,0.15)',
  borderWidth: 1,
  titleColor: 'rgba(228,228,231,0.5)',
  bodyColor: '#e4e4e7',
  padding: 12,
  titleFont: { family: '"JetBrains Mono"', size: 10 },
  bodyFont:  { family: '"JetBrains Mono"', size: 12, weight: '500' },
  displayColors: false,
  cornerRadius: 8,
};

function drawCharts(bets, stats) {
  drawLineChart(bets);
  drawBetsBarChart(bets, stats);
}

function drawLineChart(bets) {
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
    borderColor: '#22c55e',        // overridden by lineGradientFill plugin
    backgroundColor: 'transparent', // overridden by lineGradientFill plugin
    fill: true,
    tension: 0.4,
    pointRadius: 0,
    pointHoverRadius: 5,
    pointHoverBackgroundColor: ctx => ctx.parsed.y >= 0 ? '#22c55e' : '#ef4444',
    pointHoverBorderColor: '#ffffff',
    pointHoverBorderWidth: 2,
    borderWidth: 2.5,
  };

  _chartLucro = new Chart(document.getElementById('chartLucro'), {
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

function drawBetsBarChart(bets, stats) {
  // Group by date → count
  const byDate = {};
  bets.forEach(b => {
    const d = b.data || 'N/A';
    byDate[d] = (byDate[d] ?? 0) + 1;
  });

  let labels = Object.keys(byDate).sort();
  let data   = labels.map(k => byDate[k]);

  // If > 20 unique dates, group by month
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

  _chartTipo = new Chart(document.getElementById('chartTipo'), {
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

// ── Formatters ────────────────────────────────────────────────────────────
function fmtMoney(v) {
  if (v == null) return '—';
  return (v >= 0 ? '↑ ' : '↓ ') + 'R$ ' + Math.abs(v).toFixed(2);
}
