/* ───────────────────────────────────────────────────────────────
   nba.js — NBA Analysis Dashboard tab
   ─────────────────────────────────────────────────────────────── */

let _nbaAnalysesCache = null;
let _nbaBetsCache = null;

const TEAM_TRICODES = {
  'hawks': 'ATL', 'celtics': 'BOS', 'nets': 'BKN', 'hornets': 'CHA',
  'bulls': 'CHI', 'cavaliers': 'CLE', 'mavericks': 'DAL', 'nuggets': 'DEN',
  'pistons': 'DET', 'warriors': 'GSW', 'rockets': 'HOU', 'pacers': 'IND',
  'clippers': 'LAC', 'lakers': 'LAL', 'grizzlies': 'MEM', 'heat': 'MIA',
  'bucks': 'MIL', 'timberwolves': 'MIN', 'pelicans': 'NOP', 'knicks': 'NYK',
  'thunder': 'OKC', 'magic': 'ORL', '76ers': 'PHI', 'suns': 'PHX',
  'trail blazers': 'POR', 'blazers': 'POR', 'kings': 'SAC', 'spurs': 'SAS',
  'raptors': 'TOR', 'jazz': 'UTA', 'wizards': 'WAS',
};

function matchBetToAnalysis(bet, analyses) {
  const analysis = analyses.find(a => a.date === bet.data);
  if (!analysis || !analysis.results) return null;
  const partida = (bet.partida || '').toLowerCase();
  const betTricodes = [];
  for (const [name, code] of Object.entries(TEAM_TRICODES)) {
    if (partida.includes(name)) betTricodes.push(code);
  }
  const matchingResults = analysis.results.filter(r => {
    if (!r.game) return false;
    const gameTricodes = r.game.replace(' @ ', ' ').split(' ');
    return betTricodes.some(tc => gameTricodes.includes(tc));
  });
  if (matchingResults.length === 0) return null;
  const desc = (bet.descricao || '').toLowerCase();
  const playerMatch = matchingResults.find(r => {
    const lastName = (r.player || '').split(' ').pop().toLowerCase();
    return lastName.length > 2 && desc.includes(lastName);
  });
  if (!playerMatch) return null;
  if (matchingResults.length > 1) {
    const multiMatch = matchingResults.filter(r => {
      const lastName = (r.player || '').split(' ').pop().toLowerCase();
      return lastName.length > 2 && desc.includes(lastName);
    });
    if (multiMatch.length > 1) return null;
  }
  return playerMatch;
}

async function loadNBA() {
  const panel = document.getElementById('tab-nba');
  if (!panel) return;

  panel.innerHTML = '<div class="pg-wrap"><p class="muted">Carregando dados NBA...</p></div>';

  try {
    const [analysesRes, betsRes] = await Promise.all([
      authFetch('/api/analyses'),
      authFetch('/api/bets'),
    ]);

    _nbaAnalysesCache = analysesRes.ok ? await analysesRes.json() : [];
    _nbaBetsCache = betsRes.ok ? await betsRes.json() : [];

    renderNBA();
  } catch (err) {
    panel.innerHTML = '<div class="pg-wrap"><p class="red">Erro ao carregar dados NBA.</p></div>';
    console.error('[nba] load error:', err);
  }
}

function renderNBA() {
  const panel = document.getElementById('tab-nba');
  if (!panel) return;

  panel.innerHTML = `
    <div class="pg-wrap">
      <div class="pg-hdr">
        <div>
          <h1 class="section-title">NBA DASHBOARD</h1>
          <p class="section-sub">Engine performance, dados ao vivo e correlação</p>
        </div>
      </div>

      <!-- Section: Engine Scorecard -->
      <div id="nba-scorecard"></div>

      <!-- Section: Dados ao Vivo -->
      <div id="nba-live"></div>

      <!-- Section: Correlação Engine x Apostas -->
      <div id="nba-correlation"></div>
    </div>
  `;

  renderEngineScorecard();
  renderLiveData();
  renderCorrelation();
}

function renderEngineScorecard() {
  const el = document.getElementById('nba-scorecard');
  if (!el) return;

  const analyses = _nbaAnalysesCache || [];
  const allPicks = [];
  analyses.forEach(a => {
    (a.results || []).forEach(r => {
      if (r.outcome) allPicks.push({ ...r, date: a.date });
    });
  });

  if (allPicks.length === 0) {
    el.innerHTML = `
      <h2 class="section-title" style="margin-top:2rem;">ENGINE SCORECARD</h2>
      <div class="muted" style="text-align:center;padding:2rem;">
        Dados de accuracy serão exibidos após os primeiros resultados serem processados
      </div>`;
    return;
  }

  const hits = allPicks.filter(p => p.outcome === 'hit');
  const bestPicks = allPicks.filter(p => p.score >= 6);
  const bestHits = bestPicks.filter(p => p.outcome === 'hit');
  const vfPicks = allPicks.filter(p => p.score >= 4 && p.score < 6);
  const vfHits = vfPicks.filter(p => p.outcome === 'hit');

  const accGeral = ((hits.length / allPicks.length) * 100).toFixed(1);
  const accBest = bestPicks.length > 0 ? ((bestHits.length / bestPicks.length) * 100).toFixed(1) : '—';
  const accVF = vfPicks.length > 0 ? ((vfHits.length / vfPicks.length) * 100).toFixed(1) : '—';

  el.innerHTML = `
    <h2 class="section-title" style="margin-top:2rem;">ENGINE SCORECARD</h2>
    <div class="dash-kpi-row">
      <div class="dash-kpi">
        <div class="dkpi-label">Accuracy Geral</div>
        <div class="dkpi-main"><span class="dkpi-val">${accGeral}%</span></div>
      </div>
      <div class="dash-kpi">
        <div class="dkpi-label">BEST OF THE NIGHT</div>
        <div class="dkpi-main"><span class="dkpi-val">${accBest}${accBest !== '—' ? '%' : ''}</span></div>
      </div>
      <div class="dash-kpi">
        <div class="dkpi-label">VERY FAVORABLE</div>
        <div class="dkpi-main"><span class="dkpi-val">${accVF}${accVF !== '—' ? '%' : ''}</span></div>
      </div>
      <div class="dash-kpi">
        <div class="dkpi-label">Total de Picks</div>
        <div class="dkpi-main"><span class="dkpi-val">${allPicks.length}</span></div>
      </div>
    </div>

    <div class="dash-chart-card">
      <div class="dash-chart-hdr">
        <div class="dch-title">Trend de Accuracy</div>
        <div class="dch-range-btns">
          <button class="dch-range-btn" onclick="filterAccuracyTrend(30)">30D</button>
          <button class="dch-range-btn" onclick="filterAccuracyTrend(60)">60D</button>
          <button class="dch-range-btn" onclick="filterAccuracyTrend(90)">90D</button>
          <button class="dch-range-btn active" onclick="filterAccuracyTrend(0)">TUDO</button>
        </div>
      </div>
      <canvas id="chartAccuracyTrend" height="250"></canvas>
    </div>

    <div class="dash-chart-card">
      <div class="dch-title">Accuracy por Score</div>
      <canvas id="chartAccuracyScore" height="250"></canvas>
    </div>
  `;

  drawAccuracyTrend(analyses);
  drawAccuracyScore(allPicks);
}

let _accuracyFilterDays = 0;

function filterAccuracyTrend(days) {
  _accuracyFilterDays = days;
  document.querySelectorAll('#nba-scorecard .dch-range-btn').forEach(btn => {
    btn.classList.toggle('active', parseInt(btn.textContent) === days || (days === 0 && btn.textContent === 'TUDO'));
  });
  drawAccuracyTrend(_nbaAnalysesCache || []);
}

function drawAccuracyTrend(analyses) {
  let filtered = [...analyses].sort((a, b) => a.date.localeCompare(b.date));
  if (_accuracyFilterDays > 0) {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - _accuracyFilterDays);
    const cutoffStr = cutoff.toISOString().slice(0, 10);
    filtered = filtered.filter(a => a.date >= cutoffStr);
  }
  const sorted = filtered;
  const labels = [], accAll = [], accBest = [], accVF = [];
  let cumHit = 0, cumTotal = 0, cumBestHit = 0, cumBestTotal = 0, cumVFHit = 0, cumVFTotal = 0;

  sorted.forEach(a => {
    (a.results || []).forEach(r => {
      if (!r.outcome) return;
      cumTotal++; if (r.outcome === 'hit') cumHit++;
      if (r.score >= 6) { cumBestTotal++; if (r.outcome === 'hit') cumBestHit++; }
      if (r.score >= 4 && r.score < 6) { cumVFTotal++; if (r.outcome === 'hit') cumVFHit++; }
    });
    if (cumTotal === 0) return;
    labels.push(a.date);
    accAll.push((cumHit / cumTotal) * 100);
    accBest.push(cumBestTotal > 0 ? (cumBestHit / cumBestTotal) * 100 : null);
    accVF.push(cumVFTotal > 0 ? (cumVFHit / cumVFTotal) * 100 : null);
  });

  const ctx = document.getElementById('chartAccuracyTrend');
  if (!ctx || labels.length === 0) return;
  if (window._chartAccTrend) window._chartAccTrend.destroy();

  window._chartAccTrend = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Geral', data: accAll, borderColor: '#f59e0b', tension: 0.3, pointRadius: 0 },
        { label: 'BEST OF NIGHT', data: accBest, borderColor: '#22c55e', tension: 0.3, pointRadius: 0 },
        { label: 'VERY FAVORABLE', data: accVF, borderColor: '#06b6d4', tension: 0.3, pointRadius: 0 },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#ccc' } } },
      scales: {
        y: { min: 0, max: 100, ticks: { color: '#888', callback: v => v + '%' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { ticks: { color: '#888', maxTicksLimit: 10 }, grid: { display: false } },
      },
    },
  });
}

function drawAccuracyScore(picks) {
  const scores = [4, 5, 6];
  const data = scores.map(s => {
    const group = picks.filter(p => p.score === s);
    const hits = group.filter(p => p.outcome === 'hit');
    return { score: s, total: group.length, hitRate: group.length > 0 ? (hits.length / group.length) * 100 : 0 };
  });

  const ctx = document.getElementById('chartAccuracyScore');
  if (!ctx) return;
  if (window._chartAccScore) window._chartAccScore.destroy();

  window._chartAccScore = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: scores.map(s => 'Score ' + s),
      datasets: [{ data: data.map(d => d.hitRate), backgroundColor: ['#06b6d4', '#f59e0b', '#22c55e'], borderRadius: 6 }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => { const d = data[ctx.dataIndex]; return [`Hit rate: ${d.hitRate.toFixed(1)}%`, `${d.total} picks`]; } } } },
      scales: {
        y: { min: 0, max: 100, ticks: { color: '#888', callback: v => v + '%' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { ticks: { color: '#888' }, grid: { display: false } },
      },
    },
  });
}

async function renderLiveData() {
  const el = document.getElementById('nba-live');
  if (el) el.innerHTML = '<p class="muted" style="padding:1rem 0;">Dados ao Vivo — em breve</p>';
}

function renderCorrelation() {
  const el = document.getElementById('nba-correlation');
  if (el) el.innerHTML = '<p class="muted" style="padding:1rem 0;">Correlação — em breve</p>';
}
