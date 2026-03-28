# Blowout Filter Design

**Date:** 2026-03-28
**Status:** Approved
**Scope:** Filter out games with extreme moneyline disparity before analysis

## Problem

The analysis engine currently has no mechanism to exclude lopsided matchups (blowouts). Games where one team is an overwhelming favorite (e.g., decimal odd ≤ 1.10) are unlikely to produce reliable prop bet opportunities because:

- Starters may rest or play reduced minutes in blowouts
- Game flow becomes unpredictable (garbage time, bench rotations)
- Betting lines are less reliable in extreme matchups

## Solution

Add a blowout filter that excludes games where any team's moneyline decimal odd is ≤ 1.10, applied early in the pipeline to save API calls.

## Design

### 1. New Scraper Function — `scrapers/odds.py`

**Current state:** `get_event_ids(games)` calls the FREE endpoint `/v4/sports/basketball_nba/events` and returns `{(away_tricode, home_tricode): event_id}`. This endpoint does **not** return odds data — only event metadata.

**New function:** `get_game_moneylines(games)`

A new function that calls `/v4/sports/basketball_nba/odds` with `markets=h2h&oddsFormat=decimal` to fetch moneyline odds. This endpoint **costs 1 request credit** but provides the h2h (moneyline) prices from all bookmakers.

```python
def get_game_moneylines(games):
    """
    Fetches moneyline (h2h) odds for today's NBA games.
    Returns {(away_tricode, home_tricode): lowest_odd} where lowest_odd
    is the minimum decimal price (the favorite) across all bookmakers.
    Returns float values. Empty dict on failure.
    """
```

**Extraction logic:**
- Call `/v4/sports/basketball_nba/odds?markets=h2h&oddsFormat=decimal`
- For each event, iterate over `bookmakers[].markets[]` where `market.key == "h2h"`
- Collect all `outcomes[].price` values (floats)
- Take `min()` to get the favorite's lowest odd across all bookmakers
- Map to tricode tuple using existing `TRICODE_TO_API_NAME` reverse lookup
- Only include games present in the `wanted` set (same pattern as `get_event_ids`)

**Return format:**

```python
{("BOS", "LAL"): 1.08, ("MIA", "NYK"): 1.45}
```

**Note:** `get_event_ids(games)` remains unchanged — it continues to return `{(away_tc, home_tc): event_id}` as before.

### 2. Engine Change — `analysis/engine.py`

**New constant at the top of the file:**

```python
BLOWOUT_ODD_THRESHOLD = 1.10
```

**New function:**

```python
def filter_games_by_blowout(games, moneylines):
    """
    Remove games where the favorite's moneyline odd is ≤ BLOWOUT_ODD_THRESHOLD.
    moneylines: {(away_tc, home_tc): float} from get_game_moneylines().
    Pipeline-position-agnostic: filters whatever list it receives.
    """
```

- For each game, builds the tuple key `(away_tricode, home_tricode)` and looks up `moneylines`
- If `lowest_odd is not None and lowest_odd <= BLOWOUT_ODD_THRESHOLD`: exclude with debug log
- If no odds data available for the game: **include** it (fail-open — avoid false exclusions)
- Logs follow existing codebase pattern with `" @ "` separator (spaces around `@`):
  - `[blowout-filter] BOS @ LAL — excluded (odd 1.08 ≤ 1.10)`
  - `[blowout-filter] MIA @ NYK — included (odd 1.45)`
  - `[blowout-filter] GSW @ SAC — included (no odds data)`

**Fail-open rationale:** Missing odds data should not penalize a game. Better to analyze a game unnecessarily than to miss a valid opportunity due to an API hiccup.

### 3. Pipeline Change — `analysis/pipeline.py`

**Current pipeline flow (abbreviated):**

```
1. get_todays_games()
2. filter_games_by_stake(games, standings)
3. Load lineups, DvP, pace...
4. run_analysis()
5. get_event_ids(games) + get_player_lines()
```

**New pipeline flow:**

```
1. get_todays_games()
2. get_game_moneylines(games)      ← NEW (1 API credit, all games)
3. filter_games_by_stake(games, standings)
4. filter_games_by_blowout(games, moneylines)  ← NEW
5. Load lineups, DvP, pace...
6. run_analysis()
7. get_event_ids(games) + get_player_lines()    ← unchanged
```

**Key details:**
- `get_game_moneylines(games)` is called with the **unfiltered** game list (before stake filter). This is intentional — we want odds for all games so the blowout filter can operate on the full set. The cost is 1 API credit regardless of how many games there are.
- `get_event_ids(games)` stays in its current position (after analysis, before player lines). It is **not moved**. Its signature, return format, and all consumers remain unchanged.
- If `get_game_moneylines()` fails (API error, missing key), it returns `{}` and the blowout filter becomes a no-op — all games pass through.

**Import changes in `pipeline.py`:**

```python
# Add to existing odds.py imports:
from scrapers.odds import get_event_ids, get_player_lines, get_game_moneylines

# Add to existing engine.py imports:
from analysis.engine import run_analysis, filter_games_by_stake, filter_games_by_blowout
```

## Files Changed

| File | Change |
|------|--------|
| `scrapers/odds.py` | New function `get_game_moneylines(games)` returning `{(away_tc, home_tc): float}` |
| `analysis/engine.py` | New constant `BLOWOUT_ODD_THRESHOLD = 1.10` + new function `filter_games_by_blowout(games, moneylines)` |
| `analysis/pipeline.py` | Add imports, call `get_game_moneylines()` before filters, call `filter_games_by_blowout()` after stake filter |

## Files NOT Changed

- `scrapers/odds.py` `get_event_ids()` — untouched, keeps current signature and return format
- `scrapers/odds.py` `get_player_lines()` — untouched
- `analysis/engine.py` scoring functions (PTS/AST/REB/3PT) — untouched
- `output/formatter.py` — no display changes
- `scrapers/nba.py`, `scrapers/rotowire.py`, `scrapers/fantasypros.py` — untouched
- Deduplication logic — untouched
- Stake filter — remains independent

## Behavior Examples

| Game | Lowest Odd | Result |
|------|-----------|--------|
| BOS @ LAL | 1.08 | Excluded: `[blowout-filter] BOS @ LAL — excluded (odd 1.08 ≤ 1.10)` |
| MIA @ NYK | 1.45 | Included: `[blowout-filter] MIA @ NYK — included (odd 1.45)` |
| PHX @ DEN | 1.10 | Excluded: `[blowout-filter] PHX @ DEN — excluded (odd 1.10 ≤ 1.10)` |
| GSW @ SAC | No data | Included: `[blowout-filter] GSW @ SAC — included (no odds data)` |

## API Cost

- `get_game_moneylines()` uses the `/v4/sports/basketball_nba/odds` endpoint which costs **1 request credit** per call
- This is a single call per pipeline run regardless of number of games
- The existing `/events` endpoint used by `get_event_ids()` remains free

## Threshold

The constant `BLOWOUT_ODD_THRESHOLD = 1.10` corresponds to approximately 90.9% implied probability. Games where the favorite's decimal odd is **≤** this value are excluded from analysis. The constant is defined at the top of `engine.py` for easy adjustment.
