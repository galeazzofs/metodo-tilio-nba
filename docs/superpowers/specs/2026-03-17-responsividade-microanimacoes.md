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

A `.bottom-nav` element is added **inside `#appShell`, between `</div><!-- /main-scroll -->` and `</div><!-- /appShell -->`** — these two tags are on adjacent lines in the file. The nav uses `position: fixed` so it doesn't participate in the flex flow, but it must be scoped inside `#appShell` for DOM organisation.

The element is only visible at ≤ 960px via CSS.

**Viewport meta update:** `env(safe-area-inset-bottom)` requires `viewport-fit=cover` to return a non-zero value on iOS. The existing viewport meta tag must be updated:

```html
<!-- Before -->
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<!-- After -->
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
```

**HTML structure:**
```html
<nav class="bottom-nav">
  <button class="bn-item active" data-tab="analise" onclick="switchTab(this.dataset.tab)">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <!-- bar-chart-2: three vertical bars -->
      <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
    </svg>
    <span>Análise</span>
  </button>
  <button class="bn-item" data-tab="apostas" onclick="switchTab(this.dataset.tab)">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <!-- list: three horizontal lines -->
      <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/>
      <line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
    </svg>
    <span>Apostas</span>
  </button>
  <button class="bn-item" data-tab="painel" onclick="switchTab(this.dataset.tab)">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <!-- layout-dashboard: 2×2 grid of squares -->
      <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
      <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
    </svg>
    <span>Painel</span>
  </button>
</nav>
```

**CSS:**
```css
/* Note: flex properties (align-items, justify-content) are declared here alongside
   display:none — they take effect when display:flex is applied by the media query below. */
.bottom-nav {
  display: none; /* hidden on desktop */
  position: fixed;
  bottom: 0; left: 0; right: 0;
  height: calc(64px + env(safe-area-inset-bottom, 0px)); /* 64px usable + iOS home indicator */
  background: var(--vintage-grape);
  border-top: 1px solid rgba(255,255,255,0.1);
  z-index: 200;
  align-items: flex-start; /* top-align items so tap targets sit in the 64px zone */
  justify-content: space-around;
  padding: 0 8px;
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
.bn-item svg { width: 20px; height: 20px; }
.bn-item.active { color: #ffffff; }
.bn-item.active svg { stroke: var(--majorelle-blue); }
```

**Active state sync:** The existing `switchTab(tab)` function is extended to also update `.bn-item.active`:

```js
// inside switchTab(), after existing active-class logic:
document.querySelectorAll('.bn-item').forEach(b =>
  b.classList.toggle('active', b.dataset.tab === tab)
);
```

### 2.5 Content area clearance

The bottom nav total height is `calc(64px + env(safe-area-inset-bottom, 0px))`. The content clearance adds a small buffer on top of that:

```css
@media (max-width: 960px) {
  .main-scroll { padding-bottom: calc(80px + env(safe-area-inset-bottom, 0px)); }
}
```

### 2.6 Padding reduction

```css
@media (max-width: 960px) {
  .pg-wrap { padding: 16px; }
}
```

### 2.7 Grid collapse

The codebase already contains `@media (max-width: 800px) { .charts-grid { grid-template-columns: 1fr; } }`. The new `@media (max-width: 960px)` block supersedes this — **remove the existing `800px` rule** to avoid dead CSS. The new block handles all grid targets:

```css
@media (max-width: 960px) {
  .kpi-grid        { grid-template-columns: 1fr 1fr; } /* 2-col on mobile — KPI cards are compact */
  .dash-kpi-row    { grid-template-columns: 1fr 1fr; }
  .charts-grid     { grid-template-columns: 1fr; }
  .dash-bottom     { grid-template-columns: 1fr; }
}
```

Note: `.kpi-grid` and `.dash-kpi-row` use 2 columns on mobile (not 1) because KPI cards are compact enough to pair side-by-side.

### 2.8 Auth screen

The auth screen (`.auth-screen`) is full-screen centered — no sidebar involved — no changes needed.

---

## 3. Micro-animações

### 3.1 CSS — animation class

The existing `@keyframes fadeUp` is already defined. The existing `.tab-panel.active` rule currently applies `animation: fadeUp 0.2s ease` to the **entire panel** on tab switch. To avoid a double-animation (panel-level + card-level), **remove the `animation` property from `.tab-panel.active`**:

```css
/* Before */
.tab-panel.active { display: block; animation: fadeUp 0.2s ease; }
/* After */
.tab-panel.active { display: block; }
```

The card-level staggered animation replaces this panel-level fade entirely.

A new utility class is added:

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

`animateTab(name)` is called at the end of the existing `switchTab(name)` function. Note: the real function signature uses the parameter name `name`, not `tab`:

```js
function switchTab(name) {
  // ... existing logic ...
  animateTab(name); // ← added at the end
}
```

### 3.4 Initial page load

Because `animateTab(name)` is called inside `switchTab(name)`, the `onAuthChange → switchTab → animateTab` chain fires automatically for the default tab. However, `apostas` and `painel` cards are populated asynchronously (via `loadApostas()` / `loadPainel()` which are called lazily inside `switchTab`). When `animateTab` runs synchronously at the end of `switchTab`, the `.bet-card` and `.dash-kpi` DOM elements may not yet exist, causing a silent no-op.

**Fix:** Also call `animateTab` at the end of the data-render functions — specifically at the end of `renderApostas()` (in `apostas.js`) and at the end of `renderPainel()` / the equivalent render function in `painel.js` that appends cards to the DOM.

However, since `apostas.js` and `painel.js` are separate files outside this spec's scope, the acceptable fallback is: calling `animateTab` at the end of `switchTab` is still correct for the Análise tab (whose cards are synchronously available) and for re-visits to already-loaded tabs. On first load of `apostas`/`painel` via hash deep-link, the animation may not fire — this is an acceptable known limitation for this spec. It can be addressed in a follow-up pass on `apostas.js` and `painel.js`.

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
| `static/index.html` | Update viewport meta (`viewport-fit=cover`) |
| `static/index.html` | Remove `animation` from `.tab-panel.active` |
| `static/index.html` | New CSS block (`.bottom-nav`, `.bn-item`, `.anim-enter`, `@media (max-width: 960px)`) |
| `static/index.html` | New HTML block (`.bottom-nav` inside `#appShell` after `.main-scroll`) |
| `static/index.html` | Extend `switchTab()` + add `animateTab()` in inline script |

No new files. No backend changes. No other JS files modified.

---

## 5. Out of Scope

- Modal redesign (step 3) — separate spec
- Tablet-specific intermediate layouts (not requested)
- Any chart responsiveness (Chart.js handles its own canvas sizing)
- Form panel / print modal — separate spec
