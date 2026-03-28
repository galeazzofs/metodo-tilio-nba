# 3PT Open Gate + Bench Threshold Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open 3PT analysis to all qualifying players (not just injury replacements), add a 3PA volume gate, graduate DvP/Signal 3 scoring, and raise bench minutes threshold from 20 to 25 min/g globally.

**Architecture:** Rewrite `_score_player_3pt()` to remove `is_stepping_up` and graduate scoring. Move 3PT from Loop 1 (injury gate) to Loop 2 (open gate). Add constants `MIN_3PA_PER_GAME` and `MIN_BENCH_MINUTES`. All changes in `engine.py` and its tests.

**Tech Stack:** Python, pytest

**Spec:** `docs/superpowers/specs/2026-03-28-3pt-open-gate-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `analysis/engine.py` | Modify | Rewrite `_score_player_3pt()`, restructure loops, add constants, change bench threshold |
| `tests/test_engine.py` | Modify | Rewrite 3PT tests, add graduated scoring tests, add volume gate boundary test |

---

## Chunk 1: Rewrite `_score_player_3pt()` Scoring Function

### Task 1: Update tests for new `_score_player_3pt` signature and graduated scoring

**Files:**
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Rewrite `test_3pt_gate_not_stepping_up` → remove (no longer applicable)**

Delete `test_3pt_gate_not_stepping_up` entirely (lines 892-903). The stepping-up gate no longer exists.

- [ ] **Step 3: Update `test_3pt_gate_dvp_rank_above_6` — remove `is_stepping_up`**

Replace the function (lines 906-915) with:

```python
def test_3pt_gate_dvp_rank_above_6():
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=TEAM_DEF_3PT_POOR,
        recent_stats=RECENT_3PT_ABOVE_AVG,
        tracking_data=None,
    )
    assert score == 0
    assert rating is None
```

- [ ] **Step 4: Rewrite `test_3pt_full_score_6` — DvP rank 1-2 still gives +3**

Replace the function (lines 918-932) with:

```python
def test_3pt_full_score_6():
    """DvP rank 2 (+3) + form above avg (+1) + both Signal 3 conditions (+2) = 6 BEST."""
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=TEAM_DEF_3PT_ELITE,
        recent_stats=RECENT_3PT_ABOVE_AVG,
        tracking_data=None,
    )
    assert score == 6
    assert rating == "BEST OF THE NIGHT"
    assert signals["dvp"] == 3
    assert signals["recent_form"] == 1
    assert signals["potential_3pt"] == 2
```

- [ ] **Step 5: Add test for graduated DvP rank 3-6 → +2**

```python
def test_3pt_dvp_rank_3_to_6_gives_2():
    """DvP rank 5 (3-6 range) → +2 instead of +3. Max score = 5 = VERY FAVORABLE."""
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=TEAM_DEF_3PT_GOOD,
        recent_stats=RECENT_3PT_ABOVE_AVG,
        tracking_data=None,
    )
    assert signals["dvp"] == 2
    assert score == 5  # 2 + 1 + 2
    assert rating == "VERY FAVORABLE"
```

- [ ] **Step 6: Rewrite `test_3pt_volume_down_no_bonus` — graduated Signal 3**

Replace with:

```python
def test_3pt_volume_down_opponent_permissive():
    """Volume DOWN but opponent permissive (rank_three_pa <= 6) → only one condition → +1."""
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=TEAM_DEF_3PT_ELITE,
        recent_stats=RECENT_3PT_VOLUME_DOWN,
        tracking_data=None,
    )
    assert signals["potential_3pt"] == 1
    # DvP rank 2 (+3) + form +1 + one condition (+1) = 5
    assert score == 5
    assert rating == "VERY FAVORABLE"
```

- [ ] **Step 7: Rewrite fallback tests — unified Signal 3 (no more fallback distinction)**

Replace `test_3pt_fallback_rank_pa_top3` (lines 950-960) with:

```python
def test_3pt_both_signal3_conditions():
    """rank_three_pa <= 6 AND volume up → +2 (both conditions met)."""
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=TEAM_DEF_3PT_RANK_PA_TOP3,
        recent_stats=RECENT_3PT_ABOVE_AVG,
        tracking_data=None,
    )
    assert signals["potential_3pt"] == 2
```

Replace `test_3pt_rank_pa_4_no_fallback` (lines 963-973) with:

```python
def test_3pt_rank_pa_4_both_conditions():
    """rank_three_pa=4 (<=6, condition A met) + volume up (condition B met) → +2."""
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=TEAM_DEF_3PT_RANK_PA_4,
        recent_stats=RECENT_3PT_ABOVE_AVG,
        tracking_data=None,
    )
    assert signals["potential_3pt"] == 2
    # DvP rank 4 (+2) + form +1 + both conditions (+2) = 5
    assert score == 5
```

- [ ] **Step 8: Add test for Signal 3 neither condition met**

```python
def test_3pt_neither_signal3_condition():
    """Opponent NOT permissive (rank > 6) AND volume DOWN → 0 for Signal 3."""
    team_def_strict = {"PG": {"rank_ast": 10, "rank_reb": 10, "rank_three_pm": 2, "rank_three_pa": 8}}
    recent_vol_down = {"three_pm": 3.0, "season_avg_three_pm": 2.0, "three_pa": 5.0, "season_avg_three_pa": 6.0}
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=team_def_strict,
        recent_stats=recent_vol_down,
        tracking_data=None,
    )
    assert signals["potential_3pt"] == 0
    # DvP rank 2 (+3) + form +1 + neither (0) = 4
    assert score == 4
    assert rating == "VERY FAVORABLE"
```

- [ ] **Step 9: Add test for Signal 3 only volume up (opponent not permissive)**

```python
def test_3pt_only_volume_up():
    """Volume UP but opponent rank_three_pa > 6 → only one condition → +1."""
    team_def_strict = {"PG": {"rank_ast": 10, "rank_reb": 10, "rank_three_pm": 2, "rank_three_pa": 8}}
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=team_def_strict,
        recent_stats=RECENT_3PT_ABOVE_AVG,
        tracking_data=None,
    )
    assert signals["potential_3pt"] == 1
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -k "3pt" -v`
Expected: FAIL — tests call `_score_player_3pt` without `is_stepping_up`, but current code requires it.

- [ ] **Step 11: Commit failing tests**

```bash
git add tests/test_engine.py
git commit -m "test: rewrite 3PT tests for graduated scoring without stepping-up gate"
```

---

### Task 2: Rewrite `_score_player_3pt()` implementation

**Files:**
- Modify: `analysis/engine.py`

- [ ] **Step 1: Replace `_score_player_3pt` function entirely**

Replace lines 463-528 in `analysis/engine.py` with:

```python
def _score_player_3pt(position, opponent_name, team_defense, recent_stats, tracking_data):
    """
    Score a player's 3-point upside (0-6 scale).
    Graduated DvP: rank 1-2 → 3pts, rank 3-6 → 2pts, 7+ → discard.
    Graduated Signal 3: both conditions → 2pts, one → 1pt, neither → 0.
    Threshold: 4 for VERY FAVORABLE, 6 for BEST OF THE NIGHT.
    Returns (score, rating, signals_dict, context_dict).
    """
    pos_def = team_defense.get(position, {})
    dvp_rank = pos_def.get("rank_three_pm")

    score = 0
    signals = {}
    descriptions = []

    # --- Signal 1: DvP 3PM rank (graduated: 0, 2, or 3 pts) ---
    dvp_pts = 0
    if dvp_rank is not None:
        if dvp_rank <= 2:
            dvp_pts = 3
        elif dvp_rank <= 6:
            dvp_pts = 2
    if dvp_pts == 0:
        return 0, None, {}, {}
    score += dvp_pts
    signals["dvp"] = dvp_pts
    descriptions.append(f"3PT matchup vs {opponent_name} (DvP #{dvp_rank}, +{dvp_pts})")

    # --- Signal 2: Recent form (0 or 1 pt) ---
    three_pm_recent = recent_stats.get("three_pm", 0)
    season_avg_three_pm = recent_stats.get("season_avg_three_pm", 0)
    if three_pm_recent >= season_avg_three_pm:
        score += 1
        signals["recent_form"] = 1
        descriptions.append(f"3PT form above avg ({three_pm_recent} vs {season_avg_three_pm} season)")
    else:
        signals["recent_form"] = 0

    # --- Signal 3: 3PT opportunity (graduated: 0, 1, or 2 pts) ---
    three_pa = recent_stats.get("three_pa", 0)
    season_avg_three_pa = recent_stats.get("season_avg_three_pa", 0)
    rank_three_pa = pos_def.get("rank_three_pa", 99)

    condition_a = rank_three_pa <= 6  # opponent permissive
    condition_b = three_pa >= season_avg_three_pa  # volume up

    if condition_a and condition_b:
        three_bonus = 2
        descriptions.append(f"Volume up ({three_pa} 3PA) + opponent allows 3PA (rank {rank_three_pa})")
    elif condition_a or condition_b:
        three_bonus = 1
        if condition_a:
            descriptions.append(f"Opponent allows 3PA (rank {rank_three_pa})")
        else:
            descriptions.append(f"Volume up ({three_pa} 3PA)")
    else:
        three_bonus = 0

    score += three_bonus
    signals["potential_3pt"] = three_bonus

    # --- Rating ---
    if score >= 6:
        rating = "BEST OF THE NIGHT"
    elif score >= 4:
        rating = "VERY FAVORABLE"
    else:
        rating = None

    context = {"dvp_rank": dvp_rank, "signal_descriptions": descriptions}
    return score, rating, signals, context
```

- [ ] **Step 2: Run 3PT tests**

Run: `python -m pytest tests/test_engine.py -k "3pt" -v`
Expected: All tests PASS

- [ ] **Step 3: Run full engine test suite**

Run: `python -m pytest tests/test_engine.py -v`
Expected: All tests PASS (some existing tests call `_score_player_3pt` with `is_stepping_up=True` from inside `run_analysis` tests — those will break in Task 3 when we change the loops. For now, confirm the direct `_score_player_3pt` tests pass.)

- [ ] **Step 4: Commit**

```bash
git add analysis/engine.py
git commit -m "feat: graduate 3PT scoring and remove stepping-up gate"
```

---

## Chunk 2: Loop Restructure + Bench Threshold

### Task 3: Add constants, restructure loops, change bench threshold

**Files:**
- Modify: `analysis/engine.py`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Add new constants**

Add after `BLOWOUT_ODD_THRESHOLD = 1.10` (after line 38):

```python
MIN_3PA_PER_GAME = 3.0
MIN_BENCH_MINUTES = 25.0
```

- [ ] **Step 2: Update Loop 1 — remove 3PT, update labels**

In `run_analysis()`, make these changes:

Change the Loop 1 header (line 636) from:
```python
    print("  --- Loop 1: PTS/3PT (injury gate) ---")
```
to:
```python
    print("  --- Loop 1: PTS (injury gate) ---")
```

Change the skip log (line 660) from:
```python
                print(f"  [skip PTS/3PT] {player_tricode} - no starter out")
```
to:
```python
                print(f"  [skip PTS] {player_tricode} - no starter out")
```

Change the analyzing log (line 680) from:
```python
                print(f"  [PTS/3PT] Analyzing {player_name} ({player_tricode} vs {opponent_tricode}, {min_avg} min/g)...")
```
to:
```python
                print(f"  [PTS] Analyzing {player_name} ({player_tricode} vs {opponent_tricode}, {min_avg} min/g)...")
```

Delete the entire 3PT scoring block from Loop 1 (lines 726-749):
```python
                # 3PT scoring — tracking_data now nested by team_id → position
                opp_3pt_tracking = None
                ...
                    })
```

- [ ] **Step 3: Update Loop 2 header and logs**

Change the Loop 2 header from:
```python
    print("  --- Loop 2: AST/REB (open gate) ---", flush=True)
```
to:
```python
    print("  --- Loop 2: AST/REB/3PT (open gate) ---", flush=True)
```

Change the pace gate skip log from `"[skip AST/REB]"` to `"[skip AST/REB/3PT]"`.

Change the player count log from `"[AST/REB]"` to `"[AST/REB/3PT]"`.

Update the comment at the "Build player list" line from `"projected starters + bench >= 20 min/g"` to `"projected starters + bench >= MIN_BENCH_MINUTES min/g"`.

Update the comment `"Add bench players >= 20 min/g from roster"` to `"Add bench players >= MIN_BENCH_MINUTES min/g from roster"`.

- [ ] **Step 4: Change bench threshold to use constant**

Replace the bench threshold check (currently line 798, shifted after Loop 1 changes) from:
```python
                        if mins is not None and mins >= 20.0:
```
to:
```python
                        if mins is not None and mins >= MIN_BENCH_MINUTES:
```

- [ ] **Step 5: Add 3PT scoring to Loop 2**

Insert **immediately after** the REB candidate append block ends (after the `})` closing the `all_candidates["reb"].append({...})` block, currently line 870), add:

```python

                # 3PT scoring — only for players with sufficient 3PA volume
                season_avg_3pa = recent_stats.get("season_avg_three_pa", 0)
                if season_avg_3pa >= MIN_3PA_PER_GAME:
                    three_score, three_rating, three_signals, three_context = _score_player_3pt(
                        pos_key, opponent_name, opp_def, recent_stats, opp_tracking,
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

- [ ] **Step 6: Update test imports and add constant/gate tests**

Update the import block in `tests/test_engine.py` to include new constants:

```python
from analysis.engine import (
    _score_player, run_analysis, _position_compatible, _team_has_stake,
    filter_games_by_stake, _ordinal, _score_player_ast, _score_player_reb,
    _score_player_3pt, _dedup_candidates,
    filter_games_by_blowout, BLOWOUT_ODD_THRESHOLD,
    MIN_3PA_PER_GAME, MIN_BENCH_MINUTES,
)
```

Add constant value tests and volume gate boundary test at the end of the 3PT test section:

```python
def test_3pt_constants():
    """Verify constant values."""
    assert MIN_3PA_PER_GAME == 3.0
    assert MIN_BENCH_MINUTES == 25.0


def test_3pt_volume_gate_boundary():
    """Player with exactly 3.0 3PA/g passes the gate (>= is inclusive)."""
    assert 3.0 >= MIN_3PA_PER_GAME  # boundary: exactly at threshold passes
    assert 2.9 < MIN_3PA_PER_GAME   # below threshold fails


def test_bench_threshold_boundary():
    """Player with exactly 25.0 min/g passes (>= is inclusive), 24.9 fails."""
    assert 25.0 >= MIN_BENCH_MINUTES
    assert 24.9 < MIN_BENCH_MINUTES
```

- [ ] **Step 7: Run full engine test suite**

Run: `python -m pytest tests/test_engine.py -v`
Expected: All tests PASS

- [ ] **Step 8: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add analysis/engine.py tests/test_engine.py
git commit -m "feat: move 3PT to open gate loop, raise bench threshold to 25 min/g"
```
