# Responsividade + Micro-animações Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add mobile-responsive layout (bottom nav bar at ≤ 960px) and staggered card entrance animations to the SCOUT NBA app.

**Architecture:** All changes are pure CSS + inline JS in `static/index.html`. No new files, no backend changes. Two chunks: Chunk 1 builds the mobile layout; Chunk 2 adds the card animations. Both chunks are independent enough to be committed separately.

**Tech Stack:** Vanilla CSS (CSS custom properties, media queries, `env()`), vanilla JS (DOM manipulation, `requestAnimationFrame`), single HTML file SPA.

**Note on TDD:** This is a CSS/HTML app with no automated test harness. Each task lists visual verification steps instead of test commands. The app is served via FastAPI — run it with `uvicorn main:app --reload` from the project root, then open `http://localhost:8000` to verify.

---

## Chunk 1: Responsividade (mobile layout)

### Task 1: Viewport meta + clean up stale 800px rule + remove panel animation

**File:** `static/index.html`

- [ ] **Step 1: Update viewport meta (line 5)**

  Find:
  ```html
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  ```
  Replace with:
  ```html
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  ```
  This enables `env(safe-area-inset-bottom)` to return a non-zero value on iOS devices with a home indicator.

- [ ] **Step 2: Remove the stale 800px media query (line 893)**

  Find and delete:
  ```css
  @media (max-width: 800px) { .charts-grid { grid-template-columns: 1fr; } }
  ```
  The new 960px block in Task 3 covers this and more. Removing the 800px rule avoids dead CSS.

- [ ] **Step 3: Remove `animation` from `.tab-panel.active` (line 384)**

  Find:
  ```css
  .tab-panel.active { display: block; animation: fadeUp 0.2s ease; }
  ```
  Replace with:
  ```css
  .tab-panel.active { display: block; }
  ```
  The card-level staggered animation (Chunk 2) replaces this panel-level fade. Keeping both would double-animate.

- [ ] **Step 4: Commit**
  ```bash
  git add static/index.html
  git commit -m "fix(responsive): viewport-fit=cover, remove stale 800px rule, remove panel-level fadeUp"
  ```

---

### Task 2: Add bottom nav CSS block

**File:** `static/index.html` — `<style>` block, appended near the end before `</style>`

- [ ] **Step 1: Add the CSS**

  Find the closing `</style>` tag and insert the following block immediately before it:

  ```css
  /* ─── Mobile bottom nav ──────────────────────────────────── */
  /* Note: flex properties declared here take effect when display:flex
     is applied by the media query. display:none hides this on desktop. */
  .bottom-nav {
    display: none;
    position: fixed;
    bottom: 0; left: 0; right: 0;
    height: calc(64px + env(safe-area-inset-bottom, 0px));
    background: var(--vintage-grape);
    border-top: 1px solid rgba(255,255,255,0.1);
    z-index: 200;
    align-items: flex-start;
    justify-content: space-around;
    padding: 0 8px;
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

  /* ─── Mobile breakpoint ≤ 960px ──────────────────────────── */
  @media (max-width: 960px) {
    .sidebar          { display: none; }
    #appShell         { flex-direction: column; }
    .bottom-nav       { display: flex; }
    .main-scroll      { padding-bottom: calc(80px + env(safe-area-inset-bottom, 0px)); }
    .pg-wrap          { padding: 16px; }
    .kpi-grid         { grid-template-columns: 1fr 1fr; }
    .dash-kpi-row     { grid-template-columns: 1fr 1fr; }
    .charts-grid      { grid-template-columns: 1fr; }
    .dash-bottom      { grid-template-columns: 1fr; }
  }
  ```

- [ ] **Step 2: Commit**
  ```bash
  git add static/index.html
  git commit -m "feat(responsive): add bottom nav CSS and 960px mobile breakpoint"
  ```

---

### Task 3: Add bottom nav HTML element

**File:** `static/index.html` — inside `#appShell`, between `</div><!-- /main-scroll -->` and `</div><!-- /appShell -->`

In the file, lines 1219–1220 read:
```html
  </div><!-- /main-scroll -->
</div><!-- /appShell -->
```

- [ ] **Step 1: Insert the `.bottom-nav` HTML between those two lines**

  Note exact indentation: line 1219 has 2 leading spaces; line 1220 has 0 leading spaces.

  Replace:
  ```
    </div><!-- /main-scroll -->
</div><!-- /appShell -->
  ```
  With:
  ```
    </div><!-- /main-scroll -->

    <nav class="bottom-nav">
      <button class="bn-item active" data-tab="analise" onclick="switchTab(this.dataset.tab)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
        </svg>
        <span>Análise</span>
      </button>
      <button class="bn-item" data-tab="apostas" onclick="switchTab(this.dataset.tab)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/>
          <line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
        </svg>
        <span>Apostas</span>
      </button>
      <button class="bn-item" data-tab="painel" onclick="switchTab(this.dataset.tab)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
          <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
        </svg>
        <span>Painel</span>
      </button>
    </nav>
</div><!-- /appShell -->
  ```

- [ ] **Step 2: Commit**
  ```bash
  git add static/index.html
  git commit -m "feat(responsive): add bottom nav HTML element inside appShell"
  ```

---

### Task 4: Extend `switchTab()` with bottom nav active state sync

**File:** `static/index.html` — inline `<script>` block, inside `function switchTab(name)`

The existing function (starting at line ~1312) handles `.nav-item.active` for the sidebar. It needs to also sync `.bn-item.active` on the bottom nav.

- [ ] **Step 1: Read the current `switchTab` function**

  Find `function switchTab(name)` in the inline `<script>` block and read the full function to understand where the active-class logic ends.

- [ ] **Step 2: Add `.bn-item` sync inside `switchTab`**

  The actual function (lines 1312–1321) looks like:
  ```js
  function switchTab(name) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    const navEl = document.querySelector(`.nav-item[data-tab="${name}"]`);
    if (navEl) navEl.classList.add('active');
    history.replaceState(null, '', '#' + name);
    if (name === 'apostas') loadApostas();
    if (name === 'painel')  loadPainel();
  }
  ```

  Insert the `.bn-item` sync immediately after `if (navEl) navEl.classList.add('active');`:
  ```js
    if (navEl) navEl.classList.add('active');
    document.querySelectorAll('.bn-item').forEach(b =>
      b.classList.toggle('active', b.dataset.tab === name)
    );
    history.replaceState(null, '', '#' + name);
  ```

- [ ] **Step 3: Verify**

  Open the app in a browser. Use DevTools → Device Toolbar → set width to 400px. Confirm:
  - Sidebar is hidden ✓
  - Bottom nav is visible at the bottom ✓
  - Tapping each nav item switches the tab content ✓
  - Active item shows white text + blue icon ✓
  - Inactive items show dimmed text ✓
  - Resize back to desktop (> 960px) — bottom nav disappears, sidebar shows ✓

- [ ] **Step 4: Commit**
  ```bash
  git add static/index.html
  git commit -m "feat(responsive): sync bottom nav active state in switchTab()"
  ```

---

## Chunk 2: Micro-animações

### Task 5: Add `.anim-enter` CSS class

**File:** `static/index.html` — `<style>` block, inside the mobile bottom nav CSS block added in Task 2 (or appended near it)

- [ ] **Step 1: Add the `.anim-enter` CSS class**

  Find the `/* ─── Mobile bottom nav ───` comment added in Task 2 and insert the following block immediately before it (or after the mobile breakpoint block — either placement is fine since it's not media-query-scoped):

  ```css
  /* ─── Card entrance animation ────────────────────────────── */
  .anim-enter {
    animation: fadeUp 0.35s ease both;
    animation-delay: calc(var(--i, 0) * 60ms);
  }
  @media (prefers-reduced-motion: reduce) {
    .anim-enter { animation: none; }
  }
  ```

  Note: `@keyframes fadeUp` is already defined at line 85. Do not add it again.

- [ ] **Step 2: Commit**
  ```bash
  git add static/index.html
  git commit -m "feat(anim): add .anim-enter CSS class with staggered delay"
  ```

---

### Task 6: Add `animateTab()` function and wire it into `switchTab()`

**File:** `static/index.html` — inline `<script>` block

- [ ] **Step 1: Add `animateTab(tabId)` function**

  Find `function switchTab(name)` in the inline script. Insert the following function **immediately before** it:

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
    // Remove stale classes synchronously
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

- [ ] **Step 2: Call `animateTab(name)` at the end of `switchTab(name)`**

  At the very end of the `switchTab(name)` function body (after the `.bn-item` sync added in Task 4), add:
  ```js
  animateTab(name);
  ```

  The full end of `switchTab` should now look like:
  ```js
  document.querySelectorAll('.bn-item').forEach(b =>
    b.classList.toggle('active', b.dataset.tab === name)
  );
  animateTab(name);
  ```

- [ ] **Step 3: Verify**

  Open the app in a browser (any screen size). Confirm:
  - On tab switch, cards in the newly active tab slide up from slightly below with staggered delays ✓
  - Switching back to a previously visited tab re-triggers the animation ✓
  - The whole panel no longer fades as a single block (panel-level animation was removed in Task 1) ✓
  - Enable "Emulate CSS prefers-reduced-motion: reduce" in DevTools → cards appear instantly without animation ✓
  - Cards 9+ (if any) appear without animation (no `anim-enter` class) ✓

- [ ] **Step 4: Commit**
  ```bash
  git add static/index.html
  git commit -m "feat(anim): animateTab() staggered card entrance on tab switch"
  ```

---

## Known Limitations

- On first load of `apostas` or `painel` tab via URL hash (e.g. `#apostas`), the card-entrance animation may not fire because card DOM elements are populated asynchronously after `switchTab` runs. The animation works correctly on all subsequent tab visits. A follow-up pass on `apostas.js` and `painel.js` (calling `animateTab` at the end of their render functions) would fix first-load animation for those tabs.
