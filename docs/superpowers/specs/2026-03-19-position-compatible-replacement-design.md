# Position-Compatible Replacement Gate — Design Spec

**Date:** 2026-03-19
**Status:** Approved
**Scope:** `analysis/engine.py` only

---

## Problem

The engine currently checks whether *any* starter is out for a team before scoring bench candidates. It does not verify that the candidate's position is compatible with the absent starter's position. This means a C could be surfaced as a replacement when only a PG is out — a logically invalid stepping-up scenario.

---

## Goal

A bench player is only a valid replacement candidate if their position is compatible with the position of at least one starter who is confirmed out tonight.

---

## Design

### 1. New constant — `POSITION_COMPAT`

Added near the existing `POSITION_MAP` constant:

```python
POSITION_COMPAT = {
    "PG": {"PG", "SG", "G"},
    "SG": {"SG", "PG", "G"},
    "G":  {"G",  "PG", "SG"},
    "SF": {"SF", "PF", "F"},
    "PF": {"PF", "SF", "F", "C"},
    "F":  {"F",  "SF", "PF"},
    "C":  {"C",  "PF"},
}
```

Keys are the **out starter's position**. Values are the set of **candidate positions** that can legitimately fill that role.

Design rationale:
- Guards (PG/SG/G) are interchangeable within the backcourt.
- Forwards (SF/PF/F) are interchangeable within the frontcourt.
- A C can replace a PF (and vice versa) but not backcourt players.
- A PG cannot replace a C or SF — position families do not cross.

### 2. `out_starters` stores dicts, not just names

**Current:**
```python
out_starters.append(p["name"])
```

**New:**
```python
out_starters.append({"name": p["name"], "position": p["position"]})
```

RotoWire already provides position data for out players; this change simply captures it.

### 3. New helper — `_position_compatible`

```python
def _position_compatible(candidate_pos, out_starters):
    """
    Returns the subset of out_starters whose position is compatible
    with the given candidate position.
    """
    allowed = POSITION_COMPAT.get(candidate_pos, set())
    return [s for s in out_starters if s["position"] in allowed]
```

Returns a list. Empty list means no valid replacement scenario exists for this candidate.

### 4. Gate in the candidate loop

Inserted after the existing `min_avg < STARTER_MIN_THRESHOLD` check, before `_score_player` is called:

```python
matched_starters = _position_compatible(position, out_starters)
if not matched_starters:
    print(f"  [skip] {player_name} - no position-compatible starter out ({position})")
    continue
```

### 5. `replaces` field updated

The `replaces` field in the candidate dict is narrowed to only the starters the candidate can actually replace:

```python
"replaces": [s["name"] for s in matched_starters],
```

Previously it contained all out starters regardless of position. Now it contains only position-matched ones, making downstream display (Telegram, UI) accurate.

---

## What Does Not Change

- `_score_player` — no changes to scoring logic or thresholds.
- `POSITION_MAP` — kept as-is (used for DvP lookups, unrelated to replacement logic).
- All other files — no changes outside `engine.py`.

---

## Edge Cases

| Scenario | Behaviour |
|---|---|
| Out player has no position in RotoWire data | `p["position"]` is an empty string or missing → `POSITION_COMPAT.get("")` returns `set()` → no candidates qualify for that out player (safe default) |
| Candidate position not in `POSITION_COMPAT` | `POSITION_COMPAT.get(candidate_pos, set())` returns empty set → candidate is skipped (safe default) |
| Multiple starters out, candidate matches at least one | Candidate proceeds; `replaces` lists only the matched starters |
| Multiple starters out, candidate matches none | Candidate is skipped |

---

## Files Changed

- `analysis/engine.py` — only file modified
