# Betting Lines Enrichment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After the analysis engine returns its top 5 candidates, fetch each player's points over/under line from The Odds API (EU region) and display the consensus line in the formatted output.

**Architecture:** A new `scrapers/odds.py` module handles all Odds API communication. `main.py` calls it after `run_analysis()` to enrich candidates with a `line` field. `output/formatter.py` renders that field. No existing modules are restructured.

**Tech Stack:** Python stdlib (`statistics`), `requests` (already in use), `python-dotenv` (new dep), `pytest` (new dep), The Odds API v4.

> **Note on test files:** `test_*.py` is in `.gitignore` — test files are intentionally not committed in this project. Do not attempt to `git add` test files; they are local-only.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `requirements.txt` | Modify | Add `python-dotenv` and `pytest` |
| `.env` | Create | Store `ODDS_API_KEY` |
| `.env.example` | Create | Document required env vars |
| `scrapers/odds.py` | Create | `TRICODE_TO_API_NAME` lookup, `get_event_ids()`, `get_player_lines()` |
| `test_odds.py` | Create | Unit tests for all odds functions (local-only, not committed) |
| `main.py` | Modify | Call odds functions after `run_analysis()`, enrich candidates |
| `output/formatter.py` | Modify | Render `Line:` field per candidate |

---

## Chunk 1: `scrapers/odds.py` — setup, tests, implementation

### Task 1: Add dependencies and environment setup

**Files:**
- Modify: `requirements.txt`
- Create: `.env`
- Create: `.env.example`

- [ ] **Step 1: Add python-dotenv and pytest to requirements.txt**

Open `requirements.txt` and add two lines:

```
python-dotenv
pytest
```

Final file:
```
nba_api
requests
beautifulsoup4
playwright
pandas
fastapi
uvicorn[standard]
firebase-admin
python-multipart
google-generativeai
python-dotenv
pytest
```

- [ ] **Step 2: Install the new dependencies**

```bash
pip install python-dotenv pytest
```

Expected: installs without errors.

- [ ] **Step 3: Create .env.example**

Create `.env.example` at the project root:

```
# The Odds API — get a free key at https://the-odds-api.com
ODDS_API_KEY=your_key_here
```

- [ ] **Step 4: Create .env with your real API key**

Create `.env` at the project root. This file is already in `.gitignore` and must never be committed.

```
ODDS_API_KEY=paste_your_real_key_here
```

Verify `.gitignore` already excludes it:
```bash
grep "^.env$" .gitignore
```

Expected: prints `.env`.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example
git commit -m "chore: add python-dotenv and pytest dependencies"
```

---

### Task 2: Write failing tests for `get_event_ids`

**Files:**
- Create: `test_odds.py` (local-only, not committed)

- [ ] **Step 1: Create test_odds.py**

Create `test_odds.py` at the project root:

```python
"""Tests for scrapers/odds.py"""

import requests
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_events_response(events):
    """Build a mock requests.Response for the /events endpoint."""
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = events
    mock.headers = {"x-requests-remaining": "490"}
    mock.status_code = 200
    return mock


# ---------------------------------------------------------------------------
# get_event_ids
# ---------------------------------------------------------------------------

SAMPLE_EVENTS = [
    {
        "id": "abc123",
        "home_team": "Oklahoma City Thunder",
        "away_team": "Boston Celtics",
    },
    {
        "id": "def456",
        "home_team": "Los Angeles Lakers",
        "away_team": "Los Angeles Clippers",
    },
]

SAMPLE_GAMES = [
    {"home_tricode": "OKC", "away_tricode": "BOS"},
    {"home_tricode": "LAL", "away_tricode": "LAC"},
]


def test_get_event_ids_returns_correct_mapping():
    """Maps (away_tricode, home_tricode) tuples to event IDs."""
    from scrapers.odds import get_event_ids

    with patch("scrapers.odds.requests.get") as mock_get:
        mock_get.return_value = _make_events_response(SAMPLE_EVENTS)

        result = get_event_ids(SAMPLE_GAMES)

    assert result == {
        ("BOS", "OKC"): "abc123",
        ("LAC", "LAL"): "def456",
    }


def test_get_event_ids_disambiguates_la_teams():
    """LAL and LAC must never be swapped."""
    from scrapers.odds import get_event_ids

    with patch("scrapers.odds.requests.get") as mock_get:
        mock_get.return_value = _make_events_response(SAMPLE_EVENTS)

        result = get_event_ids(SAMPLE_GAMES)

    assert result[("LAC", "LAL")] == "def456"
    assert ("LAL", "LAC") not in result


def test_get_event_ids_returns_empty_on_http_error():
    """HTTP errors must be swallowed and return {}."""
    from scrapers.odds import get_event_ids

    with patch("scrapers.odds.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.RequestException("timeout")

        result = get_event_ids(SAMPLE_GAMES)

    assert result == {}


def test_get_event_ids_raises_on_missing_api_key(monkeypatch):
    """RuntimeError raised at call time if ODDS_API_KEY is not set."""
    from scrapers.odds import get_event_ids

    monkeypatch.delenv("ODDS_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ODDS_API_KEY"):
        get_event_ids(SAMPLE_GAMES)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest test_odds.py -v
```

Expected: `ModuleNotFoundError: No module named 'scrapers.odds'` — confirms tests are wired correctly.

---

### Task 3: Implement `get_event_ids`

**Files:**
- Create: `scrapers/odds.py`

- [ ] **Step 1: Create scrapers/odds.py**

```python
import os
import statistics
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.the-odds-api.com/v4"

TRICODE_TO_API_NAME = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}


def _get_api_key():
    key = os.getenv("ODDS_API_KEY")
    if not key:
        raise RuntimeError(
            "ODDS_API_KEY is not set. Add it to your .env file. "
            "Get a free key at https://the-odds-api.com"
        )
    return key


def get_event_ids(games):
    """
    Fetches today's NBA events from The Odds API and maps them to tricodes.

    Only returns event IDs for games present in the input `games` list.
    Returns {(away_tricode, home_tricode): event_id}.
    Returns {} on any HTTP error (all lines will show as N/A).
    """
    api_key = _get_api_key()

    # Build set of today's games we care about, keyed by (away_tc, home_tc)
    wanted = {
        (g["away_tricode"], g["home_tricode"])
        for g in games
        if g.get("away_tricode") and g.get("home_tricode")
    }

    try:
        resp = requests.get(
            f"{BASE_URL}/sports/basketball_nba/events",
            params={"apiKey": api_key},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"  [odds] WARNING: could not fetch events — {e}")
        return {}

    print(f"  [odds] requests remaining: {resp.headers.get('x-requests-remaining', 'unknown')}")

    api_events = resp.json()

    # Build reverse lookup: API name → tricode
    name_to_tricode = {v: k for k, v in TRICODE_TO_API_NAME.items()}

    result = {}
    for event in api_events:
        away_api = event.get("away_team", "")
        home_api = event.get("home_team", "")
        away_tc = name_to_tricode.get(away_api)
        home_tc = name_to_tricode.get(home_api)
        if away_tc and home_tc and (away_tc, home_tc) in wanted:
            result[(away_tc, home_tc)] = event["id"]

    return result
```

- [ ] **Step 2: Run get_event_ids tests**

```bash
pytest test_odds.py::test_get_event_ids_returns_correct_mapping test_odds.py::test_get_event_ids_disambiguates_la_teams test_odds.py::test_get_event_ids_returns_empty_on_http_error test_odds.py::test_get_event_ids_raises_on_missing_api_key -v
```

Expected: all 4 PASS.

- [ ] **Step 3: Commit**

```bash
git add scrapers/odds.py
git commit -m "feat(odds): implement get_event_ids with tricode lookup"
```

---

### Task 4: Write failing tests for `get_player_lines`

**Files:**
- Modify: `test_odds.py`

- [ ] **Step 1: Append tests to test_odds.py**

Add the following below the existing tests in `test_odds.py`:

```python
# ---------------------------------------------------------------------------
# get_player_lines
# ---------------------------------------------------------------------------

def _make_odds_response(bookmakers):
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = {"bookmakers": bookmakers}
    mock.headers = {"x-requests-remaining": "485"}
    mock.status_code = 200
    return mock


def _make_bookmaker(name, player_name, point):
    return {
        "key": name,
        "markets": [
            {
                "key": "player_points",
                "outcomes": [
                    {"description": player_name, "name": "Over", "point": point},
                    {"description": player_name, "name": "Under", "point": point},
                ],
            }
        ],
    }


SAMPLE_CANDIDATES = [
    {"player": "Cason Wallace", "game": "BOS @ OKC"},
]

SAMPLE_EVENT_IDS = {
    ("BOS", "OKC"): "abc123",
}


def test_get_player_lines_returns_consensus_line():
    """Returns the mode line when all books agree."""
    from scrapers.odds import get_player_lines

    bookmakers = [
        _make_bookmaker("bet365", "Cason Wallace", 14.5),
        _make_bookmaker("unibet", "Cason Wallace", 14.5),
        _make_bookmaker("betfair", "Cason Wallace", 14.5),
    ]

    with patch("scrapers.odds.requests.get") as mock_get:
        mock_get.return_value = _make_odds_response(bookmakers)

        result = get_player_lines(SAMPLE_CANDIDATES, SAMPLE_EVENT_IDS)

    assert result == {"Cason Wallace": 14.5}


def test_get_player_lines_uses_median_when_no_consensus():
    """Falls back to median when books are split (multimode tie)."""
    from scrapers.odds import get_player_lines

    # Each _make_bookmaker produces both an Over and Under outcome at the same
    # point, so 2 books at 14.5 → [14.5, 14.5, 14.5, 14.5] and 2 books at
    # 15.5 → [15.5, 15.5, 15.5, 15.5]. Full list: 8 values, median = 15.0.
    bookmakers = [
        _make_bookmaker("bet365", "Cason Wallace", 14.5),
        _make_bookmaker("unibet", "Cason Wallace", 14.5),
        _make_bookmaker("betfair", "Cason Wallace", 15.5),
        _make_bookmaker("pinnacle", "Cason Wallace", 15.5),
    ]

    with patch("scrapers.odds.requests.get") as mock_get:
        mock_get.return_value = _make_odds_response(bookmakers)

        result = get_player_lines(SAMPLE_CANDIDATES, SAMPLE_EVENT_IDS)

    assert result == {"Cason Wallace": 15.0}


def test_get_player_lines_case_insensitive_name_match():
    """Player name match is case-insensitive."""
    from scrapers.odds import get_player_lines

    bookmakers = [
        _make_bookmaker("bet365", "cason wallace", 14.5),
    ]

    with patch("scrapers.odds.requests.get") as mock_get:
        mock_get.return_value = _make_odds_response(bookmakers)

        result = get_player_lines(SAMPLE_CANDIDATES, SAMPLE_EVENT_IDS)

    assert result == {"Cason Wallace": 14.5}


def test_get_player_lines_returns_none_for_unknown_player():
    """Players not listed by any bookmaker are absent from the result."""
    from scrapers.odds import get_player_lines

    bookmakers = [
        _make_bookmaker("bet365", "Someone Else", 20.5),
    ]

    with patch("scrapers.odds.requests.get") as mock_get:
        mock_get.return_value = _make_odds_response(bookmakers)

        result = get_player_lines(SAMPLE_CANDIDATES, SAMPLE_EVENT_IDS)

    assert "Cason Wallace" not in result


def test_get_player_lines_deduplicates_game_api_calls():
    """Two candidates in the same game produce only one API call."""
    from scrapers.odds import get_player_lines

    candidates = [
        {"player": "Cason Wallace", "game": "BOS @ OKC"},
        {"player": "Shai Gilgeous-Alexander", "game": "BOS @ OKC"},
    ]
    bookmakers = [
        _make_bookmaker("bet365", "Cason Wallace", 14.5),
        _make_bookmaker("bet365", "Shai Gilgeous-Alexander", 32.5),
    ]

    with patch("scrapers.odds.requests.get") as mock_get:
        mock_get.return_value = _make_odds_response(bookmakers)

        get_player_lines(candidates, SAMPLE_EVENT_IDS)

    assert mock_get.call_count == 1


def test_get_player_lines_returns_empty_on_http_error():
    """HTTP errors return {} without raising."""
    from scrapers.odds import get_player_lines

    with patch("scrapers.odds.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.RequestException("timeout")

        result = get_player_lines(SAMPLE_CANDIDATES, SAMPLE_EVENT_IDS)

    assert result == {}


def test_get_player_lines_returns_empty_on_quota_exceeded():
    """HTTP 429 returns {} without raising."""
    from scrapers.odds import get_player_lines

    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch("scrapers.odds.requests.get") as mock_get:
        mock_get.return_value = mock_resp

        result = get_player_lines(SAMPLE_CANDIDATES, SAMPLE_EVENT_IDS)

    assert result == {}


def test_get_player_lines_returns_empty_when_no_event_id():
    """If a game has no event_id match, result is empty."""
    from scrapers.odds import get_player_lines

    result = get_player_lines(SAMPLE_CANDIDATES, event_ids={})

    assert result == {}
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
pytest test_odds.py -k "player_lines" -v
```

Expected: all 8 FAIL with `ImportError` or `AttributeError` — `get_player_lines` doesn't exist yet.

---

### Task 5: Implement `get_player_lines`

**Files:**
- Modify: `scrapers/odds.py`

- [ ] **Step 1: Append get_player_lines to scrapers/odds.py**

Add this function at the bottom of `scrapers/odds.py`:

```python
def get_player_lines(candidates, event_ids):
    """
    Fetches the consensus points over/under line for each candidate.

    Returns {player_name: line_value}.
    Players not found in any bookmaker's props are omitted (shown as N/A).
    Returns {} on any HTTP error or quota exhaustion.
    """
    api_key = _get_api_key()

    # Group candidates by game to deduplicate API calls
    games_to_players = {}
    for c in candidates:
        game_str = c["game"]  # e.g. "BOS @ OKC"
        games_to_players.setdefault(game_str, []).append(c["player"])

    result = {}

    for game_str, player_names in games_to_players.items():
        away_tc, home_tc = game_str.split(" @ ")
        event_id = event_ids.get((away_tc, home_tc))
        if not event_id:
            continue

        try:
            resp = requests.get(
                f"{BASE_URL}/sports/basketball_nba/events/{event_id}/odds",
                params={
                    "apiKey": api_key,
                    "regions": "eu",
                    "markets": "player_points",
                },
                timeout=10,
            )
            if resp.status_code == 429:
                print("[odds] quota exceeded — HTTP 429")
                return {}
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"  [odds] WARNING: could not fetch odds for {game_str} — {e}")
            return {}

        data = resp.json()
        bookmakers = data.get("bookmakers", [])

        # Collect lines per player across all bookmakers
        player_values = {name: [] for name in player_names}

        for bookmaker in bookmakers:
            for market in bookmaker.get("markets", []):
                if market.get("key") != "player_points":
                    continue
                for outcome in market.get("outcomes", []):
                    desc = outcome.get("description", "")
                    point = outcome.get("point")
                    if point is None:
                        continue
                    for name in player_names:
                        if name.lower() in desc.lower():
                            player_values[name].append(float(point))

        for name, values in player_values.items():
            if not values:
                continue
            modes = statistics.multimode(values)
            if len(modes) == 1:
                result[name] = modes[0]
            else:
                result[name] = statistics.median(values)

    return result
```

- [ ] **Step 2: Run all odds tests**

```bash
pytest test_odds.py -v
```

Expected: all 12 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add scrapers/odds.py
git commit -m "feat(odds): implement get_player_lines with consensus logic"
```

---

## Chunk 2: Integration into main.py and formatter.py

### Task 6: Wire odds into main.py

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add import at the top of main.py**

Current imports:
```python
from scrapers.nba import get_todays_games
from scrapers.rotowire import get_projected_lineups
from scrapers.fantasypros import get_defense_vs_position
from analysis.engine import run_analysis
from output.formatter import format_results
```

Add one line:
```python
from scrapers.odds import get_event_ids, get_player_lines
```

- [ ] **Step 2: Add enrichment block after run_analysis()**

Current end of `main()`:
```python
    print("Running analysis...")
    candidates = run_analysis(games, lineups, dvp)

    print("\n")
    print(format_results(candidates))
```

Replace with:
```python
    print("Running analysis...")
    candidates = run_analysis(games, lineups, dvp)

    print("Fetching betting lines (The Odds API)...")
    event_ids = get_event_ids(games)
    lines = get_player_lines(candidates, event_ids)
    for c in candidates:
        c["line"] = lines.get(c["player"])

    print("\n")
    print(format_results(candidates))
```

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: enrich analysis candidates with betting lines"
```

---

### Task 7: Update formatter to display the line

**Files:**
- Modify: `output/formatter.py`

- [ ] **Step 1: Add Line display to format_results**

In `output/formatter.py`, find this block (around line 34):

```python
            icon = RATING_ICON.get(p["rating"], "")
            lines.append(f"  #{rank} {p['player']} ({p['position']}) - {p['team']}")
            lines.append(f"      {icon} {p['rating']}")

            # Signals
            for signal in p["signals"]:
```

Replace with:

```python
            icon = RATING_ICON.get(p["rating"], "")
            lines.append(f"  #{rank} {p['player']} ({p['position']}) - {p['team']}")
            lines.append(f"      {icon} {p['rating']}")
            line_str = f"{p['line']} pts" if p.get("line") is not None else "N/A"
            lines.append(f"      Line: {line_str}")

            # Signals
            for signal in p["signals"]:
```

- [ ] **Step 2: Smoke-test the formatter in isolation**

```bash
python -c "
from output.formatter import format_results
candidates = [{
    'player': 'Test Player', 'position': 'SG', 'team': 'Thunder',
    'game': 'BOS @ OKC', 'score': 7, 'rating': 'VERY FAVORABLE',
    'signals': ['Good matchup (DvP #5)'], 'recent_stats': None, 'line': 14.5
}]
print(format_results(candidates))
"
```

Expected: output includes `Line: 14.5 pts` between the rating line and the signals.

Then test the `None` case:

```bash
python -c "
from output.formatter import format_results
candidates = [{
    'player': 'Test Player', 'position': 'SG', 'team': 'Thunder',
    'game': 'BOS @ OKC', 'score': 7, 'rating': 'VERY FAVORABLE',
    'signals': ['Good matchup (DvP #5)'], 'recent_stats': None, 'line': None
}]
print(format_results(candidates))
"
```

Expected: `Line: N/A`.

- [ ] **Step 3: Commit**

```bash
git add output/formatter.py
git commit -m "feat(formatter): display betting line per candidate"
```

---

### Task 8: End-to-end smoke test

- [ ] **Step 1: Run the full pipeline**

```bash
python main.py
```

Expected flow:
```
Fetching today's games...
  N games tonight

Fetching projected lineups (RotoWire)...
  N teams loaded

Fetching Defense vs Position (FantasyPros)...
  Done

Running analysis...
  ...

Fetching betting lines (The Odds API)...
  [odds] requests remaining: NNN

========================================================
   NBA TONIGHT - TOP PLAYS
========================================================

  BOS @ OKC
  ------------------------------
  #1 Cason Wallace (SG) - Thunder
      ** VERY FAVORABLE
      Line: 14.5 pts
      - Good matchup vs Celtics (DvP #5, ...)
      Stats (last 15g): ...
```

If no games today, the pipeline exits before reaching the odds step — expected.
If the API key is wrong: `RuntimeError: ODDS_API_KEY is not set.`

- [ ] **Step 2: Run the full test suite**

```bash
pytest test_odds.py -v
```

Expected: all 12 odds tests pass. If you have other local test files (`test_nba.py`, `test_fantasypros.py`), add them to the command — they are local-only and may or may not exist on your machine.

- [ ] **Step 3: Final commit**

```bash
git add .
git commit -m "feat: betting lines enrichment complete"
```
