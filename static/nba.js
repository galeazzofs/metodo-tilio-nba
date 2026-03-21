/* ───────────────────────────────────────────────────────────────
   nba.js — NBA Analysis Dashboard tab
   ─────────────────────────────────────────────────────────────── */

let _nbaAnalysesCache = null;
let _nbaBetsCache = null;

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
  if (el) el.innerHTML = '<p class="muted" style="padding:1rem 0;">Engine Scorecard — em breve</p>';
}

async function renderLiveData() {
  const el = document.getElementById('nba-live');
  if (el) el.innerHTML = '<p class="muted" style="padding:1rem 0;">Dados ao Vivo — em breve</p>';
}

function renderCorrelation() {
  const el = document.getElementById('nba-correlation');
  if (el) el.innerHTML = '<p class="muted" style="padding:1rem 0;">Correlação — em breve</p>';
}
