# Win/Loss Color Correction + Análise Tab Fix — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revert win/loss semantic colors from majorelle-blue/vintage-grape back to proper green (#16a34a) and red (#dc2626) across the whole app, and fix stale hardcoded dark-mode rgba values in the Análise tab analysis cards.

**Architecture:** Pure CSS + JS edits — no new files, no HTML structure changes. Two files touched: `static/index.html` (all CSS in the embedded `<style>` block) and `static/painel.js` (Chart.js line chart colors + gradient plugin RGB values). Changes are grouped into logical commits.

**Tech Stack:** Vanilla HTML/CSS, embedded `<style>` block in `static/index.html`, Chart.js with custom `lineGradientFill` plugin in `static/painel.js`

**Spec:** `docs/superpowers/specs/2026-03-17-analise-tab-winloss-redesign.md`

---

## Chunk 1: `:root` Token Changes + Core Badge/Bet Colors

### Task 1: Update `:root` win/loss CSS tokens

**Files:**
- Modify: `static/index.html` — `:root` block, lines 42–47

- [ ] **Step 1: Open `static/index.html` and locate the `:root` block**

  Find this block (around lines 42–47):
  ```css
  /* Wins → majorelle-blue  |  Losses → vintage-grape */
  --green:         #623cea;
  --green-dim:     rgba(98,60,234,0.08);
  --green-border:  rgba(98,60,234,0.22);

  --red:    #54426b;
  ```

- [ ] **Step 2: Replace those lines with correct green/red values**

  Replace with:
  ```css
  /* Wins → green #16a34a  |  Losses → red #dc2626 */
  --green:         #16a34a;
  --green-dim:     rgba(22,163,74,0.1);
  --green-border:  rgba(22,163,74,0.25);

  --red:    #dc2626;
  ```

- [ ] **Step 3: Verify in DevTools**

  Open the app in a browser. In DevTools console run:
  ```js
  getComputedStyle(document.documentElement).getPropertyValue('--green').trim()
  // Expected: "#16a34a"
  getComputedStyle(document.documentElement).getPropertyValue('--red').trim()
  // Expected: "#dc2626"
  ```

---

### Task 2: Fix `.badge-error` hardcoded red values

**Files:**
- Modify: `static/index.html` — line 452

- [ ] **Step 1: Locate `.badge-error` rule**

  Find line 452:
  ```css
  .badge-error   { background: rgba(244,63,94,.1); color: var(--red);   border: 1px solid rgba(244,63,94,.25); }
  ```

- [ ] **Step 2: Replace hardcoded rgba values**

  Change to:
  ```css
  .badge-error   { background: rgba(220,38,38,0.1); color: var(--red);   border: 1px solid rgba(220,38,38,0.25); }
  ```

---

### Task 3: Fix `.b-win` color and `.b-loss` all properties

**Files:**
- Modify: `static/index.html` — lines 677–678

- [ ] **Step 1: Locate `.b-win` and `.b-loss` rules**

  Find lines 677–678:
  ```css
  .b-win  { background: var(--green-dim); color: var(--majorelle-blue); border: 1px solid var(--green-border); }
  .b-loss { background: rgba(84,66,107,0.07); color: var(--vintage-grape); border: 1px solid rgba(84,66,107,0.2); }
  ```

- [ ] **Step 2: Fix `.b-win` color and fix `.b-loss` all three properties**

  Replace with:
  ```css
  .b-win  { background: var(--green-dim); color: var(--green); border: 1px solid var(--green-border); }
  .b-loss { background: rgba(220,38,38,0.08); color: var(--red); border: 1px solid rgba(220,38,38,0.25); }
  ```

---

### Task 4: Fix `.t-pnl-pos` and `.t-pnl-neg`

**Files:**
- Modify: `static/index.html` — lines 711–712

- [ ] **Step 1: Locate the rules**

  Find lines 711–712:
  ```css
  .t-pnl-pos  { color: var(--majorelle-blue); font-family: var(--font-mono); font-weight: 600; }
  .t-pnl-neg  { color: var(--vintage-grape); font-family: var(--font-mono); font-weight: 600; }
  ```

- [ ] **Step 2: Change color references**

  Replace with:
  ```css
  .t-pnl-pos  { color: var(--green); font-family: var(--font-mono); font-weight: 600; }
  .t-pnl-neg  { color: var(--red); font-family: var(--font-mono); font-weight: 600; }
  ```

---

### Task 5: Fix `.bc-ganhou` and `.bc-perdeu` accent bars

**Files:**
- Modify: `static/index.html` — lines 798–799

- [ ] **Step 1: Locate the rules**

  Find lines 798–799:
  ```css
  .bc-ganhou   .bc-accent { background: var(--majorelle-blue); }
  .bc-perdeu   .bc-accent { background: var(--vintage-grape); }
  ```

- [ ] **Step 2: Change to green/red**

  Replace with:
  ```css
  .bc-ganhou   .bc-accent { background: var(--green); }
  .bc-perdeu   .bc-accent { background: var(--red); }
  ```

---

### Task 6: Commit Chunk 1

- [ ] **Step 1: Stage only `static/index.html`**

  ```bash
  git add static/index.html
  ```

- [ ] **Step 2: Commit**

  ```bash
  git commit -m "fix(colors): revert win/loss tokens to green/red — badges, bets, t-pnl, bc-accent"
  ```

---

## Chunk 2: Dashboard KPI and Utility Class Colors

### Task 7: Fix `.dkpi-pos`, `.dkpi-neg`, `.dbadge-pos`, `.dbadge-neg`

**Files:**
- Modify: `static/index.html` — lines 966–967, 973–974

- [ ] **Step 1: Locate `.dkpi-pos` and `.dkpi-neg`**

  Find lines 966–967:
  ```css
  .dkpi-pos { color: var(--majorelle-blue); }
  .dkpi-neg { color: var(--vintage-grape); }
  ```

- [ ] **Step 2: Change to green/red vars**

  Replace with:
  ```css
  .dkpi-pos { color: var(--green); }
  .dkpi-neg { color: var(--red); }
  ```

- [ ] **Step 3: Locate `.dbadge-pos` and `.dbadge-neg`**

  Find lines 973–974:
  ```css
  .dbadge-pos { background: rgba(98,60,234,0.1); color: var(--majorelle-blue); }
  .dbadge-neg { background: rgba(84,66,107,0.08); color: var(--vintage-grape); }
  ```

- [ ] **Step 4: Fix both rules**

  Replace with:
  ```css
  .dbadge-pos { background: rgba(22,163,74,0.1); color: var(--green); }
  .dbadge-neg { background: rgba(220,38,38,0.08); color: var(--red); }
  ```

---

### Task 8: Fix `.dkpi-prog.kpf-lime` and `.dkpi-prog.kpf-red`

**Files:**
- Modify: `static/index.html` — lines 984, 986

- [ ] **Step 1: Locate the rules**

  Find lines 984 and 986:
  ```css
  .dkpi-prog.kpf-lime  { background: var(--majorelle-blue); }
  .dkpi-prog.kpf-gold  { background: var(--gold); }
  .dkpi-prog.kpf-red   { background: var(--vintage-grape); opacity: 0.6; }
  ```

- [ ] **Step 2: Fix lime and red progress bars**

  Replace those two lines (keep `.dkpi-prog.kpf-gold` unchanged):
  ```css
  .dkpi-prog.kpf-lime  { background: var(--green); }
  .dkpi-prog.kpf-gold  { background: var(--gold); }
  .dkpi-prog.kpf-red   { background: var(--red); }
  ```

  Note: `opacity: 0.6` is removed from `.kpf-red` — the saturated `#dc2626` red does not need dimming.

---

### Task 9: Fix `.dtype-val.dkpi-pos`, `.dtype-bar-pos`, `.dtype-bar-neg`

**Files:**
- Modify: `static/index.html` — lines 1068, 1079–1080

- [ ] **Step 1: Locate `.dtype-val.dkpi-pos`**

  Find line 1068:
  ```css
  .dtype-val.dkpi-pos { color: #22c55e; }
  ```

- [ ] **Step 2: Replace hardcoded hex**

  Change to:
  ```css
  .dtype-val.dkpi-pos { color: #16a34a; }
  ```

- [ ] **Step 3: Locate `.dtype-bar-pos` and `.dtype-bar-neg`**

  Find lines 1079–1080:
  ```css
  .dtype-bar-pos { background: var(--majorelle-blue); }
  .dtype-bar-neg { background: var(--vintage-grape); opacity: 0.55; }
  ```

- [ ] **Step 4: Fix both rules**

  Replace with:
  ```css
  .dtype-bar-pos { background: var(--green); }
  .dtype-bar-neg { background: var(--red); }
  ```

  Note: `opacity: 0.55` removed from `.dtype-bar-neg` — saturated red needs no dimming. These classes are overridden by inline `style` on each bar element (using `dotColors`), so this change is for CSS correctness and future consistency.

---

### Task 10: Fix standalone `.kpf-*` and `.kv-*` utility classes

**Files:**
- Modify: `static/index.html` — lines 1083–1089

- [ ] **Step 1: Locate the utility class block**

  Find lines 1083–1089:
  ```css
  /* kept for backward compat */
  .kpf-lime  { background: var(--majorelle-blue); }
  .kpf-green { background: var(--majorelle-blue); }
  .kpf-red   { background: var(--vintage-grape); }
  .kpf-gold  { background: var(--gold); }
  .kv-lime  { color: var(--majorelle-blue); }
  .kv-green { color: var(--majorelle-blue); }
  .kv-red   { color: var(--vintage-grape); }
  ```

- [ ] **Step 2: Fix lime, green, and red entries**

  Replace with:
  ```css
  /* kept for backward compat */
  .kpf-lime  { background: var(--green); }
  .kpf-green { background: var(--green); }
  .kpf-red   { background: var(--red); }
  .kpf-gold  { background: var(--gold); }
  .kv-lime  { color: var(--green); }
  .kv-green { color: var(--green); }
  .kv-red   { color: var(--red); }
  ```

  Leave `.kpf-gold`, `.kv-gold`, `.kv-teal`, `.kv-text` unchanged.

---

### Task 11: Verify KPI colors in DevTools

- [ ] **Step 1: Visual spot-check**

  Open the app, navigate to the Painel tab. Verify:
  - Positive KPI values (`.dkpi-pos`) appear in green
  - Negative KPI values (`.dkpi-neg`) appear in red
  - Dashboard progress bars for lime/red KPIs use green/red

  In DevTools console:
  ```js
  getComputedStyle(document.querySelector('.dkpi-pos')).color
  // Expected: "rgb(22, 163, 74)"
  ```

---

### Task 12: Commit Chunk 2

- [ ] **Step 1: Stage only `static/index.html`**

  ```bash
  git add static/index.html
  ```

- [ ] **Step 2: Commit**

  ```bash
  git commit -m "fix(colors): fix dashboard KPI, dbadge, dtype, kpf/kv utility classes to green/red"
  ```

---

## Chunk 3: Análise Tab Hardcoded Color Fix

### Task 13: Fix `.card-very` hardcoded teal rgba values

**Files:**
- Modify: `static/index.html` — lines 552–553

- [ ] **Step 1: Locate `.card-very` rules**

  Find lines 552–553:
  ```css
  .card-very::before { background: linear-gradient(90deg, rgba(0,212,180,.06), transparent); }
  .card-very:hover { box-shadow: 4px 0 28px rgba(0,212,180,.12); }
  ```

- [ ] **Step 2: Replace old teal (0,212,180) with current `--purple` (8,145,178)**

  Replace with:
  ```css
  .card-very::before { background: linear-gradient(90deg, rgba(8,145,178,0.06), transparent); }
  .card-very:hover { box-shadow: 4px 0 28px rgba(8,145,178,0.12); }
  ```

---

### Task 14: Fix `.card-fav` hardcoded green rgba values

**Files:**
- Modify: `static/index.html` — lines 556–557

- [ ] **Step 1: Locate `.card-fav` rules**

  Find lines 556–557:
  ```css
  .card-fav::before { background: linear-gradient(90deg, rgba(34,197,94,.05), transparent); }
  .card-fav:hover { box-shadow: 4px 0 28px rgba(34,197,94,.1); }
  ```

- [ ] **Step 2: Replace old green (34,197,94) with new `--green` (22,163,74)**

  Replace with:
  ```css
  .card-fav::before { background: linear-gradient(90deg, rgba(22,163,74,0.05), transparent); }
  .card-fav:hover { box-shadow: 4px 0 28px rgba(22,163,74,0.1); }
  ```

---

### Task 15: Commit Chunk 3

- [ ] **Step 1: Stage only `static/index.html`**

  ```bash
  git add static/index.html
  ```

- [ ] **Step 2: Commit**

  ```bash
  git commit -m "fix(analise): align card-very and card-fav hover colors to current palette"
  ```

---

## Chunk 4: painel.js Line Chart Colors

### Task 16: Fix `lineGradientFill` plugin RGB values

**Files:**
- Modify: `static/painel.js` — lines 26–27

- [ ] **Step 1: Locate the gradient plugin RGB values**

  Find lines 26–27:
  ```js
  // isPos → majorelle-blue  |  isNeg → vintage-grape
  const r = isPos ? 98  : 84, g = isPos ? 60  : 66, b = isPos ? 234 : 107;
  ```

- [ ] **Step 2: Update comment and RGB values to green/red**

  Replace with:
  ```js
  // isPos → green #16a34a  |  isNeg → red #dc2626
  const r = isPos ? 22  : 220, g = isPos ? 163 : 38, b = isPos ? 74  : 38;
  ```

---

### Task 17: Fix `drawLineChart` line color and background color

**Files:**
- Modify: `static/painel.js` — lines 344, 350

- [ ] **Step 1: Locate `lineColor` assignment**

  Find line 344:
  ```js
  const lineColor  = isPositive ? '#623cea' : '#54426b';
  ```

- [ ] **Step 2: Replace with green/red hex values**

  Change to:
  ```js
  const lineColor  = isPositive ? '#16a34a' : '#dc2626';
  ```

- [ ] **Step 3: Locate `backgroundColor` in dataset**

  Find line 350:
  ```js
  backgroundColor: isPositive ? 'rgba(98,60,234,0.08)' : 'rgba(84,66,107,0.06)',
  ```

- [ ] **Step 4: Replace with green/red rgba values**

  Change to:
  ```js
  backgroundColor: isPositive ? 'rgba(22,163,74,0.08)' : 'rgba(220,38,38,0.06)',
  ```

---

### Task 18: Verify line chart in browser

- [ ] **Step 1: Reload the app, navigate to Painel tab**

  The P&L cumulative chart should render:
  - In green (`#16a34a`) when total P&L is positive
  - In red (`#dc2626`) when total P&L is negative

  The gradient fill should match: green fade for positive, red fade for negative.

---

### Task 19: Commit Chunk 4

- [ ] **Step 1: Stage only `static/painel.js`**

  ```bash
  git add static/painel.js
  ```

- [ ] **Step 2: Commit**

  ```bash
  git commit -m "fix(painel): update P&L line chart gradient and colors to green/red"
  ```

---

## Final Verification

- [ ] Open the app and verify all Success Criteria from the spec:
  - `getComputedStyle(document.documentElement).getPropertyValue('--green').trim()` → `"#16a34a"`
  - `getComputedStyle(document.documentElement).getPropertyValue('--red').trim()` → `"#dc2626"`
  - `getComputedStyle(document.querySelector('.dkpi-pos')).color` → `"rgb(22, 163, 74)"`
  - `getComputedStyle(document.querySelector('.dkpi-neg')).color` → `"rgb(220, 38, 38)"`
  - Win badges (`.b-win`) display in green; loss badges (`.b-loss`) display in red
  - P&L line chart positive renders in green, negative in red
  - Análise tab `.card-very` hover shadow is teal-blue (not old teal `rgba(0,212,180,...)`)
  - Análise tab `.card-fav` hover shadow is green (`rgba(22,163,74,...)`)
