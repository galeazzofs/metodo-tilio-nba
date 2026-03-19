# Position-Compatible Replacement Gate — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate bench player candidates so they only qualify if their position is compatible with at least one starter who is confirmed out tonight.

**Architecture:** Add `POSITION_COMPAT` constant and `_position_compatible` helper to `analysis/engine.py`. Change `out_starters` to store dicts (name + position). Insert a position gate after the existing minutes threshold check. Narrow the `replaces` field to position-matched starters only.

**Tech Stack:** Python 3, pytest, unittest.mock

---

## Chunk 1: `POSITION_COMPAT` constant + `_position_compatible` helper

### Task 1: Tests for `_position_compatible`

**Files:**
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Add the failing tests at the bottom of `tests/test_engine.py`**

First, update the existing import at the top of `tests/test_engine.py` (line 3) to include `_position_compatible`:

```python
# Before:
from analysis.engine import _score_player, run_analysis
# After:
from analysis.engine import _score_player, run_analysis, _position_compatible
```

Then add the test fixtures and tests at the bottom of the file:

```python
# ---------------------------------------------------------------------------
# _position_compatible
# ---------------------------------------------------------------------------

OUT_PG = {"name": "Star PG", "position": "PG"}
OUT_C  = {"name": "Star C",  "position": "C"}
OUT_SF = {"name": "Star SF", "position": "SF"}
OUT_G  = {"name": "Star G",  "position": "G"}   # composite label from RotoWire
OUT_F  = {"name": "Star F",  "position": "F"}   # composite label from RotoWire

def test_position_compat_pg_candidate_matches_pg_out():
    result = _position_compatible("PG", [OUT_PG])
    assert result == [OUT_PG]

def test_position_compat_pg_candidate_matches_g_out():
    # G (composite guard) out — PG candidate qualifies
    result = _position_compatible("PG", [OUT_G])
    assert result == [OUT_G]

def test_position_compat_pg_candidate_no_match_for_c_out():
    result = _position_compatible("PG", [OUT_C])
    assert result == []

def test_position_compat_c_candidate_matches_pf_out():
    out_pf = {"name": "Star PF", "position": "PF"}
    result = _position_compatible("C", [out_pf])
    assert result == [out_pf]

def test_position_compat_c_candidate_no_match_for_sf_out():
    result = _position_compatible("C", [OUT_SF])
    assert result == []

def test_position_compat_f_candidate_no_match_for_c_out():
    # F (wing/stretch-four) does NOT cover a C out — intentional asymmetry
    result = _position_compatible("F", [OUT_C])
    assert result == []

def test_position_compat_pf_candidate_matches_c_out():
    # PF covers a C out (true bigs overlap)
    result = _position_compatible("PF", [OUT_C])
    assert result == [OUT_C]

def test_position_compat_multiple_out_returns_only_matches():
    # PG out and C out — SG candidate matches PG but not C
    out_c  = {"name": "Star C",  "position": "C"}
    out_pg = {"name": "Star PG", "position": "PG"}
    result = _position_compatible("SG", [out_c, out_pg])
    assert result == [out_pg]

def test_position_compat_unknown_candidate_position_returns_empty():
    result = _position_compatible("UNKNOWN", [OUT_PG])
    assert result == []

def test_position_compat_missing_position_key_returns_empty():
    # out player dict with no "position" key — must not raise
    out_no_pos = {"name": "Mystery Player"}
    result = _position_compatible("PG", [out_no_pos])
    assert result == []

def test_position_compat_composite_f_out_matches_sf_candidate():
    # "F" as an out-starter label — SF candidate should qualify
    result = _position_compatible("SF", [OUT_F])
    assert result == [OUT_F]

def test_position_compat_composite_f_out_no_match_for_c_candidate():
    result = _position_compatible("C", [OUT_F])
    assert result == []

def test_position_compat_g_candidate_matches_sg_out():
    # G (composite guard candidate) covers SG out
    out_sg = {"name": "Star SG", "position": "SG"}
    result = _position_compatible("G", [out_sg])
    assert result == [out_sg]
```

- [ ] **Step 2: Run to confirm failure (function not yet defined)**

```bash
cd "C:/Users/ferna/OneDrive/Área de Trabalho/projeto-nba"
pytest tests/test_engine.py::test_position_compat_pg_candidate_matches_pg_out -v
```

Expected: `ImportError` or `AttributeError: module 'analysis.engine' has no attribute '_position_compatible'`

---

### Task 2: Add `POSITION_COMPAT` and `_position_compatible` to `engine.py`

**Files:**
- Modify: `analysis/engine.py:18-26` (after `POSITION_MAP`), `analysis/engine.py:95` (after `_best_dvp_rank`)

- [ ] **Step 3: Add `POSITION_COMPAT` constant directly after `POSITION_MAP` (line 26)**

Insert after the closing `}` of `POSITION_MAP`:

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

- [ ] **Step 4: Add `_position_compatible` helper after `_best_dvp_rank` (after line 95)**

Insert before `def _score_player(`:

```python
def _position_compatible(candidate_pos, out_starters):
    """
    Returns the subset of out_starters that this candidate can replace.

    Looks up candidate_pos in POSITION_COMPAT to get the set of out-starter
    positions this candidate covers, then filters out_starters to those whose
    position falls in that set.
    """
    allowed = POSITION_COMPAT.get(candidate_pos, set())
    return [s for s in out_starters if s.get("position", "") in allowed]
```

Note: uses `s.get("position", "")` defensively so dict entries without a `position` key (e.g. malformed data) return an empty string, which is not in any `allowed` set, and the candidate is safely skipped.

- [ ] **Step 5: Run the new tests — all must pass**

```bash
pytest tests/test_engine.py -k "position_compat" -v
```

Expected: 12 tests PASSED

- [ ] **Step 6: Run full test suite — no regressions**

```bash
pytest tests/test_engine.py -v
```

Expected: all previously passing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add analysis/engine.py tests/test_engine.py
git commit -m "feat: add POSITION_COMPAT constant and _position_compatible helper"
```

---

## Chunk 2: Wire the position gate into `run_analysis`

### Task 3: Tests for position gate behaviour in `run_analysis`

**Files:**
- Modify: `tests/test_engine.py`

The existing `test_run_analysis_wiring_no_type_error` (line 238) uses an outdated fixture where `out` is a list of strings and patches `get_player_season_stats` (which no longer exists in the engine). These tests are superseded by the new wiring tests below. Leave the existing test in place — it will continue to verify the function does not crash.

- [ ] **Step 8: Add position-gate wiring tests after the existing wiring test**

```python
# ---------------------------------------------------------------------------
# run_analysis — position gate wiring
# ---------------------------------------------------------------------------

def _make_games():
    return [{
        "game_id": "001",
        "home_team": "TeamA", "home_team_id": 1, "home_tricode": "HME",
        "away_team": "TeamB", "away_team_id": 2, "away_tricode": "AWY",
    }]


def _patch_run_analysis(season_minutes, out_players, candidate_name="Bench Player", candidate_pos="PG"):
    """
    Returns (games, lineups, dvp) and the patches needed to test run_analysis
    without real NBA API calls.

    season_minutes: dict mapping player_id → avg minutes
    out_players:    list of dicts [{name, position}] placed in HME's out list
    """
    games = _make_games()
    lineups = {
        "HME": {
            "team_name": "TeamA",
            "starters": [{"name": candidate_name, "position": candidate_pos}],
            "out": out_players,
        },
        "AWY": {"team_name": "TeamB", "starters": [], "out": []},
    }
    dvp = {"PG": {"TeamB": {"rank": 2, "pts": 28.0}}}
    return games, lineups, dvp


def test_run_analysis_position_gate_compatible_starter_out_yields_candidate():
    """
    When the out starter's position is compatible with the candidate's position,
    the candidate is not skipped by the position gate and can reach scoring.
    (With a good DvP, recent stats, and no zone data the player may not score
     high enough to appear in results — we just verify no crash and the gate
     allows the candidate through. An empty result is acceptable here.)
    """
    # PG out, PG candidate — positions match
    out_players = [{"name": "Star PG", "position": "PG"}]
    games, lineups, dvp = _patch_run_analysis(
        season_minutes={9999: 20.0, 8888: 30.0},
        out_players=out_players,
        candidate_name="Bench PG",
        candidate_pos="PG",
    )
    with patch("analysis.engine.get_all_teams_defense_zones", return_value={}), \
         patch("analysis.engine.get_player_season_minutes", return_value={9999: 20.0, 8888: 30.0}), \
         patch("analysis.engine._find_player_id", side_effect=lambda name: 8888 if "Star" in name else 9999), \
         patch("analysis.engine.get_player_recent_stats", return_value={"pts": 15.0, "season_avg_pts": 10.0, "min": 22.0, "games": 15}), \
         patch("analysis.engine.get_player_shot_zones", return_value={}):
        result = run_analysis(games, lineups, dvp)
    # Gate did not crash and did not wrongly exclude a compatible candidate
    assert isinstance(result, list)
    # With rank-1 DVP and recent pts above season avg, the candidate should score >= 4
    assert len(result) > 0, "Compatible PG candidate with elite DVP should not be excluded by position gate"


def test_run_analysis_position_gate_incompatible_starter_out_excludes_candidate():
    """
    When the only out starter is a C and the candidate is a PG,
    the position gate must exclude the candidate — result is empty.
    """
    out_players = [{"name": "Star C", "position": "C"}]
    games, lineups, dvp = _patch_run_analysis(
        season_minutes={9999: 20.0, 8888: 30.0},
        out_players=out_players,
        candidate_name="Bench PG",
        candidate_pos="PG",
    )
    with patch("analysis.engine.get_all_teams_defense_zones", return_value={}), \
         patch("analysis.engine.get_player_season_minutes", return_value={9999: 20.0, 8888: 30.0}), \
         patch("analysis.engine._find_player_id", side_effect=lambda name: 8888 if "Star" in name else 9999), \
         patch("analysis.engine.get_player_recent_stats", return_value={"pts": 15.0, "season_avg_pts": 10.0, "min": 22.0, "games": 15}), \
         patch("analysis.engine.get_player_shot_zones", return_value={}):
        result = run_analysis(games, lineups, dvp)
    assert result == []  # PG cannot replace a C — must be excluded


def test_run_analysis_replaces_field_contains_only_matched_starters():
    """
    When two starters are out (PG and C) and the candidate is an SG,
    the replaces field must only list the PG (the compatible one), not the C.
    """
    out_players = [
        {"name": "Star PG", "position": "PG"},
        {"name": "Star C",  "position": "C"},
    ]
    games, lineups, dvp = _patch_run_analysis(
        season_minutes={9999: 20.0, 7777: 30.0, 8888: 30.0},
        out_players=out_players,
        candidate_name="Bench SG",
        candidate_pos="SG",
    )
    # Use a DVP that will produce a rating so the candidate appears in results
    dvp = {"SG": {"TeamB": {"rank": 1, "pts": 30.0}}}

    with patch("analysis.engine.get_all_teams_defense_zones", return_value={}), \
         patch("analysis.engine.get_player_season_minutes", return_value={9999: 20.0, 7777: 30.0, 8888: 30.0}), \
         patch("analysis.engine._find_player_id", side_effect=lambda name: {
             "Star PG": 7777, "Star C": 8888
         }.get(name, 9999)), \
         patch("analysis.engine.get_player_recent_stats", return_value={
             "pts": 20.0, "season_avg_pts": 10.0, "min": 28.0, "games": 15
         }), \
         patch("analysis.engine.get_player_shot_zones", return_value={}):
        result = run_analysis(games, lineups, dvp)

    assert result, "Expected non-empty result: SG candidate with rank-1 DVP vs TeamB should score >= 4 (VERY FAVORABLE)"
    assert result[0]["replaces"] == ["Star PG"]
    assert "Star C" not in result[0]["replaces"]
```

- [ ] **Step 9: Run to confirm failure**

```bash
pytest tests/test_engine.py::test_run_analysis_position_gate_incompatible_starter_out_excludes_candidate -v
```

Expected: FAIL — the test expects `[]` but the current engine has no position gate, so the candidate is not excluded.

---

### Task 4: Apply the three wiring changes to `run_analysis`

**Files:**
- Modify: `analysis/engine.py`

Three surgical edits in `run_analysis`:

**Edit A — `out_starters` stores dicts (line 211)**

Change:
```python
out_starters.append(p["name"])
```
To:
```python
out_starters.append({"name": p["name"], "position": p.get("position", "")})
```

**Edit B — Position gate after `min_avg >= STARTER_MIN_THRESHOLD` check (after line 236)**

Insert immediately after the `if min_avg >= STARTER_MIN_THRESHOLD: continue` block:

```python
                # --- Position gate: candidate must cover at least one out starter ---
                matched_starters = _position_compatible(position, out_starters)
                if not matched_starters:
                    print(f"  [skip] {player_name} - no position-compatible starter out ({position})")
                    continue
```

**Edit C — `replaces` field narrowed (line 268)**

Change:
```python
"replaces": out_starters,
```
To:
```python
"replaces": [s["name"] for s in matched_starters],
```

- [ ] **Step 10: Run the new wiring tests — all must pass**

```bash
pytest tests/test_engine.py -k "position_gate or replaces_field" -v
```

Expected: 3 tests PASSED

- [ ] **Step 11: Run full test suite — no regressions**

```bash
pytest tests/test_engine.py -v
```

Expected: all tests pass.

- [ ] **Step 12: Commit**

```bash
git add analysis/engine.py tests/test_engine.py
git commit -m "feat: gate candidates by position compatibility with out starter"
```

---

## Done

All 5 spec changes are now implemented and test-covered:

| Spec item | Implemented in |
|---|---|
| `POSITION_COMPAT` constant | Task 2, Step 3 |
| `_position_compatible` helper | Task 2, Step 4 |
| `out_starters` stores dicts | Task 4, Edit A |
| Position gate in candidate loop | Task 4, Edit B |
| `replaces` field narrowed | Task 4, Edit C |
