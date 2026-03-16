// painel.js — Aba Painel (Dashboard)

let _chartLucro     = null;
let _chartResultado = null;
let _chartTipo      = null;

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
  const container = document.getElementById('tab-painel');

  if (bets.length === 0) {
    container.innerHTML = `
      <div style="text-align:center;padding:80px 24px">
        <div style="font-size:44px;margin-bottom:16px;opacity:0.4">◧</div>
        <p style="font-family:var(--font-mono);font-size:11px;color:var(--muted);letter-spacing:0.08em;line-height:1.8">SEM DADOS AINDA<br>Importe ou adicione apostas para ver seu desempenho.</p>
      </div>`;
    return;
  }

  const de  = document.getElementById('painelDe')?.value  || '';
  const ate = document.getElementById('painelAte')?.value || '';
  let filtered = bets;
  if (de)  filtered = filtered.filter(b => b.data >= de);
  if (ate) filtered = filtered.filter(b => b.data <= ate);

  const stats = calcStats(filtered);

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

      <!-- KPI Cards -->
      <div class="kpi-grid">
        ${kpiCard('Lucro / Prejuízo', fmtMoney(stats.totalLP),
            stats.totalLP >= 0 ? '#22c55e' : 'var(--red)')}
        ${kpiCard('Taxa de Acerto',
            stats.winRate === null ? '—' : stats.winRate.toFixed(1) + '%',
            'var(--orange)')}
        ${kpiCard('ROI',
            stats.roi === null ? '—' : stats.roi.toFixed(1) + '%',
            stats.roi !== null && stats.roi >= 0 ? '#22c55e' : 'var(--red)')}
        ${kpiCard('Odds Médias',
            stats.avgOdds === null ? '—' : stats.avgOdds.toFixed(2),
            'var(--gold)')}
        ${kpiCard('Sequência Atual', stats.streakLabel,
            stats.streakVal >= 0 ? '#22c55e' : 'var(--red)')}
        ${kpiCard('Total de Apostas', String(stats.total), 'var(--purple)')}
      </div>

      <!-- Charts -->
      <div class="charts-grid" style="margin-bottom:14px">
        <div class="chart-box chart-box-full">
          <div class="chart-lbl">P&amp;L Acumulado</div>
          <canvas id="chartLucro"></canvas>
        </div>
      </div>
      <div class="charts-grid">
        <div class="chart-box">
          <div class="chart-lbl">Apostas por Resultado</div>
          <canvas id="chartResultado"></canvas>
        </div>
        <div class="chart-box">
          <div class="chart-lbl">L/P por Tipo de Aposta</div>
          <canvas id="chartTipo"></canvas>
        </div>
      </div>
    </div>`;

  [_chartLucro, _chartResultado, _chartTipo].forEach(c => c?.destroy());
  drawCharts(filtered);
}

function calcStats(bets) {
  const resolved = bets.filter(b => b.resultado === 'ganhou' || b.resultado === 'perdeu');
  const won  = bets.filter(b => b.resultado === 'ganhou');

  const totalLP = bets
    .filter(b => ['ganhou','perdeu','void'].includes(b.resultado))
    .reduce((s, b) => s + (b.lucro_prejuizo ?? 0), 0);

  const winRate = resolved.length > 0 ? (won.length / resolved.length) * 100 : null;

  const roiStake = resolved.reduce((s, b) => s + (b.stake ?? 0), 0);
  const roiLP    = resolved.reduce((s, b) => s + (b.lucro_prejuizo ?? 0), 0);
  const roi = roiStake > 0 ? (roiLP / roiStake) * 100 : null;

  const avgOdds = resolved.length > 0
    ? resolved.reduce((s, b) => s + (b.odds ?? 0), 0) / resolved.length
    : null;

  const sorted = [...bets]
    .filter(b => b.resultado === 'ganhou' || b.resultado === 'perdeu')
    .sort((a, b) => (b.criado_em || '').localeCompare(a.criado_em || ''));

  let streakVal = 0, streakLabel = '—';
  if (sorted.length > 0) {
    const first = sorted[0].resultado;
    for (const b of sorted) {
      if (b.resultado !== first) break;
      streakVal += first === 'ganhou' ? 1 : -1;
    }
    const n = Math.abs(streakVal);
    streakLabel = streakVal > 0
      ? `+${n} vitória${n > 1 ? 's' : ''}`
      : `-${n} derrota${n > 1 ? 's' : ''}`;
  }

  return { totalLP: parseFloat(totalLP.toFixed(2)), winRate, roi, avgOdds, streakVal, streakLabel, total: bets.length };
}

function drawCharts(bets) {
  const gridColor = 'rgba(255,255,255,0.04)';
  const tickColor = 'rgba(221,232,245,0.3)';

  // 1. P&L Acumulado — linha
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
        label: 'Lucro Acumulado (R$)',
        data: lineData,
        borderColor: '#c6f135',
        backgroundColor: 'rgba(198,241,53,0.07)',
        fill: true,
        tension: 0.4,
        pointRadius: 2,
        pointHoverRadius: 5,
        pointBackgroundColor: '#c6f135',
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: tickColor, font: { size: 11, family: 'IBM Plex Mono' } } } },
      scales: {
        x: { ticks: { color: tickColor, maxTicksLimit: 10, font: { size: 10 } }, grid: { color: gridColor } },
        y: { ticks: { color: tickColor, font: { size: 10 } }, grid: { color: gridColor } },
      },
    },
  });

  // 2. Por resultado — rosca
  const counts = { Ganhou: 0, Perdeu: 0, Pendente: 0, Void: 0 };
  bets.forEach(b => {
    if (b.resultado === 'ganhou') counts.Ganhou++;
    else if (b.resultado === 'perdeu') counts.Perdeu++;
    else if (b.resultado === 'pendente') counts.Pendente++;
    else counts.Void++;
  });

  _chartResultado = new Chart(document.getElementById('chartResultado'), {
    type: 'doughnut',
    data: {
      labels: Object.keys(counts),
      datasets: [{
        data: Object.values(counts),
        backgroundColor: ['#22c55e','#f43f5e','#f59e0b','rgba(255,255,255,0.12)'],
        borderWidth: 0,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      cutout: '68%',
      plugins: { legend: { position: 'bottom', labels: { color: tickColor, padding: 16, font: { size: 11, family: 'IBM Plex Mono' } } } },
    },
  });

  // 3. L/P por tipo — barra horizontal
  const byTipo = {};
  bets.filter(b => b.resultado !== 'pendente').forEach(b => {
    const t = b.tipo_aposta || 'Outro';
    byTipo[t] = (byTipo[t] ?? 0) + (b.lucro_prejuizo ?? 0);
  });

  _chartTipo = new Chart(document.getElementById('chartTipo'), {
    type: 'bar',
    data: {
      labels: Object.keys(byTipo),
      datasets: [{
        label: 'L/P (R$)',
        data: Object.values(byTipo).map(v => parseFloat(v.toFixed(2))),
        backgroundColor: Object.values(byTipo).map(v => v >= 0 ? 'rgba(34,197,94,0.65)' : 'rgba(244,63,94,0.65)'),
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: tickColor, font: { size: 10 } }, grid: { color: gridColor } },
        y: { ticks: { color: 'rgba(221,232,245,0.55)', font: { size: 10, family: 'IBM Plex Mono' } }, grid: { display: false } },
      },
    },
  });
}

function kpiCard(label, value, color) {
  return `
    <div class="kpi-card">
      <div class="kpi-lbl">${label}</div>
      <div class="kpi-val" style="color:${color}">${value}</div>
    </div>`;
}

function fmtMoney(v) {
  if (v == null) return '—';
  return (v >= 0 ? '+' : '') + 'R$ ' + Math.abs(v).toFixed(2);
}
