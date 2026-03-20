# Stake Filter — Design Spec
**Date:** 2026-03-20

## Problem

As the NBA regular season approaches its end, many late-season games have no playoff or play-in implications for either team. These games tend to be low-effort, high-blowout-rate contests. Including them in the analysis wastes expensive API calls and degrades signal quality.

## Goal

Add a game-level filter that runs before player analysis. A game passes the filter if at least one of its two teams still has a mathematical stake in the outcome — either fighting to reach the play-in, maintain their seeding, or avoid falling out of a playoff position.

## Stake Definition

A team **has a stake** if it satisfies either of the following conditions:

| Condition | Formula | Meaning |
|---|---|---|
| `can_improve` | `games_back_from_above ≤ games_remaining` | Team can still reach the seed above them |
| `can_be_caught` | `games_ahead_of_below ≤ games_remaining` | Team below can still catch them |

`has_stake = can_improve OR can_be_caught`

Edge cases:
- Seed 1: `can_improve = False` (no seed above); only `can_be_caught` matters
- Seed 15: `can_be_caught = False` (no seed below); only `can_improve` matters

A **game passes the filter** if `has_stake` is True for at least one of its two teams.

## Data

### New scraper: `get_conference_standings()`

Location: `scrapers/nba.py`

Uses `LeagueStandingsV3` from `nba_api`. Returns `dict[team_id → StandingData]`:

```python
{
    1610612738: {
        "team_id": 1610612738,
        "conference": "East",
        "seed": 1,                      # position within conference (1–15)
        "wins": 58,
        "losses": 16,
        "games_remaining": 8,           # 82 - wins - losses
        "games_back_from_above": None,  # None for seed 1
        "games_ahead_of_below": 4.5,    # difference to seed 2
    },
    ...
}
```

`games_remaining = 82 - wins - losses`

Gaps between adjacent seeds are derived from the `GamesBehind` field (games back from conference leader), by computing the difference between consecutive seeds within each conference.

## Components

### `scrapers/nba.py`
- Add `get_conference_standings() → dict[int, dict]`

### `analysis/engine.py`
- Add `_team_has_stake(team_data: dict) → tuple[bool, str]`
  - Returns `(True, reason)` or `(False, reason)` for logging
- Add `filter_games_by_stake(games: list, standings: dict) → list`
  - Filters to games where at least one team has a stake
  - Logs each decision (included/skipped) with seed, games back, and reason

### `main.py`
- Fetch standings after `get_todays_games()`
- Call `filter_games_by_stake()` before any other scraping
- Early-exit with a clear message if no games pass the filter

## Pipeline Integration

```
get_todays_games()
    ↓
get_conference_standings()          ← new
filter_games_by_stake()             ← new (drops cold games early)
    ↓
get_projected_lineups()
get_defense_vs_position()
run_analysis()
get_player_lines()
format_results()
```

The filter runs before lineup and DvP fetching, avoiding wasted API calls for irrelevant games.

## Logging

Skipped game:
```
[stake-filter] MEM @ SAS — skipped: neither team has a stake
  MEM: seed 12E, 8.0 GB from 11th, 6 games remaining → eliminated
  SAS: seed 14W, 12.0 GB from 13th, 6 games remaining → eliminated
```

Included game:
```
[stake-filter] MIA @ CHI — included (MIA: seed 8E, can be caught by 9th within remaining games)
```

## Out of Scope

- No changes to `run_analysis()` signature or internals
- No changes to `scheduler.py`, `routers/`, or frontend
- No per-player stake weighting (this is a binary game-level gate)
