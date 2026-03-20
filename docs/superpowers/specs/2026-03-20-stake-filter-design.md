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

A team is **eliminated** when both `can_improve = False` AND `can_be_caught = False`.

Edge cases:
- Seed 1: `games_back_from_above = None` → `can_improve = False`; only `can_be_caught` matters
- Seed 15: `games_ahead_of_below = None` → `can_be_caught = False`; only `can_improve` matters
- Tied seeds: when two teams share the same `ConferenceGamesBack`, the gap between them is `0.0`, so `can_improve = True` for the lower-ranked team. This is correct behavior. The filter has its strongest effect only in the final ~10 games of the season when ties resolve.

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

Gaps between adjacent seeds are derived from the `ConferenceGamesBack` field (games back from conference leader within each conference), by computing the difference between consecutive seeds. The conference leader's `ConferenceGamesBack` is returned by the API as `None` or `"-"` — treat it as `0.0` when computing gaps.

If a `team_id` from `get_todays_games()` is absent from the standings dict (e.g., API lag, exhibition game), treat the game as **included** (pass-through) and log a warning:
```
[stake-filter] WARNING: no standings data for team_id=XXXX — including game by default
```

## Components

### `scrapers/nba.py`
- Add `get_conference_standings() → dict[int, dict]`
  - Calls `time.sleep(DELAY)` at the top, following the existing convention in this module

### `analysis/engine.py`
- Add `_team_has_stake(team_data: dict) → tuple[bool, str]`
  - Returns `(True, reason_tag)` or `(False, reason_tag)` where `reason_tag` is a short label: `"can improve"`, `"can be caught"`, or `"eliminated"`
  - `filter_games_by_stake` is responsible for assembling the full log line from the tag and team data
- Add `filter_games_by_stake(games: list, standings: dict) → list`
  - Uses `home_team_id`/`away_team_id` to look up each team in `standings`; uses `home_tricode`/`away_tricode` for display labels in log lines
  - Logs each decision (included/skipped) with both `games_back_from_above` and `games_ahead_of_below` values for each team
  - When both teams have a stake, log detail lines for **both** teams as normal. Select the team with the tighter margin and append `" (both)"` only to that team's reason tag — e.g., `can improve (both)` or `can be caught (both)`. Tighter margin = `min(v for v in [games_back_from_above, games_ahead_of_below] if v is not None)` (treat `None` as infinity, never selecting it)
  - Seed notation format: `{PlayoffRank}{Conference[0].upper()}` — e.g., `12E` for 12th seed East, `3W` for 3rd seed West. Adjacent seed ordinals in log lines use `seed ± 1` rendered as an ordinal (e.g., seed 12 → `11th` above, `13th` below). When there is no adjacent seed in a direction (seed 1 has none above; seed 15 has none below), display that slot as `"n/a above"` or `"n/a below"` respectively

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

Skipped game (both teams eliminated):
```
[stake-filter] MEM @ SAS — skipped: neither team has a stake
  MEM: seed 12E, 8.0 GB from 11th (above), 3.0 ahead of 13th (below), 6 remaining → eliminated
  SAS: seed 14W, 12.0 GB from 13th (above), 5.5 ahead of 15th (below), 6 remaining → eliminated
```

Included game (one team has stake, one is eliminated):
```
[stake-filter] MIA @ CHI — included
  MIA: seed 8E, 2.0 GB from 7th (above), 1.5 ahead of 9th (below), 10 remaining → can be caught
  CHI: seed 11E, 9.0 GB from 10th (above), 2.0 ahead of 12th (below), 10 remaining → eliminated
```

Included game (both teams have stake):
```
[stake-filter] BOS @ CLE — included (both teams have stake)
  BOS: seed 1E, n/a above, 4.5 ahead of 2nd (below), 8 remaining → can be caught
  CLE: seed 2E, 4.5 GB from 1st (above), 3.0 ahead of 3rd (below), 8 remaining → can improve (both)
```

## Out of Scope

- No changes to `run_analysis()` signature or internals
- No changes to `scheduler.py`, `routers/`, or frontend
- No per-player stake weighting (this is a binary game-level gate)
