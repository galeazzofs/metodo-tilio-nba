# Login Screen Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the auth screen so the brand mark is the sole hero element in the card, the SCOUT watermark is larger and uses vintage-grape, and all "SCOUT / NBA Intelligence Platform" copy is removed from the login card.

**Architecture:** Pure CSS + HTML changes inside the single embedded `<style>` block in `static/index.html`. No JS changes. No new files. Five targeted edits.

**Tech Stack:** Vanilla HTML/CSS, embedded `<style>` block in `static/index.html`

**Spec:** `docs/superpowers/specs/2026-03-17-login-screen-redesign.md`

---

## Chunk 1: CSS Changes

### Task 1: Update `.auth-wm` watermark

**Files:**
- Modify: `static/index.html` — `.auth-wm` rule inside `<style>`

- [ ] **Step 1: Locate the rule**

  Find the `.auth-wm` CSS rule (currently around line 107). Verify current values:
  - `font-size: clamp(90px, 16vw, 220px)`
  - `color: rgba(98,60,234,0.05)`

- [ ] **Step 2: Apply the change**

  Replace those two properties:
  ```css
  font-size: clamp(140px, 22vw, 320px);
  color: rgba(84,66,107,0.04);
  ```

- [ ] **Step 3: Verify in browser DevTools**

  Open the app, inspect `.auth-wm`. Confirm:
  - Computed `font-size` is larger than before
  - Computed `color` resolves to `rgba(84, 66, 107, 0.04)`

---

### Task 2: Update `.auth-logo` CSS

**Files:**
- Modify: `static/index.html` — `.auth-logo` rule inside `<style>`

- [ ] **Step 1: Locate the rule**

  Find the `.auth-logo` CSS rule. Current values:
  ```css
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 30px;
  ```

- [ ] **Step 2: Apply the change**

  Replace with:
  ```css
  display: flex;
  justify-content: center;
  margin-bottom: 28px;
  ```

  Remove `align-items: center` and `gap: 12px`.

---

### Task 3: Update `.auth-logo-mark` CSS

**Files:**
- Modify: `static/index.html` — `.auth-logo-mark` rule inside `<style>`

- [ ] **Step 1: Locate the rule**

  Find `.auth-logo-mark`. Current values:
  ```css
  width: 42px; height: 42px; border-radius: 10px;
  font-size: 16px;
  ```

- [ ] **Step 2: Apply the change**

  Update:
  ```css
  width: 60px; height: 60px; border-radius: 14px;
  font-size: 20px;
  ```

- [ ] **Step 3: Verify in browser DevTools**

  Inspect `.auth-logo-mark`. Confirm computed `width` and `height` both resolve to `60px`.

---

### Task 4: Remove `.auth-logo-name` and `.auth-logo-sub` CSS rules

**Files:**
- Modify: `static/index.html` — remove two CSS rules inside `<style>`

- [ ] **Step 1: Locate the rules**

  Find `.auth-logo-name` and `.auth-logo-sub` CSS rules.

- [ ] **Step 2: Delete both rules entirely**

  Remove the full `.auth-logo-name { ... }` and `.auth-logo-sub { ... }` rule blocks. They will no longer have corresponding HTML elements.

---

## Chunk 2: HTML Change

### Task 5: Clean up `.auth-logo` HTML

**Files:**
- Modify: `static/index.html` — `.auth-logo` element in `<body>`

- [ ] **Step 1: Locate the HTML**

  Find the `.auth-logo` div in the HTML body. It currently reads:
  ```html
  <div class="auth-logo">
    <div class="auth-logo-mark">SC</div>
    <div>
      <div class="auth-logo-name">SCOUT</div>
      <div class="auth-logo-sub">NBA Intelligence Platform</div>
    </div>
  </div>
  ```

- [ ] **Step 2: Remove the wrapper and text elements**

  Replace with:
  ```html
  <div class="auth-logo">
    <div class="auth-logo-mark">SC</div>
  </div>
  ```

  Remove the unnamed wrapper `<div>`, `.auth-logo-name`, and `.auth-logo-sub` entirely from the DOM.

- [ ] **Step 3: Verify in browser DevTools**

  Run in console:
  ```js
  document.querySelector('.auth-logo-name')  // must return null
  document.querySelector('.auth-logo-sub')   // must return null
  ```

---

## Chunk 3: Commit

### Task 6: Commit the changes

- [ ] **Step 1: Stage only the modified file**

  ```bash
  git add static/index.html
  ```

- [ ] **Step 2: Commit**

  ```bash
  git commit -m "feat(auth): editorial login — brand mark hero, larger watermark"
  ```

- [ ] **Step 3: Final visual check**

  Open the app login screen. Confirm:
  1. No "SCOUT" text or "NBA Intelligence Platform" subtitle visible in the card
  2. Brand mark (SC square, ~60px) is centered at the top of the card
  3. Background watermark "SCOUT" is barely perceptible but present
  4. Form tabs appear immediately below the brand mark
