# Scoring Engine Tightening Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten the NBA player scoring engine to reduce false positives by stricter DvP gates, an above-average recent-form requirement, and removing the stepping-up scoring bonus in favour of a hard gate.

**Architecture:** Two files change — `scrapers/nba.py` gains a richer return value from the season stats function, and `analysis/engine.py` updates the scoring logic and its caller accordingly. No new modules, no new API calls.

**Tech Stack:** Python 3, nba_api, pandas, pytest (already installed)

**Spec:** `docs/superpowers/specs/2026-03-18-scoring-engine-tightening-design.md`

---

## Chunk 1: scrapers/nba.py — rename and extend get_player_season_stats

### Task 1: Write failing test for get_player_season_stats

**Files:**
- Create: `tests/test_scrapers_nba.py`

- [ ] **Step 1: Create the test file**

```python
# tests/test_scrapers_nba.py
from unittest.mock import patch, MagicMock
import pandas as pd
from scrapers.nba import get_player_season_stats


def _make_stats_df(rows):
    """rows: list of (player_id, gp, min_avg, pts_avg)"""
    return pd.DataFrame(
        rows,
        columns=["PLAYER_ID", "GP", "MIN", "PTS"],
    )


def test_returns_min_and_pts_for_qualifying_players():
    df = _make_stats_df([
        (1, 10, 28.5, 18.2),
        (2, 10, 22.0, 9.4),
    ])
    mock_endpoint = MagicMock()
    mock_endpoint.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguedashplayerstats.LeagueDashPlayerStats", return_value=mock_endpoint):
        result = get_player_season_stats()

    assert result == {
        1: {"min": 28.5, "pts": 18.2},
        2: {"min": 22.0, "pts": 9.4},
    }


def test_excludes_players_with_fewer_than_5_games():
    df = _make_stats_df([
        (1, 4, 30.0, 20.0),   # GP < 5 → excluded
        (2, 5, 25.0, 12.0),   # GP == 5 → included
    ])
    mock_endpoint = MagicMock()
    mock_endpoint.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguedashplayerstats.LeagueDashPlayerStats", return_value=mock_endpoint):
        result = get_player_season_stats()

    assert 1 not in result
    assert 2 in result


def test_rounds_values_to_one_decimal():
    df = _make_stats_df([(1, 10, 28.456, 17.678)])
    mock_endpoint = MagicMock()
    mock_endpoint.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguedashplayerstats.LeagueDashPlayerStats", return_value=mock_endpoint):
        result = get_player_season_stats()

    assert result[1]["min"] == 28.5
    assert result[1]["pts"] == 17.7
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_scrapers_nba.py -v
```

Expected: `ImportError` or `AttributeError` — `get_player_season_stats` does not exist yet.

---

### Task 2: Implement get_player_season_stats in scrapers/nba.py

**Files:**
- Modify: `scrapers/nba.py`

- [ ] **Step 1: Rename the function and update the return value**

In `scrapers/nba.py`, replace the entire `get_player_season_minutes` function (lines 178–203) with:

```python
def get_player_season_stats():
    """
    Returns {player_id: {"min": avg_min, "pts": avg_pts}} for all players
    with >= 5 games played.

    LeagueDashPlayerStats does not expose GS (games started), so we use
    season-long minutes per game as a reliable proxy for starter status:
      >= 27 min/game  →  regular starter (skip in engine)
      <  27 min/game  →  bench player   (eligible if team has injuries)
    """
    time.sleep(DELAY)
    df = _retry(lambda: leaguedashplayerstats.LeagueDashPlayerStats(
        season=SEASON,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
    ).get_data_frames()[0])

    result = {}
    for _, row in df.iterrows():
        gp = int(row["GP"])
        if gp < 5:
            continue  # too few games for a reliable reading
        result[int(row["PLAYER_ID"])] = {
            "min": round(float(row["MIN"]), 1),
            "pts": round(float(row["PTS"]), 1),
        }
    return result
```

Also update the export in `scrapers/__init__.py` if it lists `get_player_season_minutes` explicitly (check first — if the file is empty or uses `*`, no change needed).

- [ ] **Step 2: Run tests to confirm they pass**

```
pytest tests/test_scrapers_nba.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add scrapers/nba.py tests/test_scrapers_nba.py
git commit -m "feat(scrapers): rename get_player_season_minutes to get_player_season_stats, add pts"
```

---

## Chunk 2: analysis/engine.py — update _score_player

### Task 3: Write failing tests for _score_player

**Files:**
- Create: `tests/test_engine.py`

Context: `_score_player` is a pure function (no I/O). Tests call it directly with fixture data.

- [ ] **Step 1: Create the test file**

```python
# tests/test_engine.py
import pytest
from analysis.engine import _score_player

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DVP_ELITE = {"PG": {"TeamA": {"rank": 2, "pts": 28.4}}}   # rank ≤ 3  → +3
DVP_GOOD  = {"PG": {"TeamA": {"rank": 5, "pts": 24.1}}}   # rank 4-6  → +2
DVP_POOR  = {"PG": {"TeamA": {"rank": 7, "pts": 20.0}}}   # rank > 6  → discard

RECENT_HOT    = {"pts": 19.0, "min": 28.0, "games": 15}   # ≥ 18 → +3
RECENT_SOLID  = {"pts": 13.0, "min": 24.0, "games": 15}   # ≥ 12 → +2
RECENT_MOD    = {"pts": 8.0,  "min": 20.0, "games": 15}   # ≥ 7  → +1
RECENT_LOW    = {"pts": 5.0,  "min": 18.0, "games": 15}   # < 7  → +0

SEASON_AVG_10 = 10.0   # baseline for above-average checks

ZONES_PAINT = {"Restricted Area": {"attempts": 20, "made": 14, "pct": 70.0, "frequency": 50.0}}
OPP_DEFENSE_PAINT = {"Restricted Area": {"fgm": 18.0, "fga": 28.0, "pct": 0.64}}

# ---------------------------------------------------------------------------
# Gate 0: is_stepping_up
# ---------------------------------------------------------------------------

def test_gate0_not_stepping_up_returns_none():
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_HOT, season_avg_pts=SEASON_AVG_10,
        player_zones=ZONES_PAINT, opponent_defense_zones=OPP_DEFENSE_PAINT,
        is_stepping_up=False,
    )
    assert rating is None
    assert score == 0
    assert signals == []


# ---------------------------------------------------------------------------
# Gate 1: DvP
# ---------------------------------------------------------------------------

def test_gate1_poor_dvp_rank_returns_none():
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_POOR,
        recent_stats=RECENT_HOT, season_avg_pts=SEASON_AVG_10,
        player_zones=ZONES_PAINT, opponent_defense_zones=OPP_DEFENSE_PAINT,
        is_stepping_up=True,
    )
    assert rating is None


def test_gate1_elite_dvp_adds_3():
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats={}, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    # DvP +3, no Signal 2 (empty recent_stats), no zone data → no zone discard
    assert score == 3


def test_gate1_good_dvp_adds_2():
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_GOOD,
        recent_stats={}, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 2


# ---------------------------------------------------------------------------
# Signal 2: Recent form above-average gate
# ---------------------------------------------------------------------------

def test_signal2_below_season_avg_does_not_score():
    # recent pts (8.0) is below season avg (10.0) → Signal 2 scores 0
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_MOD, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    # DvP +3 only
    assert score == 3
    assert not any("scorer" in s.lower() for s in signals)


def test_signal2_above_avg_hot_scorer_adds_3():
    # recent pts 19.0 > season avg 10.0 and ≥ 18 → +3
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_HOT, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 6
    assert any("Hot scorer" in s for s in signals)


def test_signal2_above_avg_solid_scorer_adds_2():
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_SOLID, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 5
    assert any("Solid scorer" in s for s in signals)


def test_signal2_above_avg_moderate_scorer_adds_1():
    # recent pts 8.0 > season avg 5.0 and ≥ 7 → moderate scorer, +1
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_MOD, season_avg_pts=5.0,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 4
    assert any("Moderate scorer" in s for s in signals)


def test_signal2_above_avg_but_below_7pts_no_message():
    # recent pts 6.0 > season avg 4.0, but < 7 → no points, no message
    recent = {"pts": 6.0, "min": 18.0, "games": 15}
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=recent, season_avg_pts=4.0,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 3  # DvP only
    assert not any("scorer" in s.lower() for s in signals)


def test_signal2_empty_recent_stats_skips_block():
    score, _, _ = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats={}, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 3  # DvP only, no crash


# ---------------------------------------------------------------------------
# Rating thresholds
# ---------------------------------------------------------------------------

def test_rating_best_of_night_at_7():
    # DvP +3, form +3, zone +1 = 7
    score, rating, _ = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_HOT, season_avg_pts=SEASON_AVG_10,
        player_zones=ZONES_PAINT, opponent_defense_zones=OPP_DEFENSE_PAINT,
        is_stepping_up=True,
    )
    assert score == 7
    assert rating == "BEST OF THE NIGHT"


def test_rating_very_favorable_at_5():
    # DvP +2, form +3, zone +0 (no zone data) = 5
    score, rating, _ = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_GOOD,
        recent_stats=RECENT_HOT, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 5
    assert rating == "VERY FAVORABLE"


def test_rating_none_below_5():
    # DvP +2, form +2 (solid but not hot), no zone = 4 → None
    score, rating, _ = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_GOOD,
        recent_stats=RECENT_SOLID, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 4
    assert rating is None


def test_no_favorable_tier():
    # Score of 4 must not return FAVORABLE
    _, rating, _ = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_GOOD,
        recent_stats=RECENT_SOLID, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert rating != "FAVORABLE"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_engine.py -v
```

Expected: multiple failures — wrong signature (`season_avg_pts` missing), wrong thresholds, `FAVORABLE` still returned, etc.

---

### Task 4: Update _score_player in analysis/engine.py

**Files:**
- Modify: `analysis/engine.py`

Apply all changes to `_score_player` in order. The full updated function is:

- [ ] **Step 1: Update the import at the top of engine.py**

Replace line 6:
```python
# Before
    get_player_season_minutes,
# After
    get_player_season_stats,
```

- [ ] **Step 2: Replace the _score_player function**

Replace the entire `_score_player` function (lines 98–174) with:

```python
def _score_player(position, opponent_name, dvp, recent_stats, season_avg_pts, player_zones, opponent_defense_zones, is_stepping_up):
    """
    Score a player 0-7 across four signals.
    Thresholds: 7 = BEST OF THE NIGHT, 5-6 = VERY FAVORABLE.
    Returns (score, rating, signals_list).
    """
    score = 0
    signals = []

    # --- Gate 0: Stepping up (mandatory) ---
    if not is_stepping_up:
        return 0, None, []

    # --- Gate 1: DvP rank (0-3 pts) ---
    dvp_rank, dvp_pts = _best_dvp_rank(position, opponent_name, dvp)
    if dvp_rank is None:
        return 0, None, []
    if dvp_rank <= 3:
        score += 3
        signals.append(f"Elite matchup vs {opponent_name} (DvP #{dvp_rank}, {dvp_pts} pts/g allowed)")
    elif dvp_rank <= 6:
        score += 2
        signals.append(f"Good matchup vs {opponent_name} (DvP #{dvp_rank}, {dvp_pts} pts/g allowed)")
    else:
        # Rank > 6: not worth surfacing
        return 0, None, []

    # --- Signal 2: Recent scoring form (0-3 pts) ---
    if recent_stats:
        pts = recent_stats["pts"]
        mins = recent_stats["min"]
        if pts > season_avg_pts:
            if pts >= 18:
                score += 3
                signals.append(f"Hot scorer: {pts} pts avg last {recent_stats['games']}g")
            elif pts >= 12:
                score += 2
                signals.append(f"Solid scorer: {pts} pts avg last {recent_stats['games']}g")
            elif pts >= 7:
                score += 1
                signals.append(f"Moderate scorer: {pts} pts avg last {recent_stats['games']}g")
            # pts > season_avg but < 7: no points, no message

        if mins >= 25:
            signals.append(f"High usage: {mins} min avg")

    # --- Signal 3: Zone match (required gate) ---
    primary_zone = _get_primary_zone(player_zones) if player_zones else None
    weakest_zone = _get_opponent_weakest_zone(opponent_defense_zones)

    if primary_zone and weakest_zone:
        player_cat = _zone_category(primary_zone)
        opponent_cat = _zone_category(weakest_zone)
        pz = player_zones[primary_zone]
        zone_str = f"{primary_zone} ({pz['frequency']}% freq, {pz['pct']}% FG)"

        if player_cat == opponent_cat:
            score += 1
            signals.append(f"Zone match: scores from {zone_str} -{opponent_name} concedes most there ({weakest_zone})")
        else:
            # Zone mismatch: discard this player
            return 0, None, []

    # --- Rating ---
    if score >= 7:
        rating = "BEST OF THE NIGHT"
    elif score >= 5:
        rating = "VERY FAVORABLE"
    else:
        rating = None

    return score, rating, signals
```

- [ ] **Step 3: Run the _score_player tests**

```
pytest tests/test_engine.py -v
```

Expected: all tests PASS.

> **Do not commit yet.** `run_analysis` still references `get_player_season_minutes` and calls `_score_player` with the old signature. The module would be broken at runtime until Task 5 is complete. Both tasks share one commit at the end of Task 5.

---

## Chunk 3: analysis/engine.py — update run_analysis

### Task 5: Update run_analysis loop

**Files:**
- Modify: `analysis/engine.py`
- Modify: `tests/test_engine.py` (add smoke test)

- [ ] **Step 1: Update the season stats call and loop**

In `run_analysis`, make these three targeted edits:

**Edit A** — print string + function call (lines 188–189):
```python
# Before
print("  Fetching player season minutes (starter filter)...")
season_minutes = get_player_season_minutes()

# After
print("  Fetching player season stats (starter filter)...")
season_stats = get_player_season_stats()
```

**Edit B** — player_id lookup (lines 237–243):
```python
# Before
min_avg = season_minutes.get(player_id)
if min_avg is None:
    print(f"  [skip] {player_name} - insufficient season data (<5 games)")
    continue
if min_avg >= STARTER_MIN_THRESHOLD:
    print(f"  [skip] {player_name} - regular starter ({min_avg} min/g this season)")
    continue

# After
player_stats = season_stats.get(player_id)
min_avg = player_stats.get("min") if player_stats else None
if min_avg is None:
    print(f"  [skip] {player_name} - insufficient season data (<5 games)")
    continue
if min_avg >= STARTER_MIN_THRESHOLD:
    print(f"  [skip] {player_name} - regular starter ({min_avg} min/g this season)")
    continue
season_avg_pts = player_stats["pts"]  # safe: min_avg guard above ensures player_stats is not None
```

**Edit C** — `_score_player` call (lines 254–262):
```python
# Before
score, rating, signals = _score_player(
    position=position,
    opponent_name=opponent_name,
    dvp=dvp,
    recent_stats=recent_stats,
    player_zones=player_zones,
    opponent_defense_zones=opponent_defense_zones,
    is_stepping_up=True,  # always True: bench player on injured team
)

# After
score, rating, signals = _score_player(
    position=position,
    opponent_name=opponent_name,
    dvp=dvp,
    recent_stats=recent_stats,
    season_avg_pts=season_avg_pts,
    player_zones=player_zones,
    opponent_defense_zones=opponent_defense_zones,
    is_stepping_up=True,  # always True: bench player on injured team
)
```

- [ ] **Step 2: Add run_analysis smoke test to tests/test_engine.py**

Append to `tests/test_engine.py`:

```python
# ---------------------------------------------------------------------------
# run_analysis wiring smoke test
# ---------------------------------------------------------------------------

from unittest.mock import patch
from analysis.engine import run_analysis

def test_run_analysis_wiring_no_type_error():
    """
    Verifies that run_analysis correctly wires season_avg_pts into _score_player.
    All scrapers are patched — this test only checks the call is wired correctly,
    not that real data is returned.
    """
    games = [{
        "game_id": "001",
        "home_team": "TeamA", "home_team_id": 1, "home_tricode": "HME",
        "away_team": "TeamB", "away_team_id": 2, "away_tricode": "AWY",
    }]
    lineups = {
        "HME": {
            "team_name": "TeamA",
            "starters": [{"name": "John Doe", "position": "PG"}],
            "out": ["Injured Player"],
        },
        "AWY": {"team_name": "TeamB", "starters": [], "out": []},
    }
    dvp = {}

    with patch("analysis.engine.get_all_teams_defense_zones", return_value={}), \
         patch("analysis.engine.get_player_season_stats", return_value={
             9999: {"min": 20.0, "pts": 10.0}
         }), \
         patch("analysis.engine._find_player_id", return_value=9999), \
         patch("analysis.engine.get_player_recent_stats", return_value={"pts": 15.0, "min": 22.0, "games": 15}), \
         patch("analysis.engine.get_player_shot_zones", return_value={}):
        result = run_analysis(games, lineups, dvp)

    # No TypeError = wiring is correct. Result may be empty (dvp={} means no DvP match).
    assert isinstance(result, list)
```

- [ ] **Step 3: Run all tests**

```
pytest tests/ -v
```

Expected: all tests PASS. No ImportError, no TypeError.

- [ ] **Step 4: Commit Tasks 4 and 5 together**

```bash
git add analysis/engine.py tests/test_engine.py
git commit -m "feat(engine): tighten _score_player — stricter DvP, above-avg form gate, remove stepping-up bonus; wire season_avg_pts into run_analysis"
```

---

## Chunk 4: scrapers/__init__.py check

### Task 6: Verify scrapers/__init__.py exports

**Files:**
- Check: `scrapers/__init__.py`

- [ ] **Step 1: Read the file**

Open `scrapers/__init__.py`. If it explicitly exports `get_player_season_minutes` by name, rename it to `get_player_season_stats`. If the file is empty or does not reference the function, no change needed.

- [ ] **Step 2: Run the full test suite**

```
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit if changed**

Only commit if the file was modified:
```bash
git add scrapers/__init__.py
git commit -m "chore(scrapers): update __init__ export for get_player_season_stats rename"
```
