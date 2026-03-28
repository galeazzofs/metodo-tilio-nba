# Blowout Filter Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Filter out lopsided NBA games (moneyline odd ≤ 1.10) before running the analysis engine, saving API calls and avoiding unreliable prop picks.

**Architecture:** New scraper function `get_game_moneylines()` fetches h2h odds from The Odds API. New engine function `filter_games_by_blowout()` excludes games where the favorite's odd is ≤ threshold. Pipeline wires both into the flow between game fetch and lineup loading.

**Tech Stack:** Python, requests, The Odds API (`/v4/sports/basketball_nba/odds`), pytest

**Spec:** `docs/superpowers/specs/2026-03-28-blowout-filter-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `scrapers/odds.py` | Modify | Add `get_game_moneylines(games)` function |
| `analysis/engine.py` | Modify | Add `BLOWOUT_ODD_THRESHOLD` constant + `filter_games_by_blowout()` function |
| `analysis/pipeline.py` | Modify | Wire new imports, call moneylines + blowout filter |
| `tests/test_engine.py` | Modify | Add tests for `filter_games_by_blowout()` |
| `tests/test_odds.py` | Create | Add tests for `get_game_moneylines()` |
| `tests/test_pipeline.py` | Modify | Update pipeline orchestration test |

---

## Chunk 1: Engine — Blowout Filter Function

### Task 1: Write failing tests for `filter_games_by_blowout`

**Files:**
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Add imports and fixtures for blowout filter tests**

Append to the existing imports at `tests/test_engine.py:5-9`:

```python
from analysis.engine import (
    _score_player, run_analysis, _position_compatible, _team_has_stake,
    filter_games_by_stake, _ordinal, _score_player_ast, _score_player_reb,
    _score_player_3pt, _dedup_candidates,
    filter_games_by_blowout, BLOWOUT_ODD_THRESHOLD,
)
```

Add fixtures after the existing ones (after line ~26):

```python
# ---------------------------------------------------------------------------
# Blowout filter fixtures
# ---------------------------------------------------------------------------

GAME_BOS_LAL = {
    "home_tricode": "LAL", "away_tricode": "BOS",
    "home_team_id": 1, "away_team_id": 2,
}
GAME_MIA_NYK = {
    "home_tricode": "NYK", "away_tricode": "MIA",
    "home_team_id": 3, "away_team_id": 4,
}
GAME_GSW_SAC = {
    "home_tricode": "SAC", "away_tricode": "GSW",
    "home_team_id": 5, "away_team_id": 6,
}
```

- [ ] **Step 2: Write test — excludes game when odd equals threshold (boundary)**

```python
def test_blowout_filter_excludes_at_threshold():
    """Odd exactly equal to threshold (1.10) should be excluded."""
    games = [GAME_BOS_LAL]
    moneylines = {("BOS", "LAL"): 1.10}
    result = filter_games_by_blowout(games, moneylines)
    assert result == []
```

- [ ] **Step 3: Write test — excludes game when odd below threshold**

```python
def test_blowout_filter_excludes_below_threshold():
    """Odd below threshold (e.g. 1.05) should be excluded."""
    games = [GAME_BOS_LAL]
    moneylines = {("BOS", "LAL"): 1.05}
    result = filter_games_by_blowout(games, moneylines)
    assert result == []
```

- [ ] **Step 4: Write test — includes game when odd above threshold**

```python
def test_blowout_filter_includes_above_threshold():
    """Odd above threshold (e.g. 1.45) should be included."""
    games = [GAME_MIA_NYK]
    moneylines = {("MIA", "NYK"): 1.45}
    result = filter_games_by_blowout(games, moneylines)
    assert len(result) == 1
    assert result[0] is GAME_MIA_NYK
```

- [ ] **Step 5: Write test — includes game when no odds data (fail-open)**

```python
def test_blowout_filter_includes_when_no_odds_data():
    """Games without odds data should pass through (fail-open)."""
    games = [GAME_GSW_SAC]
    moneylines = {}  # no data for this game
    result = filter_games_by_blowout(games, moneylines)
    assert len(result) == 1
    assert result[0] is GAME_GSW_SAC
```

- [ ] **Step 6: Write test — mixed games filtering**

```python
def test_blowout_filter_mixed_games():
    """Multiple games: some excluded, some included."""
    games = [GAME_BOS_LAL, GAME_MIA_NYK, GAME_GSW_SAC]
    moneylines = {
        ("BOS", "LAL"): 1.08,   # excluded
        ("MIA", "NYK"): 1.45,   # included
        # GSW @ SAC: no data    # included (fail-open)
    }
    result = filter_games_by_blowout(games, moneylines)
    assert len(result) == 2
    assert GAME_BOS_LAL not in result
    assert GAME_MIA_NYK in result
    assert GAME_GSW_SAC in result
```

- [ ] **Step 7: Write test — log output format**

```python
def test_blowout_filter_logs_excluded_game(capsys):
    """Excluded games should log in the correct format."""
    games = [GAME_BOS_LAL]
    moneylines = {("BOS", "LAL"): 1.08}
    filter_games_by_blowout(games, moneylines)
    captured = capsys.readouterr()
    assert "[blowout-filter] BOS @ LAL" in captured.out
    assert "excluded" in captured.out
    assert "1.08" in captured.out
```

- [ ] **Step 8: Write test — threshold constant value**

```python
def test_blowout_threshold_value():
    """Threshold constant should be 1.10."""
    assert BLOWOUT_ODD_THRESHOLD == 1.10
```

- [ ] **Step 9: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -k "blowout" -v`
Expected: FAIL — `ImportError: cannot import name 'filter_games_by_blowout'`

- [ ] **Step 10: Commit failing tests**

```bash
git add tests/test_engine.py
git commit -m "test: add failing tests for blowout filter"
```

---

### Task 2: Implement `filter_games_by_blowout` in engine

**Files:**
- Modify: `analysis/engine.py`

- [ ] **Step 1: Add constant after existing constants (after line 36)**

At `analysis/engine.py`, after the `POSITION_COMPAT` dict (line 36), add:

```python
BLOWOUT_ODD_THRESHOLD = 1.10
```

- [ ] **Step 2: Add `filter_games_by_blowout` function after `filter_games_by_stake` (after line 240)**

Insert after `filter_games_by_stake()` ends at line 240:

```python
def filter_games_by_blowout(games, moneylines):
    """
    Remove games where the favorite's moneyline odd is <= BLOWOUT_ODD_THRESHOLD.

    moneylines: {(away_tc, home_tc): float} from get_game_moneylines().
    Pipeline-position-agnostic: filters whatever list it receives.
    Games with no odds data are included (fail-open).
    """
    filtered = []

    for game in games:
        away_tri = game["away_tricode"]
        home_tri = game["home_tricode"]
        label = f"{away_tri} @ {home_tri}"
        lowest_odd = moneylines.get((away_tri, home_tri))

        if lowest_odd is not None and lowest_odd <= BLOWOUT_ODD_THRESHOLD:
            print(f"[blowout-filter] {label} — excluded (odd {lowest_odd} <= {BLOWOUT_ODD_THRESHOLD})")
            continue

        if lowest_odd is None:
            print(f"[blowout-filter] {label} — included (no odds data)")
        else:
            print(f"[blowout-filter] {label} — included (odd {lowest_odd})")

        filtered.append(game)

    return filtered
```

- [ ] **Step 3: Run blowout filter tests**

Run: `python -m pytest tests/test_engine.py -k "blowout" -v`
Expected: All 7 tests PASS

- [ ] **Step 4: Run full engine test suite to check no regressions**

Run: `python -m pytest tests/test_engine.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add analysis/engine.py
git commit -m "feat: add blowout filter to exclude lopsided games (odd <= 1.10)"
```

---

## Chunk 2: Scraper — `get_game_moneylines` Function

### Task 3: Write failing tests for `get_game_moneylines`

**Files:**
- Create: `tests/test_odds.py`

- [ ] **Step 1: Create test file with fixtures and first test**

Create `tests/test_odds.py`:

```python
# tests/test_odds.py
import requests
from unittest.mock import patch, MagicMock
from scrapers.odds import get_game_moneylines

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GAMES = [
    {"away_tricode": "BOS", "home_tricode": "LAL"},
    {"away_tricode": "MIA", "home_tricode": "NYK"},
]

# Simulates The Odds API /odds response with h2h market
ODDS_API_RESPONSE = [
    {
        "away_team": "Boston Celtics",
        "home_team": "Los Angeles Lakers",
        "bookmakers": [
            {
                "key": "fanduel",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Boston Celtics", "price": 1.08},
                            {"name": "Los Angeles Lakers", "price": 9.50},
                        ],
                    }
                ],
            },
            {
                "key": "draftkings",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Boston Celtics", "price": 1.10},
                            {"name": "Los Angeles Lakers", "price": 8.00},
                        ],
                    }
                ],
            },
        ],
    },
    {
        "away_team": "Miami Heat",
        "home_team": "New York Knicks",
        "bookmakers": [
            {
                "key": "fanduel",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Miami Heat", "price": 2.10},
                            {"name": "New York Knicks", "price": 1.75},
                        ],
                    }
                ],
            },
        ],
    },
]


def _mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    mock.headers = {"x-requests-remaining": "450"}
    mock.raise_for_status = MagicMock()
    return mock
```

- [ ] **Step 2: Write test — returns correct moneylines**

```python
@patch("scrapers.odds._get_api_key", return_value="test-key")
@patch("scrapers.odds.requests.get")
def test_get_game_moneylines_returns_lowest_odds(mock_get, mock_key):
    mock_get.return_value = _mock_response(ODDS_API_RESPONSE)
    result = get_game_moneylines(GAMES)
    # BOS @ LAL: min(1.08, 1.10) = 1.08
    assert result[("BOS", "LAL")] == 1.08
    # MIA @ NYK: min(2.10, 1.75) = 1.75
    assert result[("MIA", "NYK")] == 1.75
```

- [ ] **Step 3: Write test — returns empty dict when no API key**

```python
@patch("scrapers.odds._get_api_key", return_value=None)
def test_get_game_moneylines_no_api_key(mock_key):
    result = get_game_moneylines(GAMES)
    assert result == {}
```

- [ ] **Step 4: Write test — returns empty dict on request failure**

```python
@patch("scrapers.odds._get_api_key", return_value="test-key")
@patch("scrapers.odds.requests.get", side_effect=requests.exceptions.ConnectionError("Network error"))
def test_get_game_moneylines_request_failure(mock_get, mock_key):
    result = get_game_moneylines(GAMES)
    assert result == {}
```

- [ ] **Step 5: Write test — only includes games in wanted set**

```python
@patch("scrapers.odds._get_api_key", return_value="test-key")
@patch("scrapers.odds.requests.get")
def test_get_game_moneylines_filters_to_wanted_games(mock_get, mock_key):
    mock_get.return_value = _mock_response(ODDS_API_RESPONSE)
    # Only ask for BOS @ LAL, not MIA @ NYK
    single_game = [{"away_tricode": "BOS", "home_tricode": "LAL"}]
    result = get_game_moneylines(single_game)
    assert ("BOS", "LAL") in result
    assert ("MIA", "NYK") not in result
```

- [ ] **Step 6: Write test — calls correct endpoint with correct params**

```python
@patch("scrapers.odds._get_api_key", return_value="test-key")
@patch("scrapers.odds.requests.get")
def test_get_game_moneylines_calls_correct_endpoint(mock_get, mock_key):
    mock_get.return_value = _mock_response([])
    get_game_moneylines(GAMES)
    call_args = mock_get.call_args
    assert "basketball_nba/odds" in call_args[0][0]
    assert call_args[1]["params"]["markets"] == "h2h"
    assert call_args[1]["params"]["oddsFormat"] == "decimal"
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `python -m pytest tests/test_odds.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_game_moneylines'`

- [ ] **Step 8: Commit failing tests**

```bash
git add tests/test_odds.py
git commit -m "test: add failing tests for get_game_moneylines scraper"
```

---

### Task 4: Implement `get_game_moneylines` in scraper

**Files:**
- Modify: `scrapers/odds.py`

- [ ] **Step 1: Add `get_game_moneylines` function after `get_event_ids` (after line 104)**

Insert at `scrapers/odds.py` after line 104:

```python
def get_game_moneylines(games):
    """
    Fetches moneyline (h2h) odds for today's NBA games.

    Returns {(away_tricode, home_tricode): lowest_odd} where lowest_odd
    is the minimum decimal price (the favorite) across all bookmakers.
    Returns float values. Empty dict on failure.
    Costs 1 API request credit per call.
    """
    api_key = _get_api_key()
    if not api_key:
        print("  [odds] WARNING: ODDS_API_KEY not set — skipping moneylines")
        return {}

    wanted = {
        (g["away_tricode"], g["home_tricode"])
        for g in games
        if g.get("away_tricode") and g.get("home_tricode")
    }

    try:
        resp = requests.get(
            f"{BASE_URL}/sports/basketball_nba/odds",
            params={
                "apiKey": api_key,
                "markets": "h2h",
                "oddsFormat": "decimal",
            },
            timeout=10,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"  [odds] WARNING: could not fetch moneylines — {e}")
        return {}

    print(f"  [odds] moneylines — requests remaining: {resp.headers.get('x-requests-remaining', 'unknown')}")

    api_events = resp.json()
    name_to_tricode = {v: k for k, v in TRICODE_TO_API_NAME.items()}

    result = {}
    for event in api_events:
        away_api = event.get("away_team", "")
        home_api = event.get("home_team", "")
        away_tc = name_to_tricode.get(away_api)
        home_tc = name_to_tricode.get(home_api)

        if not away_tc or not home_tc or (away_tc, home_tc) not in wanted:
            continue

        # Collect all h2h prices across bookmakers
        all_prices = []
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for outcome in market.get("outcomes", []):
                    price = outcome.get("price")
                    if price is not None:
                        all_prices.append(float(price))

        if all_prices:
            result[(away_tc, home_tc)] = min(all_prices)

    return result
```

- [ ] **Step 2: Run odds tests**

Run: `python -m pytest tests/test_odds.py -v`
Expected: All 5 tests PASS

- [ ] **Step 3: Commit**

```bash
git add scrapers/odds.py
git commit -m "feat: add get_game_moneylines scraper for blowout detection"
```

---

## Chunk 3: Pipeline Wiring + Integration

### Task 5: Update pipeline to wire blowout filter

**Files:**
- Modify: `analysis/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Update imports in `analysis/pipeline.py`**

Change line 8 from:
```python
from scrapers.odds import get_event_ids, get_player_lines
```
to:
```python
from scrapers.odds import get_event_ids, get_player_lines, get_game_moneylines
```

Change line 10 from:
```python
from analysis.engine import run_analysis, filter_games_by_stake
```
to:
```python
from analysis.engine import run_analysis, filter_games_by_stake, filter_games_by_blowout
```

- [ ] **Step 2: Add moneylines fetch and blowout filter to pipeline**

In `run_pipeline()`, insert **immediately after** `print(f"  {len(games)} jogos esta noite")` (before the stake filter section):

```python
    print("Buscando moneylines para filtro de blowout...")
    moneylines = get_game_moneylines(games)
    print(f"  {len(moneylines)} jogos com odds carregados")
```

Then, insert **immediately after** `print(f"  {len(games)} jogos relevantes")` (after the stake filter block ends — note line numbers will have shifted from the insertion above):

```python
    print("Filtrando jogos com disparidade extrema (blowout)...")
    games = filter_games_by_blowout(games, moneylines)
    if not games:
        print("  Todos os jogos restantes foram filtrados por blowout.")
        return None, games
    print(f"  {len(games)} jogos após filtro de blowout")
```

- [ ] **Step 3: Update pipeline orchestration test in `tests/test_pipeline.py`**

The existing test at line 4-21 needs two new mocks. Update to:

```python
@patch("analysis.pipeline.get_player_lines", return_value={})
@patch("analysis.pipeline.get_event_ids", return_value={})
@patch("analysis.pipeline.run_analysis", return_value={"pts": [], "ast": [], "reb": [], "three_pt": []})
@patch("analysis.pipeline.get_team_pace", return_value=({}, 99.0))
@patch("analysis.pipeline.get_team_defense_tracking", return_value=None)
@patch("analysis.pipeline.get_team_defense_vs_position", return_value={})
@patch("analysis.pipeline.get_defense_vs_position", return_value={})
@patch("analysis.pipeline.get_projected_lineups", return_value={})
@patch("analysis.pipeline.filter_games_by_blowout", side_effect=lambda g, m: g)
@patch("analysis.pipeline.filter_games_by_stake", side_effect=lambda g, s: g)
@patch("analysis.pipeline.get_conference_standings", return_value={})
@patch("analysis.pipeline.get_game_moneylines", return_value={})
@patch("analysis.pipeline.get_todays_games", return_value=[{"game_id": "1"}])
def test_pipeline_orchestrates_all_steps(
    mock_games, mock_moneylines, mock_standings, mock_stake,
    mock_blowout, mock_lineups, mock_dvp, mock_team_def,
    mock_tracking, mock_pace, mock_analysis, mock_events, mock_lines
):
    """Bottom-up: first @patch arg = bottom decorator (get_todays_games)."""
    from analysis.pipeline import run_pipeline
    stats, games = run_pipeline()
    assert stats is not None
    assert isinstance(stats, dict)
    mock_moneylines.assert_called_once()  # get_game_moneylines
    mock_blowout.assert_called_once()     # filter_games_by_blowout
    mock_analysis.assert_called_once()    # run_analysis
```

- [ ] **Step 4: Add test for blowout filter removing all games**

Append to `tests/test_pipeline.py`:

```python
@patch("analysis.pipeline.get_game_moneylines", return_value={})
@patch("analysis.pipeline.get_conference_standings", return_value={})
@patch("analysis.pipeline.filter_games_by_stake", side_effect=lambda g, s: g)
@patch("analysis.pipeline.filter_games_by_blowout", return_value=[])
@patch("analysis.pipeline.get_todays_games", return_value=[{"game_id": "1"}])
def test_pipeline_returns_none_when_all_blowout(
    mock_games, mock_blowout, mock_stake, mock_standings, mock_moneylines
):
    from analysis.pipeline import run_pipeline
    stats, games = run_pipeline()
    assert stats is None
```

- [ ] **Step 5: Run all pipeline tests**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add analysis/pipeline.py tests/test_pipeline.py
git commit -m "feat: wire blowout filter into analysis pipeline"
```
