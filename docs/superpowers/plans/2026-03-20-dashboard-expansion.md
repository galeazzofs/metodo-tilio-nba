# Dashboard Expansion Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the Painel tab with advanced betting analytics and create a new NBA tab with engine performance, live data, and engine-to-bets correlation.

**Architecture:** Two independent frontend JS modules (`painel.js` expansion + new `nba.js`) with shared data from existing `/api/bets` and `/api/analyses` endpoints. New backend router (`routers/nba.py`) exposes scraper data via cached HTTP endpoints. Outcome resolution adds a `POST /api/analyses/{date}/resolve` endpoint.

**Tech Stack:** Chart.js 4.4.2, vanilla JS, FastAPI, Firestore, existing scrapers (NBA Stats API, RotoWire, FantasyPros)

**Spec:** `docs/superpowers/specs/2026-03-20-dashboard-expansion-design.md`

---

## Chunk 1: Painel de Apostas — KPIs Expandidos + Cálculos

### Task 1: Add advanced stat calculations to `calcStats()`

**Files:**
- Modify: `static/painel.js:283-310` (calcStats function)
- Test: manual browser test (no JS test framework in project)

- [ ] **Step 1: Add max drawdown calculation to `calcStats()`**

In `static/painel.js`, expand the `calcStats` function to compute the 4 new metrics. Add after the existing calculations (after line ~308, before the return):

```javascript
// --- Advanced metrics ---
// Max Drawdown
let peak = 0, maxDD = 0, cumPL = 0;
resolved.forEach(b => {
  if (b.resultado === 'pendente' || b.resultado === 'void') return;
  cumPL += b.lucro_prejuizo || 0;
  if (cumPL > peak) peak = cumPL;
  const dd = peak - cumPL;
  if (dd > maxDD) maxDD = dd;
});

// Streaks
let curWin = 0, curLoss = 0, bestWin = 0, bestLoss = 0;
resolved.forEach(b => {
  if (b.resultado === 'ganhou') {
    curWin++; curLoss = 0;
    if (curWin > bestWin) bestWin = curWin;
  } else if (b.resultado === 'perdeu') {
    curLoss++; curWin = 0;
    if (curLoss > bestLoss) bestLoss = curLoss;
  }
});

// Profit Factor
const grossWin  = resolved.reduce((s, b) => s + (b.lucro_prejuizo > 0 ? b.lucro_prejuizo : 0), 0);
const grossLoss = resolved.reduce((s, b) => s + (b.lucro_prejuizo < 0 ? Math.abs(b.lucro_prejuizo) : 0), 0);
const profitFactor = grossLoss > 0 ? grossWin / grossLoss : null;
```

Then add these fields to the returned object:

```javascript
maxDrawdown: maxDD,
longestWin: bestWin,
longestLoss: bestLoss,
profitFactor,
```

**Important:** The existing `calcStats()` uses a variable called `resolved` (not `sorted`) — see `painel.js:284`. Replace every `sorted` in the code above with `resolved`. Also note `resolved` only contains `ganhou`/`perdeu` bets (no void), so the `pendente`/`void` guard in the drawdown loop is redundant but harmless. The streak and profit factor code also operates on `resolved` which is correct.

- [ ] **Step 2: Verify calcStats returns the new fields**

Open the app in browser, switch to Painel tab, open DevTools console and run:
```javascript
console.log(calcStats(_allBetsCache));
```
Expected: object contains `maxDrawdown`, `longestWin`, `longestLoss`, `profitFactor` fields.

- [ ] **Step 3: Commit**

```bash
git add static/painel.js
git commit -m "feat(painel): add max drawdown, streaks, profit factor to calcStats"
```

### Task 2: Render the 4 new KPI cards

**Files:**
- Modify: `static/painel.js:92-233` (renderPainel function)

- [ ] **Step 1: Find the KPI row HTML in `renderPainel()`**

In `renderPainel()`, locate where the 4 existing KPI cards are rendered. They use the class `dash-kpi-row`. After the closing `</div>` of the existing KPI row, add a second row of 4 cards.

- [ ] **Step 2: Add the second KPI row HTML**

In `renderPainel()`, find the closing `</div>` of the existing `dash-kpi-row` (after the Avg Odds card, search for `</div>` after the line with `apostas finalizadas`). Insert a second KPI row immediately after, using the same inline HTML pattern as the existing cards (there is NO `kpi()` helper — all cards are inline HTML):

```javascript
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
```

Note: The conditional `s.wonCount + s.lostCount > 0` checks for resolved bets (not `s.total` which includes pending). This matches the spec empty state: "No resolved bets".

- [ ] **Step 3: Test in browser**

Open app → Painel tab. Verify:
- 8 KPI cards visible (4 + 4)
- Max Drawdown shows a positive R$ value
- Streaks show integer counts
- Profit Factor shows a decimal number
- On mobile: cards wrap to 2 per row
- Empty state message when no resolved bets

- [ ] **Step 4: Commit**

```bash
git add static/painel.js
git commit -m "feat(painel): render advanced KPI cards (drawdown, streaks, profit factor)"
```

---

## Chunk 2: Painel de Apostas — Pattern Analysis Charts

### Task 3: Performance by Day of Week chart

**Files:**
- Modify: `static/painel.js` (add new chart function + call from renderPainel)

- [ ] **Step 1: Add `drawDayOfWeekChart(bets)` function**

Add after `drawBetsBarChart()` in `painel.js`:

```javascript
function drawDayOfWeekChart(bets) {
  const days = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];
  const dayData = days.map(() => ({ pl: 0, staked: 0, count: 0, won: 0 }));
  bets.forEach(b => {
    if (b.resultado === 'pendente' || b.resultado === 'void') return;
    const d = new Date(b.data + 'T12:00:00').getDay(); // 0=Sun
    dayData[d].pl += b.lucro_prejuizo || 0;
    dayData[d].staked += b.stake || 0;
    dayData[d].count++;
    if (b.resultado === 'ganhou') dayData[d].won++;
  });

  const ctx = document.getElementById('chartDayOfWeek');
  if (!ctx) return;
  if (window._chartDayOfWeek) window._chartDayOfWeek.destroy();

  window._chartDayOfWeek = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: days,
      datasets: [{
        data: dayData.map(d => d.pl),
        backgroundColor: dayData.map(d => d.pl >= 0 ? '#22c55e' : '#ef4444'),
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const i = ctx.dataIndex;
              const d = dayData[i];
              const wr = d.count > 0 ? ((d.won / d.count) * 100).toFixed(0) : '0';
              return [
                `P&L: R$ ${d.pl.toFixed(2)}`,
                `Apostado: R$ ${d.staked.toFixed(2)}`,
                `${d.count} apostas — ${wr}% win rate`,
              ];
            },
          },
        },
      },
      scales: {
        y: { ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { ticks: { color: '#888' }, grid: { display: false } },
      },
    },
  });
}
```

- [ ] **Step 2: Add canvas to renderPainel HTML**

In `renderPainel()`, after the existing charts section (after the `</div>` closing `dash-bottom`), add a new chart section. Wrap in a minimum bet threshold check (spec requires 7+ resolved bets for pattern analysis):

```html
      ${s.wonCount + s.lostCount >= 7 ? `
      <!-- ── Pattern Analysis ── -->
      <div class="dash-charts-row" style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;">
        <div class="dash-chart-card">
          <div class="dch-title">Performance por Dia da Semana</div>
          <canvas id="chartDayOfWeek" height="250"></canvas>
        </div>
        <div class="dash-chart-card">
          <div class="dch-title">Performance por Faixa de Odds</div>
          <canvas id="chartOddsRange" height="250"></canvas>
        </div>
      </div>
      ` : `<div class="muted" style="text-align:center;padding:2rem;">Aposte mais para ver padrões por dia da semana</div>`}
```

Note: The CSS class `dash-charts-row` does not exist yet. The inline `style` handles the grid. For mobile responsiveness, add a `@media` rule in the `<style>` section of `index.html` (see Task 19).

- [ ] **Step 3: Call the chart function from drawCharts**

In `drawCharts(bets, stats)` (line ~329), add:
```javascript
drawDayOfWeekChart(bets);
```

- [ ] **Step 4: Test in browser**

Verify bar chart renders with 7 bars (Dom-Sáb), green/red colors, tooltips showing P&L, staked, count, win rate.

- [ ] **Step 5: Commit**

```bash
git add static/painel.js
git commit -m "feat(painel): add day-of-week performance chart"
```

### Task 4: Performance by Odds Range chart

**Files:**
- Modify: `static/painel.js` (add new chart function)

- [ ] **Step 1: Add `drawOddsRangeChart(bets)` function**

```javascript
function drawOddsRangeChart(bets) {
  const ranges = [
    { label: '1.00-1.50', min: 1.00, max: 1.50 },
    { label: '1.51-1.80', min: 1.51, max: 1.80 },
    { label: '1.81-2.20', min: 1.81, max: 2.20 },
    { label: '2.21-3.00', min: 2.21, max: 3.00 },
    { label: '3.01+',     min: 3.01, max: Infinity },
  ];
  const rangeData = ranges.map(() => ({ pl: 0, count: 0, won: 0 }));
  bets.forEach(b => {
    if (b.resultado === 'pendente' || b.resultado === 'void' || !b.odds) return;
    const idx = ranges.findIndex(r => b.odds >= r.min && b.odds <= r.max);
    if (idx < 0) return;
    rangeData[idx].pl += b.lucro_prejuizo || 0;
    rangeData[idx].count++;
    if (b.resultado === 'ganhou') rangeData[idx].won++;
  });

  const ctx = document.getElementById('chartOddsRange');
  if (!ctx) return;
  if (window._chartOddsRange) window._chartOddsRange.destroy();

  window._chartOddsRange = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ranges.map(r => r.label),
      datasets: [{
        label: 'P&L',
        data: rangeData.map(d => d.pl),
        backgroundColor: rangeData.map(d => d.pl >= 0 ? '#22c55e' : '#ef4444'),
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const i = ctx.dataIndex;
              const d = rangeData[i];
              const wr = d.count > 0 ? ((d.won / d.count) * 100).toFixed(0) : '0';
              return [
                `P&L: R$ ${d.pl.toFixed(2)}`,
                `${d.count} apostas — ${wr}% win rate`,
              ];
            },
          },
        },
      },
      scales: {
        y: { ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { ticks: { color: '#888' }, grid: { display: false } },
      },
    },
  });
}
```

- [ ] **Step 2: Call from drawCharts**

Add `drawOddsRangeChart(bets);` in `drawCharts()`.

- [ ] **Step 3: Test in browser**

Verify 5 bars with odds ranges, green/red, tooltips with count and win rate.

- [ ] **Step 4: Commit**

```bash
git add static/painel.js
git commit -m "feat(painel): add odds range performance chart"
```

### Task 5: Hot/Cold Streaks timeline

**Files:**
- Modify: `static/painel.js`

- [ ] **Step 1: Add `drawStreaksTimeline(bets)` function**

```javascript
function drawStreaksTimeline(bets) {
  // Last 50 resolved bets, chronological order
  const resolved = bets
    .filter(b => b.resultado === 'ganhou' || b.resultado === 'perdeu' || b.resultado === 'void')
    .sort((a, b) => a.data.localeCompare(b.data) || (a.criado_em || '').localeCompare(b.criado_em || ''))
    .slice(-50);

  if (resolved.length === 0) return;

  const container = document.getElementById('streaksTimeline');
  if (!container) return;

  // Detect streaks
  const items = resolved.map((b, i) => {
    const color = b.resultado === 'ganhou' ? '#22c55e' : b.resultado === 'perdeu' ? '#ef4444' : '#666';
    return { color, resultado: b.resultado, data: b.data, desc: b.descricao || b.partida || '' };
  });

  // Mark streak runs (3+ consecutive same result — void breaks streaks)
  let html = '<div style="display:flex;gap:4px;flex-wrap:wrap;align-items:center;">';
  let streakStart = 0;
  for (let i = 0; i <= items.length; i++) {
    // void/push breaks any streak — only ganhou/perdeu form streaks
    if (i < items.length && items[i].resultado !== 'void' && items[i].resultado === items[streakStart].resultado) continue;
    const len = i - streakStart;
    const isStreak = len >= 3 && items[streakStart].resultado !== 'void';
    for (let j = streakStart; j < i; j++) {
      const it = items[j];
      const bg = isStreak ? (it.resultado === 'ganhou' ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)') : 'transparent';
      html += `<div title="${it.data} — ${it.desc}" style="width:12px;height:12px;border-radius:50%;background:${it.color};box-shadow:0 0 4px ${it.color};outline:2px solid ${bg};cursor:pointer;"></div>`;
    }
    streakStart = i;
  }
  html += '</div>';
  container.innerHTML = html;
}
```

- [ ] **Step 2: Add streaks container to renderPainel HTML**

After the two-column chart row added in Task 3, add:

```html
<div class="dash-chart-card">
  <div class="dch-title">Hot/Cold Streaks (últimas 50 apostas)</div>
  <div id="streaksTimeline" style="padding:1rem 0;"></div>
</div>
```

- [ ] **Step 3: Call from drawCharts**

Add `drawStreaksTimeline(bets);` in `drawCharts()`.

- [ ] **Step 4: Test in browser**

Verify: colored dots timeline, streaks of 3+ have background highlight, hover tooltip shows date and match.

- [ ] **Step 5: Commit**

```bash
git add static/painel.js
git commit -m "feat(painel): add hot/cold streaks timeline"
```

---

## Chunk 3: Painel de Apostas — Distribution Charts

### Task 6: Odds Histogram chart

**Files:**
- Modify: `static/painel.js`

- [ ] **Step 1: Add `drawOddsHistogram(bets)` function**

Uses the same ranges as the odds range chart for consistency:

```javascript
function drawOddsHistogram(bets) {
  const ranges = [
    { label: '1.00-1.50', min: 1.00, max: 1.50 },
    { label: '1.51-1.80', min: 1.51, max: 1.80 },
    { label: '1.81-2.20', min: 1.81, max: 2.20 },
    { label: '2.21-3.00', min: 2.21, max: 3.00 },
    { label: '3.01+',     min: 3.01, max: Infinity },
  ];
  const counts = ranges.map(() => 0);
  bets.forEach(b => {
    if (!b.odds) return;
    const idx = ranges.findIndex(r => b.odds >= r.min && b.odds <= r.max);
    if (idx >= 0) counts[idx]++;
  });

  const ctx = document.getElementById('chartOddsHist');
  if (!ctx) return;
  if (window._chartOddsHist) window._chartOddsHist.destroy();

  window._chartOddsHist = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ranges.map(r => r.label),
      datasets: [{
        data: counts,
        backgroundColor: '#f59e0b',
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { title: { display: true, text: 'Qtd apostas', color: '#888' }, ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { ticks: { color: '#888' }, grid: { display: false } },
      },
    },
  });
}
```

- [ ] **Step 2: Add canvas to renderPainel HTML**

Add a new two-column chart row after the streaks section:

```html
<div class="dash-charts-row" style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;">
  <div class="dash-chart-card">
    <div class="dch-title">Distribuição de Odds</div>
    <canvas id="chartOddsHist" height="250"></canvas>
  </div>
  <div class="dash-chart-card">
    <div class="dch-title">Odds vs Resultado</div>
    <canvas id="chartOddsScatter" height="250"></canvas>
  </div>
</div>
```

- [ ] **Step 3: Call from drawCharts and test**

Add `drawOddsHistogram(bets);` in `drawCharts()`. Verify amber bars, 5 bins, counts shown.

- [ ] **Step 4: Commit**

```bash
git add static/painel.js
git commit -m "feat(painel): add odds distribution histogram"
```

### Task 7: Scatter Plot — Odds vs Resultado

**Files:**
- Modify: `static/painel.js`

- [ ] **Step 1: Add `drawOddsScatter(bets)` function**

```javascript
function drawOddsScatter(bets) {
  const won = [], lost = [];
  bets.forEach(b => {
    if (!b.odds || b.resultado === 'pendente' || b.resultado === 'void') return;
    const pt = { x: b.odds, y: b.lucro_prejuizo || 0 };
    (b.resultado === 'ganhou' ? won : lost).push(pt);
  });

  const ctx = document.getElementById('chartOddsScatter');
  if (!ctx) return;
  if (window._chartOddsScatter) window._chartOddsScatter.destroy();

  window._chartOddsScatter = new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: [
        { label: 'Ganhou', data: won, backgroundColor: '#22c55e', pointRadius: 5 },
        { label: 'Perdeu', data: lost, backgroundColor: '#ef4444', pointRadius: 5 },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: '#ccc' } },
        annotation: {
          annotations: {
            zeroline: { type: 'line', yMin: 0, yMax: 0, borderColor: 'rgba(255,255,255,0.3)', borderDash: [5, 5] },
          },
        },
      },
      scales: {
        x: { title: { display: true, text: 'Odds', color: '#888' }, ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        y: { title: { display: true, text: 'P&L (R$)', color: '#888' }, ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.05)' } },
      },
    },
  });
}
```

Note: The annotation plugin for the Y=0 reference line requires `chartjs-plugin-annotation`. Check if it's already loaded. If not, either add the CDN script tag or draw the line manually using a custom plugin:

```javascript
// Alternative: simple zero-line without annotation plugin
plugins: [{
  afterDraw: (chart) => {
    const y = chart.scales.y.getPixelForValue(0);
    const ctx = chart.ctx;
    ctx.save();
    ctx.setLineDash([5, 5]);
    ctx.strokeStyle = 'rgba(255,255,255,0.3)';
    ctx.beginPath();
    ctx.moveTo(chart.chartArea.left, y);
    ctx.lineTo(chart.chartArea.right, y);
    ctx.stroke();
    ctx.restore();
  },
}],
```

Use the inline plugin approach to avoid adding a new dependency.

- [ ] **Step 2: Call from drawCharts and test**

Add `drawOddsScatter(bets);` in `drawCharts()`. Verify scatter plot with green/red dots, zero reference line.

- [ ] **Step 3: Commit**

```bash
git add static/painel.js
git commit -m "feat(painel): add odds vs resultado scatter plot"
```

### Task 8: ROI Evolution line chart

**Files:**
- Modify: `static/painel.js`

- [ ] **Step 1: Add `drawROIEvolution(bets)` function**

```javascript
function drawROIEvolution(bets) {
  const resolved = bets
    .filter(b => b.resultado !== 'pendente' && b.resultado !== 'void')
    .sort((a, b) => a.data.localeCompare(b.data));
  if (resolved.length < 2) return;

  // Median stake for flat betting reference
  const stakes = resolved.map(b => b.stake || 0).sort((a, b) => a - b);
  const medianStake = stakes[Math.floor(stakes.length / 2)];

  // Cumulative ROI (actual)
  let cumStake = 0, cumPL = 0;
  // Cumulative ROI (flat betting)
  let flatStake = 0, flatPL = 0;

  const labels = [], roiActual = [], roiFlat = [];
  resolved.forEach(b => {
    cumStake += b.stake || 0;
    cumPL += b.lucro_prejuizo || 0;
    roiActual.push(cumStake > 0 ? (cumPL / cumStake) * 100 : 0);

    // Flat betting: same result but with median stake
    flatStake += medianStake;
    const flatResult = b.resultado === 'ganhou'
      ? medianStake * ((b.odds || 1) - 1)
      : -medianStake;
    flatPL += flatResult;
    roiFlat.push(flatStake > 0 ? (flatPL / flatStake) * 100 : 0);

    labels.push(b.data);
  });

  const ctx = document.getElementById('chartROI');
  if (!ctx) return;
  if (window._chartROI) window._chartROI.destroy();

  window._chartROI = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'ROI Real',
          data: roiActual,
          borderColor: '#f59e0b',
          backgroundColor: 'rgba(245,158,11,0.1)',
          fill: true,
          tension: 0.3,
          pointRadius: 0,
        },
        {
          label: 'ROI Flat Betting',
          data: roiFlat,
          borderColor: 'rgba(255,255,255,0.3)',
          borderDash: [5, 5],
          fill: false,
          tension: 0.3,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#ccc' } } },
      scales: {
        y: { title: { display: true, text: 'ROI (%)', color: '#888' }, ticks: { color: '#888', callback: v => v.toFixed(0) + '%' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { ticks: { color: '#888', maxTicksLimit: 10 }, grid: { display: false } },
      },
    },
  });
}
```

- [ ] **Step 2: Add canvas to renderPainel HTML**

After the histogram/scatter row, add full-width:

```html
<div class="dash-chart-card">
  <div class="dch-title">Evolução do ROI</div>
  <canvas id="chartROI" height="200"></canvas>
</div>
```

- [ ] **Step 3: Call from drawCharts and test**

Add `drawROIEvolution(bets);`. Verify: amber line (actual), dashed gray line (flat), both on same chart.

- [ ] **Step 4: Commit**

```bash
git add static/painel.js
git commit -m "feat(painel): add ROI evolution chart with flat betting comparison"
```

---

## Chunk 4: NBA Backend — New API Endpoints + Outcome Resolution

### Task 9: Create NBA router with cached scraper endpoints

**Files:**
- Create: `routers/nba.py`
- Modify: `app.py:40-41` (register new router)

- [ ] **Step 1: Write the failing test for the cache utility**

Create `tests/test_nba_router.py`:

```python
"""Tests for routers/nba.py caching and endpoint logic."""
import time
from routers.nba import _cache_get, _cache_set, _cache


def test_cache_set_and_get():
    _cache.clear()
    _cache_set("test_key", {"data": 1}, ttl=10)
    assert _cache_get("test_key") == {"data": 1}


def test_cache_expired():
    _cache.clear()
    _cache_set("test_key", {"data": 1}, ttl=0)
    time.sleep(0.1)
    assert _cache_get("test_key") is None
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/test_nba_router.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'routers.nba'`

- [ ] **Step 3: Create `routers/nba.py` with cache + endpoints**

```python
"""
routers/nba.py — NBA live data endpoints with in-memory caching.
Exposes scraper data via HTTP for the NBA frontend tab.
"""
import time
from fastapi import APIRouter, Depends
from deps import require_auth

router = APIRouter(prefix="/api/nba", tags=["nba"])

# ── Simple TTL cache ──
_cache: dict = {}


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and time.time() < entry["expires"]:
        return entry["data"]
    return None


def _cache_set(key: str, data, ttl: int):
    _cache[key] = {"data": data, "expires": time.time() + ttl}


def invalidate_cache():
    """Called after analysis run completes to refresh data."""
    _cache.clear()


@router.get("/standings")
def get_standings(uid: str = Depends(require_auth)):
    cached = _cache_get("standings")
    if cached:
        return cached
    from scrapers.nba import get_conference_standings
    data = get_conference_standings()
    # Restructure: group by conference
    east, west = [], []
    for team_id, info in data.items():
        entry = {"team_id": team_id, **info}
        (east if info["conference"] == "East" else west).append(entry)
    east.sort(key=lambda x: x["seed"])
    west.sort(key=lambda x: x["seed"])
    result = {"east": east, "west": west}
    _cache_set("standings", result, ttl=3600)
    return result


@router.get("/today")
def get_today_games(uid: str = Depends(require_auth)):
    cached = _cache_get("today")
    if cached:
        return cached
    from scrapers.nba import get_todays_games, get_conference_standings
    from scrapers.rotowire import get_projected_lineups
    from analysis.engine import filter_games_by_stake

    games = get_todays_games()
    if not games:
        result = {"games": [], "message": "Sem jogos hoje"}
        _cache_set("today", result, ttl=1800)
        return result

    standings = get_conference_standings()
    lineups = get_projected_lineups()
    filtered = filter_games_by_stake(games, standings)

    enriched = []
    for g in games:
        home_tc = g.get("home_tricode", "")
        away_tc = g.get("away_tricode", "")
        game_label = f"{away_tc} @ {home_tc}"

        # Determine stake tag per spec: PLAYOFF, PLAY-IN, or LOW STAKE
        # Check standings for both teams to determine highest stake
        from analysis.engine import _team_has_stake
        stake_tag = "LOW STAKE"
        for team_key in ["home_team_id", "away_team_id"]:
            team_id = g.get(team_key)
            team_standings = standings.get(team_id, {}) if team_id else {}
            if team_standings:
                has_stake, reason = _team_has_stake(team_standings)
                if has_stake:
                    seed = team_standings.get("seed", 99)
                    if seed <= 6:
                        stake_tag = "PLAYOFF"
                        break  # highest possible
                    elif seed <= 10:
                        if stake_tag != "PLAYOFF":
                            stake_tag = "PLAY-IN"

        # Get injuries from lineups
        injuries = []
        for team_tc in [home_tc, away_tc]:
            team_lineup = lineups.get(team_tc, {})
            for status_key in ["out", "questionable"]:
                for player in team_lineup.get(status_key, []):
                    injuries.append({
                        "name": player.get("name", ""),
                        "team": team_tc,
                        "status": status_key,
                    })

        enriched.append({
            **g,
            "game_label": game_label,
            "stake_tag": stake_tag,
            "injuries": injuries,
        })

    # Sort high stake first
    enriched.sort(key=lambda x: x["stake_tag"] != "HIGH STAKE")
    result = {"games": enriched}
    _cache_set("today", result, ttl=1800)
    return result


@router.get("/dvp")
def get_dvp(uid: str = Depends(require_auth)):
    cached = _cache_get("dvp")
    if cached:
        return cached
    from scrapers.fantasypros import get_defense_vs_position
    data = get_defense_vs_position()
    # Extract top 5 worst defenses per position
    snapshot = {}
    for pos, teams in data.items():
        sorted_teams = sorted(teams.items(), key=lambda x: x[1]["rank"])
        snapshot[pos] = [
            {"team": name, "rank": info["rank"], "pts": info["pts"]}
            for name, info in sorted_teams[:5]
        ]
    _cache_set("dvp", snapshot, ttl=3600)
    return snapshot
```

- [ ] **Step 4: Run cache tests to verify they pass**

```bash
pytest tests/test_nba_router.py -v
```
Expected: PASS

- [ ] **Step 5: Register router in `app.py`**

In `app.py`, after the existing router imports (around line 40), add:

```python
from routers.nba import router as nba_router
```

And after the existing `app.include_router()` calls:

```python
app.include_router(nba_router)
```

- [ ] **Step 6: Commit**

```bash
git add routers/nba.py tests/test_nba_router.py app.py
git commit -m "feat(api): add /api/nba/ endpoints with cached standings, today, dvp"
```

### Task 10: Add outcome resolution endpoint

**Files:**
- Modify: `routers/analyses.py` (add resolve endpoint)
- Create: `analysis/resolver.py` (outcome resolution logic)

- [ ] **Step 1: Write the failing test for resolve logic**

Create `tests/test_resolver.py`:

```python
"""Tests for analysis/resolver.py — outcome resolution logic."""
from analysis.resolver import resolve_outcome


def test_hit_when_actual_exceeds_line():
    result = {"player": "Test Player", "line": 18.5}
    actual_pts = 22.0
    assert resolve_outcome(result, actual_pts) == "hit"


def test_miss_when_actual_below_line():
    result = {"player": "Test Player", "line": 18.5}
    actual_pts = 15.0
    assert resolve_outcome(result, actual_pts) == "miss"


def test_miss_when_actual_equals_line():
    """Push = miss (did not exceed the line)."""
    result = {"player": "Test Player", "line": 18.5}
    actual_pts = 18.5
    assert resolve_outcome(result, actual_pts) == "miss"


def test_none_when_no_line():
    result = {"player": "Test Player"}
    assert resolve_outcome(result, 20.0) is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_resolver.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `analysis/resolver.py`**

```python
"""
analysis/resolver.py — Resolves analysis pick outcomes.
Compares stored betting lines against actual player performance.
"""


def resolve_outcome(result: dict, actual_pts: float) -> str | None:
    """
    Determines if a pick was a hit or miss.

    Args:
        result: Analysis result dict with 'line' field (points prop line)
        actual_pts: Actual points scored by the player

    Returns:
        "hit" if actual > line, "miss" if actual <= line, None if no line stored
    """
    line = result.get("line")
    if line is None:
        return None
    return "hit" if actual_pts > line else "miss"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_resolver.py -v
```
Expected: 4 PASS

- [ ] **Step 5: Add resolve endpoint to `routers/analyses.py`**

Add at the end of `routers/analyses.py`:

```python
@router.post("/{date_str}/resolve")
def resolve_analysis(date_str: str, uid: str = Depends(require_auth)):
    """
    Resolve pick outcomes for a specific date.
    Fetches actual player stats from NBA API and compares against stored lines.
    """
    db = firestore.client()
    doc_ref = db.collection("analyses").document(date_str)
    doc = doc_ref.get()
    if not doc.exists:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Análise não encontrada")

    data = doc.to_dict()
    results = data.get("results", [])

    from analysis.resolver import resolve_outcome
    from scrapers.nba import get_player_game_pts

    updated = 0
    for result in results:
        if result.get("outcome") is not None:
            continue  # Already resolved

        line = result.get("line")
        if line is None:
            continue  # No line to compare against

        # Fetch actual points scored in the specific game
        player_name = result.get("player", "")
        actual_pts = get_player_game_pts(player_name, date_str)
        if actual_pts is None:
            continue  # Game not played yet or player DNP

        result["outcome"] = resolve_outcome(result, actual_pts)
        if result["outcome"] is not None:
            updated += 1

    # Save back to Firestore
    doc_ref.update({"results": results})
    return {"resolved": updated, "total": len(results)}
```

**Important:** This requires a new function `get_player_game_pts(player_name, date_str)` in `scrapers/nba.py` that fetches a single-game box score. The existing `get_player_recent_stats()` returns 15-game averages, which is wrong for resolution. Add this function in a sub-step below.

- [ ] **Step 6: Add `get_player_game_pts()` to `scrapers/nba.py`**

Add at the end of `scrapers/nba.py`:

```python
def get_player_game_pts(player_name: str, date_str: str) -> float | None:
    """
    Fetch actual points scored by a player on a specific date.
    Uses the NBA Stats PlayerGameLog endpoint.
    Returns None if player did not play or data unavailable.
    """
    # Search for player ID by name using leaguedashplayerstats
    # (reuse existing headers/session pattern from this file)
    try:
        from nba_api.stats.endpoints import playergamelog
        from nba_api.stats.static import players

        matched = players.find_players_by_full_name(player_name)
        if not matched:
            return None
        player_id = matched[0]["id"]

        log = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=_current_season(),
            season_type_all_star="Regular Season",
        )
        df = log.get_data_frames()[0]
        # date_str is "YYYY-MM-DD", NBA uses "MMM DD, YYYY"
        for _, row in df.iterrows():
            game_date = row["GAME_DATE"]  # "YYYY-MM-DDT..." or "MMM DD, YYYY"
            if date_str in str(game_date):
                return float(row["PTS"])
        return None
    except Exception:
        return None
```

**Note:** If `nba_api` is not installed, use the same raw `requests` approach used elsewhere in this file (hitting `stats.nba.com` directly with proper headers). Match the existing pattern in `scrapers/nba.py` for API calls.

- [ ] **Step 7: Commit**

```bash
git add analysis/resolver.py tests/test_resolver.py routers/analyses.py scrapers/nba.py
git commit -m "feat(api): add outcome resolution endpoint, resolver module, and game pts scraper"
```

---

## Chunk 5: NBA Frontend — Navigation + Tab Structure

### Task 11: Add NBA tab to navigation

**Files:**
- Modify: `static/index.html:1613-1626` (sidebar nav)
- Modify: `static/index.html:1641-1666` (tab panels)
- Modify: `static/index.html:1670-1691` (bottom nav)
- Modify: `static/index.html:1784-1828` (switchTab + animateTab + onAuthChange)

- [ ] **Step 1: Add NBA nav item to sidebar nav**

In `static/index.html`, in the sidebar nav (line ~1617), add a new `nav-item` for NBA after the Análise item:

```html
<div class="nav-item" data-tab="nba" onclick="switchTab('nba')">
  <span class="nav-dot"></span>
  <span>NBA</span>
</div>
```

Insert it between the Análise and Apostas nav items.

- [ ] **Step 2: Add NBA tab panel**

After `<div id="tab-analise" class="tab-panel active">...</div>` and before `<div id="tab-apostas"...>`, add:

```html
<!-- Aba NBA (preenchida pelo JS) -->
<div id="tab-nba" class="tab-panel"></div>
```

- [ ] **Step 3: Add NBA button to bottom nav**

In the bottom nav (line ~1670), add an NBA button after the Análise button and before Apostas:

```html
<button class="bn-item" data-tab="nba" onclick="switchTab(this.dataset.tab)">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="10"/><path d="M4.93 4.93c4.08 2.38 8.58 7.88 14.14 14.14"/><path d="M19.07 4.93c-4.08 2.38-8.58 7.88-14.14 14.14"/>
  </svg>
  <span>NBA</span>
</button>
```

(Basketball-like icon using circle + curved lines)

- [ ] **Step 4: Update `switchTab()` to handle 'nba'**

In the `switchTab(name)` function (~line 1804), add:

```javascript
if (name === 'nba') loadNBA();
```

Also update the `animateTab` SELECTORS object to include:
```javascript
nba: '.dash-kpi, .dash-chart-card, .nba-game-card, .nba-standings-table',
```

And update the `onAuthChange` hash validation (~line 1828):
```javascript
switchTab(['analise','nba','apostas','painel'].includes(hash) ? hash : 'analise');
```

- [ ] **Step 5: Test navigation**

Open app, verify 4 tabs visible in both sidebar and bottom nav. Clicking NBA tab shows empty panel (no JS loaded yet). URL hash changes to `#nba`.

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "feat(nav): add NBA tab to sidebar and bottom navigation"
```

### Task 12: Create `nba.js` module and load function

**Files:**
- Create: `static/nba.js`
- Modify: `static/index.html:1704-1707` (add script tag)

- [ ] **Step 1: Create `static/nba.js` with loadNBA function**

```javascript
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
    // Fetch analyses and bets in parallel
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
  // Will be implemented in Task 13
  const el = document.getElementById('nba-scorecard');
  if (el) el.innerHTML = '<p class="muted">Engine Scorecard — em breve</p>';
}

function renderLiveData() {
  // Will be implemented in Task 15
  const el = document.getElementById('nba-live');
  if (el) el.innerHTML = '<p class="muted">Dados ao Vivo — em breve</p>';
}

function renderCorrelation() {
  // Will be implemented in Task 17
  const el = document.getElementById('nba-correlation');
  if (el) el.innerHTML = '<p class="muted">Correlação — em breve</p>';
}
```

- [ ] **Step 2: Add script tag to `index.html`**

After the `painel.js` script tag (~line 1707), add:

```html
<script src="/static/nba.js"></script>
```

- [ ] **Step 3: Test in browser**

Click NBA tab → see "NBA DASHBOARD" title with 3 placeholder sections. No errors in console.

- [ ] **Step 4: Commit**

```bash
git add static/nba.js static/index.html
git commit -m "feat(nba): create nba.js module with loadNBA skeleton"
```

---

## Chunk 6: NBA Frontend — Engine Scorecard

### Task 13: Render Engine Scorecard KPIs

**Files:**
- Modify: `static/nba.js` (implement renderEngineScorecard)

- [ ] **Step 1: Implement `renderEngineScorecard()`**

Replace the placeholder:

```javascript
function renderEngineScorecard() {
  const el = document.getElementById('nba-scorecard');
  if (!el) return;

  const analyses = _nbaAnalysesCache || [];

  // Flatten all results with outcome data
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
```

- [ ] **Step 2: Commit**

```bash
git add static/nba.js
git commit -m "feat(nba): render engine scorecard KPIs with empty state"
```

### Task 14: Engine Scorecard charts

**Files:**
- Modify: `static/nba.js`

- [ ] **Step 1: Add `drawAccuracyTrend(analyses)` function**

```javascript
let _accuracyFilterDays = 0; // 0 = all-time

function filterAccuracyTrend(days) {
  _accuracyFilterDays = days;
  // Update active button
  document.querySelectorAll('#nba-scorecard .dch-range-btn').forEach(btn => {
    btn.classList.toggle('active', parseInt(btn.textContent) === days || (days === 0 && btn.textContent === 'TUDO'));
  });
  drawAccuracyTrend(_nbaAnalysesCache || []);
}

function drawAccuracyTrend(analyses) {
  // Filter by days if set
  let filtered = [...analyses].sort((a, b) => a.date.localeCompare(b.date));
  if (_accuracyFilterDays > 0) {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - _accuracyFilterDays);
    const cutoffStr = cutoff.toISOString().slice(0, 10);
    filtered = filtered.filter(a => a.date >= cutoffStr);
  }
  const sorted = filtered;
  const labels = [], accAll = [], accBest = [], accVF = [];

  let cumHit = 0, cumTotal = 0;
  let cumBestHit = 0, cumBestTotal = 0;
  let cumVFHit = 0, cumVFTotal = 0;

  resolved.forEach(a => {
    (a.results || []).forEach(r => {
      if (!r.outcome) return;
      cumTotal++;
      if (r.outcome === 'hit') cumHit++;
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
```

- [ ] **Step 2: Add `drawAccuracyScore(picks)` function**

```javascript
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
      datasets: [{
        data: data.map(d => d.hitRate),
        backgroundColor: ['#06b6d4', '#f59e0b', '#22c55e'],
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const d = data[ctx.dataIndex];
              return [`Hit rate: ${d.hitRate.toFixed(1)}%`, `${d.total} picks`];
            },
          },
        },
      },
      scales: {
        y: { min: 0, max: 100, ticks: { color: '#888', callback: v => v + '%' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { ticks: { color: '#888' }, grid: { display: false } },
      },
    },
  });
}
```

- [ ] **Step 3: Test in browser**

If there are analysis results with `outcome` field, charts should render. If no outcome data, empty state message appears.

- [ ] **Step 4: Commit**

```bash
git add static/nba.js
git commit -m "feat(nba): add accuracy trend and score charts"
```

---

## Chunk 7: NBA Frontend — Live Data Section

### Task 15: Render standings tables

**Files:**
- Modify: `static/nba.js` (implement renderLiveData)

- [ ] **Step 1: Implement `renderLiveData()`**

Replace the placeholder:

```javascript
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

    // Get today's team tricodes for highlighting
    const todayTeams = new Set();
    if (today && today.games) {
      today.games.forEach(g => {
        todayTeams.add(g.home_tricode);
        todayTeams.add(g.away_tricode);
      });
    }

    let html = '<h2 class="section-title" style="margin-top:2rem;">DADOS AO VIVO</h2>';

    // Standings
    if (standings) {
      html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:1.5rem;">';
      html += renderStandingsTable('Eastern Conference', standings.east, todayTeams);
      html += renderStandingsTable('Western Conference', standings.west, todayTeams);
      html += '</div>';
    } else {
      html += '<div class="muted" style="text-align:center;padding:1rem;">Standings indisponíveis no momento</div>';
    }

    // Today's games
    html += renderTodayGames(today);

    // DvP Rankings
    html += renderDvPSnapshot(dvp);

    el.innerHTML = html;
  } catch (err) {
    el.innerHTML = '<h2 class="section-title" style="margin-top:2rem;">DADOS AO VIVO</h2><p class="red">Erro ao carregar dados ao vivo.</p>';
    console.error('[nba] live data error:', err);
  }
}
```

- [ ] **Step 2: Add `renderStandingsTable()` helper**

```javascript
function renderStandingsTable(title, teams, todayTeams) {
  let html = `<div class="dash-chart-card nba-standings-table"><div class="dch-title">${title}</div>`;
  html += '<table style="width:100%;border-collapse:collapse;font-size:0.85rem;">';
  html += '<thead><tr style="color:#888;"><th>#</th><th>Time</th><th>W-L</th><th>%</th><th>GB</th></tr></thead><tbody>';

  teams.forEach(t => {
    const total = t.wins + t.losses;
    const pct = total > 0 ? (t.wins / total).toFixed(3) : '.000';
    const gb = t.games_back_from_above !== null && t.games_back_from_above !== undefined
      ? t.games_back_from_above.toFixed(1)
      : '—';

    // Zone dividers
    let borderStyle = '';
    if (t.seed === 7) borderStyle = 'border-top: 2px solid #f59e0b;'; // play-in starts
    if (t.seed === 11) borderStyle = 'border-top: 2px solid #ef4444;'; // outside play-in

    // Highlight today's teams
    const isPlaying = todayTeams.has(t.team_id?.toString());
    const highlight = isPlaying ? 'color:#f59e0b;font-weight:600;' : 'color:#ccc;';

    const teamName = t.team_name || t.team_id || '?';
    html += `<tr style="${borderStyle}${highlight}">
      <td style="padding:4px 6px;">${t.seed}</td>
      <td style="padding:4px 6px;">${teamName}</td>
      <td style="padding:4px 6px;">${t.wins}-${t.losses}</td>
      <td style="padding:4px 6px;">${pct}</td>
      <td style="padding:4px 6px;">${gb}</td>
    </tr>`;
  });

  html += '</tbody></table></div>';
  return html;
}
```

- [ ] **Step 3: Commit**

```bash
git add static/nba.js
git commit -m "feat(nba): render conference standings tables with play-in dividers"
```

### Task 16: Today's Games cards + DvP snapshot

**Files:**
- Modify: `static/nba.js`

- [ ] **Step 1: Add `renderTodayGames()` helper**

```javascript
function renderTodayGames(today) {
  let html = '<h3 class="section-title" style="margin-top:1.5rem;font-size:1rem;">JOGOS DE HOJE</h3>';

  if (!today || !today.games || today.games.length === 0) {
    return html + '<div class="muted" style="text-align:center;padding:1rem;">Sem jogos hoje</div>';
  }

  // Cross-reference with today's analysis for engine pick badges
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

    // Engine pick badge for this game
    const pick = todayPicks.find(p => p.game === g.game_label);
    const pickBadge = pick
      ? `<div style="margin-top:0.5rem;padding:4px 8px;background:rgba(245,158,11,0.15);border:1px solid #f59e0b;border-radius:6px;font-size:0.75rem;color:#f59e0b;">
           ⚡ ${pick.player} — ${pick.rating}
         </div>`
      : '';

    html += `
      <div class="dash-chart-card nba-game-card" style="padding:1rem;">
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
```

- [ ] **Step 2: Add `renderDvPSnapshot()` helper**

```javascript
function renderDvPSnapshot(dvp) {
  let html = '<h3 class="section-title" style="margin-top:1.5rem;font-size:1rem;">DvP RANKINGS — PIORES DEFESAS</h3>';

  if (!dvp) {
    return html + '<div class="muted" style="text-align:center;padding:1rem;">Dados DvP indisponíveis no momento</div>';
  }

  html += '<div class="dash-chart-card"><div style="overflow-x:auto;">';
  html += '<table style="width:100%;border-collapse:collapse;font-size:0.85rem;">';
  html += '<thead><tr style="color:#888;"><th>Pos</th><th>#1</th><th>#2</th><th>#3</th><th>#4</th><th>#5</th></tr></thead><tbody>';

  const positions = ['PG', 'SG', 'SF', 'PF', 'C'];
  positions.forEach(pos => {
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
```

- [ ] **Step 3: Test in browser**

Click NBA tab → verify standings, game cards, and DvP table all render. Test empty states when no games today.

- [ ] **Step 4: Commit**

```bash
git add static/nba.js
git commit -m "feat(nba): add today's games cards and DvP rankings snapshot"
```

---

## Chunk 8: NBA Frontend — Correlation Section

### Task 17: Engine x Bets correlation

**Files:**
- Modify: `static/nba.js` (implement renderCorrelation)

- [ ] **Step 1: Add tricode lookup map**

At the top of `nba.js`, add the NBA team name → tricode map:

```javascript
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
  // Step 1: match by date
  const analysis = analyses.find(a => a.date === bet.data);
  if (!analysis || !analysis.results) return null;

  // Step 2: match by game (tricode normalization)
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

  // Step 3: match by player (last name substring)
  const desc = (bet.descricao || '').toLowerCase();
  const playerMatch = matchingResults.find(r => {
    const lastName = (r.player || '').split(' ').pop().toLowerCase();
    return lastName.length > 2 && desc.includes(lastName);
  });

  if (!playerMatch) return null;

  // Step 4: ambiguity check
  if (matchingResults.length > 1) {
    const multiMatch = matchingResults.filter(r => {
      const lastName = (r.player || '').split(' ').pop().toLowerCase();
      return lastName.length > 2 && desc.includes(lastName);
    });
    if (multiMatch.length > 1) return null; // ambiguous
  }

  return playerMatch;
}
```

- [ ] **Step 2: Implement `renderCorrelation()`**

```javascript
function renderCorrelation() {
  const el = document.getElementById('nba-correlation');
  if (!el) return;

  const bets = (_nbaBetsCache || []).filter(b => b.resultado !== 'pendente' && b.resultado !== 'void');
  const analyses = _nbaAnalysesCache || [];

  // Classify bets FIRST, then check empty state after matching
  const followed = [], notFollowed = [];
  bets.forEach(b => {
    const match = matchBetToAnalysis(b, analyses);
    if (match) {
      followed.push({ ...b, engineScore: match.score });
    } else {
      notFollowed.push(b);
    }
  });

  // Empty state: show only after attempting to match
  if (followed.length === 0) {
    el.innerHTML = `
      <h2 class="section-title" style="margin-top:2rem;">CORRELAÇÃO ENGINE × APOSTAS</h2>
      <div class="muted" style="text-align:center;padding:2rem;">
        Nenhuma aposta correspondente a picks do engine encontrada
      </div>`;
    return;
  }

  // ROI calculations
  const calcROI = (arr) => {
    const staked = arr.reduce((s, b) => s + (b.stake || 0), 0);
    const pl = arr.reduce((s, b) => s + (b.lucro_prejuizo || 0), 0);
    return staked > 0 ? ((pl / staked) * 100).toFixed(1) : '—';
  };

  const roiFollowed = calcROI(followed);
  const roiNotFollowed = calcROI(notFollowed);
  const delta = roiFollowed !== '—' && roiNotFollowed !== '—'
    ? (parseFloat(roiFollowed) - parseFloat(roiNotFollowed)).toFixed(1)
    : '—';

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
```

- [ ] **Step 3: Commit**

```bash
git add static/nba.js
git commit -m "feat(nba): add correlation KPIs with bet-to-engine matching"
```

### Task 18: Correlation charts

**Files:**
- Modify: `static/nba.js`

- [ ] **Step 1: Add `drawCorrelationPL()` function**

```javascript
function drawCorrelationPL(followed, notFollowed) {
  const sortByDate = (arr) => [...arr].sort((a, b) => a.data.localeCompare(b.data));
  const fSorted = sortByDate(followed);
  const nSorted = sortByDate(notFollowed);

  // Merge all dates for x-axis
  const allDates = [...new Set([...fSorted, ...nSorted].map(b => b.data))].sort();

  let cumF = 0, cumN = 0;
  const fData = [], nData = [];
  allDates.forEach(date => {
    fSorted.filter(b => b.data === date).forEach(b => cumF += b.lucro_prejuizo || 0);
    nSorted.filter(b => b.data === date).forEach(b => cumN += b.lucro_prejuizo || 0);
    fData.push(cumF);
    nData.push(cumN);
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
```

- [ ] **Step 2: Add `drawCorrelationScore()` function**

```javascript
function drawCorrelationScore(followed) {
  const scores = [4, 5, 6];
  const data = scores.map(s => {
    const group = followed.filter(b => b.engineScore === s);
    const won = group.filter(b => b.resultado === 'ganhou');
    return {
      score: s,
      total: group.length,
      winRate: group.length > 0 ? (won.length / group.length) * 100 : 0,
    };
  });

  const ctx = document.getElementById('chartCorrelationScore');
  if (!ctx) return;
  if (window._chartCorrScore) window._chartCorrScore.destroy();

  window._chartCorrScore = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: scores.map(s => 'Score ' + s),
      datasets: [{
        data: data.map(d => d.winRate),
        backgroundColor: ['#06b6d4', '#f59e0b', '#22c55e'],
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const d = data[ctx.dataIndex];
              return [`Win rate: ${d.winRate.toFixed(1)}%`, `${d.total} apostas`];
            },
          },
        },
      },
      scales: {
        y: { min: 0, max: 100, ticks: { color: '#888', callback: v => v + '%' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { ticks: { color: '#888' }, grid: { display: false } },
      },
    },
  });
}
```

- [ ] **Step 3: Test full NBA tab in browser**

Verify all 3 sections render: Engine Scorecard, Live Data, Correlation. Test empty states for each.

- [ ] **Step 4: Commit**

```bash
git add static/nba.js
git commit -m "feat(nba): add correlation P&L and score charts"
```

---

## Chunk 9: Responsive + Mobile Polish

### Task 19: Add responsive CSS for new sections

**Files:**
- Modify: `static/index.html` (add CSS rules in style section) or `static/painel.js` / `static/nba.js` (inline styles)

- [ ] **Step 1: Add responsive media query for chart grids**

Find the existing `<style>` section in `index.html` and add:

```css
@media (max-width: 768px) {
  .dash-charts-row {
    grid-template-columns: 1fr !important;
  }
  .nba-standings-table table {
    font-size: 0.75rem;
  }
}
```

If charts use inline `style="display:grid;grid-template-columns:1fr 1fr"`, convert these to use the `.dash-charts-row` class instead for consistent responsive behavior.

- [ ] **Step 2: Test on mobile viewport**

Use browser DevTools responsive mode (375px width). Verify:
- KPI cards: 2 per row
- Charts: stack vertically
- Standings tables: stack vertically
- Game cards: single column
- No horizontal scroll

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat: add responsive CSS for new dashboard and NBA sections"
```

### Task 20: Final integration test

- [ ] **Step 1: Full flow test**

1. Open app in browser
2. Switch to **Painel** tab:
   - Verify 8 KPI cards (2 rows)
   - Verify 6 new charts render (day of week, odds range, streaks, histogram, scatter, ROI)
   - Test time filters (week/month/year/all) — new charts should respond to filters
3. Switch to **NBA** tab:
   - Verify Engine Scorecard section (KPIs or empty state)
   - Verify Live Data (standings, games, DvP) — may show error if scraper endpoints fail in dev
   - Verify Correlation section (KPIs + charts or empty state)
4. Test on mobile viewport
5. Check browser console for errors

- [ ] **Step 2: Fix any issues found**

Address any rendering bugs, console errors, or responsive layout issues.

- [ ] **Step 3: Final commit**

```bash
git add static/painel.js static/nba.js static/index.html
git commit -m "fix: address integration issues from full flow test"
```
