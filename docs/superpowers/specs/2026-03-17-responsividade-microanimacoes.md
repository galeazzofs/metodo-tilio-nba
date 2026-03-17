# Spec: Responsividade + Micro-animações
**Date:** 2026-03-17
**Project:** SCOUT — NBA Betting Intelligence (Fintech Premium redesign)

---

## 1. Scope

Two CSS/JS enhancements to `static/index.html` and `static/index.html`'s inline `<script>` block:

1. **Responsividade** — mobile layout at `≤ 960px` with bottom navigation bar
2. **Micro-animações** — staggered `fadeUp` entrance on all three tabs' cards

No backend changes. No new files. All changes confined to `static/index.html`.

---

## 2. Responsividade

### 2.1 Breakpoint

Single new media query: `@media (max-width: 960px)`.

### 2.2 Sidebar → Hidden

```css
@media (max-width: 960px) {
  .sidebar { display: none; }
}
```

### 2.3 App shell direction

```css
@media (max-width: 960px) {
  #appShell { flex-direction: column; }
}
```

### 2.4 Bottom navigation bar

A `.bottom-nav` element is added to the HTML immediately before `</body>` (inside `#appShell`, after `.main-scroll`). It is only visible at ≤ 960px.

**HTML structure:**
```html
<nav class="bottom-nav">
  <button class="bn-item active" data-tab="analise">
    <svg><!-- analysis icon --></svg>
    <span>Análise</span>
  </button>
  <button class="bn-item" data-tab="apostas">
    <svg><!-- bets icon --></svg>
    <span>Apostas</span>
  </button>
  <button class="bn-item" data-tab="painel">
    <svg><!-- dashboard icon --></svg>
    <span>Painel</span>
  </button>
</nav>
```

**CSS:**
```css
.bottom-nav {
  display: none; /* hidden on desktop */
  position: fixed;
  bottom: 0; left: 0; right: 0;
  height: 64px;
  background: var(--vintage-grape);
  border-top: 1px solid rgba(255,255,255,0.1);
  z-index: 200;
  align-items: center;
  justify-content: space-around;
  padding: 0 8px;
  padding-bottom: env(safe-area-inset-bottom, 0px); /* iPhone notch */
}

@media (max-width: 960px) {
  .bottom-nav { display: flex; }
}

.bn-item {
  display: flex; flex-direction: column; align-items: center;
  gap: 3px;
  background: none; border: none; cursor: pointer;
  color: rgba(255,255,255,0.5);
  font-family: var(--font-body); font-size: 11px; font-weight: 500;
  padding: 6px 16px; border-radius: 10px;
  transition: color var(--transition);
  flex: 1;
}
.bn-item svg { width: 20px; height: 20px; stroke: currentColor; fill: none; stroke-width: 2; }
.bn-item.active { color: #ffffff; }
.bn-item.active svg { stroke: var(--majorelle-blue); }
```

**Icons (inline SVG, stroke-based):**
- Análise: bar-chart-2 (three vertical bars)
- Apostas: list (three horizontal lines)
- Painel: layout-dashboard (grid of 4 squares)

**Active state sync:** The existing `switchTab(tab)` function in the inline `<script>` block is extended to also update `.bn-item.active`:

```js
// inside switchTab(), after existing active-class logic:
document.querySelectorAll('.bn-item').forEach(b =>
  b.classList.toggle('active', b.dataset.tab === tab)
);
```

The `.bn-item` buttons call `switchTab()` via `onclick="switchTab(this.dataset.tab)"` (mirrors existing `.nav-item` pattern).

### 2.5 Content area clearance

```css
@media (max-width: 960px) {
  .main-scroll { padding-bottom: 80px; }
}
```

### 2.6 Padding reduction

```css
@media (max-width: 960px) {
  .pg-wrap { padding: 16px; }
}
```

### 2.7 Grid collapse — all multi-column grids to 1 column

```css
@media (max-width: 960px) {
  .kpi-grid        { grid-template-columns: 1fr 1fr; } /* 2-col on mobile (compact KPIs) */
  .dash-kpi-row    { grid-template-columns: 1fr 1fr; }
  .charts-grid     { grid-template-columns: 1fr; }
  .dash-bottom     { grid-template-columns: 1fr; }
}
```

Note: `.kpi-grid` and `.dash-kpi-row` use 2 columns on mobile (not 1) because the KPI cards are compact enough to pair side-by-side on a phone screen.

### 2.8 Auth screen

The auth screen (`.auth-screen`) is full-screen centered — no sidebar involved — no changes needed.

---

## 3. Micro-animações

### 3.1 CSS — animation class

The existing `@keyframes fadeUp` is already defined. A new utility class is added:

```css
.anim-enter {
  animation: fadeUp 0.35s ease both;
  animation-delay: calc(var(--i, 0) * 60ms);
}

@media (prefers-reduced-motion: reduce) {
  .anim-enter { animation: none; }
}
```

### 3.2 JS — `animateTab(tabId)` helper

A new function `animateTab(tabId)` is added to the inline `<script>` block:

```js
function animateTab(tabId) {
  const SELECTORS = {
    painel:  '.dash-kpi, .dash-chart-card, .chart-box',
    apostas: '.bet-card',
    analise: '.card',
  };
  const sel = SELECTORS[tabId];
  if (!sel) return;

  const panel = document.getElementById('tab-' + tabId);
  if (!panel) return;

  // Remove stale classes first (synchronously)
  panel.querySelectorAll('.anim-enter').forEach(el => el.classList.remove('anim-enter'));

  // Re-apply on next frame so animation fires even on re-visit
  requestAnimationFrame(() => {
    const els = [...panel.querySelectorAll(sel)].slice(0, 8);
    els.forEach((el, i) => {
      el.style.setProperty('--i', i);
      el.classList.add('anim-enter');
    });
  });
}
```

### 3.3 Integration with `switchTab()`

`animateTab(tab)` is called at the end of the existing `switchTab(tab)` function:

```js
function switchTab(tab) {
  // ... existing logic ...
  animateTab(tab); // ← added at the end
}
```

### 3.4 Initial page load

On `DOMContentLoaded` (or at the bottom of the inline script where tab initialization happens), `animateTab('analise')` is called once to animate the default tab.

### 3.5 Cap at 8 cards

To avoid excessively long `animation-delay` chains on large bet lists, only the first 8 matching elements in each tab are animated. Cards 9+ appear instantly (no class applied).

### 3.6 Which elements animate per tab

| Tab | Selector | Typical count |
|-----|----------|---------------|
| Painel | `.dash-kpi`, `.dash-chart-card`, `.chart-box` | 4–6 |
| Apostas | `.bet-card` | up to 8 |
| Análise | `.card` | up to 8 |

---

## 4. Files Modified

| File | Change |
|------|--------|
| `static/index.html` | New CSS block (`.bottom-nav`, `.bn-item`, `.anim-enter`, `@media (max-width: 960px)`) |
| `static/index.html` | New HTML block (`.bottom-nav` element before `</body>`) |
| `static/index.html` | Extend `switchTab()` inline script + add `animateTab()` helper |

No new files. No backend changes. No other JS files modified.

---

## 5. Out of Scope

- Modal redesign (step 3) — separate spec
- Tablet-specific intermediate layouts (not requested)
- Any chart responsiveness (Chart.js handles its own canvas sizing)
- Form panel / print modal — separate spec
