// painel.js — Aba Painel (Dashboard)

let _chartLucro     = null;
let _chartResultado = null;
let _chartTipo      = null;
let _pluginsRegistered = false;

let _chartRange    = 'ALL';
let _allBetsCache  = null;
let _filteredCache = null;

// ── Chart.js custom plugins (registered once) ────────────────────────────
function ensurePlugins() {
  if (_pluginsRegistered) return;
  _pluginsRegistered = true;

  // Gradient fill for line chart
  Chart.register({
    id: 'lineGradientFill',
    afterLayout(chart) {
      if (chart.config.type !== 'line') return;
      const { ctx, chartArea } = chart;
      if (!chartArea) return;
      const ds = chart.data.datasets[0];
      const isPos = (ds._isPositive !== false);
      // isPos → green #16a34a  |  isNeg → red #dc2626
      const r = isPos ? 22  : 220, g = isPos ? 163 : 38, b = isPos ? 74  : 38;
      const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
      gradient.addColorStop(0,   `rgba(${r},${g},${b},0.18)`);
      gradient.addColorStop(0.5, `rgba(${r},${g},${b},0.05)`);
      gradient.addColorStop(1,   `rgba(${r},${g},${b},0)`);
      ds.backgroundColor = gradient;
    },
  });
}

// ── Load & render ─────────────────────────────────────────────────────────
async function loadPainel() {
  const container = document.getElementById('tab-painel');
  container.innerHTML = '<div style="padding:60px;text-align:center;color:var(--muted);font-family:var(--font-mono);font-size:12px;letter-spacing:0.08em">Carregando...</div>';

  try {
    const res = await authFetch('/api/bets');
    if (!res.ok) throw new Error('Erro ao carregar apostas');
    const bets = await res.json();
    _allBetsCache = bets;
    renderPainel(bets);
  } catch (e) {
    container.innerHTML = `<div style="padding:60px;text-align:center;color:var(--red);font-family:var(--font-mono);font-size:12px">${e.message}</div>`;
  }
}

function renderPainel(bets) {
  ensurePlugins();
  _allBetsCache = bets;
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

  const de  = document.getElementById('painelDe')?.value  || '';
  const ate = document.getElementById('painelAte')?.value || '';
  let filtered = bets;
  if (de)  filtered = filtered.filter(b => b.data >= de);
  if (ate) filtered = filtered.filter(b => b.data <= ate);
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

  const rb = r => _chartRange === r ? 'active' : '';

  container.innerHTML = `
    <div class="pg-wrap">

      <!-- Header -->
      <div class="pg-hdr">
        <div>
          <h1 class="section-title">PAINEL</h1>
          <div class="section-sub">Performance &amp; Analytics</div>
        </div>
        <div class="hdr-actions" style="align-items:center;gap:8px">
          <span style="font-family:var(--font-mono);font-size:10px;color:var(--muted)">De</span>
          <input type="date" class="f-input" id="painelDe" value="${de}" onchange="loadPainel()" />
          <span style="font-family:var(--font-mono);font-size:10px;color:var(--muted)">Até</span>
          <input type="date" class="f-input" id="painelAte" value="${ate}" onchange="loadPainel()" />
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

      <!-- ── P&L Line Chart (full width) ── -->
      <div class="dash-chart-card">
        <div class="dash-chart-hdr">
          <div>
            <div class="dch-title">Acumulação P&amp;L</div>
            <div class="dch-sub">Evolução diária de lucro e prejuízo</div>
          </div>
          <div class="dch-range-btns">
            <button class="dch-range-btn ${rb('1W')}"  onclick="setChartRange('1W')">1S</button>
            <button class="dch-range-btn ${rb('1M')}"  onclick="setChartRange('1M')">1M</button>
            <button class="dch-range-btn ${rb('3M')}"  onclick="setChartRange('3M')">3M</button>
            <button class="dch-range-btn ${rb('ALL')}" onclick="setChartRange('ALL')">TUDO</button>
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

// ── Chart range filter ────────────────────────────────────────────────────
function setChartRange(range) {
  _chartRange = range;

  // Update button states
  const labelMap = { '1S': '1W', '1M': '1M', '3M': '3M', 'TUDO': 'ALL' };
  document.querySelectorAll('.dch-range-btn').forEach(btn => {
    btn.classList.toggle('active', labelMap[btn.textContent.trim()] === range);
  });

  if (_chartLucro) { _chartLucro.destroy(); _chartLucro = null; }
  drawLineChart(_filteredCache || []);
}

function getRangeBets(bets) {
  if (_chartRange === 'ALL') return bets;
  const days = { '1W': 7, '1M': 30, '3M': 90 }[_chartRange];
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);
  const cutoffStr = cutoff.toISOString().slice(0, 10);
  return bets.filter(b => b.data >= cutoffStr);
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
  const dotColors = ['#623cea', '#0891b2', '#d97706', '#8b5cf6', '#0d9488', '#54426b'];

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

  return {
    totalLP: parseFloat(totalLP.toFixed(2)),
    totalStake: parseFloat(totalStake.toFixed(2)),
    wonCount, lostCount, pendingCount,
    winRate, roi, avgOdds,
    total: bets.length,
  };
}

// ── Charts ────────────────────────────────────────────────────────────────
const _GRID  = 'rgba(84,66,107,0.07)';
const _TICK  = 'rgba(84,66,107,0.45)';
const _MONO  = { family: '"IBM Plex Mono"', size: 10 };
const _TT    = {
  backgroundColor: '#ffffff',
  borderColor: '#dbd5b2',
  borderWidth: 1,
  titleColor: 'rgba(84,66,107,0.55)',
  bodyColor: '#54426b',
  padding: 12,
  titleFont: { family: '"IBM Plex Mono"', size: 10 },
  bodyFont:  { family: '"IBM Plex Mono"', size: 12, weight: '500' },
  displayColors: false,
  cornerRadius: 8,
};

function drawCharts(bets, stats) {
  drawLineChart(bets);
  drawBetsBarChart(bets, stats);
}

function drawLineChart(bets) {
  const ranged = getRangeBets(bets)
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

  const finalVal  = data.length > 0 ? data[data.length - 1] : 0;
  const isPositive = finalVal >= 0;
  const lineColor  = isPositive ? '#16a34a' : '#dc2626';

  const ds = {
    label: 'P&L Acumulado',
    data,
    borderColor: lineColor,
    backgroundColor: isPositive ? 'rgba(22,163,74,0.08)' : 'rgba(220,38,38,0.06)',
    _isPositive: isPositive,
    fill: true,
    tension: 0.4,
    pointRadius: 0,
    pointHoverRadius: 5,
    pointHoverBackgroundColor: lineColor,
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
          border: { color: 'rgba(84,66,107,0.1)' },
        },
        y: {
          ticks: {
            color: _TICK, font: _MONO,
            callback: v => (v >= 0 ? '+' : '') + 'R$' + v.toFixed(0),
          },
          grid:  { color: _GRID },
          border: { color: 'rgba(84,66,107,0.1)' },
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
    if (i === maxIdx) return 'rgba(84,66,107,0.85)';
    const t = v / maxVal;
    // vintage-grape gradient by intensity
    return `rgba(84,66,107,${0.2 + t * 0.5})`;
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
          border: { color: 'rgba(84,66,107,0.1)' },
        },
        y: {
          ticks: { color: _TICK, font: _MONO, stepSize: 1 },
          grid:  { color: _GRID },
          border: { color: 'rgba(84,66,107,0.1)' },
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
