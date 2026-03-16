// analise.js — Lógica da aba Análise
// Depende de: auth.js (authFetch), elementos do DOM injetados pelo index.html

let pollTimer  = null;
let logSeen    = 0;
let lastStatus = 'idle';

function initAnalise() {
  document.getElementById('dateChip').textContent =
    new Date().toLocaleDateString('pt-BR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  fetchStatus();
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
const GROUPS = [
  { key: 'BEST OF THE NIGHT', label: 'Melhor da Noite',    icon: '◈', css: 'best', tagLabel: '★ MELHOR DA NOITE' },
  { key: 'VERY FAVORABLE',    label: 'Muito Favorável',    icon: '◎', css: 'very', tagLabel: '↑↑ MUITO FAVORÁVEL' },
  { key: 'FAVORABLE',         label: 'Favorável',          icon: '○', css: 'fav',  tagLabel: '↑ FAVORÁVEL' },
];

const COLOR    = { best: 'var(--gold)', very: 'var(--purple)', fav: 'var(--green)' };
const COUNT_BG = { best: 'var(--gold-dim)', very: 'var(--purple-dim)', fav: 'var(--green-dim)' };

function renderResults(results) {
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
        <span class="rating-tag tag-${css}">${esc(g.tagLabel)}</span>
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
