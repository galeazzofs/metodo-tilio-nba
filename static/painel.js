// painel.js — Aba Painel (Dashboard)

let _chartLucro     = null;
let _chartResultado = null;
let _chartTipo      = null;
let _pluginsRegistered = false;

// ── Chart.js custom plugins (registered once) ───────────────────────────────
function ensurePlugins() {
  if (_pluginsRegistered) return;
  _pluginsRegistered = true;

  // 1. Gradient fill for line chart
  Chart.register({
    id: 'lineGradientFill',
    afterLayout(chart) {
      if (chart.config.type !== 'line') return;
      const { ctx, chartArea } = chart;
      if (!chartArea) return;
      const ds = chart.data.datasets[0];
      const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
      gradient.addColorStop(0, 'rgba(198,241,53,0.18)');
      gradient.addColorStop(0.65, 'rgba(198,241,53,0.04)');
      gradient.addColorStop(1, 'rgba(198,241,53,0)');
      ds.backgroundColor = gradient;
    },
  });

  // 2. Center text for doughnut
  Chart.register({
    id: 'doughnutCenter',
    afterDraw(chart) {
      if (chart.config.type !== 'doughnut') return;
      const opts = chart.options?.plugins?.doughnutCenter;
      if (!opts) return;
      const { ctx, chartArea } = chart;
      if (!chartArea) return;
      const cx = (chartArea.left + chartArea.right) / 2;
      const cy = (chartArea.top + chartArea.bottom) / 2;
      ctx.save();
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.font = '800 26px "Syne", sans-serif';
      ctx.fillStyle = '#dde8f5';
      ctx.fillText(opts.value, cx, cy - 10);
      ctx.font = '400 9px "IBM Plex Mono", monospace';
      ctx.fillStyle = 'rgba(221,232,245,0.35)';
      ctx.fillText(opts.label, cx, cy + 12);
      ctx.restore();
    },
  });
}

// ── Load & render ────────────────────────────────────────────────────────────
async function loadPainel() {
  const container = document.getElementById('tab-painel');
  container.innerHTML = '<div style="padding:60px;text-align:center;color:var(--muted);font-family:var(--font-mono);font-size:12px;letter-spacing:0.08em">Carregando...</div>';

  try {
    const res = await authFetch('/api/bets');
    if (!res.ok) throw new Error('Erro ao carregar apostas');
    const bets = await res.json();
    renderPainel(bets);
  } catch (e) {
    container.innerHTML = `<div style="padding:60px;text-align:center;color:var(--red);font-family:var(--font-mono);font-size:12px">${e.message}</div>`;
  }
}

function renderPainel(bets) {
  ensurePlugins();
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

  const s = calcStats(filtered);

  // Hero class and background number
  const heroClass = s.totalLP > 0 ? 'pnl-pos' : s.totalLP < 0 ? 'pnl-neg' : 'pnl-zero';
  const bgNumRaw  = fmtMoney(s.totalLP);

  // Last 10 bets dots
  const dotsHtml = s.lastBets.length > 0 ? `
    <div class="hero-history">
      <span class="hero-hist-lbl">ÚLTIMAS ${s.lastBets.length}</span>
      ${s.lastBets.map(r =>
        `<span class="h-dot ${r === 'ganhou' ? 'h-win' : r === 'perdeu' ? 'h-loss' : 'h-pend'}" title="${r}"></span>`
      ).join('')}
    </div>` : '';

  // Win rate progress fill color
  const winFillClass = s.winRate !== null && s.winRate >= 55 ? 'kpf-lime'
                     : s.winRate !== null && s.winRate >= 40 ? 'kpf-gold'
                     : 'kpf-red';

  // Streak color
  const streakColor = s.streakVal > 0 ? 'kv-green' : s.streakVal < 0 ? 'kv-red' : 'kv-text';
  const streakSub   = s.streakVal > 0 ? 'em alta ↑' : s.streakVal < 0 ? 'em baixa ↓' : '—';

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

      <!-- ── HERO CARD ── -->
      <div class="painel-hero ${heroClass}">
        <div class="hero-bg-num">${bgNumRaw}</div>
        <div class="hero-eyebrow">Resultado Total</div>
        <div class="hero-pnl">${bgNumRaw}</div>
        <div class="hero-chips">
          <span class="hero-chip">${s.total} apostas</span>
          <span class="hero-chip">R$ ${s.totalStake.toFixed(2)} apostado</span>
          ${s.roi !== null ? `<span class="hero-chip">ROI ${s.roi >= 0 ? '+' : ''}${s.roi.toFixed(1)}%</span>` : ''}
          <span class="hero-chip">${s.wonCount}G &middot; ${s.lostCount}P${s.pendingCount > 0 ? ` &middot; ${s.pendingCount}⧖` : ''}</span>
        </div>
        ${dotsHtml}
      </div>

      <!-- ── KPI ROW (4 cards) ── -->
      <div class="kpi-row">

        <!-- Win Rate -->
        <div class="kpi-card">
          <div class="kpi-lbl">Taxa de Acerto</div>
          <div class="kpi-val kv-lime" style="font-size:26px">
            ${s.winRate !== null ? s.winRate.toFixed(1) + '%' : '—'}
          </div>
          ${s.winRate !== null ? `
          <div class="kpi-prog-wrap">
            <div class="kpi-prog-fill ${winFillClass}" style="width:${Math.min(s.winRate, 100).toFixed(1)}%"></div>
          </div>
          <div class="kpi-sub-mono">${s.wonCount}G &middot; ${s.lostCount}P de ${s.wonCount + s.lostCount}</div>
          ` : '<div class="kpi-sub-mono">sem dados</div>'}
        </div>

        <!-- Avg Odds -->
        <div class="kpi-card">
          <div class="kpi-lbl">Odds Médias</div>
          <div class="kpi-val kv-gold" style="font-size:26px">
            ${s.avgOdds !== null ? s.avgOdds.toFixed(2) : '—'}
          </div>
          <div class="kpi-sub-mono" style="margin-top:${s.winRate !== null ? '20px' : '8px'}">finalizadas</div>
        </div>

        <!-- Streak -->
        <div class="kpi-card">
          <div class="kpi-lbl">Sequência</div>
          <div class="kpi-val ${streakColor}" style="font-size:22px;letter-spacing:0">${s.streakLabel}</div>
          <div class="kpi-sub-mono" style="margin-top:${s.winRate !== null ? '20px' : '8px'}">${streakSub}</div>
        </div>

        <!-- Total -->
        <div class="kpi-card">
          <div class="kpi-lbl">Apostas</div>
          <div class="kpi-val kv-teal" style="font-size:26px">${s.total}</div>
          <div class="kpi-sub-mono" style="margin-top:${s.winRate !== null ? '20px' : '8px'}">
            ${s.pendingCount > 0 ? s.pendingCount + ' pendentes' : 'todas fechadas'}
          </div>
        </div>

      </div>

      <!-- ── P&L LINE CHART (full width) ── -->
      <div class="chart-full">
        <div class="chart-box">
          <div class="chart-lbl">P&amp;L Acumulado</div>
          <canvas id="chartLucro" style="max-height:200px"></canvas>
        </div>
      </div>

      <!-- ── DOUGHNUT + BAR ── -->
      <div class="charts-grid">
        <div class="chart-box">
          <div class="chart-lbl">Resultados</div>
          <canvas id="chartResultado" style="max-height:260px"></canvas>
        </div>
        <div class="chart-box">
          <div class="chart-lbl">P&amp;L por Tipo</div>
          <canvas id="chartTipo"></canvas>
        </div>
      </div>

    </div>`;

  [_chartLucro, _chartResultado, _chartTipo].forEach(c => c?.destroy());
  drawCharts(filtered, s);
}

// ── Stats calculation ────────────────────────────────────────────────────────
function calcStats(bets) {
  const resolved    = bets.filter(b => b.resultado === 'ganhou' || b.resultado === 'perdeu');
  const wonCount    = bets.filter(b => b.resultado === 'ganhou').length;
  const lostCount   = bets.filter(b => b.resultado === 'perdeu').length;
  const pendingCount = bets.filter(b => b.resultado === 'pendente').length;

  const totalLP = bets
    .filter(b => ['ganhou','perdeu','void'].includes(b.resultado))
    .reduce((s, b) => s + (b.lucro_prejuizo ?? 0), 0);

  const totalStake = bets.reduce((s, b) => s + (b.stake ?? 0), 0);

  const winRate = resolved.length > 0 ? (wonCount / resolved.length) * 100 : null;

  const roiStake = resolved.reduce((s, b) => s + (b.stake ?? 0), 0);
  const roiLP    = resolved.reduce((s, b) => s + (b.lucro_prejuizo ?? 0), 0);
  const roi      = roiStake > 0 ? (roiLP / roiStake) * 100 : null;

  const avgOdds = resolved.length > 0
    ? resolved.reduce((s, b) => s + (b.odds ?? 0), 0) / resolved.length
    : null;

  // Streak
  const sortedStreak = [...bets]
    .filter(b => b.resultado === 'ganhou' || b.resultado === 'perdeu')
    .sort((a, b) => (b.criado_em || b.data || '').localeCompare(a.criado_em || a.data || ''));

  let streakVal = 0, streakLabel = '—';
  if (sortedStreak.length > 0) {
    const first = sortedStreak[0].resultado;
    for (const b of sortedStreak) {
      if (b.resultado !== first) break;
      streakVal += first === 'ganhou' ? 1 : -1;
    }
    const n = Math.abs(streakVal);
    streakLabel = streakVal > 0
      ? `+${n} vitória${n > 1 ? 's' : ''}`
      : `-${n} derrota${n > 1 ? 's' : ''}`;
  }

  // Last 10 resolved bets (oldest→newest for left-to-right display)
  const lastBets = [...bets]
    .filter(b => b.resultado === 'ganhou' || b.resultado === 'perdeu')
    .sort((a, b) => (a.data || '').localeCompare(b.data || ''))
    .slice(-10)
    .map(b => b.resultado);

  return {
    totalLP: parseFloat(totalLP.toFixed(2)),
    totalStake: parseFloat(totalStake.toFixed(2)),
    wonCount, lostCount, pendingCount,
    winRate, roi, avgOdds, streakVal, streakLabel,
    total: bets.length, lastBets,
  };
}

// ── Charts ───────────────────────────────────────────────────────────────────
function drawCharts(bets, stats) {
  const gridColor = 'rgba(255,255,255,0.04)';
  const tickColor = 'rgba(221,232,245,0.3)';
  const monoFont  = { family: '"IBM Plex Mono"', size: 10 };

  const tooltip = {
    backgroundColor: 'rgba(12,16,32,0.95)',
    borderColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1,
    titleColor: 'rgba(221,232,245,0.5)',
    bodyColor: '#dde8f5',
    padding: 10,
    titleFont: { family: '"IBM Plex Mono"', size: 10 },
    bodyFont:  { family: '"IBM Plex Mono"', size: 12, weight: '500' },
    displayColors: false,
  };

  // 1. P&L Line chart
  const resolvedSorted = bets
    .filter(b => b.resultado !== 'pendente')
    .sort((a, b) => a.data.localeCompare(b.data));

  let cum = 0;
  const lineLabels = [];
  const lineData   = [];
  resolvedSorted.forEach(b => {
    cum += b.lucro_prejuizo ?? 0;
    lineLabels.push(b.data);
    lineData.push(parseFloat(cum.toFixed(2)));
  });

  _chartLucro = new Chart(document.getElementById('chartLucro'), {
    type: 'line',
    data: {
      labels: lineLabels,
      datasets: [{
        label: 'P&L Acumulado (R$)',
        data: lineData,
        borderColor: '#c6f135',
        backgroundColor: 'rgba(198,241,53,0.1)', // overridden by plugin
        fill: true,
        tension: 0.42,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: '#c6f135',
        pointHoverBorderColor: 'rgba(6,8,15,0.8)',
        pointHoverBorderWidth: 2,
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltip,
          callbacks: {
            title: (items) => items[0]?.label || '',
            label: (item) => ` ${item.raw >= 0 ? '+' : ''}R$ ${Math.abs(item.raw).toFixed(2)}`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: tickColor, maxTicksLimit: 8, font: monoFont },
          grid:  { color: gridColor },
          border: { color: 'rgba(255,255,255,0.06)' },
        },
        y: {
          ticks: {
            color: tickColor, font: monoFont,
            callback: v => (v >= 0 ? '+' : '') + 'R$' + v.toFixed(0),
          },
          grid:  { color: gridColor },
          border: { color: 'rgba(255,255,255,0.06)' },
        },
      },
    },
  });

  // 2. Results doughnut
  const counts = { Ganhou: stats.wonCount, Perdeu: stats.lostCount, Pendente: stats.pendingCount, Void: 0 };
  bets.forEach(b => { if (b.resultado === 'void') counts.Void++; });

  const doughnutData = Object.values(counts);
  const totalBets    = doughnutData.reduce((a, b) => a + b, 0);

  _chartResultado = new Chart(document.getElementById('chartResultado'), {
    type: 'doughnut',
    data: {
      labels: Object.keys(counts),
      datasets: [{
        data: doughnutData,
        backgroundColor: ['#22c55e','#f43f5e','#f59e0b','rgba(255,255,255,0.1)'],
        borderWidth: 0,
        hoverOffset: 8,
        hoverBorderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      cutout: '72%',
      plugins: {
        doughnutCenter: { value: String(totalBets), label: 'TOTAL' },
        legend: {
          position: 'bottom',
          labels: {
            color: tickColor, padding: 16, font: monoFont,
            boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'rect',
          },
        },
        tooltip: {
          ...tooltip,
          callbacks: {
            label: (item) => {
              const val = item.raw;
              const pct = totalBets > 0 ? ((val / totalBets) * 100).toFixed(1) : '0';
              return ` ${val} (${pct}%)`;
            },
          },
        },
      },
    },
  });

  // 3. P&L by type — horizontal bar
  const byTipo = {};
  bets.filter(b => b.resultado !== 'pendente').forEach(b => {
    const t = b.tipo_aposta || 'Outro';
    byTipo[t] = (byTipo[t] ?? 0) + (b.lucro_prejuizo ?? 0);
  });

  const tipoVals   = Object.values(byTipo).map(v => parseFloat(v.toFixed(2)));
  const tipoBgColors = tipoVals.map(v =>
    v >= 0 ? 'rgba(34,197,94,0.65)' : 'rgba(244,63,94,0.65)'
  );
  const tipoBorderColors = tipoVals.map(v =>
    v >= 0 ? 'rgba(34,197,94,1)' : 'rgba(244,63,94,1)'
  );

  _chartTipo = new Chart(document.getElementById('chartTipo'), {
    type: 'bar',
    data: {
      labels: Object.keys(byTipo),
      datasets: [{
        label: 'L/P (R$)',
        data: tipoVals,
        backgroundColor: tipoBgColors,
        borderColor: tipoBorderColors,
        borderWidth: 1,
        borderRadius: 4,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltip,
          callbacks: {
            label: (item) => ` ${item.raw >= 0 ? '+' : ''}R$ ${Math.abs(item.raw).toFixed(2)}`,
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: tickColor, font: monoFont,
            callback: v => (v >= 0 ? '+' : '') + 'R$' + v.toFixed(0),
          },
          grid:  { color: gridColor },
          border: { color: 'rgba(255,255,255,0.06)' },
        },
        y: {
          ticks: { color: 'rgba(221,232,245,0.55)', font: monoFont },
          grid:  { display: false },
          border: { display: false },
        },
      },
    },
  });
}

// ── Formatters ───────────────────────────────────────────────────────────────
function fmtMoney(v) {
  if (v == null) return '—';
  return (v >= 0 ? '+' : '−') + 'R$ ' + Math.abs(v).toFixed(2);
}
