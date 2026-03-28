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

### 1. Scraper Change — `scrapers/odds.py`

**Function:** `get_event_ids()`

This function already calls the free endpoint `/v4/sports/basketball_nba/odds` and currently returns only event IDs. The response already contains moneyline odds from bookmakers.

**Change:** Extract the lowest decimal odd (the favorite's best price across all bookmakers) from each game's `h2h` market.

**Return format change:**

```python
# Before:
{"BOS@LAL": "event_abc123"}

# After:
{
    "BOS@LAL": {
        "event_id": "event_abc123",
        "lowest_odd": 1.08
    }
}
```

**Extraction logic:**
- Iterate over `bookmakers[].markets[]` where `market.key == "h2h"`
- Collect all `outcomes[].price` values
- Take `min()` to get the favorite's lowest odd across all bookmakers

### 2. Engine Change — `analysis/engine.py`

**New constant:**

```python
BLOWOUT_ODD_THRESHOLD = 1.10
```

Placed at the top of the file, easy to adjust.

**New function:** `filter_games_by_blowout(games, event_data)`

- Iterates over games that passed the stake filter
- For each game, looks up `lowest_odd` from `event_data`
- If `lowest_odd <= BLOWOUT_ODD_THRESHOLD`: exclude with debug log
- If no odds data available: include the game (fail-open, avoid false exclusions)
- Logs follow existing pattern: `[blowout-filter] BOS@LAL — excluded (odd 1.08 ≤ 1.10)`

**Fail-open rationale:** Missing odds data should not penalize a game. Better to analyze a game unnecessarily than to miss a valid opportunity.

### 3. Pipeline Change — `analysis/pipeline.py`

**Reorder:** Move `get_event_ids()` call earlier in the pipeline (before filters).

**New pipeline flow:**

```
1. get_todays_games()
2. get_event_ids()              ← moved up (free API call)
3. filter_games_by_stake()
4. filter_games_by_blowout()    ← NEW, uses data from step 2
5. Load lineups, DvP, pace...
6. run_analysis()
7. get_player_lines()           ← reuses event_ids from step 2
```

**Adaptations:**
- `get_player_lines()` must extract `event_id` from the new nested format instead of using the value directly
- If `get_event_ids()` fails entirely, blowout filter is a no-op and pipeline continues

## Files Changed

| File | Change |
|------|--------|
| `scrapers/odds.py` | `get_event_ids()` returns `{game_key: {event_id, lowest_odd}}` |
| `analysis/engine.py` | New `BLOWOUT_ODD_THRESHOLD = 1.10` constant + `filter_games_by_blowout()` function |
| `analysis/pipeline.py` | Reorder `get_event_ids()` earlier, add blowout filter call, adapt `get_player_lines()` to new format |

## Files NOT Changed

- `analysis/engine.py` scoring functions (PTS/AST/REB/3PT) — untouched
- `output/formatter.py` — no display changes
- `scrapers/nba.py`, `scrapers/rotowire.py`, `scrapers/fantasypros.py` — untouched
- Deduplication logic — untouched
- Stake filter — remains independent

## Behavior Examples

| Game | Lowest Odd | Result |
|------|-----------|--------|
| BOS @ LAL | 1.08 | Excluded: `[blowout-filter] BOS@LAL — excluded (odd 1.08 ≤ 1.10)` |
| MIA @ NYK | 1.45 | Included: `[blowout-filter] MIA@NYK — included (odd 1.45)` |
| PHX @ DEN | 1.10 | Excluded: `[blowout-filter] PHX@DEN — excluded (odd 1.10 ≤ 1.10)` |
| GSW @ SAC | No data | Included: `[blowout-filter] GSW@SAC — included (no odds data)` |

## Threshold

The threshold `BLOWOUT_ODD_THRESHOLD = 1.10` corresponds to approximately 90.9% implied probability. Games at or below this threshold represent matchups where one team is an overwhelming favorite and are excluded from analysis. The constant is defined at the top of `engine.py` for easy adjustment.
