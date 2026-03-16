// painel.js — Aba Painel (Dashboard)
// Depende de: auth.js (authFetch), Chart.js (CDN no index.html)

let _chartLucro     = null;
let _chartResultado = null;
let _chartTipo      = null;

async function loadPainel() {
  const container = document.getElementById('tab-painel');
  container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--muted)">Carregando...</div>';

  try {
    const res = await authFetch('/api/bets');
    if (!res.ok) throw new Error('Erro ao carregar apostas');
    const bets = await res.json();
    renderPainel(bets);
  } catch (e) {
    container.innerHTML = `<div style="padding:40px;text-align:center;color:#f87171">${e.message}</div>`;
  }
}

function renderPainel(bets) {
  const container = document.getElementById('tab-painel');

  if (bets.length === 0) {
    container.innerHTML = `
      <div style="text-align:center;padding:80px 24px;color:var(--muted)">
        <div style="font-size:52px;margin-bottom:16px">📊</div>
        <p style="font-size:15px">Sem dados ainda.<br>Importe ou adicione apostas para ver seu desempenho.</p>
      </div>`;
    return;
  }

  const de  = document.getElementById('painelDe')?.value  || '';
  const ate = document.getElementById('painelAte')?.value || '';
  let filtered = bets;
  if (de)  filtered = filtered.filter(b => b.data >= de);
  if (ate) filtered = filtered.filter(b => b.data <= ate);

  const stats = calcStats(filtered);
  const inputStyle = 'padding:8px 12px;background:var(--card);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:13px;outline:none';

  container.innerHTML = `
    <div style="max-width:1100px;margin:0 auto;padding:32px 24px">

      <!-- Header com filtros de data -->
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:28px;flex-wrap:wrap">
        <h2 style="font-size:20px;font-weight:800;flex:1;letter-spacing:-.5px">Painel de Desempenho</h2>
        <label style="font-size:12px;color:var(--muted);font-weight:600">De</label>
        <input type="date" id="painelDe" value="${de}" onchange="loadPainel()" style="${inputStyle}" />
        <label style="font-size:12px;color:var(--muted);font-weight:600">Até</label>
        <input type="date" id="painelAte" value="${ate}" onchange="loadPainel()" style="${inputStyle}" />
      </div>

      <!-- Cards de resumo -->
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:16px;margin-bottom:32px">
        ${card('Lucro / Prejuízo Total', fmtMoney(stats.totalLP),
          stats.totalLP >= 0 ? '#34d399' : '#f87171')}
        ${card('Taxa de Acerto',
          stats.winRate === null ? '—' : stats.winRate.toFixed(1) + '%',
          '#f76c1b')}
        ${card('Retorno (ROI)',
          stats.roi === null ? '—' : stats.roi.toFixed(1) + '%',
          stats.roi !== null && stats.roi >= 0 ? '#34d399' : '#f87171')}
        ${card('Odds Médias',
          stats.avgOdds === null ? '—' : stats.avgOdds.toFixed(2),
          '#fbbf24')}
        ${card('Sequência Atual', stats.streakLabel,
          stats.streakVal >= 0 ? '#34d399' : '#f87171')}
        ${card('Total de Apostas', String(stats.total), '#a78bfa')}
      </div>

      <!-- Gráficos — linha superior -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px">
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:24px">
          <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:16px">Lucro Acumulado</div>
          <canvas id="chartLucro"></canvas>
        </div>
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:24px">
          <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:16px">Apostas por Resultado</div>
          <canvas id="chartResultado"></canvas>
        </div>
      </div>

      <!-- Gráfico — linha inferior -->
      <div style="background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:24px;margin-bottom:24px">
        <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:16px">L/P por Tipo de Aposta</div>
        <canvas id="chartTipo"></canvas>
      </div>
    </div>`;

  // Destruir gráficos antigos antes de recriar
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

  // Sequência atual
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
  const gridColor = 'rgba(255,255,255,0.05)';
  const tickColor = '#64748b';

  // 1. Lucro Acumulado — gráfico de linha
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
        borderColor: '#f76c1b',
        backgroundColor: 'rgba(247,108,27,0.08)',
        fill: true,
        tension: 0.35,
        pointRadius: 2,
        pointHoverRadius: 5,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#94a3b8', font: { size: 12 } } } },
      scales: {
        x: { ticks: { color: tickColor, maxTicksLimit: 8 }, grid: { color: gridColor } },
        y: { ticks: { color: tickColor }, grid: { color: gridColor } },
      },
    },
  });

  // 2. Apostas por Resultado — rosca
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
        backgroundColor: ['#34d399','#f87171','#fbbf24','#64748b'],
        borderWidth: 0,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      cutout: '68%',
      plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', padding: 16, font: { size: 12 } } } },
    },
  });

  // 3. L/P por Tipo — barra horizontal
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
        backgroundColor: Object.values(byTipo).map(v => v >= 0 ? 'rgba(52,211,153,0.75)' : 'rgba(248,113,113,0.75)'),
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: tickColor }, grid: { color: gridColor } },
        y: { ticks: { color: '#94a3b8' }, grid: { display: false } },
      },
    },
  });
}

function card(label, value, color) {
  return `
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:22px 20px">
      <div style="font-size:11px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px">${label}</div>
      <div style="font-size:26px;font-weight:900;color:${color};letter-spacing:-.5px">${value}</div>
    </div>`;
}

function fmtMoney(v) {
  if (v == null) return '—';
  return (v >= 0 ? '+' : '') + 'R$ ' + Math.abs(v).toFixed(2);
}
