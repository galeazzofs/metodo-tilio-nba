// analise.js — Lógica da aba Análise
// Depende de: auth.js (authFetch), elementos do DOM injetados pelo index.html

let pollTimer  = null;
let logSeen    = 0;
let lastStatus = 'idle';

function initAnalise() {
  document.getElementById('dateChip').textContent =
    new Date().toLocaleDateString('pt-BR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  fetchStatus();
  loadHistory();
}

// ── ações ──────────────────────────────────────────────────────────────────
async function startAnalysis() {
  setRunBtn(false);
  logSeen = 0;
  document.getElementById('results').innerHTML = '';
  document.getElementById('terminal').innerHTML = '';
  document.getElementById('logWrap').classList.add('show');

  try {
    const r = await authFetch('/api/run', { method: 'POST' });
    if (!r.ok) {
      const e = await r.json();
      showBadge('error', '⚠ ' + (e.error || 'Falha ao iniciar'));
      setRunBtn(true);
      return;
    }
  } catch {
    showBadge('error', '⚠ Servidor inacessível');
    setRunBtn(true);
    return;
  }

  showBadge('running', '<span class="spinner"></span> Analisando…');
  pollTimer = setInterval(fetchStatus, 1600);
}

async function fetchStatus() {
  try {
    const r = await authFetch('/api/status');
    if (!r.ok) return;
    const d = await r.json();
    handleState(d);
  } catch { /* ignora falha de rede */ }
}

function handleState(d) {
  if (d.status === lastStatus && d.status === 'running') {
    appendLogs(d.logs);
    return;
  }
  lastStatus = d.status;

  if (d.status === 'running') {
    showBadge('running', '<span class="spinner"></span> Analisando…');
    document.getElementById('logWrap').classList.add('show');
    appendLogs(d.logs);

  } else if (d.status === 'done') {
    clearInterval(pollTimer);
    appendLogs(d.logs);
    showBadge('done', '<span class="dot"></span> Análise concluída');
    setRunBtn(true, 'Rodar Novamente');
    renderResults(d.results);
    loadHistory();

  } else if (d.status === 'error') {
    clearInterval(pollTimer);
    showBadge('error', '⚠ ' + (d.error || 'Erro desconhecido'));
    setRunBtn(true);
  }
}

// ── helpers ────────────────────────────────────────────────────────────────
function setRunBtn(enabled, label) {
  const b = document.getElementById('runBtn');
  b.disabled = !enabled;
  if (label) b.textContent = label;
}

function showBadge(type, html) {
  const row = document.getElementById('statusRow');
  row.innerHTML = `<span class="badge badge-${type}">${html}</span>`;
}

function appendLogs(logs) {
  if (!logs || logs.length <= logSeen) return;
  const term = document.getElementById('terminal');
  logs.slice(logSeen).forEach(line => {
    const d = document.createElement('div');
    d.className = 'log-line';
    d.innerHTML = `<span class="prompt">&gt; </span>${esc(line)}`;
    term.appendChild(d);
  });
  logSeen = logs.length;
  term.scrollTop = term.scrollHeight;
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── renderizar resultados ──────────────────────────────────────────────────
const STAT_SECTIONS = [
  { key: 'pts', title: 'PONTOS', icon: '📊', abbr: 'PTS' },
  { key: 'ast', title: 'ASSISTÊNCIAS', icon: '🎯', abbr: 'AST' },
  { key: 'reb', title: 'REBOTES', icon: '🏀', abbr: 'REB' },
  { key: 'three_pt', title: 'CESTAS DE 3', icon: '💧', abbr: '3PT' },
];

const GROUPS = [
  { key: 'BEST OF THE NIGHT', label: 'Melhor da Noite',    icon: '◈', css: 'best', tagLabel: '★ MELHOR DA NOITE' },
  { key: 'VERY FAVORABLE',    label: 'Muito Favorável',    icon: '◎', css: 'very', tagLabel: '↑↑ MUITO FAVORÁVEL' },
  { key: 'FAVORABLE',         label: 'Favorável',          icon: '○', css: 'fav',  tagLabel: '↑ FAVORÁVEL' },
];

const COLOR    = { best: 'var(--gold)', very: 'var(--purple)', fav: 'var(--green)' };
const COUNT_BG = { best: 'var(--gold-dim)', very: 'var(--purple-dim)', fav: 'var(--green-dim)' };

function renderResults(data) {
  const wrap = document.getElementById('results');
  if (!data) { wrap.innerHTML = ''; return; }

  // Backward compat: old format is array
  if (Array.isArray(data)) { renderResultsLegacy(data); return; }

  // New format: object with stat keys (pts, ast, reb, three_pt)
  let html = '<div class="results-divider"></div>';

  for (const sec of STAT_SECTIONS) {
    const candidates = data[sec.key] || [];
    html += `<div class="stat-section">`;
    html += `<h2 class="stat-section-title">${sec.icon} ${sec.title} (${sec.abbr})</h2>`;

    if (candidates.length === 0) {
      html += `<p class="muted" style="opacity:0.5;font-size:0.9rem;">Nenhuma oportunidade identificada hoje</p>`;
    } else {
      for (const p of candidates) {
        html += buildStatCard(p, sec.key);
      }
    }
    html += `</div>`;
  }

  wrap.innerHTML = html;
}

function renderResultsLegacy(results) {
  const el = document.getElementById('results');

  if (!results || results.length === 0) {
    el.innerHTML = `
      <div class="empty">
        <div class="empty-icon">🏀</div>
        <p>Nenhuma jogada favorável encontrada esta noite.</p>
      </div>`;
    return;
  }

  const grouped = {};
  GROUPS.forEach(g => { grouped[g.key] = []; });
  results.forEach(p => { if (grouped[p.rating]) grouped[p.rating].push(p); });

  let html = `
    <div class="divider">
      <div class="divider-line"></div>
      <div class="divider-label">Jogadas de Hoje</div>
      <div class="divider-line"></div>
    </div>`;

  GROUPS.forEach(g => {
    const players = grouped[g.key];
    if (!players.length) return;

    html += `
      <div class="rating-group">
        <div class="group-header">
          <span class="group-icon">${g.icon}</span>
          <span class="group-label" style="color:${COLOR[g.css]}">${g.label}</span>
          <div class="group-line"></div>
          <span class="group-count"
            style="background:${COUNT_BG[g.css]};color:${COLOR[g.css]};border:1px solid ${COLOR[g.css]}33">
            ${players.length}
          </span>
        </div>`;

    players.forEach(p => { html += buildCard(p, g); });
    html += `</div>`;
  });

  el.innerHTML = html;
}

const RATING_CSS = { 'BEST OF THE NIGHT': 'best', 'VERY FAVORABLE': 'very', 'FAVORABLE': 'fav' };

function buildStatCard(p, statKey) {
  const name = p.player_name || p.player || 'Desconhecido';
  const rating = RATING_CSS[p.rating] || p.rating || 'fav';
  const ratingColor = COLOR[rating] || '#888';
  const ratingBg = COUNT_BG[rating] || 'rgba(136,136,136,0.1)';

  // Resolve line value from various formats
  const lineVal = p.line && p.line.value ? p.line.value : (typeof p.line === 'number' ? p.line : null);

  // Signals from context or flat array
  const signals = p.context?.signal_descriptions || (Array.isArray(p.signals) ? p.signals : []);

  // Starter out info
  const starterOut = p.context?.starter_out || (p.replaces ? p.replaces.join(', ') : '');

  // Build signal HTML
  const signalsHtml = signals.map(s =>
    `<div class="signal"><span class="sig-arrow">›</span><span>${esc(s)}</span></div>`
  ).join('');

  // Recent stats — highlight the relevant stat for this section
  const STAT_KEY_MAP = { pts: 'pts', ast: 'ast', reb: 'reb', three_pt: 'fg3m' };
  const STAT_LABEL_MAP = { pts: 'PTS', ast: 'AST', reb: 'REB', three_pt: '3PT' };
  let statsHtml = '';
  if (p.recent_stats) {
    const rs = p.recent_stats;
    const highlight = STAT_KEY_MAP[statKey] || statKey;
    const highlightLabel = STAT_LABEL_MAP[statKey] || statKey.toUpperCase();
    statsHtml = `<div class="stats">`;
    // Highlighted stat first
    if (rs[highlight] != null) {
      statsHtml += statCell(rs[highlight], highlightLabel);
    }
    // Then other common stats
    if (statKey !== 'pts' && rs.pts != null) statsHtml += statCell(rs.pts, 'PTS');
    if (statKey !== 'reb' && rs.reb != null) statsHtml += statCell(rs.reb, 'REB');
    if (statKey !== 'ast' && rs.ast != null) statsHtml += statCell(rs.ast, 'AST');
    if (rs.min != null) statsHtml += statCell(rs.min, 'MIN');
    if (rs.games != null) statsHtml += statCell(rs.games + 'j', 'AMOSTRA');
    statsHtml += `</div>`;
  }

  // Rating tag
  const ratingLabels = { best: '★ MELHOR DA NOITE', very: '↑↑ MUITO FAVORÁVEL', fav: '↑ FAVORÁVEL' };
  const tagLabel = ratingLabels[rating] || rating.toUpperCase();

  const lineDisplay = lineVal != null
    ? `<span class="line-value">${lineVal}</span>`
    : `<span class="line-na">N/A</span>`;

  return `
    <div class="card card-${rating}">
      <div class="card-head">
        <div>
          <div class="player-name">${esc(name)}</div>
          <div class="player-sub">
            ${p.position ? `<span class="pos-tag pos-${rating}">${esc(p.position)}</span>` : ''}
            <span class="card-meta">${esc(p.team || '')} ${p.game ? '&middot; ' + esc(p.game) : ''}</span>
            ${starterOut ? `<span class="card-meta" style="color:var(--amber)">⚠ Titular fora: ${esc(starterOut)}</span>` : ''}
          </div>
        </div>
        <div class="card-head-right">
          <span class="rating-tag tag-${rating}">${esc(tagLabel)}</span>
          <span class="line-label">Linha: ${lineDisplay}</span>
        </div>
      </div>
      <div class="signals">${signalsHtml}</div>
      ${statsHtml}
    </div>`;
}

function buildCard(p, g) {
  const css = g.css;
  const signals = (p.signals || []).map(s =>
    `<div class="signal"><span class="sig-arrow">›</span><span>${esc(s)}</span></div>`
  ).join('');

  const stats = p.recent_stats ? `
    <div class="stats">
      ${statCell(p.recent_stats.pts, 'PTS')}
      ${statCell(p.recent_stats.reb, 'REB')}
      ${statCell(p.recent_stats.ast, 'AST')}
      ${statCell(p.recent_stats.min, 'MIN')}
      ${statCell(p.recent_stats.games + 'j', 'AMOSTRA')}
    </div>` : '';

  const lineDisplay = p.line != null
    ? `<span class="line-value">${p.line} pts</span>`
    : `<span class="line-na">N/A</span>`;

  return `
    <div class="card card-${css}">
      <div class="card-head">
        <div>
          <div class="player-name">${esc(p.player)}</div>
          <div class="player-sub">
            <span class="pos-tag pos-${css}">${esc(p.position)}</span>
            <span class="card-meta">${esc(p.team)} &middot; ${esc(p.game)}</span>
          </div>
        </div>
        <div class="card-head-right">
          <span class="rating-tag tag-${css}">${esc(g.tagLabel)}</span>
          <span class="line-label">Linha: ${lineDisplay}</span>
        </div>
      </div>
      <div class="signals">${signals}</div>
      ${stats}
    </div>`;
}

function statCell(val, label) {
  return `
    <div class="stat">
      <div class="stat-val">${val}</div>
      <div class="stat-lbl">${label}</div>
    </div>`;
}

// ── Histórico de análises ──────────────────────────────────────────────────

const HIST_CSS = {
  'BEST OF THE NIGHT': 'hist-chip-best',
  'VERY FAVORABLE':    'hist-chip-very',
  'FAVORABLE':         'hist-chip-fav',
};

async function loadHistory() {
  try {
    const r = await authFetch('/api/analyses');
    if (!r.ok) return;
    const analyses = await r.json();
    renderHistory(analyses);
  } catch (e) {
    // Silencioso — histórico é feature secundária
    console.warn('[hist] Falha ao carregar histórico:', e);
  }
}

const HIST_PAGE_SIZE = 7;
let histShowCount = HIST_PAGE_SIZE;

function renderHistory(analyses) {
  // Remove seção anterior se existir
  const old = document.getElementById('histSection');
  if (old) old.remove();

  const resultsEl = document.getElementById('results');
  if (!resultsEl) return;

  if (!analyses || analyses.length === 0) return;

  // Ordenar por data decrescente (mais recente primeiro)
  const sorted = [...analyses].sort((a, b) => b.date.localeCompare(a.date));

  histShowCount = HIST_PAGE_SIZE;

  const section = document.createElement('div');
  section.id = 'histSection';
  section.className = 'hist-section';

  const visible = sorted.slice(0, histShowCount);
  const hasMore = sorted.length > histShowCount;

  section.innerHTML = `
    <div class="hist-header">
      <span class="hist-title">Histórico</span>
      <span class="hist-count">${sorted.length} dia(s) com jogadas</span>
    </div>
    <div id="histList">
      ${visible.map(a => buildHistEntry(a)).join('')}
    </div>
    ${hasMore ? `<button class="hist-more-btn" id="histMoreBtn" onclick="showMoreHistory()">Mostrar mais (${sorted.length - histShowCount} restantes)</button>` : ''}`;

  // Store sorted data for pagination
  section._allAnalyses = sorted;

  resultsEl.insertAdjacentElement('afterend', section);
}

function showMoreHistory() {
  const section = document.getElementById('histSection');
  if (!section || !section._allAnalyses) return;

  const sorted = section._allAnalyses;
  histShowCount += HIST_PAGE_SIZE;

  const list = document.getElementById('histList');
  const visible = sorted.slice(histShowCount - HIST_PAGE_SIZE, histShowCount);
  visible.forEach(a => { list.insertAdjacentHTML('beforeend', buildHistEntry(a)); });

  const btn = document.getElementById('histMoreBtn');
  if (histShowCount >= sorted.length) {
    if (btn) btn.remove();
  } else if (btn) {
    btn.textContent = `Mostrar mais (${sorted.length - histShowCount} restantes)`;
  }
}

function buildHistEntry(analysis) {
  const dateDisplay = _fmtHistDate(analysis.date);
  const trigger     = analysis.triggered_by === 'manual' ? 'manual' : 'auto';
  const badgeCss    = trigger === 'auto' ? 'hist-badge-auto' : 'hist-badge-manual';
  const badgeTxt    = trigger === 'auto' ? '⚡ Auto' : '▶ Manual';
  const id          = `hist-${analysis.date}`;

  const isNewFormat = analysis.stats && typeof analysis.stats === 'object' && !Array.isArray(analysis.stats);

  let chipsHtml = '';
  let bodyHtml  = '';
  let candidateCount = 0;

  if (isNewFormat) {
    // New format: stats grouped by stat key
    for (const sec of STAT_SECTIONS) {
      const candidates = analysis.stats[sec.key] || [];
      candidateCount += candidates.length;
      for (const c of candidates) {
        const name = c.player_name || c.player || '?';
        const rating = c.rating || 'fav';
        const color = COLOR[rating] || '#888';
        chipsHtml += `<span class="hist-cand-chip" style="border:1px solid ${color};color:${color};background:rgba(255,255,255,0.03)">${sec.icon} ${esc(name)}</span> `;
      }
    }

    // Body: stat-grouped cards
    for (const sec of STAT_SECTIONS) {
      const candidates = analysis.stats[sec.key] || [];
      if (candidates.length === 0) continue;
      bodyHtml += `<h3 class="stat-section-title" style="font-size:0.95rem;margin-top:0.8rem;">${sec.icon} ${sec.title}</h3>`;
      for (const c of candidates) {
        bodyHtml += buildStatCard(c, sec.key);
      }
    }

    if (analysis.candidate_count != null) candidateCount = analysis.candidate_count;
  } else {
    // Legacy format: use analysis.results
    const results = analysis.results || [];
    candidateCount = results.length;

    chipsHtml = results.map(p => {
      const css = HIST_CSS[p.rating] || 'hist-chip-fav';
      return `<span class="hist-cand-chip ${css}">${esc(p.player)}</span>`;
    }).join('');

    bodyHtml = results.map(p => {
      const g = GROUPS.find(g => g.key === p.rating) || GROUPS[2];
      return buildCard(p, g);
    }).join('');
  }

  return `
    <div class="hist-entry" id="${id}">
      <div class="hist-entry-head" onclick="toggleHistEntry('${id}')">
        <span class="hist-date">${dateDisplay}</span>
        <span class="hist-games">${analysis.game_count || '?'} jogos</span>
        <div class="hist-candidates">${chipsHtml}</div>
        <span class="hist-trigger-badge ${badgeCss}">${badgeTxt}</span>
        <span class="hist-chevron" id="${id}-chevron">▾</span>
      </div>
      <div class="hist-body" id="${id}-body">
        ${bodyHtml || '<div class="hist-empty">Sem candidatos neste dia.</div>'}
      </div>
    </div>`;
}

function toggleHistEntry(id) {
  const head    = document.querySelector(`#${id} .hist-entry-head`);
  const body    = document.getElementById(`${id}-body`);
  const chevron = document.getElementById(`${id}-chevron`);
  if (!head || !body || !chevron) return;

  const isOpen = body.classList.contains('open');
  body.classList.toggle('open', !isOpen);
  head.classList.toggle('open', !isOpen);
  chevron.classList.toggle('open', !isOpen);
}

function _fmtHistDate(dateStr) {
  // '2026-03-18' → 'Ter, 18 Mar'
  try {
    const d = new Date(dateStr + 'T12:00:00'); // noon para evitar problema de timezone
    return d.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short' });
  } catch {
    return dateStr;
  }
}
