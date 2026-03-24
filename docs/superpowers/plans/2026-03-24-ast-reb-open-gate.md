# AST/REB Open Gate Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the starter injury gate for AST and REB, analyze all starters + bench >= 20min/g, add pace gate, and use graduated DvP scoring with threshold 5.

**Architecture:** Split `run_analysis` into two loops: (1) injury-gated loop for PTS/3PT (unchanged), (2) open loop for AST/REB that iterates all games, checks pace gate, and analyzes starters + qualifying bench players. Scoring functions lose the `is_stepping_up` gate and use graduated ranks instead of binary gates.

**Tech Stack:** Python, nba_api, pytest

---

## File Map

- **Modify:** `scrapers/nba.py` — add `get_team_pace()` function
- **Modify:** `analysis/engine.py` — update `_score_player_ast`, `_score_player_reb`, `run_analysis`
- **Modify:** `analysis/pipeline.py` — pass pace data to engine
- **Modify:** `tests/test_engine.py` — update AST/REB tests for new scoring, add pace gate tests
- **Create:** `tests/test_nba_pace.py` — test `get_team_pace()`

---

## Chunk 1: Pace Data Fetcher

### Task 1: Add `get_team_pace()` to nba.py

**Files:**
- Create: `tests/test_nba_pace.py`
- Modify: `scrapers/nba.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_nba_pace.py
from unittest.mock import patch, MagicMock
from scrapers.nba import get_team_pace


def test_get_team_pace_returns_dict_with_pace_and_median():
    """get_team_pace returns {team_id: pace} and league median."""
    fake_rows = [
        [1610612737, "Atlanta Hawks", 100.5],  # ATL
        [1610612738, "Boston Celtics", 98.2],   # BOS
        [1610612739, "Cleveland Cavaliers", 97.0],  # CLE
    ]
    fake_headers = ["TEAM_ID", "TEAM_NAME", "PACE"]

    mock_result = MagicMock()
    mock_result.get_dict.return_value = {
        "resultSets": [{"headers": fake_headers, "rowSet": fake_rows}]
    }

    with patch("scrapers.nba.leaguedashteamstats.LeagueDashTeamStats", return_value=mock_result):
        pace_map, median_pace = get_team_pace()

    assert pace_map[1610612737] == 100.5
    assert pace_map[1610612738] == 98.2
    assert pace_map[1610612739] == 97.0
    # median of [97.0, 98.2, 100.5] = 98.2
    assert median_pace == 98.2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_nba_pace.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_team_pace'`

- [ ] **Step 3: Implement `get_team_pace()`**

Add to `scrapers/nba.py` after `get_team_defense_tracking()` (after line ~390):

```python
def get_team_pace():
    """
    Fetch pace for all 30 teams.
    Returns (pace_map, median_pace):
      - pace_map: {team_id: pace_float}
      - median_pace: float (league median)
    """
    from nba_api.stats.endpoints import leaguedashteamstats
    import statistics

    time.sleep(DELAY)
    result = _retry(lambda: leaguedashteamstats.LeagueDashTeamStats(
        season=SEASON,
        per_mode_detailed="PerGame",
        measure_type_detailed_defense="Base",
    ))
    data = result.get_dict()
    rows = data["resultSets"][0]["rowSet"]
    headers = data["resultSets"][0]["headers"]

    team_id_idx = headers.index("TEAM_ID")
    pace_idx = headers.index("PACE")

    pace_map = {}
    all_paces = []
    for row in rows:
        tid = row[team_id_idx]
        pace = row[pace_idx]
        pace_map[tid] = pace
        all_paces.append(pace)

    median_pace = statistics.median(all_paces)
    return pace_map, median_pace
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_nba_pace.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/nba.py tests/test_nba_pace.py
git commit -m "feat: add get_team_pace() for pace gate data"
```

---

## Chunk 2: Update AST/REB Scoring Functions

### Task 2: Update `_score_player_ast` with graduated scoring and no gates

**Files:**
- Modify: `analysis/engine.py:308-366`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Write new tests for graduated AST scoring**

Add to `tests/test_engine.py` (replace existing AST tests):

```python
# --- AST graduated scoring tests ---

def test_ast_dvp_rank_1_scores_3():
    """DvP rank 1-2 gives 3 points."""
    team_defense = {"PG": {"rank_ast": 1}}
    recent = {"ast": 8, "season_avg_ast": 7}
    score, rating, signals, ctx = _score_player_ast(
        "PG", "OPP", team_defense, recent, None,
    )
    assert signals["dvp"] == 3


def test_ast_dvp_rank_4_scores_2():
    """DvP rank 3-6 gives 2 points."""
    team_defense = {"PG": {"rank_ast": 4}}
    recent = {"ast": 5, "season_avg_ast": 6}
    score, rating, signals, ctx = _score_player_ast(
        "PG", "OPP", team_defense, recent, None,
    )
    assert signals["dvp"] == 2


def test_ast_dvp_rank_7_scores_0():
    """DvP rank 7+ gives 0 points."""
    team_defense = {"PG": {"rank_ast": 7}}
    recent = {"ast": 8, "season_avg_ast": 7}
    score, rating, signals, ctx = _score_player_ast(
        "PG", "OPP", team_defense, recent, None,
    )
    assert signals["dvp"] == 0
    assert score == 0  # can't reach threshold without DvP


def test_ast_potential_rank_2_scores_2():
    """Potential AST rank 1-2 gives 2 points."""
    team_defense = {"PG": {"rank_ast": 1}}
    recent = {"ast": 8, "season_avg_ast": 7}
    tracking = {"rank_potential_ast": 2}
    score, rating, signals, ctx = _score_player_ast(
        "PG", "OPP", team_defense, recent, tracking,
    )
    assert signals["potential_ast"] == 2


def test_ast_potential_rank_5_scores_1():
    """Potential AST rank 3-6 gives 1 point."""
    team_defense = {"PG": {"rank_ast": 1}}
    recent = {"ast": 8, "season_avg_ast": 7}
    tracking = {"rank_potential_ast": 5}
    score, rating, signals, ctx = _score_player_ast(
        "PG", "OPP", team_defense, recent, tracking,
    )
    assert signals["potential_ast"] == 1


def test_ast_potential_rank_7_scores_0():
    """Potential AST rank 7+ gives 0 points."""
    team_defense = {"PG": {"rank_ast": 1}}
    recent = {"ast": 8, "season_avg_ast": 7}
    tracking = {"rank_potential_ast": 7}
    score, rating, signals, ctx = _score_player_ast(
        "PG", "OPP", team_defense, recent, tracking,
    )
    assert signals["potential_ast"] == 0


def test_ast_full_score_6_best_of_night():
    """DvP 1 (3) + form (1) + potential 1 (2) = 6 BEST OF THE NIGHT."""
    team_defense = {"SG": {"rank_ast": 1}}
    recent = {"ast": 9, "season_avg_ast": 7}
    tracking = {"rank_potential_ast": 2}
    score, rating, signals, ctx = _score_player_ast(
        "SG", "OPP", team_defense, recent, tracking,
    )
    assert score == 6
    assert rating == "BEST OF THE NIGHT"


def test_ast_score_5_very_favorable():
    """DvP 3 (2) + form (1) + potential 1 (2) = 5 VERY FAVORABLE."""
    team_defense = {"PG": {"rank_ast": 3}}
    recent = {"ast": 8, "season_avg_ast": 7}
    tracking = {"rank_potential_ast": 2}
    score, rating, signals, ctx = _score_player_ast(
        "PG", "OPP", team_defense, recent, tracking,
    )
    assert score == 5
    assert rating == "VERY FAVORABLE"


def test_ast_score_4_filtered_out():
    """Score 4 is below threshold 5 — filtered."""
    team_defense = {"PG": {"rank_ast": 3}}
    recent = {"ast": 8, "season_avg_ast": 7}
    tracking = {"rank_potential_ast": 5}
    score, rating, signals, ctx = _score_player_ast(
        "PG", "OPP", team_defense, recent, tracking,
    )
    assert score == 4
    assert rating is None


def test_ast_no_is_stepping_up_param():
    """Function no longer requires is_stepping_up parameter."""
    team_defense = {"PG": {"rank_ast": 1}}
    recent = {"ast": 8, "season_avg_ast": 7}
    # Should work with 5 args (no is_stepping_up)
    score, rating, signals, ctx = _score_player_ast(
        "PG", "OPP", team_defense, recent, None,
    )
    assert score >= 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -k "ast" -v`
Expected: FAIL — signature mismatch (6 args vs 5), wrong scoring values

- [ ] **Step 3: Rewrite `_score_player_ast` in `engine.py:308-366`**

```python
def _score_player_ast(position, opponent_name, team_defense, recent_stats, tracking_data):
    """
    Score a player's assist upside (0-6 scale).
    Graduated DvP: rank 1-2 → 3pts, rank 3-6 → 2pts, 7+ → 0.
    Graduated potential AST: rank 1-2 → 2pts, rank 3-6 → 1pt, 7+ → 0.
    Threshold: 5 (no rating below 5).
    Returns (score, rating, signals_dict, context_dict).
    """
    pos_def = team_defense.get(position, {})
    dvp_rank = pos_def.get("rank_ast")

    score = 0
    signals = {}
    descriptions = []

    # --- Signal 1: DvP AST rank (graduated: 0, 2, or 3 pts) ---
    dvp_pts = 0
    if dvp_rank is not None:
        if dvp_rank <= 2:
            dvp_pts = 3
        elif dvp_rank <= 6:
            dvp_pts = 2
    score += dvp_pts
    signals["dvp"] = dvp_pts
    if dvp_pts > 0:
        descriptions.append(f"AST matchup vs {opponent_name} (DvP #{dvp_rank}, +{dvp_pts})")

    # --- Signal 2: Recent form (0 or 1 pt) ---
    ast_recent = recent_stats.get("ast", 0)
    season_avg_ast = recent_stats.get("season_avg_ast", 0)
    if ast_recent >= season_avg_ast and season_avg_ast > 0:
        score += 1
        signals["recent_form"] = 1
        descriptions.append(f"AST form above avg ({ast_recent} vs {season_avg_ast} season)")
    else:
        signals["recent_form"] = 0

    # --- Signal 3: Potential AST (graduated: 0, 1, or 2 pts) ---
    potential_pts = 0
    if tracking_data is not None:
        rank_pot = tracking_data.get("rank_potential_ast", 99)
        if rank_pot <= 2:
            potential_pts = 2
        elif rank_pot <= 6:
            potential_pts = 1
    score += potential_pts
    signals["potential_ast"] = potential_pts
    if potential_pts > 0:
        rank_pot = tracking_data.get("rank_potential_ast", 99)
        descriptions.append(f"Potential AST opportunity (rank #{rank_pot}, +{potential_pts})")

    # --- Rating (threshold 5) ---
    if score >= 6:
        rating = "BEST OF THE NIGHT"
    elif score >= 5:
        rating = "VERY FAVORABLE"
    else:
        rating = None

    context = {"dvp_rank": dvp_rank, "signal_descriptions": descriptions}
    return score, rating, signals, context
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -k "ast" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add analysis/engine.py tests/test_engine.py
git commit -m "feat: graduated AST scoring without gates, threshold 5"
```

---

### Task 3: Update `_score_player_reb` with graduated scoring and no gates

**Files:**
- Modify: `analysis/engine.py:369-426`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Write new tests for graduated REB scoring**

Add to `tests/test_engine.py` (replace existing REB tests):

```python
# --- REB graduated scoring tests ---

def test_reb_dvp_rank_2_scores_3():
    """DvP rank 1-2 gives 3 points."""
    team_defense = {"C": {"rank_reb": 2}}
    recent = {"reb": 10, "season_avg_reb": 9}
    score, rating, signals, ctx = _score_player_reb(
        "C", "OPP", team_defense, recent, None,
    )
    assert signals["dvp"] == 3


def test_reb_dvp_rank_5_scores_2():
    """DvP rank 3-6 gives 2 points."""
    team_defense = {"PF": {"rank_reb": 5}}
    recent = {"reb": 7, "season_avg_reb": 8}
    score, rating, signals, ctx = _score_player_reb(
        "PF", "OPP", team_defense, recent, None,
    )
    assert signals["dvp"] == 2


def test_reb_dvp_rank_8_scores_0():
    """DvP rank 7+ gives 0 points."""
    team_defense = {"C": {"rank_reb": 8}}
    recent = {"reb": 10, "season_avg_reb": 9}
    score, rating, signals, ctx = _score_player_reb(
        "C", "OPP", team_defense, recent, None,
    )
    assert signals["dvp"] == 0


def test_reb_opportunity_rank_1_scores_2():
    """REB opportunity rank 1-2 gives 2 points."""
    team_defense = {"C": {"rank_reb": 1}}
    recent = {"reb": 10, "season_avg_reb": 9}
    tracking = {"rank_reb_chances": 1}
    score, rating, signals, ctx = _score_player_reb(
        "C", "OPP", team_defense, recent, tracking,
    )
    assert signals["reb_opportunity"] == 2


def test_reb_opportunity_rank_4_scores_1():
    """REB opportunity rank 3-6 gives 1 point."""
    team_defense = {"C": {"rank_reb": 1}}
    recent = {"reb": 10, "season_avg_reb": 9}
    tracking = {"rank_reb_chances": 4}
    score, rating, signals, ctx = _score_player_reb(
        "C", "OPP", team_defense, recent, tracking,
    )
    assert signals["reb_opportunity"] == 1


def test_reb_opportunity_rank_7_scores_0():
    """REB opportunity rank 7+ gives 0 points."""
    team_defense = {"C": {"rank_reb": 1}}
    recent = {"reb": 10, "season_avg_reb": 9}
    tracking = {"rank_reb_chances": 7}
    score, rating, signals, ctx = _score_player_reb(
        "C", "OPP", team_defense, recent, tracking,
    )
    assert signals["reb_opportunity"] == 0


def test_reb_full_score_6_best_of_night():
    """DvP 2 (3) + form (1) + opportunity 1 (2) = 6 BEST OF THE NIGHT."""
    team_defense = {"C": {"rank_reb": 2}}
    recent = {"reb": 10, "season_avg_reb": 9}
    tracking = {"rank_reb_chances": 1}
    score, rating, signals, ctx = _score_player_reb(
        "C", "OPP", team_defense, recent, tracking,
    )
    assert score == 6
    assert rating == "BEST OF THE NIGHT"


def test_reb_score_5_very_favorable():
    """DvP 4 (2) + form (1) + opportunity 2 (2) = 5 VERY FAVORABLE."""
    team_defense = {"PF": {"rank_reb": 4}}
    recent = {"reb": 8, "season_avg_reb": 7}
    tracking = {"rank_reb_chances": 2}
    score, rating, signals, ctx = _score_player_reb(
        "PF", "OPP", team_defense, recent, tracking,
    )
    assert score == 5
    assert rating == "VERY FAVORABLE"


def test_reb_score_4_filtered_out():
    """Score 4 is below threshold 5 — filtered."""
    team_defense = {"C": {"rank_reb": 4}}
    recent = {"reb": 10, "season_avg_reb": 9}
    tracking = {"rank_reb_chances": 5}
    score, rating, signals, ctx = _score_player_reb(
        "C", "OPP", team_defense, recent, tracking,
    )
    assert score == 4
    assert rating is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -k "reb" -v`
Expected: FAIL

- [ ] **Step 3: Rewrite `_score_player_reb` in `engine.py:369-426`**

```python
def _score_player_reb(position, opponent_name, team_defense, recent_stats, tracking_data):
    """
    Score a player's rebound upside (0-6 scale).
    Graduated DvP: rank 1-2 → 3pts, rank 3-6 → 2pts, 7+ → 0.
    Graduated REB opportunity: rank 1-2 → 2pts, rank 3-6 → 1pt, 7+ → 0.
    Threshold: 5 (no rating below 5).
    Returns (score, rating, signals_dict, context_dict).
    """
    pos_def = team_defense.get(position, {})
    dvp_rank = pos_def.get("rank_reb")

    score = 0
    signals = {}
    descriptions = []

    # --- Signal 1: DvP REB rank (graduated: 0, 2, or 3 pts) ---
    dvp_pts = 0
    if dvp_rank is not None:
        if dvp_rank <= 2:
            dvp_pts = 3
        elif dvp_rank <= 6:
            dvp_pts = 2
    score += dvp_pts
    signals["dvp"] = dvp_pts
    if dvp_pts > 0:
        descriptions.append(f"REB matchup vs {opponent_name} (DvP #{dvp_rank}, +{dvp_pts})")

    # --- Signal 2: Recent form (0 or 1 pt) ---
    reb_recent = recent_stats.get("reb", 0)
    season_avg_reb = recent_stats.get("season_avg_reb", 0)
    if reb_recent >= season_avg_reb and season_avg_reb > 0:
        score += 1
        signals["recent_form"] = 1
        descriptions.append(f"REB form above avg ({reb_recent} vs {season_avg_reb} season)")
    else:
        signals["recent_form"] = 0

    # --- Signal 3: REB opportunity (graduated: 0, 1, or 2 pts) ---
    opp_pts = 0
    if tracking_data is not None:
        rank_reb = tracking_data.get("rank_reb_chances", 99)
        if rank_reb <= 2:
            opp_pts = 2
        elif rank_reb <= 6:
            opp_pts = 1
    score += opp_pts
    signals["reb_opportunity"] = opp_pts
    if opp_pts > 0:
        rank_reb = tracking_data.get("rank_reb_chances", 99)
        descriptions.append(f"REB opportunity (rank #{rank_reb}, +{opp_pts})")

    # --- Rating (threshold 5) ---
    if score >= 6:
        rating = "BEST OF THE NIGHT"
    elif score >= 5:
        rating = "VERY FAVORABLE"
    else:
        rating = None

    context = {"dvp_rank": dvp_rank, "signal_descriptions": descriptions}
    return score, rating, signals, context
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -k "reb" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add analysis/engine.py tests/test_engine.py
git commit -m "feat: graduated REB scoring without gates, threshold 5"
```

---

## Chunk 3: Update Engine Flow and Pipeline

### Task 4: Add pace gate helper and refactor `run_analysis`

**Files:**
- Modify: `analysis/engine.py:557-741`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Write pace gate test**

```python
# --- Pace gate tests ---
from analysis.engine import _pace_gate_passes

def test_pace_gate_both_above_median_passes():
    pace_map = {1: 100.0, 2: 101.0}
    assert _pace_gate_passes(1, 2, pace_map, 99.0) is True

def test_pace_gate_one_above_one_below_passes():
    pace_map = {1: 100.0, 2: 95.0}
    assert _pace_gate_passes(1, 2, pace_map, 99.0) is True

def test_pace_gate_both_below_median_fails():
    pace_map = {1: 95.0, 2: 96.0}
    assert _pace_gate_passes(1, 2, pace_map, 99.0) is False

def test_pace_gate_exactly_at_median_passes():
    pace_map = {1: 99.0, 2: 95.0}
    assert _pace_gate_passes(1, 2, pace_map, 99.0) is True

def test_pace_gate_missing_team_passes():
    """If pace data missing for a team, don't block."""
    pace_map = {1: 95.0}
    assert _pace_gate_passes(1, 2, pace_map, 99.0) is True
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_engine.py -k "pace_gate" -v`
Expected: FAIL — `_pace_gate_passes` not found

- [ ] **Step 3: Add `_pace_gate_passes` to engine.py**

Add before `run_analysis` (around line 555):

```python
def _pace_gate_passes(home_team_id, away_team_id, pace_map, median_pace):
    """
    Pace gate for AST/REB: at least one team must have pace >= median.
    If pace data is missing for a team, pass through (don't block).
    """
    home_pace = pace_map.get(home_team_id)
    away_pace = pace_map.get(away_team_id)
    # If either team's data is missing, don't block
    if home_pace is None or away_pace is None:
        return True
    return home_pace >= median_pace or away_pace >= median_pace
```

- [ ] **Step 4: Run pace gate tests**

Run: `python -m pytest tests/test_engine.py -k "pace_gate" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add analysis/engine.py tests/test_engine.py
git commit -m "feat: add _pace_gate_passes helper"
```

---

### Task 5: Refactor `run_analysis` for dual-loop architecture

**Files:**
- Modify: `analysis/engine.py:557-741` — the `run_analysis` function
- Modify: `analysis/pipeline.py` — pass pace data
- Modify: `scrapers/nba.py` — import in pipeline

- [ ] **Step 1: Write integration test for open-gate AST/REB flow**

```python
@patch("analysis.engine.get_player_shot_zones", return_value={})
@patch("analysis.engine.get_player_recent_stats", return_value={
    "pts": 15, "reb": 10, "ast": 8, "min": 30, "three_pm": 2, "three_pa": 5,
    "games": 15, "season_avg_pts": 14, "season_avg_ast": 7,
    "season_avg_reb": 9, "season_avg_three_pm": 1.5, "season_avg_three_pa": 4,
})
@patch("analysis.engine.get_player_season_data", return_value=(
    {201566: 32.0},  # LeBron-like player with 32 min/g
    {201566},  # IS a starter — should still be analyzed for AST/REB
))
@patch("analysis.engine.get_all_teams_defense_zones", return_value={})
@patch("analysis.engine._find_player_id", return_value=201566)
def test_run_analysis_ast_reb_analyzes_starters(mock_pid, mock_zones, mock_season, mock_recent, mock_shot):
    """AST/REB open gate: starters are analyzed (not filtered like PTS/3PT)."""
    games = [{
        "home_tricode": "LAL", "away_tricode": "BOS",
        "home_team_id": 1610612747, "away_team_id": 1610612738,
    }]
    lineups = {
        "LAL": {
            "team_name": "Lakers",
            "starters": [{"name": "LeBron James", "position": "SF"}],
            "out": [],
        },
        "BOS": {"team_name": "Celtics", "starters": [], "out": []},
    }
    # DvP data with rank 1 AST for SF
    team_defense = {"SF": {"rank_ast": 1, "rank_reb": 1, "rank_three_pm": 15, "rank_three_pa": 15}}
    tracking = {"rank_potential_ast": 1, "rank_reb_chances": 1}
    pace_map = {1610612747: 102.0, 1610612738: 100.0}
    median_pace = 99.0

    stats = run_analysis(games, lineups, {}, team_defense, tracking, pace_map, median_pace)

    # LeBron should appear in AST or REB (starter, but open gate allows it)
    ast_names = [c["player_name"] for c in stats["ast"]]
    reb_names = [c["player_name"] for c in stats["reb"]]
    assert "LeBron James" in ast_names or "LeBron James" in reb_names
```

- [ ] **Step 2: Update `run_analysis` signature and body**

New signature:
```python
def run_analysis(games, lineups, dvp, team_defense, tracking_data, pace_map=None, median_pace=None):
```

The function now has **two loops**:

**Loop 1 (PTS/3PT — unchanged injury gate):**
Same as current code — requires out_starters, bench-only, position-compatible.
Only scores PTS and 3PT.

**Loop 2 (AST/REB — open gate):**
For EVERY game:
1. Check pace gate — if both teams below median, skip game for AST/REB
2. For each team in the game:
   - Iterate projected starters (all of them)
   - Also iterate bench players with >= 20 min/g from `season_minutes`
   - For each player: fetch recent_stats, score AST and REB
   - No injury gate, no bench-only gate, no position-compat gate

Key implementation detail for bench >= 20min/g: use `get_team_roster(team_id)` data cross-referenced with `season_minutes` to find bench players not in the projected starters list.

**Simpler approach:** Instead of fetching full rosters, iterate ALL players from `season_minutes` that belong to the team. But we don't have team membership in `season_minutes`. So:

**Best approach:** Use the `lineups` data — it has `starters` list. For bench players, we need the roster. BUT to avoid extra API calls, we can use `get_player_season_data()` which already returns all players with >= 5 GP. We just need to know which team they're on.

**Simplest approach:** Only use RotoWire projected starters for AST/REB (they already include the players most likely to play significant minutes). Don't add extra bench players for now — the spec says "starters + bench >= 20min/g", but starters from RotoWire already covers most high-minute players.

Actually, re-reading the spec: the projected starters from RotoWire ARE the starters. We also need bench players >= 20 min/g. We can get team rosters from nba_api and cross-reference with season_minutes.

**Implementation plan for Loop 2:**

```python
# --- Loop 2: AST/REB (open gate — all games, all qualifying players) ---
for game in games:
    home_id = game["home_team_id"]
    away_id = game["away_team_id"]
    game_label = f"{game['away_tricode']} @ {game['home_tricode']}"

    # Pace gate
    if pace_map and median_pace is not None:
        if not _pace_gate_passes(home_id, away_id, pace_map, median_pace):
            print(f"  [skip AST/REB] {game_label} - both teams below pace median")
            continue

    for player_tricode, opponent_tricode in [
        (game["home_tricode"], game["away_tricode"]),
        (game["away_tricode"], game["home_tricode"]),
    ]:
        team_data = lineups.get(player_tricode, {})
        opponent_data = lineups.get(opponent_tricode, {})
        if not team_data:
            continue

        opponent_name = opponent_data.get("team_name", opponent_tricode)
        opponent_team_id = tricode_to_team_id.get(opponent_tricode)

        # Build player list: projected starters + bench >= 20min/g
        players_to_analyze = []
        starter_names = set()
        for s in team_data.get("starters", []):
            players_to_analyze.append(s)
            starter_names.add(s["name"])

        # Add bench players >= 20 min/g (from season data, not in starters)
        team_id = tricode_to_team_id.get(player_tricode)
        if team_id:
            try:
                roster = get_team_roster(team_id)
            except Exception:
                roster = []
            for rp in roster:
                if rp["player_name"] not in starter_names:
                    pid = rp["player_id"]
                    mins = season_minutes.get(pid)
                    if mins is not None and mins >= 20.0:
                        players_to_analyze.append({
                            "name": rp["player_name"],
                            "position": rp["position"] or "G",
                        })

        for player in players_to_analyze:
            player_name = player["name"]
            position = player["position"]
            player_id = _find_player_id(player_name)
            if not player_id:
                continue

            min_avg = season_minutes.get(player_id)
            if min_avg is None:
                continue

            try:
                recent_stats = get_player_recent_stats(player_id)
            except Exception as e:
                print(f"    [error] {e} - skipping {player_name}")
                continue

            # Normalize position for team_defense lookup
            pos_key = position
            if pos_key in POSITION_MAP:
                pos_key = POSITION_MAP[pos_key][0]  # e.g. "G" → "PG"

            opp_def = team_defense.get(opponent_team_id, {})

            # AST scoring
            ast_score, ast_rating, ast_signals, ast_context = _score_player_ast(
                pos_key, opponent_name, opp_def, recent_stats, tracking_data,
            )
            if ast_rating:
                ast_context["starter_out"] = None  # no injury context
                all_candidates["ast"].append({
                    "player_name": player_name,
                    "player_id": player_id,
                    "team": team_data.get("team_name", player_tricode),
                    "position": position,
                    "game": game_label,
                    "score": ast_score,
                    "rating": ast_rating,
                    "signals": ast_signals,
                    "context": ast_context,
                    "recent_stats": recent_stats,
                    "replaces": [],
                })

            # REB scoring
            reb_score, reb_rating, reb_signals, reb_context = _score_player_reb(
                pos_key, opponent_name, opp_def, recent_stats, tracking_data,
            )
            if reb_rating:
                reb_context["starter_out"] = None
                all_candidates["reb"].append({
                    "player_name": player_name,
                    "player_id": player_id,
                    "team": team_data.get("team_name", player_tricode),
                    "position": position,
                    "game": game_label,
                    "score": reb_score,
                    "rating": reb_rating,
                    "signals": reb_signals,
                    "context": reb_context,
                    "recent_stats": recent_stats,
                    "replaces": [],
                })
```

**Remove AST/REB scoring from Loop 1** — only PTS and 3PT remain in the injury-gated loop.

- [ ] **Step 3: Update `pipeline.py` to pass pace data**

```python
# In pipeline.py, add import and fetch pace before run_analysis:
from scrapers.nba import (
    get_todays_games, get_team_defense_vs_position, get_team_defense_tracking,
    get_team_pace,
)

# After tracking_data fetch, add:
print("Buscando pace dos times (NBA API)...")
pace_map, median_pace = get_team_pace()
print(f"  Concluído (mediana: {median_pace:.1f})")

# Update run_analysis call:
stats = run_analysis(games, lineups, dvp, team_defense, tracking_data, pace_map, median_pace)
```

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add analysis/engine.py analysis/pipeline.py
git commit -m "feat: dual-loop engine — open gate for AST/REB with pace gate"
```

---

### Task 6: Update existing tests that break due to signature changes

**Files:**
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Fix any tests still using old `_score_player_ast`/`_score_player_reb` signatures**

Old tests pass `is_stepping_up` as 6th arg — remove that arg from all AST/REB test calls.

Old tests that test `is_stepping_up=False` gate → **delete these tests** (gate no longer exists).

Tests to delete:
- `test_ast_gate_not_stepping_up` (line 739)
- `test_reb_gate_not_stepping_up` (line 827)

Tests to update (remove 6th arg):
- `test_ast_gate_dvp_rank_above_6` → update expectations (rank 7 now returns score 0, not gate rejection)
- `test_ast_full_score_6` → remove `True` arg
- `test_ast_fallback_tracking_none_rank_2` → remove fallback logic tests (no more fallback)
- `test_reb_gate_dvp_rank_above_6` → update similarly
- `test_reb_full_score_6` → remove `True` arg

Also update `test_run_analysis_wiring_no_type_error` (line 243) and `test_run_analysis_returns_stat_dict` (line 1075) to pass `pace_map` and `median_pace` args to `run_analysis`.

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_engine.py
git commit -m "test: update AST/REB tests for graduated scoring and open gate"
```

---

## Chunk 4: Integration Verification

### Task 7: End-to-end smoke test

- [ ] **Step 1: Run the full pipeline locally**

```bash
python -c "
from analysis.pipeline import run_pipeline
stats, games = run_pipeline()
if stats:
    for key, candidates in stats.items():
        print(f'{key}: {len(candidates)} candidates')
        for c in candidates:
            print(f'  {c[\"player_name\"]} ({c[\"position\"]}) - score {c[\"score\"]} - {c[\"rating\"]}')
else:
    print('No stats returned')
"
```

Verify:
- No errors/crashes
- AST/REB sections may now have candidates (starters included)
- PTS/3PT still require injury gate
- Pace gate logs show which games were skipped

- [ ] **Step 2: Run full test suite one final time**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Final commit and push**

```bash
git push origin main
```
