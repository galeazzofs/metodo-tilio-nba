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
  if (!el) return;

  el.innerHTML = '<h2 class="section-title" style="margin-top:2rem;">DADOS AO VIVO</h2><p class="muted">Carregando...</p>';

  try {
    const [standingsRes, todayRes, dvpRes] = await Promise.all([
      authFetch('/api/nba/standings'),
      authFetch('/api/nba/today'),
      authFetch('/api/nba/dvp'),
    ]);

    const standings = standingsRes.ok ? await standingsRes.json() : null;
    const today = todayRes.ok ? await todayRes.json() : null;
    const dvp = dvpRes.ok ? await dvpRes.json() : null;

    const todayTeams = new Set();
    if (today && today.games) {
      today.games.forEach(g => { todayTeams.add(g.home_tricode); todayTeams.add(g.away_tricode); });
    }

    let html = '<h2 class="section-title" style="margin-top:2rem;">DADOS AO VIVO</h2>';

    if (standings) {
      html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:1.5rem;">';
      html += renderStandingsTable('Eastern Conference', standings.east, todayTeams);
      html += renderStandingsTable('Western Conference', standings.west, todayTeams);
      html += '</div>';
    } else {
      html += '<div class="muted" style="text-align:center;padding:1rem;">Standings indisponíveis no momento</div>';
    }

    html += renderTodayGames(today);
    html += renderDvPSnapshot(dvp);
    el.innerHTML = html;
  } catch (err) {
    el.innerHTML = '<h2 class="section-title" style="margin-top:2rem;">DADOS AO VIVO</h2><p class="red">Erro ao carregar dados ao vivo.</p>';
    console.error('[nba] live data error:', err);
  }
}

function renderStandingsTable(title, teams, todayTeams) {
  let html = `<div class="dash-chart-card nba-standings-table"><div class="dch-title">${title}</div>`;
  html += '<table style="width:100%;border-collapse:collapse;font-size:0.85rem;">';
  html += '<thead><tr style="color:#888;"><th>#</th><th>Time</th><th>W-L</th><th>%</th><th>GB</th></tr></thead><tbody>';
  teams.forEach(t => {
    const total = t.wins + t.losses;
    const pct = total > 0 ? (t.wins / total).toFixed(3) : '.000';
    const gb = t.games_back_from_above != null ? t.games_back_from_above.toFixed(1) : '—';
    let borderStyle = '';
    if (t.seed === 7) borderStyle = 'border-top: 2px solid #f59e0b;';
    if (t.seed === 11) borderStyle = 'border-top: 2px solid #ef4444;';
    const highlight = todayTeams.has(String(t.team_id)) ? 'color:#f59e0b;font-weight:600;' : 'color:#ccc;';
    const teamName = t.team_name || t.team_id || '?';
    html += `<tr style="${borderStyle}${highlight}"><td style="padding:4px 6px;">${t.seed}</td><td style="padding:4px 6px;">${teamName}</td><td style="padding:4px 6px;">${t.wins}-${t.losses}</td><td style="padding:4px 6px;">${pct}</td><td style="padding:4px 6px;">${gb}</td></tr>`;
  });
  html += '</tbody></table></div>';
  return html;
}

function renderTodayGames(today) {
  let html = '<h3 class="section-title" style="margin-top:1.5rem;font-size:1rem;">JOGOS DE HOJE</h3>';
  if (!today || !today.games || today.games.length === 0) {
    return html + '<div class="muted" style="text-align:center;padding:1rem;">Sem jogos hoje</div>';
  }
  const todayDate = new Date().toISOString().slice(0, 10);
  const todayAnalysis = (_nbaAnalysesCache || []).find(a => a.date === todayDate);
  const todayPicks = todayAnalysis ? (todayAnalysis.results || []) : [];

  html += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem;margin-bottom:1.5rem;">';
  today.games.forEach(g => {
    const stakeColors = { 'PLAYOFF': '#22c55e', 'PLAY-IN': '#f59e0b', 'LOW STAKE': '#666' };
    const stakeColor = stakeColors[g.stake_tag] || '#666';
    const injuries = (g.injuries || []).filter(i => i.status === 'out');
    const injuryHtml = injuries.length > 0
      ? injuries.map(i => `<span style="color:#ef4444;font-size:0.75rem;">${i.team} — ${i.name} (OUT)</span>`).join('<br>')
      : '<span style="color:#666;font-size:0.75rem;">Sem lesões confirmadas</span>';
    const pick = todayPicks.find(p => p.game === g.game_label);
    const pickBadge = pick
      ? `<div style="margin-top:0.5rem;padding:4px 8px;background:rgba(245,158,11,0.15);border:1px solid #f59e0b;border-radius:6px;font-size:0.75rem;color:#f59e0b;">⚡ ${pick.player} — ${pick.rating}</div>`
      : '';
    html += `<div class="dash-chart-card nba-game-card" style="padding:1rem;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
        <span style="font-weight:700;color:#fff;">${g.game_label}</span>
        <span style="font-size:0.7rem;padding:2px 8px;border-radius:4px;background:${stakeColor};color:#fff;">${g.stake_tag}</span>
      </div>
      <div style="font-size:0.8rem;">${injuryHtml}</div>
      ${pickBadge}
    </div>`;
  });
  html += '</div>';
  return html;
}

function renderDvPSnapshot(dvp) {
  let html = '<h3 class="section-title" style="margin-top:1.5rem;font-size:1rem;">DvP RANKINGS — PIORES DEFESAS</h3>';
  if (!dvp) {
    return html + '<div class="muted" style="text-align:center;padding:1rem;">Dados DvP indisponíveis no momento</div>';
  }
  html += '<div class="dash-chart-card"><div style="overflow-x:auto;">';
  html += '<table style="width:100%;border-collapse:collapse;font-size:0.85rem;">';
  html += '<thead><tr style="color:#888;"><th>Pos</th><th>#1</th><th>#2</th><th>#3</th><th>#4</th><th>#5</th></tr></thead><tbody>';
  ['PG', 'SG', 'SF', 'PF', 'C'].forEach(pos => {
    const teams = dvp[pos] || [];
    html += `<tr style="color:#ccc;"><td style="padding:6px;font-weight:600;color:#f59e0b;">${pos}</td>`;
    for (let i = 0; i < 5; i++) {
      const t = teams[i];
      html += `<td style="padding:6px;">${t ? `${t.team} (${t.pts.toFixed(1)})` : '—'}</td>`;
    }
    html += '</tr>';
  });
  html += '</tbody></table></div></div>';
  return html;
}

function renderCorrelation() {
  const el = document.getElementById('nba-correlation');
  if (!el) return;

  const bets = (_nbaBetsCache || []).filter(b => b.resultado !== 'pendente' && b.resultado !== 'void');
  const analyses = _nbaAnalysesCache || [];

  const followed = [], notFollowed = [];
  bets.forEach(b => {
    const match = matchBetToAnalysis(b, analyses);
    if (match) { followed.push({ ...b, engineScore: match.score }); }
    else { notFollowed.push(b); }
  });

  if (followed.length === 0) {
    el.innerHTML = `
      <h2 class="section-title" style="margin-top:2rem;">CORRELAÇÃO ENGINE × APOSTAS</h2>
      <div class="muted" style="text-align:center;padding:2rem;">
        Nenhuma aposta correspondente a picks do engine encontrada
      </div>`;
    return;
  }

  const calcROI = (arr) => {
    const staked = arr.reduce((s, b) => s + (b.stake || 0), 0);
    const pl = arr.reduce((s, b) => s + (b.lucro_prejuizo || 0), 0);
    return staked > 0 ? ((pl / staked) * 100).toFixed(1) : '—';
  };

  const roiFollowed = calcROI(followed);
  const roiNotFollowed = calcROI(notFollowed);
  const delta = roiFollowed !== '—' && roiNotFollowed !== '—'
    ? (parseFloat(roiFollowed) - parseFloat(roiNotFollowed)).toFixed(1) : '—';
  const deltaColor = delta !== '—' && parseFloat(delta) >= 0 ? '#22c55e' : '#ef4444';

  el.innerHTML = `
    <h2 class="section-title" style="margin-top:2rem;">CORRELAÇÃO ENGINE × APOSTAS</h2>
    <div class="dash-kpi-row">
      <div class="dash-kpi">
        <div class="dkpi-label">ROI Seguindo Engine</div>
        <div class="dkpi-main"><span class="dkpi-val">${roiFollowed}${roiFollowed !== '—' ? '%' : ''}</span></div>
        <div class="muted" style="font-size:0.75rem;">${followed.length} apostas</div>
      </div>
      <div class="dash-kpi">
        <div class="dkpi-label">ROI Não Seguindo</div>
        <div class="dkpi-main"><span class="dkpi-val">${roiNotFollowed}${roiNotFollowed !== '—' ? '%' : ''}</span></div>
        <div class="muted" style="font-size:0.75rem;">${notFollowed.length} apostas</div>
      </div>
      <div class="dash-kpi">
        <div class="dkpi-label">Diferença</div>
        <div class="dkpi-main"><span class="dkpi-val" style="color:${deltaColor};">${delta !== '—' ? (parseFloat(delta) >= 0 ? '+' : '') + delta + '%' : '—'}</span></div>
      </div>
    </div>
    <div class="dash-chart-card">
      <div class="dch-title">Lucro Acumulado: Engine vs Sem Engine</div>
      <canvas id="chartCorrelationPL" height="250"></canvas>
    </div>
    <div class="dash-chart-card">
      <div class="dch-title">Win Rate por Score do Engine</div>
      <canvas id="chartCorrelationScore" height="250"></canvas>
    </div>
  `;

  drawCorrelationPL(followed, notFollowed);
  drawCorrelationScore(followed);
}

function drawCorrelationPL(followed, notFollowed) {
  const sortByDate = (arr) => [...arr].sort((a, b) => a.data.localeCompare(b.data));
  const fSorted = sortByDate(followed);
  const nSorted = sortByDate(notFollowed);
  const allDates = [...new Set([...fSorted, ...nSorted].map(b => b.data))].sort();
  let cumF = 0, cumN = 0;
  const fData = [], nData = [];
  allDates.forEach(date => {
    fSorted.filter(b => b.data === date).forEach(b => cumF += b.lucro_prejuizo || 0);
    nSorted.filter(b => b.data === date).forEach(b => cumN += b.lucro_prejuizo || 0);
    fData.push(cumF); nData.push(cumN);
  });
  const ctx = document.getElementById('chartCorrelationPL');
  if (!ctx) return;
  if (window._chartCorrPL) window._chartCorrPL.destroy();
  window._chartCorrPL = new Chart(ctx, {
    type: 'line',
    data: {
      labels: allDates,
      datasets: [
        { label: 'Seguindo Engine', data: fData, borderColor: '#f59e0b', tension: 0.3, pointRadius: 0, fill: false },
        { label: 'Sem Engine', data: nData, borderColor: 'rgba(255,255,255,0.3)', tension: 0.3, pointRadius: 0, fill: false },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#ccc' } } },
      scales: {
        y: { ticks: { color: '#888', callback: v => 'R$ ' + v.toFixed(0) }, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { ticks: { color: '#888', maxTicksLimit: 10 }, grid: { display: false } },
      },
    },
  });
}

function drawCorrelationScore(followed) {
  const scores = [4, 5, 6];
  const data = scores.map(s => {
    const group = followed.filter(b => b.engineScore === s);
    const won = group.filter(b => b.resultado === 'ganhou');
    return { score: s, total: group.length, winRate: group.length > 0 ? (won.length / group.length) * 100 : 0 };
  });
  const ctx = document.getElementById('chartCorrelationScore');
  if (!ctx) return;
  if (window._chartCorrScore) window._chartCorrScore.destroy();
  window._chartCorrScore = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: scores.map(s => 'Score ' + s),
      datasets: [{ data: data.map(d => d.winRate), backgroundColor: ['#06b6d4', '#f59e0b', '#22c55e'], borderRadius: 6 }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => { const d = data[ctx.dataIndex]; return [`Win rate: ${d.winRate.toFixed(1)}%`, `${d.total} apostas`]; } } } },
      scales: {
        y: { min: 0, max: 100, ticks: { color: '#888', callback: v => v + '%' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { ticks: { color: '#888' }, grid: { display: false } },
      },
    },
  });
}
