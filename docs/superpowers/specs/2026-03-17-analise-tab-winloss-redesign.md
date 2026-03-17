# Análise Tab + Win/Loss Color Correction — Design Spec
**Date:** 2026-03-17
**Project:** SCOUT · NBA Intelligence Platform
**Scope:** `static/index.html` (CSS) + `static/painel.js`
Note: `static/apostas.js` uses win/loss colors exclusively via CSS variables and classes — no JS changes needed in that file.

---

## Objective

Two bundled changes:
1. **Phase 1 correction** — revert win/loss semantic colors from majorelle-blue/vintage-grape back to proper green/red (better UX readability across the whole app)
2. **Análise tab fix** — correct hardcoded dark-mode color values in analysis player cards that were not updated in Phase 1

---

## Part 1 — Global Win/Loss Color Correction

### Token changes in `:root`

| Token | Phase 1 value (wrong) | New value | Rationale |
|---|---|---|---|
| `--green` | `#623cea` | `#16a34a` | Readable green on light backgrounds |
| `--green-dim` | `rgba(98,60,234,0.08)` | `rgba(22,163,74,0.1)` | Green tint for badge backgrounds |
| `--green-border` | `rgba(98,60,234,0.22)` | `rgba(22,163,74,0.25)` | Green border for badges |
| `--red` | `#54426b` | `#dc2626` | Readable red on light backgrounds |

Note: `--red` is used directly as a value, no associated `--red-dim`/`--red-border` variables needed (hardcoded in the few places that use them).

### CSS rules that auto-update via variables (no further changes needed)

The following properties auto-update by changing the `:root` tokens alone:
- `.b-win { background: var(--green-dim); border: 1px solid var(--green-border) }` — background and border auto-update; **`color` does NOT** (it's `var(--majorelle-blue)`, see manual table)
- `.badge-error { color: var(--red) }` — color auto-updates; **background and border still require manual update** (see table below)
- `.dtype-val.dkpi-neg { color: var(--red) }` — already uses `var(--red)`, auto-updates; no further action needed
- `.card-fav { border-left-color: var(--green); border-color: var(--green-border) }` — borders auto-update as Part 1 side-effect; the `::before` and `:hover` hardcoded values are fixed in Part 2
- `.badge-done`, `.pos-fav`, `.tag-fav` — all use `--green`/`--green-dim`/`--green-border`; will render in new green `#16a34a` as a Part 1 side-effect. These represent positive/favorite tiers (not win/loss), and the green update is intentional and correct for them.

All other win/loss semantic rules require manual changes (see table below).

Note: `.dtype-bar-wrap { background: rgba(84,66,107,0.07) }` — this is a structural neutral track background (not a win/loss semantic color); intentionally unchanged.

Note: `.bc-ganhou .bc-accent` and `.bc-perdeu .bc-accent` reference `var(--majorelle-blue)` / `var(--vintage-grape)` directly — they do NOT auto-update (see manual table).

### CSS rules with hardcoded values that need manual update

| Rule | Current hardcoded value | New value |
|---|---|---|
| `.dkpi-pos` color | `var(--majorelle-blue)` | `var(--green)` |
| `.dkpi-neg` color | `var(--vintage-grape)` | `var(--red)` |
| `.b-win` color | `var(--majorelle-blue)` | `var(--green)` |
| `.bc-ganhou .bc-accent` background | `var(--majorelle-blue)` | `var(--green)` |
| `.bc-perdeu .bc-accent` background | `var(--vintage-grape)` | `var(--red)` |
| `.dbadge-pos` background | `rgba(98,60,234,0.1)` | `rgba(22,163,74,0.1)` |
| `.dbadge-pos` color | `var(--majorelle-blue)` | `var(--green)` |
| `.dbadge-neg` background | `rgba(84,66,107,0.08)` | `rgba(220,38,38,0.08)` |
| `.dbadge-neg` color | `var(--vintage-grape)` | `var(--red)` |
| `.b-loss` background | `rgba(84,66,107,0.07)` | `rgba(220,38,38,0.08)` |
| `.b-loss` color | `var(--vintage-grape)` | `var(--red)` |
| `.b-loss` border | `rgba(84,66,107,0.2)` | `rgba(220,38,38,0.25)` |
| `.t-pnl-pos` color | `var(--majorelle-blue)` | `var(--green)` |
| `.t-pnl-neg` color | `var(--vintage-grape)` | `var(--red)` |
| `.dtype-val.dkpi-pos` color | `#22c55e` (hardcoded) | `#16a34a` |
| `.dtype-bar-pos` background | `var(--majorelle-blue)` | `var(--green)` |
| `.dtype-bar-neg` background | `var(--vintage-grape)` | `var(--red)` |
| `.dtype-bar-neg` opacity | `opacity: 0.55` | remove (no longer needed) |
| `.dkpi-prog.kpf-lime` background | `var(--majorelle-blue)` | `var(--green)` |
| `.kpf-lime` (standalone) background | `var(--majorelle-blue)` | `var(--green)` |
| `.kv-lime` color | `var(--majorelle-blue)` | `var(--green)` |
| `.kv-green` color | `var(--majorelle-blue)` | `var(--green)` |
| `.kpf-green` background | `var(--majorelle-blue)` | `var(--green)` |
| `.kpf-red` background | `var(--vintage-grape)` | `var(--red)` |
| `.kv-red` color | `var(--vintage-grape)` | `var(--red)` |
| `.dkpi-prog.kpf-red` background | `var(--vintage-grape)` | `var(--red)` |
| `.dkpi-prog.kpf-red` opacity | `opacity: 0.6` | remove (no longer needed) |
| `.badge-error` background | `rgba(244,63,94,.1)` | `rgba(220,38,38,0.1)` |
| `.badge-error` border | `rgba(244,63,94,.25)` | `rgba(220,38,38,0.25)` |

### painel.js changes

| Location | Current value | New value |
|---|---|---|
| `drawLineChart` — `lineColor` positive | `'#623cea'` | `'#16a34a'` |
| `drawLineChart` — `lineColor` negative | `'#54426b'` | `'#dc2626'` |
| `lineGradientFill` plugin — positive RGB | `r=98, g=60, b=234` | `r=22, g=163, b=74` |
| `lineGradientFill` plugin — negative RGB | `r=84, g=66, b=107` | `r=220, g=38, b=38` |
| `drawLineChart` — `backgroundColor` positive | `'rgba(98,60,234,0.08)'` | `'rgba(22,163,74,0.08)'` |
| `drawLineChart` — `backgroundColor` negative | `'rgba(84,66,107,0.06)'` | `'rgba(220,38,38,0.06)'` |
| `drawLineChart` — `pointHoverBorderColor` | `'#ffffff'` | `'#ffffff'` (unchanged) |
| Stale comment line 26 | `// isPos → majorelle-blue  \| isNeg → vintage-grape` | `// isPos → green #16a34a  \| isNeg → red #dc2626` |

The `↑`/`↓` arrows in `fmtMoney()` (painel.js) and `buildBetCard()` (apostas.js) are kept.

---

## Part 2 — Análise Tab: Fix Hardcoded Dark-Mode Colors

These CSS rules in `static/index.html` still reference old dark-mode hardcoded values for the `.card-very` (teal tier) and `.card-fav` (green tier) analysis player cards. Note: `--purple` current value is `#0891b2` (set in `:root`, unchanged by this spec); the rgba values below derive from that token's RGB components.

| Rule | Current hardcoded value | New value | Reason |
|---|---|---|---|
| `.card-very::before` background | `rgba(0,212,180,.06)` | `rgba(8,145,178,0.06)` | Match new `--purple: #0891b2` |
| `.card-very:hover` box-shadow | `4px 0 28px rgba(0,212,180,.12)` | `4px 0 28px rgba(8,145,178,0.12)` | Match new `--purple` |
| `.card-fav::before` background | `rgba(34,197,94,.05)` | `rgba(22,163,74,0.05)` | Match new `--green: #16a34a` |
| `.card-fav:hover` box-shadow | `4px 0 28px rgba(34,197,94,.1)` | `4px 0 28px rgba(22,163,74,0.1)` | Match new `--green` |

The `.card-best` rules (gold tier) are unchanged — gold values are unaffected.

---

## Files to Modify

| File | Change |
|---|---|
| `static/index.html` | `:root` — update 4 token values (`--green`, `--green-dim`, `--green-border`, `--red`) |
| `static/index.html` | `.dkpi-pos`, `.dkpi-neg` — change from majorelle-blue/vintage-grape to green/red vars |
| `static/index.html` | `.b-win` color — change `var(--majorelle-blue)` to `var(--green)` |
| `static/index.html` | `.bc-ganhou .bc-accent`, `.bc-perdeu .bc-accent` — change to `var(--green)` / `var(--red)` |
| `static/index.html` | `.dbadge-pos`, `.dbadge-neg` — update hardcoded colors |
| `static/index.html` | `.b-loss` — update hardcoded colors |
| `static/index.html` | `.t-pnl-pos`, `.t-pnl-neg` — change from majorelle-blue/vintage-grape to green/red vars |
| `static/index.html` | `.dtype-val.dkpi-pos` — change hardcoded `#22c55e` to `#16a34a` |
| `static/index.html` | `.dtype-bar-pos` — change from majorelle-blue to green; `.dtype-bar-neg` — change from vintage-grape to red, remove opacity |
| `static/index.html` | `.dkpi-prog.kpf-lime` — change from majorelle-blue to green; `.dkpi-prog.kpf-red` — change background from vintage-grape to red, remove opacity |
| `static/index.html` | `.kpf-lime` (standalone), `.kv-lime` — change from majorelle-blue to green |
| `static/index.html` | `.badge-error` — update hardcoded red values |
| `static/index.html` | `.kv-green`, `.kpf-green`, `.kv-red`, `.kpf-red` — point to correct vars |
| `static/index.html` | `.card-very::before`, `.card-very:hover` — fix teal hardcoded values |
| `static/index.html` | `.card-fav::before`, `.card-fav:hover` — fix green hardcoded values |
| `static/painel.js` | `lineGradientFill` plugin RGB values |
| `static/painel.js` | `drawLineChart` — `lineColor`, `backgroundColor` for positive/negative |
| `static/painel.js` | Stale comment on line 26 — update to reflect new green/red colors |

---

## What Does NOT Change

- The `↑`/`↓` arrows in badges and P&L display (apostas.js, painel.js)
- The majorelle-blue color for buttons, primary actions, active nav, chart bars
- The vintage-grape color for text, sidebar, headings
- Gold tier colors in analysis cards (`.card-best`)
- All layout, spacing, typography
- `dotColors` array in painel.js (`['#623cea', '#0891b2', '#d97706', …]`) — per-player stat bar colors cycling through the palette, not win/loss semantic; intentionally unchanged
- `.dtype-bar-wrap` track background `rgba(84,66,107,0.07)` — neutral structural color, not win/loss semantic; intentionally unchanged
- `_GRID = 'rgba(84,66,107,0.07)'` and `_TICK = 'rgba(84,66,107,0.45)'` constants in painel.js — structural chart grid/tick colors, not win/loss semantic; intentionally unchanged
- `bodyColor: '#54426b'` in painel.js tooltip config — neutral chart label color matching `--vintage-grape`; intentionally unchanged
- Note: `.dtype-bar-pos`/`.dtype-bar-neg` CSS class changes will have no visual effect on stat bars in the analysis section — the inline `style` attribute on each bar element overrides the class background with a `dotColors` value. The CSS update is still correct for consistency.
- `pointHoverBackgroundColor: lineColor` in painel.js line 356 — derives from `lineColor`; will change automatically when `lineColor` is updated per the painel.js changes table. This is an intentional side-effect, not a separate manual change.

---

## Success Criteria

- **Measurable:** Computed color of `.dkpi-pos` resolves to `rgb(22, 163, 74)` in DevTools
- **Measurable:** Computed color of `.dkpi-neg` resolves to `rgb(220, 38, 38)` in DevTools
- **Measurable:** `--green` CSS variable resolves to `#16a34a` in DevTools
- **Measurable:** `--red` CSS variable resolves to `#dc2626` in DevTools
- Win badges (`.b-win`) display in green; loss badges (`.b-loss`) display in red
- P&L line chart positive trend renders in green (`#16a34a`), negative in red (`#dc2626`)
- Análise tab `.card-very` hover shadow matches the teal-blue `#0891b2` hue
- Análise tab `.card-fav` hover shadow matches the green `#16a34a` hue
