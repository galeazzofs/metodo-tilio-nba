# 3PT Open Gate + Bench Threshold Increase Design

**Date:** 2026-03-28
**Status:** Approved
**Scope:** Remove injury gate from 3PT analysis, open to all qualifying players, add volume gate, graduate scoring, and raise bench minutes threshold to 25 min/g globally

## Problem

The 3PT analysis currently requires the "stepping up" gate — only bench players replacing injured starters are analyzed. This is too restrictive and misses strong 3PT matchups for starters and regular rotation players.

Additionally, the bench threshold of 20 min/g for AST/REB is too low, surfacing players with insufficient playing time who often don't have betting lines available.

## Solution

Two changes:

1. **Open 3PT gate:** Move 3PT from Loop 1 (injury gate) to Loop 2 (open gate), using the same player pool as AST/REB. Add a minimum 3PA volume gate. Graduate the DvP scoring and Signal 3.

2. **Raise bench threshold globally:** Change bench player minimum from 20 to 25 min/g for AST, REB, and 3PT (all Loop 2 stats).

## Design

### 1. Scoring Function Change — `_score_player_3pt()`

**Remove `is_stepping_up` parameter and gate.**

Current first lines:
```python
def _score_player_3pt(position, opponent_name, team_defense, recent_stats, tracking_data, is_stepping_up):
    if not is_stepping_up:
        return 0, None, {}, {}
```

New signature (no `is_stepping_up`):
```python
def _score_player_3pt(position, opponent_name, team_defense, recent_stats, tracking_data):
```

**Graduate DvP scoring (Signal 1).** Currently binary: rank ≤ 6 → +3, else discard. New:

| DvP 3PM Rank | Points |
|---|---|
| 1-2 | +3 |
| 3-6 | +2 |
| 7+ | discard (return 0) |

**Graduate Signal 3 (opportunity).** Currently all-or-nothing: both conditions → +2, else 0. New:

| Condition | Points |
|---|---|
| Opponent `rank_three_pa` ≤ 6 **AND** player 3PA recent ≥ season avg | +2 |
| Only one of the two conditions met | +1 |
| Neither condition met | 0 |

**Signal 2 (recent form)** stays the same: 3PM recent ≥ season avg → +1.

**Thresholds** stay the same: ≥ 6 BEST OF THE NIGHT, ≥ 4 VERY FAVORABLE.

### 2. Loop Restructure — `run_analysis()`

**Remove 3PT from Loop 1.** Loop 1 becomes PTS-only (injury gate).

**Add 3PT to Loop 2.** Loop 2 becomes AST/REB/3PT (open gate). For each player in the open-gate pool, after scoring AST and REB, also score 3PT — but only if the player passes the volume gate.

**Volume gate for 3PT:** Player must have season average 3PA/g ≥ 3.0 to be analyzed for 3PT. This is checked per-player inside Loop 2, before calling `_score_player_3pt()`. Players who don't meet this threshold are skipped for 3PT but still analyzed for AST/REB.

**New constant:**
```python
MIN_3PA_PER_GAME = 3.0
```

### 3. Bench Threshold Change — Global

**Change bench player minimum from 20 to 25 min/g** in Loop 2.

Current code at `engine.py` line 798:
```python
if mins is not None and mins >= 20.0:
```

New:
```python
if mins is not None and mins >= 25.0:
```

**New constant** (replace magic number):
```python
MIN_BENCH_MINUTES = 25.0
```

This affects **all Loop 2 stats**: AST, REB, and 3PT.

### 4. Loop 1 Cleanup

Loop 1 currently scores both PTS and 3PT for injury-gate players. After this change:

- Loop 1 scores **PTS only**
- The 3PT scoring block inside Loop 1 (lines 726-749) is **removed entirely**
- Loop 1 header changes from `"Loop 1: PTS/3PT (injury gate)"` to `"Loop 1: PTS (injury gate)"`
- The skip log changes from `"[skip PTS/3PT]"` to `"[skip PTS]"`

### 5. Caller Update for `_score_player_3pt()`

Every call to `_score_player_3pt()` must drop the `is_stepping_up` argument:

- **Loop 1 call (lines 732-734):** Removed entirely (3PT no longer in Loop 1)
- **Any future call:** New signature has no `is_stepping_up` param

### 6. 3PT in Loop 2 — Implementation Detail

Inside Loop 2, after the REB scoring block, add 3PT scoring:

```python
# 3PT scoring — only for players with sufficient 3PA volume
season_avg_3pa = recent_stats.get("season_avg_three_pa", 0)
if season_avg_3pa >= MIN_3PA_PER_GAME:
    opp_3pt_tracking = opp_tracking  # already fetched for AST/REB
    three_score, three_rating, three_signals, three_context = _score_player_3pt(
        pos_key, opponent_name, opp_def, recent_stats, opp_3pt_tracking,
    )
    if three_rating:
        three_context["starter_out"] = None
        all_candidates["three_pt"].append({
            "player_name": player_name,
            "player_id": player_id,
            "team": team_data.get("team_name", player_tricode),
            "position": position,
            "game": game_label,
            "score": three_score,
            "rating": three_rating,
            "signals": three_signals,
            "context": three_context,
            "recent_stats": recent_stats,
            "replaces": [],
        })
```

Note: `replaces` is always `[]` since there is no injury gate.

## Files Changed

| File | Change |
|------|--------|
| `analysis/engine.py` | Remove `is_stepping_up` from `_score_player_3pt()`, graduate DvP and Signal 3, add `MIN_3PA_PER_GAME` and `MIN_BENCH_MINUTES` constants, remove 3PT from Loop 1, add 3PT to Loop 2, change bench threshold from 20 to 25 |
| `tests/test_engine.py` | Update `_score_player_3pt` tests (remove `is_stepping_up`), add graduated DvP tests, add graduated Signal 3 tests, add volume gate tests, update bench threshold tests |

## Files NOT Changed

- `analysis/pipeline.py` — no changes
- `scrapers/odds.py` — no changes
- `output/formatter.py` — no changes (3PT candidates have same structure)
- PTS scoring — untouched (stays in Loop 1 with injury gate)
- AST/REB scoring functions — untouched
- Deduplication — untouched (already handles 4 stat categories)

## Behavior Examples

### 3PT now finds starters
Before: Steph Curry would never appear in 3PT analysis (he's a starter, not stepping up).
After: Steph Curry with 11.2 3PA/g vs MIA (DvP #3) → scored and potentially rated.

### Volume gate filters non-shooters
A center averaging 0.5 3PA/g with a great DvP matchup is skipped — no point analyzing 3PT for a player who doesn't shoot threes.

### Bench threshold filters low-minute players
A bench player averaging 18 min/g is excluded from AST, REB, and 3PT analysis. Before, they would have been included (threshold was 20).

## Summary of Constants

| Constant | Value | Used by |
|----------|-------|---------|
| `BLOWOUT_ODD_THRESHOLD` | 1.10 | `filter_games_by_blowout()` (existing) |
| `MIN_3PA_PER_GAME` | 3.0 | 3PT volume gate in Loop 2 (new) |
| `MIN_BENCH_MINUTES` | 25.0 | Bench player eligibility in Loop 2 (new, replaces hardcoded 20.0) |
