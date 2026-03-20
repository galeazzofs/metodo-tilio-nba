# Stake Filter Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a game-level filter that skips NBA games with no playoff/play-in implications before running the expensive per-player analysis.

**Architecture:** A new `get_conference_standings()` scraper fetches standings data from the NBA API; two new functions in `analysis/engine.py` (`_team_has_stake` and `filter_games_by_stake`) implement the stake logic; `main.py` wires the filter in before lineup fetching so cold games are dropped early with zero extra API cost.

**Tech Stack:** Python, `nba_api` (`LeagueStandingsV3`), `unittest.mock` for tests

---

## Chunk 1: Standings scraper + stake helper

### Task 1: `get_conference_standings()` in `scrapers/nba.py`

**Files:**
- Modify: `scrapers/nba.py`
- Test: `tests/test_scrapers_nba.py`

The function fetches per-conference standings from `LeagueStandingsV3` and returns a `dict[team_id → StandingData]`. Each entry contains the fields needed by the stake logic.

Fields returned per team:
- `team_id` (int)
- `conference` (`"East"` or `"West"`)
- `seed` (int, 1–15 within conference)
- `wins` (int)
- `losses` (int)
- `games_remaining` (int, `= 82 - wins - losses`)
- `games_back_from_above` (float or `None` for seed 1)
- `games_ahead_of_below` (float or `None` for seed 15)

The `ConferenceGamesBack` field from the API is `None` or `"-"` for the conference leader — treat as `0.0` when computing inter-seed gaps. Gaps are computed by sorting each conference's teams by seed and subtracting adjacent `ConferenceGamesBack` values.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scrapers_nba.py`:

```python
from unittest.mock import patch, MagicMock
import pandas as pd
from scrapers.nba import get_conference_standings


def _make_standings_df(rows):
    """
    rows: list of dicts with keys:
      TeamID, Conference, PlayoffRank, WINS, LOSSES, ConferenceGamesBack
    """
    return pd.DataFrame(rows)


def test_get_conference_standings_basic_structure():
    """Two teams, one per conference — correct keys and types."""
    df = _make_standings_df([
        {"TeamID": 1, "Conference": "East", "PlayoffRank": 1,
         "WINS": 50, "LOSSES": 20, "ConferenceGamesBack": None},
        {"TeamID": 2, "Conference": "West", "PlayoffRank": 1,
         "WINS": 48, "LOSSES": 22, "ConferenceGamesBack": None},
    ])
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguestandingsv3.LeagueStandingsV3", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"):
        result = get_conference_standings()

    assert 1 in result
    entry = result[1]
    assert entry["team_id"] == 1
    assert entry["conference"] == "East"
    assert entry["seed"] == 1
    assert entry["wins"] == 50
    assert entry["losses"] == 20
    assert entry["games_remaining"] == 12   # 82 - 50 - 20
    assert entry["games_back_from_above"] is None   # seed 1
    assert isinstance(entry["games_ahead_of_below"], (float, type(None)))


def test_get_conference_standings_seed1_games_back_from_above_is_none():
    """Seed-1 team always has games_back_from_above = None."""
    df = _make_standings_df([
        {"TeamID": 10, "Conference": "East", "PlayoffRank": 1,
         "WINS": 58, "LOSSES": 16, "ConferenceGamesBack": None},
        {"TeamID": 11, "Conference": "East", "PlayoffRank": 2,
         "WINS": 54, "LOSSES": 20, "ConferenceGamesBack": 4.0},
    ])
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguestandingsv3.LeagueStandingsV3", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"):
        result = get_conference_standings()

    assert result[10]["games_back_from_above"] is None
    assert result[10]["games_ahead_of_below"] == 4.0


def test_get_conference_standings_seed15_games_ahead_of_below_is_none():
    """Seed-15 team always has games_ahead_of_below = None."""
    rows = [
        {"TeamID": i, "Conference": "East", "PlayoffRank": i,
         "WINS": max(0, 60 - i * 4), "LOSSES": min(82, 22 + i * 4),
         "ConferenceGamesBack": None if i == 1 else float(i - 1) * 2}
        for i in range(1, 16)
    ]
    df = _make_standings_df(rows)
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguestandingsv3.LeagueStandingsV3", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"):
        result = get_conference_standings()

    # team with PlayoffRank 15 = TeamID 15
    assert result[15]["games_ahead_of_below"] is None


def test_get_conference_standings_none_and_dash_gamesback_treated_as_zero():
    """
    ConferenceGamesBack of None or '-' for the leader must be treated as 0.0
    so adjacent gap computation does not crash.
    """
    df = _make_standings_df([
        {"TeamID": 20, "Conference": "West", "PlayoffRank": 1,
         "WINS": 55, "LOSSES": 19, "ConferenceGamesBack": "-"},   # dash string
        {"TeamID": 21, "Conference": "West", "PlayoffRank": 2,
         "WINS": 52, "LOSSES": 22, "ConferenceGamesBack": 3.0},
    ])
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguestandingsv3.LeagueStandingsV3", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"):
        result = get_conference_standings()

    # gap between seed-1 (0.0) and seed-2 (3.0) = 3.0
    assert result[20]["games_ahead_of_below"] == 3.0
    assert result[21]["games_back_from_above"] == 3.0


def test_get_conference_standings_games_remaining_formula():
    """games_remaining = 82 - wins - losses."""
    df = _make_standings_df([
        {"TeamID": 30, "Conference": "East", "PlayoffRank": 1,
         "WINS": 70, "LOSSES": 10, "ConferenceGamesBack": None},
    ])
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguestandingsv3.LeagueStandingsV3", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"):
        result = get_conference_standings()

    assert result[30]["games_remaining"] == 2   # 82 - 70 - 10
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_scrapers_nba.py::test_get_conference_standings_basic_structure -v
```

Expected: `FAILED` — `ImportError: cannot import name 'get_conference_standings'`

- [ ] **Step 3: Implement `get_conference_standings()` in `scrapers/nba.py`**

Add the import at the top of the imports block (alongside existing endpoint imports):
```python
from nba_api.stats.endpoints import (
    ...
    leaguestandingsv3,
)
```

Add the function at the end of `scrapers/nba.py` (after `get_player_recent_stats`):

```python
def get_conference_standings():
    """
    Returns per-team standing data keyed by team_id, for use by the stake filter.

    {
        team_id: {
            "team_id": int,
            "conference": "East" | "West",
            "seed": int,                       # 1–15 within conference
            "wins": int,
            "losses": int,
            "games_remaining": int,            # 82 - wins - losses
            "games_back_from_above": float | None,   # None for seed 1
            "games_ahead_of_below": float | None,    # None for seed 15
        },
        ...
    }

    ConferenceGamesBack for the conference leader is returned by the API as
    None or "-" — both are treated as 0.0 for gap computation.
    """
    time.sleep(DELAY)
    df = _retry(lambda: leaguestandingsv3.LeagueStandingsV3(
        season=SEASON,
        season_type="Regular Season",
    ).get_data_frames()[0])

    def _to_float(val):
        """Convert API ConferenceGamesBack to float; treat None and '-' as 0.0."""
        if val is None or str(val).strip() == "-":
            return 0.0
        return float(val)

    # Group by conference, sort by seed, compute adjacent gaps
    result = {}
    for conf in ("East", "West"):
        conf_rows = df[df["Conference"] == conf].copy()
        conf_rows = conf_rows.sort_values("PlayoffRank").reset_index(drop=True)
        gb_values = [_to_float(row["ConferenceGamesBack"]) for _, row in conf_rows.iterrows()]

        for i, (_, row) in enumerate(conf_rows.iterrows()):
            team_id = int(row["TeamID"])
            seed = int(row["PlayoffRank"])
            wins = int(row["WINS"])
            losses = int(row["LOSSES"])

            games_back_from_above = (gb_values[i] - gb_values[i - 1]) if i > 0 else None
            games_ahead_of_below = (gb_values[i + 1] - gb_values[i]) if i < len(gb_values) - 1 else None

            result[team_id] = {
                "team_id": team_id,
                "conference": conf,
                "seed": seed,
                "wins": wins,
                "losses": losses,
                "games_remaining": 82 - wins - losses,
                "games_back_from_above": games_back_from_above,
                "games_ahead_of_below": games_ahead_of_below,
            }

    return result
```

- [ ] **Step 4: Run new standings tests**

```
pytest tests/test_scrapers_nba.py -k "get_conference_standings" -v
```

Expected: all 5 new tests pass.

Note: the existing `test_returns_min_and_pts_for_qualifying_players` test has a pre-existing import error unrelated to this work (`get_player_season_stats` vs `get_player_season_minutes` naming). Do not fix it here — it is out of scope.

- [ ] **Step 5: Commit**

```bash
git add scrapers/nba.py tests/test_scrapers_nba.py
git commit -m "feat: add get_conference_standings() scraper for stake filter"
```

---

### Task 2: `_team_has_stake()` in `analysis/engine.py`

**Files:**
- Modify: `analysis/engine.py`
- Test: `tests/test_engine.py`

`_team_has_stake(team_data)` evaluates the two stake conditions for a single team and returns `(bool, reason_tag)`.

Stake logic:
- `can_improve = games_back_from_above is not None and games_back_from_above <= games_remaining`
- `can_be_caught = games_ahead_of_below is not None and games_ahead_of_below <= games_remaining`
- `has_stake = can_improve or can_be_caught`
- reason tags: `"can improve"` | `"can be caught"` | `"eliminated"`
  - If both are True: return `"can improve"` (primary; `filter_games_by_stake` handles the `(both)` annotation)
  - If only `can_improve`: return `"can improve"`
  - If only `can_be_caught`: return `"can be caught"`
  - If neither: return `"eliminated"`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_engine.py`. The existing import on line 3 reads:
`from analysis.engine import _score_player, run_analysis, _position_compatible`
Amend it to:
`from analysis.engine import _score_player, run_analysis, _position_compatible, _team_has_stake`

Then add the new tests below the existing `_position_compatible` tests:

```python
# ---------------------------------------------------------------------------
# _team_has_stake
# ---------------------------------------------------------------------------

def _standing(seed, gb_above, gb_below, remaining):
    return {
        "seed": seed,
        "games_back_from_above": gb_above,
        "games_ahead_of_below": gb_below,
        "games_remaining": remaining,
    }


def test_has_stake_can_improve():
    """Team can reach the seed above within remaining games."""
    data = _standing(seed=8, gb_above=3.0, gb_below=10.0, remaining=10)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is True
    assert tag == "can improve"


def test_has_stake_can_be_caught():
    """Team cannot improve but can be caught from below."""
    data = _standing(seed=3, gb_above=15.0, gb_below=2.0, remaining=10)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is True
    assert tag == "can be caught"


def test_has_stake_both_conditions_true_returns_can_improve():
    """When both conditions are true, tag is 'can improve'."""
    data = _standing(seed=5, gb_above=4.0, gb_below=3.0, remaining=10)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is True
    assert tag == "can improve"


def test_has_stake_eliminated():
    """Both conditions false — team is eliminated."""
    data = _standing(seed=13, gb_above=12.0, gb_below=5.0, remaining=6)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is False
    assert tag == "eliminated"


def test_has_stake_seed1_no_above():
    """Seed 1 has games_back_from_above=None — can_improve is always False."""
    data = _standing(seed=1, gb_above=None, gb_below=3.0, remaining=8)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is True   # can be caught
    assert tag == "can be caught"


def test_has_stake_seed15_no_below():
    """Seed 15 has games_ahead_of_below=None — can_be_caught is always False."""
    data = _standing(seed=15, gb_above=4.0, gb_below=None, remaining=8)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is True   # can still improve
    assert tag == "can improve"


def test_has_stake_exact_boundary_games_back_equals_remaining():
    """games_back_from_above == games_remaining — can_improve is True (≤, not <)."""
    data = _standing(seed=10, gb_above=5.0, gb_below=20.0, remaining=5)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is True
    assert tag == "can improve"


def test_has_stake_one_game_over_remaining():
    """games_back_from_above > games_remaining — can_improve is False."""
    data = _standing(seed=10, gb_above=6.0, gb_below=20.0, remaining=5)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is False
    assert tag == "eliminated"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_engine.py::test_has_stake_can_improve -v
```

Expected: `FAILED` — `ImportError: cannot import name '_team_has_stake'`

- [ ] **Step 3: Implement `_team_has_stake()` in `analysis/engine.py`**

Add after the `_position_compatible` helper (before `_score_player`):

```python
def _team_has_stake(team_data):
    """
    Returns (has_stake: bool, reason_tag: str).

    reason_tag is one of: "can improve", "can be caught", "eliminated"

    Stake conditions:
      can_improve  = games_back_from_above is not None
                     and games_back_from_above <= games_remaining
      can_be_caught = games_ahead_of_below is not None
                      and games_ahead_of_below <= games_remaining

    When both are True, returns "can improve" as the primary tag.
    filter_games_by_stake is responsible for appending " (both)" when needed.
    """
    gb_above = team_data.get("games_back_from_above")
    gb_below = team_data.get("games_ahead_of_below")
    remaining = team_data.get("games_remaining", 0)

    can_improve = gb_above is not None and gb_above <= remaining
    can_be_caught = gb_below is not None and gb_below <= remaining

    if can_improve:
        return True, "can improve"
    if can_be_caught:
        return True, "can be caught"
    return False, "eliminated"
```

- [ ] **Step 4: Run stake helper tests**

```
pytest tests/test_engine.py -k "has_stake" -v
```

Expected: all 8 tests pass

- [ ] **Step 5: Commit**

```bash
git add analysis/engine.py tests/test_engine.py
git commit -m "feat: add _team_has_stake() helper to analysis engine"
```

---

## Chunk 2: Game filter + pipeline integration

### Task 3: `filter_games_by_stake()` in `analysis/engine.py`

**Files:**
- Modify: `analysis/engine.py`
- Test: `tests/test_engine.py`

`filter_games_by_stake(games, standings)` filters the game list, logs each decision, and returns only games where at least one team has a stake.

Log format rules (from spec):
- Seed notation: `{seed}{conference[0].upper()}` — e.g., `8E`, `3W`
- Adjacent ordinals: `seed - 1` and `seed + 1` rendered as ordinals (e.g., seed 8 → `7th` above, `9th` below)
- Boundary slots: `"n/a above"` (seed 1) or `"n/a below"` (seed 15)
- When only one team has a stake: log both teams' lines, eliminated team shows `→ eliminated`
- When both teams have a stake: log both lines, select tighter-margin team for `" (both)"` suffix
  - Tighter margin = `min(v for v in [gb_above, gb_below] if v is not None)`
- Missing standings for a team: include game with `[stake-filter] WARNING: no standings data for team_id=...`

- [ ] **Step 1: Write the failing tests**

Amend the existing import line in `tests/test_engine.py` (currently ends with `_team_has_stake` after Task 2) to also include `filter_games_by_stake`:
`from analysis.engine import _score_player, run_analysis, _position_compatible, _team_has_stake, filter_games_by_stake`

Then add the new tests and helpers below the `_team_has_stake` tests:

```python
# ---------------------------------------------------------------------------
# filter_games_by_stake
# ---------------------------------------------------------------------------

def _make_game(home_id=1, away_id=2, home_tri="HME", away_tri="AWY"):
    return {
        "home_team_id": home_id, "away_team_id": away_id,
        "home_tricode": home_tri, "away_tricode": away_tri,
    }


def _make_standing(team_id, seed, conf, gb_above, gb_below, remaining=10):
    return {
        "team_id": team_id, "seed": seed, "conference": conf,
        "games_back_from_above": gb_above,
        "games_ahead_of_below": gb_below,
        "games_remaining": remaining,
    }


def test_filter_includes_game_when_home_team_has_stake():
    games = [_make_game()]
    standings = {
        1: _make_standing(1, seed=8, conf="East", gb_above=3.0, gb_below=10.0),
        2: _make_standing(2, seed=13, conf="East", gb_above=12.0, gb_below=5.0),
    }
    result = filter_games_by_stake(games, standings)
    assert result == games


def test_filter_includes_game_when_away_team_has_stake():
    games = [_make_game()]
    standings = {
        1: _make_standing(1, seed=14, conf="East", gb_above=15.0, gb_below=3.0),
        2: _make_standing(2, seed=9, conf="East", gb_above=2.0, gb_below=8.0),
    }
    result = filter_games_by_stake(games, standings)
    assert result == games


def test_filter_excludes_game_when_both_eliminated():
    # Both teams eliminated: gb_above > remaining AND gb_below > remaining for each
    games = [_make_game()]
    standings = {
        1: _make_standing(1, seed=13, conf="East", gb_above=12.0, gb_below=8.0, remaining=5),
        2: _make_standing(2, seed=14, conf="West", gb_above=15.0, gb_below=9.0, remaining=5),
    }
    result = filter_games_by_stake(games, standings)
    assert result == []


def test_filter_includes_game_when_both_have_stake():
    games = [_make_game()]
    standings = {
        1: _make_standing(1, seed=3, conf="East", gb_above=2.0, gb_below=1.5),
        2: _make_standing(2, seed=8, conf="East", gb_above=3.0, gb_below=2.0),
    }
    result = filter_games_by_stake(games, standings)
    assert result == games


def test_filter_pass_through_when_team_missing_from_standings(capsys):
    games = [_make_game(home_id=999)]   # 999 not in standings
    standings = {
        2: _make_standing(2, seed=8, conf="East", gb_above=3.0, gb_below=2.0),
    }
    result = filter_games_by_stake(games, standings)
    assert result == games   # pass-through
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "999" in captured.out


def test_filter_multiple_games_mixed_results():
    game_with_stake = _make_game(home_id=1, away_id=2, home_tri="BOS", away_tri="CLE")
    game_no_stake   = _make_game(home_id=3, away_id=4, home_tri="MEM", away_tri="SAS")
    standings = {
        1: _make_standing(1, seed=1, conf="East", gb_above=None, gb_below=4.0),
        2: _make_standing(2, seed=2, conf="East", gb_above=4.0,  gb_below=3.0),
        3: _make_standing(3, seed=12, conf="West", gb_above=10.0, gb_below=6.0, remaining=5),
        4: _make_standing(4, seed=14, conf="West", gb_above=12.0, gb_below=7.0, remaining=5),
    }
    result = filter_games_by_stake([game_with_stake, game_no_stake], standings)
    assert result == [game_with_stake]
    assert game_no_stake not in result
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_engine.py::test_filter_includes_game_when_home_team_has_stake -v
```

Expected: `FAILED` — `ImportError: cannot import name 'filter_games_by_stake'`

- [ ] **Step 3: Implement `filter_games_by_stake()` in `analysis/engine.py`**

Add after `_team_has_stake` (before `_score_player`):

```python
def _ordinal(n):
    """Return English ordinal string for integer n (e.g. 1 → '1st', 11 → '11th')."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _format_team_line(tricode, team_data, reason_tag):
    """Build the detail log line for one team, prefixed with tricode."""
    seed = team_data["seed"]
    conf = team_data["conference"][0].upper()
    gb_above = team_data["games_back_from_above"]
    gb_below = team_data["games_ahead_of_below"]
    remaining = team_data["games_remaining"]

    above_str = (
        "n/a above" if gb_above is None
        else f"{gb_above} GB from {_ordinal(seed - 1)} (above)"
    )
    below_str = (
        "n/a below" if gb_below is None
        else f"{gb_below} ahead of {_ordinal(seed + 1)} (below)"
    )
    return (
        f"  {tricode}: seed {seed}{conf}, {above_str}, {below_str}, "
        f"{remaining} remaining → {reason_tag}"
    )


def _tighter_margin(data):
    """Return the smaller of games_back_from_above / games_ahead_of_below (None = inf)."""
    vals = [v for v in [data["games_back_from_above"], data["games_ahead_of_below"]] if v is not None]
    return min(vals) if vals else float("inf")


def filter_games_by_stake(games, standings):
    """
    Filters games to those where at least one team has playoff/play-in stake.

    A team has a stake if it can still improve its seed OR be caught by the
    team below it within the remaining games of the regular season.

    Games where a team_id is missing from standings are passed through with a warning.
    Returns the filtered list (same structure as input).
    """
    filtered = []

    for game in games:
        home_id = game["home_team_id"]
        away_id = game["away_team_id"]
        home_tri = game["home_tricode"]
        away_tri = game["away_tricode"]
        label = f"{away_tri} @ {home_tri}"

        # Handle missing standings data
        if home_id not in standings or away_id not in standings:
            missing = [tid for tid in (home_id, away_id) if tid not in standings]
            for tid in missing:
                print(f"[stake-filter] WARNING: no standings data for team_id={tid} — including game by default")
            filtered.append(game)
            continue

        home_data = standings[home_id]
        away_data = standings[away_id]

        home_stake, home_tag = _team_has_stake(home_data)
        away_stake, away_tag = _team_has_stake(away_data)

        if not home_stake and not away_stake:
            print(f"[stake-filter] {label} — skipped: neither team has a stake")
            print(_format_team_line(home_tri, home_data, home_tag))
            print(_format_team_line(away_tri, away_data, away_tag))
            continue

        # At least one team has a stake — include the game
        if home_stake and away_stake:
            if _tighter_margin(home_data) <= _tighter_margin(away_data):
                home_tag = home_tag + " (both)"
            else:
                away_tag = away_tag + " (both)"
            print(f"[stake-filter] {label} — included (both teams have stake)")
        else:
            print(f"[stake-filter] {label} — included")

        print(_format_team_line(home_tri, home_data, home_tag))
        print(_format_team_line(away_tri, away_data, away_tag))

        filtered.append(game)

    return filtered
```

- [ ] **Step 4: Run all filter tests**

```
pytest tests/test_engine.py -k "filter" -v
```

Expected: all 6 filter tests pass

- [ ] **Step 5: Run new filter tests to confirm no regressions in this task**

```
pytest tests/test_engine.py -k "filter or has_stake" -v
```

Expected: all stake-related tests pass. Note: pre-existing failures in `test_scrapers_nba.py` (import naming mismatch) and potentially other `test_engine.py` tests are out of scope for this task.

- [ ] **Step 6: Commit**

```bash
git add analysis/engine.py tests/test_engine.py
git commit -m "feat: add filter_games_by_stake() to analysis engine"
```

---

### Task 4: Wire filter into `main.py`

**Files:**
- Modify: `main.py`
- Test: `tests/test_engine.py` (wiring smoke test)

- [ ] **Step 1: Write the wiring smoke test**

Add below the filter tests in `tests/test_engine.py`. No new import needed — `patch` is already imported at the top of the file.

```python
def test_filter_games_by_stake_wiring_in_main():
    """
    Smoke test: filter_games_by_stake is called before get_projected_lineups
    when main() runs. Verifies the wiring order, not real standings data.
    """
    import main as main_module

    fake_games = [{
        "home_team_id": 1, "away_team_id": 2,
        "home_tricode": "HME", "away_tricode": "AWY",
    }]
    fake_standings = {
        1: {"team_id": 1, "seed": 8, "conference": "East",
            "games_back_from_above": 3.0, "games_ahead_of_below": 10.0, "games_remaining": 10},
        2: {"team_id": 2, "seed": 13, "conference": "East",
            "games_back_from_above": 12.0, "games_ahead_of_below": 5.0, "games_remaining": 6},
    }

    call_order = []

    with patch("main.get_todays_games", return_value=fake_games) as m_games, \
         patch("main.get_conference_standings", side_effect=lambda: call_order.append("standings") or fake_standings), \
         patch("main.filter_games_by_stake", side_effect=lambda g, s: call_order.append("filter") or g) as m_filter, \
         patch("main.get_projected_lineups", side_effect=lambda: call_order.append("lineups") or {}) as m_lineups, \
         patch("main.get_defense_vs_position", return_value={}), \
         patch("main.run_analysis", return_value=[]), \
         patch("main.get_event_ids", return_value={}), \
         patch("main.get_player_lines", return_value={}), \
         patch("main.format_results", return_value=""):
        main_module.main()

    # standings and filter must precede lineups
    assert call_order.index("standings") < call_order.index("lineups")
    assert call_order.index("filter") < call_order.index("lineups")
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_engine.py::test_filter_games_by_stake_wiring_in_main -v
```

Expected: `FAILED` — `ImportError: cannot import name 'get_conference_standings' from 'main'`

- [ ] **Step 3: Update `main.py`**

```python
from scrapers.nba import get_todays_games, get_conference_standings
from scrapers.rotowire import get_projected_lineups
from scrapers.fantasypros import get_defense_vs_position
from scrapers.odds import get_event_ids, get_player_lines
from analysis.engine import run_analysis, filter_games_by_stake
from output.formatter import format_results


def main():
    print("Fetching today's games...")
    games = get_todays_games()
    if not games:
        print("No games today.")
        return

    print(f"  {len(games)} games tonight\n")

    print("Fetching conference standings (stake filter)...")
    standings = get_conference_standings()

    games = filter_games_by_stake(games, standings)
    if not games:
        print("No games with playoff/play-in implications tonight.")
        return

    print(f"  {len(games)} games with stake tonight\n")

    print("Fetching projected lineups (RotoWire)...")
    lineups = get_projected_lineups()
    print(f"  {len(lineups)} teams loaded\n")

    print("Fetching Defense vs Position (FantasyPros)...")
    dvp = get_defense_vs_position()
    print("  Done\n")

    print("Running analysis...")
    candidates = run_analysis(games, lineups, dvp)

    print("Fetching betting lines (The Odds API)...")
    event_ids = get_event_ids(games)
    lines = get_player_lines(candidates, event_ids)
    for c in candidates:
        c["line"] = lines.get(c["player"])

    print("\n")
    print(format_results(candidates))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run wiring test**

```
pytest tests/test_engine.py::test_filter_games_by_stake_wiring_in_main -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```
pytest tests/ -v
```

Expected: all stake-related tests pass. Note: the pre-existing `test_scrapers_nba.py` import failure (`get_player_season_stats`) is expected and out of scope — do not fix it here.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_engine.py
git commit -m "feat: wire stake filter into main pipeline before lineup fetching"
```
