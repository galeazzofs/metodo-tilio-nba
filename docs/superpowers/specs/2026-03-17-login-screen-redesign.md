# Login Screen Redesign — Design Spec
**Date:** 2026-03-17
**Project:** SCOUT · NBA Intelligence Platform
**Scope:** `static/index.html` — `#authScreen` and `.auth-card` sections only

---

## Objective

Elevate the login screen from a functional form to a branded, editorial-feeling entry point that communicates quality and intention. The aesthetic direction is **"Fintech Premium Editorial"** — minimalist card, ghost typography watermark, brand mark as the sole hero element.

---

## Design Decisions

| Dimension | Decision | Rationale |
|---|---|---|
| Layout | Centered card on alice-blue | Maximises whitespace; lets the card breathe |
| Background text | "SCOUT" ghost watermark, ~3-4% opacity | Adds editorial depth without visual noise |
| Brand anchor | 60×60px SC mark centered, alone | Immediate brand recognition; no copy needed |
| Tagline | None | Logo mark speaks for itself |
| Card decoration | None beyond shadow + pearl-beige border | Purity is the personality |

---

## Background Layer (stacking order, bottom to top)

1. **Base** — solid `#e9f1f7` (alice-blue)
2. **Dot-grid** — `radial-gradient` dots in `rgba(98,60,234,0.12)`, spaced 28×28px (already implemented)
3. **"SCOUT" watermark** — font-size increases from `clamp(90px, 16vw, 220px)` to `clamp(140px, 22vw, 320px)`, Syne 900. Color changes from `rgba(98,60,234,0.05)` (majorelle-blue) to `rgba(84,66,107,0.04)` (vintage-grape — chosen so the ghost text recedes into the background rather than hinting at the accent color). Centered at `top: 45%` / `left: 50%`, `transform: translate(-50%, -52%)`, `pointer-events: none`, `user-select: none`
4. **Radial vignette** — `radial-gradient(ellipse 80% 80% at 50% 50%, transparent 35%, #e9f1f7 100%)` (already implemented)

---

## Card Layout

**Container:** `max-width: 400px`, `padding: 40px`, `background: #ffffff`, `border: 1px solid #dbd5b2`, `border-radius: 16px`, `box-shadow: 0 8px 48px rgba(84,66,107,0.10), 0 2px 8px rgba(84,66,107,0.06)`

### Internal structure (top → bottom)

#### 1. Brand Mark Hero
- Element: `.auth-logo-mark` (repurposed as standalone centered hero)
- Size: `60×60px` (up from 42px)
- `border-radius: 14px`
- Background: `#623cea` (majorelle-blue)
- Text: "SC", Syne 900, 20px, `#ffffff`
- Layout on `.auth-logo`: `display: flex; justify-content: center; margin-bottom: 28px` (changes from left-aligned flex row with `gap:12px; margin-bottom:30px`)
- **HTML change:** remove the unnamed wrapper `<div>` that currently wraps `.auth-logo-name` and `.auth-logo-sub`, and remove those two elements entirely from the DOM. The resulting `.auth-logo` contains only `.auth-logo-mark`.

#### 2. Toggle Tabs (Entrar / Criar conta)
- No changes to function
- Background: `rgba(84,66,107,0.06)` (already implemented)
- Active tab: `#ffffff` with soft shadow (already implemented)

#### 3. Form Fields
- Email, Password, (Confirm Password for registration)
- Background: `#e9f1f7` (alice-blue), border: `#dbd5b2` (pearl-beige)
- Focus: `border-color: rgba(98,60,234,0.45)` + `box-shadow: 0 0 0 3px rgba(98,60,234,0.08)`
- All already implemented in Phase 1

#### 4. Primary Button
- Background: `#623cea`, color: `#ffffff`, shimmer animation
- Already implemented in Phase 1

#### 5. Divider + Google Button
- Already implemented in Phase 1

---

## Files to Modify

| File | Section | Change |
|---|---|---|
| `static/index.html` | `.auth-logo` (CSS) | Change `align-items:center; gap:12px; margin-bottom:30px` → `justify-content:center; margin-bottom:28px` |
| `static/index.html` | `.auth-logo` (HTML) | Remove unnamed wrapper `<div>` + `.auth-logo-name` + `.auth-logo-sub` elements; leave only `.auth-logo-mark` inside |
| `static/index.html` | `.auth-logo-mark` (CSS) | `42×42px` → `60×60px`; `border-radius: 10px` → `14px`; `font-size: 16px` → `20px` |
| `static/index.html` | `.auth-logo-name`, `.auth-logo-sub` (CSS) | Remove these rules (elements no longer exist in DOM) |
| `static/index.html` | `.auth-wm` (CSS) | `font-size: clamp(90px,16vw,220px)` → `clamp(140px,22vw,320px)`; `color: rgba(98,60,234,0.05)` → `rgba(84,66,107,0.04)` |

---

## What Does NOT Change

- Card dimensions, padding, border-radius, shadow (already set in Phase 1)
- Form fields, buttons, divider, Google button (already set in Phase 1)
- Dot-grid and vignette background (already set in Phase 1)
- Auth toggle tabs (already set in Phase 1)
- All CSS variables and the rest of the app

---

## Success Criteria

- **Measurable:** No element with class `.auth-logo-name` or `.auth-logo-sub` exists in the DOM
- **Measurable:** Computed `width` and `height` of `.auth-logo-mark` resolve to `60px` in browser DevTools
- **Measurable:** Computed `color` of `.auth-wm` resolves to `rgba(84, 66, 107, 0.04)` in browser DevTools
- Brand mark is the first visible element inside the card — no text copy precedes the form tabs
- Background watermark is perceptible on close inspection but does not draw the eye away from the card
