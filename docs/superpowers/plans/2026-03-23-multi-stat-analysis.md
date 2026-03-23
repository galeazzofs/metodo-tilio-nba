# Multi-Stat Player Analysis Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the PTS-only analysis engine to score players across PTS, AST, REB, and 3PT with per-stat scoring pipelines, dedup, and 4-section UI.

**Architecture:** 4 independent scoring passes (one per stat) with adapted signals. NBA API provides DvP for AST/REB/3PT; FantasyPros kept for PTS. Shared pipeline extracted from duplicated code in `app.py` and `scheduler.py`. Frontend renders 4 stat sections with no player duplication.

**Tech Stack:** Python 3 / FastAPI / nba_api / BeautifulSoup / Firebase Firestore / Telegram Bot API / Vanilla JS

**Spec:** `docs/superpowers/specs/2026-03-23-multi-stat-analysis-design.md`

---

## Important Implementation Notes

**Key naming:** The existing engine uses `"player"` as the dict key for player name. All new code must use `"player_name"` consistently. When refactoring `run_analysis()` (Task 8), rename the key from `"player"` to `"player_name"` and add `"player_id"`.

**Scoring return format:** All scoring functions (existing and new) must return structured data with BOTH:
- `signals` dict: numeric breakdown (e.g., `{"dvp": 3, "recent_form": 1, "third_signal": 2}`)
- `context` dict: `{"starter_out": "Name", "dvp_rank": N, "signal_descriptions": ["...", "..."]}`

**Test pattern:** All scraper tests must use `unittest.mock.patch` to mock NBA API calls (matching existing pattern in `tests/test_scrapers_nba.py`). No live API calls in tests.

**Date handling:** Always use BRT for date strings: `datetime.now(BRT).date().isoformat()` (matching existing pattern).

---

## File Structure

| File | Responsibility | Action |
|------|---------------|--------|
| `scrapers/nba.py` | NBA API data fetching | Modify: add `get_team_defense_vs_position()`, `get_team_defense_tracking()`, extend `get_player_recent_stats()` |
| `scrapers/odds.py` | Betting line fetching | Modify: extend `get_player_lines()` for 4 markets |
| `analysis/engine.py` | Scoring logic | Modify: add 3 scoring functions, dedup, refactor `run_analysis()` |
| `analysis/pipeline.py` | Shared analysis pipeline | **Create**: extract from `app.py` + `scheduler.py` |
| `app.py` | FastAPI server | Modify: use shared pipeline |
| `scheduler.py` | APScheduler orchestration | Modify: use shared pipeline, update Firestore save |
| `scrapers/telegram.py` | Telegram notifications | Modify: 4-section format, message splitting |
| `static/analise.js` | Frontend analysis tab | Modify: 4-section rendering, history backward compat |
| `static/index.html` | HTML structure | Modify: section containers |
| `output/formatter.py` | Plain text output | Modify: 4-stat format |
| `routers/analyses.py` | History API | Modify: backward compat for new structure |
| `tests/test_engine.py` | Engine tests | Modify: add tests for new scoring, dedup |
| `tests/test_scrapers_nba.py` | NBA scraper tests | Modify: add mocked tests for new functions |

---

## Chunk 1: NBA API — Team Defense by Position

### Task 1: Extend `get_player_recent_stats()` to return all box score stats

**Files:**
- Modify: `scrapers/nba.py:259-284`
- Test: `tests/test_scrapers_nba.py`

The existing function only parses PTS, REB, AST, MIN from `PlayerGameLog`. It already fetches all columns — we just need to parse more fields and add season averages for each.

- [ ] **Step 1: Write failing test for extended stats (mocked)**

```python
# tests/test_scrapers_nba.py — add to existing file
from unittest.mock import patch, MagicMock
import pandas as pd

@patch("scrapers.nba.playergamelog.PlayerGameLog")
def test_get_player_recent_stats_returns_all_fields(mock_gamelog):
    """Extended stats should include ast, reb, three_pm with season averages."""
    # Build fake game log DataFrame with 10 games
    fake_data = pd.DataFrame({
        "PTS": [20, 22, 18, 25, 19, 21, 23, 17, 24, 20],
        "REB": [5, 6, 4, 7, 5, 6, 8, 3, 5, 6],
        "AST": [8, 7, 9, 6, 10, 7, 8, 5, 9, 7],
        "MIN": [32, 30, 34, 28, 36, 31, 33, 29, 35, 30],
        "FG3M": [3, 2, 4, 1, 3, 2, 5, 1, 3, 2],
        "FG3A": [7, 5, 8, 4, 7, 6, 9, 3, 8, 5],
    })
    mock_instance = MagicMock()
    mock_instance.get_data_frames.return_value = [fake_data]
    mock_gamelog.return_value = mock_instance

    from scrapers.nba import get_player_recent_stats
    stats = get_player_recent_stats(2544, last_n_games=5)
    assert stats is not None
    # Existing fields
    assert "pts" in stats
    assert "reb" in stats
    assert "ast" in stats
    assert "min" in stats
    assert "season_avg_pts" in stats
    # New fields
    assert "season_avg_ast" in stats
    assert "season_avg_reb" in stats
    assert "three_pm" in stats
    assert "season_avg_three_pm" in stats
    assert "three_pa" in stats
    assert "season_avg_three_pa" in stats  # needed for 3PT scoring
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scrapers_nba.py::test_get_player_recent_stats_returns_all_fields -v`
Expected: FAIL with KeyError on "season_avg_ast"

- [ ] **Step 3: Extend `get_player_recent_stats` in `scrapers/nba.py`**

In `scrapers/nba.py`, modify the `get_player_recent_stats()` function (around line 259). The `PlayerGameLog` endpoint already returns `FG3M`, `FG3A`, `REB`, `AST` columns — we just need to parse them and compute season averages.

Add to the return dict (around lines 275-284):
- `season_avg_ast` = `round(df["AST"].mean(), 1)`
- `season_avg_reb` = `round(df["REB"].mean(), 1)`
- `season_avg_three_pm` = `round(df["FG3M"].mean(), 1)`
- `season_avg_three_pa` = `round(df["FG3A"].mean(), 1)`
- `three_pm` = `round(recent["FG3M"].mean(), 1)`
- `three_pa` = `round(recent["FG3A"].mean(), 1)`

Follow the same pattern already used for `season_avg_pts` and recent `pts`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scrapers_nba.py::test_get_player_recent_stats_returns_all_fields -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/nba.py tests/test_scrapers_nba.py
git commit -m "feat: extend get_player_recent_stats with AST/REB/3PM season averages"
```

---

### Task 2: Add `get_team_defense_vs_position()`

**Files:**
- Modify: `scrapers/nba.py`
- Test: `tests/test_scrapers_nba.py`

Fetches how much each team concedes per position (PG/SG/SF/PF/C). Makes 5 API calls (one per position). Returns AST, REB, 3PM, and 3PA allowed — plus ranks for each.

- [ ] **Step 1: Write failing test (mocked)**

```python
@patch("scrapers.nba._retry")
def test_get_team_defense_vs_position_structure(mock_retry):
    """Should return nested dict with ranks: {team_id: {position: {ast, reb, three_pm, three_pa, rank_*}}}."""
    # Build fake response for one position — 3 teams
    fake_df = pd.DataFrame({
        "TEAM_ID": [1, 2, 3],
        "AST": [25.0, 20.0, 30.0],
        "REB": [45.0, 50.0, 40.0],
        "FG3M": [12.0, 10.0, 14.0],
        "FG3A": [35.0, 30.0, 38.0],
    })
    mock_endpoint = MagicMock()
    mock_endpoint.get_data_frames.return_value = [fake_df]
    mock_retry.return_value = mock_endpoint

    from scrapers.nba import get_team_defense_vs_position
    result = get_team_defense_vs_position(last_n_games=15)
    assert isinstance(result, dict)
    assert 1 in result
    assert "PG" in result[1]
    pg = result[1]["PG"]
    assert "ast" in pg
    assert "reb" in pg
    assert "three_pm" in pg
    assert "three_pa" in pg
    assert "rank_ast" in pg
    assert "rank_reb" in pg
    assert "rank_three_pm" in pg
    assert "rank_three_pa" in pg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scrapers_nba.py::test_get_team_defense_vs_position_structure -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement `get_team_defense_vs_position` in `scrapers/nba.py`**

Add after `get_player_season_data()`. For each position:
1. Call `leaguedashplayerstats.LeagueDashPlayerStats(per_mode_detailed="PerGame", season=SEASON, last_n_games=last_n_games, player_position_nullable=position, measure_type_detailed_defense="Opponent")` via `_retry()`.
2. Sleep `DELAY`.
3. Parse: extract `TEAM_ID`, `AST`, `REB`, `FG3M`, `FG3A` per team.
4. Compute ranks for each stat (rank 1 = highest value = worst defense = best matchup).
5. Build nested dict: `{team_id: {pos: {ast, reb, three_pm, three_pa, rank_ast, rank_reb, rank_three_pm, rank_three_pa}}}`

If `player_or_team_abbreviation="T"` works with position filter (team mode), use it for simpler 1-row-per-team parsing. Otherwise aggregate player rows by team.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scrapers_nba.py::test_get_team_defense_vs_position_structure -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/nba.py tests/test_scrapers_nba.py
git commit -m "feat: add get_team_defense_vs_position for AST/REB/3PT DvP with ranks"
```

---

### Task 3: Add `get_team_defense_tracking()`

**Files:**
- Modify: `scrapers/nba.py`
- Test: `tests/test_scrapers_nba.py`

Fetches tracking stats: potential AST, REB chances. Falls back gracefully if endpoints unavailable.

- [ ] **Step 1: Write failing test (mocked)**

```python
@patch("scrapers.nba._retry")
def test_get_team_defense_tracking_structure(mock_retry):
    """Should return dict with tracking stats and ranks per team."""
    fake_df = pd.DataFrame({
        "TEAM_ID": [1, 2, 3],
        "POTENTIAL_AST": [30.0, 25.0, 35.0],
        "REB_CHANCES": [55.0, 50.0, 60.0],
    })
    mock_endpoint = MagicMock()
    mock_endpoint.get_data_frames.return_value = [fake_df]
    mock_retry.return_value = mock_endpoint

    from scrapers.nba import get_team_defense_tracking
    result = get_team_defense_tracking(last_n_games=15)
    assert isinstance(result, dict)
    team_data = result[1]
    assert "potential_ast" in team_data
    assert "reb_chances" in team_data
    assert "rank_potential_ast" in team_data
    assert "rank_reb_chances" in team_data

@patch("scrapers.nba._retry")
def test_get_team_defense_tracking_fallback_on_error(mock_retry):
    """Should return None when tracking endpoints fail."""
    mock_retry.side_effect = Exception("API unavailable")
    from scrapers.nba import get_team_defense_tracking
    result = get_team_defense_tracking(last_n_games=15)
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scrapers_nba.py -k "tracking" -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement `get_team_defense_tracking`**

Add in `scrapers/nba.py`. Import `leaguedashptstats` at the top of the file.

1. Try `leaguedashptstats` with `player_or_team="Team"`, `pt_measure_type="Passing"` for potential assists.
2. Try `leaguedashptstats` with `pt_measure_type="Rebounding"` for REB_CHANCES.
3. Compute ranks for each.
4. Wrap everything in try/except — return `None` on failure (scoring engine handles `None` with fallbacks).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scrapers_nba.py -k "tracking" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/nba.py tests/test_scrapers_nba.py
git commit -m "feat: add get_team_defense_tracking for potential AST/REB chances"
```

---

## Chunk 2: Scoring Engine — New Stat Scoring Functions

### Task 4: Add `_score_player_ast()` scoring function

**Files:**
- Modify: `analysis/engine.py`
- Modify: `tests/test_engine.py`

All new scoring functions return `(score, rating, signals_dict, context_dict)` where:
- `signals_dict` = `{"dvp": 3, "recent_form": 1, "potential_ast": 2}` (numeric)
- `context_dict` = `{"dvp_rank": N, "signal_descriptions": ["...", "..."]}` (human-readable)

- [ ] **Step 1: Write failing tests for AST scoring**

```python
# tests/test_engine.py

def test_ast_gate_dvp_rank_above_6_discards():
    """AST: opponent not in top 6 AST allowed → discard."""
    from analysis.engine import _score_player_ast
    team_def = {"PG": {"ast": 5.0, "rank_ast": 10}}
    recent = {"ast": 8.0, "season_avg_ast": 7.0}
    tracking = {"rank_potential_ast": 3}
    score, rating, signals, context = _score_player_ast("PG", "BOS", team_def, recent, tracking, True)
    assert score == 0
    assert rating is None

def test_ast_full_score_best_of_night():
    """AST: DvP top 6 (+3) + form (+1) + potential AST top 6 (+2) = 6."""
    from analysis.engine import _score_player_ast
    team_def = {"PG": {"ast": 10.0, "rank_ast": 2}}
    recent = {"ast": 9.0, "season_avg_ast": 7.5}
    tracking = {"rank_potential_ast": 4}
    score, rating, signals, context = _score_player_ast("PG", "BOS", team_def, recent, tracking, True)
    assert score == 6
    assert rating == "BEST OF THE NIGHT"
    assert signals["dvp"] == 3
    assert signals["recent_form"] == 1
    assert signals["potential_ast"] == 2
    assert "signal_descriptions" in context

def test_ast_fallback_when_tracking_unavailable():
    """AST: tracking=None → fallback uses rank_ast top 3 for +2."""
    from analysis.engine import _score_player_ast
    team_def = {"PG": {"ast": 10.0, "rank_ast": 2}}
    recent = {"ast": 9.0, "season_avg_ast": 7.5}
    score, rating, signals, context = _score_player_ast("PG", "BOS", team_def, recent, None, True)
    assert score == 6  # DvP +3, form +1, fallback rank_ast=2 <=3 → +2

def test_ast_fallback_rank_4_no_bonus():
    """AST: tracking=None, rank_ast=4 (not top 3) → no +2 bonus."""
    from analysis.engine import _score_player_ast
    team_def = {"PG": {"ast": 8.0, "rank_ast": 4}}
    recent = {"ast": 9.0, "season_avg_ast": 7.5}
    score, rating, signals, context = _score_player_ast("PG", "BOS", team_def, recent, None, True)
    assert score == 4  # DvP +3, form +1, no bonus
    assert rating == "VERY FAVORABLE"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -k "ast" -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement `_score_player_ast()` in `analysis/engine.py`**

Add after `_score_player()` (after line 305):

```python
def _score_player_ast(position, opponent_name, team_defense, recent_stats, tracking_data, is_stepping_up):
    """Score a player for AST opportunity (0-6). Returns (score, rating, signals, context)."""
    signals = {"dvp": 0, "recent_form": 0, "potential_ast": 0}
    descriptions = []

    if not is_stepping_up:
        return 0, None, signals, {}

    pos_def = team_defense.get(position)
    if not pos_def or pos_def.get("rank_ast", 99) > 6:
        return 0, None, signals, {}

    dvp_rank = pos_def["rank_ast"]
    signals["dvp"] = 3
    descriptions.append(f"AST cedidas à posição — top {dvp_rank} vs {opponent_name}")

    if recent_stats and recent_stats.get("ast", 0) >= recent_stats.get("season_avg_ast", 999):
        signals["recent_form"] = 1
        descriptions.append(f"Forma recente acima da média ({recent_stats['ast']} ast vs {recent_stats['season_avg_ast']} avg)")

    # Signal 3: Potential AST
    if tracking_data and tracking_data.get("rank_potential_ast", 99) <= 6:
        signals["potential_ast"] = 2
        descriptions.append(f"Potential AST cedidas — top {tracking_data['rank_potential_ast']}")
    elif not tracking_data and dvp_rank <= 3:
        # Fallback: stricter threshold when tracking unavailable
        signals["potential_ast"] = 2
        descriptions.append(f"AST cedidas — top {dvp_rank} (fallback)")

    score = sum(signals.values())
    rating = "BEST OF THE NIGHT" if score >= 6 else "VERY FAVORABLE" if score >= 4 else None
    context = {"dvp_rank": dvp_rank, "signal_descriptions": descriptions}
    return score, rating, signals, context
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -k "ast" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add analysis/engine.py tests/test_engine.py
git commit -m "feat: add _score_player_ast scoring function"
```

---

### Task 5: Add `_score_player_reb()` scoring function

**Files:**
- Modify: `analysis/engine.py`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Write failing tests for REB scoring**

```python
def test_reb_gate_dvp_rank_above_6_discards():
    from analysis.engine import _score_player_reb
    team_def = {"C": {"reb": 8.0, "rank_reb": 10}}
    recent = {"reb": 10.0, "season_avg_reb": 9.0}
    tracking = {"rank_reb_chances": 3}
    score, rating, signals, ctx = _score_player_reb("C", "ORL", team_def, recent, tracking, True)
    assert score == 0

def test_reb_full_score_best_of_night():
    from analysis.engine import _score_player_reb
    team_def = {"C": {"reb": 12.0, "rank_reb": 1}}
    recent = {"reb": 11.0, "season_avg_reb": 9.5}
    tracking = {"rank_reb_chances": 2}
    score, rating, signals, ctx = _score_player_reb("C", "ORL", team_def, recent, tracking, True)
    assert score == 6
    assert rating == "BEST OF THE NIGHT"
    assert signals == {"dvp": 3, "recent_form": 1, "reb_opportunity": 2}

def test_reb_fallback_when_tracking_unavailable():
    from analysis.engine import _score_player_reb
    team_def = {"C": {"reb": 12.0, "rank_reb": 2}}
    recent = {"reb": 11.0, "season_avg_reb": 9.5}
    score, rating, signals, ctx = _score_player_reb("C", "ORL", team_def, recent, None, True)
    assert score == 6  # rank_reb=2 top 3 fallback → +2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -k "reb" -v`
Expected: FAIL

- [ ] **Step 3: Implement `_score_player_reb()`**

Same pattern as `_score_player_ast`. Signal 3 uses `rank_reb_chances` from tracking (top 6 → +2), fallback uses `rank_reb` <= 3.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -k "reb" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add analysis/engine.py tests/test_engine.py
git commit -m "feat: add _score_player_reb scoring function"
```

---

### Task 6: Add `_score_player_3pt()` scoring function

**Files:**
- Modify: `analysis/engine.py`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Write failing tests for 3PT scoring**

```python
def test_3pt_gate_dvp_rank_above_6_discards():
    from analysis.engine import _score_player_3pt
    team_def = {"SG": {"three_pm": 2.0, "rank_three_pm": 10, "three_pa": 5.0, "rank_three_pa": 8}}
    recent = {"three_pm": 2.5, "season_avg_three_pm": 2.0, "three_pa": 6.0, "season_avg_three_pa": 5.5}
    score, rating, signals, ctx = _score_player_3pt("SG", "SAC", team_def, recent, None, True)
    assert score == 0

def test_3pt_full_score_best_of_night():
    from analysis.engine import _score_player_3pt
    team_def = {"SG": {"three_pm": 3.5, "rank_three_pm": 2, "three_pa": 8.0, "rank_three_pa": 3}}
    recent = {"three_pm": 3.0, "season_avg_three_pm": 2.5, "three_pa": 7.0, "season_avg_three_pa": 6.0}
    score, rating, signals, ctx = _score_player_3pt("SG", "SAC", team_def, recent, None, True)
    assert score == 6
    assert rating == "BEST OF THE NIGHT"
    # DvP +3, form +1, fallback: three_pa vol up + rank_three_pa=3 <=3 → +2

def test_3pt_no_volume_no_bonus():
    """3PA below season avg → no 3rd signal bonus even if rank is good."""
    from analysis.engine import _score_player_3pt
    team_def = {"SG": {"three_pm": 3.5, "rank_three_pm": 2, "three_pa": 8.0, "rank_three_pa": 1}}
    recent = {"three_pm": 3.0, "season_avg_three_pm": 2.5, "three_pa": 4.0, "season_avg_three_pa": 6.0}
    score, rating, signals, ctx = _score_player_3pt("SG", "SAC", team_def, recent, None, True)
    assert signals["potential_3pt"] == 0  # volume is DOWN, no bonus
    assert score == 4  # DvP +3, form +1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -k "3pt" -v`
Expected: FAIL

- [ ] **Step 3: Implement `_score_player_3pt()`**

Signal 3 logic: Player's recent `three_pa` >= `season_avg_three_pa` (volume is up) AND opponent's `rank_three_pa` <= 6 → +2. Fallback (stricter): both conditions AND `rank_three_pa` <= 3.

**Note:** `team_defense` already includes `three_pa` and `rank_three_pa` from Task 2.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -k "3pt" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add analysis/engine.py tests/test_engine.py
git commit -m "feat: add _score_player_3pt scoring function"
```

---

### Task 7: Add dedup logic

**Files:**
- Modify: `analysis/engine.py`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Write failing tests for dedup**

```python
def test_dedup_keeps_highest_score():
    from analysis.engine import _dedup_candidates
    candidates = {
        "pts": [{"player_name": "Player A", "game": "G1", "score": 5}],
        "ast": [{"player_name": "Player A", "game": "G1", "score": 6}],
        "reb": [], "three_pt": [],
    }
    result = _dedup_candidates(candidates)
    assert len(result["pts"]) == 0
    assert len(result["ast"]) == 1

def test_dedup_tiebreaker_pts_over_ast():
    from analysis.engine import _dedup_candidates
    candidates = {
        "pts": [{"player_name": "Player A", "game": "G1", "score": 5}],
        "ast": [{"player_name": "Player A", "game": "G1", "score": 5}],
        "reb": [], "three_pt": [],
    }
    result = _dedup_candidates(candidates)
    assert len(result["pts"]) == 1
    assert len(result["ast"]) == 0

def test_dedup_max_one_per_game_per_stat():
    from analysis.engine import _dedup_candidates
    candidates = {
        "pts": [
            {"player_name": "A", "game": "G1", "score": 6},
            {"player_name": "B", "game": "G1", "score": 5},
        ],
        "ast": [], "reb": [], "three_pt": [],
    }
    result = _dedup_candidates(candidates)
    assert len(result["pts"]) == 1
    assert result["pts"][0]["player_name"] == "A"

def test_dedup_max_five_per_stat():
    from analysis.engine import _dedup_candidates
    candidates = {
        "pts": [{"player_name": f"P{i}", "game": f"G{i}", "score": 5} for i in range(8)],
        "ast": [], "reb": [], "three_pt": [],
    }
    result = _dedup_candidates(candidates)
    assert len(result["pts"]) == 5

def test_dedup_player_in_three_stats_keeps_best():
    from analysis.engine import _dedup_candidates
    candidates = {
        "pts": [{"player_name": "X", "game": "G1", "score": 4}],
        "ast": [{"player_name": "X", "game": "G1", "score": 5}],
        "reb": [{"player_name": "X", "game": "G1", "score": 6}],
        "three_pt": [],
    }
    result = _dedup_candidates(candidates)
    assert len(result["pts"]) == 0
    assert len(result["ast"]) == 0
    assert len(result["reb"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -k "dedup" -v`
Expected: FAIL

- [ ] **Step 3: Implement `_dedup_candidates()`**

```python
STAT_PRIORITY = {"pts": 0, "three_pt": 1, "ast": 2, "reb": 3}

def _dedup_candidates(candidates):
    """Dedup players across stats, then max 1/game, top 5 per stat."""
    # Step 1: Find best stat for each player
    player_best = {}
    for stat_key, entries in candidates.items():
        for entry in entries:
            name = entry["player_name"]
            score = entry["score"]
            priority = STAT_PRIORITY[stat_key]
            if name not in player_best:
                player_best[name] = (stat_key, score, priority)
            else:
                prev_stat, prev_score, prev_priority = player_best[name]
                if score > prev_score or (score == prev_score and priority < prev_priority):
                    player_best[name] = (stat_key, score, priority)

    # Step 2: Keep player only in their best stat
    deduped = {k: [] for k in candidates}
    for stat_key, entries in candidates.items():
        for entry in entries:
            if player_best[entry["player_name"]][0] == stat_key:
                deduped[stat_key].append(entry)

    # Step 3: Per stat — max 1 per game, top 5
    result = {}
    for stat_key, entries in deduped.items():
        entries.sort(key=lambda x: x["score"], reverse=True)
        seen_games = set()
        filtered = []
        for entry in entries:
            if entry["game"] not in seen_games:
                seen_games.add(entry["game"])
                filtered.append(entry)
        result[stat_key] = filtered[:5]
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -k "dedup" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add analysis/engine.py tests/test_engine.py
git commit -m "feat: add _dedup_candidates for multi-stat deduplication"
```

---

## Chunk 3: Odds API Extension + Refactor run_analysis + Extract Pipeline

### Task 8: Extend `get_player_lines()` for 4 markets

**Files:**
- Modify: `scrapers/odds.py:98-170`

This must be done BEFORE the pipeline extraction since the pipeline calls `get_player_lines` with the new structure.

- [ ] **Step 1: Update `get_player_lines()` signature and market request**

Change signature from `get_player_lines(candidates, event_ids)` to `get_player_lines(stats, event_ids)` where `stats` is the 4-key dict.

Change market request from `markets="player_points"` to `markets="player_points,player_assists,player_rebounds,player_threes"`.

Collect all unique player names across all stat categories and games:

```python
# Build set of (player_name, game_key) across all stats
all_candidates = []
for stat_key, entries in stats.items():
    for c in entries:
        all_candidates.append(c)
```

- [ ] **Step 2: Update market parsing to extract all 4 stat lines**

For each bookmaker outcome, map market key to stat:
- `player_points` → `"pts"`
- `player_assists` → `"ast"`
- `player_rebounds` → `"reb"`
- `player_threes` → `"three_pt"` (try `player_three_pointers` if `player_threes` returns no data)

Return: `{player_name: {"pts": val, "ast": val, "reb": val, "three_pt": val}}`

Also extract odds (the `price` field from outcomes) and include in the return value.

- [ ] **Step 3: Commit**

```bash
git add scrapers/odds.py
git commit -m "feat: extend get_player_lines for AST/REB/3PT markets"
```

---

### Task 9: Refactor `run_analysis()` to return 4-stat structure

**Files:**
- Modify: `analysis/engine.py`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Write failing test for new return structure**

```python
@patch("analysis.engine.get_player_season_data")
@patch("analysis.engine.get_all_teams_defense_zones")
@patch("analysis.engine.get_player_shot_zones")
@patch("analysis.engine.get_player_recent_stats")
def test_run_analysis_returns_stat_dict(mock_recent, mock_zones, mock_defense, mock_season):
    mock_defense.return_value = {}
    mock_season.return_value = ({}, set())
    mock_zones.return_value = {}
    mock_recent.return_value = None
    from analysis.engine import run_analysis
    result = run_analysis([], {}, {}, {}, None)
    assert isinstance(result, dict)
    assert set(result.keys()) == {"pts", "ast", "reb", "three_pt"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_engine.py::test_run_analysis_returns_stat_dict -v`
Expected: FAIL (returns list, wrong arg count)

- [ ] **Step 3: Refactor `run_analysis()`**

Update signature: `run_analysis(games, lineups, dvp, team_defense, tracking_data)`

Key changes inside the main loop:
1. Rename `"player"` key to `"player_name"` everywhere.
2. Add `"player_id"` from the roster data (already available).
3. Run 4 scoring passes per candidate, collect results in `candidates = {"pts": [], "ast": [], "reb": [], "three_pt": []}`.
4. For PTS: update `_score_player()` to also return `signals` dict and `context` dict (or wrap its return).
5. For AST/REB/3PT: use new scoring functions which already return the right format.
6. Each candidate dict now includes: `player_name, player_id, team, position, game, score, rating, signals, context, recent_stats, replaces`.
7. After loop: call `_dedup_candidates(candidates)` and return.

**Important:** Update ALL existing tests that call `run_analysis()` to pass 5 args and expect dict return.

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/test_engine.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add analysis/engine.py tests/test_engine.py
git commit -m "refactor: run_analysis returns 4-stat dict with player_id and structured signals"
```

---

### Task 10: Extract shared pipeline into `analysis/pipeline.py`

**Files:**
- Create: `analysis/pipeline.py`
- Create: `tests/test_pipeline.py`
- Modify: `app.py:67-141`
- Modify: `scheduler.py:184-263`

- [ ] **Step 1: Create `analysis/pipeline.py`**

```python
"""Shared analysis pipeline for manual and scheduled triggers."""
from scrapers.nba import (
    get_todays_games, get_team_defense_vs_position, get_team_defense_tracking,
)
from scrapers.rotowire import get_projected_lineups
from scrapers.fantasypros import get_defense_vs_position
from scrapers.odds import get_event_ids, get_player_lines
from analysis.engine import run_analysis


def run_pipeline(games=None):
    """
    Execute the full analysis pipeline.
    Returns (stats_dict, games_list) or (None, games) if no games.
    """
    if games is None:
        print("Buscando jogos de hoje...")
        games = get_todays_games()

    if not games:
        print("Nenhum jogo hoje.")
        return None, games

    print(f"  {len(games)} jogos esta noite")

    print("Buscando lineups projetados (RotoWire)...")
    lineups = get_projected_lineups()
    print(f"  {len(lineups)} times carregados")

    print("Buscando Defesa por Posição — PTS (FantasyPros)...")
    dvp = get_defense_vs_position()
    print("  Concluído")

    print("Buscando Defesa por Posição — AST/REB/3PT (NBA API)...")
    team_defense = get_team_defense_vs_position()
    print("  Concluído")

    print("Buscando tracking stats defensivos (NBA API)...")
    tracking_data = get_team_defense_tracking()
    print("  Concluído")

    print("Rodando análise (4 stats)...")
    stats = run_analysis(games, lineups, dvp, team_defense, tracking_data)
    total = sum(len(v) for v in stats.values())
    print(f"  {total} candidato(s) encontrado(s)")

    print("Buscando linhas de apostas (The Odds API)...")
    event_ids = get_event_ids(games)
    lines = get_player_lines(stats, event_ids)
    for stat_key, candidates in stats.items():
        line_key = stat_key  # pts/ast/reb/three_pt
        for c in candidates:
            player_lines = lines.get(c["player_name"], {})
            val = player_lines.get(line_key) if isinstance(player_lines, dict) else None
            c["line"] = {"value": val, "odds": player_lines.get(f"{line_key}_odds")} if val else None

    return stats, games
```

- [ ] **Step 2: Write test for pipeline (mocked)**

```python
# tests/test_pipeline.py
from unittest.mock import patch, MagicMock

@patch("analysis.pipeline.get_player_lines", return_value={})
@patch("analysis.pipeline.get_event_ids", return_value={})
@patch("analysis.pipeline.run_analysis", return_value={"pts": [], "ast": [], "reb": [], "three_pt": []})
@patch("analysis.pipeline.get_team_defense_tracking", return_value=None)
@patch("analysis.pipeline.get_team_defense_vs_position", return_value={})
@patch("analysis.pipeline.get_defense_vs_position", return_value={})
@patch("analysis.pipeline.get_projected_lineups", return_value={})
@patch("analysis.pipeline.get_todays_games", return_value=[{"game_id": "1"}])
def test_pipeline_calls_all_steps(mock_games, mock_lineups, mock_dvp, mock_td, mock_track, mock_engine, mock_events, mock_lines):
    from analysis.pipeline import run_pipeline
    stats, games = run_pipeline()
    assert stats is not None
    assert isinstance(stats, dict)
    mock_games.assert_called_once()
    mock_lineups.assert_called_once()
    mock_dvp.assert_called_once()
    mock_td.assert_called_once()
    mock_track.assert_called_once()
    mock_engine.assert_called_once()

@patch("analysis.pipeline.get_todays_games", return_value=[])
def test_pipeline_no_games_returns_none(mock_games):
    from analysis.pipeline import run_pipeline
    stats, games = run_pipeline()
    assert stats is None
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 4: Update `app.py` to use shared pipeline**

Replace `_run_analysis()` body to call `run_pipeline()`. Use `datetime.now(BRT).date().isoformat()` for date_str (import BRT from scrapers.nba).

- [ ] **Step 5: Update `scheduler.py` to use shared pipeline**

Replace `run_scheduled_analysis()` body to call `run_pipeline(games)`. Update `_save_analysis_to_firestore()` to save the new stats dict structure with `candidate_count` = sum of all stat arrays.

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add analysis/pipeline.py tests/test_pipeline.py app.py scheduler.py
git commit -m "refactor: extract shared pipeline, update app.py and scheduler.py"
```

---

## Chunk 4: Telegram 4-Section Format

### Task 11: Update Telegram notification for 4 stat sections

**Files:**
- Modify: `scrapers/telegram.py`
- Create: `tests/test_telegram.py`

- [ ] **Step 1: Rewrite `_format_message()` and `send_analysis()` for stats dict**

Add section config:
```python
STAT_SECTIONS = [
    ("pts", "📊 PONTOS (PTS)"),
    ("ast", "🎯 ASSISTÊNCIAS (AST)"),
    ("reb", "🏀 REBOTES (REB)"),
    ("three_pt", "💧 CESTAS DE 3 (3PT)"),
]
```

Rewrite `_format_message(stats, date_str, game_count)` to iterate sections, skip empty ones, format players with line info from `c["line"]["value"]` if available.

Extract `_send_message(token, chat_id, text)` helper from `send_analysis`.

Add message splitting: if formatted message > 4000 chars, send one message per section.

- [ ] **Step 2: Write tests for message formatting and splitting**

```python
# tests/test_telegram.py

def test_format_message_4_sections():
    from scrapers.telegram import _format_message
    stats = {
        "pts": [{"player_name": "A", "position": "PG", "team": "LAL", "game": "LAL@BOS",
                  "rating": "BEST OF THE NIGHT", "line": {"value": 22.5, "odds": -110},
                  "context": {"signal_descriptions": ["Signal 1", "Signal 2"]}}],
        "ast": [], "reb": [], "three_pt": [],
    }
    msg = _format_message(stats, "2026-03-23", 8)
    assert "PONTOS (PTS)" in msg
    assert "ASSISTÊNCIAS" not in msg  # empty section omitted
    assert "A" in msg

def test_format_message_empty_stats():
    from scrapers.telegram import _format_message
    stats = {"pts": [], "ast": [], "reb": [], "three_pt": []}
    msg = _format_message(stats, "2026-03-23", 8)
    assert "SCOUT" in msg
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_telegram.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add scrapers/telegram.py tests/test_telegram.py
git commit -m "feat: 4-section Telegram format with message splitting"
```

---

## Chunk 5: Frontend — 4 Stat Sections

### Task 12: Update result rendering in `analise.js`

**Files:**
- Modify: `static/analise.js`
- Modify: `static/index.html`

- [ ] **Step 1: Add stat section config and rewrite `renderResults()`**

Add `STAT_SECTIONS` config array. Rewrite `renderResults(data)` to:
- If `Array.isArray(data)`: call legacy renderer (move old code to `renderResultsLegacy`)
- If object: iterate STAT_SECTIONS, render each section with header + cards or empty message

- [ ] **Step 2: Update `buildCard()` for stat-specific content**

- Use `p.context.signal_descriptions` for signals (fall back to `p.signals` if array)
- Show `p.line.value` for the betting line
- Show `p.context.starter_out` or `p.replaces` for starter replaced
- Show relevant stat in the stat cells based on section key

- [ ] **Step 3: Add CSS for `.stat-section` and `.stat-section-title` in `index.html`**

- [ ] **Step 4: Commit**

```bash
git add static/analise.js static/index.html
git commit -m "feat: frontend 4-stat sections with backward compat"
```

---

### Task 13: Update history rendering for new format

**Files:**
- Modify: `static/analise.js`

- [ ] **Step 1: Update `buildHistEntry()` for both formats**

Detect format: `analysis.stats` (new) vs `analysis.results` (old). New format shows player chips grouped by stat section. Old format renders as before.

- [ ] **Step 2: Commit**

```bash
git add static/analise.js
git commit -m "feat: history handles both old and new Firestore formats"
```

---

## Chunk 6: Formatter, Router, Final Integration

### Task 14: Update `output/formatter.py` for 4 stats

**Files:**
- Modify: `output/formatter.py`

- [ ] **Step 1: Rewrite `format_results()` to accept stats dict**

Iterate `STAT_LABELS` dict, render each non-empty section with player details. Use `context.signal_descriptions` for signals.

- [ ] **Step 2: Commit**

```bash
git add output/formatter.py
git commit -m "feat: formatter outputs 4-stat sections"
```

---

### Task 15: Verify `routers/analyses.py` backward compatibility

**Files:**
- Read: `routers/analyses.py`

- [ ] **Step 1: Verify no changes needed**

The `list_analyses` query filters on `candidate_count > 0`. Since `_save_analysis_to_firestore` keeps `candidate_count`, the query works for both old and new documents. The `get_analysis` endpoint returns the raw doc dict — frontend handles format detection. No code changes needed.

- [ ] **Step 2: Commit (only if changes were needed)**

---

### Task 16: Full integration test

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest tests/ -v
```
Expected: ALL PASS

- [ ] **Step 2: Manual smoke test**

Start server: `python app.py`
Open `http://localhost:8000`. Verify:
- 4 stat sections render when analysis runs
- Empty sections show muted message
- History shows both old and new format entries
- Betting lines display correctly per stat

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete multi-stat analysis — PTS, AST, REB, 3PT"
```
